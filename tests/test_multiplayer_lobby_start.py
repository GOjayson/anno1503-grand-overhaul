"""Exercise the generated-match Start guard on synthetic native lobby records."""

import ctypes
import os
from pathlib import Path
from struct import unpack_from
import subprocess
from tempfile import TemporaryDirectory
import unittest

from anno1503_overhaul.multiplayer_coop_lobby import COOP_LOBBY_FLAG_CALLS, verify_coop_lobby_flags
from anno1503_overhaul.multiplayer_menu_coop import MENU_COOP_CALLS, verified_menu_coop_calls
from anno1503_overhaul.multiplayer_menu_frame import MENU_CALLBACKS, callback_load


ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "src/anno1503_overhaul/native/multiplayer_menu"


class LobbyStartCallbackTests(unittest.TestCase):
    def test_both_callback_assignments_preserve_the_stock_start_target(self):
        callbacks = [row for row in MENU_CALLBACKS if row[2] == "AnnoMenuStartWorldLobby"]
        self.assertEqual([row[0] for row in callbacks], [0x4CD9F, 0x4D5AE])
        for rva, native, _ in callbacks:
            self.assertEqual(rva + len(native) + unpack_from("<i", native, 3)[0], 0x4D7E0)
            self.assertEqual(callback_load(native, bytes(4)), native[:1] + b"\x8b" + native[2:3] + bytes(4))

    def test_coop_patches_only_the_reviewed_gameplay_factory(self):
        (rva, before, export), = MENU_COOP_CALLS
        self.assertEqual((rva, before[:2], export), (0x55C54, b"\xff\x15", "AnnoMenuCoopScene"))
        self.assertEqual(rva + len(before) + unpack_from("<i", before, 2)[0], 0x9E300)
        with self.assertRaisesRegex(ValueError, "reviewed stock History Edition"):
            verified_menu_coop_calls(bytes(0x56C60))
        source = os.environ.get("ANNO_MULTIPLAYER_STOCK_FRAME")
        if source:
            self.assertEqual(verified_menu_coop_calls(Path(source).read_bytes()), MENU_COOP_CALLS)

    def test_coop_reuses_both_native_flag_picker_callback_bindings(self):
        for rva, before, export in COOP_LOBBY_FLAG_CALLS[:2]:
            self.assertEqual(rva + len(before) + unpack_from("<i", before, 3)[0], 0x4D660)
            self.assertEqual(export, "AnnoMenuCoopChooseFlag")
            self.assertEqual(callback_load(before, bytes(4)), before[:1] + b"\x8b" + before[2:3] + bytes(4))
        source = os.environ.get("ANNO_MULTIPLAYER_STOCK_FRAME")
        if source:
            verify_coop_lobby_flags(Path(source).read_bytes())


FIXTURE = r'''
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

enum { LOBBY_VTABLE = 0xa44c0, ROSTER_GLOBAL = 0xc7c38, SERVER_GLOBAL = 0xc6c18,
       NODE_COLOR = 0x42, TRIAL_HOST = 1, TRIAL_GUEST = 2 };
typedef struct TrialSettings { unsigned int role, player_count; } TrialSettings;
static TrialSettings plan = {TRIAL_HOST, 2};
static const TrialSettings *settings(void) {return &plan;}
static const TrialSettings *named_direct_session(unsigned char *frame) {return frame ? &plan : NULL;}
static bool direct_mode(void) {return true;}
static bool anno_shadow_is_armed(void) {return true;}
static bool menu_room_transport(const TrialSettings *value) {return value->player_count > 2;}
static bool menu_room_all_admitted(const TrialSettings *value, const unsigned char *server)
{return value->player_count > 2 && server;}
static bool coop_requested;
static bool menu_coop_active(void) {return coop_requested;}
static uint32_t get32(const void *memory) {uint32_t value;memcpy(&value,memory,4);return value;}
#include "menu_coop.h"
#include "lobby_start.h"

static void putptr(unsigned char *target, const void *value)
{
    memcpy(target, &value, sizeof value);
}

__declspec(dllexport) int start_admitted(uint32_t first_colour, uint32_t second_colour, uint32_t fault, bool shared)
{
    unsigned char lobby[0x3120] = {0}, roster[0x28] = {0}, first[0x48] = {0}, second[0x48] = {0};
    unsigned char disconnects[0x18] = {0};
    const uint32_t queued[1] = {1};
    memset(lobby + MENU_LOBBY_COLOUR_TABLE, 0xff, MENU_LOBBY_COLOURS);
    putptr(roster + 0x20, first);
    putptr(first + 8, second);
    second[0x20] = 1;
    first[NODE_COLOR] = (unsigned char)first_colour;
    second[NODE_COLOR] = (unsigned char)second_colour;
    putptr(disconnects, queued);
    putptr(disconnects + 8, fault == 2 ? queued + 1 : queued);
    if (fault == 3) putptr(first + 8, NULL);
    if (fault == 4) second[0x20] = 0;
    if (fault == 5) lobby[MENU_LOBBY_COLOUR_TABLE] = 0;
    if (fault == 6) putptr(second + 8, first);
    return menu_lobby_start_problem(lobby, roster, disconnects, fault != 1, shared) == NULL;
}

__declspec(dllexport) bool wire_flags(unsigned int first, unsigned int second, bool shared)
{
    return menu_wire_flag_pair(first, second, shared);
}

__declspec(dllexport) unsigned int sync_flags(unsigned int host_colour, unsigned int guest_colour,
                                             unsigned int role, bool coop, bool guest_present)
{
    unsigned char lobby[0x3120] = {0}, roster[0x28] = {0}, host[0x48] = {0}, guest[0x48] = {0};
    unsigned char *const frame = HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, ROSTER_GLOBAL + 8);
    if (!frame)
        return UINT32_MAX;
    putptr(lobby, frame + LOBBY_VTABLE);
    putptr(frame + ROSTER_GLOBAL, roster);
    putptr(roster + 0x20, guest_present ? guest : host);
    putptr(guest + 8, host);
    host[NODE_COLOR] = (unsigned char)host_colour;
    guest[NODE_COLOR] = (unsigned char)guest_colour;
    guest[0x20] = 1;
    plan.role = role;
    coop_requested = coop;
    menu_coop_sync_lobby_flags(frame, lobby);
    const bool dirty = frame[MENU_COOP_ROSTER_DIRTY] != 0;
    HeapFree(GetProcessHeap(), 0, frame);
    plan.role = TRIAL_HOST;
    if (host[NODE_COLOR] != host_colour || host[0x20] != 0 || guest[0x20] != 1)
        return UINT32_MAX;
    return (unsigned int)guest[NODE_COLOR] | (dirty ? 0x100 : 0);
}

typedef struct { void *table; unsigned int disabled; } TestFlag;
typedef struct { void *table; TestFlag flags[8]; } TestPicker;

static unsigned int flag_count(void *picker, unsigned int capability)
{
    return picker && capability == 0xb00 ? 8 : 0;
}

static void *flag_at(void *picker, unsigned int capability, unsigned int index)
{
    return capability == 0xb00 && index < 8 ? &((TestPicker *)picker)->flags[index] : NULL;
}

static void set_enabled(void *flag, unsigned int capability, const uint32_t *caps)
{
    if (capability == 0x193 && !caps[2])
        ((TestFlag *)flag)->disabled = 1;
}

__declspec(dllexport) unsigned int disable_picker(unsigned int role, bool coop, bool invalid_button)
{
    unsigned char lobby[0x3120] = {0};
    void *widgets[11] = {0};
    TestPicker picker = {0};
    unsigned char *const frame = HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, ROSTER_GLOBAL + 8);
    if (!frame)
        return UINT32_MAX;
    picker.table = frame + MENU_COOP_PICKER_VTABLE;
    void **group_methods = picker.table;
    group_methods[0x70 / sizeof(void *)] = (void *)flag_count;
    group_methods[0x48 / sizeof(void *)] = (void *)flag_at;
    void **button_methods = (void **)(frame + MENU_COOP_FLAG_VTABLE);
    button_methods[0xa0 / sizeof(void *)] = (void *)set_enabled;
    for (unsigned int index = 0; index < 8; ++index)
        picker.flags[index].table = button_methods;
    if (invalid_button)
        picker.flags[7].table = NULL;
    widgets[10] = &picker;
    putptr(lobby, frame + LOBBY_VTABLE);
    putptr(lobby + MENU_COOP_WIDGETS, widgets);
    plan.role = role;
    coop_requested = coop;
    menu_coop_disable_guest_picker(frame, lobby);
    HeapFree(GetProcessHeap(), 0, frame);
    plan.role = TRIAL_HOST;
    unsigned int result = 0;
    for (unsigned int index = 0; index < 8; ++index)
        result += picker.flags[index].disabled;
    return result;
}

__declspec(dllexport) int start_room(unsigned int count, unsigned int fault)
{
    unsigned char lobby[0x3120] = {0}, roster[0x28] = {0}, nodes[8][0x48] = {0}, disconnects[0x18] = {0};
    if (count > 8u || !count)
        return 0;
    memset(lobby + MENU_LOBBY_COLOUR_TABLE, 0xff, MENU_LOBBY_COLOURS);
    putptr(roster + 0x20, nodes[0]);
    for (unsigned int index = 0; index < count; ++index) {
        nodes[index][0x20] = (unsigned char)index;
        nodes[index][NODE_COLOR] = (unsigned char)(index + 1u);
        if (index + 1u < count)
            putptr(nodes[index] + 8, nodes[index + 1]);
    }
    if (fault == 1) nodes[count - 1][NODE_COLOR] = 1;
    if (fault == 2) nodes[count - 1][0x20] = 0;
    if (fault == 3) putptr(nodes[count - 1] + 8, nodes[0]);
    if (fault == 4) putptr(disconnects, nodes[0]);
    return menu_room_start_problem(lobby, roster, disconnects, fault != 5, count) == NULL;
}

static HRESULT test_factory(void *unused, const char *path, void *context, void **scene, void *view,
                            int game_mode, unsigned int flags)
{
    (void)unused; (void)path; (void)scene; (void)view; (void)game_mode;
    ++*(unsigned int *)context;
    return flags ? E_FAIL : S_OK;
}

__declspec(dllexport) unsigned int create_scene(unsigned int coop, unsigned int reversed,
                                                unsigned int host_colour, unsigned int guest_colour,
                                                unsigned int fault)
{
    unsigned char roster[0x28] = {0}, host[0x48] = {0}, guest[0x48] = {0};
    unsigned char *const frame = HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, ROSTER_GLOBAL + 8);
    if (!frame)
        return 0;
    putptr(frame + ROSTER_GLOBAL, roster);
    putptr(roster + 0x20, reversed ? guest : host);
    putptr((reversed ? guest : host) + 8, reversed ? host : guest);
    host[NODE_COLOR] = (unsigned char)host_colour;
    guest[NODE_COLOR] = (unsigned char)guest_colour;
    guest[0x20] = fault == 3 ? 0 : 1;
    frame[MENU_COOP_SCENARIO_MODE] = fault == 2 ? 1 : 0;
    char *const directory = (char *)frame + MENU_COOP_SCENARIO_DIRECTORY;
    GetModuleFileNameA(NULL, directory, MAX_PATH);
    *strrchr(directory, '\\') = '\0';
    strcpy((char *)frame + MENU_COOP_SCENARIO_NAME, fault == 4 ? "Other.sze" : "Scenes\\0500MultiEndlos\\NewEarth.sze");
    coop_requested = coop != 0;
    unsigned int calls = 0;
    const HRESULT result = menu_coop_create_scene(test_factory, frame, NULL, NULL,
                                                  &calls, NULL, NULL, 0, fault == 1);
    HeapFree(GetProcessHeap(), 0, frame);
    if (host[NODE_COLOR] != host_colour || host[0x20] != 0 || guest[0x20] != (fault == 3 ? 0 : 1))
        return 0;
    return (SUCCEEDED(result) ? 1u : 0u) | (calls << 8u) | ((unsigned int)guest[NODE_COLOR] << 16u);
}
'''


@unittest.skipUnless(os.name == "nt", "Requires the native Windows lobby fixture.")
class LobbyStartNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = os.environ.get("ANNO_MULTIPLAYER_TEST_ZIG")
        zig = Path(compiler) if compiler else ROOT / ".local/toolchain/ziglang/zig.exe"
        if not zig.is_file():
            raise unittest.SkipTest("Reviewed native compiler unavailable.")
        temporary = TemporaryDirectory(prefix="anno-lobby-start-")
        cls.addClassCleanup(temporary.cleanup)
        folder = Path(temporary.name)
        source, target = folder / "fixture.c", folder / "fixture.dll"
        source.write_text(FIXTURE, encoding="utf-8")
        compiled = subprocess.run([str(zig), "cc", "-std=c11", "-target", "x86_64-windows-gnu", "-O2",
                                   "-shared", "-Wall", "-Wextra", "-Werror", "-I", str(NATIVE),
                                   str(source), "-luser32", "-o", str(target)], capture_output=True, text=True)
        if compiled.returncode:
            raise AssertionError(compiled.stdout + compiled.stderr)
        cls.native = ctypes.CDLL(str(target))
        import _ctypes
        cls.addClassCleanup(_ctypes.FreeLibrary, cls.native._handle)
        cls.native.start_admitted.argtypes = [ctypes.c_uint32] * 3 + [ctypes.c_bool]
        cls.native.sync_flags.argtypes = [ctypes.c_uint32] * 3 + [ctypes.c_bool] * 2
        cls.native.sync_flags.restype = ctypes.c_uint32
        cls.native.disable_picker.argtypes = [ctypes.c_uint32, ctypes.c_bool, ctypes.c_bool]
        cls.native.wire_flags.argtypes = [ctypes.c_uint32] * 2 + [ctypes.c_bool]
        cls.native.wire_flags.restype = ctypes.c_bool
        cls.native.start_room.argtypes = [ctypes.c_uint32] * 2
        cls.native.create_scene.argtypes = [ctypes.c_uint32] * 5
        cls.native.create_scene.restype = ctypes.c_uint32

    def test_uses_one_based_available_distinct_native_colours(self):
        self.assertEqual(self.native.start_admitted(1, 8, 0, False), 1)
        for first, second in ((0, 8), (1, 0xFF), (1, 1), (1, 9)):
            with self.subTest(first=first, second=second):
                self.assertEqual(self.native.start_admitted(first, second, 0, False), 0)

    def test_coop_start_requires_one_available_shared_host_flag(self):
        self.assertEqual(self.native.start_admitted(8, 8, 0, True), 1)
        for first, second, fault in ((1, 8, 0), (1, 0xff, 0), (0xff, 0xff, 0), (1, 1, 2), (1, 1, 5)):
            with self.subTest(first=first, second=second, fault=fault):
                self.assertEqual(self.native.start_admitted(first, second, fault, True), 0)

    def test_coop_host_mirrors_flag_changes_without_reassigning_transport_players(self):
        for first, second in ((4, 0xff), (8, 4), (0xff, 8)):
            with self.subTest(first=first, second=second):
                self.assertEqual(self.native.sync_flags(first, second, 1, True, True), 0x100 | first)
        self.assertEqual(self.native.sync_flags(4, 4, 1, True, True), 4)
        self.assertEqual(self.native.sync_flags(4, 7, 2, True, True), 7)
        self.assertEqual(self.native.sync_flags(4, 7, 1, False, True), 7)

    def test_late_guest_receives_the_current_host_flag_once_present(self):
        self.assertEqual(self.native.sync_flags(6, 0xff, 1, True, False), 0xff)
        self.assertEqual(self.native.sync_flags(6, 0xff, 1, True, True), 0x106)

    def test_only_coop_guest_has_all_verified_flag_buttons_disabled(self):
        self.assertEqual(self.native.disable_picker(2, True, False), 8)
        self.assertEqual(self.native.disable_picker(1, True, False), 0)
        self.assertEqual(self.native.disable_picker(2, False, False), 0)
        self.assertEqual(self.native.disable_picker(2, True, True), 0)

    def test_only_coop_accepts_a_shared_wire_flag(self):
        self.assertTrue(self.native.wire_flags(8, 8, True))
        self.assertTrue(self.native.wire_flags(0xff, 0xff, True))
        self.assertFalse(self.native.wire_flags(8, 8, False))
        self.assertTrue(self.native.wire_flags(4, 8, False))
        self.assertFalse(self.native.wire_flags(4, 8, True))
        self.assertFalse(self.native.wire_flags(0, 0, True))

    def test_room_requires_all_native_connections_and_distinct_flags(self):
        for count in (3, 4, 5, 6, 7, 8):
            self.assertEqual(self.native.start_room(count, 0), 1)
        for fault in (1, 2, 3, 4, 5):
            self.assertEqual(self.native.start_room(8, fault), 0)

    def test_waits_for_both_peers_and_an_empty_disconnect_vector(self):
        for fault in range(1, 7):
            with self.subTest(fault=fault):
                self.assertEqual(self.native.start_admitted(1, 8, fault, False), 0)

    def test_coop_assigns_the_host_flag_without_changing_either_connection_id(self):
        for reversed in (0, 1):
            with self.subTest(reversed=reversed):
                self.assertEqual(self.native.create_scene(1, reversed, 3, 8, 0), 0x030101)
                self.assertEqual(self.native.create_scene(1, reversed, 3, 0xff, 0), 0x030101)
        self.assertEqual(self.native.create_scene(0, 0, 3, 8, 0), 0x080101)

    def test_coop_rejects_other_scenarios_and_keeps_roster_unchanged_on_failure(self):
        self.assertEqual(self.native.create_scene(1, 0, 3, 8, 1), 0x080100)
        for fault in (2, 3, 4):
            with self.subTest(fault=fault):
                self.assertEqual(self.native.create_scene(1, 0, 3, 8, fault), 0x080000)
        self.assertEqual(self.native.create_scene(1, 0, 0, 8, 0), 0x080000)
