/* History Edition x64 loaded-data certificate. See CERTIFICATE.md and
 * native_evidence.json. Not proof of navigation, harvesting or a game run. */
typedef uintptr_t (*WSCertFn)(void*,uintptr_t,uintptr_t,uintptr_t);
typedef float (*WSCertFloat)(void*);
static int wsCertMemory(const void *p,size_t n,int executable){
 uintptr_t at=(uintptr_t)p,end;MEMORY_BASIC_INFORMATION m;
 if(!at||!n||n>UINTPTR_MAX-at)return 0;end=at+n;
 while(at<end){
  if(!VirtualQuery((void*)at,&m,sizeof m)||m.State!=MEM_COMMIT||m.Protect&(PAGE_GUARD|PAGE_NOACCESS))return 0;
  DWORD protection=m.Protect&0xff;
  if(executable){if(!(protection==PAGE_EXECUTE||protection==PAGE_EXECUTE_READ||protection==PAGE_EXECUTE_READWRITE||protection==PAGE_EXECUTE_WRITECOPY))return 0;}
  else if(!(protection==PAGE_READONLY||protection==PAGE_READWRITE||protection==PAGE_WRITECOPY||protection==PAGE_EXECUTE_READ||protection==PAGE_EXECUTE_READWRITE||protection==PAGE_EXECUTE_WRITECOPY))return 0;
  uintptr_t base=(uintptr_t)m.BaseAddress;if(m.RegionSize>UINTPTR_MAX-base)return 0;
  uintptr_t next=base+m.RegionSize;if(next<=at)return 0;at=next<end?next:end;
 }return 1;
}
static int wsCertRead(const void *p,void *out,size_t n){if(!out||!wsCertMemory(p,n,0))return 0;memcpy(out,p,n);return 1;}
static void *wsCertPointer(const void*p,size_t off){void*r=0;uintptr_t at=(uintptr_t)p;if(!at||off>UINTPTR_MAX-at||!wsCertRead((void*)(at+off),&r,sizeof r))return 0;return r;}
#ifndef WS_CERT_MODULE
#define WS_CERT_MODULE(name) GetModuleHandleA(name)
#endif
static void *wsCertNative(void*o,uint32_t module,uint32_t vtRva,uint32_t slot,uint32_t method,size_t objectSize){
 unsigned char*base=(unsigned char*)WS_CERT_MODULE(module?"AnnoGame.dll":"AnnoWelt.dll");void*vt=0,*f=0;MEMORY_BASIC_INFORMATION m;
 if(!base||!wsCertMemory(o,objectSize,0)||!wsCertRead(o,&vt,8)||vt!=base+vtRva||!wsCertRead(base+vtRva+slot,&f,8)||f!=base+method||!wsCertMemory(f,1,1))return 0;
 if(!VirtualQuery(f,&m,sizeof m)||m.AllocationBase!=base)return 0;
 return f;
}
static void *wsCertMethod(void*o,uint32_t offset){
 void*vt=wsCertPointer(o,0);unsigned char*w=(unsigned char*)WS_CERT_MODULE("AnnoWelt.dll"),*g=(unsigned char*)WS_CERT_MODULE("AnnoGame.dll");
 uintptr_t v=(uintptr_t)vt;uint32_t r=0,method=0,module=0;size_t size=0;if(!vt)return 0;
 if(g&&(v==(uintptr_t)g+0x21038||v==(uintptr_t)g+0x211b0||v==(uintptr_t)g+0x21328)){
  if(offset!=0x88)return 0;r=(uint32_t)(v-(uintptr_t)g);module=1;size=0x168;method=0x159e0;
 }else if(w&&v>=(uintptr_t)w&&v-(uintptr_t)w<=UINT32_MAX){
  r=(uint32_t)(v-(uintptr_t)w);
  switch(r){
   case 0xf2da8:case 0xf33e8:case 0xf37a0:
    size=0x158;method=offset==0x190?0x49500:offset==0x238?0x1fa50:offset==0x1f8?0x47980:0;break;
   case 0xf42f8:
    size=0x60;method=offset==0x28?0x5b340:offset==0x20?0x5b6c0:0;break;
   case 0xf4098:case 0xf41c8:case 0xf58e8:case 0xf5a18:case 0xf5b48:case 0xf5c78:case 0xf60a8:case 0xf6468:case 0xf65a0:case 0xf66d0:case 0xf6808:
    size=0x30;method=offset==0xe8?0x35210:offset==0xb0?0x72430:offset==0xc0?0x19320:0;
    if(r==0xf58e8){size=0x48;if(offset==0x118)method=0x717e0;if(offset==0xf8)method=0x718d0;}break;
   case 0xfabe0:
    size=0xd0;method=offset==0x98?0xa28e0:offset==0x88?0x8d00:0;break;
   case 0xfc678:
    size=0x30;method=offset==0x40?0x8ca0:0;break;
   case 0xee000:
    size=0x278;method=offset==0xb0?0x19320:offset==0xc0?0x19340:offset==0x40?0x198d0:offset==0xf8?0x19370:0;break;
   default:return 0;
  }
 }else return 0;
 return method?wsCertNative(o,module,r,offset,method,size):0;
}
static int wsCertCall(void*o,uint32_t off,uintptr_t a,uintptr_t b,uintptr_t c,uintptr_t*out){void*f=wsCertMethod(o,off);if(!f)return 0;*out=((WSCertFn)f)(o,a,b,c);return 1;}
static int wsCertFloat(void*o,uint32_t off,float*out){void*f=wsCertMethod(o,off);if(!f)return 0;*out=((WSCertFloat)f)(o);return 1;}
static int wsCertProperty(void*o,uint32_t property,uint32_t*out){
 uint64_t payload[32]={0};uintptr_t ok=0;
 if(!wsCertCall(o,0x98,property,(uintptr_t)payload,0,&ok)||!ok)return 0;
 memcpy(out,(unsigned char*)payload+8,4);return 1;
}
/* Welt a28e0 property1c reads player+9e u16; Game23c90 gives enum names.
 * Catalogue bit order deliberately differs from engine enum order. */
static uint32_t wsCertCulture(uint32_t value){
 static const unsigned char nativeValues[8]={2,4,3,6,5,8,7,9};
 for(uint32_t i=0;i<8;i++)if(nativeValues[i]==value)return 1u<<i;
 return 0;
}
static uint32_t wsCertMineral(uint32_t definition){
 switch(definition){case 1560:case 1661:return 1;case 1561:return 2;case 1562:return 4;case 1563:return 8;case 1564:return 0x20;default:return 0;}
}
static int wsCertShipWater(float x,float y,uint32_t*blockedIsland){
 *blockedIsland=UINT32_MAX;
 if(!(x>=16&&x<WS_WORLD-16&&y>=16&&y<WS_WORLD-16))return 0;
 for(uint32_t i=0;i<planCount;i++){const WSPlanIsland*p=&planned[i];if(!(x+16<p->x||x-16>=p->x+p->width||y+16<p->y||y-16>=p->y+p->height)){*blockedIsland=p->id;return 0;}}
 return 1;
}
typedef struct WSCertShipDiagnostic {
 uint32_t residents,live,ships,checked,humans,otherShips,index,known,owner,definition,clearance;
 float x,y;char tableClass[40],shipClass[40],ownerClass[40],figureClass[40],firstClass[40],firstOther[40];
} WSCertShipDiagnostic;
static void wsCertClassName(void*vt,char out[40]){
 unsigned char*w=(unsigned char*)WS_CERT_MODULE("AnnoWelt.dll"),*g=(unsigned char*)WS_CERT_MODULE("AnnoGame.dll");MEMORY_BASIC_INFORMATION m;
 if(!vt)snprintf(out,40,"unreadable");
 else if(w&&(uintptr_t)vt>=(uintptr_t)w&&(uintptr_t)vt-(uintptr_t)w<=UINT32_MAX&&VirtualQuery(vt,&m,sizeof m)&&m.AllocationBase==w)
  snprintf(out,40,"Welt+0x%lx",(unsigned long)((uintptr_t)vt-(uintptr_t)w));
 else if(g&&(uintptr_t)vt>=(uintptr_t)g&&(uintptr_t)vt-(uintptr_t)g<=UINT32_MAX&&VirtualQuery(vt,&m,sizeof m)&&m.AllocationBase==g)
  snprintf(out,40,"Game+0x%lx",(unsigned long)((uintptr_t)vt-(uintptr_t)g));
 else snprintf(out,40,"outside native modules");
}
static int wsCertShipFailure(const WSCertShipDiagnostic*d,const char*reason,const char*method,char*error,uint32_t cap){
 char clearance[20],index[20];
 if(d->clearance==UINT32_MAX)snprintf(clearance,sizeof clearance,"none");else snprintf(clearance,sizeof clearance,"%u",d->clearance);
 if(d->index==UINT32_MAX)snprintf(index,sizeof index,"none");else snprintf(index,sizeof index,"%u",d->index);
 if(error&&cap){
  snprintf(error,cap,"Loaded starting ships rejected. reason=%s method=%s table=%s residents=%u live=%u playerShips=%u checked=%u humans=%u index=%s class=%s xy=%.9g,%.9g known=0x%x owner=%u def=%u ownerClass=%s figureClass=%s clearanceIsland=%s otherShips=%u first=%s firstOther=%s",
   reason,method,d->tableClass,d->residents,d->live,d->ships,d->checked,d->humans,index,d->shipClass,
   (double)d->x,(double)d->y,d->known,d->owner,d->definition,d->ownerClass,d->figureClass,clearance,d->otherShips,d->firstClass,d->firstOther);
  error[cap-1]=0;
 }return 0;
}
static int wsCertShips(void*world,char*error,uint32_t cap){
 WSCertShipDiagnostic d={0};d.index=d.clearance=UINT32_MAX;
 snprintf(d.shipClass,sizeof d.shipClass,"none");snprintf(d.ownerClass,sizeof d.ownerClass,"none");snprintf(d.figureClass,sizeof d.figureClass,"none");snprintf(d.firstClass,sizeof d.firstClass,"none");snprintf(d.firstOther,sizeof d.firstOther,"none");
 #define WS_SHIP_FAIL(reason,method) return wsCertShipFailure(&d,reason,method,error,cap)
 /* Native server-world init dbb63 stores tBewohnerTabServer at +208.
  * +220 is a tKarteObject map object, not a resident collection. */
 unsigned char*w=(unsigned char*)WS_CERT_MODULE("AnnoWelt.dll");void*table=wsCertPointer(world,0x208),*vt=wsCertPointer(table,0);
 wsCertClassName(vt,d.tableClass);
 if(!w||(vt!=w+0xfcec8&&vt!=w+0xffa20))WS_SHIP_FAIL("resident-table-class","world+208");
 if(!wsCertMemory(table,0x28,0))WS_SHIP_FAIL("resident-table-unreadable","world+208");
 uintptr_t begin=(uintptr_t)wsCertPointer(table,0x18),end=(uintptr_t)wsCertPointer(table,0x20);
 if(end<begin||(end-begin)%32||(end-begin)/32>65536)WS_SHIP_FAIL("resident-vector-range","table+18/+20");
 d.residents=(uint32_t)((end-begin)/32);
 if(!begin||!d.residents)WS_SHIP_FAIL("resident-vector-empty","table+18/+20");
 if(!wsCertMemory((void*)begin,end-begin,0))WS_SHIP_FAIL("resident-vector-unreadable","table+18/+20");
 /* First pass counts exact native classes without invoking unreviewed methods.
  * Other known ship classes are diagnostic evidence, never accepted as the
  * verified player-ship class. No addresses or arbitrary object bytes appear. */
 for(uintptr_t at=begin;at<end;at+=32){
  void*resident=wsCertPointer((void*)at,0x18);if(!resident)continue;void*classPointer=wsCertPointer(resident,0);d.live++;
  if(d.live==1)wsCertClassName(classPointer,d.firstClass);
  if(classPointer==w+0xee000)d.ships++;
  else if(classPointer==w+0xedbb0||classPointer==w+0xee388||classPointer==w+0xee6a8||classPointer==w+0xee9c8){if(!d.otherShips)wsCertClassName(classPointer,d.firstOther);d.otherShips++;}
 }
 if(d.ships>1024)WS_SHIP_FAIL("player-ship-traversal-cap","resident-vector");
 /* Native c1390 vector: 32-byte records, resident pointer+18. */
 for(uintptr_t at=begin;at<end;at+=32){
  void*ship=wsCertPointer((void*)at,0x18);if(!ship||wsCertPointer(ship,0)!=w+0xee000)continue;
  d.checked++;d.index=(uint32_t)((at-begin)/32);d.known=0;d.owner=d.definition=0;d.x=d.y=0;d.clearance=UINT32_MAX;wsCertClassName(wsCertPointer(ship,0),d.shipClass);snprintf(d.ownerClass,sizeof d.ownerClass,"none");snprintf(d.figureClass,sizeof d.figureClass,"none");
  uintptr_t owner=0,id=0,definition=0,figure=0;
  if(!wsCertFloat(ship,0xb0,&d.x))WS_SHIP_FAIL("ship-x-getter","ship+b0");d.known|=1;
  if(!wsCertFloat(ship,0xc0,&d.y))WS_SHIP_FAIL("ship-y-getter","ship+c0");d.known|=2;
  if(!wsCertCall(ship,0x40,0,0,0,&owner))WS_SHIP_FAIL("ship-owner-getter","ship+40");
  if(!owner)WS_SHIP_FAIL("ship-owner-null","ship+40");
  wsCertClassName(wsCertPointer((void*)owner,0),d.ownerClass);
  if(!wsCertCall((void*)owner,0x88,0,0,0,&id))WS_SHIP_FAIL("owner-id-getter","owner+88");d.owner=(uint32_t)id;d.known|=4;
  if(!wsCertCall(ship,0xf8,0,0,0,&figure))WS_SHIP_FAIL("ship-figure-getter","ship+f8");
  if(!figure)WS_SHIP_FAIL("ship-figure-null","ship+f8");
  wsCertClassName(wsCertPointer((void*)figure,0),d.figureClass);
  if(!wsCertCall((void*)figure,0x88,0,0,0,&definition))WS_SHIP_FAIL("figure-definition-getter","figure+88");d.definition=(uint32_t)definition;d.known|=8;
  if(!id)d.humans++;
  if(!wsCertShipWater(d.x,d.y,&d.clearance))WS_SHIP_FAIL(d.clearance==UINT32_MAX?"position-bounds":"island-clearance","ship+b0/+c0");
  if(!id){
   /* All3source scenes have one owner0 ship1502, at one of these2positions.
    * Other loaded player ships also need open-water envelope clearance. */
   if(definition!=1502)WS_SHIP_FAIL("human-stock-definition","figure+88");
   if(!((d.x==566.5f&&d.y==435.5f)||(d.x==450.5f&&d.y==422.5f)))WS_SHIP_FAIL("human-stock-position","ship+b0/+c0");
  }
 }
 if(d.humans!=1||!d.ships)WS_SHIP_FAIL("human-ship-count","resident-vector");
 #undef WS_SHIP_FAIL
 return 1;
}
/* Only planned scalars and the rejected island's reviewed rectangle, climate
 * byte and vtable are inspected. Diagnostics contain no absolute addresses or
 * arbitrary memory dumps. snprintf bounds every caller-provided error buffer. */
static int wsCertIslandFailure(uint32_t id,const WSPlanIsland*p,void*island,
                              const char*kind,const char*reason,char*error,uint32_t cap){
 uint16_t actual[4]={0};unsigned char climate=0;uintptr_t at=(uintptr_t)island;
 int geometryRead=at<=UINTPTR_MAX-8&&wsCertRead((void*)(at+8),actual,sizeof actual);
 int climateRead=at<=UINTPTR_MAX-0x148&&wsCertRead((void*)(at+0x148),&climate,1);
 void*vt=wsCertPointer(island,0);unsigned char*w=(unsigned char*)WS_CERT_MODULE("AnnoWelt.dll");
 char className[40],climateName[24];MEMORY_BASIC_INFORMATION m;
 if(!vt)snprintf(className,sizeof className,"unreadable");
 else if(w&&(uintptr_t)vt>=(uintptr_t)w&&(uintptr_t)vt-(uintptr_t)w<=UINT32_MAX&&VirtualQuery(vt,&m,sizeof m)&&m.AllocationBase==w)
  snprintf(className,sizeof className,"Welt+0x%lx",(unsigned long)((uintptr_t)vt-(uintptr_t)w));
 else snprintf(className,sizeof className,"outside Welt");
 if(climateRead)snprintf(climateName,sizeof climateName,"%u",(unsigned)climate);
 else snprintf(climateName,sizeof climateName,"unreadable");
 if(error&&cap){
  snprintf(error,cap,"Loaded island %s differs from the validated plan. id=%u reason=%s plan(id=%u xy=%u,%u size=%u,%u climate=%u template=%u/%u) loaded(read=%d xy=%u,%u size=%u,%u climate=%s) class=%s method190=%s",
   kind,id,reason,p->id,p->x,p->y,p->width,p->height,p->climate,p->templateIndex,(unsigned)WS_COUNT,
   geometryRead,(unsigned)actual[0],(unsigned)actual[1],(unsigned)actual[2],(unsigned)actual[3],climateName,className,
   wsCertMethod(island,0x190)?"verified":"no verified method");
  error[cap-1]=0;
 }return 0;
}
static int wsLoadedCertificate(void*scene,char*error,uint32_t cap){
 #define WS_CERT_FAIL(message) do{wsMessage(error,cap,message);return 0;}while(0)
 if(!planCount||planCount>WS_LIMIT)WS_CERT_FAIL("Loaded world has no valid island plan.");
 void*world=wsCertPointer(scene,0x160);uint32_t liveCount=0,crops=0,fertileCrops=0,minerals=0,cultures=0,whales=0;unsigned char*w=(unsigned char*)WS_CERT_MODULE("AnnoWelt.dll");void*worldVT=wsCertPointer(world,0);
 if(!w||(worldVT!=w+0xff1d8&&worldVT!=w+0xff650)||!wsCertMemory(world,0x6e40,0))WS_CERT_FAIL("Loaded world has no verified native island table.");
 for(uint32_t id=0;id<256;id++){
  void*island=wsCertPointer(world,0x6640+id*8);if(!island)continue;
  if(id>=planCount)WS_CERT_FAIL("Loaded world contains an unexpected island.");
  const WSPlanIsland*p=&planned[id];uint16_t geometry[4]={0};const char*geometryReason=NULL;
  if(p->id!=id)geometryReason="plan-id";
  else if(p->climate>=6)geometryReason="plan-climate";
  else if(p->templateIndex>=WS_COUNT)geometryReason="template-index";
  else if(!p->width||p->width>256||!p->height||p->height>256)geometryReason="plan-dimensions";
  else if(p->x>WS_WORLD-p->width||p->y>WS_WORLD-p->height)geometryReason="plan-world-bounds";
  else if(!wsCertMethod(island,0x190))geometryReason="native-method190";
  else if(!wsCertRead((unsigned char*)island+8,geometry,sizeof geometry))geometryReason="unreadable-rectangle";
  else if(geometry[0]!=p->x||geometry[1]!=p->y||geometry[2]!=p->width||geometry[3]!=p->height)geometryReason="rectangle-mismatch";
  if(geometryReason)return wsCertIslandFailure(id,p,island,"geometry",geometryReason,error,cap);
  for(uint32_t j=0;j<id;j++)if(!wsSeparated(p,&planned[j],planSpacing))WS_CERT_FAIL("Loaded islands overlap or violate selected spacing.");
  liveCount++;uintptr_t mask=0,climate=0;
  if(!wsCertCall(island,0x190,7,0,0,&climate)||climate!=p->climate)return wsCertIslandFailure(id,p,island,"climate","climate-mismatch",error,cap);
  if(!wsCertCall(island,0x190,11,0,0,&mask)||(mask&p->cropMask)!=p->cropMask)WS_CERT_FAIL("Loaded island lost a required crop or resource flag.");
  crops|=(uint32_t)mask;
  /* FRUCHTBAR low nibble is native fertility, World4b8e0. HEIGHT uses
   * (width+1) vertex stride, Worldc8b90. The>=48landtest is conservative
   * data coverage only; farming/building accessibility requires a game run. */
  const unsigned char*fertility=wsCertPointer(island,0x28),*heights=wsCertPointer(island,0x20);uint32_t fertile=0;
  if(!fertility||!heights||!wsCertMemory(fertility,(size_t)p->width*p->height,0)||!wsCertMemory(heights,(size_t)(p->width+1)*(p->height+1),0))WS_CERT_FAIL("Loaded island terrain arrays are unreadable.");
  for(uint32_t y=0;y<p->height;y++)for(uint32_t x=0;x<p->width;x++)if((fertility[y*p->width+x]&15)&&heights[y*(p->width+1)+x]>=48)fertile++;
  if(p->climate&&fertile==0)WS_CERT_FAIL("A loaded growing climate has no fertile land coverage.");
  if(fertile)fertileCrops|=(uint32_t)mask&cropMasks[p->climate]&0x1fff;
  uintptr_t collection=0,occ=0,next=0;uint32_t islandMinerals=0,occCount=0;
  if(!wsCertCall(island,0x238,0,0,0,&collection)||!collection||!wsCertCall((void*)collection,0x28,p->x,p->y,0,&occ))WS_CERT_FAIL("Loaded island occurrences cannot be enumerated.");
  while(occ){
   if(++occCount>4096||!wsCertMemory((void*)occ,0x30,0))WS_CERT_FAIL("Loaded occurrence collection is cyclic or unsupported.");
   uintptr_t def=0,definition=0;
   if(!wsCertCall((void*)occ,0xe8,0,0,0,&def)||!def||!wsCertCall((void*)def,0x88,0,0,0,&definition))WS_CERT_FAIL("Loaded occurrence definition is unreadable.");
   uint32_t mineral=wsCertMineral((uint32_t)definition);
   if(mineral||definition==1559){
    float x=0,y=0;
    if(!wsCertFloat((void*)occ,0xb0,&x)||!wsCertFloat((void*)occ,0xc0,&y)||!(x>=p->x&&x<p->x+p->width&&y>=p->y&&y<p->y+p->height))WS_CERT_FAIL("A resource occurrence lies outside its island.");
    if(mineral){uintptr_t left=0,flag=0;
     /* NativeC250 removes unused deposits by consuming all remaining
      * quantity through+118(1)/+120(quantity,1). Never count such leftovers. */
     if(!wsCertCall((void*)occ,0x118,1,0,0,&left)||!wsCertCall((void*)occ,0xf8,4,0,0,&flag))WS_CERT_FAIL("Loaded mineral quantity cannot be queried.");
     if(left>0&&left<=0x7fffffff&&!flag)islandMinerals|=mineral;
    }else if(wsCertPointer((void*)occ,0)==w+0xf66d0)whales++;
   }
   if(!wsCertCall((void*)collection,0x20,occ,0,0,&next)||next==occ)WS_CERT_FAIL("Loaded occurrence list does not advance.");occ=next;
  }
  uint32_t required=p->mineralMask;if(required&0x40)required=(required&~0x40u)|1;
  if((islandMinerals&required)!=required)WS_CERT_FAIL("A loaded island is missing an assigned physical mineral deposit.");
  minerals|=islandMinerals;
  uint32_t islandCultures=0;
  for(uint32_t slot=0;slot<16;slot++){
   uintptr_t city=0,owner=0;
   if(!wsCertCall(island,0x1f8,slot,0,0,&city))WS_CERT_FAIL("Loaded city slots cannot be inspected.");if(!city)continue;
   if(!wsCertCall((void*)city,0x40,0,0,0,&owner)||!owner)WS_CERT_FAIL("A loaded settlement has no owner.");
   uint32_t type=0,nativeCulture=0;
   if(!wsCertProperty((void*)owner,9,&type)||!wsCertProperty((void*)owner,0x1c,&nativeCulture))WS_CERT_FAIL("Loaded settlement ownership cannot be queried.");
   if(type!=14)WS_CERT_FAIL("A template settlement was not transferred to a native player.");
   uint32_t bit=wsCertCulture(nativeCulture);if(!bit)WS_CERT_FAIL("Loaded settlement has an unsupported native culture.");islandCultures|=bit;
  }
  if(islandCultures!=p->cultures)WS_CERT_FAIL("Loaded native culture owners differ from the selected cultures.");cultures|=islandCultures;
 }
 uint32_t expectedCultures=0;for(uint32_t i=0;i<planCount;i++)expectedCultures|=planned[i].cultures;
 if(liveCount!=planCount||(crops&0x1ffff)!=0x1ffff||(fertileCrops&0x1fff)!=0x1fff||(minerals&0x2f)!=0x2f||!whales||cultures!=expectedCultures)WS_CERT_FAIL("Loaded world lacks an essential crop, mineral, whale or culture owner.");
 if(!wsCertShips(world,error,cap))return 0;
 wsMessage(error,cap,"");return 1;
 #undef WS_CERT_FAIL
}
