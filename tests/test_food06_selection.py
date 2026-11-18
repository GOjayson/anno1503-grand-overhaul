"""Explicit Food-version routing and restoration with isolated file fixtures.

Game compatibility/compiler probes are substituted here. The source profile,
copy transaction, installed version record and restoration boundary are real;
no installed game or running process is used.
"""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from anno1503_overhaul import __main__ as cli, beta_paths, food06_package, food_launch
from anno1503_overhaul import installer, packages, selector, vanilla, world_options_package, frozen_runner
from anno1503_overhaul.profile import default_profile


FOOD_FIXTURE = '''from types import SimpleNamespace
def build_edits(root, spec, progress=print):
    before = (root / "Sample.dat").read_bytes()
    if before != b"original fixture":
        raise RuntimeError("Fixture is not the original baseline")
    return "vanilla", [SimpleNamespace(name="Sample.dat", before=before,
        after=b"food06 fixture", file_size=len(before), offset=None)]
'''


def profile(*, food=True, world=False):
    value = default_profile()
    value["features"].update(food_overhaul=food, world_settings=world)
    return value


class VisibleFoodChoiceTests(unittest.TestCase):
    def test_food06_supports_explicit_food_only_or_combined_selection(self):
        for world in (False, True):
            self.assertEqual(selector.food_version_for_selection(profile(world=world)["features"], selector.FOOD06_CHOICE),
                             installer.FOOD06_VERSION)

    def test_preserved_version_remains_available_for_both_supported_selections(self):
        for world in (False, True):
            self.assertEqual(selector.food_version_for_selection(profile(world=world)["features"], selector.FOOD05_CHOICE),
                             installer.FOOD05_VERSION)

    def test_combined06_keeps_bug_fixes_as_an_independent_enabled_choice(self):
        selected = profile(world=True)
        selected['features']['bug_fixes'] = True
        self.assertEqual(selector.food_version_for_selection(selected['features'], selector.FOOD06_CHOICE),
                         installer.FOOD06_VERSION)
        self.assertTrue(selected['features']['bug_fixes'])

    def test_preserved_food05_world_profile_explains_the_bug_fixes_boundary(self):
        selected = profile(world=True)
        selected['features']['bug_fixes'] = True
        with self.assertRaisesRegex(installer.InstallerError, 'Preserved Food 0.5'):
            selector.food_version_for_selection(selected['features'], selector.FOOD05_CHOICE)

    def test_disabled_food_ignores_its_version_but_enabled_food_requires_a_choice(self):
        self.assertIsNone(selector.food_version_for_selection(profile(food=False, world=True)["features"], selector.FOOD06_CHOICE))
        with self.assertRaisesRegex(installer.InstallerError, "Choose"):
            selector.food_version_for_selection(profile()["features"], "")


class Food06InstallerSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="anno-food06-selection-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "original"
        self.source.mkdir()
        (self.source / "Anno1503.exe").write_bytes(b"synthetic fixture executable")
        (self.source / "Sample.dat").write_bytes(b"original fixture")
        self.copy = self.root / "managed"
        self.prepared = self.root / "prepared"
        (self.prepared / "food").mkdir(parents=True)
        (self.prepared / "world").mkdir()
        (self.prepared / "food/food_mod.py").write_text(FOOD_FIXTURE)
        (self.prepared / "food/food_patch.json").write_text("{}")
        (self.prepared / "manifest.json").write_text("{}")
        (self.prepared / "world/world_patch.json").write_text(json.dumps({"source_baselines":{}, "unchanged_native":{},
            "exe_sha256": installer.file_sha(self.source / "Anno1503.exe")}))
        world_fixture = '''from pathlib import Path
import json

def resolve_copy(spec, root, package=None):
    root = Path(root).resolve(strict=True)
    marker = json.loads((root / '.anno1503-worldsettings-test-copy.json').read_bytes())
    if Path(marker['copy_root']).resolve() != root:
        raise RuntimeError('Synthetic World fixture belongs to another copy')
    return root

'''
        (self.prepared / "world/world_mod.py").write_text(world_fixture + FOOD_FIXTURE.replace("food06 fixture", "combined06 fixture"))
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        (self.root / "repo").mkdir()
        self.mock(installer, "REPO", self.root / "repo")
        self.mock(installer, "_workspace", return_value=self.workspace)
        self.mock(installer, "require_game_closed")
        self.mock(beta_paths, "package_workspace", return_value=self.workspace)
        self.constructor06 = self.mock(food06_package, "prepare_food06_package", return_value=self.prepared)
        self.constructor05 = self.mock(packages, "prepare_food_package", return_value=self.prepared)
        self.constructor_world = self.mock(world_options_package, "prepare_options_package", return_value=self.prepared)
        # The separate package owns native compilation tests. This fixture
        # substitutes only its preparation boundary while exercising routing.
        combined_module = ModuleType("anno1503_overhaul.food_world_package")
        combined_module.prepare_food_world_package = unittest.mock.Mock(return_value=self.prepared)
        module_patch = patch.dict(sys.modules, {combined_module.__name__: combined_module})
        module_patch.start()
        self.addCleanup(module_patch.stop)
        self.constructor_world06 = combined_module.prepare_food_world_package
        public_module = ModuleType('anno1503_overhaul.food_world_public')
        public_module.prepare_public_food_world_package = unittest.mock.Mock(return_value=self.prepared)
        public_patch = patch.dict(sys.modules, {public_module.__name__: public_module})
        public_patch.start()
        self.addCleanup(public_patch.stop)
        self.constructor_public_world06 = public_module.prepare_public_food_world_package
        self.compiler = self.mock(beta_paths, 'compiler_path', return_value=self.root / 'compiler')
        self.metadata = dict(kind=installer.FOOD06_PACKAGE_KIND, verified=True, copy_root=str(self.copy),
                             feature_versions={"food_overhaul":installer.FOOD06_VERSION},
                             new_world_required=True, old_save_migration_supported=False, world_settings_supported=False)
        self.validator = self.mock(packages, "validate_package", side_effect=lambda *args, **kwargs: dict(self.metadata))
        self.recovery = self.mock(vanilla, "plan_vanilla_recovery", return_value=[])
        self.mock(vanilla, "apply_vanilla_recovery", side_effect=lambda *args, **kwargs: None)
        self.mock(vanilla, "verify_vanilla", side_effect=self.verify_fixture)

    def mock(self, obj, name, *args, **kwargs):
        patcher = patch.object(obj, name, *args, **kwargs)
        value = patcher.start()
        self.addCleanup(patcher.stop)
        return value

    def verify_fixture(self, root, package):
        if (Path(root) / "Sample.dat").read_bytes() != b"original fixture":
            raise vanilla.VanillaError("Fixture not restored")

    def test_explicit_food06_prepares_only_its_separate_recipe(self):
        result = installer.check_install(self.source, self.copy, profile(), food_version=installer.FOOD06_VERSION)
        self.constructor06.assert_called_once()
        self.constructor05.assert_not_called()
        self.constructor_world.assert_not_called()
        self.assertEqual(result["food_version"], installer.FOOD06_VERSION)
        self.assertTrue(result["new_world_required"])
        self.assertFalse(result["old_save_migration_supported"])
        self.assertFalse(result["world_settings_supported"])
        self.assertFalse(self.copy.exists())
        self.assertEqual((self.source / "Sample.dat").read_bytes(), b"original fixture")

    def test_old_api_without_version_still_prepares_preserved_food05(self):
        self.metadata["kind"] = "anno1503-food-installer-package"
        result = installer.check_install(self.source, self.copy, profile())
        self.constructor05.assert_called_once()
        self.constructor06.assert_not_called()
        self.assertEqual(result["food_version"], installer.FOOD05_VERSION)

    def test_explicit_food06_combined_selection_uses_its_new_package_and_independent_host(self):
        self.metadata.update(kind=installer.PUBLIC_FOOD_WORLD06_PACKAGE_KIND, food_enabled=True, world_settings_supported=True)
        with patch.object(installer.adapter, "prepare_edits") as legacy_source_check:
            plan = installer.check_install(self.source, self.copy, profile(world=True), food_version=installer.FOOD06_VERSION)
        self.constructor_public_world06.assert_called_once()
        self.assertEqual(self.constructor_public_world06.call_args.args[1:], (self.source, self.copy))
        self.assertEqual(self.constructor_public_world06.call_args.kwargs, {'compiler_path': self.root / 'compiler'})
        self.constructor_world06.assert_not_called()
        self.constructor06.assert_not_called()
        self.constructor05.assert_not_called()
        self.constructor_world.assert_not_called()
        legacy_source_check.assert_not_called()
        self.assertEqual(plan["food_version"], installer.FOOD06_VERSION)
        self.assertTrue(plan["world_settings_supported"])
        self.assertTrue(plan["new_world_required"])
        self.assertFalse(plan["old_save_migration_supported"])
        self.assertFalse(self.copy.exists())

    def test_explicit_food06_combined_keeps_the_selected_development_input_folder(self):
        self.metadata.update(kind=installer.FOOD_WORLD06_PACKAGE_KIND, food_enabled=True, world_settings_supported=True)
        provider = self.root / "preserved provider"
        installer.check_install(self.source, self.copy, profile(world=True), baseline_dir=provider,
                                food_version=installer.FOOD06_VERSION)
        self.assertEqual(self.constructor_world06.call_args.args[0], provider)

    def test_frozen_combined_uses_public_original_game_recipe_and_explicit_optional_bug_fixes(self):
        selected = profile(world=True)
        self.metadata.update(kind=installer.PUBLIC_FOOD_WORLD06_PACKAGE_KIND, food_enabled=True,
                             world_settings_supported=True)
        with patch.object(sys, 'frozen', True, create=True):
            installer.check_install(self.source, self.copy, selected, food_version=installer.FOOD06_VERSION)
        self.constructor_public_world06.assert_called_once()
        self.assertEqual(self.constructor_public_world06.call_args.kwargs, {'compiler_path':self.root / 'compiler'})
        self.constructor_world06.assert_not_called()
        self.assertFalse(self.copy.exists())

    def test_frozen_food05_and_private_combined_profiles_refuse_without_changing_the_copy(self):
        with patch.object(sys, 'frozen', True, create=True):
            with self.assertRaisesRegex(installer.InstallerError, 'preserved source'):
                installer.check_install(self.source, self.copy, profile(), food_version=installer.FOOD05_VERSION)
            self.metadata.update(kind=installer.FOOD_WORLD06_PACKAGE_KIND, food_enabled=True)
            with self.assertRaisesRegex(installer.InstallerError, 'public World Settings'):
                installer.check_install(self.source, self.copy, profile(world=True), package=self.prepared,
                                        food_version=installer.FOOD06_VERSION)
            with self.assertRaisesRegex(installer.InstallerError, 'Clear Advanced'):
                installer.check_install(self.source, self.copy, profile(world=True),
                    baseline_dir=self.root / 'preserved', food_version=installer.FOOD06_VERSION)
        self.constructor_world06.assert_not_called()
        self.constructor_public_world06.assert_not_called()
        self.assertFalse(self.copy.exists())

    def test_combined06_package_cannot_silently_enable_bug_fixes(self):
        self.metadata.update(kind=installer.FOOD_WORLD06_PACKAGE_KIND, food_enabled=True,
                             world_settings_supported=True, bug_fixes_enabled=True)
        with self.assertRaisesRegex(installer.InstallerError, "different Bug Fixes selection"):
            installer.check_install(self.source, self.copy, profile(world=True), package=self.prepared,
                                    food_version=installer.FOOD06_VERSION)
        self.constructor_world06.assert_not_called()
        self.assertFalse(self.copy.exists())

    def test_preserved_food05_world_and_bug_fixes_refuse_before_any_preparation(self):
        selected = profile(world=True)
        selected['features']['bug_fixes'] = True
        with self.assertRaisesRegex(installer.InstallerError, 'Preserved Food 0.5'):
            installer.check_install(self.source, self.copy, selected,
                                    food_version=installer.FOOD05_VERSION)
        self.constructor_world.assert_not_called()
        self.validator.assert_not_called()
        self.assertFalse(self.copy.exists())

    def test_food06_package_is_rejected_by_world_and_combined_routes(self):
        for food in (False, True):
            with self.subTest(food=food), self.assertRaisesRegex(installer.InstallerError, "Food-only"):
                installer.check_install(self.source, self.copy, profile(food=food, world=True), package=self.prepared)
        self.recovery.assert_not_called()

    def test_explicit_versions_cannot_silently_accept_each_others_package(self):
        with self.assertRaisesRegex(installer.InstallerError, "different Food version"):
            installer.check_install(self.source, self.copy, profile(), package=self.prepared,
                                     food_version=installer.FOOD05_VERSION)
        self.metadata["kind"] = "anno1503-food-installer-package"
        with self.assertRaisesRegex(installer.InstallerError, "different Food version"):
            installer.check_install(self.source, self.copy, profile(), package=self.prepared,
                                     food_version=installer.FOOD06_VERSION)
        self.recovery.assert_not_called()

    def test_food06_combined_package_cannot_be_selected_as_food_only_or_world_only(self):
        self.metadata.update(kind=installer.FOOD_WORLD06_PACKAGE_KIND, food_enabled=True, world_settings_supported=True)
        for selected, version in ((profile(), installer.FOOD06_VERSION), (profile(food=False, world=True), None)):
            with self.subTest(selected=selected), self.assertRaisesRegex(installer.InstallerError, "requires both features"):
                installer.check_install(self.source, self.copy, selected, package=self.prepared, food_version=version)
        self.recovery.assert_not_called()

    def test_unversioned_food_selection_keeps_food05_and_refuses_both_food06_package_kinds(self):
        for kind, world in ((installer.FOOD06_PACKAGE_KIND, False), (installer.FOOD_WORLD06_PACKAGE_KIND, True)):
            self.metadata.update(kind=kind, food_enabled=True, world_settings_supported=world)
            with self.subTest(kind=kind), self.assertRaisesRegex(installer.InstallerError, "different Food version"):
                installer.check_install(self.source, self.copy, profile(world=world), package=self.prepared)
        self.recovery.assert_not_called()

    def test_preserved_combined_profile_keeps_its_food05_startup_proof(self):
        self.metadata.update(kind="anno1503-world-options-installer-package", food_enabled=True)
        with patch.object(installer.adapter, "prepare_edits", return_value={"state":"combined-0.5.0", "edits":[]}) as proof:
            result = installer.check_install(self.source, self.copy, profile(world=True),
                baseline_dir=self.root / "preserved provider", food_version=installer.FOOD05_VERSION)
        self.constructor_world.assert_called_once()
        self.assertTrue(self.constructor_world.call_args.kwargs["food_enabled"])
        self.constructor06.assert_not_called()
        proof.assert_called_once()
        self.assertEqual(result["food_version"], installer.FOOD05_VERSION)

    def test_food_version_needs_food_selection_and_known_version(self):
        for value, chosen in ((installer.FOOD06_VERSION, profile(food=False, world=True)), ("0.7-unreviewed", profile())):
            with self.subTest(value=value), self.assertRaises(installer.InstallerError):
                installer.check_install(self.source, self.copy, chosen, food_version=value)
        self.validator.assert_not_called()

    def test_food06_install_records_version_and_restores_original_fixture(self):
        result = installer.install(self.source, self.copy, profile(), package=self.prepared,
                                    food_version=installer.FOOD06_VERSION)
        self.assertEqual(result["food_version"], installer.FOOD06_VERSION)
        self.assertTrue(result["new_world_required"])
        self.assertEqual((self.copy / "Sample.dat").read_bytes(), b"food06 fixture")
        (self.copy / "preserved-save.txt").write_text("player progress")
        restored = installer.restore(self.copy)
        self.assertTrue(restored["restored"])
        self.assertEqual((self.copy / "Sample.dat").read_bytes(), b"original fixture")
        self.assertEqual((self.source / "Sample.dat").read_bytes(), b"original fixture")
        self.assertEqual((self.copy / "preserved-save.txt").read_text(), "player progress")
        self.assertTrue((self.copy / "GrandOverhaul_Backup_v1").is_dir())

    def test_combined06_install_and_restore_preserve_new_world_scope_and_original_files(self):
        self.metadata.update(kind=installer.FOOD_WORLD06_PACKAGE_KIND, food_enabled=True, world_settings_supported=True)
        result = installer.install(self.source, self.copy, profile(world=True), package=self.prepared,
                                    food_version=installer.FOOD06_VERSION)
        self.assertTrue(result["world_settings_supported"])
        self.assertTrue(result["new_world_required"])
        self.assertFalse(result["old_save_migration_supported"])
        self.assertEqual(result["food_version"], installer.FOOD06_VERSION)
        self.assertEqual((self.copy / "Sample.dat").read_bytes(), b"combined06 fixture")
        (self.copy / "preserved-save.txt").write_text("player progress")
        installer.restore(self.copy)
        self.assertEqual((self.copy / "Sample.dat").read_bytes(), b"original fixture")
        self.assertEqual((self.source / "Sample.dat").read_bytes(), b"original fixture")
        self.assertEqual((self.copy / "preserved-save.txt").read_text(), "player progress")

    def test_frozen_food_only_install_retains_its_sealed_launcher_and_restores_without_removing_it(self):
        runtime = self.root / 'runtime'
        runtime.mkdir()
        (runtime / frozen_runner.WORKER).write_bytes(b'retained worker fixture')
        (runtime / frozen_runner.LAUNCHER).write_bytes(b'retained GUI fixture')
        retained = dict(kind=frozen_runner.RUNTIME_KIND, runtime_root=str(self.root / 'runtime'),
                        worker_path=str(self.root / 'runtime' / frozen_runner.WORKER),
                        launcher_path=str(self.root / 'runtime' / frozen_runner.LAUNCHER))
        with (patch.object(sys, 'frozen', True, create=True),
              patch.object(frozen_runner, 'application_root', return_value=self.root / 'release'),
              patch.object(frozen_runner, 'retain_worker', return_value=retained) as retain,
              patch.object(frozen_runner, 'source_script', return_value=ROOT / 'src/anno1503_overhaul/legacy_worker.py'),
              patch.object(beta_paths, 'application_data', return_value=self.root / 'appdata')):
            record = installer.install(self.source, self.copy, profile(), package=self.prepared,
                                       food_version=installer.FOOD06_VERSION)
            self.assertEqual(record['launcher_runtime'], retained)
            retain.assert_called_once_with(self.root / 'release', self.root / 'appdata/Launchers')
            (self.copy / 'preserved-save.txt').write_text('player progress')
            installer.restore(self.copy)
        self.assertEqual((self.copy / 'Sample.dat').read_bytes(), b'original fixture')
        self.assertEqual((self.copy / 'preserved-save.txt').read_text(), 'player progress')
        self.assertEqual((self.source / 'Sample.dat').read_bytes(), b'original fixture')
        self.assertEqual((runtime / frozen_runner.WORKER).read_bytes(), b'retained worker fixture')
        self.assertEqual((runtime / frozen_runner.LAUNCHER).read_bytes(), b'retained GUI fixture')


class Food06CLITests(unittest.TestCase):
    def test_food06_mode_overrides_default_flags_and_reaches_both_production_apis(self):
        for action, api in (("check-install", "check_install"), ("install", "install")):
            initial = profile(food=False, world=True)
            with (self.subTest(action=action), patch.object(cli, "default_profile", return_value=deepcopy(initial)),
                  patch.object(installer, api, return_value={}) as invoke,
                  redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO())):
                result = cli.main([action,"--source","original","--copy","managed","--food06"])
            self.assertEqual(result, 0)
            self.assertTrue(invoke.call_args.args[2]["features"]["food_overhaul"])
            self.assertFalse(invoke.call_args.args[2]["features"]["world_settings"])
            self.assertEqual(invoke.call_args.kwargs["food_version"], installer.FOOD06_VERSION)

    def test_food06_world_mode_selects_both_features_and_explicit_version_for_both_apis(self):
        for action, api in (("check-install", "check_install"), ("install", "install")):
            with (self.subTest(action=action), patch.object(installer, api, return_value={}) as invoke,
                  redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO())):
                result = cli.main([action, "--source", "original", "--copy", "managed", "--food06-world"])
            self.assertEqual(result, 0)
            self.assertTrue(invoke.call_args.args[2]["features"]["food_overhaul"])
            self.assertTrue(invoke.call_args.args[2]["features"]["world_settings"])
            self.assertEqual(invoke.call_args.kwargs["food_version"], installer.FOOD06_VERSION)

    def test_food06_world_mode_can_add_bug_fixes_without_losing_any_selection(self):
        for action, api in (("check-install", "check_install"), ("install", "install")):
            with (self.subTest(action=action), patch.object(installer, api, return_value={}) as invoke,
                  redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO())):
                result = cli.main([action, "--source", "original", "--copy", "managed",
                                   "--food06-world", "--bug-fixes"])
            self.assertEqual(result, 0)
            self.assertTrue(all(invoke.call_args.args[2]["features"][feature]
                                for feature in ("food_overhaul", "world_settings", "bug_fixes")))
            self.assertEqual(invoke.call_args.kwargs["food_version"], installer.FOOD06_VERSION)

    def test_preparation_tool_food06_flag_calls_new_builder_with_explicit_compiler(self):
        spec = importlib.util.spec_from_file_location("_food06_preparation_tool", ROOT / "tools/prepare_installer_package.py")
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        arguments = ["prepare_installer_package.py","--food06","--source-game","original", "--copy-game","managed",
                     "--output","prepared","--compiler","reviewed-zig"]
        result = dict(files={"fixture": "hash"}, kind=food06_package.KIND, new_world_required=True)
        for flag, options in (([], {}), (["--bug-fixes"], {"city_statistics_guard": True})):
            with (self.subTest(flag=flag), patch.object(sys,"argv",arguments + flag),
                  patch.object(food06_package,"prepare_food06_package",return_value=Path("prepared")) as build,
                  patch.object(tool,"validate_package",return_value=result), redirect_stdout(io.StringIO())):
                self.assertEqual(tool.main(),0)
                build.assert_called_once_with(Path("prepared"),Path("original"),Path("managed"),
                                              compiler_path=Path("reviewed-zig"), **options)

    def test_preparation_tool_binds_all_three_features_in_the_combined_package(self):
        spec = importlib.util.spec_from_file_location("_all_mods_preparation_tool", ROOT / "tools/prepare_installer_package.py")
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        arguments = ["prepare_installer_package.py", "--food06-world", "--bug-fixes",
                     "--baselines", "reviewed-inputs", "--source-game", "original", "--copy-game", "managed",
                     "--output", "prepared", "--compiler", "reviewed-zig"]
        builder = ModuleType('anno1503_overhaul.food_world_package')
        builder.prepare_food_world_package = unittest.mock.Mock(return_value=Path('prepared'))
        result = dict(files={"fixture": "hash"}, kind=installer.FOOD_WORLD06_PACKAGE_KIND,
                      new_world_required=True, bug_fixes_enabled=True)
        output = io.StringIO()
        with (patch.dict(sys.modules, {builder.__name__: builder}), patch.object(sys, "argv", arguments),
              patch.object(tool, "validate_package", return_value=result), redirect_stdout(output)):
            self.assertEqual(tool.main(), 0)
        builder.prepare_food_world_package.assert_called_once_with(
            Path('reviewed-inputs'), Path('prepared'), Path('original'), Path('managed'),
            compiler_path=Path('reviewed-zig'), bug_fixes_enabled=True)
        self.assertIs(json.loads(output.getvalue())['bug_fixes_enabled'], True)

    def test_preparation_tool_rejects_an_ignored_bug_fixes_flag_for_other_profiles(self):
        spec = importlib.util.spec_from_file_location("_all_mods_preparation_tool_error", ROOT / "tools/prepare_installer_package.py")
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        for chosen in ('--food-only', '--bug-fixes-only'):
            with (self.subTest(chosen=chosen),
                  patch.object(sys, 'argv', ['prepare_installer_package.py', chosen, '--bug-fixes',
                               '--source-game', 'original', '--copy-game', 'managed', '--output', 'prepared']),
                  redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error):
                tool.main()
            self.assertEqual(error.exception.code, 2)

    def test_preparation_tool_binds_world_and_bug_fixes_with_food_disabled(self):
        spec = importlib.util.spec_from_file_location("_world_bugfix_preparation_tool", ROOT / "tools/prepare_installer_package.py")
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        arguments = ['prepare_installer_package.py', '--world-only', '--bug-fixes',
                     '--baselines', 'reviewed-inputs', '--source-game', 'original', '--copy-game', 'managed',
                     '--output', 'prepared']
        result = dict(files={'fixture': 'hash'}, kind=world_options_package.KIND, bug_fixes_enabled=True)
        with (patch.object(sys, 'argv', arguments), patch.object(world_options_package,
              'prepare_options_package', return_value=Path('prepared')) as build,
              patch.object(tool, 'validate_package', return_value=result), redirect_stdout(io.StringIO())):
            self.assertEqual(tool.main(), 0)
        build.assert_called_once_with(Path('reviewed-inputs'), Path('prepared'), Path('original'), Path('managed'),
                                      food_enabled=False, bug_fixes_enabled=True)

    def test_generic_launch_command_dispatches_the_installed_selection(self):
        with (patch.object(installer, "launch_installed_game", return_value=SimpleNamespace(pid=123)) as start,
              redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO())):
            self.assertEqual(cli.main(["launch", "--copy", "managed"]), 0)
        self.assertEqual(start.call_args.args, (Path("managed"),))
        self.assertTrue(callable(start.call_args.kwargs["progress"]))


class InstalledStartupDispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="anno-installed-start-")
        self.addCleanup(self.temp.cleanup)
        self.copy = Path(self.temp.name).resolve()
        self.record = dict(status="installed", profile=profile(), food_version=installer.FOOD06_VERSION)
        self.marker = dict(phase="installed")
        self.patchers = []
        self.addCleanup(self.stop_patches)
        self.mock(installer, "read_copy_marker", side_effect=lambda root: dict(self.marker))
        self.mock(installer, "_read_install", side_effect=lambda root: deepcopy(self.record))
        self.journal = self.mock(installer, "_verify_journal", return_value={"status":"installed"})
        self.world = self.mock(installer, "launch_world_settings", return_value=SimpleNamespace(pid=12))
        self.food = self.mock(food_launch, "launch_food06", return_value=SimpleNamespace(pid=34))

    def mock(self, obj, name, **kwargs):
        patcher = patch.object(obj, name, **kwargs)
        self.patchers.append(patcher)
        return patcher.start()

    def stop_patches(self):
        for patcher in reversed(self.patchers):
            patcher.stop()

    def test_food06_uses_its_installed_record_and_read_only_launch_api(self):
        progress = lambda message: None
        child = installer.launch_installed_game(self.copy, progress=progress)
        self.assertEqual(child.pid, 34)
        self.journal.assert_called_once_with(self.copy)
        self.food.assert_called_once_with(self.copy, progress=progress)
        self.world.assert_not_called()

    def test_retained_or_frozen_food_dispatches_through_its_version_owned_launcher(self):
        for frozen, retained in ((False, {'kind':'retained fixture'}), (True, None)):
            self.record['launcher_runtime'] = retained
            with (self.subTest(frozen=frozen), patch.object(sys, 'frozen', frozen, create=True),
                  patch.object(installer, 'launch_retained_food06', return_value=SimpleNamespace(pid=56)) as launch):
                self.assertEqual(installer.launch_installed_game(self.copy).pid, 56)
                launch.assert_called_once_with(self.copy)
        self.food.assert_not_called();self.world.assert_not_called()

    def test_retained_food_launch_checks_worker_and_package_before_windowless_spawn(self):
        retained = {'launcher_path':str(self.copy / frozen_runner.LAUNCHER)}
        Path(retained['launcher_path']).write_bytes(b'GUI fixture')
        worker = self.copy / frozen_runner.WORKER
        worker.write_bytes(b'worker fixture')
        self.record.update(launcher_runtime=retained, package_root=str(self.copy), package_manifest_sha256='a'*64)
        with (patch.object(installer, 'require_game_closed'),
              patch.object(frozen_runner, 'verify_retained_worker', return_value=worker) as verify,
              patch.object(frozen_runner, 'validate_package_closure', return_value={'kind':installer.FOOD06_PACKAGE_KIND}) as closure,
              patch.object(installer.subprocess, 'Popen', return_value=SimpleNamespace(pid=56)) as spawn):
            self.assertEqual(installer.launch_retained_food06(self.copy).pid, 56)
            verify.assert_called_once_with(retained)
            closure.assert_called_once_with(self.copy, 'a'*64, copy_root=self.copy)
            spawn.assert_called_once_with([retained['launcher_path'], '--launch-food06', '--copy', str(self.copy)],
                cwd=worker.parent, creationflags=getattr(installer.subprocess,'CREATE_NO_WINDOW',0))
            closure.return_value = {'kind':installer.PUBLIC_FOOD_WORLD06_PACKAGE_KIND}
            spawn.reset_mock()
            with self.assertRaisesRegex(installer.InstallerError, 'Food-only'):
                installer.launch_retained_food06(self.copy)
            spawn.assert_not_called()
            verify.side_effect = frozen_runner.RunnerError('changed retained runtime')
            with self.assertRaisesRegex(frozen_runner.RunnerError, 'changed retained'):
                installer.launch_retained_food06(self.copy)
            spawn.assert_not_called()

    def test_frozen_food_without_retained_launcher_refuses_before_spawning(self):
        with (patch.object(installer, 'require_game_closed'),
              patch.object(frozen_runner, 'verify_retained_worker') as verify,
              patch.object(installer.subprocess, 'Popen') as spawn):
            with self.assertRaisesRegex(installer.InstallerError, 'no retained Windows launcher'):
                installer.launch_retained_food06(self.copy)
        verify.assert_not_called();spawn.assert_not_called()

    def test_world_and_preserved_combined_installations_keep_the_existing_route(self):
        for with_food in (False, True):
            with self.subTest(food=with_food):
                self.record.update(profile=profile(food=with_food,world=True),food_version=installer.FOOD05_VERSION)
                self.world.reset_mock()
                self.assertEqual(installer.launch_installed_game(self.copy).pid, 12)
                self.world.assert_called_once_with(self.copy)
                self.food.assert_not_called()

    def test_combined06_has_an_explicit_installed_route_and_uses_world_activation(self):
        self.record.update(profile=profile(world=True), food_version=installer.FOOD06_VERSION)
        self.assertEqual(installer.installed_launch_kind(self.record), "food06-world")
        self.assertEqual(installer.launch_installed_game(self.copy).pid, 12)
        self.world.assert_called_once_with(self.copy)
        self.food.assert_not_called()

    def test_preserved_food05_has_clear_guidance_without_attempting_a_launch(self):
        for version in (None, installer.FOOD05_VERSION):
            with self.subTest(version=version):
                self.record["food_version"] = version
                with self.assertRaisesRegex(installer.InstallerError, "known-working Food 0.5"):
                    installer.launch_installed_game(self.copy)
        self.world.assert_not_called()
        self.food.assert_not_called()
        self.journal.assert_not_called()

    def test_restored_or_malformed_installation_has_no_startup_route(self):
        cases = [None, {}, dict(status="restored",profile=profile(),food_version=installer.FOOD06_VERSION),
                 dict(status="installed",profile=None),
                 dict(status="installed",profile=profile(),food_version="0.7-unreviewed")]
        for record in cases:
            with self.subTest(record=record):
                self.assertIsNone(installer.installed_launch_kind(record))
                self.record = record
                with self.assertRaises(installer.InstallerError):
                    installer.launch_installed_game(self.copy)
        self.food.assert_not_called()
        self.world.assert_not_called()

    def test_changed_restoration_journal_stops_both_launchers(self):
        self.journal.side_effect = installer.InstallerError("changed installed preimage")
        with self.assertRaisesRegex(installer.InstallerError, "changed"):
            installer.launch_installed_game(self.copy)
        self.food.assert_not_called()
        self.world.assert_not_called()

    def test_copy_marker_must_still_describe_an_installed_copy(self):
        self.marker["phase"] = "restored"
        with self.assertRaises(installer.InstallerError):
            installer.launch_installed_game(self.copy)
        self.food.assert_not_called()
        self.world.assert_not_called()
        self.journal.assert_not_called()


if __name__ == "__main__":
    unittest.main()
