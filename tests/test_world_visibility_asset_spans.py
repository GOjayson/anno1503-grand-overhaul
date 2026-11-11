"""Current-draw span proofs retain exact object extents and late bindings.

Protected native-memory fixtures are isolated and never open Anno.
"""
import ctypes as C
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_world_visibility_native import FIXTURE, NATIVE, ROOT

EXTRA=r'''
static void*boundaryObject(const void*source,size_t size,void**allocation){
 unsigned char*pages=(unsigned char*)VirtualAlloc(0,8192,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);if(!pages)return 0;
 unsigned char*pointer=pages+4096-size;memcpy(pointer,source,size);DWORD previous;
 if(!VirtualProtect(pages+4096,4096,PAGE_NOACCESS,&previous)){VirtualFree(pages,0,MEM_RELEASE);return 0;}
 *allocation=pages;return pointer;
}
__declspec(dllexport) int boundaryCase(uint32_t which,uint32_t proofFlags,uint32_t*out){
 prepare(wsVisibilityEncode(1,0),1);chartFixtureHouse(20,20);void*allocation=0;void*object=0;void*protectedPage=0;DWORD prior=0;int result=0;
 if(which<=3){
  size_t extent=which==0?0x20fu:(which==1?0x20eu:(which==2?0x2c8u:0x2c7u));
  if(which<2){ptr(definitionBytes,moduleBytes+0x1f888u);ptr(moduleBytes+0x1f888u+0x108,moduleBytes+0x1120u);ptr(moduleBytes+0x1f888u+0x148,moduleBytes+0x41d0u);ptr(moduleBytes+0x1f888u+0x150,moduleBytes+0x41d0u);}
  object=boundaryObject(definitionBytes,extent,&allocation);if(!object)return 90;ptr(catalogueBytes+0x218u+123u*8u,object);
 }
 if(which>=4&&which<=7){
  size_t extent=which==4?0x40u:(which==5?0x3fu:(which==6?0x48u:0x40u));
  if(which<6){ptr(chartFrame,moduleBytes+0xf609d0u);wsPut16(chartFrame+0x38,0);wsPut16(chartFrame+0x40,0);ptr(moduleBytes+0xf609d0u+0xc8,moduleBytes+0x17540u);ptr(moduleBytes+0xf609d0u+0xe0,moduleBytes+0x17540u);}
  object=boundaryObject(chartFrame,extent,&allocation);if(!object)return 90;ptr(definitionBytes+0x268,object);
 }
 if(which>=8&&which<=11){
  size_t extent=which==8?0x20u:(which==9?0x1fu:(which==10?0x28u:0x20u));
  if(which>=10){ptr(chartTexture,moduleBytes+0xf65fc8u);ptr(moduleBytes+0xf65fc8u+0xc0,moduleBytes+0x185a0u);ptr(moduleBytes+0xf65fc8u+0xe0,moduleBytes+0x5f580u);wsPut16(chartTexture+0xc,23);ptr(chartTexture+0x20,chartPalette);}
  object=boundaryObject(chartTexture,extent,&allocation);if(!object)return 90;chartArray[0]=object;
 }
 if(which==12||which==13){object=boundaryObject(chartPalette,which==12?8u:4u,&allocation);if(!object)return 90;ptr(chartTexture+0x18,object);}
 if(which==14||which==15){object=boundaryObject(chartArray,which==14?8u:4u,&allocation);if(!object)return 90;ptr(chartFrame+0x18,object);}
 if(which==16){
  /* A genuinely unreadable unused Display VT page defeats the optional broad
   * proof while every individual interface needed by this asset stays valid. */
  uintptr_t low=(uintptr_t)(moduleBytes+0xf61600u),high=(uintptr_t)(moduleBytes+0xf63740u);uintptr_t page=(low+4095u)&~(uintptr_t)4095u;
  if(page+4096u>high){result=91;goto done_no_context;}protectedPage=(void*)page;
  if(!VirtualProtect(protectedPage,4096,PAGE_NOACCESS,&prior)){result=92;goto done_no_context;}
 }
 WSVisibilityWorld view;WSVisibilityDrawContext c;
 if(!wsVisibilityWorldRead(worldBytes,&view)||!wsVisibilityContextRead(&view,&c)||!wsVisibilityFastPrepare(&c,drawRendererBytes)){result=93;goto done_no_context;}
 #ifdef SPAN_CANDIDATE
 if(which!=16){c.fast->chartGameVTSpanReady=(proofFlags&1u)!=0;c.fast->chartDisplayVTSpanReady=(proofFlags&2u)!=0;}
 out[1]=(uint32_t)c.fast->chartGameVTSpanReady|(uint32_t)c.fast->chartDisplayVTSpanReady<<1;
 #else
 (void)proofFlags;out[1]=0;
 #endif
 if(which>=17){
  unsigned char nodes[2][0x238];memset(nodes,0,sizeof nodes);ptr(moduleBytes+0xf33b8u+8u,moduleBytes+0x35210u);ptr(nodes[0],moduleBytes+0xf33b8u);ptr(nodes[1],moduleBytes+0xf33b8u);ptr(nodes[0]+8,nodes[1]);ptr(nodes[1]+8,nodes[0]);
  chartNodes[8]|=0x20u;ptr(chartNodes+16,which==21?0:nodes[0]);
  if(which==18)ptr(nodes[1],moduleBytes+0xf33b0u);
  if(which==19)ptr(moduleBytes+0xf33b8u+8u,0);
  if(which==20)nodes[0][0x230]=5;
  out[0]=(uint32_t)wsChartProducerGuard(&c,c.islands,16,16);
 }else out[0]=(uint32_t)wsChartAssetGuard(&c,123,1);
 wsVisibilityFastRelease(&c);
 done_no_context:
 if(protectedPage){DWORD previous;if(!VirtualProtect(protectedPage,4096,prior,&previous))result=94;}
 if(allocation)VirtualFree(allocation,0,MEM_RELEASE);return result;
}

static void fieldFault(uint32_t which){
 switch(which){
 case 1:ptr(definitionBytes,0);break;
 case 2:ptr(worldBytes+0x200,neighbourDefinition);break;
 case 3:ptr(catalogueBytes,0);break;
 case 4:ptr(moduleBytes+0x20300+0xe8,0);break;
 case 5:ptr(catalogueBytes+0x218+123*8,neighbourDefinition);break;
 case 6:ptr(moduleBytes+0x1fac8+0x108,0);break;
 case 7:ptr(moduleBytes+0x1fac8+0x148,0);break;
 case 8:ptr(moduleBytes+0x1fac8+0x150,0);break;
 case 9:definitionBytes[0xa]=0;break;
 case 10:definitionBytes[0xb]=0;break;
 case 11:ptr(definitionBytes+0x268,(void*)(uintptr_t)1u);break;
 case 12:ptr(chartFrame,moduleBytes+0xf65000);break;
 case 13:ptr(moduleBytes+0xf60af0+0xc8,0);break;
 case 14:wsPut16(chartFrame+0x38,0);break;
 case 15:wsPut16(chartFrame+0x40,1);break;
 case 16:ptr(moduleBytes+0xf60af0+0xd8,0);break;
 case 17:ptr(moduleBytes+0xf60af0+0xf8,0);break;
 case 18:ptr(chartFrame+0x18,0);break;
 case 19:ptr(chartFrame+0x18,(void*)(uintptr_t)1u);break;
 case 20:chartArray[0]=0;break;
 case 21:chartArray[0]=(void*)(uintptr_t)1u;break;
 case 22:ptr(chartTexture,moduleBytes+0xf65000);break;
 case 23:ptr(moduleBytes+0xf65a50+0xc0,0);break;
 case 24:ptr(moduleBytes+0xf65a50+0xe0,0);break;
 case 25:wsPut16(chartTexture+0xa,0);break;
 case 26:ptr(chartTexture+0x18,0);break;
 case 27:ptr(chartTexture+0x18,(void*)(uintptr_t)1u);break;
 case 28:ptr(chartPalette,0);break;
 case 29:ptr(moduleBytes+0xf5f648+0xf8,0);break;
 case 30:ptr(moduleBytes+0xf5f648+0xd0,0);break;
 case 31:ptr(moduleBytes+0xf5f648+0xe8,0);break;
 }
}
__declspec(dllexport) int fieldCase(uint32_t which,uint32_t cached,uint32_t fallback){
 prepare(wsVisibilityEncode(1,0),1);chartFixtureHouse(20,20);WSVisibilityWorld view;WSVisibilityDrawContext c;
 if(!wsVisibilityWorldRead(worldBytes,&view)||!wsVisibilityContextRead(&view,&c)||!wsVisibilityFastPrepare(&c,drawRendererBytes))return -1;
#ifdef REVIEW_PROTOTYPE
 if(fallback)c.fast->chartDisplayVTSpanReady=0;
#else
 (void)fallback;
#endif
 if(cached&&!wsChartAssetGuard(&c,123,1)){wsVisibilityFastRelease(&c);return -2;}
 fieldFault(which);int result=wsChartAssetGuard(&c,123,1);wsVisibilityFastRelease(&c);return result;
}
'''


@unittest.skipUnless(os.name=='nt','Asset span adapters use Windows memory guards.')
class VisibilityAssetSpanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='anno-visibility-asset-spans-');folder=Path(cls.temp.name);source=folder/'spans.c';dll=folder/'spans.dll'
        head,tail=FIXTURE.rsplit('#endif',1);source.write_text('#define SPAN_CANDIDATE 1\n#define REVIEW_PROTOTYPE 1\n'+head+EXTRA+'\n#endif'+tail)
        compiler=ROOT/'.local/toolchain/ziglang/zig.exe'
        if not compiler.exists():raise unittest.SkipTest('Reviewed native compiler is unavailable.')
        run=subprocess.run([str(compiler),'cc','-target','x86_64-windows-gnu','-std=c11','-shared','-O2','-Wall','-Wextra','-Werror','-I',str(NATIVE),str(source),'-o',str(dll)],capture_output=True,text=True)
        if run.returncode:raise AssertionError(run.stdout+run.stderr)
        cls.lib=C.CDLL(str(dll));cls.lib.boundaryCase.argtypes=[C.c_uint32,C.c_uint32,C.POINTER(C.c_uint32)];cls.lib.fieldCase.argtypes=[C.c_uint32,C.c_uint32,C.c_uint32]

    @classmethod
    def tearDownClass(cls):
        import _ctypes
        _ctypes.FreeLibrary(cls.lib._handle);del cls.lib;cls.temp.cleanup()

    def boundary(self,case,flags,expected):
        values=(C.c_uint32*2)();self.assertEqual(self.lib.boundaryCase(case,flags,values),0);self.assertEqual(values[0],expected);return values

    def test_exact_native_minimum_extents_with_unreadable_following_page(self):
        for flags in range(4):
            for case in (0,2,4,6,8,10,12,14):
                with self.subTest(proof_flags=flags,case=case):self.boundary(case,flags,1)

    def test_truncated_definition_frame_texture_palette_and_array_refuse(self):
        for flags in range(4):
            for case in (1,3,5,7,9,11,13,15):
                with self.subTest(proof_flags=flags,case=case):self.boundary(case,flags,0)

    def test_unreadable_unused_display_page_retains_valid_slow_path(self):
        values=self.boundary(16,3,1);self.assertEqual(values[1],1)

    def test_linked_producer_cycles_classes_getters_and_property5_stop(self):
        for flags in range(4):
            for case in range(17,22):
                with self.subTest(proof_flags=flags,case=case):self.boundary(case,flags,int(case in (20,21)))

    def test_fresh_and_cached_binding_getter_period_and_format_changes_refuse(self):
        for cached in (0,1):
            for fallback in (0,1):
                for fault in range(32):
                    with self.subTest(cached=cached,forced_slow=fallback,fault=fault):self.assertEqual(self.lib.fieldCase(fault,cached,fallback),int(fault==0))


if __name__=='__main__':unittest.main()
