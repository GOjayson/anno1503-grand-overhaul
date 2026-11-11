"""Within-draw remembered-quad unions preserve frozen helper inputs.

Real Windows memory guards protect an isolated synthetic graph. Native helper
boundaries are spies; original native compositionality is audited separately.
"""
import ctypes as C
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_world_visibility_native import FIXTURE, NATIVE, ROOT

EXTRA=r'''
static void batchStatic1(void*q,const uint16_t*xy,uint32_t n,void*r){batchCalls[1]++;spyChartStatic1(q,xy,n,r);}
static void batchStatic2(void*q,const uint16_t*xy,uint32_t n,void*r){batchCalls[2]++;spyChartStatic2(q,xy,n,r);}
static void batchStatic3(void*q,const uint16_t*xy,uint32_t n,void*r){batchCalls[3]++;spyChartStatic3(q,xy,n,r);}
static void batchColor(void*q,const uint16_t*xy,uint32_t f,uint32_t n,void*r){batchCalls[4]++;spyChartColor(q,xy,f,n,r);}
static void batchAllQuads(void){listBytes[8+0x4d]=15;memset(listBytes+8+0x38,0,4);for(uint32_t q=0;q<4;q++)ptr(listBytes+16+q*8,quadBytes);}
static void batchTile(uint32_t x,uint32_t z,uint32_t rotation,uint32_t phase){wsPut32(physicalTiles+((z-16u)*16u+x-16u)*8u,123u|(rotation<<22)|(phase<<24)|0x80000000u);}
static void batchPosition(float x,float z){memcpy(humanShip+0x28,&x,4);memcpy(humanShip+0x30,&z,4);}
static int batchBegin(WSVisibilityDrawContext*c,uint32_t mode){
 WSVisibilityWorld view;wsPut32(drawRendererBytes+0x498,mode);memset(batchCalls,0,sizeof batchCalls);
 return wsVisibilityWorldRead(worldBytes,&view)&&wsVisibilityContextRead(&view,c)&&wsVisibilityFastPrepare(c,drawRendererBytes)&&wsVisibilityChartBeginDraw(c,listBytes,2000,drawRendererBytes,0);
}
static int batchQuery(WSVisibilityDrawContext*c,uint32_t x,uint32_t z,uint32_t rotation,uint32_t kind,uint32_t time,int expected){
 static const uint32_t callers[]={0,0xc4d35,0xc504f,0xc538f,0xc5760};float point[3]={(float)x+1.5f,0,(float)z+1.5f};uint32_t phase=999,flags=kind==4?0x5c0u:0x1c0u;
 int actual=wsVisibilityChartGhostSprite(c,chartFrame,rotation*4u,(uintptr_t)(moduleBytes+callers[kind]),point,&phase,&flags);
 return actual==expected&&phase==(expected==1?(27u+(kind>=3?time/50u:0u)):999u)&&flags==(kind==4?0x5c0u:0x1c0u);
}
static int batchEnd(WSVisibilityDrawContext*c){int ok=wsVisibilityChartEndDraw(c);wsVisibilityFastRelease(c);return ok&&!wsChartReadTLS&&!wsVisibilityBackupCount&&!wsChartRetiredBytes;}
__declspec(dllexport) int batch_case(uint32_t which,uint32_t mode,uint32_t rotation){
 prepare(wsVisibilityEncode(1,0),1);chartFixtureHouse(20,20);batchAllQuads();WSVisibilityDrawContext c;memset(&c,0,sizeof c);int result=0;
 if(which==0){
  memset(physicalTiles,0,sizeof physicalTiles);definitionBytes[0xa]=definitionBytes[0xb]=1;
  for(uint32_t n=0;n<3;n++)batchTile(20+n,20,rotation,27);wsPut16(chartFrame+0x40,mode>=10?0:2);uint32_t actualMode=mode%10;
  batchPosition(22,22);if(!chartFixtureObserve(500))return 1;wsChartActive.cells[20u*256u+21u].time=550;batchPosition(128,128);
  unsigned char before[sizeof listBytes],physicalBefore[sizeof physicalTiles];memcpy(before,listBytes,sizeof before);memcpy(physicalBefore,physicalTiles,sizeof physicalBefore);
  if(!batchBegin(&c,actualMode))return 2;WSChartDraw*d=(WSChartDraw*)c.chartDraw;if(!d){result=3;goto done;}
  int animated=mode<10;uint32_t expected=animated?(actualMode==0||actualMode==3?6u:3u):(actualMode==2?0u:6u);
  if(d->ghostCount!=expected||batchCalls[1]!=(actualMode!=2)||batchCalls[2]!=(actualMode!=2)||batchCalls[3]!=(uint32_t)(animated&&actualMode!=2)*2u||batchCalls[4]!=(uint32_t)(animated&&actualMode!=1)*2u){result=4;goto done;}
  for(uint32_t n=0;n<3;n++)for(uint32_t kind=1;kind<=4;kind++){
   int present=kind<3?(!animated&&actualMode!=2):(animated&&(kind==3?actualMode!=2:actualMode!=1));
   if(!batchQuery(&c,20+n,20,rotation,kind,n==1?550u:500u,present)){result=5;goto done;}
  }
  if(memcmp(physicalBefore,physicalTiles,sizeof physicalBefore)){result=6;goto done;}
  if(!batchEnd(&c)||memcmp(before,listBytes,sizeof before))return 7;return 0;
 }
 if(which==1){
  memset(physicalTiles,0,sizeof physicalTiles);definitionBytes[0xa]=definitionBytes[0xb]=1;batchTile(24,20,rotation,27);batchTile(28,20,rotation,27);
  batchPosition(22,22);if(!chartFixtureObserve(500))return 1;batchTile(24,20,rotation,42);batchTile(28,20,rotation,42);batchPosition(74,20);
  if(!batchBegin(&c,mode))return 2;WSChartCell*hidden=wsChartActive.cells+20u*256u+24u,*live=wsChartActive.cells+20u*256u+28u;
  if(hidden->time!=500u||live->time!=2000u||(hidden->visual[3]&63u)!=27u||(live->visual[3]&63u)!=42u){result=3;goto done;}
  for(uint32_t kind=3;kind<=4;kind++){
   int present=kind==3?mode!=2:mode!=1;if(!batchQuery(&c,24,20,rotation,kind,500,present)||!batchQuery(&c,28,20,rotation,kind,2000,0)){result=4;goto done;}
  }
  if(!batchEnd(&c))return 5;return 0;
 }
 if(which==2){
  memset(physicalTiles,0,sizeof physicalTiles);chartFixtureHouse(23,23);batchAllQuads();batchPosition(24,24);if(!chartFixtureObserve(500))return 1;
  for(uint32_t z=23;z<26;z++)for(uint32_t x=23;x<26;x++){
   WSChartCell*r=wsChartActive.cells+(size_t)z*256u+x;r->visual[3]|=0x40;r->visual[5]=0xc0;r->rootCode=(unsigned char)((r->rootCode&63u)|(rotation<<6));r->visual[2]=(unsigned char)((r->visual[2]&63u)|(rotation<<6));r->time=1000u+(z-23u)*150u+(x-23u)*50u;
  }
  /* The final non-renderable continuation still sets the per-quad time. */
  wsChartActive.cells[25u*256u+25u].visual[3]&=~0x40u;batchPosition(128,128);
  if(!batchBegin(&c,mode))return 2;WSChartDraw*d=(WSChartDraw*)c.chartDraw;uint32_t expected=(mode==0||mode==3)?16u:8u;
  if(!d||d->ghostCount!=expected){result=3;goto done;}
  for(uint32_t z=23;z<26;z++)for(uint32_t x=23;x<26;x++)if(x!=25||z!=25){
   uint32_t endX=x<24?23u:25u,endZ=z<24?23u:25u,time=1000u+(endZ-23u)*150u+(endX-23u)*50u;
   for(uint32_t kind=3;kind<=4;kind++)if(!batchQuery(&c,x,z,rotation,kind,time,kind==3?mode!=2:mode!=1)){result=4;goto done;}
  }
  if(batchCalls[1]!=(uint32_t)(mode!=2)*4u||batchCalls[2]!=(uint32_t)(mode!=2)*4u||batchCalls[3]!=(uint32_t)(mode!=2)*4u||batchCalls[4]!=(uint32_t)(mode!=1)*4u){result=5;goto done;}
  if(!batchEnd(&c))return 6;return 0;
 }
 if(which==3){
  batchPosition(22,22);if(!chartFixtureObserve(500))return 1;batchPosition(128,128);if(!batchBegin(&c,1))return 2;
  WSChartDraw*d=(WSChartDraw*)c.chartDraw;uint32_t count=d->ghostCount;WSChartGhost duplicate={0};
  for(uint32_t n=0;n<d->ghostCapacity;n++)if(d->ghosts[n].used){duplicate=d->ghosts[n];break;}
  if(!duplicate.used||!wsChartGhostInsert(d,&duplicate)||d->ghostCount!=count){result=3;goto done;}duplicate.phase++;
  if(wsChartGhostInsert(d,&duplicate)||d->ghostCount!=count){result=4;goto done;}
  ptr(moduleBytes+0xf5f648+0xe8,0);if(!batchQuery(&c,20,20,0,3,500,-1)){result=5;goto done;}ptr(moduleBytes+0xf5f648+0xe8,moduleBytes+0x243f0);
  if(!batchQuery(&c,20,20,0,3,500,1)){result=6;goto done;}if(!batchEnd(&c))return 7;return 0;
 }
 if(which==4){
  batchPosition(22,22);if(!chartFixtureObserve(500))return 1;batchPosition(128,128);wsPut16(chartFrame+0x40,1);unsigned char before[sizeof listBytes];memcpy(before,listBytes,sizeof before);
  if(batchBegin(&c,1)||memcmp(before,listBytes,sizeof before)||wsChartReadTLS||c.chartDraw||wsChartRetiredBytes)return 2;wsVisibilityFastRelease(&c);return 0;
 }
 if(which==5){
  wsPut16(chartFrame+0x40,0);ptr(chartFrame,moduleBytes+0xf609d0);wsPut16(chartFrame+0x38,0);ptr(moduleBytes+0xf609d0+0xc8,moduleBytes+0x17540);ptr(moduleBytes+0xf609d0+0xe0,moduleBytes+0x17540);
  batchPosition(22,22);if(!chartFixtureObserve(500))return 1;batchPosition(128,128);if(!batchBegin(&c,mode))return 2;
  if(batchCalls[3]||batchCalls[4]||batchCalls[1]!=(uint32_t)(mode!=2)||batchCalls[2]!=(uint32_t)(mode!=2)){result=3;goto done;}
  if(!batchEnd(&c))return 4;return 0;
 }
 if(which==6){wsVisibilityFastRelease(&c);return chart_case(mode);}
 result=99;
 done:wsVisibilityChartEndDraw(&c);wsVisibilityFastRelease(&c);return result;
}
'''

def batch_fixture():
    fixture=FIXTURE.replace('static uint32_t visibilityReadChecks,stackQueryFault;','static uint32_t visibilityReadChecks,stackQueryFault;static uint32_t batchCalls[5];')
    declarations='\n'.join('static void batchStatic%d(void*,const uint16_t*,uint32_t,void*);'%i for i in (1,2,3))+'\nstatic void batchColor(void*,const uint16_t*,uint32_t,uint32_t,void*);\n'
    fixture=fixture.replace('#define WS_CHART_NATIVE_PRODUCER(module) spyChartProducer',declarations+'#define WS_CHART_NATIVE_PRODUCER(module) spyChartProducer')
    fixture=fixture.replace('((kind)==1?spyChartStatic1:((kind)==2?spyChartStatic2:spyChartStatic3))','((kind)==1?batchStatic1:((kind)==2?batchStatic2:batchStatic3))').replace('#define WS_CHART_NATIVE_COLOR(module) spyChartColor','#define WS_CHART_NATIVE_COLOR(module) batchColor')
    marker='float point[3]={(float)(xy[0]+(cell&7u))+1.5f'
    fixture=fixture.replace(marker,'if((kind<=2u&&wsU16(chartFrame+0x40))||(kind>=3u&&!wsU16(chartFrame+0x40)))continue;\n  '+marker)
    head,tail=fixture.rsplit('#endif',1);return head+EXTRA+'\n#endif'+tail

@unittest.skipUnless(os.name=='nt','Scoped native batching adapters use Windows memory guards.')
class VisibilityBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='anno-visibility-batches-');folder=Path(cls.temp.name);source=folder/'batch.c';dll=folder/'batch.dll';source.write_text(batch_fixture())
        compiler=ROOT/'.local/toolchain/ziglang/zig.exe'
        if not compiler.exists():raise unittest.SkipTest('Reviewed native compiler is unavailable.')
        run=subprocess.run([str(compiler),'cc','-target','x86_64-windows-gnu','-std=c11','-shared','-O2','-Wall','-Wextra','-Werror','-I',str(NATIVE),str(source),'-o',str(dll)],capture_output=True,text=True)
        if run.returncode:raise AssertionError(run.stdout+run.stderr)
        cls.lib=C.CDLL(str(dll));cls.lib.batch_case.argtypes=[C.c_uint32,C.c_uint32,C.c_uint32]

    @classmethod
    def tearDownClass(cls):
        import _ctypes
        _ctypes.FreeLibrary(cls.lib._handle);del cls.lib;cls.temp.cleanup()

    def check(self,case,mode=0,rotation=0):
        with self.subTest(case=case,mode=mode,rotation=rotation):self.assertEqual(self.lib.batch_case(case,mode,rotation),0)

    def test_static_and_mixed_time_animation_unions_all_normal_modes_and_rotations(self):
        for mode in range(4):
            for rotation in range(4):
                self.check(0,mode,rotation);self.check(0,mode+10,rotation)

    def test_live_figures_in_same_quad_are_excluded_from_remembered_commands(self):
        for mode in range(4):
            for rotation in range(4):self.check(1,mode,rotation)

    def test_crossquad_phase_uses_last_matching_cell_in_each_quad(self):
        for mode in range(4):
            for rotation in range(4):self.check(2,mode,rotation)

    def test_duplicate_phase_conflicts_and_late_asset_rebinding_still_refuse(self):self.check(3)

    def test_bad_animated_asset_refuses_before_borrowed_pointer_publication(self):self.check(4)

    def test_exact_period_zero_noop_frame_remains_valid_in_all_normal_modes(self):
        for mode in range(4):self.check(5,mode)

    def test_readonly_preflight_restore_and_quarantine_contracts_remain_active(self):
        for case in (7,8,13):self.check(6,case)

    def test_picking_remains_readonly_after_batching(self):
        self.check(6,5)

if __name__=='__main__':unittest.main()
