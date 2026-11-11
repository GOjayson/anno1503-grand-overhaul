/* Opaque unknown coverage after the final NORMAL native mode2 flush.
 * Native8x8 unknown terrain is culled before submission by the chart gates.
 * This ground-plane overlay therefore cannot expose unknown elevated terrain.
 * No physical terrain, native palette, renderer cache or input buffer is edited.
 */
#include <math.h>

typedef struct WSVisibilityExplorationSurface {
 WSVisibilityWorld view;void*context,*renderer,*surface,*parent;
 unsigned char*pixels;uint32_t width,height,rowPixels;int32_t viewport[4];
 float matrix[8];int empty;
} WSVisibilityExplorationSurface;

/* 0 invalid; 1 positive native surface; 2 legacy/non-Terra delegation.
 * Every pointer is obtained afresh in this invocation. No pre-flush pixel
 * pointer or stack context is retained for use after the original flush. */
static int wsVisibilityExplorationSurfaceRead(void*renderer,void*context,WSVisibilityExplorationSurface*out){
 unsigned char frame[0x20],draw[0x4b8],surface[0x80],parent[0x50];
 WSVisibilityExplorationSurface s={0};void*world=0,*bound=0,*vt=0;
 if(!out||!wsCertRead(context,frame,sizeof frame))return 0;
 memcpy(&bound,frame+8,8);memcpy(&world,frame+0x18,8);if(bound!=renderer)return 0;
 if(!wsVisibilityWorldRead(world,&s.view))return 0;
 if(s.view.marked<0)return 0;
 if(!s.view.marked||s.view.map!=0){*out=s;return 2;}
 if(!wsCertRead(renderer,draw,sizeof draw))return 0;
 unsigned char*display=(unsigned char*)WS_CERT_MODULE("AnnoDisplay.dll");
 memcpy(&vt,draw,8);
 if(!display||vt!=display+0xf63740||
    !wsVisibilityWithinModule(display,display+0xf653a0,0x120)||
    wsCertPointer(display+0xf63740,0x108)!=display+0x43390||
    wsCertPointer(display+0xf63740,0x118)!=display+0x483e0||
    wsU32(draw+0x498)!=2u)return 0;
 s.context=context;s.renderer=renderer;memcpy(s.viewport,draw+0x458,16);
 if(s.viewport[0]<0||s.viewport[1]<0||s.viewport[2]<s.viewport[0]||s.viewport[3]<s.viewport[1]||
    s.viewport[2]>16384||s.viewport[3]>16384)return 0;
 if(s.viewport[0]==s.viewport[2]||s.viewport[1]==s.viewport[3]){s.empty=1;*out=s;return 1;}
 memcpy(&s.surface,draw+0x4b0,8);
 if(!wsCertRead(s.surface,surface,sizeof surface))return 0;
 memcpy(&vt,surface,8);memcpy(&s.parent,surface+8,8);memcpy(&s.pixels,surface+0x10,8);
 if(vt!=display+0xf653a0||wsU32(surface+0x20)!=0x20080808u||!s.pixels||
    wsCertPointer(vt,0xa8)!=display+0x5e550||wsCertPointer(vt,0xb0)!=display+0x5e560||
    wsCertPointer(vt,0xb8)!=display+0x5e570||wsCertPointer(vt,0x108)!=display+0x5ea70||
    !wsCertRead(s.parent,parent,sizeof parent))return 0;
 s.width=wsU16(surface+0x18);s.height=wsU16(surface+0x1a);s.rowPixels=wsU32(surface+0x1c);
 void*parentPixels=0;memcpy(&parentPixels,parent+0x48,8);
 if(!s.width||!s.height||s.width>16384u||s.height>16384u||s.rowPixels<s.width||s.rowPixels>16384u||
    wsU32(parent+0x28)!=s.width||wsU32(parent+0x2c)!=s.height||
    wsU32(parent+0x44)!=s.rowPixels*4u||parentPixels!=s.pixels||
    (uint32_t)(s.viewport[2]-s.viewport[0])>s.width||(uint32_t)(s.viewport[3]-s.viewport[1])>s.height)return 0;
 size_t extent=(size_t)s.rowPixels*4u*s.height;
 if(!extent||!wsMineralPersistenceWritable(s.pixels,extent))return 0;
 const uint32_t offsets[8]={0xd8,0xdc,0xf8,0xfc,0x108,0x10c,0x118,0x11c};
 for(uint32_t i=0;i<8u;i++)memcpy(&s.matrix[i],draw+offsets[i],4);
 /* Preflight may query page protections. Compare current ownership afterwards
  * before the first pixel write; the native calling thread owns this surface. */
 if(wsCertPointer(context,8)!=renderer||wsCertPointer(context,0x18)!=world||
    wsCertPointer(renderer,0x4b0)!=s.surface||wsCertPointer(s.surface,8)!=s.parent||
    wsCertPointer(s.surface,0x10)!=s.pixels||wsCertPointer(s.parent,0x48)!=s.pixels)return 0;
 *out=s;return 1;
}

/* This readonly check never suppresses/drains a native flush. The caller must
 * always drain the original workers once, even if this preflight returns0. */
static int wsVisibilityExplorationPreflight(void*renderer,void*liveFrameContext){
 WSVisibilityExplorationSurface surface;return wsVisibilityExplorationSurfaceRead(renderer,liveFrameContext,&surface)!=0;
}

static int wsVisibilityExplorationSurfaceSame(const WSVisibilityExplorationSurface*s){
 WSVisibilityExplorationSurface n;
 return wsVisibilityExplorationSurfaceRead(s->renderer,s->context,&n)==1&&!n.empty&&
  n.view.world==s->view.world&&n.view.module==s->view.module&&n.view.width==s->view.width&&n.view.height==s->view.height&&
  n.view.viewer==s->view.viewer&&n.view.flags==s->view.flags&&n.view.marked==s->view.marked&&n.view.map==s->view.map&&
  n.surface==s->surface&&n.parent==s->parent&&n.pixels==s->pixels&&n.width==s->width&&n.height==s->height&&n.rowPixels==s->rowPixels&&
  !memcmp(n.viewport,s->viewport,sizeof n.viewport)&&!memcmp(n.matrix,s->matrix,sizeof n.matrix);
}

static void wsVisibilityExplorationBlack(const WSVisibilityExplorationSurface*s){
 const uint32_t black=0xff000000u;uint32_t width=(uint32_t)(s->viewport[2]-s->viewport[0]);
 uint32_t height=(uint32_t)(s->viewport[3]-s->viewport[1]);
 for(uint32_t y=0;y<height;y++){
  unsigned char*row=s->pixels+(size_t)y*s->rowPixels*4u;
  for(uint32_t x=0;x<width;x++)memcpy(row+(size_t)x*4u,&black,4);
 }
}

static int wsVisibilityExplorationProjection(const WSVisibilityExplorationSurface*s,double out[6]){
 for(uint32_t i=0;i<8u;i++)if(!wsVisibilityFinite(s->matrix[i]))return 0;
 double ax=s->matrix[0],bx=s->matrix[1],az=s->matrix[2],bz=s->matrix[3];
 double determinant=ax*bz-az*bx;if(!isfinite(determinant)||fabs(determinant)<1e-12)return 0;
 double u=(double)s->viewport[0]+0.5-(double)s->matrix[4]-(double)s->matrix[6];
 double v=(double)s->matrix[7]-(double)s->viewport[1]-0.5-(double)s->matrix[5];
 out[0]=(u*bz-az*v)/determinant;out[1]=(ax*v-u*bx)/determinant;
 out[2]=bz/determinant;out[3]=-bx/determinant;out[4]=az/determinant;out[5]=-ax/determinant;
 /* Validate the entire affine viewport before touching pixels. This broad
  * bound avoids undefined integer conversion on corrupt/near-singular data. */
 double width=s->viewport[2]-s->viewport[0],height=s->viewport[3]-s->viewport[1];
 for(uint32_t corner=0;corner<4u;corner++)for(uint32_t axis=0;axis<2u;axis++){
  double n=out[axis]+((corner&1u)?width:0.0)*out[axis+2]+((corner&2u)?height:0.0)*out[axis+4];
  if(!isfinite(n)||fabs(n)>16777216.0)return 0;
 }
 return 1;
}

/* Exact integer-pixel run inside one ground8cell. A negative step includes
 * the current boundary pixel, while a positive step excludes the next one. */
static uint32_t wsVisibilityExplorationRun(double position,double step,uint32_t remaining){
 if(step==0.0)return remaining;
 double cell=floor(position/8.0),edge=(step>0.0?cell+1.0:cell)*8.0;
 double distance=(edge-position)/step;
 double count=step>0.0?ceil(distance):floor(distance)+1.0;
 if(!isfinite(count)||count<1.0)return 1u;
 return count>=(double)remaining?remaining:(uint32_t)count;
}

/* Evaluate from the actual pixel coordinates, never accumulated world steps.
 * Fractional zoom can otherwise put an exact8cell boundary on the wrong side
 * by one rounding bit. The derivative is used only to propose a run length. */
static void wsVisibilityExplorationWorldAt(const WSVisibilityExplorationSurface*s,uint32_t x,uint32_t y,double*outX,double*outZ){
 double ax=s->matrix[0],bx=s->matrix[1],az=s->matrix[2],bz=s->matrix[3],determinant=ax*bz-az*bx;
 double u=(double)s->viewport[0]+(double)x+0.5-(double)s->matrix[4]-(double)s->matrix[6];
 double v=(double)s->matrix[7]-((double)s->viewport[1]+(double)y+0.5)-(double)s->matrix[5];
 *outX=(u*bz-az*v)/determinant;*outZ=(ax*v-u*bx)/determinant;
}
static int wsVisibilityExplorationSameCell(const WSVisibilityExplorationSurface*s,uint32_t x,uint32_t y,int32_t cx,int32_t cz){
 double wx,wz;wsVisibilityExplorationWorldAt(s,x,y,&wx,&wz);
 return (int32_t)floor(wx/8.0)==cx&&(int32_t)floor(wz/8.0)==cz;
}

/* One bounded scalar hierarchy for this pass only. A parent is uniform only
 * when all four children agree. Leaves retain the exact chart bit; mixed
 * parents are never treated as known or unknown. The largest supported World
 * has 256x256 leaves and nine levels, totalling87381bytes. The existing chart
 * read guard pins the bits throughout construction and pixel submission. */
typedef struct WSVisibilityExplorationSummary {
 unsigned char cells[87381];uint32_t offset[9],side[9],levels;
} WSVisibilityExplorationSummary;
static void wsVisibilityExplorationSummarize(const WSVisibilityWorld*v,WSVisibilityExplorationSummary*out){
 uint32_t side=v->width>>3,used=0;out->levels=0;
 while(side){out->offset[out->levels]=used;out->side[out->levels]=side;used+=side*side;out->levels++;side>>=1;}
 side=out->side[0];
 for(uint32_t z=0;z<side;z++)for(uint32_t x=0;x<side;x++)
  out->cells[z*side+x]=(unsigned char)!!wsVisibilityChartPoint(v,(float)(x*8u+4u),(float)(z*8u+4u));
 for(uint32_t level=1;level<out->levels;level++){
  uint32_t current=out->side[level],previous=out->side[level-1];
  for(uint32_t z=0;z<current;z++)for(uint32_t x=0;x<current;x++){
   uint32_t base=out->offset[level-1]+(z*2u)*previous+x*2u;
   unsigned char a=out->cells[base],b=out->cells[base+1u],c=out->cells[base+previous],d=out->cells[base+previous+1u];
   out->cells[out->offset[level]+z*current+x]=(a==b&&a==c&&a==d)?a:2u;
  }
 }
}
static uint32_t wsVisibilityExplorationUniformLevel(const WSVisibilityExplorationSummary*s,uint32_t x,uint32_t z){
 uint32_t result=0;
 for(uint32_t level=1;level<s->levels;level++){
  if(s->cells[s->offset[level]+(z>>level)*s->side[level]+(x>>level)]==2u)break;
  result=level;
 }
 return result;
}

/* These coarse proposals use the same direct-coordinate endpoint proof as
 * ground8 runs. Only completely uniform, aligned power-of-two blocks enter
 * this path. Keep the original constant8 arithmetic for mixed leaf cells. */
static uint32_t wsVisibilityExplorationBlockRun(double position,double step,uint32_t remaining,double span){
 if(step==0.0)return remaining;
 double cell=floor(position/span),edge=(step>0.0?cell+1.0:cell)*span;
 double distance=(edge-position)/step;
 double count=step>0.0?ceil(distance):floor(distance)+1.0;
 if(!isfinite(count)||count<1.0)return 1u;
 return count>=(double)remaining?remaining:(uint32_t)count;
}
static int wsVisibilityExplorationSameBlock(const WSVisibilityExplorationSurface*s,uint32_t x,uint32_t y,int32_t cx,int32_t cz,double span){
 double wx,wz;wsVisibilityExplorationWorldAt(s,x,y,&wx,&wz);
 return (int32_t)floor(wx/span)==cx&&(int32_t)floor(wz/span)==cz;
}

/* Called AFTER exact original Display483E0 drained the normal mode2 workers.
 * Return1 for success/legacy/non-Terra. A validated surface becomes wholly
 * opaque black if chart/projection certification fails. If the destination
 * itself is invalid, return0 without unsafe writes: the caller must report a
 * fatal unpublished-frame condition, not claim that return0 hides pixels. */
static int wsVisibilityApplyExploredSea(void*renderer,void*liveFrameContext){
 WSVisibilityExplorationSurface surface;int status=wsVisibilityExplorationSurfaceRead(renderer,liveFrameContext,&surface);
 if(!status)return 0;if(status==2||surface.empty)return 1;
 double projection[6];
 if(!wsVisibilityExplorationProjection(&surface,projection)){wsVisibilityExplorationBlack(&surface);return 0;}
 WSVisibilityChartReadView read;
 if(!wsVisibilityChartReadBegin(&surface.view,&read)){
  if(wsVisibilityExplorationSurfaceSame(&surface))wsVisibilityExplorationBlack(&surface);return 0;
 }
 if(!wsVisibilityExplorationSurfaceSame(&surface)){wsVisibilityChartReadEnd(&read);return 0;}
 uint32_t width=(uint32_t)(surface.viewport[2]-surface.viewport[0]),height=(uint32_t)(surface.viewport[3]-surface.viewport[1]);
 const uint32_t black=0xff000000u;int32_t cellsX=(int32_t)(surface.view.width>>3),cellsZ=(int32_t)(surface.view.height>>3);
 WSVisibilityExplorationSummary summary;wsVisibilityExplorationSummarize(&surface.view,&summary);
 for(uint32_t y=0;y<height;y++){
  unsigned char*row=surface.pixels+(size_t)y*surface.rowPixels*4u;
  for(uint32_t x=0;x<width;){
   double wx,wz;wsVisibilityExplorationWorldAt(&surface,x,y,&wx,&wz);
   int32_t cx=(int32_t)floor(wx/8.0),cz=(int32_t)floor(wz/8.0);
   int inside=cx>=0&&cz>=0&&cx<cellsX&&cz<cellsZ;
   int charted=inside&&summary.cells[(uint32_t)cz*(uint32_t)cellsX+(uint32_t)cx];
   uint32_t level=inside?wsVisibilityExplorationUniformLevel(&summary,(uint32_t)cx,(uint32_t)cz):summary.levels-1u;
   uint32_t run;
   /* At fixed y both inverse coordinates are monotone in pixel x. A direct
    * endpoint check certifies the entire proposed run stays in this uniform
    * block; bounded binary search corrects any proposal rounding mismatch.
    * A World-sized aligned block outside the World is wholly unknown. */
   if(!level){
    run=wsVisibilityExplorationRun(wx,projection[2],width-x);
    uint32_t other=wsVisibilityExplorationRun(wz,projection[3],width-x);if(other<run)run=other;
    if(run>1u&&!wsVisibilityExplorationSameCell(&surface,x+run-1u,y,cx,cz)){
     uint32_t low=1u,high=run;
     while(low<high){uint32_t middle=low+(high-low+1u)/2u;
      if(wsVisibilityExplorationSameCell(&surface,x+middle-1u,y,cx,cz))low=middle;else high=middle-1u;
     }run=low;
    }
   }else{
    double span=(double)(8u<<level);int32_t bx=(int32_t)floor(wx/span),bz=(int32_t)floor(wz/span);
    run=wsVisibilityExplorationBlockRun(wx,projection[2],width-x,span);
    uint32_t other=wsVisibilityExplorationBlockRun(wz,projection[3],width-x,span);if(other<run)run=other;
    if(run>1u&&!wsVisibilityExplorationSameBlock(&surface,x+run-1u,y,bx,bz,span)){
     uint32_t low=1u,high=run;
     while(low<high){uint32_t middle=low+(high-low+1u)/2u;
      if(wsVisibilityExplorationSameBlock(&surface,x+middle-1u,y,bx,bz,span))low=middle;else high=middle-1u;
     }run=low;
    }
   }
   if(!charted)for(uint32_t n=0;n<run;n++)memcpy(row+(size_t)(x+n)*4u,&black,4);
   x+=run;
  }
 }
 wsVisibilityChartReadEnd(&read);return 1;
}
