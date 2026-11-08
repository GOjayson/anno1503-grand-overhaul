"""Prepare future lifetime-scoped sources; never edits a compiled source."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[2]
SOURCE=HERE.parent/'experiment_runtime'
source=(SOURCE/'world_ai.c').read_text('utf-8')
def replace(old,new):
 global source
 assert source.count(old)==1,(old,source.count(old));source=source.replace(old,new)
replace('static volatile LONG wsProfileStatus;',
 '''static volatile LONG wsProfileStatus;
static uint32_t wsNativeSequence,wsNativeActive;
static int wsNativeExpected,wsNativeChecked;
static void *wsNativeWorld;
extern int WorldSettingsIsActive(void);
extern void WorldSettingsFinishAttempt(int);
__declspec(dllexport) uint32_t __cdecl WorldSettingsBeginNativeWorldStart(void){
 if(wsNativeActive)return 0; /* reject reentry without consuming its owner */
 InterlockedExchange(&wsProfileStatus,0);
 if(!++wsNativeSequence)++wsNativeSequence;
 wsNativeActive=wsNativeSequence;wsNativeExpected=wsProfilesExpected>=0;
 wsNativeChecked=0;wsNativeWorld=NULL;return wsNativeActive;
}
__declspec(dllexport) int __cdecl WorldSettingsEndNativeWorldStart(uint32_t token,int nativeSuccess){
 if(!token||token!=wsNativeActive)return 0; /* stale completion cannot consume a newer attempt */
 int complete=nativeSuccess&&(!wsNativeExpected||wsNativeChecked);
 int missing=nativeSuccess&&wsNativeExpected&&!wsNativeChecked;
 wsProfilesExpected=-1;wsNativeActive=0;wsNativeExpected=0;wsNativeChecked=0;wsNativeWorld=NULL;
 if(!complete)InterlockedExchange(&wsProfileStatus,0);
 if(!complete&&WorldSettingsIsActive())WorldSettingsFinishAttempt(0);
 if(missing){
  snprintf(wsProfileError,sizeof wsProfileError,"The generated world did not complete opponent validation. Start is blocked.");
  #ifndef WS_AI_FIXTURE
  MessageBoxA(GetActiveWindow(),wsProfileError,"Anno 1503 - World Settings",MB_OK|MB_ICONERROR);
  #endif
 }
 return complete;
}''')
replace('void WorldSettingsAIProfileAttemptFinished(int success){if(!success){InterlockedExchange(&wsProfileStatus,0);wsProfilesExpected=-1;}}',
 'void WorldSettingsAIProfileAttemptFinished(int success){if(!success){InterlockedExchange(&wsProfileStatus,0);wsProfilesExpected=-1;wsNativeChecked=0;wsNativeWorld=NULL;}}')
replace('if(wsProfilesExpected<0)return 1;\n int expected=wsProfilesExpected;wsProfilesExpected=-1;',
 '''if(wsProfilesExpected<0){
  if(wsNativeActive&&wsNativeExpected&&wsNativeChecked&&world!=wsNativeWorld){
   wsNativeChecked=0;InterlockedExchange(&wsProfileStatus,0);
   snprintf(wsProfileError,sizeof wsProfileError,"Opponent validation received a different world. Start is blocked.");
   #ifndef WS_AI_FIXTURE
   MessageBoxA(GetActiveWindow(),wsProfileError,"Anno 1503 - World Settings",MB_OK|MB_ICONERROR);
   #endif
   return 0;
  }return 1;
 }
 int expected=wsProfilesExpected;wsProfilesExpected=-1;
 if(!wsNativeActive||!wsNativeExpected||!wsNativeWorld||world!=wsNativeWorld){
  wsNativeChecked=0;InterlockedExchange(&wsProfileStatus,0);
  snprintf(wsProfileError,sizeof wsProfileError,"Opponent validation does not match the generated world. Start is blocked.");
  #ifndef WS_AI_FIXTURE
  MessageBoxA(GetActiveWindow(),wsProfileError,"Anno 1503 - World Settings",MB_OK|MB_ICONERROR);
  #endif
  return 0;
 }''')
replace('InterlockedExchange(&wsProfileStatus,valid==1?(LONG)expected+1:0);',
 'wsNativeChecked=valid==1;InterlockedExchange(&wsProfileStatus,valid==1?(LONG)expected+1:0);')
anchor='__declspec(dllexport) int WorldSettingsCheckAIControllers(void *world,int32_t expected,void *approvedAI,char *error,uint32_t cap){'
binding='''__declspec(dllexport) int WorldSettingsBindAIProfileWorld(void *scene,char *error,uint32_t cap){
 if(wsProfilesExpected<0||!wsNativeActive||!wsNativeExpected||wsNativeWorld)return wsAIError(error,cap,"Generated world has no unique native start scope.");
 void *world=wsAIPointer(scene,0x160);unsigned char *w=(unsigned char*)WS_AI_WORLD_MODULE();void *vt=wsAIPointer(world,0);
 if(!w||(vt!=w+0xff1d8&&vt!=w+0xff650))return wsAIError(error,cap,"Generated world identity is not the verified native type.");
 wsNativeWorld=world;return 1;
}
'''
replace(anchor,binding+anchor)
(HERE/'world_ai.c.candidate').write_text(source,'utf-8')
header=(SOURCE/'world_ai.h').read_text('utf-8')
assert header.endswith('#endif\n')
header=header[:-7]+'''__declspec(dllexport) uint32_t __cdecl WorldSettingsBeginNativeWorldStart(void);
__declspec(dllexport) int __cdecl WorldSettingsEndNativeWorldStart(uint32_t,int);
__declspec(dllexport) int WorldSettingsBindAIProfileWorld(void*,char*,uint32_t);
#endif
'''
(HERE/'world_ai.h.candidate').write_text(header,'utf-8')
factory=(WORK/'world_factory.c').read_text('utf-8')
old='extern void WorldSettingsFinishAttempt(int);';assert factory.count(old)==1
factory=factory.replace(old,old+'\nextern int WorldSettingsBindAIProfileWorld(void*,char*,uint32_t);')
old='WorldSettingsValidateScene(*out, lastFactoryError, sizeof lastFactoryError) != 1';assert factory.count(old)==1
factory=factory.replace(old,old+' || WorldSettingsBindAIProfileWorld(*out,lastFactoryError,sizeof lastFactoryError) != 1')
(HERE/'world_factory.c.candidate').write_text(factory,'utf-8')
inputs=[SOURCE/'world_ai.c',SOURCE/'world_ai.h',WORK/'world_factory.c']
result=dict(scope=__doc__,compiled_sources_unchanged={str(p.relative_to(WORK)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
 candidate_sha256={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in ['world_ai.c.candidate','world_ai.h.candidate','world_factory.c.candidate']})
(HERE/'candidate_sources.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')
print(json.dumps(dict(candidate_files=3,compiled_sources_changed=False)))
