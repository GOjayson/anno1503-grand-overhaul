/* Part of the existing paused-thread transaction. Seven dispatch pointers and
 * eight already-prepared code calls share preflight, commit and rollback. */
#include "visibility_native_pins.h"
typedef struct WSVisibilityHook {const wchar_t*module;uint32_t slot,target;const char*exportName;} WSVisibilityHook;
static const WSVisibilityHook wsVisibilityHookPlan[]={
 {L"AnnoWelt.dll",0xff398u,0xcc5a0u,"WorldSettingsVisibilityDrawTerrain"},
 {L"AnnoWelt.dll",0xff3a0u,0xcd470u,"WorldSettingsVisibilityDrawTerrainClipped"},
 {L"AnnoWelt.dll",0xff810u,0xcc5a0u,"WorldSettingsVisibilityDrawTerrain"},
 {L"AnnoWelt.dll",0xff818u,0xcd470u,"WorldSettingsVisibilityDrawTerrainClipped"},
 {L"AnnoWelt.dll",0xff5f8u,0xd2620u,"WorldSettingsVisibilityCreateMap"},
 {L"AnnoDisplay.dll",0xf638c0u,0x49410u,"WorldSettingsVisibilityRenderStatic180"},
 {L"AnnoDisplay.dll",0xf638c8u,0x49bd0u,"WorldSettingsVisibilityRenderStatic188"}
};
typedef struct WSVisibilityCall {const wchar_t*module;uint32_t rva,length;unsigned char before[7];const char*exportName;} WSVisibilityCall;
static const WSVisibilityCall wsVisibilityCallPlan[]={
 {L"AnnoWelt.dll",0xcbf15u,6,{0xff,0x90,0,1,0,0},"WorldSettingsVisibilityDispatchResident100"},
 {L"AnnoWelt.dll",0xcdb1cu,6,{0xff,0x90,8,1,0,0},"WorldSettingsVisibilityDispatchResident108"},
 {L"AnnoWelt.dll",0xcbe60u,6,{0xff,0x90,0,1,0,0},"WorldSettingsVisibilityDispatchOccurrence100"},
 {L"AnnoFrame.dll",0x1bc1fu,6,{0xff,0x90,0x20,1,0,0},"WorldSettingsVisibilityMinimapExclude"},
 {L"AnnoWelt.dll",0xcb91au,7,{0x41,0xff,0x92,0x88,1,0,0},"WorldSettingsVisibilityDrawStatic188"},
 {L"AnnoWelt.dll",0xcb9ccu,7,{0x41,0xff,0x92,0x80,1,0,0},"WorldSettingsVisibilityDrawStatic180"},
 {L"AnnoWelt.dll",0xcbc89u,6,{0xff,0x90,0x80,1,0,0},"WorldSettingsVisibilityDrawStatic180"},
 {L"AnnoWelt.dll",0xcde09u,6,{0xff,0x90,0x80,1,0,0},"WorldSettingsVisibilityDrawStatic180"}
};
_Static_assert(sizeof wsVisibilityHookPlan/sizeof wsVisibilityHookPlan[0]==WS_VISIBILITY_POINTER_COUNT,"Visibility pointer count differs");
_Static_assert(sizeof wsVisibilityCallPlan/sizeof wsVisibilityCallPlan[0]==WS_VISIBILITY_CALL_COUNT,"Visibility call count differs");
_Static_assert(WS_VISIBILITY_POINTER_COUNT+WS_VISIBILITY_CALL_COUNT==WS_VISIBILITY_HOOK_COUNT,"Visibility total differs");
static unsigned char*wsVisibilitySites[WS_VISIBILITY_HOOK_COUNT];
static unsigned char wsVisibilityExpected[WS_VISIBILITY_HOOK_COUNT][WS_MAX_PATCH];
static uint32_t wsVisibilityLengths[WS_VISIBILITY_HOOK_COUNT];
static unsigned char*wsVisibilityBridges[WS_VISIBILITY_CALL_COUNT];
static uintptr_t wsVisibilityCallbacks[WS_VISIBILITY_CALL_COUNT];
static const unsigned char wsVisibilityLeaf[8]={0xff,0x25,2,0,0,0,0x90,0x90};

static int wsPrepareVisibility(HMODULE self,WSPatch*patches,uint32_t*count){
 HMODULE module=wsEngineModules[WS_ENGINE_MODULE_WORLD];uint32_t imageSize=0;
 if(!patches||!count||*count>WS_MAX_HOOKS||!module||!wsModuleImage(module,&imageSize)||
    WS_VISIBILITY_POINTER_COUNT>WS_MAX_HOOKS-*count)
  return wsError("Visibility dispatch exceeds the verified native transaction bounds.");
 for(uint32_t i=0;i<sizeof wsVisibilityModulePins/sizeof wsVisibilityModulePins[0];i++){
  const WSVisibilityModulePin*p=&wsVisibilityModulePins[i];uint32_t size=0;HMODULE loaded=GetModuleHandleW(p->name);
  if(!loaded||!wsModuleImage(loaded,&size)||!wsHashModule(loaded,p->sha256))
   return wsError("A visibility data or renderer module differs from this exact native profile.");
 }
 /* wsPrepareBlob already owns these edits and their registered allocations.
  * Validate their full linkage, without appending them a second time. */
 for(uint32_t i=0;i<WS_VISIBILITY_CALL_COUNT;i++){
  const WSVisibilityCall*entry=&wsVisibilityCallPlan[i];WSPatch*found=0;unsigned char*bridge=0;uint32_t matches=0;
  HMODULE owner=GetModuleHandleW(entry->module);FARPROC callback=GetProcAddress(self,entry->exportName);
  if(!owner||!callback)return wsError("A strict visibility call lacks its native module or callback.");
  for(uint32_t j=0;j<WS_BLOB_COUNT;j++)if(wsInstalled[j].module==owner){
   const WSBlob*blob=&wsBlobs[j];
   for(uint32_t k=0;k<blob->hookCount;k++){
    const WSHook*h=&blob->hooks[k];if(h->rva!=entry->rva)continue;
    if(h->length!=entry->length||h->call!=1||memcmp(h->before,entry->before,entry->length)||
       !wsSpan(h->target,16,blob->codeSize)||!wsInstalled[j].registered)
     return wsError("Strict visibility call metadata differs from its reviewed instruction and leaf.");
    bridge=wsInstalled[j].allocation+h->target;matches++;
   }
  }
  if(matches!=1||!bridge||!wsReadable(bridge,16)||memcmp(bridge,wsVisibilityLeaf,8))
   return wsError("Strict visibility requires one complete registered native leaf bridge.");
  uintptr_t target=(uintptr_t)callback;
  if(memcmp(bridge+8,&target,8))return wsError("A strict visibility bridge has the wrong compiled delegate.");
  for(uint32_t j=0;j<*count;j++)if(patches[j].address==(unsigned char*)owner+entry->rva){if(found)return wsError("Duplicate strict visibility call edit.");found=&patches[j];}
  if(!found||found->length!=entry->length||memcmp(found->before,entry->before,entry->length)||found->after[0]!=0xe8)
   return wsError("A strict visibility call is missing from the guarded transaction.");
  int32_t displacement=0;memcpy(&displacement,found->after+1,4);
  if((uintptr_t)(found->address+5)+(intptr_t)displacement!=(uintptr_t)bridge)
   return wsError("A strict visibility native call does not reach its verified leaf.");
  for(uint32_t j=5;j<entry->length;j++)if(found->after[j]!=0x90)return wsError("Strict visibility call padding differs.");
  uint32_t index=WS_VISIBILITY_POINTER_COUNT+i;wsVisibilitySites[index]=found->address;
  wsVisibilityLengths[index]=found->length;memcpy(wsVisibilityExpected[index],found->after,found->length);
  wsVisibilityBridges[i]=bridge;wsVisibilityCallbacks[i]=target;
 }
 for(uint32_t i=0;i<WS_VISIBILITY_POINTER_COUNT;i++){
  const WSVisibilityHook*entry=&wsVisibilityHookPlan[i];uint32_t ownerSize=0;
  HMODULE owner=GetModuleHandleW(entry->module);
  if(!owner||!wsModuleImage(owner,&ownerSize)||!wsSpan(entry->slot,8,ownerSize)||!wsSpan(entry->target,1,ownerSize))
   return wsError("A visibility dispatch leaves the inspected native image.");
  unsigned char*site=(unsigned char*)owner+entry->slot;uintptr_t before=(uintptr_t)owner+entry->target;
  if(!wsReadable(site,8)||memcmp(site,&before,8))
   return wsError("A native visibility dispatch differs from its exact History Edition preimage.");
  FARPROC callback=GetProcAddress(self,entry->exportName);
  if(!callback)return wsError("The selected runtime lacks a required visibility callback.");
  uintptr_t after=(uintptr_t)callback;
  for(uint32_t j=0;j<*count;j++){
   uintptr_t a=(uintptr_t)site,b=(uintptr_t)patches[j].address;
   if(a<b+patches[j].length&&b<a+8u)return wsError("Visibility dispatch overlaps another native transaction edit.");
  }
  WSPatch*patch=&patches[(*count)++];patch->address=site;patch->length=8;
  memcpy(patch->before,&before,8);memcpy(patch->after,&after,8);
  wsVisibilitySites[i]=site;wsVisibilityLengths[i]=8;memcpy(wsVisibilityExpected[i],&after,8);
 }
 return 1;
}
static DWORD wsVisibilityPatchStatusUnlocked(void){
 if(wsInstallState!=1)return 0;
 for(uint32_t i=0;i<WS_VISIBILITY_HOOK_COUNT;i++)
  if(!wsVisibilitySites[i]||!wsVisibilityLengths[i]||wsVisibilityLengths[i]>WS_MAX_PATCH||
     !wsReadable(wsVisibilitySites[i],wsVisibilityLengths[i])||
     memcmp(wsVisibilitySites[i],wsVisibilityExpected[i],wsVisibilityLengths[i]))return 0;
 for(uint32_t i=0;i<WS_VISIBILITY_CALL_COUNT;i++)
  if(!wsVisibilityBridges[i]||!wsReadable(wsVisibilityBridges[i],16)||
     memcmp(wsVisibilityBridges[i],wsVisibilityLeaf,8)||
     memcmp(wsVisibilityBridges[i]+8,&wsVisibilityCallbacks[i],8))return 0;
 return WS_VISIBILITY_HOOK_COUNT;
}
__declspec(dllexport) DWORD WorldSettingsVisibilityPatchStatus(void){
 AcquireSRWLockShared(&wsInstallLock);DWORD result=wsVisibilityPatchStatusUnlocked();
 ReleaseSRWLockShared(&wsInstallLock);return result;
}
