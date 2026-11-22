/* Opt-in subset of the reviewed native hooks. No simulation properties,
 * scene factories, network commands, or save callbacks are replaced here. */
extern int WorldSettingsSetMultiplayerVisibility(uint32_t policy);

enum { WS_MP_DRAW_POINTER_COUNT = 7, WS_MP_DRAW_CALL_COUNT = 9, WS_MP_BRIDGE_SIZE = 24 };
#ifdef WS_MP_PEACEFUL_AI
static const WSVisibilityHook wsMpPeacefulDiplomacy = {
    L"AnnoWelt.dll", 0xff860u, 0xdf460u, "WorldSettingsMultiplayerPeacefulDiplomacy",
};
enum { WS_MP_POINTER_COUNT = WS_MP_DRAW_POINTER_COUNT + 1 };
#else
enum { WS_MP_POINTER_COUNT = WS_MP_DRAW_POINTER_COUNT };
#endif
enum { WS_MP_FRAME, WS_MP_WORLD, WS_MP_DISPLAY, WS_MP_MODULE_COUNT };
static const uint32_t wsMpDrawCalls[WS_MP_DRAW_CALL_COUNT] = {0, 1, 2, 3, 4, 5, 6, 7, 12};
enum { WS_MP_RELOAD_NETWORK_ARGUMENT = 2 };
static const WSVisibilityCall wsMpReloadComplete = {
    L"AnnoFrame.dll", 0x76d8au, 5, {0xb8,1,0,0,0},
    "WorldSettingsMultiplayerFinishReload", 1, WS_MP_RELOAD_NETWORK_ARGUMENT,
};
/* At this successful reload tail, RBX still holds the native network client.
 * The following stock stores use only RBX and R14D. Supply RCX and return 1. */
static const unsigned char wsMpReloadLeaf[16] = {
    0x48,0x89,0xd9,0xff,0x25,7,0,0,0,0x90,0x90,0x90,0x90,0x90,0x90,0x90,
};
static const WSVisibilityCall wsMpActivityCalls[] = {
    {L"AnnoWelt.dll", 0xcac9cu, 5, {0xe8,0x5f,0xe7,0xff,0xff}, "WorldSettingsVisibilityProjectActivityTiles", 1, 0},
    {L"AnnoWelt.dll", 0xcc3eeu, 5, {0xe8,0x0d,0xd0,0xff,0xff}, "WorldSettingsVisibilityProjectActivityTiles", 1, 0},
    {L"AnnoWelt.dll", 0xd2992u, 6, {0xff,0x90,0xf0,0,0,0}, "WorldSettingsVisibilityActivityMinimapProperty", 1, 0},
};
typedef struct WSMultiplayerActivityBranch {
    uint32_t rva, length, leafLength;
    unsigned char before[11], leaf[WS_MP_BRIDGE_SIZE];
} WSMultiplayerActivityBranch;
static const WSMultiplayerActivityBranch wsMpActivityBranches[] = {
    /* C9400 saved its fourth byte argument at [rbp+0x168]. The native kind-5
     * construction layer stays in use. In its per-cell selection test,
     * compare the marked false value exactly as stock zero. */
    {0xc96ceu, 7, 17, {0x80,0xbd,0x68,1,0,0,0},
     {0x80,0xbd,0x68,1,0,0,0x80, 0x74,7, 0x80,0xbd,0x68,1,0,0,0, 0xc3}},
    /* In the branch where stock selects a live tile over the construction
     * layer, clear its decoded hidden bit in R15D before the stock JNE. */
    {0xc9707u, 7, 20, {0x41,0xc1,0xef,0x1f,0x45,0x85,0xff},
     {0x41,0xc1,0xef,0x1f, 0x80,0xbd,0x68,1,0,0,0x80, 0x72,3,
      0x45,0x33,0xff, 0x45,0x85,0xff, 0xc3}},
    /* For live rows without a construction layer, both marked values leave
     * the signed branch open. Neither live branch writes the tile word. */
    {0xc9a80u, 5, 15, {0x83,0x7c,0x3b,2,0},
     {0x80,0xbd,0x68,1,0,0,0x80, 0x73,5, 0x83,0x7c,0x3b,2,0, 0xc3}},
};
enum {
    WS_MP_ACTIVITY_CALL_COUNT = sizeof wsMpActivityCalls / sizeof wsMpActivityCalls[0],
    WS_MP_ACTIVITY_BRANCH_COUNT = sizeof wsMpActivityBranches / sizeof wsMpActivityBranches[0],
    WS_MP_RELOAD_CALL_INDEX = WS_MP_DRAW_CALL_COUNT + WS_MP_ACTIVITY_CALL_COUNT + WS_MP_ACTIVITY_BRANCH_COUNT,
    WS_MP_CALL_COUNT = WS_MP_RELOAD_CALL_INDEX + 1,
};
static int wsMpInstalled;

static int wsMpDrawPinModules(HMODULE modules[WS_MP_MODULE_COUNT], uint32_t sizes[WS_MP_MODULE_COUNT])
{
    static const wchar_t *const names[] = {L"AnnoFrame.dll", L"AnnoWelt.dll", L"AnnoDisplay.dll"};
    for (uint32_t i = 0; i < WS_MP_MODULE_COUNT; ++i) {
        modules[i] = GetModuleHandleW(names[i]);
        if (!modules[i] || !wsModuleImage(modules[i], &sizes[i]))
            return 0;
    }
    if (!wsHashModule(modules[WS_MP_FRAME], wsMpFrameSha) ||
        !wsHashModule(modules[WS_MP_DISPLAY], wsMpDisplaySha))
        return 0;
#ifdef WS_MP_HAS_SCENE_PIN
    HMODULE scene = GetModuleHandleW(L"AnnoScene.dll");
    uint32_t sceneSize;
    if (!scene || !wsModuleImage(scene, &sceneSize) || !wsHashModule(scene, wsMpSceneSha))
        return 0;
#endif

    /* A combined multiplayer build can pin a locally derived World image.
     * The single-player loader keeps its independent native profile pins. */
    for (uint32_t i = 0; i < sizeof wsVisibilityModulePins / sizeof wsVisibilityModulePins[0]; ++i) {
        const WSVisibilityModulePin *pin = &wsVisibilityModulePins[i];
        const int isWorld = !wcscmp(pin->name, L"AnnoWelt.dll");
        if (!isWorld && wcscmp(pin->name, L"AnnoGame.dll"))
            continue;
        const unsigned char *expected = pin->sha256;
#ifdef WS_MP_HAS_WORLD_PIN
        if (isWorld)
            expected = wsMpWorldSha;
#endif
        HMODULE loaded = GetModuleHandleW(pin->name);
        uint32_t size;
        if (!loaded || !wsModuleImage(loaded, &size) || !wsHashModule(loaded, expected))
            return 0;
    }
    return 1;
}

static int wsMpDrawPointer(HMODULE self, HMODULE module, uint32_t size,
    const WSVisibilityHook *entry, WSPatch *patch)
{
    if (!wsSpan(entry->slot, 8u, size) || !wsSpan(entry->target, 1u, size))
        return 0;
    uintptr_t original = (uintptr_t)module + entry->target;
    uintptr_t replacement = (uintptr_t)GetProcAddress(self, entry->exportName);
    unsigned char *site = (unsigned char *)module + entry->slot;
    if (!replacement || !wsReadable(site, 8u) || memcmp(site, &original, 8u))
        return 0;
    patch->address = site;
    patch->length = 8u;
    memcpy(patch->before, &original, 8u);
    memcpy(patch->after, &replacement, 8u);
    return 1;
}

static int wsMpCallSite(HMODULE module, uint32_t size, uint32_t rva, uint32_t length,
    const unsigned char *before, const unsigned char *bridge, WSPatch *patch)
{
    if (!wsSpan(rva, length, size) || length < 5u || length > sizeof patch->before)
        return 0;
    unsigned char *site = (unsigned char *)module + rva;
    int64_t distance = (int64_t)(uintptr_t)bridge - (int64_t)(uintptr_t)(site + 5);
    if (distance < INT32_MIN || distance > INT32_MAX ||
        !wsReadable(site, length) || memcmp(site, before, length))
        return 0;
    patch->address = site;
    patch->length = length;
    memcpy(patch->before, before, length);
    memset(patch->after, 0x90, length);
    patch->after[0] = 0xe8;
    int32_t relative = (int32_t)distance;
    memcpy(patch->after + 1, &relative, sizeof relative);
    return 1;
}

static int wsMpDrawCall(HMODULE self, HMODULE module, uint32_t size,
    const WSVisibilityCall *entry, unsigned char *bridge, WSPatch *patch)
{
    uintptr_t replacement = (uintptr_t)GetProcAddress(self, entry->exportName);
    if (!entry->call || !replacement ||
        !wsMpCallSite(module, size, entry->rva, entry->length, entry->before, bridge, patch))
        return 0;
    /* Tail-only leaves preserve the stack. The contextual leaves supply
     * the exact native register used by each reviewed call. */
    size_t targetOffset = entry->contextArgument ? 16u : 8u;
    const unsigned char *leaf = entry->contextArgument == WS_MP_RELOAD_NETWORK_ARGUMENT ? wsMpReloadLeaf :
                                entry->contextArgument ? wsVisibilityContextLeaf : wsVisibilityLeaf;
    memcpy(bridge, leaf, targetOffset);
    memcpy(bridge + targetOffset, &replacement, 8u);
    return 1;
}

static int wsMpDrawInstall(HMODULE self)
{
    enum { PATCHES = WS_MP_POINTER_COUNT + WS_MP_CALL_COUNT, BRIDGES = WS_MP_CALL_COUNT * WS_MP_BRIDGE_SIZE };
    HMODULE modules[WS_MP_MODULE_COUNT] = {0};
    uint32_t sizes[WS_MP_MODULE_COUNT] = {0};
    WSPatch patches[PATCHES] = {0};
    WSPage pages[PATCHES] = {0};
    WSThread threads[WS_MAX_THREADS] = {0};
    uint32_t pageCount = 0, threadCount = 0;
    unsigned char *bridges[2] = {0};
    int applied = 0;

    if (!wsMpDrawPinModules(modules, sizes))
        return 0;
    for (uint32_t i = 0; i < WS_MP_DRAW_POINTER_COUNT; ++i) {
        const WSVisibilityHook *entry = &wsVisibilityHookPlan[i];
        uint32_t owner = !wcscmp(entry->module, L"AnnoWelt.dll") ? WS_MP_WORLD : WS_MP_DISPLAY;
        if (!wsMpDrawPointer(self, modules[owner], sizes[owner], entry, &patches[i]))
            return 0;
    }
#ifdef WS_MP_PEACEFUL_AI
    if (!wsMpDrawPointer(self, modules[WS_MP_WORLD], sizes[WS_MP_WORLD], &wsMpPeacefulDiplomacy,
        &patches[WS_MP_DRAW_POINTER_COUNT]))
        return 0;
#endif
    for (uint32_t i = 0; i < WS_MP_DRAW_CALL_COUNT + WS_MP_ACTIVITY_CALL_COUNT; ++i) {
        const WSVisibilityCall *entry = i < WS_MP_DRAW_CALL_COUNT ? &wsVisibilityCallPlan[wsMpDrawCalls[i]] :
            &wsMpActivityCalls[i - WS_MP_DRAW_CALL_COUNT];
        uint32_t owner = !wcscmp(entry->module, L"AnnoWelt.dll") ? WS_MP_WORLD : WS_MP_FRAME;
        if (!bridges[owner])
            bridges[owner] = wsAllocateNear(modules[owner], sizes[owner], BRIDGES);
        if (!bridges[owner] || !wsMpDrawCall(self, modules[owner], sizes[owner], entry,
            bridges[owner] + i * WS_MP_BRIDGE_SIZE, &patches[WS_MP_POINTER_COUNT + i]))
            goto done;
    }
    for (uint32_t i = 0; i < WS_MP_ACTIVITY_BRANCH_COUNT; ++i) {
        const WSMultiplayerActivityBranch *entry = &wsMpActivityBranches[i];
        const uint32_t index = WS_MP_DRAW_CALL_COUNT + WS_MP_ACTIVITY_CALL_COUNT + i;
        unsigned char *bridge = bridges[WS_MP_WORLD] + index * WS_MP_BRIDGE_SIZE;
        if (!wsMpCallSite(modules[WS_MP_WORLD], sizes[WS_MP_WORLD], entry->rva, entry->length, entry->before,
            bridge, &patches[WS_MP_POINTER_COUNT + index]))
            goto done;
        memcpy(bridge, entry->leaf, entry->leafLength);
    }
    if (!wsMpDrawCall(self, modules[WS_MP_FRAME], sizes[WS_MP_FRAME], &wsMpReloadComplete,
        bridges[WS_MP_FRAME] + WS_MP_RELOAD_CALL_INDEX * WS_MP_BRIDGE_SIZE,
        &patches[WS_MP_POINTER_COUNT + WS_MP_RELOAD_CALL_INDEX]))
        goto done;
    for (uint32_t i = 0; i < 2u; ++i) {
        DWORD prior;
        if (!bridges[i] || !VirtualProtect(bridges[i], BRIDGES, PAGE_EXECUTE_READ, &prior) ||
            !FlushInstructionCache(GetCurrentProcess(), bridges[i], BRIDGES))
            goto done;
    }

    /* Pin this DLL for the installed process lifetime before releasing any
     * patched call site. Rollback may also require retaining its callbacks. */
    HMODULE pinned;
    if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_PIN,
        (LPCWSTR)(uintptr_t)self, &pinned))
        goto done;
    SYSTEM_INFO system;
    GetSystemInfo(&system);
    if (wsGroupPages(patches, PATCHES, pages, &pageCount, system.dwPageSize) &&
        wsSuspendThreads(threads, &threadCount, patches, PATCHES))
        applied = wsApplyPatches(patches, PATCHES, pages, pageCount);
    wsResumeThreads(threads, threadCount);

done:
    if (applied == 0) {
        for (uint32_t i = 0; i < 2u; ++i)
            if (bridges[i]) VirtualFree(bridges[i], 0, MEM_RELEASE);
    }
    return applied;
}

__declspec(dllexport) BOOL WINAPI WorldSettingsEnableMultiplayerVisibility(uint32_t mapMode, uint32_t activityMode)
{
    if (mapMode > 2u || activityMode > 1u)
        return FALSE;
    uint32_t policy = (1u + mapMode + 3u * activityMode) << 12u;
    AcquireSRWLockExclusive(&wsInstallLock);
    if (!wsInstallState && !wsMpInstalled) {
        HMODULE self = NULL;
        if (GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
            (LPCWSTR)(uintptr_t)&WorldSettingsEnableMultiplayerVisibility, &self))
            wsMpInstalled = wsMpDrawInstall(self);
    }
    BOOL enabled = wsMpInstalled == 1 && WorldSettingsSetMultiplayerVisibility(policy);
    ReleaseSRWLockExclusive(&wsInstallLock);
    return enabled;
}
