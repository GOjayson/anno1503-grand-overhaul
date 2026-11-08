#ifndef WS_ADVANCED_SETTINGS_H
#define WS_ADVANCED_SETTINGS_H
#include <stdio.h>
#define WS_WORLD_OPTIONS_GENERATOR "pending-build"

/* The original 56-byte prefix retains every native bridge field offset. */
_Static_assert(sizeof(WSWorldSettings)==96,"Advanced settings ABI differs");
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
 if(error&&cap)snprintf(error,cap,"%s",reason?reason:"");
 return reason==NULL;
}
#endif
