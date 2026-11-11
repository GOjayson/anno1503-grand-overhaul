/* Pure bounded SCP transformation. All input pointers are read-only. HEIGHT
 * is a padded vertex grid, while GFXID/fertility are cell grids. */
#include <math.h>
#include "island_rotation_definitions.h"
static void wsRotateBox(uint32_t n,uint32_t q,int32_t*x,int32_t*y,uint32_t*w,uint32_t*h){
 for(uint32_t i=0;i<q;i++){int32_t ox=*x;uint32_t ow=*w;*x=(int32_t)n-*y-(int32_t)*h;*y=ox;*w=*h;*h=ow;}
}
static void wsRotateVertex(uint32_t n,uint32_t q,uint32_t x,uint32_t y,uint32_t*nx,uint32_t*ny){
 if(q==1u){*nx=n-y;*ny=x;}else if(q==2u){*nx=n-x;*ny=n-y;}else if(q==3u){*nx=y;*ny=n-x;}else{*nx=x;*ny=y;}
}
static void wsRotateFloat(uint32_t n,uint32_t q,float*x,float*y){
 float ox=*x,oy=*y;if(q==1u){*x=(float)n-oy;*y=ox;}else if(q==2u){*x=(float)n-ox;*y=(float)n-oy;}else if(q==3u){*x=oy;*y=(float)n-ox;}
}
static int wsRotationEmitGrid(WSBuffer*out,const char*tag,const unsigned char*data,uint32_t width,uint32_t height,uint32_t stride){
 unsigned char tile[6+32*32*2];
 for(uint32_t y=0;y<height;y+=32u){
  for(uint32_t x=0;x<width;x+=32u){
  uint32_t w=width-x<32u?width-x:32u,h=height-y<32u?height-y:32u;
  wsPut16(tile,(uint16_t)x);wsPut16(tile+2,(uint16_t)y);tile[4]=(unsigned char)w;tile[5]=(unsigned char)h;
  for(uint32_t row=0;row<h;row++)memcpy(tile+6+row*w*stride,data+((y+row)*width+x)*stride,w*stride);
  if(!wsChunk(out,tag,tile,6u+w*h*stride))return 0;
  }
 }
 return 1;
}
static int wsRotationDecodeGrid(const unsigned char*island,uint32_t size,const char*tag,uint32_t n,uint32_t stride,unsigned char*out){
 unsigned char*seen=(unsigned char*)calloc(n*n,1);if(!seen)return 0;int ok=0;
 for(uint32_t at=12;at<size;){
  if(size-at<16u)goto done;uint32_t len=wsU32(island+at+12);if(len>size-at-16u)goto done;
  if(wsTag(island+at,tag)){
   const unsigned char*p=island+at+16;if(len<6u)goto done;
   uint32_t x=wsU16(p),y=wsU16(p+2),w=p[4],h=p[5];
   if(!w||!h||x>n||y>n||w>n-x||h>n-y||len!=6u+w*h*stride)goto done;
   for(uint32_t r=0;r<h;r++)for(uint32_t c=0;c<w;c++){
    uint32_t i=(y+r)*n+x+c;if(seen[i])goto done;seen[i]=1;memcpy(out+i*stride,p+6+(r*w+c)*stride,stride);
   }
  }at+=16u+len;
 }
 for(uint32_t i=0;i<n*n;i++)if(!seen[i])goto done;ok=1;
done:free(seen);return ok;
}
static int wsRotationPlacements(unsigned char*p,uint32_t len,uint32_t n,uint32_t q){
 if(len<6u||(len-6u)%6u)return 0;
 uint32_t ox=wsU16(p),oy=wsU16(p+2),tw=p[4],th=p[5];
 if(!tw||!th||ox>n||oy>n||tw>n-ox||th>n-oy)return 0;
 int32_t tx=(int32_t)ox,ty=(int32_t)oy;uint32_t nw=tw,nh=th;wsRotateBox(n,q,&tx,&ty,&nw,&nh);
 wsPut16(p,(uint16_t)tx);wsPut16(p+2,(uint16_t)ty);p[4]=(unsigned char)nw;p[5]=(unsigned char)nh;
 for(uint32_t at=6;at<len;at+=6u){
  uint32_t packed=wsU16(p+at),definition=packed&16383u,orientation=packed>>14;
  if(definition>=4096u)return 0;uint32_t dims=wsRotationDimensions[definition],dw=dims&255u,dh=dims>>8;
  if(orientation&1u){uint32_t t=dw;dw=dh;dh=t;}
  int32_t x=(int32_t)ox+(int8_t)p[at+4],y=(int32_t)oy+(int8_t)p[at+5];
  if(!dw||!dh||x<0||y<0||(uint32_t)x>n||(uint32_t)y>n||dw>n-(uint32_t)x||dh>n-(uint32_t)y)return 0;
  wsRotateBox(n,q,&x,&y,&dw,&dh);int32_t dx=x-tx,dy=y-ty;
  if(dx < -128||dx>127||dy < -128||dy>127)return 0;
  wsPut16(p+at,(uint16_t)(definition|(((orientation+q)&3u)<<14)));p[at+4]=(unsigned char)(int8_t)dx;p[at+5]=(unsigned char)(int8_t)dy;
 }return 1;
}
static int wsRotationMines(unsigned char*p,uint32_t len,uint32_t n,uint32_t q){
 if(len%12u)return 0;
 for(uint32_t at=0;at<len;at+=12u){
  if(memcmp(p+at,"ENTRY\0\x04\0",8))return 0;uint32_t v=wsU32(p+at+8),direction=(v>>24)&3u;
  int32_t x=(int32_t)(v&4095u),y=(int32_t)((v>>12)&4095u);uint32_t w=direction&1u?4u:3u,h=direction&1u?3u:4u;
  if((uint32_t)x>n||(uint32_t)y>n||w>n-(uint32_t)x||h>n-(uint32_t)y)return 0;
  wsRotateBox(n,q,&x,&y,&w,&h);wsPut32(p+at+8,(v&0xfc000000u)|(uint32_t)x|((uint32_t)y<<12)|(((direction+q)&3u)<<24));
 }return 1;
}
static int wsRotationOccurrences(unsigned char*p,uint32_t len,uint32_t n,uint32_t q){
 for(uint32_t at=0;at<len;){
  if(len-at<8u||memcmp(p+at,"ENTRY2",6))return 0;uint32_t size=wsU16(p+at+6);if(size<24u||size>len-at-8u)return 0;
  unsigned char*v=p+at+8;uint32_t definition=(wsU32(v)>>14)&4095u;
  if(definition!=1559u&&definition!=1560u&&definition!=1561u&&definition!=1562u&&definition!=1563u&&definition!=1565u)return 0;
  if(definition!=1559u&&size!=24u)return 0;float x,y,z;memcpy(&x,v+4,4);memcpy(&y,v+8,4);memcpy(&z,v+12,4);
  if(!isfinite(x)||!isfinite(y)||!isfinite(z)||!(x>=0&&y>=0&&x<=(float)n&&y<=(float)n))return 0;
  wsRotateFloat(n,q,&x,&y);memcpy(v+4,&x,4);memcpy(v+8,&y,4);
  if(definition==1559u){
   if(memcmp(v+16,"WHALE\0",6)||size-24u!=wsU16(v+22)||(size-24u)%6u)return 0;
   for(uint32_t i=24;i<size;i+=6u){int32_t dx=(int8_t)v[i+2],dy=(int8_t)v[i+3];
    for(uint32_t r=0;r<q;r++){int32_t t=dx;dx=-dy;dy=t;}
    if(dx < -128||dx>127||dy < -128||dy>127)return 0;v[i+2]=(unsigned char)(int8_t)dx;v[i+3]=(unsigned char)(int8_t)dy;
   }
  }at+=8u+size;
 }return 1;
}
static int wsRotationBake(const unsigned char*src,uint32_t size,uint32_t n,uint32_t q,WSBuffer*out,char*error,uint32_t cap){
 unsigned char *height=NULL,*graphics=NULL,*vertices=NULL,*rotated=NULL,*gfxRotated=NULL;int ok=0;
 if(!src||!out||q<1u||q>3u||n<1u||n>256u||size<32u||size>64u*1024u*1024u||
    (!wsTag(src,"ANNO")&&!wsTag(src,"ANNOADDON1")))goto done;
 uint32_t root=wsU32(src+12);if(root>size-16u)goto done;root+=16u;uint32_t islandAt=0,islandSize=0,ware=0;
 for(uint32_t at=16;at<root;){
  if(root-at<16u)goto done;uint32_t len=wsU32(src+at+12);if(len>root-at-16u)goto done;
  if(wsTag(src+at,"INSEL5")){if(islandAt||len<12u)goto done;islandAt=at+16u;islandSize=len;}
  else if(wsTag(src+at,"WARETYPE")){if(++ware>1u)goto done;}else goto done;at+=16u+len;
 }
 if(!islandAt||ware!=1u)goto done;const unsigned char*island=src+islandAt;
 if(wsU16(island)||wsU16(island+2)||wsU16(island+4)!=n||wsU16(island+6)!=n)goto done;
 height=(unsigned char*)malloc(n*n);graphics=(unsigned char*)malloc(n*n*2u);vertices=(unsigned char*)calloc((n+1u)*(n+1u),1);
 rotated=(unsigned char*)malloc((n+1u)*(n+1u));gfxRotated=(unsigned char*)malloc(n*n*2u);
 if(!height||!graphics||!vertices||!rotated||!gfxRotated||!wsRotationDecodeGrid(island,islandSize,"HEIGHT",n,1,height)||!wsRotationDecodeGrid(island,islandSize,"GFXID",n,2,graphics))goto done;
 for(uint32_t y=0;y<n;y++)memcpy(vertices+y*(n+1u),height+y*n,n);
 for(uint32_t y=0;y<=n;y++)for(uint32_t x=0;x<=n;x++){uint32_t nx,ny;wsRotateVertex(n,q,x,y,&nx,&ny);rotated[ny*(n+1u)+nx]=vertices[y*(n+1u)+x];}
 for(uint32_t y=0;y<n;y++)for(uint32_t x=0;x<n;x++){int32_t nx=(int32_t)x,ny=(int32_t)y;uint32_t w=1,h=1;wsRotateBox(n,q,&nx,&ny,&w,&h);uint32_t v=wsU16(graphics+(y*n+x)*2u);wsPut16(gfxRotated+((uint32_t)ny*n+(uint32_t)nx)*2u,(uint16_t)((v&~3u)|((v-q)&3u)));}
 if(!wsAppend(out,src,16))goto done;
 for(uint32_t at=16;at<root;){
  uint32_t len=wsU32(src+at+12);if(at+16u!=islandAt){if(!wsAppend(out,src+at,16u+len))goto done;at+=16u+len;continue;}
  uint32_t outputIsland=out->size;if(!wsAppend(out,src+at,28))goto done;uint32_t infos=0,fertilities=0,crops=0,seenHeight=0,seenGfx=0;
  for(uint32_t part=12;part<islandSize;){
   if(islandSize-part<16u)goto done;uint32_t count=wsU32(island+part+12);if(count>islandSize-part-16u)goto done;
   const unsigned char*tag=island+part,*value=tag+16;
   if(wsTag(tag,"HEIGHT")){if(!seenHeight++&&!wsRotationEmitGrid(out,"HEIGHT",rotated,n+1u,n+1u,1))goto done;}
   else if(wsTag(tag,"GFXID")){if(!seenGfx++&&!wsRotationEmitGrid(out,"GFXID",gfxRotated,n,n,2))goto done;}
   else if(wsTag(tag,"INFO")){if(++infos>1u||count!=12u||value[0]>5u||!wsAppend(out,tag,16u+count))goto done;}
   else if(wsTag(tag,"ANBAU")){if(++crops>1u||!wsAppend(out,tag,16u+count))goto done;}
   else if(wsTag(tag,"FRUCHTBAR")){
    if(++fertilities>1u||count!=n*n)goto done;
    for(uint32_t y=0;y<n;y++)for(uint32_t x=0;x<n;x++){int32_t nx=(int32_t)x,ny=(int32_t)y;uint32_t w=1,h=1;wsRotateBox(n,q,&nx,&ny,&w,&h);height[(uint32_t)ny*n+(uint32_t)nx]=value[y*n+x];}
    if(!wsChunk(out,"FRUCHTBAR",height,n*n))goto done;
   }else{
    if(!wsTag(tag,"GELAENDE")&&!wsTag(tag,"FLUESSE")&&!wsTag(tag,"BERGWERK2")&&!wsTag(tag,"OCCUR"))goto done;
    unsigned char*copy=(unsigned char*)malloc(count?count:1u);if(!copy)goto done;memcpy(copy,value,count);int valid;
    if(wsTag(tag,"GELAENDE")||wsTag(tag,"FLUESSE"))valid=wsRotationPlacements(copy,count,n,q);
    else if(wsTag(tag,"BERGWERK2"))valid=wsRotationMines(copy,count,n,q);else valid=wsRotationOccurrences(copy,count,n,q);
    if(valid){unsigned char head[16];memcpy(head,tag,16);valid=wsAppend(out,head,16)&&wsAppend(out,copy,count);}free(copy);if(!valid)goto done;
   }part+=16u+count;
  }
  if(infos!=1u||fertilities!=1u||crops!=1u||!seenHeight||!seenGfx)goto done;
  wsPut32(out->data+outputIsland+12,out->size-outputIsland-16u);at+=16u+len;
 }
 wsPut32(out->data+12,out->size-16u);if(!wsAppend(out,src+root,size-root))goto done;ok=1;
done:
 free(height);free(graphics);free(vertices);free(rotated);free(gfxRotated);
 if(!ok)wsMessage(error,cap,"An island cannot be rotated without changing unsupported terrain or scenario data.");return ok;
}
