"""Closed combined06 recipe checks with explicitly synthetic native proofs.

Only native compilation/derivation boundaries are substituted. These tests do
not establish module compatibility, installation or actual game acceptance.
The public helper closure, paths, complete manifest and refusals are real.
"""
import ast
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from anno1503_overhaul import food06_package as food
from anno1503_overhaul import food_world_package as combined
from anno1503_overhaul import food_world_runtime as native
from anno1503_overhaul import packages as common, world_options_build as options
from anno1503_overhaul import filesystem
import test_world_only_package as fixtures


class FoodWorldPackageTests(unittest.TestCase):
    _payload = fixtures.WorldOnlyPackageTests._payload
    _pin = fixtures.WorldOnlyPackageTests._pin

    def setUp(self):
        fixtures.WorldOnlyPackageTests.setUp(self)
        self.view = fixtures.native() + b'fixture-food06-view'
        self.welt = fixtures.native() + b'fixture-food06-world'
        self.guarded_welt = self.welt + b'-city-statistics-guard'
        self.compiler = self.root / 'fixture-compiler'
        self.compiler.write_bytes(b'Test marker, not a compiler.')
        self.runtime_pin = common._sha(self.runtime.read_bytes())
        self.stack.enter_context(patch.object(native, 'RUNTIME_SHA256', self.runtime_pin))
        self.stack.enter_context(patch.object(native, 'ENGINE_PLAN_SHA256', common._sha(self.engine)))
        self.host = {'Anno1503.exe': self.frozen['exe_sha256'],
                     'AnnoFrame.dll': '046b5ad6f351dfe867ed38ce29fb50a594485b43a32ee90adadc48e850466baf',
                     'AnnoWelt.dll': common._sha(self.welt), 'View.dll': common._sha(self.view)}
        self.stack.enter_context(patch.object(native, 'HOST_SHA256', self.host))
        self.guarded_host = dict(self.host, **{'AnnoWelt.dll': common._sha(self.guarded_welt)})
        self.stack.enter_context(patch.object(native, 'expected_native_hashes', return_value=self.guarded_host))
        self.stack.enter_context(patch.object(native, 'GUARDED_RUNTIME_SHA256', self.runtime_pin))
        self.stack.enter_context(patch.object(native, 'GUARDED_ENGINE_PLAN_SHA256', common._sha(self.engine)))
        self.engine_builder = self.stack.enter_context(patch.object(native, 'derive_engine_plan', return_value=self.engine))
        self.stack.enter_context(patch.object(options, 'PINNED_GENERATOR', combined.generator_id()))
        self.stack.enter_context(patch.object(food, '_view_policy', return_value=common._sha(self.view)))
        self.stack.enter_context(patch.object(food, '_welt_policy',
            side_effect=lambda *, city_statistics_guard=False: common._sha(
                self.guarded_welt if city_statistics_guard else self.welt)))
        self.view_builder = self.stack.enter_context(patch.object(food, '_build_view_from_source', return_value=(self.view, {'fixture': True})))
        self.welt_builder = self.stack.enter_context(patch.object(food, '_build_welt_from_source',
            side_effect=lambda source, *, city_statistics_guard=False: (
                self.guarded_welt if city_statistics_guard else self.welt, {'fixture': True})))
        self.ai = {name: fixtures.native() + b'fixture-food06-ai-' + name.encode()
                   for name in ('CompLogic.dll', 'CompLogicClassic.dll')}
        self.stack.enter_context(patch.object(combined, '_private_ai', return_value=self.ai))

    def prepare(self, *, bug_fixes_enabled=False):
        return combined.prepare_food_world_package(self.provider, self.output, self.source, self.copy,
                                                   compiler_path=self.compiler, runtime_path=self.runtime,
                                                   bug_fixes_enabled=bug_fixes_enabled)

    def bless(self, *names):
        path = self.output / 'manifest.json'
        value = json.loads(path.read_bytes())
        for name in names:
            value['files'][name] = common._sha((self.output / name).read_bytes())
        path.write_bytes(common._encoded(value))

    def test_distinct_combined_kind_carries_both_versions_and_independent_host(self):
        self.prepare()
        value = common.validate_package(self.output, self.source)
        self.assertEqual(value['kind'], 'anno1503-food-world06-installer-package')
        self.assertEqual(value['profile'], 'food06-world')
        self.assertEqual(value['feature_versions'], {'food_overhaul': food.VERSION,
                                                    'world_settings': combined.WORLD_VERSION})
        self.assertTrue(value['food_enabled'])
        self.assertTrue(value['world_settings_supported'])
        self.assertTrue(value['new_world_required'])
        self.assertFalse(value['old_save_migration_supported'])
        self.assertFalse(value['actual_game_test_performed'])
        spec = json.loads((self.output / 'world/world_patch.json').read_bytes())
        self.assertEqual(spec['host_root'], str(self.copy))
        self.assertEqual(spec['original_game_root'], str(self.copy))
        self.assertEqual(spec['input_source_root'], str(self.source))
        self.assertEqual(spec['native_sha256'], self.host)
        self.assertNotIn('native_overlays', spec)
        self.assertEqual(len(spec['introduced_files']), 19)
        self.assertFalse(self.copy.exists())
        self.assertEqual(list(self.source.iterdir()), [])

    def test_food05_recovery_and_frozen_world_inputs_are_preserved_exactly(self):
        self.prepare()
        for relative in ('food/food_patch.json', 'world/food_patch.json'):
            self.assertEqual((self.output / relative).read_bytes(),
                             (ROOT / 'legacy/food_overhaul/food_patch.json').read_bytes())
        for name, digest in self.frozen['payloads'].items():
            self.assertEqual(common._sha((self.output / 'world/frozen-inputs' / name).read_bytes()), digest)
        self.assertEqual((self.output / 'world/native/View.food06.dll').read_bytes(), self.view)
        self.assertEqual((self.output / 'world/native/AnnoWelt.food06.dll').read_bytes(), self.welt)

    def test_ready_frame_remains_food05_and_normal_client_handoff_is_preserved(self):
        self.prepare()
        text = (self.output / 'launcher/native_ready.py').read_text()
        tree = ast.parse(text)
        constant = next(node for node in tree.body if isinstance(node, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == 'FRAME_SHA256' for t in node.targets))
        self.assertEqual(ast.literal_eval(constant.value), self.host['AnnoFrame.dll'])
        self.assertIn('inspect_owned_bootstrap', text)
        launcher = (self.output / 'launcher/launch_world_settings.pyw').read_text()
        self.assertIn('start_game(self.uri,self.normal_source', launcher)
        self.assertNotIn('os.startfile(self.uri)', launcher)
        self.assertNotIn('59a4856b2551d129', text)

    def test_manifest_cannot_bless_changed_runtime_food_native_helper_or_corpus(self):
        self.prepare()
        names = ('world/native/AnnoWorldSettings.dll', food.VIEW_PAYLOAD, food.WELT_PAYLOAD,
                 'world/world_mod.py', 'world/support/food_world_policy.py',
                 'world/frozen-inputs/native/AnnoFrame.world.dll')
        for name in names:
            with self.subTest(name=name):
                path = self.output / name
                original = path.read_bytes()
                path.write_bytes(original + b'unreviewed')
                self.bless(name)
                with self.assertRaises(common.PackageError):
                    combined.validate_food_world_package(self.output)
                path.write_bytes(original)
                self.bless(name)

    def test_manifest_and_spec_cannot_bless_changed_private_ai(self):
        self.prepare()
        payload = 'native/CompLogic.food06.dll'
        path = self.output / 'world' / payload
        path.write_bytes(path.read_bytes() + b'unreviewed')
        spec_path = self.output / 'world/world_patch.json'
        spec = json.loads(spec_path.read_bytes())
        spec['payloads'][payload] = common._sha(path.read_bytes())
        spec_path.write_bytes(common._encoded(spec))
        self.bless('world/' + payload, 'world/world_patch.json')
        with self.assertRaises(common.PackageError):
            combined.validate_food_world_package(self.output)

    def test_other_package_kinds_and_scope_cannot_masquerade_as_combined06(self):
        self.prepare()
        path = self.output / 'manifest.json'
        original = json.loads(path.read_bytes())
        for key, changed in (('kind', food.KIND), ('kind', 'anno1503-world-options-installer-package'),
                             ('profile', 'food-world'), ('food_enabled', False),
                             ('world_settings_supported', False), ('new_world_required', False),
                             ('old_save_migration_supported', True)):
            with self.subTest(key=key, changed=changed):
                value = dict(original)
                value[key] = changed
                path.write_bytes(common._encoded(value))
                with self.assertRaises(common.PackageError):
                    combined.validate_food_world_package(self.output)

    def test_unknown_native_runtime_architecture_and_engine_are_refused(self):
        wrong = fixtures.native(0x14c) + b'fixture-food06-runtime'
        self.runtime.write_bytes(wrong)
        with patch.object(native, 'RUNTIME_SHA256', common._sha(wrong)):
            with self.assertRaisesRegex(common.PackageError, 'AMD64'):
                self.prepare()
        self.assertFalse(self.output.exists())
        self.runtime.write_bytes(fixtures.native() + b'world-only-runtime')
        with patch.object(native, 'derive_engine_plan', return_value=b'unreviewed-engine-plan'):
            with self.assertRaises(common.PackageError):
                self.prepare()
        self.assertFalse(self.output.exists())

    def test_generator_and_missing_review_pin_refuse_before_publication(self):
        for changes in ({'RUNTIME_SHA256': ''}, {'ENGINE_PLAN_SHA256': ''}):
            with self.subTest(changes=changes), patch.multiple(native, **changes):
                with self.assertRaisesRegex(common.PackageError, 'build review'):
                    self.prepare()
        with patch.object(combined, 'generator_id', return_value='unreviewed-generator'):
            with self.assertRaisesRegex(common.PackageError, 'generator source changed'):
                self.prepare()
        self.view_builder.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_paths_source_binding_and_unlisted_files_are_refused(self):
        for output in (self.source / 'package', self.copy, self.provider / 'package'):
            with self.subTest(output=output), self.assertRaises(common.PackageError):
                combined.prepare_food_world_package(self.provider, output, self.source, self.copy,
                    compiler_path=self.compiler, runtime_path=self.runtime)
        self.prepare()
        with self.assertRaises(common.PackageError):
            combined.validate_food_world_package(self.output, self.copy)
        extra = self.output / 'extra.py'
        extra.write_text('pass')
        with self.assertRaises(common.PackageError):
            combined.validate_food_world_package(self.output)

    def test_optional_bug_fixes_is_explicit_and_keeps_the_unselected_recipe_independent(self):
        self.prepare()
        metadata = common.validate_package(self.output, self.source)
        spec = json.loads((self.output / 'world/world_patch.json').read_bytes())
        self.assertNotIn('bug_fixes_enabled', metadata)
        self.assertNotIn('bug_fixes', spec)
        self.assertFalse((self.output / 'world/support/_combined_bugfix_recipe.py').exists())
        self.assertEqual(list(self.source.iterdir()), [])

    def test_selected_bug_fixes_binds_the_recipe_version_and_authored_helper_closure(self):
        from anno1503_overhaul import food_world_bug_fixes
        # Asset transforms themselves have separate original-file fixtures.
        recipe = dict(version='1.2', quests=[dict(locale='Nl', path='fixture-quest')],
                      sounds=[dict(path='fixture-sound')], files=[dict(path='fixture-quest')])
        with patch.object(food_world_bug_fixes, 'recipe', return_value=recipe):
            self.prepare(bug_fixes_enabled=True)
            metadata = common.validate_package(self.output, self.source)
            self.assertTrue(metadata['bug_fixes_enabled'])
            self.assertTrue(metadata['city_statistics_guard'])
            self.assertEqual((self.output / food.WELT_PAYLOAD).read_bytes(), self.guarded_welt)
            self.assertEqual(metadata['feature_versions']['bug_fixes'], '1.2')
            spec = json.loads((self.output / 'world/world_patch.json').read_bytes())
            self.assertEqual(spec['native_sha256'], self.guarded_host)
            self.assertEqual(spec['bug_fixes'], recipe)
            support = self.output / 'world/support'
            self.assertTrue((support / '_combined_bugfix_recipe.py').is_file())
            for name in ('_combined_filesystem.py', '_combined_bug_fixes.py', '_combined_ambient_sound.py',
                         '_combined_ambient_sound_baselines.py', '_combined_bugfix_recipe.py'):
                text = (support / name).read_text()
                ast.parse(text)
                self.assertNotIn('from .', text)
            changed = json.loads(json.dumps(spec))
            changed['bug_fixes']['files'][0]['path'] = 'unreviewed-target'
            (self.output / 'world/world_patch.json').write_bytes(common._encoded(changed))
            self.bless('world/world_patch.json')
            with self.assertRaises(common.PackageError):
                common.validate_package(self.output, self.source)

    def test_selected_bug_fixes_helper_cannot_be_blessed_by_manifest_edits(self):
        from anno1503_overhaul import food_world_bug_fixes
        recipe = dict(version='1.2', quests=[], sounds=[], files=[])
        with patch.object(food_world_bug_fixes, 'recipe', return_value=recipe):
            self.prepare(bug_fixes_enabled=True)
            name = 'world/support/_combined_ambient_sound.py'
            path = self.output / name
            path.write_bytes(path.read_bytes() + b'\n# unreviewed helper\n')
            self.bless(name)
            with self.assertRaises(common.PackageError):
                common.validate_package(self.output, self.source)

    def test_bug_fixes_requires_a_real_boolean_before_native_preparation(self):
        for value in (None, 'true', 1):
            with self.subTest(value=value), self.assertRaisesRegex(common.PackageError, 'explicit Bug Fixes'):
                self.prepare(bug_fixes_enabled=value)
        self.view_builder.assert_not_called()
        self.assertFalse(self.output.exists())


class CombinedSourceProbeTests(unittest.TestCase):
    """Emitted source-reader behavior with native readiness replaced, never run."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='anno-combined-source-probe-')
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name).resolve()
        self.source, self.package = base / 'source', base / 'package'
        self.source.mkdir()
        self.package.mkdir()
        names = ('AnnoFrame.dll', 'AnnoWelt.dll', 'View.dll', 'AnnoGame.dll', 'CompLogic.dll', 'CompLogicClassic.dll')
        self.profiles = {mode: {name: (mode + ':' + name).encode() for name in names}
                         for mode in ('vanilla', 'food05')}
        self.residents = {'vanilla': b'stock resident fixture', 'food05': b'Food05 resident fixture'}
        self.extra = {'Anno1503.exe': b'exact normal client fixture',
                      'AnnoScene.dll': b'exact Scene fixture', 'AnnoDisplay.dll': b'exact Display fixture'}
        raw = dict(native_modules=[dict(name=name, sources={'vanilla': common._sha(self.profiles['vanilla'][name])},
                after_sha256=common._sha(self.profiles['food05'][name])) for name in names],
                files={'Data/BGruppen.dat': dict(sources={'vanilla': common._sha(self.residents['vanilla'])},
                                                after_sha256=common._sha(self.residents['food05']))})
        (self.package / 'food_patch.json').write_text(json.dumps(raw))
        self.spec = dict(input_source_root=str(self.source), exe_sha256=common._sha(self.extra['Anno1503.exe']),
                         native_sha256={name: common._sha(data) for name, data in self.extra.items() if name.endswith('.dll')})
        ready = ModuleType('native_ready')
        self.probe = ready.NativeReadiness = Mock(return_value=SimpleNamespace(fixture=True))
        managed = ModuleType('managed_filesystem')
        managed.checked_path, managed.safe_child = filesystem.checked_path, filesystem.safe_child
        self.namespace = {}
        with patch.dict(sys.modules, {'native_ready': ready, 'managed_filesystem': managed}):
            exec(compile(combined._source_readiness(), '<emitted source-only reader>', 'exec'), self.namespace)
        self.set_profile('vanilla')

    def set_profile(self, mode):
        for name, data in {**self.profiles[mode], **self.extra, 'Data/BGruppen.dat': self.residents[mode]}.items():
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.probe.reset_mock()

    def test_exact_stock_or_food05_native_and_resident_profiles_reach_separate_source_probe(self):
        for mode in ('vanilla', 'food05'):
            with self.subTest(mode=mode):
                self.set_profile(mode)
                source, probe = self.namespace['build_source_probe'](self.package, self.spec)
                self.assertEqual(source, self.source)
                self.assertIs(probe, self.probe.return_value)
                inputs = self.probe.call_args.args[1]
                self.assertEqual(inputs['source'], self.source)
                self.assertEqual(inputs['copy'], self.source)
                self.assertEqual(inputs['private_native_sha256'], {})
                self.assertEqual(self.probe.call_args.kwargs['frame_sha'], common._sha(self.profiles[mode]['AnnoFrame.dll']))

    def test_mixed_known_native_versions_are_refused_before_menu_observer_construction(self):
        (self.source / 'View.dll').write_bytes(self.profiles['food05']['View.dll'])
        with self.assertRaisesRegex(RuntimeError, 'one exact stock or Food 0.5'):
            self.namespace['build_source_probe'](self.package, self.spec)
        self.probe.assert_not_called()

    def test_wrong_residents_including_food06_are_refused_for_both_source_profiles(self):
        for mode in ('vanilla', 'food05'):
            for residents in (b'Food06 changed tiers', self.residents['food05' if mode == 'vanilla' else 'vanilla']):
                with self.subTest(mode=mode, residents=residents):
                    self.set_profile(mode)
                    (self.source / 'Data/BGruppen.dat').write_bytes(residents)
                    with self.assertRaisesRegex(RuntimeError, 'resident data and native source profile differ'):
                        self.namespace['build_source_probe'](self.package, self.spec)
                    self.probe.assert_not_called()

    def test_wrong_executable_scene_or_display_refuses_before_menu_observer(self):
        for name in self.extra:
            with self.subTest(name=name):
                self.set_profile('food05')
                (self.source / name).write_bytes(b'unknown source version')
                with self.assertRaises(RuntimeError):
                    self.namespace['build_source_probe'](self.package, self.spec)
                self.probe.assert_not_called()


if __name__ == '__main__':
    unittest.main()
