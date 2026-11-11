/* Part of the existing paused-thread transaction. Eleven native dispatch
 * pointers, one cross-module import and sixteen prepared branches share
 * preflight, commit and rollback. */
#include "visibility_native_pins.h"
typedef struct WSVisibilityHook {const wchar_t*module;uint32_t slot,target;const char*exportName;} WSVisibilityHook;
static const WSVisibilityHook wsVisibilityHookPlan[]={
 {L"AnnoWelt.dll",0xff398u,0xcc5a0u,"WorldSettingsVisibilityDrawTerrain"},
 {L"AnnoWelt.dll",0xff3a0u,0xcd470u,"WorldSettingsVisibilityDrawTerrainClipped"},
 {L"AnnoWelt.dll",0xff810u,0xcc5a0u,"WorldSettingsVisibilityDrawTerrain"},
 {L"AnnoWelt.dll",0xff818u,0xcd470u,"WorldSettingsVisibilityDrawTerrainClipped"},
 {L"AnnoWelt.dll",0xff5f8u,0xd2620u,"WorldSettingsVisibilityCreateMap"},
 {L"AnnoDisplay.dll",0xf638c0u,0x49410u,"WorldSettingsVisibilityRenderStatic180"},
 {L"AnnoDisplay.dll",0xf638c8u,0x49bd0u,"WorldSettingsVisibilityRenderStatic188"},
 {L"AnnoFrame.dll",0xa7248u,0x78630u,"WorldSettingsVisibilityBuildingCommand"},
 {L"AnnoFrame.dll",0xa7250u,0x785d0u,"WorldSettingsVisibilityShipQueue"},
 {L"AnnoFrame.dll",0xa74f0u,0x7d340u,"WorldSettingsVisibilityBuildingCommand"},
 {L"AnnoFrame.dll",0xa74f8u,0x7d230u,"WorldSettingsVisibilityShipQueue"}
};
typedef struct WSVisibilityImportHook {const wchar_t*module;uint32_t slot;const wchar_t*targetModule;const char*importName;uint32_t target;const char*exportName;} WSVisibilityImportHook;
static const WSVisibilityImportHook wsVisibilityImportHookPlan[]={
 {L"View.dll",0xa1098u,L"AnnoScene.dll","CreateAnnoSceneInstance",0x11a0u,"WorldSettingsVisibilityCreateSceneFromView"}
};
typedef struct WSVisibilityCall {const wchar_t*module;uint32_t rva,length;unsigned char before[7];const char*exportName;int call,contextArgument;} WSVisibilityCall;
static const WSVisibilityCall wsVisibilityCallPlan[]={
 {L"AnnoWelt.dll",0xcbf15u,6,{0xff,0x90,0,1,0,0},"WorldSettingsVisibilityDispatchResident100",1,0},
 {L"AnnoWelt.dll",0xcdb1cu,6,{0xff,0x90,8,1,0,0},"WorldSettingsVisibilityDispatchResident108",1,0},
 {L"AnnoWelt.dll",0xcbe60u,6,{0xff,0x90,0,1,0,0},"WorldSettingsVisibilityDispatchOccurrence100",1,0},
 {L"AnnoFrame.dll",0x1bc1fu,6,{0xff,0x90,0x20,1,0,0},"WorldSettingsVisibilityMinimapExclude",1,0},
 {L"AnnoWelt.dll",0xcb91au,7,{0x41,0xff,0x92,0x88,1,0,0},"WorldSettingsVisibilityDrawStatic188",1,0},
 {L"AnnoWelt.dll",0xcb9ccu,7,{0x41,0xff,0x92,0x80,1,0,0},"WorldSettingsVisibilityDrawStatic180",1,0},
 {L"AnnoWelt.dll",0xcbc89u,6,{0xff,0x90,0x80,1,0,0},"WorldSettingsVisibilityDrawStatic180",1,0},
 {L"AnnoWelt.dll",0xcde09u,6,{0xff,0x90,0x80,1,0,0},"WorldSettingsVisibilityDrawStatic180",1,0},
 {L"AnnoFrame.dll",0x75b80u,5,{0xe9,0x0b,0,0,0},"WorldSettingsVisibilitySave",0,0},
 {L"AnnoFrame.dll",0x7666cu,5,{0xe8,0x1f,0xf5,0xff,0xff},"WorldSettingsVisibilitySave",1,0},
 {L"AnnoFrame.dll",0x7e713u,5,{0xe8,0x78,0x74,0xff,0xff},"WorldSettingsVisibilitySave",1,0},
 {L"AnnoFrame.dll",0x8040au,5,{0xe8,0x81,0x57,0xff,0xff},"WorldSettingsVisibilitySave",1,0},
 {L"AnnoFrame.dll",0x1ca76u,6,{0xff,0x90,0x18,1,0,0},"WorldSettingsVisibilityFinishFrame",1,1},
 {L"AnnoFrame.dll",0x169acu,6,{0xff,0x90,0xf0,0,0,0},"WorldSettingsVisibilityInteractionProperty",1,0},
 {L"AnnoFrame.dll",0x16a72u,6,{0xff,0x90,0xf0,0,0,0},"WorldSettingsVisibilityInteractionProperty",1,0},
 {L"AnnoFrame.dll",0x76b50u,6,{0xff,0x90,0xa8,0,0,0},"WorldSettingsVisibilityLoadFileA8",1,0}
};
_Static_assert(sizeof wsVisibilityHookPlan/sizeof wsVisibilityHookPlan[0]==WS_VISIBILITY_NATIVE_POINTER_COUNT,"Visibility pointer count differs");
_Static_assert(sizeof wsVisibilityCallPlan/sizeof wsVisibilityCallPlan[0]==WS_VISIBILITY_CALL_COUNT,"Visibility call count differs");
_Static_assert(sizeof wsVisibilityImportHookPlan/sizeof wsVisibilityImportHookPlan[0]==WS_VISIBILITY_IMPORT_COUNT,"Visibility import count differs");
_Static_assert(WS_VISIBILITY_NATIVE_POINTER_COUNT+WS_VISIBILITY_IMPORT_COUNT==WS_VISIBILITY_POINTER_COUNT,"Visibility pointer family total differs");
_Static_assert(WS_VISIBILITY_POINTER_COUNT+WS_VISIBILITY_CALL_COUNT==WS_VISIBILITY_HOOK_COUNT,"Visibility total differs");
static unsigned char*wsVisibilitySites[WS_VISIBILITY_HOOK_COUNT];
static unsigned char wsVisibilityExpected[WS_VISIBILITY_HOOK_COUNT][WS_MAX_PATCH];
static uint32_t wsVisibilityLengths[WS_VISIBILITY_HOOK_COUNT];
static unsigned char*wsVisibilityBridges[WS_VISIBILITY_CALL_COUNT];
static uintptr_t wsVisibilityCallbacks[WS_VISIBILITY_CALL_COUNT];

static const unsigned char wsVisibilityViewFactoryHead[15]={0x41,0x56,0x48,0x83,0xec,0x30,0x48,0xc7,0x44,0x24,0x20,0xfe,0xff,0xff,0xff};
static uint32_t wsVisibilityRead32(const unsigned char*p){uint32_t v;memcpy(&v,p,4);return v;}
static uint64_t wsVisibilityRead64(const unsigned char*p){uint64_t v;memcpy(&v,p,8);return v;}
static int wsVisibilityImportString(unsigned char*base,uint32_t size,uint32_t rva,const char*text){
 size_t n=strlen(text)+1u;return n<=256u&&wsSpan(rva,(uint32_t)n,size)&&wsReadable(base+rva,n)&&!memcmp(base+rva,text,n);
}
static int wsVisibilityImportIdentity(HMODULE owner,uint32_t slot,const char*dll,const char*name){
 unsigned char*base=(unsigned char*)owner;uint32_t size=0;if(!wsModuleImage(owner,&size)||!wsReadable(base,64))return 0;
 uint32_t nt=wsVisibilityRead32(base+60);if(!wsSpan(nt,0x98u,size)||!wsReadable(base+nt,0x98u))return 0;
 if(memcmp(base,"MZ",2)||memcmp(base+nt,"PE\0\0",4)||base[nt+4]!=0x64||base[nt+5]!=0x86||base[nt+24]!=0x0b||base[nt+25]!=2)return 0;
 uint32_t rva=wsVisibilityRead32(base+nt+0x90u),bytes=wsVisibilityRead32(base+nt+0x94u);
 if(!rva||bytes<40u||bytes>4096u*20u||bytes%20u||!wsSpan(rva,bytes,size)||!wsReadable(base+rva,bytes))return 0;
 uint32_t matches=0;int terminated=0;
 for(uint32_t at=0;at<bytes;at+=20u){unsigned char*d=base+rva+at;uint32_t lookup=wsVisibilityRead32(d),first=wsVisibilityRead32(d+16);
  if(!lookup&&!wsVisibilityRead32(d+4)&&!wsVisibilityRead32(d+8)&&!wsVisibilityRead32(d+12)&&!first){terminated=1;break;}
  if(!first||slot<first||(slot-first)%8u||(slot-first)/8u>=8192u)continue;
  if(!lookup)return 0;uint32_t index=(slot-first)/8u;uint64_t thunk=0;int stopped=0;
  for(uint32_t i=0;i<=index;i++){if(i>(UINT32_MAX-lookup)/8u||!wsSpan(lookup+i*8u,8,size)||!wsReadable(base+lookup+i*8u,8))return 0;thunk=wsVisibilityRead64(base+lookup+i*8u);if(!thunk){stopped=1;break;}}
  if(stopped)continue;if(thunk>UINT32_MAX-2u||(thunk>>63))return 0;
  if(!wsVisibilityImportString(base,size,wsVisibilityRead32(d+12),dll)||!wsVisibilityImportString(base,size,(uint32_t)thunk+2u,name))return 0;matches++;
 }
 return terminated&&matches==1u;
}
static int wsPrepareVisibilityImports(HMODULE self,WSPatch*patches,uint32_t*count){
 if(!patches||!count||*count>WS_MAX_HOOKS||WS_VISIBILITY_IMPORT_COUNT>WS_MAX_HOOKS-*count)return wsError("Visibility import exceeds the native transaction bounds.");
 for(uint32_t i=0;i<WS_VISIBILITY_IMPORT_COUNT;i++){
  const WSVisibilityImportHook*entry=&wsVisibilityImportHookPlan[i];uint32_t ownerSize=0,targetSize=0;
  HMODULE owner=GetModuleHandleW(entry->module),dependency=GetModuleHandleW(entry->targetModule);
  if(!owner||!dependency||!wsModuleImage(owner,&ownerSize)||!wsModuleImage(dependency,&targetSize)||!wsSpan(entry->slot,8,ownerSize)||!wsSpan(entry->target,sizeof wsVisibilityViewFactoryHead,targetSize)||
     !wsVisibilityImportIdentity(owner,entry->slot,"AnnoScene.dll",entry->importName))return wsError("The exact View Scene-factory import descriptor differs.");
  unsigned char*site=(unsigned char*)owner+entry->slot;uintptr_t before=(uintptr_t)dependency+entry->target;
  if(GetProcAddress(dependency,entry->importName)!=(FARPROC)before||!wsReadable((void*)before,sizeof wsVisibilityViewFactoryHead)||memcmp((void*)before,wsVisibilityViewFactoryHead,sizeof wsVisibilityViewFactoryHead)||!wsReadable(site,8)||memcmp(site,&before,8))
   return wsError("The View Scene-factory import has a different cross-module export/preimage.");
  FARPROC callback=GetProcAddress(self,entry->exportName);if(!callback)return wsError("The runtime lacks its View Scene-factory adapter.");uintptr_t after=(uintptr_t)callback;
  for(uint32_t j=0;j<*count;j++){uintptr_t a=(uintptr_t)site,b=(uintptr_t)patches[j].address;if(a<b+patches[j].length&&b<a+8u)return wsError("Visibility import overlaps another native transaction edit.");}
  WSPatch*patch=&patches[(*count)++];patch->address=site;patch->length=8;memcpy(patch->before,&before,8);memcpy(patch->after,&after,8);
  uint32_t index=WS_VISIBILITY_NATIVE_POINTER_COUNT+i;wsVisibilitySites[index]=site;wsVisibilityLengths[index]=8;memcpy(wsVisibilityExpected[index],&after,8);
 }return 1;
}

static const unsigned char wsVisibilityLeaf[8]={0xff,0x25,2,0,0,0,0x90,0x90};
static const unsigned char wsVisibilityContextLeaf[16]={0x48,0x89,0xfa,0xff,0x25,7,0,0,0,0x90,0x90,0x90,0x90,0x90,0x90,0x90};

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
    if(h->length!=entry->length||h->call!=entry->call||memcmp(h->before,entry->before,entry->length)||
       !wsSpan(h->target,entry->contextArgument?24u:16u,blob->codeSize)||!wsInstalled[j].registered)
     return wsError("Strict visibility call metadata differs from its reviewed instruction and leaf.");
    bridge=wsInstalled[j].allocation+h->target;matches++;
   }
  }
  uint32_t importOffset=entry->contextArgument?16u:8u;
  const unsigned char*head=entry->contextArgument?wsVisibilityContextLeaf:wsVisibilityLeaf;
  if(matches!=1||!bridge||!wsReadable(bridge,importOffset+8u)||memcmp(bridge,head,importOffset))
   return wsError("Strict visibility requires one complete registered native leaf bridge.");
  uintptr_t target=(uintptr_t)callback;
  if(memcmp(bridge+importOffset,&target,8))return wsError("A strict visibility bridge has the wrong compiled delegate.");
  for(uint32_t j=0;j<*count;j++)if(patches[j].address==(unsigned char*)owner+entry->rva){if(found)return wsError("Duplicate strict visibility call edit.");found=&patches[j];}
  if(!found||found->length!=entry->length||memcmp(found->before,entry->before,entry->length)||found->after[0]!=(entry->call?0xe8:0xe9))
   return wsError("A strict visibility call is missing from the guarded transaction.");
  int32_t displacement=0;memcpy(&displacement,found->after+1,4);
  if((uintptr_t)(found->address+5)+(intptr_t)displacement!=(uintptr_t)bridge)
   return wsError("A strict visibility native call does not reach its verified leaf.");
  for(uint32_t j=5;j<entry->length;j++)if(found->after[j]!=0x90)return wsError("Strict visibility call padding differs.");
  uint32_t index=WS_VISIBILITY_POINTER_COUNT+i;wsVisibilitySites[index]=found->address;
  wsVisibilityLengths[index]=found->length;memcpy(wsVisibilityExpected[index],found->after,found->length);
  wsVisibilityBridges[i]=bridge;wsVisibilityCallbacks[i]=target;
 }
 for(uint32_t i=0;i<WS_VISIBILITY_NATIVE_POINTER_COUNT;i++){
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
 if(!wsPrepareVisibilityImports(self,patches,count))return 0;
 return 1;
}
static DWORD wsVisibilityPatchStatusUnlocked(void){
 if(wsInstallState!=1)return 0;
 for(uint32_t i=0;i<WS_VISIBILITY_HOOK_COUNT;i++)
  if(!wsVisibilitySites[i]||!wsVisibilityLengths[i]||wsVisibilityLengths[i]>WS_MAX_PATCH||
     !wsReadable(wsVisibilitySites[i],wsVisibilityLengths[i])||
     memcmp(wsVisibilitySites[i],wsVisibilityExpected[i],wsVisibilityLengths[i]))return 0;
 for(uint32_t i=0;i<WS_VISIBILITY_CALL_COUNT;i++){
  uint32_t offset=wsVisibilityCallPlan[i].contextArgument?16u:8u;
  const unsigned char*head=wsVisibilityCallPlan[i].contextArgument?wsVisibilityContextLeaf:wsVisibilityLeaf;
  if(!wsVisibilityBridges[i]||!wsReadable(wsVisibilityBridges[i],offset+8u)||
     memcmp(wsVisibilityBridges[i],head,offset)||
     memcmp(wsVisibilityBridges[i]+offset,&wsVisibilityCallbacks[i],8))return 0;
 }
 return WS_VISIBILITY_HOOK_COUNT;
}
__declspec(dllexport) DWORD WorldSettingsVisibilityPatchStatus(void){
 AcquireSRWLockShared(&wsInstallLock);DWORD result=wsVisibilityPatchStatusUnlocked();
 ReleaseSRWLockShared(&wsInstallLock);return result;
}
