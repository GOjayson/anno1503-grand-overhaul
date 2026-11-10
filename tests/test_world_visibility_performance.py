"""Dense aligned-coordinate lookup and read-only picking regressions.

Synthetic native adapters run in an isolated DLL; no game/FPS claim.
"""
import ctypes as C
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_world_visibility_native import FIXTURE, NATIVE, ROOT

EXTRA = r'''
static uint32_t oldAlignedHash(void*frame,const uint32_t xyz[3]){
 uintptr_t p=(uintptr_t)frame;uint32_t n=(uint32_t)p^(uint32_t)(p>>32)^3u*131u^0x1c0u;
 for(uint32_t k=0;k<3;k++)n=(n^xyz[k])*16777619u;return n;
}
__declspec(dllexport) int performance_case(uint32_t which,uint32_t*out){
 if(which==0){
  enum{COUNT=4096,CAPACITY=8192};uint32_t*newBins=(uint32_t*)calloc(CAPACITY,4),*oldBins=(uint32_t*)calloc(CAPACITY,4),*table=(uint32_t*)calloc(CAPACITY,4);
  if(!newBins||!oldBins||!table){free(newBins);free(oldBins);free(table);return 1;}
  uint32_t probes=0,used=0,maxBucket=0,oldUsed=0;
  for(uint32_t i=0;i<COUNT;i++){
   float point[3]={(float)(i&127u)+0.5f,0,(float)(i>>7)+0.5f};uint32_t xyz[3];memcpy(xyz,point,12);
   uint32_t bucket=wsChartGhostHash(chartFrame,0,3,xyz,0x1c0)&(CAPACITY-1u);newBins[bucket]++;oldBins[oldAlignedHash(chartFrame,xyz)&(CAPACITY-1u)]++;
   probes++;while(table[bucket]){bucket=(bucket+1u)&(CAPACITY-1u);probes++;}table[bucket]=i+1u;
  }
  for(uint32_t i=0;i<CAPACITY;i++){used+=newBins[i]!=0;oldUsed+=oldBins[i]!=0;if(newBins[i]>maxBucket)maxBucket=newBins[i];}
  out[0]=used;out[1]=maxBucket;out[2]=probes;out[3]=oldUsed;free(newBins);free(oldBins);free(table);return 0;
 }
 prepare(wsVisibilityEncode(1,0),1);chartFixtureHouse(20,20);WSVisibilityWorld v;WSVisibilityDrawContext c;
 if(!wsVisibilityWorldRead(worldBytes,&v)||!wsVisibilityContextRead(&v,&c)||!wsVisibilityFastPrepare(&c,drawRendererBytes))return 2;
 int result=0;
 if(which==1){
  if(!wsChartAssetGuard(&c,123,1)){result=3;goto done;}
  WSChartDraw draw={0};c.chartDraw=&draw;const WSChartAssetProof*asset=(const WSChartAssetProof*)c.fast->chartAssets[123];
  for(uint32_t i=0;i<4096;i++){
   WSChartGhost r={0};r.frame=chartFrame;r.asset=asset;r.assetId=123;r.kind=3;r.flags=0x1c0;r.phase=i%31u;r.used=1;
   float point[3]={(float)(i&127u)+0.5f,0,(float)(i>>7)+0.5f};memcpy(r.xyz,point,12);
   if(!wsChartGhostInsert(&draw,&r)){result=4;goto table_done;}
  }
  if(draw.ghostCount!=4096){result=5;goto table_done;}
  for(uint32_t i=0;i<4096;i++){
   float point[3]={(float)(i&127u)+0.5f,0,(float)(i>>7)+0.5f};uint32_t phase=999,flags=0x1c0;
   if(wsVisibilityChartGhostSprite(&c,chartFrame,0,(uintptr_t)(moduleBytes+0xc538f),point,&phase,&flags)!=1||phase!=i%31u||flags!=0x1c0){result=6;goto table_done;}
  }
  WSChartGhost duplicate={0};duplicate.frame=chartFrame;duplicate.asset=asset;duplicate.assetId=123;duplicate.kind=3;duplicate.flags=0x1c0;duplicate.used=1;float point[3]={0.5f,0,0.5f};memcpy(duplicate.xyz,point,12);
  if(!wsChartGhostInsert(&draw,&duplicate)||draw.ghostCount!=4096){result=7;goto table_done;}duplicate.phase=1;
  if(wsChartGhostInsert(&draw,&duplicate)||draw.ghostCount!=4096)result=8;
  table_done:free(draw.ghosts);c.chartDraw=0;
 }else if(which==2){
  float position=22;memcpy(humanShip+0x28,&position,4);memcpy(humanShip+0x30,&position,4);wsVisibilityFastRelease(&c);
  if(!chartFixtureObserve(500)){result=9;goto done;}
  position=128;memcpy(humanShip+0x28,&position,4);memcpy(humanShip+0x30,&position,4);
  uint64_t bits=wsChHash(wsChartActive.bits,wsChartActive.bitBytes),cells=wsChHash(wsChartActive.cells,(size_t)wsChartActive.count*sizeof(WSChartCell));uint32_t generation=wsChartActive.generation;spyChartProducerCalls=0;
  for(uint32_t mode=4;mode<=5;mode++){
   wsPut32(drawRendererBytes+0x498,mode);if(!wsVisibilityContextRead(&v,&c)||!wsVisibilityFastPrepare(&c,drawRendererBytes)){result=10;goto done;}
   if(!wsVisibilityChartBeginDraw(&c,listBytes,99999,drawRendererBytes,0)){result=11;goto done;}
   if(c.chartDraw||spyChartProducerCalls||bits!=wsChHash(wsChartActive.bits,wsChartActive.bitBytes)||cells!=wsChHash(wsChartActive.cells,(size_t)wsChartActive.count*sizeof(WSChartCell))||generation!=wsChartActive.generation){result=12;wsVisibilityChartEndDraw(&c);goto done;}
   if(!wsVisibilityChartEndDraw(&c)){result=13;goto done;}wsVisibilityFastRelease(&c);
  }
 }else if(which==3){
  float position=22;memcpy(humanShip+0x28,&position,4);memcpy(humanShip+0x30,&position,4);wsVisibilityFastRelease(&c);
  if(!chartFixtureObserve(500)){result=14;goto done;}position=128;memcpy(humanShip+0x28,&position,4);memcpy(humanShip+0x30,&position,4);ptr(worldBytes+0x220,mapBytes);
  uint64_t bits=wsChHash(wsChartActive.bits,wsChartActive.bitBytes),cells=wsChHash(wsChartActive.cells,(size_t)wsChartActive.count*sizeof(WSChartCell));uint32_t generation=wsChartActive.generation;unsigned char pixels[sizeof pixelBytes];memcpy(pixels,pixelBytes,sizeof pixels);
  spyChartProducerCalls=0;spyChartDrawMode=1;
  for(uint32_t selection=0;selection<3;selection++){
   wsPut32(drawRendererBytes+0x498,selection<2?selection+4u:1u);uint32_t calls=spyCalls;
   uintptr_t returned=selection==2?WorldSettingsVisibilityDrawTerrainClipped(worldBytes,listBytes,17,(int32_t*)tableBytes,99999,drawRendererBytes):WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,99999,drawRendererBytes);
   if(returned!=(selection==2?0x1235u:0x1234u)||spyCalls!=calls+1u||spyFailure||spyChartProducerCalls||spyViewportCalls||wsVisibilityLastError||worldBytes[0x6ee9]!=0x7c||wsChartActive.generation!=generation||bits!=wsChHash(wsChartActive.bits,wsChartActive.bitBytes)||cells!=wsChHash(wsChartActive.cells,(size_t)wsChartActive.count*sizeof(WSChartCell))||memcmp(pixels,pixelBytes,sizeof pixels)){result=15+selection;goto done;}
  }
  wsPut32(drawRendererBytes+0x498,1);if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,2000,drawRendererBytes)!=0x1234||worldBytes[0x6ee9]!=1||!spyViewportCalls||bits==wsChHash(wsChartActive.bits,wsChartActive.bitBytes)||!memcmp(pixels,pixelBytes,sizeof pixels)||spyFailure)result=18;
  wsVisibilityChartRetire(drawRendererBytes);
 }else if(which==4){
  wsVisibilityFastRelease(&c);prepare(wsVisibilityEncode(0,0),1);uint64_t bits=wsChHash(wsChartActive.bits,wsChartActive.bitBytes);spyMasked=1;spyChartDrawMode=1;
  for(uint32_t selection=0;selection<3;selection++){
   wsPut32(drawRendererBytes+0x498,selection<2?selection+4u:1u);
   uintptr_t returned=selection==2?WorldSettingsVisibilityDrawTerrainClipped(worldBytes,listBytes,17,(int32_t*)tableBytes,99999,drawRendererBytes):WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,99999,drawRendererBytes);
   if(returned!=(selection==2?0x1235u:0x1234u)||spyFailure||listBytes[8+0x4d]!=1||wsVisibilityBackupCount||wsChartReadTLS||spyChartProducerCalls||spyViewportCalls||worldBytes[0x6ee9]!=0x7c||bits!=wsChHash(wsChartActive.bits,wsChartActive.bitBytes)){result=19+selection;goto done;}
  }
 }else result=99;
 done:wsVisibilityFastRelease(&c);return result;
}
'''

@unittest.skipUnless(os.name == 'nt', 'Scoped native adapters use Windows memory guards.')
class VisibilityPerformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='anno-visibility-performance-')
        folder=Path(cls.temp.name);source=folder/'performance.c';dll=folder/'performance.dll'
        head,tail=FIXTURE.rsplit('#endif',1);source.write_text(head+EXTRA+'\n#endif'+tail)
        compiler=ROOT/'.local/toolchain/ziglang/zig.exe'
        if not compiler.exists():raise unittest.SkipTest('Reviewed native compiler is unavailable.')
        run=subprocess.run([str(compiler),'cc','-target','x86_64-windows-gnu','-std=c11','-shared','-O2','-Wall','-Wextra','-Werror','-I',str(NATIVE),str(source),'-o',str(dll)],capture_output=True,text=True)
        if run.returncode:raise AssertionError(run.stdout+run.stderr)
        cls.lib=C.CDLL(str(dll));cls.lib.performance_case.argtypes=[C.c_uint32,C.POINTER(C.c_uint32)]

    @classmethod
    def tearDownClass(cls):
        import _ctypes
        _ctypes.FreeLibrary(cls.lib._handle);del cls.lib;cls.temp.cleanup()

    def case(self, number):
        out=(C.c_uint32*4)();self.assertEqual(self.lib.performance_case(number,out),0);return list(out)

    def test_aligned_sprite_keys_distribute_without_quadratic_probing(self):
        used,maximum,probes,old_used=self.case(0)
        self.assertLessEqual(old_used,4)
        self.assertGreater(used,2000)
        self.assertLess(maximum,16)
        self.assertLess(probes,4096*4)

    def test_growth_collisions_exact_lookup_and_phase_conflicts_preserve_keys(self):
        self.case(1)

    def test_picking_chart_guard_does_not_capture_ticks_or_new_exploration(self):
        self.case(2)

    def test_full_picking_wrappers_preserve_history_map_and_world_then_normal_updates(self):
        self.case(3)

    def test_full_picking_still_masks_unknown_terrain_and_restores_rows(self):
        self.case(4)

if __name__=='__main__':unittest.main()
