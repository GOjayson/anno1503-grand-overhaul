"""New/old runtime trust boundaries with explicit synthetic native pins."""
from pathlib import Path
import json
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from anno1503_overhaul import packages as common, world_options_package as options
from anno1503_overhaul import world_options_build as build, world_runtime_build as base
from anno1503_overhaul import world_options_factions as factions
import test_world_only_package as fixtures


class OptionsPackageTests(unittest.TestCase):
    _payload = fixtures.WorldOnlyPackageTests._payload
    _pin = fixtures.WorldOnlyPackageTests._pin

    def setUp(self):
        fixtures.WorldOnlyPackageTests.setUp(self)
        for name in ('CompLogic.dll', 'CompLogicClassic.dll'):
            self.frozen['introduced_files']['WorldSettingsAI/' + name] = (
                'native/' + name.removesuffix('.dll') + '.food-ai.dll')
        self._pin()
        hashes = {name: common._sha(value) for name, value in self.stock.items()}
        hashes['AnnoScene.dll'] = self.frozen['payloads']['native/AnnoScene.source.dll']
        hashes['Anno1503.exe'] = self.frozen['exe_sha256']
        self.stack.enter_context(patch.dict(build.PINNED_RUNTIMES,
            {'world-only': common._sha(self.runtime.read_bytes()), 'food-world': common._sha(self.runtime.read_bytes())}))
        # This is a synthetic package/native fixture, so bind its mocked
        # runtime to the current source identity rather than a release pin.
        self.stack.enter_context(patch.object(build, 'PINNED_GENERATOR', options.generator_id()))
        self.stack.enter_context(patch.object(base, 'STOCK_SHA256', hashes))
        self.stack.enter_context(patch.object(base, 'WORLD_ONLY_ENGINE_PLAN_SHA256', common._sha(self.engine)))
        # Native instruction proofs live in dedicated tests. This recipe
        # fixture checks exact profile-specific inputs and payload propagation.
        inputs = {
            'world-only': {name: self.stock[name] + b'world-policy' for name in ('CompLogic.dll', 'CompLogicClassic.dll')},
            'food-world': {name: (self.provider / 'world_settings/native' /
                (name.removesuffix('.dll') + '.food-ai.dll')).read_bytes()
                for name in ('CompLogic.dll', 'CompLogicClassic.dll')},
        }
        self.activity_inputs = inputs
        self.stack.enter_context(patch.dict(factions.PROFILE_INPUT_SHA256,
            {profile: {name: common._sha(data) for name, data in values.items()}
             for profile, values in inputs.items()}))
        def derive(name, original, expected_sha256):
            if common._sha(original) != expected_sha256 or not any(
                    original == values[name] for values in inputs.values()):
                raise base.RuntimeBuildError('Synthetic exact activity input refused.')
            value = original + b'activity-policy-v1'
            return value, dict(input_sha256=expected_sha256, output_sha256=common._sha(value))
        self.stack.enter_context(patch.object(factions, 'derive_faction_ai', side_effect=derive))

    def prepare(self, food=False):
        return options.prepare_options_package(self.provider, self.output, self.source, self.copy,
                                               food_enabled=food, runtime_path=self.runtime)

    def test_stock_recipe_food_flag_and_expanded_decoder(self):
        path = self.prepare()
        value = options.validate_options_package(path, self.source)
        self.assertFalse(value['food_enabled'])
        self.assertEqual(value['kind'], options.KIND)
        spec = json.loads((path / 'world/world_patch.json').read_bytes())
        self.assertEqual(spec['world_options']['settings_size'], 176)
        self.assertEqual(spec['world_options']['preview_size'], 5824)
        self.assertEqual(len(spec['introduced_files']), 19)
        self.assertIn(b'SETTINGS_SIZE = 176', (path / 'world/activation/preview_snapshot.py').read_bytes())
        for name in ('CompLogic.dll', 'CompLogicClassic.dll'):
            payload = spec['introduced_files']['WorldSettingsAI/' + name]
            value = self.activity_inputs['world-only'][name] + b'activity-policy-v1'
            self.assertEqual((path / 'world' / payload).read_bytes(), value)
            self.assertEqual(spec['payloads'][payload], common._sha(value))
        self.assertFalse(self.copy.exists())

    def test_food_recipe_preserves_every_other_frozen_payload(self):
        path = self.prepare(True)
        value = options.validate_options_package(path)
        self.assertTrue(value['food_enabled'])
        for name in self.frozen['payloads']:
            original = (path / 'world/frozen-inputs' / name).read_bytes()
            self.assertEqual(common._sha(original), self.frozen['payloads'][name])
            if name not in {'native/AnnoWorldSettings.dll', 'native/CompLogic.food-ai.dll',
                            'native/CompLogicClassic.food-ai.dll'}:
                self.assertEqual((path / 'world' / name).read_bytes(), original)
        for name in ('CompLogic.dll', 'CompLogicClassic.dll'):
            payload = 'native/' + name.removesuffix('.dll') + '.food-ai.dll'
            self.assertEqual((path / 'world' / payload).read_bytes(),
                             self.activity_inputs['food-world'][name] + b'activity-policy-v1')

    def test_changed_private_ai_cannot_be_blessed_by_manifest_and_spec(self):
        parent = self.output.parent
        for food in (False, True):
            for filename in ('CompLogic.dll', 'CompLogicClassic.dll'):
                with self.subTest(food=food, filename=filename):
                    self.output = parent / ('tamper-' + str(food) + '-' + filename)
                    path = self.prepare(food)
                    spec_path = path / 'world/world_patch.json'
                    spec = json.loads(spec_path.read_bytes())
                    payload = spec['introduced_files']['WorldSettingsAI/' + filename]
                    changed = path / 'world' / payload
                    changed.write_bytes(changed.read_bytes() + b'unreviewed')
                    spec['payloads'][payload] = common._sha(changed.read_bytes())
                    spec_path.write_bytes(common._encoded(spec))
                    config_path = path / 'launcher/launcher_config.json'
                    config = json.loads(config_path.read_bytes())
                    config['package_spec_sha256'] = common._sha(spec_path.read_bytes())
                    config_path.write_bytes(common._encoded(config))
                    manifest = json.loads((path / 'manifest.json').read_bytes())
                    for name in ('world/' + payload, 'world/world_patch.json', 'launcher/launcher_config.json'):
                        manifest['files'][name] = common._sha((path / name).read_bytes())
                    (path / 'manifest.json').write_bytes(common._encoded(manifest))
                    with self.assertRaises(common.PackageError):
                        options.validate_options_package(path)

    def test_profile_cannot_accept_the_other_profiles_ai_input(self):
        hashes = dict(factions.PROFILE_INPUT_SHA256['food-world'])
        with patch.dict(factions.PROFILE_INPUT_SHA256, {'world-only': hashes}):
            with self.assertRaisesRegex(common.PackageError, 'private faction AI input'):
                self.prepare()

    def test_manifest_cannot_bless_runtime_or_helper_changes(self):
        self.prepare()
        path = self.output / 'world/native/AnnoWorldSettings.dll'
        path.write_bytes(fixtures.native() + b'unknown-runtime')
        manifest = json.loads((self.output / 'manifest.json').read_bytes())
        manifest['files']['world/native/AnnoWorldSettings.dll'] = common._sha(path.read_bytes())
        (self.output / 'manifest.json').write_bytes(common._encoded(manifest))
        with self.assertRaises(common.PackageError):
            options.validate_options_package(self.output)

    def test_original_frozen_runtime_cannot_masquerade_as_new(self):
        self.runtime.write_bytes((self.provider / 'world_settings/native/AnnoWorldSettings.dll').read_bytes())
        with self.assertRaises(common.PackageError):
            self.prepare()

    def test_selection_path_and_extra_file_refusal(self):
        self.prepare()
        with self.assertRaises(common.PackageError):
            options.validate_options_package(self.output, self.copy)
        (self.output / 'world/untrusted.py').write_text('raise RuntimeError("not a provider")')
        with self.assertRaises(common.PackageError):
            options.validate_options_package(self.output)

    def test_changed_generator_cannot_be_blessed_by_old_runtime_pin(self):
        self.prepare()
        with patch.object(options, 'generator_id', return_value='ws6-unreviewed'):
            with self.assertRaisesRegex(common.PackageError, 'generator source changed'):
                options.validate_options_package(self.output)


if __name__ == '__main__':
    unittest.main()
