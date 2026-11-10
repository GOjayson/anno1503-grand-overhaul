"""Owned land-unit vision adapters on an independent synthetic memory graph.

The existing native fixture is included unchanged, then extended with owned
land lists. These tests do not execute Anno or certify rendering/gameplay.
"""
import ctypes as C
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_world_visibility_native import FIXTURE, NATIVE, ROOT


LAND_FIXTURE = r'''
#ifdef _WIN32
static unsigned char landUnits[WS_VISIBILITY_UNIT_LIMIT+1u][0x178],landNodes[WS_VISIBILITY_UNIT_LIMIT+1u][24];
static const uint32_t landClasses[6]={0xeb5f0u,0xeeff8u,0xef3a8u,0xef750u,0xefb00u,0xefeb8u};
static void landPrepareUnit(uint32_t n,uint32_t kind,float x,float z){
 unsigned char*u=landUnits[n];memset(u,0,sizeof landUnits[n]);ptr(u,moduleBytes+landClasses[kind]);
 ptr(u+0x28,worldBytes);ptr(u+0x30,islandBytes);ptr(u+0xb8,humanBytes);ptr(u+0xf0,enemyBytes);
 /* The thief's unrelated F0 owner must not override its human B8 controller. */
 wsPut16(u+0x18,500);memcpy(u+0x40,&x,4);memcpy(u+0x48,&z,4);
 ptr(moduleBytes+landClasses[kind]+0x138,moduleBytes+(kind<4u?0xaf00u:0x27360u));
 memset(landNodes[n],0,24);ptr(landNodes[n]+0x10,u);
}
static void landList(uint32_t count){
 for(uint32_t n=0;n<count;n++){ptr(landNodes[n],n?landNodes[n-1]:0);ptr(landNodes[n]+8,n+1u<count?landNodes[n+1]:0);}
 ptr(humanBytes+0x2b8,count?landNodes[0]:0);ptr(humanBytes+0x2c0,count?landNodes[count-1u]:0);
}
__declspec(dllexport) int land_unit_case(uint32_t which){
 prepare(0x1000,0);memset(landUnits,0,sizeof landUnits);memset(landNodes,0,sizeof landNodes);
 WSVisibilityWorld view;if(!wsVisibilityWorldRead(worldBytes,&view))return 1;
 WSVisibilityDrawContext*c=(WSVisibilityDrawContext*)calloc(1,sizeof(*c));if(!c)return 2;
 uint32_t kind=which<6u?which:0;landPrepareUnit(0,kind,24,24);landList(1);
 int want=1,ok=1;uint32_t units=1;
 if(which==6){wsPut16(landUnits[0]+0xc,2);units=0;}
 if(which==7){wsPut16(landUnits[0]+0xc,4);units=0;}
 if(which==8){wsPut16(landUnits[0]+0xc,8);units=0;}
 if(which==9){wsPut16(landUnits[0]+0xc,0x80);units=0;}
 if(which==10){wsPut16(landUnits[0]+0x18,0);units=0;}
 if(which==11){wsPut16(landUnits[0]+0x18,0xffff);units=0;}
 if(which==12){ptr(landUnits[0]+0xb8,enemyBytes);units=0;}
 if(which==13){ptr(landUnits[0]+0x28,enemyBytes);units=0;}
 if(which==14){ptr(landUnits[0]+0x30,enemyBytes);units=0;}
 if(which==15){float x=32;memcpy(landUnits[0]+0x40,&x,4);units=0;}
 if(which==16){wsPut32(landUnits[0]+0x40,0x7fc00000);units=0;}
 if(which==17){wsPut32(landUnits[0]+0x48,0x7f800000);units=0;}
 if(which==18){ptr(landUnits[0],moduleBytes+0xf0ed0);units=0;}
 if(which==20)wsPut16(landUnits[0]+0xc,1);
 if(which==21){ptr(moduleBytes+landClasses[0]+0x38,moduleBytes+0x1234);want=0;}
 if(which==22){ptr(landNodes[0],landNodes[0]);want=0;}
 if(which==23){ptr(humanBytes+0x2c0,landNodes[1]);want=0;}
 if(which==24){ptr(landNodes[0]+8,landNodes[0]);want=0;}
 if(which==25){landPrepareUnit(1,1,25,25);landList(2);ptr(landNodes[1]+0x10,landUnits[0]);want=0;}
 if(which==26||which==27){
  uint32_t count=WS_VISIBILITY_UNIT_LIMIT+(which==26?1u:0u);
  for(uint32_t n=0;n<count;n++)landPrepareUnit(n,n%6u,24,24);landList(count);units=count;want=which==27;
 }
 if(which==28){landList(0);units=0;}
 if(which==30){ptr(landNodes[0]+0x10,0);want=0;}
 void*bad=0;
 if(which==31){bad=VirtualAlloc(0,4096,MEM_COMMIT|MEM_RESERVE,PAGE_NOACCESS);if(!bad){free(c);return 3;}ptr(humanBytes+0x2b8,bad);ptr(humanBytes+0x2c0,bad);want=0;}
 if(which==33){
  for(uint32_t n=0;n<8;n++)landPrepareUnit(n,n%6u,24,24);landList(8);wsPut16(landUnits[6]+0xc,0x80);ptr(landUnits[7]+0xb8,enemyBytes);units=6;
 }
 int result=wsVisibilityContextRead(&view,c);
 if(result!=want)ok=0;
 if(result&&(c->visionCount!=units+1u||!wsVisibilityInSight(c,128,128)))ok=0;
 if(result&&units&&which!=27&&!wsVisibilityInSight(c,24,24))ok=0;
 if(result&&!units&&wsVisibilityInSight(c,24,24))ok=0;
 if(which==32){c->visionCount=WS_VISIBILITY_VISION_LIMIT;if(wsVisibilityUnitObserversRead(c))ok=0;}
 if(which==34||which==35){
  WSVisibilityChartReadView chart;
  if(!wsVisibilityChartReadBegin(&view,&chart))ok=0;
  else{
   if(!result||wsVisibilityChartPoint(&view,24,24)||!wsVisibilityChartMarkContext(c)||!wsVisibilityChartPoint(&view,24,24)||wsVisibilityChartPoint(&view,250,16))ok=0;
   if(which==35){wsPut16(landUnits[0]+0x18,0);if(!wsVisibilityContextRead(&view,c)||c->visionCount!=1u||wsVisibilityInSight(c,24,24)||!wsVisibilityChartPoint(&view,24,24))ok=0;}
   wsVisibilityChartReadEnd(&chart);
  }
 }
 if(bad)VirtualFree(bad,0,MEM_RELEASE);free(c);return ok?0:100+(int)which;
}
#endif
'''


@unittest.skipUnless(os.name == 'nt', 'Land-unit snapshots use real Windows memory guards.')
class LandUnitVisibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        zig = ROOT / '.local/toolchain/ziglang/zig.exe'
        if not zig.is_file():
            raise unittest.SkipTest('Land-unit fixtures need the reviewed local Zig toolchain.')
        cls.temp = tempfile.TemporaryDirectory(prefix='anno-land-visibility-')
        folder = Path(cls.temp.name)
        source, output = folder / 'land.c', folder / 'land.dll'
        source.write_text(FIXTURE + LAND_FIXTURE, encoding='utf-8')
        result = subprocess.run([str(zig), 'cc', '-target', 'x86_64-windows-gnu',
            '-std=c11', '-shared', '-O2', '-Wall', '-Wextra', '-Werror',
            '-I', str(NATIVE), str(source), '-o', str(output)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf-8', errors='replace')
        if result.returncode:
            cls.temp.cleanup()
            raise AssertionError(result.stdout)
        cls.lib = C.CDLL(str(output))
        cls.lib.land_unit_case.argtypes = [C.c_uint32]

    @classmethod
    def tearDownClass(cls):
        import _ctypes
        _ctypes.FreeLibrary(cls.lib._handle)
        del cls.lib
        cls.temp.cleanup()

    def check_cases(self, cases):
        for case in cases:
            with self.subTest(case=case):
                self.assertEqual(self.lib.land_unit_case(case), 0)

    def test_scout_and_all_six_military_classes_add_stationary_or_moving_vision(self):
        self.check_cases((*range(6), 19, 20))

    def test_dead_embarked_hidden_foreign_and_invalid_coordinates_preserve_ship_vision(self):
        self.check_cases((*range(6, 14), 16, 17, 18))

    def test_wrong_island_and_off_island_units_do_not_reveal_land(self):
        self.check_cases((14, 15))

    def test_corrupt_class_and_list_cycles_duplicates_and_unreadable_nodes_refuse(self):
        self.check_cases((*range(21, 27), 30, 31))

    def test_adapter_bound_accepts_4096_units_and_empty_lists(self):
        self.check_cases((27, 28))

    def test_mixed_exclusions_and_vision_capacity(self):
        self.check_cases((32, 33))

    def test_scout_integrates_with_permanent_terra_charting(self):
        self.check_cases((34,))

    def test_dead_scout_removes_current_sight_but_preserves_charted_land(self):
        self.check_cases((35,))


if __name__ == '__main__':
    unittest.main()
