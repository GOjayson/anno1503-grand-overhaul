#ifndef WORLD_SETTINGS_AI_LOADER_H
#define WORLD_SETTINGS_AI_LOADER_H
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
int WorldSettingsConfigureAIExperiment(const char *copyRoot, const char *sourceRoot);
void WorldSettingsSetAILoaderHookReady(int ready);
int WorldSettingsAIExperimentConfigured(void);
HMODULE WorldSettingsLoadedAIModule(void);
__declspec(dllexport) HMODULE WINAPI WorldSettingsLoadAiModule(const char *nativePath);
__declspec(dllexport) DWORD WINAPI WorldSettingsCopyAILoaderError(void *buffer);
#endif
