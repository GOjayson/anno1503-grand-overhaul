"""Independent game-copy boundaries; all inputs are synthetic local fixtures."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from anno1503_overhaul import filesystem as fs


class FilesystemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name).resolve()
        self.source = self.folder / "original"
        self.source.mkdir()
        self.target = self.folder / "copy"
        self.repo = self.folder / "repo"
        self.repo.mkdir()
        for name, data in {
            "Anno1503.exe": b"synthetic game executable",
            "Example.dll": b"synthetic native image",
            "Data/Data.zip": b"required stock archive",
            "Scenes/Islands/example.scp": b"stock island",
            "Languages/Nl/Texte.dat": b"stock translation",
            "ToolGfx/fenster.inc": b"stock icon index",
            "FishMod_Backup_0_1/files/Example.dll": b"old backup",
            "WorldSettings_Work/game_copy/Anno1503.exe": b"old development copy",
            "anno1503_food_mod/food_mod.py": b"old installer",
            "oldgame.sav": b"private save",
            "crash.dmp": b"private crash",
        }.items():
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    def files(self, root):
        return {p.relative_to(root).as_posix(): p.read_bytes()
                for p in root.rglob("*") if p.is_file()}

    def test_clone_has_independent_files_and_omits_existing_mods_backups_and_root_saves(self):
        before = self.files(self.source)
        marker = fs.clone_game(self.source, self.target, repo=self.repo)
        self.assertEqual(marker["phase"], "copied")
        self.assertEqual(marker["copied_files"], 6)
        self.assertTrue((self.target / "Data/Data.zip").is_file())
        for name in ("Anno1503.exe", "Example.dll", "Data/Data.zip", "Scenes/Islands/example.scp"):
            self.assertFalse(os.path.samefile(self.source / name, self.target / name))
            self.assertEqual((self.target / name).stat().st_nlink, 1)
        for name in ("FishMod_Backup_0_1", "WorldSettings_Work", "anno1503_food_mod", "oldgame.sav", "crash.dmp"):
            self.assertFalse((self.target / name).exists())
        (self.target / "Example.dll").write_bytes(b"changed only in copy")
        self.assertEqual(self.files(self.source), before)
        inventory = json.loads((self.target / ".grand-overhaul-copy-inventory.json").read_bytes())
        self.assertEqual(len(inventory["files"]), 6)
        self.assertEqual(fs.read_copy_marker(self.target)["copy_root"], str(self.target))

    def test_nested_saves_logs_dumps_and_backup_files_are_not_game_inputs(self):
        unwanted = (
            "Scenes/private.sav", "Scenes/Islands/example.scp.bak",
            "Data/crash.dmp", "ToolGfx/session.log", "Languages/Nl/example.tmp",
        )
        for name in unwanted:
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"private or stale local artifact")
        inventory = {item["name"] for item in fs.game_inventory(self.source)}
        self.assertTrue(set(unwanted).isdisjoint(inventory))
        self.assertIn("Data/Data.zip", inventory)

    def test_overlapping_source_and_copy_roots_are_refused(self):
        for destination in (self.source, self.source / "child", self.folder):
            with self.subTest(destination=destination):
                with self.assertRaises(fs.CopyError):
                    fs.validate_roots(self.source, destination)

    def test_repository_is_protected_and_only_ignored_local_game_copies_are_allowed(self):
        for destination in (self.repo, self.repo / "src/game", self.folder):
            with self.subTest(destination=destination):
                with self.assertRaises(fs.CopyError):
                    fs.validate_roots(self.source, destination, self.repo)
        _, destination = fs.validate_roots(self.source, self.repo / ".local/game-copies/test", self.repo)
        self.assertEqual(destination, self.repo / ".local/game-copies/test")

    def test_existing_destination_is_never_replaced(self):
        self.target.mkdir()
        important = self.target / "keep.txt"
        important.write_bytes(b"existing user content")
        with self.assertRaisesRegex(fs.CopyError, "already exists"):
            fs.clone_game(self.source, self.target)
        self.assertEqual(important.read_bytes(), b"existing user content")
        self.assertFalse((self.target / fs.COPY_MARKER).exists())

    def test_copy_marker_cannot_be_reused_at_another_path(self):
        fs.clone_game(self.source, self.target)
        elsewhere = self.folder / "different-copy"
        shutil.copytree(self.target, elsewhere)
        with self.assertRaisesRegex(fs.CopyError, "matching"):
            fs.read_copy_marker(elsewhere)

    def test_marker_identity_fields_cannot_be_rebound(self):
        fs.clone_game(self.source, self.target)
        original = (self.target / fs.COPY_MARKER).read_bytes()
        for field, value in (("copy_root", str(self.source)), ("source_root", str(self.target)),
                             ("source_exe_sha256", "0" * 64), ("managed_copy", False)):
            with self.subTest(field=field):
                with self.assertRaisesRegex(fs.CopyError, "identity"):
                    fs.update_copy_marker(self.target, **{field: value})
                self.assertEqual((self.target / fs.COPY_MARKER).read_bytes(), original)

    def test_existing_copy_marker_can_be_read_when_original_source_is_unavailable(self):
        fs.clone_game(self.source, self.target)
        self.source.rename(self.folder / "source-no-longer-at-original-path")
        marker = fs.read_copy_marker(self.target)
        self.assertEqual(Path(marker["source_root"]), self.source)
        self.assertEqual(marker["phase"], "copied")

    def test_operation_lock_serializes_writers_and_does_not_remove_replacement_token(self):
        self.target.mkdir()
        lock = self.target / ".grand-overhaul-operation.lock"
        with fs.operation_lock(self.target):
            first = lock.read_bytes()
            with self.assertRaises(fs.CopyError):
                with fs.operation_lock(self.target):
                    self.fail("second writer acquired the lock")
            self.assertEqual(lock.read_bytes(), first)
        self.assertFalse(lock.exists())
        with fs.operation_lock(self.target):
            lock.write_text(json.dumps(dict(token="another-operation", pid=123)))
        self.assertEqual(json.loads(lock.read_bytes())["token"], "another-operation")

    def test_corrupted_external_lock_is_preserved_without_masking_operation_failure(self):
        self.target.mkdir()
        lock = self.target / ".grand-overhaul-operation.lock"
        with self.assertRaisesRegex(RuntimeError, "operation failed"):
            with fs.operation_lock(self.target):
                lock.write_bytes(b"not a valid lock record")
                raise RuntimeError("operation failed")
        self.assertEqual(lock.read_bytes(), b"not a valid lock record")

    def test_interrupted_clone_is_marked_failed_and_not_silently_reused(self):
        def stop_copying(_):
            raise RuntimeError("cancelled copy")
        with self.assertRaisesRegex(RuntimeError, "cancelled copy"):
            fs.clone_game(self.source, self.target, progress=stop_copying)
        self.assertEqual(fs.read_copy_marker(self.target)["phase"], "failed")
        with self.assertRaisesRegex(fs.CopyError, "already exists"):
            fs.clone_game(self.source, self.target)

    def test_unsafe_relative_paths_are_refused(self):
        for name in ("../escape", "Data/../escape", "/absolute", "C:drive", "Data\\file",
                     "Data/file:stream", "Data/LPT1.txt", "Data/CON", "Data/file.", "Data//file"):
            with self.subTest(name=name):
                with self.assertRaises(fs.CopyError):
                    fs.safe_child(self.source, name)

    def test_linked_source_folder_and_nested_game_file_are_refused(self):
        alias = self.folder / "linked-original"
        try:
            alias.symlink_to(self.source, target_is_directory=True)
        except OSError as exc:
            self.skipTest("Creating a symlink requires platform privileges: " + str(exc))
        with self.assertRaises(fs.CopyError):
            fs.validate_roots(alias, self.target)
        child = self.source / "Data/linked.dat"
        child.symlink_to(self.source / "Example.dll")
        with self.assertRaises(fs.CopyError):
            fs.game_inventory(self.source)


if __name__ == "__main__":
    unittest.main()
