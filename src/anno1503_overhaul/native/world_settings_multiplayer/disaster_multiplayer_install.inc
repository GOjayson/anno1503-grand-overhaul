/* The optional multiplayer runtime installs only the eight disaster calls
 * after checking the exact locally derived World image and every preimage. */
extern int WorldSettingsConfigureMultiplayerDisasters(const unsigned char *);

enum { WS_MP_DISASTER_HOOKS = 8 };
static WSInstalledBlob wsMpDisasterBlob;
static int wsMpDisasterInstalled;

static int wsInstallMultiplayerDisasters(HMODULE self)
{
    /* These entries were appended together by apply_disaster_calls. Their
     * offsets address the same assembler blob and native unwind metadata. */
    enum { FIRST_HOOK = 8, FIRST_FUNCTION = 8, FIRST_IMPORT = 7 };
    const WSBlob plan = {
        L"AnnoWelt.dll", {0}, world_policy_code, sizeof world_policy_code, NULL, 0,
        world_policy_imports + FIRST_IMPORT, WS_MP_DISASTER_HOOKS,
        world_policy_functions + FIRST_FUNCTION, WS_MP_DISASTER_HOOKS,
        world_policy_hooks + FIRST_HOOK, WS_MP_DISASTER_HOOKS,
    };
    WSBlob pinnedPlan = plan;
    memcpy(pinnedPlan.sha256, wsMpDisasterWorldSha, sizeof pinnedPlan.sha256);
    WSPatch patches[WS_MP_DISASTER_HOOKS] = {0};
    WSPage pages[WS_MP_DISASTER_HOOKS] = {0};
    WSThread threads[WS_MAX_THREADS] = {0};
    uint32_t patchCount = 0, pageCount = 0, threadCount = 0;
    int applied = 0;
    HMODULE pinned;
    SYSTEM_INFO system;
    GetSystemInfo(&system);
    if (wsPrepareBlobFromPlan(&pinnedPlan, &wsMpDisasterBlob, self, patches, &patchCount) &&
        patchCount == WS_MP_DISASTER_HOOKS &&
        GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_PIN,
                          (LPCWSTR)(uintptr_t)self, &pinned) &&
        wsGroupPages(patches, patchCount, pages, &pageCount, system.dwPageSize) &&
        wsSuspendThreads(threads, &threadCount, patches, patchCount))
        applied = wsApplyPatches(patches, patchCount, pages, pageCount);
    wsResumeThreads(threads, threadCount);
    if (!applied) {
        if (wsMpDisasterBlob.registered && !RtlDeleteFunctionTable(wsMpDisasterBlob.functions))
            return -1;
        wsMpDisasterBlob.registered = 0;
        if (wsMpDisasterBlob.allocation && !VirtualFree(wsMpDisasterBlob.allocation, 0, MEM_RELEASE))
            return -1;
        memset(&wsMpDisasterBlob, 0, sizeof wsMpDisasterBlob);
    }
    return applied;
}

__declspec(dllexport) BOOL WINAPI WorldSettingsPrepareMultiplayerDisasters(const unsigned char *policy)
{
    if (!policy)
        return FALSE;
    AcquireSRWLockExclusive(&wsInstallLock);
    if (!wsInstallState && !wsMpDisasterInstalled) {
        HMODULE self;
        if (GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                              (LPCWSTR)(uintptr_t)&WorldSettingsPrepareMultiplayerDisasters, &self))
            wsMpDisasterInstalled = wsInstallMultiplayerDisasters(self);
    }
    BOOL ready = wsMpDisasterInstalled == 1 && WorldSettingsConfigureMultiplayerDisasters(policy);
    ReleaseSRWLockExclusive(&wsInstallLock);
    return ready;
}

__declspec(dllexport) void WINAPI WorldSettingsClearMultiplayerDisasters(void)
{
    WorldSettingsConfigureMultiplayerDisasters(NULL);
}
