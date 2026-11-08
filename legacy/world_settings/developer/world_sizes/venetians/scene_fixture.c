#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#define API __declspec(dllexport)
typedef struct WSBuffer{unsigned char*data;uint32_t size,capacity;}WSBuffer;
static uint16_t wsU16(const unsigned char*p){uint16_t v;memcpy(&v,p,2);return v;}
static uint32_t wsU32(const unsigned char*p){uint32_t v;memcpy(&v,p,4);return v;}
static void wsPut32(unsigned char*p,uint32_t v){memcpy(p,&v,4);}
static int wsTag(const unsigned char*p,const char*tag){return !memcmp(p,tag,strlen(tag))&&p[strlen(tag)]==0;}
static void wsMessage(char*out,uint32_t cap,const char*text){if(out&&cap){snprintf(out,cap,"%s",text);out[cap-1]=0;}}
static int wsAppend(WSBuffer*b,const void*p,uint32_t n){if(b->size>b->capacity||n>b->capacity-b->size)return 0;memcpy(b->data+b->size,p,n);b->size+=n;return 1;}
static int wsChunk(WSBuffer*b,const char*tag,const void*p,uint32_t n){unsigned char h[16]={0};memcpy(h,tag,strlen(tag));wsPut32(h+12,n);return wsAppend(b,h,16)&&wsAppend(b,p,n);}
#include "special_scene.inc"
API uint32_t TestScene(const unsigned char*p,uint32_t n,uint32_t faction,unsigned char*out,uint32_t capacity,char*error,uint32_t cap){WSBuffer b={out,0,capacity};return wsSpecialScenePlayer(&b,p,n,faction,error,cap)?b.size:UINT32_MAX;}
API int TestPlayers(const unsigned char*p,uint32_t n,unsigned char*out,char*error,uint32_t cap){return wsSpecialPlayers(p,n,out,error,cap);}
static int readAllowed=1,callAllowed=1;
static int wsCertRead(const void*p,void*out,size_t n){if(!readAllowed||!p)return 0;memcpy(out,p,n);return 1;}
static void*wsCertPointer(const void*p,size_t off){void*r=0;if(p)memcpy(&r,(const unsigned char*)p+off,8);return r;}
static int wsCertCall(void*p,uint32_t off,uintptr_t a,uintptr_t b,uintptr_t c,uintptr_t*out){(void)a;(void)b;(void)c;if(!callAllowed||!p||off!=0x88)return 0;uint32_t id;memcpy(&id,(unsigned char*)p+8,4);*out=id;return 1;}
#include "owner_gate.generated.h"
API int TestOwner(void*world,void*owner,int allowRead,int allowCall){readAllowed=allowRead;callAllowed=allowCall;return wsCertVenetianOwner(world,owner);}
