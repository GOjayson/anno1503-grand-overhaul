"""A current-draw scalar index preserves rectangle order and owner guards.

The isolated native fixture never opens Anno or executes its GPU renderer.
"""
import ctypes as C
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_world_visibility_native import FIXTURE, NATIVE, ROOT

ALLOCATOR=r'''
static uint32_t indexTestFail,indexTestAllocations,indexTestFrees;static size_t indexTestBytes;
static void*indexTestAllocate(size_t bytes){indexTestAllocations++;indexTestBytes=bytes;return indexTestFail?0:malloc(bytes);}
static void indexTestFree(void*pointer){if(pointer)indexTestFrees++;free(pointer);}
#define WS_VISIBILITY_INDEX_ALLOC(bytes) indexTestAllocate(bytes)
#define WS_VISIBILITY_INDEX_FREE(pointer) indexTestFree(pointer)
'''
EXTRA=r'''
static const WSVisibilityIsland*indexReference(const WSVisibilityDrawContext*c,float x,float z){
 for(uint32_t id=0;id<WS_VISIBILITY_ISLAND_LIMIT;id++)if(c->present[id]){
  const WSVisibilityIsland*p=c->islands+id;
  if(x>=(float)p->x&&z>=(float)p->y&&x<(float)(p->x+p->width)&&z<(float)(p->y+p->height))return p;
 }
 return 0;
}
static int indexPointEqual(const WSVisibilityDrawContext*c,float x,float z){return wsVisibilityIslandAt(c,x,z)==indexReference(c,x,z);}
__declspec(dllexport) int island_index_case(uint32_t which,uint32_t size){
 WSVisibilityDrawContext c;memset(&c,0,sizeof c);c.view.width=c.view.height=size;
 WSVisibilityFastDraw*f=(WSVisibilityFastDraw*)calloc(1,sizeof(*f));if(!f)return 99;c.fast=f;int result=0;
 indexTestFail=indexTestAllocations=indexTestFrees=0;indexTestBytes=0;
 if(which==0){
  for(uint32_t scenario=0;scenario<6;scenario++){
   memset(c.present,0,sizeof c.present);memset(c.islands,0,sizeof c.islands);
   uint32_t count=scenario==0?0u:(scenario==1?4u:(scenario==3?128u:24u));
   for(uint32_t n=0;n<count;n++){
    uint32_t id=(n*37u+17u)%255u;WSVisibilityIsland*p=c.islands+id;c.present[id]=1;p->id=id;
    if(scenario<=3){p->x=(n%16u)*16u;p->y=(n/16u)*16u;p->width=p->height=16u;}
    if(scenario==4){p->x=(n%6u)*32u;p->y=(n/6u)*32u;p->width=9u+n%7u;p->height=5u+n%11u;}
    if(scenario==5){p->x=32u+(n%3u)*8u;p->y=32u+(n%4u)*8u;p->width=p->height=32u;}
   }
   wsVisibilityIslandIndexPrepare(&c,f);if(!f->islandIndex){result=1;goto done;}
   uint32_t seed=123456789u;
   for(uint32_t n=0;n<100000u;n++){
    seed=seed*1664525u+1013904223u;float x=(float)(seed%(size*1024u))/1024.0f;
    seed=seed*1664525u+1013904223u;float z=(float)(seed%(size*1024u))/1024.0f;
    if(!indexPointEqual(&c,x,z)){result=2;goto done;}
   }
   const float delta[]={-0.25f,0,0.25f,0.99999f};
   for(uint32_t id=0;id<255u;id++)if(c.present[id]){
    const WSVisibilityIsland*p=c.islands+id;
    for(uint32_t edge=0;edge<4;edge++)for(uint32_t dx=0;dx<4;dx++)for(uint32_t dz=0;dz<4;dz++){
     float x=(float)(edge&1u?p->x+p->width:p->x)+delta[dx],z=(float)(edge&2u?p->y+p->height:p->y)+delta[dz];
     if(!indexPointEqual(&c,x,z)){result=3;goto done;}
    }
   }
   uint32_t specials[]={0xff800000u,0xbf800000u,0x80000000u,0u,0x7f800000u,0x7fc00000u};
   for(uint32_t x=0;x<6;x++)for(uint32_t z=0;z<6;z++){
    float px,pz;memcpy(&px,specials+x,4);memcpy(&pz,specials+z,4);if(!indexPointEqual(&c,px,pz)){result=4;goto done;}
   }
   wsVisibilityIslandIndexRelease(f);
  }
 }else if(which==1){
  c.present[254]=1;c.islands[254]=(WSVisibilityIsland){0,254,size-8u,size-8u,8,8,0};
  wsVisibilityIslandIndexPrepare(&c,f);if(!f->islandIndex||indexTestBytes!=(size_t)(size>>3)*(size>>3)){result=1;goto done;}
  if(wsVisibilityIslandAt(&c,(float)size-0.25f,(float)size-0.25f)!=c.islands+254){result=2;goto done;}
  unsigned char*pointer=f->islandIndex;wsVisibilityIslandIndexPrepare(&c,f);if(f->islandIndex!=pointer||indexTestAllocations!=1u){result=3;goto done;}
  c.view.width=c.view.height=size==256u?512u:256u;
  if(!indexPointEqual(&c,(float)size-0.25f,(float)size-0.25f)){result=4;goto done;}
  wsVisibilityIslandIndexRelease(f);wsVisibilityIslandIndexRelease(f);
  if(f->islandIndex||f->islandIndexWidth||f->islandIndexHeight||indexTestFrees!=1u){result=5;goto done;}
 }else if(which==2){
  c.present[0]=1;c.islands[0]=(WSVisibilityIsland){0,0,8,8,9,13,0};indexTestFail=1;
  wsVisibilityIslandIndexPrepare(&c,f);indexTestFail=0;
  if(f->islandIndex||f->islandIndexWidth||f->islandIndexHeight||indexTestAllocations!=1u||!indexPointEqual(&c,16.5f,20.5f)){result=1;goto done;}
 }else if(which==3){
  for(uint32_t failure=0;failure<8;failure++){
   memset(c.present,0,sizeof c.present);memset(c.islands,0,sizeof c.islands);c.view.width=c.view.height=size;c.present[0]=1;c.islands[0]=(WSVisibilityIsland){0,0,8,8,9,13,0};
   if(failure==0)c.islands[0].width=0;if(failure==1)c.islands[0].x=9;if(failure==2)c.islands[0].y=9;
   if(failure==3)c.islands[0].width=UINT32_MAX;if(failure==4)c.islands[0].height=UINT32_MAX;if(failure==5)c.islands[0].x=UINT32_MAX;
   if(failure==6)c.view.width=c.view.height=4096;if(failure==7)c.view.height=size/2u;
   wsVisibilityIslandIndexPrepare(&c,f);if(f->islandIndex||indexTestAllocations){result=1;goto done;}
  }
 }else result=98;
 done:wsVisibilityIslandIndexRelease(f);free(f);return result;
}
__declspec(dllexport) int island_index_native_allocation_failure(uint32_t fail){
 prepare(wsVisibilityEncode(0,0),1);chartFixtureHouse(20,20);WSVisibilityWorld v;WSVisibilityDrawContext c;
 indexTestFail=fail;indexTestAllocations=indexTestFrees=0;
 if(!wsVisibilityWorldRead(worldBytes,&v)||!wsVisibilityContextRead(&v,&c)||!wsVisibilityFastPrepare(&c,drawRendererBytes)){indexTestFail=0;return 1;}
 indexTestFail=0;int result=0;
 if((c.fast->islandIndex!=0)!=(fail==0)||indexTestAllocations!=1u||wsVisibilityIslandAt(&c,21.5f,21.5f)!=c.islands){result=2;goto done;}
 void*owner=0;if(wsVisibilityOwnedBuilding(&c,c.islands,21.5f,21.5f,&owner)!=1||owner!=enemyBytes){result=3;goto done;}
 ptr(cityBytes+0x28,0);if(wsVisibilityOwnedBuilding(&c,c.islands,21.5f,21.5f,&owner)!=-1){result=4;goto done;}
 done:wsVisibilityFastRelease(&c);if(c.fast||indexTestFrees!=(fail?0u:1u))return 5;return result;
}
'''


@unittest.skipUnless(os.name=='nt','Current-draw native island indexing uses Windows guards.')
class VisibilityIslandIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='anno-visibility-island-index-');folder=Path(cls.temp.name);source=folder/'index.c';dll=folder/'index.dll'
        fixture=FIXTURE.replace('#define WS_CERT_MODULE(name) moduleBytes',ALLOCATOR+'\n#define WS_CERT_MODULE(name) moduleBytes')
        head,tail=fixture.rsplit('#endif',1);source.write_text(head+EXTRA+'\n#endif'+tail)
        compiler=ROOT/'.local/toolchain/ziglang/zig.exe'
        if not compiler.exists():raise unittest.SkipTest('Reviewed native compiler is unavailable.')
        run=subprocess.run([str(compiler),'cc','-target','x86_64-windows-gnu','-std=c11','-shared','-O2','-Wall','-Wextra','-Werror','-I',str(NATIVE),str(source),'-o',str(dll)],capture_output=True,text=True)
        if run.returncode:raise AssertionError(run.stdout+run.stderr)
        cls.lib=C.CDLL(str(dll));cls.lib.island_index_case.argtypes=[C.c_uint32,C.c_uint32];cls.lib.island_index_native_allocation_failure.argtypes=[C.c_uint32]

    @classmethod
    def tearDownClass(cls):
        import _ctypes
        _ctypes.FreeLibrary(cls.lib._handle);del cls.lib;cls.temp.cleanup()

    def test_first_rectangle_order_partial_overlap_fractional_and_nonfinite_points(self):
        for size in (256,512,1024,2048):
            with self.subTest(size=size):self.assertEqual(self.lib.island_index_case(0,size),0)

    def test_far_border_table_size_release_and_context_dimension_fallback(self):
        for size in (256,512,1024,2048):
            with self.subTest(size=size):self.assertEqual(self.lib.island_index_case(1,size),0)

    def test_allocation_failure_and_unindexable_geometry_use_original_scan(self):
        for size in (256,512,1024,2048):
            for case in (2,3):
                with self.subTest(size=size,case=case):self.assertEqual(self.lib.island_index_case(case,size),0)

    def test_optional_index_preserves_native_ownership_checks_and_cleanup(self):
        for fail in (0,1):
            with self.subTest(allocation_failure=fail):self.assertEqual(self.lib.island_index_native_allocation_failure(fail),0)


if __name__=='__main__':unittest.main()
