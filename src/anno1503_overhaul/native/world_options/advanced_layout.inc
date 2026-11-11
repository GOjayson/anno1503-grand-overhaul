/* Optional layouts use a separate RNG and only native eight-tile coordinates.
 * Every placement still honors the configured gap and all ship reservations.
 * Dense archipelagos may expand around their anchors; they never use the
 * even-spread optimizer as a hidden fallback. Central ocean is a hard empty
 * middle-third square, independently checked before staging the scene. */
static void wsCentralOcean(WSPlanIsland*out){
 uint32_t edge=(wsWorld/3u+7u)&~7u;
 *out=(WSPlanIsland){0,edge,edge,wsWorld-edge*2u,wsWorld-edge*2u,0,0,0,0,0,0};
}
static int wsAdvancedLayoutMatches(const WSWorldSettings*s,uint32_t count){
 if(!s||s->layoutStyle<0||s->layoutStyle>2||count>WS_LIMIT)return 0;
 if(s->layoutStyle!=2)return 1;
 WSPlanIsland ocean;wsCentralOcean(&ocean);
 for(uint32_t i=0;i<count;i++)if(!wsSeparated(&planned[i],&ocean,0))return 0;
 return 1;
}
static int wsAdvancedFits(const WSPlanIsland*q,const uint32_t*order,uint32_t done,
                          uint32_t spacing,int central){
 if(q->x<spacing||q->y<spacing||q->x+q->width+spacing>wsWorld||
    q->y+q->height+spacing>wsWorld)return 0;
 if(central){WSPlanIsland ocean;wsCentralOcean(&ocean);if(!wsSeparated(q,&ocean,0))return 0;}
 for(uint32_t j=0;j<wsActiveShipReserveCount;j++)
  if(!wsSeparated(q,&wsActiveShipReserves[j],spacing))return 0;
 for(uint32_t j=0;j<done;j++)
  if(!wsSeparated(q,&planned[order[j]],spacing))return 0;
 return 1;
}
static uint64_t wsAdvancedDistance(const WSPlanIsland*q,uint32_t ax,uint32_t ay){
 int64_t dx=(int64_t)q->x*2+q->width-(int64_t)ax*2;
 int64_t dy=(int64_t)q->y*2+q->height-(int64_t)ay*2;
 return (uint64_t)(dx*dx+dy*dy);
}
static void wsAdvancedCandidate(uint32_t index,const uint32_t*order,uint32_t done,
 uint32_t spacing,int central,uint32_t ax,uint32_t ay,uint32_t x,uint32_t y,
 WSPlanIsland*best,uint64_t*score,int*found){
 WSPlanIsland q=planned[index];q.id=index;q.x=x;q.y=y;
 if(!wsAdvancedFits(&q,order,done,spacing,central))return;
 uint64_t distance=wsAdvancedDistance(&q,ax,ay);
 if(!*found||distance<*score||(distance==*score&&(q.y<best->y||(q.y==best->y&&q.x<best->x)))){
  *found=1;*score=distance;*best=q;
 }
}
static int wsAdvancedPack(const WSWorldSettings*s,uint32_t count,uint32_t spacing){
 if(!s||(s->layoutStyle!=1&&s->layoutStyle!=2))return 0;
 uint32_t order[WS_LIMIT];
 for(uint32_t i=0;i<count;i++)order[i]=i;
 for(uint32_t i=1;i<count;i++){
  uint32_t key=order[i],j=i,area=planned[key].width*planned[key].height;
  while(j&&planned[order[j-1]].width*planned[order[j-1]].height<area){order[j]=order[j-1];j--;}
  order[j]=key;
 }
 uint32_t state=rngState^0x4c41594fu;if(!state)state=0x15032026u;
 uint32_t low=(spacing+7u)&~7u,step=(wsWorld/64u)&~7u;
 if(step<8u)step=8u;
 const uint32_t groups=count<=10u?2u:(count<=20u?3u:4u);
 for(uint32_t attempt=0;attempt<6u;attempt++){
  uint32_t anchors[4][2]={{wsWorld/4u,wsWorld/4u},{3u*wsWorld/4u,3u*wsWorld/4u},
                          {3u*wsWorld/4u,wsWorld/4u},{wsWorld/4u,3u*wsWorld/4u}};
  if(groups==3u){anchors[1][0]=3u*wsWorld/4u;anchors[1][1]=wsWorld/4u;anchors[2][0]=wsWorld/2u;anchors[2][1]=3u*wsWorld/4u;}
  uint32_t rotation=wsLayoutRandom(&state)%groups;
  for(uint32_t g=0;g<groups;g++)for(uint32_t axis=0;axis<2;axis++){
   int32_t jitter=(int32_t)(wsLayoutRandom(&state)%9u)-4;
   anchors[g][axis]=(uint32_t)((int32_t)anchors[g][axis]+jitter*(int32_t)(wsWorld/128u));
  }
  int failed=0;
  for(uint32_t at=0;at<count;at++){
   uint32_t index=order[at],highX=(wsWorld-spacing-planned[index].width)&~7u;
   uint32_t highY=(wsWorld-spacing-planned[index].height)&~7u;
   if(highX<low||highY<low){failed=1;break;}
   uint32_t group=(at+rotation)%groups,ax=anchors[group][0],ay=anchors[group][1];
   /* On a central-ocean map use seeded rim anchors, leaving the hard square
    * empty while covering all four sides rather than one corner. */
   if(s->layoutStyle==2){
    static const uint8_t rim[8][2]={{1,1},{4,1},{7,1},{7,4},{7,7},{4,7},{1,7},{1,4}};
    uint32_t r=(at+attempt)%8u;ax=wsWorld*rim[r][0]/8u;ay=wsWorld*rim[r][1]/8u;
   }
   WSPlanIsland best={0};uint64_t score=0;int found=0;
   for(uint32_t y=low;;){
    for(uint32_t x=low;;){
     wsAdvancedCandidate(index,order,at,spacing,s->layoutStyle==2,ax,ay,x,y,&best,&score,&found);
     if(x==highX)break;uint32_t next=x+step;x=next<highX?next:highX;
    }
    if(y==highY)break;uint32_t next=y+step;y=next<highY?next:highY;
   }
   /* Exact neighboring edges complement the coarse world-wide search. They
    * keep dense legal packings available without a full eight-tile scan. */
   uint32_t xs[WS_LIMIT*2+2],ys[WS_LIMIT*2+2],nx=2,ny=2;xs[0]=low;xs[1]=highX;ys[0]=low;ys[1]=highY;
   for(uint32_t j=0;j<at;j++){
    const WSPlanIsland*p=&planned[order[j]];
    uint32_t x=(p->x+p->width+spacing+7u)&~7u,y=(p->y+p->height+spacing+7u)&~7u;
    if(x>=low&&x<=highX)xs[nx++]=x;if(y>=low&&y<=highY)ys[ny++]=y;
    if(p->x>=planned[index].width+spacing){x=(p->x-planned[index].width-spacing)&~7u;if(x>=low&&x<=highX)xs[nx++]=x;}
    if(p->y>=planned[index].height+spacing){y=(p->y-planned[index].height-spacing)&~7u;if(y>=low&&y<=highY)ys[ny++]=y;}
   }
   for(uint32_t y=0;y<ny;y++)for(uint32_t x=0;x<nx;x++)
    wsAdvancedCandidate(index,order,at,spacing,s->layoutStyle==2,ax,ay,xs[x],ys[y],&best,&score,&found);
   if(!found){failed=1;break;}
   planned[index]=best;
  }
  if(!failed&&wsAdvancedLayoutMatches(s,count))return 1;
 }
 return 0;
}
