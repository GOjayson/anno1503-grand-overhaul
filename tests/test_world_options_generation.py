"""Compiled start-route decisions; no game process, native commit or UI input."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from anno1503_overhaul.world_options import PRIVATE
from anno1503_overhaul.world_options_menu import apply_menu
from test_world_options_menu import native_compiler


def exported(source, name):
    start = source.index('__declspec(dllexport) int __cdecl ' + name + '(')
    brace = source.index('{', start)
    at, depth = brace + 1, 1
    while depth:
        depth += (source[at] == '{') - (source[at] == '}')
        at += 1
    return source[start:at]


DRIVER = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifndef _WIN32
#define __declspec(x)
#define __cdecl
#endif
typedef uintptr_t HWND;
static unsigned char frameBytes[0xc7544],pageBytes[0x21b8],unchanged[0xc7544];
static int selection,choice,accepted,choosers,dialogs,finished,errors,classifications,argErrors,pending=77;
static int prepares,bindings;
static const char*wsMenuSetupResetMessage="Reset the game setup";
static int WorldSettingsRestoreNativeSetup(void){return 1;}
static HWND GetActiveWindow(void){return 123;}
static void WorldSettingsFinishAttempt(int success){if(success)argErrors++;finished++;pending=0;}
static void reportGenerationFailure(const char*message){if(!message||!message[0])argErrors++;errors++;}
int WorldSettingsClassifyDirectSelection(const char*name,uint32_t capacity,const unsigned char*digest){
 classifications++;if(name!=(const char*)frameBytes+0xc7430||capacity!=260||digest!=frameBytes+0xc7534)argErrors++;
 return selection;
}
static int choose(HWND owner){if(owner!=123)argErrors++;choosers++;return choice;}
static int custom(HWND owner,void*setup,void*frame){
 if(owner!=123||setup!=(void*)(uintptr_t)0x777||frame!=frameBytes)argErrors++;
 dialogs++;if(accepted>0){prepares++;bindings++;pending=1;}return accepted;
}
#define WS_MENU_GENERATION_CHOOSER(owner) choose(owner)
#define WS_MENU_OPEN_CUSTOM(owner,setup,frame) custom(owner,setup,frame)
#include "menu_generation.inc"
@EXPORTS@
int main(int argc,char**argv){
 if(argc!=7)return 9;
 selection=atoi(argv[2]);choice=atoi(argv[3]);accepted=atoi(argv[4]);int childrenPresent=atoi(argv[5]),nullFrame=atoi(argv[6]);
 void*children[1]={(void*)(uintptr_t)0x777};void**array=childrenPresent?children:NULL;
 memcpy(pageBytes+0x21b0,&array,sizeof array);memcpy(unchanged,frameBytes,sizeof unchanged);
 void*frame=nullFrame?NULL:frameBytes;
 int result=!strcmp(argv[1],"direct")?WorldSettingsBeforeDirectStart(pageBytes,frame):WorldSettingsBeforeStart((void*)(uintptr_t)0x777,frame);
 int commits=result==2,native=result>0;
 printf("{\"result\":%d,\"chooser\":%d,\"dialog\":%d,\"finish\":%d,\"errors\":%d,\"classifications\":%d,\"argument_errors\":%d,\"pending\":%d,\"prepares\":%d,\"bindings\":%d,\"custom_commits\":%d,\"native_starts\":%d,\"setup_unchanged\":%d}\n",
  result,choosers,dialogs,finished,errors,classifications,argErrors,pending,prepares,bindings,commits,native,!memcmp(unchanged,frameBytes,sizeof unchanged));
 return 0;
}
'''


class NativeGenerationRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='anno-generation-routes-')
        folder = Path(cls.temporary.name)
        files = {PRIVATE + name: (ROOT / 'legacy/world_settings' / PRIVATE / name).read_bytes()
                 for name in ('WorldSettings.c', 'world_menu_preview.inc')}
        apply_menu(files)
        menu = files[PRIVATE + 'WorldSettings.c'].decode()
        exports = '\n'.join(exported(menu, name) for name in
            ('WorldSettingsBeforeStart', 'WorldSettingsBeforeDirectStart'))
        (folder / 'menu_generation.inc').write_bytes(files[PRIVATE + 'menu_generation.inc'])
        source = folder / 'routes.c'
        source.write_text(DRIVER.replace('@EXPORTS@', exports), encoding='utf-8')
        cls.exe = folder / ('routes.exe' if os.name == 'nt' else 'routes')
        result = subprocess.run([*native_compiler(), '-std=c11', '-O2', '-Wall', '-Wextra',
            '-Werror', '-Wno-misleading-indentation', str(source), '-o', str(cls.exe)],
            capture_output=True, text=True, timeout=90)
        if result.returncode:
            raise AssertionError('Actual start-route fixture failed to compile:\n' + result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def observed(self, route, selection, choice=2, accepted=1, children=1, null_frame=0):
        result = subprocess.run([str(self.exe), route, str(selection), str(choice), str(accepted),
            str(children), str(null_frame)], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value['argument_errors'], 0)
        self.assertEqual(value['setup_unchanged'], 1)
        return value

    def test_tutorial_campaign_and_scenario_use_untouched_native_route(self):
        # The exact existing classifier returns0 for every non-endless category.
        # No setup child is required on the fixed-flag tutorial/campaign route.
        for route in ('flag', 'direct'):
            with self.subTest(route=route):
                value = self.observed(route, 0, children=0)
                self.assertEqual((value['result'], value['native_starts'], value['custom_commits']), (1, 1, 0))
                self.assertEqual((value['chooser'], value['dialog'], value['prepares'], value['bindings']), (0, 0, 0, 0))
                self.assertEqual((value['finish'], value['pending'], value['errors']), (1, 0, 0))

    def test_original_game_clears_pending_options_without_staging_or_binding(self):
        for route in ('flag', 'direct'):
            with self.subTest(route=route):
                value = self.observed(route, 1, choice=1)
                self.assertEqual((value['result'], value['native_starts'], value['custom_commits']), (1, 1, 0))
                self.assertEqual((value['chooser'], value['dialog'], value['prepares'], value['bindings']), (1, 0, 0, 0))
                self.assertEqual((value['finish'], value['pending'], value['errors']), (1, 0, 0))

    def test_only_accepted_custom_world_requests_native_custom_commit(self):
        for route in ('flag', 'direct'):
            with self.subTest(route=route):
                value = self.observed(route, 1, choice=2)
                self.assertEqual((value['result'], value['native_starts'], value['custom_commits']), (2, 1, 1))
                self.assertEqual((value['chooser'], value['dialog'], value['prepares'], value['bindings']), (1, 1, 1, 1))
                self.assertEqual((value['finish'], value['pending'], value['errors']), (1, 1, 0))

    def test_back_close_or_failed_custom_dialog_cannot_start(self):
        for route in ('flag', 'direct'):
            for choice, accepted in ((0, 1), (7, 1), (2, 0), (2, -1)):
                with self.subTest(route=route, choice=choice, accepted=accepted):
                    value = self.observed(route, 1, choice=choice, accepted=accepted)
                    self.assertEqual((value['result'], value['native_starts'], value['custom_commits']), (0, 0, 0))
                    self.assertEqual((value['pending'], value['prepares'], value['bindings']), (0, 0, 0))

    def test_unknown_endless_source_is_refused_before_ui(self):
        for route in ('flag', 'direct'):
            with self.subTest(route=route):
                value = self.observed(route, -1)
                self.assertEqual((value['result'], value['chooser'], value['dialog'], value['errors']), (0, 0, 0, 1))
                self.assertEqual(value['pending'], 0)

    def test_missing_direct_setup_and_null_frame_do_not_open_ui_or_commit(self):
        for route, children, null_frame in (('direct', 0, 0), ('direct', 1, 1), ('flag', 1, 1)):
            with self.subTest(route=route, children=children, null_frame=null_frame):
                value = self.observed(route, 1, children=children, null_frame=null_frame)
                self.assertEqual((value['result'], value['chooser'], value['dialog'], value['custom_commits']), (0, 0, 0, 0))


if __name__ == '__main__':
    unittest.main()
