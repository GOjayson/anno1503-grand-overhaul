"""Exact invocation-local readability proofs retain fresh native values.

The123 isolated cases exercise slow, fresh-fast and shared-fast proof routes.
They never open Anno or require private benchmark inputs.
"""
import ctypes as C
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_world_visibility_native import FIXTURE, NATIVE, ROOT

EXTRA=r'''
#ifdef HAS_LEDGER
typedef WSChartInvocationSpans TestSpans;
#else
typedef struct TestSpans {int unused;} TestSpans;
#endif
static uint32_t invocationProofPath;
static int guardProof(const WSVisibilityDrawContext*c,uint16_t id,int full){
 if(invocationProofPath==0)return wsChartAssetGuardSlow(c,id,full);
 if(invocationProofPath==1)return wsChartAssetGuardFast(c,id,full);
 return wsChartAssetGuard(c,id,full);
}
static int chainProof(const WSVisibilityDrawContext*c,WSChartFrameProof*p,TestSpans*spans){
 if(invocationProofPath==0)return wsChartColorChainSlow(c,p);
 if(invocationProofPath==1){TestSpans fresh={0};return wsChartColorChainFast(c,p,&fresh);}
 return wsChartColorChainFast(c,p,spans);
}
static void*endObject(const void*source,size_t bytes,void**allocation){
 unsigned char*pages=(unsigned char*)VirtualAlloc(0,8192,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);if(!pages)return 0;
 unsigned char*pointer=pages+4096-bytes;memcpy(pointer,source,bytes);DWORD previous;if(!VirtualProtect(pages+4096,4096,PAGE_NOACCESS,&previous)){VirtualFree(pages,0,MEM_RELEASE);return 0;}*allocation=pages;return pointer;
}
__declspec(dllexport) int invocationCase(uint32_t which,uint32_t path,uint32_t*out){
 invocationProofPath=path;
 prepare(wsVisibilityEncode(1,0),1);chartFixtureHouse(20,20);WSVisibilityWorld view;WSVisibilityDrawContext c;
 unsigned char extraDefinition[0x300],newTexture[0x28],newPalette[8];void*newArray[1]={chartTexture};void*allocation=0;void*bounded=0;
 memset(extraDefinition,0,sizeof extraDefinition);memcpy(extraDefinition,definitionBytes,sizeof definitionBytes);memcpy(newTexture,chartTexture,sizeof newTexture);memcpy(newPalette,chartPalette,sizeof newPalette);
 if(which==8){
  ptr(chartPalette,moduleBytes+0xf5f750u);ptr(moduleBytes+0xf5f750u+0xf8,moduleBytes+0x244c0u);ptr(moduleBytes+0xf5f750u+0xd0,moduleBytes+0x24d60u);ptr(moduleBytes+0xf5f750u+0xe8,moduleBytes+0x243f0u);
  bounded=endObject(chartPalette,8,&allocation);if(!bounded)return 90;ptr(chartTexture+0x18,bounded);
 }
 if(which==9){bounded=endObject(chartTexture,0x20u,&allocation);if(!bounded)return 90;chartArray[0]=bounded;}
 if(which==11){
  ptr(catalogueBytes+0x218+124u*8u,extraDefinition);
  for(uint32_t n=0;n<4;n++){ptr(definitionBytes+0x268+n*24u,chartFrame);ptr(extraDefinition+0x268+n*24u,chartFrame);}
 }
 if(which==12){bounded=endObject(chartArray,4,&allocation);if(!bounded)return 90;}
 if(!wsVisibilityWorldRead(worldBytes,&view)||!wsVisibilityContextRead(&view,&c)||!wsVisibilityFastPrepare(&c,drawRendererBytes)){if(allocation)VirtualFree(allocation,0,MEM_RELEASE);return 91;}
 int error=0;TestSpans spans={0};
 if(!wsChartAssetGuard(&c,123,0)){error=92;goto done;}
 WSChartAssetProof*proof=(WSChartAssetProof*)c.fast->chartAssets[123];WSChartFrameProof*r=proof->frames;
 if(which==11){
  if(!wsChartAssetGuard(&c,124,0)){error=92;goto done;}
  visibilityReadChecks=0;out[0]=(uint32_t)guardProof(&c,123,1);out[1]=visibilityReadChecks;
  visibilityReadChecks=0;out[2]=(uint32_t)guardProof(&c,124,1);out[3]=visibilityReadChecks;goto done;
 }
 visibilityReadChecks=0;out[0]=(uint32_t)chainProof(&c,r,&spans);out[1]=visibilityReadChecks;if(!out[0]){error=93;goto done;}
 if(which==1)chartArray[0]=newTexture;
 if(which==2)ptr(chartFrame+0x18,newArray);
 if(which==3)ptr(chartTexture+0x18,newPalette);
 if(which==4)ptr(chartTexture,moduleBytes+0xf65000u);
 if(which==5)ptr(moduleBytes+0xf65a50u+0xc0,0);
 if(which==6||which==8)wsPut16(chartTexture+0xa,0);
 if(which==7)ptr(moduleBytes+0xf5f648u+0xf8,0);
 if(which==9){ptr(bounded,moduleBytes+0xf65fc8u);ptr(moduleBytes+0xf65fc8u+0xc0,moduleBytes+0x185a0u);ptr(moduleBytes+0xf65fc8u+0xe0,moduleBytes+0x5f580u);wsPut16((unsigned char*)bounded+0xc,23);}
 if(which==10)ptr(chartFrame+0x18,(void*)(uintptr_t)1);
 if(which==12)ptr(chartFrame+0x18,bounded);
 if(which==13)chartArray[0]=(void*)(uintptr_t)1;
 if(which==14)ptr(chartTexture+0x18,(void*)(uintptr_t)1);
 if(which==15)ptr(moduleBytes+0xf5f648u+0xe8,0);
 if(which==16)ptr(chartFrame+0x18,0);
 visibilityReadChecks=0;out[2]=(uint32_t)chainProof(&c,r,&spans);out[3]=visibilityReadChecks;
 #ifdef HAS_LEDGER
 out[4]=(uint32_t)spans.array.bytes;out[5]=(uint32_t)spans.texture.bytes;out[6]=(uint32_t)spans.palette.bytes;
 if(which==10||which==12)out[7]=(uint32_t)(spans.array.pointer==chartArray);
 if(which==9)out[7]=(uint32_t)(spans.texture.pointer==bounded);
 #endif
 if(which==12){
  DWORD old;if(!VirtualProtect((unsigned char*)allocation+4096,4096,PAGE_READWRITE,&old)){error=94;goto done;}
  ptr(bounded,chartTexture);visibilityReadChecks=0;out[8]=(uint32_t)chainProof(&c,r,&spans);out[9]=visibilityReadChecks;
 }
 done:wsVisibilityFastRelease(&c);if(allocation)VirtualFree(allocation,0,MEM_RELEASE);return error;
}
__declspec(dllexport) int unknownMinimum(uint32_t family,uint32_t variant,uint32_t proofFlags,uint32_t path){
 invocationProofPath=path;
 prepare(wsVisibilityEncode(1,0),1);chartFixtureHouse(20,20);void*allocation=0;void*object=0;size_t extent;
 if(family==0){ptr(definitionBytes,moduleBytes+0x1000u);extent=variant?0x20fu:8u;object=endObject(definitionBytes,extent,&allocation);if(!object)return -90;ptr(catalogueBytes+0x218+123u*8u,object);}
 if(family==1){
  ptr(chartFrame,moduleBytes+0xf65000u);ptr(moduleBytes+0xf65000u+0xc8,moduleBytes+0x17540u);wsPut16(chartFrame+0x38,1);extent=variant?0x40u:8u;
  object=endObject(chartFrame,extent,&allocation);if(!object)return -90;ptr(definitionBytes+0x268,object);
 }
 if(family==2){ptr(chartTexture,moduleBytes+0xf65000u);extent=variant?0x20u:8u;object=endObject(chartTexture,extent,&allocation);if(!object)return -90;chartArray[0]=object;}
 WSVisibilityWorld view;WSVisibilityDrawContext c;int result;
 if(!wsVisibilityWorldRead(worldBytes,&view)||!wsVisibilityContextRead(&view,&c)||!wsVisibilityFastPrepare(&c,drawRendererBytes)){VirtualFree(allocation,0,MEM_RELEASE);return -91;}
 c.fast->chartGameVTSpanReady=(proofFlags&1u)!=0;c.fast->chartDisplayVTSpanReady=(proofFlags&2u)!=0;
 result=guardProof(&c,123,1);wsVisibilityFastRelease(&c);VirtualFree(allocation,0,MEM_RELEASE);return result;
}
'''


@unittest.skipUnless(os.name=='nt','Invocation span adapters use Windows memory guards.')
class VisibilityInvocationSpanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='anno-visibility-invocation-spans-');folder=Path(cls.temp.name);source=folder/'invocation.c';dll=folder/'invocation.dll'
        head,tail=FIXTURE.rsplit('#endif',1);source.write_text('#define HAS_LEDGER 1\n'+head+EXTRA+'\n#endif'+tail)
        compiler=ROOT/'.local/toolchain/ziglang/zig.exe'
        if not compiler.exists():raise unittest.SkipTest('Reviewed native compiler is unavailable.')
        run=subprocess.run([str(compiler),'cc','-target','x86_64-windows-gnu','-std=c11','-shared','-O2','-Wall','-Wextra','-Werror','-I',str(NATIVE),str(source),'-o',str(dll)],capture_output=True,text=True)
        if run.returncode:raise AssertionError(run.stdout+run.stderr)
        cls.lib=C.CDLL(str(dll));cls.lib.invocationCase.argtypes=[C.c_uint32,C.c_uint32,C.POINTER(C.c_uint32)];cls.lib.unknownMinimum.argtypes=[C.c_uint32,C.c_uint32,C.c_uint32,C.c_uint32]

    @classmethod
    def tearDownClass(cls):
        import _ctypes
        _ctypes.FreeLibrary(cls.lib._handle);del cls.lib;cls.temp.cleanup()

    def check_case(self,case,path):
        values=(C.c_uint32*10)();self.assertEqual(self.lib.invocationCase(case,path,values),0);self.assertEqual(values[0],1);self.assertEqual(values[2],int(case in (0,1,2,3,11)));return values

    def test_same_typed_pointer_reuses_only_proven_extents_and_new_pointers_requery(self):
        for path in range(3):
            for case in range(4):
                with self.subTest(path=path,case=case):
                    values=self.check_case(case,path)
                    if path==2:self.assertEqual(values[3],int(case!=0))

    def test_cached_ranges_do_not_cache_fields_vtables_getters_or_format(self):
        for path in range(3):
            for case in (4,5,6,7,13,14,15,16):
                with self.subTest(path=path,case=case):self.check_case(case,path)

    def test_extent_upgrades_failed_proofs_and_repaired_pointer_revalidation(self):
        for path in range(3):
            for case in (8,9,10,12):
                with self.subTest(path=path,case=case):
                    values=self.check_case(case,path)
                    if path==2:
                        if case==8:self.assertEqual((values[6],values[3]),(8,1))
                        if case==9:self.assertEqual((values[5],values[7],values[3]),(0x20,1,1))
                        if case==10:self.assertEqual((values[7],values[4]),(1,8))
                        if case==12:self.assertEqual((values[7],values[8],values[9]),(1,1,1))

    def test_two_asset_guard_invocations_start_with_empty_slots(self):
        for path in range(3):
            with self.subTest(path=path):
                values=self.check_case(11,path)
                self.assertEqual(values[1],values[3])
                if path:self.assertEqual(values[3],3)

    def test_unknown_and_truncated_families_match_native_positive_getter_contracts(self):
        for path in range(3):
            for family in range(3):
                for complete in range(2):
                    for flags in range(4):
                        with self.subTest(path=path,family=family,complete=complete,flags=flags):self.assertEqual(self.lib.unknownMinimum(family,complete,flags,path),int(family==1 and complete==1))


if __name__=='__main__':unittest.main()
