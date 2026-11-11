/* Read-only display of bounded preview/catalogue metadata. Fertile land is a
 * template estimate, not proof that a building or mine can be placed. */
static void wsMenuResourceNames(uint32_t mask,const char*const*names,uint32_t count,char*out,uint32_t cap){
 if(!out||!cap)return;out[0]=0;uint32_t used=0;
 for(uint32_t i=0;i<count;i++)if((mask&(1u<<i))&&names[i]){
  int n=snprintf(out+used,cap-used,"%s%s",used?", ":"",names[i]);
  if(n<0||(uint32_t)n>=cap-used){out[cap-1]=0;return;}used+=(uint32_t)n;
 }
 if(!used)snprintf(out,cap,"None");
}
static int wsMenuDescribeIsland(const WSPlanIsland*p,const WSIslandDetails*d,char*out,uint32_t cap){
 static const char*const climates[]={"Polar","Tundra","North","Prairie","Jungle","Steppe"};
 static const char*const crops[]={"Grain","Tobacco","Spices","Flax","Sugar cane","Cotton","Grapes","Cocoa","Hops","Silk","Indigo","Herbs","Potatoes"};
 static const char*const minerals[]={"Iron","Gold","Salt","Gems",NULL,"Marble"};
 static const char*const cultures[]={"Moors","Mongols","Bedouins","Aztecs","Africans","Native Americans","Inuit","Polynesians"};
 if(!p||!d||!out||!cap||d->size!=sizeof(*d)||d->index!=p->id||p->climate>=6||p->rotation>3u)return 0;
 char plantText[256],oreText[128],cultureText[192],nearPlants[256],nearOres[128],owner[64];
 wsMenuResourceNames(p->cropMask&0x1fffu,crops,13,plantText,sizeof plantText);
 wsMenuResourceNames(p->mineralMask|((p->mineralMask&64u)?1u:0u),minerals,6,oreText,sizeof oreText);
 wsMenuResourceNames(p->cultures,cultures,8,cultureText,sizeof cultureText);
 wsMenuResourceNames(d->nearbyCrops&0x1fffu,crops,13,nearPlants,sizeof nearPlants);
 wsMenuResourceNames(d->nearbyMinerals|((d->nearbyMinerals&64u)?1u:0u),minerals,6,nearOres,sizeof nearOres);
 if(d->startOwner==0)snprintf(owner,sizeof owner,"Human player");
 else if(d->startOwner>0&&d->startOwner<=3)snprintf(owner,sizeof owner,"AI opponent %d",d->startOwner);
 else snprintf(owner,sizeof owner,"Not assigned");
 const char*faction=d->faction==1?"Pirates":(d->faction==2?"Venetians":(p->cultures?cultureText:"Uninhabited"));
 int n=snprintf(out,cap,
  "Island %u - %s\r\nDimensions: %u x %u tiles; position: %u, %u\r\nOrientation: %u degrees\r\n"
  "Fertile land tiles (catalogue estimate): %u\r\n"
  "Terrain, coast and buildings can further restrict usable space.\r\n\r\n"
  "Occupants: %s\r\nPlanned crops: %s\r\nPlanned minerals: %s\r\n"
  "Template ore occurrences: %u; whale occurrence: %s\r\n\r\n"
  "Nearby ordinary-island resources (within %u tiles of the island edge):\r\n"
  "Crops: %s\r\nMinerals: %s\r\n\r\n"
  "Starting assignment: %s\r\nPreferred start: %s",
  p->id+1u,climates[p->climate],p->width,p->height,p->x,p->y,p->rotation*90u,d->fertileLand,
  faction,plantText,oreText,d->oreSlots,d->whales?"Yes":"No",d->resourceRadius,
  nearPlants,nearOres,owner,d->startEligible?"Eligible; use the button above to start nearby.":"Unavailable (inhabited island or no safe coastal position).");
 return n>=0&&(uint32_t)n<cap;
}
