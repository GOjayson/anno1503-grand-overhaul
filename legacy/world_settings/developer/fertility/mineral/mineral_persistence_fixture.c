#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "world_backend.h"
#define WS_LIMIT 128
#define WS_WORLD 1024
#define WS_COUNT 128
typedef struct WSTemplate {uint32_t oreSlots;} WSTemplate;
static WSTemplate wsTemplates[WS_COUNT];
static WSPlanIsland planned[WS_LIMIT];
static uint32_t planCount,planSpacing;
static int pending,prepared;
static void*preparedScene;
static const uint32_t cropMasks[6]={0x18000,0xf009,0xf949,0xf06b,0xf6b9,0xf04d};
static void*fixtureBases[2];
static void*fixtureModule(const char*name){return fixtureBases[!strcmp(name,"AnnoGame.dll")];}
#define WS_CERT_MODULE(name) fixtureModule(name)
static void wsMessage(char*out,uint32_t cap,const char*message){if(out&&cap)snprintf(out,cap,"%s",message);}
static int wsSeparated(const WSPlanIsland*a,const WSPlanIsland*b,uint32_t gap){return a->x+a->width+gap<=b->x||b->x+b->width+gap<=a->x||a->y+a->height+gap<=b->y||b->y+b->height+gap<=a->y;}
#include "validated_world.inc"
#include "mineral_persistence.inc"
__declspec(dllexport) void PersistenceModules(void*welt,void*game){fixtureBases[0]=welt;fixtureBases[1]=game;}
__declspec(dllexport) int PersistencePlan(WSPlanIsland*p,uint32_t count,uint32_t capacity){if(count>WS_LIMIT)return 0;planCount=count;planSpacing=0;memcpy(planned,p,count*sizeof(*p));for(uint32_t i=0;i<WS_COUNT;i++)wsTemplates[i].oreSlots=capacity;return 1;}
__declspec(dllexport) void PersistencePending(void*scene,int active,int ready){preparedScene=scene;pending=active;prepared=ready;}
__declspec(dllexport) int PersistenceApply(void*scene,char*err,uint32_t cap){return wsStabilizeMineralAbsence(scene,err,cap);}
__declspec(dllexport) int PersistenceFullCertificate(void*scene,char*err,uint32_t cap){return wsLoadedCertificate(scene,err,cap);}
