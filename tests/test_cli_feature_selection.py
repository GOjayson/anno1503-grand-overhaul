"""Explicit CLI feature modes reach the production API with exact flags.

Most installer calls are mocked. Package-version refusal also reaches the real
checker with temporary directory fixtures. No installed game or process is used.
"""
from contextlib import redirect_stdout,redirect_stderr
from copy import deepcopy
from pathlib import Path
import io
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from anno1503_overhaul import __main__ as cli,installer,packages,vanilla
from anno1503_overhaul.profile import default_profile


class ExplicitCLIFeatures(unittest.TestCase):
    def mode(self,flag,expected,food_version=installer.FOOD05_VERSION):
        for action,api in (('check-install','check_install'),('install','install')):
            for initial in ((False,False),(True,True),(True,False),(False,True)):
                profile=deepcopy(default_profile())
                profile['features'].update(food_overhaul=initial[0],world_settings=initial[1])
                with (self.subTest(action=action,flag=flag,initial=initial),
                      patch.object(cli,'default_profile',return_value=profile),
                      patch.object(installer,api,return_value=dict(ok=True))as invoke,
                      redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO())):
                    result=cli.main([action,'--source','source-game','--copy','managed-copy',flag])
                self.assertEqual(result,0);invoke.assert_called_once()
                self.assertEqual(invoke.call_args.args[:2],(Path('source-game'),Path('managed-copy')))
                actual=invoke.call_args.args[2]['features']
                self.assertEqual((actual['food_overhaul'],actual['world_settings']),expected)
                if expected[0]:
                    self.assertEqual(invoke.call_args.kwargs['food_version'],food_version)
                else:
                    self.assertNotIn('food_version',invoke.call_args.kwargs)
                self.assertEqual({k:v for k,v in actual.items()if k not in ('food_overhaul','world_settings')},
                                 {k:v for k,v in default_profile()['features'].items()if k not in ('food_overhaul','world_settings')})

    def test_food_only_explicitly_enables_food_and_disables_world_for_both_commands(self):
        self.mode('--food-only',(True,False))

    def test_world_only_explicitly_enables_world_and_disables_food_for_both_commands(self):
        self.mode('--world-only',(False,True))

    def test_food06_world_selects_the_distinct_combined_mode_for_both_commands(self):
        self.mode('--food06-world',(True,True),installer.FOOD06_VERSION)

    def test_food06_world_preserves_additive_flag_for_installer_validation(self):
        for action,api in (('check-install','check_install'),('install','install')):
            with (self.subTest(action=action),patch.object(installer,api,return_value={})as invoke,
                  redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO())):
                result=cli.main([action,'--source','source-game','--copy','managed-copy',
                                 '--food06-world','--bug-fixes'])
            self.assertEqual(result,0)
            chosen=invoke.call_args.args[2]['features']
            self.assertEqual({k for k,v in chosen.items()if v},{'food_overhaul','world_settings','bug_fixes'})
            self.assertEqual(invoke.call_args.kwargs['food_version'],installer.FOOD06_VERSION)

    def test_combined_mode_cannot_be_confused_with_other_explicit_modes(self):
        for other in (['--food06'],['--food-only'],['--world-only'],['--profile','chosen.json']):
            with (self.subTest(other=other),redirect_stderr(io.StringIO()),
                  patch.object(installer,'check_install')as check):
                with self.assertRaises(SystemExit)as refusal:
                    cli.main(['check-install','--source','source-game','--copy','managed-copy',
                              '--food06-world',*other])
            self.assertEqual(refusal.exception.code,2)
            check.assert_not_called()

    def test_bug_fixes_only_selects_only_bug_fixes_for_both_commands(self):
        for action, api in (('check-install', 'check_install'), ('install', 'install')):
            chosen = default_profile()
            chosen['features'].update(food_overhaul=True, world_settings=True)
            with (self.subTest(action=action),
                  patch.object(cli, 'default_profile', return_value=chosen),
                  patch.object(installer, api, return_value={}) as invoke,
                  redirect_stdout(io.StringIO())):
                result = cli.main([action, '--source', 'source-game', '--copy', 'managed-copy',
                                   '--bug-fixes-only'])
            self.assertEqual(result, 0)
            invoke.assert_called_once()
            features = invoke.call_args.args[2]['features']
            self.assertEqual({key for key, enabled in features.items() if enabled}, {'bug_fixes'})
            self.assertNotIn('food_version', invoke.call_args.kwargs)

    def test_additive_bug_fixes_preserves_the_food_or_world_mode(self):
        cases = (('--world-only', 'world_settings', None),
                 ('--food-only', 'food_overhaul', installer.FOOD05_VERSION),
                 ('--food06', 'food_overhaul', installer.FOOD06_VERSION))
        for mode, module, food_version in cases:
            with (self.subTest(mode=mode),
                  patch.object(installer, 'check_install', return_value={}) as invoke,
                  redirect_stdout(io.StringIO())):
                result = cli.main(['check-install', '--source', 'source-game', '--copy', 'managed-copy',
                                   mode, '--bug-fixes'])
            self.assertEqual(result, 0)
            invoke.assert_called_once()
            features = invoke.call_args.args[2]['features']
            self.assertEqual({key for key, enabled in features.items() if enabled}, {module, 'bug_fixes'})
            self.assertEqual(invoke.call_args.kwargs.get('food_version'), food_version)

    def test_saved_profile_is_preserved_without_explicit_mode(self):
        chosen=default_profile();chosen['features'].update(food_overhaul=True,world_settings=True,bug_fixes=True)
        with (patch.object(cli,'load_profile',return_value=deepcopy(chosen))as load,
              patch.object(cli,'default_profile')as defaults,
              patch.object(installer,'check_install',return_value={})as invoke,
              redirect_stdout(io.StringIO())):
            self.assertEqual(cli.main(['check-install','--source','source-game','--copy','managed-copy',
                                       '--profile','chosen.json']),0)
        load.assert_called_once_with(Path('chosen.json'));defaults.assert_not_called()
        self.assertEqual(invoke.call_args.args[2],chosen)
        self.assertEqual(invoke.call_args.kwargs['food_version'],installer.FOOD05_VERSION)

    def test_saved_food_profiles_pin_food05_for_both_commands_with_existing_package(self):
        for action,api in (('check-install','check_install'),('install','install')):
            for world in (False,True):
                chosen=default_profile();chosen['features'].update(food_overhaul=True,world_settings=world)
                with (self.subTest(action=action,world=world),
                      patch.object(cli,'load_profile',return_value=deepcopy(chosen)),
                      patch.object(installer,api,return_value={})as invoke,
                      redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO())):
                    self.assertEqual(cli.main([action,'--source','source-game','--copy','managed-copy',
                        '--profile','chosen.json','--package','existing-package']),0)
                self.assertEqual(invoke.call_args.args[2],chosen)
                self.assertEqual(invoke.call_args.kwargs['food_version'],installer.FOOD05_VERSION)

    def test_food_disabled_saved_profile_does_not_request_a_food_version(self):
        chosen=default_profile();chosen['features'].update(food_overhaul=False,world_settings=True)
        with (patch.object(cli,'load_profile',return_value=chosen),
              patch.object(installer,'check_install',return_value={})as invoke,
              redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO())):
            self.assertEqual(cli.main(['check-install','--source','source-game','--copy','managed-copy',
                                      '--profile','world-only.json']),0)
        self.assertNotIn('food_version',invoke.call_args.kwargs)

    def test_explicit_food05_modes_reject_a_food06_package_before_recovery_or_install(self):
        with tempfile.TemporaryDirectory(prefix='anno-cli-food-version-')as folder:
            base=Path(folder).resolve();source=base/'original';source.mkdir()
            (source/'Anno1503.exe').write_bytes(b'Synthetic checker fixture, not a game.')
            copied=base/'managed';prepared=base/'prepared';prepared.mkdir()
            metadata=dict(kind=installer.FOOD06_PACKAGE_KIND,copy_root=str(copied))
            chosen=default_profile();chosen['features'].update(food_overhaul=True,world_settings=False)
            for mode in (['--food-only'],['--profile','chosen.json']):
                with (self.subTest(mode=mode),patch.object(cli,'load_profile',return_value=deepcopy(chosen)),
                      patch.object(packages,'validate_package',return_value=metadata),
                      patch.object(vanilla,'plan_vanilla_recovery',return_value=[])as recovery,
                      redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO())as errors):
                    result=cli.main(['check-install','--source',str(source),'--copy',str(copied),
                                     '--package',str(prepared),*mode])
                self.assertEqual(result,2)
                self.assertIn('different Food version',errors.getvalue())
                recovery.assert_not_called()
                self.assertFalse(copied.exists())
                self.assertEqual(list(source.iterdir()),[source/'Anno1503.exe'])


if __name__=='__main__':unittest.main()
