"""Actual Windows temporary-file ownership and failure cleanup; no game run."""
import ctypes as C
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
import test_world_island_rotation as codec
from test_world_options_menu import DRIVER
from test_world_options_factions import staged_sources
from anno1503_overhaul.world_options import PRIVATE


def stage_wrapper():
    unused,files=staged_sources();text=files[PRIVATE+'world_backend.c'].decode()
    match=re.search(r'^static int wsStagePlan\(',text,re.M)
    if not match:raise AssertionError('The actual stage wrapper is absent.')
    at=text.index('{',match.start());end=at+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[match.start():end]


EXTRA=r'''
#define WS_COUNT 444u
#define WS_LIMIT 128u
typedef struct WSTemplate {const char*path;unsigned short width,height;unsigned char climate,cultures,oreSlots,whales,excludedNative,sizeChoices;unsigned int fertileLand;unsigned char sha256[32];} WSTemplate;
static WSTemplate wsTemplates[444];static WSPlanIsland planned[128];static uint32_t planCount;
static int baseFailure;
static int wsFullPath(const char*root,const char*relative,char*out){int n=snprintf(out,MAX_PATH,"%s\\%s",root,relative);return n>0&&n<MAX_PATH;}
#include "island_rotation_plan.h"
#include "island_rotation_io.inc"
static int wsStagePlanBase(const WSWorldSettings*s,const char*root,char*out,uint32_t outCap,char*error,uint32_t cap){
 (void)s;(void)root;(void)out;(void)outCap;(void)error;(void)cap;return !baseFailure;
}
@WRAPPER@
__declspec(dllexport) void initialise(const unsigned char*raw,uint32_t size){
 wsRotationCleanup();memset(planned,0,sizeof planned);memset(wsTemplates,0,sizeof wsTemplates);wsRotationSequence=0;planCount=1;
 wsTemplates[0].path="Scenes\\source.scp";wsTemplates[0].width=wsTemplates[0].height=64;
 wsRotationDigest(raw,size,wsTemplates[0].sha256);planned[0].width=planned[0].height=64;
}
__declspec(dllexport) int prepare(const char*root,uint32_t rotation,int fail){
 WSWorldSettings s={0};s.islandRotation=rotation?1:0;planned[0].rotation=rotation;baseFailure=fail;char out[MAX_PATH],error[512];
 return wsStagePlan(&s,root,out,sizeof out,error,sizeof error);
}
__declspec(dllexport) int selected(const char*root,char*out){return wsRotationSelectedPath(root,planned,out);}
__declspec(dllexport) void cleanup(void){wsRotationCleanup();}
'''


@unittest.skipUnless(os.name=='nt','Identity-checked file deletion requires Windows.')
class RotationFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler=ROOT/'.local/toolchain/ziglang/zig.exe'
        if not compiler.is_file():raise unittest.SkipTest('The reviewed native compiler is unavailable.')
        cls.tmp=tempfile.TemporaryDirectory(prefix='rotation-io-',dir=ROOT/'.local/validation')
        cls.folder=Path(cls.tmp.name).resolve();assert cls.folder.is_relative_to((ROOT/'.local/validation').resolve())
        prefix=DRIVER.split('#define WS_WORLD_OPTIONS_GENERATOR',1)[0]
        helpers=codec.PREFIX.split('#include "island_rotation_codec.inc"',1)[0]
        code='#define WIN32_LEAN_AND_MEAN\n#include <windows.h>\n#include <bcrypt.h>\n'+prefix+helpers+EXTRA.replace('@WRAPPER@',stage_wrapper())
        source=cls.folder/'fixture.c';source.write_text(code,encoding='utf-8');dll=cls.folder/'fixture.dll'
        result=subprocess.run([str(compiler),'cc','-shared','-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
            '-Wno-unused-function','-I',str(codec.NATIVE),str(source),'-o',str(dll),'-lbcrypt','-lkernel32'],capture_output=True,text=True,timeout=90)
        if result.returncode:raise AssertionError(result.stdout+result.stderr)
        cls.lib=C.CDLL(str(dll));cls.lib.initialise.argtypes=[C.c_void_p,C.c_uint32]
        cls.lib.prepare.argtypes=[C.c_char_p,C.c_uint32,C.c_int];cls.lib.selected.argtypes=[C.c_char_p,C.c_void_p]
    @classmethod
    def tearDownClass(cls):
        cls.lib.cleanup();import _ctypes
        _ctypes.FreeLibrary(cls.lib._handle);cls.tmp.cleanup()
    def setUp(self):
        self.case=tempfile.TemporaryDirectory(prefix='case-',dir=self.folder);self.root=Path(self.case.name).resolve()
        self.assertTrue(self.root.is_relative_to(self.folder));(self.root/'Scenes').mkdir()
        self.raw=codec.fixture();self.source=self.root/'Scenes/source.scp';self.source.write_bytes(self.raw)
        self.lib.initialise(self.raw,len(self.raw))
    def tearDown(self):
        self.lib.cleanup();self.assertTrue(self.root.is_relative_to(self.folder));self.case.cleanup()
    def prepare(self,q=1,fail=0):return self.lib.prepare(os.fsencode(self.root),q,fail)
    def selected(self):
        value=C.create_string_buffer(260)
        return Path(os.fsdecode(value.value))if self.lib.selected(os.fsencode(self.root),value)else None
    def test_rotated_file_is_exact_exclusive_and_removed_after_the_attempt(self):
        for q in (1,2,3):
            self.assertEqual(self.prepare(q),1);path=self.selected();self.assertIsNotNone(path)
            self.assertNotEqual(path,self.source);self.assertTrue(path.is_relative_to(self.root/'Scenes'))
            self.assertEqual(path.read_bytes(),codec.rotate_island(self.raw,q,{1585:(3,4),2708:(4,4)}))
            self.lib.cleanup();self.assertFalse(path.exists());self.assertEqual(self.source.read_bytes(),self.raw)
    def test_default_orientation_creates_no_temporary_island(self):
        self.assertEqual(self.prepare(0),1);self.assertEqual(self.selected(),self.source)
        self.lib.cleanup();self.assertEqual(list((self.root/'Scenes').iterdir()),[self.source])
    def test_existing_name_collision_is_preserved(self):
        path=self.root/'Scenes'/('WorldSettingsIsland_%d_1_0.scp'%os.getpid());path.write_bytes(b'prior user file')
        self.assertEqual(self.prepare(),0);self.lib.cleanup();self.assertEqual(path.read_bytes(),b'prior user file')
        self.assertEqual(self.source.read_bytes(),self.raw)
    def test_native_stage_failure_removes_only_owned_derivatives(self):
        self.assertEqual(self.prepare(fail=1),0)
        self.assertEqual(list((self.root/'Scenes').iterdir()),[self.source])
    def test_changed_temporary_file_is_not_loaded_or_deleted(self):
        self.assertEqual(self.prepare(),1);path=self.selected();path.write_bytes(b'user changed file')
        self.assertIsNone(self.selected());self.lib.cleanup();self.assertEqual(path.read_bytes(),b'user changed file')
    def test_replaced_same_bytes_have_a_different_identity_and_are_preserved(self):
        self.assertEqual(self.prepare(),1);path=self.selected();raw=path.read_bytes();moved=path.with_suffix('.moved')
        path.rename(moved);path.write_bytes(raw)
        self.assertIsNone(self.selected());self.lib.cleanup();self.assertEqual(path.read_bytes(),raw);self.assertEqual(moved.read_bytes(),raw)
    def test_hardlink_is_preserved_instead_of_deleted(self):
        self.assertEqual(self.prepare(),1);path=self.selected();link=path.with_suffix('.linked');os.link(path,link)
        self.assertIsNone(self.selected());self.lib.cleanup();self.assertTrue(path.is_file());self.assertTrue(link.is_file())
    def test_source_tamper_and_invalid_rotation_never_create_a_derivative(self):
        self.source.write_bytes(self.raw+b'changed');self.assertEqual(self.prepare(),0)
        self.assertEqual(list((self.root/'Scenes').iterdir()),[self.source])
        self.source.write_bytes(self.raw);self.assertEqual(self.prepare(q=4),0)
        self.assertEqual(self.source.read_bytes(),self.raw)


if __name__=='__main__':unittest.main()
