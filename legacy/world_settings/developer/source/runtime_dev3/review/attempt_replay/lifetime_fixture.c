static void *wsAttemptFixtureApproved;
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "world_ai.h"
#include "stock_ai_profiles.h"
#ifndef WS_AI_FIXTURE
#include "../../ai_loader/ai_loader.h"
#endif
static int wsProfilesExpected=-1;
static char wsProfileError[512];
static volatile LONG wsProfileStatus;
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
}
/* Remote-thread-compatible result:0unverified,1..4verified AIcount+1. */
__declspec(dllexport) DWORD WINAPI WorldSettingsAIProfileStatus(void *unused){(void)unused;return (DWORD)InterlockedCompareExchange(&wsProfileStatus,0,0);}
void WorldSettingsExpectAIProfiles(int32_t count){InterlockedExchange(&wsProfileStatus,0);wsProfilesExpected=count;wsProfileError[0]=0;}
void WorldSettingsAIProfileAttemptFinished(int success){if(!success){InterlockedExchange(&wsProfileStatus,0);wsProfilesExpected=-1;wsNativeChecked=0;wsNativeWorld=NULL;}}
__declspec(dllexport) unsigned long WorldSettingsCopyAIProfileError(void *buffer){
 if(!buffer)return 0;char *out=(char*)buffer;unsigned long n=0;
 do{out[n]=wsProfileError[n];n++;}while(n<sizeof wsProfileError&&wsProfileError[n-1]);out[n-1]=0;return n;
}
__declspec(dllexport) int WorldSettingsAfterProfiles(void *world){
 if(wsProfilesExpected<0){
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
 }
 #ifdef WS_AI_FIXTURE
 void *approved=wsAttemptFixtureApproved;
 #else
 void *approved=WorldSettingsLoadedAIModule();
 #endif
 int valid=WorldSettingsCheckAIControllers(world,expected,approved,wsProfileError,sizeof wsProfileError);
 wsNativeChecked=valid==1;InterlockedExchange(&wsProfileStatus,valid==1?(LONG)expected+1:0);
 #ifndef WS_AI_FIXTURE
 if(!valid)MessageBoxA(GetActiveWindow(),wsProfileError,"Anno 1503 - World Settings",MB_OK|MB_ICONERROR);
 #endif
 return valid;
}
static int wsAIWritable(const void *p,SIZE_T n){
 uintptr_t at=(uintptr_t)p,end;MEMORY_BASIC_INFORMATION m;
 if(!at||n>UINTPTR_MAX-at)return 0;end=at+n;
 while(at<end){
  if(!VirtualQuery((void*)at,&m,sizeof m)||m.State!=MEM_COMMIT||m.Protect&(PAGE_GUARD|PAGE_NOACCESS))return 0;
  DWORD protection=m.Protect&255;
  if(protection!=PAGE_READWRITE&&protection!=PAGE_WRITECOPY&&protection!=PAGE_EXECUTE_READWRITE&&protection!=PAGE_EXECUTE_WRITECOPY)return 0;
  uintptr_t base=(uintptr_t)m.BaseAddress;if(m.RegionSize>UINTPTR_MAX-base||base+m.RegionSize<=at)return 0;
  at=base+m.RegionSize<end?base+m.RegionSize:end;
 }return 1;
}
static int wsAIError(char *out,uint32_t cap,const char *message){if(out&&cap){snprintf(out,cap,"%s",message);out[cap-1]=0;}return 0;}
static int wsAIRead(const void *pointer,void *out,SIZE_T n){
 uintptr_t at=(uintptr_t)pointer,end;MEMORY_BASIC_INFORMATION m;
 if(!at||!out||n>UINTPTR_MAX-at)return 0;end=at+n;
 while(at<end){
  if(!VirtualQuery((void*)at,&m,sizeof m)||m.State!=MEM_COMMIT||m.Protect&(PAGE_GUARD|PAGE_NOACCESS))return 0;
  DWORD p=m.Protect&255;
  if(p!=PAGE_READONLY&&p!=PAGE_READWRITE&&p!=PAGE_WRITECOPY&&p!=PAGE_EXECUTE_READ&&p!=PAGE_EXECUTE_READWRITE&&p!=PAGE_EXECUTE_WRITECOPY)return 0;
  uintptr_t base=(uintptr_t)m.BaseAddress;if(m.RegionSize>UINTPTR_MAX-base||base+m.RegionSize<=at)return 0;
  at=base+m.RegionSize<end?base+m.RegionSize:end;
 }memcpy(out,pointer,n);return 1;
}
static void *wsAIPointer(const void *object,SIZE_T offset){
 uintptr_t p=(uintptr_t)object;void *result=NULL;
 if(!p||offset>UINTPTR_MAX-p||!wsAIRead((void*)(p+offset),&result,sizeof result))return NULL;
 return result;
}
#ifdef WS_AI_FIXTURE
static void *wsFixtureWorldModule;
__declspec(dllexport) void WorldSettingsAITestWorldModule(void *module){wsFixtureWorldModule=module;}
#define WS_AI_WORLD_MODULE() wsFixtureWorldModule
#else
#define WS_AI_WORLD_MODULE() GetModuleHandleA("AnnoWelt.dll")
#endif
__declspec(dllexport) int WorldSettingsBindAIProfileWorld(void *scene,char *error,uint32_t cap){
 if(wsProfilesExpected<0||!wsNativeActive||!wsNativeExpected||wsNativeWorld)return wsAIError(error,cap,"Generated world has no unique native start scope.");
 void *world=wsAIPointer(scene,0x160);unsigned char *w=(unsigned char*)WS_AI_WORLD_MODULE();void *vt=wsAIPointer(world,0);
 if(!w||(vt!=w+0xff1d8&&vt!=w+0xff650))return wsAIError(error,cap,"Generated world identity is not the verified native type.");
 wsNativeWorld=world;return 1;
}
__declspec(dllexport) int WorldSettingsCheckAIControllers(void *world,int32_t expected,void *approvedAI,char *error,uint32_t cap){
 if(expected<0||expected>3||!approvedAI)return wsAIError(error,cap,"Opponent count or approved AI payload is missing.");
 unsigned char *w=(unsigned char*)WS_AI_WORLD_MODULE(),*a=(unsigned char*)approvedAI;
 void *vt=wsAIPointer(world,0),*table=wsAIPointer(world,0x210);
 if(!w||(vt!=w+0xff1d8&&vt!=w+0xff650)||wsAIPointer(table,0)!=w+0xfdbc0||wsAIPointer(w+0xfdbc0,0x10)!=w+0xc6d80||wsAIPointer(w+0xfdbc0,0x18)!=w+0x95990)return wsAIError(error,cap,"Loaded opponent table is not the verified native type.");
 uint32_t active=0,placeholders=0;
 for(uint32_t id=0;id<32;id++){
  void *player=wsAIPointer(table,8+id*8);if(!player)continue;
  uint16_t type=0;
  if(wsAIPointer(player,0)!=w+0xfabe0||!wsAIRead((unsigned char*)player+0x9c,&type,2))return wsAIError(error,cap,"Loaded player has an unsupported native type.");
  if(type!=12)continue;
  void *controller=wsAIPointer(player,0x18),*cv=wsAIPointer(controller,0);uint32_t cpu=0,suspend=0,disabled=0;unsigned char thinking=0;
  int classic=cv==a+0x84fc8;
  uint32_t vtable=classic?0x84fc8:0x88128,setter=classic?0x4260:0x6090,getter=classic?0x4a10:0x6640;
  MEMORY_BASIC_INFORMATION allocation;
  if(cv!=a+vtable||!VirtualQuery(cv,&allocation,sizeof allocation)||allocation.AllocationBase!=a||wsAIPointer(cv,8)!=a+setter||wsAIPointer(cv,0x10)!=a+getter||
   !wsAIRead((unsigned char*)controller+0xa4c,&cpu,4)||cpu!=12||!wsAIRead((unsigned char*)controller+0xab4,&suspend,4)||!wsAIRead((unsigned char*)controller+0xab0,&disabled,4)||!wsAIRead((unsigned char*)controller+0x1e9d,&thinking,1)||suspend>1||disabled>1||thinking>1)return wsAIError(error,cap,"A loaded opponent is not using the approved Food AI controller.");
  placeholders++;
  if(thinking!=(unsigned char)!suspend||(disabled&&(!suspend||thinking)))return wsAIError(error,cap,"Opponent suspension and thinking flags disagree.");
  if(!suspend&&!disabled&&thinking)active++;
 }
 if(placeholders<3||placeholders>4||active!=(uint32_t)expected){
  if(error&&cap){snprintf(error,cap,"Loaded active opponents differ from selection: requested=%ld active=%u stock=%u.",(long)expected,active,placeholders);error[cap-1]=0;}return 0;
 }
 if(error&&cap)error[0]=0;return 1;
}
__declspec(dllexport) int WorldSettingsBindStockAIProfiles(void *setup,int32_t difficulty,int32_t count,char *error,uint32_t cap){
 if(difficulty<0||difficulty>2||count<0||count>3)return wsAIError(error,cap,"AI experiment supports zero to three existing stock placeholders.");
 uintptr_t base=(uintptr_t)setup;
 if(!base||base>UINTPTR_MAX-0x2720||!wsAIWritable((void*)(base+0x2280),0x4a0))return wsAIError(error,cap,"Native opponent setup storage is not writable.");
 /* Build all seven transport records first. Do not inherit profiles from a
  * previously selected difficulty or preserve extra enabled placeholders. */
 unsigned char flags[7]={0},records[7*168]={0};
 for(int32_t i=0;i<count;i++){flags[i]=1;memcpy(records+i*168,wsAIProfiles[difficulty][i],168);}
 memcpy((void*)(base+0x2288),records,sizeof records);
 memcpy((void*)(base+0x2280),flags,sizeof flags);
 if(error&&cap)error[0]=0;return 1;
}

__declspec(dllexport) void FixtureExpect(int n){WorldSettingsExpectAIProfiles(n);}
__declspec(dllexport) void FixtureFinish(int n){WorldSettingsAIProfileAttemptFinished(n);}
__declspec(dllexport) void FixtureApprove(void *p){wsAttemptFixtureApproved=p;}
static int fixturePending,fixtureCleanups;
int WorldSettingsIsActive(void){return fixturePending;}
void WorldSettingsFinishAttempt(int success){fixturePending=0;fixtureCleanups++;WorldSettingsAIProfileAttemptFinished(success);}
__declspec(dllexport) void FixturePending(int n){fixturePending=n;fixtureCleanups=0;}
__declspec(dllexport) int FixtureCleanups(void){return fixtureCleanups;}
