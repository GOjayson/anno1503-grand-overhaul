"""Preset parser and menu staging checks, separate from actual game UI runs."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from anno1503_overhaul.world_options import PRIVATE, ROOT
from anno1503_overhaul.world_options_menu import apply_menu
from anno1503_overhaul.world_runtime_build import RuntimeBuildError


FROZEN = ROOT / 'legacy/world_settings'
NATIVE = ROOT / 'src/anno1503_overhaul/native/world_options'
FIELDS = ('difficulty', 'islandSize', 'islandCount', 'spacing', 'aiCount',
          'cultures', 'factions', 'startingMoney', 'startingFleet', 'aiDifficulty',
          'plantFertility', 'mineralFertility', 'worldSize', 'mapSeed',
          'startClimate', 'startIsland', 'cargoMode', 'cargoTools', 'cargoWood',
          'cargoFood', 'climateBalance', 'layoutStyle', 'disasters')

DRIVER = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif
typedef struct WSWorldSettings {
 uint32_t size;int32_t difficulty,islandSize,islandCount,spacing,aiCount;
 uint32_t cultures,factions;
 int32_t startingMoney,startingFleet,aiDifficulty,plantFertility,mineralFertility,worldSize;
 uint32_t mapSeed;
 int32_t startClimate,startIsland,cargoMode,cargoTools,cargoWood,cargoFood,climateBalance,layoutStyle,disasters;
} WSWorldSettings;
#define WS_WORLD_OPTIONS_GENERATOR "menu-codec-native-fixture-v1"
#include "menu_presets_codec.inc"
int main(int argc,char**argv){
#ifdef _WIN32
 _setmode(_fileno(stdin),_O_BINARY);_setmode(_fileno(stdout),_O_BINARY);
#endif
 if(argc<2)return 9;
 if(!strcmp(argv[1],"name"))return argc==3&&wsPresetNameValid(argv[2])?0:2;
 if(!strcmp(argv[1],"unsigned")){uint32_t value;if(argc!=3||!wsMenuUnsigned(argv[2],strlen(argv[2]),&value))return 2;printf("%u",value);return 0;}
 if(!strcmp(argv[1],"signed")){int32_t value;if(argc!=3||!wsMenuSigned(argv[2],strlen(argv[2]),&value))return 2;printf("%d",value);return 0;}
 WSWorldSettings value={.size=sizeof value,.difficulty=2,.islandSize=4,.islandCount=24,.spacing=16,.aiCount=3,
  .cultures=255,.factions=3,.startingMoney=100000,.startingFleet=1,.aiDifficulty=3,.plantFertility=3,.mineralFertility=2,
  .worldSize=2048,.mapSeed=UINT32_MAX,.startClimate=-1,.startIsland=127,.cargoMode=1,.cargoTools=400,.cargoWood=0,.cargoFood=0,
  .climateBalance=3,.layoutStyle=2,.disasters=1};
 char data[WS_PRESET_MAX_BYTES+1];uint32_t length=0;
 if(!strcmp(argv[1],"encode")){if(!wsPresetEncode(&value,data,WS_PRESET_MAX_BYTES,&length))return 8;fwrite(data,1,length,stdout);return 0;}
 if(strcmp(argv[1],"decode"))return 9;
 length=(uint32_t)fread(data,1,sizeof data,stdin);
 WSWorldSettings before;memset(&before,0xa5,sizeof before);memcpy(&value,&before,sizeof value);
 if(!wsPresetDecode(data,length,&value)){if(memcmp(&before,&value,sizeof value))return 7;fputs("unchanged",stdout);return 2;}
 printf("{\"size\":%u",value.size);
 for(size_t i=0;i<sizeof(wsPresetFields)/sizeof(wsPresetFields[0]);i++){
  const WSMenuPresetField*f=&wsPresetFields[i];uint32_t u;int32_t s;memcpy(&u,(char*)&value+f->offset,sizeof u);memcpy(&s,&u,sizeof s);
  if(f->unsignedValue)printf(",\"%s\":%u",f->name,u);else printf(",\"%s\":%d",f->name,s);
 }
 puts("}");return 0;
}
'''


class MenuStagingTests(unittest.TestCase):
    def inputs(self):
        return {PRIVATE + name: (FROZEN / PRIVATE / name).read_bytes()
                for name in ('WorldSettings.c', 'world_menu_preview.inc')}

    def test_stages_menu_without_changing_imported_inputs(self):
        files = self.inputs()
        before = {name: hashlib.sha256(value).hexdigest() for name, value in files.items()}
        apply_menu(files)
        self.assertEqual(set(files) - set(before), {PRIVATE + name for name in
            ('menu_values.inc', 'menu_create.inc', 'menu_preview.inc', 'menu_presets_codec.inc')})
        self.assertEqual(before, {name: hashlib.sha256((FROZEN / name).read_bytes()).hexdigest()
                                  for name in before})
        for name in before:
            self.assertNotEqual(before[name], hashlib.sha256(files[name]).hexdigest())

    def test_refuses_changed_staging_anchors(self):
        files = self.inputs()
        files[PRIVATE + 'WorldSettings.c'] = files[PRIVATE + 'WorldSettings.c'].replace(
            b'WS_MENU_WIDTH=1120', b'WS_MENU_WIDTH=1121')
        with self.assertRaises(RuntimeBuildError):
            apply_menu(files)


class NativePresetCodecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        local_zig = ROOT / '.local/toolchain/ziglang/zig.exe'
        if os.name == 'nt' and local_zig.is_file():
            compiler = [str(local_zig), 'cc']
        else:
            found = shutil.which('cc') or shutil.which('gcc') or shutil.which('clang')
            if not found:
                raise unittest.SkipTest('A local C compiler is required for native preset parser fixtures.')
            compiler = [found]
        cls.temporary = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.temporary.name)
        cls.addClassCleanup(cls.temporary.cleanup)
        source = cls.directory / 'preset_codec_fixture.c'
        source.write_text(DRIVER, encoding='utf-8')
        cls.exe = cls.directory / ('preset_codec_fixture.exe' if os.name == 'nt' else 'preset_codec_fixture')
        result = subprocess.run([*compiler, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                                 '-I', str(NATIVE), str(source), '-o', str(cls.exe)],
                                capture_output=True, text=True, timeout=90)
        if result.returncode:
            raise AssertionError('Native preset fixture compilation failed:\n' + result.stderr)
        cls.encoded = cls.call('encode').stdout

    @classmethod
    def call(cls, *args, data=None):
        return subprocess.run([str(cls.exe), *args], input=data, capture_output=True,
                              timeout=10)

    def decoded(self, data=None):
        result = self.call('decode', data=self.encoded if data is None else data)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def assert_rejected(self, data):
        result = self.call('decode', data=data)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, b'unchanged')

    def test_round_trip_keeps_every_setting_and_unsigned_seed(self):
        value = self.decoded()
        self.assertEqual(set(value), {'size', *FIELDS})
        self.assertEqual(value['size'], 96)
        self.assertEqual(value['mapSeed'], 4294967295)
        self.assertEqual(value['startClimate'], -1)
        self.assertEqual(value['startIsland'], 127)
        self.assertEqual(value['climateBalance'], 3)
        self.assertEqual(value['layoutStyle'], 2)
        self.assertEqual(value['cargoTools'], 400)
        self.assertEqual(value['disasters'], 1)
        self.assertEqual(value, self.decoded(self.encoded.replace(b'\n', b'\r\n')))

    def test_seed_zero_and_high_bit_values_are_not_signed_or_replaced(self):
        for seed in (0, 1, 2147483648, 4294967295):
            with self.subTest(seed=seed):
                data = self.encoded.replace(b'mapSeed=4294967295', ('mapSeed=' + str(seed)).encode())
                self.assertEqual(self.decoded(data)['mapSeed'], seed)

    def test_rejects_invalid_numbers_and_incomplete_or_extra_schema(self):
        cases = [self.encoded[:-1], self.encoded + b'extra\n', b'\0' + self.encoded,
                 self.encoded.replace(b'PRESET 1\n', b'PRESET 2\n'),
                 self.encoded.replace(b'menu-codec-native-fixture-v1', b'another-generator'),
                 self.encoded.replace(b'mapSeed=4294967295', b'mapSeed=4294967296'),
                 self.encoded.replace(b'mapSeed=4294967295', b'mapSeed=-1'),
                 self.encoded.replace(b'mapSeed=4294967295', b'mapSeed=+1'),
                 self.encoded.replace(b'mapSeed=4294967295', b'mapSeed= 1'),
                 self.encoded.replace(b'cargoTools=400\n', b'cargoTools=400\ncargoTools=1\n'),
                 self.encoded.replace(b'cargoTools=400\n', b''),
                 self.encoded.replace(b'disasters=1', b'unknown=1'),
                 self.encoded.replace(b'startIsland=127', b'startIsland=2147483648'),
                 b'x' * 4097]
        for data in cases:
            with self.subTest(data=data[:70]):
                self.assert_rejected(data)

    def test_rejects_every_truncated_complete_field_boundary(self):
        for at, character in enumerate(self.encoded):
            if character == 10 and at + 1 < len(self.encoded):
                self.assert_rejected(self.encoded[:at + 1])

    def test_unsigned_and_signed_decimal_boundaries(self):
        for number in ('0', '1', '2147483648', '4294967295'):
            self.assertEqual(self.call('unsigned', number).stdout.decode(), number)
        for number in ('', '+1', '-1', '4294967296', '1x', ' 1', '1 ', '00000000000'):
            self.assertEqual(self.call('unsigned', number).returncode, 2)
        for number in ('-2147483648', '-1', '0', '2147483647'):
            self.assertEqual(self.call('signed', number).stdout.decode(), number)
        for number in ('-2147483649', '2147483648', '--1', '-', '+1'):
            self.assertEqual(self.call('signed', number).returncode, 2)

    def test_preset_names_cannot_leave_the_local_folder_or_use_device_aliases(self):
        for name in ('My world', 'North-123', 'Mixed_Seed_0', 'x' * 32):
            self.assertEqual(self.call('name', name).returncode, 0)
        for name in ('', 'x' * 33, '../other', '..', 'x.awp', 'C:other', 'a/b', 'a\\b',
                     ' Leading', 'Trailing ', 'con', 'NUL', 'COM1', 'lpt9', 'a\nname'):
            self.assertEqual(self.call('name', name).returncode, 2)


if __name__ == '__main__':
    unittest.main()
