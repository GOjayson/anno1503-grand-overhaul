#ifndef WS_PRIVATE_AI_H
#define WS_PRIVATE_AI_H
#include <stdint.h>
#include "world_diplomacy.h"
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
/* Private experiment, not a claim of the engine maximum or Food gameplay. */
__declspec(dllexport) int WorldSettingsBindStockAIProfiles(void*,int32_t,int32_t,char*,uint32_t);
/* approvedAI must be the exact payload module verified by the private loader.
 * This is called AFTER Frame55330 applies profiles, never by early factory
 * validation. Reads only; it does not resume or suspend an opponent. */
__declspec(dllexport) int WorldSettingsCheckAIControllers(void*,int32_t,void*,char*,uint32_t);
void WorldSettingsExpectAIProfiles(int32_t,uint32_t,int32_t);
__declspec(dllexport) int WorldSettingsCheckSpecialControllers(void*,uint32_t,void*,char*,uint32_t);
void WorldSettingsAIProfileAttemptFinished(int);
__declspec(dllexport) int WorldSettingsAfterProfiles(void*);
__declspec(dllexport) unsigned long WorldSettingsCopyAIProfileError(void*);
__declspec(dllexport) DWORD WINAPI WorldSettingsAIProfileStatus(void*);
__declspec(dllexport) uint32_t __cdecl WorldSettingsBeginNativeWorldStart(void);
__declspec(dllexport) int __cdecl WorldSettingsEndNativeWorldStart(uint32_t,int);
__declspec(dllexport) int WorldSettingsBindAIProfileWorld(void*,char*,uint32_t);
#endif
