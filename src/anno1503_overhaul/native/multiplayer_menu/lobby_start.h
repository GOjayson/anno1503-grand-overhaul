/* Direct group, generated and co-op matches retain their admitted sockets through Start. */
enum {
    MENU_NATIVE_LOBBY_START = 0x4d7e0,
    MENU_NATIVE_DISCONNECT_VECTOR = 0xc7c18,
    MENU_LOBBY_COLOUR_TABLE = 0x30e4,
    MENU_LOBBY_COLOURS = MENU_NATIVE_FLAG_COUNT,
    MENU_LOBBY_STARTING = 0x3104,
};

static bool menu_lobby_colour_available(const unsigned char *lobby, unsigned int colour)
{
    return menu_native_flag(colour) &&
           lobby[MENU_LOBBY_COLOUR_TABLE + colour - 1u] != 0;
}

static const WCHAR *menu_lobby_start_problem(const unsigned char *lobby, unsigned char *roster,
                                            const unsigned char *disconnects, bool paired, bool shared_flag)
{
    unsigned char *host, *guest;
    if (!paired || !disconnects || !menu_two_player_roster(roster, &host, &guest))
        return L"Both players must be connected before starting the match.";

    /* Start would disconnect every queued entry through tConnectServerSock
     * +0xF0. A nonempty list is incompatible with a paired generated start. */
    if (*(const void *const *)disconnects != *(const void *const *)(disconnects + 8u))
        return L"A player is marked for removal. Reopen the lobby with both players before starting.";

    const unsigned int host_colour = host[NODE_COLOR], guest_colour = guest[NODE_COLOR];
    if (shared_flag)
        return menu_lobby_colour_available(lobby, host_colour) && host_colour == guest_colour ? NULL :
            L"Wait for the host to choose the shared flag.";
    if (host_colour == guest_colour || !menu_lobby_colour_available(lobby, host_colour) ||
        !menu_lobby_colour_available(lobby, guest_colour))
        return L"Wait until both players have chosen different available colours before starting.";
    return NULL;
}

static const WCHAR *menu_room_start_problem(const unsigned char *lobby, const unsigned char *roster,
                                             const unsigned char *disconnects, bool admitted, unsigned int count)
{
    const WCHAR *const missing = L"Wait for every paired player to enter the native lobby before starting.";
    if (!admitted || !roster || !disconnects || count < 3u || count > MENU_LOBBY_COLOURS)
        return missing;
    if (*(const void *const *)disconnects != *(const void *const *)(disconnects + 8u))
        return L"A player is marked for removal. Reopen the lobby with the full group before starting.";

    const unsigned char *node = *(const unsigned char *const *)(roster + 0x20u);
    unsigned int players = 0, colours = 0;
    for (unsigned int index = 0; index < count; ++index) {
        if (!node)
            return missing;
        const uint32_t id = get32(node + 0x20u);
        if (id >= count || (players & (1u << id)))
            return missing;
        const unsigned int colour = node[NODE_COLOR];
        if (!menu_lobby_colour_available(lobby, colour) || (colours & (1u << colour)))
            return L"Each player needs a different available flag before starting.";
        players |= 1u << id;
        colours |= 1u << colour;
        node = *(const unsigned char *const *)(node + 8u);
    }
    return node ? missing : NULL;
}

__declspec(dllexport) void AnnoMenuStartWorldLobby(unsigned char *lobby)
{
    unsigned char *const frame = (unsigned char *)GetModuleHandleW(L"AnnoFrame.dll");
    if (!frame || !lobby)
        return;
    void (*const stock_start)(void *) = (void (*)(void *))(frame + MENU_NATIVE_LOBBY_START);
    const bool coop = menu_coop_active();
    const TrialSettings *const plan = settings();
    const bool group = menu_room_transport(plan);
    if (*(const void *const *)lobby != frame + LOBBY_VTABLE || (!anno_shadow_is_armed() && !coop && !group) ||
        !direct_mode() || plan->role != TRIAL_HOST) {
        stock_start(lobby);
        return;
    }
    if (lobby[MENU_LOBBY_STARTING])
        return;

    unsigned char *const roster = *(unsigned char **)(frame + ROSTER_GLOBAL);
    const unsigned char *const disconnects = *(const unsigned char *const *)(frame + MENU_NATIVE_DISCONNECT_VECTOR);
    const bool ready = named_direct_session(frame) != NULL;
    const WCHAR *problem;
    if (group && plan->player_count > 4u && (!anno_shadow_is_armed() || !menu_coop_new_earth(frame))) {
        problem = L"Choose New Earth with the agreed World Settings map for five to eight players.";
    } else if (group) {
        const unsigned char *const server = *(const unsigned char *const *)(frame + SERVER_GLOBAL);
        problem = menu_room_start_problem(lobby, roster, disconnects, ready && menu_room_all_admitted(plan, server),
                                         plan->player_count);
    } else if (coop && !menu_coop_new_earth(frame)) {
        problem = L"Choose New Earth in New Game to start a co-op match.";
    } else {
        problem = menu_lobby_start_problem(lobby, roster, disconnects, ready, coop);
    }
    if (!problem) {
        stock_start(lobby);
        return;
    }
    const HWND window = *(const HWND *)(lobby + 0x2220u);
    if (window && (void *)GetWindowLongPtrW(window, GWLP_USERDATA) == lobby)
        MessageBoxW(window, problem, coop ? L"Co-op" : group ? L"Multiplayer lobby" : L"World Settings",
                    MB_OK | MB_ICONINFORMATION);
}
