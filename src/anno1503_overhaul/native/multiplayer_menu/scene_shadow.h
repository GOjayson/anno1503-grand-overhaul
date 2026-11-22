/* Route audited native read calls to the verified, locked match artifact. */
#include <bcrypt.h>
#include <wchar.h>

enum { ANNO_SHADOW_MAX_BYTES = 16 * 1024 * 1024 };

static const WCHAR anno_shadow_stock_suffix[] = L"\\Scenes\\0500MultiEndlos\\NewEarth.sze";
static const WCHAR anno_shadow_directory[] = L"\\AnnoGrandMatches";
static const WCHAR anno_shadow_extended_prefix[] = L"\\\\?\\";
static SRWLOCK anno_shadow_lock = SRWLOCK_INIT;
static HANDLE anno_shadow_file;
static WCHAR anno_shadow_stock[MAX_PATH];

static bool anno_shadow_equal_path(const WCHAR *first, const WCHAR *second)
{
    return CompareStringOrdinal(first, -1, second, -1, TRUE) == CSTR_EQUAL;
}

static bool anno_shadow_digest(HANDLE file, uint64_t size, const unsigned char expected[32])
{
    BCRYPT_ALG_HANDLE algorithm = NULL;
    BCRYPT_HASH_HANDLE hash = NULL;
    unsigned char digest[32], data[16384];
    bool matches = false;
    if (BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, NULL, 0) < 0)
        return false;
    if (BCryptCreateHash(algorithm, &hash, NULL, 0, NULL, 0, 0) >= 0) {
        while (size) {
            DWORD count = 0, chunk = size > sizeof data ? sizeof data : (DWORD)size;
            if (!ReadFile(file, data, chunk, &count, NULL) || count != chunk ||
                BCryptHashData(hash, data, count, 0) < 0)
                break;
            size -= count;
        }
        matches = !size && BCryptFinishHash(hash, digest, sizeof digest, 0) >= 0 &&
            memcmp(digest, expected, sizeof digest) == 0;
        BCryptDestroyHash(hash);
    }
    BCryptCloseAlgorithmProvider(algorithm, 0);
    return matches;
}

#include "scene_island_assets.h"

static SceneIslandAssets anno_shadow_assets;

static inline bool anno_shadow_is_armed(void)
{
    AcquireSRWLockShared(&anno_shadow_lock);
    const bool armed = anno_shadow_file != NULL;
    ReleaseSRWLockShared(&anno_shadow_lock);
    return armed;
}

static inline DWORD anno_shadow_world_width(void)
{
    AcquireSRWLockShared(&anno_shadow_lock);
    const DWORD width = anno_shadow_file ? anno_shadow_assets.world_width : 0;
    ReleaseSRWLockShared(&anno_shadow_lock);
    return width;
}

static bool anno_shadow_arm_for_executable(const WCHAR *path, uint64_t size, const unsigned char digest[32],
                                           const WCHAR *executable)
{
    static const WCHAR extension[] = L".sze";
    static const WCHAR digits[] = L"0123456789abcdef";
    WCHAR directory[MAX_PATH], expected[MAX_PATH], stock[MAX_PATH], final[MAX_PATH + 4];
    const WCHAR *last_slash = executable ? wcsrchr(executable, L'\\') : NULL;
    if (!path || !digest || !size || size > ANNO_SHADOW_MAX_BYTES || !last_slash ||
        last_slash <= executable + 2 || executable[1] != L':' || executable[2] != L'\\')
        return false;
    const size_t root = (size_t)(last_slash - executable);
    const size_t directory_length = root + ARRAYSIZE(anno_shadow_directory) - 1;
    if (directory_length + 1 + 64 + ARRAYSIZE(extension) > ARRAYSIZE(expected) ||
        root + ARRAYSIZE(anno_shadow_stock_suffix) > ARRAYSIZE(stock))
        return false;

    memcpy(directory, executable, root * sizeof(WCHAR));
    memcpy(directory + root, anno_shadow_directory, sizeof anno_shadow_directory);
    memcpy(expected, directory, directory_length * sizeof(WCHAR));
    expected[directory_length] = L'\\';
    WCHAR *name = expected + directory_length + 1;
    for (size_t index = 0; index < 32; ++index) {
        name[index * 2] = digits[digest[index] >> 4];
        name[index * 2 + 1] = digits[digest[index] & 15];
    }
    memcpy(name + 64, extension, sizeof extension);
    if (wcscmp(path, expected) != 0)
        return false;

    HANDLE folder = CreateFileW(directory, FILE_READ_ATTRIBUTES, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL,
        OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, NULL);
    if (folder == INVALID_HANDLE_VALUE)
        return false;
    BY_HANDLE_FILE_INFORMATION info;
    HANDLE file = INVALID_HANDLE_VALUE;
    if (GetFileInformationByHandle(folder, &info) && (info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) &&
        !(info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT)) {
        file = CreateFileW(expected, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                           FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_SEQUENTIAL_SCAN, NULL);
    }
    CloseHandle(folder);
    if (file == INVALID_HANDLE_VALUE)
        return false;

    DWORD length = GetFinalPathNameByHandleW(file, final, ARRAYSIZE(final), FILE_NAME_NORMALIZED | VOLUME_NAME_DOS);
    bool valid = length > 4 && length < ARRAYSIZE(final) &&
        wcsncmp(final, anno_shadow_extended_prefix, 4) == 0 && anno_shadow_equal_path(final + 4, expected) &&
        GetFileInformationByHandle(file, &info) && info.nNumberOfLinks == 1 && !info.nFileSizeHigh &&
        info.nFileSizeLow == size && !(info.dwFileAttributes & (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT)) &&
        anno_shadow_digest(file, size, digest);
    SceneIslandAssets assets = {0};
    if (valid)
        valid = anno_hold_scene_islands(file, (DWORD)size, executable, root, &assets);
    if (valid) {
        memcpy(stock, executable, root * sizeof(WCHAR));
        memcpy(stock + root, anno_shadow_stock_suffix, sizeof anno_shadow_stock_suffix);
        AcquireSRWLockExclusive(&anno_shadow_lock);
        valid = !anno_shadow_file;
        if (valid) {
            memcpy(anno_shadow_stock, stock, (root + ARRAYSIZE(anno_shadow_stock_suffix)) * sizeof(WCHAR));
            anno_shadow_file = file;
            anno_shadow_assets = assets;
        }
        ReleaseSRWLockExclusive(&anno_shadow_lock);
    }
    if (!valid) {
        anno_release_scene_islands(&assets);
        CloseHandle(file);
    }
    return valid;
}

static inline bool anno_shadow_arm(const WCHAR *path, uint64_t size, const unsigned char digest[32])
{
    WCHAR executable[MAX_PATH];
    DWORD length = GetModuleFileNameW(NULL, executable, ARRAYSIZE(executable));
    return length && length < ARRAYSIZE(executable) && anno_shadow_arm_for_executable(path, size, digest, executable);
}

static void anno_shadow_clear(void)
{
    AcquireSRWLockExclusive(&anno_shadow_lock);
    if (anno_shadow_file) {
        anno_release_scene_islands(&anno_shadow_assets);
        CloseHandle(anno_shadow_file);
        anno_shadow_file = NULL;
    }
    ReleaseSRWLockExclusive(&anno_shadow_lock);
}

static bool anno_shadow_stock_path(LPCSTR path)
{
    WCHAR wide[MAX_PATH], absolute[MAX_PATH];
    if (!path || !MultiByteToWideChar(CP_ACP, MB_ERR_INVALID_CHARS, path, -1, wide, ARRAYSIZE(wide)))
        return false;
    for (const WCHAR *component = wide; *component;) {
        const size_t length = wcscspn(component, L"\\/");
        if ((length == 1 && component[0] == L'.') || (length == 2 && component[0] == L'.' && component[1] == L'.'))
            return false;
        component += length;
        if (*component)
            ++component;
    }
    DWORD length = GetFullPathNameW(wide, ARRAYSIZE(absolute), absolute, NULL);
    return length && length < ARRAYSIZE(absolute) && anno_shadow_equal_path(absolute, anno_shadow_stock);
}

static inline bool anno_shadow_selection_allowed(LPCSTR directory, LPCSTR scenario)
{
    char path[MAX_PATH];
    bool allowed = true;
    AcquireSRWLockShared(&anno_shadow_lock);
    if (anno_shadow_file) {
        const size_t prefix = directory ? strnlen(directory, MAX_PATH) : 0;
        const size_t name = scenario ? strnlen(scenario, MAX_PATH) : 0;
        allowed = prefix && name && prefix + 1 + name < ARRAYSIZE(path);
        if (allowed) {
            memcpy(path, directory, prefix);
            path[prefix] = '\\';
            memcpy(path + prefix + 1, scenario, name + 1);
            allowed = anno_shadow_stock_path(path);
        }
    }
    ReleaseSRWLockShared(&anno_shadow_lock);
    return allowed;
}

__declspec(dllexport) HANDLE WINAPI AnnoTrialOpenScene(LPCSTR path, DWORD access, DWORD share,
    LPSECURITY_ATTRIBUTES attributes, DWORD disposition, DWORD flags, HANDLE template_file)
{
    const DWORD previous_error = GetLastError();
    AcquireSRWLockShared(&anno_shadow_lock);
    if (!anno_shadow_file || !anno_shadow_stock_path(path)) {
        ReleaseSRWLockShared(&anno_shadow_lock);
        SetLastError(previous_error);
        return CreateFileA(path, access, share, attributes, disposition, flags, template_file);
    }

    HANDLE file = INVALID_HANDLE_VALUE;
    SetLastError(ERROR_ACCESS_DENIED);
    if (access == GENERIC_READ && (share == FILE_SHARE_READ || share == (FILE_SHARE_READ | FILE_SHARE_WRITE)) &&
        !attributes && disposition == OPEN_EXISTING && !template_file &&
        (flags == FILE_ATTRIBUTE_NORMAL || flags == (FILE_FLAG_SEQUENTIAL_SCAN | FILE_ATTRIBUTE_NORMAL))) {
        file = ReOpenFile(anno_shadow_file, GENERIC_READ, FILE_SHARE_READ, flags & FILE_FLAG_SEQUENTIAL_SCAN);
    }
    const DWORD error = GetLastError();
    ReleaseSRWLockShared(&anno_shadow_lock);
    SetLastError(file == INVALID_HANDLE_VALUE ? error : previous_error);
    return file;
}
