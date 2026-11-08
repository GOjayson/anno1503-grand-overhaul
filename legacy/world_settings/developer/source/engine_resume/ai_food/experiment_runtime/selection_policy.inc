/* Ordinary size modes retain their inspected catalogue meanings. Large strict
 * uses the largest available size per climate/exact native-culture group.
 * Large lenient tries that first, then progressively admits real smaller
 * templates after unsuccessful packing attempts. No island is resampled.
 * Fillers choose the least represented available climate before a template,
 * so climates with many source files no longer dominate the world.
 */
static uint8_t wsSelectionRanks[WS_COUNT];
static uint32_t wsSelectionReady,wsSelectionStage,wsSelectionSmallest;
static uint32_t wsTemplateFaction(const WSTemplate*t){return wsTemplateFactions[t-wsTemplates];}
static int wsSelectionBase(const WSTemplate*t){return (!t->excludedNative||wsTemplateFaction(t))&&(t->fertileLand>0||t->climate==0);}
static void wsSelectionInit(void){
 if(wsSelectionReady)return;
 for(uint32_t i=0;i<WS_COUNT;i++){
  const WSTemplate*t=&wsTemplates[i];uint32_t widths[WS_COUNT],count=0;
  if(!wsSelectionBase(t))continue;
  for(uint32_t j=0;j<WS_COUNT;j++){
   const WSTemplate*q=&wsTemplates[j];
   if(!wsSelectionBase(q)||q->climate!=t->climate||q->cultures!=t->cultures||wsTemplateFaction(q)!=wsTemplateFaction(t)||q->width<=t->width)continue;
   uint32_t k=0;while(k<count&&widths[k]!=q->width)k++;
   if(k==count)widths[count++]=q->width;
  }
  wsSelectionRanks[i]=(uint8_t)(count<4u?count:3u);
 }
 wsSelectionReady=1;
}
static void wsSelectionBeginAttempt(const WSWorldSettings*s,int attempt){
 wsSelectionInit();wsSelectionStage=0;wsSelectionSmallest=0;
 if(s->islandSize==4){
  uint32_t n=attempt<0?0u:(uint32_t)attempt;
  wsSelectionStage=n/8u;if(wsSelectionStage>3u)wsSelectionStage=3u;
  wsSelectionSmallest=n>=31u;
 }
}
static int wsSize(const WSTemplate*t,int size){return size==3||size==4||(size>=0&&size<=2&&(t->sizeChoices&(1u<<size)));}
static int wsEligible(const WSTemplate*t,const WSWorldSettings*s){
 uint32_t f=wsTemplateFaction(t);
 int size=f?(s->islandSize==3||s->islandSize==4||(s->islandSize>=0&&s->islandSize<=2&&(wsTemplateFactionSizes[t-wsTemplates]&(1u<<s->islandSize)))):wsSize(t,s->islandSize);
 if(!wsSelectionBase(t)||(f&~s->factions)||!size||(t->cultures&~s->cultures)||s->spacing<0)return 0;
 uint32_t gap=(uint32_t)s->spacing;
 return gap<=wsWorld/2u&&t->width<=wsWorld-2u*gap&&t->height<=wsWorld-2u*gap;
}
static int wsSelectionMatch(uint32_t index,const WSWorldSettings*s,uint32_t requiredCulture,int climate,int ore,int whale,int empty,int faction){
 const WSTemplate*t=&wsTemplates[index];
 if(!wsEligible(t,s)||wsTemplateFaction(t)!=(uint32_t)faction)return 0;
 if(requiredCulture&&!(t->cultures&requiredCulture))return 0;
 if(climate>=0&&t->climate!=climate)return 0;
 if(ore&&(!t->oreSlots||!(mineralMasks[t->climate]&(uint32_t)ore)))return 0;
 if(whale&&!t->whales)return 0;
 return !(empty&&t->cultures);
}
static int wsChoose(const WSWorldSettings*s,uint32_t requiredCulture,int climate,int ore,int whale,int empty,int faction){
 wsSelectionInit();uint32_t present=0,minimumWidth=0xffffffffu;
 for(uint32_t i=0;i<WS_COUNT;i++)if(wsSelectionMatch(i,s,requiredCulture,climate,ore,whale,empty,faction)){
  present|=1u<<wsSelectionRanks[i];if(wsTemplates[i].width<minimumWidth)minimumWidth=wsTemplates[i].width;
 }
 if(!present)return -1;
 uint32_t selectedRank=4;
 if(s->islandSize==4&&!wsSelectionSmallest){
  static const uint8_t weights[4][4]={{1,0,0,0},{3,1,0,0},{1,2,2,0},{1,2,4,8}};
  uint32_t total=0;for(uint32_t r=0;r<4;r++)if(present&(1u<<r))total+=weights[wsSelectionStage][r];
  if(!total){selectedRank=0;while(!(present&(1u<<selectedRank)))selectedRank++;}
  else{
   uint32_t ticket=wsRandom()%total;
   for(uint32_t r=0;r<4;r++)if(present&(1u<<r)){
    uint32_t weight=weights[wsSelectionStage][r];
    if(ticket<weight){selectedRank=r;break;}ticket-=weight;
   }
  }
 }
 uint32_t choice=0,count=0;
 for(uint32_t i=0;i<WS_COUNT;i++){
  if(!wsSelectionMatch(i,s,requiredCulture,climate,ore,whale,empty,faction))continue;
  if(s->islandSize==4&&(wsSelectionSmallest?wsTemplates[i].width!=minimumWidth:wsSelectionRanks[i]!=selectedRank))continue;
  if(++count==1||wsRandom()%count==0)choice=i;
 }
 return count?(int)choice:-1;
}
static int wsChooseBalancedFill(const WSWorldSettings*s,uint32_t count){
 if(count>=WS_LIMIT)return -1;
 uint32_t climates[6]={0},available[6]={0},minimum=0xffffffffu,choices[6],choiceCount=0;
 for(uint32_t i=0;i<count;i++){if(planned[i].climate>=6)return -1;climates[planned[i].climate]++;}
 for(uint32_t i=0;i<WS_COUNT;i++)if(wsSelectionMatch(i,s,0,-1,0,0,1,0))available[wsTemplates[i].climate]=1;
 for(uint32_t c=0;c<6;c++)if(available[c]){
  if(climates[c]<minimum){minimum=climates[c];choiceCount=0;}
  if(climates[c]==minimum)choices[choiceCount++]=c;
 }
 if(!choiceCount)return -1;
 return wsChoose(s,0,(int)choices[wsRandom()%choiceCount],0,0,1,0);
}
