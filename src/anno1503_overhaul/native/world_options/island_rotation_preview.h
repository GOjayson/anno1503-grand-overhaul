#ifndef WS_ISLAND_ROTATION_PREVIEW_H
#define WS_ISLAND_ROTATION_PREVIEW_H
/* Paint and hit testing share one inverse projection. The existing coastline
 * mask remains an approximation; rotation zero retains its exact old pixels. */
static inline int wsRotationPreviewSolid(const WSPlanIsland*p,const unsigned char*coast,uint32_t x,uint32_t y,uint32_t width,uint32_t height){
 if(!p||!coast||!width||!height||x>=width||y>=height||!p->width||!p->height||p->rotation>3u)return 0;
 uint32_t column,row;
 if(!p->rotation){column=x*WS_PREVIEW_COAST_SIZE/width;row=y*WS_PREVIEW_COAST_SIZE/height;}
 else{
  if(p->width!=p->height)return 0;uint32_t sx=x*p->width/width,sy=y*p->height/height,ox=sx,oy=sy;
  if(p->rotation==1u){sx=oy;sy=p->height-ox;}
  else if(p->rotation==2u){sx=p->width-ox;sy=p->height-oy;}
  else{sx=p->width-oy;sy=ox;}
  if(sx>=p->width||sy>=p->height)return 0;
  column=sx*WS_PREVIEW_COAST_SIZE/p->width;row=sy*WS_PREVIEW_COAST_SIZE/p->height;
 }
 uint32_t bit=row*WS_PREVIEW_COAST_SIZE+column;return !!(coast[bit>>3]&(1u<<(bit&7u)));
}
#endif
