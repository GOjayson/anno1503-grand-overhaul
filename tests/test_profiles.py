"""Portable profile checks: no game inputs, installation or native processes."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from anno1503_overhaul.features import CatalogError, Feature, FeatureCatalog, default_catalog
from anno1503_overhaul.profile import (
    MAX_PROFILE_BYTES, ProfileError, default_profile, load_profile, profile_path,
    resolve_selection, save_profile, selected_features, validate_profile,
)


def entry(feature_id, *, requires=(), status="experimental", enabled=False):
    return Feature(feature_id, feature_id, "Fixture feature", status, "planned", enabled, requires)


def document(**flags):
    return {"schema_version": 1, "name": "Test profile", "features": flags}


class CatalogTests(unittest.TestCase):
    def test_default_catalogue_preserves_current_dependency_and_priorities(self):
        catalog = default_catalog()
        self.assertEqual(catalog["world_settings"].requires, ("food_overhaul",))
        self.assertEqual(catalog["world_settings"].priority, "priority")
        self.assertEqual(catalog["food_overhaul"].priority, "priority")
        self.assertEqual(catalog["lan_multiplayer"].priority, "priority")
        self.assertEqual(catalog["world_settings"].status, "experimental")

    def test_research_targets_are_unavailable_and_off_by_default(self):
        for feature_id in ("smarter_ai", "lan_multiplayer", "knowledge_overhaul"):
            with self.subTest(feature_id=feature_id):
                feature = default_catalog()[feature_id]
                self.assertEqual(feature.status, "research")
                self.assertFalse(feature.available)
                self.assertFalse(feature.default_enabled)

    def test_duplicate_ids_are_rejected(self):
        with self.assertRaisesRegex(CatalogError, "Duplicate feature ID"):
            FeatureCatalog((entry("food"), entry("food")))

    def test_missing_dependency_is_rejected(self):
        with self.assertRaisesRegex(CatalogError, "Unknown dependency"):
            FeatureCatalog((entry("world", requires=("missing",)),))

    def test_direct_and_indirect_dependency_cycles_are_rejected(self):
        for values in ((entry("a", requires=("a",)),),
                       (entry("a", requires=("b",)), entry("b", requires=("c",)),
                        entry("c", requires=("a",)))):
            with self.subTest(values=values), self.assertRaisesRegex(CatalogError, "cycle"):
                FeatureCatalog(values)

    def test_unknown_status_or_nonboolean_default_is_rejected(self):
        for value in (entry("a", status="implemented_maybe"), entry("a", enabled=1),
                      entry("a", status="research", enabled=True)):
            with self.subTest(value=value), self.assertRaises(CatalogError):
                FeatureCatalog((value,))

    def test_invalid_ids_or_duplicate_dependency_are_rejected(self):
        for value in (entry("../food"), entry(""), entry("a", requires=("b", "b"))):
            with self.subTest(value=value), self.assertRaises(CatalogError):
                FeatureCatalog((value, entry("b")))


class ProfileTests(unittest.TestCase):
    def test_default_profile_enables_only_existing_priority_baselines(self):
        value = default_profile()
        self.assertEqual({key for key, flag in value["features"].items() if flag},
                         {"food_overhaul", "world_settings"})
        self.assertEqual(validate_profile(value), value)

    def test_world_settings_without_food_is_rejected(self):
        with self.assertRaisesRegex(ProfileError, "requires Food overhaul"):
            validate_profile(document(world_settings=True, food_overhaul=False))

    def test_explicit_dependency_resolution_enables_food(self):
        value = resolve_selection(document(world_settings=True), auto_enable_dependencies=True)
        self.assertTrue(value["features"]["world_settings"])
        self.assertTrue(value["features"]["food_overhaul"])
        self.assertFalse(value["features"]["lan_multiplayer"])

    def test_partial_profiles_do_not_silently_enable_defaults(self):
        food = validate_profile(document(food_overhaul=True))
        self.assertFalse(food["features"]["world_settings"])
        empty = validate_profile(document())
        self.assertTrue(all(flag is False for flag in empty["features"].values()))

    def test_research_cannot_be_selected_even_with_dependency_resolution(self):
        for feature_id in ("smarter_ai", "lan_multiplayer", "knowledge_overhaul"):
            for auto in (False, True):
                with self.subTest(feature_id=feature_id, auto=auto), self.assertRaisesRegex(ProfileError, "research target"):
                    resolve_selection(document(**{feature_id: True}), auto_enable_dependencies=auto)

    def test_unknown_ids_are_rejected_even_when_false(self):
        for flag in (False, True):
            with self.subTest(flag=flag), self.assertRaisesRegex(ProfileError, "Unknown feature"):
                validate_profile(document(unknown_feature=flag))

    def test_choices_are_strict_json_booleans(self):
        for flag in (0, 1, "true", "false", [], {}, None):
            with self.subTest(flag=flag), self.assertRaisesRegex(ProfileError, "booleans"):
                validate_profile(document(food_overhaul=flag))

    def test_schema_version_is_strict_integer_and_supported(self):
        for schema in (True, False, 0, 2, "1", None):
            value = document()
            value["schema_version"] = schema
            with self.subTest(schema=schema), self.assertRaisesRegex(ProfileError, "schema version"):
                validate_profile(value)

    def test_profile_shape_requires_known_fields_and_feature_object(self):
        missing = document()
        del missing["name"]
        extra = document()
        extra["game_directory"] = "unrequested-install-target"
        bad_features = document()
        bad_features["features"] = ["food_overhaul"]
        for value in ([], None, missing, extra, bad_features):
            with self.subTest(value=value), self.assertRaises(ProfileError):
                validate_profile(value)

    def test_names_are_bounded_printable_display_text(self):
        for name in ("", "  ", "a" * 81, "profile\nname", "profile\x85name", 123):
            value = document()
            value["name"] = name
            with self.subTest(name=name), self.assertRaises(ProfileError):
                validate_profile(value)
        valid = document()
        valid["name"] = "Handel en kennis — één wereld"
        self.assertEqual(validate_profile(valid)["name"], valid["name"])

    def test_normalisation_never_mutates_requested_flags(self):
        original = document(world_settings=True)
        preserved = copy.deepcopy(original)
        resolve_selection(original, auto_enable_dependencies=True)
        self.assertEqual(original, preserved)

    def test_dependency_order_is_transitive_and_stable(self):
        catalog = FeatureCatalog((entry("a", requires=("b",)),
                                  entry("b", requires=("c",)), entry("c")))
        value = resolve_selection(document(a=True), catalog, auto_enable_dependencies=True)
        self.assertTrue(all(value["features"].values()))
        self.assertEqual(tuple(item.id for item in selected_features(value, catalog)), ("c", "b", "a"))

    def test_available_feature_cannot_pull_in_unavailable_dependency(self):
        catalog = FeatureCatalog((entry("available", requires=("future",)),
                                  entry("future", status="research")))
        with self.assertRaisesRegex(ProfileError, "research target"):
            resolve_selection(document(available=True), catalog, auto_enable_dependencies=True)

    def test_resolution_switch_is_strict_boolean(self):
        with self.assertRaises(ProfileError):
            resolve_selection(document(), auto_enable_dependencies="yes")


class ProfileStorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_generated_filenames_cannot_escape_the_chosen_directory(self):
        for slug in ("../escape", "..", "foo/bar", "foo\\bar", "C:\\escape", "/escape",
                     "profile.json", "name.", "name ", "UPPERCASE", ""):
            with self.subTest(slug=slug), self.assertRaises(ProfileError):
                profile_path(self.root, slug)
        self.assertEqual(profile_path(self.root, "world-1"), self.root.resolve() / "world-1.json")

    def test_windows_reserved_names_are_rejected_on_every_platform(self):
        for slug in ("con", "aux", "nul", "prn", "com1", "com9", "lpt1", "lpt9"):
            with self.subTest(slug=slug), self.assertRaises(ProfileError):
                profile_path(self.root, slug)

    def test_save_and_load_roundtrip_is_source_only(self):
        value = default_profile(name="Mijn wereld — één")
        target = profile_path(self.root / "profiles", "default")
        self.assertEqual(save_profile(target, value), target)
        self.assertEqual(load_profile(target), value)
        self.assertEqual(sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_file()),
                         ["profiles/default.json"])

    def test_existing_profile_is_preserved_without_overwrite(self):
        target = profile_path(self.root, "default")
        save_profile(target, default_profile())
        before = target.read_bytes()
        with self.assertRaises(FileExistsError):
            save_profile(target, document(food_overhaul=True))
        self.assertEqual(target.read_bytes(), before)

    def test_explicit_overwrite_replaces_valid_profile_and_cleans_temporary(self):
        target = profile_path(self.root, "default")
        save_profile(target, default_profile())
        replacement = document(food_overhaul=True)
        save_profile(target, replacement, overwrite=True)
        self.assertEqual(load_profile(target), validate_profile(replacement))
        self.assertEqual([p.name for p in self.root.iterdir()], ["default.json"])

    def test_invalid_selection_never_creates_directories_or_files(self):
        target = self.root / "not-created" / "invalid.json"
        with self.assertRaises(ProfileError):
            save_profile(target, document(lan_multiplayer=True))
        self.assertFalse(target.parent.exists())

    def test_invalid_explicit_filename_and_parent_traversal_are_rejected(self):
        for target in (self.root / "profile.txt", self.root / "CON.json",
                       self.root / "parent" / ".." / "escape.json"):
            with self.subTest(target=target), self.assertRaises(ProfileError):
                save_profile(target, default_profile())

    def test_bounded_read_rejects_oversized_profile(self):
        target = profile_path(self.root, "oversized")
        target.write_bytes(b" " * (MAX_PROFILE_BYTES + 1))
        with self.assertRaisesRegex(ProfileError, "too large"):
            load_profile(target)

    def test_duplicate_json_keys_and_malformed_json_are_rejected(self):
        values = (b'{"schema_version":1,"name":"A","name":"B","features":{}}',
                  b'{"schema_version":1,"name":"A","features":{"food_overhaul":true,"food_overhaul":false}}',
                  b'{not-json}', b'\xff\xff')
        target = profile_path(self.root, "invalid")
        for value in values:
            target.write_bytes(value)
            with self.subTest(value=value), self.assertRaises(ProfileError):
                load_profile(target)

    def test_symlink_destination_is_refused_without_touching_target(self):
        original = self.root / "original.json"
        original.write_text(json.dumps(default_profile()), encoding="utf-8")
        alias = self.root / "alias.json"
        try:
            alias.symlink_to(original)
        except OSError:
            self.skipTest("Creating symlinks requires a platform privilege.")
        before = original.read_bytes()
        with self.assertRaises(ProfileError):
            load_profile(alias)
        with self.assertRaises(ProfileError):
            save_profile(alias, document(), overwrite=True)
        self.assertEqual(original.read_bytes(), before)

    def test_overwrite_switch_is_strict_boolean(self):
        with self.assertRaises(ProfileError):
            save_profile(self.root / "invalid.json", default_profile(), overwrite=1)
        self.assertFalse((self.root / "invalid.json").exists())


if __name__ == "__main__":
    unittest.main()
