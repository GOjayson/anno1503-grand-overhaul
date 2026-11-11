"""In-game filename-load regression using real Windows checkpoint files.

The chart lifecycle is extracted byte-for-byte from authored source; the Scene,
World and native parser graphs are synthetic. These checks exercise file locks,
rollback, five-argument Win64 dispatch and apply-before-publication ordering.
They do not launch Anno or establish GPU/queued-render-copy lifetime acceptance.
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
from anno1503_overhaul.world_options_visibility import apply_memory_factory
from anno1503_overhaul.world_options_visibility_calls import bridge_layout

def sha(data):
    return hashlib.sha256(data).hexdigest()

def function(text, name):
    import re
    match = re.search(r'^.*\b' + re.escape(name) + r'\([^;\n]*\)\s*\{', text, re.M)
    if not match:
        raise AssertionError('Function absent: ' + name)
    begin = match.start()
    pos = text.index('{', match.start())
    depth = 1
    end = pos + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[begin:end]

chart = (old.NATIVE / 'start_visibility_chart.inc').read_text()
prefix = chart.split('typedef struct WSChartFigure')[0]
for removed in ('wsVisibilityChartMarkContext', 'wsVisibilityChartPrepareFresh'):
    prefix = prefix.replace(function(prefix, removed), '')
LIFECYCLE = ('wsChartEnsureLocked', 'wsVisibilityChartReadBegin', 'wsVisibilityChartReadEnd',
             'wsVisibilityChartSaveBlob', 'wsVisibilityChartStageBlob',
             'wsVisibilityChartApplyBlob', 'wsVisibilityChartCancelBlob')
EXTRACTED = {n: sha(function(prefix, n).encode()) for n in LIFECYCLE}
assert all(function(prefix, n) == function(chart, n) for n in LIFECYCLE)

REAL_CHART = r'''
typedef struct WSVisibilityChartReadView {
 const WSChartCore*core;unsigned char*world;uint32_t width,height,viewer,policy,generation;int owned;
 struct WSVisibilityChartReadView*previous;
} WSVisibilityChartReadView;
static uint32_t wsFreshVisibilityCode;static volatile LONG wsVisibilityLastError;
static uint32_t transientCalls;static char sequence[64];
static void sequencePut(char ch){size_t n=strlen(sequence);if(n+1<sizeof sequence){sequence[n]=ch;sequence[n+1]=0;}}
static void wsVisibilityChartTransientReset(void){transientCalls++;sequencePut('T');}
/* REAL_LIFECYCLE */
#define active wsChartActive
#define staged wsChartStaged
int WorldSettingsVisibilitySaveBlob(unsigned char**out,uint32_t*n,char*e,uint32_t cap){if(fault==3)return wsChError(e,cap,"snapshot refused");return wsVisibilityChartSaveBlob(out,n,e,cap);}
int WorldSettingsVisibilityStageBlob(const void*p,uint32_t n,char*e,uint32_t cap){stageCalls++;sequencePut('S');return wsVisibilityChartStageBlob(p,n,e,cap);}
void WorldSettingsVisibilityCancelBlob(void){wsVisibilityChartCancelBlob();}
int WorldSettingsVisibilityApplyBlob(void*w,char*e,uint32_t cap){applyCalls++;sequencePut('A');return fault==4?wsChError(e,cap,"apply refused"):wsVisibilityChartApplyBlob(w,e,cap);}
'''.replace('/* REAL_LIFECYCLE */', prefix)

EXTRA = r'''
static int nativeLoadCalls,nestedResult;static uintptr_t gotArgs[5];static const char*providedPath;static int nativeReturn;
static unsigned char*targetWorld;
static int32_t nativeLoadA8(void*scene,const char*filename,uint32_t index,void*world,unsigned char flag){
 nativeLoadCalls++;sequencePut('N');gotArgs[0]=(uintptr_t)scene;gotArgs[1]=(uintptr_t)filename;gotArgs[2]=index;gotArgs[3]=(uintptr_t)world;gotArgs[4]=flag;
 if(fault==16)nestedResult=WorldSettingsVisibilityLoadFileA8(scene,filename,index,world,flag);
 if(fault==6)return (int32_t)0x80004004u;
 if(fault==17)((char*)providedPath)[0]='?';
 unsigned char*data=0;uint32_t size=0;BY_HANDLE_FILE_INFORMATION info;char error[512];WSMemoryFile f;
 HANDLE file=wsMemoryReadFile(filename,&data,&size,&info,error,sizeof error);if(file==INVALID_HANDLE_VALUE)return (int32_t)0x80004005u;
 int ok=wsMemoryParse(data,size,&f,error,sizeof error);CloseHandle(file);free(data);if(!ok)return (int32_t)0x80004005u;
 unsigned char*w=(unsigned char*)world;memset(w,0,0x7000);wsPut32(w+0x1d8,f.width);wsPut32(w+0x1dc,f.height);wsPut32(w+0x1e4,f.viewer);wsPut32(w+0x6eec,f.policy);memcpy(w+0x6e4c,f.guid,16);
 if(fault==18)w[0x6e4c]^=0x55;
 memcpy((unsigned char*)scene+0x160,&world,8);((unsigned char*)scene)[0x178]=flag;
 return nativeReturn;
}
__declspec(dllexport) void fixture_adapter_reset(int target,int vtKind){
 nativeLoadCalls=nestedResult=nativeReturn=0;memset(gotArgs,0,sizeof gotArgs);providedPath=0;sequence[0]=0;transientCalls=0;wsMemoryInGameLoadBusy=0;
 targetWorld=target?worldOtherBytes:worldBytes;void*vt=moduleBytes+(vtKind==1?0x36108u:vtKind==2?0x3f648u:0x35498u);memcpy(sceneBytes,&vt,8);
 void*fn=moduleBytes+0x3ac0;const uint32_t tables[]={0x35498,0x36108,0x3f648};for(unsigned i=0;i<3;i++)memcpy(moduleBytes+tables[i]+0xa8,&fn,8);
 moduleBytes[0x3ac0]=0x48;moduleBytes[0x3ac1]=0xb8;fn=(void*)nativeLoadA8;memcpy(moduleBytes+0x3ac2,&fn,8);moduleBytes[0x3aca]=0xff;moduleBytes[0x3acb]=0xe0;FlushInstructionCache(GetCurrentProcess(),moduleBytes+0x3ac0,12);
}
__declspec(dllexport) int32_t fixture_ingame_load(const char*path,uint32_t index,unsigned char flag){
 providedPath=path;int32_t result=WorldSettingsVisibilityLoadFileA8(sceneBytes,path,index,targetWorld,flag);
 if(result>=0){WSVisibilityWorld v;WSVisibilityChartReadView read;if(!wsVisibilityWorldRead(targetWorld,&v)||!wsVisibilityChartReadBegin(&v,&read))return (int32_t)0x80004006u;wsVisibilityChartReadEnd(&read);sequencePut('P');}return result;
}
__declspec(dllexport) uint64_t fixture_state(int which){
 if(which==0)return (uint32_t)nativeLoadCalls;if(which==1)return active.cells?active.cells[0].visual[0]:0;
 if(which==2)return wsChartWorldBinding==(uintptr_t)targetWorld;if(which==3)return (uint32_t)wsChartLoadIntent;
 if(which==4)return (uint32_t)nestedResult;if(which==5)return transientCalls;
 if(which==6)return (uintptr_t)active.bits;if(which==7)return (uintptr_t)staged.bits;
 if(which==8)return wsMemoryLoad.file||wsMemoryLoad.data;if(which==9)return active.width;
 return which>=10&&which<15?gotArgs[which-10]:0;
}
__declspec(dllexport) const char*fixture_sequence(void){return sequence;}
__declspec(dllexport) void fixture_return(int32_t value){nativeReturn=value;}
__declspec(dllexport) void fixture_prior_state(int newGuid){active.cells[0].visual[0]=211;active.cells[0].time=39;if(newGuid){worldBytes[0x6e4c]^=0x66;active.guid[0]^=0x66;}}
__declspec(dllexport) int fixture_dimensions(uint32_t side,int checkpoint){
 wsChartCoreFree(&active);wsPut32(worldBytes+0x1d8,side);wsPut32(worldBytes+0x1dc,side);
 if(!wsChartCoreNew(&active,side,side,0,0x1000,worldBytes+0x6e4c))return 0;
 wsChartWorldBinding=(uintptr_t)worldBytes;active.bits[0]=1;active.cells[0].visual[0]=checkpoint?123:211;
 active.cells[0].flags=3;active.cells[0].owner=14;active.cells[0].time=checkpoint?17:39;active.cells[0].logical=checkpoint?123:211;
 if(checkpoint){wsPut32(nativeOutput+32,side);wsPut32(nativeOutput+36,side);}return 1;
}
__declspec(dllexport) void fixture_bad_boundary(int which){void*vt=0;memcpy(&vt,sceneBytes,8);if(which==0){void*bad=moduleBytes+0x3ac1;memcpy((unsigned char*)vt+0xa8,&bad,8);}else if(which==1){memcpy(externalSceneVT,vt,sizeof externalSceneVT);void*foreign=externalSceneVT;memcpy(sceneBytes,&foreign,8);}else{void*foreign=moduleBytes+0x354a0;memcpy(sceneBytes,&foreign,8);}}
'''

@unittest.skipUnless(os.name == 'nt', 'In-game checkpoint files use Windows BCrypt and file sharing.')
class NativeFileLoadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        zig = ROOT / '.local/toolchain/ziglang/zig.exe'
        if not zig.is_file():
            raise unittest.SkipTest('Pinned Zig toolchain unavailable.')
        cls.build = tempfile.TemporaryDirectory(prefix='anno-ingame-load-build-')
        folder = Path(cls.build.name)
        files = {old.FACTORY: (ROOT / 'legacy/world_settings' / old.FACTORY).read_bytes()}
        apply_memory_factory(files)
        source = old.FIXTURE
        source = source.replace('static WSChartCore active,staged;', 'static unsigned char worldOtherBytes[0x7000];')
        source = source.replace('if(p!=worldBytes)return 0;', 'if(p!=worldBytes&&p!=worldOtherBytes)return 0;')
        source = source.replace('wsU32(worldBytes+0x1d8)', 'wsU32((unsigned char*)p+0x1d8)').replace('wsU32(worldBytes+0x1dc)', 'wsU32((unsigned char*)p+0x1dc)').replace('wsU32(worldBytes+0x6eec)', 'wsU32((unsigned char*)p+0x6eec)').replace('wsU32(worldBytes+0x1e4)', 'wsU32((unsigned char*)p+0x1e4)')
        start = source.index('int WorldSettingsVisibilitySaveBlob(')
        end = source.index('static uintptr_t nativeSave(', start)
        source = source[:start] + REAL_CHART + source[end:]
        source = source.replace('/* STAGED_FACTORY */', files[old.FACTORY].decode())
        source = source.replace('active.bits[0]=1;', 'wsChartWorldBinding=(uintptr_t)worldBytes;wsChartFreshBinding=0;active.bits[0]=1;')
        source += EXTRA
        cls.source_sha = sha(source.encode())
        with (folder / 'fixture.c').open('x', encoding='utf-8', newline='\n') as output:
            output.write(source)
        zig = ROOT / '.local/toolchain/ziglang/zig.exe'
        command = [str(zig),'cc','-target','x86_64-windows-gnu','-shared','-O2','-Wall','-Wextra','-Werror','-Wno-unused-function','-I',str(old.NATIVE),str(folder/'fixture.c'),'-o',str(folder/'fixture.dll'),'-lbcrypt','-luser32','-lkernel32']
        result = subprocess.run(command,capture_output=True,text=True)
        if result.returncode:
            raise AssertionError(result.stdout+result.stderr)
        cls.lib=C.CDLL(str(folder/'fixture.dll'))
        for name,args,result in [('fixture_init',[C.c_char_p,C.c_void_p,C.c_uint32],C.c_int),('fixture_save',[C.c_char_p],C.c_size_t),('fixture_load',[C.c_char_p],C.c_int),('fixture_ingame_load',[C.c_char_p,C.c_uint32,C.c_ubyte],C.c_int32),('fixture_state',[C.c_int],C.c_uint64),('fixture_sequence',[],C.c_char_p),('fixture_lock_prior',[C.c_char_p],C.c_int),('fixture_adapter_reset',[C.c_int,C.c_int],None),('fixture_bad_boundary',[C.c_int],None),('fixture_fault',[C.c_int],None),('fixture_prior_state',[C.c_int],None),('fixture_return',[C.c_int32],None),('fixture_dimensions',[C.c_uint32,C.c_int],C.c_int),('WorldSettingsVisibilityBeforeLoad',[C.c_char_p,C.c_void_p,C.c_uint32],C.c_int)]:
            fn=getattr(cls.lib,name);fn.argtypes=args;fn.restype=result

    @classmethod
    def tearDownClass(cls):
        import _ctypes
        cls.lib.fixture_finish();_ctypes.FreeLibrary(cls.lib._handle)
        cls.build.cleanup()

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='anno-ingame-prototype-');self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.lib.fixture_finish)
        self.folder=Path(self.tmp.name);raw=old.native_save();self.assertEqual(self.lib.fixture_init(os.fsencode(self.folder),raw,len(raw)),1)
        self.assertEqual(self.lib.fixture_save(b'checkpoint.sav'),0x123456789ABCDEF0)
        self.path=self.folder/'checkpoint.sav';self.saved=self.path.read_bytes()
        self.lib.fixture_adapter_reset(1,0)

    def load(self,index=0,flag=1):
        return self.lib.fixture_ingame_load(os.fsencode(self.path),index,flag)

    def assert_clean(self):
        self.assertEqual([self.lib.fixture_state(i) for i in (3,7,8)],[0,0,0])
        self.assertEqual(self.path.read_bytes(),self.saved)
        self.assertEqual(self.lib.fixture_counts(3),0)

    def test_new_world_address_and_different_guid_restores_before_publication(self):
        self.lib.fixture_prior_state(1);self.assertEqual(self.load(),0)
        self.assertEqual(self.lib.fixture_sequence(),b'SNATP')
        self.assertEqual([self.lib.fixture_state(i) for i in (0,1,2,5)],[1,123,1,1]);self.assert_clean()

    def test_reallocated_and_reused_same_guid_rollback_for_all_scene_vtables(self):
        for target in (0,1):
            for vt in (0,1,2):
                with self.subTest(target=target,vt=vt):
                    self.lib.fixture_adapter_reset(target,vt);self.lib.fixture_prior_state(0)
                    self.assertEqual(self.load(0x12345678,0xa5),0)
                    self.assertEqual(self.lib.fixture_state(1),123);self.assertEqual(self.lib.fixture_state(2),1)
                    self.assertEqual(self.lib.fixture_state(12),0x12345678);self.assertEqual(self.lib.fixture_state(14),0xa5)
                    self.assert_clean()

    def test_same_guid_1024_to_2048_on_reused_world_restores_exact_shape(self):
        self.assertEqual(self.lib.fixture_dimensions(2048,1),1)
        self.assertEqual(self.lib.fixture_save(b'huge.sav'),0x123456789ABCDEF0)
        self.path=self.folder/'huge.sav';self.saved=self.path.read_bytes()
        self.assertEqual(self.lib.fixture_dimensions(1024,0),1)
        self.lib.fixture_adapter_reset(0,0)
        self.assertEqual(self.load(),0);self.assertEqual(self.lib.fixture_sequence(),b'SNATP')
        self.assertEqual([self.lib.fixture_state(i) for i in (1,2,9)],[123,1,2048]);self.assert_clean()

    def test_missing_history_resets_same_guid_reused_world_conservatively(self):
        self.path=self.folder/'old.sav';self.saved=old.native_save();self.path.write_bytes(self.saved)
        self.lib.fixture_adapter_reset(0,0);self.lib.fixture_prior_state(0)
        self.assertEqual(self.load(),0);self.assertEqual(self.lib.fixture_sequence(),b'SNATP')
        self.assertEqual([self.lib.fixture_state(i) for i in (1,2)],[0,1]);self.assert_clean()

    def test_signed_hresult_preserved_and_native_failure_cancels_only_staging(self):
        self.lib.fixture_prior_state(0);before=self.lib.fixture_state(6);self.lib.fixture_fault(6)
        self.assertEqual(self.load(),C.c_int32(0x80004004).value)
        self.assertEqual(self.lib.fixture_state(6),before);self.assertEqual(self.lib.fixture_state(1),211)
        self.assertEqual(self.lib.fixture_sequence(),b'SN');self.assert_clean()
        self.lib.fixture_fault(0);self.lib.fixture_adapter_reset(1,0);self.lib.fixture_return(0x12345678)
        self.assertEqual(self.load(),0x12345678);self.assertEqual(self.lib.fixture_sequence(),b'SNATP');self.assert_clean()

    def test_corrupt_or_write_locked_checkpoint_refuses_before_native(self):
        before=self.lib.fixture_state(6)
        corrupted=bytearray(self.saved);corrupted[-1]^=1;self.path.write_bytes(corrupted)
        self.assertLess(self.load(),0);self.assertEqual(self.lib.fixture_state(0),0);self.assertEqual(self.lib.fixture_state(6),before)
        self.path.write_bytes(self.saved);self.assertEqual(self.lib.fixture_lock_prior(os.fsencode(self.path)),1)
        self.assertLess(self.load(),0);self.assertEqual(self.lib.fixture_state(0),0);self.assertEqual(self.lib.fixture_state(6),before)
        self.assertEqual([self.lib.fixture_state(i) for i in (3,7,8)],[0,0,0])

    def test_afterload_identity_or_apply_failure_keeps_prior_chart(self):
        for fault in (18,4):
            with self.subTest(fault=fault):
                self.lib.fixture_adapter_reset(1,0);self.lib.fixture_prior_state(0);before=self.lib.fixture_state(6);self.lib.fixture_fault(fault)
                self.assertLess(self.load(),0);self.assertEqual(self.lib.fixture_state(6),before);self.assertEqual(self.lib.fixture_state(1),211)
                self.assertNotIn(b'P',self.lib.fixture_sequence());self.assert_clean()

    def test_foreign_vtable_or_changed_target_refuses_without_staging(self):
        for fault in range(3):
            with self.subTest(fault=fault):
                self.lib.fixture_adapter_reset(1,0);self.lib.fixture_bad_boundary(fault)
                self.assertLess(self.load(),0);self.assertEqual(self.lib.fixture_state(0),0);self.assertEqual(self.lib.fixture_sequence(),b'');self.assert_clean()

    def test_nested_entry_and_existing_factory_owner_do_not_double_stage(self):
        self.lib.fixture_fault(16);self.assertEqual(self.load(),0)
        self.assertEqual(self.lib.fixture_state(4),0x80004005);self.assertEqual(self.lib.fixture_sequence(),b'SNATP');self.assert_clean()
        self.lib.fixture_fault(0);self.lib.fixture_adapter_reset(1,0);error=C.create_string_buffer(512)
        self.assertEqual(self.lib.WorldSettingsVisibilityBeforeLoad(os.fsencode(self.path),error,512),1)
        self.assertLess(self.load(),0);self.assertEqual(self.lib.fixture_sequence(),b'S');self.assertEqual(self.lib.fixture_state(3),1)
        self.lib.WorldSettingsVisibilityCancelLoad();self.assert_clean()

    def test_filename_is_bounded_and_captured_for_native_callback(self):
        path=C.create_string_buffer(os.fsencode(self.path));self.lib.fixture_fault(17)
        self.assertEqual(self.lib.fixture_ingame_load(path,0,1),0);self.assertEqual(path.value[:1],b'?')
        self.assertNotEqual(self.lib.fixture_state(11),C.addressof(path));self.assert_clean()
        for bad in (None,b'',b'X'*260):
            with self.subTest(bad=bad):
                self.lib.fixture_adapter_reset(1,0);self.lib.fixture_fault(0)
                self.assertLess(self.lib.fixture_ingame_load(bad,0,1),0);self.assertEqual(self.lib.fixture_state(0),0)

    def test_original_factory_path_still_stages_and_applies_once(self):
        self.assertEqual(self.lib.fixture_load(os.fsencode(self.path)),1)
        self.assertEqual([self.lib.fixture_counts(i) for i in (1,2,4)],[1,1,1]);self.assertEqual(self.lib.fixture_state(0),0)
        self.assertEqual(self.lib.fixture_sequence(),b'SAT');self.assert_clean()

class NativeLeafProof(unittest.TestCase):
    def test_exact_native_file_load_call_and_scene_adapter_when_available(self):
        from anno1503_overhaul.world_runtime_build import PE
        folder = ROOT / '.local/game-copies/World Settings'
        if not all((folder / name).is_file() for name in ('AnnoFrame.dll', 'AnnoScene.dll')):
            self.skipTest('Exact local HE native input copies unavailable.')
        frame = (folder / 'AnnoFrame.dll').read_bytes()
        scene = (folder / 'AnnoScene.dll').read_bytes()
        self.assertEqual(sha(frame), 'dfd7c76dfc0b017fa5142c46a2bb084c01fc750a049d85ca70b56dca2f555ccd')
        self.assertEqual(sha(scene), 'f7d0685cf6156ff25c518f2f558863b351d7738280467e48dd585a1fefa9537a')
        fp, sp = PE(frame), PE(scene)
        # World in R9, zero index in R8, byte flag 1 at caller RSP+20.
        self.assertEqual(fp.read(0x76b45, 19), bytes.fromhex('4d8bcfc6442420014533c0ff90a800000085c0'))
        # TEST EAX followed by JS proves signed-32 HRESULT, not AL/BOOL.
        self.assertEqual(fp.read(0x76b56, 8), bytes.fromhex('85c00f8875fbffff'))
        self.assertEqual(sp.read(0x3ac0, 28), bytes.fromhex('0fb6442428888178010000488b014c89896001000048ffa0b0000000'))
        scene_base, = sp.unpack('<Q', sp.optional + 24)
        for vt in (0x35498, 0x36108, 0x3f648):
            self.assertEqual(struct.unpack('<Q', sp.read(vt + 0xa8, 8))[0], scene_base + 0x3ac0)

    def test_generated_win64_leaf_preserves_five_arguments_stack_and_nonvolatiles(self):
        try:
            import unicorn as U
            from unicorn import x86_const as X
        except ImportError:
            self.skipTest('Native Win64 leaf execution needs Unicorn.')
        prefix,cell,end=bridge_layout('AnnoFrame.dll',0x76b50);self.assertEqual((cell,end),(8,6))
        for base in (0x180000000,0x280000000):
            with self.subTest(base=base):
                cpu=U.Uc(U.UC_ARCH_X86,U.UC_MODE_64);stack=0x31000000;callback=0x32000000;stop=callback+0x100
                for address,size in ((base,0x1000),(stack,0x3000),(callback,0x1000)):cpu.mem_map(address,size)
                bridge=bytearray(prefix+bytes(8));struct.pack_into('<Q',bridge,cell,callback);cpu.mem_write(base,bytes(bridge))
                rsp=stack+0x1008;raw=bytearray(struct.pack('<Q',stop)+bytes(range(1,97)));raw[0x28]=0xa5;cpu.mem_write(rsp,bytes(raw))
                values={X.UC_X86_REG_RCX:0x44000000,X.UC_X86_REG_RDX:0x45000000,X.UC_X86_REG_R8:0x12345678,X.UC_X86_REG_R9:0x46000000,X.UC_X86_REG_RSP:rsp}
                nonvol=(X.UC_X86_REG_RBX,X.UC_X86_REG_RBP,X.UC_X86_REG_RSI,X.UC_X86_REG_RDI,X.UC_X86_REG_R12,X.UC_X86_REG_R13,X.UC_X86_REG_R14,X.UC_X86_REG_R15)
                values.update({reg:0x102030400+j*0x100 for j,reg in enumerate(nonvol)})
                for reg,value in values.items():cpu.reg_write(reg,value)
                calls=[]
                def recorder(machine,address,size,data):
                    if address!=callback:return
                    calls.append(1);self.assertEqual(machine.reg_read(X.UC_X86_REG_RSP),rsp);self.assertEqual(bytes(machine.mem_read(rsp,len(raw))),bytes(raw))
                    for reg,value in values.items():self.assertEqual(machine.reg_read(reg),value)
                    machine.reg_write(X.UC_X86_REG_RAX,0x80004004);machine.reg_write(X.UC_X86_REG_RSP,rsp+8);machine.reg_write(X.UC_X86_REG_RIP,stop)
                cpu.hook_add(U.UC_HOOK_CODE,recorder);cpu.emu_start(base,stop,count=20)
                self.assertEqual(calls,[1]);self.assertEqual(cpu.reg_read(X.UC_X86_REG_RAX),0x80004004);self.assertEqual(cpu.reg_read(X.UC_X86_REG_RSP),rsp+8)


if __name__ == '__main__':
    unittest.main()
