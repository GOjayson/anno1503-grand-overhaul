"""Exercise package trust boundaries using tiny synthetic native payloads.

These tests deliberately replace the frozen specification/runtime trust pins
with fixture pins. They do not certify a game DLL or require licensed inputs.
The actual curated public helper sources and provenance are used unchanged.
"""
from __future__ import annotations

from contextlib import ExitStack
import ast
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from anno1503_overhaul import packages as p


def digest(data):
    return hashlib.sha256(data).hexdigest()


class NativeCompositionTests(unittest.TestCase):
    def setUp(self):
        source = (ROOT / "legacy/world_settings/world_mod.py").read_bytes()
        adapted = p._adapt("world/world_mod.py", source, None)
        tree = ast.parse(adapted)
        helper = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                      and node.name == "_require_composed_food_native")
        namespace = {"food": SimpleNamespace(fm=SimpleNamespace(sha=digest, ModError=p.PackageError))}
        exec(compile(ast.Module(body=[helper], type_ignores=[]), "<generated native composition proof>", "exec"), namespace)
        self.check = namespace["_require_composed_food_native"]
        self.before, self.after = b"reviewed-stock-native", b"reviewed-food-native"
        self.name = "CompLogic.dll"
        self.change = SimpleNamespace(name=self.name, before=self.before, after=self.after, offset=None)

    def test_stock_native_requires_one_exact_whole_file_food_proof(self):
        self.check(self.name, self.before, digest(self.after), False, [self.change])
        for changes in ([], [self.change, self.change],
                        [SimpleNamespace(name=self.name, before=b"other", after=self.after, offset=None)],
                        [SimpleNamespace(name=self.name, before=self.before, after=b"other", offset=None)],
                        [SimpleNamespace(name=self.name, before=self.before, after=self.after, offset=0)],
                        [SimpleNamespace(name="Other.dll", before=self.before, after=self.after, offset=None)]):
            with self.subTest(changes=changes), self.assertRaises(p.PackageError):
                self.check(self.name, self.before, digest(self.after), False, changes)

    def test_installed_activation_never_accepts_a_deferred_stock_native(self):
        with self.assertRaises(p.PackageError):
            self.check(self.name, self.before, digest(self.after), True, [self.change])
        self.check(self.name, self.after, digest(self.after), True, [])

    def test_generated_world_worker_runs_proof_after_food_validation(self):
        adapted = p._adapt("world/world_mod.py", (ROOT / "legacy/world_settings/world_mod.py").read_bytes(), None)
        self.assertLess(adapted.index(b"state, edits = food.build_edits"),
                        adapted.index(b"_require_composed_food_native(name, deferred_native[name]"))
        self.assertIn(b"require_amd64(data, name)", adapted)
        self.assertIn(b'repository_source_snapshot', adapted)

    def test_food_overlay_membership_comes_from_food_spec_and_retains_output_proof(self):
        adapted = p._adapt("world/world_mod.py", (ROOT / "legacy/world_settings/world_mod.py").read_bytes(), None)
        membership = b"if name not in food_native_names and current[name] != native[overlay[\"baseline_payload\"]]:"
        self.assertIn(membership, adapted)
        self.assertLess(adapted.index(b"food_native_names={entry"), adapted.index(membership))
        self.assertIn(b"native_edits[0].after != baseline", adapted)
        tree = ast.parse(adapted)
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "build_edits")
        overlay_gate = next(node for node in function.body if isinstance(node, ast.If)
                            and "name not in food_native_names" in ast.unparse(node))
        namespace = dict(installed=False, food_native_names={"AnnoWelt.dll"},
                         current={"AnnoWelt.dll": b"stock", "AnnoScene.dll": b"scene"},
                         native={"welt": b"food-welt", "scene": b"scene"},
                         spec={"native_overlays": {
                             "AnnoWelt.dll": {"baseline_payload": "welt", "food_native": False},
                             "AnnoScene.dll": {"baseline_payload": "scene", "food_native": False}}},
                         food=SimpleNamespace(fm=SimpleNamespace(ModError=p.PackageError)))
        gate = compile(ast.Module(body=[overlay_gate], type_ignores=[]), "<generated overlay gate>", "exec")
        exec(gate, namespace)
        namespace["current"]["AnnoScene.dll"] = b"unrecognized-scene"
        with self.assertRaises(p.PackageError):
            exec(gate, namespace)


class FoodPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source-game"
        self.source.mkdir()
        self.copy = self.root / "game-copy"
        self.output = self.root / "food-package"

    def test_food_package_needs_no_preserved_world_payloads(self):
        # No provider directory, private payload or substitute trust pin exists
        # in this test. Food is reconstructed from reviewed public source.
        root = p.prepare_food_package(self.output, self.source, self.copy)
        result = p.validate_package(root, self.source)
        self.assertEqual(result["kind"], "anno1503-food-installer-package")
        self.assertEqual(result["feature_versions"], {"food_overhaul": "0.5.0"})
        self.assertEqual(result["copy_root"], str(self.copy.resolve()))
        self.assertIsNone(result["world_path"])
        self.assertIsNone(result["launcher_path"])
        self.assertNotIn("runtime_sha256", result)
        self.assertFalse((root / "world").exists())
        self.assertEqual((root / "food/food_patch.json").read_bytes(),
                         (ROOT / "legacy/food_overhaul/food_patch.json").read_bytes())
        self.assertFalse(self.copy.exists())
        self.assertFalse(any(self.source.iterdir()))

    def test_food_manifest_cannot_bless_changed_helper(self):
        p.prepare_food_package(self.output, self.source, self.copy)
        helper = self.output / "food/food_mod.py"
        helper.write_bytes(helper.read_bytes() + b"\n# changed helper\n")
        manifest = json.loads((self.output / "manifest.json").read_bytes())
        manifest["files"]["food/food_mod.py"] = digest(helper.read_bytes())
        (self.output / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(p.PackageError):
            p.validate_package(self.output)

    def test_food_package_rejects_world_outputs_and_unknown_kind(self):
        p.prepare_food_package(self.output, self.source, self.copy)
        world = self.output / "world"
        world.mkdir()
        (world / "activation_session.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(p.PackageError):
            p.validate_package(self.output)
        shutil.rmtree(world)
        manifest = json.loads((self.output / "manifest.json").read_bytes())
        manifest["kind"] = "unreviewed-installer"
        (self.output / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(p.PackageError):
            p.validate_package(self.output)

    def test_food_output_refuses_existing_or_source_locations(self):
        self.output.mkdir()
        with self.assertRaises(p.PackageError):
            p.prepare_food_package(self.output, self.source, self.copy)
        with self.assertRaises(p.PackageError):
            p.prepare_food_package(self.source / "installer", self.source, self.copy)


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.baselines = self.root / "baselines"
        self.source = self.root / "source-game"
        self.source.mkdir()
        self.copy = self.root / "game-copy"
        self.output = self.root / "prepared"
        for _, (family, names) in p._LAYOUT.items():
            for name in names:
                original = ROOT / "legacy" / family / name
                target = self.baselines / family / name
                target.parent.mkdir(parents=True, exist_ok=True)
                data = original.read_bytes()
                if family == "world_settings" and name == "world_mod.py":
                    lines = data.splitlines(keepends=True)
                    at = next(i for i, line in enumerate(lines)
                              if b'if spec.get("repository_source_snapshot", {}).get("source_only") is True:' in line)
                    del lines[at:at+2]
                    data = b"".join(lines)
                target.write_bytes(data)
        self.native = self._native()
        self.frozen = {
            "version": "0.11.0-dev.1", "status": "UNFINISHED",
            "original_game_root": "historical-placeholder",
            "payloads": {name: digest(self.native) for name in p._NATIVE},
            "data_payloads": {}, "actual_game_run": True,
            "expanded_engine_plan_sha256": digest((ROOT / "legacy/world_settings/developer/huge_world/runtime_engine_edits.json").read_bytes()),
        }
        for i in range(16):
            name = "assets/WorldSettingsIslands/Nord/template_" + str(i) + ".scp"
            data = b"native fixture asset " + bytes([i])
            self.frozen["data_payloads"][name] = digest(data)
            self.frozen["payloads"][name] = digest(data)
            target = self.baselines / "world_settings" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        for name in p._NATIVE:
            target = self.baselines / "world_settings" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(self.native)
        self.patches = ExitStack()
        self.addCleanup(self.patches.close)
        self._pin_fixture()

    @staticmethod
    def _native(machine=0x8664):
        data = bytearray(256)
        data[:2] = b"MZ"
        struct.pack_into("<I", data, 60, 128)
        data[128:132] = b"PE\0\0"
        struct.pack_into("<H", data, 132, machine)
        struct.pack_into("<H", data, 152, 0x20b)
        return bytes(data)

    def _pin_fixture(self):
        raw = (json.dumps(self.frozen, indent=2) + "\n").encode()
        (self.baselines / "world_settings/world_patch.json").write_bytes(raw)
        self.patches.enter_context(patch.object(p, "FROZEN_WORLD_SPEC_SHA256", digest(raw)))
        self.patches.enter_context(patch.object(p, "RUNTIME_SHA256", self.frozen["payloads"]["native/AnnoWorldSettings.dll"]))

    def prepare(self, **kwargs):
        return p.prepare_package(self.baselines, self.output, self.source, self.copy, **kwargs)

    def test_prepares_pinned_helpers_and_relocated_spec_without_changing_inputs(self):
        source_spec = (self.baselines / "world_settings/world_patch.json").read_bytes()
        self.assertEqual(self.prepare(), self.output.resolve())
        result = p.validate_package(self.output, self.source)
        self.assertTrue(result["verified"])
        self.assertEqual(result["source_root"], str(self.source.resolve()))
        self.assertEqual(result["copy_root"], str(self.copy.resolve()))
        self.assertEqual(result["transaction"]["backup"], "GrandOverhaul_Backup_v1")
        deployed = json.loads((self.output / "world/world_patch.json").read_bytes())
        self.assertFalse(deployed["actual_game_run"])
        self.assertFalse(deployed["local_installer_package"]["actual_game_test_performed"])
        self.assertEqual((self.output / "world/frozen_world_patch.json").read_bytes(), source_spec)
        self.assertEqual((self.baselines / "world_settings/world_patch.json").read_bytes(), source_spec)
        launcher = (self.output / "launcher/launch_world_settings.pyw").read_bytes()
        once = (self.output / "launcher/activation_once.py").read_bytes()
        self.assertIn(b"preflight.verify(self.config['copy_root'])", launcher)
        self.assertIn(b"a.verify(config['copy_root'])", once)
        self.assertIn(b'repository_source_snapshot', (self.output / "world/world_mod.py").read_bytes())
        self.assertFalse((self.source / "manifest.json").exists())

    def test_manifest_cannot_bless_tampered_helper(self):
        self.prepare()
        target = self.output / "world/world_mod.py"
        target.write_bytes(target.read_bytes() + b"\nraise RuntimeError('changed')\n")
        manifest = json.loads((self.output / "manifest.json").read_bytes())
        manifest["files"]["world/world_mod.py"] = digest(target.read_bytes())
        (self.output / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(p.PackageError):
            p.validate_package(self.output)

    def test_manifest_cannot_bless_tampered_native(self):
        self.prepare()
        target = self.output / "world/native/AnnoWorldSettings.dll"
        target.write_bytes(target.read_bytes() + b"changed")
        manifest = json.loads((self.output / "manifest.json").read_bytes())
        manifest["files"]["world/native/AnnoWorldSettings.dll"] = digest(target.read_bytes())
        (self.output / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(p.PackageError):
            p.validate_package(self.output)

    def test_untrusted_provider_code_is_refused_before_output_creation(self):
        (self.baselines / "launcher/activation_once.py").write_text("raise RuntimeError('untrusted')", encoding="utf-8")
        with self.assertRaises(p.PackageError):
            self.prepare()
        self.assertFalse(self.output.exists())
        self.assertFalse(any(self.root.glob(".installer-package-staging-*")))

    def test_wrong_payload_fingerprint_is_refused(self):
        (self.baselines / "world_settings/native/AnnoWorldSettings.dll").write_bytes(b"unreviewed")
        with self.assertRaises(p.PackageError):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_source_snapshot_is_not_accepted_as_frozen_spec(self):
        shutil.copyfile(ROOT / "legacy/world_settings/world_patch.json",
                        self.baselines / "world_settings/world_patch.json")
        with self.assertRaises(p.PackageError):
            self.prepare()

    def test_wrong_architecture_is_rejected_even_with_matching_fixture_pin(self):
        invalid = self._native(machine=0x14c)
        for name in p._NATIVE:
            (self.baselines / "world_settings" / name).write_bytes(invalid)
            self.frozen["payloads"][name] = digest(invalid)
        self._pin_fixture()
        with self.assertRaisesRegex(p.PackageError, "AMD64"):
            self.prepare()

    def test_output_cannot_overwrite_or_be_inside_inputs(self):
        self.output.mkdir()
        sentinel = self.output / "keep.txt"
        sentinel.write_text("keep", encoding="utf-8")
        with self.assertRaises(p.PackageError):
            self.prepare()
        self.assertEqual(sentinel.read_text(), "keep")
        for output in (self.baselines / "new", self.source / "new", self.copy / "new"):
            with self.assertRaises(p.PackageError):
                p.prepare_package(self.baselines, output, self.source, self.copy)

    def test_different_source_or_same_source_copy_is_refused(self):
        self.prepare()
        other = self.root / "another-game"
        other.mkdir()
        with self.assertRaises(p.PackageError):
            p.validate_package(self.output, other)
        with self.assertRaises(p.PackageError):
            p.prepare_package(self.baselines, self.root / "other-output", self.source, self.source)

    def test_unexpected_files_and_directories_are_refused(self):
        self.prepare()
        extra = self.output / "world/usercustomize.py"
        extra.write_text("pass", encoding="utf-8")
        with self.assertRaises(p.PackageError):
            p.validate_package(self.output)
        extra.unlink()
        (self.output / "unreviewed").mkdir()
        with self.assertRaises(p.PackageError):
            p.validate_package(self.output)

    def test_only_bounded_diagnostic_locations_are_mutable(self):
        self.prepare()
        (self.output / "world/activation_session.json").write_text("{}", encoding="utf-8")
        logs = self.output / "launcher/logs"
        logs.mkdir()
        (logs / "20261108.jsonl").write_text('{"observation":"fixture"}\n', encoding="utf-8")
        self.assertTrue(p.validate_package(self.output)["verified"])
        (logs / "helper.py").write_text("pass", encoding="utf-8")
        with self.assertRaises(p.PackageError):
            p.validate_package(self.output)

    def test_missing_helper_is_refused(self):
        self.prepare()
        (self.output / "world/activation/preflight.py").unlink()
        with self.assertRaises(p.PackageError):
            p.validate_package(self.output)

    def test_symlinked_payload_is_refused(self):
        self.prepare()
        native = self.output / "world/native/AnnoWorldSettings.dll"
        external = self.root / "external.dll"
        external.write_bytes(native.read_bytes())
        native.unlink()
        try:
            native.symlink_to(external)
        except OSError:
            self.skipTest("Creating a symlink requires platform privilege")
        with self.assertRaises(p.PackageError):
            p.validate_package(self.output)


if __name__ == "__main__":
    unittest.main()
