/* Pointer-free chart/last-seen storage and canonical checkpoint codec.
 * This header has no Windows or engine dependencies; native bindings live in
 * start_visibility_chart.inc. No engine address is ever serialized. */
#ifndef ANNO_WORLD_VISIBILITY_CHART_H
#define ANNO_WORLD_VISIBILITY_CHART_H
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

#define WS_CHART_BLOB_LIMIT (96u*1024u*1024u)
#define WS_CHART_HEADER_BYTES 128u
#define WS_CHART_OBSERVED 1u
#define WS_CHART_BUILDING 2u
#define WS_CHART_ANIMATED 4u
typedef struct WSChartCell {
 unsigned char visual[8],renderFlag,owner,flags,rootCode;uint32_t time;uint16_t logical,reserved;
} WSChartCell;
typedef char WSChartCellSize[(sizeof(WSChartCell)==20)?1:-1];
typedef struct WSChartCore {
 uint32_t width,height,viewer,policy,generation,count,bitBytes;unsigned char guid[16];
 unsigned char*bits;WSChartCell*cells;
 uint32_t mapWidth,mapHeight,mapCount,mapKnownBytes;unsigned char*mapPixels,*mapKnown;
} WSChartCore;
static inline int wsChError(char*out,uint32_t cap,const char*message){if(out&&cap)snprintf(out,cap,"%s",message);return 0;}
static inline uint32_t wsCh32(const unsigned char*p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static inline uint64_t wsCh64(const unsigned char*p){return wsCh32(p)|(uint64_t)wsCh32(p+4)<<32;}
static inline void wsChPut32(unsigned char*p,uint32_t n){for(unsigned k=0;k<4;k++)p[k]=(unsigned char)(n>>(8*k));}
static inline void wsChPut64(unsigned char*p,uint64_t n){wsChPut32(p,(uint32_t)n);wsChPut32(p+4,(uint32_t)(n>>32));}
static inline uint64_t wsChHash(const void*data,size_t size){const unsigned char*p=(const unsigned char*)data;uint64_t n=UINT64_C(14695981039346656037);for(size_t i=0;i<size;i++)n=(n^p[i])*UINT64_C(1099511628211);return n;}
static inline int wsChZero(const void*data,size_t size){const unsigned char*p=(const unsigned char*)data;for(size_t i=0;i<size;i++)if(p[i])return 0;return 1;}
static inline int wsChFinite(float value){uint32_t n;memcpy(&n,&value,4);return (n&0x7f800000u)!=0x7f800000u;}
static inline int wsChShape(uint32_t w,uint32_t h,uint32_t viewer,uint32_t policy){uint32_t code=policy>>12;return w==h&&(w==256u||w==512u||w==1024u||w==2048u)&&viewer<16u&&!(policy&~0x7000u)&&code>=1u&&code<=6u;}
static inline void wsChartCoreFree(WSChartCore*c){if(c){free(c->bits);free(c->cells);free(c->mapPixels);free(c->mapKnown);memset(c,0,sizeof(*c));}}
static inline int wsChartCoreNew(WSChartCore*c,uint32_t w,uint32_t h,uint32_t viewer,uint32_t policy,const unsigned char guid[16]){
 if(!c||!guid||!wsChShape(w,h,viewer,policy))return 0;
 WSChartCore n={0};n.width=w;n.height=h;n.viewer=viewer;n.policy=policy;n.generation=1;n.count=w*h;n.bitBytes=((w>>3)*(h>>3)+7u)>>3;memcpy(n.guid,guid,16);
 n.bits=(unsigned char*)calloc(n.bitBytes,1);n.cells=(WSChartCell*)calloc(n.count,sizeof(WSChartCell));
 if(!n.bits||!n.cells){wsChartCoreFree(&n);return 0;}*c=n;return 1;
}
static inline int wsChartCoreIdentity(const WSChartCore*c,uint32_t w,uint32_t h,uint32_t viewer,uint32_t policy,const unsigned char guid[16]){
 return c&&c->bits&&c->cells&&c->width==w&&c->height==h&&c->viewer==viewer&&c->policy==policy&&!memcmp(c->guid,guid,16);
}
static inline void wsChartCoreChanged(WSChartCore*c){if(++c->generation==0)c->generation=1;}
static inline int wsChartCoreCell(const WSChartCore*c,int32_t x,int32_t z){
 if(!c||!c->bits||x<0||z<0||(uint32_t)x>=(c->width>>3)||(uint32_t)z>=(c->height>>3))return 0;
 uint32_t index=(uint32_t)z*(c->width>>3)+(uint32_t)x;return !!(c->bits[index>>3]&(1u<<(index&7u)));
}
static inline int wsChartCorePoint(const WSChartCore*c,float x,float z){
 return c&&wsChFinite(x)&&wsChFinite(z)&&x>=0&&z>=0&&x<(float)c->width&&z<(float)c->height&&wsChartCoreCell(c,(int32_t)x>>3,(int32_t)z>>3);
}
static inline int wsChartCoreMark(WSChartCore*c,float left,float top,float right,float bottom){
 if(!c||!c->bits||!wsChFinite(left)||!wsChFinite(top)||!wsChFinite(right)||!wsChFinite(bottom)||left<0||top<0||right<left||bottom<top||right>=(float)c->width||bottom>=(float)c->height)return 0;
 int32_t x0=(int32_t)(left-48.0f)/8,z0=(int32_t)(top-48.0f)/8,x1=(int32_t)(right+48.0f)/8,z1=(int32_t)(bottom+48.0f)/8;
 if(x0<0)x0=0;if(z0<0)z0=0;if(x1>=(int32_t)(c->width>>3))x1=(int32_t)(c->width>>3)-1;if(z1>=(int32_t)(c->height>>3))z1=(int32_t)(c->height>>3)-1;
 int changed=0;
 for(int32_t z=z0;z<=z1;z++)for(int32_t x=x0;x<=x1;x++){
  float a=(float)(x*8),b=(float)(z*8),dx=a+8<left?left-a-8:(a>right?a-right:0),dz=b+8<top?top-b-8:(b>bottom?b-bottom:0);
  if(dx*dx+dz*dz>2304.0f)continue;uint32_t index=(uint32_t)z*(c->width>>3)+(uint32_t)x;unsigned char mask=(unsigned char)(1u<<(index&7u));
  if(!(c->bits[index>>3]&mask)){c->bits[index>>3]|=mask;changed=1;}
 }
 if(changed)wsChartCoreChanged(c);return 1;
}
static inline int wsChartCellValid(const WSChartCell*c){
 if(wsChZero(c,sizeof(*c)))return 1;
 if(c->reserved||!(c->flags&WS_CHART_OBSERVED)||(c->flags&~7u)||((c->flags&WS_CHART_ANIMATED)&&!(c->flags&WS_CHART_BUILDING)))return 0;
 if(!(c->flags&WS_CHART_BUILDING))return c->flags==WS_CHART_OBSERVED&&wsChZero(c->visual,8)&&!c->renderFlag&&!c->owner&&!c->rootCode&&!c->time&&!c->logical;
 uint32_t id=(uint32_t)c->visual[0]|(uint32_t)c->visual[1]<<8;return id<4000u&&c->logical>0u&&c->logical<4000u&&c->owner<32u&&c->renderFlag<=1u&&!c->visual[7]&&(!(c->visual[3]&0x40u)||c->visual[5]==0xc0u);
}
static inline int wsChartCellSet(WSChartCore*c,uint32_t x,uint32_t z,const WSChartCell*value){
 if(!c||!c->cells||!value||x>=c->width||z>=c->height||!wsChartCellValid(value))return 0;
 WSChartCell*at=c->cells+(size_t)z*c->width+x;if(memcmp(at,value,sizeof(*value))){*at=*value;wsChartCoreChanged(c);}return 1;
}
static inline void wsChartCellWrite(unsigned char*out,const WSChartCell*c){memcpy(out,c->visual,8);out[8]=c->renderFlag;out[9]=c->owner;out[10]=c->flags;out[11]=c->rootCode;wsChPut32(out+12,c->time);out[16]=(unsigned char)c->logical;out[17]=(unsigned char)(c->logical>>8);out[18]=out[19]=0;}
static inline void wsChartCellRead(WSChartCell*out,const unsigned char*p){memcpy(out->visual,p,8);out->renderFlag=p[8];out->owner=p[9];out->flags=p[10];out->rootCode=p[11];out->time=wsCh32(p+12);out->logical=(uint16_t)((uint16_t)p[16]|(uint16_t)p[17]<<8);out->reserved=(uint16_t)((uint16_t)p[18]|(uint16_t)p[19]<<8);}
static inline int wsChartMapShape(WSChartCore*c,uint32_t width,uint32_t height){
 if(!c||!width||!height||width>2048u||height>2048u)return 0;
 if(c->mapWidth==width&&c->mapHeight==height&&c->mapPixels&&c->mapKnown)return 1;
 uint32_t count=width*height,known=(count+7u)>>3;unsigned char*p=(unsigned char*)calloc(count,1),*k=(unsigned char*)calloc(known,1);
 if(!p||!k){free(p);free(k);return 0;}free(c->mapPixels);free(c->mapKnown);c->mapPixels=p;c->mapKnown=k;c->mapWidth=width;c->mapHeight=height;c->mapCount=count;c->mapKnownBytes=known;return 1;
}
static inline int wsChartMapGet(const WSChartCore*c,uint32_t index,unsigned char*out){
 if(!c||!out||!c->mapKnown||!c->mapPixels||index>=c->mapCount||!(c->mapKnown[index>>3]&(1u<<(index&7u))))return 0;*out=c->mapPixels[index];return 1;
}
static inline int wsChartMapPut(WSChartCore*c,uint32_t index,unsigned char value){
 if(!c||!c->mapKnown||!c->mapPixels||index>=c->mapCount||value>=160u)return 0;c->mapPixels[index]=value;c->mapKnown[index>>3]|=(unsigned char)(1u<<(index&7u));return 1;
}
static inline int wsChartMapValid(const WSChartCore*c){
 if(!c->mapWidth&&!c->mapHeight)return !c->mapCount&&!c->mapKnownBytes&&!c->mapPixels&&!c->mapKnown;
 if(!c->mapWidth||!c->mapHeight||c->mapWidth>2048u||c->mapHeight>2048u||c->mapCount!=c->mapWidth*c->mapHeight||c->mapKnownBytes!=((c->mapCount+7u)>>3)||!c->mapKnown||!c->mapPixels)return 0;
 if((c->mapCount&7u)&&(c->mapKnown[c->mapKnownBytes-1u]&~((1u<<(c->mapCount&7u))-1u)))return 0;
 for(uint32_t i=0;i<c->mapCount;i++)if((c->mapKnown[i>>3]&(1u<<(i&7u)))?c->mapPixels[i]>=160u:c->mapPixels[i]!=0u)return 0;return 1;
}
static inline int wsChartCoreRecordsValid(const WSChartCore*c){
 if(!c||!c->cells||c->count!=c->width*c->height)return 0;
 for(uint32_t index=0;index<c->count;index++){
  const WSChartCell*r=c->cells+index;if(!wsChartCellValid(r))return 0;if(!(r->flags&WS_CHART_BUILDING))continue;
  uint32_t x=index%c->width,z=index/c->width,dx=r->rootCode&7u,dz=(r->rootCode>>3)&7u;
  if(x<dx||z<dz)return 0;const WSChartCell*root=c->cells+(size_t)(z-dz)*c->width+x-dx;
  if(!(root->flags&WS_CHART_BUILDING)||(root->rootCode&63u)||root->logical!=r->logical||root->owner!=r->owner||(root->rootCode&0xc0u)!=(r->rootCode&0xc0u))return 0;
 }
 return 1;
}
static inline int wsChartCoreEncode(const WSChartCore*c,unsigned char**out,uint32_t*size,char*error,uint32_t cap){
 if(!c||!out||!size||!wsChShape(c->width,c->height,c->viewer,c->policy)||!c->bits||!c->cells||c->count!=c->width*c->height||c->bitBytes!=(((c->width>>3)*(c->height>>3)+7u)>>3)||!wsChartCoreRecordsValid(c))return wsChError(error,cap,"Invalid exploration snapshot.");
 if(!wsChartMapValid(c))return wsChError(error,cap,"Invalid remembered bitmap shape.");
 uint64_t bound=128u+c->bitBytes+(uint64_t)c->count*20u+8u+c->mapCount+c->mapKnownBytes;if(bound>WS_CHART_BLOB_LIMIT)return wsChError(error,cap,"Exploration snapshot exceeds its bound.");
 unsigned char*blob=(unsigned char*)malloc((size_t)bound);if(!blob)return wsChError(error,cap,"Cannot allocate exploration snapshot.");
 memset(blob,0,128);memcpy(blob,"WSCHRT01",8);wsChPut32(blob+8,1);wsChPut32(blob+12,128);wsChPut32(blob+16,c->width);wsChPut32(blob+20,c->height);wsChPut32(blob+24,c->viewer);wsChPut32(blob+28,c->policy);memcpy(blob+32,c->guid,16);wsChPut32(blob+48,c->count);wsChPut32(blob+52,c->bitBytes);wsChPut32(blob+64,20);wsChPut32(blob+68,1);wsChPut32(blob+88,c->generation);
 wsChPut32(blob+92,c->mapWidth);wsChPut32(blob+96,c->mapHeight);wsChPut32(blob+100,c->mapCount);wsChPut32(blob+104,c->mapKnownBytes);
 memcpy(blob+128,c->bits,c->bitBytes);size_t cursor=128u+c->bitBytes;
 if(c->mapCount){memcpy(blob+cursor,c->mapKnown,c->mapKnownBytes);cursor+=c->mapKnownBytes;memcpy(blob+cursor,c->mapPixels,c->mapCount);cursor+=c->mapCount;}
 uint32_t index=0,runs=0;
 while(index<c->count){
  uint32_t zeros=0,data=0,start;
  while(index<c->count&&wsChZero(c->cells+index,20)){zeros++;index++;}start=index;
  while(index<c->count&&!wsChZero(c->cells+index,20)){if(!wsChartCellValid(c->cells+index)){free(blob);return wsChError(error,cap,"Invalid remembered figure record.");}data++;index++;}
  wsChPut32(blob+cursor,zeros);wsChPut32(blob+cursor+4,data);cursor+=8;
  for(uint32_t n=0;n<data;n++){wsChartCellWrite(blob+cursor,c->cells+start+n);cursor+=20;}runs++;
 }
 wsChPut32(blob+56,runs);wsChPut32(blob+60,(uint32_t)(cursor-128u));wsChPut64(blob+72,wsChHash(blob+128,cursor-128u));wsChPut64(blob+80,wsChHash(blob,128));
 unsigned char*shrunk=(unsigned char*)realloc(blob,cursor);if(shrunk)blob=shrunk;*out=blob;*size=(uint32_t)cursor;return 1;
}
static inline int wsChartCoreDecode(const void*data,uint32_t size,WSChartCore*out,char*error,uint32_t cap){
 if(!data||!out||size<128u||size>WS_CHART_BLOB_LIMIT)return wsChError(error,cap,"Invalid exploration payload size.");
 const unsigned char*p=(const unsigned char*)data;unsigned char head[128];memcpy(head,p,128);uint64_t hash=wsCh64(head+80);memset(head+80,0,8);
 uint32_t w=wsCh32(p+16),h=wsCh32(p+20),viewer=wsCh32(p+24),policy=wsCh32(p+28),count=wsCh32(p+48),bits=wsCh32(p+52),runs=wsCh32(p+56),payload=wsCh32(p+60);
 uint32_t mw=wsCh32(p+92),mh=wsCh32(p+96),mc=wsCh32(p+100),mk=wsCh32(p+104);
 if(memcmp(p,"WSCHRT01",8)||wsCh32(p+8)!=1u||wsCh32(p+12)!=128u||!wsChShape(w,h,viewer,policy)||count!=w*h||bits!=(((w>>3)*(h>>3)+7u)>>3)||!runs||runs>count+1u||payload!=size-128u||(uint64_t)bits+mc+mk>payload||wsCh32(p+64)!=20u||wsCh32(p+68)!=1u||!wsChZero(p+108,20)||hash!=wsChHash(head,128)||wsCh64(p+72)!=wsChHash(p+128,payload)||
    ((!mw||!mh)?(mw||mh||mc||mk):(mw>2048u||mh>2048u||mc!=mw*mh||mk!=((mc+7u)>>3))))return wsChError(error,cap,"Invalid exploration header or checksum.");
 if(mc){
  const unsigned char*known=p+128u+bits,*pixels=known+mk;
  if((mc&7u)&&(known[mk-1u]&~((1u<<(mc&7u))-1u)))return wsChError(error,cap,"Invalid bitmap history padding.");
  for(uint32_t i=0;i<mc;i++)if((known[i>>3]&(1u<<(i&7u)))?pixels[i]>=160u:pixels[i]!=0u)return wsChError(error,cap,"Invalid remembered bitmap palette index.");
 }
 size_t cursor=128u+bits+mk+mc;uint32_t index=0;
 for(uint32_t run=0;run<runs;run++){
  if(cursor>size||size-cursor<8u)return wsChError(error,cap,"Truncated exploration run.");uint32_t zeros=wsCh32(p+cursor),records=wsCh32(p+cursor+4);cursor+=8;
  if((!zeros&&!records)||(run&& !zeros)||zeros>count-index||records>count-index-zeros||(!records&&run+1u!=runs)||(uint64_t)records*20u>size-cursor)return wsChError(error,cap,"Invalid exploration run bounds.");
  index+=zeros+records;
  for(uint32_t n=0;n<records;n++){WSChartCell c;wsChartCellRead(&c,p+cursor);if(wsChZero(&c,20)||!wsChartCellValid(&c))return wsChError(error,cap,"Invalid remembered figure record.");cursor+=20;}
 }
 if(index!=count||cursor!=size)return wsChError(error,cap,"Exploration runs do not cover their exact bounds.");
 WSChartCore next={0};if(!wsChartCoreNew(&next,w,h,viewer,policy,p+32))return wsChError(error,cap,"Cannot allocate exploration memory.");next.generation=wsCh32(p+88);if(!next.generation)next.generation=1;memcpy(next.bits,p+128,bits);
 if(mc){if(!wsChartMapShape(&next,mw,mh)){wsChartCoreFree(&next);return wsChError(error,cap,"Cannot allocate bitmap history.");}memcpy(next.mapKnown,p+128u+bits,mk);memcpy(next.mapPixels,p+128u+bits+mk,mc);}
 cursor=128u+bits+mk+mc;index=0;
 for(uint32_t run=0;run<runs;run++){uint32_t zeros=wsCh32(p+cursor),records=wsCh32(p+cursor+4);cursor+=8;index+=zeros;for(uint32_t n=0;n<records;n++){wsChartCellRead(next.cells+index++,p+cursor);cursor+=20;}}
 if(!wsChartCoreRecordsValid(&next)){wsChartCoreFree(&next);return wsChError(error,cap,"Inconsistent remembered footprint anchors.");}
 *out=next;return 1;
}
#endif
