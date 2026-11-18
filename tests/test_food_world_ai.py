"""Exact private-AI instruction fixtures, not live AI economy acceptance."""
from __future__ import annotations

import ctypes as C
import hashlib
import os
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / ".local/toolchain/world-options-validation")]
from anno1503_overhaul import food_world_ai as f
from anno1503_overhaul.world_options_factions import PROFILE_INPUT_SHA256, derive_faction_ai
from anno1503_overhaul.world_runtime_build import PE, RuntimeBuildError


GOODS = list(range(26, 41)) + [24, 25, 45]


def inputs():
    for name, pin in PROFILE_INPUT_SHA256["food-world"].items():
        path = ROOT / ".local/baselines/world_settings/native" / name.replace(".dll", ".food-ai.dll")
        if not path.is_file():
            raise unittest.SkipTest("Exact local private AI construction inputs are unavailable.")
        raw, _ = derive_faction_ai(name, path.read_bytes(), pin)
        if hashlib.sha256(raw).hexdigest() != f.INPUT_SHA256[name]:
            raise AssertionError("Private AI predecessor differs from its reviewed input.")
        yield name, raw


def profiles(mode):
    raw = bytearray(5 * 0x120)
    for level in range(5):
        count = 18 if mode == "complete" else [8, 13, 16, 15, 12][level]
        if mode == "invalid" and level == 0:
            count = 0
        elif mode == "invalid" and level == 1:
            count = 19
        at = level * 0x120
        raw[at + 2] = count
        # Poison unused rates: a count sentinel must never be treated as a
        # real demand. The complete mapping also exercises the old loop.
        for index in range(47):
            struct.pack_into("<H", raw, at + 0x66 + index * 4, 60000)
        for good in GOODS:
            raw[at + good + 3] = count
        available = GOODS if mode == "complete" else (
            [26, 40, 24] + ([45] if level else []) + ([25] if level >= 2 else [])
            + [good for good in GOODS if good not in (26, 40, 24, 25, 45)])
        for index, good in enumerate(available[:min(count, 18)]):
            raw[at + good + 3] = index
            struct.pack_into("<H", raw, at + 0x66 + index * 4,
                             0 if index == 2 else (index * 7 + level * 3 + 1) % 137)
        if mode == "invalid":
            raw[at + 25 + 3] = 255
            raw[at + 45 + 3] = count
    return bytes(raw)


def reference(raw, highest, good, counts):
    f32 = lambda value: C.c_float(value).value
    total = 0.0
    for level in range(highest + 1):
        at = level * 0x120
        count, index = raw[at + 2], raw[at + good + 3]
        if count > 18 or index >= count:
            continue
        population = max(60, counts[level]) if level == highest else counts[level]
        if not population:
            continue
        if highest == 0:
            population += 50
        rate, = struct.unpack_from("<H", raw, at + 0x66 + index * 4)
        total = f32(total + f32(population * rate))
    demand = f32(total / 4096)
    if highest == 0 and demand < f32(0.7):
        demand = f32(demand + demand)
    return struct.pack("<fff", demand, -demand, f32(f32(good * 257) / 256))


class DerivativeTests(unittest.TestCase):
    def test_exact_pins_and_deterministic_single_mapping_change(self):
        self.assertEqual(set(f.INPUT_SHA256), set(f.OUTPUT_SHA256))
        for digest in [*f.INPUT_SHA256.values(), *f.OUTPUT_SHA256.values()]:
            self.assertRegex(digest, r"^[0-9a-f]{64}$")
        for name, raw in inputs():
            output, proof = f.derive_food06_ai(name, raw)
            self.assertEqual((output, proof), f.derive_food06_ai(name, raw))
            self.assertEqual(hashlib.sha256(output).hexdigest(), f.OUTPUT_SHA256[name])
            old, new = PE(raw), PE(output)
            self.assertEqual(new.sections[-1]["name"], ".f06need")
            self.assertEqual(new.sections[-1]["flags"], 0x60000020)
            self.assertEqual(new.function_table() - old.function_table(),
                             {(proof["guard_rva"], proof["guard_rva"] + proof["code_size"], proof["unwind_rva"])})
            self.assertEqual(new.read(proof["unwind_rva"], 16),
                             bytes.fromhex("21000000") + struct.pack("<III", *proof["unwind_parent"]))
            for directory in range(16):
                if directory != 3:
                    self.assertEqual(old.directory(directory), new.directory(directory))
            self.assertTrue(proof["original_sections_preserved_except_mapping"])
            for section in old.sections:
                expected = bytearray(raw[section["raw"]:section["raw"] + section["raw_size"]])
                if section["rva"] <= proof["patch_rva"] < section["rva"] + section["virtual"]:
                    relative = proof["patch_rva"] - section["rva"]
                    expected[relative:relative + 10] = bytes.fromhex(proof["patch"])
                self.assertEqual(output[section["raw"]:section["raw"] + section["raw_size"]], expected)

    def test_unknown_mutated_cross_profile_repeated_and_mutable_inputs_refuse(self):
        for name, raw in inputs():
            output, _ = f.derive_food06_ai(name, raw)
            for data in (raw[:-1] + bytes([raw[-1] ^ 1]), output, bytearray(raw)):
                with self.assertRaises(RuntimeBuildError):
                    f.derive_food06_ai(name, data)
            with self.assertRaises(RuntimeBuildError):
                f.derive_food06_ai("Other.dll", raw)


class NativeDemandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import pefile
            from unicorn import Uc, UC_ARCH_X86, UC_MODE_64, x86_const as X
        except ImportError as exc:
            raise unittest.SkipTest("Local native instruction tools are unavailable.") from exc
        cls.pefile, cls.Uc, cls.X, cls.arch, cls.mode = pefile, Uc, X, UC_ARCH_X86, UC_MODE_64
        cls.variants = [(name, raw, *f.derive_food06_ai(name, raw)) for name, raw in inputs()]
        cls.mapped = {}

    def image(self, raw, base):
        key = (hashlib.sha256(raw).hexdigest(), base)
        if key not in self.mapped:
            pe = self.pefile.PE(data=raw)
            image = bytearray(pe.get_memory_mapped_image())
            delta = base - pe.OPTIONAL_HEADER.ImageBase
            for block in pe.DIRECTORY_ENTRY_BASERELOC:
                for entry in block.entries:
                    if entry.type == 10:
                        struct.pack_into("<Q", image, entry.rva,
                                         struct.unpack_from("<Q", image, entry.rva)[0] + delta)
            self.mapped[key] = bytes(image)
        return self.mapped[key]

    def run_evaluator(self, name, raw, base, data, highest):
        u, X = self.Uc(self.arch, self.mode), self.X
        image = self.image(raw, base)
        u.mem_map(base, (len(image) + 4095) & ~4095)
        u.mem_write(base, image)
        for at, size in ((0x31000000, 0x10000), (0x32000000, 0x20000), (0x33000000, 0x1000)):
            u.mem_map(at, size)
        state = bytearray([0xA5]) * (56 * 0x5C)
        for good in range(56):
            state[good * 0x5C + 0x34] = 8 if good in GOODS else 0
        statebase, profilebase, citybase = 0x32002000, 0x32004000, 0x32008000
        u.mem_write(statebase, bytes(state))
        u.mem_write(profilebase, data)
        city = bytearray(0x400)
        struct.pack_into("<QQ", city, 0, 0x32009000, 0x3200A000)
        for good in GOODS:
            struct.pack_into("<i", city, 0x200 + good * 4, good * 257)
        u.mem_write(citybase, bytes(city))
        vt = bytearray(0x108)
        struct.pack_into("<Q", vt, 0xC0, 0x33000100)
        struct.pack_into("<Q", vt, 0x100, 0x33000120)
        u.mem_write(0x32009000, bytes(vt))
        counts = [0, 23, 65, 131, 400]
        u.mem_write(0x3200A000, struct.pack("<Q5i", 0x3200B000, *counts))
        u.mem_write(0x3200B000, struct.pack("<Q", 0x33000140))
        u.mem_write(0x33000100, bytes.fromhex("488b4108c3"))
        u.mem_write(0x33000120, bytes.fromhex("8b849100020000c3"))
        u.mem_write(0x33000140, bytes.fromhex("8b449108c3"))
        values = {"RSP": 0x31008008, "RAX": profilebase, "RBP": statebase + 26 * 0x5C - 0x97C,
                  "R13": citybase, "RSI": highest}
        for register, value in values.items():
            u.reg_write(getattr(X, "UC_X86_REG_" + register), value)
        u.emu_start(base + f.SPEC[name]["begin"], base + f.SPEC[name]["end"], count=30000)
        self.assertEqual(u.reg_read(X.UC_X86_REG_RIP), base + f.SPEC[name]["end"])
        self.assertEqual(u.reg_read(X.UC_X86_REG_RSP), values["RSP"])
        self.assertEqual(bytes(u.mem_read(profilebase, len(data))), data)
        self.assertEqual(bytes(u.mem_read(citybase, len(city))), bytes(city))
        return bytes(u.mem_read(statebase, len(state))), state, counts

    def test_complete_native_evaluator_matches_bounded_reference_at_two_bases(self):
        for name, old, output, proof in self.variants:
            for base in (0x180000000, 0x280000000):
                for mode in ("complete", "tiered", "invalid"):
                    data = profiles(mode)
                    for highest in range(5):
                        with self.subTest(name=name, base=base, mode=mode, highest=highest):
                            actual, expected, counts = self.run_evaluator(name, output, base, data, highest)
                            for good in GOODS:
                                result, at = reference(data, highest, good, counts), good * 0x5C
                                expected[at:at + 4] = result[:4]
                                expected[at + 8:at + 16] = result[4:12]
                            self.assertEqual(actual, bytes(expected))
                            if mode == "complete":
                                previous, _, _ = self.run_evaluator(name, old, base, data, highest)
                                self.assertEqual(actual, previous)

    def test_poisoned_absent_slot_reproduces_prior_bug_and_new_guard_ignores_it(self):
        for name, old, output, proof in self.variants:
            data = profiles("tiered")
            fixed, _, _ = self.run_evaluator(name, output, 0x180000000, data, 0)
            prior, _, _ = self.run_evaluator(name, old, 0x180000000, data, 0)
            for good in (25, 45):
                self.assertEqual(struct.unpack_from("<f", fixed, good * 0x5C)[0], 0)
                self.assertGreater(struct.unpack_from("<f", prior, good * 0x5C)[0], 0)

    @unittest.skipUnless(os.name == "nt", "Actual chained unwind uses Windows AMD64.")
    def test_guard_unwind_matches_native_frame_at_every_byte_offset(self):
        kernel = C.WinDLL("kernel32", use_last_error=True)
        kernel.VirtualAlloc.argtypes = [C.c_void_p, C.c_size_t, C.c_uint32, C.c_uint32]
        kernel.VirtualAlloc.restype = C.c_void_p
        kernel.VirtualFree.argtypes = [C.c_void_p, C.c_size_t, C.c_uint32]
        kernel.VirtualFree.restype = C.c_int
        kernel.RtlAddFunctionTable.argtypes = [C.c_void_p, C.c_uint32, C.c_uint64]
        kernel.RtlAddFunctionTable.restype = C.c_ubyte
        kernel.RtlDeleteFunctionTable.argtypes = [C.c_void_p]
        kernel.RtlDeleteFunctionTable.restype = C.c_ubyte
        unwind = kernel.RtlVirtualUnwind
        unwind.argtypes = [C.c_uint32, C.c_uint64, C.c_uint64, C.c_void_p, C.c_void_p,
                           C.POINTER(C.c_void_p), C.POINTER(C.c_uint64), C.c_void_p]
        unwind.restype = C.c_void_p
        for name, old, output, proof in self.variants:
            pe = PE(output)
            image = self.image(output, self.pefile.PE(data=output).OPTIONAL_HEADER.ImageBase)
            memory = kernel.VirtualAlloc(None, len(image), 0x3000, 4)
            if not memory:
                raise OSError(C.get_last_error(), "Allocate local unwind fixture")
            registered = False
            try:
                C.memmove(memory, image, len(image))
                table, size = pe.directory(3)
                self.assertTrue(kernel.RtlAddFunctionTable(memory + table, size // 12, memory))
                registered = True
                entries = list(struct.iter_unpack("<III", pe.read(table, size)))
                native_index = entries.index(tuple(proof["unwind_parent"]))
                guard_index = next(i for i, entry in enumerate(entries) if entry[0] == proof["guard_rva"])
                stack = C.create_string_buffer(0x4000)
                rsp = (C.addressof(stack) + 0x1000 + 15) & ~15
                for offset in range(0, 0x1000, 8):
                    C.c_uint64.from_address(rsp + offset).value = 0x1234000000000000 + offset

                def invoke(pc, index):
                    context = C.create_string_buffer(1232 + 16)
                    aligned = (C.addressof(context) + 15) & ~15
                    C.c_uint32.from_address(aligned + 48).value = 0x10000B
                    C.c_uint64.from_address(aligned + 152).value = rsp
                    C.c_uint64.from_address(aligned + 248).value = memory + pc
                    handler, frame = C.c_void_p(), C.c_uint64()
                    unwind(0, memory, memory + pc, memory + table + index * 12, aligned,
                           C.byref(handler), C.byref(frame), None)
                    return C.string_at(aligned, 1232), frame.value

                # The preceding CMOVNE is an untouched body instruction.
                expected, expected_frame = invoke(proof["patch_rva"] - 3, native_index)
                # RIP/RSP, all nonvolatile GPRs and XMM6..15 must restore from
                # the same native chain, including its intermediate saves.
                offsets = [144, 152, 160, 168, 176, 216, 224, 232, 240, 248]
                for offset in range(proof["code_size"]):
                    actual, frame = invoke(proof["guard_rva"] + offset, guard_index)
                    self.assertEqual(frame, expected_frame, (name, offset))
                    for at in offsets:
                        self.assertEqual(actual[at:at + 8], expected[at:at + 8], (name, offset, at))
                    self.assertEqual(actual[512:672], expected[512:672], (name, offset, "XMM6..15"))
                for offset in range(len(f.PREIMAGE)):
                    actual, frame = invoke(proof["patch_rva"] + offset, native_index)
                    self.assertEqual(frame, expected_frame, (name, "entry", offset))
                    for at in offsets:
                        self.assertEqual(actual[at:at + 8], expected[at:at + 8], (name, "entry", offset, at))
                    self.assertEqual(actual[512:672], expected[512:672], (name, "entry", offset, "XMM6..15"))
            finally:
                if registered:
                    self.assertTrue(kernel.RtlDeleteFunctionTable(memory + table))
                if not kernel.VirtualFree(memory, 0, 0x8000):
                    raise OSError(C.get_last_error(), "Release local unwind fixture")


if __name__ == "__main__":
    unittest.main()
