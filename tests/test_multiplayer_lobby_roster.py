"""Test the native direct lobby's stock list-row format and capacity."""

import ctypes
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from anno1503_overhaul.multiplayer_lobby_roster_frame import LOBBY_ROSTER_CALLS, verify_lobby_roster


ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "src/anno1503_overhaul/native/multiplayer_menu"


class LobbyRosterHookTests(unittest.TestCase):
    def test_only_replaces_the_reviewed_initial_and_periodic_refresh(self):
        initial, periodic = LOBBY_ROSTER_CALLS
        self.assertEqual((initial[0], len(initial[1])), (0x4C6DA, 8))
        self.assertEqual((periodic[0], len(periodic[1])), (0x4E7B7, 12))

    def test_rejects_a_different_stock_frame(self):
        with self.assertRaisesRegex(ValueError, "roster image"):
            verify_lobby_roster(b"unsupported frame")


FIXTURE = r'''
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

enum { NODE_COLOR = 0x42, MENU_ROOM_SEATS = 8, SERVER_GLOBAL = 0x40, ROSTER_GLOBAL = 0x48,
       TRIAL_HOST = 1, TRIAL_GUEST = 2, LOBBY_VTABLE = 0xa44c0, NATIVE_ROSTER_REFRESH = 0x4e190 };
typedef struct { unsigned role; unsigned player_count; char host_name[32], guest_name[32]; } TrialSettings;
static TrialSettings plan;
static unsigned char frame_storage[0xc6ccc];
static const TrialSettings *settings(void) { return &plan; }
static bool menu_room_transport(const TrialSettings *value) { return value->player_count > 2; }
static bool use_native_lobby_paint(unsigned char *frame) { (void)frame; return false; }
static void menu_coop_disable_guest_picker(unsigned char *frame, unsigned char *lobby) { (void)frame; (void)lobby; }
static const char *menu_room_roster_name(const TrialSettings *value, const unsigned char *server,
                                         uint32_t seat, uint32_t local_seat)
{
    (void)server;
    return seat == 0 ? value->host_name : seat == local_seat ? value->guest_name : NULL;
}
static uint32_t get32(const void *memory) { uint32_t value; memcpy(&value, memory, 4); return value; }
#include "lobby_roster.h"

typedef struct { unsigned int calls, names, flags; bool valid; } Capture;

static int capture_row(void *opaque, unsigned int capability, const MenuLobbyListCaps *caps)
{
    Capture *const capture = opaque;
    const unsigned char *const raw = (const unsigned char *)caps->row;
    const char *const name = caps->row->name;
    const uint32_t seat = get32(raw + 8);
    const uint32_t flag = get32(raw + 0x40);
    capture->calls++;
    if (seat < 8 && name[0]) capture->names |= 1u << seat;
    if (flag < 9) capture->flags |= 1u << flag;
    if (capability != 0x1b8 || caps->unused || get32(raw + 0x18) != 0x16 ||
        get32(raw + 0x2c) != 365 || get32(raw + 0x50) != UINT32_MAX ||
        (seat == 0 && strcmp(name, "Host") != 0) || (seat == 5 && strcmp(name, "Own guest") != 0))
        capture->valid = false;
    return 1;
}

__declspec(dllexport) unsigned int roster_fixture(unsigned int fault)
{
    unsigned char nodes[8][0x48] = {{0}};
    const uint32_t local = 5;
    memcpy(frame_storage + 0xc6cc8, &local, 4);
    plan = (TrialSettings){.role = TRIAL_GUEST, .player_count = 8, .host_name = "Host", .guest_name = "Own guest"};
    for (uint32_t id = 0; id < 8; ++id) {
        unsigned char *next = id == 7 ? NULL : nodes[id + 1];
        memcpy(nodes[id] + 8, &next, sizeof next);
        memcpy(nodes[id] + 0x20, &id, 4);
        memcpy(nodes[id] + 0x24, "Guest", 6);
        nodes[id][0x42] = (unsigned char)(id + 1);
    }
    if (fault == 1) memcpy(nodes[7] + 8, nodes[0] + 8, sizeof(void *));
    if (fault == 2) memset(nodes[7] + 0x20, 0, 4);
    if (fault == 3) memset(nodes[7] + 0x24, 'X', NODE_COLOR - 0x24);
    if (fault == 4) nodes[7][0x42] = 9;
    if (fault == 5) nodes[7][0x42] = 0xff;
    MenuLobbyDisplayPlayer players[8];
    unsigned int count;
    if (!menu_lobby_collect_players(frame_storage, &plan, nodes[0], players, &count))
        return 0;
    Capture capture = {.valid = true};
    for (unsigned int index = 0; index < count; ++index)
        menu_lobby_list_add(&capture, capture_row, players[index].name, players[index].id, 365, players[index].colour);
    return capture.calls == 8 && capture.names == 0xff && capture.valid ? capture.flags : UINT32_MAX;
}
'''


@unittest.skipUnless(os.name == "nt", "Requires the native Windows roster fixture.")
class LobbyRosterNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = os.environ.get("ANNO_MULTIPLAYER_TEST_ZIG")
        zig = Path(compiler) if compiler else ROOT / ".local/toolchain/ziglang/zig.exe"
        if not zig.is_file():
            raise unittest.SkipTest("Reviewed native compiler unavailable.")
        temporary = TemporaryDirectory(prefix="anno-lobby-roster-")
        cls.addClassCleanup(temporary.cleanup)
        folder = Path(temporary.name)
        source, target = folder / "fixture.c", folder / "fixture.dll"
        source.write_text(FIXTURE, encoding="utf-8")
        subprocess.run([str(zig), "cc", "-std=c11", "-target", "x86_64-windows-gnu", "-O2", "-shared",
                        "-Wall", "-Wextra", "-Werror", "-I", str(NATIVE), str(source), "-o", str(target)], check=True)
        cls.native = ctypes.CDLL(str(target))
        import _ctypes
        cls.addClassCleanup(_ctypes.FreeLibrary, cls.native._handle)
        cls.native.roster_fixture.argtypes = [ctypes.c_uint]
        cls.native.roster_fixture.restype = ctypes.c_uint

    def test_emits_eight_distinct_stock_name_and_flag_rows(self):
        self.assertEqual(self.native.roster_fixture(0), 0x1FE)
        self.assertEqual(self.native.roster_fixture(5), 0x0FF)

    def test_rejects_inconsistent_or_oversized_native_records(self):
        for fault in range(1, 5):
            with self.subTest(fault=fault):
                self.assertEqual(self.native.roster_fixture(fault), 0)
