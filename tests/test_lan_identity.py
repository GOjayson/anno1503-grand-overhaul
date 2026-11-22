from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
import unittest
from unittest.mock import patch

from anno1503_overhaul import lan_identity


class LanIdentityTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "identity" / "lan-player.json"

    def test_first_save_and_rename_keep_the_same_id(self):
        self.assertIsNone(lan_identity.load_player(self.path))
        self.assertFalse(self.path.parent.exists())

        original = lan_identity.set_player_name("  E\u0301léonore  ", self.path)
        self.assertEqual(original.display_name, "Éléonore")
        self.assertEqual(lan_identity.validate_player_id(original.player_id), original.player_id)
        self.assertEqual(lan_identity.load_player(self.path), original)

        changed = lan_identity.set_player_name("Capitaine 🏝", self.path)
        self.assertEqual(changed.display_name, "Capitaine 🏝")
        self.assertEqual(changed.player_id, original.player_id)
        self.assertEqual(lan_identity.load_player(self.path), changed)

    def test_default_location_is_the_existing_application_data_directory(self):
        base = str(self.path.parent)
        with patch.dict(os.environ, {"LOCALAPPDATA": base}):
            self.assertIsNone(lan_identity.load_player())
            saved = lan_identity.set_player_name("Captain")
            self.assertEqual(lan_identity.load_player(), saved)
        self.assertEqual(lan_identity.load_player(Path(base) / "Anno1503GrandOverhaul" / "lan-player.json"), saved)

    def test_reject_non_printing_overlong_and_blank_names(self):
        for name in ("", "   ", "y" * 25, "Captain\n", "a\x1bb", "a\u202eb", None):
            with self.subTest(name=name), self.assertRaisesRegex(lan_identity.PlayerIdentityError, "printable"):
                lan_identity.set_player_name(name, self.path)
        self.assertFalse(self.path.exists())
        self.assertEqual(lan_identity.validate_display_name("é" * 24), "é" * 24)

    def test_invalid_saved_state_is_reported_and_left_intact(self):
        stored = lan_identity.set_player_name("Captain", self.path)
        document = dict(schema_version=1, player_id=stored.player_id, display_name=stored.display_name)
        cases = (
            b"\xff",
            b"{",
            b"[1]",
            b" " * 1025,
            json.dumps(dict(document, schema_version=True)).encode(),
            json.dumps(dict(document, player_id="00000000-0000-0000-0000-000000000000")).encode(),
            json.dumps(dict(document, display_name=" Captain")).encode(),
            json.dumps(dict(document, unknown=True)).encode(),
            ('{"display_name":"Captain",' + json.dumps(document)[1:]).encode(),
        )
        for raw in cases:
            with self.subTest(raw=raw[:50]):
                self.path.write_bytes(raw)
                with self.assertRaisesRegex(lan_identity.PlayerIdentityError, "saved LAN player identity is invalid"):
                    lan_identity.load_player(self.path)
                with self.assertRaises(lan_identity.PlayerIdentityError):
                    lan_identity.set_player_name("New Captain", self.path)
                self.assertEqual(self.path.read_bytes(), raw)

    def test_concurrent_first_saves_share_one_id(self):
        ready = Barrier(2, timeout=5)
        publish = lan_identity._publish_new_player

        def synchronized_publish(path, document):
            ready.wait()
            return publish(path, document)

        with patch.object(lan_identity, "_publish_new_player", side_effect=synchronized_publish):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(lan_identity.set_player_name, "First", self.path)
                second = pool.submit(lan_identity.set_player_name, "Second", self.path)
                self.assertEqual(first.result().player_id, second.result().player_id)

        self.assertIn(lan_identity.load_player(self.path), (first.result(), second.result()))


if __name__ == "__main__":
    unittest.main()
