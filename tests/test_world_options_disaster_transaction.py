"""The complete new transaction and readiness certificate, without game access."""
import ctypes as C
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from anno1503_overhaul.world_options import apply_options,PRIVATE
from anno1503_overhaul.world_runtime_build import _verified_sources,SOURCE_PREFIX,BLOBS
from anno1503_overhaul.world_options_disasters import apply_disaster_transaction
INSTALLER='developer/source/engine_resume/ai_loader/install_test_hooks.c'

def staged():
 return apply_options({n.removeprefix(SOURCE_PREFIX):(ROOT/n).read_bytes()for n in _verified_sources(ROOT)})

class TransactionRecipe(unittest.TestCase):
 def test_full_transaction_has_exact_capacity_and_checks_before_commit(self):
  files=staged();raw=files[INSTALLER]
  self.assertIn(b'#define WS_MAX_HOOKS (45+WS_ENGINE_PATCH_COUNT)',raw)
  self.assertIn(b'if(patchCount!=17u+WS_ENGINE_PATCH_COUNT+WS_VISIBILITY_HOOK_COUNT)',raw)
  self.assertIn(b'if(result&&wsDisasterPatchStatusUnlocked()!=8u)result=0;',raw)
  self.assertLess(raw.index(b'if(!wsPrepareDisasterHooks('),raw.index(b'if(!wsSuspendThreads('))
  self.assertEqual(17+173+28,45+173)
  with self.assertRaises(Exception):apply_disaster_transaction(files)

@unittest.skipUnless(os.name=='nt','Requires the actual Win64 fixture ABI.')
class NativeTransactionCertificate(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory(prefix='anno-disaster-transaction-');out=Path(cls.tmp.name);files=staged()
  (out/'blobs.h').write_bytes(files[BLOBS]);(out/'disaster_hooks.inc').write_bytes(files['developer/source/engine_resume/ai_loader/disaster_hooks.inc'])
  code=r'''
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>
#include <wchar.h>
#include "blobs.h"
#define WS_MAX_PATCH 32
#define WS_ENGINE_PATCH_COUNT 173u
#define WS_VISIBILITY_HOOK_COUNT 28u
#define WS_MAX_HOOKS (45+WS_ENGINE_PATCH_COUNT)
#define WS_BLOB_COUNT (sizeof wsBlobs/sizeof wsBlobs[0])
typedef struct{HMODULE module;unsigned char*allocation;int registered;}WSInstalledBlob;
typedef struct{unsigned char*address;uint32_t length;unsigned char before[32],after[32];}WSPatch;
static WSInstalledBlob wsInstalled[WS_BLOB_COUNT];
static int wsInstallState;
static unsigned char storage[0x300000];static WSPatch patches[WS_MAX_HOOKS];
static int wsError(const char*text){(void)text;return 0;}
static int wsSpan(uint32_t a,uint32_t n,uint32_t size){return a<=size&&n<=size-a;}
static int wsReadable(const void*p,SIZE_T n){uintptr_t at=(uintptr_t)p,base=(uintptr_t)storage;return at>=base&&n<=sizeof storage&&at-base<=sizeof storage-n;}
static HMODULE fixtureModule(const wchar_t*name){return wcscmp(name,L"AnnoWelt.dll")?NULL:(HMODULE)storage;}
static FARPROC fixtureProc(HMODULE self,const char*name){(void)self;(void)name;return(FARPROC)(uintptr_t)0x1122334455667788ull;}
#define GetModuleHandleW fixtureModule
#define GetProcAddress fixtureProc
#include "disaster_hooks.inc"
__declspec(dllexport) int setup(void){
 memset(storage,0,sizeof storage);memset(wsInstalled,0,sizeof wsInstalled);memset(patches,0,sizeof patches);wsInstallState=0;
 const WSBlob*b=NULL;WSInstalledBlob*s=NULL;
 for(uint32_t j=0;j<WS_BLOB_COUNT;j++)if(wsBlobs[j].code==world_policy_code){b=&wsBlobs[j];s=&wsInstalled[j];}
 if(!b||!s||b->codeSize>0x100000u)return 0;s->module=(HMODULE)storage;s->allocation=storage+0x200000;s->registered=1;
 memcpy(s->allocation,b->code,b->codeSize);
 for(uint32_t j=0;j<b->importCount;j++){uintptr_t value=(uintptr_t)fixtureProc(NULL,b->imports[j].name);memcpy(s->allocation+b->imports[j].offset,&value,8);}
 for(uint32_t i=0;i<8;i++){
  const WSHook*h=NULL;for(uint32_t j=0;j<b->hookCount;j++)if(b->hooks[j].rva==wsDisasterRvas[i])h=&b->hooks[j];if(!h)return 0;
  WSPatch*p=&patches[i];p->address=storage+h->rva;p->length=h->length;memcpy(p->before,h->before,h->length);memcpy(p->address,h->before,h->length);
  memset(p->after,0x90,p->length);p->after[0]=0xe8;int32_t d=(int32_t)((s->allocation+h->target)-(p->address+5));memcpy(p->after+1,&d,4);
 }return 1;
}
__declspec(dllexport) int prepare(uint32_t count){return wsPrepareDisasterHooks(NULL,patches,count);}
__declspec(dllexport) uint32_t status(void){return wsDisasterPatchStatusUnlocked();}
__declspec(dllexport) void commit(void){for(uint32_t i=0;i<8;i++)memcpy(patches[i].address,patches[i].after,patches[i].length);wsInstallState=1;}
__declspec(dllexport) void corrupt(uint32_t mode,uint32_t index){
 index%=8;
 if(mode==0)patches[index].address[0]^=1;
 if(mode==1&&wsDisasterBridges[index])wsDisasterBridges[index][0]^=1;
 if(mode==2)patches[index].after[1]^=1;
 if(mode==3)patches[8]=patches[index];
 if(mode==4)for(uint32_t i=0;i<WS_BLOB_COUNT;i++)wsInstalled[i].registered=0;
 if(mode==5)patches[index].before[0]^=1;
 if(mode==6&&wsDisasterBridges[index])wsDisasterBridges[index][wsDisasterBridgeLengths[index]-1]^=1;
}
'''
  (out/'fixture.c').write_text(code,encoding='utf-8')
  zig=ROOT/'.local/toolchain/ziglang/zig.exe'
  if not zig.is_file():raise unittest.SkipTest('Pinned native compiler unavailable.')
  result=subprocess.run([str(zig),'cc','-target','x86_64-windows-gnu','-shared','-O2','-Wall','-Wextra','-Werror',str(out/'fixture.c'),'-o',str(out/'fixture.dll')],capture_output=True,text=True)
  if result.returncode:raise AssertionError(result.stdout+result.stderr)
  cls.lib=C.CDLL(str(out/'fixture.dll'));cls.lib.prepare.argtypes=[C.c_uint32];cls.lib.corrupt.argtypes=[C.c_uint32,C.c_uint32]
 @classmethod
 def tearDownClass(cls):
  import _ctypes
  _ctypes.FreeLibrary(cls.lib._handle);cls.tmp.cleanup()
 def test_exact_full_capacity_preparation_and_readiness(self):
  self.assertEqual(self.lib.setup(),1);self.assertEqual(self.lib.status(),0)
  for count in(210,217,219,0):self.assertEqual(self.lib.prepare(count),0)
  self.assertEqual(self.lib.prepare(218),1);self.assertEqual(self.lib.status(),0)
  self.lib.commit();self.assertEqual(self.lib.status(),8)
 def test_all_eight_sites_and_full_bridge_or_callback_tampering_fail_readiness(self):
  for index in range(8):
   for mode in(0,1,6):
    self.assertEqual(self.lib.setup(),1);self.assertEqual(self.lib.prepare(218),1);self.lib.commit()
    self.lib.corrupt(mode,index);self.assertEqual(self.lib.status(),0,(index,mode))
 def test_missing_registered_bridge_duplicate_or_wrong_transaction_is_refused(self):
  for index in range(8):
   for mode in(2,3,4,5):
    self.assertEqual(self.lib.setup(),1);self.lib.corrupt(mode,index);self.assertEqual(self.lib.prepare(218),0,(index,mode))

if __name__=='__main__':unittest.main()
