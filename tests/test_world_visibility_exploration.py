"""Synthetic native-surface checks, separate from actual Anno/GPU acceptance."""
import ctypes as C
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'src/anno1503_overhaul/native/world_options'
SOURCE = r'''
#include <windows.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
typedef struct WSVisibilityWorld {unsigned char*world,*module;uint32_t width,height,flags,viewer;int32_t map,enemy;int marked;} WSVisibilityWorld;
typedef struct WSVisibilityChartReadView {int held;} WSVisibilityChartReadView;
static unsigned char moduleBytes[0x1100000],worldBytes[64],drawBytes[0x600],surfaceBytes[0x80],parentBytes[0x50],contextBytes[0x20],bits[8192];
static WSVisibilityWorld view;static unsigned char*allocation,*pixels;static size_t pixelBytes;static uint32_t beginCalls,endCalls,pointCalls,chartFault,worldFault,writesChecked;
static uint32_t width,height,rowPixels,viewWidth,viewHeight;
static void ptr(void*p,void*v){memcpy(p,&v,8);}static void u32(void*p,uint32_t v){memcpy(p,&v,4);}static void u16(void*p,uint16_t v){memcpy(p,&v,2);}static void flt(void*p,float v){memcpy(p,&v,4);}
static uint32_t wsU32(const unsigned char*p){uint32_t v;memcpy(&v,p,4);return v;}static uint16_t wsU16(const unsigned char*p){uint16_t v;memcpy(&v,p,2);return v;}
static int readable(DWORD p){p&=255u;return p==PAGE_READONLY||p==PAGE_READWRITE||p==PAGE_WRITECOPY||p==PAGE_EXECUTE_READ||p==PAGE_EXECUTE_READWRITE||p==PAGE_EXECUTE_WRITECOPY;}
static int range(const void*p,size_t n,int writable){uintptr_t at=(uintptr_t)p,end;if(!at||!n||n>UINTPTR_MAX-at)return 0;end=at+n;
 while(at<end){MEMORY_BASIC_INFORMATION m;if(VirtualQuery((void*)at,&m,sizeof m)!=sizeof m||m.State!=MEM_COMMIT||(m.Protect&(PAGE_GUARD|PAGE_NOACCESS))||!readable(m.Protect))return 0;
  DWORD q=m.Protect&255u;if(writable&&q!=PAGE_READWRITE&&q!=PAGE_WRITECOPY&&q!=PAGE_EXECUTE_READWRITE&&q!=PAGE_EXECUTE_WRITECOPY)return 0;
  uintptr_t b=(uintptr_t)m.BaseAddress;if(m.RegionSize>UINTPTR_MAX-b)return 0;uintptr_t next=b+m.RegionSize;if(next<=at)return 0;at=next<end?next:end;}return 1;}
static int wsCertRead(const void*p,void*out,size_t n){if(!range(p,n,0))return 0;memcpy(out,p,n);return 1;}
static void*wsCertPointer(const void*p,size_t off){void*out=0;uintptr_t at=(uintptr_t)p;if(!at||off>UINTPTR_MAX-at||!wsCertRead((void*)(at+off),&out,8))return 0;return out;}
static int wsMineralPersistenceWritable(void*p,size_t n){writesChecked++;return range(p,n,1);}
static int wsVisibilityWithinModule(unsigned char*m,const void*p,size_t n){uintptr_t at=(uintptr_t)p,b=(uintptr_t)m;return m==moduleBytes&&at>=b&&at-b<sizeof moduleBytes&&n<=sizeof moduleBytes-(at-b)&&range(p,n,0);}
static int wsVisibilityWorldRead(void*w,WSVisibilityWorld*out){if(w!=worldBytes||worldFault)return 0;*out=view;return 1;}
static int wsVisibilityFinite(float n){uint32_t b;memcpy(&b,&n,4);return (b&0x7f800000u)!=0x7f800000u;}
#define WS_CERT_MODULE(name) moduleBytes
static int wsVisibilityChartReadBegin(const WSVisibilityWorld*v,WSVisibilityChartReadView*out){beginCalls++;if(chartFault==1||v->world!=worldBytes)return 0;out->held=1;
 if(chartFault==2)ptr(surfaceBytes+0x10,0);if(chartFault==3)u32(drawBytes+0x460,7+viewWidth+1);return 1;}
static void wsVisibilityChartReadEnd(WSVisibilityChartReadView*v){if(v->held){endCalls++;v->held=0;}}
static int wsVisibilityChartPoint(const WSVisibilityWorld*v,float x,float z){pointCalls++;if(!isfinite(x)||!isfinite(z)||x<0||z<0||x>=v->width||z>=v->height)return 0;
 uint32_t index=((uint32_t)z>>3)*(v->width>>3)+((uint32_t)x>>3);return (bits[index>>3]>>(index&7u))&1u;}
#include "start_visibility_exploration.inc"
static void dispose(void){if(allocation)VirtualFree(allocation,0,MEM_RELEASE);allocation=pixels=0;}
static void prepare(uint32_t w,uint32_t h,uint32_t pitch,uint32_t viewportW,uint32_t viewportH,uint32_t worldSize,uint32_t quarter,float scale,double firstX,double firstZ){
 dispose();width=w;height=h;rowPixels=pitch;viewWidth=viewportW;viewHeight=viewportH;pixelBytes=(size_t)pitch*h*4u;
 allocation=(unsigned char*)VirtualAlloc(0,pixelBytes+128,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);pixels=allocation+64;
 memset(allocation,0xa5,pixelBytes+128);for(size_t i=0;i<pixelBytes;i++)pixels[i]=(unsigned char)(i*13u+31u);
 memset(drawBytes,0,sizeof drawBytes);memset(surfaceBytes,0,sizeof surfaceBytes);memset(parentBytes,0,sizeof parentBytes);memset(contextBytes,0,sizeof contextBytes);memset(bits,0,sizeof bits);
 view=(WSVisibilityWorld){worldBytes,moduleBytes,worldSize,worldSize,0x1000,0,0,0,1};
 ptr(contextBytes+8,drawBytes);ptr(contextBytes+0x18,worldBytes);ptr(drawBytes,moduleBytes+0xf63740);u32(drawBytes+0x498,2);
 int32_t viewport[4]={7,11,7+(int32_t)viewportW,11+(int32_t)viewportH};memcpy(drawBytes+0x458,viewport,16);ptr(drawBytes+0x4b0,surfaceBytes);
 ptr(moduleBytes+0xf63740+0x108,moduleBytes+0x43390);ptr(moduleBytes+0xf63740+0x118,moduleBytes+0x483e0);
 ptr(surfaceBytes,moduleBytes+0xf653a0);ptr(surfaceBytes+8,parentBytes);ptr(surfaceBytes+0x10,pixels);u16(surfaceBytes+0x18,(uint16_t)w);u16(surfaceBytes+0x1a,(uint16_t)h);u32(surfaceBytes+0x1c,pitch);u32(surfaceBytes+0x20,0x20080808u);
 ptr(moduleBytes+0xf653a0+0xa8,moduleBytes+0x5e550);ptr(moduleBytes+0xf653a0+0xb0,moduleBytes+0x5e560);ptr(moduleBytes+0xf653a0+0xb8,moduleBytes+0x5e570);ptr(moduleBytes+0xf653a0+0x108,moduleBytes+0x5ea70);
 u32(parentBytes+0x28,w);u32(parentBytes+0x2c,h);u32(parentBytes+0x44,pitch*4);ptr(parentBytes+0x48,pixels);
 float ax[4]={scale,scale,-scale,-scale},az[4]={-scale,scale,scale,-scale},bx[4]={scale/2,-scale/2,-scale/2,scale/2},bz[4]={scale/2,scale/2,-scale/2,-scale/2};
 flt(drawBytes+0xd8,ax[quarter]);flt(drawBytes+0xdc,bx[quarter]);flt(drawBytes+0xf8,az[quarter]);flt(drawBytes+0xfc,bz[quarter]);
 flt(drawBytes+0x108,0);flt(drawBytes+0x118,(float)(7.5-ax[quarter]*firstX-az[quarter]*firstZ));
 flt(drawBytes+0x10c,0);flt(drawBytes+0x11c,(float)(11.5+bx[quarter]*firstX+bz[quarter]*firstZ));
 beginCalls=endCalls=pointCalls=chartFault=worldFault=writesChecked=0;
}
static int canaries(void){for(uint32_t i=0;i<64;i++)if(allocation[i]!=0xa5||pixels[pixelBytes+i]!=0xa5)return 0;return 1;}
static int bitAt(int32_t cx,int32_t cz){if(cx<0||cz<0||cx>=(int32_t)(view.width>>3)||cz>=(int32_t)(view.height>>3))return 0;uint32_t n=(uint32_t)cz*(view.width>>3)+(uint32_t)cx;return (bits[n>>3]>>(n&7u))&1u;}
static uint32_t originalPixel(uint32_t x,uint32_t y){unsigned char b[4];for(uint32_t n=0;n<4;n++)b[n]=(unsigned char)((((size_t)y*rowPixels+x)*4+n)*13u+31u);return wsU32(b);}
static int checkBlack(int all){for(uint32_t y=0;y<height;y++)for(uint32_t x=0;x<rowPixels;x++){
 uint32_t got=wsU32(pixels+((size_t)y*rowPixels+x)*4u),wanted=(!all||x>=viewWidth||y>=viewHeight)?originalPixel(x,y):0xff000000u;if(got!=wanted)return 0;}return canaries();}
__declspec(dllexport) int sea_oracle_case(uint32_t which){
 uint32_t quarter=which%4u,zoom=(which/4u)%10u,phase=(which/40u)%7u,worldSize=256u<<(which/280u);float scales[10]={0.25f,0.5f,1,2,4,0.3f,0.7f,1.1f,2.3f,3.7f};double offsets[7]={0,0.125,7.5,8,8.5,63.75,worldSize-8};
 prepare(67,47,80,63,41,worldSize,quarter,scales[zoom],offsets[phase],offsets[(phase+3)%7]);
 uint32_t cells=worldSize>>3;for(uint32_t cz=0;cz<cells;cz++)for(uint32_t cx=0;cx<cells;cx++)if(((cx*3+cz*5)%7u)<3u){uint32_t n=cz*cells+cx;bits[n>>3]|=(unsigned char)(1u<<(n&7u));}
 if(!wsVisibilityApplyExploredSea(drawBytes,contextBytes)||beginCalls!=1||endCalls!=1){dispose();return 1;}
 float a,b,c,d,t0,t1,t2,t3;memcpy(&a,drawBytes+0xd8,4);memcpy(&b,drawBytes+0xdc,4);memcpy(&c,drawBytes+0xf8,4);memcpy(&d,drawBytes+0xfc,4);memcpy(&t0,drawBytes+0x108,4);memcpy(&t1,drawBytes+0x10c,4);memcpy(&t2,drawBytes+0x118,4);memcpy(&t3,drawBytes+0x11c,4);double determinant=(double)a*d-(double)c*b;
 for(uint32_t y=0;y<height;y++)for(uint32_t x=0;x<rowPixels;x++){
  uint32_t wanted=originalPixel(x,y);
  if(x<viewWidth&&y<viewHeight){double u=7.0+x+0.5-(double)t0-t2,v=(double)t3-(11.0+y+0.5)-t1;double wx=(u*d-c*v)/determinant,wz=(a*v-u*b)/determinant;
   if(!bitAt((int32_t)floor(wx/8.0),(int32_t)floor(wz/8.0)))wanted=0xff000000u;}
  if(wsU32(pixels+((size_t)y*rowPixels+x)*4u)!=wanted){dispose();return 2;}
 }
 /* The per-pass summary samples every chart cell exactly once. Pixel runs
  * then read only scalar summary bytes under the existing chart guard. */
 if(!canaries()||pointCalls!=cells*cells){dispose();return 3;}dispose();return 0;
}
__declspec(dllexport) int sea_guard_case(uint32_t which){
 prepare(64,48,80,29,25,256,0,1,64,64);int result=0;
 if(which==0){if(!wsVisibilityExplorationPreflight(drawBytes,contextBytes)||!checkBlack(0)||beginCalls||!writesChecked)result=1;
  if(!result&&(!wsVisibilityApplyExploredSea(drawBytes,contextBytes)||!checkBlack(1)||beginCalls!=1||endCalls!=1))result=2;
 }else if(which==1){for(int mode=0;mode<3;mode++){view.map=mode;view.marked=mode?1:0;if(!wsVisibilityApplyExploredSea(drawBytes,contextBytes)||!checkBlack(0)||beginCalls){result=1;break;}}
 }else if(which==2){view.marked=-1;if(wsVisibilityApplyExploredSea(drawBytes,contextBytes)||!checkBlack(0))result=1;
 }else if(which==3){flt(drawBytes+0xd8,0);flt(drawBytes+0xf8,0);if(wsVisibilityApplyExploredSea(drawBytes,contextBytes)||!checkBlack(1)||beginCalls)result=1;
 }else if(which==4){u32(drawBytes+0xd8,0x7fc00000u);if(wsVisibilityApplyExploredSea(drawBytes,contextBytes)||!checkBlack(1)||beginCalls)result=1;
 }else if(which==5){chartFault=1;if(wsVisibilityApplyExploredSea(drawBytes,contextBytes)||!checkBlack(1)||beginCalls!=1||endCalls)result=1;
 }else if(which==6){ptr(contextBytes+8,worldBytes);if(wsVisibilityApplyExploredSea(drawBytes,contextBytes)||!checkBlack(0))result=1;
 }else if(which==7){ptr(surfaceBytes,moduleBytes+0xf657a0);if(wsVisibilityApplyExploredSea(drawBytes,contextBytes)||!checkBlack(0))result=1;
 }else if(which==8){u32(surfaceBytes+0x20,0x10050505);if(wsVisibilityApplyExploredSea(drawBytes,contextBytes)||!checkBlack(0))result=1;
 }else if(which==9){u32(parentBytes+0x44,rowPixels*4+4);if(wsVisibilityApplyExploredSea(drawBytes,contextBytes)||!checkBlack(0))result=1;
 }else if(which==10){u32(drawBytes+0x460,7+65);if(wsVisibilityApplyExploredSea(drawBytes,contextBytes)||!checkBlack(0))result=1;
 }else if(which==11){u32(drawBytes+0x460,7);ptr(drawBytes+0x4b0,0);if(!wsVisibilityApplyExploredSea(drawBytes,contextBytes)||!checkBlack(0)||beginCalls)result=1;
 }else if(which==12){ptr(moduleBytes+0xf653a0+0xb8,0);if(wsVisibilityApplyExploredSea(drawBytes,contextBytes)||!checkBlack(0))result=1;
 }else if(which==13){u32(drawBytes+0x498,5);if(wsVisibilityApplyExploredSea(drawBytes,contextBytes)||!checkBlack(0))result=1;
 }else if(which==14){
  dispose();prepare(32,64,32,32,64,256,0,1,64,64);unsigned char*saved=malloc(pixelBytes);memcpy(saved,pixels,pixelBytes);DWORD old;
  uintptr_t page=((uintptr_t)pixels+4095u)&~(uintptr_t)4095u;
  if(!VirtualProtect((void*)page,4096,PAGE_READONLY,&old)){free(saved);dispose();return 9;}
  if(wsVisibilityApplyExploredSea(drawBytes,contextBytes)||memcmp(saved,pixels,pixelBytes)||beginCalls)result=1;
  VirtualProtect((void*)page,4096,old,&old);free(saved);
 }else if(which==15||which==16){chartFault=which-13;if(wsVisibilityApplyExploredSea(drawBytes,contextBytes)||!checkBlack(0)||beginCalls!=1||endCalls!=1)result=1;
 }else if(which==17){view.enemy=1;if(!wsVisibilityApplyExploredSea(drawBytes,contextBytes)||!checkBlack(1)||beginCalls!=1||endCalls!=1)result=1;
 }else result=99;
 dispose();return result;
}
'''


@unittest.skipUnless(os.name == 'nt', 'Exploration surface fixtures use real Windows memory guards.')
class NativeExplorationSurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        zig = ROOT / '.local/toolchain/ziglang/zig.exe'
        if not zig.is_file():
            raise unittest.SkipTest('The reviewed local native toolchain is unavailable.')
        cls.temp = tempfile.TemporaryDirectory(prefix='anno1503-exploration-')
        directory = Path(cls.temp.name)
        source = directory / 'surface.c'
        source.write_text(SOURCE, encoding='utf-8')
        dll = directory / 'surface.dll'
        completed = subprocess.run([str(zig), 'cc', '-target', 'x86_64-windows-gnu', '-shared', '-O2',
                                    '-std=c11', '-I', str(NATIVE), str(source), '-o', str(dll)],
                                   capture_output=True, text=True)
        if completed.returncode:
            cls.temp.cleanup()
            raise AssertionError(completed.stderr)
        cls.lib = C.CDLL(str(dll))
        cls.lib.sea_oracle_case.argtypes = [C.c_uint32]
        cls.lib.sea_guard_case.argtypes = [C.c_uint32]

    @classmethod
    def tearDownClass(cls):
        kernel = C.WinDLL('kernel32', use_last_error=True)
        kernel.FreeLibrary.argtypes = [C.c_void_p]
        kernel.FreeLibrary(cls.lib._handle)
        cls.temp.cleanup()

    def test_all_quarters_zooms_and_cell_boundaries_match_pixel_oracle(self):
        for case in range(1120):
            with self.subTest(case=case):
                self.assertEqual(self.lib.sea_oracle_case(case), 0)

    def test_opaque_black_preserves_charted_pixels_padding_and_ui(self):
        for case in (0, 17):
            with self.subTest(case=case):
                self.assertEqual(self.lib.sea_guard_case(case), 0)

    def test_legacy_revealed_modes_and_empty_viewports_delegate(self):
        for case in (1, 11):
            with self.subTest(case=case):
                self.assertEqual(self.lib.sea_guard_case(case), 0)

    def test_chart_or_projection_failure_blacks_validated_viewport(self):
        for case in (3, 4, 5):
            with self.subTest(case=case):
                self.assertEqual(self.lib.sea_guard_case(case), 0)

    def test_changed_interfaces_or_bounds_refuse_without_writing(self):
        for case in (2, 6, 7, 8, 9, 10, 12, 13, 15, 16):
            with self.subTest(case=case):
                self.assertEqual(self.lib.sea_guard_case(case), 0)

    def test_readonly_second_page_refuses_before_partial_pixel_writes(self):
        self.assertEqual(self.lib.sea_guard_case(14), 0)
