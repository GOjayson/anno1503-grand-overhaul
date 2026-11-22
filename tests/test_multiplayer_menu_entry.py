from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from anno1503_overhaul import multiplayer_menu_entry as entry
from anno1503_overhaul.lan_room import LanRoomError
from anno1503_overhaul.multiplayer_menu_frame import MENU_CALLBACKS, callback_load
from anno1503_overhaul.multiplayer_menu_world import WORLD_MARKER


class MultiplayerMenuEntryTests(unittest.TestCase):
    def test_invalid_or_absent_pipe_request_starts_no_pairing(self):
        malformed = entry._REQUEST.pack(1, 42, 99, 101, 102, b"N\0hidden", b"", b"10.10.0.1", 0, 0, 0, 0, b"")
        unknown_action = entry._REQUEST.pack(5, 42, 99, 101, 102, b"Name", b"", b"10.10.0.1", 0, 0, 0, 0, b"")
        with patch.object(entry, "pair_menu_request") as pair:
            for raw in (b"", malformed, unknown_action, malformed + b"X"):
                with self.subTest(raw=raw), self.assertRaises(ValueError):
                    entry._handle(raw, Path("unused"), {})
            pair.assert_not_called()

    def test_request_with_lost_dialog_starts_no_pairing_or_identity_write(self):
        request = entry._REQUEST.pack(1, 42, 99, 101, 102, b"Name", b"", b"10.10.0.1", 0, 0, 0, 0, b"")
        with TemporaryDirectory() as temporary:
            game = Path(temporary)
            (game / "Anno1503.exe").touch()
            with (
                patch.object(entry, "_owner", side_effect=LanRoomError("Dialog closed")) as guard,
                patch.object(entry, "pair_menu_request") as pair,
                patch.object(entry, "set_player_name") as set_name,
            ):
                with self.assertRaisesRegex(LanRoomError, "Dialog closed"):
                    entry._handle(request, game, {})
                guard.assert_called_once_with(42, 99, 101, 102, (game / "Anno1503.exe").resolve())
                pair.assert_not_called()
                set_name.assert_not_called()

    def test_callback_replacements_keep_the_native_register(self):
        for address, before, _ in MENU_CALLBACKS:
            with self.subTest(address=address):
                replacement = callback_load(before, b"\x11\x22\x33\x44")
                self.assertEqual(replacement, before[:1] + b"\x8b" + before[2:3] + b"\x11\x22\x33\x44")
        self.assertIsNone(callback_load(b"\x48\x8d\x05\0\0\0\0", b"\xff" * 4))

    def test_base_maps_pair_without_opening_the_optional_companion(self):
        request = entry._REQUEST.pack(1, 42, 99, 101, 102, b"", b"", b"10.10.0.1", 0, 0, 0, 0, b"")
        fingerprints = []

        def pair(*args, game_fingerprint, **options):
            self.assertNotIn("addon_offer", options)
            fingerprints.append(game_fingerprint())
            return SimpleNamespace(native_plan=lambda **_: b"\x01" * 88)

        with TemporaryDirectory() as temporary:
            game = Path(temporary)
            (game / "Anno1503.exe").touch()
            (game / "AnnoDisplay.dll").touch()
            with (
                patch.object(entry, "_owner"),
                patch.object(entry, "read_copy_marker", return_value={"phase": "vanilla", "source_exe_sha256": "1" * 64}),
                patch.object(entry, "file_sha", side_effect=["1" * 64, "2" * 64] * 2),
                patch.object(entry, "game_fingerprint", return_value="3" * 64),
                patch.object(entry, "load_player", return_value=object()),
                patch.object(entry, "pair_menu_request", side_effect=pair),
                patch.object(entry, "require_runtime") as runtime,
            ):
                pins = {"AnnoDisplay.dll": "2" * 64}
                first = entry._handle(request, game, pins)
                second = entry._handle(request, game, pins, "4" * 64, visibility=True, huge=True)
                self.assertEqual(first, second)
                self.assertEqual(fingerprints[0], fingerprints[1])
                runtime.assert_not_called()

    def test_custom_map_requires_install_selection_before_opening_the_companion(self):
        request = entry._REQUEST.pack(1, 42, 99, 101, 102, b"", b"", b"10.10.0.1", 1, 1, 0, 0, b"")
        with TemporaryDirectory() as temporary:
            game = Path(temporary)
            (game / "Anno1503.exe").touch()
            with (
                patch.object(entry, "_owner"),
                patch.object(entry, "read_copy_marker", return_value={"phase": "vanilla", "source_exe_sha256": "1" * 64}),
                patch.object(entry, "file_sha", return_value="1" * 64),
                patch("anno1503_overhaul.multiplayer_menu_world.read_copy_marker", return_value={WORLD_MARKER: False}),
                patch("anno1503_overhaul.multiplayer_menu_world.choose_preview") as chooser,
            ):
                with self.assertRaisesRegex(ValueError, "was not selected"):
                    entry._handle(request, game, {}, "4" * 64, visibility=True, huge=True)
                chooser.assert_not_called()

    def test_faction_frequency_build_checks_the_installed_module_variant_and_pairs_base_maps(self):
        base = entry._REQUEST.pack(1, 42, 99, 101, 102, b"", b"", b"10.10.0.1", 0, 0, 0, 0, b"")
        preview = entry._REQUEST.pack(1, 42, 99, 101, 102, b"", b"", b"10.10.0.1", 1, 1, 0, 0, b"")
        choice = b"\x04" * entry.SNAPSHOT_SIZE
        derived = entry.MULTIPLAYER_FREQUENCY_AI_SHA256
        results = []

        def pair(*args, game_fingerprint, **kwargs):
            results.append(game_fingerprint())
            return SimpleNamespace(native_plan=lambda **_: bytes(entry.NATIVE_PLAN_SIZE))

        with TemporaryDirectory() as temporary:
            game = Path(temporary)
            files = {"Anno1503.exe": "1" * 64, "AnnoDisplay.dll": "2" * 64}
            for name in (*files, *derived):
                (game / name).touch()
            marker = {"phase": "vanilla", "source_exe_sha256": files["Anno1503.exe"], WORLD_MARKER: False}
            native = {name: (digest, entry.STOCK_SHA256[name]) for name, digest in derived.items()}
            options = {"factions": True, "faction_ai_pins": derived}
            pins = {"AnnoDisplay.dll": files["AnnoDisplay.dll"]}
            with (
                patch.object(entry, "_owner"),
                patch.object(entry, "read_copy_marker", return_value=marker),
                patch.object(entry, "file_sha", side_effect=lambda path: files[path.name]),
                patch.object(entry, "game_fingerprint", return_value="3" * 64) as fingerprint,
                patch.object(entry, "load_player", return_value=object()),
                patch.object(entry, "require_runtime", return_value=game / "AnnoWorldSettings.dll"),
                patch.object(entry, "supports_faction_frequency", return_value=True) as supports,
                patch.object(entry, "select_world", return_value=choice) as chooser,
                patch.object(entry, "pair_menu_request", side_effect=pair),
            ):
                files.update({name: entry.STOCK_SHA256[name] for name in derived})
                entry._handle(base, game, pins, "4" * 64, **options)
                self.assertEqual({name: fingerprint.call_args.kwargs["native_baselines"][name]
                                  for name in derived}, native)
                with self.assertRaisesRegex(LanRoomError, "Enable the verified World Settings"):
                    entry._handle(preview, game, pins, "4" * 64, **options)
                chooser.assert_not_called()
                marker[WORLD_MARKER] = True
                with self.assertRaisesRegex(LanRoomError, "modules differ"):
                    entry._handle(preview, game, pins, "4" * 64, **options)
                supports.assert_not_called()
                files.update(derived)
                entry._handle(base, game, pins, "4" * 64, **options)
                self.assertEqual(results[0], results[1])
                supports.assert_not_called()
                chosen = entry._REPLY.unpack(entry._handle(preview, game, pins, "4" * 64, **options))
                self.assertEqual(chosen[8], choice)
                supports.assert_called_once()
                chooser.assert_called_once()

    def test_shared_flag_mode_changes_pairing_fingerprint_without_the_companion(self):
        fingerprints = []

        def pair(request, player, *, game_fingerprint, **options):
            self.assertNotIn("addon_offer", options)
            fingerprints.append((request.co_op, game_fingerprint()))
            return SimpleNamespace(native_plan=lambda **_: b"\0" * 88)

        with TemporaryDirectory() as temporary:
            game = Path(temporary)
            (game / "Anno1503.exe").touch()
            (game / "AnnoDisplay.dll").touch()
            with (
                patch.object(entry, "_owner"),
                patch.object(entry, "read_copy_marker", return_value={"phase": "vanilla", "source_exe_sha256": "1" * 64}),
                patch.object(entry, "file_sha", return_value="1" * 64),
                patch.object(entry, "game_fingerprint", return_value="3" * 64),
                patch.object(entry, "load_player", return_value=object()),
                patch.object(entry, "pair_menu_request", side_effect=pair),
            ):
                pins = {"AnnoDisplay.dll": "1" * 64}
                for action, address, bind, co_op in (
                    (1, b"", b"10.10.0.1", 0), (1, b"", b"10.10.0.1", 1), (2, b"10.10.0.1", b"", 1),
                ):
                    request = entry._REQUEST.pack(action, 42, 99, 101, 102, b"", address, bind, 0, 0, 0, co_op, b"")
                    entry._handle(request, game, pins)
        self.assertFalse(fingerprints[0][0])
        self.assertNotEqual(fingerprints[0][1], fingerprints[1][1])
        self.assertEqual(fingerprints[1], fingerprints[2])

    def test_both_transports_pass_generated_eight_player_map_through_the_optional_companion(self):
        snapshot = b"\x01" * entry.SNAPSHOT_SIZE
        companion = "4" * 64
        generated = SimpleNamespace(offer={"artifact_sha256": "5" * 64}, scene_size=123,
                                    digest=b"\x05" * 32, map_visibility=0, enemy_visibility=0)

        def pair(request, player, *, game_fingerprint, **options):
            self.assertEqual(request.player_count, 8)
            self.assertEqual(len(game_fingerprint()), 64)
            if request.action in (entry.MenuAction.LAN_HOST, entry.MenuAction.INTERNET_HOST):
                self.assertIs(options["addon_offer"], generated.offer)
            else:
                self.assertEqual(options["addon_id"], entry.FEATURE)
                self.assertEqual(options["prepare_addon"](generated.offer), "5" * 64)
            return SimpleNamespace(native_plan=lambda **_: bytes(entry.NATIVE_PLAN_SIZE))

        with TemporaryDirectory() as temporary:
            game = Path(temporary)
            (game / "Anno1503.exe").touch()
            (game / "AnnoDisplay.dll").touch()
            with (
                patch.object(entry, "_owner"),
                patch.object(entry, "read_copy_marker", return_value={"phase": "vanilla", "source_exe_sha256": "1" * 64}),
                patch.object(entry, "file_sha", return_value="1" * 64),
                patch.object(entry, "game_fingerprint", return_value="3" * 64),
                patch.object(entry, "load_player", return_value=object()),
                patch.object(entry, "start_resolver", return_value=None),
                patch.object(entry, "require_runtime") as runtime,
                patch.object(entry, "make_world", return_value=generated) as make,
                patch.object(entry, "receive_world", return_value=generated) as receive,
                patch.object(entry, "pair_menu_request", side_effect=pair),
            ):
                pins = {"AnnoDisplay.dll": "1" * 64}
                for action, address, bind in ((1, b"", b"10.10.0.1"), (2, b"10.10.0.1", b""),
                                              (3, b"1.1.1.1", b"10.10.0.1"), (4, b"1.1.1.1", b"")):
                    preview = snapshot if action in (1, 3) else b""
                    request = entry._REQUEST.pack(action, 42, 99, 101, 102, b"", address, bind,
                                                  0, 1, len(preview), 8, preview)
                    reply = entry._REPLY.unpack(entry._handle(request, game, pins, companion))
                    self.assertEqual((reply[0], reply[3], reply[4]), (0, generated.scene_size, generated.digest))
                self.assertEqual(runtime.call_count, 4)
                self.assertEqual(make.call_count, 2)
                self.assertEqual(receive.call_count, 2)
                for call in (*make.call_args_list, *receive.call_args_list):
                    self.assertEqual(call.kwargs["human_slots"], 8)


if __name__ == "__main__":
    unittest.main()
