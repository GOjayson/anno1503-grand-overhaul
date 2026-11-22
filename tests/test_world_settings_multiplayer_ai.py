from hashlib import sha256
from struct import pack, pack_into, unpack_from
import unittest
from unittest.mock import patch

from anno1503_overhaul import world_settings_multiplayer_ai as ai
from anno1503_overhaul import world_settings_multiplayer_scene as exporter
from anno1503_overhaul.world_island_catalogue import _chunks
from anno1503_overhaul.world_options_snapshot import SETTINGS_FIELDS
from test_world_settings_multiplayer_scene import chunk, field, snapshot, stock_scene, stock_seat, templates


def profiles(defaults):
    entries = b"".join(field(b"ENTRY", bytes([template]) * 168) for template in range(12))
    return chunk(b"COMPPROFIL2", entries + field(b"DEF", pack("<32i", *defaults)))


def native_scene(*parts):
    return chunk(b"ANNO", chunk(b"SCENE", b"".join(parts)))


def donor_scene(difficulty):
    selections = ((3, 5, 2), (1, 6, 9), (4, 0, 5))[difficulty]
    coins = (40_000, 20_000, 15_000)[difficulty]
    parts = [profiles([-1, *selections, *([-1] * 28)])]
    for seat, x, y in ((1, 344.5, 254.5), (2, 605.5, 434.5), (3, 692.5, 534.5)):
        header = bytearray(stock_seat(seat, 12, coins))
        pack_into("<I", header, 16 + 92, 255)
        parts.append(bytes(header))
        player = pack("<II", 0, seat).ljust(104, b"\0")
        ship = pack("<HHIff", seat, 1502, seat, x + difficulty - 1, y)
        if difficulty == 2:
            ship += field(b"CREW", b"map-specific crew")
        player += field(b"SCHIFF", ship)
        player += field(b"COMP", pack("<II", 12, seat) + f"TYP={4 + difficulty}".encode() + b"\0SUSPEND=0\0")
        parts.append(chunk(b"SPIELER", player))
    return chunk(b"ANNOADDON1", chunk(b"SCENE", b"".join(parts)))


def preview_for_world(world, count):
    return snapshot(worldSize=world, aiCount=count, first=(192, 192), last=(864, 864), extra=((400, 96),))


class ComputerSceneTests(unittest.TestCase):
    def export(self, world, count, *, opt_in, difficulty=1, ai_difficulty=1, donor_edit=None, preview=None,
               peaceful=False, disasters=False):
        base = native_scene(profiles([-1] * 32), stock_scene()[32:])
        donors = tuple(donor_scene(mode) for mode in range(3))
        known = tuple((name, sha256(data).hexdigest(), defaults)
                      for (name, _, defaults), data in zip(ai._DONORS, donors, strict=True))
        if preview is None:
            data = bytearray(preview_for_world(world, count))
            pack_into("<i", data, 16 + 4 * SETTINGS_FIELDS.index("difficulty"), difficulty)
            pack_into("<i", data, 16 + 4 * SETTINGS_FIELDS.index("aiDifficulty"), ai_difficulty)
            preview = bytes(data)
        files, entries = templates()
        with (
            patch.object(exporter, "SOURCE_SHA256", sha256(base).hexdigest()),
            patch.object(ai, "_DONORS", known),
            patch.object(exporter, "catalogue_rows", return_value=entries),
        ):
            return exporter.export_multiplayer_scene(
                base, preview, b"fixture catalogue", files.__getitem__, allow_huge=world == 2048,
                allow_ai=opt_in, allow_disasters=disasters, allow_peaceful_ai=peaceful,
                read_ai_donor=lambda mode: donors[mode] if donor_edit is None else donor_edit(donors[mode]),
            )

    def test_stock_cpu_seats_and_default_profiles_are_deterministic_on_huge(self):
        out = self.export(2048, 3, opt_in=True)
        self.assertEqual(out, self.export(2048, 3, opt_in=True))
        records = list(_chunks(out, 32, len(out)))
        profiles, = [data for tag, data in records if tag == b"COMPPROFIL2"]
        self.assertEqual(unpack_from("<32i", profiles, len(profiles) - 128), (-1, 1, 6, 9, *([-1] * 28)))
        players = [data for tag, data in records if tag == b"SPIELER"]
        ships = []
        for seat, color in ((1, 5), (2, 6), (3, 8)):
            header, body = [data for data in players if unpack_from("<I", data, 4)[0] == seat]
            self.assertEqual(unpack_from("<II", header, 16), (12, 20_000))
            self.assertEqual(unpack_from("<I", header, 92)[0], color)
            ship_id, definition, owner, x, y = unpack_from("<HHIff", body, 112)
            self.assertEqual((definition, owner), (1502, seat))
            self.assertEqual((x % 8, y % 8), (0.5, 0.5))
            self.assertTrue(24 <= x < 2024 and 24 <= y < 2024)
            self.assertIn(pack("<II", 12, seat) + b"TYP=5\0SUSPEND=0\0", body)
            ships.append((ship_id, x, y))
        ids = [unpack_from("<H", data, 112)[0] for data in players if data[104:110] == b"SCHIFF"]
        self.assertEqual(len(ids), len(set(ids)))
        for _, x, y in ships:
            for px, py in exporter.WORLD_SHIP_TILES[2048]:
                self.assertTrue(abs(x - px - 0.5) >= 49 or abs(y - py - 0.5) >= 49)

    def test_difficulty_changes_native_funds_profiles_and_controller_without_preset_ship_state(self):
        standard = self.export(1024, 2, opt_in=True)
        standard_players = [data for tag, data in _chunks(standard, 32, len(standard)) if tag == b"SPIELER"]
        [standard_ship] = [data[:128] for data in standard_players
                           if unpack_from("<I", data, 4)[0] == 1 and data[104:110] == b"SCHIFF"]
        for difficulty, defaults, coins in ((0, (3, 5), 40_000), (2, (4, 0), 15_000)):
            with self.subTest(difficulty=difficulty):
                out = self.export(1024, 2, opt_in=True, difficulty=difficulty)
                records = list(_chunks(out, 32, len(out)))
                [table] = [data for tag, data in records if tag == b"COMPPROFIL2"]
                self.assertEqual(unpack_from("<32i", table, len(table) - 128), (-1, *defaults, *([-1] * 29)))
                roster = [data for tag, data in records if tag == b"SPIELER" and unpack_from("<I", data, 4)[0] == 1]
                head, ship = roster
                self.assertEqual(unpack_from("<II", head, 16), (12, coins))
                self.assertEqual(ship[:128], standard_ship)
                self.assertIn(f"TYP={4 + difficulty}".encode() + b"\0SUSPEND=0\0", ship)
                self.assertNotIn(b"map-specific crew", out)

    def test_rejects_unapproved_count_diplomacy_and_donor(self):
        with self.assertRaisesRegex(ValueError, "cannot apply yet"):
            self.export(1024, 1, opt_in=False)
        with self.assertRaisesRegex(ValueError, "cannot apply yet"):
            self.export(1024, 1, opt_in=True, ai_difficulty=3)
        with self.assertRaisesRegex(ValueError, "reviewed donor"):
            self.export(1024, 1, opt_in=True, donor_edit=lambda data: data + b"changed")

    def test_opt_in_peaceful_ai_marks_only_the_agreed_scenario_guid(self):
        for disasters in (False, True):
            with self.subTest(disasters=disasters):
                stock = self.export(1024, 2, opt_in=True, peaceful=True, disasters=disasters)
                map_bytes = self.export(1024, 2, opt_in=True, ai_difficulty=0, peaceful=True, disasters=disasters)
                stock_records = list(_chunks(stock, 32, len(stock)))
                peaceful_records = list(_chunks(map_bytes, 32, len(map_bytes)))
                [(tag, guid)] = [row for row in peaceful_records if row[0] == b"GUID"]
                self.assertEqual((tag, len(guid), guid[:8]), (b"GUID", 16, b"WSMPAI0!"))
                self.assertEqual([row for row in stock_records if row[0] != b"GUID"],
                                 [row for row in peaceful_records if row[0] != b"GUID"])
        with self.assertRaisesRegex(ValueError, "cannot apply yet"):
            self.export(1024, 2, opt_in=True, ai_difficulty=0)
        for mode in (2, 3):
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, "cannot apply yet"):
                self.export(1024, 2, opt_in=True, ai_difficulty=mode, peaceful=True)

    def test_insufficient_islands_and_zero_count(self):
        with self.assertRaisesRegex(ValueError, "too few clear computer starting positions"):
            preview = snapshot(worldSize=256, first=(8, 8), last=(160, 80), aiCount=3)
            self.export(256, 3, opt_in=True, preview=preview)
        self.assertEqual(self.export(1024, 0, opt_in=True), self.export(1024, 0, opt_in=False))

    def test_uses_only_selected_profiles_and_checks_their_resource_guarantee(self):
        preview = bytearray(preview_for_world(1024, 2))
        pack_into("<i", preview, 16 + 4 * SETTINGS_FIELDS.index("guaranteeBasics"), 1)
        with patch.object(exporter, "verify_starting_resources") as verify:
            out = self.export(1024, 2, opt_in=True, preview=bytes(preview))
        records = dict((tag, data) for tag, data in _chunks(out, 32, len(out)) if tag == b"COMPPROFIL2")
        defaults = unpack_from("<32i", records[b"COMPPROFIL2"], len(records[b"COMPPROFIL2"]) - 128)
        self.assertEqual(defaults, (-1, 1, 6, *([-1] * 29)))
        verify.assert_called_once()
        _, _, starts, size = verify.call_args.args
        self.assertEqual((len(starts), size), (6, 1024))
        self.assertEqual(len({island for _, _, island in starts[4:]}), 2)
