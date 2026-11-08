#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "world_backend.h"
#define WS_LIMIT 128
static const uint32_t cropMasks[6]={0x18000,0xf009,0xf949,0xf06b,0xf6b9,0xf04d};
static WSPlanIsland planned[WS_LIMIT];
static uint32_t planCount;
static int wsPop(uint32_t n){int count=0;while(n){count++;n&=n-1;}return count;}
static void wsMessage(char*out,uint32_t cap,const char*message){if(out&&cap)snprintf(out,cap,"%s",message);}
#include "plant_fertility.inc"
__declspec(dllexport) int PlantFixture(int mode,uint32_t seed,uint32_t count,const uint32_t*climates,WSPlanIsland*out,char*error,uint32_t cap){
 WSWorldSettings settings={0};settings.size=sizeof(settings);settings.plantFertility=mode;
 planCount=count;
 for(uint32_t i=0;i<count&&i<WS_LIMIT;i++){
  WSPlanIsland*p=&planned[i];p->id=i;p->x=i*8;p->y=8;p->width=64;p->height=64;
  p->templateIndex=100+i;p->cropMask=0xdeadbeefu;p->mineralMask=0x5a5a0000u+i;p->cultures=0xff;p->climate=climates[i];
 }
 int result=wsApplyPlantFertility(&settings,seed,error,cap);
 memcpy(out,planned,(count<WS_LIMIT?count:WS_LIMIT)*sizeof(*out));return result;
}
