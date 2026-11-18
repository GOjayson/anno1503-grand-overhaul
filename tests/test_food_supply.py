"""Authored guard execution plus optional exact native Food 0.5 comparisons.

Executable allocations belong only to this Python test process. Game files are
opened read-only; neither a game process nor its installation is modified.
"""
from __future__ import annotations

import ctypes as C
from contextlib import contextmanager
import hashlib
import importlib.util
import mmap
import os
from pathlib import Path
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
        struct.pack_into("<Q", self.data, 0x48, C.addressof(self.needs))
        struct.pack_into("<H", self.data, 0x52, 12)
        C.memset(C.addressof(self.needs) + 3, 255, 96)
        self.count(2)
        for index, (good, rate, stock) in enumerate(((26, 16, 16), (40, 32, 8))):
            self.map(good, index)
            self.rate(index, rate)
            self.stock(index, stock)

    def count(self, count):
        struct.pack_into("<B", self.needs, 2, count)

    def map(self, good, index):
        struct.pack_into("<B", self.needs, good + 3, index)

    def rate(self, index, rate):
        struct.pack_into("<H", self.needs, 0x66 + index * 4, rate)

    def stock(self, index, amount):
        struct.pack_into("<H", self.data, 0x54 + index * 2, amount)

    def before(self):
        return bytes(self.data), bytes(self.needs)


def reviewed_tier_groups():
    """Read actual diet membership without installing or publishing native data."""
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
    result = food_diet.transform_food05(food05)
    _, section, _ = food_diet._sections(result)
    _, groups = food_diet._groups(section)
    return tuple((name, tuple(food_diet._NEED.finditer(text))) for name, text in groups)


class PromotionFamily:
    """Real diet membership/Force flags with authored rates and supply buffers."""
    IDS = dict(NAHRUNG=26, WILD2=24, KART2=40, BROT2=25, MEAT2=45,
               LEDER=27, STOFFE=28, SALZ=30, TABAKWAREN=32, GEWUERZE=31,
               LAMPENOEL=33, SEIDESTOFFE=34, KLEIDUNG=35, SCHMUCK=36,
               WEIN=37, PELZE=38, HEILKRAEUTER=39, WIRTSHAUS=76, KAPELLE=77,
               SCHULE=78, KIRCHE=79, BADEHAUS=80, HOCHSCHULE=81, THEATER=82,
               PARK=83, KATHETRALE=84)

    def __init__(self, groups, tier):
        self.data = C.create_string_buffer(0x100)
        self.needs = C.create_string_buffer(0x240)
        self.city = C.create_string_buffer(8)
        self.vtable = C.create_string_buffer(0x140)
        self.calls, self.errors, self.maps = 0, [], []
        self.callback = C.WINFUNCTYPE(C.c_int, C.c_void_p, C.c_void_p)(self.promote)
        struct.pack_into("<Q", self.data, 0x48, C.addressof(self.needs))
        struct.pack_into("<H", self.data, 0x52, 12)
        struct.pack_into("<Q", self.data, 0x18, C.addressof(self.city))
        struct.pack_into("<Q", self.city, 0, C.addressof(self.vtable))
        struct.pack_into("<Q", self.vtable, 0x130, C.cast(self.callback, C.c_void_p).value)
        for which, (_, entries) in enumerate(groups[tier:tier + 2]):
            offset, count = which * 0x120, len(entries)
            struct.pack_into("<B", self.needs, offset + 2, count)
            C.memset(C.addressof(self.needs) + offset + 3, count, 96)
            service_start = next((i for i, item in enumerate(entries) if self.IDS[item["good"]] >= 76), count)
            struct.pack_into("<BB", self.needs, offset + 0xCC, service_start, count)
            mapping = {}
            for i, item in enumerate(entries):
                good = self.IDS[item["good"]]
                mapping[good] = i
                struct.pack_into("<B", self.needs, offset + 3 + good, i)
                struct.pack_into("<BBH", self.needs, offset + 0x64 + 4 * i,
                                 good, int("TRUE" in item["tail"]), 96)
                if not which:
                    struct.pack_into("<H", self.data, 0x54 + 2 * i, 96)
            # Native IdSec aliases preserve the previous service's coverage.
            for service, alias in ((79, 77), (81, 78), (84, 79)):
                if service not in mapping and alias in mapping:
                    struct.pack_into("<B", self.needs, offset + 3 + service, mapping[alias])
            for i in range(21):
                struct.pack_into("<B", self.needs, offset + 0xCF + i, int(i > 0))
                struct.pack_into("<B", self.needs, offset + 0xE4 + i, int(i >= 16))
                struct.pack_into("<B", self.needs, offset + 0xF9 + i, int(i > 0))
            self.maps.append(mapping)

    def promote(self, city, house):
        if city != C.addressof(self.city) or house != C.addressof(self.data):
            self.errors.append("Unexpected native promotion callback identity.")
            return 0
        self.calls += 1
        return 777

    def stock(self, good, amount):
        struct.pack_into("<H", self.data, 0x54 + 2 * self.maps[0][good], amount)

    def missing(self, good):
        self.needs[good + 3] = self.needs[2]

    def zero_rate(self, good):
        struct.pack_into("<H", self.needs, 0x66 + 4 * self.maps[0][good], 0)

    def before(self):
        return bytes(self.data), bytes(self.needs), bytes(self.city), bytes(self.vtable)


class _GuardExecution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if C.sizeof(C.c_void_p) != 8:
            raise unittest.SkipTest("AMD64 guard fixtures require an x64 process.")
        cls.bridge_temp = None
        if os.name == "nt":
            native = C.CFUNCTYPE(C.c_uint32, C.c_void_p, C.c_uint32)
            cls.invoke_native = staticmethod(lambda address, house, argument: native(address)(house, argument))
        else:
            compiler = shutil.which(os.environ.get("CC", "cc"))
            if not compiler:
                raise unittest.SkipTest("A native compiler is required for the System V to Windows ABI bridge.")
            cls.bridge_temp = tempfile.TemporaryDirectory(prefix="anno-food-guard-bridge-")
            folder = Path(cls.bridge_temp.name)
            source, binary = folder / "bridge.c", folder / "bridge.so"
            source.write_text('''#include <stdint.h>
typedef uint32_t (__attribute__((ms_abi)) *Getter)(void*,uint32_t);
__attribute__((visibility("default"))) uint32_t invoke(uintptr_t target,void*house,uint32_t argument){
 return ((Getter)target)(house,argument);
}
''', encoding="utf-8")
            result = subprocess.run([compiler, "-std=c11", "-shared", "-fPIC", "-O2", "-Wall", "-Wextra",
                                     "-Werror", str(source), "-o", str(binary)], capture_output=True, text=True)
            if result.returncode:
                cls.bridge_temp.cleanup()
                raise AssertionError(result.stdout + result.stderr)
            cls.bridge = C.CDLL(str(binary))
            cls.bridge.invoke.argtypes = [C.c_size_t, C.c_void_p, C.c_uint32]
            cls.bridge.invoke.restype = C.c_uint32
            cls.invoke_native = staticmethod(lambda address, house, argument: cls.bridge.invoke(address, house, argument))

    @classmethod
    def tearDownClass(cls):
        del cls.invoke_native
        if cls.bridge_temp is not None:
            del cls.bridge
            cls.bridge_temp.cleanup()

    def invoke(self, address, house, argument):
        before = None if house is None else house.before()
        result = self.invoke_native(address, None if house is None else C.addressof(house.data), argument)
        if house is not None:
            self.assertEqual(house.before(), before, "Supply guard changed household memory.")
        return result


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

    @unittest.skipUnless(os.name == "nt", "Whole native promotion calls and unwind use Windows x64.")
    def test_actual_promotion_body_accepts_current_foods_and_preserves_other_requirements(self):
        groups = reviewed_tier_groups()
        output, _ = supply.build_welt(self.original)
        with self.mapped(output) as (image, _):
            promote = C.WINFUNCTYPE(C.c_int, C.c_void_p)(image.base + supply.PROMOTION["begin"])
            cases = (("supplied", None, ()), ("cloth_missing_stock", "stock", (28, 0)),
                     ("tavern_missing_stock", "stock", (76, 0)),
                     ("missing_nonfood", "missing", (28,)), ("zero_nonfood_rate", "zero_rate", (28,)),
                     # Native eligibility deliberately starts at the second
                     # need; first-slot Fish uses the separate hunger rules.
                     ("zero_present_food_rate", "zero_rate", (24,)))
            for tier in (0, 1):
                for label, method, arguments in cases:
                    with self.subTest(tier=tier, case=label):
                        family = PromotionFamily(groups, tier)
                        if method:
                            getattr(family, method)(*arguments)
                        before = family.before()
                        result = promote(C.addressof(family.data))
                        self.assertEqual(result, 777 if method is None else 0)
                        self.assertEqual(family.calls, 1 if method is None else 0)
                        self.assertEqual(family.errors, [])
                        self.assertEqual(family.before(), before)

    @unittest.skipUnless(os.name == "nt", "Native chained unwind requires Windows x64.")
    def test_promotion_thunk_unwind_restores_the_complete_native_frame(self):
        output, proof = supply.build_welt(self.original)
        hook = proof["promotion_guard"]
        with self.mapped(output) as (image, pe):
            table, size = pe.directory(3)
            rows = list(struct.iter_unpack("<III", pe.read(table, size)))
            index = next(i for i, row in enumerate(rows) if row[0] == hook["target_rva"])
            entry = image.base + table + index * 12
            native_index = rows.index(tuple(hook["unwind_parent"]))
            native_entry = image.base + table + native_index * 12
            kernel = C.WinDLL("kernel32")
            unwind = kernel.RtlVirtualUnwind
            unwind.argtypes = [C.c_uint32, C.c_uint64, C.c_uint64, C.c_void_p, C.c_void_p,
                               C.POINTER(C.c_void_p), C.POINTER(C.c_uint64), C.c_void_p]
            unwind.restype = C.c_void_p
            stack = C.create_string_buffer(512)
            rsp = (C.addressof(stack) + 128 + 15) & ~15
            saved = {"rbx": (0x50, 144), "rsi": (0x58, 168), "r12": (0x60, 216),
                     "r15": (0x20, 240), "r14": (0x28, 232), "r13": (0x30, 224),
                     "rdi": (0x38, 176), "rbp": (0x40, 160)}
            expected = {}
            for i, (name, (offset, _)) in enumerate(saved.items()):
                expected[name] = 0x1234000000000000 + i
                C.c_uint64.from_address(rsp + offset).value = expected[name]
            return_address = 0x123456789ABC0000
            C.c_uint64.from_address(rsp + 0x48).value = return_address
            # Registered native tables must also recognize the entry detour as
            # an in-frame continuation. Test every byte there as well as in the
            # thunk, including the failure path's register restores.
            cases = [("thunk", hook["target_rva"] + i, entry) for i in range(hook["code_size"])]
            cases += [("entry", hook["patch_rva"] + i, native_entry)
                      for i in range(len(bytes.fromhex(hook["patch"])))]
            for location, rva, function_entry in cases:
                with self.subTest(location=location, rva=rva):
                    context = C.create_string_buffer(1232 + 16)
                    aligned = (C.addressof(context) + 15) & ~15
                    C.c_uint32.from_address(aligned + 48).value = 0x100003
                    C.c_uint64.from_address(aligned + 152).value = rsp
                    pc = image.base + rva
                    C.c_uint64.from_address(aligned + 248).value = pc
                    handler, frame = C.c_void_p(), C.c_uint64()
                    unwind(0, image.base, pc, function_entry, aligned, C.byref(handler), C.byref(frame), None)
                    self.assertEqual(C.c_uint64.from_address(aligned + 248).value, return_address)
                    self.assertEqual(C.c_uint64.from_address(aligned + 152).value, rsp + 0x50)
                    for name, (_, context_offset) in saved.items():
                        self.assertEqual(C.c_uint64.from_address(aligned + context_offset).value, expected[name], name)


if __name__ == "__main__":
    unittest.main()
