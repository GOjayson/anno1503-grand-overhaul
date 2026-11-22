"""Verify the direct lobby's redraw of its native startup artwork."""

import ctypes
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from anno1503_overhaul.multiplayer_lobby_frame import LOBBY_BACKGROUND_CALLS, verify_lobby_background, verify_lobby_backdrop_inputs


ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "src/anno1503_overhaul/native/multiplayer_menu"


class LobbyBackgroundCallTests(unittest.TestCase):
    def test_rejects_an_unreviewed_frame(self):
        with self.assertRaisesRegex(ValueError, "lobby paint image"):
            verify_lobby_background(b"other AnnoFrame.dll")

    def test_rejects_an_unreviewed_display(self):
        with self.assertRaisesRegex(ValueError, "lobby paint image"):
            verify_lobby_backdrop_inputs(ROOT, b"other AnnoDisplay.dll", "0" * 64)

    def test_preserves_the_original_lobby_initializer_abi(self):
        self.assertEqual(LOBBY_BACKGROUND_CALLS, (
            (0x4C6E5, b"\xff\x90\xb0\x01\x00\x00", "AnnoMenuPrepareLobbyPaint"),
        ))


FIXTURE = r'''
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

enum { LOBBY_VTABLE = 0xa44c0, DISPLAY_INSTANCE = 0x1347450 };
static bool use_native_lobby_paint(unsigned char *frame) { (void)frame; return false; }
static uint32_t get32(const void *memory) { uint32_t value; memcpy(&value, memory, 4); return value; }
#include "lobby_background.h"

static void put32(void *destination, uint32_t value) { memcpy(destination, &value, 4); }
static void putptr(void *destination, void *value) { memcpy(destination, &value, sizeof value); }
static unsigned int cleared;
static unsigned int initialized;
static void clear_surface(unsigned char *texture)
{
    unsigned char *const pixels = *(unsigned char **)(texture + 0x20);
    cleared = (cleared << 4) | pixels[0];
    pixels[0] = 0;
}

static void set_backdrop(void *layer, void *texture)
{
    if (layer && texture)
        cleared = (cleared << 4) | 3;
}

__declspec(dllexport) unsigned int clear_fixture(unsigned int fault)
{
    void *renderer_storage[0x29d8 / sizeof(void *)] = {0};
    unsigned char *renderer = (unsigned char *)renderer_storage;
    unsigned char pixels[3] = {1, 2, 3};
    put32(renderer + 0x29d0, fault == 1 ? 1 : 3);
    for (unsigned int index = 0; index < 3; ++index) {
        unsigned char *texture = renderer + 0x1d0 + 0xa0 * index;
        putptr(texture + 0x20, index == 1 && fault == 2 ? NULL : &pixels[index == 1 && fault == 3 ? 0 : index]);
        put32(texture + 0x38, index == 1 && fault == 4 ? 801 : 800);
        put32(texture + 0x3c, index == 0 && fault == 5 ? 601 : 600);
        put32(texture + 0x44, index == 0 && fault == 6 ? 2 : 4);
        texture[0x70] = (unsigned char)(index % 2);
    }
    cleared = 0;
    menu_repaint_lobby_background(fault == 7 ? NULL : renderer, clear_surface,
        fault == 8 ? NULL : renderer, fault == 9 ? NULL : &pixels[2], set_backdrop);
    if (pixels[2] != 3 || renderer[0x240] || !renderer[0x2e0] || renderer[0x380])
        return UINT32_MAX;
    return cleared;
}

static void stock_initialize(void *lobby)
{
    if (lobby)
        ++initialized;
}

__declspec(dllexport) unsigned int stock_initializer_fixture(void)
{
    void *methods[0x1b8 / sizeof(void *)] = {0};
    void *lobby = methods;
    methods[0x1b0 / sizeof(void *)] = (void *)stock_initialize;
    initialized = 0;
    AnnoMenuPrepareLobbyPaint((unsigned char *)&lobby);
    return initialized;
}
'''


@unittest.skipUnless(os.name == "nt", "Requires the native Windows lobby fixture.")
class LobbyBackgroundNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = os.environ.get("ANNO_MULTIPLAYER_TEST_ZIG")
        zig = Path(compiler) if compiler else ROOT / ".local/toolchain/ziglang/zig.exe"
        if not zig.is_file():
            raise unittest.SkipTest("Reviewed native compiler unavailable.")
        temporary = TemporaryDirectory(prefix="anno-lobby-background-")
        cls.addClassCleanup(temporary.cleanup)
        folder = Path(temporary.name)
        source, target = folder / "fixture.c", folder / "fixture.dll"
        source.write_text(FIXTURE, encoding="utf-8")
        subprocess.run([str(zig), "cc", "-std=c11", "-target", "x86_64-windows-gnu", "-O2", "-shared",
                        "-Wall", "-Wextra", "-Werror", "-I", str(NATIVE), str(source), "-o", str(target)], check=True)
        cls.native = ctypes.CDLL(str(target))
        import _ctypes
        cls.addClassCleanup(_ctypes.FreeLibrary, cls.native._handle)
        cls.native.clear_fixture.argtypes = [ctypes.c_uint]
        cls.native.clear_fixture.restype = ctypes.c_uint

    def test_clears_both_startup_layers_then_sets_the_exact_backdrop(self):
        self.assertEqual(self.native.clear_fixture(0), 0x123)

    def test_skips_clear_when_either_surface_layout_is_unknown(self):
        for fault in range(1, 8):
            with self.subTest(fault=fault):
                self.assertEqual(self.native.clear_fixture(fault), 0)

    def test_skips_clear_when_the_backdrop_cannot_be_set(self):
        for fault in (8, 9):
            with self.subTest(fault=fault):
                self.assertEqual(self.native.clear_fixture(fault), 0)

    def test_preserves_stock_initializer_outside_the_verified_lobby(self):
        self.assertEqual(self.native.stock_initializer_fixture(), 1)
