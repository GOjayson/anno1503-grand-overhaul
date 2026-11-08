/* Fair starts alter only verified scene ship coordinates.  Ordinary CPU scene
 * records are owner IDs 1..4; the selected native transport profile uses the
 * first count entries.  The native post-profile controller certificate also
 * checks those exact active IDs before accepting a generated world.
 *
 * fertileLand is the catalogue's conservative fertile-height tile count.  It
 * is an estimate of growing land, not proof of building/farming accessibility.
 */
static int32_t wsAssignedStartIsland[4]={-1,-1,-1,-1};
static uint32_t wsAssignedStartCount,wsFairOwnerMask,wsFairCacheValid;
static WSWorldSettings wsFairCachedSettings;
static uint64_t wsFairCachedGeometry;
static float wsFairCachedXY[4][2];
static uint32_t wsFairCachedIslands[4];
static uint32_t wsFairQualityCache[WS_LIMIT],wsFairQualityCached;

static uint64_t wsFairGeometry(void){
 uint64_t hash=UINT64_C(1469598103934665603);
 for(uint32_t i=0;i<planCount;i++){
  const WSPlanIsland*p=&planned[i];
  const uint32_t fields[]={p->id,p->x,p->y,p->width,p->height,p->templateIndex,p->cultures,p->climate};
  for(uint32_t j=0;j<8u;j++){hash^=fields[j];hash*=UINT64_C(1099511628211);}
 }
 return hash^planCount;
}
static uint32_t wsFairRadius(void){return wsWorld/4u<128u?128u:wsWorld/4u;}
static uint64_t wsFairIslandDistance(const WSPlanIsland*a,const WSPlanIsland*b){
 uint32_t dx=a->x+a->width<b->x?b->x-a->x-a->width:(b->x+b->width<a->x?a->x-b->x-b->width:0u);
 uint32_t dy=a->y+a->height<b->y?b->y-a->y-a->height:(b->y+b->height<a->y?a->y-b->y-b->height:0u);
 return (uint64_t)dx*dx+(uint64_t)dy*dy;
}
static uint32_t wsFairQuality(uint32_t index){
 if(index>=planCount)return 0;
 if(wsFairQualityCached)return wsFairQualityCache[index];
 uint32_t crops=0,minerals=0,radius=wsFairRadius();
 for(uint32_t i=0;i<planCount;i++)if(wsStartingIslandOrdinary(i)&&
     wsFairIslandDistance(&planned[index],&planned[i])<=(uint64_t)radius*radius){
  if(wsTemplates[planned[i].templateIndex].fertileLand)crops|=planned[i].cropMask&0x1fffu;
  uint32_t ore=planned[i].mineralMask;
  minerals|=(ore&0x40u)?((ore&~0x40u)|1u):ore;
 }
 return (uint32_t)wsPop(crops)+2u*(uint32_t)wsPop(minerals&0x2fu);
}
static uint32_t wsFairMinimumDistance(const WSWorldSettings*s){
 uint32_t minimum=s->startSeparation==0?wsWorld/12u:(s->startSeparation==1?wsWorld/4u:wsWorld/2u);
 uint32_t floor=s->startSeparation==0?64u:(s->startSeparation==1?96u:128u);
 return minimum<floor?floor:minimum;
}
static uint32_t wsFairMaximumDistance(const WSWorldSettings*s){
 return s->startSeparation==0?wsWorld/2u:(s->startSeparation==1?wsWorld:wsWorld*2u);
}
static uint64_t wsFairPointDistance(float ax,float ay,float bx,float by){
 int64_t dx=(int64_t)(ax-bx),dy=(int64_t)(ay-by);
 return (uint64_t)(dx*dx+dy*dy);
}
static uint32_t wsFairRoot(uint64_t value){
 uint64_t result=0,bit=UINT64_C(1)<<62;
 while(bit>value)bit>>=2;
 while(bit){
  if(value>=result+bit){value-=result+bit;result=(result>>1)+bit;}
  else result>>=1;
  bit>>=2;
 }
 return (uint32_t)result;
}
static int wsFairPairFits(const WSWorldSettings*s,uint32_t a,float ax,float ay,uint32_t b,float bx,float by){
 if(a==b)return 0;
 uint32_t landA=wsTemplates[planned[a].templateIndex].fertileLand;
 uint32_t landB=wsTemplates[planned[b].templateIndex].fertileLand;
 uint32_t qualityA=wsFairQuality(a),qualityB=wsFairQuality(b);
 if(!landA||!landB||(uint64_t)landA>2u*(uint64_t)landB||(uint64_t)landB>2u*(uint64_t)landA||
    !qualityA||!qualityB||qualityA>2u*qualityB||qualityB>2u*qualityA)return 0;
 uint64_t distance=wsFairPointDistance(ax,ay,bx,by);
 uint32_t minimum=wsFairMinimumDistance(s),maximum=wsFairMaximumDistance(s);
 if(distance<(uint64_t)minimum*minimum||distance>(uint64_t)maximum*maximum)return 0;
 WSPlanIsland reserveA={0,(uint32_t)ax-24u,(uint32_t)ay-24u,49u,49u,0,0,0,0,0};
 WSPlanIsland reserveB={0,(uint32_t)bx-24u,(uint32_t)by-24u,49u,49u,0,0,0,0,0};
 return wsSeparated(&reserveA,&reserveB,0);
}
typedef struct WSFairCandidate{uint32_t island,land,quality;float x,y;} WSFairCandidate;
static WSFairCandidate wsFairCandidates[WS_LIMIT];
static uint32_t wsFairCandidateCount,wsFairSelected[4],wsFairSearchBudget;

static uint64_t wsFairCandidateRank(const WSWorldSettings*s,uint32_t owner,uint32_t index){
 const WSFairCandidate*c=&wsFairCandidates[index],*human=&wsFairCandidates[wsFairSelected[0]];
 uint64_t landDelta=c->land>human->land?c->land-human->land:human->land-c->land;
 uint64_t rank=landDelta*UINT64_C(1048576)/(human->land?human->land:1u);
 uint32_t delta=c->quality>human->quality?c->quality-human->quality:human->quality-c->quality;
 rank+=(uint64_t)delta*16384u;
 uint32_t target=s->startSeparation==0?wsWorld/3u:(s->startSeparation==1?wsWorld/2u:wsWorld*3u/4u);
 for(uint32_t p=0;p<owner;p++){
  const WSFairCandidate*other=&wsFairCandidates[wsFairSelected[p]];
  uint32_t distance=wsFairRoot(wsFairPointDistance(c->x,c->y,other->x,other->y));
  rank+=(uint64_t)(distance>target?distance-target:target-distance)*32u;
 }
 return rank*128u+c->island;
}
static int wsFairSearch(const WSWorldSettings*s,uint32_t owner,uint32_t count){
 if(owner==count)return 1;
 if(!wsFairSearchBudget)return 0;
 wsFairSearchBudget--;
 uint32_t choices[16],choiceCount=0;uint64_t ranks[16];
 for(uint32_t i=0;i<wsFairCandidateCount;i++){
  const WSFairCandidate*c=&wsFairCandidates[i];int fits=1;
  for(uint32_t p=0;p<owner;p++){
   const WSFairCandidate*other=&wsFairCandidates[wsFairSelected[p]];
   if(!wsFairPairFits(s,c->island,c->x,c->y,other->island,other->x,other->y)){fits=0;break;}
  }
  if(!fits)continue;
  uint64_t rank=wsFairCandidateRank(s,owner,i);uint32_t at=0;
  while(at<choiceCount&&ranks[at]<=rank)at++;
  if(at>=16u)continue;
  if(choiceCount<16u)choiceCount++;
  for(uint32_t j=choiceCount-1u;j>at;j--){choices[j]=choices[j-1u];ranks[j]=ranks[j-1u];}
  choices[at]=i;ranks[at]=rank;
 }
 for(uint32_t i=0;i<choiceCount;i++){
  wsFairSelected[owner]=choices[i];
  if(wsFairSearch(s,owner+1u,count))return 1;
 }
 return 0;
}
static int wsFairCommit(const WSWorldSettings*s,char*error,uint32_t cap){
 wsFairQualityCached=0;
 uint32_t count=(uint32_t)s->aiCount+1u;
 float original[4][2]={{0}};
 if(count>4u||wsBaseShipReserveCount+count>WS_MAX_START_SHIPS){wsMessage(error,cap,"Fair starting fleet reservations are unavailable.");return 0;}
 for(uint32_t owner=0;owner<count;owner++){
  int found=0;
  for(uint32_t i=0;i<wsExpectedSceneShipCount;i++)if(wsExpectedSceneShips[i].owner==owner){original[owner][0]=wsExpectedSceneShips[i].x;original[owner][1]=wsExpectedSceneShips[i].y;found=1;break;}
  if(!found){wsMessage(error,cap,"A selected ordinary player has no verified stock starting ship.");return 0;}
  uint32_t island=wsFairCachedIslands[owner];float x=wsFairCachedXY[owner][0],y=wsFairCachedXY[owner][1];
  if(!wsStartingIslandOrdinary(island)||!wsPreferredWaterFits((int)x,(int)y)){
   wsMessage(error,cap,"A fair starting island no longer has safe coastal water. Regenerate the preview.");return 0;
  }
  if(!owner&&((s->startIsland>=0&&island!=(uint32_t)s->startIsland)||(s->startClimate>=0&&planned[island].climate!=(uint32_t)s->startClimate))){
   wsMessage(error,cap,"Fair starts conflict with the preferred human island or climate.");return 0;
  }
  for(uint32_t previous=0;previous<owner;previous++)if(!wsFairPairFits(s,island,x,y,wsFairCachedIslands[previous],wsFairCachedXY[previous][0],wsFairCachedXY[previous][1])){
   wsMessage(error,cap,"The selected starts cannot satisfy the fertile-land, resource-access and distance balance. Regenerate or change separation.");return 0;
  }
 }
 /* All owners, destinations and pairwise constraints pass before mutation. */
 wsActiveShipReserveCount=wsBaseShipReserveCount;wsAssignedStartCount=count;wsStartOverrideMask=0;
 for(uint32_t owner=0;owner<count;owner++){
  float oldX=original[owner][0],oldY=original[owner][1];
  float x=wsFairCachedXY[owner][0],y=wsFairCachedXY[owner][1];
  for(uint32_t i=0;i<wsExpectedSceneShipCount;i++)if(wsExpectedSceneShips[i].owner==owner){wsExpectedSceneShips[i].x+=x-oldX;wsExpectedSceneShips[i].y+=y-oldY;}
  wsStartOverrideXY[owner][0]=x;wsStartOverrideXY[owner][1]=y;wsStartOverrideMask|=1u<<owner;
  wsAssignedStartIsland[owner]=(int32_t)wsFairCachedIslands[owner];
  wsActiveShipReserves[wsActiveShipReserveCount++]=(WSPlanIsland){0,(uint32_t)x-24u,(uint32_t)y-24u,49u,49u,0,0,0,0,0};
 }
 for(uint32_t owner=count;owner<4u;owner++)wsAssignedStartIsland[owner]=-1;
 wsFairOwnerMask=((1u<<count)-1u)&~1u;
 wsPreferredIsland=wsAssignedStartIsland[0];wsExpectedDisasters=s->disasters;
 return 1;
}
static int wsApplyFairStarts(const WSWorldSettings*s,char*error,uint32_t cap){
 wsFairQualityCached=0;
 uint64_t geometry=wsFairGeometry();
 if(wsPreviewCache.state==1u&&wsFairCacheValid&&geometry==wsFairCachedGeometry&&!memcmp(s,&wsFairCachedSettings,sizeof *s))return wsFairCommit(s,error,cap);
 wsFairCacheValid=wsFairOwnerMask=wsAssignedStartCount=0;wsFairCandidateCount=0;
 for(uint32_t i=0;i<4u;i++)wsAssignedStartIsland[i]=-1;
 for(uint32_t i=0;i<planCount;i++)wsFairQualityCache[i]=wsFairQuality(i);
 wsFairQualityCached=1;
 for(uint32_t i=0;i<planCount;i++){
  if(!wsStartingIslandOrdinary(i)||!planned[i].climate||!wsTemplates[planned[i].templateIndex].fertileLand)continue;
  float x,y;if(!wsPreferredWater(i,&x,&y))continue;
  WSFairCandidate*c=&wsFairCandidates[wsFairCandidateCount++];
  *c=(WSFairCandidate){i,wsTemplates[planned[i].templateIndex].fertileLand,wsFairQuality(i),x,y};
 }
 uint32_t count=(uint32_t)s->aiCount+1u;
 if(count>4u||wsFairCandidateCount<count){wsFairQualityCached=0;wsMessage(error,cap,"Fair starts need one safe uninhabited growing island per player. Add islands, reduce opponents or regenerate.");return 0;}
 uint32_t humans[WS_LIMIT],humanCount=0;
 for(uint32_t i=0;i<wsFairCandidateCount;i++){
  const WSFairCandidate*c=&wsFairCandidates[i];
  if((s->startIsland>=0&&c->island!=(uint32_t)s->startIsland)||(s->startClimate>=0&&planned[c->island].climate!=(uint32_t)s->startClimate))continue;
  uint32_t at=humanCount;
  while(at&&wsFairCandidates[humans[at-1u]].land<c->land){humans[at]=humans[at-1u];at--;}
  humans[at]=i;humanCount++;
 }
 wsFairSearchBudget=65536u;
 for(uint32_t h=0;h<humanCount;h++){
  wsFairSelected[0]=humans[h];
  if(!wsFairSearch(s,1u,count))continue;
  for(uint32_t owner=0;owner<count;owner++){
   const WSFairCandidate*c=&wsFairCandidates[wsFairSelected[owner]];
   wsFairCachedIslands[owner]=c->island;wsFairCachedXY[owner][0]=c->x;wsFairCachedXY[owner][1]=c->y;
  }
  wsFairCachedSettings=*s;wsFairCachedGeometry=geometry;wsFairCacheValid=1;
  return wsFairCommit(s,error,cap);
 }
 wsFairQualityCached=0;
 wsMessage(error,cap,"No fair starts fit this preview and preferred island/climate. Try another seed, more islands, another separation or disable fair starts.");return 0;
}
static int wsStartResourceAnchor(const WSWorldSettings*s,uint32_t participant,uint32_t*island){
 if(!s||!island||participant>(uint32_t)s->aiCount||participant>=4u)return 0;
 if(s->fairStarts){
  if(participant>=wsAssignedStartCount||wsAssignedStartIsland[participant]<0)return 0;
  *island=(uint32_t)wsAssignedStartIsland[participant];return wsStartingIslandOrdinary(*island);
 }
 float x,y;wsWorldShipPosition(participant,&x,&y);uint32_t best=WS_LIMIT;uint64_t distance=UINT64_MAX;
 if(!participant&&wsPreferredIsland>=0){*island=(uint32_t)wsPreferredIsland;return wsStartingIslandOrdinary(*island);}
 for(uint32_t i=0;i<planCount;i++)if(wsStartingIslandOrdinary(i)&&planned[i].climate&&wsTemplates[planned[i].templateIndex].fertileLand){
  const WSPlanIsland*p=&planned[i];
  int64_t dx=x<p->x?(int64_t)p->x-(int64_t)x:(x>p->x+p->width?(int64_t)x-p->x-p->width:0);
  int64_t dy=y<p->y?(int64_t)p->y-(int64_t)y:(y>p->y+p->height?(int64_t)y-p->y-p->height:0);
  uint64_t d=(uint64_t)(dx*dx+dy*dy);
  if(d<distance){best=i;distance=d;}
 }
 if(best==WS_LIMIT||distance>(uint64_t)wsFairRadius()*wsFairRadius())return 0;
 *island=best;return 1;
}
static int wsValidateFairStarts(const WSWorldSettings*s,char*error,uint32_t cap){
 if(!s->fairStarts)return 1;
 if(!wsFairCacheValid||wsAssignedStartCount!=(uint32_t)s->aiCount+1u||wsFairCachedGeometry!=wsFairGeometry()||memcmp(s,&wsFairCachedSettings,sizeof *s)){
  wsMessage(error,cap,"Fair starting assignments do not match this world preview.");return 0;
 }
 if(wsStartOverrideMask!=(1u<<wsAssignedStartCount)-1u||wsFairOwnerMask!=(wsStartOverrideMask&~1u)){
  wsMessage(error,cap,"The selected player fleet overrides do not match the fair starts.");return 0;
 }
 for(uint32_t owner=0;owner<wsAssignedStartCount;owner++){
  uint32_t island=(uint32_t)wsAssignedStartIsland[owner];
  if(island!=wsFairCachedIslands[owner]||wsStartOverrideXY[owner][0]!=wsFairCachedXY[owner][0]||wsStartOverrideXY[owner][1]!=wsFairCachedXY[owner][1]||
     !wsStartingIslandOrdinary(island)||!wsTemplates[planned[island].templateIndex].fertileLand||
     !wsPreferredWaterFits((int)wsFairCachedXY[owner][0],(int)wsFairCachedXY[owner][1])){
   wsMessage(error,cap,"A fair start has invalid fertile land or blocked coastal water.");return 0;
  }
  for(uint32_t other=0;other<owner;other++)if(!wsFairPairFits(s,island,wsFairCachedXY[owner][0],wsFairCachedXY[owner][1],(uint32_t)wsAssignedStartIsland[other],wsFairCachedXY[other][0],wsFairCachedXY[other][1])){
   wsMessage(error,cap,"Fair starts fail the final fertile-land, resource-access or distance check.");return 0;
  }
 }
 return 1;
}
__declspec(dllexport) uint32_t WorldSettingsExpectedFairOwners(void){return wsFairOwnerMask;}
__declspec(dllexport) int WorldSettingsStartOwner(uint32_t index){
 if(wsPreviewCache.state!=1u)return -1;
 for(uint32_t owner=0;owner<wsAssignedStartCount;owner++)if(wsAssignedStartIsland[owner]==(int32_t)index)return (int)owner;
 return -1;
}
__declspec(dllexport) int WorldSettingsDescribeStarts(char*out,uint32_t cap){
 if(!out||!cap)return 0;
 if(wsPreviewCache.state!=1u){wsMessage(out,cap,"Generate a valid preview to inspect starting conditions.");return 0;}
 if(!wsFairOwnerMask&&wsAssignedStartCount<=1u&&!wsFairCacheValid){wsMessage(out,cap,"Original starting positions. Enable Fair starts to balance island access.");return 1;}
 if(!wsFairCacheValid){wsMessage(out,cap,"Original starting positions; highlighted islands are the nearest ordinary growing islands.");return 1;}
 uint32_t minLand=UINT32_MAX,maxLand=0,minQuality=UINT32_MAX,maxQuality=0,minDistance=UINT32_MAX;
 for(uint32_t owner=0;owner<wsAssignedStartCount;owner++){
  uint32_t island=(uint32_t)wsAssignedStartIsland[owner],land=wsTemplates[planned[island].templateIndex].fertileLand,quality=wsFairQuality(island);
  if(land<minLand)minLand=land;
  if(land>maxLand)maxLand=land;
  if(quality<minQuality)minQuality=quality;
  if(quality>maxQuality)maxQuality=quality;
  for(uint32_t other=0;other<owner;other++){
   uint32_t distance=wsFairRoot(wsFairPointDistance(wsFairCachedXY[owner][0],wsFairCachedXY[owner][1],wsFairCachedXY[other][0],wsFairCachedXY[other][1]));
   if(distance<minDistance)minDistance=distance;
  }
 }
 if(wsAssignedStartCount==1u)snprintf(out,cap,"Fair start: island %u; estimated fertile area %u tiles; nearby resource score %u (radius %u tiles).",(uint32_t)wsAssignedStartIsland[0]+1u,maxLand,maxQuality,wsFairRadius());
 else snprintf(out,cap,"%u fair starts: fertile area %u-%u tiles; resource access %u-%u; nearest fleets %u tiles apart. Both balance ratios pass 2:1; resource radius %u tiles.",wsAssignedStartCount,minLand,maxLand,minQuality,maxQuality,minDistance,wsFairRadius());
 return 1;
}
