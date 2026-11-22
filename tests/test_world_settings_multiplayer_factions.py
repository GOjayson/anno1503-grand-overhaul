from hashlib import sha256
import os
from pathlib import Path
from struct import pack, unpack_from
import unittest

from anno1503_overhaul.beta_inputs import derive_beta_assets
from anno1503_overhaul.world_island_catalogue import _chunks, catalogue_rows
from anno1503_overhaul.world_options_factions import MERCHANT_TAG, PIRATE_TAG
from anno1503_overhaul.world_settings_multiplayer import CATALOGUE
from anno1503_overhaul.world_settings_multiplayer_ai import _subfields
from anno1503_overhaul.world_settings_multiplayer_cultures import culture_players, donor_names, linked_culture_island
from anno1503_overhaul.world_settings_multiplayer_island import _CROP_MASKS, _MINERAL_MASKS
from anno1503_overhaul.world_settings_multiplayer_factions import faction_for_template, faction_players, linked_faction_island
from anno1503_overhaul.world_settings_multiplayer_linked import link_generated_islands, stock_trailer
from anno1503_overhaul.world_settings_multiplayer_scene import SCENARIO, _source_chunks

from test_world_settings_multiplayer_scene import chunk, field


def stock_faction_records():
    rows = [(b"BIGBROTHER", b'[PLAYERMAPPER_DEFINE]\n"VENEZIANER" 5\n"PIRAT" 6\r\n[SIGNALS]\n')]
    for seat, kind, culture, alias in ((5, 16, b"VENECIA\0", b"VENEZIANER\0"), (6, 15, b"PIRATEN\0", b"PIRAT\0")):
        prefix = pack("<II", 0, seat)
        head = pack("<I", kind) + bytes(104)
        rows += [(b"SPIELER", prefix + field(b"HEAD", head) + field(b"VOLK", culture) + field(b"ALIAS", alias)),
                 (b"SPIELER", prefix + field(b"COMP", pack("<II", kind, seat) + b"SUSPEND=0\0"))]
    return rows


class FactionTests(unittest.TestCase):
    def test_frequencies_only_tag_active_non_normal_native_controllers(self):
        stock = stock_faction_records()
        expected = {5: MERCHANT_TAG | (2 << 8), 6: PIRATE_TAG | (1 << 10)}
        for mask in range(4):
            with self.subTest(mask=mask):
                self.assertEqual(faction_players(stock, mask),
                                 faction_players(stock, mask, pirate_frequency=1, merchant_frequency=1))
                output = faction_players(stock, mask, pirate_frequency=0, merchant_frequency=2)
                original = faction_players(stock, mask)
                self.assertEqual(len(output), len(original))
                for (tag, before), (_, after) in zip(original, output, strict=True):
                    if tag != b"SPIELER" or before[8:12] != b"COMP":
                        self.assertEqual(before, after)
                        continue
                    seat, = unpack_from("<I", after, 4)
                    controller, = [data for name, data in _subfields(after[8:]) if name == b"COMP"]
                    expected_token = f"SPEZFLAG={expected[seat]}".encode("ascii") + b"\0"
                    self.assertEqual(controller, before[16:] + expected_token)

        with self.assertRaisesRegex(ValueError, "Rare, Normal or Frequent"):
            faction_players(stock, 3, merchant_frequency=3)
        modified = [(tag, data if not (tag == b"SPIELER" and data[8:12] == b"COMP") else
                     data[:8] + field(b"COMP", data[16:] + b"SPEZFLAG=1\0")) for tag, data in stock]
        with self.assertRaisesRegex(ValueError, "already has special flags"):
            faction_players(modified, 3, merchant_frequency=2)

    def test_native_players_and_script_mappings_are_removed_or_bound_together(self):
        stock = stock_faction_records()
        for mask in range(4):
            with self.subTest(mask=mask):
                output = faction_players(stock, mask)
                self.assertEqual(faction_players(stock, mask), output)
                for bit, seat, alias in ((1, 6, b"PIRAT01"), (2, 5, b"VENEZIA01")):
                    parts = [data for tag, data in output
                             if tag == b"SPIELER" and unpack_from("<I", data, 4)[0] == seat]
                    if mask & bit:
                        self.assertEqual(len(parts), 2)
                        self.assertIn(field(b"ALIAS", alias + b"\0"), parts[0])
                        self.assertIn(b'"' + alias + b'" ' + str(seat).encode("ascii"), output[0][1])
                    else:
                        self.assertEqual(parts, [])
                        self.assertNotIn(alias, output[0][1])
                self.assertIn(b"[SIGNALS]\n", output[0][1])
        self.assertIn(b"VENEZIANER", stock[0][1])
        with self.assertRaisesRegex(ValueError, "missing"):
            faction_players(stock[:-1], 1)
        with self.assertRaisesRegex(ValueError, "duplicated"):
            faction_players([stock[0], *stock], 3)

    def test_refuses_culture_towns_outside_native_room(self):
        with self.assertRaisesRegex(ValueError, "differ from the selected"):
            culture_players([], [{"cultures": 32}], 16, None)
        with self.assertRaisesRegex(ValueError, "up to 21 culture towns"):
            culture_players([], [{"cultures": 32}] * 22, 32, None)

    def test_linked_scene_requires_exact_local_special_asset_key(self):
        data = b"native town bytes"
        digest = sha256(data).hexdigest()
        link = chunk(b"INSELLNK", pack("<4HI", 16, 16, 64, 64, 0) + f"WS\\{digest}.scp".encode() + b"\0")
        scene = chunk(b"ANNO", chunk(b"SCENE", chunk(b"WARETYPE", b"native goods") + link))
        with self.assertRaisesRegex(ValueError, "unexpected island link"):
            link_generated_islands(scene, b"")
        with self.assertRaisesRegex(ValueError, "invalid special faction asset"):
            link_generated_islands(scene, b"", populated_assets={digest: data + b"changed"})
        self.assertEqual(link_generated_islands(scene, b"", populated_assets={digest: data}),
                         (scene, {digest: data}))

    @unittest.skipUnless(os.environ.get("ANNO_TEST_STOCK"), "set ANNO_TEST_STOCK to the reviewed installed game")
    def test_all_licensed_home_towns_keep_their_resident_and_production_records(self):
        game = Path(os.environ["ANNO_TEST_STOCK"])
        authored, _ = derive_beta_assets(game)
        source = _source_chunks((game / SCENARIO).read_bytes())
        ware, = [payload for tag, payload in source if tag == b"WARETYPE"]
        working = [entry for entry in catalogue_rows(Path(CATALOGUE).read_bytes()) if faction_for_template(entry)]
        self.assertEqual(len(working), 16)
        for entry in working:
            with self.subTest(island=entry["index"]):
                width, height, climate, _, ore, *_ = entry["fields"]
                template = authored["assets/" + entry["path"]]
                planned = dict(width=width, height=height, climate=climate, rotation=0,
                               cultures=0, cropMask=0xF949, mineralMask=int(ore > 0), x=8, y=8, id=0)
                for vision, native_bits in ((0, 0), (2, 0x381)):
                    link, digest, image = linked_faction_island(entry, planned, template, ware, vision)
                    self.assertEqual(sha256(image).hexdigest(), digest)
                    scene = chunk(b"ANNO", chunk(b"SCENE", chunk(b"WARETYPE", ware) + link))
                    self.assertEqual(link_generated_islands(scene, stock_trailer(game), populated_assets={digest: image}),
                                     (scene, {digest: image}))
                    old_end, new_end = (unpack_from("<I", value, 12)[0] + 16 for value in (template, image))
                    self.assertEqual(image[new_end:], template[old_end:])
                    old_root, new_root = (list(_chunks(data, 16, end)) for data, end in
                                          ((template, old_end), (image, new_end)))
                    self.assertEqual(old_root[2], new_root[2])
                    old_island, new_island = (list(_chunks(chunks[1][1], 12, len(chunks[1][1])))
                                              for chunks in (old_root, new_root))
                    self.assertEqual([record for record in old_island if record[0] == b"PROD2"],
                                     [record for record in new_island if record[0] == b"PROD2"])
                    flags, = [unpack_from("<H", data)[0] for name, data in new_island if name == b"DISCOVER"]
                    self.assertEqual(flags & 0x381, native_bits)


    @unittest.skipUnless(os.environ.get("ANNO_TEST_STOCK"), "set ANNO_TEST_STOCK to the reviewed installed game")
    def test_licensed_cultures_keep_populated_assets_and_get_distinct_native_owners(self):
        game = Path(os.environ["ANNO_TEST_STOCK"])
        source = _source_chunks((game / SCENARIO).read_bytes())
        ware, = [payload for tag, payload in source if tag == b"WARETYPE"]
        entries = [row for row in catalogue_rows(Path(CATALOGUE).read_bytes()) if row["fields"][3]]
        self.assertEqual(len(entries), 158)
        for entry in entries:
            with self.subTest(island=entry["index"]):
                width, height, climate, bit, ore, *_ = entry["fields"]
                mask = _MINERAL_MASKS[climate]
                plan = dict(width=width, height=height, climate=climate, cultures=bit, rotation=0,
                            cropMask=_CROP_MASKS[climate], mineralMask=mask & -mask if ore else 0, x=8, y=8, id=0)
                stock = (game / entry["path"]).read_bytes()
                _, digest, output = linked_culture_island(entry, plan, stock, ware, 0)
                self.assertEqual(sha256(output).hexdigest(), digest)
                old, new = (list(_chunks(payload, 16, 16 + unpack_from("<I", payload, 12)[0]))
                            for payload in (stock, output))
                self.assertEqual(old[2], new[2])
                old_island, new_island = (list(_chunks(chunks[1][1], 12, len(chunks[1][1]))) for chunks in (old, new))
                self.assertEqual([record for record in old_island if record[0] == b"PROD2"],
                                 [record for record in new_island if record[0] == b"PROD2"])

        native_bits = (1, 2, 4, 8, 16, 32, 32, 64, 128)
        populate = lambda bits: donor_names(game, bits)
        output = culture_players(source, [{"cultures": bit} for bit in native_bits], 255, populate)
        entries = [(i, data) for i, (tag, data) in enumerate(output)
                   if tag == b"SPIELER" and data[8:16] == b"HEAD\0\0l\0" and unpack_from("<I", data, 16)[0] == 14]
        owners = {unpack_from("<I", data, 4)[0] for _, data in entries}
        self.assertEqual(len(owners), len(native_bits))
        self.assertTrue({10, 11, 12, 13}.issubset(owners))
        self.assertLess(entries[-1][0], next(i for i, (tag, _) in enumerate(output) if tag == b"INSELLNK"))
        cleared = culture_players(source, [], 0, populate)
        self.assertFalse(any(b"COM_NATIVE_" in value for _, value in cleared))
