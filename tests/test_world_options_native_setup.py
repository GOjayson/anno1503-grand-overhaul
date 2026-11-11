"""Actual staged Start/End functions with exact bounded native-field rollback."""
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
from anno1503_overhaul.world_options import PRIVATE, apply_options
from anno1503_overhaul.world_runtime_build import SOURCE_PREFIX, _verified_sources
from test_world_options_menu import c_function, native_compiler
from test_world_options_generation import exported
from test_world_options_disaster_memory import POLICY_STRUCT


DRIVER = r'''
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
@SETTINGS@
typedef WSWorldSettings WSSettings;
typedef struct DialogState {
 HWND window;unsigned char*frame;void*setup;WSSettings settings,previewSettings;
 int previewValid,result,done;
} DialogState;
static unsigned char*frameMemory,*setupMemory;static int pending,stageCalls,aiCalls,factionCalls,failAI,failFaction,messages;
static char statusText[512];
static uint32_t wsNativeActive=73,wsFactionsExpected,wsNativeFactions;
static int wsNativeExpected,wsNativeChecked,wsProfilesExpected;
static void*wsNativeWorld;static LONG wsProfileStatus;static char wsProfileError[512];
static void WorldSettingsFinishAttempt(int success){if(!success)pending=0;}
static int WorldSettingsIsActive(void){return pending;}
static void WorldSettingsAIProfileAttemptFinished(int success){(void)success;}
static void WorldSettingsResetFactionActivity(void){}
static void WorldSettingsFinishDisasterAttempt(int success){(void)success;}
static void invalidatePreview(DialogState*d){d->previewValid=0;}
static void status(DialogState*d,const char*text){(void)d;snprintf(statusText,sizeof statusText,"%s",text);}
static void reportGenerationFailure(const char*text){messages++;snprintf(statusText,sizeof statusText,"%s",text);}
static int collect(DialogState*d){(void)d;return 1;}
static int WorldSettingsEnginePatchStatus(void){return 173;}
static int stage(const WSSettings*s,const char*selected,char*path,uint32_t pathCap,char*error,uint32_t errorCap,void*context){
 (void)s;(void)selected;(void)error;(void)errorCap;(void)context;stageCalls++;snprintf(path,pathCap,"fixture.scp");pending=1;return 1;
}
static int(*prepareBackend)(const WSSettings*,const char*,char*,uint32_t,char*,uint32_t,void*)=stage;
static int WorldSettingsBindStockAIProfiles(void*setup,int32_t difficulty,int32_t count,char*error,uint32_t cap){
 (void)difficulty;(void)count;aiCalls++;memset((unsigned char*)setup+0x2280,0x13,7);memset((unsigned char*)setup+0x2288,0x47,7*168);
 if(failAI){snprintf(error,cap,"Injected AI binding failure");return 0;}return 1;
}
static int wsBindNativeFactionOptions(unsigned char*frame,uint32_t factions,int32_t disasters){
 (void)factions;(void)disasters;factionCalls++;frame[0xc7a78]=0;frame[0xc7a79]=0;return !failFaction;
}
static void WorldSettingsExpectAIProfiles(int32_t count,uint32_t factions,int32_t mode){(void)count;(void)factions;(void)mode;}
static void WorldSettingsExpectDisasterOptions(const WSSettings*s){(void)s;}
static void WorldSettingsExpectFactionActivity(uint32_t f,int32_t a,int32_t b,int32_t c){(void)f;(void)a;(void)b;(void)c;}
static DWORD attributes(const char*path){(void)path;return FILE_ATTRIBUTE_NORMAL;}
static BOOL noDestroy(HWND window){(void)window;return TRUE;}
static UINT_PTR noTimer(HWND w,UINT_PTR id,UINT timeout,TIMERPROC callback){(void)w;(void)id;(void)timeout;(void)callback;return 1;}
static HWND activeWindow(void){return (HWND)(uintptr_t)1;}
static int noMessage(HWND w,const char*text,const char*title,UINT flags){(void)w;(void)title;(void)flags;reportGenerationFailure(text);return IDOK;}
#define GetFileAttributesA(path) attributes(path)
#define DestroyWindow(window) noDestroy(window)
#define SetTimer(w,id,timeout,callback) noTimer(w,id,timeout,callback)
#define GetActiveWindow() activeWindow()
#define MessageBoxA(w,text,title,flags) noMessage(w,text,title,flags)
#define WS_PREVIEW_TIMER 1
static const char*noBackend="No backend";
#define WS_MENU_FRAME_MODULE() frameMemory
#include "menu_native_setup.inc"
static int choose(HWND owner){(void)owner;return 1;}
static int custom(HWND owner,void*setup,void*frame){(void)owner;(void)setup;(void)frame;return 0;}
int WorldSettingsClassifyDirectSelection(const char*p,uint32_t n,const unsigned char*d){(void)p;(void)n;(void)d;return 1;}
#define WS_MENU_GENERATION_CHOOSER(owner) choose(owner)
#define WS_MENU_OPEN_CUSTOM(owner,setup,frame) custom(owner,setup,frame)
#include "menu_generation.inc"
@FUNCTIONS@
int main(int argc,char**argv){
 if(argc!=2)return 9;int mode=atoi(argv[1]);
 frameMemory=VirtualAlloc(NULL,0xc8000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
 setupMemory=VirtualAlloc(NULL,0x3000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
 if(!frameMemory||!setupMemory)return 8;memset(frameMemory,0xa5,0xc8000);memset(setupMemory,0x6d,0x3000);
 void*vt=frameMemory+0x1000;memcpy(setupMemory,&vt,8);frameMemory[0xc7a78]=frameMemory[0xc7a79]=1;
 unsigned char*frameBefore=malloc(0xc8000),*setupBefore=malloc(0x3000);if(!frameBefore||!setupBefore)return 8;
 memcpy(frameBefore,frameMemory,0xc8000);memcpy(setupBefore,setupMemory,0x3000);
 DialogState d={0};d.window=(HWND)(uintptr_t)1;d.frame=frameMemory;d.setup=setupMemory;d.previewValid=1;
 d.settings.size=sizeof d.settings;d.settings.factions=3;d.settings.disasters=1;d.previewSettings=d.settings;
 failAI=mode==1;failFaction=mode==2;start(&d);
 int outcome=-1,staleActive=-1,original=-1,changedBefore=-1;
 if(mode==3)outcome=WorldSettingsEndNativeWorldStart(73,0);
 if(mode==4)outcome=WorldSettingsEndNativeWorldStart(73,1);
 if(mode==5){outcome=WorldSettingsEndNativeWorldStart(72,0);staleActive=wsMenuNativeSetup.active;WorldSettingsEndNativeWorldStart(73,0);}
 if(mode==6){void*other=frameMemory+0x1008;memcpy(setupMemory,&other,8);changedBefore=setupMemory[0x2280];outcome=WorldSettingsFinishNativeSetup(0);}
 if(mode==7){DWORD prior;VirtualProtect(setupMemory,0x3000,PAGE_READONLY,&prior);changedBefore=setupMemory[0x2280];outcome=WorldSettingsFinishNativeSetup(0);VirtualProtect(setupMemory,0x3000,prior,&prior);}
 if(mode!=4)original=WorldSettingsBeforeStart(setupMemory,frameMemory);
 else WorldSettingsRestoreNativeSetup();
 printf("{\"setup_same\":%d,\"frame_same\":%d,\"gap_same\":%d,\"active\":%d,\"poisoned\":%d,\"stage_calls\":%d,\"ai_calls\":%d,\"faction_calls\":%d,\"native_result\":%d,\"original_result\":%d,\"stale_active\":%d,\"messages\":%d,\"changed_fields_preserved_on_refusal\":%d}\n",
  !memcmp(setupMemory,setupBefore,0x3000),!memcmp(frameMemory,frameBefore,0xc8000),setupMemory[0x2287]==setupBefore[0x2287],
  wsMenuNativeSetup.active,wsMenuNativeSetup.poisoned,stageCalls,aiCalls,factionCalls,outcome,original,staleActive,messages,changedBefore<0||setupMemory[0x2280]==changedBefore);
 free(frameBefore);free(setupBefore);VirtualFree(setupMemory,0,MEM_RELEASE);VirtualFree(frameMemory,0,MEM_RELEASE);return 0;
}
'''


@unittest.skipUnless(os.name == 'nt', 'Requires actual Windows allocation/identity checks.')
class NativeSetupRollback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        files = apply_options({n.removeprefix(SOURCE_PREFIX): (ROOT / n).read_bytes()
                               for n in _verified_sources(ROOT)})
        menu = files[PRIVATE + 'WorldSettings.c'].decode()
        ai = files[PRIVATE + 'world_ai.c'].decode()
        cls.temporary = tempfile.TemporaryDirectory(prefix='anno-native-setup-')
        folder = Path(cls.temporary.name)
        for name in ('menu_generation.inc', 'menu_native_setup.inc'):
            (folder / name).write_bytes(files[PRIVATE + name])
        source = folder / 'native_setup.c'
        settings = POLICY_STRUCT.split('#include "disaster_policy.inc"', 1)[0]
        body = DRIVER.replace('@SETTINGS@', settings).replace('@FUNCTIONS@', '\n'.join((
            c_function(menu, 'start(DialogState*d)'), exported(menu, 'WorldSettingsBeforeStart'),
            exported(ai, 'WorldSettingsEndNativeWorldStart'))))
        source.write_text(body, encoding='utf-8')
        cls.exe = folder / 'native_setup.exe'
        result = subprocess.run([*native_compiler(), '-std=c11', '-O2', '-Wall', '-Wextra',
            '-Werror', '-Wno-misleading-indentation', str(source), '-o', str(cls.exe)],
            capture_output=True, text=True, timeout=90)
        if result.returncode:
            raise AssertionError('Actual native-setup fixture failed to compile:\n' + result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def observed(self, mode):
        result = subprocess.run([str(self.exe), str(mode)], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value['stage_calls'], 1)
        self.assertEqual(value['gap_same'], 1)
        return value

    def test_partial_ai_or_faction_failure_restores_original_before_native_choice(self):
        for mode in (1, 2):
            with self.subTest(mode=mode):
                value = self.observed(mode)
                self.assertEqual((value['setup_same'], value['frame_same'], value['active'], value['poisoned']), (1, 1, 0, 0))
                self.assertEqual(value['original_result'], 1)
                self.assertEqual(value['faction_calls'], mode - 1)

    def test_failed_native_scope_restores_all_bounded_fields(self):
        value = self.observed(3)
        self.assertEqual((value['native_result'], value['setup_same'], value['frame_same'], value['active']), (0, 1, 1, 0))
        self.assertEqual(value['original_result'], 1)

    def test_successful_commit_discards_snapshot_without_reverting_consumed_setup(self):
        value = self.observed(4)
        self.assertEqual((value['native_result'], value['setup_same'], value['frame_same'], value['active'], value['poisoned']), (1, 0, 0, 0, 0))

    def test_stale_native_scope_cannot_discard_or_restore_newer_snapshot(self):
        value = self.observed(5)
        self.assertEqual((value['native_result'], value['stale_active'], value['setup_same'], value['frame_same'], value['active']), (0, 1, 1, 1, 0))

    def test_changed_type_or_unwritable_storage_refuses_original_without_restoring(self):
        for mode in (6, 7):
            with self.subTest(mode=mode):
                value = self.observed(mode)
                self.assertEqual((value['native_result'], value['original_result'], value['poisoned']), (0, 0, 1))
                self.assertEqual(value['changed_fields_preserved_on_refusal'], 1)
                self.assertGreater(value['messages'], 0)


if __name__ == '__main__':
    unittest.main()
