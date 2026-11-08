"""Portable checks for the stock-bound native derivative; no compiler/game run."""
from pathlib import Path
import hashlib
import json
import struct
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from anno1503_overhaul import world_runtime_build as build
from anno1503_overhaul.world_native import WORLD_ONLY_AI_SHA256


SOURCE = build.ROOT / 'legacy/world_settings'


def raw_pe(*, debug=False):
    """A small mapped test image; supplied hashes are explicitly fixture-only."""
    code_rva, code_size = 0x1000, 0x133000
    pdata_rva, pdata_size = 0x134000, 45864
    code_raw, pdata_raw = 0x400, 0x133400
    build_raw = pdata_raw + 0xb400
    data = bytearray(build_raw + 0x200)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 60, 0x80)
    data[0x80:0x84] = b'PE\0\0'
    struct.pack_into('<HH', data, 0x84, 0x8664, 3 if debug else 2)
    struct.pack_into('<I', data, 0x88, 0x12345678)
    struct.pack_into('<H', data, 0x94, 240)
    optional = 0x98
    struct.pack_into('<H', data, optional, 0x20b)
    struct.pack_into('<II', data, optional + 56, 0x147000, 0x400)
    struct.pack_into('<I', data, optional + 108, 16)
    struct.pack_into('<II', data, optional + 112 + 3 * 8, pdata_rva, pdata_size)
    section = optional + 240
    for index, (name, virtual, rva, size, raw, flags) in enumerate((
        (b'.text', code_size, code_rva, code_size, code_raw, 0x60000020),
        (b'.pdata', pdata_size, pdata_rva, 0xb400, pdata_raw, 0x40000040),
        (b'.buildid', 86, 0x140000, 0x200, build_raw, 0x40000040),
    )[:3 if debug else 2]):
        at = section + index * 40
        data[at:at + len(name)] = name
        struct.pack_into('<IIII', data, at + 8, virtual, rva, size, raw)
        struct.pack_into('<I', data, at + 36, flags)
    if debug:
        struct.pack_into('<II', data, optional + 112 + 6 * 8, 0x140000, 56)
        payload = b'RSDS' + bytes(range(16)) + struct.pack('<I', 1) + b'a.pdb\0'
        struct.pack_into('<IIHHIIII', data, build_raw, 0, 0xaabbccdd, 0, 0, 2,
                         len(payload), 0x140000 + 56, build_raw + 56)
        struct.pack_into('<IIHHIIII', data, build_raw + 28, 0, 0x87654321, 0, 0, 16, 0, 0, 0)
        data[build_raw + 56:build_raw + 56 + len(payload)] = payload
    return data


def stock_fixture():
    """Populate publicly declared instruction snippets in synthetic PE images."""
    sources = {name: (SOURCE / name).read_bytes() for name in (build.BLOBS, build.AI_LOADER, build.WORLD_SETTINGS)}
    derivatives = build.transform_sources(sources[build.BLOBS], sources[build.AI_LOADER],
                                         sources[build.WORLD_SETTINGS], WORLD_ONLY_AI_SHA256)
    header = derivatives[build.BLOBS]
    frozen = (SOURCE / build.ENGINE_PLAN).read_bytes()
    plan = json.loads(frozen)
    images = {name: raw_pe() for name in ('AnnoFrame.dll', 'AnnoWelt.dll', 'AnnoScene.dll')}
    for edit in plan['edits']:
        if edit['rva'] in (0x14be8c, 0x14be94):
            continue
        name = edit.get('module', plan['module'])
        pe = build.PE(images[name])
        before = bytes.fromhex(edit['before'])
        at = pe.offset(edit['rva'], len(before))
        images[name][at:at + len(before)] = before
    for blob in build.blob_metadata(header):
        pe = build.PE(images[blob['module']])
        for hook in blob['hooks']:
            at = pe.offset(hook['rva'], len(hook['before']))
            images[blob['module']][at:at + len(hook['before'])] = hook['before']
        for function in blob['functions']:
            unwind = function['unwind']
            if unwind[0] >> 3 == 4:
                ordinary = (4 + 2 * unwind[2] + 3) & ~3
                parent = struct.unpack_from('<III', unwind, ordinary)
                table_rva, _ = pe.directory(3)
                index = 0 if parent[0] == 0xd800 else 1
                at = pe.offset(table_rva + index * 12, 12)
                images[blob['module']][at:at + 12] = struct.pack('<III', *parent)
                at = pe.offset(parent[2], 4)
                images[blob['module']][at:at + 4] = b'\x01\0\0\0'
    pe = build.PE(images['AnnoWelt.dll'])
    for rva, value in ((0x1389d4, (0x68024, 0x6804d, 0x115800)),
                       (0x1389e0, (0x6804d, 0x68053, 0x115814))):
        at = pe.offset(rva, 12)
        images['AnnoWelt.dll'][at:at + 12] = struct.pack('<III', *value)
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in images.items()}
    for name in images:
        header = header.replace(build._c_digest(build.STOCK_SHA256[name]), build._c_digest(hashes[name]))
    return sources, images, hashes, header, frozen


class WorldRuntimeBuildTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name).resolve()
        self.sources, self.images, self.hashes, self.header, self.frozen = stock_fixture()
        for name, data in self.images.items():
            (self.directory / name).write_bytes(data)

    def derived_plan(self):
        with mock.patch.dict(build.STOCK_SHA256, {'AnnoWelt.dll': self.hashes['AnnoWelt.dll']}):
            return build.derive_engine_plan(bytes(self.images['AnnoWelt.dll']), self.frozen)

    def test_transform_keeps_hook_code_and_metadata_except_source_pins(self):
        result = build.transform_sources(self.sources[build.BLOBS], self.sources[build.AI_LOADER],
                                         self.sources[build.WORLD_SETTINGS], WORLD_ONLY_AI_SHA256)
        before = build.blob_metadata(self.sources[build.BLOBS])
        after = build.blob_metadata(result[build.BLOBS])
        for original, derived in zip(before, after):
            self.assertEqual({k: v for k, v in original.items() if k != 'sha256'},
                             {k: v for k, v in derived.items() if k != 'sha256'})
            self.assertEqual(derived['sha256'], build.STOCK_SHA256[derived['module']])
        loader = result[build.AI_LOADER]
        for name in WORLD_ONLY_AI_SHA256:
            self.assertIn(build.STOCK_SHA256[name].encode(), loader)
            self.assertIn(WORLD_ONLY_AI_SHA256[name].encode(), loader)
            self.assertNotIn(build.FOOD_SHA256[name].encode(), loader)
            self.assertNotIn(build.FOOD_AI_CANDIDATES[name].encode(), loader)

    def test_same_root_guard_requires_regular_managed_marker_and_exact_host_spelling(self):
        result = build.transform_sources(self.sources[build.BLOBS], self.sources[build.AI_LOADER],
                                         self.sources[build.WORLD_SETTINGS], WORLD_ONLY_AI_SHA256)
        world = result[build.WORLD_SETTINGS]
        self.assertIn(b'.anno1503-grand-overhaul-copy.json', world)
        self.assertIn(b'FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT', world)
        self.assertIn(b'if(_wcsicmp(full,exe))', world)
        self.assertIn(b'GetFileInformationByHandle(copyDirectory,&copyInfo)', world)
        self.assertNotIn(b'||!_stricmp(copyRoot,sourceRoot)', result[build.AI_LOADER])

    def test_unknown_source_shape_and_invalid_ai_pin_map_are_refused(self):
        with self.assertRaises(build.RuntimeBuildError):
            build.transform_sources(self.sources[build.BLOBS] + self.sources[build.BLOBS],
                                    self.sources[build.AI_LOADER], self.sources[build.WORLD_SETTINGS], WORLD_ONLY_AI_SHA256)
        with self.assertRaises(build.RuntimeBuildError):
            build.transform_sources(*self.sources.values(), {})

    def test_frozen_food_plan_has_unmapped_stock_edits_and_derived_plan_proves_all_sites(self):
        with self.assertRaisesRegex(build.RuntimeBuildError, 'mapped span leaves'):
            build.verify_native_preimages(self.directory, self.header, self.frozen, expected_hashes=self.hashes)
        proof = build.verify_native_preimages(self.directory, self.header, self.derived_plan(), expected_hashes=self.hashes)
        self.assertEqual(proof['hook_sites_verified'], 9)
        self.assertEqual(proof['engine_sites_verified'], 173)
        self.assertEqual(len(proof['unwind_parents_verified']), 2)
        self.assertFalse(proof['game_executed'])

    def test_engine_derivative_changes_only_two_edit_addresses_and_matches_compiled_header(self):
        original, derived = json.loads(self.frozen), json.loads(self.derived_plan())
        changes = [(left, right) for left, right in zip(original['edits'], derived['edits']) if left != right]
        self.assertEqual(len(changes), 2)
        self.assertEqual({right['rva'] for _, right in changes}, {0x1389d8, 0x1389e0})
        for left, right in changes:
            self.assertEqual({k: v for k, v in left.items() if k != 'rva'},
                             {k: v for k, v in right.items() if k != 'rva'})
        header = build.derive_engine_header((SOURCE / build.ENGINE_HEADER).read_bytes())
        self.assertIn(b'0x1389d8u', header)
        self.assertIn(b'0x1389e0u', header)
        self.assertNotIn(b'0x14be8cu', header)

    def test_bad_stock_hash_and_missing_unique_unwind_parent_are_refused(self):
        with self.assertRaisesRegex(build.RuntimeBuildError, 'stock module'):
            build.verify_native_preimages(self.directory, self.header, self.derived_plan(), expected_hashes={
                **self.hashes, 'AnnoFrame.dll': '0' * 64})
        data = self.images['AnnoWelt.dll']
        pe = build.PE(data)
        at = pe.offset(0x1389d4, 12)
        data[at:at + 12] = bytes(12)
        with mock.patch.dict(build.STOCK_SHA256, {'AnnoWelt.dll': hashlib.sha256(data).hexdigest()}):
            with self.assertRaisesRegex(build.RuntimeBuildError, 'absent or ambiguous'):
                build.derive_engine_plan(bytes(data), self.frozen)

    def test_mutated_hook_preimage_is_refused_even_with_explicit_fixture_hash(self):
        plan = self.derived_plan()
        data = self.images['AnnoFrame.dll']
        at = build.PE(data).offset(0x43e44, 1)
        data[at] ^= 1
        (self.directory / 'AnnoFrame.dll').write_bytes(data)
        self.hashes['AnnoFrame.dll'] = hashlib.sha256(data).hexdigest()
        old = build.blob_metadata(self.header)[0]['sha256']
        header = self.header.replace(build._c_digest(old), build._c_digest(self.hashes['AnnoFrame.dll']))
        with self.assertRaisesRegex(build.RuntimeBuildError, 'hook preimage differs'):
            build.verify_native_preimages(self.directory, header, plan, expected_hashes=self.hashes)

    def test_duplicate_engine_spans_and_missing_chained_parent_are_refused(self):
        plan = json.loads(self.derived_plan())
        plan['edits'][1] = dict(plan['edits'][0])
        with self.assertRaisesRegex(build.RuntimeBuildError, 'overlap'):
            build.verify_native_preimages(self.directory, self.header, json.dumps(plan).encode(), expected_hashes=self.hashes)
        data = self.images['AnnoScene.dll']
        table, _ = build.PE(data).directory(3)
        at = build.PE(data).offset(table, 12)
        data[at:at + 12] = bytes(12)
        (self.directory / 'AnnoScene.dll').write_bytes(data)
        old = self.hashes['AnnoScene.dll']
        self.hashes['AnnoScene.dll'] = hashlib.sha256(data).hexdigest()
        header = self.header.replace(build._c_digest(old), build._c_digest(self.hashes['AnnoScene.dll']))
        with self.assertRaisesRegex(build.RuntimeBuildError, 'chained unwind parent'):
            build.verify_native_preimages(self.directory, header, self.derived_plan(), expected_hashes=self.hashes)

    def test_canonicalization_only_changes_declared_debug_metadata_and_is_idempotent(self):
        raw = bytes(raw_pe(debug=True))
        canonical, edits = build.normalize_pe_metadata(raw)
        allowed = {index for edit in edits for index in range(edit['offset'], edit['offset'] + len(bytes.fromhex(edit['before'])))}
        self.assertTrue({index for index, (a, b) in enumerate(zip(raw, canonical)) if a != b} <= allowed)
        pe = build.PE(raw)
        for section in pe.sections:
            if section['name'] != '.buildid':
                start, size = section['raw'], section['raw_size']
                self.assertEqual(raw[start:start + size], canonical[start:start + size])
        self.assertEqual(build.normalize_pe_metadata(canonical)[0], canonical)

    def test_different_compiler_debug_ids_canonicalize_to_the_same_bytes(self):
        first = raw_pe(debug=True)
        second = bytearray(first)
        pe = build.PE(second)
        debug_rva, _ = pe.directory(6)
        debug_at = pe.offset(debug_rva, 56)
        payload = pe.unpack('<IIHHIIII', debug_at)[7]
        second[pe.pe + 8:pe.pe + 12] = b'\x99' * 4
        second[debug_at + 4:debug_at + 8] = b'\x88' * 4
        second[debug_at + 32:debug_at + 36] = b'\x77' * 4
        second[payload + 4:payload + 20] = b'\x66' * 16
        self.assertEqual(build.normalize_pe_metadata(bytes(first))[0],
                         build.normalize_pe_metadata(bytes(second))[0])

    def test_x86_or_signed_candidate_cannot_be_canonicalized(self):
        raw = raw_pe(debug=True)
        struct.pack_into('<H', raw, 0x84, 0x14c)
        with self.assertRaisesRegex(build.RuntimeBuildError, 'AMD64'):
            build.normalize_pe_metadata(bytes(raw))
        raw = raw_pe(debug=True)
        struct.pack_into('<II', raw, 0x98 + 112 + 4 * 8, 0x400, 10)
        with self.assertRaisesRegex(build.RuntimeBuildError, 'signed'):
            build.normalize_pe_metadata(bytes(raw))


if __name__ == '__main__':
    unittest.main()
