"""Installer lifecycle and refusal checks with isolated game-file fixtures.

The Windows process probe and native vanilla/package validators are replaced
with bounded fixture validators. Copying, preparation subprocesses, journals,
rollback guards and restoration use their real implementations.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from anno1503_overhaul import filesystem, installer, packages, vanilla
from anno1503_overhaul.profile import default_profile


FOOD_FIXTURE = '''from pathlib import Path
from types import SimpleNamespace
def build_edits(root, spec, progress=print):
    before = (root / "Sample.dat").read_bytes()
    if before != b"original fixture":
        raise RuntimeError("Fixture is not the original baseline")
    return "vanilla", [SimpleNamespace(name="Sample.dat", before=before,
        after=b"modded fixture", file_size=len(before), offset=None),
        SimpleNamespace(name="PrivateRuntime/helper.dat", before=None,
        after=b"private fixture runtime", file_size=None, offset=None)]
'''


class InstallerLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.repo = self.base / "repo"
        self.repo.mkdir()
        self.source = self.base / "original"
        self.source.mkdir()
        (self.source / "Anno1503.exe").write_bytes(b"fixture executable, not a game binary")
        (self.source / "Sample.dat").write_bytes(b"original fixture")
        (self.source / "FoodMod_Backup_0_5").mkdir()
        (self.source / "FoodMod_Backup_0_5/manifest.json").write_bytes(b"preserved historical fixture backup")
        self.target = self.base / "managed"
        self.package = self.base / "package"
        (self.package / "food").mkdir(parents=True)
        (self.package / "launcher").mkdir()
        (self.package / "food/food_mod.py").write_text(FOOD_FIXTURE, encoding="utf-8")
        (self.package / "food/food_patch.json").write_text("{}", encoding="utf-8")
        (self.package / "manifest.json").write_text("{}", encoding="utf-8")
        (self.package / "launcher/launcher_config.json").write_text(
            json.dumps({"copy_root": str(self.target)}), encoding="utf-8")
        self.profile = default_profile()
        self.profile["features"]["world_settings"] = False
        self.closed = self.patch(installer, "require_game_closed")
        self.patch(installer, "REPO", self.repo)
        self.validate_package = self.patch(packages, "validate_package", return_value={
            "verified": True, "copy_root": str(self.target), "kind": "anno1503-local-installer-package"})
        self.plan_vanilla = self.patch(vanilla, "plan_vanilla_recovery", return_value=[])
        self.apply_vanilla = self.patch(vanilla, "apply_vanilla_recovery", side_effect=self.apply_fixture_baseline)
        self.verify_vanilla = self.patch(vanilla, "verify_vanilla", side_effect=self.verify_fixture_baseline)

    def patch(self, obj, name, *args, **kwargs):
        patcher = mock.patch.object(obj, name, *args, **kwargs)
        value = patcher.start()
        self.addCleanup(patcher.stop)
        return value

    def apply_fixture_baseline(self, root, source, package, progress):
        self.assertEqual(root, self.target)
        self.assertEqual(source, self.source)
        self.assertNotEqual(root, source)
        self.assertEqual((root / "Sample.dat").read_bytes(), b"original fixture")
        return {"state": "vanilla"}

    def verify_fixture_baseline(self, root, package):
        if (Path(root) / "Sample.dat").read_bytes() != b"original fixture":
            raise vanilla.VanillaError("Fixture is not the verified original baseline")
        return {"state": "vanilla"}

    def install(self):
        return installer.install(self.source, self.target, self.profile, package=self.package)

    def mark(self, *, source=None, phase="restored"):
        self.target.mkdir()
        filesystem.atomic_json(self.target / filesystem.COPY_MARKER, dict(
            schema=1, managed_copy=True, source_root=str(source or self.source),
            copy_root=str(self.target), phase=phase,
            source_exe_sha256=filesystem.file_sha(self.source / "Anno1503.exe")))

    def test_original_or_nested_destination_is_rejected_before_package_preparation(self):
        for destination in (self.source, self.source / "nested-copy", self.base):
            with self.subTest(destination=destination):
                with self.assertRaises(filesystem.CopyError):
                    installer.check_install(self.source, destination, self.profile, package=self.package)
        self.validate_package.assert_not_called()
        self.assertEqual((self.source / "Sample.dat").read_bytes(), b"original fixture")

    def test_existing_unmarked_target_is_never_adopted_or_overwritten(self):
        self.target.mkdir()
        sentinel = self.target / "valuable.dat"
        sentinel.write_bytes(b"leave this folder alone")
        with self.assertRaises((OSError, filesystem.CopyError)):
            installer.check_install(self.source, self.target, self.profile, package=self.package)
        self.assertEqual(sentinel.read_bytes(), b"leave this folder alone")
        self.validate_package.assert_not_called()

    def test_copy_bound_to_another_source_is_refused(self):
        other = self.base / "other-original"
        other.mkdir()
        self.mark(source=other)
        with self.assertRaisesRegex(installer.InstallerError, "different original"):
            installer.check_install(self.source, self.target, self.profile, package=self.package)
        self.validate_package.assert_not_called()

    def test_world_only_preserves_food_off_and_never_prepares_food_for_original(self):
        self.profile["features"]["world_settings"] = True
        self.profile["features"]["food_overhaul"] = False
        self.validate_package.return_value['kind'] = 'anno1503-world-only-installer-package'
        with mock.patch.object(installer.adapter, "prepare_edits") as prepare:
            plan = installer.check_install(self.source, self.target, self.profile, package=self.package)
        prepare.assert_not_called()
        self.assertFalse(plan['profile']['features']['food_overhaul'])
        self.assertFalse(self.target.exists())
        self.assertEqual((self.source / "Sample.dat").read_bytes(), b"original fixture")

    def test_world_only_refuses_a_combined_food_package_before_game_writes(self):
        self.profile['features']['world_settings'] = True
        self.profile['features']['food_overhaul'] = False
        with self.assertRaisesRegex(installer.InstallerError, 'different Food selection'):
            installer.check_install(self.source, self.target, self.profile, package=self.package)
        self.assertFalse(self.target.exists())
        self.assertEqual((self.source / 'Sample.dat').read_bytes(), b'original fixture')

    def test_world_only_checks_unowned_stock_inputs_before_removing_any_payload(self):
        self.profile['features']['world_settings'] = True
        self.profile['features']['food_overhaul'] = False
        self.validate_package.return_value['kind'] = 'anno1503-world-only-installer-package'
        world = self.package / 'world'
        world.mkdir()
        (world / 'world_mod.py').write_text('''from types import SimpleNamespace
def resolve_copy(spec, root, package=None): return root
def build_edits(root, spec, progress=print):
    return 'vanilla', [SimpleNamespace(name='PrivateRuntime/helper.dat', before=None,
        after=b'world-only fixture', file_size=None, offset=None)]
''', encoding='utf-8')
        (world / 'world_patch.json').write_text(json.dumps({
            'exe_sha256': filesystem.file_sha(self.source / 'Anno1503.exe')}), encoding='utf-8')
        self.install()
        (self.target / 'Sample.dat').write_bytes(b'external stock-file change')
        journal = (self.target / 'GrandOverhaul_Backup_v1/manifest.json').read_bytes()
        with self.assertRaisesRegex(vanilla.VanillaError, 'verified original baseline'):
            installer.restore(self.target)
        self.assertEqual((self.target / 'PrivateRuntime/helper.dat').read_bytes(), b'world-only fixture')
        self.assertEqual((self.target / 'GrandOverhaul_Backup_v1/manifest.json').read_bytes(), journal)

    def test_running_game_refusal_occurs_before_creating_copy(self):
        self.closed.side_effect = RuntimeError("Close Anno first")
        with self.assertRaisesRegex(RuntimeError, "Close Anno"):
            self.install()
        self.assertFalse(self.target.exists())
        self.validate_package.assert_not_called()

    def test_installed_copy_round_trip_restores_original_bytes_and_preserves_source_and_saves(self):
        record = self.install()
        self.assertEqual(record["status"], "installed")
        self.assertEqual(record["baseline"], "vanilla")
        self.assertEqual((self.target / "Sample.dat").read_bytes(), b"modded fixture")
        self.assertFalse(os.path.samefile(self.source / "Sample.dat", self.target / "Sample.dat"))
        (self.target / "Savegames").mkdir()
        (self.target / "Savegames/keep.sav").write_bytes(b"preserved user save")
        (self.target / "unrelated-user-file.txt").write_bytes(b"preserved unrelated file")
        report = installer.restore(self.target)
        self.assertTrue(report["restored"])
        self.assertEqual((self.target / "Sample.dat").read_bytes(), b"original fixture")
        self.assertFalse((self.target / "PrivateRuntime").exists())
        self.assertEqual((self.target / "Savegames/keep.sav").read_bytes(), b"preserved user save")
        self.assertEqual((self.target / "unrelated-user-file.txt").read_bytes(), b"preserved unrelated file")
        self.assertEqual((self.source / "Sample.dat").read_bytes(), b"original fixture")
        self.assertEqual((self.source / "FoodMod_Backup_0_5/manifest.json").read_bytes(), b"preserved historical fixture backup")
        self.assertFalse((self.source / "GrandOverhaul_Backup_v1").exists())
        self.assertFalse((self.source / filesystem.COPY_MARKER).exists())
        self.assertEqual(installer.inspect_copy(self.target)["phase"], "restored")

    def test_feature_changes_require_restore_of_active_installation(self):
        self.install()
        before = (self.target / "GrandOverhaul_Backup_v1/manifest.json").read_bytes()
        with self.assertRaisesRegex(installer.InstallerError, "Restore original game"):
            installer.check_install(self.source, self.target, self.profile, package=self.package)
        self.assertEqual((self.target / "GrandOverhaul_Backup_v1/manifest.json").read_bytes(), before)
        self.assertEqual((self.target / "Sample.dat").read_bytes(), b"modded fixture")

    def test_restore_changed_file_refuses_before_altering_other_targets_or_records(self):
        self.install()
        (self.target / "Sample.dat").write_bytes(b"external changes")
        journal = (self.target / "GrandOverhaul_Backup_v1/manifest.json").read_bytes()
        record = (self.target / installer.INSTALL_RECORD).read_bytes()
        with self.assertRaisesRegex(Exception, "Changed since preflight/installation"):
            installer.restore(self.target)
        self.assertEqual((self.target / "Sample.dat").read_bytes(), b"external changes")
        self.assertEqual((self.target / "PrivateRuntime/helper.dat").read_bytes(), b"private fixture runtime")
        self.assertEqual((self.target / "GrandOverhaul_Backup_v1/manifest.json").read_bytes(), journal)
        self.assertEqual((self.target / installer.INSTALL_RECORD).read_bytes(), record)

    def test_restore_works_after_original_and_prepared_package_have_moved(self):
        self.install()
        moved_source = self.base / "moved-original"
        moved_package = self.base / "moved-package"
        self.source.rename(moved_source)
        self.package.rename(moved_package)
        report = installer.restore(self.target)
        self.assertTrue(report["restored"])
        self.assertEqual((self.target / "Sample.dat").read_bytes(), b"original fixture")
        self.assertEqual((moved_source / "Sample.dat").read_bytes(), b"original fixture")

    def test_existing_operation_lock_blocks_restore_without_touching_journal(self):
        self.install()
        lock = self.target / ".grand-overhaul-operation.lock"
        lock.write_text('{"token":"different-operation"}', encoding="utf-8")
        before = (self.target / "GrandOverhaul_Backup_v1/manifest.json").read_bytes()
        with self.assertRaisesRegex(filesystem.CopyError, "Another installer operation"):
            installer.restore(self.target)
        self.assertEqual((self.target / "GrandOverhaul_Backup_v1/manifest.json").read_bytes(), before)
        self.assertTrue(lock.exists())


if __name__ == "__main__":
    unittest.main()
