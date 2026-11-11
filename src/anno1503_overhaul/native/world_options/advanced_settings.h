#ifndef WS_ADVANCED_SETTINGS_H
#define WS_ADVANCED_SETTINGS_H
#include <stddef.h>
#include <stdio.h>
#define WS_WORLD_OPTIONS_GENERATOR "pending-build"

/* The original 56-byte prefix retains every native bridge field offset. */
_Static_assert(sizeof(WSWorldSettings)==176,"Advanced settings ABI differs");
_Static_assert(sizeof(WSPlanIsland)==44,"Preview island orientation ABI differs");
_Static_assert(offsetof(WSWorldSettings,pirateFrequency)==120,"Existing settings prefix differs");
_Static_assert(offsetof(WSWorldSettings,pirateStrength)==124,"Pirate strength offset differs");
_Static_assert(offsetof(WSWorldSettings,merchantFrequency)==128,"Merchant frequency offset differs");
_Static_assert(offsetof(WSWorldSettings,islandVariety)==132,"Existing activity settings prefix differs");
_Static_assert(offsetof(WSWorldSettings,maxTropical)==156,"Climate quota offsets differ");
_Static_assert(offsetof(WSWorldSettings,disasterMask)==160,"Disaster policy offsets differ");
_Static_assert(offsetof(WSWorldSettings,disasterSeverity)==168,"Disaster severity offset differs");
_Static_assert(offsetof(WSWorldSettings,islandRotation)==172,"Island rotation offset differs");
_Static_assert(sizeof(WSIslandDetails)==44,"Island details ABI differs");
static inline int wsAdvancedValidateSettings(const WSWorldSettings*s,char*error,uint32_t cap){
 const char*reason=NULL;
 if(!s||s->size!=sizeof(*s))reason="Invalid World Settings structure.";
 else if(s->startClimate < -1||s->startClimate>5)reason="Choose a starting climate or Any.";
 else if(s->startIsland < -1||s->startIsland>=128)reason="Choose a valid preferred island on the preview.";
 else if(s->cargoMode<0||s->cargoMode>1)reason="Choose the fleet cargo or custom cargo.";
 else if(s->cargoTools<0||s->cargoWood<0||s->cargoFood<0||s->cargoTools>400||s->cargoWood>400||s->cargoFood>400)reason="Cargo amounts must be whole tons from 0 to 400.";
 else if(s->cargoMode){
  uint32_t holds=s->startingFleet==1?8u:4u;
  uint32_t used=((uint32_t)s->cargoTools+49u)/50u+((uint32_t)s->cargoWood+49u)/50u+((uint32_t)s->cargoFood+49u)/50u;
  if(used>holds)reason="Custom cargo exceeds the trade ship's 50-ton holds. Reduce the cargo amounts.";
 }
 if(!reason&&s->climateBalance<0)reason="Choose a climate balance.";
 if(!reason&&s->climateBalance>3)reason="Choose a supported climate balance.";
 if(!reason&&(s->layoutStyle<0||s->layoutStyle>2))reason="Choose evenly spread, archipelagos or central ocean.";
 if(!reason&&(s->disasters<0||s->disasters>1))reason="Choose whether disasters are enabled.";
 if(!reason&&(s->fairStarts<0||s->fairStarts>1))reason="Choose automatic or balanced starting positions.";
 if(!reason&&(s->startSeparation<0||s->startSeparation>2))reason="Choose close, balanced or distant starting positions.";
 if(!reason&&(s->resourceDistribution<0||s->resourceDistribution>2))reason="Choose normal, spread or specialised resource distribution.";
 if(!reason&&(s->guaranteeBasics<0||s->guaranteeBasics>1))reason="Choose whether basic resources are guaranteed near starts.";
 if(!reason&&(s->mapVisibility<0||s->mapVisibility>2))reason="Choose unexplored, revealed geography or a fully explored map.";
 if(!reason&&(s->enemyVisibility<0||s->enemyVisibility>1))reason="Choose strict line of sight or reveal all activity.";
 if(!reason&&(s->pirateFrequency<0||s->pirateFrequency>2))reason="Choose rare, normal or frequent pirate activity.";
 if(!reason&&(s->pirateStrength<0||s->pirateStrength>2))reason="Choose weak, normal or strong pirate ships.";
 if(!reason&&(s->merchantFrequency<0||s->merchantFrequency>2))reason="Choose rare, normal or frequent neutral merchant visits.";
 if(!reason&&(s->islandVariety<0||s->islandVariety>2))reason="Choose allowed repeats, unique templates or varied island shapes.";
 if(!reason&&(s->minPolar<0||s->maxPolar>128||s->minPolar>s->maxPolar||
              s->minTemperate<0||s->maxTemperate>128||s->minTemperate>s->maxTemperate||
              s->minTropical<0||s->maxTropical>128||s->minTropical>s->maxTropical))
  reason="Each climate range needs a minimum and maximum from 0 to 128, with minimum no greater than maximum.";
 if(!reason&&(s->maxPolar<2||s->maxTemperate<2||s->maxTropical<2))
  reason="Each climate group must allow at least two islands to preserve all six climates and essential resources.";
 if(!reason&&(s->minPolar+s->minTemperate+s->minTropical>s->islandCount||
              s->maxPolar+s->maxTemperate+s->maxTropical<s->islandCount))
  reason="The climate ranges must accommodate the selected total island count.";
 if(!reason&&((s->disasterMask&~31u)||(s->disasterFrequency&~1023u)||(s->disasterSeverity&~1023u)))
  reason="The disaster policy contains an unsupported type or setting.";
 for(uint32_t i=0;!reason&&i<5u;i++)if(((s->disasterFrequency>>(i*2u))&3u)>2u||((s->disasterSeverity>>(i*2u))&3u)>2u)
  reason="Choose rare, normal or frequent disasters and a supported severity.";
 if(!reason&&(s->disasterSeverity&15u)!=5u)reason="Fire and plague use native Normal severity.";
 if(!reason&&(s->islandRotation<0||s->islandRotation>1))reason="Choose original island orientations or random quarter turns.";
 if(!reason&&s->mapVisibility==0&&s->startIsland>=0)reason="Unexplored worlds use an automatic starting island. Clear the preferred island or reveal the geography.";
 if(error&&cap)snprintf(error,cap,"%s",reason?reason:"");
 return reason==NULL;
}
#endif
