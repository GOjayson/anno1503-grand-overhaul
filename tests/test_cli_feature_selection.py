"""Explicit CLI feature modes reach the production API with exact flags.

Installer calls are mocked; no game, package, installation or process is used.
"""
from contextlib import redirect_stdout,redirect_stderr
from copy import deepcopy
from pathlib import Path
import io
import sys
import unittest
from unittest.mock import patch

sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from anno1503_overhaul import __main__ as cli,installer
from anno1503_overhaul.profile import default_profile


class ExplicitCLIFeatures(unittest.TestCase):
    def mode(self,flag,expected):
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
                self.assertEqual({k:v for k,v in actual.items()if k not in ('food_overhaul','world_settings')},
                                 {k:v for k,v in default_profile()['features'].items()if k not in ('food_overhaul','world_settings')})

    def test_food_only_explicitly_enables_food_and_disables_world_for_both_commands(self):
        self.mode('--food-only',(True,False))

    def test_world_only_explicitly_enables_world_and_disables_food_for_both_commands(self):
        self.mode('--world-only',(False,True))

    def test_saved_profile_is_preserved_without_explicit_mode(self):
        chosen=default_profile();chosen['features'].update(food_overhaul=True,world_settings=True)
        with (patch.object(cli,'load_profile',return_value=deepcopy(chosen))as load,
              patch.object(cli,'default_profile')as defaults,
              patch.object(installer,'check_install',return_value={})as invoke,
              redirect_stdout(io.StringIO())):
            self.assertEqual(cli.main(['check-install','--source','source-game','--copy','managed-copy',
                                       '--profile','chosen.json']),0)
        load.assert_called_once_with(Path('chosen.json'));defaults.assert_not_called()
        self.assertEqual(invoke.call_args.args[2],chosen)


if __name__=='__main__':unittest.main()
