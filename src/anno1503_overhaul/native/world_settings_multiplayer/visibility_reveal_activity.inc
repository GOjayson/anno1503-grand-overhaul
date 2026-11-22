/* Only the two reviewed render-cache producers and the minimap query call
 * these functions. A private producer argument conveys the render policy. */
#define WS_MP_REVEAL_ACTIVITY 0x80u

static int wsMultiplayerRevealActivity(void *world)
{
    WSMultiplayerVisibilitySelection *selected = &wsMultiplayerVisibility;
    int32_t enemy = 0;
    if (GetCurrentThreadId() != selected->thread || selected->retired ||
        wsVisibilityDecode(selected->policy, NULL, &enemy) != 1 || !enemy)
        return 0;
    void *scope = wsMultiplayerWorldScope();
    if (!selected->pendingReload && scope == world && selected->world == world && selected->player)
        return 1;
    if (scope != wsMultiplayerPendingWorld && selected->pendingReload != world)
        return 0;
    WSVisibilityWorld view;
    return wsVisibilityWorldRead(world, &view) && view.multiplayerPlayer && view.enemy;
}

typedef void (__cdecl *WSVisibilityNativeActivityTiles)(void *, const void *, uint32_t, uint32_t, void *);
typedef uint32_t (__cdecl *WSVisibilityNativeActivityProperty)(void *, uint32_t);
#ifndef WS_MP_NATIVE_ACTIVITY_TILES
#define WS_MP_NATIVE_ACTIVITY_TILES(module) ((WSVisibilityNativeActivityTiles)((module) + 0xc9400u))
#define WS_MP_NATIVE_ACTIVITY_PROPERTY(target) ((WSVisibilityNativeActivityProperty)(target))
#endif

__declspec(dllexport) void __cdecl WorldSettingsVisibilityProjectActivityTiles(
    void *world, const void *row, uint32_t quadrant, uint32_t flags, void *output)
{
    unsigned char *module = (unsigned char *)WS_CERT_MODULE("AnnoWelt.dll");
    if (!module)
        return;
    /* Retain the native Boolean for the construction layer's tile choice. */
    flags = flags != 0;
    if (wsMultiplayerRevealActivity(world))
        flags |= WS_MP_REVEAL_ACTIVITY;
    WS_MP_NATIVE_ACTIVITY_TILES(module)(world, row, quadrant, flags, output);
}

__declspec(dllexport) uint32_t __cdecl WorldSettingsVisibilityActivityMinimapProperty(void *world, uint32_t property)
{
    if (property == 5u && wsMultiplayerRevealActivity(world))
        return 0;
    void *target = wsCertPointer(wsCertPointer(world, 0), 0xf0u);
    return target ? WS_MP_NATIVE_ACTIVITY_PROPERTY(target)(world, property) : 1;
}
