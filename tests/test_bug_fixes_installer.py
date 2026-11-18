"""Bug Fixes packaging, installation and restoration with synthetic game files."""
from __future__ import annotations

from contextlib import ExitStack
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from anno1503_overhaul import (
    ambient_sound, beta_paths, bug_fixes, bug_fixes_launch, filesystem, installer, packages, vanilla,
)


QUEST = bug_fixes.KING_OF_ORE_PATH
SCENE = bug_fixes.KING_OF_ORE_SCENE_PATH
ENG_QUEST = QUEST.replace('/Nl/', '/Eng/')
ENG_SCENE = SCENE.replace('/Nl/', '/Eng/')
SAMPLE_FILENAME = 'Schaf1.wav'
NL_SAMPLE = f'Languages/Nl/Samples/{SAMPLE_FILENAME}'
ENG_SAMPLE = f'Languages/Eng/Samples/{SAMPLE_FILENAME}'
ORIGINAL_QUEST = b'<h1>Fixture</h1>\r\n' + b'<p>' + bug_fixes._ORE_OBJECTIVE_BEFORE + b'</p>\r\n'
ORIGINAL_QUEST *= 2
ORIGINAL_SCENE = b'synthetic stock scenario'
ORIGINAL_DATA = b'synthetic stock data'
ORIGINAL_EXE = b'synthetic executable fingerprint fixture'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def snapshot(root):
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob('*') if path.is_file()}


def wav(samples):
    values = struct.pack(f'<{len(samples)}h', *samples)
    content = (b'WAVEfmt ' + struct.pack('<IHHIIHH', 16, 1, 1, 22050, 44100, 2, 16)
               + b'data' + struct.pack('<I', len(values)) + values)
    return b'RIFF' + struct.pack('<I', len(content)) + content


class BugFixesInstallerTests(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.base = Path(stack.enter_context(tempfile.TemporaryDirectory())).resolve()
        self.source = self.base / 'original'
        self.copy = self.base / 'managed'
        self.repo = self.base / 'repo'
        self.repo.mkdir()
        self.package = self.base / 'package'
        self.package_workspace = self.base / 'installer-packages'
        self.profile = dict(schema_version=1, name='Bug Fixes', features={'bug_fixes': True})
        self.source_files = {
            'Anno1503.exe': ORIGINAL_EXE, 'Sample.dat': ORIGINAL_DATA,
            QUEST: ORIGINAL_QUEST, SCENE: ORIGINAL_SCENE,
        }
        for name, data in self.source_files.items():
            target = self.source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        self.sound_baselines = {}
        self.add_sound_fixture('Nl', (-1000, 0, 1000))
        stack.enter_context(patch.object(ambient_sound, 'localized_sample_baselines',
                                         side_effect=self.sound_baselines.__getitem__))
        stock_spec = {'exe_sha256': digest(ORIGINAL_EXE)}
        stock_items = [('Sample.dat', digest(ORIGINAL_DATA), None, None, None, digest(ORIGINAL_DATA))]
        self.stock_items = vanilla._items
        stack.enter_context(patch.object(vanilla, '_spec', return_value=stock_spec))
        stack.enter_context(patch.object(vanilla, '_items', return_value=stock_items))
        stack.enter_context(patch.object(installer, 'require_game_closed'))
        stack.enter_context(patch.object(installer, 'REPO', self.repo))
        stack.enter_context(patch.object(beta_paths, 'package_workspace', return_value=self.package_workspace))
        stack.enter_context(patch.object(bug_fixes, 'KING_OF_ORE_SHA256', digest(ORIGINAL_QUEST)))
        stack.enter_context(patch.object(bug_fixes, 'KING_OF_ORE_SCENE_SHA256', digest(ORIGINAL_SCENE)))

    def prepare(self):
        return packages.prepare_bug_fixes_package(self.package, self.source, self.copy)

    def clone_baseline(self):
        filesystem.clone_game(self.source, self.copy, repo=self.repo)
        filesystem.update_copy_marker(self.copy, phase='vanilla', baseline='vanilla')

    def add_sound_fixture(self, locale, samples):
        path = f'Languages/{locale}/Samples/{SAMPLE_FILENAME}'
        source_file = self.source / path
        original = wav(samples)
        source_file.parent.mkdir(parents=True, exist_ok=True)
        source_file.write_bytes(original)
        self.source_files[path] = original
        self.sound_baselines[locale] = {
            SAMPLE_FILENAME: (len(original), hashlib.sha1(original, usedforsecurity=False).hexdigest()),
        }

    def add_english_fixture(self, stack):
        objective = b'Mine 170 tons of iron ore in each city.'
        quest_rows = [
            b'<tr><td><a name="single14_' + quest_id + b'">#' + quest_id + b'*</a></td>'
            b'<td><p>' + objective + b'</p></td></tr>\r\n'
            for quest_id in (b'300170', b'300171')
        ]
        quest = b'<html>\r\n<table>' + b''.join(quest_rows) + b'</table></html>\r\n'
        kernel = b'IF fixture condition THEN TELL("HUMAN", "Won"); ENDIF'
        scene = (bug_fixes._ORE_SCENE_HEADER + bug_fixes._ORE_QUEST_REFERENCE
                 + b'[SCRIPT_KERNEL]\r\n$ comment\r\n' + kernel + b'\r\n[SIGNALS]')
        english = replace(
            bug_fixes._KING_OF_ORE_BASELINES['Eng'],
            quest_size=len(quest), quest_sha1=hashlib.sha1(quest, usedforsecurity=False).hexdigest(),
            scene_size=len(scene), scene_sha1=hashlib.sha1(scene, usedforsecurity=False).hexdigest(),
        )
        stack.enter_context(patch.dict(bug_fixes._KING_OF_ORE_BASELINES, {'Eng': english}))
        stack.enter_context(patch.object(bug_fixes, '_ORE_KERNEL_SHA256', digest(kernel)))
        for name, data in ((ENG_QUEST, quest), (ENG_SCENE, scene)):
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.add_sound_fixture('Eng', (-2000, 0, 2000))
        return quest, scene

    def install_launch_fixture(self, stack, *, legacy_version=None):
        scene_dll = b'synthetic native Scene module'
        (self.source / 'AnnoScene.dll').write_bytes(scene_dll)
        self.prepare()
        if legacy_version is not None:
            path = self.package / 'manifest.json'
            manifest = json.loads(path.read_bytes())
            manifest['schema_version'] = legacy_version
            manifest['feature_versions'] = {'bug_fixes': {1: '1.0', 2: '1.1'}[legacy_version]}
            manifest.pop('sounds')
            if legacy_version == 1:
                quest, = manifest.pop('quests')
                manifest['quest'] = {key: quest[key] for key in ('path', 'before_sha256',
                                                                'after_sha256', 'scene_sha256')}
            path.write_bytes((json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode('utf-8'))
        record = installer.install(self.source, self.copy, self.profile, package=self.package)
        native = {'AnnoScene.dll': digest(scene_dll)}
        stack.enter_context(patch.object(bug_fixes_launch, 'STOCK_SHA256', native))
        stack.enter_context(patch.object(bug_fixes_launch, '_spec', return_value={
            'exe_sha256': digest(ORIGINAL_EXE), 'native_modules': [],
        }))
        stack.enter_context(patch.object(bug_fixes_launch, 'verified_ubisoft_native',
                                         return_value=('vanilla', native)))
        stack.enter_context(patch.object(bug_fixes_launch, 'require_game_closed'))
        return record

    def test_standalone_package_binds_source_copy_and_only_contains_recovery_spec(self):
        self.assertEqual(self.prepare(), self.package)
        manifest = packages.validate_package(self.package, self.source)
        self.assertTrue(manifest['verified'])
        self.assertEqual(manifest['kind'], packages.BUG_FIXES_PACKAGE_KIND)
        self.assertEqual(Path(manifest['source_root']), self.source)
        self.assertEqual(Path(manifest['copy_root']), self.copy)
        self.assertEqual(manifest['schema_version'], 3)
        self.assertEqual(manifest['feature_versions']['bug_fixes'], '1.2')
        self.assertEqual(manifest['quests'], [{
            'locale': 'Nl', 'path': QUEST, 'before_sha256': digest(ORIGINAL_QUEST),
            'after_sha256': digest(bug_fixes.fix_king_of_ore(ORIGINAL_QUEST)),
            'scene_path': SCENE, 'scene_sha256': digest(ORIGINAL_SCENE),
        }])
        self.assertEqual(manifest['sounds'], [{
            'path': NL_SAMPLE, 'before_sha256': digest(self.source_files[NL_SAMPLE]),
            'after_sha256': digest(wav((-316, 0, 316))),
        }])
        self.assertEqual(set(snapshot(self.package)), {'manifest.json', 'food/food_patch.json'})
        self.assertFalse(self.copy.exists())
        another_source = self.base / 'another-source'
        another_source.mkdir()
        with self.assertRaisesRegex(packages.PackageError, 'different source game'):
            packages.validate_package(self.package, another_source)
        with self.assertRaisesRegex(installer.InstallerError, 'another modded copy'):
            installer.check_install(self.source, self.base / 'another-copy', self.profile,
                                    package=self.package)
        for unexpected in ('unreviewed.dat', 'food/unreviewed.dat'):
            with self.subTest(unexpected=unexpected):
                extra = self.package / unexpected
                extra.write_bytes(b'unreviewed input')
                with self.assertRaisesRegex(packages.PackageError, 'Unexpected'):
                    packages.validate_package(self.package, self.source)
                extra.unlink()

    def test_install_record_accepts_bounded_six_language_asset_fingerprints(self):
        from anno1503_overhaul.ambient_sound_baselines import localized_sample_baselines
        self.clone_baseline()
        sounds = [dict(path=f'Languages/{locale}/Samples/{name}',
                       before_sha256='a' * 64, after_sha256='b' * 64)
                  for locale in bug_fixes.KING_OF_ORE_LOCALES
                  for name in localized_sample_baselines(locale)]
        record = dict(schema=1, copy_root=str(self.copy), source_root=str(self.source),
                      baseline='vanilla', status='installed', bug_fixes_version='1.2',
                      bug_fix_sounds=sounds)
        raw = json.dumps(record, indent=2).encode('utf-8')
        self.assertGreater(len(raw), 128 * 1024)
        self.assertLess(len(raw), installer._MAX_INSTALL_RECORD)
        path = self.copy / installer.INSTALL_RECORD
        path.write_bytes(raw)
        self.assertEqual(installer._read_install(self.copy), record)
        path.write_bytes(b' ' * (installer._MAX_INSTALL_RECORD + 1))
        with self.assertRaisesRegex(installer.InstallerError, 'installation record is invalid'):
            installer._read_install(self.copy)

    def test_standalone_check_install_and_restore_journal_quest_and_sound(self):
        plan = installer.check_install(self.source, self.copy, self.profile)
        self.assertFalse(self.copy.exists())
        self.assertFalse(plan['game_files_changed'])
        record = installer.install(self.source, self.copy, self.profile,
                                   package=Path(plan['package_root']))
        self.assertEqual(record['status'], 'installed')
        self.assertEqual(record['changed_files'], 2)
        self.assertEqual(installer.installed_launch_kind(record), 'bug_fixes')
        self.assertEqual({entry['name'] for entry in installer.adapter.read_manifest(self.copy)['edits']},
                         {QUEST, NL_SAMPLE})
        self.assertEqual((self.copy / QUEST).read_bytes(), bug_fixes.fix_king_of_ore(ORIGINAL_QUEST))
        self.assertEqual((self.copy / SCENE).read_bytes(), ORIGINAL_SCENE)
        self.assertEqual((self.copy / NL_SAMPLE).read_bytes(), wav((-316, 0, 316)))
        self.assertEqual((self.copy / 'Sample.dat').read_bytes(), ORIGINAL_DATA)
        save = self.copy / 'Savegames' / 'keep.sav'
        save.parent.mkdir()
        save.write_bytes(b'unrelated save')
        self.assertTrue(installer.restore(self.copy)['restored'])
        self.assertEqual((self.copy / QUEST).read_bytes(), ORIGINAL_QUEST)
        self.assertEqual((self.copy / NL_SAMPLE).read_bytes(), self.source_files[NL_SAMPLE])
        self.assertEqual(save.read_bytes(), b'unrelated save')
        self.assertEqual(snapshot(self.source), self.source_files)

    def test_mixed_languages_install_and_restore_in_one_journal_with_shared_stock_checks(self):
        with ExitStack() as stack:
            english_quest, english_scene = self.add_english_fixture(stack)
            ui = Path('Languages/Eng/ToolGfx/fenster.tex')
            (self.source / ui).parent.mkdir()
            (self.source / ui).write_bytes(b'preserved localized UI')
            other_sound = Path('Languages/Eng/Samples/Unrelated voice.wav')
            (self.source / other_sound).write_bytes(wav((1200,)))
            source_before = snapshot(self.source)
            stock_spec = {
                'exe_sha256': digest(ORIGINAL_EXE), 'native_modules': [], 'archives': [],
                'files': {'Sample.dat': {'sources': {'vanilla': digest(ORIGINAL_DATA)}}},
            }
            stack.enter_context(patch.object(vanilla, '_spec', return_value=stock_spec))
            stack.enter_context(patch.object(vanilla, '_items', self.stock_items))
            plan = installer.check_install(self.source, self.copy, self.profile)
            self.assertEqual([quest['locale'] for quest in plan['bug_fix_quests']], ['Eng', 'Nl'])
            self.assertEqual([sound['path'] for sound in plan['bug_fix_sounds']], [ENG_SAMPLE, NL_SAMPLE])
            self.assertTrue(plan['localized_bug_fixes'])
            package = Path(plan['package_root'])
            record = installer.install(self.source, self.copy, self.profile, package=package)
            self.assertTrue(record['localized_bug_fixes'])
            self.assertEqual(record['changed_files'], 4)
            journal = installer.adapter.read_manifest(self.copy)
            self.assertEqual({entry['name'] for entry in journal['edits']},
                             {QUEST, ENG_QUEST, NL_SAMPLE, ENG_SAMPLE})
            self.assertEqual((self.copy / ENG_QUEST).read_bytes().count(b'in stock'), 2)
            self.assertEqual((self.copy / QUEST).read_bytes(), bug_fixes.fix_king_of_ore(ORIGINAL_QUEST))
            self.assertEqual((self.copy / ENG_SCENE).read_bytes(), english_scene)
            self.assertEqual((self.copy / ENG_SAMPLE).read_bytes(), wav((-632, 0, 632)))
            self.assertEqual((self.copy / NL_SAMPLE).read_bytes(), wav((-316, 0, 316)))
            self.assertEqual((self.copy / other_sound).read_bytes(), wav((1200,)))
            self.assertTrue(installer.restore(self.copy)['restored'])
            self.assertEqual((self.copy / ENG_QUEST).read_bytes(), english_quest)
            self.assertEqual((self.copy / QUEST).read_bytes(), ORIGINAL_QUEST)
            for name in (ENG_SAMPLE, NL_SAMPLE, other_sound.as_posix()):
                self.assertEqual((self.copy / name).read_bytes(), source_before[name])
            self.assertEqual((self.copy / ui).read_bytes(), b'preserved localized UI')
            self.assertEqual(snapshot(self.source), source_before)
            (self.copy / ENG_SAMPLE).write_bytes(source_before[NL_SAMPLE])
            swapped_sound = snapshot(self.copy)
            with self.assertRaisesRegex(bug_fixes.BugFixError, 'Sound effect differs'):
                installer.install(self.source, self.copy, self.profile, package=package)
            self.assertEqual(snapshot(self.copy), swapped_sound)

    def test_bad_source_quest_scene_or_sound_blocks_package_preparation_and_install(self):
        for name, message in ((QUEST, 'King of Ore'), (SCENE, 'King of Ore'),
                              (NL_SAMPLE, 'Sound effect differs')):
            with self.subTest(name=name):
                original = self.source_files[name]
                bad = original + b'changed'
                path = self.source / name
                path.write_bytes(bad)
                with self.assertRaisesRegex(bug_fixes.BugFixError, message):
                    self.prepare()
                with self.assertRaisesRegex(bug_fixes.BugFixError, message):
                    installer.install(self.source, self.copy, self.profile)
                self.assertFalse(self.package.exists())
                self.assertFalse(self.package_workspace.exists())
                self.assertFalse(self.copy.exists())
                self.assertEqual(path.read_bytes(), bad)
                path.write_bytes(original)

    def test_changed_quest_scene_or_sound_in_existing_copy_refuses_before_writes(self):
        self.clone_baseline()
        self.prepare()
        for name, message in ((QUEST, 'King of Ore'), (SCENE, 'King of Ore'),
                              (NL_SAMPLE, 'Sound effect differs')):
            with self.subTest(name=name):
                path = self.copy / name
                path.write_bytes(self.source_files[name] + b'changed')
                before = snapshot(self.copy)
                with self.assertRaisesRegex(bug_fixes.BugFixError, message):
                    installer.install(self.source, self.copy, self.profile, package=self.package)
                self.assertEqual(snapshot(self.copy), before)
                path.write_bytes(self.source_files[name])
        self.assertEqual(snapshot(self.source), self.source_files)

    def test_valid_package_for_another_copy_cannot_replace_checked_package(self):
        self.clone_baseline()
        self.prepare()
        other = packages.prepare_bug_fixes_package(self.base / 'other-package', self.source,
                                                 self.base / 'other-copy')
        real_check = installer.check_install

        def swap_manifest(*args, **kwargs):
            plan = real_check(*args, **kwargs)
            (self.package / 'manifest.json').write_bytes((other / 'manifest.json').read_bytes())
            return plan

        before = snapshot(self.copy)
        with patch.object(installer, 'check_install', side_effect=swap_manifest):
            with self.assertRaisesRegex(installer.InstallerError, 'prepared package changed'):
                installer.install(self.source, self.copy, self.profile, package=self.package)
        self.assertEqual(snapshot(self.copy), before)

    def test_food_recipe_can_share_the_bug_fixes_transaction(self):
        food = self.package / 'food'
        food.mkdir(parents=True)
        (self.package / 'manifest.json').write_text('{}', encoding='utf-8')
        (food / 'food_patch.json').write_text('{}', encoding='utf-8')
        (food / 'food_mod.py').write_text(
            'from types import SimpleNamespace\n'
            'def build_edits(root, spec, progress):\n'
            '    before = (root / "Sample.dat").read_bytes()\n'
            '    edit = SimpleNamespace(name="Sample.dat", before=before, after=b"modded food",\n'
            '                           file_size=len(before), offset=None)\n'
            '    return "vanilla", [edit]\n', encoding='utf-8',
        )
        metadata = dict(kind='anno1503-food-installer-package', copy_root=str(self.copy), verified=True)
        self.profile['features']['food_overhaul'] = True
        with patch.object(packages, 'validate_package', return_value=metadata):
            record = installer.install(self.source, self.copy, self.profile, package=self.package)
        self.assertEqual(record['changed_files'], 3)
        self.assertEqual({entry['name'] for entry in installer.adapter.read_manifest(self.copy)['edits']},
                         {QUEST, NL_SAMPLE, 'Sample.dat'})
        self.assertEqual((self.copy / QUEST).read_bytes(), bug_fixes.fix_king_of_ore(ORIGINAL_QUEST))
        self.assertEqual((self.copy / 'Sample.dat').read_bytes(), b'modded food')
        self.assertEqual((self.copy / NL_SAMPLE).read_bytes(), wav((-316, 0, 316)))
        self.assertTrue(installer.restore(self.copy)['restored'])
        self.assertEqual((self.copy / QUEST).read_bytes(), ORIGINAL_QUEST)
        self.assertEqual((self.copy / 'Sample.dat').read_bytes(), ORIGINAL_DATA)
        self.assertEqual((self.copy / NL_SAMPLE).read_bytes(), self.source_files[NL_SAMPLE])
        self.assertEqual(snapshot(self.source), self.source_files)

    def install_all_mods_fixture(self, stack):
        """Exercise the common transaction with isolated native-build outputs."""
        food = self.package / 'food'
        world = self.package / 'world'
        food.mkdir(parents=True)
        world.mkdir()
        (self.package / 'manifest.json').write_text('{}', encoding='utf-8')
        (food / 'food_patch.json').write_text('{}', encoding='utf-8')
        (world / 'world_patch.json').write_text(json.dumps({'exe_sha256': digest(ORIGINAL_EXE)}))
        (world / 'world_mod.py').write_text(
            'from types import SimpleNamespace\n'
            'def resolve_copy(spec, root, package=None):\n'
            '    return root\n'
            'def build_edits(root, spec, progress):\n'
            '    before = (root / "Sample.dat").read_bytes()\n'
            '    return "vanilla", [\n'
            '        SimpleNamespace(name="Sample.dat", before=before, after=b"tiered food",\n'
            '                        file_size=len(before), offset=None),\n'
            '        SimpleNamespace(name="AnnoWorldSettings.dll", before=None, after=b"World fixture",\n'
            '                        file_size=None, offset=None),\n'
            '    ]\n', encoding='utf-8',
        )
        metadata = dict(kind=installer.PUBLIC_FOOD_WORLD06_PACKAGE_KIND, copy_root=str(self.copy),
                        food_enabled=True, bug_fixes_enabled=True, verified=True,
                        new_world_required=True, old_save_migration_supported=False,
                        world_settings_supported=True)
        stack.enter_context(patch.object(packages, 'validate_package', return_value=metadata))
        builder = ModuleType('anno1503_overhaul.food_world_public')
        builder.prepare_public_food_world_package = Mock(return_value=self.package)
        stack.enter_context(patch.dict(sys.modules, {builder.__name__: builder}))
        selected = dict(schema_version=1, name='All three features', features={
            'food_overhaul': True, 'world_settings': True, 'bug_fixes': True,
        })
        plan = installer.check_install(self.source, self.copy, selected,
                                       food_version=installer.FOOD06_VERSION)
        builder.prepare_public_food_world_package.assert_called_once()
        self.assertIs(builder.prepare_public_food_world_package.call_args.kwargs['bug_fixes_enabled'], True)
        self.assertFalse(self.copy.exists())
        record = installer.install(self.source, self.copy, selected, package=self.package,
                                   food_version=installer.FOOD06_VERSION)
        return record, plan

    def test_all_three_modules_share_one_guarded_journal_and_restore_together(self):
        with ExitStack() as stack:
            record, plan = self.install_all_mods_fixture(stack)
        self.assertEqual(record['changed_files'], 4)
        self.assertEqual(record['food_version'], installer.FOOD06_VERSION)
        self.assertEqual(record['bug_fixes_version'], '1.2')
        self.assertEqual(record['bug_fix_quests'], plan['bug_fix_quests'])
        self.assertEqual(record['bug_fix_sounds'], plan['bug_fix_sounds'])
        self.assertEqual(installer.installed_launch_kind(record), 'food06-world')
        self.assertTrue(record['new_world_required'])
        self.assertFalse(record['old_save_migration_supported'])
        self.assertEqual({entry['name'] for entry in installer.adapter.read_manifest(self.copy)['edits']},
                         {QUEST, NL_SAMPLE, 'Sample.dat', 'AnnoWorldSettings.dll'})
        self.assertEqual((self.copy / 'Sample.dat').read_bytes(), b'tiered food')
        self.assertEqual((self.copy / 'AnnoWorldSettings.dll').read_bytes(), b'World fixture')
        self.assertEqual((self.copy / QUEST).read_bytes(), bug_fixes.fix_king_of_ore(ORIGINAL_QUEST))
        self.assertEqual((self.copy / NL_SAMPLE).read_bytes(), wav((-316, 0, 316)))
        installer._verify_food06_bug_fixes(self.copy, record)
        save = self.copy / 'progress.txt'
        save.write_bytes(b'preserve all-mods progress')
        self.assertTrue(installer.restore(self.copy)['restored'])
        self.assertFalse((self.copy / 'AnnoWorldSettings.dll').exists())
        self.assertEqual((self.copy / 'Sample.dat').read_bytes(), ORIGINAL_DATA)
        self.assertEqual((self.copy / QUEST).read_bytes(), ORIGINAL_QUEST)
        self.assertEqual((self.copy / NL_SAMPLE).read_bytes(), self.source_files[NL_SAMPLE])
        self.assertEqual(save.read_bytes(), b'preserve all-mods progress')
        self.assertEqual(snapshot(self.source), self.source_files)

    def test_all_mods_launcher_refuses_changed_assets_or_incoherent_feature_bindings(self):
        with ExitStack() as stack:
            record, _ = self.install_all_mods_fixture(stack)
            launch = stack.enter_context(patch.object(installer, 'launch_world_settings', return_value='started'))
            self.assertEqual(installer.launch_installed_game(self.copy), 'started')
            launch.assert_called_once_with(self.copy)
            launch.reset_mock()
            for name in (QUEST, NL_SAMPLE, SCENE):
                with self.subTest(name=name):
                    path = self.copy / name
                    before = path.read_bytes()
                    path.write_bytes(before + b'changed')
                    with self.assertRaises((installer.InstallerError, installer.adapter.AdapterError)):
                        installer.launch_installed_game(self.copy)
                    path.write_bytes(before)
            record_path = self.copy / installer.INSTALL_RECORD
            original = record_path.read_bytes()
            for key in ('bug_fixes_version', 'bug_fix_quests', 'bug_fix_sounds'):
                with self.subTest(binding=key):
                    changed = json.loads(original)
                    changed.pop(key)
                    record_path.write_text(json.dumps(changed))
                    with self.assertRaisesRegex(installer.InstallerError, 'Bug Fixes'):
                        installer.launch_installed_game(self.copy)
            record_path.write_bytes(original)
            launch.assert_not_called()

    def test_all_mods_cannot_use_a_combined_package_that_excludes_bug_fixes(self):
        with ExitStack() as stack:
            _, _ = self.install_all_mods_fixture(stack)
            installer.restore(self.copy)
            profile = dict(schema_version=1, name='All three', features={
                'food_overhaul': True, 'world_settings': True, 'bug_fixes': True,
            })
            metadata = dict(kind=installer.FOOD_WORLD06_PACKAGE_KIND, copy_root=str(self.copy),
                            food_enabled=True, bug_fixes_enabled=False, verified=True)
            stack.enter_context(patch.object(packages, 'validate_package', return_value=metadata))
            before = snapshot(self.copy)
            with self.assertRaisesRegex(installer.InstallerError, 'different Bug Fixes selection'):
                installer.install(self.source, self.copy, profile, package=self.package,
                                  food_version=installer.FOOD06_VERSION)
            self.assertEqual(snapshot(self.copy), before)

    def test_food06_cannot_hide_installed_bug_fixes_by_clearing_the_checkbox_and_binding(self):
        with ExitStack() as stack:
            record, _ = self.install_all_mods_fixture(stack)
            launch = stack.enter_context(patch.object(installer, 'launch_world_settings'))
            for key in ('bug_fixes_version', 'bug_fix_quests', 'bug_fix_sounds'):
                record.pop(key)
            record['profile']['features']['bug_fixes'] = False
            (self.copy / installer.INSTALL_RECORD).write_text(json.dumps(record))
            with self.assertRaisesRegex(installer.InstallerError, 'Bug Fixes assets.*unchecked'):
                installer.launch_installed_game(self.copy)
            launch.assert_not_called()
            # The same guard applies to the Food-only route before any native
            # startup observer is created.
            record['profile']['features']['world_settings'] = False
            with self.assertRaisesRegex(installer.InstallerError, 'Bug Fixes assets.*unchecked'):
                installer._verify_food06_bug_fixes(self.copy, record)

    def test_standalone_launch_uses_verified_identity_and_existing_client_handoff(self):
        with ExitStack() as stack:
            self.install_launch_fixture(stack)
            # Simulate starting the finished copy from the standalone installer.
            stack.enter_context(patch.object(sys, 'frozen', True, create=True))
            uri = stack.enter_context(patch.object(bug_fixes_launch, 'find_registered_uri',
                                                   return_value='uplay://launch/fixture'))
            source_probe, copy_probe = Mock(), Mock()
            probes = stack.enter_context(patch.object(bug_fixes_launch, '_make_probes',
                                                      return_value=(source_probe, copy_probe)))
            process = Mock()
            handoff = stack.enter_context(patch.object(bug_fixes_launch, 'start_game', return_value=process))
            self.assertIs(installer.launch_installed_game(self.copy), process)
        uri.assert_called_once_with(self.source)
        handoff.assert_called_once_with('uplay://launch/fixture', self.source, self.copy,
                                        source_probe, copy_probe=copy_probe, progress=None)
        verified = probes.call_args.args[0]
        self.assertEqual(verified['source_inputs']['source'], self.source)
        self.assertEqual(verified['copy_inputs']['copy'], self.copy)
        self.assertEqual(verified['copy_inputs']['native_sha256'], {
            'AnnoScene.dll': filesystem.file_sha(self.copy / 'AnnoScene.dll'),
        })
        source_probe.close.assert_called_once_with()
        copy_probe.close.assert_called_once_with()

    def test_persisted_dutch_v1_package_can_still_verify_for_standalone_launch(self):
        with ExitStack() as stack:
            record = self.install_launch_fixture(stack, legacy_version=1)
            self.assertNotIn('localized_bug_fixes', record)
            # A language added to the original game after installation is
            # outside this legacy package's single-locale binding.
            (self.source / ENG_QUEST).parent.mkdir(parents=True)
            (self.source / ENG_QUEST).write_bytes(b'unverified additional language')
            verified = bug_fixes_launch.verify_bug_fixes_installation(self.copy)
            manifest = packages.validate_package(self.package, self.source)
            self.assertEqual(manifest['schema_version'], 1)
            self.assertEqual([quest['locale'] for quest in manifest['quests']], ['Nl'])
            self.assertEqual(manifest['sounds'], [])
            self.assertEqual((self.copy / NL_SAMPLE).read_bytes(), self.source_files[NL_SAMPLE])
            self.assertEqual(verified['copy_root'], self.copy)

    def test_persisted_localized_v2_package_can_still_verify_for_standalone_launch(self):
        with ExitStack() as stack:
            self.add_english_fixture(stack)
            record = self.install_launch_fixture(stack, legacy_version=2)
            self.assertTrue(record['localized_bug_fixes'])
            verified = bug_fixes_launch.verify_bug_fixes_installation(self.copy)
            manifest = packages.validate_package(self.package, self.source)
            self.assertEqual(manifest['schema_version'], 2)
            self.assertEqual([quest['locale'] for quest in manifest['quests']], ['Eng', 'Nl'])
            self.assertEqual(manifest['sounds'], [])
            for name in (NL_SAMPLE, ENG_SAMPLE):
                self.assertEqual((self.copy / name).read_bytes(), self.source_files[name])
            self.assertEqual(verified['copy_root'], self.copy)

    def test_launch_refuses_changed_assets_before_requesting_client_handoff(self):
        with ExitStack() as stack:
            self.install_launch_fixture(stack)
            handoff = stack.enter_context(patch.object(bug_fixes_launch, 'start_game'))
            probes = stack.enter_context(patch.object(bug_fixes_launch, '_make_probes'))
            cases = (
                (self.copy / QUEST, installer.InstallerError, 'Changed since preflight/installation'),
                (self.copy / NL_SAMPLE, installer.InstallerError, 'Changed since preflight/installation'),
                (self.copy / SCENE, installer.InstallerError, 'King of Ore scenario changed'),
                (self.source / QUEST, bug_fixes.BugFixError, 'King of Ore quest text'),
                (self.source / NL_SAMPLE, bug_fixes.BugFixError, 'Sound effect differs'),
                (self.package / 'manifest.json', installer.InstallerError, 'package identity changed'),
            )
            for path, error, message in cases:
                with self.subTest(path=path.name):
                    before = path.read_bytes()
                    path.write_bytes(before + b'changed')
                    with self.assertRaisesRegex(error, message):
                        installer.launch_installed_game(self.copy)
                    path.write_bytes(before)
            handoff.assert_not_called()
            probes.assert_not_called()


if __name__ == '__main__':
    unittest.main()
