/* Include after wsChunk. Identify typed ordinary CPU COMP fields and suspend
 * them before native loading. Selected profiles later resume through native
 * property1a; zero-GUID placeholders never get a thinking dispatch. */
static int wsAISuspensionOffsets(const unsigned char*src,uint32_t size,int difficulty,uint32_t offsets[32],char*error,uint32_t cap){
 unsigned char basics[32]={0},states[32]={0};uint32_t count=0;
 for(uint32_t at=32;at<size;){
  if(size-at<16)goto invalid;uint32_t n=wsU32(src+at+12);if(n>size-at-16)goto invalid;
  if(wsTag(src+at,"SPIELER")){
   if(n<8||wsU32(src+at+16))goto invalid;uint32_t id=wsU32(src+at+20);if(id>=32)goto invalid;
   const unsigned char*p=src+at+24;uint32_t remaining=n-8;
   if(remaining>=8&&!memcmp(p,"HEAD\0\0",6)){
    if(wsU16(p+6)!=108||remaining<116)goto invalid;
    if(wsU16(p+8)==12){if(!id||id>4||basics[id])goto invalid;basics[id]=1;count++;}
   }else{
    for(uint32_t k=0;k<remaining;){
     if(remaining-k<8)goto invalid;uint32_t len=wsU16(p+k+6),h=8;
     if(len>=0xff00){if(remaining-k<10)goto invalid;h=10;len=((len&255u)<<16)|wsU16(p+k+8);}
     if(len>remaining-k-h)goto invalid;const unsigned char*v=p+k+h;
     if(!memcmp(p+k,"COMP\0\0",6)&&len>=8&&wsU32(v)==12){
      if(!id||id>4||states[id]||wsU32(v+4)!=id||len<18||v[len-1])goto invalid;
      uint32_t found=0;
      for(uint32_t t=8;t<len;){
       uint32_t end=t;while(end<len&&v[end])end++;if(end==len)goto invalid;
       if(end-t==9&&!memcmp(v+t,"SUSPEND=",8)){
        if(found++||(v[t+8]!='0'&&v[t+8]!='1'))goto invalid;
        offsets[id]=(uint32_t)((v+t+8)-src);
       }t=end+1;
      }
      if(found!=1)goto invalid;states[id]=1;
     }k+=h+len;
    }
   }
  }at+=n+16;
 }
 if(count!=(uint32_t)(difficulty==0?3:4))goto invalid;
 for(uint32_t id=0;id<32;id++)if(basics[id]!=states[id]||((id>0&&id<=count)!=!!basics[id]))goto invalid;
 return 1;
 invalid:wsMessage(error,cap,"Stock ordinary opponent controller or suspension fields are unsupported.");return 0;
}
static int wsAIAppendSourceChunk(WSBuffer*b,const unsigned char*src,uint32_t at,uint32_t length,const uint32_t offsets[32]){
 uint32_t output=b->size;if(!wsAppend(b,src+at,length))return 0;
 for(uint32_t id=1;id<32;id++)if(offsets[id]>=at&&offsets[id]-at<length)b->data[output+offsets[id]-at]='1';
 return 1;
}
