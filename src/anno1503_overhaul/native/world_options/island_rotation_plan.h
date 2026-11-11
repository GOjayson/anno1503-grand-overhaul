/* Save-safe uninhabited island whitelist; 13 nonzero-edge templates retain orientation.
 * Native settlements and special factions never rotate. */
#ifndef WS_ISLAND_ROTATION_PLAN_H
#define WS_ISLAND_ROTATION_PLAN_H
static const uint8_t wsTemplateCanRotate[444]={
 1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,1,1,1,
 1,1,1,0,1,0,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,
 1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,
 0,0,1,1,1,1,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,
 1,0,1,0,1,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,
 0,0,0,0,1,1,1,1,0,1,1,1,1,1,0,0,0,0,0,1,1,1,1,1,
 1,1,1,1,1,1,1,1,1,1,1,1,0,1,0,1,0,1,0,1,0,1,0,1,
 0,1,0,1,0,1,0,1,0,1,1,0,1,0,1,0,1,0,1,1,0,0,0,1,
 0,1,0,1,1,1,1,0,0,1,0,1,0,1,0,1,0,0,0,1,0,1,0,1,
 0,1,0,0,0,1,1,1,1,1,0,0,0,0,0,0,0,0,0,1,1,1,1,0,
 0,0,0,0,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,1,1,1,1,
 1,0,0,0,0,0,1,1,0,0,1,1,1,1,1,1,1,1,1,1,1,0,0,0,
 0,0,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,1,1,1,
 1,1,0,0,0,0,1,0,0,0,1,0,1,0,1,0,0,1,0,1,0,1,0,1,
 0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,1,1,0,1,1,0,1,
 0,1,1,0,1,0,1,0,1,0,0,0,0,0,0,0,0,1,0,0,0,1,0,1,
 0,1,1,0,1,1,0,1,0,1,0,0,1,0,0,0,1,0,0,1,0,1,0,1,
 0,0,1,0,1,0,0,0,1,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,
 1,1,1,0,0,0,1,1,1,1,0,0,
};
_Static_assert(sizeof wsTemplateCanRotate/sizeof wsTemplateCanRotate[0]==WS_COUNT,"Island rotation metadata count differs");
static int wsRotationMessage(char*error,uint32_t cap,const char*message){
 if(error&&cap){uint32_t n=0;while(n+1u<cap&&message[n]){error[n]=message[n];n++;}error[n]=0;}return 0;
}
static uint32_t wsRotationMix(uint32_t value){
 value^=value>>16;value*=0x7feb352du;value^=value>>15;value*=0x846ca68bu;return value^(value>>16);
}
static int wsIslandRotationEligible(uint32_t index){
 return index<WS_COUNT&&wsTemplateCanRotate[index]&&!wsTemplates[index].cultures&&
  !wsTemplates[index].excludedNative&&wsTemplates[index].width==wsTemplates[index].height;
}
/* Runs after packing/resources. This independent hash never advances the layout RNG. */
static int wsAssignIslandRotations(const WSWorldSettings*s,uint32_t seed,WSPlanIsland*rows,uint32_t count,char*error,uint32_t cap){
 if(!s||!rows||!count||count>WS_LIMIT||s->islandRotation<0||s->islandRotation>1)
  return wsRotationMessage(error,cap,"Island rotation settings differ.");
 for(uint32_t i=0;i<count;i++){
  WSPlanIsland*p=&rows[i];if(p->id!=i||p->templateIndex>=WS_COUNT)
   return wsRotationMessage(error,cap,"Island rotation plan identity differs.");
  const WSTemplate*t=&wsTemplates[p->templateIndex];
  if(p->width!=t->width||p->height!=t->height)
   return wsRotationMessage(error,cap,"Island rotation geometry differs.");
 }
 for(uint32_t i=0;i<count;i++)rows[i].rotation=s->islandRotation&&wsIslandRotationEligible(rows[i].templateIndex)?
  wsRotationMix(seed^wsRotationMix(rows[i].templateIndex+0x9e3779b9u)^wsRotationMix(rows[i].id+0x85ebca6bu))&3u:0u;
 return 1;
}
static int wsIslandRotationsValid(const WSWorldSettings*s,const WSPlanIsland*rows,uint32_t count){
 if(!s||!rows||!count||count>WS_LIMIT||s->islandRotation<0||s->islandRotation>1)return 0;
 for(uint32_t i=0;i<count;i++)if(rows[i].rotation>3u||
  ((!s->islandRotation||!wsIslandRotationEligible(rows[i].templateIndex))&&rows[i].rotation))return 0;
 return 1;
}
/* HEIGHT coordinates are vertices, not cell centres. Missing original end edges are zero. */
static inline int wsRotationCoastSource(uint32_t rotation,uint32_t width,uint32_t height,uint32_t x,uint32_t y,uint32_t*sx,uint32_t*sy){
 if(!sx||!sy||rotation>3u||x>=width||y>=height||width!=height)return 0;
 if(rotation==1u){*sx=y;*sy=height-x;}
 else if(rotation==2u){*sx=width-x;*sy=height-y;}
 else if(rotation==3u){*sx=width-y;*sy=x;}
 else{*sx=x;*sy=y;}
 return *sx<width&&*sy<height;
}
#endif
