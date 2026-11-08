#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "../engine_resume/ai_food/experiment_runtime/world_backend.h"
#define WS_LIMIT 128
#define WS_WORLD 1024
#define WS_COUNT 1
static WSPlanIsland planned[WS_LIMIT];
static uint32_t planCount,planSpacing;
static const uint32_t cropMasks[6]={0x18000,0xf009,0xf949,0xf06b,0xf6b9,0xf04d};
static void*fixtureBases[2];
static void*fixtureModule(const char*name){return fixtureBases[!strcmp(name,"AnnoGame.dll")];}
#define WS_CERT_MODULE(name) fixtureModule(name)
static void wsMessage(char*out,uint32_t cap,const char*message){if(out&&cap)snprintf(out,cap,"%s",message);}
static int wsSeparated(const WSPlanIsland*a,const WSPlanIsland*b,uint32_t gap){return a->x+a->width+gap<=b->x||b->x+b->width+gap<=a->x||a->y+a->height+gap<=b->y||b->y+b->height+gap<=a->y;}
#include "validated_world.inc"
__declspec(dllexport) void FixtureModules(void*welt,void*game){fixtureBases[0]=welt;fixtureBases[1]=game;}
__declspec(dllexport) int FixturePlan(WSPlanIsland*p,uint32_t count,uint32_t gap){if(count>WS_LIMIT)return 0;planCount=count;planSpacing=gap;memcpy(planned,p,count*sizeof(*p));return 1;}
__declspec(dllexport) int FixtureValidate(void*scene,char*err,uint32_t cap){return wsLoadedCertificate(scene,err,cap);}
__declspec(dllexport) int FixtureMemory(void*data,size_t count,int execute){return wsCertMemory(data,count,execute);}
__declspec(dllexport) void*FixtureMethod(void*data,uint32_t slot){return wsCertMethod(data,slot);}
__declspec(dllexport) uint32_t FixtureCulture(uint32_t value){return wsCertCulture(value);}
