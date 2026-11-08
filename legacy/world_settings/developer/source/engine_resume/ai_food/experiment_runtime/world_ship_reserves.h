/* Runtime world/ship contract. Reservations are a preset/fleet-independent
 * union, keeping world geometry independent of starting difficulty and fleet.
 * 1024 keeps stock coordinates; other sizes use separated fixed anchors.
 */
#define WS_MAX_START_SHIPS 32u
typedef struct WSSceneShip { uint32_t owner,definition; float x,y; } WSSceneShip;
static uint32_t wsWorld=1024u;
static WSPlanIsland wsActiveShipReserves[WS_MAX_START_SHIPS];
static uint32_t wsActiveShipReserveCount;
static WSSceneShip wsExpectedSceneShips[WS_MAX_START_SHIPS];
static uint32_t wsExpectedSceneShipCount,wsShipDifficulty;
static const WSPlanIsland wsStockShipReserves[]={
 {0,320,230,49,49,0,0,0,0,0},{0,387,452,49,49,0,0,0,0,0},
 {0,426,398,49,49,0,0,0,0,0},{0,532,526,49,49,0,0,0,0,0},
 {0,542,411,49,49,0,0,0,0,0},{0,581,410,49,49,0,0,0,0,0},
 {0,668,510,49,49,0,0,0,0,0}
};
static const float wsStockShipXY[3][5][2]={
 {{566.5f,435.5f},{411.5f,476.5f},{605.5f,434.5f},{692.5f,534.5f},{0,0}},
 {{450.5f,422.5f},{344.5f,254.5f},{605.5f,434.5f},{692.5f,534.5f},{556.5f,550.5f}},
 {{566.5f,435.5f},{411.5f,476.5f},{605.5f,434.5f},{692.5f,534.5f},{556.5f,550.5f}}
};
/* The guarded engine profile appends the complete 256x256 lookup and
 * 32x32 ship refinement tables while preserving every native field offset.
 * Actual game Start additionally requires the atomic engine activation. */
static int wsWorldSizeAllowed(int32_t n){return n==256||n==512||n==1024||n==2048;}
static void wsWorldShipPosition(uint32_t owner,float*x,float*y){
 if(wsWorld==1024u){*x=wsStockShipXY[wsShipDifficulty][owner][0];*y=wsStockShipXY[wsShipDifficulty][owner][1];return;}
 /* Small worlds need continuous land space: spread ships along one edge,
  * leaving the upper200 tiles available for80/96/128 tile island templates. */
 if(wsWorld==256u){static const float smallX[5]={128.5f,32.5f,80.5f,176.5f,224.5f};*x=smallX[owner];*y=224.5f;return;}
 uint32_t q=wsWorld/4u;
 *x=(float)(owner==0?wsWorld/2u:(owner==1||owner==4?q:3u*q))+0.5f;
 *y=(float)(owner==0?wsWorld/3u:(owner==1||owner==2?q:3u*q))+0.5f;
}
static int wsAddSceneShip(uint32_t owner,uint32_t definition,float x,float y){
 if(wsExpectedSceneShipCount>=WS_MAX_START_SHIPS||!(x>=16.0f&&y>=16.0f&&x<(float)wsWorld-16.0f&&y<(float)wsWorld-16.0f))return 0;
 uint32_t i=wsExpectedSceneShipCount++;
 wsExpectedSceneShips[i]=(WSSceneShip){owner,definition,x,y};
 return 1;
}
static int wsConfigureWorldSize(const WSWorldSettings*s){
 wsExpectedSceneShipCount=wsActiveShipReserveCount=0;
 if(!s||!wsWorldSizeAllowed(s->worldSize)||s->difficulty<0||s->difficulty>2||s->startingFleet<0||s->startingFleet>2)return 0;
 wsWorld=(uint32_t)s->worldSize;wsShipDifficulty=(uint32_t)s->difficulty;
 uint32_t stockCount=s->difficulty==0?4u:5u;
 for(uint32_t owner=0;owner<stockCount;owner++){
  float x,y;wsWorldShipPosition(owner,&x,&y);
  if(!wsAddSceneShip(owner,!owner&&s->startingFleet?1503u:1502u,x,y))return 0;
 }
 if(s->startingFleet){float x,y;wsWorldShipPosition(0,&x,&y);uint32_t def=s->startingFleet==1?1504u:1502u;
  if(!wsAddSceneShip(0,def,x-6.0f,y+6.0f)||!wsAddSceneShip(0,def,x+6.0f,y+6.0f))return 0;
 }
 if(wsWorld==1024u){memcpy(wsActiveShipReserves,wsStockShipReserves,sizeof wsStockShipReserves);wsActiveShipReserveCount=(uint32_t)(sizeof wsStockShipReserves/sizeof wsStockShipReserves[0]);}
 else{for(uint32_t owner=0;owner<5;owner++){float x,y;wsWorldShipPosition(owner,&x,&y);wsActiveShipReserves[owner]=(WSPlanIsland){0,(uint32_t)x-24u,(uint32_t)y-24u,49u,49u,0,0,0,0,0};}wsActiveShipReserveCount=5;}
 return 1;
}
