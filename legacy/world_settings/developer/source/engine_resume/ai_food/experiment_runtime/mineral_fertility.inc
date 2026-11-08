/* Per-island mineral availability. Only native distinct-goods assignments are
 * changed; quantity/reserve semantics and all terrain/template bytes remain
 * owned by the original History Edition loader. Mandatory world-wide deposits
 * were assigned before packing and are never removed by this pass. */
static uint32_t wsMineralFertilityHash(uint32_t seed,uint32_t island,uint32_t value){
 uint32_t x=seed^0x4d494e35u^(island*0x9e3779b9u)^(value*0x85ebca6bu);
 x^=x>>16;x*=0x7feb352du;x^=x>>15;x*=0x846ca68bu;x^=x>>16;return x;
}
static int wsApplyMineralFertility(const WSWorldSettings*s,uint32_t seed,char*error,uint32_t cap){
 const uint32_t goods[5]={1u,2u,4u,8u,32u};
 if(!s||s->mineralFertility<0||s->mineralFertility>3||!planCount||planCount>WS_LIMIT){wsMessage(error,cap,"Invalid mineral fertility setting or island plan.");return 0;}
 uint32_t output[WS_LIMIT];
 for(uint32_t i=0;i<planCount;i++){
  const WSPlanIsland*p=&planned[i];
  if(p->templateIndex>=WS_COUNT||p->climate>=6){wsMessage(error,cap,"Invalid island mineral profile.");return 0;}
  const WSTemplate*t=&wsTemplates[p->templateIndex];
  /* Native indices0 and6 both represent iron; this policy uses only index0
   * (the verified shallow-iron definition1661), never duplicate iron types. */
  uint32_t supported=mineralMasks[p->climate]&0x2fu,assigned=p->mineralMask;
  if(t->climate!=p->climate||(assigned&~supported)||(uint32_t)wsPop(assigned)>t->oreSlots){wsMessage(error,cap,"Mandatory minerals exceed this island's native capacity.");return 0;}
  int mode=s->mineralFertility;
  if(mode==3)mode=(int)(wsMineralFertilityHash(seed,p->id,0x100u)%3u);
  uint32_t order[5]={0,1,2,3,4};
  /* Sort the optional goods independently of world-generation RNG. All modes
   * use the same order, so Low is a subset of Medium, itself a subset of Very. */
  for(uint32_t a=1;a<5;a++){
   uint32_t key=order[a],j=a,rank=wsMineralFertilityHash(seed,p->id,goods[key]);
   while(j&&wsMineralFertilityHash(seed,p->id,goods[order[j-1]])>rank){order[j]=order[j-1];j--;}
   order[j]=key;
  }
  uint32_t most=assigned;
  for(uint32_t a=0;a<5&&(uint32_t)wsPop(most)<t->oreSlots;a++){
   uint32_t bit=goods[order[a]];
   if(supported&bit)most|=bit;
  }
  if(mode!=2){
   for(uint32_t a=0;a<5;a++){
    uint32_t bit=goods[order[a]];
    /* Filter only the capacity-limited Very set: skipping an earlier good in
     * Medium must not admit a later good which would be absent in Very. */
    if(!(most&bit)||(assigned&bit))continue;
    if(mode==0||(wsMineralFertilityHash(seed,p->id,bit)&1u)==0)assigned|=bit;
   }
  }
  output[i]=assigned;
 }
 /* Publish only after all islands passed capacity and climate validation. */
 for(uint32_t i=0;i<planCount;i++)planned[i].mineralMask=output[i];
 return 1;
}
