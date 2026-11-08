"""Bounded copy discovery tests; no real game writes, process access or activation.

Only temporary marker/layout fixtures under WorldSettings_Work/installer_audit
are created. The existing development-copy guard is used without replacing it.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
PACKAGE = Path(__file__).resolve().parents[1]
WORK = PACKAGE.parent
AUDIT = (WORK / "installer_audit").resolve(strict=True)
sys.path.insert(0, str(PACKAGE))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = load_module("copy_location_world_mod", PACKAGE / "world_mod.py")
with patch.dict(sys.modules, {"world_mod": mod}):
    activation = load_module("copy_location_preflight", PACKAGE / "activation/preflight.py")


class SourceValidationBoundary(Exception):
    """Stop before source validation: these fixtures are deliberately not games."""


class CopyLocation(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="copy-location-", dir=AUDIT)
        self.root = Path(self.temporary.name).resolve(strict=True)
        self.root.relative_to(AUDIT)
        self.source = self.root / "source"
        self.source.mkdir()
        self.package = self.root / "layout" / "package"
        self.package.mkdir(parents=True)
        self.spec = {"original_game_root": str(self.source), "exe_sha256": "1" * 64}

    def tearDown(self):
        # Resolve and verify the exact recursive-cleanup target before cleanup.
        resolved = Path(self.temporary.name).resolve(strict=True)
        resolved.relative_to(AUDIT)
        self.assertEqual(resolved, self.root)
        self.assertNotEqual(resolved, AUDIT)
        self.temporary.cleanup()

    def marked(self, path, **changes):
        path.mkdir(parents=True, exist_ok=True)
        marker = dict(schema=1, development_copy=True, copy_root=str(path.resolve()),
                      source_root=str(self.source), source_exe_sha256=self.spec["exe_sha256"])
        marker.update(changes)
        (path / mod.MARKER).write_text(json.dumps(marker), encoding="utf-8")
        return path.resolve()

    def canonical(self):
        return self.source / "WorldSettings_Work" / "game_copy"

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob("*") if p.is_file()}

    def resolve(self, root=None, package=None):
        before = self.snapshot()
        try:
            return mod.resolve_copy(self.spec, root=root, package=package or self.package)
        finally:
            self.assertEqual(self.snapshot(), before, "Copy discovery must be read-only")

    def test_sibling_copy(self):
        selected = self.marked(self.package.parent / "game_copy")
        self.assertEqual(self.resolve(), selected)

    def test_package_extracted_beside_original(self):
        package = self.source / "anno1503_food_world_dev8"
        package.mkdir()
        selected = self.marked(self.canonical())
        self.assertEqual(self.resolve(package=package), selected)

    def test_current_package_version_and_backup_are_distinct_from_dev7(self):
        self.assertEqual(mod.VERSION,"0.11.0-dev.1")
        self.assertEqual(mod.FINAL_STATE,"food-world-0.11.0-dev.1")
        self.assertEqual(mod.tx.BACKUP,"WorldFoodMod_Backup_0_11_Dev1")
        self.assertEqual(mod.tx.LOCK,".worldfoodmod-0.11-dev1.lock")
        old_backup=self.source/"WorldFoodMod_Backup_0_10_Dev1"
        old_backup.mkdir()
        (old_backup/"manifest.json").write_bytes(b"preserved dev7 fixture")
        self.marked(self.canonical())
        self.resolve()
        self.assertEqual((old_backup/"manifest.json").read_bytes(),b"preserved dev7 fixture")

    def test_nested_package_extraction_uses_bound_source_copy(self):
        package = self.source / "WorldSettings_Work" / "package" / "package"
        package.mkdir(parents=True)
        selected = self.marked(self.canonical())
        self.assertEqual(self.resolve(package=package), selected)

    def test_local_worldsettings_work_copy(self):
        selected = self.marked(self.package.parent / "WorldSettings_Work" / "game_copy")
        self.assertEqual(self.resolve(), selected)

    def test_same_resolved_candidate_is_not_ambiguous(self):
        package = self.source / "WorldSettings_Work" / "package"
        package.mkdir(parents=True)
        selected = self.marked(self.canonical())
        self.assertEqual(self.resolve(package=package), selected)

    def test_unmarked_neighbor_is_ignored(self):
        (self.package.parent / "game_copy").mkdir()
        selected = self.marked(self.canonical())
        self.assertEqual(self.resolve(), selected)

    def test_no_marked_copy_is_rejected(self):
        (self.package.parent / "game_copy").mkdir()
        with self.assertRaises(mod.food.fm.ModError):
            self.resolve()

    def test_wrong_copy_source_and_exe_markers_cannot_fall_back(self):
        self.marked(self.canonical())
        candidate = self.package.parent / "game_copy"
        cases = [dict(copy_root=str(self.root / "different-copy")),
                 dict(source_root=str(self.root / "different-source")),
                 dict(source_exe_sha256="2" * 64), dict(schema=2),
                 dict(development_copy=False)]
        for changes in cases:
            with self.subTest(changes=changes):
                self.marked(candidate, **changes)
                with self.assertRaises(mod.food.fm.ModError):
                    self.resolve()

    def test_malformed_marker_cannot_fall_back(self):
        self.marked(self.canonical())
        candidate = self.marked(self.package.parent / "game_copy")
        (candidate / mod.MARKER).write_text("{malformed", encoding="utf-8")
        with self.assertRaises(mod.food.fm.ModError):
            self.resolve()

    def test_marker_directory_cannot_fall_back(self):
        self.marked(self.canonical())
        candidate = self.package.parent / "game_copy"
        (candidate / mod.MARKER).mkdir(parents=True)
        with self.assertRaises(mod.food.fm.ModError):
            self.resolve()

    def test_two_different_valid_copies_are_ambiguous(self):
        self.marked(self.package.parent / "game_copy")
        self.marked(self.canonical())
        with self.assertRaises(mod.food.fm.ModError):
            self.resolve()

    def test_explicit_copy_can_select_among_default_candidates(self):
        selected = self.marked(self.package.parent / "game_copy")
        self.marked(self.canonical())
        self.assertEqual(self.resolve(root=selected), selected)

    def test_explicit_missing_copy_does_not_fall_back(self):
        self.marked(self.canonical())
        with self.assertRaises((OSError, mod.food.fm.ModError)):
            self.resolve(root=self.root / "missing")

    def test_explicit_unmarked_copy_does_not_fall_back(self):
        self.marked(self.canonical())
        unmarked = self.root / "unmarked"
        unmarked.mkdir()
        with self.assertRaises(mod.food.fm.ModError):
            self.resolve(root=unmarked)

    def test_original_game_is_refused_even_with_marker(self):
        self.marked(self.canonical())
        self.marked(self.source)
        with self.assertRaises(mod.food.fm.ModError):
            self.resolve(root=self.source)

    def package_specs(self):
        (self.package / "world_patch.json").write_text(json.dumps(self.spec), encoding="utf-8")
        (self.package / "food_patch.json").write_text("{}", encoding="utf-8")

    def test_installer_default_cli_uses_discovery(self):
        selected = self.marked(self.canonical())
        self.package_specs()
        before = self.snapshot()
        with patch.object(mod, "PACKAGE", self.package), \
                patch.object(mod, "build_edits", return_value=(mod.FINAL_STATE, [])) as build, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(mod.main(["check"]), 0)
        self.assertEqual(Path(build.call_args.args[0]).resolve(), selected)
        self.assertEqual(self.snapshot(), before)

    def test_installer_explicit_missing_cli_never_builds(self):
        self.marked(self.canonical())
        self.package_specs()
        before = self.snapshot()
        with patch.object(mod, "PACKAGE", self.package), patch.object(mod, "build_edits") as build, \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(mod.main(["check", "--game-dir", str(self.root / "missing")]), 1)
        build.assert_not_called()
        self.assertEqual(self.snapshot(), before)

    def check_preflight_selection(self, explicit=None):
        selected = self.marked(self.canonical())
        self.package_specs()
        before = self.snapshot()
        with patch.object(mod, "PACKAGE", self.package), patch.object(activation, "PACKAGE", self.package), \
                patch.object(mod, "build_edits", return_value=(mod.FINAL_STATE, [])) as build, \
                patch.object(mod.food, "build_edits", side_effect=SourceValidationBoundary) as source_build:
            with self.assertRaises(SourceValidationBoundary):
                activation.verify(copy_root=explicit)
        self.assertEqual(Path(build.call_args.args[0]).resolve(), selected)
        self.assertEqual(Path(source_build.call_args.args[0]).resolve(), self.source)
        self.assertEqual(self.snapshot(), before)

    def test_activation_default_uses_same_discovery(self):
        self.check_preflight_selection()

    def test_activation_explicit_copy_is_preserved(self):
        self.marked(self.package.parent / "game_copy")
        self.check_preflight_selection(explicit=self.canonical())


if __name__ == "__main__":
    unittest.main(verbosity=2)
