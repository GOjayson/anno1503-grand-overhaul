#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <string.h>
static void*fixtureWelt,*fixtureGame;
static void*fixtureModule(const char*name){return !strcmp(name,"AnnoWelt.dll")?fixtureWelt:!strcmp(name,"AnnoGame.dll")?fixtureGame:NULL;}
#define WS_CERT_MODULE(name) fixtureModule(name)
#include "runtime/world_backend.c"
__declspec(dllexport) void FactionFixtureModules(void*w,void*g){fixtureWelt=w;fixtureGame=g;}
__declspec(dllexport) int FactionFixturePlayers(void*world,uint32_t factions,char*error,uint32_t cap){planFactions=factions;return wsCertSpecialPlayers(world,error,cap);}
__declspec(dllexport) int FactionFixtureLoaded(void*scene,char*error,uint32_t cap){return wsLoadedCertificate(scene,error,cap);}
__declspec(dllexport) int FactionFixtureSpecialMap(const unsigned char*src,uint32_t size,unsigned char*out,char*error,uint32_t cap){return wsSpecialPlayers(src,size,out,error,cap);}
__declspec(dllexport) int FactionFixtureScene(const WSWorldSettings*s,unsigned char*out,uint32_t cap,char*error,uint32_t errorCap){WSBuffer b={out,0,cap};return wsBuildSZE(s,&b,error,errorCap)?(int)b.size:0;}
__declspec(dllexport) int FactionFixturePreparedRoot(const char*root){if(!root||strlen(root)>=MAX_PATH)return 0;snprintf(gameDirectory,sizeof gameDirectory,"%s",root);pending=1;return 1;}
