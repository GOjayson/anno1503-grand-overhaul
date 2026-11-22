/* Keep every generated standalone island immutable while its New Earth link is active. */
enum { ANNO_SCENE_MAX_ISLANDS = 128, ANNO_SCENE_LINK_SIZE = 84 };

typedef struct {
    HANDLE files[ANNO_SCENE_MAX_ISLANDS];
    size_t count;
    DWORD world_width;
} SceneIslandAssets;

static void anno_release_scene_islands(SceneIslandAssets *assets)
{
    while (assets->count)
        CloseHandle(assets->files[--assets->count]);
}

static bool anno_scene_read_at(HANDLE scene, DWORD offset, void *data, DWORD bytes)
{
    const LARGE_INTEGER position = {.QuadPart = offset};
    DWORD count = 0;
    return SetFilePointerEx(scene, position, NULL, FILE_BEGIN) &&
        ReadFile(scene, data, bytes, &count, NULL) && count == bytes;
}

static int anno_scene_hex(unsigned char digit)
{
    if (digit >= '0' && digit <= '9')
        return digit - '0';
    if (digit >= 'a' && digit <= 'f')
        return digit - 'a' + 10;
    return -1;
}

static HANDLE anno_open_scene_island(const WCHAR *executable, size_t root, const unsigned char link[ANNO_SCENE_LINK_SIZE])
{
    static const WCHAR folder[] = L"\\Scenes\\WS\\";
    if (root + ARRAYSIZE(folder) - 1 + 69 > MAX_PATH || memcmp(link + 79, ".scp", 5) != 0)
        return INVALID_HANDLE_VALUE;
    WCHAR path[MAX_PATH], final[MAX_PATH + 4];
    unsigned char digest[32];
    memcpy(path, executable, root * sizeof(WCHAR));
    memcpy(path + root, folder, (ARRAYSIZE(folder) - 1) * sizeof(WCHAR));
    WCHAR *name = path + root + ARRAYSIZE(folder) - 1;
    for (size_t index = 0; index < 32; ++index) {
        const unsigned char first = link[15 + index * 2], second = link[16 + index * 2];
        const int high = anno_scene_hex(first), low = anno_scene_hex(second);
        if (high < 0 || low < 0)
            return INVALID_HANDLE_VALUE;
        name[index * 2] = first;
        name[index * 2 + 1] = second;
        digest[index] = (unsigned char)((high << 4) | low);
    }
    memcpy(name + 64, L".scp", sizeof L".scp");
    HANDLE file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
        FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_SEQUENTIAL_SCAN, NULL);
    if (file == INVALID_HANDLE_VALUE)
        return file;
    const DWORD length = GetFinalPathNameByHandleW(file, final, ARRAYSIZE(final), FILE_NAME_NORMALIZED | VOLUME_NAME_DOS);
    BY_HANDLE_FILE_INFORMATION info;
    if (length > 4 && length < ARRAYSIZE(final) &&
        wcsncmp(final, anno_shadow_extended_prefix, 4) == 0 && anno_shadow_equal_path(final + 4, path) &&
        GetFileInformationByHandle(file, &info) && info.nNumberOfLinks == 1 && !info.nFileSizeHigh &&
        info.nFileSizeLow && info.nFileSizeLow <= ANNO_SHADOW_MAX_BYTES &&
        !(info.dwFileAttributes & (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT)) &&
        anno_shadow_digest(file, info.nFileSizeLow, digest))
        return file;
    CloseHandle(file);
    return INVALID_HANDLE_VALUE;
}

static bool anno_hold_scene_islands(HANDLE scene, DWORD size, const WCHAR *executable, size_t root,
    SceneIslandAssets *assets)
{
    typedef struct {
        char id[12];
        DWORD length;
    } SceneChunk;
    _Static_assert(sizeof(SceneChunk) == 16, "Native scene chunk size");
    SceneChunk envelope[2];
    if (size < sizeof envelope || !anno_scene_read_at(scene, 0, envelope, sizeof envelope) ||
        memcmp(envelope[0].id, "ANNO\0\0\0\0\0\0\0", 12) != 0 || envelope[0].length != size - sizeof(SceneChunk) ||
        memcmp(envelope[1].id, "SCENE\0\0\0\0\0\0", 12) != 0 || envelope[1].length != size - sizeof envelope)
        return false;
    for (DWORD offset = sizeof envelope; offset < size;) {
        SceneChunk chunk;
        if (size - offset < sizeof chunk || !anno_scene_read_at(scene, offset, &chunk, sizeof chunk))
            return false;
        offset += sizeof chunk;
        if (chunk.length > size - offset)
            return false;
        if (memcmp(chunk.id, "HEAD\0\0\0\0\0\0\0", 12) == 0) {
            DWORD dimensions[2];
            if (assets->world_width || chunk.length != 32 ||
                !anno_scene_read_at(scene, offset, dimensions, sizeof dimensions) || dimensions[0] != dimensions[1])
                return false;
            switch (dimensions[0]) {
            case 256: case 512: case 1024: case 2048:
                assets->world_width = dimensions[0];
                break;
            default:
                return false;
            }
        } else if (memcmp(chunk.id, "INSELLNK\0\0\0", 12) == 0) {
            unsigned char link[ANNO_SCENE_LINK_SIZE] = {0};
            if (chunk.length < 16 || !anno_scene_read_at(scene, offset, link, 16))
                return false;
            if (memcmp(link + 12, "WS\\", 3) == 0) {
                if (chunk.length != sizeof link || assets->count >= ARRAYSIZE(assets->files) ||
                    !anno_scene_read_at(scene, offset, link, sizeof link))
                    return false;
                const HANDLE file = anno_open_scene_island(executable, root, link);
                if (file == INVALID_HANDLE_VALUE)
                    return false;
                assets->files[assets->count++] = file;
            }
        }
        offset += chunk.length;
    }
    return assets->world_width != 0;
}
