"""Filesystem recovery checks; no Anno installation or process is touched."""
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from anno1503_overhaul import vanilla


def sha(data):
    return hashlib.sha256(data).hexdigest()


class VanillaRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.source = self.folder / "source"
        self.source.mkdir()
        self.package = self.folder / "food"
        self.package.mkdir()
        self.original = {
            "Anno1503.exe": b"inspected executable",
            "Example.dll": b"original native image",
            "Data/example.dat": b"original data",
            "Anlagen.dat": b"HEAD-original-region-TAIL",
            "ToolGfx/fenster.inc": b"original index",
            "ToolGfx/fenster.tex": b"original texture",
        }
        self.modified = dict(self.original)
        self.modified.update({
            "Example.dll": b"changed native image",
            "Data/example.dat": b"changed data",
            "Anlagen.dat": b"HEAD-modified-region-TAIL",
            "ToolGfx/fenster.inc": b"changed index",
            "ToolGfx/fenster.tex": b"changed texture",
        })
        for name, data in self.modified.items():
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        archive = self.original["Anlagen.dat"]
        self.offset, self.region_size = 5, 15
        self.region = archive[self.offset:self.offset + self.region_size]
        self.spec = dict(
            exe_sha256=sha(self.original["Anno1503.exe"]),
            native_modules=[dict(name="Example.dll", sources={"vanilla": sha(self.original["Example.dll"])})],
            files={"Data/example.dat": dict(sources={"vanilla": sha(self.original["Data/example.dat"])})},
            archives=[dict(name="Anlagen.dat", sources={"vanilla": sha(self.region)},
                           region_offset=self.offset, region_size=self.region_size,
                           source_size=len(archive))],
        )
        raw = json.dumps(self.spec).encode()
        (self.package / "food_patch.json").write_bytes(raw)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(vanilla, "FOOD_SPEC_SHA256", sha(raw)))
        self.stack.enter_context(patch.object(vanilla, "VANILLA_ARCHIVE_HASHES", {"Anlagen.dat": sha(archive)}))
        self.stack.enter_context(patch.object(vanilla, "VANILLA_UI_HASHES", {
            name: sha(data) for name, data in self.original.items() if name.startswith("ToolGfx/")
        }))
        backup = self.source / "FishMod_Backup_0_1"
        entries = []
        for name, data in self.original.items():
            if name == "Anno1503.exe":
                continue
            path = backup / "files" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            offset = self.offset if name == "Anlagen.dat" else None
            path.write_bytes(self.region if offset is not None else data)
            entries.append(dict(name=name, original_sha256=sha(data), region_offset=offset))
        (backup / "backup-manifest.json").write_text(json.dumps(dict(files=entries)))
        self.target = self.folder / "copy"
        shutil.copytree(self.source, self.target)
        (self.target / vanilla.MARKER).write_text(json.dumps(dict(
            schema=1, managed_copy=True, phase="copied",
            source_root=str(self.source), copy_root=str(self.target)
        )))

    def snapshots(self, root):
        return {p.relative_to(root).as_posix(): sha(p.read_bytes()) for p in root.rglob("*") if p.is_file()}

    def test_recovery_uses_verified_originals_and_leaves_source_and_journals_unchanged(self):
        original_source = self.snapshots(self.source)
        plan = vanilla.plan_vanilla_recovery(self.source, self.package)
        self.assertEqual(len(plan), 5)
        result = vanilla.apply_vanilla_recovery(self.target, self.source, self.package, lambda _: None)
        self.assertEqual(result["state"], "vanilla")
        self.assertEqual(set(result["recovered_files"]), set(self.original) - {"Anno1503.exe"})
        for name, data in self.original.items():
            self.assertEqual((self.target / name).read_bytes(), data)
        self.assertEqual(self.snapshots(self.source), original_source)

    def test_wrong_whole_archive_hash_is_detected_before_any_file_publication(self):
        for root in (self.source, self.target):
            path = root / "Anlagen.dat"
            path.write_bytes(b"BAD!" + path.read_bytes()[4:])
        before = self.snapshots(self.target)
        with self.assertRaisesRegex(vanilla.VanillaError, "whole-file"):
            vanilla.apply_vanilla_recovery(self.target, self.source, self.package, lambda _: None)
        self.assertEqual(self.snapshots(self.target), before)

    def test_corrupt_original_backup_is_refused_before_target_changes(self):
        (self.source / "FishMod_Backup_0_1/files/Example.dll").write_bytes(b"corrupt")
        before = self.snapshots(self.target)
        with self.assertRaisesRegex(vanilla.VanillaError, "unavailable"):
            vanilla.apply_vanilla_recovery(self.target, self.source, self.package, lambda _: None)
        self.assertEqual(self.snapshots(self.target), before)

    def test_source_is_never_a_valid_recovery_target(self):
        with self.assertRaisesRegex(vanilla.VanillaError, "independent"):
            vanilla.apply_vanilla_recovery(self.source, self.source, self.package)

    def test_mismatched_marker_refuses_all_writes(self):
        (self.target / vanilla.MARKER).write_text(json.dumps(dict(
            schema=1, managed_copy=True, phase="copied",
            source_root=str(self.folder / "other"), copy_root=str(self.target))))
        before = self.snapshots(self.target)
        with self.assertRaisesRegex(vanilla.VanillaError, "marker"):
            vanilla.apply_vanilla_recovery(self.target, self.source, self.package)
        self.assertEqual(self.snapshots(self.target), before)

    def test_hard_linked_target_is_refused(self):
        path = self.target / "Example.dll"
        path.unlink()
        os.link(self.source / "Example.dll", path)
        with self.assertRaisesRegex(vanilla.VanillaError, "shares"):
            vanilla.apply_vanilla_recovery(self.target, self.source, self.package)

    def test_only_a_new_managed_copy_is_a_valid_recovery_target(self):
        path = self.target / vanilla.MARKER
        original = json.loads(path.read_bytes())
        before = self.snapshots(self.target)
        for changes in ({"managed_copy": False}, {"phase": "installed"}, {"schema": True}):
            with self.subTest(changes=changes):
                path.write_text(json.dumps({**original, **changes}))
                with self.assertRaisesRegex(vanilla.VanillaError, "marker"):
                    vanilla.apply_vanilla_recovery(self.target, self.source, self.package)
                self.assertEqual((self.target / "Example.dll").read_bytes(), self.modified["Example.dll"])
        path.write_text(json.dumps(original))
        self.assertEqual(self.snapshots(self.target), before)

    def test_untrusted_specification_is_refused(self):
        (self.package / "food_patch.json").write_text("{}")
        with self.assertRaisesRegex(vanilla.VanillaError, "specification"):
            vanilla.plan_vanilla_recovery(self.source, self.package)

    def test_path_traversal_in_backup_journal_is_refused(self):
        journal = self.source / "FishMod_Backup_0_1/backup-manifest.json"
        journal.write_text(json.dumps(dict(files=[dict(
            name="../outside", original_sha256=sha(b"outside"), region_offset=None)])))
        with self.assertRaisesRegex(vanilla.VanillaError, "Unsafe"):
            vanilla.plan_vanilla_recovery(self.source, self.package)

    def test_duplicate_keys_in_backup_journal_are_refused(self):
        journal = self.source / "FishMod_Backup_0_1/backup-manifest.json"
        journal.write_text('{"files": [], "files": []}')
        with self.assertRaisesRegex(vanilla.VanillaError, "Duplicate"):
            vanilla.plan_vanilla_recovery(self.source, self.package)

    def test_already_stock_source_needs_no_backup(self):
        for name, data in self.original.items():
            (self.source / name).write_bytes(data)
        shutil.rmtree(self.source / "FishMod_Backup_0_1")
        self.assertEqual(vanilla.plan_vanilla_recovery(self.source, self.package), [])
        self.assertEqual(vanilla.verify_vanilla(self.source, self.package)["state"], "vanilla")


if __name__ == "__main__":
    unittest.main()
