/* Call only after wsLoadedCertificate succeeds on the fresh pending world.
 * Native Scene c250 exhausts unused ore instead of deleting it. The ordinary
 * Erz loader reconstructs reserved deposits from zero on the next save/load.
 * Persist unused slots as the engine's zero-quantity non-reserve1661 form.
 * All object/method/write preconditions are checked before publishing changes;
 * a native refusal rejects this pending world before the gameplay commit. */
typedef struct WSMineralPersistenceCandidate {void*occurrence;void*definition;} WSMineralPersistenceCandidate;
static int wsMineralPersistenceWritable(void*p,size_t n){
 uintptr_t at=(uintptr_t)p,end;if(!at||!n||n>UINTPTR_MAX-at)return 0;end=at+n;
 while(at<end){MEMORY_BASIC_INFORMATION m;
  if(!VirtualQuery((void*)at,&m,sizeof m)||m.State!=MEM_COMMIT||m.Protect&(PAGE_GUARD|PAGE_NOACCESS))return 0;
  DWORD prot=m.Protect&0xff;
  if(!(prot==PAGE_READWRITE||prot==PAGE_WRITECOPY||prot==PAGE_EXECUTE_READWRITE||prot==PAGE_EXECUTE_WRITECOPY))return 0;
  uintptr_t base=(uintptr_t)m.BaseAddress;if(m.RegionSize>UINTPTR_MAX-base)return 0;
  uintptr_t next=base+m.RegionSize;if(next<=at)return 0;at=next<end?next:end;
 }return 1;
}
static int wsStabilizeMineralAbsence(void*scene,char*error,uint32_t cap){
 #define WS_MINERAL_PERSIST_FAIL(message) do{wsMessage(error,cap,message);goto failed;}while(0)
 WSMineralPersistenceCandidate*candidates=NULL;size_t capacity=0,count=0;void*shallow=NULL;
 unsigned char*w=(unsigned char*)WS_CERT_MODULE("AnnoWelt.dll"),*g=(unsigned char*)WS_CERT_MODULE("AnnoGame.dll");
 if(!pending||!prepared||preparedScene!=scene||!w||!g||!planCount||planCount>WS_LIMIT)WS_MINERAL_PERSIST_FAIL("Mineral persistence requires the verified pending generated world.");
 void*world=wsCertPointer(scene,0x160);void*worldVT=wsCertPointer(world,0);
 if((worldVT!=w+0xff1d8&&worldVT!=w+0xff650)||!wsCertMemory(world,0x6e40,0))WS_MINERAL_PERSIST_FAIL("Mineral persistence cannot verify the native world table.");
 for(uint32_t i=0;i<planCount;i++){
  if(planned[i].templateIndex>=WS_COUNT)WS_MINERAL_PERSIST_FAIL("Mineral persistence has an invalid template index.");
  capacity+=wsTemplates[planned[i].templateIndex].oreSlots;
 }
 /* A generated template cannot legitimately acquire additional ore slots
  * between native c250 and its synchronous before-gameplay certificate. */
 if(!capacity||capacity>WS_LIMIT*4096u||capacity>SIZE_MAX/sizeof(*candidates))WS_MINERAL_PERSIST_FAIL("Mineral persistence has unsupported native occurrence capacity.");
 candidates=(WSMineralPersistenceCandidate*)malloc(capacity*sizeof(*candidates));
 if(!candidates)WS_MINERAL_PERSIST_FAIL("Cannot allocate the mineral persistence check.");
 for(uint32_t i=0;i<planCount;i++){
  const WSPlanIsland*p=&planned[i];void*island=wsCertPointer(world,0x6640+i*8);uintptr_t collection=0,occ=0,next=0;uint32_t seen=0;
  if(!island||!wsCertCall(island,0x238,0,0,0,&collection)||!collection||!wsCertCall((void*)collection,0x28,p->x,p->y,0,&occ))WS_MINERAL_PERSIST_FAIL("Mineral persistence cannot enumerate a verified island.");
  while(occ){
   if(++seen>4096)WS_MINERAL_PERSIST_FAIL("Mineral persistence encountered a cyclic or oversized occurrence list.");
   uintptr_t def=0,ident=0;
   if(!wsCertCall((void*)occ,0xe8,0,0,0,&def)||!def||!wsCertCall((void*)def,0x88,0,0,0,&ident))WS_MINERAL_PERSIST_FAIL("Mineral persistence cannot verify an occurrence definition.");
   if(wsCertMineral((uint32_t)ident)){
    uintptr_t left=0,disabled=0,reserve=0;
    if(!wsCertCall((void*)occ,0x118,1,0,0,&left)||!wsCertCall((void*)occ,0xf8,4,0,0,&disabled)||!wsCertCall((void*)occ,0xf8,1,0,0,&reserve)||left>0x7fffffffu)WS_MINERAL_PERSIST_FAIL("Mineral persistence cannot verify current deposit state.");
    /* Disabled positive deposits have no proved persisted absence encoding.
     * Never silently reactivate, consume or reinterpret an active deposit. */
    if(disabled&&left)WS_MINERAL_PERSIST_FAIL("A disabled positive deposit has unsupported save persistence.");
    if(ident==1661&&left&&!disabled)shallow=(void*)def;
    if(!left){
     if(ident==1661){if(reserve)WS_MINERAL_PERSIST_FAIL("An exhausted shallow deposit has an unexpected reserve flag.");}
     else{
      if(count>=capacity||!wsCertMethod((void*)occ,0x58)||!wsCertMethod((void*)occ,0x120)||!wsMineralPersistenceWritable((void*)occ,0x48))WS_MINERAL_PERSIST_FAIL("An exhausted native deposit cannot be safely persisted.");
      candidates[count++]=(WSMineralPersistenceCandidate){(void*)occ,(void*)def};
     }
    }
   }
   if(!wsCertCall((void*)collection,0x20,occ,0,0,&next)||next==occ)WS_MINERAL_PERSIST_FAIL("Mineral persistence occurrence enumeration did not advance.");occ=next;
  }
 }
 if(count){
  /* Use an actual already-certified mandatory1661 definition, never a new
   * definition allocation, guessed registry layout or fabricated Figure. */
  void*vt=wsCertPointer(shallow,0);uintptr_t v=(uintptr_t)vt;
  if(!shallow||!(v==(uintptr_t)g+0x21038||v==(uintptr_t)g+0x211b0||v==(uintptr_t)g+0x21328)||!wsCertNative(shallow,1,(uint32_t)(v-(uintptr_t)g),0x30,0x159d0,0x168)||!wsCertMethod(shallow,0x88))WS_MINERAL_PERSIST_FAIL("The required native shallow-iron definition is unavailable.");
  /* Finish all candidate checks before the first native setter writes. */
  for(size_t i=0;i<count;i++){
   uintptr_t actual=0,left=0;
   if(!wsCertCall(candidates[i].occurrence,0xe8,0,0,0,&actual)||(void*)actual!=candidates[i].definition||!wsCertCall(candidates[i].occurrence,0x118,1,0,0,&left)||left)WS_MINERAL_PERSIST_FAIL("A mineral candidate changed during startup validation.");
  }
  for(size_t i=0;i<count;i++){
   void*o=candidates[i].occurrence;uintptr_t result=0,left=0,reserve=0,actual=0,ident=0;
   if(!wsCertCall(o,0x58,(uintptr_t)shallow,0,0,&result)||result||!wsCertCall(o,0x118,1,0,0,&left)||left!=0x19000u)WS_MINERAL_PERSIST_FAIL("Native mineral definition conversion failed.");
   /* The native extractor can report its requested amount even if its world
    * flag rejects the write. Its return value is not a quantity certificate. */
   if(!wsCertCall(o,0x120,left,1,0,&result)||!wsCertCall(o,0x118,1,0,0,&left)||left||!wsCertCall(o,0xf8,1,0,0,&reserve)||reserve||!wsCertCall(o,0xe8,0,0,0,&actual)||(void*)actual!=shallow||!wsCertCall((void*)actual,0x88,0,0,0,&ident)||ident!=1661)WS_MINERAL_PERSIST_FAIL("Native mineral absence could not be made persistent; this world was not started.");
  }
 }
 free(candidates);return 1;
 failed:free(candidates);return 0;
 #undef WS_MINERAL_PERSIST_FAIL
}
