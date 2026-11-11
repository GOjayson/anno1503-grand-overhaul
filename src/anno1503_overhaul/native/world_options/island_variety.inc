/* Selection-time counters only. Default settings bypass every quota/variety
 * decision and retain the previous catalogue traversal and RNG sequence. */
#include "island_shapes.h"
static uint32_t wsSelectedTemplates[WS_COUNT],wsSelectedShapes[WS_COUNT];
static uint32_t wsSelectedGroups[3],wsSelectedTotal,wsSelectedClimates,wsVarietyRelaxed;
static void wsClimateRange(const WSWorldSettings*s,uint32_t group,uint32_t*minimum,uint32_t*maximum){
 const int32_t lower[3]={s->minPolar,s->minTemperate,s->minTropical};
 const int32_t upper[3]={s->maxPolar,s->maxTemperate,s->maxTropical};
 *minimum=(uint32_t)lower[group];*maximum=(uint32_t)upper[group];
}
static int wsClimateQuotaSettings(const WSWorldSettings*s){
 if(!s||s->islandVariety<0||s->islandVariety>2||s->islandCount<1||s->islandCount>WS_LIMIT)return 0;
 const int32_t lower[3]={s->minPolar,s->minTemperate,s->minTropical};
 const int32_t upper[3]={s->maxPolar,s->maxTemperate,s->maxTropical};
 uint32_t minimum=0,maximum=0;
 for(uint32_t g=0;g<3u;g++){
  if(lower[g]<0||upper[g]<2||upper[g]>WS_LIMIT||lower[g]>upper[g])return 0;
  minimum+=(uint32_t)lower[g];maximum+=(uint32_t)upper[g];
 }
 return minimum<=(uint32_t)s->islandCount&&maximum>=(uint32_t)s->islandCount;
}
static int wsClimateQuotasActive(const WSWorldSettings*s){
 return s->minPolar||s->minTemperate||s->minTropical||
  s->maxPolar!=WS_LIMIT||s->maxTemperate!=WS_LIMIT||s->maxTropical!=WS_LIMIT;
}
static void wsIslandSelectionReset(uint32_t attempt){
 memset(wsSelectedTemplates,0,sizeof wsSelectedTemplates);memset(wsSelectedShapes,0,sizeof wsSelectedShapes);
 memset(wsSelectedGroups,0,sizeof wsSelectedGroups);wsSelectedTotal=wsSelectedClimates=0;
 wsVarietyRelaxed=attempt>=32u;
}
static void wsIslandSelectionAdded(uint32_t index){
 if(index>=WS_COUNT||wsTemplates[index].climate>=6u||wsTemplateShapeIds[index]>=WS_COUNT)return;
 wsSelectedTemplates[index]++;wsSelectedShapes[wsTemplateShapeIds[index]]++;
 wsSelectedGroups[wsTemplates[index].climate/2u]++;wsSelectedTotal++;
 wsSelectedClimates|=1u<<wsTemplates[index].climate;
}
static int wsClimateQuotaCandidate(const WSWorldSettings*s,uint32_t climate){
 if(!wsClimateQuotasActive(s))return 1;
 if(climate>=6u||!wsClimateQuotaSettings(s)||wsSelectedTotal>=(uint32_t)s->islandCount)return 0;
 uint32_t group=climate/2u,minimum,maximum;wsClimateRange(s,group,&minimum,&maximum);
 if(wsSelectedGroups[group]>=maximum)return 0;
 uint32_t missing=0,mask=wsSelectedClimates|(1u<<climate);
 for(uint32_t g=0;g<3u;g++){
  uint32_t count=wsSelectedGroups[g]+(g==group);wsClimateRange(s,g,&minimum,&maximum);
  uint32_t need=count<minimum?minimum-count:0;
  uint32_t absent=!(mask&(1u<<(g*2u)))+!(mask&(1u<<(g*2u+1u)));
  missing+=need>absent?need:absent;
 }
 return missing<=(uint32_t)s->islandCount-wsSelectedTotal-1u;
}
static int wsClimateQuotaFiller(const WSWorldSettings*s,uint32_t climate){
 if(!wsClimateQuotasActive(s))return 1;
 uint32_t minimum,maximum;int deficient=0;
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
 uint32_t groups[3]={0};
 for(uint32_t i=0;i<count;i++){if(rows[i].climate>=6u)return 0;groups[rows[i].climate/2u]++;}
 for(uint32_t g=0;g<3u;g++){uint32_t minimum,maximum;wsClimateRange(s,g,&minimum,&maximum);if(groups[g]<minimum||groups[g]>maximum)return 0;}
 return 1;
}
