#ifndef WS_ISLAND_QUOTAS_H
#define WS_ISLAND_QUOTAS_H
/* Pure interval validation shared by the menu, generator and native fixtures.
 * Every climate retains one island for the existing essential-resource rules.
 * Historic group intervals remain meaningful when importing older presets. */
static inline const char*wsIslandQuotaSettingsError(const WSWorldSettings*s){
 if(!s||s->islandCount<6||s->islandCount>128)return "Choose between 6 and 128 islands to retain all six climates.";
 const int32_t groupMin[3]={s->minPolar,s->minTemperate,s->minTropical};
 const int32_t groupMax[3]={s->maxPolar,s->maxTemperate,s->maxTropical};
 uint32_t climateLow[6],climateHigh[6],totalLow=0,totalHigh=0;
 for(uint32_t c=0;c<6u;c++){
  if(s->climateMin[c]<0||s->climateMax[c]<1||s->climateMax[c]>128||s->climateMin[c]>s->climateMax[c])
   return "Every climate needs a minimum and maximum from 0 to 128, with maximum at least 1 and minimum no greater than maximum.";
  uint32_t low=0,high=0;
  for(uint32_t z=0;z<3u;z++){
   uint32_t cell=c*3u+z;
   if(s->islandSizeMin[cell]<0||s->islandSizeMax[cell]<0||s->islandSizeMax[cell]>128||s->islandSizeMin[cell]>s->islandSizeMax[cell])
    return "Every island-size range needs whole numbers from 0 to 128, with minimum no greater than maximum.";
   low+=(uint32_t)s->islandSizeMin[cell];high+=(uint32_t)s->islandSizeMax[cell];
  }
  if(low<(uint32_t)s->climateMin[c])low=(uint32_t)s->climateMin[c];
  if(!low)low=1u;
  if(high>(uint32_t)s->climateMax[c])high=(uint32_t)s->climateMax[c];
  if(low>high)return "A climate's small, medium and large ranges do not fit its climate total. Adjust its limits.";
  climateLow[c]=low;climateHigh[c]=high;
 }
 for(uint32_t g=0;g<3u;g++){
  if(groupMin[g]<0||groupMax[g]<2||groupMax[g]>128||groupMin[g]>groupMax[g])
   return "The imported climate-group limits are invalid. Reset the climate limits or load a compatible preset.";
  uint32_t low=climateLow[g*2u]+climateLow[g*2u+1u],high=climateHigh[g*2u]+climateHigh[g*2u+1u];
  if(low<(uint32_t)groupMin[g])low=(uint32_t)groupMin[g];
  if(high>(uint32_t)groupMax[g])high=(uint32_t)groupMax[g];
  if(low>high)return "The separate climate limits conflict with an imported paired-climate limit. Reset the climate limits.";
  totalLow+=low;totalHigh+=high;
 }
 if(totalLow>(uint32_t)s->islandCount||totalHigh<(uint32_t)s->islandCount)
  return "The climate and island-size limits cannot accommodate the selected total island count.";
 return NULL;
}
#endif
