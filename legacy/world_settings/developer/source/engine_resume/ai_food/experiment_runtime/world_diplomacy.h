#ifndef WORLD_DIPLOMACY_H
#define WORLD_DIPLOMACY_H
#include <stdint.h>
/* 0 Peaceful, 1 Easy, 2 Medium, 3 Hard. Only a fresh generated world is bound. */
__declspec(dllexport) int WorldSettingsBindAIDiplomacy(void *world,int32_t expected,int32_t mode,void *approvedAI,char *error,uint32_t cap);
#endif
