/* Invocation-owned native rendering for worlds without a World Settings policy.
 * The engine supplied these live actor/renderer arguments to its original
 * calls. Prove the immutable interface spans once per draw, then retain the
 * original calls and arguments without per-tree OS memory queries. No heap
 * cache, world pointer, native image or exemption survives the invocation.
 */
typedef struct WSVisibilityNativeScope {
 void *world,*renderer;unsigned char *module,*display;uint64_t actors;
 struct WSVisibilityNativeScope *previous;
} WSVisibilityNativeScope;
_Static_assert(sizeof wsVisibilityActorLayouts/sizeof wsVisibilityActorLayouts[0]<=64u,"Native actor proof mask capacity");
static _Thread_local WSVisibilityNativeScope *wsVisibilityNativeTLS;
#ifndef WS_VISIBILITY_NATIVE_SCOPE_TARGET_OK
#define WS_VISIBILITY_NATIVE_SCOPE_TARGET_OK(module,target) (wsVisibilityWithinModule((module),(target),1)&&wsCertMemory((target),1,1))
#endif
static void wsVisibilityNativeEnter(WSVisibilityNativeScope*s,void*world,void*renderer,int owned){
 memset(s,0,sizeof(*s));s->previous=wsVisibilityNativeTLS;wsVisibilityNativeTLS=0;
 if(owned||wsVisibilityDrawContext)return;
 unsigned char*w=(unsigned char*)WS_CERT_MODULE("AnnoWelt.dll"),*d=(unsigned char*)WS_CERT_MODULE("AnnoDisplay.dll");
 uint32_t flags=0;void*vt=wsCertPointer(world,0);
 if(!w||!d||(vt!=w+0xff1d8u&&vt!=w+0xff650u)||
    !wsCertRead((unsigned char*)world+0x6eec,&flags,4)||(flags&WS_VISIBILITY_POLICY_MASK)||
    !wsCertMemory(world,0x6f00u,0)||wsCertPointer(renderer,0)!=d+0xf63740u||
    !wsCertMemory(renderer,8u,0)||!wsVisibilityWithinModule(d,d+0xf63740u,0x190u)||
    !WS_VISIBILITY_NATIVE_SCOPE_TARGET_OK(d,d+0x49410u)||!WS_VISIBILITY_NATIVE_SCOPE_TARGET_OK(d,d+0x49bd0u)||
    !wsVisibilityWithinModule(w,w+0xead10u,0xfd8c0u-0xead10u)||
    !wsCertMemory(w+0xead10u,0xfd8c0u-0xead10u,0))return;
 s->world=world;s->renderer=renderer;s->module=w;s->display=d;
 for(size_t i=0;i<sizeof wsVisibilityActorLayouts/sizeof wsVisibilityActorLayouts[0];i++){
  const WSVisibilityActorLayout*a=wsVisibilityActorLayouts+i;void*table=w+a->vtable;
  if(wsVisibilityFastPointer(table,0x38u)==w+a->worldGetter&&wsVisibilityFastPointer(table,0x40u)==w+a->ownerGetter&&
     wsVisibilityFastPointer(table,0xb0u)==w+a->xGetter&&wsVisibilityFastPointer(table,0xc0u)==w+a->zGetter)s->actors|=UINT64_C(1)<<i;
 }
 wsVisibilityNativeTLS=s;
}
static void wsVisibilityNativeLeave(WSVisibilityNativeScope*s){wsVisibilityNativeTLS=s->previous;}
static const WSVisibilityActorLayout*wsVisibilityNativeActor(void*actor,void*renderer){
 const WSVisibilityNativeScope*s=wsVisibilityNativeTLS;if(!s||wsVisibilityDrawContext||!actor||renderer!=s->renderer)return 0;
 void*vt=wsVisibilityFastPointer(actor,0);
 for(size_t i=0;i<sizeof wsVisibilityActorLayouts/sizeof wsVisibilityActorLayouts[0];i++){
  const WSVisibilityActorLayout*a=wsVisibilityActorLayouts+i;
  if(!(s->actors&(UINT64_C(1)<<i))||vt!=s->module+a->vtable)continue;
  void*parent=wsVisibilityFastPointer(actor,a->worldOffset),*world=parent;
  if(a->vtable==0xf58e8u){if(!parent)return 0;world=wsVisibilityFastPointer(parent,0x38u);}
  return world==s->world?a:0;
 }
 return 0;
}
