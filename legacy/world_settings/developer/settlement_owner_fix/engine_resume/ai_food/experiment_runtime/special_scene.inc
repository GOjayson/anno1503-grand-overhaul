/* Include after wsChunk. No arbitrary byte search or filename-based identity. */
static int wsSpecialFields(const unsigned char*p,uint32_t n,int basic,uint32_t id,uint32_t*out){
 uint32_t at=0,type=0,volk=0,alias=0,comp=0;
 while(at<n){if(n-at<8)return 0;const unsigned char*h=p+at;uint32_t len=wsU16(h+6),head=8;
  if(len>=0xff00){if(n-at<10)return 0;head=10;len=((len&255u)<<16)|wsU16(h+8);}
  if(len>n-at-head)return 0;const unsigned char*v=h+head;
  if(!memcmp(h,"HEAD\0\0",6)){if(!basic||type||len!=108)return 0;type=wsU16(v);}
  else if(!memcmp(h,"VOLK\0\0",6)){if(!basic||volk||len!=8)return 0;volk=!memcmp(v,"PIRATEN\0",8)?1u:!memcmp(v,"VENECIA\0",8)?2u:0u;if(!volk)return 0;}
  else if(!memcmp(h,"ALIAS\0",6)){if(!basic||alias)return 0;alias=(len==8&&!memcmp(v,"PIRAT01\0",8))?1u:(len==10&&!memcmp(v,"VENEZIA01\0",10))?2u:0u;if(!alias)return 0;}
  else if(!memcmp(h,"COMP\0\0",6)){if(basic||comp||len<9||wsU32(v+4)!=id)return 0;comp=wsU32(v)==15?1u:wsU32(v)==16?2u:0u;if(!comp||v[len-1])return 0;}
  at+=head+len;
 }
 if(basic){uint32_t f=type==15?1u:type==16?2u:0u;if(!f||f!=volk||f!=alias)return 0;*out=f;}
 else{if(!comp)return 0;*out=comp;}
 return 1;
}
static int wsSpecialPlayers(const unsigned char*src,uint32_t size,unsigned char out[32],char*error,uint32_t cap){
 unsigned char basics[32]={0},states[32]={0};uint32_t found=0;
 for(uint32_t at=32;at<size;){if(size-at<16)goto invalid;uint32_t n=wsU32(src+at+12);if(n>size-at-16)goto invalid;
  if(wsTag(src+at,"SPIELER")){if(n<8||wsU32(src+at+16)!=0)goto invalid;uint32_t id=wsU32(src+at+20);if(id>=32)goto invalid;
   const unsigned char*p=src+at+24;uint32_t f=0;
   if(n>=24&&!memcmp(p,"HEAD\0\0",6)){uint32_t type=wsU16(p+8);if(type==15||type==16){if(basics[id]||!wsSpecialFields(p,n-8,1,id,&f))goto invalid;basics[id]=(unsigned char)f;found|=f;}}
   else{ /* COMP must be identified as a sized field, not by searching payload. */
    for(uint32_t k=0;k<n-8;){if(n-8-k<8)goto invalid;uint32_t len=wsU16(p+k+6),h=8;if(len>=0xff00){if(n-8-k<10)goto invalid;h=10;len=((len&255u)<<16)|wsU16(p+k+8);}if(len>n-8-k-h)goto invalid;
     if(!memcmp(p+k,"COMP\0\0",6)&&len>=8&&(wsU32(p+k+h)==15||wsU32(p+k+h)==16)){if(states[id]||!wsSpecialFields(p,n-8,0,id,&f))goto invalid;states[id]=(unsigned char)f;}
     k+=h+len;
    }
   }
  }at+=n+16;
 }
 if(found!=3)goto invalid;uint32_t counts[3]={0};
 for(uint32_t id=0;id<32;id++){if(basics[id]!=states[id])goto invalid;if(basics[id])counts[basics[id]]++;out[id]=basics[id];}
 if(counts[1]!=1||counts[2]!=1)goto invalid;return 1;
 invalid:wsMessage(error,cap,"Stock special player identities or paired controller records are unsupported.");return 0;
}
/* Stock Easy embeds a Venetian city on its original island map. Replacing
 * that map must not import the city's absolute position into a new island.
 * Retain the native player and the selected difficulty's exact controller;
 * Medium/Hard already start that controller without a serialized city.
 * Validate the complete bounded state before publishing any output. */
static int wsSpecialScenePlayer(WSBuffer*b,const unsigned char*p,uint32_t n,uint32_t faction,char*error,uint32_t cap){
 uint32_t removed=0,cityCount=0;
 if(!b||!p||n<8||faction>2)goto invalid;
 if(faction==2){
  uint32_t actual=0,id=wsU32(p+4);
  int basic=n>=14&&!memcmp(p+8,"HEAD\0\0",6);
  if(wsU32(p)||id>=32||!wsSpecialFields(p+8,n-8,basic,id,&actual)||actual!=2)goto invalid;
  for(uint32_t at=basic?n:8;at<n;){
   uint32_t len=wsU16(p+at+6),head=8;
   if(len>=0xff00){head=10;len=((len&255u)<<16)|wsU16(p+at+8);}
   if(!memcmp(p+at,"STADT2",6)){
    if(len<6||++cityCount>1)goto invalid;
    removed+=head+len;
   }
   at+=head+len;
  }
 }
 if(b->size>b->capacity||b->capacity-b->size<16||n-removed>b->capacity-b->size-16){wsMessage(error,cap,"Generated scene buffer cannot hold a special player state.");return 0;}
 if(!removed)return wsChunk(b,"SPIELER",p,n);
 unsigned char header[16]={0};memcpy(header,"SPIELER",7);wsPut32(header+12,n-removed);
 if(!wsAppend(b,header,16)||!wsAppend(b,p,8))return 0;
 for(uint32_t at=8;at<n;){
  uint32_t len=wsU16(p+at+6),head=8;
  if(len>=0xff00){head=10;len=((len&255u)<<16)|wsU16(p+at+8);}
  if(memcmp(p+at,"STADT2",6)&&!wsAppend(b,p+at,head+len))return 0;
  at+=head+len;
 }
 return 1;
 invalid:wsMessage(error,cap,"Stock Venetian map-bound state is unsupported.");return 0;
}
static int wsSpecialScript(WSBuffer*b,const unsigned char*p,uint32_t n,uint32_t enabled,const unsigned char special[32],char*error,uint32_t cap){
 if((enabled&3u)==3u)return wsChunk(b,"BIGBROTHER",p,n);
 unsigned char*copy=(unsigned char*)malloc(n?n:1);if(!copy)return 0;uint32_t used=0,seen=0;
 for(uint32_t at=0;at<n;){uint32_t end=at;while(end<n&&p[end]!='\n')end++;uint32_t next=end<n?end+1:end,lineEnd=end;if(lineEnd>at&&p[lineEnd-1]=='\r')lineEnd--;int omit=0;
  for(uint32_t id=0;id<32;id++)if(special[id]&&!(enabled&special[id])){char line[64];int length=snprintf(line,sizeof line,"\"%s\" %u",special[id]==1?"PIRAT01":"VENEZIA01",id);if(length>0&&(uint32_t)length==lineEnd-at&&!memcmp(line,p+at,(size_t)length)){if(seen&special[id]){free(copy);wsMessage(error,cap,"Duplicate special player script mapping.");return 0;}seen|=special[id];omit=1;}}
  if(!omit){memcpy(copy+used,p+at,next-at);used+=next-at;}at=next;
 }
 if(seen!=(3u&~enabled)){free(copy);wsMessage(error,cap,"Special player script mapping is absent.");return 0;}
 int ok=wsChunk(b,"BIGBROTHER",copy,used);free(copy);return ok;
}
