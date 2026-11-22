/* The optional scoped policy is deterministic on every world copy. It never
 * changes the stock AI controllers, relation tables, or request counters. */
static int wsMpDenyNewWar(void *world, uint32_t relation, uint32_t state, void *source, void *target)
{
    if (relation != 2u || state != 3u || !wsMultiplayerWorldWithheld(world))
        return 0;
    unsigned char *module = (unsigned char *)WS_CERT_MODULE("AnnoWelt.dll");
    unsigned char marker[8];
    if (!module || wsCertPointer(world, 0) != module + 0xff650u ||
        !wsCertRead((unsigned char *)world + 0x6e4cu, marker, sizeof marker) || memcmp(marker, "WSMPAI0!", sizeof marker))
        return 0;

    uint16_t playerKind;
    uint32_t sourceId, targetId;
    if (source == target || wsCertPointer(source, 0) != module + 0xfabe0u ||
        wsCertPointer(target, 0) != module + 0xfabe0u ||
        wsCertPointer(source, 0x10u) != world || wsCertPointer(target, 0x10u) != world ||
        !wsCertRead((unsigned char *)source + 0x9cu, &playerKind, sizeof playerKind) || playerKind != 12u ||
        !wsCertRead((unsigned char *)source + 8u, &sourceId, sizeof sourceId) || sourceId >= 32u ||
        !wsCertRead((unsigned char *)target + 8u, &targetId, sizeof targetId) || targetId >= 32u)
        return 0;
    void *table = wsCertPointer(world, 0x210u);
    if (wsCertPointer(table, 0) != module + 0xfdbc0u ||
        wsCertPointer(table, 8u + sourceId * sizeof(void *)) != source ||
        wsCertPointer(table, 8u + targetId * sizeof(void *)) != target)
        return 0;

    unsigned char *controller = wsCertPointer(source, 0x18u);
    const unsigned char *mainAI = (const unsigned char *)WS_CERT_MODULE("CompLogic.dll");
    const unsigned char *classicAI = (const unsigned char *)WS_CERT_MODULE("CompLogicClassic.dll");
    void *controllerType = wsCertPointer(controller, 0);
    uint32_t controllerKind, disabled, suspended;
    uint16_t controllerId;
    if ((!mainAI || controllerType != mainAI + 0x88128u) && (!classicAI || controllerType != classicAI + 0x84fc8u))
        return 0;
    if (wsCertPointer(controller, 8u) != world ||
        !wsCertRead(controller + 0xa4cu, &controllerKind, sizeof controllerKind) || controllerKind != 12u ||
        !wsCertRead(controller + 0xa64u, &controllerId, sizeof controllerId) || controllerId != sourceId ||
        !wsCertRead(controller + 0xab0u, &disabled, sizeof disabled) || disabled ||
        !wsCertRead(controller + 0xab4u, &suspended, sizeof suspended) || suspended)
        return 0;

    /* The stock relation-2 getter reads this byte for the exact target ID.
     * Existing reciprocal wars and their updates stay on the native path. */
    unsigned char existing;
    return wsCertRead((unsigned char *)source + 0x1dau + targetId * 6u, &existing, sizeof existing) && !existing;
}

typedef uintptr_t (__cdecl *WSMpNativeDiplomacy)(void *, uint32_t, uint32_t, void *, void *);
#ifndef WS_MP_NATIVE_DIPLOMACY
#define WS_MP_NATIVE_DIPLOMACY(module) ((WSMpNativeDiplomacy)((module) + 0xdf460u))
#endif

__declspec(dllexport) uintptr_t __cdecl WorldSettingsMultiplayerPeacefulDiplomacy(
    void *world, uint32_t relation, uint32_t state, void *source, void *target)
{
    unsigned char *module = (unsigned char *)WS_CERT_MODULE("AnnoWelt.dll");
    if (!module || wsMpDenyNewWar(world, relation, state, source, target))
        return 0;
    return WS_MP_NATIVE_DIPLOMACY(module)(world, relation, state, source, target);
}
