"""Mineral occurrence parent and neutral-symbol isolation fixtures.

Synthetic native-memory graphs exercise the public runtime with real Windows
memory guards. The draw spy translates the audited native discovery/quantity
branch; these checks do not run Anno or establish GPU presentation.
"""
import ctypes as C
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_world_visibility_native import FIXTURE, NATIVE, ROOT

EXTRA=r'''

__declspec(dllexport) int ore_parent_case(uint32_t which,uint32_t fast){
 char error[128];prepare(wsVisibilityEncode(0,0),1);
 ptr(actorBytes,moduleBytes+0xf58e8u);ptr(actorBytes+0x10,islandBytes);
 float x=20.0f,z=20.0f;memcpy(actorBytes+0x20,&x,4);memcpy(actorBytes+0x28,&z,4);
 if(!WorldSettingsVisibilityWorldLoaded(worldBytes,error,sizeof error)||!wsChartCoreMark(&wsChartActive,20,20,20,20))return 1;
 WSVisibilityWorld v;WSVisibilityDrawContext context;
 ptr(worldBytes+0x200,catalogueBytes);ptr(catalogueBytes,moduleBytes+0x20300u);ptr(moduleBytes+0x20300u+0xe8,moduleBytes+0xb4d0u);
 if(!wsVisibilityWorldRead(worldBytes,&v)||!wsVisibilityContextRead(&v,&context))return 2;
 if(fast&&!wsVisibilityFastPrepare(&context,drawRendererBytes))return 3;
 WSVisibilityChartReadView read;int reading=0;
 if(fast){if(!wsVisibilityChartReadBegin(&v,&read)){wsVisibilityFastRelease(&context);return 8;}reading=1;}
 wsVisibilityDrawContext=fast?&context:0;
 int expected=which==0, result=0;
 if(which==1)ptr(actorBytes+0x10,worldBytes);
 if(which==2)ptr(worldBytes+0x6640,0);
 if(which==3)ptr(islandBytes+0x38,actorBytes);
 if(which==4)ptr(islandBytes,moduleBytes+0x123);
 if(which==5){x=32.0f;memcpy(actorBytes+0x20,&x,4);}
 if(which==6){z=32.0f;memcpy(actorBytes+0x28,&z,4);}
 if(which==7){wsPut32(actorBytes+0x20,0x7fc00000u);}
 if(which==8){wsPut16(islandBytes+8,24);}
 if(which==9){wsPut16(islandBytes+12,4);}
 if(which==10){ptr(moduleBytes+0xf58e8u+0x38,moduleBytes+0x19371u);}
 if(which==11){wsChartCoreFree(&wsChartActive);if(!wsVisibilityChartEnsure(&v))result=4;}
 uint32_t before=spyResidentCalls;visibilityReadChecks=0;
 uintptr_t value=result?0:WorldSettingsVisibilityDispatchOccurrence100(actorBytes,71,tableBytes,0x12345678u);
 uint32_t checks=visibilityReadChecks;
 if(!result&&((value!=0)!=expected||spyResidentCalls!=before+(uint32_t)expected||spyFailure))result=5;
 if(!result&&expected&&(value!=0x3345u||spyOccurrenceFlags!=0x12345678u))result=6;
 /* One actor span plus bounded chart/memory guards; parent fast adapter adds
  * no per-field operating-system query to the current draw's proved span. */
 if(!result&&fast&&expected&&checks>2u)result=7;
 wsVisibilityDrawContext=0;if(reading)wsVisibilityChartReadEnd(&read);wsVisibilityFastRelease(&context);return result;
}


__declspec(dllexport) int ore_submit_case(uint32_t which){
 prepare(wsVisibilityEncode(0,0),1);chartFixtureHouse(20,20);
 float sightNear=22.0f,sightFar=128.0f;memcpy(humanShip+0x28,&sightNear,4);memcpy(humanShip+0x30,&sightNear,4);
 if(!chartFixtureObserve(500))return 1;
 memcpy(humanShip+0x28,&sightFar,4);memcpy(humanShip+0x30,&sightFar,4);
 WSVisibilityWorld v;WSVisibilityDrawContext c;
 if(!wsVisibilityWorldRead(worldBytes,&v)||!wsVisibilityContextRead(&v,&c)||!wsVisibilityFastPrepare(&c,drawRendererBytes))return 2;
 if(!wsVisibilityChartReadBegin(&v,&c.chart)){wsVisibilityFastRelease(&c);return 3;}
 wsVisibilityDrawContext=&c;
 ptr(actorBytes,moduleBytes+0xf58e8);ptr(actorBytes+0x10,islandBytes);float p=20.0f;memcpy(actorBytes+0x20,&p,4);memcpy(actorBytes+0x28,&p,4);
 wsPut32(actorBytes+0x38,512000u);wsPut32(actorBytes+0x3c,1u);actorBytes[0x40]=0;worldBytes[0x6ee9]=1;
 ptr(moduleBytes+0xf63740+0x180,moduleBytes+0x49410);ptr(moduleBytes+0xf63740+0x188,moduleBytes+0x49bd0);
 oreBridgeMode=1;oreBridgeSlot=0x180;oreBridgeCaller=(uintptr_t)moduleBytes+0x725ee;oreBridgeMutate=which;oreBridgeEligible=oreBridgeNestedResult=0;
 float check[3]={20,0,20};int result=0;
 if(!wsVisibilityChartRememberedAt(&c,20,20)||WorldSettingsVisibilitySpriteVisible(check)){result=4;goto done;}
 int expected=which==0||which==1||which==4||which==12||which==13||which==14;
 if(which==1)wsPut32(actorBytes+0x3c,0u); /* HE native property5 allows charted neutral ore with activity1. */
 if(which==2){worldBytes[0x6ee9]=0;wsPut32(actorBytes+0x3c,0u);}
 if(which==3)wsPut32(actorBytes+0x38,0u);
 if(which==4){wsPut32(actorBytes+0x38,0u);actorBytes[0x40]=1;}
 if(which==5)oreBridgeCaller=(uintptr_t)moduleBytes+0xc538fu;
 if(which==6)oreBridgeSlot=0x188;
 if(which==7)memset(wsChartActive.bits,0,wsChartActive.bitBytes);
 if(which==12)oreBridgeCaller=(uintptr_t)moduleBytes+0x7145e;
 #ifdef HAS_ORE_SUBMIT
 WSVisibilityOreDrawScope sentinel={&c,actorBytes,islandBytes,drawRendererBytes};
 if(which==14)wsVisibilityOreDrawTLS=&sentinel;
 #endif
 if(which==17)ptr(tableBytes,moduleBytes+0xf63740u);
 uintptr_t value=WorldSettingsVisibilityDispatchOccurrence100(actorBytes,71,which==17?tableBytes:drawRendererBytes,0);
 if((value!=0)!=expected||spyStaticCalls!=(uint32_t)expected||spyFailure)result=5;
 if(!result&&which==13&&oreBridgeNestedResult)result=6;
 if(!result&&which==17&&oreBridgeScopeSeen)result=9;
 #ifdef HAS_ORE_SUBMIT
 if(!result&&wsVisibilityOreDrawTLS!=(which==14?&sentinel:0))result=7;
 wsVisibilityOreDrawTLS=0;
 #endif
 if(!result&&WorldSettingsVisibilityRenderStatic180(drawRendererBytes,quadBytes,7,11,0xc0,check))result=8;
 done:oreBridgeMode=0;wsVisibilityDrawContext=0;wsVisibilityChartReadEnd(&c.chart);wsVisibilityFastRelease(&c);return result;
}

'''

def _fixture():
 f=FIXTURE
 f=f.replace('static uintptr_t spyOccurrence(void*,uint32_t,void*,uint32_t);','''static uintptr_t spyOccurrence(void*,uint32_t,void*,uint32_t);
static uint32_t oreBridgeMode,oreBridgeSlot,oreBridgeEligible,oreBridgeMutate,oreBridgeNestedResult,oreBridgeNested,oreBridgeScopeSeen;
static uintptr_t oreBridgeCaller;
static void ptr(void*,void*);
#define WS_CHART_CALLER() oreBridgeCaller''')
 old='static uintptr_t spyOccurrence(void*actor,uint32_t time,void*renderer,uint32_t flags){spyOccurrenceFlags=flags;return spyResident(actor,time,renderer)+1;}'
 new=r'''static uintptr_t spyOccurrence(void*actor,uint32_t time,void*renderer,uint32_t flags){
 if(!oreBridgeMode){spyOccurrenceFlags=flags;return spyResident(actor,time,renderer)+1;}
 #ifdef HAS_ORE_SUBMIT
 oreBridgeScopeSeen=wsVisibilityOreDrawTLS!=0;
 #else
 oreBridgeScopeSeen=0;
 #endif
 /* Translated native71220 eligibility. The real engine instructions/quantity,
  * discovery fields and mode branch are not patched by the implementation. */
 if(!(wsU32((unsigned char*)actor+0x3c)&1u)&&!worldBytes[0x6ee9])return 0;
 if(!wsU32((unsigned char*)actor+0x38)&&!((unsigned char*)actor)[0x40])return 0;
 oreBridgeEligible++;float point[3];memcpy(point,(unsigned char*)actor+0x20,12);spyStaticPosition=point;
 if(oreBridgeMutate==13){
  unsigned char savedActor[sizeof actorBytes];memcpy(savedActor,actorBytes,sizeof savedActor);
  ptr(actorBytes,moduleBytes+0xee000u);ptr(actorBytes+0x20,worldBytes);ptr(actorBytes+0x270,humanBytes);
  float nestedAt=20.0f;memcpy(actorBytes+0x28,&nestedAt,4);memcpy(actorBytes+0x30,&nestedAt,4);
  oreBridgeNested=1;oreBridgeNestedResult=(uint32_t)WorldSettingsVisibilityDispatchResident100(actorBytes,time,renderer);oreBridgeNested=0;
  memcpy(actorBytes,savedActor,sizeof savedActor);spyStaticPosition=point;
 }
 if(oreBridgeMutate==8)point[0]+=1.0f;
 if(oreBridgeMutate==9)ptr((unsigned char*)actor+0x10,worldBytes);
 if(oreBridgeMutate==10)ptr(actor,moduleBytes+0xf5b48u);
 if(oreBridgeMutate==11)renderer=tableBytes;
 if(oreBridgeMutate==15)memset(wsChartActive.bits,0,wsChartActive.bitBytes);
 if(oreBridgeMutate==16)ptr(islandBytes+0x38,actorBytes);
 return oreBridgeSlot==0x180u?WorldSettingsVisibilityRenderStatic180(renderer,quadBytes,7,11,0xc0,point):WorldSettingsVisibilityRenderStatic188(renderer,quadBytes,7,11,0xc0,point);
}'''
 assert old in f;f=f.replace(old,new)
 old='static uintptr_t spyResident(void*actor,uint32_t time,void*renderer){spyResidentCalls++;'
 new='static uintptr_t spyResident(void*actor,uint32_t time,void*renderer){if(oreBridgeNested){float point[3]={20,0,20};spyStaticPosition=point;return WorldSettingsVisibilityRenderStatic180(renderer,quadBytes,7,11,0xc0,point);}spyResidentCalls++;'
 assert old in f;f=f.replace(old,new)
 old='spyStaticCalls++;if(renderer!=rendererBytes||frame!=quadBytes||orientation!=7||phase!=11||flags!=0xc0||position!=spyStaticPosition)spyFailure=14;return 0x4455;'
 new='spyStaticCalls++;if(renderer!=(oreBridgeMode?drawRendererBytes:rendererBytes)||frame!=quadBytes||orientation!=7||phase!=11||flags!=0xc0||position!=spyStaticPosition)spyFailure=14;return 0x4455;'
 assert old in f;f=f.replace(old,new)
 at=f.rfind('#endif');return f[:at]+EXTRA+'\n'+f[at:]


@unittest.skipUnless(os.name == 'nt', 'Mineral adapters use Windows native-memory guards.')
class MineralVisibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        zig = ROOT / '.local/toolchain/ziglang/zig.exe'
        if not zig.is_file():
            raise unittest.SkipTest('The reviewed local Zig toolchain is absent.')
        cls.temp = tempfile.TemporaryDirectory(prefix='anno-mineral-visibility-')
        folder = Path(cls.temp.name)
        source, output = folder / 'mineral.c', folder / 'mineral.dll'
        source.write_text(_fixture(), encoding='utf-8')
        result = subprocess.run([str(zig), 'cc', '-target', 'x86_64-windows-gnu',
            '-std=c11', '-shared', '-O2', '-Wall', '-Wextra', '-Werror', '-DHAS_ORE_SUBMIT',
            '-I', str(NATIVE), str(source), '-o', str(output)],
            capture_output=True, text=True, encoding='utf-8', errors='replace')
        if result.returncode:
            cls.temp.cleanup()
            raise AssertionError(result.stdout + result.stderr)
        cls.lib = C.CDLL(str(output))
        cls.lib.ore_parent_case.argtypes = [C.c_uint32, C.c_uint32]
        cls.lib.ore_parent_case.restype = C.c_int
        cls.lib.ore_submit_case.argtypes = [C.c_uint32]
        cls.lib.ore_submit_case.restype = C.c_int

    @classmethod
    def tearDownClass(cls):
        import _ctypes
        _ctypes.FreeLibrary(cls.lib._handle)
        del cls.lib
        cls.temp.cleanup()

    def test_registered_native_island_parent_and_fast_query_bound(self):
        for fast in (0, 1):
            with self.subTest(fast=fast):
                self.assertEqual(self.lib.ore_parent_case(0, fast), 0)

    def test_parent_class_bindings_bounds_getters_and_unknown_chart_refuse(self):
        for fast in (0, 1):
            for case in range(1, 12):
                with self.subTest(fast=fast, case=case):
                    self.assertEqual(self.lib.ore_parent_case(case, fast), 0)

    def test_native_eligible_neutral_ore_over_remembered_mine_reaches_display(self):
        for case in (0, 1, 4, 12):
            with self.subTest(case=case):
                self.assertEqual(self.lib.ore_submit_case(case), 0)

    def test_native_quantity_discovery_and_final_binding_gates_refuse(self):
        for case in (2, 3, 5, 6, 7, 8, 9, 10, 11, 15, 16, 17):
            with self.subTest(case=case):
                self.assertEqual(self.lib.ore_submit_case(case), 0)

    def test_nested_other_actor_cannot_borrow_scope_and_previous_scope_restores(self):
        for case in (13, 14):
            with self.subTest(case=case):
                self.assertEqual(self.lib.ore_submit_case(case), 0)


if __name__ == '__main__':
    unittest.main()
