/* Include after start_options.inc. The complete newly serialized scene is
 * checked before writing. Every stock AI ship is relocated once; generated
 * human fleet positions are already taken from the same pre-pack contract.
 * Unknown owner/definition/coordinates, duplicate or absent boats fail closed.
 */
static int wsSceneShipMatches(uint32_t owner,uint32_t definition,float x,float y,uint32_t*seen){
 for(uint32_t i=0;i<wsExpectedSceneShipCount;i++){
  const WSSceneShip*p=&wsExpectedSceneShips[i];uint32_t bit=1u<<i;
  if(p->owner==owner&&p->definition==definition&&p->x==x&&p->y==y){if(*seen&bit)return 0;*seen|=bit;return 1;}
 }return 0;
}
static int wsRewriteSceneShips(WSBuffer*b,char*error,uint32_t cap){
 uint32_t seen=0,heads=0,count=0;
 if(!b||!b->data||b->size<32||!wsExpectedSceneShipCount||wsExpectedSceneShipCount>=32)goto invalid;
 for(uint32_t at=32;at<b->size;){
  if(b->size-at<16)goto invalid;uint32_t n=wsU32(b->data+at+12);if(n>b->size-at-16)goto invalid;
  unsigned char*p=b->data+at+16;
  if(wsTag(b->data+at,"HEAD")){
   if(++heads!=1||n!=32||wsU32(p)!=1024u||wsU32(p+4)!=1024u)goto invalid;
   wsPut32(p,wsWorld);wsPut32(p+4,wsWorld);
  }else if(wsTag(b->data+at,"SPIELER")){
   if(n<8||wsU32(p)||wsU32(p+4)>=32)goto invalid;uint32_t owner=wsU32(p+4),fAt=8;WSStartField f;
   while(fAt<n){if(!wsStartField(p,n,&fAt,&f))goto invalid;
    int wide=wsStartTag(p+f.at,"SCHI64"),ship=wide||wsStartTag(p+f.at,"SCHIFF");
    if(ship){
     uint32_t pos=wide?12u:8u,defAt=wide?4u:2u,ownerAt=wide?8u:4u;
     if(f.size<pos+8u||owner>4u||wsU32(f.data+ownerAt)!=owner)goto invalid;
     uint32_t definition=wsU16(f.data+defAt);float x,y;memcpy(&x,f.data+pos,4);memcpy(&y,f.data+pos+4,4);
     if(owner){
      if(wide||definition!=1502u||owner>=(wsShipDifficulty==0?4u:5u)||x!=wsStockShipXY[wsShipDifficulty][owner][0]||y!=wsStockShipXY[wsShipDifficulty][owner][1])goto invalid;
      wsWorldShipPosition(owner,&x,&y);memcpy((unsigned char*)f.data+pos,&x,4);memcpy((unsigned char*)f.data+pos+4,&y,4);
     }
     if(!wsSceneShipMatches(owner,definition,x,y,&seen))goto invalid;count++;
    }
   }
  }at+=16+n;
 }
 if(heads!=1||count!=wsExpectedSceneShipCount||seen!=((1u<<wsExpectedSceneShipCount)-1u))goto invalid;
 return 1;
 invalid:wsMessage(error,cap,"World dimensions or serialized starting ship positions differ from the validated world and fleet plan.");return 0;
}
