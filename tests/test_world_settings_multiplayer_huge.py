"""Offline checks for both directions of the optional Huge engine transaction."""

import ctypes
from hashlib import sha256
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from anno1503_overhaul.world_runtime_build import AI_LOADER, ENGINE_PLAN, PE, derive_engine_plan
from anno1503_overhaul.world_settings_multiplayer_huge import INSTALL_PATH, apply_huge_engine, prove_huge_frame


ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "legacy" / "world_settings"
NATIVE = ROOT / "src" / "anno1503_overhaul" / "native" / "world_settings_multiplayer"


class HugeEngineSourceTests(unittest.TestCase):
    def test_stages_the_reviewed_plan_in_two_directions(self):
        loader = AI_LOADER.rsplit("/", 1)[0] + "/install_test_hooks.c"
        files = {loader: (LEGACY / loader).read_bytes()}
        apply_huge_engine(files)
        staged = files[loader]
        self.assertIn(b"restore?edit->after:edit->before", staged)
        self.assertIn(b"wsPrepareEngineTransition(patches,patchCount,0)", staged)
        self.assertIn(b"if(wsMpHugeState){wsError", staged)
        self.assertIn(b'#include "huge_multiplayer_install.inc"', staged)
        self.assertEqual(files[INSTALL_PATH], (NATIVE / "huge_multiplayer_install.inc").read_bytes())

    def test_checks_the_exact_derived_frame_and_instruction_preimages(self):
        frame_path = os.environ.get("ANNO_MULTIPLAYER_HUGE_FRAME")
        world_path = os.environ.get("ANNO_MULTIPLAYER_STOCK_WORLD")
        if not frame_path or not world_path:
            self.skipTest("The reviewed multiplayer Frame and World fixtures are unavailable.")
        frame = Path(frame_path).read_bytes()
        world = Path(world_path).read_bytes()
        plan = derive_engine_plan(world, (LEGACY / ENGINE_PLAN).read_bytes())
        proof = prove_huge_frame(frame, sha256(frame).hexdigest(), plan)
        self.assertEqual((proof["frame_edits"], proof["engine_edits"]), (7, 173))
        with self.assertRaisesRegex(ValueError, "visibility pin"):
            prove_huge_frame(frame, "0" * 64, plan)
        altered = bytearray(frame)
        altered[PE(frame).offset(0x1C3F6, 1)] ^= 1
        with self.assertRaisesRegex(ValueError, "preimage differs"):
            prove_huge_frame(bytes(altered), sha256(altered).hexdigest(), plan)
        with self.assertRaisesRegex(ValueError, "reviewed World-only engine plan"):
            prove_huge_frame(frame, sha256(frame).hexdigest(), plan + b"\n")


FIXTURE = r"""
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>

#define WS_ENGINE_PATCH_COUNT 2u
#define WS_MAX_THREADS 2u
enum { WS_MP_FRAME, WS_MP_WORLD, WS_MP_MODULE_COUNT };
enum { WS_ENGINE_MODULE_WORLD, WS_ENGINE_MODULE_FRAME, WS_ENGINE_MODULE_COUNT };
typedef struct { unsigned char *address, before[1], after[1]; uint32_t length; } WSPatch;
typedef struct { int placeholder; } WSPage;
typedef struct { int placeholder; } WSThread;
static SRWLOCK wsInstallLock = SRWLOCK_INIT;
static HMODULE wsEngineModules[WS_ENGINE_MODULE_COUNT];
static HMODULE frame;
static unsigned char target[2];
static int wsInstallState, wsMpHugeState, wsMpInstalled;
static int pins, wasPaused, world, appearsPaused, applyCount, corruptWrite, cleanRollback;

static BOOL WINAPI pinSelf(DWORD flags, LPCWSTR address, HMODULE *module)
{
    if (flags != (GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_PIN) ||
        !address || !module)
        return FALSE;
    *module = frame;
    return TRUE;
}
#define GetModuleHandleExW pinSelf

static int wsMpDrawPinModules(HMODULE *modules, uint32_t *sizes)
{
    modules[WS_MP_FRAME] = frame;
    modules[WS_MP_WORLD] = (HMODULE)(void *)target;
    sizes[WS_MP_FRAME] = 0xa0000u;
    sizes[WS_MP_WORLD] = sizeof target;
    return pins;
}

static int wsPrepareEngineTransition(WSPatch *patches, uint32_t *count, int restore)
{
    wsEngineModules[WS_ENGINE_MODULE_FRAME] = frame;
    wsEngineModules[WS_ENGINE_MODULE_WORLD] = (HMODULE)(void *)target;
    for (uint32_t i = 0; i < WS_ENGINE_PATCH_COUNT; ++i) {
        WSPatch *patch = &patches[i];
        patch->address = &target[i];
        patch->before[0] = restore ? 2u : 1u;
        patch->after[0] = restore ? 1u : 2u;
        patch->length = 1u;
        if (*patch->address != patch->before[0])
            return 0;
        (*count)++;
    }
    return 1;
}

static int wsEngineWorldAbsent(void) { return !world && !(wasPaused && appearsPaused); }

static int wsGroupPages(WSPatch *patches, uint32_t count, WSPage *pages, uint32_t *out, SIZE_T size)
{
    *out = 1u;
    return patches && count == WS_ENGINE_PATCH_COUNT && pages && size;
}

static int wsSuspendThreads(WSThread *threads, uint32_t *count, WSPatch *patches, uint32_t patchCount)
{
    wasPaused = threads && patches && patchCount == WS_ENGINE_PATCH_COUNT;
    *count = 1u;
    return wasPaused;
}

static void wsResumeThreads(WSThread *threads, uint32_t count)
{
    if (threads && count == 1u)
        wasPaused = 0;
}

static int wsApplyPatches(WSPatch *patches, uint32_t count, WSPage *pages, uint32_t pageCount)
{
    if (!wasPaused || !pages || pageCount != 1u)
        return 0;
    ++applyCount;
    for (uint32_t i = 0; i < count; ++i)
        *patches[i].address = patches[i].after[0];
    if (corruptWrite)
        target[0] = 0;
    return 1;
}

static int wsRestorePatches(WSPatch *patches, uint32_t count, WSPage *pages, uint32_t pageCount)
{
    if (!cleanRollback || !wasPaused || !pages || pageCount != 1u)
        return 0;
    for (uint32_t i = 0; i < count; ++i)
        *patches[i].address = patches[i].before[0];
    return 1;
}

#include "huge_multiplayer_install.inc"

static void reset(void)
{
    target[0] = target[1] = 1u;
    wsMpHugeState = wsMpInstalled = wsInstallState = 0;
    wasPaused = world = appearsPaused = applyCount = corruptWrite = 0;
    pins = cleanRollback = 1;
}

__declspec(dllexport) int hugeFixture(void)
{
    frame = VirtualAlloc(NULL, 0xa0000u, MEM_RESERVE | MEM_COMMIT, PAGE_EXECUTE_READWRITE);
    if (!frame)
        return 1;
    int result = 0;
    reset();
    pins = 0;
    if (WorldSettingsPrepareMultiplayerHugeWorld() || applyCount || !WorldSettingsClearMultiplayerHugeWorld())
        result = 2;
    reset();
    world = 1;
    if (WorldSettingsPrepareMultiplayerHugeWorld() || applyCount || wasPaused)
        result = 3;
    reset();
    appearsPaused = 1;
    if (WorldSettingsPrepareMultiplayerHugeWorld() || applyCount || wasPaused)
        result = 4;
    reset();
    wsMpInstalled = 1;
    if (WorldSettingsPrepareMultiplayerHugeWorld() != 2u || applyCount != 1 ||
        WorldSettingsPrepareMultiplayerHugeWorld() || target[0] != 2 || target[1] != 2)
        result = 5;
    world = 1;
    if (WorldSettingsClearMultiplayerHugeWorld() || applyCount != 1 || target[0] != 2)
        result = 6;
    world = 0;
    if (!WorldSettingsClearMultiplayerHugeWorld() || applyCount != 2 ||
        !WorldSettingsClearMultiplayerHugeWorld() || target[0] != 1 || target[1] != 1)
        result = 7;
    reset();
    corruptWrite = 1;
    if (WorldSettingsPrepareMultiplayerHugeWorld() || target[0] != 1 ||
        target[1] != 1 || !WorldSettingsClearMultiplayerHugeWorld() || wasPaused)
        result = 8;
    reset();
    corruptWrite = 1;
    cleanRollback = 0;
    if (WorldSettingsPrepareMultiplayerHugeWorld() || applyCount != 1 ||
        WorldSettingsClearMultiplayerHugeWorld() || WorldSettingsPrepareMultiplayerHugeWorld() || wasPaused)
        result = 9;
    reset();
    if (WorldSettingsPrepareMultiplayerHugeWorld() != 2u)
        result = 10;
    target[1] = 3u;
    if (WorldSettingsClearMultiplayerHugeWorld() || applyCount != 1 ||
        target[0] != 2 || target[1] != 3 || WorldSettingsPrepareMultiplayerHugeWorld())
        result = 11;
    VirtualFree(frame, 0, MEM_RELEASE);
    return result;
}
"""


@unittest.skipUnless(os.name == "nt", "Requires a synthetic Windows engine transaction fixture.")
class HugeEngineNativeTests(unittest.TestCase):
    def test_preparation_and_restoration_require_an_absent_world_and_complete_bytes(self):
        compiler = os.environ.get("ANNO_MULTIPLAYER_TEST_ZIG")
        if not compiler or not Path(compiler).is_file():
            self.skipTest("Reviewed native compiler unavailable.")
        with TemporaryDirectory(prefix="anno-huge-engine-test-") as folder:
            source = Path(folder) / "fixture.c"
            runtime = Path(folder) / "fixture.dll"
            source.write_text(FIXTURE, encoding="utf-8")
            result = subprocess.run(
                [compiler, "cc", "-std=c11", "-target", "x86_64-windows-gnu", "-shared", "-O2",
                 "-Wall", "-Wextra", "-Werror", "-I", str(NATIVE), str(source), "-o", str(runtime)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            library = ctypes.WinDLL(str(runtime))
            try:
                library.hugeFixture.restype = ctypes.c_int
                self.assertEqual(library.hugeFixture(), 0)
            finally:
                import _ctypes
                _ctypes.FreeLibrary(library._handle)
