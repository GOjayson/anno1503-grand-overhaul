"""Meaningful installer tests in temporary synthetic game directories only."""
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

import world_transactions as tx


class Transactions(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="world-transaction-test-", dir=Path(__file__).resolve().parent)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "View.dll").write_bytes(b"original-view")
        (self.root / "Anlagen.dat").write_bytes(b"prefix:ORIGINAL:suffix")
        old = self.root / "FoodMod_Backup_0_5"
        old.mkdir()
        (old / "manifest.json").write_bytes(b"existing-food-backup")
        previous = self.root / "WorldFoodMod_Backup_0_6_Dev3"
        previous.mkdir()
        (previous / "manifest.json").write_bytes(b"existing-world-dev3-backup")
        dev7 = self.root / "WorldFoodMod_Backup_0_10_Dev1"
        dev7.mkdir()
        (dev7 / "manifest.json").write_bytes(b"existing-world-dev7-backup")

    def edits(self):
        return [
            tx.Edit("View.dll", b"original-view", b"longer-patched-view-with-section", 13),
            tx.Edit("runtime/world.dll", None, b"new-runtime"),
            tx.Edit("Anlagen.dat", b"ORIGINAL", b"MODIFIED", 22, 7),
        ]

    def assert_old_backup(self):
        self.assertEqual((self.root / "FoodMod_Backup_0_5/manifest.json").read_bytes(), b"existing-food-backup")
        self.assertEqual((self.root / "WorldFoodMod_Backup_0_6_Dev3/manifest.json").read_bytes(), b"existing-world-dev3-backup")
        self.assertEqual((self.root / "WorldFoodMod_Backup_0_10_Dev1/manifest.json").read_bytes(), b"existing-world-dev7-backup")

    def test_current_transaction_namespace_preserves_older_release(self):
        self.assertEqual(tx.VERSION,"0.11.0-dev.1-transactions")
        self.assertEqual(tx.BACKUP,"WorldFoodMod_Backup_0_11_Dev1")
        self.assertEqual(tx.LOCK,".worldfoodmod-0.11-dev1.lock")
        tx.install(self.root,self.edits(),"combined-0.5.0")
        self.assert_old_backup()
        tx.restore(self.root)
        self.assert_originals()

    def assert_originals(self):
        self.assertEqual((self.root / "View.dll").read_bytes(), b"original-view")
        self.assertEqual((self.root / "Anlagen.dat").read_bytes(), b"prefix:ORIGINAL:suffix")
        self.assertFalse((self.root / "runtime/world.dll").exists())
        self.assert_old_backup()

    def test_full_region_new_file_and_exact_restore_with_size(self):
        tx.install(self.root, self.edits(), "combined-0.5.0")
        self.assertEqual((self.root / "Anlagen.dat").read_bytes(), b"prefix:MODIFIED:suffix")
        self.assertEqual((self.root / "runtime/world.dll").read_bytes(), b"new-runtime")
        self.assertEqual(tx.restore(self.root), "combined-0.5.0")
        self.assert_originals()
        self.assertFalse((self.root / "runtime").exists())
        self.assertEqual(tx.read_manifest(self.root)["status"], "restored")
        self.assertEqual(tx.restore(self.root), "combined-0.5.0")

    def test_new_file_never_overwrites_an_existing_file(self):
        target = self.root / "new.dll"
        target.write_bytes(b"somebody-else")
        with self.assertRaisesRegex(tx.TransactionError, "already exists"):
            tx.install(self.root, [tx.Edit("new.dll", None, b"runtime")], "test")
        self.assertEqual(target.read_bytes(), b"somebody-else")
        self.assertFalse((self.root / tx.BACKUP).exists())

    def test_atomic_create_race_never_overwrites_competing_file(self):
        publish = tx._publish

        def racing_publish(stage, target, *, new=False):
            if new:
                target.write_bytes(b"competing-creator")
            return publish(stage, target, new=new)

        with patch.object(tx, "_publish", side_effect=racing_publish):
            with self.assertRaisesRegex(tx.TransactionError, "previous setup restored"):
                tx.install(self.root, [tx.Edit("new.dll", None, b"runtime")], "test")
        self.assertEqual((self.root / "new.dll").read_bytes(), b"competing-creator")
        self.assertEqual(tx.read_manifest(self.root)["status"], "rolled_back")

    def test_exception_after_two_commits_rolls_back_old_and_new_files(self):
        def interrupt(message):
            if message == "Installing: Anlagen.dat":
                raise OSError("injected after existing and new-file commits")

        with self.assertRaisesRegex(tx.TransactionError, "previous setup restored"):
            tx.install(self.root, self.edits(), "test", progress=interrupt)
        self.assert_originals()
        self.assertFalse((self.root / "runtime").exists())
        self.assertEqual(tx.read_manifest(self.root)["status"], "rolled_back")

    def test_final_journal_failure_rolls_back_every_committed_file(self):
        save = tx._save
        faulted = False

        def fail_final(directory, record):
            nonlocal faulted
            if record["status"] == "installed" and not faulted:
                faulted = True
                raise OSError("journal failure after all file commits")
            return save(directory, record)

        with patch.object(tx, "_save", side_effect=fail_final):
            with self.assertRaisesRegex(tx.TransactionError, "previous setup restored"):
                tx.install(self.root, self.edits(), "test")
        self.assert_originals()

    def test_rollback_preserves_external_edit_to_a_committed_target(self):
        def interrupt(message):
            if message == "Installing: Anlagen.dat":
                (self.root / "View.dll").write_bytes(b"external-edit-after-commit")
                raise OSError("stop after competing edit")
        with self.assertRaisesRegex(tx.TransactionError, "rollback requires recovery"):
            tx.install(self.root, self.edits(), "test", progress=interrupt)
        self.assertEqual((self.root / "View.dll").read_bytes(), b"external-edit-after-commit")
        self.assertFalse((self.root / "runtime/world.dll").exists())
        self.assertEqual(tx.read_manifest(self.root)["status"], "rollback_failed")
        self.assertEqual((self.root / tx.BACKUP / "before/View.dll").read_bytes(), b"original-view")

    def test_all_preflight_finishes_before_any_target_write(self):
        edits = self.edits() + [tx.Edit("missing.dll", b"before", b"after", 6)]
        with patch.object(tx, "_publish") as publish:
            with self.assertRaisesRegex(tx.TransactionError, "size mismatch"):
                tx.install(self.root, edits, "test")
            publish.assert_not_called()
        self.assert_originals()
        self.assertFalse((self.root / tx.BACKUP).exists())

    def test_toctou_before_commit_preserves_external_change_and_rolls_back_ours(self):
        def mutate(message):
            if message == "Installing: Anlagen.dat":
                (self.root / "Anlagen.dat").write_bytes(b"external-edit")

        with self.assertRaisesRegex(tx.TransactionError, "Changed since preflight"):
            tx.install(self.root, self.edits(), "test", progress=mutate)
        self.assertEqual((self.root / "View.dll").read_bytes(), b"original-view")
        self.assertFalse((self.root / "runtime/world.dll").exists())
        self.assertEqual((self.root / "Anlagen.dat").read_bytes(), b"external-edit")

    def test_change_to_earlier_target_during_staging_is_detected_before_commit(self):
        def mutate(message):
            if message == "Preparing: Anlagen.dat":
                (self.root / "View.dll").write_bytes(b"external-change")

        with patch.object(tx, "_publish") as publish:
            with self.assertRaisesRegex(tx.TransactionError, "Changed since preflight"):
                tx.install(self.root, self.edits(), "test", progress=mutate)
            publish.assert_not_called()
        self.assertFalse((self.root / tx.BACKUP).exists())
        self.assertFalse(list(self.root.glob(tx.BACKUP + ".pending-*")))

    def test_restore_preflights_all_targets_and_whole_archive(self):
        tx.install(self.root, self.edits(), "test")
        # Even a change outside the edited metadata region blocks restoration.
        (self.root / "Anlagen.dat").write_bytes(b"PREFIX:MODIFIED:suffix")
        with patch.object(tx, "_publish") as publish:
            with self.assertRaisesRegex(tx.TransactionError, "Changed since preflight"):
                tx.restore(self.root)
            publish.assert_not_called()
        self.assertEqual((self.root / "View.dll").read_bytes(), b"longer-patched-view-with-section")
        self.assertTrue((self.root / "runtime/world.dll").exists())

    def test_restore_detects_backup_corruption_before_target_write(self):
        tx.install(self.root, self.edits(), "test")
        (self.root / tx.BACKUP / "before/View.dll").write_bytes(b"bad-backup")
        with patch.object(tx, "_publish") as publish:
            with self.assertRaisesRegex(tx.TransactionError, "Backup missing or changed"):
                tx.restore(self.root)
            publish.assert_not_called()
        self.assertTrue((self.root / "runtime/world.dll").exists())

    def test_changed_new_runtime_is_retained_on_restore(self):
        tx.install(self.root, self.edits(), "test")
        (self.root / "runtime/world.dll").write_bytes(b"user-changed-runtime")
        with self.assertRaisesRegex(tx.TransactionError, "Changed since preflight"):
            tx.restore(self.root)
        self.assertEqual((self.root / "runtime/world.dll").read_bytes(), b"user-changed-runtime")

    def test_restore_toctou_is_detected_immediately_before_removal(self):
        tx.install(self.root, self.edits(), "test")
        def mutate(message):
            if message == "Restoring: runtime/world.dll":
                (self.root / "runtime/world.dll").write_bytes(b"late-external-edit")
        with self.assertRaisesRegex(tx.TransactionError, "Changed since preflight"):
            tx.restore(self.root, progress=mutate)
        self.assertEqual((self.root / "runtime/world.dll").read_bytes(), b"late-external-edit")
        self.assertEqual(tx.read_manifest(self.root)["status"], "restoring")

    def test_path_traversal_absolute_ads_reserved_and_backup_paths_rejected(self):
        for name in ["../outside.dll", "/absolute.dll", "C:/absolute.dll", "folder\\file.dll",
                     "file.dll:stream", "a/../b.dll", "NUL.dll", "trailing. ",
                     "FoodMod_Backup_0_5/manifest.json", tx.BACKUP + "/x", tx.LOCK]:
            with self.subTest(name=name):
                with self.assertRaises(tx.TransactionError):
                    tx.install(self.root, [tx.Edit(name, None, b"bad")], "test")
        self.assert_originals()

    def test_symlink_parent_is_rejected_even_if_it_points_inside_root(self):
        (self.root / "real").mkdir()
        try:
            (self.root / "link").symlink_to(self.root / "real", target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest("Symlink creation unavailable: " + str(exc))
        with self.assertRaisesRegex(tx.TransactionError, "Reparse/symlink"):
            tx.install(self.root, [tx.Edit("link/world.dll", None, b"runtime")], "test")
        self.assertFalse((self.root / "real/world.dll").exists())

    def test_reparse_detection_rejects_existing_parent_before_staging(self):
        (self.root / "junction").mkdir()
        reparse = tx._reparse
        def marker(path):
            return path == self.root / "junction" or reparse(path)
        with patch.object(tx, "_reparse", side_effect=marker):
            with self.assertRaisesRegex(tx.TransactionError, "Reparse/symlink"):
                tx.install(self.root, [tx.Edit("junction/world.dll", None, b"runtime")], "test")
        self.assertFalse((self.root / tx.BACKUP).exists())

    def test_installer_lock_and_active_backup_refusal(self):
        (self.root / tx.LOCK).write_bytes(b"other transaction")
        with self.assertRaisesRegex(tx.TransactionError, "lock exists"):
            tx.install(self.root, self.edits(), "test")
        self.assertEqual((self.root / tx.LOCK).read_bytes(), b"other transaction")
        (self.root / tx.LOCK).unlink()
        tx.install(self.root, self.edits(), "test")
        with self.assertRaisesRegex(tx.TransactionError, "active .* development backup"):
            tx.install(self.root, self.edits(), "test")

    def test_reinstall_retains_completed_new_and_all_older_backups(self):
        tx.install(self.root, self.edits(), "test")
        tx.restore(self.root)
        manifest = (self.root / tx.BACKUP / "manifest.json").read_bytes()
        tx.install(self.root, self.edits(), "test-again")
        self.assertEqual((self.root / (tx.BACKUP + ".previous-1") / "manifest.json").read_bytes(), manifest)
        self.assert_old_backup()

    def test_restore_can_resume_after_interruption_and_preserves_unrelated_new_content(self):
        tx.install(self.root, self.edits(), "test")
        (self.root / "runtime/user-file.txt").write_bytes(b"retain-me")

        def interrupt(message):
            if message == "Restoring: runtime/world.dll":
                raise OSError("interrupted restoration after archive restoration")

        with self.assertRaisesRegex(OSError, "interrupted restoration"):
            tx.restore(self.root, progress=interrupt)
        self.assertEqual(tx.read_manifest(self.root)["status"], "restoring")
        self.assertEqual(tx.restore(self.root), "test")
        self.assert_originals()
        self.assertEqual((self.root / "runtime/user-file.txt").read_bytes(), b"retain-me")

    def test_region_size_and_duplicate_targets_are_rejected(self):
        for edits in [
            [tx.Edit("Anlagen.dat", b"ORIGINAL", b"SHORT", 22, 7)],
            [tx.Edit("Anlagen.dat", b"ORIGINAL", b"MODIFIED", 22, -1)],
            [tx.Edit("x.dll", None, b"x"), tx.Edit("X.dll", None, b"y")],
            [tx.Edit("x", None, b"x"), tx.Edit("x/y", None, b"y")],
        ]:
            with self.subTest(edits=edits):
                with self.assertRaises(tx.TransactionError):
                    tx.install(self.root, edits, "test")
        self.assert_originals()


if __name__ == "__main__":
    unittest.main()
