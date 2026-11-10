"""Checkpoint parser/atomic-file/factory tests; synthetic native save boundary.

These use real Windows files, BCrypt and ReplaceFile on temporary fixtures.
They neither launch Anno nor claim native GPU/save-UI acceptance.
"""
import ctypes as C
import hashlib
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

from anno1503_overhaul.world_options_visibility import apply_memory_factory

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'src/anno1503_overhaul/native/world_options'
FACTORY = 'developer/source/world_factory.c'
FIXTURE = r'''
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <bcrypt.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "start_visibility_policy.h"
#include "start_visibility_chart.h"
static unsigned char worldBytes[0x7000],ownerBytes[0x700],sceneBytes[0x200],externalSceneVT[0x40];
static unsigned char*moduleBytes;static HANDLE priorLock=INVALID_HANDLE_VALUE;
static unsigned char*nativeOutput;static uint32_t nativeSize;static int fault,saveCalls,stageCalls,applyCalls,releaseCalls,factoryCalls,reports;
static int fixtureActive,loadIntent;static char freshPath[MAX_PATH],freshTrace[64];
static void traceFresh(char value){size_t n=strlen(freshTrace);if(n+1<sizeof freshTrace){freshTrace[n]=value;freshTrace[n+1]=0;}}
static WSChartCore active,staged;
static uint16_t wsU16(const void*p){uint16_t n;memcpy(&n,p,2);return n;}
static uint32_t wsU32(const void*p){uint32_t n;memcpy(&n,p,4);return n;}
static void wsPut32(void*p,uint32_t n){memcpy(p,&n,4);}
static void wsMessage(char*p,uint32_t n,const char*s){if(p&&n)snprintf(p,n,"%s",s);}
static int wsCertMemory(const void*p,size_t n,int unused){(void)unused;uintptr_t a=(uintptr_t)p,end;if(!p||n>UINTPTR_MAX-a)return 0;end=a+n;while(a<end){MEMORY_BASIC_INFORMATION m;if(!VirtualQuery((void*)a,&m,sizeof m)||m.State!=MEM_COMMIT||m.Protect&(PAGE_GUARD|PAGE_NOACCESS))return 0;uintptr_t next=(uintptr_t)m.BaseAddress+m.RegionSize;if(next<=a)return 0;a=next<end?next:end;}return 1;}
static int wsCertRead(const void*p,void*out,size_t n){if(!out||!wsCertMemory(p,n,0))return 0;memcpy(out,p,n);return 1;}
static void*wsCertPointer(const void*p,size_t o){void*v=0;if(p)wsCertRead((const unsigned char*)p+o,&v,8);return v;}
typedef struct WSVisibilityWorld{unsigned char*world,*module;uint32_t width,height,flags,viewer;int32_t map,enemy;int marked;}WSVisibilityWorld;
static int wsVisibilityWorldRead(void*p,WSVisibilityWorld*v){if(p!=worldBytes)return 0;memset(v,0,sizeof(*v));v->world=p;v->width=wsU32(worldBytes+0x1d8);v->height=wsU32(worldBytes+0x1dc);v->flags=wsU32(worldBytes+0x6eec);v->viewer=wsU32(worldBytes+0x1e4);v->marked=wsVisibilityDecode(v->flags,&v->map,&v->enemy);return 1;}
#define WS_CERT_MODULE(name) ((void)(name),(void*)moduleBytes)
int WorldSettingsVisibilitySaveBlob(unsigned char**out,uint32_t*n,char*e,uint32_t cap){if(fault==3)return wsChError(e,cap,"snapshot refused");return wsChartCoreEncode(&active,out,n,e,cap);}
int WorldSettingsVisibilityStageBlob(const void*p,uint32_t n,char*e,uint32_t cap){WSChartCore next={0};stageCalls++;if(!p&&!n){wsChartCoreFree(&staged);loadIntent=1;return 1;}if(!p||!n)return wsChError(e,cap,"invalid missing-history intent");if(!wsChartCoreDecode(p,n,&next,e,cap))return 0;wsChartCoreFree(&staged);staged=next;loadIntent=1;return 1;}
void WorldSettingsVisibilityCancelBlob(void){wsChartCoreFree(&staged);loadIntent=0;}
int WorldSettingsVisibilityApplyBlob(void*w,char*e,uint32_t cap){applyCalls++;if(fault==4)return wsChError(e,cap,"apply refused");if(w!=worldBytes||!loadIntent)return 0;if(staged.bits){if(!wsChartCoreIdentity(&staged,256,256,0,0x1000,worldBytes+0x6e4c))return wsChError(e,cap,"identity refused");wsChartCoreFree(&active);active=staged;memset(&staged,0,sizeof staged);}else{wsChartCoreFree(&active);return wsChartCoreNew(&active,256,256,0,0x1000,worldBytes+0x6e4c);}return 1;}
static uintptr_t nativeSave(void*owner,const char*alias,const char*name,unsigned char desync){(void)alias;(void)desync;saveCalls++;if(fault==9&&priorLock!=INVALID_HANDLE_VALUE){CloseHandle(priorLock);priorLock=INVALID_HANDLE_VALUE;}if(fault!=5&&fault!=9){char path[MAX_PATH];snprintf(path,sizeof path,"%s\\%s",(char*)owner+0x30,name);HANDLE h=CreateFileA(path,GENERIC_WRITE,0,NULL,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);DWORD n;if(h!=INVALID_HANDLE_VALUE){WriteFile(h,nativeOutput,nativeSize,&n,NULL);CloseHandle(h);}}return UINT64_C(0x123456789abcdef0);}
static int replaceFile(const char*a,const char*b){if(fault==7){char removed[MAX_PATH];snprintf(removed,sizeof removed,"%s.partial-failure",a);MoveFileA(a,removed);return 0;}return fault==1?0:ReplaceFileA(a,b,NULL,REPLACEFILE_WRITE_THROUGH,NULL,NULL);}
static BOOL writeFile(HANDLE f,const void*p,DWORD n,DWORD*out,LPOVERLAPPED o){return fault==2?FALSE:WriteFile(f,p,n,out,o);}
static BOOL copyFile(const char*a,const char*b,BOOL exclusive){if(fault==8&&strstr(b,"checkpoint-backup"))return FALSE;return CopyFileA(a,b,exclusive);}
static void releaseScene(void*p){if(p==sceneBytes){releaseCalls++;if(fixtureActive)traceFresh('R');}}
#define WS_MEMORY_NATIVE_SAVE(module) ((void)(module),nativeSave)
#define WS_MEMORY_REPLACE_FILE(a,b) replaceFile(a,b)
#define WS_MEMORY_WRITE_FILE writeFile
#define WS_MEMORY_COPY_FILE copyFile
#define WS_MEMORY_REPORT_FAILURE(message) ((void)(message),reports++)
#include "start_visibility_memory_io.inc"
int WorldSettingsIsActive(void){return fixtureActive;}
const char*WorldSettingsPendingPath(void){return freshPath;}
int WorldSettingsValidateScene(void*s,char*e,uint32_t n){(void)s;traceFresh('V');return fault==10?wsChError(e,n,"scene certificate refused"):1;}
void WorldSettingsFinishAttempt(int n){traceFresh(n?'S':'F');}
int WorldSettingsBindAIProfileWorld(void*s,char*e,uint32_t n){(void)s;traceFresh('A');return fault==11?wsChError(e,n,"AI certificate refused"):1;}
int WorldSettingsVisibilityCommitFresh(void*s,char*e,uint32_t n){(void)s;traceFresh('C');return fault==12?wsChError(e,n,"fresh chart commit refused"):1;}
void WorldSettingsVisibilityCancelFresh(void){traceFresh('X');}
/* STAGED_FACTORY */
static int32_t nativeFactory(int32_t mode,const char*path,void*list,void**out,void*meta,uint32_t index,uint32_t flags){(void)mode;(void)list;(void)meta;(void)index;(void)flags;factoryCalls++;if(fixtureActive)traceFresh('N');*out=sceneBytes;if(fault==6)return (int32_t)0x80004005u;HANDLE h=CreateFileA(path,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);if(h==INVALID_HANDLE_VALUE)return (int32_t)0x80004005u;CloseHandle(h);return 0;}
__declspec(dllexport) int fixture_init(const char*root,const void*raw,uint32_t n){
 WorldSettingsVisibilityCancelLoad();if(priorLock!=INVALID_HANDLE_VALUE){CloseHandle(priorLock);priorLock=INVALID_HANDLE_VALUE;}wsChartCoreFree(&active);wsChartCoreFree(&staged);free(nativeOutput);nativeOutput=(unsigned char*)malloc(n);if(!nativeOutput)return 0;memcpy(nativeOutput,raw,n);nativeSize=n;memset(worldBytes,0,sizeof worldBytes);memset(ownerBytes,0,sizeof ownerBytes);memset(sceneBytes,0,sizeof sceneBytes);memset(externalSceneVT,0,sizeof externalSceneVT);
 if(!moduleBytes)moduleBytes=(unsigned char*)VirtualAlloc(NULL,0x40000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);if(!moduleBytes)return 0;memset(moduleBytes,0,0x40000);
 /* Use the actual module-relative VT/release checks, with an executable native
  * ABI jump stub at the proven release RVA rather than a guard-bypass macro. */
 moduleBytes[0x1b60]=0x48;moduleBytes[0x1b61]=0xb8;void*p=(void*)releaseScene;memcpy(moduleBytes+0x1b62,&p,8);moduleBytes[0x1b6a]=0xff;moduleBytes[0x1b6b]=0xe0;FlushInstructionCache(GetCurrentProcess(),moduleBytes+0x1b60,12);
 const uint32_t vts[3]={0x35498,0x36108,0x3f648},dtors[3]={0x1080,0xa480,0xb560};for(unsigned i=0;i<3;i++){p=moduleBytes+dtors[i];memcpy(moduleBytes+vts[i],&p,8);p=moduleBytes+0x1b60;memcpy(moduleBytes+vts[i]+0x18,&p,8);}
 wsPut32(worldBytes+0x1d8,256);wsPut32(worldBytes+0x1dc,256);wsPut32(worldBytes+0x6eec,wsVisibilityEncode(0,0));for(unsigned i=0;i<16;i++)worldBytes[0x6e4c+i]=(unsigned char)(i+1);
 p=worldBytes;memcpy(ownerBytes+0x10,&p,8);snprintf((char*)ownerBytes+0x30,MAX_PATH,"%s",root);memcpy(sceneBytes+0x160,&p,8);p=moduleBytes+0x35498;memcpy(sceneBytes,&p,8);
 fault=saveCalls=stageCalls=applyCalls=releaseCalls=factoryCalls=reports=fixtureActive=0;freshPath[0]=freshTrace[0]=0;if(!wsChartCoreNew(&active,256,256,0,0x1000,worldBytes+0x6e4c))return 0;active.bits[0]=1;active.cells[0].visual[0]=123;active.cells[0].flags=3;active.cells[0].owner=14;active.cells[0].time=17;active.cells[0].logical=123;return 1;
}
__declspec(dllexport) void fixture_fault(int n){fault=n;}
__declspec(dllexport) uintptr_t fixture_save(const char*name){return WorldSettingsVisibilitySave(ownerBytes,"checkpoint",name,0);}
__declspec(dllexport) int fixture_load(const char*path){void*out=0;int32_t n=WorldSettingsCreateScene(0,path,NULL,&out,NULL,0,0,nativeFactory);return n<0?0:(out==sceneBytes);}
__declspec(dllexport) int fixture_parse(const void*p,uint32_t n){WSMemoryFile f;char e[512];return wsMemoryParse(p,n,&f,e,sizeof e);}
__declspec(dllexport) int fixture_counts(int which){const int v[]={saveCalls,stageCalls,applyCalls,releaseCalls,factoryCalls,reports};return which>=0&&which<6?v[which]:-1;}
__declspec(dllexport) int fixture_chart(void){return !!(active.bits&&active.bits[0]&1u);}
__declspec(dllexport) int fixture_load_intent(void){return loadIntent;}
__declspec(dllexport) void fixture_world_change(void){worldBytes[0x6e4c]^=1;}
__declspec(dllexport) void fixture_next_state(void){nativeOutput[nativeSize-1]=197;active.cells[0].visual[0]=211;active.cells[0].time=39;}
__declspec(dllexport) int fixture_path_safe(const char*name){char path[MAX_PATH];return wsMemorySavePath(ownerBytes,name,path);}
__declspec(dllexport) void fixture_fresh_active(const char*path){fixtureActive=1;freshTrace[0]=0;snprintf(freshPath,sizeof freshPath,"%s",path);}
__declspec(dllexport) const char*fixture_fresh_trace(void){return freshTrace;}
__declspec(dllexport) int fixture_lock_prior(const char*path){if(priorLock!=INVALID_HANDLE_VALUE)CloseHandle(priorLock);priorLock=CreateFileA(path,GENERIC_WRITE,0,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);return priorLock!=INVALID_HANDLE_VALUE;}
__declspec(dllexport) int fixture_release(int kind){
 const uint32_t vts[3]={0x35498,0x36108,0x3f648};void*vt=moduleBytes+vts[kind>=0&&kind<3?kind:0],*release=moduleBytes+0x1b60;
 if(kind==3){memcpy(externalSceneVT,vt,sizeof externalSceneVT);vt=externalSceneVT;}
 if(kind==4){void*bad=moduleBytes+0xa480;memcpy(vt,&bad,8);}
 if(kind==5){void*bad=moduleBytes+0x1b61;memcpy((unsigned char*)vt+0x18,&bad,8);}
 memcpy(sceneBytes,&vt,8);int result=WorldSettingsVisibilityReleaseUnpublishedScene(sceneBytes);
 void*dtor=moduleBytes+0x1080;memcpy(moduleBytes+0x35498,&dtor,8);memcpy(moduleBytes+0x35498+0x18,&release,8);return result;
}
__declspec(dllexport) void fixture_finish(void){WorldSettingsVisibilityCancelLoad();if(priorLock!=INVALID_HANDLE_VALUE)CloseHandle(priorLock);priorLock=INVALID_HANDLE_VALUE;wsChartCoreFree(&active);wsChartCoreFree(&staged);free(nativeOutput);nativeOutput=NULL;if(moduleBytes)VirtualFree(moduleBytes,0,MEM_RELEASE);moduleBytes=NULL;}
'''


def chunk(tag, body):
    return tag.encode().ljust(12, b'\0') + struct.pack('<I', len(body)) + body


def native_save(width=256, height=256, policy=0x1000):
    welt = bytearray(32)
    struct.pack_into('<II', welt, 0, width, height)
    struct.pack_into('<H', welt, 16, policy)
    return chunk('ANNOADDON1', chunk('WELT', welt) + chunk('GUID', bytes(range(1, 17))) +
                 chunk('ALIASNAME', b'checkpoint'.ljust(128, b'\0')) +
                 chunk('FUTURE_NAT', b'\x00\xffretained unknown native bytes'))


@unittest.skipUnless(os.name == 'nt', 'Actual checkpoint files use Windows BCrypt and ReplaceFile.')
class MemoryIOTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        zig = ROOT / '.local/toolchain/ziglang/zig.exe'
        if not zig.is_file():
            raise unittest.SkipTest('Pinned Zig toolchain unavailable.')
        cls.build = tempfile.TemporaryDirectory(prefix='anno-chart-io-build-')
        folder = Path(cls.build.name)
        files = {FACTORY: (ROOT / 'legacy/world_settings' / FACTORY).read_bytes()}
        apply_memory_factory(files)
        source = FIXTURE.replace('/* STAGED_FACTORY */', files[FACTORY].decode())
        (folder / 'fixture.c').write_text(source, encoding='utf-8')
        command = [str(zig), 'cc', '-target', 'x86_64-windows-gnu', '-shared', '-O2', '-Wall', '-Wextra', '-Werror',
                   '-I', str(NATIVE), str(folder / 'fixture.c'), '-o', str(folder / 'fixture.dll'), '-lbcrypt', '-luser32', '-lkernel32']
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.lib = C.CDLL(str(folder / 'fixture.dll'))
        cls.lib.fixture_init.argtypes = [C.c_char_p, C.c_void_p, C.c_uint32]
        cls.lib.fixture_save.argtypes = [C.c_char_p]
        cls.lib.fixture_save.restype = C.c_size_t
        cls.lib.fixture_load.argtypes = [C.c_char_p]
        cls.lib.fixture_parse.argtypes = [C.c_void_p, C.c_uint32]
        cls.lib.fixture_path_safe.argtypes = [C.c_char_p]
        cls.lib.WorldSettingsVisibilityBeforeLoad.argtypes = [C.c_char_p, C.c_void_p, C.c_uint32]
        cls.lib.WorldSettingsCopyMemoryError.argtypes = [C.c_void_p]
        cls.lib.fixture_lock_prior.argtypes = [C.c_char_p]
        cls.lib.fixture_fresh_active.argtypes = [C.c_char_p]
        cls.lib.fixture_fresh_trace.restype = C.c_char_p

    @classmethod
    def tearDownClass(cls):
        import _ctypes
        cls.lib.fixture_finish()
        _ctypes.FreeLibrary(cls.lib._handle)
        cls.build.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='anno-chart-io-data-')
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.original = native_save()
        self.assertEqual(self.lib.fixture_init(os.fsencode(self.folder), self.original, len(self.original)), 1)

    def save(self, name='world.sav'):
        self.assertEqual(self.lib.fixture_save(name.encode()), 0x123456789ABCDEF0)
        return self.folder / name

    def test_save_embeds_one_checkpoint_and_retains_exact_native_backup(self):
        path = self.save()
        raw = path.read_bytes()
        self.assertEqual(self.lib.fixture_parse(raw, len(raw)), 1)
        self.assertEqual(raw[16:len(self.original)], self.original[16:])
        self.assertEqual(raw[len(self.original):len(self.original)+12], b'WSCHART'.ljust(12, b'\0'))
        backups = list(self.folder.glob('*.wschart-native-backup-*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), self.original)
        self.assertEqual(self.lib.fixture_counts(0), 1)
        self.assertEqual(self.lib.fixture_counts(5), 0)

    def test_restore_exact_checkpoint_before_factory_publication(self):
        path = self.save()
        self.assertEqual(self.lib.fixture_load(os.fsencode(path)), 1)
        self.assertEqual([self.lib.fixture_counts(i) for i in (1, 2, 3, 4)], [1, 1, 0, 1])
        self.assertEqual(self.lib.fixture_chart(), 1)

    def test_missing_extension_initializes_conservatively(self):
        path = self.folder / 'old.sav'
        path.write_bytes(self.original)
        self.assertEqual(self.lib.fixture_load(os.fsencode(path)), 1)
        self.assertEqual(self.lib.fixture_counts(1), 1)
        self.assertEqual(self.lib.fixture_chart(), 0)
        self.assertEqual(self.lib.fixture_load_intent(), 0)

    def test_missing_history_intent_cancel_keeps_previous_active_chart(self):
        path = self.folder / 'old-cancelled.sav'
        path.write_bytes(self.original)
        error = C.create_string_buffer(512)
        self.assertEqual(self.lib.WorldSettingsVisibilityBeforeLoad(os.fsencode(path), error, 512), 1)
        self.assertEqual(self.lib.fixture_counts(1), 1)
        self.assertEqual(self.lib.fixture_load_intent(), 1)
        self.assertEqual(self.lib.fixture_chart(), 1)
        self.lib.WorldSettingsVisibilityCancelLoad()
        self.assertEqual(self.lib.fixture_load_intent(), 0)
        self.assertEqual(self.lib.fixture_chart(), 1)
        self.assertEqual(self.lib.fixture_counts(2), 0)
        with path.open('r+b') as writable:
            self.assertEqual(writable.read(), self.original)

    def test_missing_history_native_load_failure_discards_only_intent(self):
        path = self.folder / 'old-native-failure.sav'
        path.write_bytes(self.original)
        self.lib.fixture_fault(6)
        self.assertEqual(self.lib.fixture_load(os.fsencode(path)), 0)
        self.assertEqual([self.lib.fixture_counts(i) for i in (1, 2, 3, 4)], [1, 0, 0, 1])
        self.assertEqual(self.lib.fixture_load_intent(), 0)
        self.assertEqual(self.lib.fixture_chart(), 1)

    def test_unmarked_rectangular_and_nonstandard_dimensions_delegate_to_native(self):
        for width, height in ((512, 256), (300, 300)):
            with self.subTest(width=width, height=height):
                path = self.folder / f'ordinary-{width}-{height}.sav'
                raw = native_save(width, height, 0)
                path.write_bytes(raw)
                before = self.lib.fixture_counts(4)
                self.assertEqual(self.lib.fixture_load(os.fsencode(path)), 1)
                self.assertEqual(self.lib.fixture_counts(4), before + 1)
                self.assertEqual([self.lib.fixture_counts(i) for i in (1, 2, 3)], [0, 0, 0])
                self.assertEqual(path.read_bytes(), raw)

    def test_unmarked_metadata_shapes_remain_the_native_factory_decision(self):
        ordinary = native_save(policy=0)
        welt = ordinary[32:64]
        variants = (
            chunk('WELT', welt) + chunk('GUID', b'short') + chunk('ALIASNAME', b'name'),
            chunk('WELT', welt) + chunk('GUID', bytes(16)) * 2 + chunk('ALIASNAME', bytes(128)),
            chunk('WELT', welt[:16]) + chunk('FUTURE_NAT', b'unknown native payload'),
        )
        for index, payload in enumerate(variants):
            with self.subTest(index=index):
                path = self.folder / f'ordinary-metadata-{index}.sav'
                raw = chunk('ANNOADDON1', payload)
                path.write_bytes(raw)
                before = self.lib.fixture_counts(4)
                self.assertEqual(self.lib.fixture_load(os.fsencode(path)), 1)
                self.assertEqual(self.lib.fixture_counts(4), before + 1)
                self.assertEqual([self.lib.fixture_counts(i) for i in (1, 2, 3)], [0, 0, 0])
                self.assertEqual(path.read_bytes(), raw)

    def test_marked_unsupported_shape_and_malformed_unmarked_extension_stay_refused(self):
        for width, height in ((512, 256), (300, 300)):
            with self.subTest(width=width, height=height):
                path = self.folder / f'marked-{width}-{height}.sav'
                path.write_bytes(native_save(width, height))
                self.assertEqual(self.lib.fixture_load(os.fsencode(path)), 0)
        path = self.folder / 'ordinary-with-bad-chart.sav'
        path.write_bytes(chunk('ANNOADDON1', native_save(policy=0)[16:] + chunk('WSCHART', bytes(128))))
        self.assertEqual(self.lib.fixture_load(os.fsencode(path)), 0)
        self.assertEqual([self.lib.fixture_counts(i) for i in (1, 2, 3, 4)], [0, 0, 0, 0])

    def test_corruption_or_native_checkpoint_change_blocks_before_original_load(self):
        path = self.save()
        raw = path.read_bytes()
        for offset in (20, len(self.original)-1, len(self.original)+32, len(raw)-1):
            with self.subTest(offset=offset):
                damaged = bytearray(raw)
                damaged[offset] ^= 1
                path.write_bytes(damaged)
                self.assertEqual(self.lib.fixture_load(os.fsencode(path)), 0)
                self.assertEqual(self.lib.fixture_counts(4), 0)

    def test_duplicate_chart_and_parent_overflow_are_rejected(self):
        path = self.save()
        raw = path.read_bytes()
        extension = raw[len(self.original):]
        duplicate = bytearray(raw + extension)
        struct.pack_into('<I', duplicate, 12, len(duplicate)-16)
        self.assertEqual(self.lib.fixture_parse(bytes(duplicate), len(duplicate)), 0)
        overflow = bytearray(raw)
        struct.pack_into('<I', overflow, len(self.original)+12, 0xFFFFFFFF)
        self.assertEqual(self.lib.fixture_parse(bytes(overflow), len(overflow)), 0)

    def test_apply_failure_releases_only_unpublished_successful_scene(self):
        path = self.save()
        self.lib.fixture_fault(4)
        self.assertEqual(self.lib.fixture_load(os.fsencode(path)), 0)
        self.assertEqual(self.lib.fixture_counts(3), 1)
        self.lib.fixture_fault(6)
        self.assertEqual(self.lib.fixture_load(os.fsencode(path)), 0)
        self.assertEqual(self.lib.fixture_counts(3), 1, 'A native failure output may already be destroyed.')

    def test_unpublished_scene_release_requires_exact_module_vt_and_destructor(self):
        for kind in (0, 1, 2):
            with self.subTest(primary_scene_kind=kind):
                before = self.lib.fixture_counts(3)
                self.assertEqual(self.lib.fixture_release(kind), 1)
                self.assertEqual(self.lib.fixture_counts(3), before + 1)
        for kind in (3, 4, 5):
            with self.subTest(refused_scene_kind=kind):
                before = self.lib.fixture_counts(3)
                self.assertEqual(self.lib.fixture_release(kind), 0)
                self.assertEqual(self.lib.fixture_counts(3), before)

    def test_fresh_chart_commits_only_after_scene_and_ai_certificates(self):
        path = self.folder / 'fresh-prepared.sav'
        path.write_bytes(self.original)
        self.lib.fixture_fresh_active(os.fsencode(path))
        self.assertEqual(self.lib.fixture_load(os.fsencode(path)), 1)
        self.assertEqual(self.lib.fixture_fresh_trace(), b'NVACS')
        self.assertEqual([self.lib.fixture_counts(i) for i in (1, 2, 3, 4)], [0, 0, 0, 1])

    def test_fresh_validation_ai_or_commit_failure_cancels_before_finish(self):
        for fault, expected in ((10, b'NVRXF'), (11, b'NVARXF'), (12, b'NVACRXF')):
            with self.subTest(fault=fault):
                self.assertEqual(self.lib.fixture_init(os.fsencode(self.folder), self.original, len(self.original)), 1)
                path = self.folder / f'fresh-refused-{fault}.sav'
                path.write_bytes(self.original)
                self.lib.fixture_fresh_active(os.fsencode(path))
                self.lib.fixture_fault(fault)
                self.assertEqual(self.lib.fixture_load(os.fsencode(path)), 0)
                self.assertEqual(self.lib.fixture_fresh_trace(), expected)
                self.assertEqual([self.lib.fixture_counts(i) for i in (1, 2, 3, 4)], [0, 0, 1, 1])

    def test_fresh_native_failure_cancels_without_releasing_already_failed_output(self):
        path = self.folder / 'fresh-native-failure.sav'
        path.write_bytes(self.original)
        self.lib.fixture_fresh_active(os.fsencode(path))
        self.lib.fixture_fault(6)
        self.assertEqual(self.lib.fixture_load(os.fsencode(path)), 0)
        self.assertEqual(self.lib.fixture_fresh_trace(), b'NXF')
        self.assertEqual(self.lib.fixture_counts(3), 0)

    def test_world_identity_mismatch_is_refused(self):
        path = self.save()
        self.lib.fixture_world_change()
        self.assertEqual(self.lib.fixture_load(os.fsencode(path)), 0)
        self.assertEqual(self.lib.fixture_counts(3), 1)

    def test_replace_or_write_failure_keeps_native_save_and_original_return(self):
        for fault in (1, 2, 3):
            with self.subTest(fault=fault):
                self.lib.fixture_fault(fault)
                path = self.save(f'fault-{fault}.sav')
                self.assertEqual(path.read_bytes(), self.original)
                self.assertGreater(self.lib.fixture_counts(5), 0)

    def test_skipped_native_save_never_attaches_new_memory_to_old_checkpoint(self):
        path = self.folder / 'unchanged.sav'
        path.write_bytes(self.original)
        before = hashlib.sha256(path.read_bytes()).digest()
        self.lib.fixture_fault(5)
        self.save(path.name)
        self.assertEqual(hashlib.sha256(path.read_bytes()).digest(), before)
        self.assertEqual(list(self.folder.glob('*.wschart-native-backup-*')), [])
        self.assertEqual(self.lib.fixture_counts(5), 1)

    def test_unreadable_prior_then_skipped_native_save_never_attaches_future_history(self):
        path = self.folder / 'unreadable-prior.sav'
        path.write_bytes(self.original)
        self.lib.fixture_next_state()
        self.assertEqual(self.lib.fixture_lock_prior(os.fsencode(path)), 1)
        self.lib.fixture_fault(9)  # Native call releases the lock but writes nothing.
        self.save(path.name)
        self.assertEqual(path.read_bytes(), self.original)
        self.assertEqual(self.lib.fixture_counts(0), 1)
        self.assertEqual(self.lib.fixture_counts(5), 1)
        self.assertEqual(list(self.folder.glob('*.wschart-*')), [])
        error = C.create_string_buffer(512)
        self.lib.WorldSettingsCopyMemoryError(error)
        self.assertIn(b'presence or identity could not be certified', error.value)
        with path.open('r+b') as writable:
            self.assertEqual(writable.read(), self.original)

    def test_previous_backups_survive_repeated_checkpoint_saves(self):
        path = self.save()
        old = {p.name: p.read_bytes() for p in self.folder.glob('*.wschart-native-backup-*')}
        self.save()
        for name, raw in old.items():
            self.assertEqual((self.folder / name).read_bytes(), raw)
        self.assertEqual(self.lib.fixture_parse(path.read_bytes(), path.stat().st_size), 1)

    def test_previous_complete_checkpoint_is_archived_before_native_overwrite_and_faults(self):
        for fault in (1, 2, 3):
            with self.subTest(fault=fault):
                self.assertEqual(self.lib.fixture_init(os.fsencode(self.folder), self.original, len(self.original)), 1)
                path = self.save(f'previous-{fault}.sav')
                state_a = path.read_bytes()
                self.lib.fixture_next_state()
                self.lib.fixture_fault(fault)
                self.save(path.name)
                state_b_native = self.original[:-1] + bytes([197])
                self.assertEqual(path.read_bytes(), state_b_native)
                self.assertEqual(self.lib.fixture_parse(state_b_native, len(state_b_native)), 1)
                archives = list(self.folder.glob(path.name + '.wschart-checkpoint-backup-*'))
                self.assertEqual(len(archives), 1)
                self.assertEqual(archives[0].read_bytes(), state_a)
                self.assertEqual(self.lib.fixture_parse(state_a, len(state_a)), 1)
                self.assertEqual(self.lib.fixture_counts(0), 2)
                self.assertEqual(self.lib.fixture_counts(5), 1)
                # A pre-save deny-write lock must have closed before native Save.
                with path.open('r+b') as writable:
                    self.assertEqual(writable.read(), state_b_native)

    def test_previous_complete_archives_survive_repeated_successful_resaves(self):
        path = self.save()
        state_a = path.read_bytes()
        self.lib.fixture_next_state()
        self.save()
        state_b = path.read_bytes()
        self.assertNotEqual(state_a, state_b)
        first = {p.name: p.read_bytes() for p in self.folder.glob('*.wschart-checkpoint-backup-*')}
        self.assertEqual(list(first.values()), [state_a])
        self.save()
        archives = list(self.folder.glob('*.wschart-checkpoint-backup-*'))
        self.assertEqual(len(archives), 2)
        for name, raw in first.items():
            self.assertEqual((self.folder / name).read_bytes(), raw)
        self.assertIn(state_b, [p.read_bytes() for p in archives])
        self.assertEqual(self.lib.fixture_counts(5), 0)

    def test_previous_backup_failure_does_not_cancel_native_or_hide_behind_success(self):
        path = self.save()
        self.lib.fixture_next_state()
        self.lib.fixture_fault(8)
        self.save()
        raw = path.read_bytes()
        self.assertEqual(self.lib.fixture_parse(raw, len(raw)), 1)
        self.assertEqual(raw[16:len(self.original)], (self.original[:-1] + bytes([197]))[16:])
        self.assertEqual(self.lib.fixture_counts(0), 2)
        self.assertEqual(self.lib.fixture_counts(5), 1)
        self.assertEqual(list(self.folder.glob('*.wschart-checkpoint-backup-*')), [])
        error = C.create_string_buffer(512)
        self.lib.WorldSettingsCopyMemoryError(error)
        self.assertIn(b'previous complete checkpoint could not be backed up', error.value)
        with path.open('r+b') as writable:
            self.assertEqual(writable.read(), raw)

    def test_inner_codec_corruption_is_refused_even_with_matching_outer_sha(self):
        path = self.save()
        raw = bytearray(path.read_bytes())
        body = len(self.original) + 16
        raw[body+128+80] ^= 1  # Inner header checksum; outer hash is repaired.
        raw[body+48:body+80] = hashlib.sha256(raw[body+128:]).digest()
        path.write_bytes(raw)
        self.assertEqual(self.lib.fixture_load(os.fsencode(path)), 0)
        self.assertEqual(self.lib.fixture_counts(4), 0)

    def test_load_holds_original_file_against_replacement_or_write(self):
        path = self.save()
        error = C.create_string_buffer(512)
        self.assertEqual(self.lib.WorldSettingsVisibilityBeforeLoad(os.fsencode(path), error, 512), 1)
        try:
            with self.assertRaises(PermissionError):
                with path.open('wb'):
                    pass
        finally:
            self.lib.WorldSettingsVisibilityCancelLoad()
        self.assertEqual(self.lib.fixture_load(os.fsencode(path)), 1)

    def test_hardlinked_native_file_is_refused_without_modification(self):
        path = self.folder / 'native.sav'
        path.write_bytes(self.original)
        linked = self.folder / 'linked.sav'
        os.link(path, linked)
        self.assertEqual(self.lib.fixture_load(os.fsencode(linked)), 0)
        self.assertEqual(path.read_bytes(), self.original)
        self.assertEqual(self.lib.fixture_counts(4), 0)

    def test_invalid_relative_save_paths_are_never_augmented(self):
        for name in (b'../escape.sav', b'..\\escape.sav', b'C:\\escape.sav', b'\\escape.sav', b'/escape.sav'):
            with self.subTest(name=name):
                self.assertEqual(self.lib.fixture_path_safe(name), 0)

    def test_partial_replace_failure_recovers_missing_native_name_exclusively(self):
        self.lib.fixture_fault(7)
        path = self.save()
        self.assertEqual(path.read_bytes(), self.original)
        self.assertEqual(self.lib.fixture_counts(5), 1)
        self.assertEqual(len(list(self.folder.glob('*.wschart-native-backup-*'))), 1)


if __name__ == '__main__':
    unittest.main()
