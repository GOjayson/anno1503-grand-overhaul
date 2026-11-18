"""Combined06 preparation/activation and one-journal restore file fixtures.

Two tiny Food targets stand in for the separately pinned21-file native/data
closure. Real transaction, paths and restoration are used. No Anno process,
native module execution, installed game or gameplay claim is involved.
"""
from contextlib import ExitStack
from copy import deepcopy
import json
from pathlib import Path
import struct
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from anno1503_overhaul import ambient_sound, bug_fixes, legacy_adapter, vanilla
from anno1503_overhaul import food_world_package, packages
from anno1503_overhaul import food_world_policy as policy


def pe(marker=b'fixture'):
    data = bytearray(256)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 60, 128)
    data[128:132] = b'PE\0\0'
    struct.pack_into('<H', data, 132, 0x8664)
    struct.pack_into('<H', data, 152, 0x20b)
    return bytes(data) + marker


class FoodWorldBackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='anno-food-world-backend-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source, self.copy, self.package = (self.root / n for n in ('original', 'managed', 'package'))
        for folder in (self.source, self.copy, self.package):
            folder.mkdir()
        self.tx = legacy_adapter._transactions()
        self.before = {'Data/BGruppen.dat': b'original residents', 'Anlagen.dat': b'abcOLDdef'}
        self.after = {'Data/BGruppen.dat': b'reviewed Food06 residents', 'Anlagen.dat': b'abcNEWdef'}
        self.food_policy = {name: dict(before_size=len(value), before_sha256=self.tx.sha(value),
            after_size=len(self.after[name]), after_sha256=self.tx.sha(self.after[name]),
            offset=3 if name == 'Anlagen.dat' else None) for name, value in self.before.items()}
        self.native = pe(b'checked native host')
        self.exe = pe(b'checked executable')
        for folder in (self.source, self.copy):
            for name, value in self.before.items():
                p = folder / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(value)
            (folder / 'Anno1503.exe').write_bytes(self.exe)
            (folder / 'AnnoWelt.dll').write_bytes(self.native)
        self.managed = dict(schema=1, managed_copy=True, copy_root=str(self.copy),
                            source_root=str(self.source), source_exe_sha256=self.tx.sha(self.exe))
        self.world_marker = dict(schema=1, development_copy=True, copy_root=str(self.copy),
                                 source_root=str(self.source), source_exe_sha256=self.tx.sha(self.exe))
        (self.copy / '.anno1503-grand-overhaul-copy.json').write_text(json.dumps(self.managed))
        (self.copy / '.anno1503-worldsettings-test-copy.json').write_text(json.dumps(self.world_marker))
        self.outputs = {'AnnoWorldSettings.dll': pe(b'runtime'),
                        'WorldSettingsAI/CompLogic.dll': pe(b'AI'),
                        'WorldSettingsAI/CompLogicClassic.dll': pe(b'classic AI'),
                        'WorldSettingsIslands/fixture.scp': b'synthetic island payload'}
        self.introduced = dict(zip(self.outputs,
            ('native/AnnoWorldSettings.dll', 'native/CompLogic.food06.dll',
             'native/CompLogicClassic.food06.dll', 'assets/fixture.scp')))
        for name, payload in self.introduced.items():
            p = self.package / payload
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(self.outputs[name])
        self.spec = dict(profile=policy.PROFILE, food_enabled=True,
            food_files=deepcopy(self.food_policy), new_world_required=True,
            old_save_migration_supported=False, host_root=str(self.copy), input_source_root=str(self.source),
            exe_sha256=self.tx.sha(self.exe), native_sha256={'AnnoWelt.dll': self.tx.sha(self.native)},
            introduced_files=self.introduced,
            payloads={payload: self.tx.sha(self.outputs[name]) for name, payload in self.introduced.items()})
        (self.package / 'world_patch.json').write_text(json.dumps(self.spec))
        (self.package / 'food_patch.json').write_text('{"fixture":true}')
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        food = ModuleType('food_mod')
        food.__file__ = str(self.package / 'food_mod.py')
        self.food_calls = []
        def build_food(root, spec, progress):
            self.food_calls.append((root, spec))
            return 'vanilla', self.food_edits()
        food.build_edits = build_food
        stock = ModuleType('stock_baseline')
        stock._root = vanilla._root
        aliases = ModuleType('package_alias_assets')
        aliases.introduced_files = lambda: {'WorldSettingsIslands/fixture.scp': 'assets/fixture.scp'}
        aliases.data_payload_hashes = lambda: {'assets/fixture.scp': self.tx.sha(self.outputs['WorldSettingsIslands/fixture.scp'])}
        aliases.validate_data_payload = lambda name, data: self.assertEqual(data, self.outputs['WorldSettingsIslands/fixture.scp'])
        islands = ModuleType('package_world_assets')
        islands.introduced_files = lambda: {}
        islands.data_payload_hashes = lambda: {}
        islands.validate_data_payload = lambda *args: None
        islands.validate_required_copy = lambda root: self.assertEqual(root, self.copy)
        self.stack.enter_context(patch.object(policy, 'FOOD_FILES', self.food_policy))
        self.stack.enter_context(patch.dict(sys.modules, {'food_mod': food, 'world_transactions': self.tx,
            'stock_baseline': stock, 'package_alias_assets': aliases, 'package_world_assets': islands,
            'food_world_policy': policy}))
        self.backend = ModuleType('_food_world_fixture')
        self.backend.__file__ = str(self.package / 'world_mod.py')
        raw = (ROOT / 'src/anno1503_overhaul/food_world_backend.py').read_bytes()
        exec(compile(raw, '<current combined backend>', 'exec'), self.backend.__dict__)

    def food_edits(self):
        return [self.tx.Edit('Data/BGruppen.dat', self.before['Data/BGruppen.dat'], self.after['Data/BGruppen.dat'],
                             len(self.before['Data/BGruppen.dat'])),
                self.tx.Edit('Anlagen.dat', b'OLD', b'NEW', len(self.before['Anlagen.dat']), 3)]

    def install(self):
        state, edits = self.backend.build_edits(self.copy, self.spec, progress=lambda _: None)
        self.assertEqual(state, 'vanilla')
        return self.tx.install(self.copy, edits, state)

    def enable_bug_fixes(self):
        """Synthetic exact recipe; real asset transforms have separate tests."""
        self.bug_before = {'Languages/Nl/Scenes/0200Single/Singleplayer14.htm': b'original quest',
                           'Languages/Nl/Samples/fixture.wav': b'original sound'}
        self.bug_after = {name: value + b' reviewed change' for name, value in self.bug_before.items()}
        self.scene_name = 'Languages/Nl/Scenes/0200Single/Single_14.sze'
        for folder in (self.source, self.copy):
            for name, value in {**self.bug_before, self.scene_name: b'unchanged scenario'}.items():
                path = folder / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(value)
        names = list(self.bug_before)
        fingerprints = lambda name: dict(path=name, before_sha256=self.tx.sha(self.bug_before[name]),
                                         after_sha256=self.tx.sha(self.bug_after[name]))
        self.bug_recipe = dict(version='1.2', quests=[dict(fingerprints(names[0]), locale='Nl',
            scene_path=self.scene_name, scene_sha256=self.tx.sha(b'unchanged scenario'))],
            sounds=[fingerprints(names[1])], files=[dict(fingerprints(name),
                before_size=len(self.bug_before[name]), after_size=len(self.bug_after[name]), offset=None)
                for name in names])
        self.spec['bug_fixes'] = deepcopy(self.bug_recipe)
        (self.package / 'world_patch.json').write_text(json.dumps(self.spec))
        (self.package / 'support').mkdir()
        modules = {}
        for name in ('_combined_filesystem', '_combined_ambient_sound_baselines', '_combined_bug_fixes',
                     '_combined_ambient_sound', '_combined_bugfix_recipe'):
            path = self.package / 'support' / (name + '.py')
            path.write_text('# Synthetic recipe fixture')
            module = ModuleType(name)
            module.__file__ = str(path)
            modules[name] = module
        def recipe(source):
            self.assertEqual(source, self.source)
            return deepcopy(self.bug_recipe)
        modules['_combined_bugfix_recipe'].recipe = recipe
        self.bug_modules = modules
        self.stack.enter_context(patch.dict(sys.modules, modules))

    def install_all_features(self):
        state, edits = self.backend.build_edits(self.copy, self.spec, progress=lambda _: None)
        self.assertEqual(state, 'vanilla')
        self.assertEqual(len(edits), 6)  # The shared installer appends Bug Fixes.
        edits.extend(self.tx.Edit(name, value, self.bug_after[name], len(value))
                     for name, value in self.bug_before.items())
        journal = self.tx.install(self.copy, edits, state)
        self.installation = dict(schema=1, status='installed', copy_root=str(self.copy),
            source_root=str(self.source), profile=dict(features=dict(food_overhaul=True,
                world_settings=True, bug_fixes=True)), bug_fixes_version='1.2',
            bug_fix_quests=deepcopy(self.bug_recipe['quests']),
            bug_fix_sounds=deepcopy(self.bug_recipe['sounds']))
        self.write_installation()
        return journal

    def write_installation(self):
        (self.copy / self.backend.INSTALL_RECORD).write_text(json.dumps(self.installation))

    def test_one_composed_transaction_is_restorable_and_preserves_source_and_saves(self):
        state, edits = self.backend.build_edits(self.copy, self.spec, progress=lambda _: None)
        self.assertEqual(state, 'vanilla')
        self.assertEqual({e.name for e in edits}, set(self.before) | set(self.outputs))
        self.assertEqual(len(edits), 6)
        self.assertEqual(len(self.food_calls), 1)
        self.assertEqual((self.copy / 'Anlagen.dat').read_bytes(), self.before['Anlagen.dat'])
        self.tx.install(self.copy, edits, state)
        state, again = self.backend.build_edits(self.copy, self.spec, progress=lambda _: None)
        self.assertEqual(state, policy.PROFILE)
        self.assertEqual(again, [])
        self.assertEqual(len(self.food_calls), 1)
        checked = self.backend.verify_activation(self.copy)
        self.assertEqual(checked['source'], self.copy)
        self.assertEqual(checked['copy'], self.copy)
        self.assertEqual(checked['native_sha256'], self.spec['native_sha256'])
        self.assertEqual(set(checked['private_native_sha256']), {'WorldSettingsAI/CompLogic.dll', 'WorldSettingsAI/CompLogicClassic.dll'})
        save = self.copy / 'preserved-save.sav'
        save.write_bytes(b'Synthetic progress fixture, not a native save')
        self.assertEqual(self.tx.restore(self.copy), 'vanilla')
        for name, value in self.before.items():
            self.assertEqual((self.source / name).read_bytes(), value)
            self.assertEqual((self.copy / name).read_bytes(), value)
        self.assertTrue(save.is_file())
        self.assertTrue((self.copy / self.tx.BACKUP).is_dir())
        self.assertTrue(all(not (self.copy / name).exists() for name in self.outputs))

    def test_profile_scope_or_other_copy_and_source_bindings_are_refused(self):
        for key, value in (('profile', 'food-world'), ('food_enabled', False),
                           ('new_world_required', False), ('old_save_migration_supported', True),
                           ('host_root', str(self.source)), ('input_source_root', str(self.copy))):
            with self.subTest(key=key):
                changed = deepcopy(self.spec)
                changed[key] = value
                with self.assertRaises((ValueError, RuntimeError)):
                    self.backend.resolve_copy(changed, self.copy)
        changed = deepcopy(self.spec)
        changed['food_files']['Data/BGruppen.dat']['after_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            self.backend.resolve_copy(changed, self.copy)

    def test_unknown_original_food_file_refuses_before_building_or_writing(self):
        path = self.copy / 'Data/BGruppen.dat'
        path.write_bytes(b'unknown resident definitions')
        with self.assertRaisesRegex(ValueError, 'exact original file'):
            self.backend.build_edits(self.copy, self.spec)
        self.assertEqual(self.food_calls, [])
        self.assertEqual(path.read_bytes(), b'unknown resident definitions')
        self.assertFalse((self.copy / self.tx.BACKUP).exists())

    def test_food_preparation_cannot_change_inventory_offset_or_final_file_hash(self):
        mutations = [self.food_edits()[:-1], self.food_edits() + [self.food_edits()[0]],
            [self.food_edits()[0], self.tx.Edit('Anlagen.dat', b'OLD', b'NEW', 9, 4)],
            [self.tx.Edit('Data/BGruppen.dat', self.before['Data/BGruppen.dat'], b'wrong', len(self.before['Data/BGruppen.dat'])), self.food_edits()[1]]]
        for values in mutations:
            with self.subTest(values=values), patch.object(self.backend.food, 'build_edits', return_value=('vanilla', values)):
                with self.assertRaises(ValueError):
                    self.backend.build_edits(self.copy, self.spec)
        self.assertFalse((self.copy / self.tx.BACKUP).exists())

    def test_changed_payload_or_unknown_introduced_target_is_preserved_and_refused(self):
        payload = self.package / 'native/AnnoWorldSettings.dll'
        original = payload.read_bytes()
        payload.write_bytes(original + b'changed')
        with self.assertRaisesRegex(ValueError, 'payload changed'):
            self.backend.build_edits(self.copy, self.spec)
        payload.write_bytes(original)
        target = self.copy / 'AnnoWorldSettings.dll'
        target.write_bytes(b'Existing unknown file')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.backend.build_edits(self.copy, self.spec)
        self.assertEqual(target.read_bytes(), b'Existing unknown file')

    def test_changed_native_host_after_installation_blocks_activation(self):
        self.install()
        (self.copy / 'AnnoWelt.dll').write_bytes(pe(b'unknown native version'))
        with self.assertRaisesRegex(ValueError, 'native host module changed'):
            self.backend.verify_activation(self.copy)

    def test_unknown_unchanged_native_input_is_refused_before_food_preparation(self):
        path = self.copy / 'AnnoWelt.dll'
        path.write_bytes(pe(b'unknown incoming host'))
        with self.assertRaisesRegex(ValueError, 'unchanged combined native host module differs'):
            self.backend.build_edits(self.copy, self.spec)
        self.assertEqual(self.food_calls, [])
        self.assertFalse((self.copy / self.tx.BACKUP).exists())

    def test_missing_and_changed_restoration_preimages_block_direct_activation(self):
        self.install()
        path = self.copy / self.tx.BACKUP / 'before/Data/BGruppen.dat'
        original = path.read_bytes()
        path.unlink()
        with self.assertRaises((ValueError, RuntimeError)):
            self.backend.verify_activation(self.copy)
        path.write_bytes(original + b'changed')
        with self.assertRaises((ValueError, RuntimeError)):
            self.backend.verify_activation(self.copy)

    def test_hardlinked_native_host_is_refused_without_modifying_it(self):
        self.install()
        original = self.copy / 'AnnoWelt.dll'
        linked = self.root / 'shared-native.dll'
        try:
            import os
            os.link(original, linked)
        except OSError:
            self.skipTest('Hard links are unavailable in this fixture filesystem')
        with self.assertRaisesRegex(ValueError, 'share writable native files'):
            self.backend.verify_activation(self.copy)
        self.assertEqual(original.read_bytes(), self.native)

    def test_all_features_verify_and_restore_one_exact_journal(self):
        self.enable_bug_fixes()
        self.install_all_features()
        checked = self.backend.verify_activation(self.copy)
        self.assertEqual(checked['native_sha256'], self.spec['native_sha256'])
        self.assertEqual(len(self.tx.read_manifest(self.copy)['edits']), 8)
        self.assertEqual(self.tx.restore(self.copy), 'vanilla')
        for name, original in {**self.before, **self.bug_before}.items():
            self.assertEqual((self.copy / name).read_bytes(), original)
            self.assertEqual((self.source / name).read_bytes(), original)
        self.assertEqual((self.copy / self.scene_name).read_bytes(), b'unchanged scenario')

    def test_all_features_requires_exact_record_selection_version_and_recipe(self):
        self.enable_bug_fixes()
        self.install_all_features()
        original = deepcopy(self.installation)
        changes = (('status', 'prepared'), ('bug_fixes_version', '1.1'),
                   ('copy_root', str(self.source)), ('source_root', str(self.copy)),
                   ('bug_fix_quests', []), ('bug_fix_sounds', []))
        for key, value in changes:
            with self.subTest(key=key):
                self.installation = dict(original, **{key: value})
                self.write_installation()
                with self.assertRaisesRegex(ValueError, 'installation binding'):
                    self.backend.verify_activation(self.copy)
        self.installation = deepcopy(original)
        for key in ('bug_fixes', 'world_settings', 'food_overhaul'):
            with self.subTest(feature=key):
                self.installation = deepcopy(original)
                self.installation['profile']['features'][key] = False
                self.write_installation()
                with self.assertRaisesRegex(ValueError, 'installation binding'):
                    self.backend.verify_activation(self.copy)

    def test_bug_fix_recipe_cannot_bless_unreviewed_files_or_changed_originals(self):
        self.enable_bug_fixes()
        changed = deepcopy(self.spec)
        changed['bug_fixes']['files'][0]['after_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'reviewed originals'):
            self.backend.build_edits(self.copy, changed)
        name = next(iter(self.bug_before))
        (self.copy / name).write_bytes(b'unknown modified quest')
        with self.assertRaisesRegex(ValueError, 'exact original file'):
            self.backend.build_edits(self.copy, self.spec)
        self.assertFalse((self.copy / self.tx.BACKUP).exists())

    def test_unselected_bug_fix_extra_journal_entries_are_refused(self):
        self.enable_bug_fixes()
        self.install_all_features()
        self.spec.pop('bug_fixes')
        (self.package / 'world_patch.json').write_text(json.dumps(self.spec))
        with self.assertRaisesRegex(ValueError, 'no selected Bug Fixes'):
            self.backend.verify_activation(self.copy)
        self.installation['profile']['features']['bug_fixes'] = False
        self.write_installation()
        with self.assertRaisesRegex(ValueError, 'restoration journal differs'):
            self.backend.verify_activation(self.copy)

    def test_changed_bug_fix_output_backup_or_unchanged_scenario_refuses_activation(self):
        self.enable_bug_fixes()
        self.install_all_features()
        name = next(iter(self.bug_before))
        paths = (self.copy / name, self.copy / self.tx.BACKUP / 'before' / name,
                 self.copy / self.scene_name)
        for path in paths:
            with self.subTest(path=path.relative_to(self.copy)):
                original = path.read_bytes()
                path.write_bytes(original + b'changed')
                with self.assertRaises((ValueError, RuntimeError, self.tx.TransactionError)):
                    self.backend.verify_activation(self.copy)
                path.write_bytes(original)
        self.backend.verify_activation(self.copy)

    def test_bug_fix_helper_import_cannot_come_from_another_package(self):
        self.enable_bug_fixes()
        self.bug_modules['_combined_bugfix_recipe'].__file__ = str(self.root / 'elsewhere.py')
        (self.root / 'elsewhere.py').write_text('# Foreign helper fixture')
        with self.assertRaisesRegex(ValueError, 'Unexpected combined Bug Fixes helper'):
            self.backend.build_edits(self.copy, self.spec)

    def test_real_isolated_worker_has_complete_bug_fix_dependency_closure(self):
        """Actual child interpreter, real transforms, explicitly synthetic pins."""
        self.enable_bug_fixes()
        quest_name, sound_name = self.bug_before
        quest = b'<p>' + bug_fixes._ORE_OBJECTIVE_BEFORE + b'</p>\r\n<p>' + bug_fixes._ORE_OBJECTIVE_BEFORE + b'</p>'
        samples = struct.pack('<6h', -30000, -1000, -1, 0, 1000, 30000)
        fmt = struct.pack('<HHIIHH', 1, 1, 22050, 44100, 2, 16)
        chunks = b'fmt ' + struct.pack('<I', len(fmt)) + fmt + b'data' + struct.pack('<I', len(samples)) + samples
        sound = b'RIFF' + struct.pack('<I', len(chunks) + 4) + b'WAVE' + chunks
        self.bug_before = {quest_name: quest, sound_name: sound}
        self.bug_after = {quest_name: quest.replace(bug_fixes._ORE_OBJECTIVE_BEFORE, bug_fixes._ORE_OBJECTIVE_AFTER),
                          sound_name: ambient_sound.attenuate_wav(sound, 10, name=sound_name)}
        for folder in (self.source, self.copy):
            for name, value in self.bug_before.items():
                (folder / name).write_bytes(value)
        fingerprints = lambda name: dict(path=name, before_sha256=self.tx.sha(self.bug_before[name]),
                                         after_sha256=self.tx.sha(self.bug_after[name]))
        self.bug_recipe = dict(version='1.2', quests=[dict(fingerprints(quest_name), locale='Nl',
            scene_path=self.scene_name, scene_sha256=self.tx.sha(b'unchanged scenario'))],
            sounds=[fingerprints(sound_name)], files=[dict(fingerprints(name), before_size=len(value),
                after_size=len(self.bug_after[name]), offset=None) for name, value in self.bug_before.items()])
        self.spec['bug_fixes'] = self.bug_recipe
        (self.package / 'world_patch.json').write_text(json.dumps(self.spec))
        support = self.package / 'support'
        for name, value in food_world_package._bug_fix_support().items():
            path = self.package / name.removeprefix('world/')
            path.write_bytes(value)
        # Substitute only fixture baselines. Source dependencies and transforms
        # are the same emitted files used by the real package and worker.
        helper = support / '_combined_bug_fixes.py'
        raw = helper.read_text()
        raw = raw.replace(bug_fixes.KING_OF_ORE_SHA256, self.tx.sha(quest))
        raw = raw.replace(bug_fixes.KING_OF_ORE_SCENE_SHA256, self.tx.sha(b'unchanged scenario'))
        helper.write_text(raw)
        sound_pin = (len(sound), __import__('hashlib').sha1(sound, usedforsecurity=False).hexdigest())
        (support / '_combined_ambient_sound_baselines.py').write_text(
            'def localized_sample_baselines(locale):\n    return ' + repr({'fixture.wav': sound_pin}) + '\n')
        tx_raw = (ROOT / 'legacy/world_settings/support/world_transactions.py').read_bytes()
        (support / 'world_transactions.py').write_bytes(packages._adapt('world/support/world_transactions.py', tx_raw, str(self.copy)))
        (support / 'stock_baseline.py').write_bytes((ROOT / 'src/anno1503_overhaul/vanilla.py').read_bytes())
        (support / 'food_world_policy.py').write_text('PROFILE="food06-world"\ndef food_files():\n    return ' + repr(self.food_policy) + '\n')
        payload = 'WorldSettingsIslands/fixture.scp'
        (support / 'package_alias_assets.py').write_text(
            'def introduced_files():\n    return ' + repr({payload: 'assets/fixture.scp'}) + '\n'
            'def data_payload_hashes():\n    return ' + repr({'assets/fixture.scp': self.tx.sha(self.outputs[payload])}) + '\n'
            'def validate_data_payload(name,data):\n    pass\n')
        (support / 'package_world_assets.py').write_text(
            'def introduced_files():\n    return {}\n'
            'def data_payload_hashes():\n    return {}\n'
            'def validate_data_payload(name,data):\n    pass\n'
            'def validate_required_copy(root):\n    pass\n')
        (self.package / 'world_mod.py').write_bytes((ROOT / 'src/anno1503_overhaul/food_world_backend.py').read_bytes())
        (self.package / 'food_mod.py').write_text(
            'from pathlib import Path\nimport sys\nsys.path.insert(0,str(Path(__file__).parent/"support"))\n'
            'import world_transactions as tx\n'
            'def build_edits(root,spec,progress):\n    return "vanilla", [\n'
            + '\n'.join('        tx.Edit(' + ','.join(repr(value) for value in
                (edit.name, edit.before, edit.after, edit.file_size, edit.offset)) + '),' for edit in self.food_edits())
            + '\n    ]\n')
        report = legacy_adapter.prepare_edits('world', self.package, self.copy, self.root / 'isolated-worker-output')
        self.assertEqual(report['state'], 'vanilla')
        self.assertEqual(len(report['edits']), 6)
        self.assertFalse((self.copy / self.tx.BACKUP).exists())
        for name, value in {**self.before, **self.bug_before}.items():
            self.assertEqual((self.copy / name).read_bytes(), value)


if __name__ == '__main__':
    unittest.main()
