/* Include in validated_world.inc after the wsCertRead / wsCertPointer helpers.
 * Call wsStartingShipMatches for owner0 after the existing type/owner/figure
 * getters and water-clearance check; pass one local uint32_t seen=0 per scan.
 * At the end require seen == (1u<<wsExpectedStartShipCount)-1 and humans == count.
 */
static int wsStartingShipMatches(void*ship,void*figure,uint32_t definition,float x,float y,uint32_t*seen,char*error,uint32_t cap){
 uint32_t index=3;
 for(uint32_t i=0;i<wsExpectedStartShipCount;i++)if(x==wsExpectedStartShips[i].x&&y==wsExpectedStartShips[i].y){index=i;break;}
 if(index>=wsExpectedStartShipCount||index>=3||(*seen&(1u<<index))||definition!=wsExpectedStartShips[index].definition){wsMessage(error,cap,"Loaded human starting fleet count, ship type or position differs from the chosen fleet.");return 0;}
 uint32_t holds=definition==1503?8:(definition==1502?4:2);uint16_t perHold=0,maxHealth=0,health=0;unsigned char actualHolds=0,maxGuns=0,guns=0;
 if(!wsCertRead((unsigned char*)figure+0xfa,&perHold,2)||perHold!=50*256||!wsCertRead((unsigned char*)figure+0xfe,&actualHolds,1)||actualHolds!=holds||!wsCertRead((unsigned char*)figure+0x100,&maxGuns,1)||maxGuns!=(definition==1502?0:6)||!wsCertRead((unsigned char*)figure+0xf2,&maxHealth,2)||!maxHealth||!wsCertRead((unsigned char*)ship+0xc0,&health,2)||health!=maxHealth||!wsCertRead((unsigned char*)ship+0xce,&guns,1)||guns!=(wsExpectedStartingFleet==1?6:0)){wsMessage(error,cap,"Loaded starting ship capacity, full health or equipped cannons differ from the verified fleet.");return 0;}
 for(uint32_t i=0;i<holds;i++){
  unsigned char slot[12],good=0;uint16_t quantity=0,want=0;uint32_t expectedGood=0;
  if(!wsCertRead((unsigned char*)ship+0x148+i*24,slot,sizeof slot)){wsMessage(error,cap,"Loaded starting cargo is unreadable.");return 0;}
  good=slot[8];memcpy(&quantity,slot+10,2);
  if(wsExpectedStartingFleet==2){if(i==0){expectedGood=41;want=40;}else if(i==1){expectedGood=42;want=40;}}
  else if(!index&&i<4){static const uint32_t goods[4]={42,26,41,41};expectedGood=goods[i];want=(uint16_t)(i==1?10:(i==3&&wsExpectedStartingDifficulty?30:50));}
  if(good!=expectedGood||quantity!=want*256){wsMessage(error,cap,"Loaded starting cargo differs from the chosen fleet.");return 0;}
 }
 *seen|=1u<<index;return 1;
}
static int wsStartingMoneyCertificate(void*world,char*error,uint32_t cap){
 void*table=wsCertPointer(world,0x210),*human=wsCertPointer(table,8);int32_t money=0;
 if(!wsExpectedStartingMoney||!human||!wsCertRead((unsigned char*)human+0x98,&money,4)||money!=(int32_t)wsExpectedStartingMoney){wsMessage(error,cap,"Loaded human starting money differs from the amount chosen in World Settings.");return 0;}
 return 1;
}
