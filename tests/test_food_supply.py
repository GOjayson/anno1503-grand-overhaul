"""Authored guard execution plus optional exact native Food 0.5 comparisons.

Executable allocations belong only to this Python test process. Game files are
opened read-only; neither a game process nor its installation is modified.
"""
from __future__ import annotations

import ctypes as C
from contextlib import contextmanager
from decimal import Decimal
import hashlib
import importlib.util
import mmap
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from anno1503_overhaul import food_supply as supply
from anno1503_overhaul.food_progression import combined_score_code
from anno1503_overhaul.world_native import checksum
from anno1503_overhaul.world_runtime_build import PE


class Memory:
    def __init__(self, size):
        self.size = (size + 4095) & ~4095
        if os.name == "nt":
            self.kernel = C.WinDLL("kernel32", use_last_error=True)
            self.kernel.VirtualAlloc.argtypes = [C.c_void_p, C.c_size_t, C.c_uint32, C.c_uint32]
            self.kernel.VirtualAlloc.restype = C.c_void_p
            self.kernel.VirtualProtect.argtypes = [C.c_void_p, C.c_size_t, C.c_uint32, C.POINTER(C.c_uint32)]
            self.kernel.VirtualProtect.restype = C.c_int
            self.kernel.VirtualFree.argtypes = [C.c_void_p, C.c_size_t, C.c_uint32]
            self.kernel.VirtualFree.restype = C.c_int
            self.base = self.kernel.VirtualAlloc(None, self.size, 0x3000, 4)
            if not self.base:
                raise OSError(C.get_last_error(), "Allocate guard fixture")
        else:
            self.mapping = mmap.mmap(-1, self.size, flags=mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS,
                                     prot=mmap.PROT_READ | mmap.PROT_WRITE)
            self.base = C.addressof(C.c_char.from_buffer(self.mapping))

    def put(self, offset, data):
        if not 0 <= offset <= self.size - len(data):
            raise ValueError("Authored fixture leaves its allocation.")
        C.memmove(self.base + offset, data, len(data))

    def execute(self, offset=0, size=None):
        size = self.size - offset if size is None else size
        begin = offset & ~4095
        size = ((offset - begin + size) + 4095) & ~4095
        if os.name == "nt":
            old = C.c_uint32()
            result = self.kernel.VirtualProtect(self.base + begin, size, 0x20, C.byref(old))
        else:
            method = C.CDLL(None).mprotect
            method.argtypes, method.restype = [C.c_void_p, C.c_size_t, C.c_int], C.c_int
            result = method(self.base + begin, size, mmap.PROT_READ | mmap.PROT_EXEC) == 0
        if not result:
            raise OSError("Protect guard fixture as executable")

    def close(self):
        if os.name == "nt":
            if not self.kernel.VirtualFree(self.base, 0, 0x8000):
                raise OSError(C.get_last_error(), "Release guard fixture")
        else:
            self.mapping.close()

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        self.close()


class House:
    def __init__(self):
        self.data = C.create_string_buffer(0xB0)
        self.needs = C.create_string_buffer(0x128)
        self.goods = C.create_string_buffer(96 * 26)
        struct.pack_into("<Q", self.data, 0x48, C.addressof(self.needs))
        struct.pack_into("<Q", self.needs, 0x118, C.addressof(self.goods))
        struct.pack_into("<H", self.data, 0x52, 12)
        C.memset(C.addressof(self.needs) + 3, 255, 96)
        self.count(2)
        for index, (good, rate, stock) in enumerate(((26, 16, 16), (40, 32, 8))):
            self.map(good, index)
            self.needs[0x64 + index * 4] = good
            self.rate(index, rate)
            self.stock(index, stock)
        self.goods[40 * 26 + 2] = 1

    def count(self, count):
        struct.pack_into("<B", self.needs, 2, count)

    def map(self, good, index):
        struct.pack_into("<B", self.needs, good + 3, index)

    def rate(self, index, rate):
        struct.pack_into("<H", self.needs, 0x66 + index * 4, rate)

    def stock(self, index, amount):
        struct.pack_into("<H", self.data, 0x54 + index * 2, amount)

    def before(self):
        return bytes(self.data), bytes(self.needs), bytes(self.goods)


def reviewed_tier_groups():
    """Read the stock and split diets and their original rating tables."""
    from anno1503_overhaul import food_diet
    path = ROOT / ".local/game-copies/World Settings/Data/BGruppen.dat"
    if not path.is_file():
        raise unittest.SkipTest("The reviewed local stock resident definitions are unavailable.")
    vanilla = path.read_bytes()
    if hashlib.sha256(vanilla).hexdigest() != food_diet.STOCK_BGRUPPEN_SHA256:
        raise AssertionError("The private resident fixture differs from its reviewed stock input.")
    loaded = {}
    for name, pin in (
        ("formats", "16ccf7bb69171b12760ce7ffb7b1c86f1269e0483935834103b4d7e13dd6a3de"),
        ("transforms", "1e3b418b4b00b0e190583246933e8418fc570f29d7ab3ffdb290145c30ebd067"),
    ):
        source = ROOT / "legacy/food_overhaul/support" / (name + ".py")
        if hashlib.sha256(source.read_bytes()).hexdigest() != pin:
            raise AssertionError("The immutable Food construction source differs.")
        spec = importlib.util.spec_from_file_location("promotion_fixture_" + name, source)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"formats": loaded.get("formats", module)}):
            spec.loader.exec_module(module)
        loaded[name] = module
    food05 = loaded["transforms"].diet(loaded["transforms"].add_definition(
        loaded["formats"].split_food_demand(vanilla)))
    diets = []
    for data in (vanilla, food_diet.transform_food05(food05)):
        _, section, _ = food_diet._sections(data)
        _, groups = food_diet._groups(section)
        diets.append(tuple((text, tuple(food_diet._NEED.finditer(text))) for _, text in groups))
    return diets


class Residence:
    """Native resident definitions with authored delivered supplies."""

    FOODS = (26, 40, 24, 25, 45)
    FOOD_GATES = {26: 0, 40: 0, 24: 0, 25: 2, 45: 1}
    # In this direct check fixture, population 1200 makes the stock for a
    # given percent equal to rate times percent in native fixed-point units.
    POPULATION = 1200
    TABLES = {"NahrungTab": 0xCF, "BedarfTab": 0xE4, "InfraTab": 0xF9}
    IDS = dict(NAHRUNG=26, WILD2=24, KART2=40, BROT2=25, MEAT2=45,
               LEDER=27, STOFFE=28, SALZ=30, TABAKWAREN=32, GEWUERZE=31,
               LAMPENOEL=33, SEIDESTOFFE=34, KLEIDUNG=35, SCHMUCK=36,
               WEIN=37, PELZE=38, HEILKRAEUTER=39, WIRTSHAUS=76, KAPELLE=77,
               SCHULE=78, KIRCHE=79, BADEHAUS=80, HOCHSCHULE=81, THEATER=82,
               PARK=83, KATHETRALE=84)

    def __init__(self, groups, tier):
        self.data = C.create_string_buffer(0x100)
        self.needs = C.create_string_buffer(0x240)
        self.goods = C.create_string_buffer(96 * 26)
        self.city = C.create_string_buffer(8)
        self.vtable = C.create_string_buffer(0x140)
        self.calls, self.errors, self.maps = 0, [], []
        self.unlocked = 0b111
        # Only Windows fixtures call this virtual. Growth fixtures also run
        # through the MS ABI bridge on other operating systems.
        callback = getattr(C, "WINFUNCTYPE", C.CFUNCTYPE)
        self.promote_callback = callback(C.c_int, C.c_void_p, C.c_void_p)(self.promote)
        struct.pack_into("<Q", self.data, 0x48, C.addressof(self.needs))
        struct.pack_into("<H", self.data, 0x52, self.POPULATION)
        struct.pack_into("<Q", self.data, 0x18, C.addressof(self.city))
        struct.pack_into("<Q", self.city, 0, C.addressof(self.vtable))
        struct.pack_into("<Q", self.vtable, 0x130, C.cast(self.promote_callback, C.c_void_p).value)
        for good, gate in self.FOOD_GATES.items():
            self.goods[good * 26 + 2] = gate
        for which, (body, entries) in enumerate(groups[tier:tier + 2]):
            offset, count = which * 0x120, len(entries)
            no_upgrade = re.search(r"(?m)^[ \t]*NoUpgrade:[ \t]+TRUE", body) is not None
            struct.pack_into("<BBB", self.needs, offset, tier + which, no_upgrade, count)
            struct.pack_into("<Q", self.needs, offset + 0x118, C.addressof(self.goods))
            C.memset(C.addressof(self.needs) + offset + 3, count, 96)
            service_start = next((i for i, item in enumerate(entries) if self.IDS[item["good"]] >= 76), count)
            struct.pack_into("<BB", self.needs, offset + 0xCC, service_start, count)
            mapping = {}
            for i, item in enumerate(entries):
                good = self.IDS[item["good"]]
                mapping[good] = i
                struct.pack_into("<B", self.needs, offset + 3 + good, i)
                rate = int(Decimal(item["amount"]) * Decimal("40.96") + Decimal("0.5"))
                struct.pack_into("<BBH", self.needs, offset + 0x64 + 4 * i,
                                 good, int("TRUE" in item["tail"]), rate)
                if not which:
                    struct.pack_into("<H", self.data, 0x54 + 2 * i, rate * 100)
            # Native IdSec aliases preserve the previous service's coverage.
            for service, alias in ((79, 77), (81, 78), (84, 79)):
                if service not in mapping and alias in mapping:
                    struct.pack_into("<B", self.needs, offset + 3 + service, mapping[alias])
            for table, at in self.TABLES.items():
                match = re.search(rf"(?m)^[ \t]*{table}:[ \t]+([^\r\n;]+)", body)
                values = tuple(int(value) for value in match[1].split(","))
                struct.pack_into("<21b", self.needs, offset + at, *values)
            self.maps.append(mapping)

    def promote(self, city, house):
        if city != C.addressof(self.city) or house != C.addressof(self.data):
            self.errors.append("Unexpected native promotion callback identity.")
            return 0
        self.calls += 1
        return 777

    def deliver(self, good, percent):
        index = self.maps[0][good]
        rate = struct.unpack_from("<H", self.needs, 0x66 + 4 * index)[0]
        struct.pack_into("<H", self.data, 0x54 + 2 * index, rate * percent)

    def deliver_food(self, percent):
        for good in self.FOODS:
            if good in self.maps[0]:
                self.deliver(good, percent)

    def missing(self, good):
        self.needs[good + 3] = self.needs[2]

    def zero_rate(self, good):
        struct.pack_into("<H", self.needs, 0x66 + 4 * self.maps[0][good], 0)

    def before(self):
        return (bytes(self.data), bytes(self.needs), bytes(self.goods), bytes(self.city), bytes(self.vtable))


class _GuardExecution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if C.sizeof(C.c_void_p) != 8:
            raise unittest.SkipTest("AMD64 guard fixtures require an x64 process.")
        cls.bridge_temp = None
        if os.name == "nt":
            native = C.CFUNCTYPE(C.c_uint32, C.c_void_p, C.c_uint32, C.c_uint32)
            cls.invoke_native = staticmethod(lambda address, house, arg, mode: native(address)(house, arg, mode))
        else:
            compiler = shutil.which(os.environ.get("CC", "cc"))
            if not compiler:
                raise unittest.SkipTest("A native compiler is required for the System V to Windows ABI bridge.")
            cls.bridge_temp = tempfile.TemporaryDirectory(prefix="anno-food-guard-bridge-")
            folder = Path(cls.bridge_temp.name)
            source, binary = folder / "bridge.c", folder / "bridge.so"
            source.write_text('''#include <stdint.h>
typedef uint32_t (__attribute__((ms_abi)) *Check)(void*,uint32_t,uint32_t);
__attribute__((visibility("default"))) uint32_t invoke(uintptr_t target,void*house,uint32_t argument,uint32_t mode){
 return ((Check)target)(house,argument,mode);
}
''', encoding="utf-8")
            result = subprocess.run([compiler, "-std=c11", "-shared", "-fPIC", "-O2", "-Wall", "-Wextra",
                                     "-Werror", str(source), "-o", str(binary)], capture_output=True, text=True)
            if result.returncode:
                cls.bridge_temp.cleanup()
                raise AssertionError(result.stdout + result.stderr)
            cls.bridge = C.CDLL(str(binary))
            cls.bridge.invoke.argtypes = [C.c_size_t, C.c_void_p, C.c_uint32, C.c_uint32]
            cls.bridge.invoke.restype = C.c_uint32
            cls.invoke_native = staticmethod(lambda address, house, arg, mode: cls.bridge.invoke(address, house, arg, mode))

    @classmethod
    def tearDownClass(cls):
        del cls.invoke_native
        if cls.bridge_temp is not None:
            del cls.bridge
            cls.bridge_temp.cleanup()

    def invoke(self, address, house, argument, mode=0):
        before = None if house is None else house.before()
        result = self.invoke_native(address, None if house is None else C.addressof(house.data), argument, mode)
        if house is not None:
            self.assertEqual(house.before(), before, "Supply check changed household memory.")
        return result


class CombinedScoreTests(_GuardExecution):
    @contextmanager
    def score(self):
        with Memory(4096) as image:
            image.put(0, combined_score_code())
            image.execute()
            yield image.base

    def test_current_supply_uses_capped_demand_weights_and_the_pioneer_conversion(self):
        house = House()
        with self.score() as score:
            self.assertEqual(self.invoke(score, house, 0b11), 64)
            self.assertEqual(self.invoke(score, house, 0b11, 1), 70)
            house.stock(0, 65535)
            self.assertEqual(self.invoke(score, house, 0b11), 64)
            self.assertEqual(self.invoke(score, house, 0b11, 1), 70)
            house.needs[0] = 1
            self.assertEqual(self.invoke(score, house, 0b11, 1), 64)
            house.stock(1, 32)
            self.assertEqual(self.invoke(score, house, 0b11, 1), 128)

    def test_rounding_uses_fixed_point_supply_scores_before_final_weighted_conversion(self):
        house = House()
        house.rate(0, 17)
        house.rate(1, 31)
        with self.score() as score:
            # Delivered scores floor to 120 and 33 before demand weighting.
            # Conversion uses the full weighted numerator (3063), not 63.
            self.assertEqual(self.invoke(score, house, 0b11), 63)
            self.assertEqual(self.invoke(score, house, 0b11, 1), 70)

    def test_ineligible_or_invalid_food_does_not_add_weight_or_satisfy_an_empty_diet(self):
        house = House()
        with self.score() as score:
            self.assertEqual(self.invoke(score, house, 0b01), 128)
            self.assertEqual(self.invoke(score, house, 0b10), 32)
            self.assertEqual(self.invoke(score, house, 0), 0)
            house.map(26, 1)  # Potato record must not also satisfy the Fish need.
            self.assertEqual(self.invoke(score, house, 0b11), 32)
            house.rate(1, 0)
            self.assertEqual(self.invoke(score, house, 0b11), 0)
            house.rate(1, 32)
            house.goods[40 * 26 + 2] = 32
            self.assertEqual(self.invoke(score, house, 0xffffffff), 0)

            house = House()
            struct.pack_into("<H", house.data, 0x52, 0)
            self.assertEqual(self.invoke(score, house, 0b11), 0)
            self.assertEqual(self.invoke(score, None, 0b11), 0)


class GuardInstructions(_GuardExecution):
    def test_authored_guards_delegate_inputs_and_reject_missing_needs_without_division(self):
        with Memory(4096) as image:
            # Authored native stand-in: empty population ->128; otherwise echo
            # the original EDX with a marker. This proves argument preservation.
            original = bytes.fromhex("66 83 79 52 00 74 08 89 d0 35 00 04 00 00 c3 b8 80 00 00 00 c3")
            image.put(0x800, original)
            image.put(0x900, original)
            for rva, target, indexed in ((0x100, 0x800, False), (0x200, 0x900, True)):
                code, _ = supply.guard_code(rva, target, indexed=indexed)
                image.put(rva, code)
            image.execute()
            good, index = image.base + 0x100, image.base + 0x200
            house = House()
            self.assertEqual(self.invoke(good, house, 26), 0x400 ^ 26)
            self.assertEqual(self.invoke(good, house, 40), 0x400 ^ 40)
            self.assertEqual(self.invoke(index, house, 0), 0x400)
            self.assertEqual(self.invoke(index, house, 1), 0x401)
            for argument in (25, 96, 0xFFFFFFFF):
                self.assertEqual(self.invoke(good, house, argument), 0)
            for argument in (2, 18, 0xFFFFFFFF):
                self.assertEqual(self.invoke(index, house, argument), 0)
            self.assertEqual(self.invoke(good, None, 26), 0)
            self.assertEqual(self.invoke(index, None, 0), 0)
            house.rate(0, 0)
            self.assertEqual(self.invoke(good, house, 26), 0)
            self.assertEqual(self.invoke(index, house, 0), 0)
            for count in (0, 19, 255):
                house.count(count)
                self.assertEqual(self.invoke(good, house, 40), 0)
                self.assertEqual(self.invoke(index, house, 1), 0)
            struct.pack_into("<Q", house.data, 0x48, 0)
            self.assertEqual(self.invoke(good, house, 26), 0)
            self.assertEqual(self.invoke(index, house, 0), 0)
            struct.pack_into("<H", house.data, 0x52, 0)
            self.assertEqual(self.invoke(good, house, 0xFFFFFFFF), 128)
            self.assertEqual(self.invoke(index, house, 0xFFFFFFFF), 128)

    def test_last_safe_slot_and_good_id_are_not_rejected(self):
        with Memory(4096) as image:
            image.put(0x800, bytes.fromhex("89 d0 c3"))  # MOV EAX,EDX / RET
            for rva, indexed in ((0x100, False), (0x200, True)):
                code, _ = supply.guard_code(rva, 0x800, indexed=indexed)
                image.put(rva, code)
            image.execute()
            house = House()
            house.count(18)
            house.map(95, 17)
            house.rate(17, 65535)
            self.assertEqual(self.invoke(image.base + 0x100, house, 95), 95)
            self.assertEqual(self.invoke(image.base + 0x200, house, 17), 17)


class GuardConstructionTests(unittest.TestCase):
    def test_unknown_mutated_and_mutable_native_inputs_refuse_before_construction(self):
        with patch.object(supply, "guard_code") as guard:
            for value in (b"", b"MZ" + bytes(300), bytearray(b"MZ"), "native"):
                with self.subTest(kind=type(value)), self.assertRaises(supply.FoodSupplyError):
                    supply.build_welt(value)
            guard.assert_not_called()

    def test_REL32_fixups_are_bounded_and_relocate_to_the_same_native_targets(self):
        for indexed in (False, True):
            for rva in (0x100, 0x153000):
                code, fixups = supply.guard_code(rva, 0x88DF0, indexed=indexed)
                self.assertTrue(code.endswith(bytes.fromhex("31c0c3")))
                for branch in fixups:
                    displacement = struct.unpack_from("<i", code, branch["displacement_offset"])[0]
                    self.assertEqual(rva + branch["displacement_offset"] + 4 + displacement, branch["target_rva"])
                    self.assertTrue(branch["target_rva"] == 0x88DF0
                                    or rva <= branch["target_rva"] < rva + len(code))
        for values in ((-1, 2, False), (1, -2, False), (1, 1 << 40, False), (1, 2, 1)):
            with self.subTest(values=values), self.assertRaises(supply.FoodSupplyError):
                supply.guard_code(values[0], values[1], indexed=values[2])

    def test_instruction_audit_has_no_stack_calls_nonvolatile_writes_or_memory_writes(self):
        with patch.object(sys, "path", [str(ROOT / ".local/toolchain/world-options-validation"), *sys.path]):
            try:
                import capstone
            except ImportError:
                self.skipTest("The optional reviewed instruction decoder is unavailable.")
        decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        decoder.detail = True
        for indexed in (False, True):
            code, _ = supply.guard_code(0x153000, 0x88DF0, indexed=indexed)
            instructions = tuple(decoder.disasm(code, 0x153000))
            self.assertEqual(sum(instruction.size for instruction in instructions), len(code))
            for instruction in instructions:
                self.assertNotIn(instruction.mnemonic, ("call", "push", "pop", "enter", "leave"))
                if instruction.mnemonic != "ret":
                    _, writes = instruction.regs_access()
                    self.assertTrue({decoder.reg_name(register) for register in writes}.issubset(
                        {"eax", "rax", "r8", "r9d", "r9", "eflags", "rflags"}), instruction.op_str)
                    self.assertNotIn("rsp", instruction.op_str)
                for operand in instruction.operands:
                    if operand.type == capstone.CS_OP_MEM:
                        self.assertFalse(operand.access & capstone.CS_AC_WRITE, instruction.op_str)


class OriginalSupplyTests(_GuardExecution):
    """The exact game-byte cases additionally need the locally owned baseline."""
    def setUp(self):
        self.path = ROOT / ".local/baselines/world_settings/native/AnnoWelt.source.dll"
        if not self.path.is_file():
            self.skipTest("Exact locally owned Food 0.5 World module is unavailable.")
        self.original = self.path.read_bytes()
        self.assertEqual(hashlib.sha256(self.original).hexdigest(), supply.FOOD05_WELT_SHA256)

    @contextmanager
    def mapped(self, output):
        pe = PE(output)
        preferred = struct.unpack_from("<Q", output, pe.optional + 24)[0]
        with Memory(pe.image_size) as image:
            image.put(0, output[:pe.header_size])
            for section in pe.sections:
                image.put(section["rva"], output[section["raw"]:section["raw"] + section["raw_size"]])
            for target in supply.relocation_entries(pe):
                pointer = C.c_uint64.from_address(image.base + target)
                pointer.value = (pointer.value + image.base - preferred) & ((1 << 64) - 1)
            for section in pe.sections:
                if section["flags"] & 0x20000000:
                    image.execute(section["rva"], max(section["virtual"], section["raw_size"]))
            registered = False
            if os.name == "nt":
                kernel = C.WinDLL("kernel32", use_last_error=True)
                kernel.RtlAddFunctionTable.argtypes = [C.c_void_p, C.c_uint32, C.c_uint64]
                kernel.RtlAddFunctionTable.restype = C.c_ubyte
                kernel.RtlDeleteFunctionTable.argtypes = [C.c_void_p]
                kernel.RtlDeleteFunctionTable.restype = C.c_ubyte
                table, size = pe.directory(3)
                self.assertTrue(kernel.RtlAddFunctionTable(image.base + table, size // 12, image.base))
                registered = True
            try:
                yield image, pe
            finally:
                if registered:
                    self.assertTrue(kernel.RtlDeleteFunctionTable(image.base + table))

    def test_fixed_derivative_preserves_old_sections_tables_and_existing_relocations(self):
        output, proof = supply.build_welt(self.original)
        self.assertEqual(supply.build_welt(self.original), (output, proof))
        self.assertEqual(hashlib.sha256(output).hexdigest(), supply.FOOD06_WELT_SHA256)
        before, after = PE(self.original), PE(output)
        self.assertEqual(before.sections, after.sections[:-1])
        self.assertEqual(after.sections[-1]["name"], ".food06")
        self.assertEqual(after.sections[-1]["flags"], 0x60000020)
        promotion = proof["promotion_guard"]
        expected_entry = (promotion["target_rva"], promotion["target_rva"] + promotion["code_size"],
                          promotion["unwind_rva"])
        self.assertEqual(after.function_table(), before.function_table() | {expected_entry})
        self.assertEqual(after.read(promotion["unwind_rva"], 16),
                         b"\x21\x00\x00\x00" + struct.pack("<III", *promotion["unwind_parent"]))
        self.assertEqual(tuple(promotion["unwind_parent"]), (0x881D9, 0x88315, 0x118CDC))
        self.assertEqual(supply.relocation_entries(before), supply.relocation_entries(after))
        for directory in range(16):
            if directory != 3:
                self.assertEqual(before.directory(directory), after.directory(directory))
        allowed = set()
        base = struct.unpack_from("<Q", self.original, before.optional + 24)[0]
        for hook in proof["hooks"]:
            offset = before.offset(hook["vtable_rva"], 8)
            allowed.update(range(offset, offset + 8))
            self.assertEqual(struct.unpack("<Q", after.read(hook["vtable_rva"], 8))[0], base + hook["target_rva"])
            self.assertIn(hook["vtable_rva"], supply.relocation_entries(after))
            self.assertEqual(after.read(hook["original_rva"], hook["original_size"]),
                             before.read(hook["original_rva"], hook["original_size"]))
        offset = before.offset(promotion["patch_rva"], 14)
        allowed.update(range(offset, offset + 14))
        self.assertEqual(before.read(promotion["patch_rva"], 14).hex(), promotion["preimage"])
        self.assertEqual(after.read(promotion["patch_rva"], 14).hex(), promotion["patch"])
        self.assertEqual(promotion["only_missing_future_foods_skipped"], [25, 45])
        changed = {i for i in range(before.header_size, len(self.original)) if self.original[i] != output[i]}
        self.assertTrue(changed)
        self.assertTrue(changed.issubset(allowed))
        self.assertEqual(struct.unpack_from("<I", output, after.optional + 64)[0], checksum(output))
        self.assertFalse(proof["actual_game_test_performed"])
        self.assertEqual(self.path.read_bytes(), self.original)
        with self.assertRaises(supply.FoodSupplyError):
            supply.build_welt(output)
        with self.assertRaises(supply.FoodSupplyError):
            supply.build_welt(self.original[:-1] + bytes([self.original[-1] ^ 1]))

    def test_actual_original_getters_match_guarded_results_after_loader_relocations(self):
        output, proof = supply.build_welt(self.original)
        pe = PE(output)
        preferred = struct.unpack_from("<Q", output, pe.optional + 24)[0]
        with self.mapped(output) as (image, pe):
            self.assertNotEqual(image.base, preferred)
            guards = {hook["kind"]: C.c_uint64.from_address(image.base + hook["vtable_rva"]).value
                      for hook in proof["hooks"]}
            house = House()
            for population, rate, stock in ((12, 16, 16), (12, 16, 8), (12, 16, 32), (8, 24, 2)):
                struct.pack_into("<H", house.data, 0x52, population)
                house.rate(0, rate)
                house.stock(0, stock)
                expected = self.invoke(image.base + 0x88DF0, house, 26)
                self.assertEqual(self.invoke(guards["good"], house, 26), expected)
                self.assertEqual(self.invoke(image.base + 0x88E40, house, 0), expected)
                self.assertEqual(self.invoke(guards["index"], house, 0), expected)
            self.assertEqual(self.invoke(guards["good"], house, 25), 0)
            self.assertEqual(self.invoke(guards["index"], house, 2), 0)
            house.rate(0, 0)
            self.assertEqual(self.invoke(guards["good"], house, 26), 0)
            self.assertEqual(self.invoke(guards["index"], house, 0), 0)
            struct.pack_into("<H", house.data, 0x52, 0)
            struct.pack_into("<Q", house.data, 0x48, 0)
            for kind, original in (("good", 0x88DF0), ("index", 0x88E40)):
                self.assertEqual(self.invoke(image.base + original, house, 0xFFFFFFFF), 128)
                self.assertEqual(self.invoke(guards[kind], house, 0xFFFFFFFF), 128)

    def test_progression_derivative_preserves_untouched_code_and_native_metadata(self):
        output, proof = supply.build_progression_welt(self.original)
        self.assertEqual(supply.build_progression_welt(self.original), (output, proof))
        before, after = PE(self.original), PE(output)
        self.assertEqual(after.sections[:-1], before.sections)
        self.assertEqual(after.sections[-1]["name"], ".food06")
        self.assertEqual(after.sections[-1]["flags"], 0x60000020)
        self.assertEqual(supply.relocation_entries(after), supply.relocation_entries(before))
        for directory in range(16):
            if directory != 3:
                self.assertEqual(after.directory(directory), before.directory(directory))
        score = combined_score_code()
        self.assertEqual(after.read(proof["food_progression_score_rva"], len(score)), score)
        detours = [proof["promotion_guard"], *proof["food_progression_hooks"]]
        allowed, new_entries = set(), set()
        for edit in detours:
            previous = bytes.fromhex(edit["preimage"])
            replacement = bytes.fromhex(edit["patch"])
            self.assertEqual(len(previous), len(replacement))
            rva = edit["patch_rva"]
            self.assertEqual(before.read(rva, len(previous)), previous)
            self.assertEqual(after.read(rva, len(replacement)), replacement)
            offset = before.offset(rva, len(previous))
            allowed.update(range(offset, offset + len(previous)))
            if edit.get("unwind_rva") is not None:
                if edit["unwind_parent"] is None:
                    self.assertEqual(edit["stack_allocation"], 0xA8)
                    # Version 1, one UWOP_ALLOC_LARGE operation, no chain.
                    self.assertEqual(after.read(edit["unwind_rva"], 8),
                                     bytes.fromhex("01 07 02 00 07 01 15 00"))
                else:
                    parent = tuple(edit["unwind_parent"])
                    self.assertIn(parent, before.function_table())
                    self.assertEqual(after.read(edit["unwind_rva"], 16),
                                     b"\x21\x00\x00\x00" + struct.pack("<III", *parent))
                start = edit["target_rva"]
                new_entries.add((start, start + edit["code_size"], edit["unwind_rva"]))
        self.assertEqual(after.function_table(), before.function_table() | new_entries)
        self.assertEqual(proof["new_unwind_entries"], len(new_entries))
        for getter in proof["hooks"]:
            offset = before.offset(getter["vtable_rva"], 8)
            allowed.update(range(offset, offset + 8))
        actual_writes = {i for i in range(before.header_size, len(self.original))
                         if self.original[i] != output[i]}
        self.assertTrue(actual_writes.issubset(allowed))
        self.assertEqual(struct.unpack_from("<I", output, after.optional + 64)[0], checksum(output))
        self.assertEqual(self.path.read_bytes(), self.original)
        with self.assertRaises(supply.FoodSupplyError):
            supply.build_progression_welt(output)

    def resident_score(self, image, address, house):
        return C.c_int32(self.invoke(image.base + address, house, house.unlocked)).value

    @unittest.skipUnless(os.name == "nt", "The promotion adapter uses a Windows x64 city callback.")
    def test_native_tick_adapters_forward_the_owner_mask_from_the_tick_stack(self):
        _, groups = reviewed_tier_groups()
        output, proof = supply.build_progression_welt(self.original)
        relays = {hook["name"]: hook for hook in proof["food_progression_hooks"]}
        cases = (("growth unlock mask", 0x887CB, 0x88380, (2, -2)),
                 ("promotion unlock mask", 0x888A3, 0x881B0, (777, 0)))
        with self.mapped(output) as (image, pe):
            for name, source, native, expected in cases:
                with self.subTest(adapter=name), Memory(4096) as caller:
                    target = relays[name]["target_rva"]
                    self.assertEqual(relays[name]["patch_rva"], source)
                    # Check the original tick's CALL itself and the relay's
                    # final tail jump independently of the proof destinations.
                    self.assertEqual(pe.read(source, 5), b"\xe8" + struct.pack("<i", target - source - 5))
                    self.assertEqual(pe.read(target + 4, 5), b"\xe9" + struct.pack("<i", native - target - 9))
                    # Recreate the tick call frame with the owner mask at +38h.
                    # A poisoned EDX proves the called adapter fetches that
                    # value from its caller's stack and forwards it correctly.
                    trampoline = (bytes.fromhex("4883ec48 89542438 baffffffff 48b8")
                                  + struct.pack("<Q", image.base + target)
                                  + bytes.fromhex("ffd0 4883c448 c3"))
                    caller.put(0, trampoline)
                    caller.execute()
                    house = Residence(groups, 0)
                    for unlocks, outcome in zip((0b111, 0), expected):
                        score = C.c_int32(self.invoke(caller.base, house, unlocks)).value
                        self.assertEqual(score, outcome)

    @unittest.skipUnless(os.name == "nt", "The public growth adapter uses Windows x64 callbacks.")
    def test_public_growth_vtable_resolves_and_uses_the_house_owners_unlocks(self):
        _, groups = reviewed_tier_groups()
        output, proof = supply.build_progression_welt(self.original)
        adapter = next(hook for hook in proof["food_progression_hooks"]
                       if hook["name"] == "growth vtable adapter")
        with self.mapped(output) as (image, _):
            self.assertEqual(adapter["patch_rva"], 0xFA028)
            target = C.c_uint64.from_address(image.base + 0xFA028).value
            self.assertEqual(target, image.base + adapter["target_rva"])

            house = Residence(groups, 1)
            house.deliver(45, 0)
            profile = C.create_string_buffer(8)
            profile_vtable = C.create_string_buffer(0xA0)
            property_result, write_property = 1, True
            seen = []

            @C.WINFUNCTYPE(C.c_void_p, C.c_void_p)
            def get_profile(city):
                seen.append((city,))
                return C.addressof(profile)

            @C.WINFUNCTYPE(C.c_int, C.c_void_p, C.c_uint32, C.c_void_p)
            def read_property(profile_address, property_id, value):
                seen.append((profile_address, property_id))
                if write_property:
                    C.c_uint64.from_address(value + 8).value = house.unlocked
                return property_result

            struct.pack_into("<Q", profile, 0, C.addressof(profile_vtable))
            struct.pack_into("<Q", house.vtable, 0x40, C.cast(get_profile, C.c_void_p).value)
            struct.pack_into("<Q", profile_vtable, 0x98, C.cast(read_property, C.c_void_p).value)
            cases = ((0b101, 1, True, 2), (0, 1, True, -2), (0b101, 0, True, 2), (0b101, 0, False, -2))
            for mask, property_result, write_property, expected in cases:
                house.unlocked = mask
                # Incoming EDX is unrelated under this public one-argument ABI.
                score = C.c_int32(self.invoke(target, house, mask ^ 0b111)).value
                self.assertEqual(score, expected)
            self.assertEqual(seen, [(C.addressof(house.city),), (C.addressof(profile), 0x21)] * len(cases))
            seen.clear()
            struct.pack_into("<H", house.data, 0x52, 0)
            self.assertEqual(self.invoke(target, house, 0xffffffff), 0)
            self.assertEqual(seen, [])

    @unittest.skipUnless(os.name == "nt", "Native promotion uses a Windows x64 city callback.")
    def test_uniform_delivery_has_vanilla_promotion_thresholds_for_all_three_upgrades(self):
        stock_groups, split_groups = reviewed_tier_groups()
        output, _ = supply.build_progression_welt(self.original)
        with self.mapped(self.original) as (stock, _), self.mapped(output) as (split, _):
            address = supply.PROMOTION["begin"]
            for tier, first_passing in enumerate((77, 91, 91)):
                vanilla = Residence(stock_groups, tier)
                changed = Residence(split_groups, tier)
                for percent in range(101):
                    with self.subTest(tier=tier, percent=percent):
                        vanilla.deliver_food(percent)
                        changed.deliver_food(percent)
                        expected = 777 if percent >= first_passing else 0
                        self.assertEqual(self.resident_score(stock, address, vanilla), expected)
                        self.assertEqual(self.resident_score(split, address, changed), expected)
                self.assertEqual(vanilla.calls, 101 - first_passing)
                self.assertEqual(changed.calls, vanilla.calls)
                self.assertEqual(vanilla.errors + changed.errors, [])
            for tier in (3, 4):
                house = Residence(split_groups, tier)
                self.assertEqual(self.resident_score(split, address, house), 0)

    @unittest.skipUnless(os.name == "nt", "Native promotion uses a Windows x64 city callback.")
    def test_promotion_preserves_goods_services_and_uses_only_the_current_active_diet(self):
        stock_groups, split_groups = reviewed_tier_groups()
        output, _ = supply.build_progression_welt(self.original)
        address = supply.PROMOTION["begin"]
        with self.mapped(self.original) as (stock, _), self.mapped(output) as (split, _):
            # Separate food votes previously let full supplies conceal a
            # missing cloth and salt supply in this exact Pioneer table.
            for missing in ((), (28,), (28, 30), (76,)):
                with self.subTest(missing=missing):
                    vanilla = Residence(stock_groups, 0)
                    changed = Residence(split_groups, 0)
                    for good in missing:
                        vanilla.deliver(good, 0)
                        changed.deliver(good, 0)
                    stock_result = self.resident_score(stock, address, vanilla)
                    self.assertEqual(self.resident_score(split, address, changed), stock_result)
                    if len(missing) == 2 or missing == (76,):
                        self.assertEqual(stock_result, 0)

            pioneer = Residence(split_groups, 0)
            pioneer.deliver(24, 0)
            pioneer.deliver(40, 0)
            pioneer.deliver(26, 500)
            self.assertEqual(self.resident_score(split, address, pioneer), 0)
            pioneer.deliver(40, 100)
            self.assertEqual(self.resident_score(split, address, pioneer), 777)

            for tier, food in ((1, 45), (2, 25)):
                with self.subTest(tier=tier, food=food):
                    house = Residence(split_groups, tier)
                    house.deliver(food, 0)
                    house.unlocked &= ~(1 << house.FOOD_GATES[food])
                    self.assertEqual(self.resident_score(split, address, house), 777)
                    house.unlocked = 0b111
                    self.assertEqual(self.resident_score(split, address, house), 0)
                    house.deliver(food, 100)
                    self.assertEqual(self.resident_score(split, address, house), 777)

            for method in (Residence.missing, Residence.zero_rate):
                house = Residence(split_groups, 0)
                method(house, 28)
                self.assertEqual(self.resident_score(split, address, house), 0)
                self.assertEqual(house.calls, 0)

    def test_native_growth_and_decline_match_vanilla_for_equal_coverage(self):
        stock_groups, split_groups = reviewed_tier_groups()
        output, _ = supply.build_progression_welt(self.original)
        address = 0x88380
        with self.mapped(self.original) as (stock, _), self.mapped(output) as (split, _):
            for tier in range(len(stock_groups)):
                vanilla = Residence(stock_groups, tier)
                changed = Residence(split_groups, tier)
                for percent in range(101):
                    with self.subTest(tier=tier, percent=percent):
                        vanilla.deliver_food(percent)
                        changed.deliver_food(percent)
                        expected = self.resident_score(stock, address, vanilla)
                        self.assertEqual(self.resident_score(split, address, changed), expected)
                        if percent == 0:
                            self.assertLess(expected, 0)
                        if percent == 100:
                            self.assertGreater(expected, 0)

            vanilla = Residence(stock_groups, 0)
            changed = Residence(split_groups, 0)
            vanilla.deliver(28, 0)
            changed.deliver(28, 0)
            for house in (vanilla, changed):
                house.deliver(27, 0)
            self.assertEqual(self.resident_score(split, address, changed),
                             self.resident_score(stock, address, vanilla))

            changed = Residence(split_groups, 0)
            changed.deliver(26, 0)
            vanilla = Residence(stock_groups, 0)
            vanilla.deliver_food(55)  # The quantized Potato and Game Meat shares total 55%.
            expected = self.resident_score(stock, address, vanilla)
            self.assertGreaterEqual(expected, 0)
            self.assertEqual(self.resident_score(split, address, changed), expected)

    @unittest.skipUnless(os.name == "nt", "Native promotion uses a Windows x64 city callback.")
    def test_legacy_promotion_guard_still_handles_missing_future_food(self):
        _, groups = reviewed_tier_groups()
        output, _ = supply.build_welt(self.original)
        with self.mapped(output) as (image, _):
            for tier in (0, 1):
                cases = ((None, ()), (Residence.deliver, (76, 0)), (Residence.missing, (28,)),
                         (Residence.zero_rate, (28,)), (Residence.zero_rate, (24,)))
                for method, arguments in cases:
                    with self.subTest(tier=tier, method=method, arguments=arguments):
                        house = Residence(groups, tier)
                        if method:
                            method(house, *arguments)
                        expected = 777 if method is None else 0
                        self.assertEqual(self.resident_score(image, supply.PROMOTION["begin"], house), expected)
                        self.assertEqual(house.calls, int(method is None))
                        self.assertEqual(house.errors, [])

    def assert_hook_unwind(self, image, pe, hook, *, growth):
        table, size = pe.directory(3)
        rows = list(struct.iter_unpack("<III", pe.read(table, size)))
        index = next(i for i, row in enumerate(rows) if row[0] == hook["target_rva"])
        entry = image.base + table + index * 12
        kernel = C.WinDLL("kernel32")
        unwind = kernel.RtlVirtualUnwind
        unwind.argtypes = [C.c_uint32, C.c_uint64, C.c_uint64, C.c_void_p, C.c_void_p,
                           C.POINTER(C.c_void_p), C.POINTER(C.c_uint64), C.c_void_p]
        unwind.restype = C.c_void_p
        stack = C.create_string_buffer(512)
        rsp = (C.addressof(stack) + 128 + 15) & ~15
        if hook["unwind_parent"] is None:
            saved = {}
            return_offset = hook["stack_allocation"]
        elif growth:
            saved = {"rbx": (0x20, 144), "r12": (0x08, 216), "r15": (0x00, 240),
                     "r14": (0x38, 232), "rdi": (0x30, 176), "rbp": (0x10, 160)}
            return_offset = 0x18
        else:
            saved = {"rbx": (0x50, 144), "rsi": (0x58, 168), "r12": (0x60, 216),
                     "r15": (0x20, 240), "r14": (0x28, 232), "r13": (0x30, 224),
                     "rdi": (0x38, 176), "rbp": (0x40, 160)}
            return_offset = 0x48
        expected = {}
        for i, (name, (offset, _)) in enumerate(saved.items()):
            expected[name] = 0x1234000000000000 + i
            C.c_uint64.from_address(rsp + offset).value = expected[name]
        return_address = 0x123456789ABC0000
        C.c_uint64.from_address(rsp + return_offset).value = return_address
        if hook["unwind_parent"] is None:
            prologue_size = pe.read(hook["unwind_rva"], 2)[1]
            cases = [("adapter body", hook["target_rva"] + prologue_size, entry)]
        else:
            native_index = rows.index(tuple(hook["unwind_parent"]))
            native_entry = image.base + table + native_index * 12
            # The original entry must still unwind the native frame, as must
            # every byte of the appended in-frame continuation.
            cases = [("thunk", hook["target_rva"] + i, entry) for i in range(hook["code_size"])]
            cases += [("entry", hook["patch_rva"] + i, native_entry)
                      for i in range(len(bytes.fromhex(hook["patch"])))]
        for location, rva, function_entry in cases:
            with self.subTest(location=location, rva=hex(rva)):
                context = C.create_string_buffer(1232 + 16)
                aligned = (C.addressof(context) + 15) & ~15
                C.c_uint32.from_address(aligned + 48).value = 0x100003
                C.c_uint64.from_address(aligned + 152).value = rsp
                pc = image.base + rva
                C.c_uint64.from_address(aligned + 248).value = pc
                handler, frame = C.c_void_p(), C.c_uint64()
                unwind(0, image.base, pc, function_entry, aligned, C.byref(handler), C.byref(frame), None)
                self.assertEqual(C.c_uint64.from_address(aligned + 248).value, return_address)
                self.assertEqual(C.c_uint64.from_address(aligned + 152).value, rsp + return_offset + 8)
                for name, (_, context_offset) in saved.items():
                    self.assertEqual(C.c_uint64.from_address(aligned + context_offset).value, expected[name], name)

    @unittest.skipUnless(os.name == "nt", "Native chained unwind requires Windows x64.")
    def test_promotion_thunk_unwind_restores_the_complete_native_frame(self):
        output, proof = supply.build_welt(self.original)
        with self.mapped(output) as (image, pe):
            self.assert_hook_unwind(image, pe, proof["promotion_guard"], growth=False)

    @unittest.skipUnless(os.name == "nt", "Native chained unwind requires Windows x64.")
    def test_progression_thunks_unwind_to_the_native_growth_or_promotion_frame(self):
        output, proof = supply.build_progression_welt(self.original)
        with self.mapped(output) as (image, pe):
            self.assert_hook_unwind(image, pe, proof["promotion_guard"], growth=False)
            for hook in proof["food_progression_hooks"]:
                if "unwind_parent" in hook:
                    with self.subTest(hook=hook["name"]):
                        self.assert_hook_unwind(image, pe, hook, growth=hook["name"].startswith("growth"))


if __name__ == "__main__":
    unittest.main()
