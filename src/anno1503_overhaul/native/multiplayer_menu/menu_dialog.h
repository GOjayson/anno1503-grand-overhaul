/* Owned by the verified Anno multiplayer selector. No startup entry point. */
enum { LAN_HOST = 1, LAN_JOIN, INTERNET_HOST, INTERNET_JOIN };
enum { MENU_ROLE = 101, MENU_NAME, MENU_ADDRESS_LABEL, MENU_ADDRESS, MENU_BIND_LABEL, MENU_BIND, MENU_STATUS,
       MENU_WORLD, MENU_BASE, MENU_JOIN_WORLD, MENU_COOP, MENU_PLAYER_COUNT };
enum { MENU_PREVIEW_BYTES = 6016 };
enum { MENU_POLL = 1 };

typedef struct {
    uint32_t action, pid;
    uint64_t creation, owner, dialog;
    char name[32], address[16], bind[16];
    uint32_t preview_only, use_world, preview_size, session_mode;
    unsigned char preview[MENU_PREVIEW_BYTES];
} MenuRequest;

typedef struct {
    uint32_t status, preview_size;
    TrialSettings plan;
    uint64_t scene_size;
    unsigned char scene_digest[32];
    uint32_t map_mode, enemy_mode;
    char message[256];
    unsigned char preview[MENU_PREVIEW_BYTES];
    unsigned char disaster_policy[32];
} MenuResponse;

_Static_assert(sizeof(MenuRequest) == 6128 && sizeof(MenuResponse) == 6840, "Menu IPC layout");

typedef struct {
    unsigned action;
    HWND owner;
    HANDLE worker, results;
    ULONGLONG deadline;
    unsigned int wants_player_count;
    bool companion, previewing, wants_world, wants_co_op, has_preview;
    unsigned char preview[MENU_PREVIEW_BYTES];
    MenuResponse reply;
} MenuDialog;

#include "menu_world.h"
#include "menu_lifecycle.h"

static void close_menu_worker(MenuDialog *menu)
{
    if (menu->worker) {
        if (WaitForSingleObject(menu->worker, 0) == WAIT_TIMEOUT)
            TerminateProcess(menu->worker, ERROR_CANCELLED);
        CloseHandle(menu->worker);
        CloseHandle(menu->results);
        menu->worker = NULL;
        menu->results = NULL;
    }
}

static bool start_menu_worker(MenuDialog *menu, const MenuRequest *request)
{
    static const WCHAR worker[] = L"AnnoGrandMenuWorker.exe";
    WCHAR directory[MAX_PATH], application[MAX_PATH];
    DWORD length = GetModuleFileNameW(NULL, directory, ARRAYSIZE(directory));
    if (!length || length >= ARRAYSIZE(directory))
        return false;
    while (length && directory[length - 1] != L'\\')
        --length;
    if (!length || length + ARRAYSIZE(worker) > ARRAYSIZE(application))
        return false;
    directory[length] = 0;
    memcpy(application, directory, length * sizeof(WCHAR));
    memcpy(application + length, worker, sizeof worker);
    HANDLE image = CreateFileW(application, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                               FILE_FLAG_OPEN_REPARSE_POINT, NULL);
    if (image == INVALID_HANDLE_VALUE)
        return false;

    SECURITY_ATTRIBUTES inheritable = {sizeof inheritable, NULL, TRUE};
    HANDLE input_read = NULL, input_write = NULL, output_read = NULL, output_write = NULL;
    HANDLE errors = CreateFileW(L"NUL", GENERIC_WRITE, FILE_SHARE_WRITE, &inheritable, OPEN_EXISTING, 0, NULL);
    STARTUPINFOEXW startup = {0};
    PROCESS_INFORMATION process = {0};
    BY_HANDLE_FILE_INFORMATION info;
    SIZE_T bytes = 0;
    bool attribute_initialized = false;
    bool started = errors != INVALID_HANDLE_VALUE && GetFileInformationByHandle(image, &info) &&
        !(info.dwFileAttributes & (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT)) &&
        CreatePipe(&input_read, &input_write, &inheritable, sizeof *request) &&
        CreatePipe(&output_read, &output_write, &inheritable, sizeof(MenuResponse)) &&
        SetHandleInformation(input_write, HANDLE_FLAG_INHERIT, 0) &&
        SetHandleInformation(output_read, HANDLE_FLAG_INHERIT, 0);
    if (started) {
        InitializeProcThreadAttributeList(NULL, 1, 0, &bytes);
        startup.lpAttributeList = HeapAlloc(GetProcessHeap(), 0, bytes);
        attribute_initialized = startup.lpAttributeList &&
            InitializeProcThreadAttributeList(startup.lpAttributeList, 1, 0, &bytes);
        HANDLE children[] = {input_read, output_write, errors};
        startup.StartupInfo.cb = sizeof startup;
        startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES;
        startup.StartupInfo.hStdInput = input_read;
        startup.StartupInfo.hStdOutput = output_write;
        startup.StartupInfo.hStdError = errors;
        started = attribute_initialized && UpdateProcThreadAttribute(startup.lpAttributeList, 0,
            PROC_THREAD_ATTRIBUTE_HANDLE_LIST, children, sizeof children, NULL, NULL) &&
            CreateProcessW(application, NULL, NULL, NULL, TRUE, EXTENDED_STARTUPINFO_PRESENT | CREATE_NO_WINDOW,
                           NULL, directory, &startup.StartupInfo, &process);
    }
    if (attribute_initialized)
        DeleteProcThreadAttributeList(startup.lpAttributeList);
    if (startup.lpAttributeList)
        HeapFree(GetProcessHeap(), 0, startup.lpAttributeList);
    CloseHandle(image);
    if (errors != INVALID_HANDLE_VALUE) CloseHandle(errors);
    if (input_read) CloseHandle(input_read);
    if (output_write) CloseHandle(output_write);
    if (started) {
        CloseHandle(process.hThread);
        menu->worker = process.hProcess;
        menu->results = output_read;
        DWORD written = 0;
        started = WriteFile(input_write, request, sizeof *request, &written, NULL) && written == sizeof *request;
        if (!started)
            close_menu_worker(menu);
    } else if (output_read) {
        CloseHandle(output_read);
    }
    if (input_write) CloseHandle(input_write);
    return started;
}

static HWND menu_control(HWND window, const WCHAR *class_name, const WCHAR *text,
                         DWORD style, int x, int y, int width, int height, int id)
{
    RECT rect = {x, y, x + width, y + height};
    MapDialogRect(window, &rect);
    HWND control = CreateWindowExW(0, class_name, text, style | WS_CHILD | WS_VISIBLE,
        rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top,
        window, (HMENU)(INT_PTR)id, GetModuleHandleW(NULL), NULL);
    if (control)
        SendMessageW(control, WM_SETFONT, (WPARAM)GetStockObject(DEFAULT_GUI_FONT), FALSE);
    return control;
}

static unsigned menu_action(HWND window, const MenuDialog *menu)
{
    if (menu->action != INTERNET_HOST)
        return menu->action;
    return SendDlgItemMessageW(window, MENU_ROLE, CB_GETCURSEL, 0, 0) == 0 ? INTERNET_HOST : INTERNET_JOIN;
}

static bool menu_hosting(unsigned action)
{
    return action == LAN_HOST || action == INTERNET_HOST;
}

static unsigned int menu_player_count(HWND window)
{
    const LRESULT selected = SendDlgItemMessageW(window, MENU_PLAYER_COUNT, CB_GETCURSEL, 0, 0);
    return selected >= 0 && selected <= 6 ? (unsigned int)selected + 2u : 2u;
}

static void menu_labels(HWND window, const MenuDialog *menu)
{
    const unsigned action = menu_action(window, menu);
    SetDlgItemTextW(window, MENU_ADDRESS_LABEL, action == INTERNET_HOST ? L"Public IPv4 address" : L"Host IPv4 address");
    EnableWindow(GetDlgItem(window, MENU_ADDRESS), action != LAN_HOST);
    SetDlgItemTextW(window, MENU_BIND_LABEL, action == LAN_HOST || action == INTERNET_HOST ?
        L"Local IPv4 address" : L"Local IPv4 address (optional)");
    const bool hosting = menu_hosting(action);
    SetDlgItemTextW(window, IDOK, hosting ? L"Host game" : L"Join game");
    if (menu->companion) {
        ShowWindow(GetDlgItem(window, MENU_WORLD), hosting ? SW_SHOW : SW_HIDE);
        ShowWindow(GetDlgItem(window, MENU_BASE), hosting && menu->has_preview ? SW_SHOW : SW_HIDE);
        ShowWindow(GetDlgItem(window, MENU_JOIN_WORLD), hosting ? SW_HIDE : SW_SHOW);
    }
    const HWND co_op = GetDlgItem(window, MENU_COOP);
    if (co_op) {
        const bool available = menu_player_count(window) == 2;
        if (!available)
            SendMessageW(co_op, BM_SETCHECK, BST_UNCHECKED, 0);
        EnableWindow(co_op, available);
    }
}

static bool menu_text(HWND window, int id, char *out, size_t capacity)
{
    WCHAR value[32];
    if (GetWindowTextLengthW(GetDlgItem(window, id)) >= (int)capacity)
        return false;
    const unsigned length = GetDlgItemTextW(window, id, value, (int)capacity);
    for (unsigned index = 0; index < length; ++index) {
        if (value[index] < 32 || value[index] > 126)
            return false;
        out[index] = (char)value[index];
    }
    return true;
}

static void menu_busy(HWND window, bool busy)
{
    static const int widgets[] = {MENU_ROLE, MENU_NAME, MENU_ADDRESS, MENU_BIND, MENU_WORLD, MENU_BASE,
                                  MENU_JOIN_WORLD, MENU_COOP, MENU_PLAYER_COUNT, IDOK};
    for (size_t index = 0; index < ARRAYSIZE(widgets); ++index)
        EnableWindow(GetDlgItem(window, widgets[index]), !busy);
}

static void menu_submit(HWND window, MenuDialog *menu, bool previewing)
{
    if (menu->worker)
        return;
    MenuRequest request = {0};
    FILETIME created, exit_time, kernel, user;
    request.action = menu_action(window, menu);
    request.pid = GetCurrentProcessId();
    request.owner = (UINT_PTR)menu->owner;
    request.dialog = (UINT_PTR)window;
    const bool hosting = menu_hosting(request.action);
    if (previewing && !(menu->companion && hosting))
        return;
    request.preview_only = previewing;
    request.use_world = menu->companion && (hosting ? previewing || menu->has_preview :
        SendDlgItemMessageW(window, MENU_JOIN_WORLD, BM_GETCHECK, 0, 0) == BST_CHECKED);
    const unsigned int count = previewing ? 2u : menu_player_count(window);
    const bool co_op = !previewing && count == 2u &&
        SendDlgItemMessageW(window, MENU_COOP, BM_GETCHECK, 0, 0) == BST_CHECKED;
    request.session_mode = count > 2u ? count : (unsigned int)co_op;
    if (count > 4u && !request.use_world) {
        SetDlgItemTextW(window, MENU_STATUS, L"Five to eight players require a generated World Settings map.");
        return;
    }
    if (hosting && request.use_world && !previewing) {
        request.preview_size = MENU_PREVIEW_BYTES;
        memcpy(request.preview, menu->preview, sizeof request.preview);
    }
    if (!GetProcessTimes(GetCurrentProcess(), &created, &exit_time, &kernel, &user) ||
        !menu_text(window, MENU_NAME, request.name, sizeof request.name) ||
        (!previewing && request.action != LAN_HOST &&
         (!menu_text(window, MENU_ADDRESS, request.address, sizeof request.address) || !request.address[0])) ||
        !menu_text(window, MENU_BIND, request.bind, sizeof request.bind)) {
        SetDlgItemTextW(window, MENU_STATUS, L"Enter valid IPv4 addresses and a printable player name.");
        return;
    }
    request.creation = ((uint64_t)created.dwHighDateTime << 32) | created.dwLowDateTime;
    if (!SetTimer(window, MENU_POLL, 80, NULL) || !start_menu_worker(menu, &request)) {
        KillTimer(window, MENU_POLL);
        SetDlgItemTextW(window, MENU_STATUS, L"The multiplayer worker could not start.");
        return;
    }
    menu->previewing = previewing;
    menu->wants_world = request.use_world;
    menu->wants_co_op = co_op;
    menu->wants_player_count = count;
    menu->deadline = GetTickCount64() + (previewing ? 600000 : count > 2u ? 200000 : 90000);
    menu_busy(window, true);
    SetDlgItemTextW(window, MENU_STATUS, previewing ? L"Opening World Settings…" :
        count > 2u ? L"Waiting for all players to pair…" :
        hosting ? L"Waiting for a player to join…" : L"Checking the host…");
}

static void menu_poll(HWND window, MenuDialog *menu)
{
    MenuResponse reply = {0};
    DWORD available = 0, received = 0;
    const bool running = WaitForSingleObject(menu->worker, 0) == WAIT_TIMEOUT;
    const bool open = PeekNamedPipe(menu->results, NULL, 0, NULL, &available, NULL);
    if (running && open && available < sizeof reply && GetTickCount64() < menu->deadline)
        return;
    const bool complete = open && available == sizeof reply &&
        ReadFile(menu->results, &reply, sizeof reply, &received, NULL) && received == sizeof reply;
    const unsigned action = menu_action(window, menu);
    const unsigned expected = menu_hosting(action) ? TRIAL_HOST : TRIAL_GUEST;
    KillTimer(window, MENU_POLL);
    close_menu_worker(menu);
    if (complete && menu->previewing && (reply.status == 2 ||
            (reply.status == 0 && reply.preview_size == MENU_PREVIEW_BYTES))) {
        if (reply.status == 0) {
            memcpy(menu->preview, reply.preview, sizeof menu->preview);
            menu->has_preview = true;
        }
        menu_busy(window, false);
        menu_labels(window, menu);
        SetDlgItemTextW(window, MENU_STATUS, menu->has_preview ?
            L"Custom map ready. Choose New Earth after pairing." : L"");
        return;
    }
    if (complete && !menu->previewing && reply.status == 0 && !reply.preview_size &&
        reply.plan.role == expected && menu_room_valid_plan(&reply.plan) &&
        reply.plan.player_count == menu->wants_player_count &&
        menu->wants_co_op == menu_coop_plan(&reply.plan) &&
        menu->wants_world == (reply.scene_size != 0)) {
        menu->reply = reply;
        EndDialog(window, IDOK);
        return;
    }
    menu_busy(window, false);
    menu_labels(window, menu);
    WCHAR message[256];
    reply.message[sizeof reply.message - 1] = 0;
    if (complete && reply.status == 1 && reply.message[0] &&
        MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, reply.message, -1, message, ARRAYSIZE(message)))
        SetDlgItemTextW(window, MENU_STATUS, message);
    else
        SetDlgItemTextW(window, MENU_STATUS, L"No compatible player connected. Try again.");
}

static INT_PTR CALLBACK multiplayer_dialog(HWND window, UINT message, WPARAM wparam, LPARAM lparam)
{
    MenuDialog *menu = (MenuDialog *)GetWindowLongPtrW(window, DWLP_USER);
    switch (message) {
    case WM_INITDIALOG: {
        menu = (MenuDialog *)lparam;
        SetWindowLongPtrW(window, DWLP_USER, (LONG_PTR)menu);
        SetWindowTextW(window, menu->action == LAN_HOST ? L"LAN Server" :
            menu->action == LAN_JOIN ? L"LAN Client" : L"Internet multiplayer");
        int y = 12;
        if (menu->action == INTERNET_HOST) {
            HWND role = menu_control(window, L"COMBOBOX", L"", WS_TABSTOP | CBS_DROPDOWNLIST, 12, y, 216, 45, MENU_ROLE);
            SendMessageW(role, CB_ADDSTRING, 0, (LPARAM)L"Host");
            SendMessageW(role, CB_ADDSTRING, 0, (LPARAM)L"Join");
            SendMessageW(role, CB_SETCURSEL, 0, 0);
            y += 23;
        }
        menu_control(window, L"STATIC", L"Player name (leave blank to use your saved name)", 0, 12, y, 216, 12, -1);
        menu_control(window, L"EDIT", L"", WS_BORDER | WS_TABSTOP | ES_AUTOHSCROLL, 12, y + 12, 216, 15, MENU_NAME);
        SendDlgItemMessageW(window, MENU_NAME, EM_SETLIMITTEXT, 31, 0);
        y += 32;
        if (menu->action != LAN_HOST) {
            menu_control(window, L"STATIC", L"", 0, 12, y, 216, 12, MENU_ADDRESS_LABEL);
            menu_control(window, L"EDIT", L"", WS_BORDER | WS_TABSTOP | ES_AUTOHSCROLL, 12, y + 12, 216, 15, MENU_ADDRESS);
            SendDlgItemMessageW(window, MENU_ADDRESS, EM_SETLIMITTEXT, 15, 0);
            y += 32;
        }
        menu_control(window, L"STATIC", L"", 0, 12, y, 216, 12, MENU_BIND_LABEL);
        menu_control(window, L"EDIT", L"", WS_BORDER | WS_TABSTOP | ES_AUTOHSCROLL, 12, y + 12, 216, 15, MENU_BIND);
        SendDlgItemMessageW(window, MENU_BIND, EM_SETLIMITTEXT, 15, 0);
        y += 34;
        menu_control(window, L"STATIC", L"Players (including host)", 0, 12, y + 2, 150, 12, -1);
        HWND count = menu_control(window, L"COMBOBOX", L"", WS_TABSTOP | CBS_DROPDOWNLIST,
                                  174, y, 54, 100, MENU_PLAYER_COUNT);
        for (unsigned int players = 2; players <= (menu->companion ? 8u : 4u); ++players) {
            const WCHAR label[] = {(WCHAR)(L'0' + players), 0};
            SendMessageW(count, CB_ADDSTRING, 0, (LPARAM)label);
        }
        SendMessageW(count, CB_SETCURSEL, 0, 0);
        y += 24;
        menu_control(window, L"BUTTON", L"Share the host’s flag (co-op)", WS_TABSTOP | BS_AUTOCHECKBOX,
                     12, y, 216, 16, MENU_COOP);
        y += 21;
        if (menu->companion) {
            menu_control(window, L"BUTTON", L"World Settings…", WS_TABSTOP, 12, y, 102, 16, MENU_WORLD);
            menu_control(window, L"BUTTON", L"Use base game maps", WS_TABSTOP, 122, y, 106, 16, MENU_BASE);
            menu_control(window, L"BUTTON", L"Join a World Settings map", WS_TABSTOP | BS_AUTOCHECKBOX,
                         12, y, 216, 16, MENU_JOIN_WORLD);
            y += 26;
        }
        menu_control(window, L"STATIC", L"", 0, 12, y, 216, 28, MENU_STATUS);
        menu_control(window, L"BUTTON", L"", WS_TABSTOP | BS_DEFPUSHBUTTON, 100, y + 32, 60, 16, IDOK);
        menu_control(window, L"BUTTON", L"Back", WS_TABSTOP | BS_PUSHBUTTON, 168, y + 32, 60, 16, IDCANCEL);
        menu_labels(window, menu);
        SetFocus(GetDlgItem(window, MENU_NAME));
        SendDlgItemMessageW(window, MENU_NAME, EM_SETSEL, 0, -1);
        return FALSE;
    }
    case WM_COMMAND:
        if (LOWORD(wparam) == IDOK) menu_submit(window, menu, false);
        else if (LOWORD(wparam) == MENU_WORLD) menu_submit(window, menu, true);
        else if (LOWORD(wparam) == MENU_BASE && !menu->worker) {
            menu->has_preview = false;
            menu_labels(window, menu);
            SetDlgItemTextW(window, MENU_STATUS, L"");
        }
        else if (LOWORD(wparam) == IDCANCEL) EndDialog(window, IDCANCEL);
        else if (LOWORD(wparam) == MENU_ROLE && HIWORD(wparam) == CBN_SELCHANGE) menu_labels(window, menu);
        else if (LOWORD(wparam) == MENU_PLAYER_COUNT && HIWORD(wparam) == CBN_SELCHANGE) {
            menu_labels(window, menu);
            SetDlgItemTextW(window, MENU_STATUS, menu_player_count(window) > 2 ?
                L"Choose the same player count on every PC." : L"");
        }
        else if (LOWORD(wparam) == MENU_COOP)
            SetDlgItemTextW(window, MENU_STATUS,
                SendDlgItemMessageW(window, MENU_COOP, BM_GETCHECK, 0, 0) == BST_CHECKED ?
                    L"Enable co-op on both PCs. The host picks one flag for both players." : L"");
        else return FALSE;
        return TRUE;
    case WM_TIMER:
        if (wparam == MENU_POLL && menu->worker) menu_poll(window, menu);
        return TRUE;
    case WM_CLOSE:
        EndDialog(window, IDCANCEL);
        return TRUE;
    case WM_DESTROY:
        if (menu) close_menu_worker(menu);
        return TRUE;
    }
    return FALSE;
}

static bool menu_selector(unsigned char *frame, unsigned char *selector, HWND window)
{
    return frame && selector && window && direct_mode() &&
        (void *)GetWindowLongPtrW(window, GWLP_USERDATA) == selector &&
        *(void **)selector == frame + 0xa4810 && *(const HWND *)(selector + 0x2220) == window &&
        !*(void **)(frame + CLIENT_GLOBAL) && !*(void **)(frame + SERVER_GLOBAL);
}

static void open_multiplayer_menu(unsigned char *selector, unsigned action)
{
    static bool active;
    unsigned char *frame = (unsigned char *)GetModuleHandleW(L"AnnoFrame.dll");
    if (active || !frame || !selector || *(void **)selector != frame + 0xa4810)
        return;
    HWND owner = *(const HWND *)(selector + 0x2220);
    if (!menu_selector(frame, selector, owner))
        return;
    if (!menu_restore_huge()) {
        MessageBoxW(owner, L"The previous Huge world is still closing. Return to the main menu before joining another match.",
                    L"World Settings", MB_OK | MB_ICONINFORMATION);
        return;
    }
    _Alignas(DWORD) struct {
        DLGTEMPLATE dialog;
        WORD menu, class_name, title;
    } definition = {0};
    definition.dialog.style = WS_POPUP | WS_CAPTION | WS_SYSMENU | DS_MODALFRAME | DS_CENTER;
    definition.dialog.cx = 240;
    MenuDialog menu = {.action = action, .owner = owner, .companion = menu_has_world_settings()};
    definition.dialog.cy = (action == LAN_HOST ? 180 : action == LAN_JOIN ? 212 : 235) + (menu.companion ? 26 : 0);
    active = true;
    menu_set_plan(NULL);
    menu_clear_world();
    const INT_PTR selected = DialogBoxIndirectParamW(GetModuleHandleW(NULL), &definition.dialog,
        owner, multiplayer_dialog, (LPARAM)&menu);
    if (selected == IDOK && menu_selector(frame, selector, owner)) {
        if (!menu_arm_world(&menu.reply)) {
            MessageBoxW(owner, L"The agreed World Settings map or view settings could not be opened.",
                        L"World Settings", MB_OK | MB_ICONERROR);
        } else {
            menu_set_plan(&menu.reply.plan);
            const unsigned callback = menu.reply.plan.role == TRIAL_HOST ? 0x50330 : 0x50490;
            ((void (*)(unsigned char *))(frame + callback))(selector);
            anno_menu_clear_closed_session(frame);
        }
    }
    active = false;
}

__declspec(dllexport) void AnnoTrialInternetMenu(unsigned char *selector)
{
    open_multiplayer_menu(selector, INTERNET_HOST);
}

__declspec(dllexport) void AnnoMenuLanServer(unsigned char *selector)
{
    open_multiplayer_menu(selector, LAN_HOST);
}

__declspec(dllexport) void AnnoMenuLanClient(unsigned char *selector)
{
    open_multiplayer_menu(selector, LAN_JOIN);
}
