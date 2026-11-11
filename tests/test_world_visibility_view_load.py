"""Seven-argument in-game View load regression with real checkpoint files.

The authored adapter and byte-extracted chart lifecycle run against a synthetic
Scene/World graph. These checks cover retired-world replacement, rollback,
Windows file locks and native Win64 stack arguments. They do not launch Anno or
establish game UI/GPU acceptance. Exact native-image proofs skip if local inputs
or the optional instruction-emulation tool are unavailable.
"""
import sys
sys.dont_write_bytecode = True
import ctypes as C
import hashlib
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests'), str(ROOT / '.local/toolchain/world-options-validation')]
import test_world_visibility_memory_io as old
import test_world_visibility_ingame_load as prior
from anno1503_overhaul.world_options_visibility import apply_memory_factory



EXTRA = r'''
static uintptr_t viewArgs[7],viewOutput,publishedWorld,retiredWorld;
static int nativeReturn,viewNativeCalls;static uintptr_t expectedOutputArgument;static char nativeFilename[MAX_PATH];
static int32_t nativeViewFactory(int32_t mode,const char*path,void*list,void**out,void*meta,uint32_t index,uint32_t flags){
 viewNativeCalls++;sequencePut('N');viewArgs[0]=(uint32_t)mode;viewArgs[1]=(uintptr_t)path;viewArgs[2]=(uintptr_t)list;viewArgs[3]=(uintptr_t)out;viewArgs[4]=(uintptr_t)meta;viewArgs[5]=index;viewArgs[6]=flags;snprintf(nativeFilename,sizeof nativeFilename,"%s",path);
 *out=sceneBytes;if(fault==6)return (int32_t)0x80004004u;
 unsigned char*data=NULL;uint32_t size=0;BY_HANDLE_FILE_INFORMATION info;char error[512];WSMemoryFile f;
 HANDLE file=wsMemoryReadFile(path,&data,&size,&info,error,sizeof error);
 if(file==INVALID_HANDLE_VALUE)return (int32_t)0x80004005u;
 int ok=wsMemoryParse(data,size,&f,error,sizeof error);CloseHandle(file);free(data);if(!ok)return (int32_t)0x80004005u;
 memset(worldOtherBytes,0,0x7000);wsPut32(worldOtherBytes+0x1d8,f.width);wsPut32(worldOtherBytes+0x1dc,f.height);
 wsPut32(worldOtherBytes+0x1e4,f.viewer);wsPut32(worldOtherBytes+0x6eec,f.policy);memcpy(worldOtherBytes+0x6e4c,f.guid,16);
 if(fault==18)worldOtherBytes[0x6e4c]^=0x55;
 void*p=worldOtherBytes;memcpy(sceneBytes+0x160,&p,8);return nativeReturn;
}
__declspec(dllexport) void fixture_view_reset(void){
 memset(viewArgs,0,sizeof viewArgs);viewOutput=publishedWorld=retiredWorld=0;nativeReturn=viewNativeCalls=viewModuleFault=0;
 sequence[0]=0;transientCalls=0;void*p=(void*)nativeViewFactory;
 moduleBytes[0x11a0]=0x48;moduleBytes[0x11a1]=0xb8;memcpy(moduleBytes+0x11a2,&p,8);moduleBytes[0x11aa]=0xff;moduleBytes[0x11ab]=0xe0;
 FlushInstructionCache(GetCurrentProcess(),moduleBytes+0x11a0,12);
}
__declspec(dllexport) int32_t fixture_view_load(const char*path,int32_t mode,void*list,void*meta,uint32_t index,uint32_t flags,int retire){
 if(retire&&worldBytes){retiredWorld=(uintptr_t)worldBytes;VirtualFree(worldBytes,0,MEM_RELEASE);worldBytes=NULL;sequencePut('F');}
 void*out=(void*)(uintptr_t)0xdeadbeef;expectedOutputArgument=(uintptr_t)&out;
 int32_t loaded=WorldSettingsVisibilityCreateSceneFromView(mode,path,list,&out,meta,index,flags);viewOutput=(uintptr_t)out;
 if(loaded>=0){WSVisibilityWorld v;WSVisibilityChartReadView read;
  if(!out||!wsVisibilityWorldRead(wsCertPointer(out,0x160),&v)||!wsVisibilityChartReadBegin(&v,&read))return (int32_t)0x80004006u;
  wsVisibilityChartReadEnd(&read);publishedWorld=(uintptr_t)v.world;sequencePut('P');
 }return loaded;
}
__declspec(dllexport) uint64_t fixture_view_state(int which){
 if(which>=0&&which<7)return viewArgs[which];
 if(which==7)return viewOutput;if(which==8)return publishedWorld;if(which==9)return retiredWorld;
 if(which==10)return viewNativeCalls;if(which==11)return active.cells?active.cells[0].visual[0]:0;
 if(which==12)return wsChartWorldBinding;if(which==13)return active.width;if(which==14)return (uintptr_t)active.bits;
 if(which==15)return wsMemoryLoad.file||wsMemoryLoad.data;if(which==16)return wsChartLoadIntent;if(which==17)return (uintptr_t)staged.bits;
 if(which==18)return transientCalls;if(which==19)return (uintptr_t)worldOtherBytes;if(which==20)return expectedOutputArgument;return 0;
}
__declspec(dllexport) const char*fixture_sequence(void){return sequence;}
__declspec(dllexport) const char*fixture_native_filename(void){return nativeFilename;}
__declspec(dllexport) void fixture_view_return(int32_t n){nativeReturn=n;}
__declspec(dllexport) void fixture_view_module_fault(int n){viewModuleFault=n;if(n==3){DWORD prior;VirtualProtect(moduleBytes+0x11a0,0x20,PAGE_READONLY,&prior);viewModuleFault=0;}}
__declspec(dllexport) void fixture_view_prior_state(int newGuid){
 active.cells[0].visual[0]=211;active.cells[0].time=39;
 if(newGuid){worldBytes[0x6e4c]^=0x66;active.guid[0]^=0x66;}
}
__declspec(dllexport) int fixture_dimensions(uint32_t side,int checkpoint){
 wsChartCoreFree(&active);wsPut32(worldBytes+0x1d8,side);wsPut32(worldBytes+0x1dc,side);
 if(!wsChartCoreNew(&active,side,side,0,0x1000,worldBytes+0x6e4c))return 0;
 wsChartWorldBinding=(uintptr_t)worldBytes;active.bits[0]=1;active.cells[0].visual[0]=checkpoint?123:211;
 active.cells[0].flags=3;active.cells[0].owner=14;active.cells[0].time=checkpoint?17:39;active.cells[0].logical=checkpoint?123:211;
 if(checkpoint){wsPut32(nativeOutput+32,side);wsPut32(nativeOutput+36,side);}return 1;
}
'''

@unittest.skipUnless(os.name == 'nt', 'Native checkpoint files require Windows sharing and BCrypt.')
class ViewFactoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        zig=ROOT/'.local/toolchain/ziglang/zig.exe'
        if not zig.is_file():raise unittest.SkipTest('Pinned Zig toolchain unavailable.')
        cls.build = tempfile.TemporaryDirectory(prefix='anno-view-native7-build-')
        folder = Path(cls.build.name)
        files = {old.FACTORY: (ROOT / 'legacy/world_settings' / old.FACTORY).read_bytes()}
        apply_memory_factory(files)
        source = old.FIXTURE.replace('static unsigned char worldBytes[0x7000],ownerBytes', 'static unsigned char *worldBytes,*worldOtherBytes;static unsigned char ownerBytes')
        source = source.replace('static WSChartCore active,staged;', '')
        cert = (ROOT/'legacy/world_settings/developer/source/world_certificate/validated_world.inc').read_text()
        source = source.replace(prior.function(source,'wsCertMemory'),prior.function(cert,'wsCertMemory'))
        source = source.replace('if(p!=worldBytes)return 0;', 'if(p!=worldBytes&&p!=worldOtherBytes)return 0;')
        for offset in ('0x1d8','0x1dc','0x6eec','0x1e4'):
            source = source.replace('wsU32(worldBytes+' + offset + ')', 'wsU32((unsigned char*)p+' + offset + ')')
        start=source.index('int WorldSettingsVisibilitySaveBlob(')
        end=source.index('static uintptr_t nativeSave(',start)
        source=source[:start]+prior.REAL_CHART+source[end:]
        source=source.replace('/* STAGED_FACTORY */', files[old.FACTORY].decode())
        source=source.replace('#define WS_CERT_MODULE(name) ((void)(name),(void*)moduleBytes)', 'static int viewModuleFault;static void*fixtureModule(const char*name){(void)name;return viewModuleFault==1?NULL:viewModuleFault==2?moduleBytes+0x1000:moduleBytes;}\n#define WS_CERT_MODULE(name) fixtureModule(name)')
        source=source.replace('WorldSettingsVisibilityCancelLoad();if(priorLock', 'if(!worldBytes)worldBytes=(unsigned char*)VirtualAlloc(NULL,0x7000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);if(!worldOtherBytes)worldOtherBytes=(unsigned char*)VirtualAlloc(NULL,0x7000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);WorldSettingsVisibilityCancelLoad();if(priorLock',1)
        source=source.replace('memset(worldBytes,0,sizeof worldBytes);','memset(worldBytes,0,0x7000);memset(worldOtherBytes,0,0x7000);')
        source=source.replace('active.bits[0]=1;', 'wsChartWorldBinding=(uintptr_t)worldBytes;wsChartFreshBinding=0;active.bits[0]=1;')
        source=source.replace('moduleBytes=NULL;}','moduleBytes=NULL;if(worldBytes)VirtualFree(worldBytes,0,MEM_RELEASE);if(worldOtherBytes)VirtualFree(worldOtherBytes,0,MEM_RELEASE);worldBytes=worldOtherBytes=NULL;}')
        source+=EXTRA
        cls.fixture_sha=hashlib.sha256(source.encode()).hexdigest()
        with (folder/'fixture.c').open('x',encoding='utf-8',newline='\n') as output: output.write(source)
        command=[str(ROOT/'.local/toolchain/ziglang/zig.exe'),'cc','-target','x86_64-windows-gnu','-shared','-O2','-Wall','-Wextra','-Werror','-Wno-unused-function','-I',str(old.NATIVE),str(folder/'fixture.c'),'-o',str(folder/'fixture.dll'),'-lbcrypt','-luser32','-lkernel32']
        result=subprocess.run(command,capture_output=True,text=True)
        if result.returncode:raise AssertionError(result.stdout+result.stderr)
        cls.lib=C.CDLL(str(folder/'fixture.dll'))
        signatures=[('WorldSettingsVisibilityCreateSceneFromView',[C.c_int32,C.c_char_p,C.c_void_p,C.POINTER(C.c_void_p),C.c_void_p,C.c_uint32,C.c_uint32],C.c_int32),('fixture_init',[C.c_char_p,C.c_void_p,C.c_uint32],C.c_int),('fixture_save',[C.c_char_p],C.c_size_t),('fixture_fault',[C.c_int],None),('fixture_counts',[C.c_int],C.c_int),('fixture_lock_prior',[C.c_char_p],C.c_int),('fixture_view_reset',[],None),('fixture_view_load',[C.c_char_p,C.c_int32,C.c_void_p,C.c_void_p,C.c_uint32,C.c_uint32,C.c_int],C.c_int32),('fixture_view_state',[C.c_int],C.c_uint64),('fixture_sequence',[],C.c_char_p),('fixture_native_filename',[],C.c_char_p),('fixture_view_prior_state',[C.c_int],None),('fixture_view_return',[C.c_int32],None),('fixture_view_module_fault',[C.c_int],None),('fixture_dimensions',[C.c_uint32,C.c_int],C.c_int)]
        for name,args,result in signatures:
            fn=getattr(cls.lib,name);fn.argtypes=args;fn.restype=result

    @classmethod
    def tearDownClass(cls):
        import _ctypes
        cls.lib.fixture_finish();_ctypes.FreeLibrary(cls.lib._handle);cls.build.cleanup()

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='anno-view-native7-files-');self.addCleanup(self.tmp.cleanup);self.addCleanup(self.lib.fixture_finish)
        self.folder=Path(self.tmp.name);self.reset_fixture()

    def reset_fixture(self):
        raw=old.native_save()
        self.assertEqual(self.lib.fixture_init(os.fsencode(self.folder),raw,len(raw)),1)
        self.assertEqual(self.lib.fixture_save(b'checkpoint.sav'),0x123456789ABCDEF0)
        self.path=self.folder/'checkpoint.sav';self.saved=self.path.read_bytes();self.lib.fixture_view_reset()

    def load(self,retire=1):
        return self.lib.fixture_view_load(os.fsencode(self.path),0,0x123456789abcdef0,0xfedcba9876543210,0xa1234567,0xe89abcde,retire)

    def assert_clean(self):
        self.assertEqual([self.lib.fixture_view_state(i) for i in (15,16,17)],[0,0,0]);self.assertEqual(self.path.read_bytes(),self.saved)

    def test_retired_old_world_replaced_before_publication(self):
        self.lib.fixture_view_prior_state(1);self.assertEqual(self.load(),0)
        self.assertEqual(self.lib.fixture_sequence(),b'FSNATP')
        self.assertEqual(self.lib.fixture_view_state(11),123)
        self.assertEqual(self.lib.fixture_view_state(8),self.lib.fixture_view_state(19))
        self.assertEqual(self.lib.fixture_view_state(12),self.lib.fixture_view_state(19))
        self.assertNotEqual(self.lib.fixture_view_state(9),self.lib.fixture_view_state(19));self.assert_clean()

    def test_older_checkpoint_rolls_back_same_guid_history(self):
        self.lib.fixture_view_prior_state(0);self.assertEqual(self.load(),0)
        self.assertEqual(self.lib.fixture_view_state(11),123);self.assertEqual(self.lib.fixture_view_state(18),1);self.assert_clean()

    def test_same_guid_1024_to_2048_changes_binding_and_shape(self):
        self.assertEqual(self.lib.fixture_dimensions(2048,1),1);self.assertEqual(self.lib.fixture_save(b'huge.sav'),0x123456789ABCDEF0)
        self.path=self.folder/'huge.sav';self.saved=self.path.read_bytes();self.assertEqual(self.lib.fixture_dimensions(1024,0),1);self.lib.fixture_view_reset()
        self.assertEqual(self.load(),0);self.assertEqual(self.lib.fixture_view_state(13),2048);self.assertEqual(self.lib.fixture_view_state(11),123);self.assert_clean()

    def test_native_seven_arguments_and_positive_hresult_preserved(self):
        self.lib.fixture_view_return(0x12345678);self.assertEqual(self.load(),0x12345678)
        self.assertEqual([self.lib.fixture_view_state(i) for i in (0,2,4,5,6)],[0,0x123456789abcdef0,0xfedcba9876543210,0xa1234567,0xe89abcde])
        self.assertEqual(self.lib.fixture_native_filename(),os.fsencode(self.path))
        self.assertEqual(self.lib.fixture_view_state(3),self.lib.fixture_view_state(20))
        self.assertEqual(self.lib.fixture_sequence(),b'FSNATP');self.assert_clean()

    def test_native_failure_cancels_without_publication_or_double_release(self):
        self.lib.fixture_view_prior_state(0);before=self.lib.fixture_view_state(14);self.lib.fixture_fault(6)
        self.assertEqual(self.load(),C.c_int32(0x80004004).value)
        self.assertEqual(self.lib.fixture_sequence(),b'FSN');self.assertEqual(self.lib.fixture_view_state(7),0);self.assertEqual(self.lib.fixture_view_state(8),0)
        self.assertEqual(self.lib.fixture_view_state(14),before);self.assertEqual(self.lib.fixture_counts(3),0);self.assert_clean()

    def test_corrupt_checkpoint_refused_before_native_or_publication(self):
        corrupted=bytearray(self.saved);corrupted[-1]^=1;self.path.write_bytes(corrupted)
        self.assertLess(self.load(),0);self.assertEqual(self.lib.fixture_sequence(),b'F');self.assertEqual(self.lib.fixture_view_state(10),0);self.assertEqual(self.lib.fixture_view_state(8),0)
        self.path.write_bytes(self.saved);self.assert_clean()

    def test_locked_checkpoint_refused_before_native_or_publication(self):
        self.assertEqual(self.lib.fixture_lock_prior(os.fsencode(self.path)),1)
        self.assertLess(self.load(),0);self.assertEqual(self.lib.fixture_sequence(),b'F');self.assertEqual(self.lib.fixture_view_state(10),0);self.assertEqual(self.lib.fixture_view_state(8),0)
        self.assertEqual([self.lib.fixture_view_state(i) for i in (15,16,17)],[0,0,0])

    def test_apply_or_identity_failure_releases_unpublished_scene_only(self):
        for fault in (4,18):
            with self.subTest(fault=fault):
                self.reset_fixture()
                self.lib.fixture_fault(fault);before=self.lib.fixture_view_state(14)
                self.assertLess(self.load(),0);self.assertEqual(self.lib.fixture_view_state(8),0);self.assertEqual(self.lib.fixture_view_state(7),0)
                self.assertEqual(self.lib.fixture_view_state(14),before);self.assertEqual(self.lib.fixture_counts(3),1);self.assert_clean()

    def test_null_output_rejected_without_native_call(self):
        self.assertEqual(self.lib.WorldSettingsVisibilityCreateSceneFromView(0,os.fsencode(self.path),None,None,None,0,0),C.c_int32(0x80004003).value)
        self.assertEqual(self.lib.fixture_view_state(10),0);self.assertEqual(self.lib.fixture_sequence(),b'');self.assert_clean()

    def test_missing_or_wrong_allocation_scene_module_refuses(self):
        for fault in (1,2,3):
            with self.subTest(fault=fault):
                self.lib.fixture_view_module_fault(fault);self.assertLess(self.load(0),0)
                self.assertEqual(self.lib.fixture_view_state(10),0);self.assertEqual(self.lib.fixture_view_state(7),0);self.assertEqual(self.lib.fixture_sequence(),b'');self.assert_clean()


class NativeSevenStackProof(unittest.TestCase):
    def test_actual_view_call_and_native_seven_stack_arguments(self):
        from anno1503_overhaul.world_runtime_build import PE
        folder=ROOT/'.local/game-copies/World Settings'
        if not all((folder/name).is_file() for name in ('View.dll','AnnoScene.dll')):
            self.skipTest('Exact local HE native input copies unavailable.')
        view=(folder/'View.dll').read_bytes();scene=(folder/'AnnoScene.dll').read_bytes()
        vp,sp=PE(view),PE(scene)
        self.assertEqual(hashlib.sha256(view).hexdigest(),'ed1c13167d6fc9fd220f074da52bb63d396b6a11b722c48a44a2babd8c6f4aef')
        self.assertEqual(hashlib.sha256(scene).hexdigest(),'f7d0685cf6156ff25c518f2f558863b351d7738280467e48dd585a1fefa9537a')
        self.assertEqual(vp.read(0x869b8,6),bytes.fromhex('ff15daa60100'))
        self.assertEqual(vp.read(0x86996,40),bytes.fromhex('44897c24304c8d8dc00300004c8bc044897c2428488d95700100004c897c242033c9ff15daa60100'))
        self.assertEqual(vp.read(0x869be,8),bytes.fromhex('85c00f8851020000'))
        # This exact IAT call preserves the caller's register and stack args.
        try:
            import unicorn as U
            from unicorn import x86_const as X
        except ImportError:
            self.skipTest('Native Win64 call execution needs Unicorn.')
        for base in (0x180000000,0x280000000):
            with self.subTest(base=base):
                cpu=U.Uc(U.UC_ARCH_X86,U.UC_MODE_64);stack=0x31000000;callback=0x32000000;stop=callback+0x100
                cpu.mem_map(base,0xb0000);cpu.mem_map(stack,0x3000);cpu.mem_map(callback,0x1000)
                cpu.mem_write(base+0x869b8,vp.read(0x869b8,6));cpu.mem_write(base+0xa1098,struct.pack('<Q',callback))
                rsp=stack+0x1000;raw=bytearray(bytes(range(1,97)));metadata,index,flags=(0xfedcba9876543210,0xa1234567,0xe89abcde)
                struct.pack_into('<Q',raw,0x20,metadata);struct.pack_into('<I',raw,0x28,index);struct.pack_into('<I',raw,0x30,flags);cpu.mem_write(rsp,bytes(raw))
                values={X.UC_X86_REG_RCX:0x12345678,X.UC_X86_REG_RDX:0x45000000,X.UC_X86_REG_R8:0x46000000,X.UC_X86_REG_R9:0x47000000,X.UC_X86_REG_RSP:rsp}
                nonvol=(X.UC_X86_REG_RBX,X.UC_X86_REG_RBP,X.UC_X86_REG_RSI,X.UC_X86_REG_RDI,X.UC_X86_REG_R12,X.UC_X86_REG_R13,X.UC_X86_REG_R14,X.UC_X86_REG_R15)
                values.update({reg:0x102030400+j*0x100 for j,reg in enumerate(nonvol)})
                for reg,value in values.items():cpu.reg_write(reg,value)
                called=[]
                def recorder(machine,address,size,data):
                    if address!=callback:return
                    called.append(1);self.assertEqual(machine.reg_read(X.UC_X86_REG_RSP),rsp-8)
                    self.assertEqual(struct.unpack('<Q',machine.mem_read(rsp-8,8))[0],base+0x869be)
                    self.assertEqual(bytes(machine.mem_read(rsp,len(raw))),bytes(raw))
                    for reg,value in values.items():
                        if reg!=X.UC_X86_REG_RSP:self.assertEqual(machine.reg_read(reg),value)
                    self.assertEqual(struct.unpack('<Q',machine.mem_read(rsp-8+0x28,8))[0],metadata)
                    self.assertEqual(struct.unpack('<I',machine.mem_read(rsp-8+0x30,4))[0],index)
                    self.assertEqual(struct.unpack('<I',machine.mem_read(rsp-8+0x38,4))[0],flags)
                    machine.reg_write(X.UC_X86_REG_RAX,0x80004004);machine.reg_write(X.UC_X86_REG_RSP,rsp);machine.reg_write(X.UC_X86_REG_RIP,stop)
                cpu.hook_add(U.UC_HOOK_CODE,recorder);cpu.emu_start(base+0x869b8,stop,count=5)
                self.assertEqual(called,[1]);self.assertEqual(cpu.reg_read(X.UC_X86_REG_RAX),0x80004004);self.assertEqual(cpu.reg_read(X.UC_X86_REG_RSP),rsp)


if __name__ == '__main__':
    unittest.main()
