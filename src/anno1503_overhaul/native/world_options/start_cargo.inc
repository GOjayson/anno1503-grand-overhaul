/* Native trade ship capacities:1502 has four holds,1503 has eight; the
 * loaded figure certificate independently requires 50 tons in each hold.
 * Goods retain their original History Edition IDs and eight-byte scene slots.
 */
static uint16_t wsExpectedCargoGoods[3][8],wsExpectedCargoTons[3][8];
static int wsStartingCargoSelection(const WSWorldSettings*s){
 if(!wsAdvancedValidateSettings(s,NULL,0))return 0;
 memset(wsExpectedCargoGoods,0,sizeof wsExpectedCargoGoods);
 memset(wsExpectedCargoTons,0,sizeof wsExpectedCargoTons);
 for(uint32_t ship=0;ship<wsExpectedStartShipCount;ship++){
  uint32_t definition=wsExpectedStartShips[ship].definition;
  if(s->cargoMode&&definition!=1504u){
   const uint16_t goods[3]={41,42,26}; /* WERKZEUG, HOLZ, NAHRUNG. */
   uint32_t amounts[3]={(uint32_t)s->cargoTools,(uint32_t)s->cargoWood,(uint32_t)s->cargoFood};
   uint32_t slot=0,holds=definition==1503u?8u:4u;
   for(uint32_t g=0;g<3;g++)while(amounts[g]){
    if(slot>=holds)return 0;
    uint32_t tons=amounts[g]>50u?50u:amounts[g];
    wsExpectedCargoGoods[ship][slot]=goods[g];wsExpectedCargoTons[ship][slot]=(uint16_t)tons;slot++;amounts[g]-=tons;
   }
  }else if(s->startingFleet==2){
   wsExpectedCargoGoods[ship][0]=41;wsExpectedCargoTons[ship][0]=40;
   wsExpectedCargoGoods[ship][1]=42;wsExpectedCargoTons[ship][1]=40;
  }else if(!ship){
   static const uint16_t goods[4]={42,26,41,41};
   for(uint32_t slot=0;slot<4;slot++){
    wsExpectedCargoGoods[ship][slot]=goods[slot];
    wsExpectedCargoTons[ship][slot]=(uint16_t)(slot==1?10:(slot==3&&s->difficulty?30:50));
   }
  }
 }
 return 1;
}
static void wsStartingCargoBytes(unsigned char*cargo,uint32_t index,uint32_t holds){
 memset(cargo,0,64);
 for(uint32_t i=0;i<holds;i++){
  wsPut16(cargo+i*8,wsExpectedCargoGoods[index][i]);
  wsPut16(cargo+i*8+2,wsExpectedCargoTons[index][i]);
 }
}
