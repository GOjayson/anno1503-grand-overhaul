"""Current-call context spans preserve fresh fields and narrow fallbacks.

An isolated native adapter compares the original guarded IslandRead with the
current function. It never opens Anno or measures actual game performance.
"""
import ctypes as C
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_world_visibility_native import FIXTURE, NATIVE, ROOT

PROBES = '\nstatic unsigned char*spanTarget;static uint32_t spanForce,spanMutate,spanDone,spanOrder;\nstatic uint64_t spanQueries,spanProbes,spanForced;static void*spanSlot,*spanReplacement;\nstatic void spanMemoryProbe(const void*p,size_t n){\n if(spanMutate==7u&&p==spanSlot&&n==8u&&!spanDone){memcpy(spanSlot,&spanReplacement,8);spanDone=1;}\n}\nstatic void spanFieldProbe(uint32_t phase){\n spanOrder=(spanOrder<<3)|phase;\n if(spanDone||!spanTarget)return;\n if(spanMutate==1u&&phase==1u){void*p=0;memcpy(spanTarget+0x38,&p,8);spanDone=1;}\n if(spanMutate==2u&&phase==3u){uint16_t known=0xa55a;memcpy(spanTarget+0x12e,&known,2);spanDone=1;}\n if(spanMutate==3u&&phase==4u){uint16_t changed=24;memcpy(spanTarget+8,&changed,2);spanDone=1;}\n if(spanMutate==4u&&phase==1u){memcpy(spanSlot,&spanReplacement,8);spanDone=1;}\n}\n'
REFERENCE = 'static int islandReference(const WSVisibilityWorld*v,uint32_t id,WSVisibilityIsland*out){\n WSVisibilityIsland n={0};void*vt;uint16_t box[4];\n if(!v||!out||id>=WS_VISIBILITY_ISLAND_LIMIT)return 0;\n n.object=(unsigned char*)wsCertPointer(v->world,0x6640u+(size_t)id*8u);\n if(!n.object)return 0;vt=wsCertPointer(n.object,0);\n if((vt!=v->module+0xf2da8&&vt!=v->module+0xf33e8&&vt!=v->module+0xf37a0)||\n    wsCertPointer(n.object,0x38)!=v->world||!wsCertRead(n.object+8,box,sizeof box)||\n    !wsCertRead(n.object+0x12e,&n.discovered,2))return 0;\n n.id=id;n.x=box[0];n.y=box[1];n.width=box[2];n.height=box[3];\n if(!n.width||!n.height||(n.x&7u)||(n.y&7u)||n.x+n.width>v->width||n.y+n.height>v->height)return 0;\n *out=n;return 1;\n}\n'
EXTRA = '\nstatic unsigned char spanOther[0x200];\nstatic void spanReset(void){spanTarget=0;spanForce=spanMutate=spanDone=spanOrder=0;spanQueries=spanProbes=spanForced=0;spanSlot=spanReplacement=0;}\n__declspec(dllexport) int islandSpanCase(uint32_t which,uint32_t reference,uint64_t*out){\n spanReset();prepare(wsVisibilityEncode(1,0),1);memcpy(spanOther,islandBytes,sizeof spanOther);\n WSVisibilityWorld v;if(!wsVisibilityWorldRead(worldBytes,&v))return 1;\n unsigned char*region=0,*object=islandBytes;uint32_t readable=0x200;\n if(which>=10u&&which<=15u){\n  static const uint32_t lengths[6]={0x130u,0x12fu,0x3fu,0x40u,0x200u,0x130u};readable=lengths[which-10u];\n  region=(unsigned char*)VirtualAlloc(0,8192,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);if(!region)return 2;\n  object=region+4096u-readable;memcpy(object,islandBytes,0x200u);\n  DWORD prior=0;if(!VirtualProtect(region+4096u,4096u,which==14u?PAGE_READONLY:PAGE_NOACCESS,&prior)){VirtualFree(region,0,MEM_RELEASE);return 3;}\n  if(which==15u)spanForce=1;\n }\n ptr(worldBytes+0x6640,object);spanTarget=object;spanSlot=worldBytes+0x6640;spanReplacement=spanOther;\n if(which==1u)spanForce=1;\n if(which>=2u&&which<=5u)spanMutate=which-1u;\n if(which==6u)ptr(object,moduleBytes+0xf2da9u);\n if(which==7u)wsPut16(object+12,0);\n if(which==8u)wsPut16(object+8,17);\n if(which==9u)ptr(object+0x38,0);\n if(which==16u){spanMutate=7;WSVisibilityDrawContext context;spanQueries=spanProbes=spanForced=0;\n  int result=wsVisibilityContextRead(&v,&context);out[0]=result;out[1]=spanQueries;out[2]=spanDone;out[3]=context.present[0];return 0;}\n WSVisibilityIsland result,before;memset(&result,0xa5,sizeof result);before=result;\n spanQueries=spanProbes=spanForced=0;int accepted=(reference?islandReference:wsVisibilityIslandRead)(&v,0,&result);\n out[0]=accepted;out[1]=spanQueries;out[2]=spanProbes;out[3]=spanForced;out[4]=spanOrder;out[5]=spanDone;\n out[6]=accepted?(result.object==object?1u:result.object==spanOther?2u:3u):!memcmp(&result,&before,sizeof result);\n if(accepted){out[7]=result.id;out[8]=result.x;out[9]=result.y;out[10]=result.width;out[11]=result.height;out[12]=result.discovered;}\n if(region&&!VirtualFree(region,0,MEM_RELEASE))return 4;return 0;\n}\n__declspec(dllexport) int fastSpanCase(uint32_t which,uint64_t*out){\n spanReset();prepare(wsVisibilityEncode(1,0),1);chartFixtureHouse(20,20);ptr(cityBytes+0x28,humanBytes);ptr(islandBytes+0x10,physicalTiles);\n DWORD protection=0;if(!VirtualProtect(moduleBytes,sizeof moduleBytes,PAGE_EXECUTE_READWRITE,&protection))return 91;\n WSVisibilityWorld v;WSVisibilityDrawContext c;\n if(!wsVisibilityWorldRead(worldBytes,&v)||!wsVisibilityContextRead(&v,&c))return 1;\n if(which==1u)spanForce=2;\n if(which==2u)ptr(drawRendererBytes,moduleBytes+0xf63741u);\n if(which==3u)ptr(catalogueBytes,moduleBytes+0x20301u);\n DWORD gapProtection=0;int gap=which==4u;void*gapPage=(void*)((uintptr_t)(moduleBytes+0xf5f648u)&~(uintptr_t)4095u);\n if(gap&&!VirtualProtect(gapPage,4096u,PAGE_NOACCESS,&gapProtection))return 92;\n spanQueries=spanProbes=spanForced=0;int result=wsVisibilityFastPrepare(&c,drawRendererBytes);\n out[0]=result;out[1]=spanQueries;out[2]=spanForced;\n if(result){out[3]=c.fast->targetsReady;out[4]=c.fast->catalogueReady;out[5]=c.fast->chartDisplayVTSpanReady;out[6]=c.fast->islands[0].ready;}\n wsVisibilityFastRelease(&c);if(gap){DWORD ignored;if(!VirtualProtect(gapPage,4096u,gapProtection,&ignored))return 93;}return 0;\n}\n'


def field_probes(source):
    pairs=(
        ('vt=wsCertPointer(n.object,0);','vt=wsCertPointer(n.object,0);spanFieldProbe(1);'),
        ('memcpy(&vt,n.object,8);','memcpy(&vt,n.object,8);spanFieldProbe(1);'),
        ('wsCertPointer(n.object,0x38)!=v->world','(spanFieldProbe(2),wsCertPointer(n.object,0x38))!=v->world'),
        ('memcpy(&world,n.object+0x38,8);','spanFieldProbe(2);memcpy(&world,n.object+0x38,8);'),
        ('!wsCertRead(n.object+8,box,sizeof box)','!(spanFieldProbe(3),wsCertRead(n.object+8,box,sizeof box))'),
        ('!wsCertRead(n.object+0x12e,&n.discovered,2)','!(spanFieldProbe(4),wsCertRead(n.object+0x12e,&n.discovered,2))'),
        ('memcpy(box,n.object+8,sizeof box);','spanFieldProbe(3);memcpy(box,n.object+8,sizeof box);'),
        ('memcpy(&n.discovered,n.object+0x12e,2);','spanFieldProbe(4);memcpy(&n.discovered,n.object+0x12e,2);'))
    for before,after in pairs:source=source.replace(before,after)
    return source


@unittest.skipUnless(os.name=='nt','Native context spans require Windows page guards.')
class VisibilityContextSpanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='anno-context-spans-');folder=Path(cls.temp.name)
        source=folder/'context.c';dll=folder/'context.dll'
        runtime=(NATIVE/'start_visibility_runtime.inc').read_text()
        macro=runtime.split('#define WS_VISIBILITY_STATIC_TARGET_OK',1)[1].split('\n#endif',1)[0]
        fixture=FIXTURE.replace('#define WS_VISIBILITY_STATIC_TARGET_OK(target) 1\n','').replace('#define WS_VISIBILITY_LEGACY_STATIC_TARGET_OK(target) 1\n','')
        fixture=fixture.replace('#define WS_VISIBILITY_NATIVE_STATIC(target) spyStatic','#define WS_VISIBILITY_NATIVE_STATIC(target) spyStatic\n#define WS_VISIBILITY_STATIC_TARGET_OK'+macro)
        marker='static int wsCertMemory(const void*p,size_t n,int executable){'
        fixture=fixture.replace(marker,PROBES+'\n'+marker)
        fixture=fixture.replace(' visibilityReadChecks++;',' visibilityReadChecks++;spanMemoryProbe(p,n);\n if(p==spanTarget&&n==0x130u){spanProbes++;if(spanForce==1u){spanForced++;return 0;}}\n if(n==0x6bf0u&&spanForce==2u){spanForced++;return 0;}')
        fixture=fixture.replace('if(!VirtualQuery(', 'if((spanQueries++,!VirtualQuery(').replace('sizeof m)||m.State','sizeof m))||m.State')
        fixture=fixture.replace('#include "start_visibility_runtime.inc"',field_probes(runtime))
        head,tail=fixture.rsplit('#endif',1);source.write_text(head+field_probes(REFERENCE)+EXTRA+'\n#endif'+tail,newline='\n')
        compiler=ROOT/'.local/toolchain/ziglang/zig.exe'
        if not compiler.exists():raise unittest.SkipTest('Reviewed native compiler is unavailable.')
        result=subprocess.run([str(compiler),'cc','-target','x86_64-windows-gnu','-std=c11','-shared','-O2','-Wall','-Wextra','-Werror','-I',str(NATIVE),str(source),'-o',str(dll)],capture_output=True,text=True)
        if result.returncode:raise AssertionError(result.stdout+result.stderr)
        cls.lib=C.CDLL(str(dll));cls.lib.islandSpanCase.argtypes=[C.c_uint32,C.c_uint32,C.POINTER(C.c_uint64)]
        cls.lib.fastSpanCase.argtypes=[C.c_uint32,C.POINTER(C.c_uint64)]

    @classmethod
    def tearDownClass(cls):
        import _ctypes
        _ctypes.FreeLibrary(cls.lib._handle);del cls.lib;cls.temp.cleanup()

    def island(self,which,reference=0):
        out=(C.c_uint64*16)();self.assertEqual(self.lib.islandSpanCase(which,reference,out),0);return list(out)

    def test_fresh_field_order_mutations_and_original_refusals(self):
        for case in tuple(range(10))+(16,):
            with self.subTest(case=case):
                current,original=self.island(case),self.island(case,1)
                self.assertEqual((current[0],current[4:13]),(original[0],original[4:13]))
        self.assertEqual(self.island(3)[12],0xa55a)
        self.assertEqual(self.island(16)[0],0)

    def test_minimum_truncation_readonly_and_noaccess_boundaries(self):
        for case in range(10,16):
            with self.subTest(case=case):
                current,original=self.island(case),self.island(case,1)
                self.assertEqual((current[0],current[4:13]),(original[0],original[4:13]))
        self.assertEqual([self.island(c)[0] for c in range(10,16)],[1,0,0,0,1,1])

    def test_one_current_span_removes_redundant_queries_and_slow_fallback_stays_guarded(self):
        current,original=self.island(0),self.island(0,1)
        self.assertEqual((current[1],original[1]),(2,5))
        fallback=self.island(1)
        self.assertEqual((fallback[0],fallback[1],fallback[3]),(1,5,1))

    def test_contained_display_ranges_keep_narrow_fallbacks_and_catalogue_bindings(self):
        expected=((1,[1,1,1,1]),(1,[1,1,0,1]),(0,[0,0,0,0]),(1,[1,0,1,0]),(1,[1,1,0,1]))
        for case,(accepted,bindings) in enumerate(expected):
            with self.subTest(case=case):
                out=(C.c_uint64*8)();self.assertEqual(self.lib.fastSpanCase(case,out),0)
                self.assertEqual((out[0],list(out[3:7])),(accepted,bindings))


if __name__=='__main__':unittest.main()
