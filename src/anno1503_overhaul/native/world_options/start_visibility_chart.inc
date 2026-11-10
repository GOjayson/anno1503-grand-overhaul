/* Native bindings for the pointer-free checkpoint core. Current read views
 * hold a single nonblocking guard; per-cell queries only read pinned scalars. */
static WSChartCore wsChartActive,wsChartStaged,wsChartFresh;
static uintptr_t wsChartWorldBinding,wsChartFreshBinding;
static volatile LONG wsChartBusy,wsChartCancelPending,wsChartFreshCancelPending,wsChartLoadIntent;
static _Thread_local WSVisibilityChartReadView*wsChartReadTLS;
static int wsChartTake(void){return InterlockedCompareExchange(&wsChartBusy,1,0)==0;}
static void wsChartGive(void){InterlockedExchange(&wsChartBusy,0);}
static int wsChartIdentity(const WSVisibilityWorld*v,unsigned char guid[16]){
 return v&&v->marked==1&&wsChShape(v->width,v->height,v->viewer,v->flags&0x7000u)&&wsCertRead(v->world+0x6e4c,guid,16);
}
static int wsChartEnsureLocked(const WSVisibilityWorld*v){
 unsigned char guid[16];if(!wsChartIdentity(v,guid))return 0;
 if(InterlockedCompareExchange(&wsChartLoadIntent,0,0)||wsFreshVisibilityCode||(wsChartFresh.bits&&!InterlockedCompareExchange(&wsChartFreshCancelPending,0,0)))return 0;
 if(wsChartActive.bits)return wsChartWorldBinding==(uintptr_t)v->world&&wsChartCoreIdentity(&wsChartActive,v->width,v->height,v->viewer,v->flags&0x7000u,guid);
 WSChartCore next={0};if(!wsChartCoreNew(&next,v->width,v->height,v->viewer,v->flags&0x7000u,guid))return 0;
 wsChartCoreFree(&wsChartActive);wsChartActive=next;wsChartWorldBinding=(uintptr_t)v->world;return 1;
}
static int wsVisibilityChartEnsure(const WSVisibilityWorld*v){
 if(wsChartReadTLS)return wsChartReadTLS->world==v->world&&wsChartReadTLS->policy==(v->flags&0x7000u);
 if(!wsChartTake())return 0;int result=wsChartEnsureLocked(v);wsChartGive();return result;
}
static int wsVisibilityChartReadBegin(const WSVisibilityWorld*v,WSVisibilityChartReadView*out){
 if(!v||!out)return 0;memset(out,0,sizeof(*out));
 if(wsChartReadTLS){
  if(wsChartReadTLS->world!=v->world||wsChartReadTLS->width!=v->width||wsChartReadTLS->height!=v->height||wsChartReadTLS->viewer!=v->viewer||wsChartReadTLS->policy!=(v->flags&0x7000u))return 0;
  *out=*wsChartReadTLS;out->owned=0;out->previous=wsChartReadTLS;wsChartReadTLS=out;return 1;
 }
 if(!wsVisibilityChartEnsure(v)||!wsChartTake())return 0;
 if(!wsChartEnsureLocked(v)){wsChartGive();return 0;}
 out->core=&wsChartActive;out->world=v->world;out->width=v->width;out->height=v->height;out->viewer=v->viewer;out->policy=v->flags&0x7000u;out->generation=wsChartActive.generation;out->owned=1;wsChartReadTLS=out;return 1;
}
static void wsVisibilityChartReadEnd(WSVisibilityChartReadView*view){
 if(!view||wsChartReadTLS!=view){InterlockedExchange(&wsVisibilityLastError,12);return;}
 wsChartReadTLS=view->previous;int owned=view->owned;memset(view,0,sizeof(*view));if(owned)wsChartGive();
}
static int wsVisibilityChartPoint(const WSVisibilityWorld*v,float x,float z){
 const WSVisibilityChartReadView*r=wsChartReadTLS;
 return v&&r&&r->world==v->world&&r->width==v->width&&r->height==v->height&&r->viewer==v->viewer&&r->policy==(v->flags&0x7000u)&&wsChartCorePoint(r->core,x,z);
}
static const WSChartCore*wsVisibilityChartReadSnapshot(const WSVisibilityWorld*v){
 const WSVisibilityChartReadView*r=wsChartReadTLS;return v&&r&&r->world==v->world&&r->width==v->width&&r->height==v->height&&r->viewer==v->viewer&&r->policy==(v->flags&0x7000u)?r->core:0;
}
static int wsVisibilityChartMarkContext(const WSVisibilityDrawContext*c){
 const WSChartCore*read=wsVisibilityChartReadSnapshot(&c->view);if(!read||read->bitBytes>8192u)return 0;
 unsigned char bits[8192];memcpy(bits,read->bits,read->bitBytes);WSChartCore marked=*read;marked.bits=bits;
 for(uint32_t n=0;n<c->visionCount;n++)if(!wsChartCoreMark(&marked,c->vision[n].left,c->vision[n].top,c->vision[n].right,c->vision[n].bottom))return 0;
 if(memcmp(bits,wsChartActive.bits,read->bitBytes)){memcpy(wsChartActive.bits,bits,read->bitBytes);wsChartCoreChanged(&wsChartActive);wsVisibilityRenderMemo.valid=0;}return 1;
}
static int wsVisibilityChartSaveBlob(unsigned char**out,uint32_t*size,char*error,uint32_t cap){
 if(!out||!size)return wsChError(error,cap,"Invalid exploration snapshot output.");
 if(!wsChartTake())return wsChError(error,cap,"Exploration memory is busy.");
 if(InterlockedCompareExchange(&wsChartLoadIntent,0,0)||wsFreshVisibilityCode||(wsChartFresh.bits&&!InterlockedCompareExchange(&wsChartFreshCancelPending,0,0))){wsChartGive();return wsChError(error,cap,"An exploration load or fresh-world commit is pending.");}
 int result=wsChartWorldBinding?wsChartCoreEncode(&wsChartActive,out,size,error,cap):wsChError(error,cap,"No active mod exploration checkpoint.");wsChartGive();return result;
}
static int wsVisibilityChartStageBlob(const void*data,uint32_t size,char*error,uint32_t cap){
 WSChartCore next={0};if((!data&&size)||(data&&!size))return wsChError(error,cap,"Invalid exploration payload.");
 if(data&&!wsChartCoreDecode(data,size,&next,error,cap))return 0;
 if(!wsChartTake()){wsChartCoreFree(&next);return wsChError(error,cap,"Exploration memory is busy.");}
 wsChartCoreFree(&wsChartStaged);wsChartStaged=next;InterlockedExchange(&wsChartCancelPending,0);InterlockedExchange(&wsChartLoadIntent,1);wsChartGive();return 1;
}
static int wsVisibilityChartApplyBlob(void*world,char*error,uint32_t cap){
 WSVisibilityWorld view;unsigned char guid[16];
 if(!wsVisibilityWorldRead(world,&view)||!wsChartIdentity(&view,guid))return wsChError(error,cap,"Invalid exploration checkpoint World.");
 if(!wsChartTake())return wsChError(error,cap,"Exploration memory is busy.");
 if(!InterlockedCompareExchange(&wsChartLoadIntent,0,0)){wsChartGive();return wsChError(error,cap,"No exploration load checkpoint is pending.");}
 if(InterlockedExchange(&wsChartCancelPending,0))wsChartCoreFree(&wsChartStaged);
 int result=0;
 if(!wsChartStaged.bits){
  /* A successful load without an extension is an explicit empty checkpoint,
   * even if the allocator reused the same World address and native GUID. */
  WSChartCore empty={0};if(wsChartCoreNew(&empty,view.width,view.height,view.viewer,view.flags&0x7000u,guid)){
   wsChartCoreFree(&wsChartActive);wsChartActive=empty;wsChartWorldBinding=(uintptr_t)world;wsVisibilityChartTransientReset();result=1;
  }
 }
 else if(wsChartCoreIdentity(&wsChartStaged,view.width,view.height,view.viewer,view.flags&0x7000u,guid)){
  wsChartCoreFree(&wsChartActive);wsChartActive=wsChartStaged;memset(&wsChartStaged,0,sizeof wsChartStaged);wsChartWorldBinding=(uintptr_t)world;wsVisibilityChartTransientReset();result=1;
 }else wsMessage(error,cap,"Exploration checkpoint identity differs from this save.");
 if(result)InterlockedExchange(&wsChartLoadIntent,0);wsChartGive();return result;
}
static void wsVisibilityChartCancelBlob(void){
 InterlockedExchange(&wsChartCancelPending,1);InterlockedExchange(&wsChartLoadIntent,0);if(!wsChartTake())return;
 wsChartCoreFree(&wsChartStaged);InterlockedExchange(&wsChartCancelPending,0);wsChartGive();
}
static int wsVisibilityChartPrepareFresh(const WSVisibilityWorld*v,char*error,uint32_t cap){
 unsigned char guid[16];WSChartCore fresh={0};
 if(!wsChartIdentity(v,guid)||!wsChartCoreNew(&fresh,v->width,v->height,v->viewer,v->flags&0x7000u,guid))return wsChError(error,cap,"Cannot initialize fresh exploration memory.");
 if(!wsChartTake()){wsChartCoreFree(&fresh);return wsChError(error,cap,"Exploration memory is busy.");}
 wsChartCoreFree(&wsChartFresh);wsChartFresh=fresh;wsChartFreshBinding=(uintptr_t)v->world;InterlockedExchange(&wsChartFreshCancelPending,0);wsChartGive();return 1;
}

typedef struct WSChartFigure {uint32_t x,z,width,height,island;uint16_t logical;unsigned char rootCode,owner;} WSChartFigure;
typedef struct WSChartFrameProof {
 void*frame,*vtable,*c8;uint16_t frames,period;void*array,*texture,*textureVT,*palette,*paletteVT,*colorGetter,*dataGetter,*shiftGetter,*formatGetter;uint32_t textureOffset,colorSelector,paletteShift,paletteBanks,formatOffset,formatBytes,format;
} WSChartFrameProof;
typedef struct WSChartAssetProof {struct WSChartAssetProof*next;void*definition,*vtable;unsigned char width,height;int level;uint32_t id;WSChartFrameProof frames[4];} WSChartAssetProof;
static int wsChartColorChain(const WSVisibilityDrawContext*c,WSChartFrameProof*p){
 unsigned char*d=c->fast->display;p->array=wsCertPointer(p->frame,0x18);p->texture=wsCertPointer(p->array,0);p->textureVT=wsCertPointer(p->texture,0);
 static const uint32_t first[]={0xf65a50u,0xf65ba8u,0xf65d00u,0xf65e58u},second[]={0xf65fc8u,0xf66138u};
 int group=0;for(size_t n=0;n<sizeof first/sizeof first[0];n++)if(p->textureVT==d+first[n])group=1;for(size_t n=0;n<sizeof second/sizeof second[0];n++)if(p->textureVT==d+second[n])group=2;
 if(!group||!wsCertMemory(p->array,8,0)||!wsCertMemory(p->texture,group==1?0x20u:0x28u,0)||wsCertPointer(p->textureVT,0xc0)!=d+(group==1?0x3b200u:0x185a0u))return 0;
 int haus=p->textureVT==d+0xf65d00u||p->textureVT==d+0xf65e58u;
 p->formatOffset=group==2?0xcu:0xau;p->formatBytes=haus?1u:2u;p->formatGetter=d+(group==2?0x5f580u:(haus?0x5fc80u:0x5f620u));
 if(wsCertPointer(p->textureVT,0xe0)!=p->formatGetter)return 0;p->format=0;memcpy(&p->format,(unsigned char*)p->texture+p->formatOffset,p->formatBytes);
 p->textureOffset=group==1?0x18u:0x20u;p->palette=wsCertPointer(p->texture,p->textureOffset);p->paletteVT=wsCertPointer(p->palette,0);if(!wsCertMemory(p->palette,8,0))return 0;
 static const uint32_t tables[]={0xf5f648u,0xf5f750u,0xf5f860u,0xf5f968u,0xf5fa70u,0xf5fb78u,0xf5fc80u,0xf5fd88u,0xf5fe90u};
 static const uint32_t getters[]={0x17540u,0x244c0u,0x244c0u,0x24ef0u,0x24ef0u,0x25a30u,0x25a30u,0x25a30u,0x25a30u};
 static const uint32_t selectors[]={0,3,3,27,27,9,9,9,9},shifts[]={8,8,8,8,8,3,3,4,4},banks[]={0,3,3,27,27,96,96,144,144};
 for(size_t n=0;n<sizeof tables/sizeof tables[0];n++)if(p->paletteVT==d+tables[n]){
  p->colorGetter=d+getters[n];p->colorSelector=selectors[n];p->paletteShift=shifts[n];p->paletteBanks=banks[n];p->dataGetter=d+(n?0x24d60u:0x24420u);p->shiftGetter=d+(shifts[n]==8u?0x243f0u:(shifts[n]==3u?0x244c0u:0x260a0u));
  if(wsCertPointer(p->paletteVT,0xf8)!=p->colorGetter||wsCertPointer(p->paletteVT,0xd0)!=p->dataGetter||wsCertPointer(p->paletteVT,0xe8)!=p->shiftGetter)return 0;
  return p->format==23u||(p->paletteBanks&&wsCertMemory(p->palette,0x410u+(size_t)p->paletteBanks*1024u,0));
 }
 return 0;
}
static int wsChartAssetCurrent(const WSVisibilityDrawContext*c,const WSChartAssetProof*p,uint16_t id,int full){
 WSVisibilityFastDraw*f=c->fast;unsigned char*g=f->game,*d=f->display;
 if(p->id!=id||wsVisibilityFastPointer(c->view.world,0x200)!=f->catalogue||wsVisibilityFastPointer(f->catalogue,0)!=f->catalogueVT||wsVisibilityFastPointer(f->catalogueVT,0xe8)!=g+0xb4d0u||wsVisibilityFastPointer(f->catalogue,0x218u+id*8u)!=p->definition||wsVisibilityFastPointer(p->definition,0)!=p->vtable||
    wsVisibilityFastPointer(p->vtable,0x150)!=(p->vtable==g+0x1f888u?g+0x41d0u:g+0x5950u))return 0;
 if(p->vtable==g+0x1f888u)return wsVisibilityFastPointer(p->vtable,0x108)==g+0x1120u&&wsVisibilityFastPointer(p->vtable,0x148)==g+0x41d0u;
 if(wsVisibilityFastPointer(p->vtable,0x108)!=g+0x1120u||wsVisibilityFastPointer(p->vtable,0x148)!=g+0x57a0u||((unsigned char*)p->definition)[0xa]!=p->width||((unsigned char*)p->definition)[0xb]!=p->height)return 0;
 for(uint32_t n=0;n<4;n++){
  const WSChartFrameProof*r=p->frames+n;if(wsVisibilityFastPointer(p->definition,0x268u+n*24u)!=r->frame)return 0;if(!r->frame)continue;
  if(wsVisibilityFastPointer(r->frame,0)!=r->vtable||wsVisibilityFastPointer(r->vtable,0xc8)!=r->c8)return 0;
  uint16_t frames=0,period=0;memcpy(&frames,(unsigned char*)r->frame+0x38,2);if(frames!=r->frames||(!frames&&(r->vtable!=d+0xf609d0u||r->c8!=d+0x17540u||wsVisibilityFastPointer(r->vtable,0xe0)!=d+0x17540u)))return 0;
  if(r->c8==d+0x277a0u)memcpy(&period,(unsigned char*)r->frame+0x40,2);if(period!=r->period)return 0;
  if(full&&period){
   if(period<2u||p->level<2||wsVisibilityFastPointer(r->vtable,0xd8)!=d+0x33880u||wsVisibilityFastPointer(r->vtable,0xf8)!=d+0x324f0u||
      wsVisibilityFastPointer(r->frame,0x18)!=r->array||wsVisibilityFastPointer(r->array,0)!=r->texture||wsVisibilityFastPointer(r->texture,0)!=r->textureVT||
      wsVisibilityFastPointer(r->textureVT,0xc0)!=d+(r->textureOffset==0x18u?0x3b200u:0x185a0u)||wsVisibilityFastPointer(r->textureVT,0xe0)!=r->formatGetter||wsVisibilityFastPointer(r->texture,r->textureOffset)!=r->palette||wsVisibilityFastPointer(r->palette,0)!=r->paletteVT||wsVisibilityFastPointer(r->paletteVT,0xf8)!=r->colorGetter||wsVisibilityFastPointer(r->paletteVT,0xd0)!=r->dataGetter||wsVisibilityFastPointer(r->paletteVT,0xe8)!=r->shiftGetter)return 0;
   uint32_t format=0;memcpy(&format,(unsigned char*)r->texture+r->formatOffset,r->formatBytes);if(format!=r->format)return 0;
  }
 }return 1;
}
static inline int wsChartAssetGuard(const WSVisibilityDrawContext*c,uint16_t id,int full){
 if(!c->fast||!c->fast->catalogueReady||id>=4000u)return 0;WSVisibilityFastDraw*f=c->fast;unsigned char*g=f->game,*d=f->display;
 WSChartAssetProof*p=(WSChartAssetProof*)f->chartAssets[id];if(p&&p->level>=(full?2:1))return wsChartAssetCurrent(c,p,id,full);
 if(p&&!wsChartAssetCurrent(c,p,id,0))return 0;
 if(!p){
  p=(WSChartAssetProof*)calloc(1,sizeof(*p));if(!p)return 0;p->id=id;p->definition=f->definitions[id];p->vtable=wsCertPointer(p->definition,0);
  if(!p->definition||(p->vtable!=g+0x1f888u&&p->vtable!=g+0x1fac8u&&p->vtable!=g+0x1fcf8u)||!wsCertMemory(p->definition,p->vtable==g+0x1f888u?0x20fu:0x2c8u,0)||wsCertPointer(p->vtable,0x108)!=g+0x1120u||wsCertPointer(p->vtable,0x148)!=(p->vtable==g+0x1f888u?g+0x41d0u:g+0x57a0u)||wsCertPointer(p->vtable,0x150)!=(p->vtable==g+0x1f888u?g+0x41d0u:g+0x5950u))goto failed;
  if(p->vtable!=g+0x1f888u){
   p->width=((unsigned char*)p->definition)[0xa];p->height=((unsigned char*)p->definition)[0xb];
   if(!p->width||!p->height||p->width>32u||p->height>32u||wsCertPointer(p->vtable,0x108)!=g+0x1120u||wsCertPointer(p->vtable,0x148)!=g+0x57a0u)goto failed;
   for(uint32_t n=0;n<4;n++){
    WSChartFrameProof*r=p->frames+n;r->frame=wsCertPointer(p->definition,0x268u+n*24u);if(!r->frame)continue;r->vtable=wsCertPointer(r->frame,0);r->c8=wsCertPointer(r->vtable,0xc8);
    if(!wsVisibilityWithinModule(d,r->vtable,0x100u)||(r->c8!=d+0x17540u&&r->c8!=d+0x277a0u)||!wsCertMemory(r->frame,r->c8==d+0x277a0u?0x48u:0x40u,0))goto failed;
    memcpy(&r->frames,(unsigned char*)r->frame+0x38,2);if(!r->frames&&(r->vtable!=d+0xf609d0u||r->c8!=d+0x17540u||wsCertPointer(r->vtable,0xe0)!=d+0x17540u))goto failed;if(r->c8==d+0x277a0u)memcpy(&r->period,(unsigned char*)r->frame+0x40,2);
   }
  }
  p->next=(WSChartAssetProof*)f->chartAssetList;f->chartAssetList=p;f->chartAssets[id]=p;p->level=1;
 }
 if(full&&p->level<2){
  /* Native Game57A0 accepts C8==0 while5950 skips it. Period0 therefore
   * submits only ordinary C0|base0/1 flags; C53/raw visual6 needs period>=2. */
  for(uint32_t n=0;n<4;n++)if(p->frames[n].frame&&p->frames[n].period){WSChartFrameProof*r=p->frames+n;if(r->period<2u||wsCertPointer(r->vtable,0xd8)!=d+0x33880u||wsCertPointer(r->vtable,0xf8)!=d+0x324f0u||!wsChartColorChain(c,r))return 0;}
  p->level=2;
 }return wsChartAssetCurrent(c,p,id,full);
 failed:free(p);return 0;
}
static void wsVisibilityChartReleaseAssets(WSVisibilityFastDraw*f){
 WSChartAssetProof*p=f?(WSChartAssetProof*)f->chartAssetList:0;while(p){WSChartAssetProof*next=p->next;free(p);p=next;}
 if(f){f->chartAssetList=0;memset(f->chartAssets,0,sizeof f->chartAssets);}
}
static int wsChartCellAssets(const WSVisibilityDrawContext*c,const unsigned char*visual,unsigned char renderFlag){
 if(!(visual[3]&0x40u))return 1;uint16_t id;memcpy(&id,visual,2);
 if(renderFlag>1u||visual[5]!=0xc0u||visual[7]||!wsChartAssetGuard(c,id,1))return 0;
 const WSChartAssetProof*p=(const WSChartAssetProof*)c->fast->chartAssets[id];
 for(uint32_t n=0;n<4;n++){if(p->frames[n].frame&&p->frames[n].period){
  const WSChartFrameProof*r=p->frames+n;uint32_t ordinary=((uint32_t)renderFlag<<8)|visual[5];
  uint32_t color=(r->colorSelector>4u?((uint32_t)visual[6]<<8):0u)|visual[5];
  if(r->format!=23u&&(!r->paletteBanks||(ordinary>>r->paletteShift)>=r->paletteBanks||(color>>r->paletteShift)>=r->paletteBanks))return 0;
 }}return 1;
}
typedef struct WSChartObservedQuad {uint32_t index;unsigned char bytes[0x390];} WSChartObservedQuad;
typedef struct WSChartPendingQuad {uint32_t index;WSChartCell cells[64];} WSChartPendingQuad;
typedef struct WSChartObservation {
 const WSVisibilityDrawContext*context;uint32_t*quadMap,*pendingMap;unsigned char*visited,*roots,*oldRoots,*bits;
 WSChartObservedQuad*quads;WSChartPendingQuad*pending;uint32_t quadCount,quadCapacity,pendingCount,pendingCapacity;
} WSChartObservation;
typedef void (__cdecl*WSChartNativeProducer)(void*,void*,uint32_t,uint32_t,void*);
#ifndef WS_CHART_NATIVE_PRODUCER
#define WS_CHART_NATIVE_PRODUCER(module) ((WSChartNativeProducer)((module)+0xc9400u))
#endif
static int wsChartGrow(void**data,uint32_t*capacity,uint32_t used,size_t stride,uint32_t maximum){
 if(used<*capacity)return 1;uint32_t next=*capacity?*capacity*2u:16u;if(next>*capacity&&next>maximum)next=maximum;
 if(next<=used||stride>SIZE_MAX/next)return 0;void*p=realloc(*data,(size_t)next*stride);if(!p)return 0;*data=p;*capacity=next;return 1;
}
static int wsChartSeenBox(const WSVisibilityDrawContext*c,float left,float top,float right,float bottom){
 for(uint32_t n=0;n<c->visionCount;n++){
  const WSVisibilityVisionSource*s=c->vision+n;float dx=right<s->left?s->left-right:(left>s->right?left-s->right:0),dz=bottom<s->top?s->top-bottom:(top>s->bottom?top-s->bottom:0);
  if(dx*dx+dz*dz<=2304.0f)return 1;
 }return 0;
}
static int wsChartFigureShape(const WSVisibilityDrawContext*c,uint32_t x,uint32_t z,uint16_t logical,unsigned char rootCode,uint32_t island,unsigned char owner,WSChartFigure*out){
 WSVisibilityFastDefinition*d=wsVisibilityFastDefinitionRead(c,logical);if(!d||d->state<0||!d->mainClass)return 0;
 unsigned char*object=(unsigned char*)d->object;uint32_t dx=rootCode&7u,dz=(rootCode>>3)&7u;if(x<dx||z<dz)return 0;
 uint32_t w=object[0xa],h=object[0xb];if((rootCode>>6)&1u){uint32_t swap=w;w=h;h=swap;}
 x-=dx;z-=dz;if(!w||!h||x+w>c->view.width||z+h>c->view.height)return 0;
 *out=(WSChartFigure){x,z,w,h,island,logical,(unsigned char)(rootCode&0xc0u),owner};return 1;
}
static int wsChartCurrentFigure(const WSVisibilityDrawContext*c,const WSVisibilityIsland*island,uint32_t x,uint32_t z,WSChartFigure*out){
 void*owner=0;int owned=wsVisibilityOwnedBuilding(c,island,(float)x,(float)z,&owner);if(owned<0)return -1;if(!owned)return 0;
 if(!c->fast||!c->fast->islands[island->id].ready)return -1;
 const WSVisibilityFastIsland*s=c->fast->islands+island->id;uint32_t words[2];memcpy(words,s->tiles+((size_t)(z-island->y)*island->width+x-island->x)*8u,8);
 uint32_t ownerID=0;memcpy(&ownerID,(unsigned char*)owner+8,4);if(ownerID>=32u)return -1;
 return wsChartFigureShape(c,x,z,(uint16_t)words[0],(unsigned char)(words[0]>>16),island->id,(unsigned char)ownerID,out)?1:-1;
}
static int wsChartSameFigure(const WSChartFigure*a,const WSChartFigure*b){return a->x==b->x&&a->z==b->z&&a->logical==b->logical&&a->rootCode==b->rootCode&&a->owner==b->owner;}
static int wsChartCachedFigure(const WSVisibilityDrawContext*c,uint32_t x,uint32_t z,const WSChartCell*cell,WSChartFigure*out){
 if(!(cell->flags&WS_CHART_BUILDING))return 0;const WSVisibilityIsland*island=wsVisibilityIslandAt(c,(float)x,(float)z);if(!island)return -1;
 return wsChartFigureShape(c,x,z,cell->logical,cell->rootCode,island->id,cell->owner,out)?1:-1;
}
/* Guard every node and optional property5 chunk that the exact native copy
 * producer may follow. Unknown linked-node classes never reach virtual calls. */
static int wsChartProducerGuard(const WSVisibilityDrawContext*c,const WSVisibilityIsland*p,uint32_t x,uint32_t z){
 uint32_t shape[2];void*nodes=0;
 if(!c||!p||p->id>=WS_VISIBILITY_ISLAND_LIMIT||x>c->view.width-8u||z>c->view.height-8u||x<p->x||z<p->y||x+8u>p->x+p->width||z+8u>p->y+p->height||
    wsVisibilityFastPointer(c->view.world,0x6640u+p->id*8u)!=p->object||!wsCertMemory(p->object,0x148u,0)||wsVisibilityFastPointer(p->object,0x38)!=c->view.world||
    !c->fast||!c->fast->islands[p->id].ready||wsVisibilityFastPointer(p->object,0x10)!=c->fast->islands[p->id].tiles||
    !wsCertRead(p->object+0x110,shape,8)||shape[0]!=p->width/8u||shape[1]!=p->height/8u||
    !(nodes=wsCertPointer(p->object,0x118))||!wsCertMemory(nodes,(size_t)shape[0]*shape[1]*24u,0)||
    !wsCertMemory(p->object+0x138,16,0))return 0;
 uint32_t qx=(x-p->x)>>3,qz=(z-p->y)>>3;unsigned char*node=(unsigned char*)nodes+((size_t)qz*shape[0]+qx)*24u;
 unsigned char header[24];if(!wsCertRead(node,header,sizeof header)||header[0]!=qx||header[1]!=qz)return 0;
 void*chunk=0;
 if(header[8]&0x20u){void*at=0;memcpy(&at,header+0x10,8);void*seen[256];uint32_t count=0;
 while(at){
  if(count==256u||!wsCertMemory(at,0x238,0)||wsCertPointer(at,0)!=c->view.module+0xf33b8u||wsCertPointer(c->view.module+0xf33b8u,8)!=c->view.module+0x35210u)return 0;
  for(uint32_t n=0;n<count;n++)if(seen[n]==at)return 0;seen[count++]=at;
  unsigned char kind=0;if(!wsCertRead((unsigned char*)at+0x230,&kind,1))return 0;if(kind==5u){chunk=at;break;}at=wsCertPointer(at,8);
 }}
 if(!c->fast||!c->fast->islands[p->id].ready)return 0;
 for(uint32_t dz=0;dz<8;dz++)for(uint32_t dx=0;dx<8;dx++){
  uint32_t words[2];const unsigned char*source=chunk?(unsigned char*)chunk+0x14u+(dz*8u+dx)*8u:
   c->fast->islands[p->id].tiles+((size_t)(z+dz-p->y)*p->width+x+dx-p->x)*8u;
  memcpy(words,source,8);if(!chunk&&(words[1]&0x80000000u))continue;
  if((words[0]&0x80000000u)&&!wsChartAssetGuard(c,(uint16_t)words[0],0))return 0;
 }
 return 1;
}
static WSChartObservedQuad*wsChartObserved(WSChartObservation*o,uint32_t x,uint32_t z,uint32_t island){
 const WSVisibilityDrawContext*c=o->context;uint32_t index=(z>>3)*(c->view.width>>3)+(x>>3),slot=o->quadMap[index];
 if(slot)return o->quads+slot-1u;
 if(!c->fast||!c->fast->catalogueReady||!wsChartProducerGuard(c,c->islands+island,x&~7u,z&~7u)||
    !wsChartGrow((void**)&o->quads,&o->quadCapacity,o->quadCount,sizeof(*o->quads),(c->view.width>>3)*(c->view.height>>3)))return 0;
 WSChartObservedQuad*q=o->quads+o->quadCount;memset(q,0,sizeof(*q));q->index=index;memcpy(q->bytes,&c->fast->catalogue,8);
 void*viewFlags=wsCertPointer(c->view.world,0x238);uint32_t baseFlags=0;
 if(!viewFlags||!wsCertMemory(viewFlags,12,0)||wsCertPointer(viewFlags,0)!=c->view.module+0xfa148u||!wsCertRead((unsigned char*)viewFlags+8,&baseFlags,4))return 0;
 unsigned char row[88]={0};uint16_t xy[2]={(uint16_t)(x&~15u),(uint16_t)(z&~15u)};memcpy(row,xy,4);memset(row+0x38,255,4);uint32_t quadrant=((x>>3)&1u)|(((z>>3)&1u)<<1);row[0x38+quadrant]=(unsigned char)island;row[0x4d]=(unsigned char)(1u<<quadrant);
 WS_CHART_NATIVE_PRODUCER(c->view.module)(c->view.world,row,quadrant,0,q->bytes);
 /* C8E10's remaining bits are transient selection/territory overlays, not
  * enemy observations. Remember only its uniform native base-render bit. */
 memset(q->bytes+0x34c,(int)(baseFlags&1u),64);
 void*header=0;memcpy(&header,q->bytes,8);if(header!=c->fast->catalogue)return 0;
 o->quadMap[index]=++o->quadCount;return q;
}
static WSChartCell*wsChartPending(WSChartObservation*o,uint32_t x,uint32_t z){
 uint32_t width=o->context->view.width,index=(z>>3)*(width>>3)+(x>>3),slot=o->pendingMap[index];
 if(!slot){
  if(!wsChartGrow((void**)&o->pending,&o->pendingCapacity,o->pendingCount,sizeof(*o->pending),(width>>3)*(width>>3)))return 0;
  WSChartPendingQuad*q=o->pending+o->pendingCount;q->index=index;uint32_t baseX=x&~7u,baseZ=z&~7u;
  for(uint32_t row=0;row<8;row++)memcpy(q->cells+row*8,wsChartActive.cells+(size_t)(baseZ+row)*width+baseX,8*sizeof(WSChartCell));
  slot=++o->pendingCount;o->pendingMap[index]=slot;
 }return o->pending[slot-1u].cells+((z&7u)*8u+(x&7u));
}
static int wsChartClearFigure(WSChartObservation*o,const WSChartFigure*f){
 uint32_t width=o->context->view.width;WSChartCell empty={{0},0,0,WS_CHART_OBSERVED,0,0,0,0};
 for(uint32_t z=f->z;z<f->z+f->height;z++)for(uint32_t x=f->x;x<f->x+f->width;x++){
  const WSChartCell*old=wsChartActive.cells+(size_t)z*width+x;WSChartFigure other;
  if(!(old->flags&WS_CHART_BUILDING))continue;int known=wsChartCachedFigure(o->context,x,z,old,&other);if(known<0)return 0;
  if(known&&wsChartSameFigure(f,&other)){WSChartCell*at=wsChartPending(o,x,z);if(!at)return 0;*at=empty;}
 }
 return 1;
}
static int wsChartCaptureFigure(WSChartObservation*o,const WSChartFigure*f,uint32_t time){
 const WSVisibilityDrawContext*c=o->context;const WSVisibilityIsland*p=c->islands+f->island;
 if(f->x<p->x||f->z<p->y||f->x+f->width>p->x+p->width||f->z+f->height>p->y+p->height)return 0;
 for(uint32_t z=f->z;z<f->z+f->height;z++)for(uint32_t x=f->x;x<f->x+f->width;x++){
  WSChartFigure current;int owned=wsChartCurrentFigure(c,p,x,z,&current);if(owned<0)return 0;if(!owned||!wsChartSameFigure(f,&current))continue;
  WSChartObservedQuad*q=wsChartObserved(o,x,z,f->island);if(!q)return 0;uint32_t cell=(z&7u)*8u+(x&7u);WSChartCell*record=wsChartPending(o,x,z);if(!record)return 0;
  memset(record,0,sizeof(*record));memcpy(record->visual,q->bytes+8u+cell*8u,8);record->renderFlag=q->bytes[0x34cu+cell];record->owner=f->owner;record->flags=WS_CHART_OBSERVED|WS_CHART_BUILDING;
  if(q->bytes[0x38c]&(1u<<(z&7u)))record->flags|=WS_CHART_ANIMATED;
  record->rootCode=(unsigned char)(f->rootCode|(x-f->x)|((z-f->z)<<3));record->logical=f->logical;record->time=time;
  if(!wsChartCellValid(record)||!wsChartCellAssets(c,record->visual,record->renderFlag))return 0;
 }
 return 1;
}
static void wsChartObservationFree(WSChartObservation*o){free(o->quadMap);free(o->pendingMap);free(o->visited);free(o->roots);free(o->oldRoots);free(o->bits);free(o->quads);free(o->pending);}
static int wsChartObserve(WSVisibilityDrawContext*c,uint32_t time){
 WSChartObservation o={0};o.context=c;uint32_t quadCount=(c->view.width>>3)*(c->view.height>>3),visitedBytes=(wsChartActive.count+7u)>>3;
 o.bits=(unsigned char*)malloc(wsChartActive.bitBytes);o.quadMap=(uint32_t*)calloc(quadCount,4);o.pendingMap=(uint32_t*)calloc(quadCount,4);
 o.visited=(unsigned char*)calloc(visitedBytes,1);o.roots=(unsigned char*)calloc(visitedBytes,1);o.oldRoots=(unsigned char*)calloc(visitedBytes,1);
 if(!o.bits||!o.quadMap||!o.pendingMap||!o.visited||!o.roots||!o.oldRoots){wsChartObservationFree(&o);return 0;}
 memcpy(o.bits,wsChartActive.bits,wsChartActive.bitBytes);WSChartCore marked=wsChartActive;marked.bits=o.bits;
 for(uint32_t n=0;n<c->visionCount;n++)if(!wsChartCoreMark(&marked,c->vision[n].left,c->vision[n].top,c->vision[n].right,c->vision[n].bottom)){wsChartObservationFree(&o);return 0;}
 if(!c->view.enemy)for(uint32_t island=0;island<WS_VISIBILITY_ISLAND_LIMIT;island++)if(c->present[island]){
  const WSVisibilityIsland*p=c->islands+island;
  for(uint32_t source=0;source<c->visionCount;source++){
   const WSVisibilityVisionSource*s=c->vision+source;int32_t x0=(int32_t)(s->left-48),z0=(int32_t)(s->top-48),x1=(int32_t)(s->right+48),z1=(int32_t)(s->bottom+48);
   if(x0<(int32_t)p->x)x0=(int32_t)p->x;if(z0<(int32_t)p->y)z0=(int32_t)p->y;if(x1>=(int32_t)(p->x+p->width))x1=(int32_t)(p->x+p->width)-1;if(z1>=(int32_t)(p->y+p->height))z1=(int32_t)(p->y+p->height)-1;
   for(int32_t z=z0;z<=z1;z++)for(int32_t x=x0;x<=x1;x++){
    uint32_t index=(uint32_t)z*c->view.width+(uint32_t)x;unsigned char bit=(unsigned char)(1u<<(index&7u));if(o.visited[index>>3]&bit)continue;o.visited[index>>3]|=bit;
    if(!wsChartSeenBox(c,(float)x,(float)z,(float)x+1,(float)z+1))continue;
    const WSChartCell*old=wsChartActive.cells+index;
    if(old->flags&WS_CHART_BUILDING){
     WSChartFigure prior,current;int known=wsChartCachedFigure(c,(uint32_t)x,(uint32_t)z,old,&prior);if(known<0)goto invalid;
     if(known){uint32_t anchor=prior.z*c->view.width+prior.x;unsigned char mask=(unsigned char)(1u<<(anchor&7u));if(!(o.oldRoots[anchor>>3]&mask)){
      o.oldRoots[anchor>>3]|=mask;int now=wsChartCurrentFigure(c,p,prior.x,prior.z,&current);if(now<0)goto invalid;
      if(!now||!wsChartSameFigure(&prior,&current))if(!wsChartClearFigure(&o,&prior))goto invalid;
     }}
    }
    WSChartFigure current;int owned=wsChartCurrentFigure(c,p,(uint32_t)x,(uint32_t)z,&current);if(owned<0)goto invalid;if(!owned)continue;
    uint32_t anchor=current.z*c->view.width+current.x;unsigned char mask=(unsigned char)(1u<<(anchor&7u));if(o.roots[anchor>>3]&mask)continue;o.roots[anchor>>3]|=mask;
    if(!wsChartCaptureFigure(&o,&current,time))goto invalid;
   }
  }
 }
 if(memcmp(wsChartActive.bits,o.bits,wsChartActive.bitBytes)){memcpy(wsChartActive.bits,o.bits,wsChartActive.bitBytes);wsChartCoreChanged(&wsChartActive);wsVisibilityRenderMemo.valid=0;}
 for(uint32_t n=0;n<o.pendingCount;n++){
  WSChartPendingQuad*q=o.pending+n;uint32_t x=(q->index%(c->view.width>>3))*8,z=(q->index/(c->view.width>>3))*8;
  for(uint32_t row=0;row<8;row++)memcpy(wsChartActive.cells+(size_t)(z+row)*c->view.width+x,q->cells+row*8,8*sizeof(WSChartCell));
 }
 wsChartObservationFree(&o);return 1;
 invalid:wsChartObservationFree(&o);return 0;
}

typedef struct WSChartGhost {
 void*frame;const WSChartAssetProof*asset;uint32_t assetId,xyz[3],orientation,kind,phase,flags;unsigned char used;
} WSChartGhost;
typedef struct WSChartCopy {
 struct WSChartCopy*next;unsigned char*row;void*original;uint32_t rowIndex;uint16_t x,z;unsigned char quadrant,island;
 uintptr_t renderer;int quarantined;unsigned char bytes[0x390];
} WSChartCopy;
typedef struct WSChartDraw {
 void*list,*renderer;uint32_t rows;WSChartCopy*copies;WSChartGhost*ghosts;uint32_t ghostCount,ghostCapacity;
 int installed,started,failed,captureKind;uint32_t renderMode;const WSVisibilityDrawContext*captureContext;const unsigned char*captureQuad;void*captureVtable[0x190/8];void*captureObject[2];
} WSChartDraw;
static WSChartCopy*wsChartRetiredCopies;static size_t wsChartRetiredBytes;
#define WS_CHART_COPY_LIMIT (96u*1024u*1024u)
typedef void (__cdecl*WSChartNativeStatic)(void*,const uint16_t*,uint32_t,void*);
typedef void (__cdecl*WSChartNativeColor)(void*,const uint16_t*,uint32_t,uint32_t,void*);
#ifndef WS_CHART_NATIVE_STATIC
#define WS_CHART_NATIVE_STATIC(module,kind) ((WSChartNativeStatic)((module)+((kind)==1?0xc4a60u:((kind)==2?0xc4da0u:0xc50b0u))))
#define WS_CHART_NATIVE_COLOR(module) ((WSChartNativeColor)((module)+0xc53f0u))
#endif
static uint32_t wsChartGhostHash(void*frame,uint32_t orientation,uint32_t kind,const uint32_t xyz[3],uint32_t flags){
 uintptr_t p=(uintptr_t)frame;uint32_t n=(uint32_t)p^(uint32_t)(p>>32)^orientation*31u^kind*131u^flags;
 for(uint32_t k=0;k<3;k++)n=(n^xyz[k])*16777619u;
 /* Tile/half-tile IEEE coordinates share low mantissa bits. Mix high bits
  * down before a power-of-two mask, rather than clustering whole towns. */
 n^=n>>16;n*=0x7feb352du;n^=n>>15;n*=0x846ca68bu;n^=n>>16;return n;
}
static int wsChartGhostInsert(WSChartDraw*d,const WSChartGhost*record){
 if(!d->ghostCapacity||d->ghostCount*2u>=d->ghostCapacity){
  uint32_t capacity=d->ghostCapacity?d->ghostCapacity*2u:64u;if(capacity>1048576u)return 0;
  WSChartGhost*next=(WSChartGhost*)calloc(capacity,sizeof(*next));if(!next)return 0;
  for(uint32_t n=0;n<d->ghostCapacity;n++)if(d->ghosts[n].used){WSChartGhost*old=d->ghosts+n;uint32_t at=wsChartGhostHash(old->frame,old->orientation,old->kind,old->xyz,old->flags)&(capacity-1u);while(next[at].used)at=(at+1u)&(capacity-1u);next[at]=*old;}
  free(d->ghosts);d->ghosts=next;d->ghostCapacity=capacity;
 }
 uint32_t at=wsChartGhostHash(record->frame,record->orientation,record->kind,record->xyz,record->flags)&(d->ghostCapacity-1u);
 while(d->ghosts[at].used){WSChartGhost*old=d->ghosts+at;if(old->frame==record->frame&&old->orientation==record->orientation&&old->kind==record->kind&&old->flags==record->flags&&!memcmp(old->xyz,record->xyz,12)){return old->phase==record->phase;}at=(at+1u)&(d->ghostCapacity-1u);}
 d->ghosts[at]=*record;d->ghosts[at].used=1;d->ghostCount++;return 1;
}
static uintptr_t __cdecl wsChartCaptureSprite(void*renderer,void*frame,uint32_t orientation,uint32_t phase,uint32_t flags,const float*position){
 void**object=(void**)renderer;WSChartDraw*d=object?(WSChartDraw*)object[1]:0;
 if(!d||renderer!=d->captureObject||!position||!frame||orientation>15u){if(d)d->failed=1;return 0;}
 float point[3];memcpy(point,position,12);for(uint32_t k=0;k<3;k++)if(!wsVisibilityFinite(point[k])){d->failed=1;return 0;}
 WSChartGhost record={0};record.frame=frame;memcpy(record.xyz,point,12);record.orientation=orientation;record.phase=phase;record.flags=flags;record.kind=(uint32_t)d->captureKind;record.used=1;
 if(!d->captureContext||!d->captureQuad||!d->captureContext->fast){d->failed=1;return 0;}
 for(uint32_t cell=0;cell<64&&!record.asset;cell++)if(d->captureQuad[8u+cell*8u+3u]&0x40u){
  uint16_t id;memcpy(&id,d->captureQuad+8u+cell*8u,2);if(id>=4000u)continue;
  const WSChartAssetProof*p=(const WSChartAssetProof*)d->captureContext->fast->chartAssets[id];if(!p||p->level<2)continue;
  for(uint32_t n=0;n<4;n++)if(p->frames[n].frame==frame){record.asset=p;record.assetId=id;break;}
 }
 if(!record.asset||!wsChartAssetCurrent(d->captureContext,record.asset,(uint16_t)record.assetId,1)){d->failed=1;return 0;}
 if(!wsChartGhostInsert(d,&record))d->failed=1;return 0;
}
static inline int wsChartCaptureAssets(const WSVisibilityDrawContext*c,const unsigned char*quad){
 if(!c->fast||!c->fast->catalogueReady)return 0;
 for(uint32_t cell=0;cell<64;cell++)if(quad[8u+cell*8u+3u]&0x40u){
  if(!wsChartCellAssets(c,quad+8u+cell*8u,quad[0x34cu+cell]))return 0;
 }
 return 1;
}
#ifndef WS_CHART_CAPTURE_ASSETS_OK
#define WS_CHART_CAPTURE_ASSETS_OK(context,quad) wsChartCaptureAssets((context),(quad))
#endif
static int wsChartCaptureGhostFigure(WSVisibilityDrawContext*c,WSChartDraw*d,const WSChartFigure*f){
 for(uint32_t qz=f->z&~7u;qz<f->z+f->height;qz+=8u)for(uint32_t qx=f->x&~7u;qx<f->x+f->width;qx+=8u){
  unsigned char quad[0x390]={0};memcpy(quad,&c->fast->catalogue,8);uint32_t time=0;int occupied=0;
  for(uint32_t z=qz;z<qz+8u&&z<c->view.height;z++)for(uint32_t x=qx;x<qx+8u&&x<c->view.width;x++){
   const WSChartCell*r=wsChartActive.cells+(size_t)z*c->view.width+x;WSChartFigure figure;
   if(!(r->flags&WS_CHART_BUILDING)||wsChartCachedFigure(c,x,z,r,&figure)!=1||!wsChartSameFigure(f,&figure))continue;
   uint32_t index=(z&7u)*8u+(x&7u);memcpy(quad+8u+index*8u,r->visual,8);quad[0x34cu+index]=r->renderFlag;quad[0x38c]|=(unsigned char)(1u<<(z&7u));time=r->time;occupied=1;
  }
  if(!occupied)continue;if(!WS_CHART_CAPTURE_ASSETS_OK(c,quad))return 0;uint16_t xy[2]={(uint16_t)qx,(uint16_t)qz};d->captureContext=c;d->captureQuad=quad;
  if(d->renderMode!=2u){
   d->captureKind=1;WS_CHART_NATIVE_STATIC(c->view.module,1)(quad,xy,0,d->captureObject);
   d->captureKind=2;WS_CHART_NATIVE_STATIC(c->view.module,2)(quad,xy,0,d->captureObject);
   d->captureKind=3;WS_CHART_NATIVE_STATIC(c->view.module,3)(quad,xy,time,d->captureObject);
  }
  if(d->renderMode!=1u){d->captureKind=4;WS_CHART_NATIVE_COLOR(c->view.module)(quad,xy,0,time,d->captureObject);}
  d->captureContext=0;d->captureQuad=0;if(d->failed)return 0;
 }
 return 1;
}
static uint32_t wsChartCallerKind(const WSVisibilityDrawContext*c,uintptr_t caller){
 uintptr_t base=(uintptr_t)c->view.module;if(caller<base)return 0;uintptr_t r=caller-base;
 if(r>=0xc4d2eu&&r<=0xc4d35u)return 1;if(r>=0xc5048u&&r<=0xc504fu)return 2;if(r>=0xc5389u&&r<=0xc538fu)return 3;
 if((r>=0xc5759u&&r<=0xc5760u)||(r>=0xcb91au&&r<=0xcb921u)||(r>=0xcb9ccu&&r<=0xcb9d3u)||(r>=0xcbc89u&&r<=0xcbc8fu)||(r>=0xcde09u&&r<=0xcde0fu))return 4;return 0;
}
static int wsVisibilityChartGhostSprite(const WSVisibilityDrawContext*c,void*frame,uint32_t orientation,uintptr_t caller,const float*position,uint32_t*phase,uint32_t*flags){
 WSChartDraw*d=c?(WSChartDraw*)c->chartDraw:0;if(!d||!d->ghostCount)return 0;uint32_t kind=wsChartCallerKind(c,caller);if(!kind)return 0;
 float point[3];if(!wsVisibilitySpriteCoordinates(c,position,point))return -1;
 if(c->view.map==0&&!wsVisibilityChartPoint(&c->view,point[0],point[2]))return -1;
 uint32_t xyz[3];memcpy(xyz,point,12);
 uint32_t at=wsChartGhostHash(frame,orientation,kind,xyz,*flags)&(d->ghostCapacity-1u);
 for(uint32_t n=0;n<d->ghostCapacity;n++){
  const WSChartGhost*r=d->ghosts+at;if(!r->used)return 0;
  if(r->frame==frame&&r->orientation==orientation&&r->kind==kind&&r->flags==*flags&&!memcmp(r->xyz,xyz,12)){
   /* Proofs belong only to this current draw. Recheck fresh bindings directly
    * before nativeDisplay submission; a mismatch must never fall back live. */
   if(!c->fast||r->assetId>=4000u||c->fast->chartAssets[r->assetId]!=r->asset||!r->asset||!wsChartAssetCurrent(c,r->asset,(uint16_t)r->assetId,1))return -1;
   int bound=0;for(uint32_t k=0;k<4;k++)if(r->asset->frames[k].frame==frame)bound=1;if(!bound)return -1;
   *phase=r->phase;*flags=r->flags;return 1;
  }at=(at+1u)&(d->ghostCapacity-1u);
 }return 0;
}
static void wsChartFreeCopyList(WSChartCopy*copy){while(copy){WSChartCopy*next=copy->next;free(copy);copy=next;}}
static int wsChartPrepareCopies(WSVisibilityDrawContext*c,WSChartDraw*d){
 if(c->view.enemy)return 1;uint32_t rows=0;if(!wsVisibilityListWritable(d->list,&rows))return 0;d->rows=rows;
 unsigned char*visited=(unsigned char*)calloc((wsChartActive.count+7u)>>3,1);if(!visited)return 0;size_t copyBytes=0;
 for(uint32_t n=0;n<rows;n++){
  unsigned char*row=(unsigned char*)d->list+8u+(size_t)n*88u;uint16_t xy[2];memcpy(xy,row,4);unsigned char valid=row[0x4d];
  if((valid&0xf0u)||(xy[0]&15u)||(xy[1]&15u)||xy[0]>=c->view.width||xy[1]>=c->view.height)goto invalid;
  for(uint32_t q=0;q<4;q++)if(valid&(1u<<q)){
   unsigned char id=row[0x38+q];uint32_t qx=xy[0]+(q&1u)*8u,qz=xy[1]+(q>>1)*8u;if(id==255u)continue;
   if(!c->present[id]||qx<c->islands[id].x||qz<c->islands[id].y||qx+8u>c->islands[id].x+c->islands[id].width||qz+8u>c->islands[id].y+c->islands[id].height)goto invalid;
   WSChartCopy*copy=0;
   for(uint32_t z=qz;z<qz+8u;z++)for(uint32_t x=qx;x<qx+8u;x++){
    const WSChartCell*r=wsChartActive.cells+(size_t)z*c->view.width+x;if(!(r->flags&WS_CHART_BUILDING))continue;
    WSChartFigure f;if(wsChartCachedFigure(c,x,z,r,&f)!=1)goto invalid;if(wsChartSeenBox(c,(float)f.x,(float)f.z,(float)(f.x+f.width),(float)(f.z+f.height)))continue;
    if(!copy){
     void*original=wsVisibilityFastPointer(row,8u+q*8u);if(!original||!wsCertMemory(original,0x390,0)||wsVisibilityFastPointer(original,0)!=c->fast->catalogue||copyBytes+sizeof(*copy)>WS_CHART_COPY_LIMIT-wsChartRetiredBytes)goto invalid;
     copy=(WSChartCopy*)calloc(1,sizeof(*copy));if(!copy)goto invalid;copy->row=row;copy->original=original;copy->rowIndex=n;copy->x=xy[0];copy->z=xy[1];copy->quadrant=(unsigned char)q;copy->island=id;copy->renderer=(uintptr_t)d->renderer;memcpy(copy->bytes,original,0x390);copy->next=d->copies;d->copies=copy;copyBytes+=sizeof(*copy);
    }
    uint32_t cell=(z&7u)*8u+(x&7u);memcpy(copy->bytes+8u+cell*8u,r->visual,8);copy->bytes[0x34cu+cell]=r->renderFlag;copy->bytes[0x38c]|=(unsigned char)(1u<<(z&7u));
    uint32_t anchor=f.z*c->view.width+f.x;unsigned char bit=(unsigned char)(1u<<(anchor&7u));if(!(visited[anchor>>3]&bit)){visited[anchor>>3]|=bit;if(!wsChartCaptureGhostFigure(c,d,&f))goto invalid;}
   }
  }
 }
 /* No borrowed-list pointer is written until all copies, identities, asset
  * captures and every target span have passed the full two-phase preflight. */
 for(WSChartCopy*copy=d->copies;copy;copy=copy->next)if(!wsMineralPersistenceWritable(copy->row+8u+copy->quadrant*8u,8)||wsVisibilityFastPointer(copy->row,8u+copy->quadrant*8u)!=copy->original)goto invalid;
 for(WSChartCopy*copy=d->copies;copy;copy=copy->next){void*pointer=copy->bytes;memcpy(copy->row+8u+copy->quadrant*8u,&pointer,8);}d->installed=1;free(visited);return 1;
 invalid:free(visited);return 0;
}
static int wsVisibilityChartBeginDraw(WSVisibilityDrawContext*c,void*list,uint32_t time,void*renderer,int picking){
 if(!wsVisibilityChartReadBegin(&c->view,&c->chart))return 0;
 uint32_t mode=0;if(!wsCertRead((unsigned char*)renderer+0x498,&mode,4)||mode>5u){wsVisibilityChartReadEnd(&c->chart);return 0;}
 if(picking||mode==4u||mode==5u)return 1;
 if(!wsChartObserve(c,time)){wsVisibilityChartReadEnd(&c->chart);return 0;}
 c->chart.generation=wsChartActive.generation;
 WSChartDraw*d=(WSChartDraw*)calloc(1,sizeof(*d));if(!d){wsVisibilityChartReadEnd(&c->chart);return 0;}
 d->list=list;d->renderer=renderer;d->renderMode=mode;d->captureVtable[0x180/8]=(void*)wsChartCaptureSprite;d->captureVtable[0x188/8]=(void*)wsChartCaptureSprite;d->captureObject[0]=d->captureVtable;d->captureObject[1]=d;c->chartDraw=d;
 if(!wsChartPrepareCopies(c,d)){wsVisibilityChartEndDraw(c);return 0;}return 1;
}
static void wsVisibilityChartDrawStarted(WSVisibilityDrawContext*c){if(c&&c->chartDraw)((WSChartDraw*)c->chartDraw)->started=1;}
static int wsVisibilityChartEndDraw(WSVisibilityDrawContext*c){
 if(!c)return 0;WSChartDraw*d=(WSChartDraw*)c->chartDraw;int restored=1;
 if(d){
  if(d->installed){
   uint32_t rows=0;if(!wsVisibilityListWritable(d->list,&rows)||rows!=d->rows)restored=0;
   for(WSChartCopy*copy=d->copies;restored&&copy;copy=copy->next){uint16_t xy[2];memcpy(xy,copy->row,4);if(xy[0]!=copy->x||xy[1]!=copy->z||copy->row[0x38+copy->quadrant]!=copy->island||wsVisibilityFastPointer(copy->row,8u+copy->quadrant*8u)!=copy->bytes)restored=0;}
   if(restored)for(WSChartCopy*copy=d->copies;copy;copy=copy->next)memcpy(copy->row+8u+copy->quadrant*8u,&copy->original,8);
  }
  if(d->started||!restored){
   while(d->copies){WSChartCopy*copy=d->copies;d->copies=copy->next;copy->quarantined=!restored;copy->next=wsChartRetiredCopies;wsChartRetiredCopies=copy;wsChartRetiredBytes+=sizeof(*copy);}
  }else wsChartFreeCopyList(d->copies);
  free(d->ghosts);free(d);c->chartDraw=0;
 }
 if(c->chart.core)wsVisibilityChartReadEnd(&c->chart);
 if(!restored){InterlockedExchange(&wsVisibilityLastError,14);wsVisibilityRenderMemo.valid=0;}return restored;
}
static void wsVisibilityChartRetire(void*renderer){
 /* Called only AFTER the verified original final flush has waited workers.
  * No original row/World/asset pointer is dereferenced at retirement. */
 if(!wsChartTake())return;WSChartCopy**at=&wsChartRetiredCopies;
 while(*at){WSChartCopy*copy=*at;if(copy->renderer==(uintptr_t)renderer&&!copy->quarantined){*at=copy->next;wsChartRetiredBytes-=sizeof(*copy);free(copy);}else at=&copy->next;}
 wsChartGive();
}
static void wsVisibilityChartTransientReset(void){
 /* Existing checkpoints and staged load data survive a failed load attempt.
  * Owned queued copies are retired solely at the explicit native flush. */
 wsVisibilityMapMemo.valid=0;wsVisibilityRenderMemo.valid=0;InterlockedIncrement(&wsVisibilityMapGeneration);
}
static int wsVisibilityChartLiveFigure(const WSVisibilityDrawContext*c,const WSVisibilityIsland*p,float x,float z){
 if(!c||!c->chart.core||!c->fast)return -2;WSChartFigure f;int current=wsChartCurrentFigure(c,p,(uint32_t)x,(uint32_t)z,&f);if(current<=0)return current;
 return wsChartSeenBox(c,(float)f.x,(float)f.z,(float)(f.x+f.width),(float)(f.z+f.height));
}
static int wsVisibilityChartRememberedAt(const WSVisibilityDrawContext*c,float x,float z){
 if(!c||!c->chart.core||c->view.enemy||!wsVisibilityPointValid(&c->view,x,z))return 0;
 const WSChartCell*r=c->chart.core->cells+(size_t)(uint32_t)z*c->view.width+(uint32_t)x;WSChartFigure f;
 return (r->flags&WS_CHART_BUILDING)&&wsChartCachedFigure(c,(uint32_t)x,(uint32_t)z,r,&f)==1&&!wsChartSeenBox(c,(float)f.x,(float)f.z,(float)(f.x+f.width),(float)(f.z+f.height));
}
static int wsChartMapSame(const WSVisibilityMapView*a,const WSVisibilityMapView*b){return a->object==b->object&&a->pixels==b->pixels&&a->width==b->width&&a->height==b->height;}
static int wsVisibilityChartMaskMap(const WSVisibilityMapView*m,const WSVisibilityDrawContext*c){
 WSVisibilityChartReadView read;WSVisibilityMapView current;WSChartCore nextMap={0};
 if(!wsVisibilityChartReadBegin(&c->view,&read))return 0;
 if(!wsVisibilityMapRead(m->object,&c->view,&current)||!wsChartMapSame(m,&current))goto invalid;
 int replace=wsChartActive.mapWidth!=m->width||wsChartActive.mapHeight!=m->height;
 if(replace&&!wsChartMapShape(&nextMap,m->width,m->height))goto invalid;
 if(!wsVisibilityMapRead(m->object,&c->view,&current)||!wsChartMapSame(m,&current))goto invalid;
 /* Frame61117 indexes exactly160 native palette entries without a clamp.
  * Validate every current input before publishing history or bitmap writes. */
 for(uint32_t n=0;n<m->width*m->height;n++)if(m->pixels[n]>=160u)goto invalid;
 if(!wsVisibilityChartMarkContext(c))goto invalid;
 if(replace){free(wsChartActive.mapPixels);free(wsChartActive.mapKnown);wsChartActive.mapWidth=nextMap.mapWidth;wsChartActive.mapHeight=nextMap.mapHeight;wsChartActive.mapCount=nextMap.mapCount;wsChartActive.mapKnownBytes=nextMap.mapKnownBytes;wsChartActive.mapPixels=nextMap.mapPixels;wsChartActive.mapKnown=nextMap.mapKnown;nextMap.mapPixels=nextMap.mapKnown=0;}
 for(uint32_t z=0;z<m->height;z++)for(uint32_t x=0;x<m->width;x++){
  uint32_t index=z*m->width+x;unsigned char*pixel=m->pixels+index;
  float wx=((float)x+0.5f)*(float)c->view.width/(float)m->width,wz=((float)z+0.5f)*(float)c->view.height/(float)m->height;
  if(c->view.map==0&&!wsVisibilityChartPoint(&c->view,wx,wz)){*pixel=0x90u;continue;}
  int seen=wsChartSeenBox(c,wx,wz,wx,wz);if(seen)wsChartMapPut(&wsChartActive,index,*pixel);
  if(!c->view.enemy&&!seen){unsigned char known=0;if(wsChartMapGet(&wsChartActive,index,&known))*pixel=known;else *pixel=(unsigned char)((*pixel&15u)|0x90u);}
 }
 wsChartCoreFree(&nextMap);wsVisibilityChartReadEnd(&read);return 1;
 invalid:wsChartCoreFree(&nextMap);wsVisibilityChartReadEnd(&read);return 0;
}
static int wsChartErrorWritable(char*error,uint32_t cap){return !cap||(!error?0:(cap<=4096u&&wsMineralPersistenceWritable(error,cap)));}
__declspec(dllexport) int WorldSettingsVisibilitySaveBlob(unsigned char**out,uint32_t*size,char*error,uint32_t cap){
 if(!out||!size||!wsMineralPersistenceWritable(out,sizeof(*out))||!wsMineralPersistenceWritable(size,sizeof(*size))||!wsChartErrorWritable(error,cap))return 0;
 return wsVisibilityChartSaveBlob(out,size,error,cap);
}
__declspec(dllexport) int WorldSettingsVisibilityStageBlob(const void*data,uint32_t size,char*error,uint32_t cap){
 if((!data&&size)||(data&&!size)||size>WS_CHART_BLOB_LIMIT||(data&&!wsCertMemory(data,size,0))||!wsChartErrorWritable(error,cap))return 0;
 return wsVisibilityChartStageBlob(data,size,error,cap);
}
__declspec(dllexport) int WorldSettingsVisibilityApplyBlob(void*world,char*error,uint32_t cap){
 if(!wsChartErrorWritable(error,cap))return 0;return wsVisibilityChartApplyBlob(world,error,cap);
}
__declspec(dllexport) void WorldSettingsVisibilityCancelBlob(void){wsVisibilityChartCancelBlob();}
__declspec(dllexport) int WorldSettingsVisibilityCommitFresh(void*scene,char*error,uint32_t cap){
 if(!wsChartErrorWritable(error,cap))return 0;void*world=wsCertPointer(scene,0x160);WSVisibilityWorld v;unsigned char guid[16];
 if(!world||!wsVisibilityWorldRead(world,&v)||!wsChartIdentity(&v,guid))return wsChError(error,cap,"Invalid fresh exploration World.");
 if(!wsChartTake())return wsChError(error,cap,"Exploration memory is busy.");
 if(InterlockedExchange(&wsChartFreshCancelPending,0)){wsChartCoreFree(&wsChartFresh);wsChartFreshBinding=0;}
 int ok=wsChartFreshBinding==(uintptr_t)world&&wsChartCoreIdentity(&wsChartFresh,v.width,v.height,v.viewer,v.flags&0x7000u,guid);
 if(ok){wsChartCoreFree(&wsChartActive);wsChartActive=wsChartFresh;memset(&wsChartFresh,0,sizeof wsChartFresh);wsChartFreshBinding=0;wsChartWorldBinding=(uintptr_t)world;wsVisibilityChartTransientReset();}
 wsChartGive();if(!ok)return wsChError(error,cap,"Fresh exploration checkpoint was not prepared for this World.");return 1;
}
__declspec(dllexport) void WorldSettingsVisibilityCancelFresh(void){
 InterlockedExchange((volatile LONG*)&wsFreshVisibilityCode,0);InterlockedExchange(&wsChartFreshCancelPending,1);if(!wsChartTake())return;wsChartCoreFree(&wsChartFresh);wsChartFreshBinding=0;InterlockedExchange(&wsChartFreshCancelPending,0);wsChartGive();
}
__declspec(dllexport) DWORD WINAPI WorldSettingsCopyVisibilityChartDiagnostics(void*out){
 if(!out||!wsMineralPersistenceWritable(out,96)||!wsChartTake())return 0;
 if(!wsChartActive.bits||!wsChartActive.cells||!wsChartWorldBinding){wsChartGive();return 0;}
 unsigned char result[96]={0};uint32_t charted=0,anchors=0,cells=0,known=0;
 for(uint32_t i=0;i<wsChartActive.bitBytes;i++)for(uint32_t b=0;b<8;b++)charted+=(wsChartActive.bits[i]>>b)&1u;
 for(uint32_t i=0;i<wsChartActive.count;i++)if(wsChartActive.cells[i].flags&WS_CHART_BUILDING){cells++;if(!(wsChartActive.cells[i].rootCode&63u))anchors++;}
 for(uint32_t i=0;i<wsChartActive.mapCount;i++)known+=(wsChartActive.mapKnown[i>>3]>>(i&7u))&1u;
 uint32_t fields[12]={1,96,wsChartActive.width,wsChartActive.height,wsChartActive.viewer,wsChartActive.policy,wsChartActive.generation,charted,anchors,cells,known,(wsChartActive.mapWidth<<16)|wsChartActive.mapHeight};
 for(uint32_t i=0;i<12;i++)wsChPut32(result+i*4u,fields[i]);
 wsChPut64(result+48,wsChHash(wsChartActive.bits,wsChartActive.bitBytes));wsChPut64(result+56,wsChHash(wsChartActive.cells,(size_t)wsChartActive.count*sizeof(WSChartCell)));
 wsChPut64(result+64,wsChHash(wsChartActive.mapPixels,wsChartActive.mapCount));wsChPut64(result+72,wsChHash(wsChartActive.mapKnown,wsChartActive.mapKnownBytes));wsChPut64(result+80,wsChHash(wsChartActive.guid,16));wsChPut64(result+88,(uint64_t)wsChartRetiredBytes);
 memcpy(out,result,96);wsChartGive();return 96;
}
