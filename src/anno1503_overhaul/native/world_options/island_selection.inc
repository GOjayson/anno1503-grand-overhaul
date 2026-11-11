/* Shared production selection prelude. The caller retries bounded attempts;
 * quota-dependent misses do not incorrectly become permanent catalogue errors.
 * Return 1 for a complete selection, 0 for a retry, -1 for a missing candidate. */
#include <stdio.h>
static void wsSelectionFailure(const WSWorldSettings*s,char*out,uint32_t cap,const char*ordinary){
 if(out&&cap)snprintf(out,cap,"%s",wsClimateQuotasActive(s)?
  "No valid world was found for these climate ranges, island sizes, cultures, factions and essential resources. Regenerate, increase a maximum or the total island count, or change those options.":ordinary);
}
static int wsSelectIslands(const WSWorldSettings*s,uint32_t*out,const char*const*cultureLabels,
 const char*const*climateLabels,char*message,uint32_t cap){
 uint32_t n=0,seen=0,climates=0;
 for(int c=0;c<8;c++)if((s->cultures&(1u<<c))&&!(seen&(1u<<c))){
  int pick=wsChoose(s,1u<<c,-1,0,0,0,0);
  if(pick<0){
   if(message&&cap)snprintf(message,cap,"No island in this size contains %s. Choose mixed or another size.",cultureLabels?cultureLabels[c]:"the selected culture");
   if(wsClimateQuotasActive(s))wsSelectionFailure(s,message,cap,"");return -1;
  }
  if(!wsAdd((uint32_t)pick,&n))return 0;seen|=wsTemplates[pick].cultures;
 }
 if(s->factions&1u){int pick=wsChoose(s,0,-1,0,0,0,1);
  if(pick<0||!wsAdd((uint32_t)pick,&n)){wsSelectionFailure(s,message,cap,"No pirate island matches this size.");return -1;}}
 if(s->factions&2u){int pick=wsChoose(s,0,-1,0,0,0,2);
  if(pick<0||!wsAdd((uint32_t)pick,&n)){wsSelectionFailure(s,message,cap,"No verified Venetian island fits this world size and spacing.");return -1;}}
 for(uint32_t i=0;i<n;i++)climates|=1u<<planned[i].climate;
 for(int c=0;c<6;c++)if(!(climates&(1u<<c))){int pick=wsChoose(s,0,c,0,0,1,0);
  if(pick<0){
   if(message&&cap)snprintf(message,cap,"This island size has no uninhabited %s template. Choose mixed or another size.",climateLabels?climateLabels[c]:"required climate");
   if(wsClimateQuotasActive(s))wsSelectionFailure(s,message,cap,"");return -1;
  }
  if(!wsAdd((uint32_t)pick,&n))return 0;
 }
 const uint32_t need[]={0x20,8,4,2,1};
 for(uint32_t r=0;r<sizeof(need)/sizeof(need[0]);r++){
  int placed=0;
  for(uint32_t i=0;i<n;i++){
   WSPlanIsland*p=&planned[i];const WSTemplate*t=&wsTemplates[p->templateIndex];
   if((mineralMasks[p->climate]&need[r])&&wsPop(p->mineralMask)<t->oreSlots){p->mineralMask|=need[r];placed=1;break;}
  }
  if(!placed){int pick=wsChoose(s,0,-1,(int)need[r],0,1,0);
   if(pick<0){wsSelectionFailure(s,message,cap,"No eligible ore occurrence matches the requested size and cultures.");return -1;}
   if(!wsAdd((uint32_t)pick,&n))return 0;planned[n-1].mineralMask=need[r];
  }
 }
 uint32_t whales=0;for(uint32_t i=0;i<n;i++)whales+=wsTemplates[planned[i].templateIndex].whales;
 if(!whales){int pick=wsChoose(s,0,-1,0,1,1,0);
  if(pick<0){wsSelectionFailure(s,message,cap,"No whale occurrence matches these settings.");return -1;}
  if(!wsAdd((uint32_t)pick,&n))return 0;
 }
 if(n>(uint32_t)s->islandCount){
  if(message&&cap)snprintf(message,cap,"At least %u islands are required for these cultures and essential resources.",n);return 0;
 }
 while(n<(uint32_t)s->islandCount){int pick=wsChooseBalancedFill(s,n);
  if(pick<0||!wsAdd((uint32_t)pick,&n)){
   wsSelectionFailure(s,message,cap,"Island size, count, spacing and layout do not fit the selected world. Reduce them or choose another layout.");return 0;
  }
 }
 *out=n;return 1;
}
