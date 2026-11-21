/* Selection counters and hard quotas. Unrestricted limits bypass quota choices
 * and preserve the preceding catalogue traversal and RNG sequence. */
#include "island_shapes.h"
static uint32_t wsSelectedTemplates[WS_COUNT],wsSelectedShapes[WS_COUNT];
static uint32_t wsSelectedGroups[3],wsSelectedByClimate[6],wsSelectedSizes[18];
static uint32_t wsQuotaAvailable[18],wsSelectedTotal,wsSelectedClimates,wsVarietyRelaxed;
static int wsQuotaFillCell=-1;
static int wsEligible(const WSTemplate*,const WSWorldSettings*);
static uint32_t wsIslandSizeClass(uint32_t width,uint32_t height){
 uint32_t extent=width>height?width:height;return extent<128u?0u:(extent==128u?1u:2u);
}
static uint32_t wsIslandQuotaCell(const WSTemplate*t){return t->climate*3u+wsIslandSizeClass(t->width,t->height);}
static void wsClimateRange(const WSWorldSettings*s,uint32_t group,uint32_t*minimum,uint32_t*maximum){
 const int32_t lower[3]={s->minPolar,s->minTemperate,s->minTropical};
 const int32_t upper[3]={s->maxPolar,s->maxTemperate,s->maxTropical};
 *minimum=(uint32_t)lower[group];*maximum=(uint32_t)upper[group];
}
static int wsClimateQuotaSettings(const WSWorldSettings*s){
 return s&&s->islandVariety>=0&&s->islandVariety<=2&&!wsIslandQuotaSettingsError(s);
}
static int wsClimateQuotasActive(const WSWorldSettings*s){
 if(s->minPolar||s->minTemperate||s->minTropical||s->maxPolar!=WS_LIMIT||s->maxTemperate!=WS_LIMIT||s->maxTropical!=WS_LIMIT)return 1;
 for(uint32_t c=0;c<6u;c++)if(s->climateMin[c]||s->climateMax[c]!=WS_LIMIT)return 1;
 for(uint32_t cell=0;cell<18u;cell++)if(s->islandSizeMin[cell]||s->islandSizeMax[cell]!=WS_LIMIT)return 1;
 return 0;
}
/* Sizes, climates, historic pairs and the world form nested intervals.
 * Intersecting every level reserves all still-required slots at each choice. */
static int wsIslandQuotaTotalsFit(const WSWorldSettings*s,const uint32_t*cells,const uint32_t*available){
 uint32_t lower[6],upper[6],totalLow=0,totalHigh=0;
 for(uint32_t c=0;c<6u;c++){
  uint32_t lo=0,hi=0;
  for(uint32_t z=0;z<3u;z++){
   uint32_t cell=c*3u+z,count=cells?cells[cell]:0u;
   uint32_t minimum=(uint32_t)s->islandSizeMin[cell],maximum=(uint32_t)s->islandSizeMax[cell];
   if(available&&!available[cell])maximum=count;
   if(count>maximum)return 0;lo+=count>minimum?count:minimum;hi+=maximum;
  }
  if(lo<(uint32_t)s->climateMin[c])lo=(uint32_t)s->climateMin[c];if(!lo)lo=1u;
  if(hi>(uint32_t)s->climateMax[c])hi=(uint32_t)s->climateMax[c];if(lo>hi)return 0;
  lower[c]=lo;upper[c]=hi;
 }
 for(uint32_t g=0;g<3u;g++){
  uint32_t minimum,maximum;wsClimateRange(s,g,&minimum,&maximum);
  uint32_t lo=lower[g*2u]+lower[g*2u+1u],hi=upper[g*2u]+upper[g*2u+1u];
  if(lo<minimum)lo=minimum;if(hi>maximum)hi=maximum;if(lo>hi)return 0;
  totalLow+=lo;totalHigh+=hi;
 }
 return totalLow<=(uint32_t)s->islandCount&&totalHigh>=(uint32_t)s->islandCount;
}
static void wsIslandQuotaAvailability(const WSWorldSettings*s,uint32_t*out){
 memset(out,0,18u*sizeof(*out));
 for(uint32_t i=0;i<WS_COUNT;i++)if(wsTemplates[i].climate<6u&&wsEligible(&wsTemplates[i],s))out[wsIslandQuotaCell(&wsTemplates[i])]=1;
}
static int wsIslandQuotaCatalogue(const WSWorldSettings*s,char*error,uint32_t cap){
 if(!wsClimateQuotaSettings(s))return 0;if(!wsClimateQuotasActive(s))return 1;
 uint32_t available[18];wsIslandQuotaAvailability(s,available);
 for(uint32_t cell=0;cell<18u;cell++)if(s->islandSizeMin[cell]&&!available[cell]){
  static const char*climates[]={"Polar","Tundra","Northern","Prairie","Jungle","Steppe"};
  static const char*sizes[]={"small","medium","large"};
  if(error&&cap)snprintf(error,cap,"No eligible %s %s island exists for these options. Use Mixed island size, change cultures or factions, or reduce that minimum.",climates[cell/3u],sizes[cell%3u]);
  return 0;
 }
 if(!wsIslandQuotaTotalsFit(s,NULL,available)){
  if(error&&cap)snprintf(error,cap,"The available island sizes cannot satisfy these climate limits. Choose Mixed island size or adjust the limits, cultures, factions, world size or spacing.");
  return 0;
 }
 return 1;
}
static void wsIslandSelectionReset(const WSWorldSettings*s,uint32_t attempt){
 memset(wsSelectedTemplates,0,sizeof wsSelectedTemplates);memset(wsSelectedShapes,0,sizeof wsSelectedShapes);
 memset(wsSelectedGroups,0,sizeof wsSelectedGroups);memset(wsSelectedByClimate,0,sizeof wsSelectedByClimate);memset(wsSelectedSizes,0,sizeof wsSelectedSizes);
 wsSelectedTotal=wsSelectedClimates=0;wsQuotaFillCell=-1;wsVarietyRelaxed=attempt>=32u;
 if(wsClimateQuotasActive(s))wsIslandQuotaAvailability(s,wsQuotaAvailable);
}
static void wsIslandSelectionAdded(uint32_t index){
 if(index>=WS_COUNT||wsTemplates[index].climate>=6u||wsTemplateShapeIds[index]>=WS_COUNT)return;
 wsSelectedTemplates[index]++;wsSelectedShapes[wsTemplateShapeIds[index]]++;
 wsSelectedGroups[wsTemplates[index].climate/2u]++;wsSelectedByClimate[wsTemplates[index].climate]++;
 wsSelectedSizes[wsIslandQuotaCell(&wsTemplates[index])]++;wsSelectedTotal++;
 wsSelectedClimates|=1u<<wsTemplates[index].climate;
}
static int wsClimateQuotaCandidate(const WSWorldSettings*s,uint32_t index){
 if(!wsClimateQuotasActive(s))return 1;
 if(index>=WS_COUNT||wsTemplates[index].climate>=6u||!wsClimateQuotaSettings(s)||wsSelectedTotal>=(uint32_t)s->islandCount)return 0;
 uint32_t cell=wsIslandQuotaCell(&wsTemplates[index]);
 if(wsQuotaFillCell>=0&&cell!=(uint32_t)wsQuotaFillCell)return 0;
 uint32_t counts[18];memcpy(counts,wsSelectedSizes,sizeof counts);counts[cell]++;
 return wsIslandQuotaTotalsFit(s,counts,wsQuotaAvailable);
}
static int wsClimateQuotaFiller(const WSWorldSettings*s,uint32_t climate){
 if(!wsClimateQuotasActive(s))return 1;
 int deficient=0;
 for(uint32_t c=0;c<6u;c++)deficient|=wsSelectedByClimate[c]<(uint32_t)s->climateMin[c];
 if(deficient)return wsSelectedByClimate[climate]<(uint32_t)s->climateMin[climate];
 uint32_t minimum,maximum;deficient=0;
 for(uint32_t g=0;g<3u;g++){wsClimateRange(s,g,&minimum,&maximum);deficient|=wsSelectedGroups[g]<minimum;}
 wsClimateRange(s,climate/2u,&minimum,&maximum);
 return !deficient||wsSelectedGroups[climate/2u]<minimum;
}
static uint32_t wsIslandVarietyScore(const WSWorldSettings*s,uint32_t index){
 uint32_t count=wsSelectedTemplates[index];
 return s->islandVariety==2?wsSelectedShapes[wsTemplateShapeIds[index]]*(WS_LIMIT+1u)+count:count;
}
static int wsClimateQuotaCertificate(const WSWorldSettings*s,const WSPlanIsland*rows,uint32_t count){
 if(!wsClimateQuotaSettings(s)||count!=(uint32_t)s->islandCount||!rows)return 0;
 uint32_t cells[18]={0};
 for(uint32_t i=0;i<count;i++){
  if(rows[i].climate>=6u||rows[i].templateIndex>=WS_COUNT||rows[i].climate!=wsTemplates[rows[i].templateIndex].climate)return 0;
  if(wsIslandSizeClass(rows[i].width,rows[i].height)!=wsIslandSizeClass(wsTemplates[rows[i].templateIndex].width,wsTemplates[rows[i].templateIndex].height))return 0;
  cells[rows[i].climate*3u+wsIslandSizeClass(rows[i].width,rows[i].height)]++;
 }
 return wsIslandQuotaTotalsFit(s,cells,NULL);
}
