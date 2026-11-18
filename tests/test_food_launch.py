"""Food launch disk-policy and read-only closure checks; no Anno is started."""
from __future__ import annotations

import ast
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from anno1503_overhaul import client_context, food_launch as launch, installer, frozen_runner
from anno1503_overhaul import packages as common
from anno1503_overhaul.food_diet import FOOD06_BGRUPPEN_SHA256
from anno1503_overhaul.profile import default_profile
from anno1503_overhaul.world_runtime_build import STOCK_SHA256


class ReadOnlyFoodClosureTests(unittest.TestCase):
    def test_native_backend_contains_only_snapshot_read_and_identity_apis(self):
        sources = launch._readiness_sources()
        self.assertEqual(set(sources), {"food_read_only.py", "native_ready.py"})
        tree = ast.parse(sources["food_read_only.py"])
        bindings = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "bind":
                bindings[node.targets[0].id] = ast.literal_eval(node.value.args[0])
        self.assertEqual(set(bindings.values()), {"CreateToolhelp32Snapshot", "CloseHandle", "Process32FirstW", "Process32NextW",
            "Module32FirstW", "Module32NextW", "OpenProcess", "QueryFullProcessImageNameW", "ReadProcessMemory", "GetProcessTimes"})
        session = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Session")
        self.assertEqual([method.name for method in session.body], ["__init__", "read"])
        initializer = session.body[0]
        opening = next(node for node in ast.walk(initializer) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open_process")
        self.assertEqual(eval(compile(ast.Expression(opening.args[0]), "<read-only mask>", "eval"), {"__builtins__": {}}), 0x1010)
        self.assertIs(ast.literal_eval(opening.args[1]), False)
        self.assertNotIn("CreateRemoteThread", sources["food_read_only.py"].decode())
        self.assertNotIn("WriteProcessMemory", sources["food_read_only.py"].decode())
        self.assertNotIn("VirtualAllocEx", sources["food_read_only.py"].decode())
        compile(sources["food_read_only.py"], "<readonly backend>", "exec")

    def test_native_ready_retains_frame_evidence_and_owned_bootstrap_identity(self):
        ready = ast.parse(launch._readiness_sources()["native_ready.py"])
        observer = next(node for node in ready.body if isinstance(node, ast.ClassDef) and node.name == "NativeReadiness")
        methods = {method.name: method for method in observer.body if isinstance(method, ast.FunctionDef)}
        self.assertIn("inspect_owned_bootstrap", methods)
        text = ast.unparse(methods["inspect"])
        for evidence in ("FRAME_EVIDENCE", "SPLASH_VTABLE", "hwnd_backlink", "_owned_bootstrap", "creation_time", "verify_modules", "World Settings is already loaded"):
            self.assertIn(evidence, text)
        dependency = next(node for node in ready.body if isinstance(node, ast.FunctionDef) and node.name == "_activation")
        self.assertEqual(ast.unparse(dependency), "def _activation(package):\n    return _FOOD_READ_ONLY_BACKEND")
        imports = [name.name for node in ast.walk(ready) if isinstance(node, ast.Import) for name in node.names]
        self.assertNotIn("activate_world_settings", imports)
        self.assertFalse(any(isinstance(node, ast.FunctionDef) and node.name == "main" for node in ready.body))

    def test_changed_preserved_observer_source_is_refused(self):
        original = common._read
        def read(root, name):
            data = original(root, name)
            return data + b"\n# unreviewed\n" if name == "legacy/launcher/native_ready.py" else data
        with patch.object(common, "_read", side_effect=read):
            with self.assertRaises(common.PackageError):
                launch._readiness_sources()


class FoodDiskProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="anno-food-launch-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source, self.copy, self.package = (self.root / name for name in ("original", "managed", "package"))
        for folder in (self.source, self.copy, self.package / "food"):
            folder.mkdir(parents=True)
        self.raw = (ROOT / "legacy/food_overhaul/food_patch.json").read_bytes()
        self.food = json.loads(self.raw)
        (self.package / "food/food_patch.json").write_bytes(self.raw)
        (self.package / "manifest.json").write_bytes(b"synthetic package manifest")
        self.view_pin = "d" * 64
        self.welt_pin = "e" * 64
        self.hashes = {self.package / "manifest.json": "a" * 64}
        names = [entry["name"] for entry in self.food["native_modules"]] + ["AnnoScene.dll", "Anno1503.exe", "Data/BGruppen.dat"]
        for folder in (self.source, self.copy):
            for name in names:
                path = folder / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"synthetic module identity fixture")
        self.record = dict(schema=1, status="installed", source_root=str(self.source), copy_root=str(self.copy),
            package_root=str(self.package), package_manifest_sha256="a" * 64,
            food_version=launch.VERSION, profile=default_profile())
        self.record["profile"]["features"].update(food_overhaul=True, world_settings=False)
        self.marker = dict(phase="installed", source_root=str(self.source))
        self.metadata = dict(kind=launch.KIND, copy_root=str(self.copy), view_sha256=self.view_pin,
                             welt_sha256=self.welt_pin)
        self.patched = []
        self.addCleanup(self.stop_patches)
        self.mock(launch, "read_copy_marker", return_value=self.marker)
        self.mock(installer, "_read_install", side_effect=lambda root: deepcopy(self.record))
        self.journal = self.mock(installer, "_verify_journal", return_value={"status": "installed"})
        self.validate = self.mock(launch, "validate_food06_package", side_effect=lambda *args: dict(self.metadata))
        self.mock(launch, "file_sha", side_effect=lambda path: self.hashes[Path(path).resolve()])
        self.set_source("vanilla")
        for entry in self.food["native_modules"]:
            pin = {"View.dll": self.view_pin, "AnnoWelt.dll": self.welt_pin}.get(entry["name"], entry["after_sha256"])
            self.hashes[self.copy / entry["name"]] = pin
        self.hashes[self.copy / "AnnoScene.dll"] = STOCK_SHA256["AnnoScene.dll"]
        self.hashes[self.copy / "Anno1503.exe"] = self.food["exe_sha256"]
        self.hashes[self.copy / "Data/BGruppen.dat"] = FOOD06_BGRUPPEN_SHA256

    def mock(self, obj, name, **kwargs):
        patcher = patch.object(obj, name, **kwargs)
        self.patched.append(patcher)
        return patcher.start()

    def stop_patches(self):
        for patcher in reversed(self.patched):
            patcher.stop()

    def set_source(self, profile):
        for entry in self.food["native_modules"]:
            self.hashes[self.source / entry["name"]] = entry["sources"]["vanilla"] if profile == "vanilla" else entry["after_sha256"]
        self.hashes[self.source / "AnnoScene.dll"] = STOCK_SHA256["AnnoScene.dll"]
        self.hashes[self.source / "Anno1503.exe"] = self.food["exe_sha256"]
        resident = self.food["files"]["Data/BGruppen.dat"]
        self.hashes[self.source / "Data/BGruppen.dat"] = resident["sources"]["vanilla"] if profile == "vanilla" else resident["after_sha256"]

    def test_exact_stock_or_food05_source_has_an_independent_food06_copy(self):
        for selected in ("vanilla", "food05"):
            with self.subTest(source=selected):
                self.set_source(selected)
                checked = launch.verify_food06_installation(self.copy)
                self.assertEqual(checked["source_profile"], selected)
                self.assertEqual(checked["source_inputs"]["source"], self.source)
                self.assertEqual(checked["copy_inputs"]["source"], self.copy)
                self.assertEqual(checked["copy_inputs"]["native_sha256"]["View.dll"], self.view_pin)
                self.assertEqual(checked["copy_inputs"]["native_sha256"]["AnnoWelt.dll"], self.welt_pin)
                self.assertEqual(checked["copy_inputs"]["private_native_sha256"], {})
        self.assertEqual(self.journal.call_count, 2)

    def test_food05_world_is_not_a_food06_copy_and_food06_world_is_not_an_original(self):
        food05_welt = next(entry["after_sha256"] for entry in self.food["native_modules"]
                           if entry["name"] == "AnnoWelt.dll")
        self.hashes[self.copy / "AnnoWelt.dll"] = food05_welt
        with self.assertRaisesRegex(launch.FoodLaunchError, "native profile.*AnnoWelt.dll"):
            launch.verify_food06_installation(self.copy)
        self.hashes[self.copy / "AnnoWelt.dll"] = self.welt_pin
        self.set_source("food05")
        self.hashes[self.source / "AnnoWelt.dll"] = self.welt_pin
        with self.assertRaisesRegex(launch.FoodLaunchError, "normal Ubisoft game"):
            launch.verify_food06_installation(self.copy)

    def test_unknown_mixed_source_native_profile_is_refused(self):
        entry = next(item for item in self.food["native_modules"] if item["name"] == "AnnoFrame.dll")
        self.hashes[self.source / "AnnoFrame.dll"] = entry["after_sha256"]
        with self.assertRaisesRegex(launch.FoodLaunchError, "native profile"):
            launch.verify_food06_installation(self.copy)

    def test_source_resident_data_cannot_disagree_with_its_native_profile(self):
        self.hashes[self.source / "Data/BGruppen.dat"] = FOOD06_BGRUPPEN_SHA256
        with self.assertRaisesRegex(launch.FoodLaunchError, "resident data"):
            launch.verify_food06_installation(self.copy)

    def test_food05_or_combined_record_is_not_a_food06_launch_selection(self):
        self.record["food_version"] = "0.5.0"
        with self.assertRaises(launch.FoodLaunchError):
            launch.verify_food06_installation(self.copy)
        self.record["food_version"] = launch.VERSION
        self.record["profile"]["features"]["world_settings"] = True
        with self.assertRaises(launch.FoodLaunchError):
            launch.verify_food06_installation(self.copy)
        self.validate.assert_not_called()
        self.journal.assert_not_called()

    def test_direct_food_startup_cannot_bypass_a_missing_bug_fixes_recipe_binding(self):
        self.record['profile']['features']['bug_fixes'] = True
        with patch.object(launch, 'verified_ubisoft_native') as native:
            with self.assertRaisesRegex(installer.InstallerError, 'Bug Fixes version binding'):
                launch.verify_food06_installation(self.copy)
        native.assert_not_called()

    def test_changed_package_binding_is_refused_before_validation_or_probe(self):
        self.hashes[self.package / "manifest.json"] = "b" * 64
        with self.assertRaisesRegex(launch.FoodLaunchError, "identity changed"):
            launch.verify_food06_installation(self.copy)
        self.validate.assert_not_called()

    def test_another_copy_package_and_changed_native_or_diet_are_refused(self):
        self.metadata["copy_root"] = str(self.source)
        with self.assertRaisesRegex(launch.FoodLaunchError, "another selected"):
            launch.verify_food06_installation(self.copy)
        self.metadata["copy_root"] = str(self.copy)
        self.hashes[self.copy / "View.dll"] = "0" * 64
        with self.assertRaisesRegex(launch.FoodLaunchError, "native profile"):
            launch.verify_food06_installation(self.copy)
        self.hashes[self.copy / "View.dll"] = self.view_pin
        self.hashes[self.copy / "Data/BGruppen.dat"] = "0" * 64
        with self.assertRaisesRegex(launch.FoodLaunchError, "tier diets"):
            launch.verify_food06_installation(self.copy)

    def retained_worker(self):
        runtime = self.root / 'retained-runtime'
        runtime.mkdir(exist_ok=True)
        worker = runtime / frozen_runner.WORKER
        worker.write_bytes(b'sealed runtime fixture')
        self.record['launcher_runtime'] = dict(runtime_root=str(runtime), worker_path=str(worker))
        return worker

    def test_frozen_food_requires_its_own_retained_runtime_then_the_full_native_profile(self):
        worker = self.retained_worker()
        with (patch.object(sys, 'frozen', True, create=True),
              patch.object(sys, 'executable', str(worker)),
              patch.object(frozen_runner, 'application_root', return_value=worker.parent),
              patch.object(frozen_runner, 'verify_retained_worker', return_value=worker) as retained,
              patch.object(frozen_runner, 'validate_package_closure', return_value={'kind':launch.KIND}) as closure):
            self.assertEqual(launch.verify_food06_installation(self.copy)['source_profile'], 'vanilla')
            retained.assert_called_once_with(self.record['launcher_runtime'])
            closure.assert_called_once_with(self.package, self.record['package_manifest_sha256'], copy_root=self.copy)
            self.validate.assert_called_once_with(self.package, self.source)
            self.hashes[self.copy / 'View.dll'] = '0' * 64
            with self.assertRaisesRegex(launch.FoodLaunchError, 'native profile'):
                launch.verify_food06_installation(self.copy)

    def test_frozen_food_refuses_missing_changed_foreign_or_wrong_profile_runtime_before_native_probe(self):
        with patch.object(sys, 'frozen', True, create=True):
            with self.assertRaisesRegex(launch.FoodLaunchError, 'no retained'):
                launch.verify_food06_installation(self.copy)
            worker = self.retained_worker()
            with patch.object(frozen_runner, 'verify_retained_worker', side_effect=frozen_runner.RunnerError('changed worker')):
                with self.assertRaisesRegex(frozen_runner.RunnerError, 'changed worker'):
                    launch.verify_food06_installation(self.copy)
            with (patch.object(frozen_runner, 'verify_retained_worker', return_value=worker),
                  patch.object(frozen_runner, 'application_root', return_value=self.source),
                  patch.object(sys, 'executable', str(worker))):
                with self.assertRaisesRegex(launch.FoodLaunchError, 'retained Windows launcher'):
                    launch.verify_food06_installation(self.copy)
            with (patch.object(frozen_runner, 'verify_retained_worker', return_value=worker),
                  patch.object(frozen_runner, 'application_root', return_value=worker.parent),
                  patch.object(sys, 'executable', str(worker)),
                  patch.object(frozen_runner, 'validate_package_closure', return_value={'kind':frozen_runner.FOOD_WORLD_PACKAGE_KIND})):
                with self.assertRaisesRegex(launch.FoodLaunchError, 'Food-only'):
                    launch.verify_food06_installation(self.copy)
        self.validate.assert_not_called()
        self.journal.assert_not_called()


class FoodHandoffTests(unittest.TestCase):
    def test_launch_uses_existing_handoff_and_closes_both_read_only_observers(self):
        checked = dict(source_root=Path("original"), copy_root=Path("managed"))
        source, copied = Mock(), Mock()
        child = SimpleNamespace(pid=1234)
        progress, event = Mock(), Mock()
        with (patch.object(launch, "_require_source_host"), patch.object(launch, "require_game_closed") as closed,
              patch.object(launch, "verify_food06_installation", return_value=checked),
              patch.object(launch, "_make_probes", return_value=(source, copied)),
              patch.object(launch, "find_registered_uri", return_value="uplay://launch/fixture/0"),
              patch.object(client_context, "start_game", return_value=child) as start):
            result = launch.launch_food06("managed", progress=progress, event=event, timeout=120)
        self.assertIs(result, child)
        closed.assert_called_once()
        start.assert_called_once_with("uplay://launch/fixture/0", Path("original"), Path("managed"), source,
            copy_probe=copied, event=event, progress=progress, timeout=120)
        source.close.assert_called_once()
        copied.close.assert_called_once()
        self.assertIn("NEW", progress.call_args.args[0])

    def test_handoff_failure_still_closes_observers_without_retry(self):
        source, copied = Mock(), Mock()
        with (patch.object(launch, "_require_source_host"), patch.object(launch, "require_game_closed"),
              patch.object(launch, "verify_food06_installation", return_value=dict(source_root=Path("original"),copy_root=Path("managed"))),
              patch.object(launch, "_make_probes", return_value=(source,copied)),
              patch.object(launch, "find_registered_uri", return_value="uplay://launch/123/0"),
              patch.object(client_context,"start_game",side_effect=RuntimeError("uncertain startup")) as start):
            with self.assertRaisesRegex(RuntimeError,"uncertain"):
                launch.launch_food06("managed")
        start.assert_called_once()
        source.close.assert_called_once()
        copied.close.assert_called_once()

    def test_existing_game_refusal_precedes_disk_or_native_preparation(self):
        with (patch.object(launch,"_require_source_host"),
              patch.object(launch,"require_game_closed",side_effect=RuntimeError("existing game")),
              patch.object(launch,"verify_food06_installation") as verify):
            with self.assertRaisesRegex(RuntimeError,"existing"):
                launch.launch_food06("managed")
        verify.assert_not_called()


if __name__ == "__main__":
    unittest.main()
