/* Resource geography changes availability only. Native terrain, occurrence
 * quantities and template capacities stay unchanged. The census from the
 * selected fertility levels is retained; optional nearby basics may add
 * assignments, with that priority made explicit in the in-game menu. */
#define WS_RESOURCE_BASIC_CROPS 0x1009u
#define WS_RESOURCE_BASIC_MINERALS 5u
static int wsStartResourceAnchor(const WSWorldSettings*,uint32_t,uint32_t*);
static uint32_t wsResourceCrops[13],wsResourceMinerals[6];
static uint32_t wsResourceFixedCrops[WS_LIMIT],wsResourceFixedMinerals[WS_LIMIT];
static uint32_t wsResourceCensusCount,wsResourceCensusValid;

static uint32_t wsResourceRadius(void){return wsWorld/4u<128u?128u:wsWorld/4u;}
static uint64_t wsResourceDistanceSquared(const WSPlanIsland*a,const WSPlanIsland*b){
 uint32_t dx=a->x+a->width<b->x?b->x-a->x-a->width:(b->x+b->width<a->x?a->x-b->x-b->width:0u);
 uint32_t dy=a->y+a->height<b->y?b->y-a->y-a->height:(b->y+b->height<a->y?a->y-b->y-b->height:0u);
 return (uint64_t)dx*dx+(uint64_t)dy*dy;
}
static uint64_t wsResourceCentreDistance(uint32_t a,uint32_t b){
 int64_t dx=(int64_t)planned[a].x*2+planned[a].width-(int64_t)planned[b].x*2-planned[b].width;
 int64_t dy=(int64_t)planned[a].y*2+planned[a].height-(int64_t)planned[b].y*2-planned[b].height;
 return (uint64_t)(dx*dx+dy*dy);
}
static int wsResourceOrdinary(uint32_t i){
 return i<planCount&&planned[i].templateIndex<WS_COUNT&&!planned[i].cultures&&!wsTemplateFaction(&wsTemplates[planned[i].templateIndex]);
}
static uint32_t wsResourceSupported(uint32_t i,int mineral){
 if(i>=planCount||planned[i].climate>=6)return 0;
 return mineral?(mineralMasks[planned[i].climate]&0x2fu):(wsTemplates[planned[i].templateIndex].fertileLand?(cropMasks[planned[i].climate]&WS_OPTIONAL_CROPS):0u);
}
static void wsResourceNearbyMasks(uint32_t index,const uint32_t*crops,const uint32_t*minerals,uint32_t*outCrops,uint32_t*outMinerals){
 uint32_t c=0,m=0,radius=wsResourceRadius();
 if(index<planCount)for(uint32_t i=0;i<planCount;i++)if(wsResourceOrdinary(i)&&wsResourceDistanceSquared(&planned[index],&planned[i])<=(uint64_t)radius*radius){
  if(wsTemplates[planned[i].templateIndex].fertileLand)c|=(crops?crops[i]:planned[i].cropMask)&cropMasks[planned[i].climate];
  m|=minerals?minerals[i]:planned[i].mineralMask;
 }
 if(outCrops)*outCrops=c&0x1fffu;
 if(outMinerals)*outMinerals=m&0x2fu;
}
static void wsResourceNearby(uint32_t index,uint32_t*crops,uint32_t*minerals){wsResourceNearbyMasks(index,NULL,NULL,crops,minerals);}
static uint32_t wsResourceHash(uint32_t seed,uint32_t a,uint32_t b){return wsPlantHash(seed^0x52455335u^(a*0x9e3779b9u)^(b*0x85ebca6bu));}
static void wsResourceCensus(uint32_t crops[13],uint32_t minerals[6]){
 memset(crops,0,13u*sizeof(*crops));memset(minerals,0,6u*sizeof(*minerals));
 for(uint32_t i=0;i<planCount;i++){
  for(uint32_t b=0;b<13;b++)crops[b]+=(planned[i].cropMask>>b)&1u;
  for(uint32_t b=0;b<6;b++)minerals[b]+=(planned[i].mineralMask>>b)&1u;
 }
}
/* Spread increases each resource's pairwise geographical separation.
 * Specialised assigns each resource a stable seeded regional anchor and
 * reduces distance to it. Moves/swaps preserve every resource's census. */
static void wsResourceOptimise(uint32_t masks[WS_LIMIT],int mineral,int mode,uint32_t seed){
 uint32_t bits=mineral?0x2fu:WS_OPTIONAL_CROPS,anchors[13];
 for(uint32_t b=0;b<13;b++){
  anchors[b]=WS_LIMIT;uint32_t rank=0;
  if(!(bits&(1u<<b)))continue;
  for(uint32_t i=0;i<planCount;i++)if(wsResourceOrdinary(i)&&(wsResourceSupported(i,mineral)&(1u<<b))&&(!mineral||wsTemplates[planned[i].templateIndex].oreSlots)){
   uint32_t value=wsResourceHash(seed^0x414e4348u,i,b);
   if(anchors[b]==WS_LIMIT||value>rank){anchors[b]=i;rank=value;}
  }
 }
 for(uint32_t pass=0;pass<planCount*4u;pass++){
  int64_t scores[13][WS_LIMIT];memset(scores,0,sizeof scores);
  for(uint32_t b=0;b<13;b++)if(bits&(1u<<b))for(uint32_t i=0;i<planCount;i++)if(wsResourceOrdinary(i)){
   if(mode==2){if(anchors[b]<planCount)scores[b][i]=-(int64_t)wsResourceCentreDistance(i,anchors[b]);}
   else for(uint32_t k=0;k<planCount;k++)if(wsResourceOrdinary(k)&&(masks[k]&(1u<<b)))scores[b][i]+=(int64_t)wsResourceCentreDistance(i,k);
  }
  int64_t best=0;uint32_t source=WS_LIMIT,destination=0,move=0,swap=0,tie=0;
  for(uint32_t b=0;b<13;b++)if(bits&(1u<<b))for(uint32_t i=0;i<planCount;i++)if(wsResourceOrdinary(i)&&(masks[i]&(1u<<b)))
   for(uint32_t j=0;j<planCount;j++)if(wsResourceOrdinary(j)&&!(masks[j]&(1u<<b))&&(wsResourceSupported(j,mineral)&(1u<<b))){
    int64_t gain=scores[b][j]-scores[b][i];
    if(mode==1)gain-=(int64_t)wsResourceCentreDistance(i,j);
    uint32_t alternatives=0;
    if(mineral&&(uint32_t)wsPop(masks[j])>=wsTemplates[planned[j].templateIndex].oreSlots)alternatives=masks[j]&bits&wsResourceSupported(i,mineral)&~masks[i];
    else alternatives=0x80000000u;
    while(alternatives){
     uint32_t chosen=alternatives&(~alternatives+1u);alternatives&=~chosen;
     int64_t actual=gain;uint32_t old=0;
     if(chosen!=0x80000000u){
      uint32_t c=0;while((1u<<c)!=chosen)c++;
      actual+=scores[c][i]-scores[c][j];
      if(mode==1)actual-=(int64_t)wsResourceCentreDistance(i,j);
      old=chosen;
     }
     uint32_t rank=wsResourceHash(seed^old,i*WS_LIMIT+j,b);
     if(actual>best||(actual>0&&actual==best&&rank>tie)){best=actual;source=i;destination=j;move=1u<<b;swap=old;tie=rank;}
    }
   }
  if(source==WS_LIMIT)break;
  masks[source]=(masks[source]&~move)|swap;masks[destination]=(masks[destination]&~swap)|move;
 }
}
static int wsApplyResourceDistribution(const WSWorldSettings*s,uint32_t seed,char*error,uint32_t cap){
 uint32_t crops[WS_LIMIT],minerals[WS_LIMIT],beforeCrops[13],beforeMinerals[6],afterCrops[13],afterMinerals[6];
 wsResourceCensusValid=0;
 if(!s||s->resourceDistribution<0||s->resourceDistribution>2||!planCount||planCount>WS_LIMIT){wsMessage(error,cap,"Invalid resource distribution or island plan.");return 0;}
 wsResourceCensus(beforeCrops,beforeMinerals);
 for(uint32_t i=0;i<planCount;i++){
  const WSPlanIsland*p=&planned[i];
  if(p->templateIndex>=WS_COUNT||p->climate>=6||p->climate!=wsTemplates[p->templateIndex].climate||(p->cropMask&~cropMasks[p->climate])||(p->mineralMask&~(mineralMasks[p->climate]&0x2fu))||(uint32_t)wsPop(p->mineralMask)>wsTemplates[p->templateIndex].oreSlots){wsMessage(error,cap,"A resource assignment exceeds its verified island climate or deposit capacity.");return 0;}
  crops[i]=p->cropMask;minerals[i]=p->mineralMask;wsResourceFixedCrops[i]=p->cropMask;wsResourceFixedMinerals[i]=p->mineralMask;
 }
 if(s->resourceDistribution){wsResourceOptimise(crops,0,s->resourceDistribution,seed);wsResourceOptimise(minerals,1,s->resourceDistribution,seed^0x4d494e45u);}
 for(uint32_t i=0;i<planCount;i++){planned[i].cropMask=crops[i];planned[i].mineralMask=minerals[i];}
 wsResourceCensus(afterCrops,afterMinerals);
 if(memcmp(beforeCrops,afterCrops,sizeof beforeCrops)||memcmp(beforeMinerals,afterMinerals,sizeof beforeMinerals)){
  for(uint32_t i=0;i<planCount;i++){planned[i].cropMask=wsResourceFixedCrops[i];planned[i].mineralMask=wsResourceFixedMinerals[i];}
  wsMessage(error,cap,"Resource distribution could not preserve the selected fertility census.");return 0;
 }
 memcpy(wsResourceCrops,beforeCrops,sizeof beforeCrops);memcpy(wsResourceMinerals,beforeMinerals,sizeof beforeMinerals);
 wsResourceCensusCount=planCount;wsResourceCensusValid=1;return 1;
}
static int wsResourceRequirementsMet(const WSWorldSettings*s,uint32_t through,const uint32_t*crops,const uint32_t*minerals){
 for(uint32_t owner=0;owner<=through;owner++){
  uint32_t anchor,c,m;
  if(owner>(uint32_t)s->aiCount||!wsStartResourceAnchor(s,owner,&anchor))return 0;
  wsResourceNearbyMasks(anchor,crops,minerals,&c,&m);
  if((c&WS_RESOURCE_BASIC_CROPS)!=WS_RESOURCE_BASIC_CROPS||(m&WS_RESOURCE_BASIC_MINERALS)!=WS_RESOURCE_BASIC_MINERALS)return 0;
 }
 return 1;
}
static int wsResourcePriorMineralsMet(const WSWorldSettings*s,uint32_t owner,const uint32_t*minerals){
 for(uint32_t previous=0;previous<owner;previous++){
  uint32_t anchor,c,m;if(!wsStartResourceAnchor(s,previous,&anchor))return 0;
  wsResourceNearbyMasks(anchor,NULL,minerals,&c,&m);
  if((m&WS_RESOURCE_BASIC_MINERALS)!=WS_RESOURCE_BASIC_MINERALS)return 0;
 }
 return 1;
}
static int wsResourceEnsureMineral(const WSWorldSettings*s,uint32_t owner,uint32_t anchor,uint32_t bit,uint32_t minerals[WS_LIMIT]){
 uint32_t radius=wsResourceRadius(),best=WS_LIMIT,beforeCrops,beforeMinerals;uint64_t nearest=UINT64_MAX;
 wsResourceNearbyMasks(anchor,NULL,minerals,&beforeCrops,&beforeMinerals);
 uint32_t retainedBasics=beforeMinerals&WS_RESOURCE_BASIC_MINERALS;
 /* Free native occurrence slots are the least disruptive option. */
 for(uint32_t i=0;i<planCount;i++)if(wsResourceOrdinary(i)&&(wsResourceSupported(i,1)&bit)&&!(minerals[i]&bit)&&(uint32_t)wsPop(minerals[i])<wsTemplates[planned[i].templateIndex].oreSlots){
  uint64_t distance=wsResourceDistanceSquared(&planned[anchor],&planned[i]);
  if(distance<=(uint64_t)radius*radius&&(best==WS_LIMIT||distance<nearest)){best=i;nearest=distance;}
 }
 if(best<planCount){minerals[best]|=bit;return 1;}
 /* If every nearby slot is full, move its old assignment to a free compatible
  * slot elsewhere, or swap with an existing deposit of the requested type.
  * Previous participants' guarantees must remain satisfied. */
 for(uint32_t i=0;i<planCount;i++)if(wsResourceOrdinary(i)&&(wsResourceSupported(i,1)&bit)&&!(minerals[i]&bit)&&wsResourceDistanceSquared(&planned[anchor],&planned[i])<=(uint64_t)radius*radius)
  for(uint32_t b=0;b<6;b++)if(minerals[i]&(1u<<b))for(uint32_t j=0;j<planCount;j++)if(j!=i&&wsResourceOrdinary(j)&&(wsResourceSupported(j,1)&(1u<<b))&&!(minerals[j]&(1u<<b))){
   uint32_t oldI=minerals[i],oldJ=minerals[j];
   if((uint32_t)wsPop(oldJ)<wsTemplates[planned[j].templateIndex].oreSlots)minerals[j]|=1u<<b;
   else if(oldJ&bit)minerals[j]=(oldJ&~bit)|(1u<<b);
   else continue;
   minerals[i]=(oldI&~(1u<<b))|bit;
   uint32_t afterCrops,afterMinerals;wsResourceNearbyMasks(anchor,NULL,minerals,&afterCrops,&afterMinerals);
   if((afterMinerals&retainedBasics)==retainedBasics&&wsResourcePriorMineralsMet(s,owner,minerals))return 1;
   minerals[i]=oldI;minerals[j]=oldJ;
  }
 return 0;
}
static int wsGuaranteeStartResources(const WSWorldSettings*s,uint32_t seed,char*error,uint32_t cap){
 (void)seed;
 if(!s||!s->guaranteeBasics)return s!=NULL;
 uint32_t crops[WS_LIMIT],minerals[WS_LIMIT];
 for(uint32_t i=0;i<planCount;i++){crops[i]=planned[i].cropMask;minerals[i]=planned[i].mineralMask;}
 for(uint32_t owner=0;owner<=(uint32_t)s->aiCount;owner++){
  uint32_t anchor,nearCrops,nearMinerals,radius=wsResourceRadius();
  if(!wsStartResourceAnchor(s,owner,&anchor)){wsMessage(error,cap,"Nearby basics need a safe ordinary starting island for every selected player. Choose fair starts, another preferred island or regenerate.");return 0;}
  wsResourceNearbyMasks(anchor,crops,minerals,&nearCrops,&nearMinerals);
  for(uint32_t b=0;b<13;b++)if((WS_RESOURCE_BASIC_CROPS&(1u<<b))&&!(nearCrops&(1u<<b))){
   uint32_t best=WS_LIMIT;uint64_t nearest=UINT64_MAX;
   for(uint32_t i=0;i<planCount;i++)if(wsResourceOrdinary(i)&&wsTemplates[planned[i].templateIndex].fertileLand&&(cropMasks[planned[i].climate]&(1u<<b))){
    uint64_t distance=wsResourceDistanceSquared(&planned[anchor],&planned[i]);
    if(distance<=(uint64_t)radius*radius&&(best==WS_LIMIT||distance<nearest)){best=i;nearest=distance;}
   }
   if(best==WS_LIMIT){wsMessage(error,cap,"A starting region cannot provide grain, flax and potatoes within the nearby-resource radius. Change starts, climate balance or regenerate.");return 0;}
   crops[best]|=1u<<b;
  }
  for(uint32_t b=0;b<3;b++)if(WS_RESOURCE_BASIC_MINERALS&(1u<<b)){
   wsResourceNearbyMasks(anchor,crops,minerals,&nearCrops,&nearMinerals);
   if(!(nearMinerals&(1u<<b))&&!wsResourceEnsureMineral(s,owner,anchor,1u<<b,minerals)){
    wsMessage(error,cap,"A starting region has no compatible free iron or salt deposit within the nearby-resource radius. Add islands, change starts or regenerate; native deposit limits were preserved.");return 0;
   }
  }
 }
 if(!wsResourceRequirementsMet(s,(uint32_t)s->aiCount,crops,minerals)){wsMessage(error,cap,"The nearby basic-resource guarantee could not be certified for every selected player.");return 0;}
 for(uint32_t i=0;i<planCount;i++){planned[i].cropMask=crops[i];planned[i].mineralMask=minerals[i];}
 wsResourceCensus(wsResourceCrops,wsResourceMinerals);return 1;
}
static int wsValidateStartResources(const WSWorldSettings*s,char*error,uint32_t cap){
 uint32_t crops[13],minerals[6];
 if(!s||!wsResourceCensusValid||wsResourceCensusCount!=planCount){wsMessage(error,cap,"The resource-distribution certificate is missing or stale.");return 0;}
 wsResourceCensus(crops,minerals);
 if(memcmp(crops,wsResourceCrops,sizeof crops)||memcmp(minerals,wsResourceMinerals,sizeof minerals)){wsMessage(error,cap,"The resource distribution changed after the preview was certified.");return 0;}
 for(uint32_t i=0;i<planCount;i++)if(!wsResourceOrdinary(i)&&(planned[i].cropMask!=wsResourceFixedCrops[i]||planned[i].mineralMask!=wsResourceFixedMinerals[i])){wsMessage(error,cap,"Resource distribution changed a native or special-faction island.");return 0;}
 if(s->guaranteeBasics&&!wsResourceRequirementsMet(s,(uint32_t)s->aiCount,NULL,NULL)){wsMessage(error,cap,"The cached map lacks nearby grain, flax, potatoes, iron or salt for a selected player.");return 0;}
 return 1;
}
