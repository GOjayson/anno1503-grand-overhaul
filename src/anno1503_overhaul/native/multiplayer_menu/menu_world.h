/* Optional World Settings is loaded only after a generated menu request. */
static const WCHAR menu_world_runtime[] = L"AnnoGrandWorldSettings\\AnnoWorldSettings.dll";

static DWORD menu_game_folder(WCHAR path[MAX_PATH])
{
    DWORD length = GetModuleFileNameW(NULL, path, MAX_PATH);
    if (!length || length >= MAX_PATH)
        return 0;
    while (length && path[length - 1] != L'\\')
        --length;
    return length;
}

static bool menu_world_path(WCHAR path[MAX_PATH])
{
    DWORD length = menu_game_folder(path);
    if (!length || length + ARRAYSIZE(menu_world_runtime) > MAX_PATH)
        return false;
    memcpy(path + length, menu_world_runtime, sizeof menu_world_runtime);
    return true;
}

static bool menu_has_world_settings(void)
{
    WCHAR path[MAX_PATH];
    if (!menu_world_path(path))
        return false;
    const DWORD flags = GetFileAttributesW(path);
    return flags != INVALID_FILE_ATTRIBUTES && !(flags & (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT));
}

#if defined(ANNO_MENU_WORLD_VISIBILITY)
#include "world_runtime_pin.h"

typedef BOOL (WINAPI *MenuVisibilityEnable)(uint32_t, uint32_t);
typedef void (WINAPI *MenuVisibilityDisable)(void);
static HMODULE menu_world_library;
static MenuVisibilityDisable menu_disable_visibility;

static HMODULE menu_load_world_runtime(void)
{
    if (!menu_world_library) {
        WCHAR path[MAX_PATH], actual[MAX_PATH + 4];
        if (!menu_world_path(path))
            return NULL;
        HANDLE file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                                   FILE_FLAG_OPEN_REPARSE_POINT, NULL);
        if (file == INVALID_HANDLE_VALUE)
            return NULL;
        BY_HANDLE_FILE_INFORMATION info;
        const DWORD size = GetFinalPathNameByHandleW(file, actual, ARRAYSIZE(actual), FILE_NAME_NORMALIZED | VOLUME_NAME_DOS);
        if (size > 4 && size < ARRAYSIZE(actual) && wcsncmp(actual, L"\\\\?\\", 4) == 0 &&
            anno_shadow_equal_path(actual + 4, path) && GetFileInformationByHandle(file, &info) &&
            !(info.dwFileAttributes & (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT)) &&
            !info.nFileSizeHigh && info.nFileSizeLow && info.nFileSizeLow <= 16 * 1024 * 1024 &&
            anno_shadow_digest(file, info.nFileSizeLow, menu_world_runtime_sha256)) {
            menu_world_library = LoadLibraryExW(path, NULL, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32);
        }
        CloseHandle(file);
    }
    return menu_world_library;
}

static bool menu_apply_visibility(uint32_t map_mode, uint32_t enemy_mode)
{
    static MenuVisibilityEnable enable;
    const HMODULE library = menu_load_world_runtime();
    if (!library)
        return false;
    if (!enable) {
        enable = (MenuVisibilityEnable)GetProcAddress(library, "WorldSettingsEnableMultiplayerVisibility");
        menu_disable_visibility = (MenuVisibilityDisable)GetProcAddress(library, "WorldSettingsDisableMultiplayerVisibility");
    }
    return enable && menu_disable_visibility && enable(map_mode, enemy_mode);
}
#endif

#if defined(ANNO_MENU_WORLD_DISASTERS)
typedef BOOL (WINAPI *MenuDisasterEnable)(const unsigned char *);
typedef void (WINAPI *MenuDisasterClear)(void);
static MenuDisasterClear menu_disable_disasters;

static bool menu_apply_disasters(const unsigned char policy[32])
{
    HMODULE library = menu_load_world_runtime();
    if (!library)
        return false;
    MenuDisasterEnable enable = (MenuDisasterEnable)GetProcAddress(library, "WorldSettingsPrepareMultiplayerDisasters");
    menu_disable_disasters = (MenuDisasterClear)GetProcAddress(library, "WorldSettingsClearMultiplayerDisasters");
    return enable && menu_disable_disasters && enable(policy);
}
#endif

#if defined(ANNO_MENU_WORLD_HUGE)
typedef DWORD (WINAPI *MenuHugePrepare)(void);
typedef BOOL (WINAPI *MenuHugeClear)(void);
static MenuHugeClear menu_huge_cleanup;
#endif

static bool menu_restore_huge(void)
{
#if defined(ANNO_MENU_WORLD_HUGE)
    if (menu_huge_cleanup) {
        if (!menu_huge_cleanup())
            return false;
        menu_huge_cleanup = NULL;
    }
#endif
    return true;
}

static bool menu_apply_world_width(DWORD width)
{
    if (width != 2048)
        return width == 256 || width == 512 || width == 1024;
#if defined(ANNO_MENU_WORLD_HUGE)
    const HMODULE library = menu_load_world_runtime();
    if (library && !menu_huge_cleanup) {
        MenuHugePrepare prepare = (MenuHugePrepare)GetProcAddress(library, "WorldSettingsPrepareMultiplayerHugeWorld");
        MenuHugeClear clear = (MenuHugeClear)GetProcAddress(library, "WorldSettingsClearMultiplayerHugeWorld");
        if (prepare && clear) {
            menu_huge_cleanup = clear;
            return prepare() == 173;
        }
    }
#endif
    return false;
}

static void menu_clear_world(void)
{
#if defined(ANNO_MENU_WORLD_VISIBILITY)
    if (menu_disable_visibility)
        menu_disable_visibility();
#endif
#if defined(ANNO_MENU_WORLD_DISASTERS)
    if (menu_disable_disasters)
        menu_disable_disasters();
#endif
    anno_shadow_clear();
}

static bool menu_arm_world(const MenuResponse *reply)
{
    if (!reply->scene_size)
        return true;
    static const WCHAR directory[] = L"AnnoGrandMatches\\";
    static const WCHAR digits[] = L"0123456789abcdef";
    static const WCHAR extension[] = L".sze";
    WCHAR path[MAX_PATH];
    DWORD length = menu_game_folder(path);
    if (!length || length + ARRAYSIZE(directory) - 1 + 64 + ARRAYSIZE(extension) > ARRAYSIZE(path))
        return false;
    memcpy(path + length, directory, sizeof directory);
    length += ARRAYSIZE(directory) - 1;
    for (size_t index = 0; index < 32; ++index) {
        path[length++] = digits[reply->scene_digest[index] >> 4];
        path[length++] = digits[reply->scene_digest[index] & 15];
    }
    memcpy(path + length, extension, sizeof extension);
    if (!anno_shadow_arm(path, reply->scene_size, reply->scene_digest))
        return false;
#if defined(ANNO_MENU_WORLD_VISIBILITY)
    const bool visible = menu_apply_visibility(reply->map_mode, reply->enemy_mode);
#else
    const bool visible = reply->map_mode == 1 && reply->enemy_mode == 0;
#endif
#if defined(ANNO_MENU_WORLD_DISASTERS)
    const bool disasters = visible && menu_apply_disasters(reply->disaster_policy);
#else
    const bool disasters = visible;
#endif
    if (disasters && menu_apply_world_width(anno_shadow_world_width()))
        return true;
    menu_clear_world();
    (void)menu_restore_huge();
    return false;
}
