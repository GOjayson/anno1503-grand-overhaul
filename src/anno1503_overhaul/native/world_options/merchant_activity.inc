/* Native Venetian merchant traffic policy. Included after the shared strict
 * faction identity helpers. Only the shared binder commits these staged rows.
 * Actual visits remain subject to native routes, travel, ports and demand. */
static int wsFactionActivityMerchantTarget(void*world,void*approved,uint32_t factions,
 int32_t mode,WSFactionActivityTarget*out,char*error,uint32_t cap){
 WSFactionActivityTarget target={0};
 if(!out||(factions&~3u)||mode<0||mode>2)
  return wsAIError(error,cap,"Neutral merchant traffic selection is outside the supported range.");
 if(!wsFactionActivityFind(world,approved,16u,!!(factions&2u),&target,error,cap))return 0;
 if(target.controller){
  if(target.before&UINT32_C(0xffffff00))
   return wsAIError(error,cap,"Neutral merchant policy storage already contains unsupported flags. No policy was changed.");
  target.after=UINT32_C(0x57550000)|((uint32_t)mode<<8)|(target.before&255u);
 }
 *out=target;return 1;
}
