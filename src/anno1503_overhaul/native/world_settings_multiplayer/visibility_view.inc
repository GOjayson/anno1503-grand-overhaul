/* This state belongs only to the optional presentation adapter. Native
 * discovery, visibility flags, and checkpoints remain engine-owned. */
typedef struct WSMultiplayerVisibilitySelection {
    DWORD thread;
    uint32_t generation, policy;
    HWND window;
    void *frame, *network, *world, *player, *worldType, *pendingReload;
    uint32_t viewer, width, height;
    unsigned char worldGuid[16];
    int retired;
} WSMultiplayerVisibilitySelection;

static WSMultiplayerVisibilitySelection wsMultiplayerVisibility;
static volatile LONG wsMultiplayerVisibilityGeneration, wsMultiplayerVisibilityThread;
static volatile LONG64 wsMultiplayerDrawnView;
static void *volatile wsMultiplayerRenderWorld, *volatile wsMultiplayerRenderer;
static void *const wsMultiplayerPendingWorld = (void *)(uintptr_t)1u;

static void *wsMultiplayerWorldScope(void)
{
    return InterlockedCompareExchangePointer(&wsMultiplayerRenderWorld, NULL, NULL);
}

/* Publication is independent of the binding thread. A draw on another
 * thread cannot fall through while the selected World is awaiting proof. */
static int wsMultiplayerWorldWithheld(void *world)
{
    void *scope = wsMultiplayerWorldScope();
    return world && (scope == wsMultiplayerPendingWorld || scope == world);
}

static int wsMultiplayerUsesRenderer(void *renderer)
{
    return renderer && wsMultiplayerWorldScope() &&
        InterlockedCompareExchangePointer(&wsMultiplayerRenderer, NULL, NULL) == renderer;
}

static int wsMultiplayerWithholdsRenderTarget(const WSVisibilityWorld *view, void *renderer)
{
    if (view->multiplayerWithheld)
        return 1;
    return !view->multiplayerPlayer && wsMultiplayerUsesRenderer(renderer);
}

static void wsMultiplayerRememberRenderer(const WSVisibilityWorld *view, void *renderer)
{
    if ((!view->multiplayerPlayer && !view->multiplayerWithheld) || wsVisibilityDrawContext ||
        (DWORD)InterlockedCompareExchange(&wsMultiplayerVisibilityThread, 0, 0) != GetCurrentThreadId())
        return;
    unsigned char *display = (unsigned char *)WS_CERT_MODULE("AnnoDisplay.dll");
    if (display && wsCertPointer(renderer, 0) == display + 0xf63740u)
        InterlockedExchangePointer(&wsMultiplayerRenderer, renderer);
}

static int wsMultiplayerUnknownActorWithheld(void *renderer)
{
    return wsMultiplayerWorldScope() == wsMultiplayerPendingWorld || wsMultiplayerUsesRenderer(renderer);
}

/* A single read is sufficient because the draw publishes all fields at once.
 * Low bytes are seat + 1, map mode, discovery count, and activity mode.
 * The high DWORD identifies the activation. Zero means no completed draw. */
__declspec(dllexport) uint64_t WINAPI WorldSettingsMultiplayerVisibilityView(void)
{
    return (uint64_t)wsMultiplayerDrawnView;
}

static void wsMultiplayerVisibilityDrawn(const WSVisibilityDrawContext *context)
{
    const WSVisibilityWorld *view = &context->view;
    if (!view->multiplayerPlayer || wsMultiplayerVisibility.retired ||
        view->multiplayerGeneration != wsMultiplayerVisibility.generation)
        return;
    uint32_t known = 0;
    for (uint32_t i = 0; i < WS_VISIBILITY_ISLAND_LIMIT; ++i)
        if (context->present[i] && (context->islands[i].discovered & (1u << view->viewer)))
            ++known;
    uint64_t packed = ((uint64_t)view->multiplayerGeneration << 32) |
        ((uint64_t)view->enemy << 24) | ((uint64_t)known << 16) | ((uint64_t)view->map << 8) | (view->viewer + 1u);
    InterlockedExchange64(&wsMultiplayerDrawnView, (LONG64)packed);
}

int WorldSettingsSetMultiplayerVisibility(uint32_t policy)
{
    DWORD thread = GetCurrentThreadId();
    DWORD owner = (DWORD)InterlockedCompareExchange(&wsMultiplayerVisibilityThread, (LONG)thread, 0);
    if (owner && owner != thread)
        return 0;
    InterlockedExchangePointer(&wsMultiplayerRenderWorld, policy ? wsMultiplayerPendingWorld : NULL);
    InterlockedExchangePointer(&wsMultiplayerRenderer, NULL);
    InterlockedExchange64(&wsMultiplayerDrawnView, 0);
    InterlockedIncrement(&wsVisibilityMapGeneration);
    wsMultiplayerVisibility = (WSMultiplayerVisibilitySelection){
        .thread = thread,
        .generation = (uint32_t)InterlockedIncrement(&wsMultiplayerVisibilityGeneration),
        .policy = policy,
    };
    return 1;
}

__declspec(dllexport) void WINAPI WorldSettingsDisableMultiplayerVisibility(void)
{
    if ((DWORD)InterlockedCompareExchange(&wsMultiplayerVisibilityThread, 0, 0) == GetCurrentThreadId())
        WorldSettingsSetMultiplayerVisibility(0);
}

typedef struct WSMultiplayerVisibilitySearch {
    WSVisibilityWorld *view;
    unsigned char *frameModule;
    HWND window;
    void *frame, *network, *player;
    uint32_t count;
} WSMultiplayerVisibilitySearch;

static BOOL CALLBACK wsMultiplayerVisibilityWindow(HWND window, LPARAM context)
{
    WSMultiplayerVisibilitySearch *search = (WSMultiplayerVisibilitySearch *)context;
    WSVisibilityWorld *view = search->view;
    if (GetWindowThreadProcessId(window, NULL) != wsMultiplayerVisibility.thread)
        return TRUE;
    void *frame = (void *)(uintptr_t)GetWindowLongPtrW(window, GWLP_USERDATA);
    void *vt = wsCertPointer(frame, 0);
    if (vt != search->frameModule + 0xa0ce8u && vt != search->frameModule + 0xa1788u)
        return TRUE;

    void *network = wsCertPointer(frame, 0x40u);
    void *player = wsCertPointer(frame, 0x48u);
    void *table = wsCertPointer(view->world, 0x210u);
    uint32_t id = UINT32_MAX;
    if (wsCertPointer(network, 0) != search->frameModule + 0xa7418u ||
        wsCertPointer(network, 0x18u) != frame ||
        wsCertPointer(player, 0) != view->module + 0xfabe0u ||
        wsCertPointer(player, 0x10u) != view->world ||
        !wsCertRead((unsigned char *)player + 8u, &id, sizeof id) ||
        id >= 16u || id != view->viewer ||
        wsCertPointer(table, 0) != view->module + 0xfdbc0u ||
        wsCertPointer(table, 8u + (size_t)id * 8u) != player)
        return TRUE;

    if (search->frame == frame)
        return TRUE;
    search->window = window;
    search->frame = frame;
    search->network = network;
    search->player = player;
    return ++search->count < 2u;
}

static BOOL CALLBACK wsMultiplayerVisibilityTopWindow(HWND window, LPARAM context)
{
    if (!wsMultiplayerVisibilityWindow(window, context))
        return FALSE;
    EnumChildWindows(window, wsMultiplayerVisibilityWindow, context);
    return ((WSMultiplayerVisibilitySearch *)context)->count < 2u;
}

static void wsMultiplayerRetireVisibility(WSMultiplayerVisibilitySelection *selected)
{
    selected->retired = 1;
    InterlockedExchangePointer(&wsMultiplayerRenderWorld, NULL);
    InterlockedExchangePointer(&wsMultiplayerRenderer, NULL);
    InterlockedExchange64(&wsMultiplayerDrawnView, 0);
}

/* AnnoFrame calls this once after native reload has restored the scene,
 * network World, and local player. Keep its stock successful return. */
__declspec(dllexport) int32_t __cdecl WorldSettingsMultiplayerFinishReload(void *network)
{
    WSMultiplayerVisibilitySelection *selected = &wsMultiplayerVisibility;
    if (GetCurrentThreadId() != selected->thread || !selected->policy || selected->retired ||
        !selected->window || !selected->player || !network || selected->network != network)
        return 1;
    unsigned char *frameModule = (unsigned char *)WS_CERT_MODULE("AnnoFrame.dll");
    if (!frameModule || wsCertPointer(network, 0) != frameModule + 0xa7418u ||
        (void *)(uintptr_t)GetWindowLongPtrW(selected->window, GWLP_USERDATA) != selected->frame ||
        wsCertPointer(selected->frame, 0x40u) != network || wsCertPointer(network, 0x18u) != selected->frame)
        return 1;

    void *world = wsCertPointer(network, 0x10u);
    if (world) {
        selected->pendingReload = world;
        InterlockedExchangePointer(&wsMultiplayerRenderWorld, world);
        InterlockedExchange64(&wsMultiplayerDrawnView, 0);
    }
    return 1;
}

static int wsVisibilityIslandRead(const WSVisibilityWorld *, uint32_t, WSVisibilityIsland *);

/* A fresh Fully explored scenario seeds all eligible human seats. After a
 * reload, verify the local seat's native island discovery on its own. */
static int wsMultiplayerFullyExploredLoaded(const WSVisibilityWorld *view, int reloaded)
{
    const uint16_t humanSeats = (1u << 0) | (1u << 7) | (1u << 8) | (1u << 9);
    if (!(humanSeats & (1u << view->viewer)))
        return 0;
    const uint16_t required = reloaded ? (uint16_t)(1u << view->viewer) : humanSeats;
    uint32_t count = 0;
    for (uint32_t id = 0; id < WS_VISIBILITY_ISLAND_LIMIT; ++id) {
        if (!wsCertPointer(view->world, 0x6640u + (size_t)id * 8u))
            continue;
        WSVisibilityIsland island;
        if (!wsVisibilityIslandRead(view, id, &island) || (island.discovered & required) != required)
            return 0;
        ++count;
    }
    return count != 0;
}

static void wsMultiplayerBindVisibility(WSVisibilityWorld *view)
{
    WSMultiplayerVisibilitySelection *selected = &wsMultiplayerVisibility;
    if (!wsMultiplayerWorldScope())
        return;
    int scoped = wsMultiplayerWorldWithheld(view->world);
    if (scoped) {
        view->multiplayerWithheld = 1;
        view->marked = -1;
    }
    if ((DWORD)InterlockedCompareExchange(&wsMultiplayerVisibilityThread, 0, 0) != GetCurrentThreadId() ||
        !selected->policy || selected->retired)
        return;
    const int reload = selected->pendingReload == view->world;
    if (selected->window && view->world != selected->world && !reload) {
        if ((void *)(uintptr_t)GetWindowLongPtrW(selected->window, GWLP_USERDATA) != selected->frame ||
            wsCertPointer(selected->frame, 0x40u) != selected->network ||
            wsCertPointer(selected->network, 0x18u) != selected->frame)
            wsMultiplayerRetireVisibility(selected);
        return;
    }
    if (!scoped)
        return;
    unsigned char *frame = (unsigned char *)WS_CERT_MODULE("AnnoFrame.dll");
    unsigned char guid[16];
    if (!frame || !wsCertRead(view->world + 0x6e4cu, guid, sizeof guid))
        return;

    WSMultiplayerVisibilitySearch search = {.view = view, .frameModule = frame};
    if (selected->window) {
        wsMultiplayerVisibilityWindow(selected->window, (LPARAM)&search);
        if (search.count != 1u || search.frame != selected->frame || search.network != selected->network ||
            view->viewer != selected->viewer || view->width != selected->width || view->height != selected->height ||
            wsCertPointer(view->world, 0) != selected->worldType || memcmp(guid, selected->worldGuid, sizeof guid) ||
            (!reload && search.player != selected->player)) {
            InterlockedExchange64(&wsMultiplayerDrawnView, 0);
            return;
        }
        if (reload) {
            int32_t mapMode;
            if (wsCertPointer(search.network, 0x10u) != view->world ||
                wsCertPointer(search.frame, 0x28u) != view->world ||
                wsVisibilityDecode(selected->policy, &mapMode, NULL) != 1 ||
                (mapMode == 2 && !wsMultiplayerFullyExploredLoaded(view, 1)))
                return;
            selected->world = view->world;
            selected->player = search.player;
            selected->pendingReload = NULL;
            selected->generation = (uint32_t)InterlockedIncrement(&wsMultiplayerVisibilityGeneration);
            InterlockedIncrement(&wsVisibilityMapGeneration);
        }
    } else {
        EnumThreadWindows(selected->thread, wsMultiplayerVisibilityTopWindow, (LPARAM)&search);
        if (search.count != 1u)
            return;
        int32_t mapMode;
        if (wsVisibilityDecode(selected->policy, &mapMode, NULL) != 1 ||
            (mapMode == 2 && !wsMultiplayerFullyExploredLoaded(view, 0)))
            return;
        selected->window = search.window;
        selected->frame = search.frame;
        selected->network = search.network;
        selected->world = view->world;
        selected->player = search.player;
        selected->worldType = wsCertPointer(view->world, 0);
        selected->viewer = view->viewer;
        selected->width = view->width;
        selected->height = view->height;
        memcpy(selected->worldGuid, guid, sizeof guid);
        InterlockedExchangePointer(&wsMultiplayerRenderWorld, view->world);
    }

    /* Flags below are a local value used by the existing renderer and chart
     * predicates. No value is stored back in World memory. */
    view->flags = (view->flags & ~WS_VISIBILITY_POLICY_MASK) | selected->policy;
    view->marked = wsVisibilityDecode(view->flags, &view->map, &view->enemy);
    view->multiplayerWithheld = 0;
    view->multiplayerPlayer = search.player;
    view->multiplayerGeneration = selected->generation;
}
