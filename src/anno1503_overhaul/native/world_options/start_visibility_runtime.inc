/* Exact HE display adapters. Include after the loaded-world certificate and
 * mineral-persistence bounds helpers. Hook installation belongs to the same
 * reviewed all-or-nothing activation transaction as the existing engine edits.
 * No physical terrain, pathfinding grid, resource assignment or AI state is
 * rewritten by the render filters. Discovery is the native island-level mask.
 */
#include "start_visibility_policy.h"
#include "start_visibility_chart.h"
#include "start_visibility_performance.inc"
typedef struct WSVisibilityWorld {
 unsigned char*world,*module;uint32_t width,height,flags,viewer;
 int32_t map,enemy;int marked;
} WSVisibilityWorld;
typedef struct WSVisibilityChartReadView {
 const WSChartCore*core;unsigned char*world;uint32_t width,height,viewer,policy,generation;int owned;
 struct WSVisibilityChartReadView*previous;
} WSVisibilityChartReadView;
static int wsVisibilityChartEnsure(const WSVisibilityWorld*);
static int wsVisibilityChartPoint(const WSVisibilityWorld*,float,float);
static int wsVisibilityChartReadBegin(const WSVisibilityWorld*,WSVisibilityChartReadView*);
static void wsVisibilityChartReadEnd(WSVisibilityChartReadView*);
static void wsVisibilityChartRetire(void*);
static int wsVisibilityChartSaveBlob(unsigned char**,uint32_t*,char*,uint32_t);
static int wsVisibilityChartStageBlob(const void*,uint32_t,char*,uint32_t);
static int wsVisibilityChartApplyBlob(void*,char*,uint32_t);
static void wsVisibilityChartCancelBlob(void);
static void wsVisibilityChartTransientReset(void);
static int wsVisibilityChartPrepareFresh(const WSVisibilityWorld*,char*,uint32_t);
typedef struct WSVisibilityIsland {
 unsigned char*object;uint32_t id,x,y,width,height;uint16_t discovered;
} WSVisibilityIsland;
#define WS_VISIBILITY_SHIP_LIMIT 512u
#define WS_VISIBILITY_CITY_LIMIT 255u
/* Bounded observer traversal, not a claimed native recruitment limit. */
#define WS_VISIBILITY_UNIT_LIMIT 4096u
#define WS_VISIBILITY_VISION_LIMIT (WS_VISIBILITY_SHIP_LIMIT+WS_VISIBILITY_CITY_LIMIT+WS_VISIBILITY_UNIT_LIMIT)
#define WS_VISIBILITY_SIGHT_RADIUS 48.0f
typedef struct WSVisibilityVisionSource {float left,top,right,bottom;} WSVisibilityVisionSource;
typedef struct WSVisibilityFastDraw WSVisibilityFastDraw;
typedef struct WSVisibilityDrawContext {
 WSVisibilityWorld view;WSVisibilityIsland islands[WS_VISIBILITY_ISLAND_LIMIT];
 unsigned char present[WS_VISIBILITY_ISLAND_LIMIT];
 unsigned char*human;uint32_t visionCount;
 WSVisibilityVisionSource vision[WS_VISIBILITY_VISION_LIMIT];
 WSVisibilityFastDraw*fast;
 WSVisibilityChartReadView chart;
 void*chartDraw;
} WSVisibilityDrawContext;
static int wsVisibilityChartBeginDraw(WSVisibilityDrawContext*,void*,uint32_t,void*,int);
static int wsVisibilityChartEndDraw(WSVisibilityDrawContext*);
static int wsVisibilityChartGhostSprite(const WSVisibilityDrawContext*,void*,uint32_t,uintptr_t,const float*,uint32_t*,uint32_t*);
static void wsVisibilityChartDrawStarted(WSVisibilityDrawContext*);
static const WSChartCore*wsVisibilityChartReadSnapshot(const WSVisibilityWorld*);
static int wsVisibilityChartMarkContext(const WSVisibilityDrawContext*);
static int wsVisibilityChartLiveFigure(const WSVisibilityDrawContext*,const WSVisibilityIsland*,float,float);
static int wsVisibilityChartRememberedAt(const WSVisibilityDrawContext*,float,float);
typedef struct WSVisibilityFastDefinition {
 void*object,*vtable;int state;uint16_t kind,subtype;unsigned char mainClass,subtypeKnown,classTag;
} WSVisibilityFastDefinition;
typedef struct WSVisibilityFastIsland {
 unsigned char*object,*tiles;void*cities[15],*owners[15];unsigned char cityValid[15];int ready;
} WSVisibilityFastIsland;
struct WSVisibilityFastDraw {
 unsigned char*game,*display;void*renderer,*catalogue,*catalogueVT;int targetsReady,catalogueReady;
 unsigned char*islandIndex;uint32_t islandIndexWidth,islandIndexHeight;
 int actorInterfacesReady;uintptr_t stackBegin,stackEnd;
 void*original180,*original188,*definitions[4000];
 WSVisibilityFastDefinition metadata[4000];WSVisibilityFastIsland islands[WS_VISIBILITY_ISLAND_LIMIT];
 void*chartAssets[4000],*chartAssetList;
};
static int wsVisibilityFastPrepare(WSVisibilityDrawContext*,void*);
static void wsVisibilityChartReleaseAssets(WSVisibilityFastDraw*);
static void wsVisibilityIslandIndexRelease(WSVisibilityFastDraw*);
static void wsVisibilityFastRelease(WSVisibilityDrawContext*c){if(c){if(c->fast){wsVisibilityChartReleaseAssets(c->fast);wsVisibilityIslandIndexRelease(c->fast);}free(c->fast);c->fast=0;}}
static int wsVisibilityObserversRead(WSVisibilityDrawContext*);
/* A pointer to the current wrapper's stack is visible only on its own thread
 * and only during that native draw. No object pointer is retained afterwards. */
static _Thread_local WSVisibilityDrawContext*wsVisibilityDrawContext;
typedef struct WSVisibilityBackup {
 unsigned char*record;uint32_t row;uint16_t x,y;
 unsigned char valid,scratch,hidden;
} WSVisibilityBackup;
typedef char WSVisibilityBackupCapacityFits[(sizeof(WSVisibilityBackup)<=SIZE_MAX/WS_VISIBILITY_RECORD_LIMIT)?1:-1];
static WSVisibilityBackup*wsVisibilityBackups;
static uint32_t wsVisibilityBackupCount,wsVisibilityBackupCapacity;
static unsigned char*wsVisibilityBackupWorld,*wsVisibilityBackupList;
static volatile LONG wsVisibilityRenderBusy,wsVisibilityLastError;
static volatile LONG wsVisibilityMaskedTiles,wsVisibilityMaskedMaps,wsVisibilityRestoredTiles;
static volatile LONG wsVisibilityMapGeneration;
static volatile LONG64 wsVisibilityRenderTarget180,wsVisibilityRenderTarget188;
/* Scalar identity/visibility memo only: cached addresses are compared, never
 * dereferenced. Every renderer/World/bitmap read comes from the current draw. */
typedef struct WSVisibilityRenderIslandMemo {uintptr_t object;uint32_t x,y,width,height;uint16_t known;unsigned char present;} WSVisibilityRenderIslandMemo;
typedef struct WSVisibilityRenderMemo {
 uintptr_t world,renderer,records;uint32_t generation,width,height,viewer,policy,visionCount;int valid;
 int32_t viewport[4];WSVisibilityRenderIslandMemo islands[WS_VISIBILITY_ISLAND_LIMIT];
 WSVisibilityVisionSource vision[WS_VISIBILITY_VISION_LIMIT];
} WSVisibilityRenderMemo;
static WSVisibilityRenderMemo wsVisibilityRenderMemo;

static int wsVisibilityWorldRead(void*world,WSVisibilityWorld*out){
 unsigned char*w=(unsigned char*)WS_CERT_MODULE("AnnoWelt.dll");void*vt=wsCertPointer(world,0);
 WSVisibilityWorld v={0};
 if(!w||!out||(vt!=w+0xff1d8&&vt!=w+0xff650)||!wsCertMemory(world,0x6f00,0))return 0;
 v.world=(unsigned char*)world;v.module=w;
 if(!wsCertRead(v.world+0x1d8,&v.width,4)||!wsCertRead(v.world+0x1dc,&v.height,4)||
    !wsCertRead(v.world+0x6eec,&v.flags,4)||!wsCertRead(v.world+0x1e4,&v.viewer,4)||
    v.width!=v.height||(v.width!=256u&&v.width!=512u&&v.width!=1024u&&v.width!=2048u)||v.viewer>=16u)return 0;
 v.marked=wsVisibilityDecode(v.flags,&v.map,&v.enemy);
 *out=v;return 1;
}
static int wsVisibilityHasPolicy(void*world){
 unsigned char*w=(unsigned char*)WS_CERT_MODULE("AnnoWelt.dll");void*vt=wsCertPointer(world,0);uint32_t flags=0;
 return w&&(vt==w+0xff1d8||vt==w+0xff650)&&
  wsCertRead((unsigned char*)world+0x6eec,&flags,4)&&(flags&WS_VISIBILITY_POLICY_MASK)!=0;
}
static int wsVisibilityIslandRead(const WSVisibilityWorld*v,uint32_t id,WSVisibilityIsland*out){
 WSVisibilityIsland n={0};void*vt;uint16_t box[4];
 if(!v||!out||id>=WS_VISIBILITY_ISLAND_LIMIT)return 0;
 n.object=(unsigned char*)wsCertPointer(v->world,0x6640u+(size_t)id*8u);
 if(!n.object)return 0;vt=wsCertPointer(n.object,0);
 if((vt!=v->module+0xf2da8&&vt!=v->module+0xf33e8&&vt!=v->module+0xf37a0)||
    wsCertPointer(n.object,0x38)!=v->world||!wsCertRead(n.object+8,box,sizeof box)||
    !wsCertRead(n.object+0x12e,&n.discovered,2))return 0;
 n.id=id;n.x=box[0];n.y=box[1];n.width=box[2];n.height=box[3];
 if(!n.width||!n.height||(n.x&7u)||(n.y&7u)||n.x+n.width>v->width||n.y+n.height>v->height)return 0;
 *out=n;return 1;
}
static int wsVisibilityContextRead(const WSVisibilityWorld*v,WSVisibilityDrawContext*out){
 void*objects[WS_VISIBILITY_ISLAND_LIMIT];
 if(!v||!out||!wsCertRead(v->world+0x6640,objects,sizeof objects))return 0;
 memset(out,0,sizeof(*out));out->view=*v;
 for(uint32_t id=0;id<WS_VISIBILITY_ISLAND_LIMIT;id++)if(objects[id]){
  if(!wsVisibilityIslandRead(v,id,&out->islands[id])||out->islands[id].object!=objects[id])return 0;
  out->present[id]=1;
 }
 return v->enemy&&v->map!=0?1:wsVisibilityObserversRead(out);
}
#include "start_visibility_vision.inc"
static int wsVisibilityListRead(void*list,uint32_t*count){
 uint32_t n=0;
 if(!count||!wsCertRead(list,&n,4)||n>WS_VISIBILITY_RECORD_LIMIT||
    !wsCertMemory(list,8u+(size_t)n*WS_VISIBILITY_RECORD_BYTES,0))return 0;
 *count=n;return 1;
}
static int wsVisibilityListWritable(void*list,uint32_t*count){
 return wsVisibilityListRead(list,count)&&wsMineralPersistenceWritable(list,8u+(size_t)*count*WS_VISIBILITY_RECORD_BYTES);
}
static int wsVisibilityRow(const WSVisibilityDrawContext*context,unsigned char*row,unsigned char*hidden){
 const WSVisibilityWorld*v=&context->view;
 uint16_t x=0,y=0;unsigned char valid=0,result=0;
 /* Both callers preflight the entire current 8+n*88 readable/writable span.
  * Every field below is inside its bounded row; no per-field OS query. */
 if(!hidden)return 0;memcpy(&x,row,2);memcpy(&y,row+2,2);valid=row[0x4d];
 if((valid&0xf0u)||(x&15u)||(y&15u)||
    x>=v->width||y>=v->height)return 0;
 for(uint32_t q=0;q<4;q++)if(valid&(1u<<q)){
  unsigned char id=255;
  id=row[0x38+q];
  if(id==255u)continue; /* Native ocean quadrant, already has no island. */
  if(!context->present[id])return 0;
  const WSVisibilityIsland*island=&context->islands[id];
  uint32_t qx=x+(q&1u)*8u,qy=y+(q>>1)*8u;
  if(qx<island->x||qy<island->y||qx+8u>island->x+island->width||qy+8u>island->y+island->height)return 0;
   if(!wsVisibilityChartPoint(v,(float)qx+4.0f,(float)qy+4.0f))result|=(unsigned char)(1u<<q);
 }
 *hidden=result;return 1;
}
/* Restore within the SAME native draw invocation. No live record pointer or
 * modified bytes survive the wrapper's return. Native producer/update methods
 * and their ownership/lifetime rules remain unhooked. Current list membership,
 * coordinates and writable flag storage must match. Quad payloads, including
 * the native table header and all ownership pointers, are NEVER changed.
 */
static int wsVisibilityRestore(void){
 WSVisibilityWorld v;uint32_t count=0;
 if(!wsVisibilityBackupCount)return 1;
 if(!wsVisibilityWorldRead(wsVisibilityBackupWorld,&v)||
    !wsVisibilityListWritable(wsVisibilityBackupList,&count))goto invalid;
 for(uint32_t i=0;i<wsVisibilityBackupCount;i++){
  WSVisibilityBackup*b=&wsVisibilityBackups[i];
  if(b->row>=count)goto invalid;
  unsigned char*row=wsVisibilityBackupList+8u+(size_t)b->row*WS_VISIBILITY_RECORD_BYTES;
  if(row!=b->record||wsU16(row)!=b->x||wsU16(row+2)!=b->y||
     row[0x4d]!=(unsigned char)(b->valid&~b->hidden))goto invalid;
 }
 for(uint32_t i=0;i<wsVisibilityBackupCount;i++){
  wsVisibilityBackups[i].record[0x4d]=wsVisibilityBackups[i].valid;
  wsVisibilityBackups[i].record[0x50]=wsVisibilityBackups[i].scratch;
  InterlockedIncrement(&wsVisibilityRestoredTiles);
 }
 wsVisibilityBackupCount=0;wsVisibilityBackupWorld=wsVisibilityBackupList=0;return 1;
 invalid:InterlockedExchange(&wsVisibilityLastError,1);wsVisibilityBackupCount=0;
 wsVisibilityBackupWorld=wsVisibilityBackupList=0;return 0;
}
__declspec(dllexport) void WorldSettingsVisibilityReset(void){
 if(InterlockedCompareExchange(&wsVisibilityRenderBusy,1,0))return;
 /* No restore at a world-replacement boundary: an address may already have
  * been freed/reused. Normally count is zero because every draw restores its
  * own flags synchronously before returning. */
 if(wsVisibilityBackupCount)InterlockedExchange(&wsVisibilityLastError,5);
 free(wsVisibilityBackups);wsVisibilityBackups=0;
 wsVisibilityBackupCount=wsVisibilityBackupCapacity=0;wsVisibilityBackupWorld=wsVisibilityBackupList=0;
 memset(&wsVisibilityRenderMemo,0,sizeof wsVisibilityRenderMemo);
 wsVisibilityChartTransientReset();
 InterlockedIncrement(&wsVisibilityMapGeneration);
 InterlockedExchange(&wsVisibilityRenderBusy,0);
}
typedef void (__cdecl*WSVisibilityNativeActivityRefresh)(void*,void*,uint32_t);
#ifndef WS_VISIBILITY_NATIVE_ACTIVITY_REFRESH
#define WS_VISIBILITY_NATIVE_ACTIVITY_REFRESH(module) ((WSVisibilityNativeActivityRefresh)((module)+0xcdf10))
#endif
/* Native property 5 allows potential city submissions in both modes. Current
 * strict vision is enforced by the separate display predicates. A transition
 * uses the exact native (World, NULL city, viewer) refresh; publish the byte
 * first because this can synchronously call the minimap wrapper again.
 * Full exploration sets only human owner-0's native island-discovery bit.
 * All candidate writes are checked before publication. Old unmarked worlds
 * retain their original native visibility and discovery bytes.
 */
__declspec(dllexport) int WorldSettingsVisibilityWorldLoaded(void*world,char*error,uint32_t cap){
 WSVisibilityWorld v;WSVisibilityIsland islands[WS_VISIBILITY_ISLAND_LIMIT];uint32_t n=0;
 if(!wsVisibilityWorldRead(world,&v))goto invalid;
 if(!v.marked)return 1;
 if(v.marked<0)goto invalid;
 if(!wsMineralPersistenceWritable(v.world+0x6ee9,1))goto invalid;
 if(v.map==2){
  for(uint32_t id=0;id<WS_VISIBILITY_ISLAND_LIMIT;id++){
   void*p=wsCertPointer(v.world,0x6640u+(size_t)id*8u);if(!p)continue;
   if(!wsVisibilityIslandRead(&v,id,&islands[n])||!wsMineralPersistenceWritable(islands[n].object+0x12e,2))goto invalid;
   n++;
  }
 }
 /* Both display policies allow native submission. The strict policy applies
  * its current-vision predicate at the submitted actor/static/marker paths. */
 int activityChanged=v.world[0x6ee9]!=1u;
 v.world[0x6ee9]=1u;
 for(uint32_t i=0;i<n;i++)__atomic_fetch_or((uint16_t*)(islands[i].object+0x12e),1u,__ATOMIC_RELAXED);
 if(activityChanged)WS_VISIBILITY_NATIVE_ACTIVITY_REFRESH(v.module)(v.world,0,v.viewer);
 if(error&&cap)error[0]=0;return 1;
 invalid:InterlockedExchange(&wsVisibilityLastError,2);
 wsMessage(error,cap,"This world cannot safely apply the saved map visibility policy.");return 0;
}
/* Linked native SCP templates can carry editor human-discovery bits. This
 * certificate runs after fresh template/ownership/start-position setup and
 * before gameplay. Clear only human bit0 once; the ordinary native ship tick
 * repeats its 14-tile contact query and establishes legitimate discovery.
 * The separate display sight radius is 48 tiles. No reload/draw calls this. */
static int wsVisibilityNormalizeFreshDiscovery(const WSVisibilityWorld*v,char*error,uint32_t cap){
 WSVisibilityIsland islands[WS_VISIBILITY_ISLAND_LIMIT];uint32_t n=0;
 if(!wsFreshVisibilityCode)return 1;
 if(wsFreshVisibilityCode!=(v->flags&WS_VISIBILITY_POLICY_MASK)||v->viewer)goto invalid;
 if(v->map==0){
  for(uint32_t id=0;id<WS_VISIBILITY_ISLAND_LIMIT;id++){
   void*p=wsCertPointer(v->world,0x6640u+(size_t)id*8u);if(!p)continue;
   if(!wsVisibilityIslandRead(v,id,&islands[n])||
      !wsMineralPersistenceWritable(islands[n].object+0x12e,2))goto invalid;
   n++;
  }
  if(!n)goto invalid;
  if(!wsVisibilityChartPrepareFresh(v,error,cap))return 0;
  /* No discovery word is changed until every target has passed preflight. */
  for(uint32_t i=0;i<n;i++)__atomic_fetch_and((uint16_t*)(islands[i].object+0x12e),(uint16_t)~1u,__ATOMIC_RELAXED);
  InterlockedIncrement(&wsVisibilityMapGeneration);
 }
 else if(!wsVisibilityChartPrepareFresh(v,error,cap))return 0;
 wsFreshVisibilityCode=0;return 1;
 invalid:InterlockedExchange(&wsVisibilityLastError,2);
 wsMessage(error,cap,"The fresh world cannot safely clear inherited island discovery.");return 0;
}
__declspec(dllexport) int WorldSettingsValidateChosenVisibility(void*world,char*error,uint32_t cap){
 WSVisibilityWorld v;
 if(!wsVisibilityWorldRead(world,&v)||!wsExpectedVisibilityCode||
    (v.flags&WS_VISIBILITY_POLICY_MASK)!=wsExpectedVisibilityCode)goto invalid;
 if(!WorldSettingsVisibilityWorldLoaded(world,error,cap))return 0;
 return wsVisibilityNormalizeFreshDiscovery(&v,error,cap);
 invalid:wsMessage(error,cap,"Loaded map visibility differs from the option chosen in World Settings.");return 0;
}
static int wsVisibilityMaskList(void*world,void*list){
 WSVisibilityWorld v;WSVisibilityDrawContext local;uint32_t count=0,needed=0;
 if(!wsVisibilityWorldRead(world,&v)){if(wsVisibilityHasPolicy(world))goto invalid;return 1;}
 if(!v.marked||v.map!=0)return 1;if(v.marked<0)goto invalid;
 const WSVisibilityDrawContext*context=wsVisibilityDrawContext;
 if(!context||context->view.world!=world||context->view.viewer!=v.viewer||context->view.flags!=v.flags){
  if(!wsVisibilityContextRead(&v,&local))goto invalid;context=&local;
 }
 if(wsVisibilityBackupCount)goto invalid;
 if(!wsVisibilityListWritable(list,&count))goto invalid;
 for(uint32_t i=0;i<count;i++){
  unsigned char*row=(unsigned char*)list+8u+(size_t)i*WS_VISIBILITY_RECORD_BYTES;
  unsigned char hidden=0;if(!wsVisibilityRow(context,row,&hidden))goto invalid;if(hidden)needed++;
 }
 if(needed>wsVisibilityBackupCapacity){
  if(needed>WS_VISIBILITY_RECORD_LIMIT)goto invalid;
  void*next=realloc(wsVisibilityBackups,(size_t)needed*sizeof(*wsVisibilityBackups));if(!next)goto invalid;
  wsVisibilityBackups=(WSVisibilityBackup*)next;wsVisibilityBackupCapacity=needed;
 }
 wsVisibilityBackupCount=0;wsVisibilityBackupWorld=(unsigned char*)world;wsVisibilityBackupList=(unsigned char*)list;
 for(uint32_t i=0;i<count;i++){
  unsigned char*row=(unsigned char*)list+8u+(size_t)i*WS_VISIBILITY_RECORD_BYTES;
  unsigned char hidden=0;if(!wsVisibilityRow(context,row,&hidden))goto invalid;
  if(hidden){
   WSVisibilityBackup*b=&wsVisibilityBackups[wsVisibilityBackupCount++];
   b->record=row;b->row=i;b->x=wsU16(row);b->y=wsU16(row+2);
   b->valid=row[0x4d];b->scratch=row[0x50];b->hidden=hidden;
  }
 }
 if(wsVisibilityBackupCount!=needed)goto invalid;
 for(uint32_t i=0;i<needed;i++){
  WSVisibilityBackup*b=&wsVisibilityBackups[i];b->record[0x4d]&=(unsigned char)~b->hidden;
  b->record[0x50]&=(unsigned char)~b->hidden;InterlockedIncrement(&wsVisibilityMaskedTiles);
 }
 return 1;
 invalid:InterlockedExchange(&wsVisibilityLastError,3);
 wsVisibilityBackupCount=0;wsVisibilityBackupWorld=wsVisibilityBackupList=0;return 0;
}
typedef struct WSVisibilityMapView {unsigned char*object,*pixels;uint32_t width,height;} WSVisibilityMapView;
static int wsVisibilityChartMaskMap(const WSVisibilityMapView*,const WSVisibilityDrawContext*);
static int wsVisibilityMapRead(void*map,const WSVisibilityWorld*v,WSVisibilityMapView*out){
 WSVisibilityMapView m={0};m.object=(unsigned char*)map;
 if(!v||!out||wsCertPointer(map,0)!=v->module+0xff5e0||wsCertPointer(map,0x18)!=v->world||
    !wsCertRead(m.object+8,&m.width,4)||!wsCertRead(m.object+12,&m.height,4)||
    !m.width||!m.height||m.width>2048u||m.height>2048u||!(m.pixels=(unsigned char*)wsCertPointer(map,0x20))||
    !wsMineralPersistenceWritable(m.pixels,(size_t)m.width*m.height))return 0;
 *out=m;return 1;
}
static void wsVisibilityClearMap(const WSVisibilityMapView*m){
 for(size_t i=0;i<(size_t)m->width*m->height;i++)m->pixels[i]=0x90u;
}
static int wsVisibilityMaskMapView(const WSVisibilityMapView*m,const WSVisibilityDrawContext*context){
 if(!wsVisibilityChartMaskMap(m,context))return 0;InterlockedIncrement(&wsVisibilityMaskedMaps);return 1;
}
#include "start_visibility_map_refresh.inc"
typedef void (__cdecl*WSVisibilityNativeDirtyViewport)(void*,const int32_t*);
#ifndef WS_VISIBILITY_NATIVE_DIRTY_VIEWPORT
#define WS_VISIBILITY_NATIVE_DIRTY_VIEWPORT(module) ((WSVisibilityNativeDirtyViewport)((module)+0x48a20))
#endif
static int wsVisibilityRenderRefresh(const WSVisibilityDrawContext*c,void*renderer){
 unsigned char*display=(unsigned char*)WS_CERT_MODULE("AnnoDisplay.dll");int32_t viewport[4];
 uintptr_t records=(uintptr_t)wsCertPointer(renderer,0x4c0);uint32_t generation=(uint32_t)InterlockedCompareExchange(&wsVisibilityMapGeneration,0,0);
 if(!display||wsCertPointer(renderer,0)!=display+0xf63740||
    wsCertPointer(display+0xf63740,0x108)!=display+0x43390||
    wsCertPointer(display+0xf63740,0x138)!=display+0x487b0||
    wsCertPointer(display+0xf63740,0x170)!=display+0x48a20||
    !wsCertRead((unsigned char*)renderer+0x458,viewport,sizeof viewport)||
    viewport[0]<0||viewport[1]<0||viewport[2]<viewport[0]||viewport[3]<viewport[1]||
    viewport[2]>16384||viewport[3]>16384)goto invalid;
 /* Empty/offscreen native viewports can occur before resize initialization.
  * Let the original draw/initialization proceed, retain no completed refresh,
  * and retry once native bounds become nonempty. No dirty call/error here. */
 if(viewport[0]==viewport[2]||viewport[1]==viewport[3]){wsVisibilityRenderMemo.valid=0;return 1;}
 if(!records||
    !wsMineralPersistenceWritable((void*)records,0x4000u*0x1a0u))goto invalid;
 WSVisibilityRenderMemo*m=&wsVisibilityRenderMemo;
 int matching=m->valid&&m->world==(uintptr_t)c->view.world&&m->renderer==(uintptr_t)renderer&&m->records==records&&
  m->generation==generation&&m->width==c->view.width&&m->height==c->view.height&&m->viewer==c->view.viewer&&
  m->policy==(c->view.flags&WS_VISIBILITY_POLICY_MASK)&&m->visionCount==c->visionCount&&
  !memcmp(m->viewport,viewport,sizeof viewport)&&!memcmp(m->vision,c->vision,(size_t)c->visionCount*sizeof c->vision[0]);
 for(uint32_t id=0;matching&&id<WS_VISIBILITY_ISLAND_LIMIT;id++){
  const WSVisibilityIsland*p=&c->islands[id];const WSVisibilityRenderIslandMemo*old=&m->islands[id];
  uint16_t known=(uint16_t)(p->discovered&(1u<<c->view.viewer));
  if(old->present!=c->present[id]||(c->present[id]&&(old->object!=(uintptr_t)p->object||old->x!=p->x||old->y!=p->y||
     old->width!=p->width||old->height!=p->height||old->known!=known)))matching=0;
 }
 if(matching)return 1;
 /* CC5A0 mode1 asks DD11+138 whether each quad intersects pending dirty
  * screen tiles BEFORE it enumerates static sprites. Native+170 marks those
  * tiles; skipping sprite submissions alone cannot erase cached pixels.
  * Leave native+160 diff notifications untouched. No physical grid writes. */
 WS_VISIBILITY_NATIVE_DIRTY_VIEWPORT(display)(renderer,viewport);
 if((uint32_t)InterlockedCompareExchange(&wsVisibilityMapGeneration,0,0)!=generation||
    wsCertPointer(renderer,0)!=display+0xf63740||(uintptr_t)wsCertPointer(renderer,0x4c0)!=records||
    !wsCertMemory((unsigned char*)renderer+0x458,sizeof viewport,0)||
    memcmp((unsigned char*)renderer+0x458,viewport,sizeof viewport))goto invalid;
 memset(m,0,sizeof(*m));m->world=(uintptr_t)c->view.world;m->renderer=(uintptr_t)renderer;m->records=records;
 m->generation=generation;m->width=c->view.width;m->height=c->view.height;m->viewer=c->view.viewer;
 m->policy=c->view.flags&WS_VISIBILITY_POLICY_MASK;m->visionCount=c->visionCount;memcpy(m->viewport,viewport,sizeof viewport);
 memcpy(m->vision,c->vision,(size_t)c->visionCount*sizeof c->vision[0]);
 for(uint32_t id=0;id<WS_VISIBILITY_ISLAND_LIMIT;id++)if(c->present[id]){
  const WSVisibilityIsland*p=&c->islands[id];WSVisibilityRenderIslandMemo*to=&m->islands[id];
  to->present=1;to->object=(uintptr_t)p->object;to->x=p->x;to->y=p->y;to->width=p->width;to->height=p->height;
  to->known=(uint16_t)(p->discovered&(1u<<c->view.viewer));
 }
 m->valid=1;return 1;
 invalid:wsVisibilityRenderMemo.valid=0;InterlockedExchange(&wsVisibilityLastError,11);return 0;
}
typedef uintptr_t (__cdecl*WSVisibilityNativeDraw5)(void*,void*,uint32_t,uint32_t,void*);
typedef uintptr_t (__cdecl*WSVisibilityNativeDraw6)(void*,void*,uint32_t,const int32_t*,uint32_t,void*);
typedef uintptr_t (__cdecl*WSVisibilityNativeMap)(void*,uint32_t,void*);
typedef uintptr_t (__cdecl*WSVisibilityNativeWildlife)(void*,uint32_t,void*);
#ifndef WS_VISIBILITY_NATIVE_DRAW5
#define WS_VISIBILITY_NATIVE_DRAW5(module) ((WSVisibilityNativeDraw5)((module)+0xcc5a0))
#define WS_VISIBILITY_NATIVE_DRAW6(module) ((WSVisibilityNativeDraw6)((module)+0xcd470))
#define WS_VISIBILITY_NATIVE_MAP(module) ((WSVisibilityNativeMap)((module)+0xd2620))
#endif
#ifndef WS_VISIBILITY_NATIVE_WILDLIFE
#define WS_VISIBILITY_NATIVE_WILDLIFE(module,legacy) ((WSVisibilityNativeWildlife)((module)+((legacy)?0x9cc0:0x2dec0)))
#define WS_VISIBILITY_NATIVE_WILDLIFE_CLIPPED(module) ((WSVisibilityNativeWildlife)((module)+0x9eb0))
#endif
static int wsVisibilityMapRefreshFromDraw(const WSVisibilityDrawContext*);
static int wsVisibilityBeginDraw(void*world,void*list,void*renderer,WSVisibilityDrawContext*context,uint32_t time,int picking){
 WSVisibilityWorld v;uint32_t mode=0;
 if(!wsVisibilityWorldRead(world,&v))return wsVisibilityHasPolicy(world)?-1:0;
 if(!v.marked)return 0;
 if(v.marked<0||!wsCertRead((unsigned char*)renderer+0x498,&mode,4)||mode>5u)return -1;
 picking=picking||mode==4u||mode==5u;
 /* Hit tests consult the existing chart. They never observe buildings,
  * chart a moved observer, or refresh the normal rendered-world cache. */
 if(!picking&&!WorldSettingsVisibilityWorldLoaded(world,0,0))return -1;
 /* A concurrent/reentrant Terra draw is refused rather than reading another
  * invocation's temporary masking or deadlocking on a rendering callback. */
 if(InterlockedCompareExchange(&wsVisibilityRenderBusy,1,0)){InterlockedExchange(&wsVisibilityLastError,6);return -1;}
 uint64_t perf=wsVisibilityPerformanceBegin();int contextReady=wsVisibilityContextRead(&v,context);wsVisibilityPerformanceEnd(WS_PERF_CONTEXT,perf);
 if(!contextReady){wsVisibilityRenderMemo.valid=0;InterlockedExchange(&wsVisibilityLastError,3);InterlockedExchange(&wsVisibilityRenderBusy,0);return -1;}
 wsVisibilityDrawContext=context;
 perf=wsVisibilityPerformanceBegin();int fastReady=wsVisibilityFastPrepare(context,renderer);wsVisibilityPerformanceEnd(WS_PERF_FAST_PREPARE,perf);
 if(!fastReady){wsVisibilityRenderMemo.valid=0;wsVisibilityDrawContext=0;InterlockedExchange(&wsVisibilityRenderBusy,0);return -1;}
 if(!wsVisibilityChartBeginDraw(context,list,time,renderer,picking)){wsVisibilityFastRelease(context);wsVisibilityDrawContext=0;InterlockedExchange(&wsVisibilityLastError,13);InterlockedExchange(&wsVisibilityRenderBusy,0);return -1;}
 int refreshed=1;
 if(!picking){
  perf=wsVisibilityPerformanceBegin();refreshed=wsVisibilityMapRefreshFromDraw(context);wsVisibilityPerformanceEnd(WS_PERF_MAP_REFRESH,perf);
  if(refreshed){perf=wsVisibilityPerformanceBegin();refreshed=wsVisibilityRenderRefresh(context,renderer);wsVisibilityPerformanceEnd(WS_PERF_RENDER_REFRESH,perf);}
 }
 if(!refreshed||(v.map==0&&!wsVisibilityMaskList(world,list))){
  wsVisibilityRenderMemo.valid=0;wsVisibilityChartEndDraw(context);wsVisibilityFastRelease(context);wsVisibilityDrawContext=0;InterlockedExchange(&wsVisibilityRenderBusy,0);return -1;
 }
 return 1;
}
static void wsVisibilityEndDraw(int owned){
 if(owned>0){uint64_t perf=wsVisibilityPerformanceBegin();int chart=wsVisibilityChartEndDraw(wsVisibilityDrawContext);if(!wsVisibilityRestore()||!chart)wsVisibilityRenderMemo.valid=0;if(!chart)InterlockedExchange(&wsVisibilityLastError,14);wsVisibilityFastRelease(wsVisibilityDrawContext);wsVisibilityDrawContext=0;InterlockedExchange(&wsVisibilityRenderBusy,0);wsVisibilityPerformanceEnd(WS_PERF_CLEANUP,perf);}
}
__declspec(dllexport) uintptr_t __cdecl WorldSettingsVisibilityDrawTerrain(void*world,void*list,uint32_t flags,uint32_t property,void*renderer){
 unsigned char*w=(unsigned char*)WS_CERT_MODULE("AnnoWelt.dll");if(!w)return 0;
 uint64_t totalPerf=wsVisibilityPerformanceBegin();WSVisibilityDrawContext context;int owned=wsVisibilityBeginDraw(world,list,renderer,&context,property,0);if(owned<0){wsVisibilityPerformanceEnd(WS_PERF_DRAW_TOTAL,totalPerf);return 0;}
 if(owned>0)wsVisibilityChartDrawStarted(&context);
 uint64_t perf=wsVisibilityPerformanceBegin();uintptr_t result=WS_VISIBILITY_NATIVE_DRAW5(w)(world,list,flags,property,renderer);wsVisibilityPerformanceEnd(WS_PERF_NATIVE_DRAW,perf);
 wsVisibilityEndDraw(owned);wsVisibilityPerformanceEnd(WS_PERF_DRAW_TOTAL,totalPerf);return result;
}
__declspec(dllexport) uintptr_t __cdecl WorldSettingsVisibilityDrawTerrainClipped(void*world,void*list,uint32_t flags,const int32_t*rect,uint32_t property,void*renderer){
 unsigned char*w=(unsigned char*)WS_CERT_MODULE("AnnoWelt.dll");if(!w)return 0;
 uint64_t totalPerf=wsVisibilityPerformanceBegin();WSVisibilityDrawContext context;int owned=wsVisibilityBeginDraw(world,list,renderer,&context,property,1);if(owned<0){wsVisibilityPerformanceEnd(WS_PERF_DRAW_TOTAL,totalPerf);return 0;}
 uint64_t perf=wsVisibilityPerformanceBegin();uintptr_t result=WS_VISIBILITY_NATIVE_DRAW6(w)(world,list,flags,rect,property,renderer);wsVisibilityPerformanceEnd(WS_PERF_NATIVE_DRAW,perf);
 wsVisibilityEndDraw(owned);wsVisibilityPerformanceEnd(WS_PERF_DRAW_TOTAL,totalPerf);return result;
}
/* Land-wildlife actor passes run outside the row's valid-quadrant gate. Only
 * the three hash-pinned native land-wildlife classes have these hooks. Their
 * normal/clipped draw ABI is (actor, animation time, renderer); marine actor
 * classes and their native behavior are untouched. */
static int wsVisibilityWildlifeRead(void*actor,unsigned char*module,void**world,int*legacy){
 void*vt=wsCertPointer(actor,0);
 if(!world||!legacy||(vt!=module+0xf0ed0&&vt!=module+0xf13d0&&vt!=module+0xf1738))return 0;
 *legacy=vt==module+0xf0ed0;*world=wsCertPointer(actor,0x28);return *world!=0;
}
static int wsVisibilityWildlifeHidden(void*actor,void*world){
 WSVisibilityWorld view;WSVisibilityDrawContext local;
 const WSVisibilityDrawContext*context=wsVisibilityDrawContext;
 if(!context||context->view.world!=world){
  if(!wsVisibilityWorldRead(world,&view))return wsVisibilityHasPolicy(world)?-1:0;
  if(view.marked<0)return -1;
  if(!view.marked||view.map!=0)return 0;
  if(!wsVisibilityContextRead(&view,&local))return -1;context=&local;
 }
 if(!context->view.marked||context->view.map!=0)return 0;
 float x=0,y=0;uint32_t xb=0,yb=0;
 if(!wsCertRead((unsigned char*)actor+0x40,&x,4)||!wsCertRead((unsigned char*)actor+0x48,&y,4))return -1;
 memcpy(&xb,&x,4);memcpy(&yb,&y,4);
 if((xb&0x7f800000u)==0x7f800000u||(yb&0x7f800000u)==0x7f800000u||
    x<0.0f||y<0.0f||x>=(float)context->view.width||y>=(float)context->view.height)return -1;
 for(uint32_t id=0;id<WS_VISIBILITY_ISLAND_LIMIT;id++)if(context->present[id]){
  const WSVisibilityIsland*island=&context->islands[id];
  if(x>=(float)island->x&&y>=(float)island->y&&
     x<(float)(island->x+island->width)&&y<(float)(island->y+island->height)){
   WSVisibilityChartReadView chart;if(!wsVisibilityChartReadBegin(&context->view,&chart))return -1;
   int visible=wsVisibilityChartMarkContext(context)&&wsVisibilityChartPoint(&context->view,x,y);wsVisibilityChartReadEnd(&chart);return !visible;
  }
 }
 return -1; /* A verified land actor outside every verified island is refused. */
}
__declspec(dllexport) uintptr_t __cdecl WorldSettingsVisibilityDrawWildlife(void*actor,uint32_t time,void*renderer){
 unsigned char*w=(unsigned char*)WS_CERT_MODULE("AnnoWelt.dll");void*world=0;int legacy=0;
 if(!w||!wsVisibilityWildlifeRead(actor,w,&world,&legacy))return 0;
 int hidden=wsVisibilityWildlifeHidden(actor,world);if(hidden){if(hidden<0)InterlockedExchange(&wsVisibilityLastError,7);return 0;}
 return WS_VISIBILITY_NATIVE_WILDLIFE(w,legacy)(actor,time,renderer);
}
__declspec(dllexport) uintptr_t __cdecl WorldSettingsVisibilityDrawWildlifeClipped(void*actor,uint32_t time,void*renderer){
 unsigned char*w=(unsigned char*)WS_CERT_MODULE("AnnoWelt.dll");void*world=0;int legacy=0;
 if(!w||!wsVisibilityWildlifeRead(actor,w,&world,&legacy))return 0;
 int hidden=wsVisibilityWildlifeHidden(actor,world);if(hidden){if(hidden<0)InterlockedExchange(&wsVisibilityLastError,7);return 0;}
 return WS_VISIBILITY_NATIVE_WILDLIFE_CLIPPED(w)(actor,time,renderer);
}
typedef uintptr_t (__cdecl*WSVisibilityNativeResident)(void*,uint32_t,void*);
typedef uintptr_t (__cdecl*WSVisibilityNativeOccurrence)(void*,uint32_t,void*,uint32_t);
typedef int (__cdecl*WSVisibilityNativeExclude)(void*,uint32_t);
typedef uintptr_t (__cdecl*WSVisibilityNativeStatic)(void*,void*,uint32_t,uint32_t,uint32_t,const float*);
#ifndef WS_VISIBILITY_NATIVE_RESIDENT
#define WS_VISIBILITY_NATIVE_RESIDENT(module,rva) ((WSVisibilityNativeResident)((module)+(rva)))
#define WS_VISIBILITY_NATIVE_OCCURRENCE(module,rva) ((WSVisibilityNativeOccurrence)((module)+(rva)))
#define WS_VISIBILITY_NATIVE_EXCLUDE(module,rva) ((WSVisibilityNativeExclude)((module)+(rva)))
#endif
#ifndef WS_VISIBILITY_UNKNOWN_RESIDENT
#define WS_VISIBILITY_UNKNOWN_RESIDENT(target) ((WSVisibilityNativeResident)(target))
#define WS_VISIBILITY_UNKNOWN_OCCURRENCE(target) ((WSVisibilityNativeOccurrence)(target))
#define WS_VISIBILITY_UNKNOWN_TARGET_OK(module,target) (wsVisibilityWithinModule((module),(target),1)&&wsCertMemory((target),1,1))
#endif
#ifndef WS_VISIBILITY_NATIVE_STATIC
#define WS_VISIBILITY_NATIVE_STATIC(target) ((WSVisibilityNativeStatic)(target))
#define WS_VISIBILITY_STATIC_TARGET_OK(target) (wsCertMemory((target),1,1)&&\
 (wsVisibilityWithinModule((unsigned char*)WS_CERT_MODULE("AnnoFrame.dll"),(target),1)||\
  wsVisibilityWithinModule((unsigned char*)WS_CERT_MODULE("AnnoDisplay.dll"),(target),1)||\
  wsVisibilityWithinModule((unsigned char*)WS_CERT_MODULE("AnnoWelt.dll"),(target),1)||\
  wsVisibilityWithinModule((unsigned char*)WS_CERT_MODULE("AnnoScene.dll"),(target),1)||\
  wsVisibilityWithinModule((unsigned char*)WS_CERT_MODULE("AnnoGame.dll"),(target),1)||\
  wsVisibilityWithinModule((unsigned char*)WS_CERT_MODULE("View.dll"),(target),1)))
#endif
#ifndef WS_VISIBILITY_LEGACY_STATIC_TARGET_OK
#define WS_VISIBILITY_LEGACY_STATIC_TARGET_OK(target) wsCertMemory((target),1,1)
#endif
#ifndef WS_VISIBILITY_QUERY_STACK
#define WS_VISIBILITY_QUERY_STACK(address,memory,size) VirtualQuery((address),(memory),(size))
#endif

/* An optional index owns scalar island IDs for this one copied draw context.
 * It never stores native pointers. Unknown geometry or allocation failure
 * simply retains the original ordered rectangle scan. */
#ifndef WS_VISIBILITY_INDEX_ALLOC
#define WS_VISIBILITY_INDEX_ALLOC(bytes) malloc(bytes)
#endif
#ifndef WS_VISIBILITY_INDEX_FREE
#define WS_VISIBILITY_INDEX_FREE(pointer) free(pointer)
#endif
static void wsVisibilityIslandIndexRelease(WSVisibilityFastDraw*f){
 if(!f)return;
 if(f->islandIndex)WS_VISIBILITY_INDEX_FREE(f->islandIndex);
 f->islandIndex=0;f->islandIndexWidth=f->islandIndexHeight=0;
}
static void wsVisibilityIslandIndexPrepare(const WSVisibilityDrawContext*c,WSVisibilityFastDraw*f){
 if(!c||!f||f->islandIndex||c->view.width!=c->view.height||
    (c->view.width!=256u&&c->view.width!=512u&&c->view.width!=1024u&&c->view.width!=2048u))return;
 /* Validate copied scalars before sizing/indexing the owned table. Native
  * rectangles need not end on an8tile boundary; their exact point tests stay
  * in IslandAt, including the ordered fallback for partial/overlap quads. */
 for(uint32_t id=0;id<WS_VISIBILITY_ISLAND_LIMIT;id++)if(c->present[id]){
  const WSVisibilityIsland*p=c->islands+id;
  if(!p->width||!p->height||(p->x&7u)||(p->y&7u)||p->x>c->view.width||p->y>c->view.height||
     p->width>c->view.width-p->x||p->height>c->view.height-p->y)return;
 }
 uint32_t side=c->view.width>>3;size_t bytes=(size_t)side*side;
 unsigned char*index=(unsigned char*)WS_VISIBILITY_INDEX_ALLOC(bytes);if(!index)return;
 memset(index,255,bytes);
 for(uint32_t id=0;id<WS_VISIBILITY_ISLAND_LIMIT;id++)if(c->present[id]){
  const WSVisibilityIsland*p=c->islands+id;
  uint32_t right=(p->x+p->width+7u)>>3,bottom=(p->y+p->height+7u)>>3;
  for(uint32_t z=p->y>>3;z<bottom;z++)for(uint32_t x=p->x>>3;x<right;x++){
   unsigned char*at=index+(size_t)z*side+x;if(*at==255u)*at=(unsigned char)id;
  }
 }
 f->islandIndex=index;f->islandIndexWidth=c->view.width;f->islandIndexHeight=c->view.height;
}

static int wsVisibilityFastPrepare(WSVisibilityDrawContext*c,void*renderer){
 if(!c||c->fast)return 0;
 WSVisibilityFastDraw*f=(WSVisibilityFastDraw*)calloc(1,sizeof(*f));if(!f){InterlockedExchange(&wsVisibilityLastError,8);return 0;}
 f->game=(unsigned char*)WS_CERT_MODULE("AnnoGame.dll");f->display=(unsigned char*)WS_CERT_MODULE("AnnoDisplay.dll");f->renderer=renderer;
 if(!f->game||!f->display||wsCertPointer(renderer,0)!=f->display+0xf63740||
    !wsCertMemory(renderer,8,0)||!wsVisibilityWithinModule(f->display,f->display+0xf63740,0x190)||
    !WS_VISIBILITY_STATIC_TARGET_OK(f->display+0x49410)||!WS_VISIBILITY_STATIC_TARGET_OK(f->display+0x49bd0))goto invalid;
 f->original180=f->display+0x49410;f->original188=f->display+0x49bd0;f->targetsReady=1;
 /* Only this current thread's one committed readable stack region is reused.
  * The local's address belongs to this invocation; reserved/guard regions and
  * heap pointers never acquire a fast-read exemption. No XYZ value is cached. */
 {
  unsigned char anchor=0;MEMORY_BASIC_INFORMATION memory;
  if(WS_VISIBILITY_QUERY_STACK(&anchor,&memory,sizeof memory)==sizeof memory&&memory.State==MEM_COMMIT&&memory.Type==MEM_PRIVATE&&
     !(memory.Protect&(PAGE_GUARD|PAGE_NOACCESS))){
   DWORD protection=memory.Protect&255u;uintptr_t start=(uintptr_t)memory.BaseAddress,at=(uintptr_t)&anchor;
   if((protection==PAGE_READONLY||protection==PAGE_READWRITE||protection==PAGE_WRITECOPY||
       protection==PAGE_EXECUTE_READ||protection==PAGE_EXECUTE_READWRITE||protection==PAGE_EXECUTE_WRITECOPY)&&
      memory.RegionSize<=UINTPTR_MAX-start&&at>=start&&at<start+memory.RegionSize){
    f->stackBegin=start;f->stackEnd=start+memory.RegionSize;
   }
  }
 }
 /* All audited resident/occurrence and production-owner interfaces lie in
  * this pinned native rdata span. Individual getter values are checked fresh
  * for each actor; this removes repeated OS queries, not identity checks. */
 f->actorInterfacesReady=wsVisibilityWithinModule(c->view.module,c->view.module+0xead10u,0x12b68u);
 f->catalogue=wsCertPointer(c->view.world,0x200);f->catalogueVT=wsCertPointer(f->catalogue,0);
 if((f->catalogueVT==f->game+0x20300||f->catalogueVT==f->game+0x20738||f->catalogueVT==f->game+0x20a78||f->catalogueVT==f->game+0x20c90)&&
    wsCertPointer(f->catalogueVT,0xe8)==f->game+0xb4d0&&
    wsCertMemory(f->catalogue,0x218u+sizeof f->definitions,0)&&
    wsVisibilityWithinModule(f->game,f->game+0x1f888,0x7e0)&&
    wsVisibilityWithinModule(f->display,f->display+0xf609d0,0xba0)){
  memcpy(f->definitions,(unsigned char*)f->catalogue+0x218,sizeof f->definitions);f->catalogueReady=1;
  for(uint32_t id=0;id<WS_VISIBILITY_ISLAND_LIMIT;id++)if(c->present[id]){
   const WSVisibilityIsland*p=&c->islands[id];WSVisibilityFastIsland*s=&f->islands[id];
   s->object=p->object;
   if(!wsCertMemory(s->object,0xf0,0))continue;
   s->tiles=(unsigned char*)wsVisibilityFastPointer(s->object,0x10);
   if(!s->tiles||!wsCertMemory(s->tiles,(size_t)p->width*p->height*8u,0))continue;
   memcpy(s->cities,s->object+0x68,sizeof s->cities);s->ready=1;
   for(uint32_t slot=0;slot<15u;slot++)if(s->cities[slot]&&wsCertMemory(s->cities[slot],0x30,0)&&
      wsVisibilityFastPointer(s->cities[slot],0)==c->view.module+0xfc678&&
      wsVisibilityFastPointer(s->cities[slot],0x20)==p->object){
    s->owners[slot]=wsVisibilityFastPointer(s->cities[slot],0x28);
    if(s->owners[slot]&&wsCertMemory(s->owners[slot],0x18,0)&&
       wsVisibilityFastPointer(s->owners[slot],0)==c->view.module+0xfabe0&&
       wsVisibilityFastPointer(s->owners[slot],0x10)==c->view.world)s->cityValid[slot]=1;
   }
  }
 }
 wsVisibilityIslandIndexPrepare(c,f);
 c->fast=f;return 1;
 invalid:free(f);InterlockedExchange(&wsVisibilityLastError,8);return 0;
}
static int wsVisibilityFastRenderer(const WSVisibilityDrawContext*c,void*renderer){
 return c&&c->fast&&c->fast->targetsReady&&c->fast->renderer==renderer&&
  wsVisibilityFastPointer(renderer,0)==c->fast->display+0xf63740;
}
static int wsVisibilityActorDecision(void*actor,const WSVisibilityActorLayout*a,unsigned char*module){
 void*world=wsCertPointer(actor,a->worldOffset);WSVisibilityWorld view;WSVisibilityDrawContext local;
 const WSVisibilityDrawContext*context=wsVisibilityDrawContext;int separate=0;
 if(context&&context->view.marked&&context->view.world!=world)return 0;
 if(!context||context->view.world!=world){
  if(!wsVisibilityWorldRead(world,&view))return !wsVisibilityHasPolicy(world);
  if(!view.marked)return 1;
  if(view.marked<0||!WorldSettingsVisibilityWorldLoaded(world,0,0)||!wsVisibilityContextRead(&view,&local))return 0;
  context=&local;separate=1;
 }
 if(context->view.module!=module)return 0;
 if(separate){WSVisibilityChartReadView read;if(!wsVisibilityChartReadBegin(&context->view,&read))return 0;
  int visible=wsVisibilityChartMarkContext(context)&&wsVisibilityActorInContext(context,actor,a);wsVisibilityChartReadEnd(&read);return visible;}
 return wsVisibilityActorInContext(context,actor,a);
}
/* A successful probe certifies all audited actor fields once for THIS call.
 * Only the exact class's fields are read. A short otherwise-valid object can
 * still use the original individually guarded reads through the fallback. */
static int wsVisibilityFastActorDecision(void*actor,unsigned char*module,const WSVisibilityActorLayout**layout,int*visible){
 const WSVisibilityDrawContext*c=wsVisibilityDrawContext;
 if(!c||!c->view.marked||c->view.module!=module||!c->fast||!c->fast->actorInterfacesReady||
    !wsCertMemory(actor,0x278u,0))return 0;
 void*vt=wsVisibilityFastPointer(actor,0);
 for(size_t i=0;i<sizeof wsVisibilityActorLayouts/sizeof wsVisibilityActorLayouts[0];i++){
  const WSVisibilityActorLayout*a=&wsVisibilityActorLayouts[i];if(vt!=module+a->vtable)continue;
  *layout=a;*visible=0;
  if(wsVisibilityFastPointer(vt,0x38)!=module+a->worldGetter||wsVisibilityFastPointer(vt,0x40)!=module+a->ownerGetter||
     wsVisibilityFastPointer(vt,0xb0)!=module+a->xGetter||wsVisibilityFastPointer(vt,0xc0)!=module+a->zGetter){
   InterlockedExchange(&wsVisibilityLastError,9);return 1;
  }
  if(wsVisibilityFastPointer(actor,a->worldOffset)!=c->view.world)return 1;
  float x,z;memcpy(&x,(unsigned char*)actor+a->xOffset,4);memcpy(&z,(unsigned char*)actor+a->zOffset,4);
  void*owner=a->ownerOffset?wsVisibilityFastPointer(actor,a->ownerOffset):0;
  *visible=wsVisibilityActorValuesInContext(c,a,x,z,owner);return 1;
 }
 return 0;
}
static void*wsVisibilityUnknownActorTarget(void*actor,unsigned char*module,uint32_t slot){
 if(wsVisibilityDrawContext&&wsVisibilityDrawContext->view.marked){InterlockedExchange(&wsVisibilityLastError,9);return 0;}
 void*vt=wsCertPointer(actor,0),*target=wsCertPointer(vt,slot);
 return wsVisibilityWithinModule(module,vt,slot+8u)&&target&&WS_VISIBILITY_UNKNOWN_TARGET_OK(module,target)?target:0;
}
__declspec(dllexport) uintptr_t __cdecl WorldSettingsVisibilityDispatchResident100(void*actor,uint32_t time,void*renderer){
 unsigned char*module=wsVisibilityDrawContext?wsVisibilityDrawContext->view.module:(unsigned char*)WS_CERT_MODULE("AnnoWelt.dll");if(!module)return 0;
 const WSVisibilityActorLayout*a=0;int visible=0,fast=wsVisibilityFastActorDecision(actor,module,&a,&visible);
 if(!fast)a=wsVisibilityActorLayout(actor,module);
 if(!a){void*target=wsVisibilityUnknownActorTarget(actor,module,0x100);return target?WS_VISIBILITY_UNKNOWN_RESIDENT(target)(actor,time,renderer):0;}
 if(!(fast?visible:wsVisibilityActorDecision(actor,a,module)))return 0;
 return WS_VISIBILITY_NATIVE_RESIDENT(module,a->draw)(actor,time,renderer);
}
__declspec(dllexport) uintptr_t __cdecl WorldSettingsVisibilityDispatchResident108(void*actor,uint32_t time,void*renderer){
 unsigned char*module=wsVisibilityDrawContext?wsVisibilityDrawContext->view.module:(unsigned char*)WS_CERT_MODULE("AnnoWelt.dll");if(!module)return 0;
 const WSVisibilityActorLayout*a=0;int visible=0,fast=wsVisibilityFastActorDecision(actor,module,&a,&visible);
 if(!fast)a=wsVisibilityActorLayout(actor,module);
 if(!a){void*target=wsVisibilityUnknownActorTarget(actor,module,0x108);return target?WS_VISIBILITY_UNKNOWN_RESIDENT(target)(actor,time,renderer):0;}
 if(!(fast?visible:wsVisibilityActorDecision(actor,a,module)))return 0;
 return WS_VISIBILITY_NATIVE_RESIDENT(module,a->clipped)(actor,time,renderer);
}
__declspec(dllexport) uintptr_t __cdecl WorldSettingsVisibilityDispatchOccurrence100(void*actor,uint32_t time,void*renderer,uint32_t flags){
 unsigned char*module=wsVisibilityDrawContext?wsVisibilityDrawContext->view.module:(unsigned char*)WS_CERT_MODULE("AnnoWelt.dll");if(!module)return 0;
 const WSVisibilityActorLayout*a=0;int visible=0,fast=wsVisibilityFastActorDecision(actor,module,&a,&visible);
 if(!fast)a=wsVisibilityActorLayout(actor,module);
 if(!a){void*target=wsVisibilityUnknownActorTarget(actor,module,0x100);return target?WS_VISIBILITY_UNKNOWN_OCCURRENCE(target)(actor,time,renderer,flags):0;}
 if(!(fast?visible:wsVisibilityActorDecision(actor,a,module)))return 0;
 return WS_VISIBILITY_NATIVE_OCCURRENCE(module,a->draw)(actor,time,renderer,flags);
}
__declspec(dllexport) int __cdecl WorldSettingsVisibilityMinimapExclude(void*actor,uint32_t reason){
 unsigned char*module=(unsigned char*)WS_CERT_MODULE("AnnoWelt.dll");if(!module)return 1;
 const WSVisibilityActorLayout*a=wsVisibilityActorLayout(actor,module);
 if(!a||a->vtable!=0xee000u||wsCertPointer(module+a->vtable,0x120)!=module+0x1a170)return 1;
 int excluded=WS_VISIBILITY_NATIVE_EXCLUDE(module,0x1a170)(actor,reason);
 return excluded?excluded:!wsVisibilityActorDecision(actor,a,module);
}
__declspec(dllexport) int __cdecl WorldSettingsVisibilitySpriteVisible(const float*position){
 const WSVisibilityDrawContext*context=wsVisibilityDrawContext;
 return !context||!context->view.marked?1:wsVisibilitySpritePoint(context,position);
}
__declspec(dllexport) uintptr_t __cdecl WorldSettingsVisibilityRenderStatic180(void*,void*,uint32_t,uint32_t,uint32_t,const float*);
__declspec(dllexport) uintptr_t __cdecl WorldSettingsVisibilityRenderStatic188(void*,void*,uint32_t,uint32_t,uint32_t,const float*);
#ifndef WS_CHART_CALLER
#define WS_CHART_CALLER() ((uintptr_t)__builtin_return_address(0))
#endif
static uintptr_t wsVisibilityStaticInvoke(void*target,void*renderer,void*frame,uint32_t orientation,uint32_t phase,uint32_t flags,const float*position,uint32_t slot,uintptr_t caller){
 if(slot==0x180u)InterlockedExchange64(&wsVisibilityRenderTarget180,(LONG64)(uintptr_t)target);
 else if(slot==0x188u)InterlockedExchange64(&wsVisibilityRenderTarget188,(LONG64)(uintptr_t)target);
 int marked=wsVisibilityDrawContext&&wsVisibilityDrawContext->view.marked;
 int known=marked&&wsVisibilityFastRenderer(wsVisibilityDrawContext,renderer)&&
  target==(slot==0x180u?wsVisibilityDrawContext->fast->original180:wsVisibilityDrawContext->fast->original188);
 if(!target||(!known&&!(marked?WS_VISIBILITY_STATIC_TARGET_OK(target):WS_VISIBILITY_LEGACY_STATIC_TARGET_OK(target)))){InterlockedExchange(&wsVisibilityLastError,8);return 0;}
 int remembered=marked?wsVisibilityChartGhostSprite(wsVisibilityDrawContext,frame,orientation,caller,position,&phase,&flags):0;
 if(remembered<0||(!remembered&&!WorldSettingsVisibilitySpriteVisible(position)))return 0;
 return WS_VISIBILITY_NATIVE_STATIC(target)(renderer,frame,orientation,phase,flags,position);
}
static uintptr_t wsVisibilityStaticDraw(void*renderer,void*frame,uint32_t orientation,uint32_t phase,uint32_t flags,const float*position,uint32_t slot,uintptr_t caller){
 const WSVisibilityDrawContext*c=wsVisibilityDrawContext;int fast=wsVisibilityFastRenderer(c,renderer);
 void*target=fast?wsVisibilityFastPointer(c->fast->display+0xf63740,slot):wsCertPointer(wsCertPointer(renderer,0),slot);
 void*hook=slot==0x180u?(void*)WorldSettingsVisibilityRenderStatic180:(void*)WorldSettingsVisibilityRenderStatic188;
 if(target==hook){
  unsigned char*display=fast?c->fast->display:(unsigned char*)WS_CERT_MODULE("AnnoDisplay.dll");
  if(!display||(!fast&&wsCertPointer(renderer,0)!=display+0xf63740)){InterlockedExchange(&wsVisibilityLastError,8);return 0;}
  target=display+(slot==0x180u?0x49410u:0x49bd0u);
 }
 return wsVisibilityStaticInvoke(target,renderer,frame,orientation,phase,flags,position,slot,caller);
}
__declspec(dllexport) uintptr_t __cdecl WorldSettingsVisibilityDrawStatic180(void*renderer,void*frame,uint32_t orientation,uint32_t phase,uint32_t flags,const float*position){
 return wsVisibilityStaticDraw(renderer,frame,orientation,phase,flags,position,0x180,WS_CHART_CALLER());
}
__declspec(dllexport) uintptr_t __cdecl WorldSettingsVisibilityDrawStatic188(void*renderer,void*frame,uint32_t orientation,uint32_t phase,uint32_t flags,const float*position){
 return wsVisibilityStaticDraw(renderer,frame,orientation,phase,flags,position,0x188,WS_CHART_CALLER());
}
static uintptr_t wsVisibilityRenderStatic(void*renderer,void*frame,uint32_t orientation,uint32_t phase,uint32_t flags,const float*position,uint32_t slot,uintptr_t caller){
 const WSVisibilityDrawContext*c=wsVisibilityDrawContext;
 if(wsVisibilityFastRenderer(c,renderer))return wsVisibilityStaticInvoke(slot==0x180u?c->fast->original180:c->fast->original188,renderer,frame,orientation,phase,flags,position,slot,caller);
 unsigned char*display=(unsigned char*)WS_CERT_MODULE("AnnoDisplay.dll");
 if(!display||wsCertPointer(renderer,0)!=display+0xf63740){InterlockedExchange(&wsVisibilityLastError,8);return 0;}
 return wsVisibilityStaticInvoke(display+(slot==0x180u?0x49410u:0x49bd0u),renderer,frame,orientation,phase,flags,position,slot,caller);
}
__declspec(dllexport) uintptr_t __cdecl WorldSettingsVisibilityRenderStatic180(void*renderer,void*frame,uint32_t orientation,uint32_t phase,uint32_t flags,const float*position){
 return wsVisibilityRenderStatic(renderer,frame,orientation,phase,flags,position,0x180,WS_CHART_CALLER());
}
__declspec(dllexport) uintptr_t __cdecl WorldSettingsVisibilityRenderStatic188(void*renderer,void*frame,uint32_t orientation,uint32_t phase,uint32_t flags,const float*position){
 return wsVisibilityRenderStatic(renderer,frame,orientation,phase,flags,position,0x188,WS_CHART_CALLER());
}
__declspec(dllexport) uintptr_t __cdecl WorldSettingsVisibilityCreateMap(void*map,uint32_t flags,void*rect){
 unsigned char*w=(unsigned char*)WS_CERT_MODULE("AnnoWelt.dll");WSVisibilityWorld v;
 if(!w)return 0;
 void*world=wsCertPointer(map,0x18);
 if(!wsVisibilityWorldRead(world,&v))return wsVisibilityHasPolicy(world)?0:WS_VISIBILITY_NATIVE_MAP(w)(map,flags,rect);
 if(!v.marked)return WS_VISIBILITY_NATIVE_MAP(w)(map,flags,rect);
 if(!WorldSettingsVisibilityWorldLoaded(world,0,0))return 0;
 if(v.map!=0&&v.enemy!=0)return WS_VISIBILITY_NATIVE_MAP(w)(map,flags,rect);
 WSVisibilityMapView before,after;WSVisibilityDrawContext local;
 if(!wsVisibilityMapRead(map,&v,&before)){InterlockedExchange(&wsVisibilityLastError,4);return 0;}
 const WSVisibilityDrawContext*context=wsVisibilityDrawContext;
 if(!context||context->view.world!=world||context->view.viewer!=v.viewer||context->view.flags!=v.flags){
  if(!wsVisibilityContextRead(&v,&local)){wsVisibilityClearMap(&before);InterlockedIncrement(&wsVisibilityMapGeneration);InterlockedExchange(&wsVisibilityLastError,4);return 0;}context=&local;
 }
 WSVisibilityChartReadView chart;
 if(!wsVisibilityChartReadBegin(&v,&chart)){wsVisibilityClearMap(&before);InterlockedIncrement(&wsVisibilityMapGeneration);return 0;}
 if(!wsVisibilityChartMarkContext(context)){wsVisibilityChartReadEnd(&chart);return 0;}
 int32_t refresh[4];uint32_t nativeFlags=flags;int locked=0;LONG generation=InterlockedCompareExchange(&wsVisibilityMapGeneration,0,0);
 if(v.map==0||!v.enemy){
  if(InterlockedCompareExchange(&wsVisibilityMapRefreshBusy,1,0)){InterlockedExchange(&wsVisibilityLastError,10);wsVisibilityChartReadEnd(&chart);return 0;}
  locked=1;
  if(!wsVisibilityMapRefreshPlan(&before,context,rect,&nativeFlags,refresh)){
   wsVisibilityClearMap(&before);InterlockedIncrement(&wsVisibilityMapGeneration);InterlockedExchange(&wsVisibilityLastError,4);InterlockedExchange(&wsVisibilityMapRefreshBusy,0);wsVisibilityChartReadEnd(&chart);return 0;
  }
  rect=refresh;
 }
 uintptr_t result=WS_VISIBILITY_NATIVE_MAP(w)(map,nativeFlags,rect);
 /* The pinned native renderer does not resize/reallocate this bitmap. Verify
  * that ownership still matches instead of writing a retained pre-call buffer. */
 if(!wsVisibilityMapRead(map,&v,&after)||after.pixels!=before.pixels||after.width!=before.width||after.height!=before.height){
  if(wsVisibilityMapRead(map,&v,&after))wsVisibilityClearMap(&after);
  InterlockedIncrement(&wsVisibilityMapGeneration);InterlockedExchange(&wsVisibilityLastError,4);if(locked)InterlockedExchange(&wsVisibilityMapRefreshBusy,0);wsVisibilityChartReadEnd(&chart);return 0;
 }
 if(!wsVisibilityMaskMapView(&after,context)){
  InterlockedIncrement(&wsVisibilityMapGeneration);if(locked)InterlockedExchange(&wsVisibilityMapRefreshBusy,0);wsVisibilityChartReadEnd(&chart);return 0;
 }
 if(locked){wsVisibilityMapRefreshCommit(&after,context,generation);InterlockedExchange(&wsVisibilityMapRefreshBusy,0);}
 wsVisibilityChartReadEnd(&chart);
 return result;
}
static int wsVisibilityMapRefreshFromDraw(const WSVisibilityDrawContext*context){
 if(context->view.map!=0&&context->view.enemy!=0)return 1;
 void*map=wsCertPointer(context->view.world,0x220);if(!map)return 1;
 WSVisibilityMapView current;
 if(!wsVisibilityMapRead(map,&context->view,&current)){InterlockedExchange(&wsVisibilityLastError,4);return 0;}
 if(InterlockedCompareExchange(&wsVisibilityMapRefreshBusy,1,0)){InterlockedExchange(&wsVisibilityLastError,10);return 0;}
 int32_t empty[4]={0},planned[4];uint32_t flags=0;
 int valid=wsVisibilityMapRefreshPlan(&current,context,empty,&flags,planned);
 InterlockedExchange(&wsVisibilityMapRefreshBusy,0);
 if(!valid){InterlockedExchange(&wsVisibilityLastError,4);return 0;}
 /* The original map method has no meaningful native return. Its guarded
  * wrapper validates ownership/commits the scalar memo after masking. */
 if(flags&3u)(void)WorldSettingsVisibilityCreateMap(map,0,empty);
 return 1;
}
/* Fixed bounded read-only diagnostic values: version, saved-policy mask,
 * masked/restored row counts, filtered bitmap calls and last bounds error.
 */
__declspec(dllexport) int WorldSettingsVisibilityDiagnostics(uint32_t*out,uint32_t count){
 if(!out||count!=7u)return 0;
 uint32_t values[7]={1u,WS_VISIBILITY_POLICY_MASK,
  (uint32_t)InterlockedCompareExchange(&wsVisibilityMaskedTiles,0,0),
  (uint32_t)InterlockedCompareExchange(&wsVisibilityRestoredTiles,0,0),
  (uint32_t)InterlockedCompareExchange(&wsVisibilityMaskedMaps,0,0),
  (uint32_t)InterlockedCompareExchange(&wsVisibilityLastError,0,0),wsVisibilityBackupCount};
 memcpy(out,values,sizeof values);return 1;
}
__declspec(dllexport) DWORD WINAPI WorldSettingsCopyVisibilityDiagnostics(void*out){
 if(!out||!wsMineralPersistenceWritable(out,7u*sizeof(uint32_t)))return 0;
 return WorldSettingsVisibilityDiagnostics((uint32_t*)out,7u)?7u*sizeof(uint32_t):0u;
}
__declspec(dllexport) DWORD WINAPI WorldSettingsCopyVisibilityRenderTargets(void*out){
 if(!out||!wsMineralPersistenceWritable(out,2u*sizeof(uint64_t)))return 0;
 uint64_t targets[2]={(uint64_t)InterlockedCompareExchange64(&wsVisibilityRenderTarget180,0,0),
  (uint64_t)InterlockedCompareExchange64(&wsVisibilityRenderTarget188,0,0)};
 memcpy(out,targets,sizeof targets);return sizeof targets;
}
#include "start_visibility_chart.inc"
