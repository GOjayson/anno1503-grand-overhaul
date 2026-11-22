import ctypes
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from anno1503_overhaul.multiplayer_menu_lifecycle import (
    MENU_LIFECYCLE_CALLS, lifecycle_arguments, verified_menu_lifecycle_calls,
)


_NATIVE = Path(__file__).resolve().parents[1] / "src/anno1503_overhaul/native/multiplayer_menu"
_FIXTURE = r"""
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>

enum { CLIENT_GLOBAL = 0xc6c10, SERVER_GLOBAL = 0xc6c18 };
static _Alignas(8) unsigned char frame[0xc6c90], startup[0x2220];
static unsigned int cleared, diagnostic_seen;
static void menu_set_plan(const void *plan) { if (!plan) ++cleared; }
static void menu_clear_world(void) { cleared += 16; SetLastError(ERROR_INVALID_DATA); }
static BOOL menu_restore_huge(void) { cleared += 32; return TRUE; }
static void log_event(const char *message) {
    diagnostic_seen = (unsigned int)(message && !strcmp(message, "original message") && cleared == 0);
    SetLastError(ERROR_FILE_NOT_FOUND);
}
static HMODULE fixture_module(LPCWSTR name) {
    return wcscmp(name, L"AnnoFrame.dll") ? NULL : (HMODULE)frame;
}
#define GetModuleHandleW fixture_module
#include "menu_lifecycle.h"

__declspec(dllexport) unsigned int RunFixture(unsigned int action, unsigned int occupied, unsigned int out[5])
{
    memset(startup, 0x55, sizeof startup);
    memset(frame, 0, sizeof frame);
    frame[MENU_LIFECYCLE_STOCK_CANCELLED] = 1;
    frame[occupied == 2 ? SERVER_GLOBAL : CLIENT_GLOBAL] = (unsigned char)occupied;
    cleared = diagnostic_seen = 0;
    *(void (**)(const char *))(frame + MENU_LIFECYCLE_STOCK_DIAGNOSTIC) = log_event;
    SetLastError(ERROR_ACCESS_DENIED);
    if (action == 0) AnnoMenuFinishBack(startup);
    else if (action == 1) AnnoMenuFinishQuit(startup);
    else AnnoMenuFinishMatch("original message");
    out[0] = *(uint32_t *)(startup + MENU_LIFECYCLE_PENDING);
    out[1] = startup[MENU_LIFECYCLE_RUNNING];
    out[2] = frame[MENU_LIFECYCLE_STOCK_CANCELLED];
    out[3] = diagnostic_seen;
    out[4] = GetLastError();
    return cleared;
}
"""


class MultiplayerLifecycleSiteTests(unittest.TestCase):
    def test_cancel_sites_have_space_to_pass_the_one_native_argument(self):
        first, second, match = MENU_LIFECYCLE_CALLS
        for address, before, _ in (first, second):
            self.assertEqual(lifecycle_arguments(address), bytes.fromhex("488bcb"))
            self.assertGreaterEqual(len(before), 9)
        self.assertEqual(lifecycle_arguments(match[0]), b"")
        self.assertEqual(match[0] + 6 + int.from_bytes(match[1][2:], "little", signed=True), 0x9E078)
        with self.assertRaisesRegex(ValueError, "cleanup image changed"):
            verified_menu_lifecycle_calls(b"MZ" + bytes(1024))

    def test_exact_stock_preimages_when_available(self):
        source = os.environ.get("ANNO_MULTIPLAYER_STOCK_FRAME")
        if not source:
            self.skipTest("The reviewed local stock Frame is unavailable.")
        self.assertEqual(verified_menu_lifecycle_calls(Path(source).read_bytes()), MENU_LIFECYCLE_CALLS)


@unittest.skipUnless(os.name == "nt", "The native lifecycle callback uses Windows.")
class MultiplayerLifecycleNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from _ctypes import FreeLibrary

        compiler = os.environ.get("ANNO_MULTIPLAYER_ZIG")
        if not compiler or not Path(compiler).is_file():
            raise unittest.SkipTest("The reviewed local Zig compiler is unavailable.")
        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        base = Path(temporary.name)
        source, output = base / "lifecycle_fixture.c", base / "lifecycle_fixture.dll"
        source.write_text(_FIXTURE, encoding="ascii")
        subprocess.run([compiler, "cc", "-target", "x86_64-windows-gnu", "-shared", "-O2", "-Wall", "-Wextra",
                        "-Werror", "-std=c11", "-I", str(_NATIVE), "-o", str(output), str(source)], check=True)
        cls.native = ctypes.WinDLL(str(output))
        cls.addClassCleanup(FreeLibrary, cls.native._handle)
        cls.native.RunFixture.argtypes = (ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(ctypes.c_uint))
        cls.native.RunFixture.restype = ctypes.c_uint

    def run_fixture(self, action, occupied=0):
        result = (ctypes.c_uint * 5)()
        cleared = self.native.RunFixture(action, occupied, result)
        return cleared, tuple(result)

    def test_cancel_preserves_original_native_flags_and_retires_a_closed_session(self):
        self.assertEqual(self.run_fixture(0), (49, (0, 0, 0, 0, 5)))
        self.assertEqual(self.run_fixture(1), (49, (1, 0, 1, 0, 5)))
        self.assertEqual(self.run_fixture(0, 1), (0, (0, 0, 0, 0, 5)))
        self.assertEqual(self.run_fixture(1, 2), (0, (1, 0, 1, 0, 5)))

    def test_post_match_diagnostic_runs_before_cleanup_and_keeps_native_last_error(self):
        self.assertEqual(self.run_fixture(2), (49, (0x55555555, 0x55, 1, 1, 2)))
        self.assertEqual(self.run_fixture(2, 2), (0, (0x55555555, 0x55, 1, 1, 2)))


if __name__ == "__main__":
    unittest.main()
