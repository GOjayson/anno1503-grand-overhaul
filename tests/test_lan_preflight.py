"""Selected game inputs for the LAN compatibility check."""
import hashlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from anno1503_overhaul import lan_preflight
from anno1503_overhaul.__main__ import main
from anno1503_overhaul.filesystem import CopyError


OTHER_SCENARIO = "Scenes/0700Multi/Custom/Harbor.sze"
ISLAND = "Scenes/Islands/Nord/Harbor.scp"


class LanFingerprintTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.exe = b"test stock executable"
        pins = patch.dict(
            lan_preflight.STOCK_INPUTS,
            {"Anno1503.exe": hashlib.sha256(self.exe).hexdigest()},
            clear=True,
        )
        pins.start()
        self.addCleanup(pins.stop)

    def make_game(self, name):
        root = self.folder / name
        root.mkdir()
        (root / "Anno1503.exe").write_bytes(self.exe)
        for relative in (*lan_preflight.COMPARED_INPUTS, OTHER_SCENARIO, ISLAND):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(relative.encode("ascii"))
        return root

    def test_same_bytes_match_from_different_roots(self):
        first = self.make_game("host")
        second = self.make_game("guest")
        (second / "grand-overhaul-local-settings.json").write_text("{}", encoding="utf-8")
        self.assertEqual(
            lan_preflight.game_fingerprint(first),
            lan_preflight.game_fingerprint(second),
        )

    def test_changed_scenario_changes_fingerprint(self):
        game = self.make_game("host")
        before = lan_preflight.game_fingerprint(game)
        (game / lan_preflight.SCENARIO).write_bytes(b"different scene")
        self.assertNotEqual(before, lan_preflight.game_fingerprint(game))

    def test_custom_scene_inventory_is_compared_by_relative_path_and_bytes(self):
        host = self.make_game("host")
        guest = self.make_game("guest")
        custom = "Scenes/0500MultiEndlos/CustomWorld.SZE"
        (host / custom).write_bytes(b"a different scenario")
        self.assertNotEqual(lan_preflight.game_fingerprint(host), lan_preflight.game_fingerprint(guest))

        (guest / Path(custom).name).write_bytes(b"a different scenario")
        self.assertNotEqual(lan_preflight.game_fingerprint(host), lan_preflight.game_fingerprint(guest))
        (guest / lan_preflight.SCENARIO).with_name("customworld.sze").write_bytes(b"a different scenario")
        self.assertEqual(lan_preflight.game_fingerprint(host), lan_preflight.game_fingerprint(guest))

        (guest / OTHER_SCENARIO).write_bytes(b"changed multiplayer scenario")
        self.assertNotEqual(lan_preflight.game_fingerprint(host), lan_preflight.game_fingerprint(guest))

    def test_changed_scene_cache_or_linked_island_changes_fingerprint(self):
        game = self.make_game("host")
        before = lan_preflight.game_fingerprint(game)
        for relative in (lan_preflight.SCENE_CACHE, ISLAND):
            with self.subTest(relative=relative):
                path = game / relative
                original = path.read_bytes()
                path.write_bytes(b"different world input")
                self.assertNotEqual(before, lan_preflight.game_fingerprint(game))
                path.write_bytes(original)

    def test_derived_island_cache_can_differ_by_installation_path(self):
        host = self.make_game("host")
        guest = self.make_game("guest")
        for game in (host, guest):
            (game / "Scenes/Islands/InselCache.txt").write_text(str(game), encoding="utf-8")
        self.assertEqual(lan_preflight.game_fingerprint(host), lan_preflight.game_fingerprint(guest))

    def test_rejects_linked_catalogue_entry(self):
        game = self.make_game("host")
        target = self.folder / "outside.scp"
        target.write_bytes(b"an external island")
        link = (game / ISLAND).with_name("link.scp")
        try:
            link.symlink_to(target)
        except OSError as exc:
            if getattr(exc, "winerror", None) != 1314:
                raise
            self.skipTest("Windows symlink privilege is unavailable")
        with self.assertRaisesRegex(CopyError, "Linked folders or files"):
            lan_preflight.game_fingerprint(game)

    def test_stock_copy_matches_a_copy_with_a_local_data_backup(self):
        stock = self.make_game("stock")
        other = self.make_game("host")
        (other / "Data/Data.zip").write_bytes(b"local backup of the loose DAT files")
        self.assertEqual(lan_preflight.game_fingerprint(stock), lan_preflight.game_fingerprint(other))

    def test_stock_copy_matches_a_copy_with_online_service_settings(self):
        stock = self.make_game("stock")
        other = self.make_game("host")
        settings = other / "Data/config/online/storm.ini"
        settings.parent.mkdir(parents=True)
        settings.write_text('{"Relay": {}, "MatchMaking": {}}', encoding="utf-8")
        self.assertEqual(lan_preflight.game_fingerprint(stock), lan_preflight.game_fingerprint(other))

    def test_all_missing_required_inputs_are_reported(self):
        game = self.make_game("guest")
        missing = (lan_preflight.SCENARIO, "Data/Felder.dat")
        for name in missing:
            (game / name).unlink()
        with self.assertRaises(ValueError) as error:
            lan_preflight.game_fingerprint(game)
        for name in missing:
            self.assertIn(name, str(error.exception))

    def test_missing_scenario_is_reported(self):
        game = self.make_game("host")
        (game / lan_preflight.SCENARIO).unlink()
        with self.assertRaisesRegex(ValueError, "NewEarth"):
            lan_preflight.game_fingerprint(game)

    def test_unsupported_executable_is_refused(self):
        game = self.make_game("host")
        (game / "Anno1503.exe").write_bytes(b"unknown game build")
        with self.assertRaisesRegex(ValueError, "stock game inputs: Anno1503.exe"):
            lan_preflight.game_fingerprint(game)

    def test_only_the_verified_native_derivative_uses_the_stock_fingerprint(self):
        game = self.make_game("host")
        name = "AnnoDisplay.dll"
        original = lan_preflight.game_fingerprint(game)
        baseline = hashlib.sha256((game / name).read_bytes()).hexdigest()
        derivative = b"known isolated native derivative"
        pins = {name: (hashlib.sha256(derivative).hexdigest(), baseline)}
        (game / name).write_bytes(derivative)
        self.assertNotEqual(lan_preflight.game_fingerprint(game), original)
        self.assertEqual(lan_preflight.game_fingerprint(game, native_baselines=pins), original)
        (game / name).write_bytes(b"unreviewed derivative")
        with self.assertRaisesRegex(ValueError, "unverified native derivative"):
            lan_preflight.game_fingerprint(game, native_baselines=pins)

    def test_cli_reports_unicode_names_in_legacy_terminal_encoding(self):
        name = "Captain \U0001f3dd"
        binary = io.BytesIO()
        with io.TextIOWrapper(binary, encoding="cp1252") as output:
            with patch("sys.stdout", output):
                code = main(["lan", "--player-file", str(self.folder / "identity.json"), "name", name])
            output.flush()
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(binary.getvalue()), {"display_name": name})


if __name__ == "__main__":
    unittest.main()
