/* Native Frame teardown sites retire the local generated-world activation. */
enum {
    MENU_LIFECYCLE_STOCK_DIAGNOSTIC = 0x9e078,
    MENU_LIFECYCLE_STOCK_CANCELLED = 0xc6c82,
    MENU_LIFECYCLE_PENDING = 0x2210,
    MENU_LIFECYCLE_RUNNING = 0x2218,
};

static void anno_menu_clear_closed_session(const unsigned char *frame)
{
    if (frame && !*(void *const *)(frame + CLIENT_GLOBAL) && !*(void *const *)(frame + SERVER_GLOBAL)) {
        const DWORD error = GetLastError();
        menu_set_plan(NULL);
        menu_clear_world();
        (void)menu_restore_huge();
        SetLastError(error);
    }
}

static void anno_menu_finish_cancel(unsigned char *startup, unsigned char *frame, uint32_t pending)
{
    if (pending)
        ((volatile unsigned char *)startup)[MENU_LIFECYCLE_RUNNING] = 0;
    *(volatile uint32_t *)(startup + MENU_LIFECYCLE_PENDING) = pending;
    if (!pending) {
        if (frame)
            ((volatile unsigned char *)frame)[MENU_LIFECYCLE_STOCK_CANCELLED] = 0;
        ((volatile unsigned char *)startup)[MENU_LIFECYCLE_RUNNING] = 0;
    }
    anno_menu_clear_closed_session(frame);
}

__declspec(dllexport) void AnnoMenuFinishQuit(unsigned char *startup)
{
    anno_menu_finish_cancel(startup, (unsigned char *)GetModuleHandleW(L"AnnoFrame.dll"), 1);
}

__declspec(dllexport) void AnnoMenuFinishBack(unsigned char *startup)
{
    anno_menu_finish_cancel(startup, (unsigned char *)GetModuleHandleW(L"AnnoFrame.dll"), 0);
}

__declspec(dllexport) void AnnoMenuFinishMatch(const char *message)
{
    unsigned char *frame = (unsigned char *)GetModuleHandleW(L"AnnoFrame.dll");
    if (frame) {
        void (*diagnostic)(const char *) = *(void (**)(const char *))(frame + MENU_LIFECYCLE_STOCK_DIAGNOSTIC);
        diagnostic(message);
        anno_menu_clear_closed_session(frame);
    }
}
