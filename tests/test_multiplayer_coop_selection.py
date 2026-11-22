"""Check the opt-in co-op action bridge without starting a licensed game."""

import ctypes
import os
from pathlib import Path
from struct import unpack_from
import subprocess
from tempfile import TemporaryDirectory
import unittest

from anno1503_overhaul.multiplayer_coop_selection import (
    COOP_FRAME_SELECTION_CALLS, COOP_WORLD_SELECTION_CALLS, coop_selection_edit,
    verified_coop_selection_calls,
)


ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "src/anno1503_overhaul/native/multiplayer_menu"


class CoopHookTests(unittest.TestCase):
    def test_replacement_call_displacements_and_lengths(self):
        slot = 0x170000
        for address, stock, name in (*COOP_FRAME_SELECTION_CALLS, *COOP_WORLD_SELECTION_CALLS):
            with self.subTest(name=name):
                revised = coop_selection_edit(address, slot)
                call = revised.index(b"\xff\x15")
                self.assertLessEqual(len(revised), len(stock))
                self.assertEqual(address + call + 6 + unpack_from("<i", revised, call + 2)[0], slot)

    def test_rejects_unverified_images(self):
        for name in ("AnnoFrame.dll", "AnnoWelt.dll", "Unknown.dll"):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "reviewed stock History Edition"):
                verified_coop_selection_calls(name, bytes(2048))

    def test_exact_native_boundaries_if_stock_inputs_are_available(self):
        for name, key, calls in (("AnnoFrame.dll", "ANNO_MULTIPLAYER_STOCK_FRAME", COOP_FRAME_SELECTION_CALLS),
                                 ("AnnoWelt.dll", "ANNO_MULTIPLAYER_STOCK_WORLD", COOP_WORLD_SELECTION_CALLS)):
            source = os.environ.get(key)
            if not source:
                self.skipTest("Exact local stock multiplayer modules are unavailable.")
            self.assertEqual(verified_coop_selection_calls(name, Path(source).read_bytes()), calls)


FIXTURE = r'''
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

static bool menu_coop_active(void) {return true;}
static uint16_t get16(const unsigned char *p) {uint16_t v; memcpy(&v, p, 2); return v;}
static uint32_t get32(const unsigned char *p) {uint32_t v; memcpy(&v, p, 4); return v;}
#include "coop_selection.h"

__declspec(dllexport) uint16_t stamp(uint16_t code, uint16_t source, int enabled)
{
    return coop_stamp_command(code, source, enabled != 0);
}

__declspec(dllexport) uint32_t replay_actor(const unsigned char *record)
{
    return coop_command_actor(record, record[0]);
}

__declspec(dllexport) uint16_t test_group_order_transfer(unsigned int old_id, unsigned int new_id)
{
    unsigned char old_flags = 7, new_flags = 11;
    unsigned char action[12] = {COOP_UNIT_GROUP_ORDER};
    memcpy(action + 8, &new_id, 4);
    coop_reconcile_row(&old_flags, action, old_id);
    coop_reconcile_row(&new_flags, action, new_id);
    return (uint16_t)(old_flags << 8) | new_flags;
}

__declspec(dllexport) unsigned int test_view_swap(void)
{
    unsigned char actor[0x400] = {0};
    unsigned char a = 1, b = 2;
    CoopSelection local = {&a, {&a, NULL, NULL, NULL}, 2, 5};
    CoopSelection remote = {&b, {NULL, &b, NULL, NULL}, 3, 12};
    coop_set_selection(actor, &local);
    const CoopSelection held = coop_read_selection(actor);
    coop_set_selection(actor, &remote);
    const CoopSelection projected = coop_read_selection(actor);
    coop_set_selection(actor, &held);
    const CoopSelection restored = coop_read_selection(actor);
    return projected.active == &b && projected.cache[0] == NULL && projected.cache[1] == &b &&
        projected.cache_kind == 3 && projected.serial == 12 && restored.active == &a &&
        restored.cache[0] == &a && restored.cache[1] == NULL && restored.cache_kind == 2 && restored.serial == 5;
}
'''


@unittest.skipUnless(os.name == "nt", "Requires the native Windows co-op fixture.")
class CoopSelectionNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = os.environ.get("ANNO_MULTIPLAYER_TEST_ZIG")
        zig = Path(compiler) if compiler else ROOT / ".local/toolchain/ziglang/zig.exe"
        if not zig.is_file():
            raise unittest.SkipTest("Reviewed native compiler unavailable.")
        temporary = TemporaryDirectory(prefix="anno-coop-selection-")
        cls.addClassCleanup(temporary.cleanup)
        folder = Path(temporary.name)
        source, target = folder / "fixture.c", folder / "fixture.dll"
        source.write_text(FIXTURE, encoding="utf-8")
        subprocess.run([str(zig), "cc", "-std=c11", "-target", "x86_64-windows-gnu", "-O2",
                        "-shared", "-Wall", "-Wextra", "-Werror", "-I", str(NATIVE),
                        str(source), "-o", str(target)], check=True, capture_output=True, text=True)
        cls.fixture = ctypes.CDLL(str(target))
        import _ctypes
        cls.addClassCleanup(_ctypes.FreeLibrary, cls.fixture._handle)
        cls.fixture.stamp.argtypes = [ctypes.c_uint16, ctypes.c_uint16, ctypes.c_int]
        cls.fixture.stamp.restype = ctypes.c_uint16
        cls.fixture.replay_actor.argtypes = [ctypes.c_char_p]
        cls.fixture.replay_actor.restype = ctypes.c_uint32

    def test_native_server_stamps_only_valid_coop_actions(self):
        for code in range(0x80, 0x87):
            self.assertEqual(self.fixture.stamp(code, 0, 1), code + 0x100)
            self.assertEqual(self.fixture.stamp(code, 1, 1), code + 0x200)
            self.assertEqual(self.fixture.stamp(code, 2, 1), code)
            self.assertEqual(self.fixture.stamp(code, 1, 0), code)
        self.assertEqual(self.fixture.stamp(0x90, 1, 1), 0x90)

    def test_split_view_preserves_each_players_selection_cache_and_hud_serial(self):
        self.assertEqual(self.fixture.test_view_swap(), 1)

    def test_overlapping_groups_keep_membership_and_only_latest_order_ownership(self):
        self.assertEqual(self.fixture.test_group_order_transfer(0, 29), 0x050B)
        self.assertEqual(self.fixture.test_group_order_transfer(29, 0), 0x050B)
        self.assertEqual(self.fixture.test_group_order_transfer(0, 0), 0x070B)

    def test_replay_keeps_owner_separate_from_source_tag_and_rejects_bad_lengths(self):
        self.assertEqual(self.fixture.replay_actor(b"\x82\x02\x05\x00\x07" + bytes(4)), 7)
        self.assertEqual(self.fixture.replay_actor(b"\x83\x01\x04\x00\x09" + bytes(3)), 9)
        self.assertEqual(self.fixture.replay_actor(b"\x85\x02\x04\x00\x00\x00\x02\x00"), 2)
        self.assertEqual(self.fixture.replay_actor(b"\x84\x01\x04\x00\x01\x00\x02\x00"), 0xFFFFFFFF)
