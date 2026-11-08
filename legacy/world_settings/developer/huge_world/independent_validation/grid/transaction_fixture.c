/* Include and exercise the actual dev8 native transaction in owned pages. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>
static uint64_t failProtectMask, failFlushMask;
static unsigned protectCalls, flushCalls;
static int lastResult, lastBefore, lastProtections, lastOutside;
static BOOL WINAPI fixtureProtect(LPVOID address, SIZE_T length, DWORD protection, PDWORD previous) {
    unsigned call = ++protectCalls;
    if (call <= 64 && (failProtectMask & ((uint64_t)1 << (call - 1)))) { SetLastError(ERROR_ACCESS_DENIED); return FALSE; }
    return VirtualProtect(address, length, protection, previous);
}
static BOOL WINAPI fixtureFlush(HANDLE process, LPCVOID address, SIZE_T length) {
    unsigned call = ++flushCalls;
    if (call <= 64 && (failFlushMask & ((uint64_t)1 << (call - 1)))) { SetLastError(ERROR_ACCESS_DENIED); return FALSE; }
    return FlushInstructionCache(process, address, length);
}
#define VirtualProtect fixtureProtect
#define FlushInstructionCache fixtureFlush
#include "transaction_source.inc"
#undef VirtualProtect
#undef FlushInstructionCache
void WorldSettingsSetAILoaderHookReady(int ready) { (void)ready; }

__declspec(dllexport) int transaction_fixture(uint64_t protectMask, uint64_t flushMask, int expected) {
    SYSTEM_INFO info;
    unsigned char *memory;
    WSPatch patches[3];
    WSPage pages[3];
    uint32_t pageCount = 0;
    DWORD temporary;
    SIZE_T size;
    int result, status = 0;
    GetSystemInfo(&info);
    size = (SIZE_T)info.dwPageSize * 2;
    memory = (unsigned char *)VirtualAlloc(0, size, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    if (!memory) return 10;
    memset(memory, 0xa5, size);
    memset(patches, 0, sizeof(patches));
    memset(pages, 0, sizeof(pages));
    const SIZE_T offsets[3] = {0x20, 0x80, (SIZE_T)info.dwPageSize + 0x40};
    for (unsigned i = 0; i < 3; i++) {
        patches[i].address = memory + offsets[i]; patches[i].length = 4;
        memset(patches[i].before, 0xa5, 4); memset(patches[i].after, 0x10 + i, 4);
    }
    if (!wsGroupPages(patches, 3, pages, &pageCount, info.dwPageSize) || pageCount != 2 || patches[0].page != patches[1].page || patches[2].page == patches[0].page) { status = 11; goto done; }
    if (!VirtualProtect(memory, info.dwPageSize, PAGE_EXECUTE_READ, &temporary) || !VirtualProtect(memory + info.dwPageSize, info.dwPageSize, PAGE_READONLY, &temporary)) { status = 12; goto done; }
    protectCalls = 0; flushCalls = 0; failProtectMask = protectMask; failFlushMask = flushMask;
    result = wsApplyPatches(patches, 3, pages, pageCount);
    lastResult = result; lastBefore = 1; lastOutside = 1; lastProtections = 1;
    if (result != expected) { status = 13; goto done; }
    for (SIZE_T index = 0; index < size; index++) {
        int patchIndex = -1;
        for (unsigned p = 0; p < 3; p++) if (index >= offsets[p] && index < offsets[p] + 4) patchIndex = (int)p;
        if (patchIndex < 0) { if (memory[index] != 0xa5) lastOutside = 0; }
        else {
            if (memory[index] != 0xa5) lastBefore = 0;
            if (result == 1 && memory[index] != 0x10 + patchIndex) { status = 14; goto done; }
        }
    }
    if (!lastOutside) { status = 15; goto done; }
    for (unsigned p = 0; p < 2; p++) {
        MEMORY_BASIC_INFORMATION region;
        if (!VirtualQuery(memory + p * info.dwPageSize, &region, sizeof(region))) { status = 16; goto done; }
        if (region.Protect != (p ? PAGE_READONLY : PAGE_EXECUTE_READ)) lastProtections = 0;
    }
    if (result != -1 && (!lastProtections || (result == 0 && !lastBefore))) status = 17;
done:
    failProtectMask = 0; failFlushMask = 0;
    VirtualProtect(memory, size, PAGE_READWRITE, &temporary);
    VirtualFree(memory, 0, MEM_RELEASE);
    return status;
}
__declspec(dllexport) unsigned transaction_protect_calls(void) { return protectCalls; }
__declspec(dllexport) unsigned transaction_flush_calls(void) { return flushCalls; }
__declspec(dllexport) int transaction_last_result(void) { return lastResult; }
__declspec(dllexport) int transaction_before_restored(void) { return lastBefore; }
__declspec(dllexport) int transaction_protections_restored(void) { return lastProtections; }
__declspec(dllexport) int transaction_no_outside_writes(void) { return lastOutside; }

__declspec(dllexport) int transaction_group_rejections(void) {
    WSPatch patches[2]; WSPage pages[2]; uint32_t count;
    memset(patches, 0, sizeof(patches)); memset(pages, 0, sizeof(pages));
    patches[0].address = (unsigned char *)(uintptr_t)0x10000fffu; patches[0].length = 4;
    if (wsGroupPages(patches, 1, pages, &count, 4096)) return 1;
    patches[0].address = (unsigned char *)(uintptr_t)0x10000020u; patches[0].length = 8;
    patches[1].address = (unsigned char *)(uintptr_t)0x10000024u; patches[1].length = 4;
    if (wsGroupPages(patches, 2, pages, &count, 4096)) return 2;
    if (wsGroupPages(patches, 1, pages, &count, 0)) return 3;
    return 0;
}
