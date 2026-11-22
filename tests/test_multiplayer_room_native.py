"""Exercise native room admission and roster updates without network traffic."""

import ctypes
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "src/anno1503_overhaul/native/multiplayer_menu"


FIXTURE = r'''
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <windows.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

enum { TRIAL_HOST = 1, TRIAL_GUEST = 2, DISCOVERY = 1, JOIN = 3, BODY_AT = 10, GAME_ID_SIZE = 16,
       OWN_HOST_PORT = 61503 };
typedef struct {
    char signature[8];
    uint32_t role, local, peer, prefix;
    char host_name[32], guest_name[32];
    uint32_t player_count, extra_guest_count;
    struct { uint32_t address; char name[32]; } extra_guests[6];
    char internet_tickets[7][24];
} TrialSettings;
static TrialSettings plan;
static const TrialSettings *settings(void) { return &plan; }
static bool valid_trial_name(const char name[32]) { return name[0] && memchr(name, 0, 32); }
static unsigned int private_range(uint32_t address) { return address && address < 10 ? 8 : 0; }
static bool public_unicast(uint32_t address) { return address >= 20 && address < 120; }
static bool valid_settings(const TrialSettings *value) { return memcmp(value->signature, "ANNOLAB1", 8) == 0; }
static uint16_t get16(const void *memory) { uint16_t value; memcpy(&value, memory, 2); return value; }
static uint32_t get32(const void *memory) { uint32_t value; memcpy(&value, memory, 4); return value; }
static void putptr(void *memory, const void *value) { memcpy(memory, &value, sizeof value); }
static void put32(void *memory, uint32_t value) { memcpy(memory, &value, 4); }

#include "menu_room_plan.h"
#include "menu_room_admission.h"
static unsigned char sent_packet[60];
static int sent_length;
static int fixture_sendto(SOCKET socket, const char *data, int length, int flags,
                          const struct sockaddr *address, int address_length)
{
    (void)socket; (void)flags; (void)address; (void)address_length;
    sent_length = length;
    if (length < 0 || (size_t)length > sizeof sent_packet)
        return SOCKET_ERROR;
    memcpy(sent_packet, data, length);
    return length;
}
#define sendto fixture_sendto
#include "menu_room_discovery.h"
#undef sendto
enum { ROSTER_RECORD_SIZE = 0x34, ROSTER_COLOR = 0x32, NODE_COLOR = 0x42 };
static bool roster_record_matches(const unsigned char *record, const unsigned char *node)
{
    return get32(record + 0x10) == get32(node + 0x20) && memcmp(record, node + 0x10, 16) == 0;
}
#include "menu_room_roster.h"

static const SOCKET listener = 545;

static void prepare(unsigned int count)
{
    memset(&plan, 0, sizeof plan);
    memcpy(plan.signature, "ANNOROOM", 8);
    plan.role = TRIAL_HOST;
    plan.local = 1;
    plan.peer = 2;
    memcpy(plan.host_name, "Host", 5);
    memcpy(plan.guest_name, "Guest2", 7);
    plan.player_count = count;
    plan.extra_guest_count = count - 2;
    for (unsigned int index = 0; index < count - 2; ++index) {
        plan.extra_guests[index].address = index + 3;
        memcpy(plan.extra_guests[index].name, "Guest0", 7);
        plan.extra_guests[index].name[5] = (char)('3' + index);
    }
    menu_room_reset_listener(listener);
}

static struct sockaddr_in endpoint(unsigned int address)
{
    struct sockaddr_in value = {0};
    value.sin_family = AF_INET;
    value.sin_addr.s_addr = address;
    value.sin_port = (uint16_t)(700 + address);
    return value;
}

static void prepare_internet(void)
{
    prepare(8);
    memcpy(plan.signature, "ANNONETR", 8);
    plan.peer = 20;
    for (unsigned int peer = 0; peer < 7; ++peer) {
        memset(plan.internet_tickets[peer], '0' + peer, 24);
        if (peer)
            plan.extra_guests[peer - 1].address = 20;
    }
}

static void install_row(unsigned char *server, unsigned int seat, const struct sockaddr_in *address)
{
    unsigned char *const row = server + 0xdbc + 0x18 * seat;
    memcpy(row, address, sizeof *address);
    put32(row + 0x14, seat);
}

static void join_packet(unsigned char *packet, const char *nickname)
{
    const size_t length = strlen(nickname);
    packet[28] = (unsigned char)(2 * length);
    for (size_t index = 0; index < length; ++index) {
        packet[30 + 2 * index] = (unsigned char)nickname[index];
        packet[31 + 2 * index] = 0;
    }
}

__declspec(dllexport) unsigned int verify_admission_order(void)
{
    void *storage[0x1000 / sizeof(void *)] = {0};
    unsigned char *const server = (unsigned char *)storage;
    const HANDLE mutex = CreateMutexW(NULL, FALSE, NULL);
    if (!mutex) return 99;
    putptr(server + 0x5a8, mutex);
    prepare(8);
    const struct sockaddr_in host = endpoint(1), outsider = endpoint(9);
    install_row(server, 0, &host);
    const unsigned int order[7] = {8, 7, 2, 6, 3, 4, 5};
    unsigned int result = menu_room_receive_seat(server, listener, &outsider, false) == MENU_ROOM_NO_SEAT ? 0 : 1;
    for (unsigned int index = 0; !result && index < 7; ++index) {
        const unsigned int seat = index + 1, address = order[index];
        const struct sockaddr_in guest = endpoint(address);
        char nickname[] = "Guest0";
        nickname[5] = (char)('0' + address);
        unsigned char packet[110] = {0};
        join_packet(packet, nickname);
        unsigned int peer = MENU_ROOM_NO_SEAT;
        if (menu_room_receive_seat(server, listener, &guest, false) != MENU_ROOM_NEXT_SEAT ||
            menu_room_queue_seat(server, packet, 59, JOIN, &guest, NULL, &peer) != MENU_ROOM_NO_SEAT ||
            menu_room_queue_seat(server, packet, 26, DISCOVERY, &guest, NULL, &peer) != seat) {
            result = 2;
            break;
        }
        menu_room_request_queued(DISCOVERY, &guest, peer);
        packet[30] = 'X';
        if (menu_room_queue_seat(server, packet, 59, JOIN, &guest, NULL, &peer) != MENU_ROOM_NO_SEAT) {
            result = 3;
            break;
        }
        join_packet(packet, nickname);
        if (menu_room_queue_seat(server, packet, 59, JOIN, &guest, NULL, &peer) != seat ||
            menu_room_receive_seat(server, listener, &guest, true) != MENU_ROOM_NO_SEAT) {
            result = 4;
            break;
        }
        install_row(server, seat, &guest);
        struct sockaddr_in wrong_port = guest;
        ++wrong_port.sin_port;
        const char *const known = menu_room_roster_name(&plan, server, seat, 0);
        if (menu_room_receive_seat(server, listener, &guest, true) != seat ||
            menu_room_receive_seat(server, listener, &wrong_port, true) != MENU_ROOM_NO_SEAT ||
            menu_room_queue_seat(server, packet, 59, JOIN, &guest, NULL, &peer) != seat ||
            !known || strcmp(known, nickname) != 0 || (menu_room_all_admitted(&plan, server) != (seat == 7))) {
            result = 5;
        }
    }
    CloseHandle(mutex);
    return result;
}

__declspec(dllexport) unsigned int verify_internet_admission(void)
{
    void *storage[0x1000 / sizeof(void *)] = {0};
    unsigned char *const server = (unsigned char *)storage;
    const HANDLE mutex = CreateMutexW(NULL, FALSE, NULL);
    if (!mutex) return 99;
    putptr(server + 0x5a8, mutex);
    prepare_internet();
    const struct sockaddr_in host = endpoint(1);
    install_row(server, 0, &host);
    unsigned int result = 0;
    for (unsigned int seat = 1; seat < 8 && !result; ++seat) {
        const unsigned int index = 7 - seat;
        struct sockaddr_in guest = endpoint(20);
        guest.sin_port += (uint16_t)seat;
        const unsigned char *const ticket = (const unsigned char *)plan.internet_tickets[index];
        unsigned char packet[110] = {0};
        join_packet(packet, menu_room_guest_name(&plan, index));
        unsigned int peer = MENU_ROOM_NO_SEAT;
        if (menu_room_queue_seat(server, packet, 59, JOIN, &guest, NULL, &peer) != MENU_ROOM_NO_SEAT ||
            menu_room_queue_seat(server, packet, 26, DISCOVERY, &guest, NULL, &peer) != MENU_ROOM_NO_SEAT ||
            menu_room_queue_seat(server, packet, 26, DISCOVERY, &guest, ticket, &peer) != seat ||
            peer != index) {
            result = 1;
            break;
        }
        menu_room_request_queued(DISCOVERY, &guest, peer);
        struct sockaddr_in replay = guest;
        replay.sin_port += 100;
        if (menu_room_queue_seat(server, packet, 26, DISCOVERY, &replay, ticket, &peer) != MENU_ROOM_NO_SEAT ||
            (index && menu_room_queue_seat(server, packet, 26, DISCOVERY, &guest,
                (const unsigned char *)plan.internet_tickets[index - 1], &peer) != MENU_ROOM_NO_SEAT) ||
            menu_room_queue_seat(server, packet, 59, JOIN, &guest, NULL, &peer) != seat) {
            result = 2;
            break;
        }
        install_row(server, seat, &guest);
        const char *const known = menu_room_roster_name(&plan, server, seat, 0);
        if (!known || strcmp(known, menu_room_guest_name(&plan, index)) ||
            menu_room_receive_seat(server, listener, &guest, true) != seat ||
            menu_room_receive_seat(server, listener, &replay, true) != MENU_ROOM_NO_SEAT ||
            menu_room_queue_seat(server, packet, 59, JOIN, &guest, NULL, &peer) != seat ||
            menu_room_all_admitted(&plan, server) != (seat == 7))
            result = 3;
    }
    CloseHandle(mutex);
    return result;
}

__declspec(dllexport) unsigned int verify_internet_discovery(void)
{
    prepare_internet();
    plan.role = TRIAL_GUEST;
    plan.extra_guest_count = 0;
    struct sockaddr_in target = endpoint(20);
    target.sin_port = htons(OWN_HOST_PORT);
    const struct sockaddr *const to = (const struct sockaddr *)&target;
    unsigned char stock[MENU_ROOM_DISCOVERY_STOCK_SIZE] = {0, 0, 26, 0, 1, 2, 3, 4, 0, DISCOVERY};
    if (AnnoMenuSendRoomDiscovery(listener, (const char *)stock, 26, 0, to, sizeof target) != 26 ||
        sent_length != MENU_ROOM_DISCOVERY_SIZE || memcmp(sent_packet, stock, sizeof stock))
        return 1;
    const unsigned char *const ticket = menu_room_read_discovery_ticket(sent_packet, sent_length);
    if (!ticket || memcmp(ticket, plan.internet_tickets[0], MENU_ROOM_TICKET_LENGTH) ||
        menu_room_read_discovery_ticket(sent_packet, sent_length - 1))
        return 2;
    sent_packet[26] = 'X';
    if (menu_room_read_discovery_ticket(sent_packet, sent_length))
        return 3;
    stock[9] = JOIN;
    AnnoMenuSendRoomDiscovery(listener, (const char *)stock, 26, 0, to, sizeof target);
    if (sent_length != 26)
        return 4;
    stock[9] = DISCOVERY;
    memcpy(plan.signature, "ANNOINET", 8);
    AnnoMenuSendRoomDiscovery(listener, (const char *)stock, 26, 0, to, sizeof target);
    if (sent_length != 26 || memcmp(sent_packet, stock, sizeof stock))
        return 5;
    memcpy(plan.signature, "ANNOROOM", 8);
    AnnoMenuSendRoomDiscovery(listener, (const char *)stock, 26, 0, to, sizeof target);
    return sent_length == 26 && !memcmp(sent_packet, stock, sizeof stock) ? 0 : 6;
}

__declspec(dllexport) unsigned int verify_join_nickname(void)
{
    prepare(4);
    WCHAR name[32] = {0};
    menu_room_client_name(&plan, name);
    if (wcscmp(name, L"Host") != 0) return 1;
    plan.role = TRIAL_GUEST;
    plan.extra_guest_count = 0;
    menu_room_client_name(&plan, name);
    if (wcscmp(name, L"Guest2") != 0) return 2;
    return menu_room_roster_name(&plan, NULL, 0, 3) == plan.host_name &&
        !menu_room_roster_name(&plan, NULL, 1, 3) &&
        menu_room_roster_name(&plan, NULL, 3, 3) == plan.guest_name ? 0 : 3;
}

__declspec(dllexport) bool valid_room_fixture(unsigned int fault)
{
    prepare(4);
    switch (fault) {
        case 1: plan.extra_guests[1].address = plan.extra_guests[0].address; break;
        case 2: plan.extra_guests[2].name[2] = 'X'; break;
        case 3: plan.host_name[22] = 'X'; break;
        case 4: plan.extra_guests[0].address = 10; break;
        case 5: plan.extra_guest_count = 1; break;
        case 6: plan.peer = plan.local; break;
        case 7: plan.role = TRIAL_GUEST; break;
        case 8: plan.player_count = 2; break;
        case 9:
            prepare(2);
            memcpy(plan.signature, "ANNOLAB1", 8);
            break;
        case 10:
            prepare(2);
            memcpy(plan.signature, "ANNOLAB1", 8);
            plan.extra_guests[3].address = 5;
            break;
        case 11:
            prepare(4);
            plan.role = TRIAL_GUEST;
            plan.extra_guest_count = 0;
            memset(plan.extra_guests, 0, sizeof plan.extra_guests);
            break;
        case 12: prepare_internet(); break;
        case 13: prepare_internet(); plan.internet_tickets[0][0] = 'A'; break;
        case 14:
            prepare_internet();
            memcpy(plan.internet_tickets[2], plan.internet_tickets[0], 24);
            break;
        case 15: prepare_internet(); plan.extra_guests[1].address = 2; break;
        case 16: plan.internet_tickets[0][0] = '0'; break;
    }
    return menu_room_valid_plan(&plan);
}

__declspec(dllexport) int reconcile_fixture(unsigned int fault)
{
    unsigned char nodes[8][0x48] = {{0}}, records[8][0x34] = {{0}}, roster[0x28] = {0};
    putptr(roster + 0x20, nodes[0]);
    for (unsigned int id = 0; id < 8; ++id) {
        putptr(nodes[id] + 8, id < 7 ? nodes[id + 1] : NULL);
        put32(nodes[id] + 0x20, id);
        put32(records[7 - id] + 0x10, id);
        nodes[id][0x42] = 0x80;
        records[7 - id][0x32] = id >= 6 ? 0xff : (unsigned char)(id + 1);
    }
    if (fault == 1) put32(records[0] + 0x10, 6);
    if (fault == 2) records[0][1] = 1;
    if (fault == 3) records[1][0x32] = 1;
    if (fault == 4) records[0][0x32] = 0;
    if (fault == 5) putptr(nodes[6] + 8, nodes[0]);
    if (fault == 6) put32(nodes[1] + 0x20, 0);
    const bool changed = menu_room_reconcile_colors(roster, records[0],
        sizeof records - (fault == 7 ? 1 : 0), 8);
    for (unsigned int id = 0; id < 8; ++id) {
        if (nodes[id][0x42] != (fault ? 0x80 : records[7 - id][0x32])) return -1;
    }
    return changed;
}
'''


@unittest.skipUnless(os.name == "nt", "Requires the native Windows room fixture.")
class RoomNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = os.environ.get("ANNO_MULTIPLAYER_TEST_ZIG")
        zig = Path(compiler) if compiler else ROOT / ".local/toolchain/ziglang/zig.exe"
        if not zig.is_file():
            raise unittest.SkipTest("Reviewed native compiler unavailable.")
        temporary = TemporaryDirectory(prefix="anno-room-native-")
        cls.addClassCleanup(temporary.cleanup)
        folder = Path(temporary.name)
        source, target = folder / "fixture.c", folder / "fixture.dll"
        source.write_text(FIXTURE, encoding="utf-8")
        subprocess.run([str(zig), "cc", "-std=c11", "-target", "x86_64-windows-gnu", "-O2", "-shared",
                        "-Wall", "-Wextra", "-Werror", "-I", str(NATIVE), str(source), "-o", str(target), "-lws2_32"],
                       check=True)
        cls.native = ctypes.CDLL(str(target))
        import _ctypes
        cls.addClassCleanup(_ctypes.FreeLibrary, cls.native._handle)
        cls.native.reconcile_fixture.argtypes = [ctypes.c_uint]
        cls.native.valid_room_fixture.argtypes = [ctypes.c_uint]
        cls.native.valid_room_fixture.restype = ctypes.c_bool

    def test_native_rows_define_join_order_after_stock_installs_them(self):
        self.assertEqual(self.native.verify_admission_order(), 0)

    def test_passes_local_verified_names_as_native_utf16(self):
        self.assertEqual(self.native.verify_join_nickname(), 0)

    def test_seven_internet_guests_on_one_public_ip_keep_distinct_native_endpoints(self):
        self.assertEqual(self.native.verify_internet_admission(), 0)

    def test_only_group_internet_discovery_carries_the_admission_ticket(self):
        self.assertEqual(self.native.verify_internet_discovery(), 0)

    def test_validates_group_endpoints_and_zero_padding(self):
        for mode in (0, 9, 11, 12):
            with self.subTest(mode=mode):
                self.assertTrue(self.native.valid_room_fixture(mode))
        for fault in (*range(1, 9), 10, 13, 14, 15, 16):
            with self.subTest(fault=fault):
                self.assertFalse(self.native.valid_room_fixture(fault))

    def test_updates_complete_native_snapshot_only(self):
        self.assertEqual(self.native.reconcile_fixture(0), 1)
        for fault in range(1, 8):
            with self.subTest(fault=fault):
                self.assertEqual(self.native.reconcile_fixture(fault), 0)
