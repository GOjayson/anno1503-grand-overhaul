"""Ownership remains independent from reveal settings and remembered graphics.

The isolated Windows memory graph exercises production guards with real page
protections. Only the final original native command/getter call is a spy; these
checks do not run Anno or establish actual multiplayer/UI acceptance.
"""
import ctypes as C
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_world_visibility_native import FIXTURE, NATIVE, ROOT

EXTRA = r'''
static uint32_t controlCalls,controlRva,controlSelector;
static int32_t controlValue;static void*controlClient,*controlHouse;
static uintptr_t controlThird,controlFourth;
static uintptr_t controlSpy(void*c,uint32_t s,int32_t n,void*h){
 controlCalls++;controlClient=c;controlSelector=s;controlValue=n;controlHouse=h;return UINT64_C(0xfedcba9876543210);
}
static uintptr_t controlGetter(void*w,uint32_t s,uintptr_t third,uintptr_t fourth){
 controlCalls++;controlClient=w;controlSelector=s;controlThird=third;controlFourth=fourth;return UINT64_C(0xf123456789abcdef);
}
#define WS_VISIBILITY_NATIVE_BUILDING_COMMAND(module,rva) (controlRva=(rva),controlSpy)
#define WS_VISIBILITY_NATIVE_INTERACTION_GETTER(module) controlGetter
#include "start_visibility_control.inc"
static unsigned char controlClientBytes[0x40],controlGame[0x60];
static void controlPrepare(uint32_t policyCode,int network){
 prepare(policyCode,0);memset(controlClientBytes,0,sizeof controlClientBytes);memset(controlGame,0,sizeof controlGame);
 memset(cityBytes,0,sizeof cityBytes);memset(buildingBytes,0,sizeof buildingBytes);
 ptr(controlClientBytes,moduleBytes+(network?0xa7418u:0xa7170u));ptr(controlClientBytes+0x10,worldBytes);ptr(controlClientBytes+0x18,controlGame);
 ptr(controlGame,moduleBytes+0xa1788);ptr(controlGame+0x28,worldBytes);ptr(controlGame+0x40,controlClientBytes);
 ptr(cityBytes,moduleBytes+0xfc678);ptr(cityBytes+0x20,islandBytes);ptr(cityBytes+0x28,humanBytes);ptr(islandBytes+0x68,cityBytes);
 ptr(buildingBytes[0],moduleBytes+0xf6938);ptr(buildingBytes[0]+0x18,cityBytes);wsPut16(buildingBytes[0]+0xa,20);wsPut16(buildingBytes[0]+0xc,20);
 for(size_t i=0;i<sizeof wsVisibilityProductionVtables/sizeof wsVisibilityProductionVtables[0];i++){
  unsigned char*vt=moduleBytes+wsVisibilityProductionVtables[i];ptr(vt+0x30,moduleBytes+0x84fc0);ptr(vt+0x38,moduleBytes+0x84fe0);ptr(vt+0x40,moduleBytes+0x84ff0);
 }
 ptr(moduleBytes+0xff650+0xf0,moduleBytes+0xd1910);ptr(moduleBytes+0xff1d8+0xf0,moduleBytes+0xd1910);
 DWORD prior;VirtualProtect(moduleBytes,sizeof moduleBytes,PAGE_EXECUTE_READWRITE,&prior);
 controlCalls=controlRva=controlSelector=0;controlValue=0;controlClient=controlHouse=0;controlThird=controlFourth=0;
}
static uintptr_t controlInvoke(int queue){return queue?WorldSettingsVisibilityShipQueue(controlClientBytes,0xfedcba98u,INT32_MIN+7,buildingBytes[0]):WorldSettingsVisibilityBuildingCommand(controlClientBytes,0xfedcba98u,INT32_MIN+7,buildingBytes[0]);}
__declspec(dllexport) int control_case(uint32_t which){
 if(which==0){
  for(uint32_t policyCode=0x1000;policyCode<=0x6000;policyCode+=0x1000)for(int network=0;network<2;network++)for(int worldVT=0;worldVT<2;worldVT++)for(int frameVT=0;frameVT<2;frameVT++)for(int queue=0;queue<2;queue++){
   controlPrepare(policyCode,network);ptr(worldBytes,moduleBytes+(worldVT?0xff1d8:0xff650));ptr(controlGame,moduleBytes+(frameVT?0xa0ce8:0xa1788));
   unsigned char priorWorld[sizeof worldBytes],priorHouse[sizeof buildingBytes],priorCity[sizeof cityBytes];memcpy(priorWorld,worldBytes,sizeof worldBytes);memcpy(priorHouse,buildingBytes,sizeof buildingBytes);memcpy(priorCity,cityBytes,sizeof cityBytes);
   for(size_t h=0;h<sizeof wsVisibilityProductionVtables/sizeof wsVisibilityProductionVtables[0];h++){
    ptr(buildingBytes[0],moduleBytes+wsVisibilityProductionVtables[h]);controlCalls=0;
    if(controlInvoke(queue)!=UINT64_C(0xfedcba9876543210)||controlCalls!=1||controlClient!=controlClientBytes||controlHouse!=buildingBytes[0]||controlSelector!=0xfedcba98u||controlValue!=INT32_MIN+7)return 1;
    if(controlRva!=(uint32_t)(network?(queue?0x7d230:0x7d340):(queue?0x785d0:0x78630)))return 2;
   }
   ptr(buildingBytes[0],moduleBytes+0xf6938);
   if(memcmp(priorWorld,worldBytes,sizeof worldBytes)||memcmp(priorHouse,buildingBytes,sizeof buildingBytes)||memcmp(priorCity,cityBytes,sizeof cityBytes))return 3;
  }
  return 0;
 }
 if(which==1){
  for(uint32_t policyCode=0x1000;policyCode<=0x6000;policyCode+=0x1000)for(int network=0;network<2;network++)for(int queue=0;queue<2;queue++){
   controlPrepare(policyCode,network);ptr(cityBytes+0x28,enemyBytes);wsPut16(islandBytes+0x12e,0xffff);worldBytes[0x6ee9]=1;
   if(controlInvoke(queue)||controlCalls)return 1;
   ptr(cityBytes+0x28,humanBytes);if(!controlInvoke(queue)||controlCalls!=1)return 2;
   ptr(cityBytes+0x28,enemyBytes);controlCalls=0;if(controlInvoke(queue)||controlCalls)return 3;
  }
  return 0;
 }
 if(which==2){
  for(uint32_t fault=0;fault<25;fault++){
   controlPrepare(0x1000,0);
   switch(fault){
    case 0:ptr(buildingBytes[0],0);break;case 1:ptr(buildingBytes[0],moduleBytes+0xee000);break;
    case 2:ptr(buildingBytes[0]+0x18,0);break;case 3:ptr(cityBytes,0);break;
    case 4:ptr(cityBytes+0x20,0);break;case 5:ptr(cityBytes+0x28,0);break;
    case 6:ptr(islandBytes+0x38,0);break;case 7:ptr(islandBytes,0);break;
    case 8:ptr(islandBytes+0x68,0);break;case 9:ptr(worldBytes+0x6640,0);break;
    case 10:ptr(humanBytes+0x10,0);break;case 11:ptr(humanBytes,0);break;
    case 12:wsPut32(humanBytes+8,1);break;case 13:ptr(players+8,enemyBytes);break;
    case 14:ptr(players,0);break;case 15:wsPut32(worldBytes+0x1e4,1);break;
    case 16:ptr(controlClientBytes+0x10,0);break;case 17:ptr(controlClientBytes+0x18,0);break;
    case 18:ptr(controlGame,0);break;case 19:ptr(controlGame+0x28,0);break;
    case 20:ptr(controlGame+0x40,0);break;case 21:ptr(moduleBytes+0xf6938+0x40,moduleBytes+0x84ff1);break;
    case 22:wsPut16(buildingBytes[0]+0xa,15);break;case 23:wsPut16(buildingBytes[0]+0xc,32);break;
    case 24:wsPut32(worldBytes+0x6eec,0x7000);break;
   }
   unsigned char prior[sizeof worldBytes];memcpy(prior,worldBytes,sizeof prior);
   if(controlInvoke(0)||controlInvoke(1)||controlCalls||memcmp(prior,worldBytes,sizeof prior))return 1+(int)fault;
  }
  return 0;
 }
 if(which==3){
  for(int network=0;network<2;network++)for(int queue=0;queue<2;queue++){
   controlPrepare(0,network);wsPut32(worldBytes+0x1d8,333);wsPut32(worldBytes+0x1dc,777);ptr(controlClientBytes+0x18,0);
   if((queue?WorldSettingsVisibilityShipQueue(controlClientBytes,3,-17,0):WorldSettingsVisibilityBuildingCommand(controlClientBytes,3,-17,0))!=UINT64_C(0xfedcba9876543210)||controlCalls!=1||controlSelector!=3||controlValue!=-17||controlHouse)return 1;
  }
  return 0;
 }
 if(which==4){
  for(uint32_t policyCode=0x1000;policyCode<=0x7000;policyCode+=0x1000)for(int byte=0;byte<2;byte++)for(int worldVT=0;worldVT<2;worldVT++){
   controlPrepare(policyCode,0);ptr(worldBytes,moduleBytes+(worldVT?0xff1d8:0xff650));worldBytes[0x6ee9]=(unsigned char)byte;
   unsigned char prior[sizeof worldBytes];memcpy(prior,worldBytes,sizeof prior);
   if(WorldSettingsVisibilityInteractionProperty(worldBytes,5,UINT64_MAX,UINT64_C(0x123456789abcdef0))!=1||controlCalls||memcmp(prior,worldBytes,sizeof prior))return 1;
  }
  for(uint32_t code=0;code<=0x6000;code+=0x1000)for(uint32_t property=0;property<10;property++){
   if(code&&property==5)continue;controlPrepare(code,0);
   if(!code){wsPut32(worldBytes+0x1d8,333);wsPut32(worldBytes+0x1dc,777);}
   if(WorldSettingsVisibilityInteractionProperty(worldBytes,property,UINT64_C(0x123456789abcdef0),UINT64_C(0xfedcba9876543210))!=UINT64_C(0xf123456789abcdef)||controlCalls!=1||controlClient!=worldBytes||controlSelector!=property||controlThird!=UINT64_C(0x123456789abcdef0)||controlFourth!=UINT64_C(0xfedcba9876543210))return 2;
  }
  controlPrepare(0x7000,0);if(WorldSettingsVisibilityInteractionProperty(worldBytes,6,1,2)||controlCalls)return 3;
  controlPrepare(0x1000,0);ptr(worldBytes,0);if(WorldSettingsVisibilityInteractionProperty(worldBytes,5,1,2)!=1||controlCalls)return 4;
  return 0;
 }
 if(which==5){
  controlPrepare(0x1000,0);unsigned char*pages=(unsigned char*)VirtualAlloc(0,8192,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);if(!pages)return 1;
  unsigned char*shortHouse=pages+4096-0x10;ptr(shortHouse,moduleBytes+0xf6938);DWORD prior;if(!VirtualProtect(pages+4096,4096,PAGE_NOACCESS,&prior)){VirtualFree(pages,0,MEM_RELEASE);return 2;}
  uintptr_t got=WorldSettingsVisibilityBuildingCommand(controlClientBytes,9,1,shortHouse);VirtualFree(pages,0,MEM_RELEASE);if(got||controlCalls)return 3;
  controlPrepare(0,0);if(!VirtualProtect(moduleBytes+0x78000,4096,PAGE_READWRITE,&prior))return 4;
  got=controlInvoke(0);VirtualProtect(moduleBytes+0x78000,4096,prior,&prior);if(got||controlCalls)return 5;
  controlPrepare(0,0);ptr(moduleBytes+0xff650+0xf0,moduleBytes+0xd1911);if(WorldSettingsVisibilityInteractionProperty(worldBytes,5,1,2)!=1||controlCalls)return 6;
  controlPrepare(0x1000,0);ptr(controlClientBytes,moduleBytes+0xa7171);if(controlInvoke(0)||controlCalls)return 7;
  return 0;
 }
 return 99;
}
'''


@unittest.skipUnless(os.name == 'nt', 'The control fixture exercises Windows page protection.')
class VisibilityControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        zig = ROOT / '.local/toolchain/ziglang/zig.exe'
        if not zig.is_file():
            raise unittest.SkipTest('The reviewed local Zig toolchain is unavailable.')
        cls.temp = tempfile.TemporaryDirectory(prefix='anno-control-')
        folder = Path(cls.temp.name)
        source = folder / 'control.c'
        before, sep, after = FIXTURE.rpartition('#endif')
        assert sep and not after.strip()
        source.write_text(before + EXTRA + sep + after, encoding='utf-8')
        output = folder / 'control.dll'
        result = subprocess.run([str(zig), 'cc', '-target', 'x86_64-windows-gnu',
            '-std=c11', '-shared', '-O2', '-Wall', '-Wextra', '-Werror',
            '-I', str(NATIVE), str(source), '-o', str(output)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace')
        if result.returncode:
            cls.temp.cleanup()
            raise AssertionError(result.stdout)
        cls.lib = C.CDLL(str(output))
        cls.lib.control_case.argtypes = [C.c_uint32]

    @classmethod
    def tearDownClass(cls):
        import _ctypes
        _ctypes.FreeLibrary(cls.lib._handle)
        del cls.lib
        cls.temp.cleanup()

    def test_all_owned_native_house_classes_and_policy_modes_preserve_commands(self):
        self.assertEqual(self.lib.control_case(0), 0)

    def test_foreign_mutations_denied_even_when_revealed_and_owner_rechecked(self):
        self.assertEqual(self.lib.control_case(1), 0)

    def test_invalid_ownership_graph_and_reserved_policy_fail_closed(self):
        self.assertEqual(self.lib.control_case(2), 0)

    def test_unmarked_irregular_native_world_delegates_unchanged(self):
        self.assertEqual(self.lib.control_case(3), 0)

    def test_interaction_gate_preserves_all_other_native_arguments_and_returns(self):
        self.assertEqual(self.lib.control_case(4), 0)

    def test_page_boundaries_nonexecutables_and_altered_native_interfaces_refused(self):
        self.assertEqual(self.lib.control_case(5), 0)
