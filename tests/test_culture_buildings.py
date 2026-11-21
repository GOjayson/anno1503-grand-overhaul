"""Culture registry, menu data and synthetic sprite tests without a game install."""

from collections import Counter
from dataclasses import replace
from importlib.util import find_spec
from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from anno1503_overhaul.culture_buildings import culture_menu, full_cultures, structure_art


LANGUAGES = {"de", "en", "nl"}
CATALOGUE = (
    ("VENETIAN", 25),
    ("AFRICAN", 12),
    ("MOORISH", 17),
    ("BEDOUIN", 9),
    ("MONGOLIAN", 15),
    ("AZTEC", 16),
    ("INUIT", 16),
    ("NATIVEAM", 13),
    ("POLYNESIAN", 13),
    ("PIRATE", 21),
)


class CultureRegistryTests(unittest.TestCase):
    def test_catalogue_covers_every_style_and_persistent_house_tier(self):
        categories = full_cultures.categories()
        self.assertEqual(tuple((category.key, len(category.buildings)) for category in categories), CATALOGUE)
        targets = full_cultures.save_targets()
        seen = set()
        art_sources = Counter()
        for category, style in zip(categories, full_cultures.STYLES, strict=True):
            with self.subTest(culture=category.key):
                self.assertEqual(set(category.labels), LANGUAGES)
                self.assertEqual(category.key, style.key)
                pioneer, aristocrat, *_ = category.buildings
                self.assertEqual((pioneer.icon, aristocrat.icon), ("residence", "aristocrat"))
                self.assertEqual(pioneer.alternate_ids, tuple(range(pioneer.ident + 20, pioneer.ident + 80, 20)))
                self.assertEqual(aristocrat.ident, pioneer.ident + 80)
                tiers = (pioneer.ident, *pioneer.alternate_ids, aristocrat.ident)
                self.assertEqual([targets[ident][1] for ident in tiers],
                                 ["Pioneer", "Settler", "Citizen", "Merchant", "Aristocrat"])
                self.assertTrue(all(targets[ident][2] for ident in tiers))
                expected = {style.first: style.housing[0], style.houses[-1]: style.housing[-1]}
                if style.ornament:
                    source, ident, _ = style.ornament
                    expected[ident] = source
                expected.update({full_cultures.OBJECT_IDS[source]: source for source in style.source_ids
                                 if source in full_cultures.ASSETS})
                self.assertEqual({entry.ident: entry.art_source for entry in category.buildings}, expected)
                for building in category.buildings:
                    self.assertEqual(set(building.labels), LANGUAGES)
                    self.assertTrue(all(label.encode("cp1252") for label in building.labels.values()))
                    self.assertIsInstance(building.art_source, int)
                    self.assertTrue(3000 <= building.art_source < 4000)
                    art_sources[building.art_source] += 1
                    for ident in (building.ident, *building.alternate_ids):
                        self.assertNotIn(ident, seen)
                        seen.add(ident)
        self.assertEqual(set(targets), seen)
        self.assertEqual(len(seen), 187)
        self.assertEqual(len(art_sources), 155)
        self.assertEqual({ident: count for ident, count in art_sources.items() if count > 1},
                         {3203: 2, 3505: 2})

    def test_selector_routes_to_all_ten_cultures_and_keeps_hidden_tiers_unlisted(self):
        categories = full_cultures.categories()
        selector = culture_menu._selector(categories)
        self.assertEqual(selector.main_link.ident, culture_menu.SELECTOR_ID)
        self.assertEqual(selector.routes[culture_menu.SELECTOR_ID], 1)
        self.assertEqual(selector.routes[culture_menu.ORNAMENTS_ID], 0)
        index, *culture_grids = selector.grids
        self.assertEqual(index.cells[-1].ident, culture_menu.ORNAMENTS_ID)
        self.assertEqual(len(index.cells), 11)
        for page, (category, link, grid) in enumerate(zip(categories, index.cells[:-1], culture_grids, strict=True), 2):
            with self.subTest(culture=category.key):
                self.assertEqual(selector.routes[link.ident], page)
                self.assertEqual(link.labels, category.labels)
                self.assertEqual(link.marker, category.key[:3])
                self.assertEqual(grid.key, f"{category.key}1")
                self.assertEqual(grid.cells[-1].ident, culture_menu.SELECTOR_ID)
                shown = tuple(cell.ident for cell in grid.cells[:-1])
                self.assertEqual(shown, tuple(building.ident for building in category.buildings))
                self.assertTrue(set(shown).isdisjoint(selector.routes))
                for building in category.buildings:
                    for ident in building.alternate_ids:
                        self.assertNotIn(ident, shown)
                        self.assertEqual(selector.names[ident], building.labels)

    def test_pagination_stays_inside_each_culture(self):
        first, second, *_ = full_cultures.categories()
        prototype = first.buildings[0]
        items = tuple(replace(prototype, ident=2900 + i, alternate_ids=()) for i in range(61))
        selector = culture_menu._selector((replace(first, buildings=items), second))
        index, first_page, middle_page, last_page, second_culture = selector.grids
        self.assertEqual([len(grid.cells) for grid in (first_page, middle_page, last_page)], [31, 32, 5])
        self.assertEqual(selector.routes[index.cells[0].ident], 2)
        self.assertEqual(selector.routes[index.cells[1].ident], 5)
        self.assertEqual(selector.routes[culture_menu.PREVIOUS_ID], culture_menu.PREVIOUS)
        self.assertEqual(selector.routes[culture_menu.NEXT_ID], culture_menu.NEXT)
        back = culture_menu.SELECTOR_ID
        previous = culture_menu.PREVIOUS_ID
        following = culture_menu.NEXT_ID
        self.assertEqual([cell.ident for cell in first_page.cells[-2:]], [following, back])
        self.assertEqual([cell.ident for cell in middle_page.cells[-3:]], [previous, following, back])
        self.assertEqual([cell.ident for cell in last_page.cells[-2:]], [previous, back])
        self.assertEqual(second_culture.cells[-1].ident, back)
        listed = (cell.ident for page in (first_page, middle_page, last_page) for cell in page.cells
                  if cell.ident not in selector.routes)
        self.assertEqual(tuple(listed), tuple(building.ident for building in items))

    def test_selector_rejects_id_collisions_and_ambiguous_labels(self):
        first, second, *_ = full_cultures.categories()
        building = first.buildings[0]
        for invalid in (
            replace(first, buildings=(building, building)),
            replace(first, buildings=(replace(building, ident=culture_menu.SELECTOR_ID),)),
            replace(first, buildings=(replace(building, alternate_ids=(building.ident,)),)),
            replace(first, buildings=(replace(building, labels={"en": "Only English"}),)),
            replace(first, buildings=(replace(building, icon="unregistered"),)),
            replace(first, key=second.key + "OTHER"),
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    culture_menu._selector((invalid, second))


def archive_chunk(tag, payload):
    return struct.pack("<12sI", tag, len(payload)) + payload


def palette_entry(ident, rgb):
    blue, green, red = reversed(rgb)
    palette = bytearray(1024)
    palette[4:8] = bytes((blue, green, red, 0))
    header = struct.pack("<II", 0, ident) + b"BODY\0\0\0\x04"
    return archive_chunk(b"ENTRY", header + palette)


def synthetic_archive():
    # Two frames per zoom use different palette slots, texture offsets and encodings.
    opaque = bytes((1, 1, 90, 1, 255))
    translucent = bytes((0, 0x41, 200, 1, 255))
    pixels = opaque + translucent
    model_tables = []
    texture_data = []
    for zoom in range(3):
        header = struct.pack("<II", zoom, 2)
        first = struct.pack("<IHH12s4xII4x", 0, 0, 0, b"BSH_RGBZ", 0, len(opaque))
        second = struct.pack("<IHH12s4xII4x", 0, 1, 0, b"BSH_RGBAZ", len(opaque), len(translucent))
        model_tables.append(archive_chunk(b"TEXTURES", header + first + second))
        texture_data.append(archive_chunk(b"TEXTURES", header + pixels))
    model = archive_chunk(b"ENTRY", bytes(16) + b"".join(model_tables))
    definition = archive_chunk(b"ENTRY", struct.pack("<II", 0, 1234)
                               + archive_chunk(b"COLORS", struct.pack("<II", 7, 19))
                               + archive_chunk(b"HAEUSER", model))
    palettes = archive_chunk(b"COLORS", palette_entry(7, (240, 80, 20)) + palette_entry(19, (10, 100, 210)))
    return archive_chunk(b"ANNO", palettes + archive_chunk(b"ANLAGEN", definition) + b"".join(texture_data))


class StructureDecoderTests(unittest.TestCase):
    def setUp(self):
        self.palette = tuple(bytes((n, 255 - n, n // 2)) for n in range(256))

    def test_rgba_runs_take_the_second_sample_byte_as_palette_and_use_run_opacity(self):
        stream = bytes((1, 0x41, 230, 1, 0, 0xC1, 1, 2, 254, 0, 0x81, 250, 3, 255))
        dimensions, pixels = structure_art._decode_frame(stream, self.palette, True)
        self.assertEqual(dimensions, (3, 2))
        clear = bytes(4)
        self.assertEqual(pixels, clear + self.palette[1] + b"\x80" + self.palette[2] + b"\xff"
                         + self.palette[3] + b"\xbf" + clear + clear)

    def test_rgb_run_does_not_mask_a_wide_count(self):
        stream = bytes((0, 65)) + bytes((220, 8)) * 65 + b"\xff"
        dimensions, pixels = structure_art._decode_frame(stream, self.palette, False)
        self.assertEqual(dimensions, (65, 1))
        self.assertEqual(pixels, (self.palette[8] + b"\xff") * 65)

    def test_malformed_sprite_runs_are_refused(self):
        valid = bytes((0, 1, 30, 1, 255))
        for body in (
            b"\xff", valid[:-1], valid + b"\0", b"\0", b"\0\x02\0\1\xff",
            bytes((253, 0)) * 9 + valid,
        ):
            with self.subTest(body=body):
                with self.assertRaises(ValueError):
                    structure_art._decode_frame(body, self.palette, False)

    def test_synthetic_archive_indexes_all_zoom_blocks_and_palettes(self):
        with TemporaryDirectory() as directory:
            archive = Path(directory) / "Anlagen.addon"
            archive.write_bytes(synthetic_archive())
            with structure_art.StructureArt(archive) as art:
                self.assertEqual(set(art._textures), {0, 1, 2})
                self.assertEqual(art._palettes[7][1], bytes((240, 80, 20)))
                self.assertEqual(art._palettes[19][1], bytes((10, 100, 210)))


@unittest.skipUnless(find_spec("PIL"), "Pillow is optional for thumbnail composition")
class ThumbnailCompositionTests(unittest.TestCase):
    def test_native_sprite_and_triplets_keep_original_border_and_metadata(self):
        from anno1503_overhaul.culture_buildings import building_icons, menu

        formats = menu.formats
        palette = building_icons.indexed_palette([(n, n, n) for n in range(256)])
        with TemporaryDirectory() as directory:
            archive = Path(directory) / "Anlagen.addon"
            archive.write_bytes(synthetic_archive())
            with structure_art.StructureArt(archive) as art:
                first = art.sprite(1234, zoom=1)
                second = art.sprite(1234, rotation=1, zoom=2)
                self.assertEqual(first.size, (1, 1))
                self.assertEqual(first.getpixel((0, 0)), (240, 80, 20, 255))
                self.assertEqual(second.getpixel((0, 0)), (10, 100, 210, 128))

                painter = building_icons.BuildingIcons(art, {1800: (1234, False), 1880: (1234, True)})
                for width, highlight_border in ((39, 3), (50, 4)):
                    with self.subTest(width=width):
                        triplet = []
                        for state, border in enumerate((2, highlight_border, 2)):
                            old = bytes(13 if min(x, y, width - 1 - x, width - 1 - y) < border else 55
                                        for y in range(width) for x in range(width))
                            head = formats._chunk("HEAD", struct.pack("<HHHH", width, width, 9, 8))
                            prefix = struct.pack("<II", 0, 90 + state)
                            body = formats._chunk("BODY", formats._encode(width, width, old))
                            frame = formats._chunk("TEXTURE", prefix + head + body)
                            updated = painter.paint(frame, 1800, state, lambda ident: palette)
                            self.assertEqual(updated[16:24 + len(head)], prefix + head)
                            actual_width, actual_height, pixels = formats._decode(updated)
                            self.assertEqual((actual_width, actual_height), (width, width))
                            self.assertNotIn(-1, pixels)
                            for i, value in enumerate(old):
                                if value == 13:
                                    self.assertEqual(pixels[i], value)
                            triplet.append(bytes(pixels))
                            if state == 0:
                                noble = painter.paint(frame, 1880, state, lambda ident: palette)
                                self.assertNotEqual(formats._decode(noble)[2], pixels)
                        self.assertEqual(len(set(triplet)), 3)


if __name__ == "__main__":
    unittest.main()
