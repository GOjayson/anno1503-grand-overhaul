"""Malformed metadata and native-coordinate edge cases, no game process."""
from pathlib import Path
import struct
import tempfile
import unittest

import template_placement_audit as audit
from scene_catalogue import SceneError, make_chunk

HERE = Path(__file__).resolve().parent


def terrain(ident=105, x=2, y=3, rotation=0, flags=255, stage=48):
    return struct.pack('<HHBBHBBbb', 0, 0, 32, 32,
                       ident | (rotation << 14), flags, stage, x, y)


def island(tag, payload):
    return make_chunk('ANNO', make_chunk('INSEL5', struct.pack('<HHHHI', 0, 0, 64, 64, 0) + make_chunk(tag, payload)))


DEFS = {105: dict(width=1, height=1, goods=['BAUM']),
        810: dict(width=3, height=4, goods=['NAHRUNG'])}


class PlacementChecks(unittest.TestCase):
    def test_exact_id_rotation_flags_stage_and_signed_offsets(self):
        body = struct.pack('<HHBBHBBbb', 128, 64, 32, 32, 105 | (3 << 14), 255, 199, -128, -64)
        self.assertEqual(list(audit.placements(body)),
                         [dict(definition=105, rotation=3, flags=63, stage=199, x=0, y=0)])

    def test_native_u16_coordinate_wrapping(self):
        body = struct.pack('<HHBBHBBbb', 0xffff, 0, 32, 32, 105, 0, 0, 1, -1)
        rec = list(audit.placements(body))[0]
        self.assertEqual((rec['x'], rec['y']), (0, 0xffff))

    def test_partial_header_or_record_rejected(self):
        for body in (b'', b'\0' * 5, terrain()[:-1], terrain() + b'\0'):
            with self.subTest(length=len(body)), self.assertRaises(SceneError):
                list(audit.placements(body))

    def test_zero_tile_extent_rejected(self):
        for width, height in ((0, 32), (32, 0)):
            with self.assertRaises(SceneError):
                list(audit.placements(struct.pack('<HHBB', 0, 0, width, height)))

    def test_excessive_record_count_rejected(self):
        with self.assertRaises(SceneError):
            list(audit.placements(struct.pack('<HHBB', 0, 0, 32, 32) + b'\0' * (6 * 65537)))

    def test_physical_tree_metadata_counted(self):
        result = audit.inspect(island('GELAENDE', terrain()), DEFS)
        self.assertEqual(result['BAUM'], 1)
        self.assertEqual(result['GELAENDE'], 1)

    def test_unknown_definition_rejected(self):
        with self.assertRaises(SceneError):
            audit.inspect(island('GELAENDE', terrain(999)), DEFS)

    def test_outside_anchor_rejected(self):
        for x, y in ((64, 0), (0, 64), (-1, 0), (0, -1)):
            with self.subTest(x=x, y=y), self.assertRaises(SceneError):
                audit.inspect(island('GELAENDE', terrain(x=x, y=y)), DEFS)

    def test_rotated_dimensions_change_fit_at_boundary(self):
        # 3x4 fits at x61/y60; its rotated4x3 does not fit at x61.
        self.assertEqual(audit.inspect(island('PROD2', terrain(810, 61, 60)), DEFS)['PROD2'], 1)
        with self.assertRaises(SceneError):
            audit.inspect(island('PROD2', terrain(810, 61, 60, 1)), DEFS)
        self.assertEqual(audit.inspect(island('PROD2', terrain(810, 60, 61, 1)), DEFS)['PROD2'], 1)

    def test_zero_production_dimensions_rejected(self):
        with self.assertRaises(SceneError):
            audit.inspect(island('PROD2', terrain()), {105: dict(width=0, height=1, goods=[])})

    def test_no_stored_fish_is_permitted(self):
        # A metadata audit must not invent a stricter rule than stock inputs.
        result = audit.inspect(island('GELAENDE', terrain()), DEFS)
        self.assertEqual(result['FISCH'], 0)

    def test_definition_container_bounds_and_duplicate_id(self):
        def entry(ident):
            head = bytes((3, 4)) + b'\0' * 50
            fields = make_chunk('HEAD', head) + make_chunk('PRODTYPE', b'FISCHER\0') + make_chunk('WARE', b'NAHRUNG\0UNUSED\0')
            return make_chunk('ENTRY', struct.pack('<II', 0, ident) + fields)
        def file_bytes(body):
            return make_chunk('ANNO', make_chunk('ANLAGEN', body))
        with tempfile.TemporaryDirectory(dir=HERE) as folder:
            path = Path(folder) / 'definitions.dat'
            path.write_bytes(file_bytes(entry(810)))
            defs = audit.definitions(path)
            self.assertEqual(defs[810]['goods'], ['NAHRUNG', 'UNUSED'])
            self.assertEqual((defs[810]['width'], defs[810]['height']), (3, 4))
            path.write_bytes(file_bytes(entry(810) + entry(810)))
            with self.assertRaises(SceneError):
                audit.definitions(path)
            path.write_bytes(file_bytes(entry(810))[:-1])
            with self.assertRaises(SceneError):
                audit.definitions(path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
