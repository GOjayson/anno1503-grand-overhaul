/* Preferred starts relocate only the human fleet after the island plan exists.
 * The original packing reservations stay intact, so this choice never rerolls
 * an island. A conservative 49-square water box also contains both escorts and
 * their native 16-tile island-clearance checks. No native terrain is modified.
 */
static int32_t wsPreferredIsland=-1,wsExpectedDisasters=1;

static int wsStartingIslandOrdinary(uint32_t index){
 if(index>=planCount)return 0;
 const WSPlanIsland*p=&planned[index];
 if(p->templateIndex>=WS_COUNT)return 0;
 return !p->cultures&&!wsTemplateFaction(&wsTemplates[p->templateIndex]);
}
static int wsPreferredWaterFits(int x,int y){
 if(x<24||y<24||x+25>(int)wsWorld||y+25>(int)wsWorld)return 0;
 WSPlanIsland reserve={0,(uint32_t)x-24u,(uint32_t)y-24u,49u,49u,0,0,0,0,0,0};
 for(uint32_t i=0;i<planCount;i++)if(!wsSeparated(&reserve,&planned[i],planSpacing))return 0;
 for(uint32_t i=0;i<wsBaseShipReserveCount;i++)if(!wsSeparated(&reserve,&wsActiveShipReserves[i],0))return 0;
 return 1;
}
static void wsPreferredConsider(const WSPlanIsland*p,int x,int y,int*found,int*bestX,int*bestY,uint64_t*best){
 if(!wsPreferredWaterFits(x,y))return;
 int64_t dx=(int64_t)x*2-((int64_t)p->x*2+p->width);
 int64_t dy=(int64_t)y*2-((int64_t)p->y*2+p->height);
 uint64_t distance=(uint64_t)(dx*dx+dy*dy);
 if(!*found||distance<*best){*found=1;*bestX=x;*bestY=y;*best=distance;}
}
static int wsPreferredWater(uint32_t index,float*x,float*y){
 if(!wsStartingIslandOrdinary(index))return 0;
 const WSPlanIsland*p=&planned[index];int found=0,bestX=0,bestY=0;uint64_t best=0;
 int left=(int)p->x-25-(int)planSpacing,right=(int)(p->x+p->width)+24+(int)planSpacing;
 int top=(int)p->y-25-(int)planSpacing,bottom=(int)(p->y+p->height)+24+(int)planSpacing;
 int cx=(int)(p->x+p->width/2u),cy=(int)(p->y+p->height/2u);
 wsPreferredConsider(p,left,cy,&found,&bestX,&bestY,&best);
 wsPreferredConsider(p,right,cy,&found,&bestX,&bestY,&best);
 wsPreferredConsider(p,cx,top,&found,&bestX,&bestY,&best);
 wsPreferredConsider(p,cx,bottom,&found,&bestX,&bestY,&best);
 for(uint32_t at=0;at<=p->height;at+=8u){int along=(int)(p->y+at);
  wsPreferredConsider(p,left,along,&found,&bestX,&bestY,&best);
  wsPreferredConsider(p,right,along,&found,&bestX,&bestY,&best);
 }
 for(uint32_t at=0;at<=p->width;at+=8u){int along=(int)(p->x+at);
  wsPreferredConsider(p,along,top,&found,&bestX,&bestY,&best);
  wsPreferredConsider(p,along,bottom,&found,&bestX,&bestY,&best);
 }
 if(found){*x=(float)bestX+0.5f;*y=(float)bestY+0.5f;}return found;
}
__declspec(dllexport) int WorldSettingsStartingIslandEligible(uint32_t index){
 float x,y;return wsPreviewCache.state==1&&wsPreferredWater(index,&x,&y);
}
__declspec(dllexport) int WorldSettingsStartingIslandChosen(void){
 return wsPreviewCache.state==1?wsPreferredIsland:-1;
}
#include "fair_starts.inc"
static int wsApplyLegacyPreferredStart(const WSWorldSettings*s,char*error,uint32_t cap){
 wsPreferredIsland=-1;wsExpectedDisasters=s->disasters;
 if(s->startIsland<0&&s->startClimate<0)return 1;
 float x=0,y=0;int32_t chosen=-1;
 if(s->startIsland>=0){
  uint32_t id=(uint32_t)s->startIsland;
  if(!wsStartingIslandOrdinary(id)||(s->startClimate>=0&&planned[id].climate!=(uint32_t)s->startClimate)){
   wsMessage(error,cap,"Choose an uninhabited ordinary island matching the preferred climate.");return 0;
  }
  if(wsPreferredWater(id,&x,&y))chosen=s->startIsland;
 }else for(uint32_t i=0;i<planCount;i++){
  if(planned[i].climate==(uint32_t)s->startClimate&&wsPreferredWater(i,&x,&y)){chosen=(int32_t)i;break;}
 }
 if(chosen<0){wsMessage(error,cap,"No clear coastal starting position fits beside that island or climate. Choose another island, Any climate, or regenerate.");return 0;}
 if(!wsExpectedSceneShipCount||wsExpectedSceneShips[0].owner||wsBaseShipReserveCount>=WS_MAX_START_SHIPS){wsMessage(error,cap,"The preferred starting fleet reservation is unavailable.");return 0;}
 float dx=x-wsExpectedSceneShips[0].x,dy=y-wsExpectedSceneShips[0].y;
 for(uint32_t i=0;i<wsExpectedSceneShipCount;i++)if(!wsExpectedSceneShips[i].owner){wsExpectedSceneShips[i].x+=dx;wsExpectedSceneShips[i].y+=dy;}
 wsPreferredStartX=x;wsPreferredStartY=y;wsPreferredStartActive=1;wsPreferredIsland=chosen;
 wsActiveShipReserveCount=wsBaseShipReserveCount;
 wsActiveShipReserves[wsActiveShipReserveCount++]=(WSPlanIsland){0,(uint32_t)x-24u,(uint32_t)y-24u,49u,49u,0,0,0,0,0,0};
 return 1;
}
static int wsApplyPreferredStart(const WSWorldSettings*s,char*error,uint32_t cap){
 if(s->fairStarts)return wsApplyFairStarts(s,error,cap);
 wsAssignedStartCount=0;wsFairOwnerMask=0;wsFairCacheValid=0;
 for(uint32_t i=0;i<4u;i++)wsAssignedStartIsland[i]=-1;
 if(!wsApplyLegacyPreferredStart(s,error,cap))return 0;
 wsAssignedStartCount=(uint32_t)s->aiCount+1u;
 for(uint32_t owner=0;owner<wsAssignedStartCount;owner++){
  uint32_t island;
  if(wsStartResourceAnchor(s,owner,&island))wsAssignedStartIsland[owner]=(int32_t)island;
 }
 return 1;
}
