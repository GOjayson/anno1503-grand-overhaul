"""Exact native composition/ASLR proofs; no game process is launched."""
from pathlib import Path
import hashlib
import json
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from anno1503_overhaul import food_household as h
from anno1503_overhaul.food06_package import _food05_view
from anno1503_overhaul.world_native import _pe, _offset
from anno1503_overhaul.world_runtime_build import PE


class NativeHouseholdComposition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = ROOT / '.local/toolchain/ziglang/zig.exe'
        stock = ROOT / '.local/game-copies/World Settings/View.dll'
        if not compiler.is_file() or not stock.is_file():
            raise unittest.SkipTest('Reviewed compiler and exact locally owned native input are unavailable.')
        spec = json.loads((ROOT / 'legacy/food_overhaul/food_patch.json').read_bytes())
        cls.original = _food05_view(stock.read_bytes(), spec)
        cls.payload, cls.compiler = h.compile_payload(compiler)
        cls.output, cls.proof = h._construct_view(cls.original, cls.payload)
        cls.old, cls.new = PE(cls.original), PE(cls.output)

    def test_only_five_reviewed_virtuals_and_native_headers_change_in_old_image(self):
        old, new = self.old, self.new
        info = _pe(self.original)
        allowed = set()
        def allow(start, size): allowed.update(range(start, start+size))
        for at, size in ((old.pe+6, 2), (old.optional+4, 4), (old.optional+56, 4),
                         (old.optional+64, 4), (old.optional+112+3*8, 8),
                         (old.optional+112+5*8, 8),
                         (info['table']+len(info['sections'])*40, 40)):
            allow(at, size)
        for slot in h.HOOKS:
            allow(_offset(info, h.HOUSE_VTABLE+slot, 8), 8)
        differences = {i for i, (a,b) in enumerate(zip(self.original, self.output)) if a != b}
        self.assertLessEqual(differences, allowed)
        self.assertEqual(len(self.proof['hooks']), 5)
        self.assertEqual(old.directory(0), new.directory(0))
        self.assertEqual(old.directory(1), new.directory(1))
        for section in old.sections:
            if section['flags'] & 0x20000000:
                self.assertEqual(old.read(section['rva'], section['raw_size']),
                                 new.read(section['rva'], section['raw_size']))

    def test_preserved_and_new_unwind_tables_have_exact_nonoverlapping_membership(self):
        self.assertLessEqual(self.old.function_table(), self.new.function_table())
        entries = sorted(self.new.function_table())
        self.assertTrue(all(a[1] <= b[0] for a,b in zip(entries, entries[1:])))
        for hook in self.proof['hooks']:
            self.assertTrue(any(begin <= hook['target_rva'] < end for begin,end,_ in entries))
        self.assertGreater(self.proof['functions_added'], 0)
        self.assertEqual(self.new.directory(13), self.old.directory(13))

    def test_each_changed_virtual_retains_its_original_aslr_relocation(self):
        relocations = h._relocations(self.new)
        for slot in h.HOOKS:
            self.assertIn(h.HOUSE_VTABLE+slot, relocations)
        self.assertEqual(relocations, h._relocations(self.old))
        source = PE(self.payload)
        self.assertEqual(source.directory(1), (0,0))
        self.assertEqual(source.directory(13), (0,0))
        self.assertFalse(any(s['flags'] & 0x80000000 for s in source.sections))

    def test_unknown_or_already_composed_native_input_is_refused(self):
        for raw in (self.output, self.original[:-1]+bytes([self.original[-1]^1]),
                    bytearray(self.original), b'MZ'):
            with self.assertRaises(h.FoodHouseholdError):
                h._construct_view(raw, self.payload)

    def test_compiler_output_and_view_are_reproducible_in_new_staging(self):
        payload, _ = h.compile_payload(ROOT / '.local/toolchain/ziglang/zig.exe')
        output, proof = h._construct_view(self.original, payload)
        self.assertEqual(payload, self.payload)
        self.assertEqual(output, self.output)
        self.assertEqual(proof, self.proof)
        if h.FOOD06_VIEW_SHA256 is not None:
            self.assertEqual(hashlib.sha256(output).hexdigest(), h.FOOD06_VIEW_SHA256)
