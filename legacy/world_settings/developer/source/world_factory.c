/* Development scene-factory boundary. The original native factory is retained.
 * Loaded-world validation must succeed before any object reaches simulation.
 */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

extern int WorldSettingsIsActive(void);
extern const char *WorldSettingsPendingPath(void);
extern int WorldSettingsValidateScene(void *, char *, uint32_t);
extern void WorldSettingsFinishAttempt(int);
extern int WorldSettingsBindAIProfileWorld(void*,char*,uint32_t);

typedef int32_t (*WSNativeFactory)(int32_t, const char *, void *, void **,
                                   void *, uint32_t, uint32_t);
typedef void (*WSSceneRelease)(void *);
typedef void (*WSFailureReporter)(const char *);
static char lastFactoryError[512];
static WSFailureReporter failureReporter;

/* Explicit UI registration only; synthetic/standalone callers remain silent. */
__declspec(dllexport) void WorldSettingsSetFailureReporter(WSFailureReporter reporter) {
    failureReporter = reporter;
}

static int32_t finishFailure(int32_t result) {
    WorldSettingsFinishAttempt(0);
    if (failureReporter) failureReporter(lastFactoryError);
    return result;
}

__declspec(dllexport) const char *WorldSettingsLastFactoryError(void) {
    return lastFactoryError;
}

/* Caller supplies a writable 512-byte buffer. The DWORD-sized byte-count return
 * also permits a remote debug thread to copy the diagnostic without returning
 * a 64-bit pointer through GetExitCodeThread. Includes the terminating NUL. */
__declspec(dllexport) uint32_t WorldSettingsCopyFactoryError(void *buffer) {
    size_t count = 0;
    if (!buffer) return 0;
    while (count < sizeof lastFactoryError - 1 && lastFactoryError[count]) count++;
    memcpy(buffer, lastFactoryError, count);
    ((char *)buffer)[count] = 0;
    return (uint32_t)count + 1;
}

__declspec(dllexport) int32_t WorldSettingsCreateScene(
        int32_t mode, const char *path, void *saveList, void **out,
        void *metadata, uint32_t index, uint32_t flags, WSNativeFactory original) {
    const int32_t failure = (int32_t)0x80004005u;
    const int active = WorldSettingsIsActive();
    lastFactoryError[0] = 0;
    if (!original || !out) {
        if (out) *out = NULL;
        snprintf(lastFactoryError, sizeof lastFactoryError, "%s", "Invalid native scene factory boundary.");
        if (active) return finishFailure((int32_t)0x80004003u);
        return (int32_t)0x80004003u;
    }
    if (!active) {
        return original(mode, path, saveList, out, metadata, index, flags);
    }
    *out = NULL;
    const char *prepared = WorldSettingsPendingPath();
    if (mode != 0 || !prepared || !prepared[0]) {
        snprintf(lastFactoryError, sizeof lastFactoryError, "%s", "Prepared endless world path is unavailable.");
        return finishFailure(failure);
    }
    int32_t result = original(mode, prepared, saveList, out, metadata, index, flags);
    if (result < 0) {
        /* Reviewed CreateAnnoSceneInstance RVA 11a0 clears *out at 11c7,
         * destroys its provisional object at 12f9 on an init/load error,
         * and publishes it only at 132f.
         * A non-NULL failure output violates that contract and may already be
         * destroyed. Hide it from Frame without a second deleting call. */
        *out = NULL;
        snprintf(lastFactoryError, sizeof lastFactoryError, "%s", "The native generator rejected the prepared world.");
        return finishFailure(result);
    }
    if (!*out || WorldSettingsValidateScene(*out, lastFactoryError, sizeof lastFactoryError) != 1 || WorldSettingsBindAIProfileWorld(*out,lastFactoryError,sizeof lastFactoryError) != 1) {
        /* Scene virtual +18 is RVA 1b60: the native release wrapper, which
         * invokes virtual +0 (the deleting destructor) with deletion flag 1.
         * This object is still owned solely by the CreateSceneInstance caller;
         * Frame has not installed it into the Game/Display interfaces yet.
         */
        if (*out) {
            void **vtable = *(void ***)*out;
            WSSceneRelease release = (WSSceneRelease)vtable[3];
            release(*out);
            *out = NULL;
        }
        if (!lastFactoryError[0]) {
            snprintf(lastFactoryError, sizeof lastFactoryError, "%s", "The loaded world failed validation.");
        }
        lastFactoryError[sizeof lastFactoryError-1] = 0;
        return finishFailure(failure);
    }
    lastFactoryError[0] = 0;
    WorldSettingsFinishAttempt(1);
    return result;
}
