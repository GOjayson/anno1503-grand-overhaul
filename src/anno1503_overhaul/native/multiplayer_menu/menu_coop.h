/* Keep two transport IDs while assigning one World player during fresh New Earth creation. */
enum {
    MENU_COOP_SCENE_FACTORY = 0x9e300,
    MENU_COOP_SCENARIO_DIRECTORY = 0xc7150,
    MENU_COOP_SCENARIO_NAME = 0xc7430,
    MENU_COOP_SCENARIO_MODE = 0xc7554,
    MENU_NATIVE_FLAG_COUNT = 8,
    MENU_COOP_ROSTER_DIRTY = 0xc7c15,
    MENU_COOP_SEND_ROSTER = 0x4ea90,
    MENU_COOP_FLAG_HANDLER = 0x4d660,
    MENU_COOP_FLAG_UI_SLOT = 0x1a8,
    MENU_COOP_PICKER_VTABLE = 0xab0c0,
    MENU_COOP_FLAG_VTABLE = 0xab3a0,
    MENU_COOP_WIDGETS = 0x21c8,
    MENU_COOP_FLAG_PICKER_INDEX = 0x50 / sizeof(void *),
};

static bool menu_two_player_roster(unsigned char *roster, unsigned char **host, unsigned char **guest)
{
    unsigned char *const first = roster ? *(unsigned char **)(roster + 0x20u) : NULL;
    unsigned char *const second = first ? *(unsigned char **)(first + 8u) : NULL;
    if (!second || first == second || *(void **)(second + 8u))
        return false;
    const uint32_t first_id = get32(first + 0x20u), second_id = get32(second + 0x20u);
    if (first_id > 1u || second_id > 1u || first_id == second_id)
        return false;
    *host = first_id == 0 ? first : second;
    *guest = first_id == 0 ? second : first;
    return true;
}

static bool menu_native_flag(unsigned int colour)
{
    return colour >= 1u && colour <= MENU_NATIVE_FLAG_COUNT;
}

static bool menu_wire_flag_pair(unsigned int first, unsigned int second, bool shared_flag)
{
    if ((first != 0xff && !menu_native_flag(first)) || (second != 0xff && !menu_native_flag(second)))
        return false;
    return shared_flag ? first == second : first == 0xff || first != second;
}

static bool menu_coop_mirror_host_flag(unsigned char *roster)
{
    unsigned char *host, *guest;
    if (!menu_two_player_roster(roster, &host, &guest))
        return false;
    const unsigned char colour = host[NODE_COLOR];
    if ((colour != 0xff && !menu_native_flag(colour)) || guest[NODE_COLOR] == colour)
        return false;
    guest[NODE_COLOR] = colour;
    return true;
}

static const TrialSettings *menu_coop_lobby_plan(unsigned char *frame, const unsigned char *lobby)
{
    if (!frame || !lobby || *(const void *const *)lobby != frame + LOBBY_VTABLE || !menu_coop_active())
        return NULL;
    return named_direct_session(frame);
}

static void menu_coop_sync_lobby_flags(unsigned char *frame, unsigned char *lobby)
{
    const TrialSettings *const plan = menu_coop_lobby_plan(frame, lobby);
    if (plan && plan->role == TRIAL_HOST &&
        menu_coop_mirror_host_flag(*(unsigned char **)(frame + ROSTER_GLOBAL)))
        frame[MENU_COOP_ROSTER_DIRTY] = 1;
}

static void menu_coop_disable_guest_picker(unsigned char *frame, unsigned char *lobby)
{
    const TrialSettings *const plan = menu_coop_lobby_plan(frame, lobby);
    if (!plan || plan->role != TRIAL_GUEST)
        return;
    void **const widgets = *(void ***)(lobby + MENU_COOP_WIDGETS);
    void *const picker = widgets ? widgets[MENU_COOP_FLAG_PICKER_INDEX] : NULL;
    if (!picker || *(void **)picker != frame + MENU_COOP_PICKER_VTABLE)
        return;

    void **const methods = *(void ***)picker;
    unsigned int (*const count)(void *, unsigned int) =
        (unsigned int (*)(void *, unsigned int))methods[0x70 / sizeof(void *)];
    void *(*const get)(void *, unsigned int, unsigned int) =
        (void *(*)(void *, unsigned int, unsigned int))methods[0x48 / sizeof(void *)];
    if (count(picker, 0xb00) != MENU_NATIVE_FLAG_COUNT)
        return;
    void *flags[MENU_NATIVE_FLAG_COUNT];
    for (unsigned int i = 0; i < MENU_NATIVE_FLAG_COUNT; ++i) {
        flags[i] = get(picker, 0xb00, i);
        if (!flags[i] || *(void **)flags[i] != frame + MENU_COOP_FLAG_VTABLE)
            return;
    }
    const uint32_t disabled[3] = {0};
    for (unsigned int i = 0; i < MENU_NATIVE_FLAG_COUNT; ++i) {
        void **const button = *(void ***)flags[i];
        void (*const set)(void *, unsigned int, const void *) =
            (void (*)(void *, unsigned int, const void *))button[0xa0 / sizeof(void *)];
        set(flags[i], 0x193, disabled);
    }
}

__declspec(dllexport) void AnnoMenuCoopChooseFlag(unsigned char *lobby, unsigned int index)
{
    unsigned char *const frame = (unsigned char *)GetModuleHandleW(L"AnnoFrame.dll");
    if (!frame)
        return;
    const TrialSettings *const plan = menu_coop_lobby_plan(frame, lobby);
    if (plan && plan->role == TRIAL_GUEST)
        return;
    void (*const choose)(void *, unsigned int) = (void (*)(void *, unsigned int))(frame + MENU_COOP_FLAG_HANDLER);
    choose(lobby, index);
}

__declspec(dllexport) int AnnoMenuCoopSendFlags(unsigned char *lobby)
{
    unsigned char *const frame = (unsigned char *)GetModuleHandleW(L"AnnoFrame.dll");
    if (frame) {
        menu_coop_sync_lobby_flags(frame, lobby);
        void (*const send)(void *) = (void (*)(void *))(frame + MENU_COOP_SEND_ROSTER);
        send(lobby);
    }
    return 1;
}

__declspec(dllexport) void AnnoMenuCoopGuestFlagUi(unsigned char *lobby)
{
    void **const methods = *(void ***)lobby;
    void (*const update)(void *) = (void (*)(void *))methods[MENU_COOP_FLAG_UI_SLOT / sizeof(void *)];
    update(lobby);
    menu_coop_disable_guest_picker((unsigned char *)GetModuleHandleW(L"AnnoFrame.dll"), lobby);
}

static bool menu_coop_new_earth(const unsigned char *frame)
{
    static const char scenario[] = "\\Scenes\\0500MultiEndlos\\NewEarth.sze";
    if (frame[MENU_COOP_SCENARIO_MODE] != 0)
        return false;
    char selected[MAX_PATH], absolute[MAX_PATH], expected[MAX_PATH];
    const DWORD executable_length = GetModuleFileNameA(NULL, expected, ARRAYSIZE(expected));
    if (!executable_length || executable_length >= ARRAYSIZE(expected))
        return false;
    char *const executable_name = strrchr(expected, '\\');
    if (!executable_name || (size_t)(executable_name - expected) + sizeof scenario > ARRAYSIZE(expected))
        return false;
    memcpy(executable_name, scenario, sizeof scenario);

    const char *const directory = (const char *)(frame + MENU_COOP_SCENARIO_DIRECTORY);
    const char *const name = (const char *)(frame + MENU_COOP_SCENARIO_NAME);
    const size_t directory_length = strnlen(directory, MAX_PATH);
    const size_t name_length = strnlen(name, MAX_PATH);
    if (!directory_length || !name_length || directory_length + 1 + name_length >= ARRAYSIZE(selected))
        return false;
    memcpy(selected, directory, directory_length);
    size_t name_at = directory_length;
    if (selected[name_at - 1] != '\\')
        selected[name_at++] = '\\';
    memcpy(selected + name_at, name, name_length + 1);
    const DWORD full_length = GetFullPathNameA(selected, ARRAYSIZE(absolute), absolute, NULL);
    return full_length && full_length < ARRAYSIZE(absolute) && _stricmp(absolute, expected) == 0;
}

typedef HRESULT (*MenuSceneFactory)(void *, const char *, void *, void **, void *, int, unsigned int);

static HRESULT menu_coop_create_scene(MenuSceneFactory factory, unsigned char *frame, void *unused,
                                      const char *path, void *context, void **scene, void *view,
                                      int game_mode, unsigned int flags)
{
    unsigned char *host = NULL, *guest = NULL;
    const bool coop = menu_coop_active();
    if (coop && (!menu_coop_new_earth(frame) || !named_direct_session(frame) ||
        !menu_two_player_roster(*(unsigned char **)(frame + ROSTER_GLOBAL), &host, &guest) ||
        !menu_native_flag(host[NODE_COLOR])))
        return E_FAIL;

    const HRESULT result = factory(unused, path, context, scene, view, game_mode, flags);
    if (SUCCEEDED(result) && coop) {
        /* Frame copies the roster into its socket-to-World seat table next.
           Its ordered tick and checksum traffic continues to use the socket IDs. */
        guest[NODE_COLOR] = host[NODE_COLOR];
    }
    return result;
}

__declspec(dllexport) HRESULT AnnoMenuCoopScene(void *unused, const char *path, void *context,
                                              void **scene, void *view, int game_mode, unsigned int flags)
{
    unsigned char *const frame = (unsigned char *)GetModuleHandleW(L"AnnoFrame.dll");
    if (!frame)
        return E_FAIL;
    const MenuSceneFactory factory = *(const MenuSceneFactory *)(frame + MENU_COOP_SCENE_FACTORY);
    return menu_coop_create_scene(factory, frame, unused, path, context, scene, view, game_mode, flags);
}
