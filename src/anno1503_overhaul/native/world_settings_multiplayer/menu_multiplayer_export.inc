/* Optional selection-only use of the native World Settings dialog. */
#include <tlhelp32.h>

static volatile LONG wsMultiplayerPreviewThread;
static int wsMultiplayerStartLayout;
static HANDLE wsMultiplayerPresetRootHandle = INVALID_HANDLE_VALUE;
static HANDLE wsMultiplayerPresetFolderHandle = INVALID_HANDLE_VALUE;
static char wsMultiplayerPresetRoot[MAX_PATH];

static int wsEnterMultiplayerPreview(int startLayout)
{
    if (GetModuleHandleW(L"AnnoFrame.dll") || WorldSettingsIsActive())
        return 0;
    if (InterlockedCompareExchange(&wsMultiplayerPreviewThread, (LONG)GetCurrentThreadId(), 0) != 0)
        return 0;
    wsMultiplayerStartLayout = startLayout;
    return 1;
}

static void wsLeaveMultiplayerPreview(void)
{
    if (wsMultiplayerPresetFolderHandle != INVALID_HANDLE_VALUE)
        CloseHandle(wsMultiplayerPresetFolderHandle);
    if (wsMultiplayerPresetRootHandle != INVALID_HANDLE_VALUE)
        CloseHandle(wsMultiplayerPresetRootHandle);
    wsMultiplayerPresetFolderHandle = wsMultiplayerPresetRootHandle = INVALID_HANDLE_VALUE;
    wsMultiplayerPresetRoot[0] = 0;
    wsMultiplayerStartLayout = 0;
    InterlockedExchange(&wsMultiplayerPreviewThread, 0);
}

int WorldSettingsMultiplayerPreviewActive(void)
{
    return (DWORD)InterlockedCompareExchange(&wsMultiplayerPreviewThread, 0, 0) == GetCurrentThreadId();
}

static int wsMultiplayerPresetParent(HWND dialog, const wchar_t *game)
{
    wchar_t windowClass[16], image[MAX_PATH];
    HWND owner = GetWindow(dialog, GW_OWNER);
    DWORD pid = 0, ownerPid = 0;
    DWORD thread = GetWindowThreadProcessId(dialog, &pid);
    if (!thread || !pid || !owner || GetWindowThreadProcessId(owner, &ownerPid) != thread ||
        pid != ownerPid || IsWindowEnabled(owner) ||
        !GetClassNameW(dialog, windowClass, ARRAYSIZE(windowClass)) || wcscmp(windowClass, L"#32770"))
        return 0;
    HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snapshot == INVALID_HANDLE_VALUE)
        return 0;
    PROCESSENTRY32W process = {.dwSize = sizeof process};
    DWORD workerPid = GetCurrentProcessId(), parentPid = 0;
    for (BOOL ok = Process32FirstW(snapshot, &process); ok; ok = Process32NextW(snapshot, &process)) {
        if (process.th32ProcessID == workerPid) {
            parentPid = process.th32ParentProcessID;
            break;
        }
    }
    CloseHandle(snapshot);
    if (pid != parentPid)
        return 0;
    HANDLE parent = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, pid);
    if (!parent)
        return 0;
    DWORD size = ARRAYSIZE(image);
    int verified = QueryFullProcessImageNameW(parent, 0, image, &size) && !_wcsicmp(image, game);
    CloseHandle(parent);
    return verified;
}

static int wsMultiplayerPresetDirectoryHandle(HANDLE directory)
{
    BY_HANDLE_FILE_INFORMATION info;
    return directory != INVALID_HANDLE_VALUE && GetFileInformationByHandle(directory, &info) &&
        (info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) &&
        !(info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT);
}

static int wsSetMultiplayerPresetRoot(HWND owner, const wchar_t *root)
{
    const wchar_t worker[] = L"\\AnnoGrandMenuWorker.exe";
    const wchar_t game[] = L"\\Anno1503.exe";
    const wchar_t marker[] = L"\\.anno1503-grand-overhaul-copy.json";
    wchar_t actual[MAX_PATH], path[MAX_PATH], roundTrip[MAX_PATH];
    DWORD length = GetModuleFileNameW(NULL, actual, ARRAYSIZE(actual));
    if (!length || length >= ARRAYSIZE(actual) || length < ARRAYSIZE(worker) ||
        _wcsicmp(actual + length - (ARRAYSIZE(worker) - 1), worker))
        return 0;
    length -= ARRAYSIZE(worker) - 1;
    actual[length] = 0;
    if (!root || _wcsicmp(root, actual) || length + ARRAYSIZE(marker) > ARRAYSIZE(path))
        return 0;
    memcpy(path, actual, length * sizeof *path);
    memcpy(path + length, marker, sizeof marker);
    DWORD attrs = GetFileAttributesW(path);
    if (attrs == INVALID_FILE_ATTRIBUTES || (attrs & (FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_DIRECTORY)))
        return 0;
    memcpy(path + length, game, sizeof game);
    if (!wsMultiplayerPresetParent(owner, path))
        return 0;
    HANDLE directory = CreateFileW(root, FILE_READ_ATTRIBUTES, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL,
        OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, NULL);
    if (!wsMultiplayerPresetDirectoryHandle(directory)) {
        if (directory != INVALID_HANDLE_VALUE)
            CloseHandle(directory);
        return 0;
    }
    wsMultiplayerPresetRootHandle = directory;
    UINT codePage = GetACP();
    BOOL fallback = FALSE;
    DWORD flags = codePage == CP_UTF8 ? WC_ERR_INVALID_CHARS : WC_NO_BEST_FIT_CHARS;
    char ansi[MAX_PATH];
    int bytes = WideCharToMultiByte(codePage, flags, root, -1, ansi, ARRAYSIZE(ansi),
        NULL, codePage == CP_UTF8 ? NULL : &fallback);
    if (!bytes || fallback || !MultiByteToWideChar(codePage, MB_ERR_INVALID_CHARS, ansi, -1,
        roundTrip, ARRAYSIZE(roundTrip)) || wcscmp(root, roundTrip) ||
        (size_t)bytes + sizeof "\\AnnoGrandMultiplayerPresets" + 64u > MAX_PATH)
        return 0;
    memcpy(wsMultiplayerPresetRoot, ansi, (size_t)bytes);
    return 1;
}

static int wsLockMultiplayerPresetFolder(const char *path)
{
    if (wsMultiplayerPresetFolderHandle != INVALID_HANDLE_VALUE)
        return 1;
    HANDLE directory = CreateFileA(path, FILE_READ_ATTRIBUTES, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL,
        OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, NULL);
    if (!wsMultiplayerPresetDirectoryHandle(directory)) {
        if (directory != INVALID_HANDLE_VALUE)
            CloseHandle(directory);
        return 0;
    }
    wsMultiplayerPresetFolderHandle = directory;
    return 1;
}

#define WS_MULTIPLAYER_VISIBILITY_CHOICES 3

#ifndef WS_MP_INDIVIDUAL_DISASTERS
#define WS_MP_INDIVIDUAL_DISASTERS 0
#endif

#define WS_MP_FIRE_PLAGUE_MASK 0x03u
#define WS_MP_WEATHER_DISASTER_MASK 0x1cu

#ifdef WS_MP_STOCK_AI
__declspec(dllexport) uint32_t WINAPI WorldSettingsMultiplayerStockAICapacity(void)
{
    return 3;
}
#endif

#ifdef WS_MP_POPULATED_FACTIONS
__declspec(dllexport) uint32_t WINAPI WorldSettingsMultiplayerFactionMask(void)
{
    return 3;
}
#endif

#ifdef WS_MP_FACTION_ACTIVITY
__declspec(dllexport) uint32_t WINAPI WorldSettingsMultiplayerFactionFrequency(void)
{
    return 1;
}
#endif

static const char wsMultiplayerCultureCapacityMessage[] =
    "The native world supports up to 21 culture towns. Choose fewer islands or regenerate.";

#ifdef WS_MP_POPULATED_CULTURES
__declspec(dllexport) uint32_t WINAPI WorldSettingsMultiplayerCultureCapacity(void)
{
    return 21;
}
#endif

static int wsMultiplayerCultureCapacity(const WSPlanIsland *islands, uint32_t count)
{
#ifdef WS_MP_POPULATED_CULTURES
    if (count > 128)
        return 0;
    uint32_t towns = 0;
    for (uint32_t i = 0; i < count; ++i)
        towns += islands[i].cultures != 0;
    return towns <= WorldSettingsMultiplayerCultureCapacity();
#else
    (void)islands;
    (void)count;
    return 1;
#endif
}

static int wsMultiplayerOptionsSupported(const WSSettings *settings, int headlessStartPlan)
{
    int worldSize = settings->worldSize;
    int supportedSize = worldSize == 256 || worldSize == 512 || worldSize == 1024;
#ifdef WS_MP_HUGE_MATCHES
    supportedSize = supportedSize || (wsMultiplayerStartLayout && worldSize == 2048);
    (void)headlessStartPlan;
#elif defined(WS_MP_HUGE_PLANNING)
    supportedSize = supportedSize || (headlessStartPlan && worldSize == 2048);
#else
    (void)headlessStartPlan;
#endif
    return supportedSize &&
        (uint32_t)settings->difficulty <= 2 &&
#ifdef WS_MP_STOCK_AI
        (uint32_t)settings->aiCount <= WorldSettingsMultiplayerStockAICapacity() &&
#else
        settings->aiCount == 0 &&
#endif
#ifdef WS_MP_PEACEFUL_AI
        (uint32_t)settings->aiDifficulty <= 1u &&
#else
        settings->aiDifficulty == 1 &&
#endif
#ifdef WS_MP_POPULATED_CULTURES
        (settings->cultures & ~255u) == 0 &&
#else
        settings->cultures == 0 &&
#endif
#ifdef WS_MP_POPULATED_FACTIONS
        (settings->factions & ~WorldSettingsMultiplayerFactionMask()) == 0 &&
#else
        settings->factions == 0 &&
#endif
        (wsMultiplayerStartLayout || (settings->startClimate == -1 && settings->startIsland == -1 &&
                                     settings->fairStarts == 0 && settings->startSeparation == 1)) &&
#ifdef WS_MULTIPLAYER_VISIBILITY
        (settings->mapVisibility >= 0 && settings->mapVisibility <= 2) &&
        (settings->enemyVisibility >= 0 && settings->enemyVisibility <= 1) &&
#else
        settings->mapVisibility == 1 && settings->enemyVisibility == 0 &&
#endif
#ifdef WS_MP_FACTION_ACTIVITY
        settings->pirateStrength == 1 &&
        (uint32_t)settings->pirateFrequency <= 2 && (uint32_t)settings->merchantFrequency <= 2 &&
#else
        settings->pirateFrequency == 1 && settings->pirateStrength == 1 &&
        settings->merchantFrequency == 1 &&
#endif
        (settings->disasters == 0 || settings->disasters == 1) &&
        (WS_MP_INDIVIDUAL_DISASTERS ||
         ((settings->disasterMask == 0 || settings->disasterMask == WS_MP_FIRE_PLAGUE_MASK ||
           settings->disasterMask == WS_MP_WEATHER_DISASTER_MASK || settings->disasterMask == 31u) &&
          settings->disasterFrequency == 341 && settings->disasterSeverity == 341));
}

static void wsMultiplayerPreviewControls(DialogState *dialogState)
{
    if (!dialogState->multiplayerPreview)
        return;

    static const int unavailable[] = {
#ifndef WS_MP_STOCK_AI
        ID_AI,
#endif
#ifndef WS_MP_PEACEFUL_AI
        ID_AI_DIFFICULTY,
#endif
#ifdef WS_MP_FACTION_ACTIVITY
        ID_PIRATE_STRENGTH,
#else
        ID_PIRATE_FREQUENCY, ID_PIRATE_STRENGTH,
        ID_MERCHANT_FREQUENCY,
#endif
#ifndef WS_MULTIPLAYER_VISIBILITY
        ID_MAP_VISIBILITY, ID_ENEMY_VISIBILITY,
#endif
    };
    const HWND window = dialogState->window;
#ifdef WS_MP_PEACEFUL_AI
    const LRESULT selectedAI = SendDlgItemMessageA(window, ID_AI_DIFFICULTY, CB_GETCURSEL, 0, 0);
    if (SendDlgItemMessageA(window, ID_AI_DIFFICULTY, CB_GETCOUNT, 0, 0) > 2) {
        SendDlgItemMessageA(window, ID_AI_DIFFICULTY, CB_RESETCONTENT, 0, 0);
        SendDlgItemMessageA(window, ID_AI_DIFFICULTY, CB_ADDSTRING, 0, (LPARAM)"Peaceful");
        SendDlgItemMessageA(window, ID_AI_DIFFICULTY, CB_ADDSTRING, 0, (LPARAM)"Stock behaviour");
    }
    SendDlgItemMessageA(window, ID_AI_DIFFICULTY, CB_SETCURSEL, selectedAI == 0 ? 0 : 1, 0);
#endif
    for (size_t i = 0; i < sizeof unavailable / sizeof unavailable[0]; ++i)
        EnableWindow(GetDlgItem(window, unavailable[i]), FALSE);
    if (!wsMultiplayerPresetRoot[0]) {
        static const int presetOptions[] = {ID_PRESET_PICK, ID_PRESET_NAME, ID_PRESET_SAVE, ID_PRESET_LOAD};
        for (size_t i = 0; i < sizeof presetOptions / sizeof presetOptions[0]; ++i)
            EnableWindow(GetDlgItem(window, presetOptions[i]), FALSE);
    }
    if (!wsMultiplayerStartLayout) {
        static const int startLayoutOptions[] = {
            ID_START_CLIMATE, ID_CLEAR_START, ID_FAIR_STARTS, ID_START_SEPARATION, ID_USE_ISLAND,
        };
        for (size_t i = 0; i < sizeof startLayoutOptions / sizeof startLayoutOptions[0]; ++i)
            EnableWindow(GetDlgItem(window, startLayoutOptions[i]), FALSE);
    }
#ifndef WS_MP_POPULATED_CULTURES
    for (int i = 0; i < 8; ++i)
        EnableWindow(GetDlgItem(window, ID_CULTURE + i), FALSE);
#endif
#ifndef WS_MP_POPULATED_FACTIONS
    for (int i = 0; i < 2; ++i)
        EnableWindow(GetDlgItem(window, ID_FACTION + i), FALSE);
#endif
}

static int wsCaptureMultiplayerPreview(const DialogState *dialogState)
{
    if (!dialogState->multiplayerPreview || !dialogState->previewValid ||
        !dialogState->previewCount || dialogState->previewCount > 128 ||
        !wsMultiplayerCultureCapacity(dialogState->previewIslands, dialogState->previewCount) ||
        !wsMultiplayerOptionsSupported(&dialogState->settings, 0))
        return 0;

    WSPreviewSnapshot snapshot;
    if (WorldSettingsCopyPreviewSnapshot(&snapshot) != sizeof snapshot ||
        snapshot.size != sizeof snapshot || snapshot.state != 1 ||
        snapshot.seed != dialogState->previewSeed || snapshot.count != dialogState->previewCount ||
        memcmp(&snapshot.settings, &dialogState->settings, sizeof snapshot.settings) ||
        memcmp(snapshot.islands, dialogState->previewIslands, snapshot.count * sizeof snapshot.islands[0]))
        return 0;

    *dialogState->multiplayerPreview = snapshot;
    return 1;
}

int WorldSettingsCopyMultiplayerStartTiles(uint32_t *, uint32_t);

static uint32_t wsBuildMultiplayerPreview(
    const WSSettings *settings, uint32_t settingsSize, void *out, uint32_t capacity,
    uint32_t *tiles, uint32_t tileWords, char *error, uint32_t errorCapacity)
{
    if (!settings || settingsSize != sizeof *settings || !out || capacity != sizeof(WSPreviewSnapshot) ||
        (tiles ? tileWords != 12 : tileWords != 0)) {
        message(error, errorCapacity, "The settings differ from the supported multiplayer preview options.");
        return 0;
    }
    if (!wsEnterMultiplayerPreview(tiles != NULL)) {
        message(error, errorCapacity, "A World Settings preview or game is already open in this process.");
        return 0;
    }
    uint32_t size = 0;
    if (!wsMultiplayerOptionsSupported(settings, tiles != NULL))
        message(error, errorCapacity, "The settings differ from the supported multiplayer preview options.");
    else if (WorldSettingsValidateSettings(settings, error, errorCapacity) &&
             WorldSettingsBuildPlan(settings, settings->mapSeed, error, errorCapacity)) {
        size = WorldSettingsCopyPreviewSnapshot(out);
        const WSPreviewSnapshot *snapshot = out;
        if (size && !wsMultiplayerCultureCapacity(snapshot->islands, snapshot->count)) {
            size = 0;
            message(error, errorCapacity, wsMultiplayerCultureCapacityMessage);
        } else if (tiles && !WorldSettingsCopyMultiplayerStartTiles(tiles, tileWords)) {
            size = 0;
            message(error, errorCapacity, "The native starting fleets could not be verified.");
        }
    }
    wsLeaveMultiplayerPreview();
    return size;
}

__declspec(dllexport) uint32_t WINAPI WorldSettingsBuildMultiplayerPreview(
    const WSSettings *settings, uint32_t settingsSize, void *out, uint32_t capacity,
    char *error, uint32_t errorCapacity)
{
    return wsBuildMultiplayerPreview(settings, settingsSize, out, capacity, NULL, 0, error, errorCapacity);
}

__declspec(dllexport) uint32_t WINAPI WorldSettingsBuildMultiplayerStartPlan(
    const WSSettings *settings, uint32_t settingsSize, void *out, uint32_t capacity,
    uint32_t *tiles, uint32_t tileWords, char *error, uint32_t errorCapacity)
{
    if (!tiles)
        return 0;
    return wsBuildMultiplayerPreview(settings, settingsSize, out, capacity, tiles, tileWords, error, errorCapacity);
}
