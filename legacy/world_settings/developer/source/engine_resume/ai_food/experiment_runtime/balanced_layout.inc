/* Keep the verified packing constraints, then distribute islands over the
 * available ocean. This uses its own RNG: template selection and fertility
 * must not depend on how many placement candidates were evaluated.
 */
static int wsCompactPack(uint32_t count,uint32_t spacing){
 uint32_t order[WS_LIMIT];for(uint32_t i=0;i<count;i++)order[i]=i;
 for(uint32_t i=1;i<count;i++){uint32_t key=order[i],j=i;while(j&&planned[order[j-1]].width<planned[key].width){order[j]=order[j-1];j--;}order[j]=key;}
 for(uint32_t i=0;i<count;i++){
  WSPlanIsland*p=&planned[order[i]];int found=0;uint32_t bestX=0,bestY=0;
  uint32_t reserveCount=wsActiveShipReserveCount;
  for(uint32_t yi=0;yi<=i+reserveCount;yi++){for(uint32_t xi=0;xi<=i+reserveCount;xi++){
   WSPlanIsland q=*p;
   q.x=xi==0?spacing:(xi<=i?planned[order[xi-1]].x+planned[order[xi-1]].width+spacing:wsActiveShipReserves[xi-i-1].x+wsActiveShipReserves[xi-i-1].width+spacing);
   q.y=yi==0?spacing:(yi<=i?planned[order[yi-1]].y+planned[order[yi-1]].height+spacing:wsActiveShipReserves[yi-i-1].y+wsActiveShipReserves[yi-i-1].height+spacing);
   /* Native loading snaps down to eight tiles. Pack on that grid now. */
   q.x=(q.x+7u)&~7u;q.y=(q.y+7u)&~7u;
   if(q.x+q.width+spacing>wsWorld||q.y+q.height+spacing>wsWorld)continue;int fits=1;
   for(uint32_t j=0;j<i;j++)if(!wsSeparated(&q,&planned[order[j]],spacing)){fits=0;break;}
   for(uint32_t j=0;j<reserveCount&&fits;j++)if(!wsSeparated(&q,&wsActiveShipReserves[j],spacing))fits=0;
   if(fits&&(!found||q.y<bestY||(q.y==bestY&&q.x<bestX))){found=1;bestX=q.x;bestY=q.y;}
  }}
  if(!found)return 0;p->x=bestX;p->y=bestY;p->id=order[i];
 }return 1;
}

typedef struct WSLayoutScore {uint32_t nearest;uint64_t crowding;} WSLayoutScore;
static uint32_t wsLayoutRandom(uint32_t *state){uint32_t n=*state;n^=n<<13;n^=n>>17;n^=n<<5;return *state=n;}
static uint32_t wsLayoutDistance(const WSPlanIsland*a,const WSPlanIsland*b){
 uint32_t dx=a->x>b->x+b->width?a->x-b->x-b->width:(b->x>a->x+a->width?b->x-a->x-a->width:0);
 uint32_t dy=a->y>b->y+b->height?a->y-b->y-b->height:(b->y>a->y+a->height?b->y-a->y-a->height:0);
 return dx*dx+dy*dy;
}
static int wsLayoutScore(const WSPlanIsland*q,uint32_t skip,uint32_t count,uint32_t spacing,uint32_t floor,WSLayoutScore*out){
 WSLayoutScore score={2u*wsWorld*wsWorld,0};
 for(uint32_t j=0;j<wsActiveShipReserveCount;j++)if(!wsSeparated(q,&wsActiveShipReserves[j],spacing))return 0;
 for(uint32_t j=0;j<count;j++)if(j!=skip){
  if(!wsSeparated(q,&planned[j],spacing))return 0;
  uint32_t distance=wsLayoutDistance(q,&planned[j]);
  if(distance<floor)return 0;
  if(distance<score.nearest)score.nearest=distance;
  score.crowding+=((uint64_t)1u<<30)/(distance+64u);
 }
 *out=score;return 1;
}
static int wsLayoutBetter(const WSLayoutScore*a,const WSLayoutScore*b){return a->nearest>b->nearest||(a->nearest==b->nearest&&a->crowding<b->crowding);}
static void wsLayoutCandidate(uint32_t index,uint32_t count,uint32_t spacing,uint32_t x,uint32_t y,WSPlanIsland*best,WSLayoutScore*score){
 WSPlanIsland q=planned[index];WSLayoutScore candidate;q.x=x;q.y=y;
 if(wsLayoutScore(&q,index,count,spacing,score->nearest,&candidate)&&wsLayoutBetter(&candidate,score)){*best=q;*score=candidate;}
}
static void wsSpreadPack(uint32_t count,uint32_t spacing){
 uint32_t state=rngState^0x9e3779b9u;if(!state)state=0x15032026u;
 uint32_t order[WS_LIMIT],passes=count<=32?6u:(count<=64?4u:3u),step=wsWorld/(count<=32?32u:16u);
 if(step<8u)step=8u;step&=~7u;
 uint32_t low=(spacing+7u)&~7u;
 for(uint32_t pass=0;pass<passes;pass++){
  for(uint32_t i=0;i<count;i++)order[i]=i;
  for(uint32_t i=count;i>1;i--){uint32_t j=wsLayoutRandom(&state)%i,tmp=order[i-1];order[i-1]=order[j];order[j]=tmp;}
  uint32_t moved=0;
  for(uint32_t at=0;at<count;at++){
   uint32_t index=order[at];WSPlanIsland best=planned[index];WSLayoutScore score;
   if(!wsLayoutScore(&best,index,count,spacing,0,&score))continue;
   uint32_t highX=(wsWorld-spacing-best.width)&~7u,highY=(wsWorld-spacing-best.height)&~7u;
   /* A grid covering the entire legal map, including its outermost rows and
    * columns, avoids the original bottom-left packing preference. Shift the
    * interior grid each pass to avoid a fixed row pattern. */
   uint32_t offsetX=(wsLayoutRandom(&state)%(step/8u))*8u,offsetY=(wsLayoutRandom(&state)%(step/8u))*8u;
   for(uint32_t y=low;y<=highY;){
    for(uint32_t x=low;x<=highX;){
     wsLayoutCandidate(index,count,spacing,x,y,&best,&score);
     if(x==highX)break;
     uint32_t next=x==low?low+step+offsetX:x+step;x=next<highX?next:highX;
    }
    if(y==highY)break;
    uint32_t next=y==low?low+step+offsetY:y+step;y=next<highY?next:highY;
   }
   /* Native-grid random samples and a local final pass soften regular rows
    * without changing validated shapes or consuming the scene RNG. */
   for(uint32_t sample=0;sample<96u;sample++){
    uint32_t x=low+(wsLayoutRandom(&state)%((highX-low)/8u+1u))*8u;
    uint32_t y=low+(wsLayoutRandom(&state)%((highY-low)/8u+1u))*8u;
    wsLayoutCandidate(index,count,spacing,x,y,&best,&score);
   }
   if(pass+1u==passes){
    uint32_t startX=best.x>24u+low?best.x-24u:low,startY=best.y>24u+low?best.y-24u:low;
    uint32_t endX=best.x+24u<highX?best.x+24u:highX,endY=best.y+24u<highY?best.y+24u:highY;
    for(uint32_t y=startY;y<=endY;y+=8u)for(uint32_t x=startX;x<=endX;x+=8u)wsLayoutCandidate(index,count,spacing,x,y,&best,&score);
   }
   if(best.x!=planned[index].x||best.y!=planned[index].y){planned[index]=best;moved++;}
  }
  if(!moved)break;
 }
}
static int wsPack(uint32_t count,uint32_t spacing){
 if(!count||count>WS_LIMIT||!(wsWorld==256u||wsWorld==512u||wsWorld==1024u||wsWorld==2048u)||spacing>wsWorld/2u||wsActiveShipReserveCount>sizeof(wsActiveShipReserves)/sizeof(wsActiveShipReserves[0]))return 0;
 for(uint32_t i=0;i<wsActiveShipReserveCount;i++){
  const WSPlanIsland*r=&wsActiveShipReserves[i];
  if(!r->width||!r->height||r->width>wsWorld||r->height>wsWorld||r->x>wsWorld-r->width||r->y>wsWorld-r->height)return 0;
 }
 uint64_t area=0;uint32_t low=(spacing+7u)&~7u;
 for(uint32_t i=0;i<count;i++){
  if(!planned[i].width||!planned[i].height||planned[i].width>wsWorld||planned[i].height>wsWorld||planned[i].width+spacing+low>wsWorld||planned[i].height+spacing+low>wsWorld)return 0;
  area+=(uint64_t)planned[i].width*planned[i].height;
 }
 if(area>(uint64_t)(wsWorld-2u*spacing)*(wsWorld-2u*spacing))return 0;
 if(!wsCompactPack(count,spacing))return 0;
 wsSpreadPack(count,spacing);return 1;
}
