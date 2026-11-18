"""Stock-Food World + Bug Fixes transaction fixtures, never a game run.

The tiny source/copy and exact module-identity fixtures come from the combined
backend tests. Here no Food edit is prepared or installed: original resident
data, archives and native host bytes remain checked and unchanged.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

import test_food_world_backend as fixture


class WorldOnlyBackendTests(unittest.TestCase):
    def setUp(self):
        self.fx = fixture.FoodWorldBackendTests(methodName='runTest')
        self.fx.setUp()
        self.addCleanup(self.fx.doCleanups)
        self.tx = self.fx.tx
        self.copy, self.package = self.fx.copy, self.fx.package
        self.spec = deepcopy(self.fx.spec)
        self.spec.update(profile='world-only-0.3.0', food_enabled=False)
        for key in ('food_files', 'new_world_required', 'old_save_migration_supported'):
            self.spec.pop(key)
        for name, suffix in (('CompLogic.dll', 'AI'), ('CompLogicClassic.dll', 'classic AI')):
            target = 'WorldSettingsAI/' + name
            old = self.spec['introduced_files'][target]
            new = 'native/' + name.removesuffix('.dll') + '.world-only.dll'
            (self.package / new).write_bytes((self.package / old).read_bytes())
            self.spec['introduced_files'][target] = new
            self.spec['payloads'][new] = self.spec['payloads'].pop(old)
        stock = sys.modules['stock_baseline']
        def verify_originals(root, package):
            self.assertEqual(root, self.copy)
            for name, value in self.fx.before.items():
                self.assertEqual((root / name).read_bytes(), value)
        stock.verify_vanilla = verify_originals
        self.backend = ModuleType('_world_only_fixture')
        self.backend.__file__ = str(self.package / 'world_mod.py')
        code = (fixture.ROOT / 'src/anno1503_overhaul/world_only_backend.py').read_bytes()
        exec(compile(code, '<current stock-Food World backend>', 'exec'), self.backend.__dict__)
        self.write_spec()

    def write_spec(self):
        (self.package / 'world_patch.json').write_text(json.dumps(self.spec))

    def install(self, *, extra=()):
        state, edits = self.backend.build_edits(self.copy, self.spec, progress=lambda _: None)
        self.assertEqual(state, 'vanilla')
        self.assertEqual({edit.name for edit in edits}, set(self.fx.outputs))
        if hasattr(self.fx, 'bug_before'):
            edits.extend(self.tx.Edit(name, value, self.fx.bug_after[name], len(value))
                         for name, value in self.fx.bug_before.items())
        edits.extend(extra)
        result = self.tx.install(self.copy, edits, state)
        if hasattr(self.fx, 'bug_recipe'):
            self.record = dict(schema=1, status='installed', copy_root=str(self.copy),
                source_root=str(self.fx.source), profile=dict(features=dict(food_overhaul=False,
                    world_settings=True, bug_fixes=True)), bug_fixes_version='1.2',
                bug_fix_quests=deepcopy(self.fx.bug_recipe['quests']),
                bug_fix_sounds=deepcopy(self.fx.bug_recipe['sounds']))
            self.write_record()
        return result

    def write_record(self):
        (self.copy / self.backend.INSTALL_RECORD).write_text(json.dumps(self.record))

    def enable_bug_fixes(self):
        self.fx.enable_bug_fixes()
        self.spec['bug_fixes'] = deepcopy(self.fx.bug_recipe)
        self.write_spec()

    def test_unchecked_world_only_keeps_its_closed_introduced_inventory(self):
        journal = self.install()
        self.assertEqual(len(journal['edits']), 4)
        state, edits = self.backend.build_edits(self.copy, self.spec, progress=lambda _: None)
        self.assertEqual((state, edits), ('world-only-0.3.0', []))
        self.assertEqual(self.fx.food_calls, [])
        self.assertEqual(self.backend.verify_activation(self.copy)['native_sha256'], self.spec['native_sha256'])

    def test_world_and_bug_fixes_activate_and_restore_without_any_food_edit(self):
        self.enable_bug_fixes()
        journal = self.install()
        self.assertEqual(len(journal['edits']), 6)
        self.assertEqual(self.fx.food_calls, [])
        self.assertEqual(self.backend.verify_activation(self.copy)['native_sha256'], self.spec['native_sha256'])
        for name, value in self.fx.before.items():
            self.assertEqual((self.copy / name).read_bytes(), value)
        self.assertEqual((self.copy / 'AnnoWelt.dll').read_bytes(), self.fx.native)
        for name, value in self.fx.bug_after.items():
            self.assertEqual((self.copy / name).read_bytes(), value)
        save = self.copy / 'preserved-progress.txt'
        save.write_bytes(b'player progress')
        self.assertEqual(self.tx.restore(self.copy), 'vanilla')
        self.assertEqual(save.read_bytes(), b'player progress')
        for name, value in self.fx.bug_before.items():
            self.assertEqual((self.copy / name).read_bytes(), value)
            self.assertEqual((self.fx.source / name).read_bytes(), value)
        self.assertTrue(all(not (self.copy / name).exists() for name in self.fx.outputs))

    def test_world_bug_fixes_refuses_missing_bindings_or_a_changed_scenario(self):
        self.enable_bug_fixes()
        self.install()
        original = deepcopy(self.record)
        for key in ('bug_fixes_version', 'bug_fix_quests', 'bug_fix_sounds'):
            with self.subTest(binding=key):
                self.record = deepcopy(original)
                self.record.pop(key)
                self.write_record()
                with self.assertRaisesRegex(ValueError, 'installation binding'):
                    self.backend.verify_activation(self.copy)
        self.record = original
        self.write_record()
        (self.copy / self.fx.scene_name).write_bytes(b'changed scenario')
        with self.assertRaisesRegex(ValueError, 'King of Ore scenario changed'):
            self.backend.verify_activation(self.copy)

    def test_world_bug_fixes_refuses_changed_outputs_and_backup_originals(self):
        self.enable_bug_fixes()
        self.install()
        for name in self.fx.bug_before:
            for location in (self.copy / name, self.copy / self.tx.BACKUP / 'before' / name):
                with self.subTest(asset=name, location=location.parent.name):
                    original = location.read_bytes()
                    location.write_bytes(original + b'changed')
                    with self.assertRaises((ValueError, self.tx.TransactionError)):
                        self.backend.verify_activation(self.copy)
                    location.write_bytes(original)

    def test_world_bug_fixes_cannot_accept_unknown_journal_entries_or_hide_the_feature(self):
        self.enable_bug_fixes()
        self.install(extra=(self.tx.Edit('unexpected.txt', None, b'unreviewed'),))
        with self.assertRaisesRegex(ValueError, 'unexpected restoration journal'):
            self.backend.verify_activation(self.copy)
        self.spec.pop('bug_fixes')
        self.write_spec()
        self.record['profile']['features']['bug_fixes'] = False
        for key in ('bug_fixes_version', 'bug_fix_quests', 'bug_fix_sounds'):
            self.record.pop(key)
        self.write_record()
        with self.assertRaisesRegex(ValueError, 'unexpected restoration journal'):
            self.backend.verify_activation(self.copy)

    def test_unselected_recipe_and_foreign_helper_imports_are_refused(self):
        self.enable_bug_fixes()
        self.install()
        self.spec.pop('bug_fixes')
        self.write_spec()
        with self.assertRaisesRegex(ValueError, 'no selected Bug Fixes recipe'):
            self.backend.verify_activation(self.copy)
        self.spec['bug_fixes'] = deepcopy(self.fx.bug_recipe)
        self.write_spec()
        helper = self.fx.bug_modules['_combined_bugfix_recipe']
        foreign = self.fx.source / 'foreign.py'
        foreign.write_text('# unreviewed helper location')
        with patch.object(helper, '__file__', str(foreign)):
            with self.assertRaisesRegex(ValueError, 'Unexpected World-only Bug Fixes helper'):
                self.backend.verify_activation(self.copy)


if __name__ == '__main__':
    unittest.main()
