"""Migration boundary regressions; fixtures never access a game installation."""
from pathlib import Path
import importlib.util
import json
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('tested_legacy_importer', ROOT/'tools/import_legacy.py')
IMPORTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(IMPORTER)


class ImportBoundaryTests(unittest.TestCase):
    def test_game_payloads_history_and_sessions_are_not_public(self):
        for name in ('native/AnnoWelt.dll', 'assets/WorldSettingsIslands/Nord/island.scp',
                     'developer/source/runtime_dev3/history/old/example.c',
                     'logs/launcher.py', 'save.sav', 'activation_session.json',
                     'developer/native_original.asm', 'developer/report.json'):
            with self.subTest(name=name):
                self.assertFalse(IMPORTER.public_rule(Path(name))[0])

    def test_compilable_mod_source_and_authored_food_assets_are_public_candidates(self):
        for name in ('developer/source/engine_resume/ai_food/experiment_runtime/WorldSettings.c',
                     'developer/source/runtime_dev3/runtime_test_blobs.h',
                     'developer/source/engine_resume/ai_loader/engine_patch_plan.h',
                     'developer/huge_world/runtime_engine_edits.json',
                     'developer/huge_world/grid/grid_plan_source.json',
                     'assets/bread.png', 'assets/source/bread.png', 'assets/bread_icon.json'):
            with self.subTest(name=name):
                self.assertTrue(IMPORTER.public_rule(Path(name))[0])

    def test_world_spec_removes_private_evidence_before_public_privacy_check(self):
        spec = dict(original_game_root='machine-specific-folder',
                    actual_game_run=True, packaged_runtime_gameplay_verified=True,
                    game_evidence={'operator': 'private-fixture-profile'},
                    game_evidence_sha256={'private-fixture-profile': 'hash'},
                    runtime_gameplay_evidence={'path':'private-fixture-profile'},
                    payloads={'native/AnnoWorldSettings.dll':'runtime-fingerprint'})
        original = json.dumps(spec).encode()
        public = IMPORTER.public_world_spec(original)
        self.assertNotIn(b'private-fixture-profile', public)
        result = json.loads(public)
        self.assertFalse(result['actual_game_run'])
        self.assertFalse(result['packaged_runtime_gameplay_verified'])
        self.assertEqual(result['original_game_root'], '${ANNO1503_GAME_DIR}')
        self.assertEqual(result['repository_source_snapshot']['original_world_spec_sha256'], IMPORTER.digest(original))
        self.assertTrue(result['repository_source_snapshot']['historical_baseline_actual_game_run'])

    def test_source_only_copy_guard_runs_before_target_code(self):
        source = b'def resolve_copy(spec, root=None, package=None):\n    """Fixture resolver."""\n    raise AssertionError("target code must not run")\n'
        changed = IMPORTER.guard_world_resolver(source)
        class ModError(Exception):
            pass
        namespace = dict(food=types.SimpleNamespace(fm=types.SimpleNamespace(ModError=ModError)))
        exec(compile(changed, '<fixture>', 'exec'), namespace)
        with self.assertRaisesRegex(ModError, 'Source-only repository snapshot'):
            namespace['resolve_copy']({'repository_source_snapshot':{'source_only':True}})
        with self.assertRaisesRegex(AssertionError, 'target code'):
            namespace['resolve_copy']({})

    def test_private_baseline_preserves_payloads_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root/'input'
            source.mkdir()
            (source/'native').mkdir()
            (source/'native/payload.dll').write_bytes(b'owned-fixture-payload')
            (source/'_build/preload').mkdir(parents=True)
            (source/'_build/preload/module.dll').write_bytes(b'owned-preload-fixture')
            (source/'_build/object.obj').write_bytes(b'owned-intermediate')
            target = root/'private-copy'
            report = IMPORTER.private_baseline(source.resolve(), target)
            self.assertEqual(len(report['files']), 2)
            self.assertEqual((target/'native/payload.dll').read_bytes(), b'owned-fixture-payload')
            self.assertFalse((target/'_build/object.obj').exists())
            with self.assertRaises(FileExistsError):
                IMPORTER.private_baseline(source.resolve(), target)
            self.assertEqual((source/'native/payload.dll').read_bytes(), b'owned-fixture-payload')


if __name__ == '__main__':
    unittest.main()
