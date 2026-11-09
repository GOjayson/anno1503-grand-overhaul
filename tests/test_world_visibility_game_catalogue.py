"""Synthetic server-catalogue strict-visibility regressions.

The live stock WorldServer used Game tAnlageDisplay definitions, not Display
Haus definitions. These memory/ABI tests exercise the production predicate with
those exact interfaces; they do not run Anno or establish GPU presentation.
"""
import ctypes as C
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'src/anno1503_overhaul/native/world_options'
spec = importlib.util.spec_from_file_location('visibility_game_base_fixture', Path(__file__).with_name('test_world_visibility_native.py'))
base_fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base_fixture)

GAME_FIXTURE = r'''
static int gamePrepare(WSVisibilityWorld*view,WSVisibilityDrawContext*context,uint32_t vtable,uint16_t kind,uint8_t subtype){
 prepare(wsVisibilityEncode(1,0),1);memset(cityBytes,0,sizeof cityBytes);memset(catalogueBytes,0,sizeof catalogueBytes);memset(definitionBytes,0,sizeof definitionBytes);memset(neighbourDefinition,0,sizeof neighbourDefinition);memset(physicalTiles,0,sizeof physicalTiles);memset(rendererVtable,0,sizeof rendererVtable);
 ptr(cityBytes,moduleBytes+0xfc678);ptr(cityBytes+0x20,islandBytes);ptr(cityBytes+0x28,enemyBytes);ptr(islandBytes+0x68,cityBytes);ptr(islandBytes+0x10,physicalTiles);
 ptr(worldBytes+0x200,catalogueBytes);ptr(catalogueBytes,moduleBytes+0x20300);ptr(moduleBytes+0x20300+0xe8,moduleBytes+0xb4d0);ptr(catalogueBytes+0x218+123*8,definitionBytes);ptr(catalogueBytes+0x218+124*8,neighbourDefinition);
 const uint32_t classes[]={0x1f888,0x1fac8,0x1fcf8};
 for(unsigned i=0;i<3;i++){ptr(moduleBytes+classes[i]+0xc0,moduleBytes+0x1090);ptr(moduleBytes+classes[i]+0x160,moduleBytes+0x41e0);}
 ptr(definitionBytes,moduleBytes+vtable);wsPut16(definitionBytes+0x18,kind);definitionBytes[0x20e]=subtype;
 ptr(neighbourDefinition,moduleBytes+0x1fac8);
 wsPut32(physicalTiles+(4*16+4)*8,0x80000000u|123u);ptr(rendererBytes,rendererVtable);ptr(rendererVtable+0x180,moduleBytes+0x11100);ptr(rendererVtable+0x188,moduleBytes+0x11110);
 if(!wsVisibilityWorldRead(worldBytes,view)||!wsVisibilityContextRead(view,context))return 0;
 wsVisibilityDrawContext=context;return 1;
}
__declspec(dllexport) int game_catalogue_case(uint32_t which){
 WSVisibilityWorld view;WSVisibilityDrawContext context;float xyz[3]={20.5f,0,20.5f};const uint32_t classes[]={0x1f888,0x1fac8,0x1fcf8};
 if(which==0){
  for(unsigned cls=0;cls<3;cls++)for(uint16_t kind=0x22;kind<=0x23;kind++){
   if(!gamePrepare(&view,&context,classes[cls],kind,0))return 1;
   unsigned char before[sizeof physicalTiles],cityBefore[sizeof cityBytes];memcpy(before,physicalTiles,sizeof before);memcpy(cityBefore,cityBytes,sizeof cityBefore);spyStaticPosition=xyz;
   if(WorldSettingsVisibilityDrawStatic188(rendererBytes,quadBytes,7,11,0xc0,xyz)||spyStaticCalls)return 2;
   float observer=40.0f;memcpy(humanShip+0x28,&observer,4);memcpy(humanShip+0x30,&observer,4);if(!wsVisibilityContextRead(&view,&context))return 3;
   if(WorldSettingsVisibilityDrawStatic180(rendererBytes,quadBytes,7,11,0xc0,xyz)!=0x4455||spyStaticCalls!=1||spyFailure)return 4;
   if(memcmp(before,physicalTiles,sizeof before)||memcmp(cityBefore,cityBytes,sizeof cityBefore)||wsU16(islandBytes+0x12e)!=1)return 5;
  }
 }else if(which==1){
  if(!gamePrepare(&view,&context,0x1fac8,1,0))return 1;void*owner=0;
  const uint8_t subtypes[]={0,26,69,70,255};
  for(uint16_t kind=0;kind<512;kind++)for(unsigned i=0;i<sizeof subtypes;i++){
   wsPut16(definitionBytes+0x18,kind);definitionBytes[0x20e]=subtypes[i];neighbourDefinition[0x20e]=0;
   uint32_t category=(((uint32_t)kind-1u)&~31u)+1u;
   int expected=category==1||category==0x21||category==0x41||category==0x61||category==0x81||category==0xa1||category==0xc1||category==0x101||category==0x121||(category==0xe1&&subtypes[i]!=69&&subtypes[i]!=70);
   int actual=wsVisibilityOwnedBuilding(&context,&context.islands[0],xyz[0],xyz[2],&owner);
   if(actual!=expected||(actual&&owner!=enemyBytes))return 2;
  }
 }else if(which==2){
  const uint8_t subtypes[]={0,1,69,70,255};
  for(unsigned cls=0;cls<3;cls++)for(unsigned a=0;a<sizeof subtypes;a++)for(unsigned b=0;b<sizeof subtypes;b++){
   if(!gamePrepare(&view,&context,classes[cls],0xe2,subtypes[a]))return 1;
   ptr(neighbourDefinition,moduleBytes+classes[(cls+1)%3]);neighbourDefinition[0x20e]=subtypes[b];void*owner=0;
   uint8_t effective=subtypes[a]?subtypes[a]:subtypes[b];
   if(wsVisibilityOwnedBuilding(&context,&context.islands[0],xyz[0],xyz[2],&owner)!=(effective!=69&&effective!=70))return 2;
  }
 }else if(which==3){
  if(!gamePrepare(&view,&context,0x1fac8,0x22,0))return 1;void*owner=0;
  ptr(moduleBytes+0x1fac8+0xc0,moduleBytes+0x1091);
  if(wsVisibilityOwnedBuilding(&context,&context.islands[0],xyz[0],xyz[2],&owner)!=-1||WorldSettingsVisibilitySpriteVisible(xyz))return 2;
  ptr(moduleBytes+0x1fac8+0xc0,moduleBytes+0x1090);ptr(moduleBytes+0x1fac8+0x160,moduleBytes+0x41e1);
  if(wsVisibilityOwnedBuilding(&context,&context.islands[0],xyz[0],xyz[2],&owner)!=-1||WorldSettingsVisibilitySpriteVisible(xyz))return 3;
  ptr(definitionBytes,moduleBytes+0x1fac0);if(wsVisibilityOwnedBuilding(&context,&context.islands[0],xyz[0],xyz[2],&owner)||!WorldSettingsVisibilitySpriteVisible(xyz))return 4;
 }else if(which==4){
  if(!gamePrepare(&view,&context,0x1fac8,0x22,0))return 1;
  ptr(cityBytes+0x28,humanBytes);if(!WorldSettingsVisibilitySpriteVisible(xyz))return 2;
  ptr(cityBytes+0x28,enemyBytes);context.view.enemy=1;if(!WorldSettingsVisibilitySpriteVisible(xyz))return 3;
  context.view.enemy=0;wsVisibilityDrawContext=0;if(!WorldSettingsVisibilitySpriteVisible(xyz))return 4;
 }else if(which==5){
  if(!gamePrepare(&view,&context,0x1fac8,0x22,0))return 1;void*owner=0;
  wsPut32(physicalTiles+(4*16+4)*8,123);if(wsVisibilityOwnedBuilding(&context,&context.islands[0],xyz[0],xyz[2],&owner))return 2;
  wsPut32(physicalTiles+(4*16+4)*8,0x80000000u|123u);wsPut32(physicalTiles+(4*16+4)*8+4,15u<<25);if(wsVisibilityOwnedBuilding(&context,&context.islands[0],xyz[0],xyz[2],&owner))return 3;
 }else if(which==6){
  if(!gamePrepare(&view,&context,0x1fac8,0x22,0))return 1;void*owner=0;
  ptr(definitionBytes,moduleBytes+0xf612e0);ptr(moduleBytes+0xf612e0+0xc0,moduleBytes+0x27790);ptr(moduleBytes+0xf612e0+0x160,moduleBytes+0x17540);wsPut16(definitionBytes+0x38,0xe1);
  if(wsVisibilityOwnedBuilding(&context,&context.islands[0],xyz[0],xyz[2],&owner)!=1)return 2;
  wsPut16(definitionBytes+0x38,0xe2);neighbourDefinition[0x20e]=69;if(wsVisibilityOwnedBuilding(&context,&context.islands[0],xyz[0],xyz[2],&owner))return 3;
  neighbourDefinition[0x20e]=26;if(wsVisibilityOwnedBuilding(&context,&context.islands[0],xyz[0],xyz[2],&owner)!=1)return 4;
  ptr(definitionBytes,moduleBytes+0xf60e60);if(wsVisibilityOwnedBuilding(&context,&context.islands[0],xyz[0],xyz[2],&owner))return 5;
 }else if(which==7){
  if(!gamePrepare(&view,&context,0x1fac8,0xe2,26))return 1;void*owner=0;
  ptr(neighbourDefinition,moduleBytes+0x1101000);if(wsVisibilityOwnedBuilding(&context,&context.islands[0],xyz[0],xyz[2],&owner)!=1)return 2;
  definitionBytes[0x20e]=0;if(wsVisibilityOwnedBuilding(&context,&context.islands[0],xyz[0],xyz[2],&owner))return 3;
  definitionBytes[0x20e]=69;if(wsVisibilityOwnedBuilding(&context,&context.islands[0],xyz[0],xyz[2],&owner))return 4;
  definitionBytes[0x20e]=70;if(wsVisibilityOwnedBuilding(&context,&context.islands[0],xyz[0],xyz[2],&owner))return 5;
 }else return 99;
 wsVisibilityDrawContext=0;return 0;
}
__declspec(dllexport) int fast_game_case(uint32_t which){
 WSVisibilityWorld view;WSVisibilityDrawContext context;float x=20.5f,z=20.5f;const uint32_t classes[]={0x1f888,0x1fac8,0x1fcf8};
 if(which==0){
  const uint16_t kinds[]={0,1,0x22,0x23,0x41,0xe1,0xe2,0x121,0x142,0x163};const uint8_t subtypes[]={0,26,69,70,255};
  for(unsigned cls=0;cls<3;cls++)for(unsigned k=0;k<sizeof kinds/sizeof kinds[0];k++)for(unsigned a=0;a<sizeof subtypes;a++)for(unsigned b=0;b<3;b++){
   if(!gamePrepare(&view,&context,classes[cls],kinds[k],subtypes[a]))return 1;neighbourDefinition[0x20e]=subtypes[b];void*slowOwner=0,*fastOwner=0;
   int slow=wsVisibilityOwnedBuilding(&context,&context.islands[0],x,z,&slowOwner);ptr(rendererBytes,moduleBytes+0xf63740);
   if(!wsVisibilityFastPrepare(&context,rendererBytes)||!context.fast||!context.fast->catalogueReady)return 2;
   int fast=wsVisibilityOwnedBuilding(&context,&context.islands[0],x,z,&fastOwner);
   if(fast!=slow||fastOwner!=slowOwner)return 3;wsVisibilityFastRelease(&context);wsVisibilityDrawContext=0;
  }
 }else if(which==1){
  for(unsigned mutation=0;mutation<9;mutation++){
   if(!gamePrepare(&view,&context,0x1fac8,0x22,0))return 1;ptr(rendererBytes,moduleBytes+0xf63740);
   if(!wsVisibilityFastPrepare(&context,rendererBytes))return 2;void*owner=0;
   if(wsVisibilityOwnedBuilding(&context,&context.islands[0],x,z,&owner)!=1)return 3;
   if(mutation==0)ptr(worldBytes+0x6640,actorBytes);
   if(mutation==1)ptr(islandBytes+0x10,physicalTiles+8);
   if(mutation==2)ptr(catalogueBytes+0x218+123*8,neighbourDefinition);
   if(mutation==3)ptr(islandBytes+0x68,0);
   if(mutation==4)ptr(cityBytes+0x28,humanBytes);
   if(mutation==5)ptr(enemyBytes+0x10,0);
   if(mutation==6)ptr(moduleBytes+0x20300+0xe8,moduleBytes+0xb4d1);
   if(mutation==7)wsPut16(definitionBytes+0x18,0x23);
   if(mutation==8)ptr(definitionBytes,moduleBytes+0x1fcf8);
   if(wsVisibilityOwnedBuilding(&context,&context.islands[0],x,z,&owner)!=-1)return 4;
   wsVisibilityFastRelease(&context);if(context.fast)return 5;wsVisibilityDrawContext=0;
  }
 }else if(which==2){
  if(!gamePrepare(&view,&context,0x1fac8,0x22,0))return 1;ptr(rendererBytes,moduleBytes+0xf63740);
  if(!wsVisibilityFastPrepare(&context,rendererBytes))return 2;void*owner=0;uint32_t*anchor=(uint32_t*)(physicalTiles+(4*16+4)*8),*part=(uint32_t*)(physicalTiles+(5*16+5)*8);part[0]=0x00090000u|123u;
  if(wsVisibilityOwnedBuilding(&context,&context.islands[0],21.5f,21.5f,&owner)!=1)return 3;
  anchor[0]&=~0x80000000u;if(wsVisibilityOwnedBuilding(&context,&context.islands[0],21.5f,21.5f,&owner))return 4;
  anchor[0]|=0x80000000u;part[1]=15u<<25;if(wsVisibilityOwnedBuilding(&context,&context.islands[0],21.5f,21.5f,&owner))return 5;
  wsVisibilityFastRelease(&context);wsVisibilityDrawContext=0;
 }else if(which==4){
  const uint32_t neighbours[]={0xf60e60,0xf609d0,0xf612e0,0xf61400,0xf60af0};
  for(unsigned i=0;i<sizeof neighbours/sizeof neighbours[0];i++){
   if(!gamePrepare(&view,&context,0x1fac8,0xe2,0))return 1;ptr(rendererBytes,moduleBytes+0xf63740);
   uint32_t vt=neighbours[i],getter=vt==0xf60af0?0x62770u:0x17540u;
   ptr(neighbourDefinition,moduleBytes+vt);ptr(moduleBytes+vt+0xc0,moduleBytes+0x27790);wsPut16(neighbourDefinition+0x38,0x41);
   ptr(moduleBytes+vt+0x160,moduleBytes+getter+1u);void*owner=0;
   if(wsVisibilityOwnedBuilding(&context,&context.islands[0],x,z,&owner))return 2;
   if(!wsVisibilityFastPrepare(&context,rendererBytes))return 3;
   if(wsVisibilityOwnedBuilding(&context,&context.islands[0],x,z,&owner))return 4;
   ptr(moduleBytes+vt+0x160,moduleBytes+getter);
   if(wsVisibilityOwnedBuilding(&context,&context.islands[0],x,z,&owner)!=1)return 5;
   ptr(moduleBytes+vt+0x160,moduleBytes+getter+1u);
   if(wsVisibilityOwnedBuilding(&context,&context.islands[0],x,z,&owner))return 6;
   wsVisibilityFastRelease(&context);wsVisibilityDrawContext=0;
  }
 }else if(which==3){
  if(!gamePrepare(&view,&context,0x1fac8,0x22,0))return 1;ptr(rendererBytes,moduleBytes+0xf63740);
  if(!wsVisibilityFastPrepare(&context,rendererBytes))return 2;
  ptr(rendererBytes,moduleBytes+0xf63748);if(wsVisibilityFastRenderer(&context,rendererBytes))return 3;
  wsVisibilityFastRelease(&context);wsVisibilityDrawContext=0;
 }else return 99;
 return 0;
}
'''


@unittest.skipUnless(os.name == 'nt', 'Server-catalogue display-memory fixture uses Windows VirtualQuery.')
class GameCatalogueVisibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        zig = ROOT / '.local/toolchain/ziglang/zig.exe'
        if not zig.is_file():
            raise unittest.SkipTest('Fixture needs the reviewed local Zig toolchain.')
        cls.temp = tempfile.TemporaryDirectory(prefix='anno-game-visibility-')
        folder = Path(cls.temp.name)
        source, output = folder / 'game_visibility.c', folder / 'game_visibility.dll'
        fixture = base_fixture.FIXTURE.replace('definitionBytes[0x80],neighbourDefinition[0x80]',
                                               'definitionBytes[0x240],neighbourDefinition[0x240]')
        before, after = fixture.rsplit('#endif', 1)
        source.write_text(before + GAME_FIXTURE + '\n#endif' + after, encoding='utf-8')
        result = subprocess.run([str(zig), 'cc', '-target', 'x86_64-windows-gnu', '-std=c11', '-shared',
                                 '-O2', '-Wall', '-Wextra', '-Werror', '-I', str(NATIVE), str(source), '-o', str(output)],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf-8', errors='replace')
        if result.returncode:
            cls.temp.cleanup()
            raise AssertionError(result.stdout)
        cls.lib = C.CDLL(str(output))
        cls.lib.game_catalogue_case.argtypes = [C.c_uint32]
        cls.lib.fast_game_case.argtypes = [C.c_uint32]

    @classmethod
    def tearDownClass(cls):
        import _ctypes
        _ctypes.FreeLibrary(cls.lib._handle)
        del cls.lib
        cls.temp.cleanup()

    def test_server_definitions_follow_sight_and_native_neutral_exceptions(self):
        for case in range(8):
            with self.subTest(case=case):
                self.assertEqual(self.lib.game_catalogue_case(case), 0)

    def test_current_draw_snapshots_match_slow_path_and_refuse_changed_bindings(self):
        for case in range(5):
            with self.subTest(case=case):
                self.assertEqual(self.lib.fast_game_case(case), 0)


if __name__ == '__main__':
    unittest.main()
