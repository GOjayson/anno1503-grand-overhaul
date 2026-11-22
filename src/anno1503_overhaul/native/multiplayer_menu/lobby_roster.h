/* Assemble the same tGadListeEx rows as the stock roster callback, using
 * accepted native UDP players for a direct lobby's names and flags. */
enum {
    MENU_LOBBY_LIST_VTABLE = 0xaada8,
    MENU_LOBBY_LIST_SET_CAPS = 0x924d0,
    MENU_LOBBY_LIST_EVENT = 0x8faf0,
    MENU_LOBBY_REFRESH_KICKS = 0x4e550,
    MENU_LOBBY_ROSTER_DIRTY = 0xc7c15,
    MENU_LOBBY_LIST_GRAPHICS = 0x2264,
    MENU_LOBBY_FLAG_SPRITE = 365,
    MENU_LOBBY_SELECTED_ID = 0x30fc,
    MENU_LOBBY_LOCAL_ID = 0xc6cc8,
    MENU_LOBBY_NAME_CAPACITY = NODE_COLOR - 0x24,
};

typedef struct {
    const char *name;
    uint64_t id;
    uint64_t optional;
    uint32_t cells[15];
} MenuLobbyListRow;

typedef struct {
    uint64_t unused;
    const MenuLobbyListRow *row;
} MenuLobbyListCaps;

_Static_assert(offsetof(MenuLobbyListRow, cells) == 0x18, "Native row column layout");
_Static_assert(offsetof(MenuLobbyListCaps, row) == 8, "Native row capability layout");

typedef void (*MenuLobbyListEvent)(void *, unsigned int, unsigned int, unsigned int, unsigned int);
typedef int (*MenuLobbyListWrite)(void *, unsigned int, const MenuLobbyListCaps *);

static void menu_coop_disable_guest_picker(unsigned char *frame, unsigned char *lobby);

static void menu_lobby_list_add(void *list, MenuLobbyListWrite write, const char *name,
                                uint32_t id, uint32_t sprite, unsigned int colour)
{
    MenuLobbyListRow row = {.name = name, .id = id};
    memset(row.cells, 0xff, sizeof row.cells);
    row.cells[0] = 0x16;
    row.cells[5] = sprite;
    row.cells[10] = colour == 0xff ? 0 : colour;
    const MenuLobbyListCaps caps = {.row = &row};
    write(list, 0x1b8, &caps);
}

typedef struct {
    const char *name;
    uint32_t id;
    unsigned int colour;
} MenuLobbyDisplayPlayer;

static const char *menu_lobby_display_name(unsigned char *frame, const TrialSettings *plan,
                                           const unsigned char *node, uint32_t id)
{
    const char *name;
    if (menu_room_transport(plan)) {
        const unsigned char *const server = *(const unsigned char **)(frame + SERVER_GLOBAL);
        name = menu_room_roster_name(plan, server, id, get32(frame + MENU_LOBBY_LOCAL_ID));
    } else {
        name = id == 0 ? plan->host_name : plan->guest_name;
    }
    if (!name || !name[0])
        name = (const char *)(node + 0x24);
    return name[0] && memchr(name, '\0', MENU_LOBBY_NAME_CAPACITY) ? name : NULL;
}

static bool menu_lobby_collect_players(unsigned char *frame, const TrialSettings *plan, const unsigned char *node,
                                       MenuLobbyDisplayPlayer players[MENU_ROOM_SEATS], unsigned int *count)
{
    unsigned int seen = 0;
    const unsigned int seats = menu_room_transport(plan) ? plan->player_count : 2;
    *count = 0;
    while (node) {
        if (*count >= seats)
            return false;
        const uint32_t id = get32(node + 0x20);
        const unsigned int colour = node[NODE_COLOR];
        if (id >= seats || (seen & (1u << id)) || (colour != 0xff && (!colour || colour > MENU_ROOM_SEATS)))
            return false;
        const char *const name = menu_lobby_display_name(frame, plan, node, id);
        if (!name)
            return false;
        players[(*count)++] = (MenuLobbyDisplayPlayer){.name = name, .id = id, .colour = colour};
        seen |= 1u << id;
        node = *(const unsigned char *const *)(node + 8);
    }
    return true;
}

static bool menu_direct_lobby_list(unsigned char *frame, unsigned char *lobby)
{
    if (*(void **)lobby != frame + LOBBY_VTABLE || !use_native_lobby_paint(frame))
        return false;
    const TrialSettings *const plan = settings();
    if (plan->role != TRIAL_HOST && plan->role != TRIAL_GUEST)
        return false;
    void **const widgets = *(void ***)(lobby + 0x21c8);
    void *const list = widgets ? widgets[0x68 / sizeof(void *)] : NULL;
    const uint32_t sprite = get32(lobby + MENU_LOBBY_LIST_GRAPHICS);
    if (!list || list != *(void **)(lobby + 0x21f0) || *(void **)list != frame + MENU_LOBBY_LIST_VTABLE ||
        sprite != MENU_LOBBY_FLAG_SPRITE)
        return false;
    const unsigned char *const roster = *(const unsigned char **)(frame + ROSTER_GLOBAL);
    const unsigned char *const head = roster ? *(const unsigned char *const *)(roster + 0x20) : NULL;
    MenuLobbyDisplayPlayer players[MENU_ROOM_SEATS];
    unsigned int count;
    if (!menu_lobby_collect_players(frame, plan, head, players, &count))
        return false;

    const MenuLobbyListEvent event = (MenuLobbyListEvent)(frame + MENU_LOBBY_LIST_EVENT);
    const MenuLobbyListWrite write = (MenuLobbyListWrite)(frame + MENU_LOBBY_LIST_SET_CAPS);
    const uint32_t selected = get32(lobby + MENU_LOBBY_SELECTED_ID);
    bool retain_selection = false;
    event(list, 0, 0x0d, 0, 0);
    for (unsigned int index = 0; index < count; ++index) {
        const MenuLobbyDisplayPlayer *const player = &players[index];
        menu_lobby_list_add(list, write, player->name, player->id, sprite, player->colour);
        retain_selection |= selected == player->id;
    }
    if (retain_selection)
        event(list, 0, 0x0e, selected, 0);
    else
        memset(lobby + MENU_LOBBY_SELECTED_ID, 0xff, sizeof selected);
    void (*const refresh_kicks)(void *) = (void (*)(void *))(frame + MENU_LOBBY_REFRESH_KICKS);
    refresh_kicks(lobby);
    menu_coop_disable_guest_picker(frame, lobby);
    return true;
}

__declspec(dllexport) void AnnoMenuRefreshLobbyPlayers(unsigned char *lobby)
{
    unsigned char *const frame = (unsigned char *)GetModuleHandleW(L"AnnoFrame.dll");
    if (!frame || !lobby)
        return;
    if (!menu_direct_lobby_list(frame, lobby)) {
        void (*const stock_refresh)(void *) = (void (*)(void *))(frame + NATIVE_ROSTER_REFRESH);
        stock_refresh(lobby);
    }
}

__declspec(dllexport) void AnnoMenuUpdateLobbyPlayers(unsigned char *lobby)
{
    AnnoMenuRefreshLobbyPlayers(lobby);
    unsigned char *const frame = (unsigned char *)GetModuleHandleW(L"AnnoFrame.dll");
    if (frame)
        frame[MENU_LOBBY_ROSTER_DIRTY] = 0;
}
