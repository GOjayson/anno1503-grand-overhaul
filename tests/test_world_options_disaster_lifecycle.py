"""Actual staged finalizers in scene-then-player order; no Anno process."""
import ctypes as C
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from anno1503_overhaul.world_options import PRIVATE,apply_options
from anno1503_overhaul.world_runtime_build import _verified_sources,SOURCE_PREFIX
from test_world_options_disaster_memory import POLICY_STRUCT


def function(raw,name):
 text=raw.decode();at=text.index(name+'(');begin=text.rfind('__declspec(dllexport)',0,at)
 brace=text.index('{',at);end=brace+1;depth=1
 while depth:
  depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[begin:end]


@unittest.skipUnless(os.name=='nt','Requires the real Windows native ABI.')
class DisasterLifecycle(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  files=apply_options({n.removeprefix(SOURCE_PREFIX):(ROOT/n).read_bytes()for n in _verified_sources(ROOT)})
  finish=function(files[PRIVATE+'world_backend.c'],'WorldSettingsFinishAttempt')
  end=function(files[PRIVATE+'world_ai.c'],'WorldSettingsEndNativeWorldStart')
  cls.tmp=tempfile.TemporaryDirectory(prefix='anno-disaster-lifecycle-');folder=Path(cls.tmp.name)
  for name in ('disaster_policy.h','disaster_policy.inc'):(folder/name).write_bytes(files[PRIVATE+name])
  source=r'''
#define WIN32_LEAN_AND_MEAN
#define WS_AI_FIXTURE 1
#include <windows.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
static unsigned char moduleBytes[0x130000],worldBytes[0x7000];
#define WS_CERT_MODULE(name) ((void)(name),(void*)moduleBytes)
static void wsMessage(char*e,uint32_t cap,const char*t){if(e&&cap)snprintf(e,cap,"%s",t);}
static int wsCertRead(const void*p,void*out,SIZE_T size){MEMORY_BASIC_INFORMATION m;uintptr_t a=(uintptr_t)p;if(!p||!out||!VirtualQuery(p,&m,sizeof m)||m.State!=MEM_COMMIT||(m.Protect&(PAGE_GUARD|PAGE_NOACCESS))||a<(uintptr_t)m.BaseAddress||size>m.RegionSize||a-(uintptr_t)m.BaseAddress>m.RegionSize-size)return 0;memcpy(out,p,size);return 1;}
static void*wsCertPointer(const void*p,SIZE_T at){void*out=NULL;if(p)wsCertRead((const unsigned char*)p+at,&out,8);return out;}
'''+POLICY_STRUCT+r'''
static uint32_t wsNativeActive,wsNativeFactions,wsFactionsExpected;
static int wsNativeExpected,wsNativeChecked,wsProfilesExpected,pending,prepared;
static void*wsNativeWorld,*preparedScene;static LONG wsProfileStatus;
static char wsProfileError[512],pendingPath[MAX_PATH],gameDirectory[MAX_PATH],prepareError[512];
static struct{uint32_t state;}wsPreviewCache;
static void wsRotationCleanup(void){}
static void WorldSettingsVisibilityCancelFresh(void){}
static void WorldSettingsAIProfileAttemptFinished(int n){(void)n;}
static void WorldSettingsResetFactionActivity(void){}
static int WorldSettingsIsActive(void){return pending;}
static void wsPreviewSetState(uint32_t n){wsPreviewCache.state=n;}
'''+finish+'\n'+end+r'''
__declspec(dllexport) void begin(void){
 memset(worldBytes,0,sizeof worldBytes);memset(moduleBytes,0,sizeof moduleBytes);
 void*vt=moduleBytes+0xff650;memcpy(worldBytes,&vt,8);void*getter=moduleBytes+0xd1910;memcpy(moduleBytes+0xff650+0xf0,&getter,8);
 uint32_t width=1024,flags=0x6000;memcpy(worldBytes+0x1d8,&width,4);memcpy(worldBytes+0x1dc,&width,4);memcpy(worldBytes+0x6eec,&flags,4);
 for(uint32_t i=0;i<16;i++)worldBytes[0x6e4c+i]=(unsigned char)(i+1);
 wsDisasterClearLoaded();wsNativeActive=73;wsNativeExpected=1;wsNativeChecked=0;pending=1;wsPreviewCache.state=2;
 WSWorldSettings s={0};s.disasters=1;s.disasterMask=21;s.disasterFrequency=582;s.disasterSeverity=101;WorldSettingsExpectDisasterOptions(&s);
}
__declspec(dllexport) int bind(void){char error[256];int n=WorldSettingsBindDisasterOptions(worldBytes,error,sizeof error);wsNativeChecked=n;return n;}
__declspec(dllexport) int current(void){return wsDisasterCurrent.active&&!wsDisasterCurrent.provisional;}
__declspec(dllexport) uint32_t choices(void){return wsDisasterPending[0];}
__declspec(dllexport) uint32_t flags(void){uint32_t n;memcpy(&n,worldBytes+0x6eec,4);return n;}
'''
  (folder/'fixture.c').write_text(source,encoding='utf-8')
  zig=ROOT/'.local/toolchain/ziglang/zig.exe'
  if not zig.is_file():raise unittest.SkipTest('Pinned native compiler unavailable.')
  result=subprocess.run([str(zig),'cc','-target','x86_64-windows-gnu','-shared','-O2','-Wall','-Wextra','-Werror',str(folder/'fixture.c'),'-o',str(folder/'fixture.dll')],capture_output=True,text=True)
  if result.returncode:raise AssertionError(result.stdout+result.stderr)
  cls.lib=C.CDLL(str(folder/'fixture.dll'));cls.lib.WorldSettingsFinishAttempt.argtypes=[C.c_int];cls.lib.WorldSettingsEndNativeWorldStart.argtypes=[C.c_uint32,C.c_int]
 @classmethod
 def tearDownClass(cls):
  import _ctypes
  _ctypes.FreeLibrary(cls.lib._handle);cls.tmp.cleanup()
 def test_scene_success_retains_choices_until_player_commit_and_native_completion(self):
  self.lib.begin();self.assertEqual(self.lib.choices(),1)
  self.lib.WorldSettingsFinishAttempt(1);self.assertEqual(self.lib.choices(),1)
  self.assertEqual(self.lib.bind(),1);self.assertEqual(self.lib.current(),0)
  self.assertEqual(self.lib.flags()&0x8e,128)
  self.assertEqual(self.lib.WorldSettingsEndNativeWorldStart(73,1),1)
  self.assertEqual(self.lib.current(),1);self.assertEqual(self.lib.choices(),0)
 def test_failed_scene_or_native_scope_cancels_uncommitted_policy(self):
  self.lib.begin();self.lib.WorldSettingsFinishAttempt(0)
  self.assertEqual(self.lib.choices(),0);self.assertEqual(self.lib.bind(),0);self.assertEqual(self.lib.current(),0)
  self.lib.begin();self.lib.WorldSettingsFinishAttempt(1);self.assertEqual(self.lib.bind(),1)
  self.assertEqual(self.lib.WorldSettingsEndNativeWorldStart(73,0),0);self.assertEqual(self.lib.current(),0)
 def test_stale_scope_cannot_consume_choices_or_commit_a_new_world(self):
  self.lib.begin();self.lib.WorldSettingsFinishAttempt(1)
  self.assertEqual(self.lib.WorldSettingsEndNativeWorldStart(72,1),0);self.assertEqual(self.lib.choices(),1)
  self.assertEqual(self.lib.bind(),1);self.assertEqual(self.lib.current(),0)
  self.assertEqual(self.lib.WorldSettingsEndNativeWorldStart(73,1),1);self.assertEqual(self.lib.current(),1)


if __name__=='__main__':unittest.main()
