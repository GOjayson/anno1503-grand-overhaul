/* Isolated scene-byte fixture; no game attachment, UI or hooks. */
#include "engine_resume/ai_food/experiment_runtime/world_backend.c"
int WorldSettingsAIExperimentConfigured(void){return 0;}
void WorldSettingsAIProfileAttemptFinished(int success){(void)success;}
__declspec(dllexport) int SceneFixtureBuild(const WSWorldSettings*s,unsigned char*out,uint32_t cap,char*error,uint32_t errorCap){WSBuffer b={out,0,cap};return wsBuildSZE(s,&b,error,errorCap)?(int)b.size:0;}
__declspec(dllexport) int SceneFixturePlayer(const unsigned char*p,uint32_t n,uint32_t faction,unsigned char*out,uint32_t cap,uint32_t*used,char*error,uint32_t errorCap){WSBuffer b={out,*used,cap};int result=wsSpecialScenePlayer(&b,p,n,faction,error,errorCap);*used=b.size;return result;}
