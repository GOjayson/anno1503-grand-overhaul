#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>
#define WS_LIMIT 128
#define WS_COUNT 128
typedef struct WSWorldSettings { int32_t mineralFertility; } WSWorldSettings;
typedef struct WSPlanIsland { uint32_t id,x,y,width,height,templateIndex,cropMask,mineralMask,cultures,climate; } WSPlanIsland;
typedef struct WSTemplate { uint32_t climate,oreSlots; } WSTemplate;
static const uint32_t mineralMasks[6]={0,0x45,0x65,0x41,0x43,0x4b};
static WSTemplate wsTemplates[WS_COUNT];
static WSPlanIsland planned[WS_LIMIT];
static uint32_t planCount;
static int wsPop(uint32_t n){int c=0;while(n){c++;n&=n-1;}return c;}
static void wsMessage(char*out,uint32_t cap,const char*msg){if(out&&cap)snprintf(out,cap,"%s",msg);}
#include "mineral_fertility.inc"
__declspec(dllexport) int MineralFixture(int32_t mode,uint32_t seed,uint32_t count,const WSPlanIsland*in,const WSTemplate*templates,WSPlanIsland*out){
 if(count>WS_LIMIT)return 0;
 planCount=count;
 memcpy(planned,in,count*sizeof(*in));
 memcpy(wsTemplates,templates,sizeof(wsTemplates));
 WSWorldSettings s={mode};char error[256]={0};
 int result=wsApplyMineralFertility(&s,seed,error,sizeof(error));
 memcpy(out,planned,count*sizeof(*out));return result;
}
