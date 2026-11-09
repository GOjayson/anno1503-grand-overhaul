/* Include after the native scene/field helpers and world_size.inc. */
#include "start_visibility_policy.h"
static uint32_t wsExpectedVisibilityCode;
/* Consumed only by the fresh-world certificate, never by draw/reload hooks. */
static uint32_t wsFreshVisibilityCode;
static int wsVisibilityScene(WSBuffer*b,const WSWorldSettings*s,char*error,uint32_t cap){
 uint32_t selected=s?wsVisibilityEncode(s->mapVisibility,s->enemyVisibility):0,heads=0,headAt=0;
 wsExpectedVisibilityCode=0;
 wsFreshVisibilityCode=0;
 if(!selected||!b||!b->data||b->size<32)goto invalid;
 for(uint32_t at=32;at<b->size;){
  if(b->size-at<16)goto invalid;
  uint32_t n=wsU32(b->data+at+12);if(n>b->size-at-16)goto invalid;
  if(wsTag(b->data+at,"HEAD")){
   if(++heads!=1||n!=32||(wsU16(b->data+at+32)&WS_VISIBILITY_POLICY_MASK))goto invalid;
   headAt=at+32;
  }at+=16+n;
 }
 if(heads!=1)goto invalid;
 wsPut16(b->data+headAt,(uint16_t)(wsU16(b->data+headAt)|selected));
 wsExpectedVisibilityCode=wsFreshVisibilityCode=selected;return 1;
 invalid:wsMessage(error,cap,"The verified scene cannot preserve the selected map visibility.");return 0;
}
