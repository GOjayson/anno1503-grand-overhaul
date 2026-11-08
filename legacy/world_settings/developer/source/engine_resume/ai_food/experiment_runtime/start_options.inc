/* History Edition scene options. Include after WSBuffer / native scene helpers.
 * No installed asset changes; only the guarded, newly generated scene is edited.
 * ABI additions: startingMoney (amount), startingFleet (0 single/1 war/2 merchant).
 */
typedef struct WSStartField { const unsigned char *data; uint32_t at,size,header; } WSStartField;
typedef struct WSStartShip { uint32_t definition; float x,y; } WSStartShip;
static WSStartShip wsExpectedStartShips[3];
static uint32_t wsExpectedStartShipCount,wsExpectedStartingMoney,wsExpectedStartingFleet,wsExpectedStartingDifficulty;
static const unsigned char*wsStartingStockShip;
static uint32_t wsStartingStockShipSize,wsStartingLastPlayerAt,wsStartingExtrasEmitted;

static int wsStartField(const unsigned char*p,uint32_t n,uint32_t *at,WSStartField*f){
 uint32_t pos=*at;if(pos>n||n-pos<8)return 0;
 uint32_t len=wsU16(p+pos+6),h=8;
 if(len>=0xff00){if(n-pos<10)return 0;len=((len&255)<<16)|wsU16(p+pos+8);h=10;}
 if(len>n-pos-h)return 0;
 int zero=0;for(uint32_t i=0;i<6;i++){unsigned char c=p[pos+i];if(!c){zero=1;continue;}if(zero||!((c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'))return 0;}
 if(!p[pos])return 0;
 f->data=p+pos+h;f->at=pos;f->size=len;f->header=h;*at=pos+h+len;return 1;
}
static int wsStartTag(const unsigned char*p,const char*t){size_t n=strlen(t);return n<=6&&!memcmp(p,t,n)&&(n==6||!p[n]);}
static int wsStartAppendField(WSBuffer*b,const char*tag,const void*data,uint32_t n){
 unsigned char h[8]={0};if(strlen(tag)>6||n>=0xff00)return 0;
 memcpy(h,tag,strlen(tag));wsPut16(h+6,(uint16_t)n);return wsAppend(b,h,8)&&wsAppend(b,data,n);
}
static int wsStartingMoneyAllowed(int32_t n){return n==10000||n==30000||n==50000||n==80000||n==100000;}
static int wsStartingShipFields(const unsigned char*p,uint32_t n,uint32_t difficulty){
 if(n<16||wsU16(p+2)!=1502||wsU32(p+4)!=0)return 0;
 const float x=difficulty==1?450.5f:566.5f,y=difficulty==1?422.5f:435.5f;float sx,sy;
 memcpy(&sx,p+8,4);memcpy(&sy,p+12,4);if(sx!=x||sy!=y)return 0;
 uint32_t at=16,heads=0,cargos=0,privates=0;WSStartField f;
 while(at<n){if(!wsStartField(p,n,&at,&f))return 0;
  if(wsStartTag(p+f.at,"HEAD")){if(++heads!=1||f.size!=16||f.data[8]!=0||f.data[9]!=128)return 0;}
  else if(wsStartTag(p+f.at,"WAREN")){
   if(++cargos!=1||f.size!=32)return 0;
   static const uint16_t goods[4]={42,26,41,41};
   for(uint32_t i=0;i<4;i++)if(wsU16(f.data+i*8)!=goods[i]||wsU16(f.data+i*8+2)!=(i==1?10:(i==3&&difficulty?30:50))||wsU32(f.data+i*8+4))return 0;
  }else if(wsStartTag(p+f.at,"PRIVAT")){if(++privates!=1||f.size<20)return 0;}
  else return 0;
 }
 return heads==1&&cargos==1&&privates==1;
}
/* Validate both paired human records before exposing expected post-load state. */
static int wsStartingInspect(const unsigned char*src,uint32_t size,const WSWorldSettings*s,char*error,uint32_t cap){
 wsExpectedStartShipCount=wsExpectedStartingMoney=wsExpectedStartingFleet=wsExpectedStartingDifficulty=0;
 wsStartingStockShip=0;wsStartingStockShipSize=wsStartingLastPlayerAt=wsStartingExtrasEmitted=0;
 if(!s||s->size!=sizeof(*s)||s->difficulty<0||s->difficulty>2||!wsStartingMoneyAllowed(s->startingMoney)||s->startingFleet<0||s->startingFleet>2){wsMessage(error,cap,"Starting money or fleet selection is unsupported.");return 0;}
 if(size<32||(!wsTag(src,"ANNO")&&!wsTag(src,"ANNOADDON1"))||wsU32(src+12)!=size-16||!wsTag(src+16,"SCENE")||wsU32(src+28)!=size-32){wsMessage(error,cap,"Starting options require the verified scene container.");return 0;}
 uint32_t at=32,basics=0,states=0,ships=0;float x,y;wsWorldShipPosition(0,&x,&y);
 while(at<size){if(size-at<16)goto malformed;uint32_t n=wsU32(src+at+12);if(n>size-at-16)goto malformed;
  const unsigned char*p=src+at+16;if(wsTag(src+at,"SPIELER")){
   wsStartingLastPlayerAt=at;
   if(n<8||wsU32(p)!=0)goto malformed;
   if(wsU32(p+4)==0){uint32_t fAt=8,head=0,ship=0;WSStartField f;
    while(fAt<n){if(!wsStartField(p,n,&fAt,&f))goto malformed;
     if(wsStartTag(p+f.at,"HEAD")){static const uint32_t stockMoney[3]={50000,30000,25000};if(++head!=1||f.size!=108||wsU32(f.data)!=11||wsU32(f.data+4)!=stockMoney[s->difficulty])goto malformed;}
     if(wsStartTag(p+f.at,"SCHIFF")){if(++ship!=1||!wsStartingShipFields(f.data,f.size,(uint32_t)s->difficulty))goto malformed;ships++;wsStartingStockShip=f.data;wsStartingStockShipSize=f.size;}
    }
    if(head&&!ship)basics++;else if(ship&&!head)states++;else goto malformed;
   }
  }at+=16+n;
 }
 if(basics!=1||states!=1||ships!=1)goto malformed;
 wsExpectedStartingMoney=(uint32_t)s->startingMoney;wsExpectedStartingFleet=(uint32_t)s->startingFleet;wsExpectedStartingDifficulty=(uint32_t)s->difficulty;
 wsExpectedStartShipCount=s->startingFleet?3:1;
 wsExpectedStartShips[0]=(WSStartShip){s->startingFleet?1503:1502,x,y};
 wsExpectedStartShips[1]=(WSStartShip){s->startingFleet==1?1504:1502,x-6,y+6};
 wsExpectedStartShips[2]=(WSStartShip){s->startingFleet==1?1504:1502,x+6,y+6};
 return 1;
 malformed:wsMessage(error,cap,"Stock human money, fleet or cargo records differ from the verified History Edition scene.");return 0;
}
static int wsStartingNewShip(WSBuffer*out,const unsigned char*stock,uint32_t stockSize,uint32_t index){
 unsigned char raw[1024]={0},prefix[20]={0},head[16],cargo[64]={0};WSBuffer b={raw,0,sizeof raw};
 uint32_t definition=wsExpectedStartShips[index].definition,holds=definition==1503?8:(definition==1502?4:2);
 uint32_t prefixSize=index?20:16;
 if(index){wsPut32(prefix,UINT32_MAX);wsPut16(prefix+4,(uint16_t)definition);memcpy(prefix+12,&wsExpectedStartShips[index].x,4);memcpy(prefix+16,&wsExpectedStartShips[index].y,4);}
 else{memcpy(prefix,stock,16);wsPut16(prefix+2,(uint16_t)definition);memcpy(prefix+8,&wsExpectedStartShips[index].x,4);memcpy(prefix+12,&wsExpectedStartShips[index].y,4);}
 uint32_t at=16;WSStartField f;const unsigned char*privateData=0;uint32_t privateSize=0;
 memset(head,0,sizeof head);head[0]=3;head[1]=255;wsPut32(head+4,0x00ffff00);head[9]=128;
 head[8]=(unsigned char)(wsExpectedStartingFleet==1?6:0);
 while(at<stockSize){if(!wsStartField(stock,stockSize,&at,&f))return 0;
  if(wsStartTag(stock+f.at,"WAREN")&&!index&&wsExpectedStartingFleet==1)memcpy(cargo,f.data,32);
  if(wsStartTag(stock+f.at,"PRIVAT")){privateData=f.data;privateSize=f.size;}
 }
 if(wsExpectedStartingFleet==2){wsPut16(cargo,41);wsPut16(cargo+2,40);wsPut16(cargo+8,42);wsPut16(cargo+10,40);}
 if(!wsAppend(&b,prefix,prefixSize)||!wsStartAppendField(&b,"HEAD",head,16)||!wsStartAppendField(&b,"WAREN",cargo,holds*8))return 0;
 if(!index){if(!privateData||!wsStartAppendField(&b,"PRIVAT",privateData,privateSize))return 0;}
 else{
  static const unsigned char names[2][16]={{'W','o','r','l','d',' ','E','s','c','o','r','t',' ','1',0,0},{'W','o','r','l','d',' ','E','s','c','o','r','t',' ','2',0,0}};
  unsigned char priv[64];WSBuffer p={priv,0,sizeof priv};const uint16_t noTrade=0xffff;
  if(!wsStartAppendField(&p,"NAME",names[index-1],15)||!wsStartAppendField(&p,"VERK",&noTrade,2)||!wsStartAppendField(&b,"PRIVAT",priv,p.size))return 0;
 }
 return wsStartAppendField(out,index?"SCHI64":"SCHIFF",raw,b.size);
}
/* Call for every owner0 SPIELER, bypassing the ordinary-CPU filter for this record.
 * A private temporary buffer makes capacity and malformed-input failures atomic. */
static int wsStartingScenePlayer(WSBuffer*out,const unsigned char*p,uint32_t n,const WSWorldSettings*s,char*error,uint32_t cap){
 unsigned char local[4096];WSBuffer b={local,0,sizeof local};uint32_t at=8;WSStartField f;
 if(!wsExpectedStartShipCount||n<8||wsU32(p)||wsU32(p+4)||!wsAppend(&b,p,8))goto failure;
 while(at<n){if(!wsStartField(p,n,&at,&f))goto failure;
  if(wsStartTag(p+f.at,"HEAD")){unsigned char head[108];if(f.size!=108)goto failure;memcpy(head,f.data,108);wsPut32(head+4,(uint32_t)s->startingMoney);if(!wsStartAppendField(&b,"HEAD",head,108))goto failure;}
  else if(wsStartTag(p+f.at,"SCHIFF")){
   if(s->startingFleet){if(!wsStartingNewShip(&b,f.data,f.size,0))goto failure;}
   else{uint32_t output=b.size;if(f.size<16||!wsAppend(&b,p+f.at,f.header+f.size))goto failure;memcpy(b.data+output+f.header+8,&wsExpectedStartShips[0].x,4);memcpy(b.data+output+f.header+12,&wsExpectedStartShips[0].y,4);}
  }
  else if(!wsAppend(&b,p+f.at,f.header+f.size))goto failure;
 }
 if(b.size>out->capacity-out->size||out->capacity-out->size-b.size<16)goto failure;
 return wsChunk(out,"SPIELER",b.data,b.size);
 failure:wsMessage(error,cap,"Could not stage the verified human starting money and fleet.");return 0;
}
/* Call at the START of each original top-level chunk iteration, with that
 * chunk's source offset. This inserts the escorts after the last stock player
 * and before BIGBROTHER. Every original basic/state record retains its order.
 * Native E1086..E1100 loads another SPIELER into the already existing owner0;
 * this chunk contains only SCHI64 and cannot replace HEAD/COMP/selection fields.
 */
static int wsStartingEmitExtraShips(WSBuffer*out,const WSWorldSettings*s,uint32_t sourceAt,char*error,uint32_t cap){
 if(!s->startingFleet||wsStartingExtrasEmitted||sourceAt<=wsStartingLastPlayerAt)return 1;
 unsigned char raw[1024]={0};WSBuffer b={raw,8,sizeof raw};
 if(!wsStartingStockShip||!wsStartingStockShipSize)goto failure;
 for(uint32_t i=1;i<3;i++)if(!wsStartingNewShip(&b,wsStartingStockShip,wsStartingStockShipSize,i))goto failure;
 if(b.size>out->capacity-out->size||out->capacity-out->size-b.size<16||!wsChunk(out,"SPIELER",b.data,b.size))goto failure;
 wsStartingExtrasEmitted=1;return 1;
 failure:wsMessage(error,cap,"Could not safely append the chosen escorts after the stock player records.");return 0;
}
