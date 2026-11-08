#ifndef ANNO_WORLD_BACKEND_H
#define ANNO_WORLD_BACKEND_H
#include <stdint.h>
typedef struct WSWorldSettings {
 uint32_t size; int32_t difficulty,islandSize,islandCount,spacing,aiCount; uint32_t cultures,factions;
 int32_t startingMoney,startingFleet,aiDifficulty;
 int32_t plantFertility,mineralFertility;
 int32_t worldSize;
} WSWorldSettings;
typedef struct WSPlanIsland {
 uint32_t id,x,y,width,height,templateIndex,cropMask,mineralMask,cultures,climate;
} WSPlanIsland;
/* Read-only diagnostics retain the exact menu preview across staging/commit.
 * State:0 absent,1 ready,2 staged,3 native commit completed,4 cancelled/failed. */
typedef struct WSPreviewSnapshot {
 uint32_t size,state,seed,count;
 WSWorldSettings settings;
 WSPlanIsland islands[128];
} WSPreviewSnapshot;
__declspec(dllexport) int WorldSettingsBuildPlan(const WSWorldSettings*,uint32_t,char*,uint32_t);
__declspec(dllexport) int WorldSettingsPlanCount(void);
__declspec(dllexport) int WorldSettingsPlanIsland(uint32_t,WSPlanIsland*);
__declspec(dllexport) int WorldSettingsStageScene(const WSWorldSettings*,const char*,uint32_t,char*,uint32_t,char*,uint32_t);
__declspec(dllexport) int WorldSettingsStagePreviewScene(const WSWorldSettings*,const char*,uint32_t,const WSPlanIsland*,uint32_t,char*,uint32_t,char*,uint32_t);
__declspec(dllexport) uint32_t WorldSettingsPreviewSnapshotSize(void);
__declspec(dllexport) uint32_t __stdcall WorldSettingsCopyPreviewSnapshot(void*);
__declspec(dllexport) const char *WorldSettingsPendingPath(void);
__declspec(dllexport) int WorldSettingsPrepareScene(void*,void*);
__declspec(dllexport) int WorldSettingsIsActive(void);
__declspec(dllexport) int WorldSettingsValidateScene(void*,char*,uint32_t);
__declspec(dllexport) void WorldSettingsFinishAttempt(int);
#endif
