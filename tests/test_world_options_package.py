"""New/old runtime trust boundaries with explicit synthetic native pins."""
from pathlib import Path
import json
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from anno1503_overhaul import packages as common, world_options_package as options
from anno1503_overhaul import world_options_build as build, world_runtime_build as base
import test_world_only_package as fixtures


class OptionsPackageTests(unittest.TestCase):
    _payload = fixtures.WorldOnlyPackageTests._payload
    _pin = fixtures.WorldOnlyPackageTests._pin

    def setUp(self):
        fixtures.WorldOnlyPackageTests.setUp(self)
        hashes = {name: common._sha(value) for name, value in self.stock.items()}
        hashes['AnnoScene.dll'] = self.frozen['payloads']['native/AnnoScene.source.dll']
        hashes['Anno1503.exe'] = self.frozen['exe_sha256']
        self.stack.enter_context(patch.dict(build.PINNED_RUNTIMES,
            {'world-only': common._sha(self.runtime.read_bytes()), 'food-world': common._sha(self.runtime.read_bytes())}))
        self.stack.enter_context(patch.object(base, 'STOCK_SHA256', hashes))
        self.stack.enter_context(patch.object(base, 'WORLD_ONLY_ENGINE_PLAN_SHA256', common._sha(self.engine)))

    def prepare(self, food=False):
        return options.prepare_options_package(self.provider, self.output, self.source, self.copy,
                                               food_enabled=food, runtime_path=self.runtime)

    def test_stock_recipe_food_flag_and_expanded_decoder(self):
        path = self.prepare()
        value = options.validate_options_package(path, self.source)
        self.assertFalse(value['food_enabled'])
        self.assertEqual(value['kind'], options.KIND)
        spec = json.loads((path / 'world/world_patch.json').read_bytes())
        self.assertEqual(spec['world_options']['settings_size'], 120)
        self.assertEqual(spec['world_options']['preview_size'], 5256)
        self.assertEqual(len(spec['introduced_files']), 19)
        self.assertIn(b'SETTINGS_SIZE = 120', (path / 'world/activation/preview_snapshot.py').read_bytes())
        self.assertFalse(self.copy.exists())

    def test_food_recipe_preserves_every_other_frozen_payload(self):
        path = self.prepare(True)
        value = options.validate_options_package(path)
        self.assertTrue(value['food_enabled'])
        for name in self.frozen['payloads']:
            original = (path / 'world/frozen-inputs' / name).read_bytes()
            self.assertEqual(common._sha(original), self.frozen['payloads'][name])
            if name != 'native/AnnoWorldSettings.dll':
                self.assertEqual((path / 'world' / name).read_bytes(), original)

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
