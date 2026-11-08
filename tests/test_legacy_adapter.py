"""Preparation isolation and failure handling for the real transaction engine."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from anno1503_overhaul import legacy_adapter as adapter


FAKE_FOOD = '''from pathlib import Path
from types import SimpleNamespace
PACKAGE = Path(__file__).resolve().parent
def build_edits(root, spec, progress=print):
    progress("Fixture validated")
    original = (root / "existing.bin").read_bytes()
    archive = (root / "archive.bin").read_bytes()
    def edit(name, before, after, size=None, offset=None):
        return SimpleNamespace(name=name, before=before, after=after,
                               file_size=size, offset=offset)
    return "vanilla", [edit("existing.bin", original, b"patched", len(original)),
        edit("newdir/runtime.bin", None, b"runtime"),
        edit("archive.bin", archive[2:5], b"XYZ", len(archive), 2)]
def main():
    raise RuntimeError("The installer must never be called by preparation")
'''


class LegacyAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.game = self.base / "game"
        self.game.mkdir()
        (self.game / "existing.bin").write_bytes(b"original")
        (self.game / "archive.bin").write_bytes(b"0123456789")
        self.package = self.base / "package"
        self.package.mkdir()
        (self.package / "food_mod.py").write_text(FAKE_FOOD, encoding="utf-8")
        (self.package / "food_patch.json").write_text("{}", encoding="utf-8")
        self.output = self.base / "prepared"

    def prepare(self):
        return adapter.prepare_edits("food", self.package, self.game, self.output)

    @staticmethod
    def rewrite_report(report):
        path = Path(report["prepared_dir"]) / "prepared.json"
        path.write_text(json.dumps(report), encoding="utf-8")

    def test_preparation_is_a_separate_process_and_never_installs(self):
        events = []
        report = adapter.prepare_edits("food", self.package, self.game, self.output, events.append)
        self.assertEqual(report["state"], "vanilla")
        self.assertEqual(len(report["edits"]), 3)
        self.assertIn("Fixture validated", events)
        self.assertEqual((self.game / "existing.bin").read_bytes(), b"original")
        self.assertEqual((self.game / "archive.bin").read_bytes(), b"0123456789")
        self.assertFalse((self.game / "newdir").exists())
        self.assertNotIn("food_mod", sys.modules)

    def test_world_preparation_retains_resolve_copy_guard(self):
        (self.package / "world_mod.py").write_text('''def resolve_copy(spec, root, package=None):
    raise RuntimeError("Source-only package refused")
def build_edits(root, spec, progress=print):
    raise RuntimeError("Must not reach build_edits")
''', encoding="utf-8")
        (self.package / "world_patch.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(adapter.AdapterError, "Source-only package refused"):
            adapter.prepare_edits("world", self.package, self.game, self.output)
        self.assertFalse(self.output.exists())

    def test_output_cannot_write_into_game_package_or_existing_folder(self):
        for target in (self.game / "output", self.package / "output", self.package):
            with self.subTest(target=target):
                with self.assertRaises(adapter.AdapterError):
                    adapter.prepare_edits("food", self.package, self.game, target)
                self.assertFalse((target / "prepared.json").exists())

    def test_install_restore_region_and_introduced_files_preserves_old_backups(self):
        old = self.game / "WorldFoodMod_Backup_0_11_Dev1"
        old.mkdir()
        (old / "manifest.json").write_bytes(b"preserve legacy backup")
        report = self.prepare()
        record = adapter.install_prepared(self.game, report, "vanilla")
        self.assertEqual(record["status"], "installed")
        self.assertEqual((self.game / "archive.bin").read_bytes(), b"01XYZ56789")
        self.assertEqual((self.game / "existing.bin").read_bytes(), b"patched")
        self.assertEqual((self.game / "newdir/runtime.bin").read_bytes(), b"runtime")
        self.assertEqual(adapter.restore(self.game), "vanilla")
        self.assertEqual((self.game / "archive.bin").read_bytes(), b"0123456789")
        self.assertEqual((self.game / "existing.bin").read_bytes(), b"original")
        self.assertFalse((self.game / "newdir").exists())
        self.assertEqual((old / "manifest.json").read_bytes(), b"preserve legacy backup")
        self.assertEqual(adapter.read_manifest(self.game)["status"], "restored")
        self.assertTrue((self.game / "GrandOverhaul_Backup_v1/before/existing.bin").is_file())

    def test_changed_target_since_preparation_stops_before_backup_or_publication(self):
        report = self.prepare()
        (self.game / "archive.bin").write_bytes(b"foreign!!!")
        with self.assertRaises(adapter.AdapterError):
            adapter.install_prepared(self.game, report, "vanilla")
        self.assertEqual((self.game / "existing.bin").read_bytes(), b"original")
        self.assertFalse((self.game / "GrandOverhaul_Backup_v1").exists())

    def test_changed_installed_target_stops_restore_before_any_target_write(self):
        report = self.prepare()
        adapter.install_prepared(self.game, report, "vanilla")
        (self.game / "archive.bin").write_bytes(b"foreign!!!")
        with self.assertRaisesRegex(adapter.AdapterError, "Changed"):
            adapter.restore(self.game)
        self.assertEqual((self.game / "existing.bin").read_bytes(), b"patched")
        self.assertEqual((self.game / "newdir/runtime.bin").read_bytes(), b"runtime")
        self.assertEqual(adapter.read_manifest(self.game)["status"], "installed")

    def test_install_failure_rolls_back_and_retains_recoverable_journal(self):
        report = self.prepare()
        tx = adapter._transactions()
        publish = tx._publish
        calls = []
        def fail_archive(stage, target, *, new=False):
            calls.append(target.name)
            if target.name == "archive.bin":
                raise OSError("injected publication failure")
            return publish(stage, target, new=new)
        with mock.patch.object(tx, "_publish", side_effect=fail_archive):
            with self.assertRaisesRegex(adapter.AdapterError, "previous setup restored"):
                adapter.install_prepared(self.game, report, "vanilla")
        self.assertIn("archive.bin", calls)
        self.assertEqual((self.game / "existing.bin").read_bytes(), b"original")
        self.assertEqual((self.game / "archive.bin").read_bytes(), b"0123456789")
        self.assertFalse((self.game / "newdir").exists())
        self.assertEqual(adapter.read_manifest(self.game)["status"], "rolled_back")

    def test_tampered_payload_and_report_are_refused(self):
        report = self.prepare()
        (self.output / "after/0000.bin").write_bytes(b"tampered")
        with self.assertRaisesRegex(adapter.AdapterError, "payload changed"):
            adapter.install_prepared(self.game, report, "vanilla")
        self.assertEqual((self.game / "existing.bin").read_bytes(), b"original")

    def test_in_memory_report_changes_and_boolean_schema_are_refused(self):
        report = self.prepare()
        report["state"] = "changed-without-updating-report"
        with self.assertRaisesRegex(adapter.AdapterError, "report changed"):
            adapter.install_prepared(self.game, report, "vanilla")
        report["state"] = "vanilla"
        report["schema_version"] = True
        self.rewrite_report(report)
        with self.assertRaisesRegex(adapter.AdapterError, "Unsupported prepared transaction"):
            adapter.install_prepared(self.game, report, "vanilla")
        self.assertFalse((self.game / "GrandOverhaul_Backup_v1").exists())

    def test_traversal_and_foreign_root_binding_are_refused(self):
        report = self.prepare()
        report["edits"][0]["name"] = "../outside.bin"
        self.rewrite_report(report)
        with self.assertRaises(adapter.AdapterError):
            adapter.install_prepared(self.game, report, "vanilla")
        report["edits"][0]["name"] = "existing.bin"
        self.rewrite_report(report)
        elsewhere = self.base / "elsewhere"
        elsewhere.mkdir()
        with self.assertRaisesRegex(adapter.AdapterError, "different game"):
            adapter.install_prepared(elsewhere, report, "vanilla")

    def test_reparse_payload_and_destination_are_refused(self):
        report = self.prepare()
        target = self.output / "after/0000.bin"
        data = target.read_bytes()
        outside = self.base / "outside.bin"
        outside.write_bytes(data)
        target.unlink()
        try:
            target.symlink_to(outside)
        except OSError:
            self.skipTest("Creating symbolic links requires a platform privilege")
        with self.assertRaisesRegex(adapter.AdapterError, "Symbolic links"):
            adapter.install_prepared(self.game, report, "vanilla")
        target.unlink()
        target.write_bytes(data)
        existing = self.game / "existing.bin"
        original = existing.read_bytes()
        existing.unlink()
        outside.write_bytes(original)
        existing.symlink_to(outside)
        with self.assertRaises(adapter.AdapterError):
            adapter.install_prepared(self.game, report, "vanilla")
        self.assertEqual(outside.read_bytes(), b"original")

    def test_reinstall_archives_previous_modular_backup(self):
        report = self.prepare()
        adapter.install_prepared(self.game, report, "vanilla")
        adapter.restore(self.game)
        old = (self.game / "GrandOverhaul_Backup_v1/manifest.json").read_bytes()
        adapter.install_prepared(self.game, report, "vanilla")
        self.assertEqual((self.game / "GrandOverhaul_Backup_v1.previous-1/manifest.json").read_bytes(), old)
        self.assertEqual(adapter.read_manifest(self.game)["status"], "installed")


if __name__ == "__main__":
    unittest.main()
