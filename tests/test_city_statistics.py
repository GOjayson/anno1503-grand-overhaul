"""Compare reviewed city statistics code before and after the native guard."""
from __future__ import annotations

import hashlib
from pathlib import Path
import struct
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from anno1503_overhaul import city_statistics
from anno1503_overhaul.food_supply import FOOD05_WELT_SHA256, build_progression_welt
from anno1503_overhaul.world_native import checksum
from anno1503_overhaul.world_runtime_build import PE


NATIVE_PATH = ROOT / ".local/baselines/world_settings/native/AnnoWelt.source.dll"
FUNCTION_RVA = 0xAE4F0
FUNCTION_SIZE = 0x2FD
MILESTONE = 0x798
TIMER = 0x79C
CURSOR = 0x7A0
SERVICE_STATISTIC = 0x958


def original_image():
    if not NATIVE_PATH.is_file():
        raise unittest.SkipTest("The private Food 0.5 native source fixture is unavailable.")
    data = NATIVE_PATH.read_bytes()
    if hashlib.sha256(data).hexdigest() != FOOD05_WELT_SHA256:
        raise unittest.SkipTest("The private Food 0.5 source fixture is a different build.")
    return build_progression_welt(data)[0]


class CityStatisticsPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = original_image()
        cls.guarded = city_statistics.bound_supply_statistics(cls.original)

    def test_guarded_version_changes_only_reviewed_spans_and_checksum(self):
        self.assertEqual(hashlib.sha256(self.guarded).hexdigest(),
                         city_statistics.FOOD06_GUARDED_WELT_SHA256)
        pe = PE(self.original)
        checksum_offset = pe.optional + 64
        self.assertEqual(struct.unpack_from("<I", self.guarded, checksum_offset)[0],
                         checksum(self.guarded))

        expected_spans = ((0xAE587, 49), (0xAE7C6, 6))
        self.assertEqual(city_statistics.edited_spans(), expected_spans)
        restored = bytearray(self.guarded)
        for offset, size in [(pe.offset(rva, size), size) for rva, size in expected_spans] + [
            (checksum_offset, 4),
        ]:
            self.assertNotEqual(restored[offset:offset + size], self.original[offset:offset + size])
            restored[offset:offset + size] = self.original[offset:offset + size]
        self.assertEqual(restored, self.original)

    def test_refuses_modified_or_already_patched_function(self):
        altered = bytearray(self.original)
        altered[PE(self.original).offset(FUNCTION_RVA, 1)] ^= 1
        for data in (self.guarded, bytes(altered)):
            with self.subTest(digest=hashlib.sha256(data).hexdigest()):
                with self.assertRaisesRegex(ValueError, "differs from the reviewed build"):
                    city_statistics.bound_supply_statistics(data)


class CityStatisticsBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        original = original_image()
        cls.original = PE(original).read(FUNCTION_RVA, FUNCTION_SIZE)
        cls.guarded = PE(city_statistics.bound_supply_statistics(original)).read(
            FUNCTION_RVA, FUNCTION_SIZE,
        )
        bundled = ROOT / ".local/toolchain/world-options-validation"
        if bundled.is_dir():
            sys.path.append(str(bundled))
        try:
            import unicorn
            from unicorn import x86_const
        except ImportError as error:
            raise unittest.SkipTest("Unicorn is unavailable for offline AMD64 execution.") from error
        cls.uc = unicorn
        cls.x86 = x86_const

        city = bytearray(b"\x11" * 0x1000)
        struct.pack_into("<H", city, MILESTONE, 517)
        struct.pack_into("<I", city, TIMER, 0x70123456)
        struct.pack_into("<H", city, CURSOR, 300)
        cls.initial_city = bytes(city)

    def run_city_loop(self, function, goods, *, satisfaction=50):
        emulator = self.uc.Uc(self.uc.UC_ARCH_X86, self.uc.UC_MODE_64)
        code_base = 0x100000
        entry = code_base + FUNCTION_RVA
        emulator.mem_map(entry & ~0xFFF, 0x1000)
        emulator.mem_write(entry, function)

        city, house, methods, group, rates, context = range(0x300000, 0x306000, 0x1000)
        emulator.mem_map(city, 0x6000)
        emulator.mem_write(city, self.initial_city)
        emulator.mem_write(house, struct.pack("<Q", methods))
        emulator.mem_write(group + 0x64, b"".join(struct.pack("<I", good) for good in goods))
        emulator.mem_write(group + 0xCC, struct.pack("<B", len(goods)))
        emulator.mem_write(group + 0x118, struct.pack("<Q", rates))
        context_methods = context + 0x200
        emulator.mem_write(context, struct.pack("<Q", context_methods))

        # The isolated function calls five virtual methods. Each stub returns a
        # fixed fixture value in RAX and leaves the caller's registers alone.
        stubs = 0x400000
        emulator.mem_map(stubs, 0x1000)
        for index, (vtable_entry, value) in enumerate((
            (methods + 0x140, 2),  # House rank.
            (methods + 0x118, group),
            (methods + 0x1A0, 28),  # Residents influencing the counters.
            (methods + 0x130, satisfaction),
            (context_methods, 0),
        )):
            address = stubs + index * 0x20
            emulator.mem_write(vtable_entry, struct.pack("<Q", address))
            emulator.mem_write(address, b"\x48\xb8" + struct.pack("<Q", value) + b"\xc3")

        stack = 0x500000
        emulator.mem_map(stack, 0x2000)
        rsp = stack + 0x1008
        stop = stubs + 0x100
        emulator.mem_write(rsp, struct.pack("<Q", stop))
        emulator.mem_write(rsp + 0x28, struct.pack("<I", 65_000))
        x86 = self.x86
        for register, value in (
            (x86.UC_X86_REG_RSP, rsp),
            (x86.UC_X86_REG_RCX, city),
            (x86.UC_X86_REG_RDX, house),
            (x86.UC_X86_REG_R8, context),
            (x86.UC_X86_REG_R9, 0),
        ):
            emulator.reg_write(register, value)
        emulator.emu_start(entry, stop, count=2_000)
        self.assertEqual(emulator.reg_read(x86.UC_X86_REG_RIP), stop)
        return bytes(emulator.mem_read(city, len(self.initial_city)))

    def test_invalid_goods_leave_milestone_timer_cursor_and_service_statistic_intact(self):
        # Game Meat 24 underruns the stock table onto the saved population threshold.
        old = self.run_city_loop(self.original, (24,))
        self.assertEqual(struct.unpack_from("<H", old, MILESTONE)[0], 503)

        # Bread 25 underruns into adjacent city fields. Butcher's Meat 45 also
        # reaches the following service-statistics region via the dword reset.
        old = self.run_city_loop(self.original, (25,))
        self.assertNotEqual(old[TIMER:TIMER + 4], self.initial_city[TIMER:TIMER + 4])
        self.assertNotEqual(old[CURSOR:CURSOR + 2], self.initial_city[CURSOR:CURSOR + 2])
        old = self.run_city_loop(self.original, (45,))
        self.assertEqual(struct.unpack_from("<I", old, SERVICE_STATISTIC)[0], 0)

        for good in (0, 24, 25, 41, 45, 255):
            with self.subTest(good=good):
                self.assertEqual(self.run_city_loop(self.guarded, (good,)), self.initial_city)

    def test_valid_boundaries_keep_original_fish_and_potato_statistics(self):
        for good in (26, 40):
            for satisfaction in (50, 85, 95):
                with self.subTest(good=good, satisfaction=satisfaction):
                    original = self.run_city_loop(self.original, (good,), satisfaction=satisfaction)
                    guarded = self.run_city_loop(self.guarded, (good,), satisfaction=satisfaction)
                    self.assertNotEqual(original, self.initial_city)
                    self.assertEqual(guarded, original)

    def test_mixed_goods_continue_after_invalid_entries(self):
        original = self.run_city_loop(self.original, (26, 40))
        guarded = self.run_city_loop(self.guarded, (24, 26, 25, 40, 45))
        self.assertEqual(guarded, original)


if __name__ == "__main__":
    unittest.main()
