/* Strict current vision is independent from remembered island/city knowledge.
 * Only bounded read-only snapshots feed these display predicates. */
#include "start_visibility_actor_layouts.h"
static int wsVisibilityFinite(float n){uint32_t bits;memcpy(&bits,&n,4);return (bits&0x7f800000u)!=0x7f800000u;}
static int wsVisibilityPointValid(const WSVisibilityWorld*v,float x,float z){return wsVisibilityFinite(x)&&wsVisibilityFinite(z)&&x>=0.0f&&z>=0.0f&&x<(float)v->width&&z<(float)v->height;}
static int wsVisibilityFloat(void*object,size_t offset,float*out){return wsCertRead((unsigned char*)object+offset,out,4)&&wsVisibilityFinite(*out);}
static const WSVisibilityActorLayout*wsVisibilityActorLayout(void*object,unsigned char*module){
 void*vt=wsCertPointer(object,0);
 for(size_t i=0;i<sizeof wsVisibilityActorLayouts/sizeof wsVisibilityActorLayouts[0];i++){
  const WSVisibilityActorLayout*a=&wsVisibilityActorLayouts[i];if(vt!=module+a->vtable)continue;
  if(wsCertPointer(vt,0x38)!=module+a->worldGetter||wsCertPointer(vt,0x40)!=module+a->ownerGetter||
     wsCertPointer(vt,0xb0)!=module+a->xGetter||wsCertPointer(vt,0xc0)!=module+a->zGetter)return 0;
  return a;
 }
 return 0;
}
static int wsVisibilityOwner(void*object,unsigned char*module,void**player){
 *player=0;if(!object)return 1;void*vt=wsCertPointer(object,0);
 if(vt==module+0xfabe0){*player=object;return 1;}
 if(vt==module+0xfc678){*player=wsCertPointer(object,0x28);return *player&&wsCertPointer(*player,0)==module+0xfabe0;}
 for(size_t i=0;i<sizeof wsVisibilityProductionVtables/sizeof wsVisibilityProductionVtables[0];i++)if(vt==module+wsVisibilityProductionVtables[i]){
  void*city=wsCertPointer(object,0x18);if(wsCertPointer(city,0)!=module+0xfc678)return 0;
  *player=wsCertPointer(city,0x28);return *player&&wsCertPointer(*player,0)==module+0xfabe0;
 }
 return 0; /* An unknown owner object is never cast to a player. */
}
static int wsVisibilityObserverList(WSVisibilityDrawContext*c,void*human,size_t headOffset,uint32_t limit,int cities){
 void*node=wsCertPointer(human,headOffset),*previous=0;void*seen[WS_VISIBILITY_SHIP_LIMIT];uint32_t count=0;
 while(node){
  if(count>=limit||!wsCertMemory(node,24,0)||wsCertPointer(node,0)!=previous)return 0;
  unsigned char*object=(unsigned char*)wsCertPointer(node,0x10);if(!object)return 0;
  for(uint32_t i=0;i<count;i++)if(seen[i]==object)return 0;seen[count++]=object;
  WSVisibilityVisionSource source={0};int have=0;
  if(!cities){
   if(wsCertPointer(object,0)!=c->view.module+0xee000||wsCertPointer(object,0x270)!=human||
      wsCertPointer(object,0x20)!=c->view.world||!wsVisibilityFloat(object,0x28,&source.left)||
      !wsVisibilityFloat(object,0x30,&source.top)||!wsVisibilityPointValid(&c->view,source.left,source.top))return 0;
   source.right=source.left;source.bottom=source.top;have=1;
  }else{
   if(wsCertPointer(object,0)!=c->view.module+0xfc678||wsCertPointer(object,0x28)!=human)return 0;
   void*island=wsCertPointer(object,0x20);const WSVisibilityIsland*known=0;
   for(uint32_t i=0;i<WS_VISIBILITY_ISLAND_LIMIT;i++)if(c->present[i]&&c->islands[i].object==island){known=&c->islands[i];break;}
   if(!known||wsCertPointer(object,0x1b0)!=c->view.module+0xfc228)return 0;
   uintptr_t begin=(uintptr_t)wsCertPointer(object,0x310),end=(uintptr_t)wsCertPointer(object,0x318);
   if(end<begin||(end-begin)%8u||(end-begin)/8u>65536u||((end>begin)&&!wsCertMemory((void*)begin,end-begin,0)))return 0;
   for(uintptr_t at=begin;at<end;at+=8u){
    void*building=wsCertPointer((void*)at,0);if(!building)continue;void*vt=wsCertPointer(building,0);uint16_t xy[2];
    if(wsCertPointer(vt,0xf8)!=c->view.module+0x832a0||wsCertPointer(vt,0x38)!=c->view.module+0x84fe0||
       wsCertPointer(building,0x18)!=object||!wsCertRead((unsigned char*)building+0xa,xy,4)||
       xy[0]<known->x||xy[1]<known->y||xy[0]>=known->x+known->width||xy[1]>=known->y+known->height)return 0;
    if(!have){source.left=source.right=(float)xy[0];source.top=source.bottom=(float)xy[1];have=1;}
    else{if((float)xy[0]<source.left)source.left=(float)xy[0];if((float)xy[0]>source.right)source.right=(float)xy[0];
     if((float)xy[1]<source.top)source.top=(float)xy[1];if((float)xy[1]>source.bottom)source.bottom=(float)xy[1];}
   }
  }
  if(have){if(c->visionCount>=WS_VISIBILITY_VISION_LIMIT)return 0;c->vision[c->visionCount++]=source;}
  previous=node;node=wsCertPointer(node,8);
 }
 return previous==wsCertPointer(human,headOffset+8u);
}
static int wsVisibilityObserversRead(WSVisibilityDrawContext*c){
 void*table=wsCertPointer(c->view.world,0x210);uint32_t id=UINT32_MAX;
 if(wsCertPointer(table,0)!=c->view.module+0xfdbc0)return 0;
 c->human=(unsigned char*)wsCertPointer(table,8);
 if(wsCertPointer(c->human,0)!=c->view.module+0xfabe0||wsCertPointer(c->human,0x10)!=c->view.world||
    !wsCertRead(c->human+8,&id,4)||id)return 0;
 return wsVisibilityObserverList(c,c->human,0x2e8,WS_VISIBILITY_SHIP_LIMIT,0)&&
  wsVisibilityObserverList(c,c->human,0x318,WS_VISIBILITY_CITY_LIMIT,1);
}
static int wsVisibilityInSight(const WSVisibilityDrawContext*c,float x,float z){
 if(!wsVisibilityPointValid(&c->view,x,z))return 0;
 if(c->view.enemy)return 1;
 for(uint32_t i=0;i<c->visionCount;i++){
  const WSVisibilityVisionSource*s=&c->vision[i];
  float dx=x<s->left?s->left-x:(x>s->right?x-s->right:0.0f);
  float dz=z<s->top?s->top-z:(z>s->bottom?z-s->bottom:0.0f);
  if(dx*dx+dz*dz<=WS_VISIBILITY_SIGHT_RADIUS*WS_VISIBILITY_SIGHT_RADIUS)return 1;
 }
 return 0;
}
static const WSVisibilityIsland*wsVisibilityIslandAt(const WSVisibilityDrawContext*c,float x,float z){
 for(uint32_t i=0;i<WS_VISIBILITY_ISLAND_LIMIT;i++)if(c->present[i]){
  const WSVisibilityIsland*s=&c->islands[i];
  if(x>=(float)s->x&&z>=(float)s->y&&x<(float)(s->x+s->width)&&z<(float)(s->y+s->height))return s;
 }
 return 0;
}
static int wsVisibilityOwnedBuilding(const WSVisibilityDrawContext*,const WSVisibilityIsland*,float,float,void**);
static int wsVisibilityActorValuesInContext(const WSVisibilityDrawContext*c,const WSVisibilityActorLayout*a,float x,float z,void*owner){
 if(!wsVisibilityPointValid(&c->view,x,z))return 0;
 void*player=0;
 int knownOwner=wsVisibilityOwner(owner,c->view.module,&player);
 if(player&&player==c->human)return wsCertPointer(player,0x10)==c->view.world;
 if(c->view.enemy&&owner&&(player||!knownOwner))return 1;
 int wildlife=a->vtable==0xf0ed0u||a->vtable==0xf13d0u||a->vtable==0xf1738u||a->vtable==0xf0570u;
 if(!wildlife&&!c->view.enemy&&owner&&(!knownOwner||player))return wsVisibilityInSight(c,x,z);
 if(!c->view.enemy&&!owner&&(a->vtable==0xf5b48u||a->vtable==0xf41c8u)){
  const WSVisibilityIsland*island=wsVisibilityIslandAt(c,x,z);void*cityOwner=0;
  if(island&&wsVisibilityOwnedBuilding(c,island,x,z,&cityOwner)&&cityOwner!=c->human)return wsVisibilityInSight(c,x,z);
 }
 if(c->view.map==0){
  const WSVisibilityIsland*island=wsVisibilityIslandAt(c,x,z);
  if(island&&!(island->discovered&(1u<<c->view.viewer)))return 0;
 }
 return 1;
}
static int wsVisibilityActorInContext(const WSVisibilityDrawContext*c,void*actor,const WSVisibilityActorLayout*a){
 float x=0,z=0;if(!wsVisibilityFloat(actor,a->xOffset,&x)||!wsVisibilityFloat(actor,a->zOffset,&z))return 0;
 return wsVisibilityActorValuesInContext(c,a,x,z,a->ownerOffset?wsCertPointer(actor,a->ownerOffset):0);
}
static int wsVisibilityWithinModule(unsigned char*module,const void*address,size_t count){
 unsigned char dos[64],header[0x58];uint32_t nt=0,size=0;uintptr_t start=(uintptr_t)module,at=(uintptr_t)address;
 if(!module||!address||!count||!wsCertRead(module,dos,sizeof dos)||memcmp(dos,"MZ",2))return 0;
 memcpy(&nt,dos+0x3c,4);if(nt>0x100000u||!wsCertRead(module+nt,header,sizeof header)||
    memcmp(header,"PE\0\0",4)||wsU16(header+4)!=0x8664u||wsU16(header+24)!=0x20bu)return 0;
 memcpy(&size,header+0x50,4);
 return size&&size<=64u*1024u*1024u&&at>=start&&at-start<size&&count<=size-(at-start)&&wsCertMemory(address,count,0);
}
/* Exact native catalogue-definition classes. The server catalogue uses Game
 * tAnlage/Display/Edit, while graphics catalogues may use Display Haus classes.
 * Native categories and ware69/70 exceptions preserve neutral objects; claimed
 * territory alone never classifies an object. No virtual getter is executed. */
/* Raw reads below are restricted to ranges preflighted by FastPrepare in the
 * SAME native draw. Only copied scalar metadata is reused; every live binding
 * is compared with the current readable owner before following its span. */
static void*wsVisibilityFastPointer(const void*object,size_t offset){void*p;memcpy(&p,(const unsigned char*)object+offset,8);return p;}
static WSVisibilityFastDefinition*wsVisibilityFastDefinitionRead(const WSVisibilityDrawContext*c,uint32_t id){
 WSVisibilityFastDraw*f=c->fast;if(!f||!f->catalogueReady||id>=4000u)return 0;
 WSVisibilityFastDefinition*d=&f->metadata[id];void*object=f->definitions[id];
 if(wsVisibilityFastPointer(c->view.world,0x200)!=f->catalogue||wsVisibilityFastPointer(f->catalogue,0)!=f->catalogueVT||
    wsVisibilityFastPointer(f->catalogueVT,0xe8)!=f->game+0xb4d0||
    wsVisibilityFastPointer(f->catalogue,0x218u+(size_t)id*8u)!=object){d->state=-1;return d;}
 if(d->state){
  if(d->state>0&&object){
   if(wsVisibilityFastPointer(object,0)!=d->vtable)d->state=-1;
   else if(d->classTag==1u){uint16_t kind;memcpy(&kind,(unsigned char*)object+0x18,2);
    if(kind!=d->kind||((unsigned char*)object)[0x20e]!=d->subtype||
       wsVisibilityFastPointer(d->vtable,0xc0)!=f->game+0x1090||wsVisibilityFastPointer(d->vtable,0x160)!=f->game+0x41e0)d->state=-1;
   }else if(d->classTag==2u){uint16_t kind;memcpy(&kind,(unsigned char*)object+0x38,2);
    if(kind!=d->kind||wsVisibilityFastPointer(d->vtable,0xc0)!=f->display+0x27790)d->state=-1;
    d->subtypeKnown=(unsigned char)(wsVisibilityFastPointer(d->vtable,0x160)==f->display+0x17540);
   }else if(d->classTag==3u)d->subtypeKnown=(unsigned char)(wsVisibilityFastPointer(d->vtable,0x160)==f->display+0x17540);
   else if(d->classTag==4u)d->subtypeKnown=(unsigned char)(wsVisibilityFastPointer(d->vtable,0x160)==f->display+0x62770);
  }return d;
 }
 d->object=object;d->state=1;if(!object)return d;
 d->vtable=wsCertPointer(object,0);if(!d->vtable){d->state=-1;return d;}
 void*vt=d->vtable;
 if(vt==f->game+0x1f888||vt==f->game+0x1fac8||vt==f->game+0x1fcf8){
  if(wsVisibilityFastPointer(vt,0xc0)!=f->game+0x1090||wsVisibilityFastPointer(vt,0x160)!=f->game+0x41e0||
     !wsCertMemory(object,0x20f,0)){d->state=-1;return d;}
  memcpy(&d->kind,(unsigned char*)object+0x18,2);d->subtype=((unsigned char*)object)[0x20e];
  d->mainClass=d->subtypeKnown=d->classTag=1;return d;
 }
 if(vt==f->display+0xf612e0||vt==f->display+0xf61400){
  if(wsVisibilityFastPointer(vt,0xc0)!=f->display+0x27790||!wsCertMemory(object,0x3a,0)){d->state=-1;return d;}
  memcpy(&d->kind,(unsigned char*)object+0x38,2);d->mainClass=1;
  d->subtypeKnown=(unsigned char)(wsVisibilityFastPointer(vt,0x160)==f->display+0x17540);d->classTag=2;return d;
 }
 int zero=vt==f->display+0xf609d0||vt==f->display+0xf60e60;
 if(zero){d->classTag=3;d->subtypeKnown=(unsigned char)(wsVisibilityFastPointer(vt,0x160)==f->display+0x17540);}
 else if(vt==f->display+0xf60af0){d->classTag=4;d->subtypeKnown=(unsigned char)(wsVisibilityFastPointer(vt,0x160)==f->display+0x62770);}
 return d;
}
static int wsVisibilityFastOwnedBuilding(const WSVisibilityDrawContext*c,const WSVisibilityIsland*island,float x,float z,void**owner){
 WSVisibilityFastDraw*f=c->fast;if(!f||!f->catalogueReady||island->id>=WS_VISIBILITY_ISLAND_LIMIT)return -2;
 WSVisibilityFastIsland*s=&f->islands[island->id];if(!s->ready||s->object!=island->object)return -2;
 if(wsVisibilityFastPointer(c->view.world,0x6640u+(size_t)island->id*8u)!=s->object)return -1;
 if(wsVisibilityFastPointer(s->object,0x10)!=s->tiles)return -1;
 uint32_t localX=(uint32_t)x-island->x,localZ=(uint32_t)z-island->y,tile[2];
 if(localX>=island->width||localZ>=island->height)return -1;
 memcpy(tile,s->tiles+((size_t)localZ*island->width+localX)*8u,8);
 uint32_t city=(tile[1]>>25)&15u;if(city==15u)return 0;
 uint32_t dx=(tile[0]>>16)&7u,dz=(tile[0]>>19)&7u;
 if(dx||dz){
  if(dx>localX||dz>localZ)return 0;uint32_t anchor[2];memcpy(anchor,s->tiles+((size_t)(localZ-dz)*island->width+localX-dx)*8u,8);
  if(!(anchor[0]&0x80000000u)||(anchor[0]&0x003f0000u)||
     (anchor[0]&0x00c0ffffu)!=(tile[0]&0x00c0ffffu)||((anchor[1]>>25)&15u)!=city)return 0;
  memcpy(tile,anchor,sizeof tile);
 }
 if(!(tile[0]&0x80000000u))return 0;
 uint32_t id=tile[0]&0xffffu;if(id>=4000u)return -1;
 WSVisibilityFastDefinition*d=wsVisibilityFastDefinitionRead(c,id);if(!d||d->state<0)return -1;if(!d->mainClass)return 0;
 uint32_t category=(((uint32_t)d->kind-1u)&~31u)+1u;
 if(category!=1u&&category!=0x21u&&category!=0x41u&&category!=0x61u&&category!=0x81u&&category!=0xa1u&&
    category!=0xc1u&&category!=0xe1u&&category!=0x101u&&category!=0x121u)return 0;
 if(category==0xe1u&&(d->subtype==69u||d->subtype==70u))return 0;
 if(d->kind==0xe2u&&!d->subtype){
  if(id==3999u)return 0;WSVisibilityFastDefinition*next=wsVisibilityFastDefinitionRead(c,id+1u);
  if(!next||next->state<0||!next->subtypeKnown||next->subtype==69u||next->subtype==70u)return 0;
 }
 if(!s->cityValid[city]||wsVisibilityFastPointer(s->object,0x68u+(size_t)city*8u)!=s->cities[city]||
    wsVisibilityFastPointer(s->cities[city],0)!=c->view.module+0xfc678||
    wsVisibilityFastPointer(s->cities[city],0x20)!=island->object||
    wsVisibilityFastPointer(s->cities[city],0x28)!=s->owners[city]||
    wsVisibilityFastPointer(s->owners[city],0)!=c->view.module+0xfabe0||
    wsVisibilityFastPointer(s->owners[city],0x10)!=c->view.world)return -1;
 *owner=s->owners[city];return 1;
}
static int wsVisibilityOwnedBuilding(const WSVisibilityDrawContext*c,const WSVisibilityIsland*island,float x,float z,void**owner){
 int fast=wsVisibilityFastOwnedBuilding(c,island,x,z,owner);if(fast!=-2)return fast;
 unsigned char*game=(unsigned char*)WS_CERT_MODULE("AnnoGame.dll"),*display=(unsigned char*)WS_CERT_MODULE("AnnoDisplay.dll");
 void*catalogue=wsCertPointer(c->view.world,0x200),*vt=wsCertPointer(catalogue,0);uint32_t tile[2];
 uint32_t localX=(uint32_t)x-island->x,localZ=(uint32_t)z-island->y;
 unsigned char*tiles=(unsigned char*)wsCertPointer(island->object,0x10);
 if(!tiles||!wsCertRead(tiles+((size_t)localZ*island->width+localX)*8u,tile,8))return -1;
 uint32_t cityIndex=(tile[1]>>25)&15u;if(cityIndex==15u)return 0;
 /* Native3A2D0 resolves footprint continuation offsets from cell byte2.
  * FigurePoints centers/rotates graphics away from the owning anchor, so a
  * sprite's sampled cell need not have the anchor flag. Follow ONE bounded
  * native offset and require the same definition, rotation and city identity. */
 uint32_t dx=(tile[0]>>16)&7u,dz=(tile[0]>>19)&7u;
 if(dx||dz){
  if(dx>localX||dz>localZ)return 0;uint32_t anchor[2];
  if(!wsCertRead(tiles+((size_t)(localZ-dz)*island->width+localX-dx)*8u,anchor,8))return -1;
  if(!(anchor[0]&0x80000000u)||(anchor[0]&0x003f0000u)||
     (anchor[0]&0x00c0ffffu)!=(tile[0]&0x00c0ffffu)||((anchor[1]>>25)&15u)!=cityIndex)return 0;
  memcpy(tile,anchor,sizeof tile);
 }
 if(!(tile[0]&0x80000000u))return 0;
 if(!game||!display||(vt!=game+0x20300&&vt!=game+0x20738&&vt!=game+0x20a78&&vt!=game+0x20c90)||
    wsCertPointer(vt,0xe8)!=game+0xb4d0)return -1;
 uint32_t definition=tile[0]&0xffffu;if(definition>0xf9fu)return -1;
 void*render=wsCertPointer(catalogue,0x218u+(size_t)definition*8u),*renderVT=wsCertPointer(render,0);
 int gameDefinition=renderVT==game+0x1f888||renderVT==game+0x1fac8||renderVT==game+0x1fcf8;
 uint16_t kind=0;
 if(gameDefinition){
  if(!wsVisibilityWithinModule(game,(unsigned char*)renderVT+0x160,8)||
     wsCertPointer(renderVT,0xc0)!=game+0x1090||wsCertPointer(renderVT,0x160)!=game+0x41e0||
     !wsCertRead((unsigned char*)render+0x18,&kind,2))return -1;
 }else{
  if(renderVT!=display+0xf612e0&&renderVT!=display+0xf61400)return 0;
  if(!wsVisibilityWithinModule(display,(unsigned char*)renderVT+0xc0,8)||
     wsCertPointer(renderVT,0xc0)!=display+0x27790||!wsCertRead((unsigned char*)render+0x38,&kind,2))return -1;
 }
 uint32_t category=(((uint32_t)kind-1u)&~31u)+1u;
 if(category!=1u&&category!=0x21u&&category!=0x41u&&category!=0x61u&&category!=0x81u&&category!=0xa1u&&
    category!=0xc1u&&category!=0xe1u&&category!=0x101u&&category!=0x121u)return 0;
 uint8_t subtype=0;
 if(category==0xe1u){
  /* Original Game getter41E0(index0) and the Food selector's index0 branch
   * both return byte20E unchanged. Display positive Haus getters return0. */
  if(gameDefinition){if(!wsCertRead((unsigned char*)render+0x20e,&subtype,1))return -1;}
  if(subtype==69u||subtype==70u)return 0;
 }
 if(kind==0xe2u&&!subtype){
  /* Native CDF10 asks the NEXT definition only when this exact kind's own
   * subtype is0. Read only proved Game fields or Display constant/masked
   * getters; preserve any unproved neighbour without making a native call. */
  if(definition>=0xf9fu)return 0;
  void*next=wsCertPointer(catalogue,0x218u+(size_t)(definition+1u)*8u),*nextVT=wsCertPointer(next,0);
  int nextGame=nextVT==game+0x1f888||nextVT==game+0x1fac8||nextVT==game+0x1fcf8;
  if(nextGame){
   if(!wsVisibilityWithinModule(game,(unsigned char*)nextVT+0x160,8)||
      wsCertPointer(nextVT,0xc0)!=game+0x1090||wsCertPointer(nextVT,0x160)!=game+0x41e0||
      !wsCertRead((unsigned char*)next+0x20e,&subtype,1)||subtype==69u||subtype==70u)return 0;
  }else{
   int zeroClass=nextVT==display+0xf609d0||nextVT==display+0xf60e60||nextVT==display+0xf612e0||nextVT==display+0xf61400;
   if(!wsVisibilityWithinModule(display,(unsigned char*)nextVT+0x160,8)||
      !((zeroClass&&wsCertPointer(nextVT,0x160)==display+0x17540)||
        (nextVT==display+0xf60af0&&wsCertPointer(nextVT,0x160)==display+0x62770)))return 0;
  }
 }
 void*city=wsCertPointer(island->object,0x68u+(size_t)cityIndex*8u);
 if(wsCertPointer(city,0)!=c->view.module+0xfc678||wsCertPointer(city,0x20)!=island->object)return -1;
 *owner=wsCertPointer(city,0x28);
 return *owner&&wsCertPointer(*owner,0)==c->view.module+0xfabe0?1:-1;
}
static int wsVisibilitySpritePoint(const WSVisibilityDrawContext*c,const float*position){
 float xyz[3];uintptr_t at=(uintptr_t)position;
 if(!position)return 0;
 if(c->fast&&c->fast->stackBegin&&at>=c->fast->stackBegin&&at<c->fast->stackEnd&&sizeof xyz<=c->fast->stackEnd-at)
  memcpy(xyz,position,sizeof xyz);
 else if(!wsCertRead(position,xyz,sizeof xyz))return 0;
 if(!wsVisibilityPointValid(&c->view,xyz[0],xyz[2]))return 0;
 if(c->view.enemy)return 1;
 const WSVisibilityIsland*island=wsVisibilityIslandAt(c,xyz[0],xyz[2]);if(!island)return 1;
 void*owner=0;int building=wsVisibilityOwnedBuilding(c,island,xyz[0],xyz[2],&owner);
 if(!building)return 1;
 if(owner==c->human)return 1;
 return wsVisibilityInSight(c,xyz[0],xyz[2]);
}
