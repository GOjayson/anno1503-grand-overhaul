#ifndef ANNO_WORLD_BACKEND_H
#define ANNO_WORLD_BACKEND_H
#include <stdint.h>
typedef struct WSWorldSettings {
 uint32_t size; int32_t difficulty,islandSize,islandCount,spacing,aiCount; uint32_t cultures;
} WSWorldSettings;
typedef struct WSPlanIsland {
 uint32_t id,x,y,width,height,templateIndex,cropMask,mineralMask,cultures,climate;
} WSPlanIsland;
__declspec(dllexport) int WorldSettingsBuildPlan(const WSWorldSettings*,uint32_t,char*,uint32_t);
__declspec(dllexport) int WorldSettingsPlanCount(void);
__declspec(dllexport) int WorldSettingsPlanIsland(uint32_t,WSPlanIsland*);
__declspec(dllexport) int WorldSettingsStageScene(const WSWorldSettings*,const char*,uint32_t,char*,uint32_t,char*,uint32_t);
__declspec(dllexport) const char *WorldSettingsPendingPath(void);
__declspec(dllexport) int WorldSettingsPrepareScene(void*,void*);
__declspec(dllexport) int WorldSettingsIsActive(void);
__declspec(dllexport) int WorldSettingsValidateScene(void*,char*,uint32_t);
__declspec(dllexport) void WorldSettingsFinishAttempt(int);
#endif
