"""Coastal metadata proofs; no game run, native generation or navigation claim."""
import hashlib
from pathlib import Path
import struct
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from anno1503_overhaul import world_island_catalogue as c


def chunk(tag, payload):
    return tag.encode('ascii').ljust(12, b'\0')+struct.pack('<I', len(payload))+payload


def island(rows, climate=2, tile_override=None):
    height, width = len(rows), len(rows[0])
    values = bytes(value for row in rows for value in row)
    tile = chunk('HEIGHT', struct.pack('<HHBB', 0, 0, width, height)+values)
    if tile_override is not None:
        tile = tile_override
    body = (struct.pack('<4HI', 0, 0, width, height, 0) +
            chunk('INFO', bytes([climate])+bytes(11)) + tile)
    return chunk('ANNO', chunk('INSEL5', body))


class CoastalShapes(unittest.TestCase):
    def test_shape_is_orientation_invariant_but_distinguishes_same_size_coastlines(self):
        rows = [[0, 48, 0], [0, 48, 48]]
        expected = c.coastal_shape(island(rows))['shape_sha256']
        for mirror in (False, True):
            rotated = [row[::-1] for row in rows] if mirror else rows
            for rotation in range(4):
                with self.subTest(mirror=mirror, rotation=rotation):
                    self.assertEqual(c.coastal_shape(island(rotated))['shape_sha256'], expected)
                rotated = [list(row) for row in zip(*rotated[::-1])]
        self.assertNotEqual(c.coastal_shape(island([[0, 48, 0], [48, 0, 48]]))['shape_sha256'], expected)

    def test_shape_depends_on_coast_not_land_elevation_or_climate(self):
        first = c.coastal_shape(island([[0, 48], [47, 255]], 0))
        other = c.coastal_shape(island([[20, 52], [1, 200]], 5))
        self.assertEqual(first['land_cells'], 2)
        self.assertEqual(first['shape_sha256'], other['shape_sha256'])
        self.assertNotEqual(first['height_sha256'], other['height_sha256'])
        self.assertNotEqual(first['shape_sha256'], c.coastal_shape(island([[0, 47], [47, 255]]))['shape_sha256'])

    def test_grid_tiling_does_not_change_coastal_identity(self):
        rows = [[0, 48, 48], [48, 48, 0]]
        tiles = b''.join(chunk('HEIGHT', struct.pack('<HHBB', x, y, 1, 1)+bytes([rows[y][x]]))
                         for x in range(3) for y in range(2))
        self.assertEqual(c.coastal_shape(island(rows)), c.coastal_shape(island(rows, tile_override=tiles)))

    def test_missing_overlapping_crossing_partial_and_empty_tiles_refused(self):
        valid = chunk('HEIGHT', struct.pack('<HHBB', 0, 0, 2, 2)+bytes(4))
        bad = [b'', valid+valid, chunk('HEIGHT', struct.pack('<HHBB', 1, 1, 2, 2)+bytes(4)),
               chunk('HEIGHT', struct.pack('<HHBB', 0, 0, 2, 2)+bytes(3)),
               chunk('HEIGHT', struct.pack('<HHBB', 0, 0, 0, 2))]
        for tiles in bad:
            with self.subTest(tiles=tiles), self.assertRaises(c.IslandCatalogueError):
                c.coastal_shape(island([[0, 0], [0, 0]], tile_override=tiles))

    def test_truncated_duplicate_island_and_unknown_climate_refused(self):
        valid = island([[0, 48], [48, 0]])
        for raw in (valid[:15], valid[:-1], chunk('ANNO', valid[16:]+valid[16:]),
                    island([[0, 48]], climate=6), chunk('BAD', valid[16:])):
            with self.subTest(raw=raw), self.assertRaises(c.IslandCatalogueError):
                c.coastal_shape(raw)

    def test_catalogue_pin_and_incomplete_metadata_refused(self):
        path = ROOT/'legacy/world_settings/developer/source/engine_resume/ai_food/experiment_runtime/world_catalogue.h'
        data = path.read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), c.CATALOGUE_SHA256)
        self.assertEqual(len(c.catalogue_rows(data)), 444)
        with self.assertRaises(c.IslandCatalogueError):
            c.catalogue_rows(data+b' ')
        for ids in ([0]*444, list(range(444)), [], [True]*444):
            with self.subTest(ids=len(ids)), self.assertRaises(c.IslandCatalogueError):
                c.shape_header(ids)


class ActualCatalogue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        host = ROOT/'.local/game-copies/World Settings'
        assets = ROOT/'.local/baselines/world_settings/assets'
        if not host.is_dir() or not assets.is_dir():
            raise unittest.SkipTest('Explicit local HE island inputs are unavailable.')
        cls.read = staticmethod(c.template_resolver(host, assets))
        cls.catalogue = (ROOT/'legacy/world_settings/developer/source/engine_resume/ai_food/experiment_runtime/world_catalogue.h').read_bytes()
        cls.header = (ROOT/'src/anno1503_overhaul/native/world_options/island_shapes.h').read_bytes()

    def test_all444_exact_inputs_geometry_and_coast_match_production_groups(self):
        proof = c.validate_island_shapes(self.catalogue, self.header, self.read)
        self.assertEqual((proof['template_count'], proof['unique_content_count'], proof['shape_count']), (444, 444, 347))
        self.assertFalse(proof['game_executed'])
        groups = {}
        for index, row in enumerate(proof['templates']):
            with self.subTest(index=index):
                ident = proof['shape_ids'][index]
                previous = groups.setdefault(ident, row['shape_sha256'])
                self.assertEqual(previous, row['shape_sha256'])
                self.assertEqual((row['width'], row['height'], row['climate']), tuple(row['fields'][:3]))
        self.assertEqual(len(set(groups.values())), 347)

    def test_header_group_tamper_refused(self):
        with self.assertRaises(c.IslandCatalogueError):
            c.validate_island_shapes(self.catalogue, self.header.replace(b' = {', b' = {0,', 1), self.read)

    def test_native_input_change_or_cross_template_substitution_refused(self):
        first = c.catalogue_rows(self.catalogue)[0]['path']
        second = c.catalogue_rows(self.catalogue)[1]['path']
        original = self.read(first)
        for changed in (original[:-1]+bytes([original[-1]^1]), self.read(second)):
            with self.subTest(changed=hashlib.sha256(changed).hexdigest()), self.assertRaises(c.IslandCatalogueError):
                c.derive_shape_ids(self.catalogue, lambda path: changed if path == first else self.read(path))


if __name__ == '__main__':
    unittest.main()
