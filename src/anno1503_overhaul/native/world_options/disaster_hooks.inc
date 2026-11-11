/* Certify the eight calls already owned by wsPrepareBlob. This adds no second
 * patch operation. Readiness rechecks both sites and full relocated bridges. */
static const uint32_t wsDisasterRvas[8]={0xb1c56u,0xb1d4au,0xe0b52u,0x587f3u,0x75977u,0x58870u,0x75a5eu,0xe0d26u};
static const char*wsDisasterExports[8]={"WorldSettingsDisasterFireRandom","WorldSettingsDisasterPlagueRandom","WorldSettingsDisasterEarthquakeThreshold","WorldSettingsDisasterDroughtThreshold","WorldSettingsDisasterVolcanoInterval","WorldSettingsDisasterDroughtBegin","WorldSettingsDisasterCreateEvent","WorldSettingsDisasterCreateEvent"};
static unsigned char*wsDisasterSites[8],*wsDisasterBridges[8];
static uint32_t wsDisasterSiteLengths[8],wsDisasterBridgeLengths[8];
static unsigned char wsDisasterSiteExpected[8][WS_MAX_PATCH],wsDisasterBridgeExpected[8][128];
static int wsPrepareDisasterHooks(HMODULE self,WSPatch*patches,uint32_t count){
 HMODULE owner=GetModuleHandleW(L"AnnoWelt.dll");
 if(!owner||!patches||count!=17u+WS_ENGINE_PATCH_COUNT+WS_VISIBILITY_HOOK_COUNT||count!=WS_MAX_HOOKS)
  return wsError("The complete disaster transaction does not contain exactly eight additional hooks.");
 for(uint32_t i=0;i<8u;i++){
  const WSHook*hook=NULL;const WSBlob*blob=NULL;WSInstalledBlob*installed=NULL;uint32_t matches=0;
  for(uint32_t b=0;b<WS_BLOB_COUNT;b++)if(wsInstalled[b].module==owner){
   for(uint32_t h=0;h<wsBlobs[b].hookCount;h++)if(wsBlobs[b].hooks[h].rva==wsDisasterRvas[i]){
    hook=&wsBlobs[b].hooks[h];blob=&wsBlobs[b];installed=&wsInstalled[b];matches++;
   }
  }
  if(matches!=1u||!blob||!installed->registered||!hook->call||hook->length<5u||hook->length>WS_MAX_PATCH)
   return wsError("A disaster call has no unique registered native bridge.");
  const WSFunctionMeta*function=NULL;matches=0;
  for(uint32_t f=0;f<blob->functionCount;f++)if(blob->functions[f].begin==hook->target){function=&blob->functions[f];matches++;}
  if(matches!=1u||function->end<=function->begin||function->end>blob->codeSize||function->end>UINT32_MAX-15u)
   return wsError("A disaster bridge has invalid native function bounds.");
  uint32_t end=((function->end+7u)&~7u)+8u,length=end-hook->target,cell=end-8u;
  if(length>128u||!wsSpan(hook->target,length,blob->codeSize))return wsError("A disaster bridge exceeds its exact bounded allocation.");
  matches=0;
  for(uint32_t c=0;c<blob->importCount;c++)if(blob->imports[c].offset==cell&&!strcmp(blob->imports[c].name,wsDisasterExports[i]))matches++;
  for(uint32_t r=0;r<blob->relocCount;r++)if(blob->relocs[r].offset>=hook->target&&blob->relocs[r].offset<end)return wsError("An unexpected relocation changes a disaster bridge.");
  uintptr_t callback=(uintptr_t)GetProcAddress(self,wsDisasterExports[i]);unsigned char expected[128];
  if(matches!=1u||!callback)return wsError("A disaster bridge lacks its exact runtime callback.");
  memcpy(expected,blob->code+hook->target,length);memcpy(expected+cell-hook->target,&callback,8);
  unsigned char*bridge=installed->allocation+hook->target;
  if(!wsReadable(bridge,length)||memcmp(bridge,expected,length))return wsError("A disaster bridge differs from its complete reviewed instructions and callback.");
  WSPatch*patch=NULL;matches=0;
  for(uint32_t p=0;p<count;p++)if(patches[p].address==(unsigned char*)owner+hook->rva){patch=&patches[p];matches++;}
  if(matches!=1u||patch->length!=hook->length||memcmp(patch->before,hook->before,hook->length)||patch->after[0]!=0xe8)
   return wsError("A disaster call is absent or duplicated in the guarded transaction.");
  int32_t displacement=0;memcpy(&displacement,patch->after+1,4);
  if((uintptr_t)(patch->address+5)+(intptr_t)displacement!=(uintptr_t)bridge)return wsError("A disaster call targets a different native bridge.");
  for(uint32_t p=5;p<patch->length;p++)if(patch->after[p]!=0x90)return wsError("A disaster call has invalid native padding.");
  wsDisasterSites[i]=patch->address;wsDisasterBridges[i]=bridge;wsDisasterSiteLengths[i]=patch->length;wsDisasterBridgeLengths[i]=length;
  memcpy(wsDisasterSiteExpected[i],patch->after,patch->length);memcpy(wsDisasterBridgeExpected[i],expected,length);
 }return 1;
}
static DWORD wsDisasterPatchStatusUnlocked(void){
 if(wsInstallState!=1)return 0;
 for(uint32_t i=0;i<8u;i++){
  uint32_t site=wsDisasterSiteLengths[i],bridge=wsDisasterBridgeLengths[i];
  if(!site||site>WS_MAX_PATCH||!bridge||bridge>128u||!wsDisasterSites[i]||!wsDisasterBridges[i]||
     !wsReadable(wsDisasterSites[i],site)||!wsReadable(wsDisasterBridges[i],bridge)||
     memcmp(wsDisasterSites[i],wsDisasterSiteExpected[i],site)||memcmp(wsDisasterBridges[i],wsDisasterBridgeExpected[i],bridge))return 0;
 }return 8;
}
