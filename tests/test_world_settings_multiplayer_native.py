"""Source staging checks for the optional native World Settings companion."""

from pathlib import Path
from struct import unpack
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from anno1503_overhaul import world_settings_multiplayer_native as native_preview
from anno1503_overhaul.world_options import PRIVATE, generator_id
from anno1503_overhaul.world_options_build import PINNED_GENERATOR
from anno1503_overhaul.world_options_menu import apply_menu
from anno1503_overhaul.world_options_snapshot import SETTINGS_FIELDS, SETTINGS_FORMAT, SETTINGS_SIZE, decode
from anno1503_overhaul.world_settings_multiplayer_native import (
    BUILD_EXPORT, BUILD_STARTS_EXPORT, PREVIEW_EXPORT, PREVIEW_PRESETS_EXPORT, PREVIEW_STARTS_EXPORT,
    apply_multiplayer_preview, build_start_plan,
)

from test_world_settings_multiplayer_scene import snapshot


class NativeMultiplayerPreviewTests(unittest.TestCase):
    def test_stages_the_existing_native_menu_and_keeps_the_stock_build_identity(self):
        source = Path(__file__).resolve().parents[1] / "legacy" / "world_settings"
        names = ("WorldSettings.c", "world_menu_preview.inc", "world_ship_reserves.h", "world_backend.c")
        reviewed = {PRIVATE + name: (source / PRIVATE / name).read_bytes() for name in names}
        native = source.parents[1] / "src/anno1503_overhaul/native/world_options"
        for name in ("resource_distribution.inc", "fair_starts.inc", "start_position.inc"):
            reviewed[PRIVATE + name] = (native / name).read_bytes()
        apply_menu(reviewed)
        companion = dict(reviewed)
        apply_multiplayer_preview(companion)
        huge_planner = dict(reviewed)
        apply_multiplayer_preview(huge_planner, allow_huge_planning=True)
        advanced = dict(reviewed)
        apply_multiplayer_preview(advanced, allow_huge_matches=True, allow_stock_ai=True)

        self.assertEqual(generator_id(), PINNED_GENERATOR)
        original_menu = reviewed[PRIVATE + "WorldSettings.c"]
        companion_menu = companion[PRIVATE + "WorldSettings.c"]
        self.assertNotIn(PREVIEW_EXPORT.encode(), original_menu)
        self.assertIn(PREVIEW_EXPORT.encode(), companion_menu)
        self.assertIn(PREVIEW_STARTS_EXPORT.encode(), companion_menu)
        self.assertIn(PREVIEW_PRESETS_EXPORT.encode(), companion_menu)
        self.assertIn(b"return dialogWithPreview(owner,setup,frame,NULL);", companion_menu)
        self.assertIn(b"case WM_CREATE:return wsCreateMenu(d,w)?0:-1;", companion_menu)
        self.assertNotIn(b"wsMultiplayerShipReserves", reviewed[PRIVATE + "world_ship_reserves.h"])
        reserves = companion[PRIVATE + "world_ship_reserves.h"]
        self.assertIn(b"wsMultiplayerShipReserves256", reserves)
        self.assertIn(b"wsMultiplayerShipReserves512", reserves)
        self.assertIn(b"wsMultiplayerShipReserves1024", reserves)
        self.assertNotIn(b"wsMultiplayerShipReserves2048", reserves)
        self.assertNotIn(b"#define WS_MP_HUGE_PLANNING", companion_menu)
        self.assertIn(b"#define WS_MP_HUGE_PLANNING", huge_planner[PRIVATE + "WorldSettings.c"])
        self.assertIn(b"wsMultiplayerShipReserves2048", huge_planner[PRIVATE + "world_ship_reserves.h"])
        self.assertIn(b"d->multiplayerPreview?3:4", companion[PRIVATE + "menu_create.inc"])
        self.assertEqual(huge_planner[PRIVATE + "menu_create.inc"], companion[PRIVATE + "menu_create.inc"])
        self.assertIn(b"#define WS_MP_HUGE_MATCHES", advanced[PRIVATE + "WorldSettings.c"])
        self.assertIn(b"#define WS_MP_STOCK_AI", advanced[PRIVATE + "WorldSettings.c"])
        stock_ai_check = b"s->aiCount&&!WorldSettingsMultiplayerPreviewActive()&&!WorldSettingsAIExperimentConfigured()"
        for name in ("WorldSettings.c", "world_backend.c"):
            self.assertIn(stock_ai_check, advanced[PRIVATE + name])
            self.assertNotIn(stock_ai_check, companion[PRIVATE + name])
        self.assertIn(b"(d->multiplayerPreview&&!wsMultiplayerStartLayout)?3:4", advanced[PRIVATE + "menu_create.inc"])
        self.assertIn(b'S: Host start   1-3: Other player starts', companion[PRIVATE + "menu_create.inc"])
        self.assertIn(b'S: You   1-3: AI', companion[PRIVATE + "menu_create.inc"])
        self.assertNotIn(b'"Fire and plague"', reviewed[PRIVATE + "menu_create.inc"])
        self.assertIn(b'"Fire and plague"', companion[PRIVATE + "menu_create.inc"])
        self.assertIn(b'"Volcanic eruptions, earthquakes and drought"', companion[PRIVATE + "menu_create.inc"])
        self.assertIn(b'!d->previewSettings.fairStarts&&!chosen', companion[PRIVATE + "world_menu_preview.inc"])
        helper = companion[PRIVATE + "menu_multiplayer_export.inc"]
        self.assertIn(BUILD_EXPORT.encode(), helper)
        self.assertIn(BUILD_STARTS_EXPORT.encode(), helper)
        self.assertIn(b"settings->cultures == 0 &&", helper)
        self.assertIn(b"settings->factions == 0 &&", helper)
        resources = companion[PRIVATE + "resource_distribution.inc"]
        self.assertEqual(resources.count(b"wsLastStartingParticipant(s)"), 4)
        self.assertIn(b"participant>wsLastStartingParticipant(s)", companion[PRIVATE + "fair_starts.inc"])
        self.assertIn(b"wsPresetDecode(data,received,&value)", companion[PRIVATE + "menu_values.inc"])
        values = companion[PRIVATE + "menu_values.inc"]
        self.assertIn(b"s->disasterMask|=WS_MP_FIRE_PLAGUE_MASK", values)
        self.assertIn(b"s->disasterMask|=WS_MP_WEATHER_DISASTER_MASK", values)
        self.assertIn(b"s->disasterFrequency=s->disasterSeverity=341u", values)
        load = values[values.index(b"static void wsMenuLoadPreset"):values.index(b"static void wsMenuSavePreset")]
        self.assertLess(load.index(b"wsMultiplayerOptionsSupported(&value,0)"), load.index(b"wsMenuApplySettings(d,&value)"))
        self.assertIn(b"wsMenuApplySettings(d,&value);wsMultiplayerPreviewControls(d);", load)
        self.assertIn(b'S: host; 1-3: other player start slots.', values)
        self.assertIn(b"AnnoGrandMultiplayerPresets", values)
        self.assertIn(b"wsLockMultiplayerPresetFolder(path)", values)
        self.assertIn(b'CreateFileA(path,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT', load)
        self.assertIn(b"Process32FirstW", helper)
        self.assertIn(b"QueryFullProcessImageNameW", helper)

    def test_rebuild_passes_the_complete_preview_quota_settings_to_native(self):
        selected = snapshot(climateMin2=1, climateMax2=2, islandSizeMin6=1, islandSizeMax6=2)
        settings = decode(selected)["settings"]

        def copy_preview(encoded, length, buffer, capacity, error, error_length):
            self.assertEqual(length, SETTINGS_SIZE)
            self.assertEqual(dict(zip(SETTINGS_FIELDS, unpack(SETTINGS_FORMAT, encoded), strict=True)), settings)
            self.assertEqual(capacity, len(selected))
            buffer.raw = selected
            return capacity

        build = Mock(side_effect=copy_preview)
        native = SimpleNamespace(**{BUILD_EXPORT: build})
        with patch.object(native_preview, "_load_preview_runtime", return_value=native):
            self.assertEqual(native_preview.build_preview("candidate.dll", "pin", settings), selected)
        build.assert_called_once()

    def test_huge_start_plan_is_refused_before_loading_the_runtime_by_default(self):
        settings = dict.fromkeys(SETTINGS_FIELDS, 0)
        settings["worldSize"] = 2048
        with patch.object(native_preview, "_load_preview_runtime") as load:
            with self.assertRaisesRegex(ValueError, "explicit offline planning opt-in"):
                build_start_plan("candidate.dll", "pin", settings)
            load.assert_not_called()

    def test_only_verified_owned_copy_can_dispatch_preset_chooser(self):
        choose = Mock(return_value=0)
        native = SimpleNamespace(**{PREVIEW_PRESETS_EXPORT: choose})
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            runtime = root / "AnnoGrandWorldSettings" / "AnnoWorldSettings.dll"
            runtime.parent.mkdir()
            runtime.touch()
            with (
                patch.object(native_preview, "_load_preview_runtime", return_value=native),
                patch.object(native_preview, "read_copy_marker", return_value={"phase": "restored"}) as marker,
            ):
                with self.assertRaisesRegex(ValueError, "verified game copy"):
                    native_preview.choose_preview(runtime, "pin", owner=123, preset_root=root)
                choose.assert_not_called()
                marker.return_value = {"phase": "vanilla"}
                self.assertIsNone(native_preview.choose_preview(
                    runtime, "pin", owner=123, allow_start_layout=True, preset_root=root,
                ))
                self.assertEqual(choose.call_args.args[:3], (123, str(root), True))
                choose.return_value = 0xFFFFFFFF
                with self.assertRaisesRegex(ValueError, "cannot be opened for multiplayer presets"):
                    native_preview.choose_preview(runtime, "pin", owner=123, preset_root=root)

    def test_runtime_without_preset_export_uses_the_existing_chooser(self):
        choose = Mock(return_value=0)
        native = SimpleNamespace(**{PREVIEW_STARTS_EXPORT: choose})
        with patch.object(native_preview, "_load_preview_runtime", return_value=native):
            self.assertIsNone(native_preview.choose_preview(
                "previous-runtime", "pin", owner=123, allow_start_layout=True,
                preset_root="older-worker-keeps-its-existing-entry-point",
            ))
        self.assertEqual(choose.call_args.args[0], 123)
