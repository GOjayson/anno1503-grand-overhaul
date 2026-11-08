/* Read-only information from the exact ready preview and its reviewed native
 * template catalogue. Fertile land is a height/fertility proxy; cliffs, roads,
 * building footprints and access are not certified by this estimate. */
__declspec(dllexport) int WorldSettingsIslandDetails(uint32_t index,WSIslandDetails*out){
 if(!out||out->size!=sizeof(*out)||wsPreviewCache.state!=1u||index>=planCount)return 0;
 const WSPlanIsland*p=&planned[index];
 if(p->templateIndex>=WS_COUNT)return 0;
 const WSTemplate*t=&wsTemplates[p->templateIndex];
 WSIslandDetails value={0};
 value.size=sizeof value;value.index=index;value.fertileLand=t->fertileLand;
 value.oreSlots=t->oreSlots;value.whales=t->whales;value.faction=wsTemplateFaction(t);
 value.startEligible=(uint32_t)WorldSettingsStartingIslandEligible(index);
 value.startOwner=WorldSettingsStartOwner(index);
 wsResourceNearby(index,&value.nearbyCrops,&value.nearbyMinerals);
 value.resourceRadius=wsResourceRadius();
 *out=value;return 1;
}
