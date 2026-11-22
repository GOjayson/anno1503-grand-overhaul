/* Apply only the reviewed 173 geometry/rendering edits for a prepared
 * generated Huge multiplayer match. No SP factory or AI hooks are installed. */

static int wsMpHugeBytes(const WSPatch *patches, uint32_t count, int after)
{
    for (uint32_t i = 0; i < count; ++i) {
        const WSPatch *patch = &patches[i];
        if (memcmp(patch->address, after ? patch->after : patch->before, patch->length))
            return 0;
    }
    return 1;
}

static int wsMpHugeExecutableFrame(HMODULE frame)
{
    const uintptr_t helper = (uintptr_t)frame + 0x9d450u;
    const SIZE_T length = 0x90u;
    MEMORY_BASIC_INFORMATION region;
    if (VirtualQuery((const void *)helper, &region, sizeof region) != sizeof region ||
        region.AllocationBase != frame || region.State != MEM_COMMIT ||
        region.Protect & (PAGE_NOACCESS | PAGE_GUARD))
        return 0;
    const DWORD protection = region.Protect & 0xffu;
    return (protection == PAGE_EXECUTE_READ || protection == PAGE_EXECUTE_READWRITE ||
            protection == PAGE_EXECUTE_WRITECOPY) &&
           helper >= (uintptr_t)region.BaseAddress && length <= region.RegionSize &&
           helper - (uintptr_t)region.BaseAddress <= region.RegionSize - length;
}

/* Caller owns wsInstallLock. A live World must keep the allocation layout
 * under which it was constructed. This applies to publishing and restoring. */
static int wsMpHugeTransition(int restore)
{
    HMODULE modules[WS_MP_MODULE_COUNT] = {0};
    uint32_t sizes[WS_MP_MODULE_COUNT] = {0};
    WSPatch patches[WS_ENGINE_PATCH_COUNT] = {0};
    WSPage pages[WS_ENGINE_PATCH_COUNT] = {0};
    WSThread threads[WS_MAX_THREADS] = {0};
    uint32_t patchCount = 0, pageCount = 0, threadCount = 0;

    if (!wsMpDrawPinModules(modules, sizes) ||
        !wsMpHugeExecutableFrame(modules[WS_MP_FRAME]) ||
        !wsPrepareEngineTransition(patches, &patchCount, restore) ||
        patchCount != WS_ENGINE_PATCH_COUNT ||
        wsEngineModules[WS_ENGINE_MODULE_WORLD] != modules[WS_MP_WORLD] ||
        wsEngineModules[WS_ENGINE_MODULE_FRAME] != modules[WS_MP_FRAME])
        return restore ? -1 : 0;
    if (!wsEngineWorldAbsent())
        return 0;

    SYSTEM_INFO system;
    GetSystemInfo(&system);
    int result = 0;
    if (wsGroupPages(patches, patchCount, pages, &pageCount, system.dwPageSize) &&
        wsSuspendThreads(threads, &threadCount, patches, patchCount) &&
        wsEngineWorldAbsent()) {
        result = wsApplyPatches(patches, patchCount, pages, pageCount);
        if (result == 1 && !wsMpHugeBytes(patches, patchCount, 1))
            result = wsRestorePatches(patches, patchCount, pages, pageCount) ? 0 : -1;
        if (result == 0 && !wsMpHugeBytes(patches, patchCount, 0))
            result = -1;
    }
    wsResumeThreads(threads, threadCount);
    return result;
}

__declspec(dllexport) DWORD WINAPI WorldSettingsPrepareMultiplayerHugeWorld(void)
{
    AcquireSRWLockExclusive(&wsInstallLock);
    DWORD ready = 0;
    HMODULE self;
    if (!wsInstallState && !wsMpHugeState && wsMpInstalled >= 0 &&
        GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_PIN,
                           (LPCWSTR)(uintptr_t)&WorldSettingsPrepareMultiplayerHugeWorld, &self)) {
        wsMpHugeState = wsMpHugeTransition(0);
        if (wsMpHugeState == 1)
            ready = WS_ENGINE_PATCH_COUNT;
    }
    ReleaseSRWLockExclusive(&wsInstallLock);
    return ready;
}

__declspec(dllexport) BOOL WINAPI WorldSettingsClearMultiplayerHugeWorld(void)
{
    AcquireSRWLockExclusive(&wsInstallLock);
    if (wsMpHugeState == 1 && !wsInstallState) {
        const int result = wsMpHugeTransition(1);
        if (result == 1)
            wsMpHugeState = 0;
        else if (result < 0)
            wsMpHugeState = -1;
    }
    const BOOL cleared = wsMpHugeState == 0;
    ReleaseSRWLockExclusive(&wsInstallLock);
    return cleared;
}
