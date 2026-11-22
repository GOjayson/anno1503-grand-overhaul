/* Opt-in co-op build only. Frame's ordered replay owns this state. */
enum {
    COOP_FIRST_ACTION = 0x80, COOP_LAST_ACTION = 0x86,
    COOP_NET_VTABLE = 0xa7418, COOP_GAME_VTABLE = 0xa1788,
    COOP_NATIVE_ID = 0xc6cc8,
    COOP_PLAYER_VTABLE = 0xfabe0, COOP_GROUP_TAB_VTABLE = 0xfb3b0,
    COOP_GROUP_VTABLE = 0xfccb0, COOP_ACTIVE_GROUP_VTABLE = 0xfaf80,
    COOP_WORLD_VTABLE = 0xff1d8, COOP_SERVER_WORLD_VTABLE = 0xff650,
    COOP_COMMAND_TABLE = 0x80c44, COOP_COMMAND_NEXT = 0x804a7,
    COOP_FIRST_STOCK_COMMAND = 0x64, COOP_LAST_STOCK_COMMAND = 0x98,
    COOP_PLAYER_ACTIVE = 0x30, COOP_PLAYER_CACHE = 0x398,
    COOP_PLAYER_CACHE_COUNT = 4, COOP_PLAYER_CACHE_KIND = 0x3f8,
    COOP_SELECTION_SERIAL = 0xb8, COOP_VIEWER = 0x1e4,
    COOP_UNINVOLVED_VIEWER = 31, COOP_GAME_WORLD = 0x28, COOP_GAME_ACTOR = 0x48,
    COOP_GUEST_GROUP = 29, COOP_STOCK_GROUP_COUNT = 30,
    COOP_GROUP_MEMBERS = 0x18, COOP_GROUP_MEMBER_SIZE = 0x20,
    COOP_GROUP_COUNT = 0x3d8, COOP_GROUP_ID = 0x469,
    COOP_GROUP_ROW_FLAGS = 0x1c, COOP_GROUP_ROW_ORDERS_UNIT = 2, COOP_UNIT_GROUP_ORDER = 0x14,
};

typedef struct {
    unsigned char *active;
    unsigned char *cache[COOP_PLAYER_CACHE_COUNT];
    uint32_t cache_kind;
    unsigned char serial;
} CoopSelection;

static _Thread_local struct {
    unsigned char *network, *world, *actor, *guest_group;
    CoopSelection local, remote;
    uint32_t viewer;
    unsigned int sender;
    bool dispatch, using_remote;
} coop_selection;

static unsigned char *coop_pointer(const unsigned char *object, size_t offset)
{
    return *(unsigned char *const *)(object + offset);
}

static void *coop_method(const unsigned char *object, size_t slot)
{
    return *(void *const *)(coop_pointer(object, 0) + slot);
}

static CoopSelection coop_read_selection(const unsigned char *actor)
{
    CoopSelection state;
    state.active = coop_pointer(actor, COOP_PLAYER_ACTIVE);
    memcpy(state.cache, actor + COOP_PLAYER_CACHE, sizeof state.cache);
    state.cache_kind = get32(actor + COOP_PLAYER_CACHE_KIND);
    state.serial = actor[COOP_SELECTION_SERIAL];
    return state;
}

static void coop_set_selection(unsigned char *actor, const CoopSelection *state)
{
    *(unsigned char **)(actor + COOP_PLAYER_ACTIVE) = state->active;
    memcpy(actor + COOP_PLAYER_CACHE, state->cache, sizeof state->cache);
    *(uint32_t *)(actor + COOP_PLAYER_CACHE_KIND) = state->cache_kind;
    actor[COOP_SELECTION_SERIAL] = state->serial;
}

static uint16_t coop_stamp_command(uint16_t opcode, uint16_t sender, bool enabled)
{
    if (enabled && opcode >= COOP_FIRST_ACTION && opcode <= COOP_LAST_ACTION && sender < 2)
        return opcode | (uint16_t)((sender + 1u) << 8u);
    return opcode;
}

__declspec(dllexport) unsigned int AnnoMenuCoopCopyCommand(unsigned char *destination, const unsigned char *payload,
                                                           unsigned int length)
{
    memcpy(destination, payload, length);
    /* The server node supplied this physical sender. Socket clients cannot
       supply a trusted marker through an ordinary command payload. */
    const uint16_t opcode = get16(payload - 8);
    const uint16_t sender = get16(payload - 4);
    if (opcode == get16(destination - 4) && length == get16(payload - 6)) {
        const uint16_t routed = coop_stamp_command(opcode, sender, menu_coop_active());
        destination[-3] = (unsigned char)(routed >> 8u);
    }
    return length;
}

static bool coop_group_backing(unsigned char *actor, const unsigned char *model)
{
    unsigned char *const table = coop_pointer(actor, 0x28);
    if (!table || coop_pointer(table, 0) != model + COOP_GROUP_TAB_VTABLE)
        return false;
    unsigned char *group = coop_pointer(table, 8 + COOP_GUEST_GROUP * sizeof(void *));
    if (group)
        return group == coop_selection.guest_group;

    typedef unsigned char *(*AllocateGroup)(unsigned char *, unsigned int, unsigned int);
    typedef int (*RegisterGroup)(unsigned char *, unsigned char *, unsigned int);
    typedef void (*SetGroup)(unsigned char *, unsigned int);
    const uint32_t previous_allocation = get32(table + 0xf8);
    group = ((AllocateGroup)coop_method(table, 0))(table, 0, 0);
    if (!group || coop_pointer(group, 0) != model + COOP_GROUP_VTABLE)
        return false;
    if (((RegisterGroup)coop_method(table, 8))(table, group, COOP_GUEST_GROUP) != COOP_GUEST_GROUP) {
        ((void (*)(void *))coop_method(group, 0x18))(group);
        return false;
    }
    *(uint32_t *)(table + 0xf8) = previous_allocation;
    *(unsigned char **)(group + 8) = actor;
    group[0x468] = 1;
    ((SetGroup)coop_method(group, 0x110))(group, COOP_GUEST_GROUP);
    coop_selection.guest_group = group;
    return true;
}

static unsigned int coop_command_actor(const unsigned char *record, unsigned int opcode)
{
    const uint16_t length = get16(record + 2);
    const unsigned char *payload = record + 4;
    if (opcode == 0x80)
        return length == 16 ? get16(payload + 2) : UINT32_MAX;
    if (opcode == 0x82)
        return length == 5 ? payload[0] : UINT32_MAX;
    if (opcode == 0x83)
        return length >= 4 && length % 4 == 0 ? get32(payload) : UINT32_MAX;
    if (length < 4 || length % 4 != 0)
        return UINT32_MAX;

    const unsigned int kind = payload[0];
    if (opcode == 0x81 && ((kind == 1 && length == 16) || (kind == 3 && length > 4) ||
                          (kind == 8 && length == 4)))
        return get16(payload + 2);
    if (opcode == 0x84 && (((kind == 0 || kind == 4 || kind == 11) && length == 12) ||
                          (kind == 1 && length == 20) || ((kind == 2 || kind == 3) && length >= 8)))
        return get16(payload + 2);
    if ((opcode == 0x85 || opcode == 0x86) && ((kind == 1 && length == 16) ||
            ((kind == 2 || kind == 3) && length > 4) || (kind == 4 && length == 8) ||
            (opcode == 0x85 && ((kind == 0 && length == 4) || (kind == 5 && length == 8)))))
        return get16(payload + 2);
    return UINT32_MAX;
}

static bool coop_group_owns_order(const unsigned char *action, unsigned int group)
{
    return get16(action) == COOP_UNIT_GROUP_ORDER && get32(action + 8) == group;
}

static void coop_reconcile_row(unsigned char *flags, const unsigned char *action, unsigned int group)
{
    if (!action || !coop_group_owns_order(action, group))
        *flags &= (unsigned char)~COOP_GROUP_ROW_ORDERS_UNIT;
}

static void coop_reconcile_group_orders(unsigned char *actor)
{
    /* A newer order may act on a unit also selected by another player. Its
       live action names the owning group. Stale rows may continue to display
       that unit but may no longer cancel or remap its action. */
    unsigned char *const table = coop_pointer(actor, 0x28);
    const unsigned char *const model = (const unsigned char *)GetModuleHandleW(L"AnnoWelt.dll");
    for (unsigned int index = 0; index < COOP_STOCK_GROUP_COUNT; ++index) {
        unsigned char *const group = coop_pointer(table, 8 + index * sizeof(void *));
        if (!group || coop_pointer(group, 0) != model + COOP_GROUP_VTABLE || group[COOP_GROUP_ID] != index)
            continue;
        const uint32_t members = get32(group + COOP_GROUP_COUNT);
        if (members > 30)
            continue;
        for (unsigned int j = 0; j < members; ++j) {
            unsigned char *const row = group + COOP_GROUP_MEMBERS + j * COOP_GROUP_MEMBER_SIZE;
            unsigned char *const unit = coop_pointer(row, 0);
            if (!unit || !(row[COOP_GROUP_ROW_FLAGS] & COOP_GROUP_ROW_ORDERS_UNIT))
                continue;
            const unsigned char *const action = ((unsigned char *(*)(void *))coop_method(unit, 0x230))(unit);
            coop_reconcile_row(row + COOP_GROUP_ROW_FLAGS, action, index);
        }
    }
}

static bool coop_begin_selection(unsigned char *frame, unsigned char *network, const unsigned char *record,
                                 unsigned int opcode, unsigned int sender)
{
    if (!network || coop_pointer(network, 0) != frame + COOP_NET_VTABLE || coop_selection.dispatch)
        return false;
    unsigned char *const game = coop_pointer(network, 0x18);
    unsigned char *const world = coop_pointer(network, 0x10);
    const unsigned char *model = (const unsigned char *)GetModuleHandleW(L"AnnoWelt.dll");
    if (!model || !game || !world || coop_pointer(game, 0) != frame + COOP_GAME_VTABLE ||
        coop_pointer(game, COOP_GAME_WORLD) != world ||
        (coop_pointer(world, 0) != model + COOP_WORLD_VTABLE &&
         coop_pointer(world, 0) != model + COOP_SERVER_WORLD_VTABLE))
        return false;
    unsigned char *const actor = coop_pointer(game, COOP_GAME_ACTOR);
    const uint32_t local = get32(frame + COOP_NATIVE_ID);
    if (!actor || coop_pointer(actor, 0) != model + COOP_PLAYER_VTABLE ||
        coop_pointer(actor, 0x10) != world || local > 1 ||
        get32(actor + 8) != coop_command_actor(record, opcode) ||
        (coop_selection.actor && (coop_selection.actor != actor || coop_selection.world != world)) ||
        !coop_group_backing(actor, model))
        return false;

    const unsigned char *const active = sender == local ? coop_pointer(actor, COOP_PLAYER_ACTIVE) :
        coop_selection.remote.active;
    if (!active && (opcode == 0x80 || opcode == 0x82 || opcode == 0x83))
        return false;

    coop_selection.world = world;
    coop_selection.actor = actor;
    coop_selection.network = network;
    coop_selection.sender = sender;
    coop_selection.dispatch = true;
    coop_selection.using_remote = sender != local;
    coop_reconcile_group_orders(actor);
    if (coop_selection.using_remote) {
        coop_selection.local = coop_read_selection(actor);
        coop_set_selection(actor, &coop_selection.remote);
        coop_selection.viewer = get32(world + COOP_VIEWER);
        *(uint32_t *)(world + COOP_VIEWER) = COOP_UNINVOLVED_VIEWER;
    }
    return true;
}

__declspec(dllexport) const unsigned char *AnnoMenuCoopBeginCommand(unsigned char *network, const unsigned char *record)
{
    unsigned char *const frame = (unsigned char *)GetModuleHandleW(L"AnnoFrame.dll");
    const uint16_t wire = get16(record);
    unsigned int opcode = wire;
    const unsigned int tag = wire >> 8u;
    if (tag && tag <= 2 && menu_coop_active()) {
        const unsigned int base = wire & 0xffu;
        if (base >= COOP_FIRST_ACTION && base <= COOP_LAST_ACTION &&
            coop_begin_selection(frame, network, record, base, tag - 1u))
            opcode = base;
    }
    const uint32_t target = opcode >= COOP_FIRST_STOCK_COMMAND && opcode <= COOP_LAST_STOCK_COMMAND ?
        get32(frame + COOP_COMMAND_TABLE + 4u * (opcode - COOP_FIRST_STOCK_COMMAND)) : COOP_COMMAND_NEXT;
    return frame + target;
}

__declspec(dllexport) const unsigned char *AnnoMenuCoopEndCommand(unsigned char *network, const unsigned char *payload)
{
    if (coop_selection.dispatch && coop_selection.network == network) {
        coop_reconcile_group_orders(coop_selection.actor);
        if (coop_selection.using_remote) {
            coop_selection.remote = coop_read_selection(coop_selection.actor);
            coop_set_selection(coop_selection.actor, &coop_selection.local);
            *(uint32_t *)(coop_selection.world + COOP_VIEWER) = coop_selection.viewer;
        }
        coop_selection.dispatch = false;
        coop_selection.using_remote = false;
    }
    return payload + get16(payload - 2);
}

__declspec(dllexport) void AnnoMenuCoopSeedGroup(unsigned char *active, int kind, const uint32_t *stock_id,
                                               unsigned int count)
{
    typedef void (*SeedGroup)(unsigned char *, int, const uint32_t *, unsigned int, unsigned int);
    const unsigned char *const model = (const unsigned char *)GetModuleHandleW(L"AnnoWelt.dll");
    uint32_t slot = *stock_id;
    if (coop_selection.dispatch && coop_selection.sender == 1 && model &&
        coop_pointer(active, 0) == model + COOP_ACTIVE_GROUP_VTABLE &&
        coop_pointer(active, 0x18) == coop_selection.actor && kind == 3)
        slot = COOP_GUEST_GROUP;
    ((SeedGroup)coop_method(active, 0x38))(active, kind, &slot, count, 0);
}

__declspec(dllexport) unsigned int AnnoMenuCoopGroupLimit(void)
{
    return coop_selection.guest_group ? COOP_GUEST_GROUP : COOP_STOCK_GROUP_COUNT;
}

static void coop_release_selection(void)
{
    if (coop_selection.actor) {
        const uint32_t view = get32(coop_selection.world + COOP_VIEWER);
        *(uint32_t *)(coop_selection.world + COOP_VIEWER) = COOP_UNINVOLVED_VIEWER;
        if (coop_selection.remote.active) {
            unsigned char *const active = coop_selection.remote.active;
            ((void (*)(void *))coop_method(active, 0x48))(active);
            ((void (*)(void *))coop_method(active, 0x18))(active);
        }
        for (size_t index = 0; index < COOP_PLAYER_CACHE_COUNT; ++index) {
            unsigned char *const cached = coop_selection.remote.cache[index];
            if (cached)
                ((void (*)(void *))coop_method(cached, 0x18))(cached);
        }
        *(uint32_t *)(coop_selection.world + COOP_VIEWER) = view;
    }
    memset(&coop_selection, 0, sizeof coop_selection);
}

__declspec(dllexport) void AnnoMenuCoopCloseGame(unsigned char *game)
{
    if (coop_selection.actor && coop_pointer(game, COOP_GAME_WORLD) == coop_selection.world)
        coop_release_selection();
    ((void (*)(void *))coop_method(game, 0xb0))(game);
}
