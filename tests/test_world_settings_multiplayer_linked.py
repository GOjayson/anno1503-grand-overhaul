from hashlib import sha256
from pathlib import Path
from struct import pack, unpack_from
import tempfile
import unittest
from unittest.mock import patch

from anno1503_overhaul import multiplayer_menu_world as menu
from anno1503_overhaul.world_island_catalogue import _chunks
from anno1503_overhaul.world_settings_multiplayer_linked import ISLAND_DIR, link_generated_islands
from test_world_settings_multiplayer_scene import chunk, snapshot


class LinkedWorldTests(unittest.TestCase):
    def setUp(self):
        self.geometry = pack("<4HI", 64, 96, 64, 64, 5)
        self.land = chunk(b"INFO", bytes(12)) + chunk(b"ANBAU", b"GETREIDE\0")
        self.definitions = chunk(b"WARETYPE", b"native definitions")
        self.inline = chunk(b"ANNO", chunk(b"SCENE", self.definitions +
                            chunk(b"INSEL5", self.geometry + self.land + chunk(b"DISCOVER", bytes(4))) +
                            chunk(b"SCHATZ", bytes(2))))
        self.trailer = bytes(60)

    def test_link_hashes_the_standalone_island_and_preserves_other_scene_records(self):
        scene, assets = link_generated_islands(self.inline, self.trailer)
        [(digest, island)] = assets.items()
        self.assertEqual(digest, sha256(island).hexdigest())
        fields = list(_chunks(scene, 32, len(scene)))
        self.assertEqual(fields, [
            (b"WARETYPE", b"native definitions"),
            (b"INSELLNK", self.geometry + f"WS\\{digest}.scp".encode("ascii") + b"\0"),
            (b"SCHATZ", bytes(2)),
        ])
        end = 16 + unpack_from("<I", island, 12)[0]
        self.assertEqual(island[16:end], self.definitions + chunk(b"INSEL5", pack("<4HI", 0, 0, 64, 64, 0) + self.land))
        self.assertEqual(island[end:], self.trailer)

    def test_host_and_guest_publish_same_assets_and_decline_wrong_content(self):
        with tempfile.TemporaryDirectory() as scratch:
            host, guest = (Path(scratch) / role for role in ("host", "guest"))
            for game in (host, guest):
                (game / "Scenes").mkdir(parents=True)
            with (
                patch.object(menu, "export_snapshot", return_value=self.inline),
                patch.object(menu, "stock_trailer", return_value=self.trailer),
            ):
                generated = menu.make_world(host, snapshot())
                with self.assertRaisesRegex(ValueError, "differs from the host"):
                    menu.receive_world(guest, {**generated.offer, "artifact_sha256": "0" * 64})
                self.assertFalse((guest / ISLAND_DIR).exists())
                self.assertEqual(menu.receive_world(guest, generated.offer), generated)
                [guest_island] = (guest / ISLAND_DIR).glob("*.scp")
                self.assertEqual(guest_island.read_bytes(), (host / ISLAND_DIR / guest_island.name).read_bytes())
                scene_name = generated.digest.hex() + ".sze"
                scene = (guest / menu.MATCH_DIR / scene_name).read_bytes()
                self.assertEqual(scene, (host / menu.MATCH_DIR / scene_name).read_bytes())
                guest_island.write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "differs from its verified content"):
                    menu.receive_world(guest, generated.offer)
                self.assertEqual(guest_island.read_bytes(), b"changed")

    def test_fully_explored_scene_seeds_the_same_human_bits_on_both_peers(self):
        sample = self.inline.replace(chunk(b"DISCOVER", bytes(4)), chunk(b"DISCOVER", pack("<HH", 0x20, 0x4321)))
        scene, assets = link_generated_islands(sample, self.trailer, discover_humans=True)
        [(digest, island)] = assets.items()
        self.assertIn(digest.encode("ascii"), scene)
        end = 16 + unpack_from("<I", island, 12)[0]
        self.assertIn(chunk(b"DISCOVER", pack("<HH", 0x03a1, 0x4321)), island[:end])
        with self.assertRaisesRegex(ValueError, "invalid native discovery"):
            link_generated_islands(self.inline.replace(b"DISCOVER", b"HIRSCH\0\0"), self.trailer, discover_humans=True)
