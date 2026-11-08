/* Welt dba44/dba6c constructs tSpielerTabServer(fdbc0), dbaf5 stores it
 * at world+210. d1a30 and 95990 independently read that table and its slots.
 * Property9 and1c query actual loaded player type and VOLK enum. */
static int wsCertSpecialPlayers(void*world,char*error,uint32_t cap){
 unsigned char*w=(unsigned char*)WS_CERT_MODULE("AnnoWelt.dll");
 void*table=wsCertPointer(world,0x210),*vt=wsCertPointer(table,0);uint32_t counts[2]={0};
 if(!w||vt!=w+0xfdbc0||!wsCertMemory(table,0x110,0)){wsMessage(error,cap,"Loaded special players have no verified native player table.");return 0;}
 for(uint32_t id=0;id<32;id++){
  void*player=wsCertPointer(table,8+id*8);if(!player)continue;uint32_t type=0,culture=0;uintptr_t actualId=0;
  if(!wsCertProperty(player,9,&type)||!wsCertProperty(player,0x1c,&culture)||!wsCertCall(player,0x88,0,0,0,&actualId)||actualId!=id){wsMessage(error,cap,"Loaded special player identity cannot be verified.");return 0;}
  if(type==15){if(culture!=11){wsMessage(error,cap,"Loaded pirates have an unexpected native culture.");return 0;}counts[0]++;}
  if(type==16){if(culture!=12){wsMessage(error,cap,"Loaded Venetians have an unexpected native culture.");return 0;}counts[1]++;}
 }
 if(counts[0]!=((planFactions&1u)!=0)||counts[1]!=((planFactions&2u)!=0)){wsMessage(error,cap,"Loaded pirates or Venetians differ from the selected settings.");return 0;}
 return 1;
}
