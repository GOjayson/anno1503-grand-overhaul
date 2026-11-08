/* Plant availability, independent of terrain fertility and production speed.
 * Native Scene c250 always enables grain/flax/potatoes/grass/trees/fish.
 * Only climate-supported optional harvest crops are varied here. Required
 * world coverage overrides an island quota when a small world needs it. */
#define WS_OPTIONAL_CROPS 0x00000ff6u
static uint32_t wsPlantHash(uint32_t value){
 value^=value>>16;value*=0x7feb352du;value^=value>>15;
 value*=0x846ca68bu;return value^(value>>16);
}
static uint32_t wsPlantRank(uint32_t seed,uint32_t index,uint32_t crop){
 return wsPlantHash(seed^0x504c414eu^(index*0x9e3779b9u)^((crop+1u)*0x85ebca6bu));
}
static int wsApplyPlantFertility(const WSWorldSettings*s,uint32_t seed,char*error,uint32_t cap){
 uint32_t masks[WS_LIMIT],unionMask=0;
 if(!s||s->plantFertility<0||s->plantFertility>3||!planCount||planCount>WS_LIMIT){
  wsMessage(error,cap,"Invalid plant availability settings or island plan.");return 0;
 }
 for(uint32_t i=0;i<planCount;i++){
  if(planned[i].climate>=6){wsMessage(error,cap,"Plant availability has an unsupported island climate.");return 0;}
  masks[i]=cropMasks[planned[i].climate]&~WS_OPTIONAL_CROPS;unionMask|=masks[i];
 }
 /* Establish the SAME essential anchors for every density level first.
  * Quota filling below then guarantees Low is a subset of Medium of Very. */
 for(uint32_t crop=0;crop<13;crop++)if(!(unionMask&(1u<<crop))){
  uint32_t best=WS_LIMIT,bestRank=0;int bestCount=32;
  for(uint32_t i=0;i<planCount;i++)if(cropMasks[planned[i].climate]&(1u<<crop)){
   int count=wsPop(masks[i]&WS_OPTIONAL_CROPS);uint32_t rank=wsPlantRank(seed^0x52455052u,i,crop);
   if(best==WS_LIMIT||count<bestCount||(count==bestCount&&rank>bestRank)){
    best=i;bestCount=count;bestRank=rank;
   }
  }
  if(best==WS_LIMIT){wsMessage(error,cap,"No climate-compatible island can grow an essential crop.");return 0;}
  masks[best]|=1u<<crop;unionMask|=1u<<crop;
 }
 for(uint32_t i=0;i<planCount;i++){
  uint32_t optional=cropMasks[planned[i].climate]&WS_OPTIONAL_CROPS;
  uint32_t remaining=optional&~masks[i];int count=wsPop(optional),mode=s->plantFertility;
  if(mode==3)mode=(int)(wsPlantHash(seed^0x4d495845u^(i*0x9e3779b9u))%3u);
  int quota=mode==0?count:(mode==1?(count+1)/2:(count?1:0));
  for(int n=wsPop(masks[i]&WS_OPTIONAL_CROPS);n<quota;n++){
   uint32_t bestBit=0,bestRank=0;
   for(uint32_t crop=0;crop<13;crop++)if(remaining&(1u<<crop)){
    uint32_t rank=wsPlantRank(seed,i,crop);
    if(!bestBit||rank>bestRank){bestBit=1u<<crop;bestRank=rank;}
   }
   if(!bestBit){wsMessage(error,cap,"Plant availability could not satisfy its island quota.");return 0;}
   masks[i]|=bestBit;remaining&=~bestBit;unionMask|=bestBit;
  }
 }
 if(unionMask!=0x1ffffu){wsMessage(error,cap,"Plant availability cannot preserve all essential crop and fishing types.");return 0;}
 for(uint32_t i=0;i<planCount;i++)planned[i].cropMask=masks[i];
 return 1;
}
