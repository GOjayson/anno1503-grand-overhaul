"""Native Food artwork composition; no game process or game assets required."""
from pathlib import Path
import importlib.util
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from anno1503_overhaul import food_artwork as art


def _frame(ident, width, height, palette, foreground=False):
    pixels = []
    for y in range(height):
        for x in range(width):
            if (x, y) in ((0, 0), (width - 1, height - 1)):
                value = -1
            elif min(x, y, width - 1 - x, height - 1 - y) < max(1, 3 * width // 50):
                value = 3
            elif foreground and width // 3 < x < width * 2 // 3 and height // 4 < y < height * 3 // 4:
                value = 2
            else:
                value = 1
            pixels.append(value)
    return art._chunk("TEXTURE", struct.pack("<II", 0, ident)
                      + art._chunk("HEAD", struct.pack("<HHHH", width, height, palette, 8))
                      + art._chunk("BODY", art._encode(width, height, pixels)))


def _palette(ident, grey=False):
    colours = [(0, 0, 0), (80, 120, 90), (180, 100, 35), (190, 185, 155)]
    colours.extend((n, n // 2, n // 3) for n in range(4, 256))
    if grey:
        colours = [(sum(rgb) // 3,) * 3 for rgb in colours]
    raw = bytes(v for red, green, blue in colours for v in (blue, green, red, 0))
    return art._chunk("COLOR", struct.pack("<II", 0, ident) + art._chunk("BODY", raw))


def _container(width=50, height=50, *, final=False, mixed=False):
    counts = (23, 15, 5) if final else (21, 14, 4)
    offset = 100
    entries, frames = [], []
    for group, count in zip(("WARENICONS_ROHSTOFF", "WARENICONS_BEDARF", "WARENICONS_BAUMATERIAL"), counts):
        for grey in (False, True):
            entries.append((group + ("_GREY" if grey else ""), offset))
            for n in range(count):
                icon_width = 40 if mixed and width == 39 and group == "WARENICONS_BEDARF" and n == 7 else width
                palette = 22 if grey else (21 if group == "WARENICONS_BEDARF" else 19)
                frames.append(_frame(offset + n, icon_width, height, palette,
                                     foreground=(group == "WARENICONS_BEDARF" and n == 0)))
            offset += count
    # A non-food native sprite proves that we do not rebuild/recolor all icons.
    frames.append(_frame(999, width, height, 19, True))
    index = art._chunk("ANNO", art._chunk("ACCESS", b"".join(
        f"{name},{ident}".encode("ascii") + b"\0" for name, ident in entries)))
    textures = art._chunk("ANNO", _palette(19) + _palette(21) + _palette(22, True) + b"".join(frames))
    return index, textures


class FoodArtworkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets = art.load_assets(ROOT / "legacy/food_overhaul/assets")

    def transform(self, width=50, height=50, mixed=False):
        stock = _container(width, height, mixed=mixed)
        target = _container(width, height, final=True, mixed=mixed)
        return stock, target, art.transform(*stock, *target, self.assets)

    def test_summary_is_original_food_payload_and_palette_not_a_good(self):
        stock, target, (index, texture, proof) = self.transform()
        old_access = dict(art._access(stock[0]))
        new_access = dict(art._access(index))
        old, new = art._frames(stock[1]), art._frames(texture)
        for name, source in ((art.SUMMARY_ACCESS, "WARENICONS_BEDARF"),
                             (art.SUMMARY_GREY_ACCESS, "WARENICONS_BEDARF_GREY")):
            self.assertEqual(art._identify(new[new_access[name]], old_access[source]), old[old_access[source]])
            self.assertTrue(proof["summary"][name]["original_payload_preserved"])
        self.assertEqual(len(new), len(art._frames(target[1])) + 2)
        self.assertFalse(proof["summary_is_traded_good"])
        self.assertEqual(art._access(index)[:-2], art._access(target[0]))

    def test_all_backgrounds_and_native_frames_share_stock_consumer_pixels(self):
        stock, _, (index, texture, proof) = self.transform()
        access, frames = dict(art._access(index)), art._frames(texture)
        stock_access, stock_frames = dict(art._access(stock[0])), art._frames(stock[1])
        for name, (group, ordinal) in art.FOOD_SLOTS.items():
            foreground = art._foreground(name, self.assets[name])
            for grey in (False, True):
                suffix = "_GREY" if grey else ""
                pixels = art._decode(frames[access[group + suffix] + ordinal])[2]
                template = art._decode(stock_frames[stock_access["WARENICONS_BEDARF" + suffix]])[2]
                for n, visible in enumerate(foreground):
                    x, y = n % 50, n // 50
                    if not visible:
                        expected = template[n] if min(x, y, 49 - x, 49 - y) < 3 else 1
                        self.assertEqual(pixels[n], expected, (name, grey, x, y))
                self.assertTrue(proof["icons"][name + ("-grey" if grey else "")]["background_matches_native_plate"])

    def test_reclassified_foods_use_native_consumer_palette_without_palette_rewrite(self):
        stock, target, (index, texture, _) = self.transform()
        access, frames = dict(art._access(index)), art._frames(texture)
        for name, (group, ordinal) in art.FOOD_SLOTS.items():
            for suffix, expected in (("", 21), ("_GREY", 22)):
                head = art._parts(frames[access[group + suffix] + ordinal])["HEAD"]
                self.assertEqual(struct.unpack_from("<H", head, 4)[0], expected)
        for palette in (19, 21, 22):
            self.assertEqual(art._palette(texture, palette)[0], art._palette(target[1], palette)[0])
            self.assertEqual(art._palette(texture, palette)[0], art._palette(stock[1], palette)[0])

    def test_native_low_resolution_mixed_dimensions_and_transparency(self):
        for width, height, mixed in ((39, 39, True), (40, 39, False)):
            with self.subTest(width=width):
                stock, target, (index, texture, proof) = self.transform(width, height, mixed)
                self.assertEqual(proof["dimensions"], [width, height])
                old, new = art._frames(target[1]), art._frames(texture)
                for name, (group, ordinal) in art.FOOD_SLOTS.items():
                    ident = dict(art._access(index))[group] + ordinal
                    w, h, pixels = art._decode(new[ident])
                    self.assertEqual((w, h), (width, height))
                    self.assertEqual((pixels[0], pixels[-1]), (-1, -1))
                self.assertEqual(new[999], old[999])

    def test_unrelated_sprites_and_nontexture_chunks_are_exact_and_output_deterministic(self):
        stock, target, result = self.transform()
        self.assertEqual(result, art.transform(*stock, *target, self.assets))
        _, texture, _ = result
        old, new = art._frames(target[1]), art._frames(texture)
        access = dict(art._access(target[0]))
        changed = {access[group + suffix] + ordinal for group, ordinal in art.FOOD_SLOTS.values()
                   for suffix in ("", "_GREY")}
        for ident, frame in old.items():
            if ident not in changed:
                self.assertEqual(new[ident], frame)
        original_chunks = [target[1][a:b] for tag, a, b in art._chunks(target[1]) if tag != "TEXTURE"]
        updated_chunks = [texture[a:b] for tag, a, b in art._chunks(texture) if tag != "TEXTURE"]
        self.assertEqual(updated_chunks, original_chunks)

    def test_duplicate_summary_and_changed_palette_are_refused(self):
        stock, target, (index, texture, _) = self.transform()
        with self.assertRaises(art.FoodArtworkError):
            art.transform(*stock, index, texture, self.assets)
        bad = bytearray(target[1])
        for tag, a, b in art._chunks(target[1]):
            if tag == "COLOR" and struct.unpack_from("<I", bad, a + 20)[0] == 21:
                body = next(c for name, c, d in art._chunks(bytes(bad[a:b]), 24) if name == "BODY")
                bad[a + body + 16] ^= 1
                break
        with self.assertRaisesRegex(art.FoodArtworkError, "palettes differ"):
            art.transform(*stock, target[0], bytes(bad), self.assets)

    def test_preserved_authored_assets_are_hash_checked(self):
        with tempfile.TemporaryDirectory(prefix="anno-food-art-") as folder:
            folder = Path(folder)
            for name in art.ASSET_SHA256:
                filename = name.replace("-", "_") + "_icon.json"
                (folder / filename).write_bytes((ROOT / "legacy/food_overhaul/assets" / filename).read_bytes())
            self.assertEqual(art.load_assets(folder), self.assets)
            (folder / "fish_icon.json").write_bytes(b"changed")
            with self.assertRaisesRegex(art.FoodArtworkError, "artwork changed"):
                art.load_assets(folder)

    def test_packaged_flat_support_module_loads_its_own_assets(self):
        with tempfile.TemporaryDirectory(prefix="anno-food-flat-") as folder:
            package = Path(folder) / "food"
            support = package / "support"
            support.mkdir(parents=True)
            assets = package / "assets"
            assets.mkdir()
            source = support / "food_artwork.py"
            source.write_bytes(Path(art.__file__).read_bytes())
            for name in art.ASSET_SHA256:
                filename = name.replace("-", "_") + "_icon.json"
                (assets / filename).write_bytes((ROOT / "legacy/food_overhaul/assets" / filename).read_bytes())
            spec = importlib.util.spec_from_file_location("flat_food_artwork", source)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.assertEqual(module.load_assets(), self.assets)
            stock, target, expected = self.transform()
            self.assertEqual(module.transform(*stock, *target), expected)

    def test_plate_uses_only_clean_stock_patch_and_preserves_frame(self):
        frame = _frame(100, 50, 50, 21, True)
        pixels = art._decode(frame)[2]
        palette = [(0, 0, 0)] * 256
        palette[1:4] = [(80, 120, 90), (180, 100, 35), (190, 185, 155)]
        for n in range(4, 11):
            palette[n] = (50 + n, 90 + n, 60 + n)
        patch_values = set()
        for y in range(4, 15):
            for x in range(34, 46):
                value = 4 + (x + y) % 7
                pixels[y * 50 + x] = value
                patch_values.add(value)
        frame = art._replace_body(frame, pixels)
        width, height, plate, donors, _ = art._plate({100: frame}, 100, palette)
        self.assertEqual((width, height), (50, 50))
        for n, value in enumerate(plate):
            x, y = n % 50, n // 50
            if min(x, y, 49 - x, 49 - y) < 3 or pixels[n] < 0:
                self.assertEqual(value, pixels[n])
            else:
                self.assertIn(value, patch_values)
                _, donor = donors[n]
                self.assertTrue(34 <= donor % 50 < 46 and 4 <= donor // 50 < 15)
                self.assertEqual(value, pixels[donor])

    def test_truncated_native_stream_and_wrong_group_counts_fail_closed(self):
        stock, target, _ = self.transform()
        for bad in (stock[0][:-1], b"", art._chunk("ANNO", b"")):
            with self.subTest(size=len(bad)), self.assertRaises(art.FoodArtworkError):
                art.transform(bad, stock[1], *target, self.assets)
        bad = target[0].replace(b"WARENICONS_ROHSTOFF_GREY,123", b"WARENICONS_ROHSTOFF_GREY,122")
        with self.assertRaisesRegex(art.FoodArtworkError, "group layout"):
            art.transform(*stock, bad, target[1], self.assets)


if __name__ == "__main__":
    unittest.main()
