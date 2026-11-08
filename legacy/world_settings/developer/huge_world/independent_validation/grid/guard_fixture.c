#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "existing_world_guard.inc"

__declspec(dllexport) int test_existing_world_guard(void) {
    uintptr_t found = 0;
    HMODULE fakeModule = (HMODULE)(uintptr_t)0x10000000u;
    unsigned char *world;
    int rc;
    if (wsEngineExistingWorld(fakeModule, &found) != 0 || found != 0) return 1;
    world = (unsigned char *)VirtualAlloc(0, 0x20000u, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    if (!world) return 2;
    *(uintptr_t *)world = (uintptr_t)fakeModule + 0xff650u;
    *(uintptr_t *)(world + 0x1c8u) = (uintptr_t)world;
    *(uint32_t *)(world + 0x1d8u) = 2048;
    *(uint32_t *)(world + 0x1dcu) = 2048;
    rc = wsEngineExistingWorld(fakeModule, &found);
    if (rc != 1 || found != (uintptr_t)world) return 3;
    *(uintptr_t *)world = (uintptr_t)fakeModule + 0xff1d8u;
    *(uint32_t *)(world + 0x1d8u) = 0;
    *(uint32_t *)(world + 0x1dcu) = 0;
    if (wsEngineExistingWorld(fakeModule, &found) != 1 || found != (uintptr_t)world) return 4;
    *(uintptr_t *)(world + 0x1c8u) = 0;
    if (wsEngineExistingWorld(fakeModule, &found) != 0) return 5;
    *(uintptr_t *)(world + 0x1c8u) = (uintptr_t)world;
    *(uint32_t *)(world + 0x1d8u) = 1024;
    *(uint32_t *)(world + 0x1dcu) = 512;
    if (wsEngineExistingWorld(fakeModule, &found) != 1) return 6;
    if (!VirtualFree(world, 0, MEM_RELEASE)) return 7;
    if (wsEngineExistingWorld(fakeModule, &found) != 0 || found != 0) return 8;
    return 0;
}
