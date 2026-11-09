/* Scalar metadata only. No cached address is ever dereferenced or restored.
 * The current validated bitmap is the only write target in its own callback. */
typedef struct WSVisibilityMapIslandMemo {
 uintptr_t identity;uint32_t x,y,width,height;unsigned char present,known;
} WSVisibilityMapIslandMemo;
typedef struct WSVisibilityMapMemo {
 uintptr_t world,map,pixels;uint32_t width,height,worldWidth,worldHeight,viewer,policy;
 LONG generation;uint32_t valid,visionCount;
 WSVisibilityMapIslandMemo islands[WS_VISIBILITY_ISLAND_LIMIT];
 WSVisibilityVisionSource vision[WS_VISIBILITY_VISION_LIMIT];
} WSVisibilityMapMemo;
static WSVisibilityMapMemo wsVisibilityMapMemo;
static volatile LONG wsVisibilityMapRefreshBusy;
static int32_t wsVisibilityClampCoordinate(int32_t n,uint32_t size){return n<0?0:((uint32_t)n>size?(int32_t)size:n);}
static void wsVisibilityUnionRect(int32_t out[4],int32_t left,int32_t top,int32_t right,int32_t bottom){
 if(right<=left||bottom<=top)return;
 if(out[2]<=out[0]||out[3]<=out[1]){out[0]=left;out[1]=top;out[2]=right;out[3]=bottom;return;}
 if(left<out[0])out[0]=left;if(top<out[1])out[1]=top;if(right>out[2])out[2]=right;if(bottom>out[3])out[3]=bottom;
}
static void wsVisibilityUnionVision(int32_t out[4],const WSVisibilityVisionSource*s,const WSVisibilityWorld*v){
 int32_t left=(int32_t)(s->left-WS_VISIBILITY_SIGHT_RADIUS),top=(int32_t)(s->top-WS_VISIBILITY_SIGHT_RADIUS);
 int32_t right=(int32_t)(s->right+WS_VISIBILITY_SIGHT_RADIUS)+1,bottom=(int32_t)(s->bottom+WS_VISIBILITY_SIGHT_RADIUS)+1;
 wsVisibilityUnionRect(out,wsVisibilityClampCoordinate(left,v->width),wsVisibilityClampCoordinate(top,v->height),
  wsVisibilityClampCoordinate(right,v->width),wsVisibilityClampCoordinate(bottom,v->height));
}
static int wsVisibilityMapMemoMatches(const WSVisibilityMapView*m,const WSVisibilityDrawContext*c){
 const WSVisibilityMapMemo*p=&wsVisibilityMapMemo;const WSVisibilityWorld*v=&c->view;
 return p->valid&&p->generation==InterlockedCompareExchange(&wsVisibilityMapGeneration,0,0)&&
  p->world==(uintptr_t)v->world&&p->map==(uintptr_t)m->object&&p->pixels==(uintptr_t)m->pixels&&
  p->width==m->width&&p->height==m->height&&p->worldWidth==v->width&&p->worldHeight==v->height&&
  p->viewer==v->viewer&&p->policy==(v->flags&WS_VISIBILITY_POLICY_MASK);
}
static int wsVisibilityMapRefreshPlan(const WSVisibilityMapView*m,const WSVisibilityDrawContext*c,const void*rect,uint32_t*flags,int32_t out[4]){
 const WSVisibilityWorld*v=&c->view;int matching=wsVisibilityMapMemoMatches(m,c);memset(out,0,16);
 if(rect){
  if(!wsCertRead(rect,out,16)||out[2]<out[0]||out[3]<out[1])return 0;
  out[0]=wsVisibilityClampCoordinate(out[0],v->width);out[2]=wsVisibilityClampCoordinate(out[2],v->width);
  out[1]=wsVisibilityClampCoordinate(out[1],v->height);out[3]=wsVisibilityClampCoordinate(out[3],v->height);
 }else if(!matching){out[2]=(int32_t)v->width;out[3]=(int32_t)v->height;}
 /* Revealed geography is allowed everywhere. A reset/failed masked bitmap
  * needs one bounded complete terrain rebuild, then unchanged frames stay
  * owner-only/idle. Terra instead rebuilds only newly known island bounds. */
 if(!matching&&v->map!=0){out[0]=out[1]=0;out[2]=(int32_t)v->width;out[3]=(int32_t)v->height;*flags|=2u;}
 if(v->map==0)for(uint32_t id=0;id<WS_VISIBILITY_ISLAND_LIMIT;id++)if(c->present[id]){
  const WSVisibilityIsland*s=&c->islands[id];const WSVisibilityMapIslandMemo*old=&wsVisibilityMapMemo.islands[id];
  int known=(s->discovered&(1u<<v->viewer))!=0;
  if(known&&(!matching||!old->present||!old->known||old->identity!=(uintptr_t)s->object||
     old->x!=s->x||old->y!=s->y||old->width!=s->width||old->height!=s->height)){
   /* Terra previously cleared owner colors as well as heights. Restore both
    * native channels even when a stationary observer's sight did not change. */
   wsVisibilityUnionRect(out,(int32_t)s->x,(int32_t)s->y,(int32_t)(s->x+s->width),(int32_t)(s->y+s->height));*flags|=3u;
  }
 }
 if(!v->enemy&&(!matching||wsVisibilityMapMemo.visionCount!=c->visionCount||
    memcmp(wsVisibilityMapMemo.vision,c->vision,(size_t)c->visionCount*sizeof(c->vision[0])))){
  if(matching)for(uint32_t i=0;i<wsVisibilityMapMemo.visionCount;i++)wsVisibilityUnionVision(out,&wsVisibilityMapMemo.vision[i],v);
  for(uint32_t i=0;i<c->visionCount;i++)wsVisibilityUnionVision(out,&c->vision[i],v);
  *flags|=1u;
 }
 return 1;
}
static void wsVisibilityMapRefreshCommit(const WSVisibilityMapView*m,const WSVisibilityDrawContext*c,LONG generation){
 WSVisibilityMapMemo*p=&wsVisibilityMapMemo;const WSVisibilityWorld*v=&c->view;p->valid=0;
 p->world=(uintptr_t)v->world;p->map=(uintptr_t)m->object;p->pixels=(uintptr_t)m->pixels;
 p->width=m->width;p->height=m->height;p->worldWidth=v->width;p->worldHeight=v->height;
 p->viewer=v->viewer;p->policy=v->flags&WS_VISIBILITY_POLICY_MASK;p->generation=generation;
 p->visionCount=c->visionCount;memcpy(p->vision,c->vision,(size_t)c->visionCount*sizeof(c->vision[0]));
 memset(p->islands,0,sizeof p->islands);
 for(uint32_t id=0;id<WS_VISIBILITY_ISLAND_LIMIT;id++)if(c->present[id]){
  const WSVisibilityIsland*s=&c->islands[id];WSVisibilityMapIslandMemo*to=&p->islands[id];
  to->present=1;to->identity=(uintptr_t)s->object;to->x=s->x;to->y=s->y;to->width=s->width;to->height=s->height;
  to->known=(s->discovered&(1u<<v->viewer))!=0;
 }
 p->valid=1;
}
