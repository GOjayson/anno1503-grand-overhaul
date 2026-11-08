/* A preview is a complete validated plan, not a second random generation.
 * The UI supplies its immutable copy at Start. Any changed cached settings,
 * seed, island or intervening BuildPlan makes that Start fail before a file
 * is created. The native loaded-world certificate remains independently required.
 */
_Static_assert(sizeof(WSWorldSettings)==56,"World-size settings ABI changed");
_Static_assert(sizeof(WSPlanIsland)==40,"Retained island ABI changed");
_Static_assert(sizeof(WSPreviewSnapshot)==5192,"Preview diagnostics ABI changed");
static WSPreviewSnapshot wsPreviewCache={.size=sizeof(WSPreviewSnapshot)};
static volatile LONG wsPreviewSequence;
static void wsPreviewClear(void){
 InterlockedIncrement(&wsPreviewSequence);
 memset(&wsPreviewCache,0,sizeof wsPreviewCache);wsPreviewCache.size=sizeof wsPreviewCache;
 InterlockedIncrement(&wsPreviewSequence);
}
static void wsPreviewRemember(const WSWorldSettings*s,uint32_t seed){
 InterlockedIncrement(&wsPreviewSequence);
 memset(&wsPreviewCache,0,sizeof wsPreviewCache);
 wsPreviewCache.size=sizeof wsPreviewCache;wsPreviewCache.state=1;
 wsPreviewCache.seed=seed;wsPreviewCache.count=planCount;wsPreviewCache.settings=*s;
 memcpy(wsPreviewCache.islands,planned,planCount*sizeof planned[0]);
 InterlockedIncrement(&wsPreviewSequence);
}
static void wsPreviewSetState(uint32_t state){
 InterlockedIncrement(&wsPreviewSequence);wsPreviewCache.state=state;
 InterlockedIncrement(&wsPreviewSequence);
}
__declspec(dllexport) uint32_t WorldSettingsPreviewSnapshotSize(void){return sizeof(WSPreviewSnapshot);}
__declspec(dllexport) uint32_t __stdcall WorldSettingsCopyPreviewSnapshot(void*buffer){
 if(!buffer)return 0;
 WSPreviewSnapshot copy;LONG sequence=InterlockedCompareExchange(&wsPreviewSequence,0,0);
 if(sequence&1)return 0;
 memcpy(&copy,&wsPreviewCache,sizeof copy);MemoryBarrier();
 if(sequence!=InterlockedCompareExchange(&wsPreviewSequence,0,0))return 0;
 memcpy(buffer,&copy,sizeof copy);return sizeof copy;
}
static int wsPreviewMatches(const WSWorldSettings*s,uint32_t seed,const WSPlanIsland*expected,uint32_t count){
 return s&&expected&&wsPreviewCache.state==1&&count>0&&count<=WS_LIMIT&&
  wsPreviewCache.seed==seed&&wsPreviewCache.count==count&&planCount==count&&
  !memcmp(&wsPreviewCache.settings,s,sizeof(*s))&&
  !memcmp(wsPreviewCache.islands,expected,count*sizeof(*expected))&&
  !memcmp(wsPreviewCache.islands,planned,count*sizeof(*expected));
}
