/* Exact HE World lifetime guard. Include after windows.h and stdint.h.
 * No allocation, CRT, heap walking or game function calls are used.
 * Call once during preparation and again with all other threads paused.
 * Return 0: no World observed; 1: existing World found; -1: incomplete scan.
 * Separately reject any paused RIP in Welt+[21c0,2690), [d1de0,d220b),
 * [d1c60,d1dd4), [e2b80,e2c61) to exclude construction/destruction races.
 * This must run before committing any allocation/grid edits.
 */
static int wsEngineExistingWorld(HMODULE welt, uintptr_t *foundWorld) {
    SYSTEM_INFO info;
    MEMORY_BASIC_INFORMATION region;
    HANDLE process = GetCurrentProcess();
    uintptr_t cursor, last;
    const uintptr_t serverVtable = (uintptr_t)welt + 0xff650u;
    const uintptr_t baseVtable = (uintptr_t)welt + 0xff1d8u;
    union { uint64_t align; unsigned char bytes[65536]; } scratch;
    if (foundWorld) *foundWorld = 0;
    if (!welt) return -1;
    GetSystemInfo(&info);
    cursor = (uintptr_t)info.lpMinimumApplicationAddress;
    last = (uintptr_t)info.lpMaximumApplicationAddress;
    while (cursor < last) {
        uintptr_t start, end, part;
        DWORD protection;
        if (!VirtualQuery((LPCVOID)cursor, &region, sizeof(region))) return -1;
        start = (uintptr_t)region.BaseAddress;
        if (region.RegionSize > last - start) end = last;
        else end = start + region.RegionSize;
        if (end <= cursor) return -1;
        protection = region.Protect & 0xffu;
        if (region.State == MEM_COMMIT && region.Type == MEM_PRIVATE &&
            !(region.Protect & (PAGE_GUARD | PAGE_NOACCESS)) &&
            (protection == PAGE_READWRITE || protection == PAGE_WRITECOPY ||
             protection == PAGE_EXECUTE_READWRITE || protection == PAGE_EXECUTE_WRITECOPY)) {
            for (part = start; part < end;) {
                SIZE_T amount = (SIZE_T)(end - part), got = 0, offset;
                if (amount > sizeof(scratch.bytes)) amount = sizeof(scratch.bytes);
                if (!ReadProcessMemory(process, (LPCVOID)part, scratch.bytes, amount, &got) || got != amount) return -1;
                for (offset = 0; offset + sizeof(uintptr_t) <= amount; offset += sizeof(uintptr_t)) {
                    uintptr_t candidate, vtable = *(const uintptr_t *)(scratch.bytes + offset);
                    struct { uintptr_t self; uint32_t unknown; uint32_t pad; uint32_t width; uint32_t height; } fields;
                    SIZE_T fieldBytes = 0;
                    if (vtable != serverVtable && vtable != baseVtable) continue;
                    candidate = part + offset;
                    if (candidate > last - 0x1e0u) continue;
                    /* +1c8 QWORD self; +1d0 DWORD state/padding; +1d8,+1dc sizes. */
                    if (!ReadProcessMemory(process, (LPCVOID)(candidate + 0x1c8u), &fields, sizeof(fields), &fieldBytes) || fieldBytes != sizeof(fields)) return -1;
                    if (fields.self != candidate) continue;
                    if ((fields.width == 0 && fields.height == 0) ||
                        (fields.width >= 8 && fields.height >= 8 &&
                         fields.width <= 65535u && fields.height <= 65535u &&
                         !(fields.width & 7u) && !(fields.height & 7u))) {
                        if (foundWorld) *foundWorld = candidate;
                        return 1;
                    }
                }
                part += amount;
            }
        }
        cursor = end;
    }
    return 0;
}
