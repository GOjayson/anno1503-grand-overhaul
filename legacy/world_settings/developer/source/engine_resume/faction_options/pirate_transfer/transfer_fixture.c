#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <string.h>
static void *fixtureWelt,*fixtureGame,*fixtureAI;
static void*fixtureModule(const char*name){return !strcmp(name,"AnnoWelt.dll")?fixtureWelt:!strcmp(name,"AnnoGame.dll")?fixtureGame:NULL;}
#define WS_CERT_MODULE(name) fixtureModule(name)
#include "../runtime/world_backend.c"
static void*WorldSettingsLoadedAIModule(void){return fixtureAI;}
#include "pirate_finalize.inc.candidate"
__declspec(dllexport) void TransferFixtureModules(void*w,void*g,void*a){fixtureWelt=w;fixtureGame=g;fixtureAI=a;}
__declspec(dllexport) int TransferFixtureFinalize(void*scene,uint32_t type,uint32_t culture,char*error,uint32_t cap){return wsFinalizePirateOwnership(scene,type,culture,error,cap);}
