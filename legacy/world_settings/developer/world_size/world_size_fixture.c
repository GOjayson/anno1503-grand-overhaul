/* Isolated production serializer/contract fixture, never a native game run.
 * The synthetic one-island plan isolates scene rewriting from layout policy.
 */
#include "../source/engine_resume/ai_food/experiment_runtime/world_backend.c"
int WorldSettingsAIExperimentConfigured(void){return 1;}
void WorldSettingsAIProfileAttemptFinished(int success){(void)success;}
__declspec(dllexport) int SizeFixtureScene(const WSWorldSettings*s,unsigned char*out,uint32_t cap,char*error,uint32_t errorCap){
 if(!wsConfigureWorldSize(s)){wsMessage(error,errorCap,"Unsupported world size.");return 0;}
 planCount=1;planned[0]=(WSPlanIsland){0,0,0,8,8,0,0,0,0,0};
 WSBuffer b={out,0,cap};return wsBuildSZE(s,&b,error,errorCap)?(int)b.size:0;
}
__declspec(dllexport) uint32_t SizeFixtureExpected(WSSceneShip*out,uint32_t cap){if(out&&cap>=wsExpectedSceneShipCount)memcpy(out,wsExpectedSceneShips,wsExpectedSceneShipCount*sizeof(*out));return wsExpectedSceneShipCount;}
__declspec(dllexport) uint32_t SizeFixtureReserves(WSPlanIsland*out,uint32_t cap){if(out&&cap>=wsActiveShipReserveCount)memcpy(out,wsActiveShipReserves,wsActiveShipReserveCount*sizeof(*out));return wsActiveShipReserveCount;}
__declspec(dllexport) int SizeFixtureMatch(uint32_t owner,uint32_t definition,float x,float y,uint32_t*seen){return wsSceneShipMatches(owner,definition,x,y,seen);}
__declspec(dllexport) int SizeFixtureRewrite(unsigned char*p,uint32_t n,char*error,uint32_t errorCap){WSBuffer b={p,n,n};return wsRewriteSceneShips(&b,error,errorCap);}
