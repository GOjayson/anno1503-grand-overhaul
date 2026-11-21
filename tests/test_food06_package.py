"""Food 0.6 recipe/refusal tests with a tiny, explicitly synthetic View image.

Native compilation is substituted only in these package fixtures. They do not
certify a game module, art transformation, installation or gameplay session.
The public legacy/new helper source closure is reconstructed unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import struct
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from anno1503_overhaul import food06_package as package
from anno1503_overhaul import ambient_sound, bug_fixes, city_statistics, frozen_runner, installer, vanilla
from anno1503_overhaul import packages as common
from anno1503_overhaul.profile import default_profile

REAL_VIEW_POLICY = package._view_policy
REAL_WELT_POLICY = package._welt_policy


def synthetic_view():
    image = bytearray(256)
    image[:2] = b"MZ"
    struct.pack_into("<I", image, 60, 128)
    image[128:132] = b"PE\0\0"
    struct.pack_into("<H", image, 132, 0x8664)
    struct.pack_into("<H", image, 152, 0x20B)
    return bytes(image)


@dataclass
class Edit:
    name: str
    before: bytes
    after: bytes
    file_size: int
    offset: int | None = None


class Food06PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="anno-food06-package-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "original game"
        self.source.mkdir()
        self.copy = self.root / "independent copy"
        self.output = self.root / "prepared package"
        self.compiler = self.root / "fixture compiler"
        self.compiler.write_bytes(b"Synthetic test marker, not a compiler.")
        self.view = synthetic_view()
        self.pin = common._sha(self.view)
        self.welt = self.view + b"synthetic World payload, not a game module"
        self.welt_pin = common._sha(self.welt)
        policy = patch.object(package, "_view_policy", return_value=self.pin)
        self.policy = policy.start()
        self.addCleanup(policy.stop)
        welt_policy = patch.object(package, "_welt_policy", return_value=self.welt_pin)
        self.welt_policy = welt_policy.start()
        self.addCleanup(welt_policy.stop)
        builder = patch.object(package, "_build_view_from_source", return_value=(self.view, {"fixture": True}))
        self.builder = builder.start()
        self.addCleanup(builder.stop)
        welt_builder = patch.object(package, "_build_welt_from_source", return_value=(self.welt, {"fixture": True}))
        self.welt_builder = welt_builder.start()
        self.addCleanup(welt_builder.stop)

    def prepare(self, **options):
        return package.prepare_food06_package(self.output, self.source, self.copy,
                                              compiler_path=self.compiler, **options)

    def manifest(self):
        return json.loads((self.output / "manifest.json").read_bytes())

    def rewrite_manifest(self, value):
        (self.output / "manifest.json").write_bytes(common._encoded(value))

    def test_new_kind_keeps_old_recovery_spec_and_explicit_food_only_new_world_scope(self):
        self.prepare()
        result = common.validate_package(self.output, self.source)
        self.assertEqual(result["kind"], package.KIND)
        self.assertEqual(result["feature_versions"], {"food_overhaul": package.VERSION})
        self.assertTrue(result["new_world_required"])
        self.assertFalse(result["old_save_migration_supported"])
        self.assertFalse(result["world_settings_supported"])
        self.assertIsNone(result["world_path"])
        self.assertIsNone(result["launcher_path"])
        self.assertFalse(result["actual_game_test_performed"])
        self.assertNotIn("city_statistics_guard", result)
        self.assertEqual(result["welt_sha256"], self.welt_pin)
        self.assertEqual((self.output / package.WELT_PAYLOAD).read_bytes(), self.welt)
        self.assertEqual((self.output / "food/food_patch.json").read_bytes(),
                         (ROOT / "legacy/food_overhaul/food_patch.json").read_bytes())
        self.assertEqual((self.output / "food/food05_mod.py").read_bytes(),
                         (ROOT / "legacy/food_overhaul/food_mod.py").read_bytes())
        self.assertIn("NEW world", (self.output / "food/food_mod.py").read_text())
        self.assertFalse(self.copy.exists())
        self.assertEqual(list(self.source.iterdir()), [])
        self.assertNotIn("world", {path.name for path in self.output.iterdir()})

    def test_old_food05_package_still_uses_its_original_recipe(self):
        with patch.object(package, "_view_policy", side_effect=AssertionError("Food 0.6 must not be consulted")):
            common.prepare_food_package(self.output, self.source, self.copy)
            checked = common.validate_package(self.output, self.source)
        self.assertEqual(checked["kind"], "anno1503-food-installer-package")
        self.assertEqual(checked["feature_versions"], {"food_overhaul": "0.5.0"})
        self.assertEqual((self.output / "food/food_mod.py").read_bytes(),
                         (ROOT / "legacy/food_overhaul/food_mod.py").read_bytes())
        self.builder.assert_not_called()
        self.welt_builder.assert_not_called()

    def test_optional_city_statistics_guard_is_bound_to_exact_food_welt_and_closed_package(self):
        guarded = self.welt + b" reviewed synthetic city bounds"
        guarded_pin = common._sha(guarded)
        self.welt_policy.side_effect = (
            lambda *, city_statistics_guard=False: guarded_pin if city_statistics_guard else self.welt_pin
        )
        with patch.object(city_statistics, "bound_supply_statistics", return_value=guarded) as guard:
            self.prepare(city_statistics_guard=True)
        guard.assert_called_once_with(self.welt)
        self.welt_builder.assert_called_once_with(self.source)
        result = common.validate_package(self.output, self.source)
        self.assertIs(result["city_statistics_guard"], True)
        self.assertEqual(result["welt_sha256"], guarded_pin)
        self.assertEqual((self.output / package.WELT_PAYLOAD).read_bytes(), guarded)
        manifest_path = self.output / "manifest.json"
        self.assertIs(frozen_runner.validate_package_closure(
            self.output, common._sha(manifest_path.read_bytes()), copy_root=self.copy,
        )["city_statistics_guard"], True)

        original = self.manifest()
        for invalid in (0, 1, None, False):
            with self.subTest(invalid=invalid):
                self.rewrite_manifest(dict(original, city_statistics_guard=invalid))
                with self.assertRaises(common.PackageError):
                    common.validate_package(self.output)
        original.pop("city_statistics_guard")
        self.rewrite_manifest(original)
        with self.assertRaises(common.PackageError):
            common.validate_package(self.output)

    def test_legacy_food_welt_cannot_be_relabelled_as_guarded(self):
        self.welt_policy.side_effect = (
            lambda *, city_statistics_guard=False: "f" * 64 if city_statistics_guard else self.welt_pin
        )
        self.prepare()
        manifest = self.manifest()
        self.assertNotIn("city_statistics_guard", manifest)
        self.rewrite_manifest(dict(manifest, city_statistics_guard=True))
        with self.assertRaises(common.PackageError):
            common.validate_package(self.output)

    def test_new_install_requires_guarded_welt_only_when_bug_fixes_is_selected(self):
        guarded = self.welt + b" reviewed synthetic city bounds"
        self.welt_policy.side_effect = (
            lambda *, city_statistics_guard=False: common._sha(guarded) if city_statistics_guard else self.welt_pin
        )
        self.prepare()
        plain = self.output
        self.output = self.root / "prepared with Bug Fixes"
        with patch.object(city_statistics, "bound_supply_statistics", return_value=guarded):
            self.prepare(city_statistics_guard=True)

        profile = default_profile()
        profile["features"].update(food_overhaul=True, world_settings=False, bug_fixes=False)
        quest = bug_fixes.KingOfOreEdit("Nl", "quest.htm", "scene.sze", "0" * 64, b"prior", b"revised")
        with (
            patch.object(bug_fixes, "king_of_ore_assets", return_value=(quest,)),
            patch.object(ambient_sound, "ambient_sound_assets", return_value=()),
            patch.object(vanilla, "plan_vanilla_recovery", return_value=[]),
            patch.object(installer, "game_inventory", return_value=[]),
        ):
            def check(folder):
                return installer.check_install(self.source, self.copy, profile, package=folder,
                                               food_version=installer.FOOD06_VERSION)

            self.assertNotIn("city_statistics_guard", check(plain))
            with self.assertRaisesRegex(installer.InstallerError, "different Bug Fixes selection"):
                check(self.output)
            profile["features"]["bug_fixes"] = True
            self.assertIs(check(self.output)["city_statistics_guard"], True)
            with self.assertRaisesRegex(installer.InstallerError, "different Bug Fixes selection"):
                check(plain)
        self.assertFalse(self.copy.exists())

    def test_unreviewed_world_pin_fails_before_build_or_output(self):
        dummy = ModuleType("anno1503_overhaul.food_supply")
        dummy.FOOD_PROGRESSION_WELT_SHA256 = None
        with patch.dict(sys.modules, {dummy.__name__: dummy}):
            with patch.object(package, "_welt_policy", REAL_WELT_POLICY):
                with self.assertRaisesRegex(common.PackageError, "build review"):
                    self.prepare()
        self.builder.assert_not_called()
        self.welt_builder.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_unreviewed_view_pin_fails_before_build_or_output(self):
        dummy = ModuleType("anno1503_overhaul.food_household")
        dummy.FOOD06_VIEW_SHA256 = None
        with patch.dict(sys.modules, {dummy.__name__: dummy}):
            with patch.object(package, "_view_policy", REAL_VIEW_POLICY):
                with self.assertRaisesRegex(common.PackageError, "build review"):
                    self.prepare()
        self.builder.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_changed_payload_cannot_be_reblessed_by_the_manifest(self):
        self.prepare()
        path = self.output / package.VIEW_PAYLOAD
        changed = path.read_bytes() + b"unreviewed change"
        path.write_bytes(changed)
        manifest = self.manifest()
        manifest["files"][package.VIEW_PAYLOAD] = common._sha(changed)
        manifest["view_sha256"] = common._sha(changed)
        self.rewrite_manifest(manifest)
        with self.assertRaises(common.PackageError):
            common.validate_package(self.output)

    def test_changed_helper_cannot_be_reblessed_by_the_manifest(self):
        self.prepare()
        name = "food/support/food_diet.py"
        path = self.output / name
        path.write_bytes(path.read_bytes() + b"\n# unreviewed provider change\n")
        manifest = self.manifest()
        manifest["files"][name] = common._sha(path.read_bytes())
        self.rewrite_manifest(manifest)
        with self.assertRaises(common.PackageError):
            common.validate_package(self.output)

    def test_changed_world_payload_cannot_be_reblessed_by_the_manifest(self):
        self.prepare()
        path = self.output / package.WELT_PAYLOAD
        changed = path.read_bytes() + b"unreviewed change"
        path.write_bytes(changed)
        manifest = self.manifest()
        manifest["files"][package.WELT_PAYLOAD] = common._sha(changed)
        manifest["welt_sha256"] = common._sha(changed)
        self.rewrite_manifest(manifest)
        with self.assertRaises(common.PackageError):
            common.validate_package(self.output)

    def test_scope_cannot_claim_combined_support_or_old_save_migration(self):
        self.prepare()
        original = self.manifest()
        for name in ("world_settings_supported", "old_save_migration_supported", "new_world_required"):
            manifest = json.loads(json.dumps(original))
            manifest["scope"][name] = not manifest["scope"][name]
            self.rewrite_manifest(manifest)
            with self.subTest(name=name), self.assertRaises(common.PackageError):
                common.validate_package(self.output)

    def test_an_extra_world_directory_or_unlisted_file_is_refused(self):
        self.prepare()
        extra = self.output / "world"
        extra.mkdir()
        with self.assertRaises(common.PackageError):
            common.validate_package(self.output)
        extra.rmdir()
        extra = self.output / "unexpected.txt"
        extra.write_text("not part of the trusted recipe")
        with self.assertRaises(common.PackageError):
            common.validate_package(self.output)

    def test_package_cannot_be_used_for_another_source(self):
        self.prepare()
        other = self.root / "another game"
        other.mkdir()
        with self.assertRaises(common.PackageError):
            common.validate_package(self.output, other)

    def test_existing_and_overlapping_outputs_are_preserved_before_build(self):
        self.output.mkdir()
        sentinel = self.output / "preserve.txt"
        sentinel.write_text("preserved")
        for output in (self.output, self.source / "nested", self.copy / "nested"):
            with self.subTest(output=output), self.assertRaises(common.PackageError):
                package.prepare_food06_package(output, self.source, self.copy, compiler_path=self.compiler)
        self.assertEqual(sentinel.read_text(), "preserved")
        self.builder.assert_not_called()

    def test_copy_must_be_independent_of_original_game(self):
        for copy in (self.source, self.source / "child", self.root):
            with self.subTest(copy=copy), self.assertRaises(common.PackageError):
                package.prepare_food06_package(self.output, self.source, copy, compiler_path=self.compiler)
        self.builder.assert_not_called()

    def test_wrong_builder_output_is_refused_before_publication(self):
        self.builder.return_value = (self.view + b"not reviewed", {"fixture": True})
        with self.assertRaises(common.PackageError):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_wrong_world_builder_output_or_absent_proof_is_refused(self):
        for output in ((self.welt + b"not reviewed", {"fixture": True}), (self.welt, None)):
            self.welt_builder.return_value = output
            with self.subTest(output=output), self.assertRaises(common.PackageError):
                self.prepare()
            self.assertFalse(self.output.exists())

    def test_generic_food05_native_reconstruction_uses_exact_original_or_food05_bytes(self):
        before = synthetic_view()
        after = before[:220] + b"Food" + before[224:] + b"fixture append"
        spec = {"native_modules": [{"name": "AnnoWelt.dll", "after_sha256": common._sha(after),
            "sources": {"vanilla": common._sha(before)}, "changes": {common._sha(before): {
                "patches": [{"offset": 220, "before": before[220:224].hex(), "after": b"Food".hex()}],
                "append_base64": "Zml4dHVyZSBhcHBlbmQ=", "result_size": len(after)}}}]}
        self.assertEqual(package._food05_native(before, spec, "AnnoWelt.dll"), after)
        self.assertIs(package._food05_native(after, spec, "AnnoWelt.dll"), after)
        with self.assertRaises(common.PackageError):
            package._food05_native(before + b"unknown native", spec, "AnnoWelt.dll")
        with self.assertRaises(common.PackageError):
            package._food05_native(before, spec, "View.dll")
        spec["native_modules"][0]["changes"][common._sha(before)]["patches"][0]["before"] = "ffffffff"
        with self.assertRaisesRegex(common.PackageError, "preimage"):
            package._food05_native(before, spec, "AnnoWelt.dll")

    def test_worker_composes_final_bytes_with_original_preimages_in_one_plan(self):
        self.prepare()
        folder = self.output / "food"
        original = [
            Edit("View.dll", b"stock view", b"food05 view", 10),
            Edit("AnnoWelt.dll", b"stock World", b"food05 World", 11),
            Edit("Data/BGruppen.dat", b"stock residents", b"food05 residents", 15),
            Edit("ToolGfx/fenster.inc", b"stock index", b"food05 index", 11),
            Edit("ToolGfx/fenster.tex", b"stock texture", b"food05 texture", 13),
            Edit("Anlagen.dat", b"old archive region", b"new archive region", 1000, 88),
        ]
        base = ModuleType("food05_mod")
        base.__file__ = str(folder / "food05_mod.py")
        base.fm = SimpleNamespace(ModError=ValueError)
        base.tx = SimpleNamespace(Edit=Edit)
        base.build_edits = lambda root, spec, progress: ("vanilla", original)
        base.ui_pairs = lambda root: [("ToolGfx/fenster.inc", "ToolGfx/fenster.tex")]
        diet = ModuleType("food_diet")
        diet.__file__ = str(folder / "support/food_diet.py")
        diet.transform_food05 = lambda before: b"food06 residents" if before == b"food05 residents" else self.fail()
        artwork = ModuleType("food_artwork")
        artwork.__file__ = str(folder / "support/food_artwork.py")
        calls = []
        def transform(*args):
            calls.append(args)
            return b"food06 index", b"food06 texture", {"fixture": True}
        artwork.transform = transform
        namespace = {"__file__": str(folder / "food_mod.py"), "__name__": "food06_fixture"}
        old_path = list(sys.path)
        try:
            with patch.dict(sys.modules, {"food05_mod": base, "food_diet": diet, "food_artwork": artwork}):
                exec(compile((folder / "food_mod.py").read_bytes(), str(folder / "food_mod.py"), "exec"), namespace)
                messages = []
                state, edits = namespace["build_edits"](self.source,
                    json.loads((folder / "food_patch.json").read_bytes()), progress=messages.append)
                self.assertEqual(state, "vanilla")
                self.assertEqual(len(edits), len(original))
                self.assertTrue(any("NEW world" in message for message in messages))
                self.assertEqual(calls, [(b"stock index", b"stock texture", b"food05 index", b"food05 texture")])
                for before, after in zip(original, edits):
                    self.assertEqual((after.name, after.before, after.file_size, after.offset),
                                     (before.name, before.before, before.file_size, before.offset))
                self.assertEqual(edits[0].after, self.view)
                self.assertEqual(edits[1].after, self.welt)
                self.assertEqual(edits[2].after, b"food06 residents")
                self.assertEqual(edits[-1].after, original[-1].after)
                base.build_edits = lambda root, spec, progress: ("combined-0.5.0", original)
                with self.assertRaisesRegex(ValueError, "Restore"):
                    namespace["build_edits"](self.source, json.loads((folder / "food_patch.json").read_bytes()), progress=lambda _: None)
        finally:
            sys.path[:] = old_path


if __name__ == "__main__":
    unittest.main()
