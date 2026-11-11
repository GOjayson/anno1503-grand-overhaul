/* Included after the unchanged chart assembler. WSDISAST is a separate native
 * root chunk, covered in full by WSCHART1's existing native-file checksum. */
static int wsDisasterSnapshot(void*world,WSDisasterContext*out){
 WSDisasterContext identity={0};if(!out)return 0;memset(out,0,sizeof *out);
 if(!wsDisasterWorld(world,&identity))return 0;
 AcquireSRWLockShared(&wsDisasterLock);
 int found=wsDisasterCurrent.active&&wsDisasterCurrent.world==world&&!wsDisasterCurrent.provisional&&
  wsDisasterCurrent.width==identity.width&&wsDisasterCurrent.height==identity.height&&!memcmp(wsDisasterCurrent.guid,identity.guid,16);
 if(found)*out=wsDisasterCurrent;ReleaseSRWLockShared(&wsDisasterLock);return found;
}
static int wsDisasterLoadContext(void*world,const WSMemoryFile*f,WSDisasterContext*out,char*error,uint32_t cap){
 if(!out||!f)return wsMemoryError(error,cap,"The saved disaster policy has no checkpoint identity.");
 memset(out,0,sizeof *out);if(!f->disaster)return 1;
 WSDisasterContext c={0};uint32_t flags=0;
 if(!wsDisasterWorld(world,&c)||c.width!=f->width||c.height!=f->height||memcmp(c.guid,f->guid,16)||
    !wsCertRead((unsigned char*)world+0x6eec,&flags,4))return wsMemoryError(error,cap,"The disaster policy belongs to a different loaded native world.");
 const unsigned char*p=f->disaster;c.master=wsU32(p+40);c.mask=wsU32(p+44);c.frequency=wsU32(p+48);c.severity=wsU32(p+52);
 if(!wsDisasterOptionsValid(c.master,c.mask,c.frequency,c.severity)||(flags&0x8eu)!=wsDisasterDisabledNative(c.master,c.mask))return wsMemoryError(error,cap,"The loaded native disaster flags differ from the saved policy.");
 c.active=1;*out=c;return 1;
}
static int wsDisasterAssembleMemory(const WSDisasterContext*c,void*world,const unsigned char*native,uint32_t size,const WSMemoryFile*base,const unsigned char*blob,uint32_t blobSize,unsigned char**out,uint32_t*outSize,char*error,uint32_t cap){
 if(!c||!c->active)return wsMemoryAssemble(native,size,base,blob,blobSize,out,outSize,error,cap);
 WSDisasterContext current={0};
 if(!wsDisasterSnapshot(world,&current)||current.world!=c->world||memcmp(current.guid,c->guid,16)||current.width!=c->width||current.height!=c->height||
    current.master!=c->master||current.mask!=c->mask||current.frequency!=c->frequency||current.severity!=c->severity||!base||base->disaster||base->chartSpan||
    base->width!=c->width||base->height!=c->height||memcmp(base->guid,c->guid,16)||size>WS_MEMORY_NATIVE_LIMIT-80u)return wsMemoryError(error,cap,"The current disaster policy changed during saving; the native save was retained.");
 uint32_t total=size+80u;unsigned char*extended=(unsigned char*)malloc(total);if(!extended)return wsMemoryError(error,cap,"Cannot allocate the bounded disaster checkpoint extension.");
 memcpy(extended,native,size);wsPut32(extended+12,total-16u);memset(extended+size,0,80);memcpy(extended+size,"WSDISAST",8);wsPut32(extended+size+12,64);
 unsigned char*p=extended+size+16;memcpy(p,"WSDISR01",8);wsPut32(p+8,1);wsPut32(p+12,64);memcpy(p+16,c->guid,16);
 wsPut32(p+32,c->width);wsPut32(p+36,c->height);wsPut32(p+40,c->master);wsPut32(p+44,c->mask);wsPut32(p+48,c->frequency);wsPut32(p+52,c->severity);
 WSMemoryFile next=*base;next.nativeSize=total;
 int ok=wsMemoryAssemble(extended,total,&next,blob,blobSize,out,outSize,error,cap);free(extended);return ok;
}
