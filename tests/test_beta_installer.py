"""Public setup routing keeps private development inputs an explicit choice."""
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from anno1503_overhaul import beta_package, installer
from anno1503_overhaul.profile import default_profile


class BetaInstaller(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='anno-beta-installer-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'source'
        self.source.mkdir()
        self.target = self.root / 'copy'
        self.package = self.root / 'prepared'
        self.package.mkdir()
        (self.package / 'manifest.json').write_text('{}')
        self.profile = default_profile()

    def patch(self, *args, **kwargs):
        context = mock.patch(*args, **kwargs)
        value = context.start()
        self.addCleanup(context.stop)
        return value

    def prepared_boundaries(self, food=False, bug_fixes=False):
        self.patch('anno1503_overhaul.installer.validate_roots', return_value=(self.source, self.target))
        self.patch('anno1503_overhaul.beta_paths.package_workspace', return_value=self.root)
        self.patch('anno1503_overhaul.beta_paths.compiler_path', return_value=self.root / 'zig.exe')
        self.patch('anno1503_overhaul.packages.validate_package', return_value={
            'verified': True, 'kind': beta_package.KIND, 'copy_root': str(self.target), 'food_enabled': food,
            **({'bug_fixes_enabled': True} if bug_fixes else {})})
        self.patch('anno1503_overhaul.vanilla.plan_vanilla_recovery', return_value=[])
        self.patch('anno1503_overhaul.installer.game_inventory', return_value=[])

    def bug_fix_boundaries(self):
        self.profile['features']['bug_fixes'] = True
        self.patch('anno1503_overhaul.bug_fixes.king_of_ore_assets', return_value=(SimpleNamespace(locale='Nl'),))
        self.patch('anno1503_overhaul.packages.king_of_ore_fingerprints', return_value=[dict(locale='Nl')])
        self.patch('anno1503_overhaul.ambient_sound.ambient_sound_assets', return_value=())

    def test_default_world_only_prepares_public_inputs_without_private_baseline(self):
        self.prepared_boundaries()
        public = self.patch('anno1503_overhaul.beta_package.prepare_beta_package', return_value=self.package)
        legacy = self.patch('anno1503_overhaul.world_options_package.prepare_options_package')
        plan = installer.check_install(self.source, self.target, self.profile)
        self.assertEqual(public.call_count, 1)
        self.assertEqual(public.call_args.args[1:], (self.source, self.target))
        self.assertEqual(public.call_args.kwargs, {'compiler_path': self.root / 'zig.exe'})
        legacy.assert_not_called()
        self.assertFalse(plan['profile']['features']['food_overhaul'])
        self.assertFalse(plan['game_files_changed'])

    def test_explicit_development_provider_retains_existing_reviewed_route(self):
        self.prepared_boundaries()
        legacy = self.patch('anno1503_overhaul.world_options_package.prepare_options_package', return_value=self.package)
        public = self.patch('anno1503_overhaul.beta_package.prepare_beta_package')
        self.patch('anno1503_overhaul.installer._workspace', return_value=self.root)
        provider = self.root / 'preserved-development-inputs'
        installer.check_install(self.source, self.target, self.profile, baseline_dir=provider)
        self.assertEqual(legacy.call_args.args[0], provider)
        self.assertFalse(legacy.call_args.kwargs['food_enabled'])
        public.assert_not_called()

    def test_world_and_bug_fixes_selects_the_bound_public_package_without_food(self):
        self.prepared_boundaries(bug_fixes=True)
        self.bug_fix_boundaries()
        public = self.patch('anno1503_overhaul.beta_package.prepare_beta_package', return_value=self.package)
        plan = installer.check_install(self.source, self.target, self.profile)
        self.assertIs(public.call_args.kwargs['bug_fixes_enabled'], True)
        self.assertFalse(plan['profile']['features']['food_overhaul'])
        self.assertTrue(plan['profile']['features']['world_settings'])
        self.assertTrue(plan['profile']['features']['bug_fixes'])
        self.assertEqual(plan['bug_fixes_version'], '1.2')
        self.assertFalse(self.target.exists())

    def test_world_and_bug_fixes_forwards_the_flag_to_advanced_stock_options(self):
        self.prepared_boundaries(bug_fixes=True)
        self.bug_fix_boundaries()
        legacy = self.patch('anno1503_overhaul.world_options_package.prepare_options_package', return_value=self.package)
        self.patch('anno1503_overhaul.installer._workspace', return_value=self.root)
        installer.check_install(self.source, self.target, self.profile, baseline_dir=self.root / 'provider')
        self.assertFalse(legacy.call_args.kwargs['food_enabled'])
        self.assertIs(legacy.call_args.kwargs['bug_fixes_enabled'], True)

    def test_world_package_cannot_drop_the_selected_bug_fixes_recipe(self):
        self.prepared_boundaries()
        self.bug_fix_boundaries()
        self.patch('anno1503_overhaul.beta_package.prepare_beta_package', return_value=self.package)
        with self.assertRaisesRegex(installer.InstallerError, 'different Bug Fixes selection'):
            installer.check_install(self.source, self.target, self.profile)
        self.assertFalse(self.target.exists())

    def test_combined_choice_requires_explicit_development_inputs_without_changing_selection(self):
        self.prepared_boundaries()
        public = self.patch('anno1503_overhaul.beta_package.prepare_beta_package')
        self.profile['features']['food_overhaul'] = True
        with self.assertRaisesRegex(installer.InstallerError, 'combined Food'):
            installer.check_install(self.source, self.target, self.profile)
        self.assertTrue(self.profile['features']['food_overhaul'])
        public.assert_not_called()
        self.assertFalse(self.target.exists())

    def test_public_package_cannot_silently_enable_food(self):
        self.prepared_boundaries(food=True)
        self.patch('anno1503_overhaul.beta_package.prepare_beta_package', return_value=self.package)
        with self.assertRaisesRegex(installer.InstallerError, 'different Food selection'):
            installer.check_install(self.source, self.target, self.profile)
        self.assertFalse(self.target.exists())


if __name__ == '__main__':
    unittest.main()
