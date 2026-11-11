"""Portable integrity/dispatch fixtures; no game process or native payloads."""
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
import zipfile
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from anno1503_overhaul import frozen_runner as runner


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def manifest(path, value):
    raw = (json.dumps(value, sort_keys=True) + '\n').encode()
    write(path, raw)
    return sha(raw)


class FrozenRunner(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='anno-frozen-runner-')
        self.base = Path(self.tmp.name).resolve()
        self.app = self.base / 'release'
        self.app.mkdir()
        self.script = self.app / 'src/anno1503_overhaul/legacy_worker.py'
        self.raw = b'import json,sys\nprint(json.dumps({"args":sys.argv[1:],"path0":sys.path[0],"name":__name__}))\n'
        write(self.script, self.raw)
        self.index = dict(schema_version=1, kind=runner.RELEASE_KIND,
                         files={'src/anno1503_overhaul/legacy_worker.py': sha(self.raw)})
        self.release_sha = manifest(self.app / 'release-files.json', self.index)
        write(self.app / runner.WORKER, b'MZ worker fixture; not executable')
        write(self.app / runner.LAUNCHER, b'MZ GUI fixture; not executable')
        write(self.app / '_internal/python-runtime.bin', b'owned runtime fixture')
        self.old_executable = sys.executable
        self.old_trust = runner._trusted_release_sha256
        runner._trusted_release_sha256 = self.release_sha

    def tearDown(self):
        sys.executable = self.old_executable
        runner._trusted_release_sha256 = self.old_trust
        self.tmp.cleanup()

    def observed(self, script=None, args=(), root=None):
        output = io.StringIO()
        old_args, old_path = sys.argv, sys.path[:]
        with redirect_stdout(output):
            value = runner.dispatch(['-B', str(script or self.script), *args], root=root or self.app)
        self.assertEqual(value, 0)
        self.assertIs(sys.argv, old_args)
        self.assertEqual(sys.path, old_path)
        return json.loads(output.getvalue())

    def package(self, kind=runner.PACKAGE_KIND):
        root = self.base / 'package'
        script = root / 'launcher/activation_once.py'
        write(script, self.raw)
        data = dict(schema_version=1, kind=kind, version='historical-version-owned',
                    copy_root=str(self.base / 'game'), files={'launcher/activation_once.py': sha(self.raw)})
        digest = manifest(root / 'manifest.json', data)
        return root, script, data, digest

    def test_source_dispatch_preserves_arguments_and_import_directory(self):
        value = self.observed(args=('literal with spaces', '--game-dir', 'C:/Games/Anno'))
        self.assertEqual(value, dict(args=['literal with spaces', '--game-dir', 'C:/Games/Anno'],
                                    path0=str(self.script.parent), name='__main__'))

    def test_frozen_dispatch_retains_the_bootstrap_zip_at_path_zero(self):
        bootstrap = self.base / 'base_library.zip'
        with zipfile.ZipFile(bootstrap, 'x') as zipped:
            zipped.writestr('anno_bootstrap_only_probe.py', 'VALUE = "zip remained reachable"\n')
        raw = b'import json,sys,anno_bootstrap_only_probe\nprint(json.dumps({"value":anno_bootstrap_only_probe.VALUE,"path":sys.path}))\n'
        write(self.script, raw)
        runner._trusted_release_sha256 = manifest(self.app / 'release-files.json', dict(self.index,
            files={'src/anno1503_overhaul/legacy_worker.py':sha(raw)}))
        previous = sys.path[:]
        try:
            sys.path.insert(0, str(bootstrap))
            with patch.object(sys, 'frozen', True, create=True):
                value = self.observed()
            self.assertEqual(value['value'], 'zip remained reachable')
            self.assertEqual(value['path'], [str(self.script.parent), str(bootstrap), *previous])
        finally:
            sys.path[:] = previous
            sys.modules.pop('anno_bootstrap_only_probe', None)

    def test_import_dependency_scan_includes_nested_external_helper_imports(self):
        names = runner.external_dependency_names(['def later():\n import decimal\nfrom ctypes import wintypes\nimport unknown_provider\n'])
        self.assertTrue({'decimal','ctypes','ctypes.wintypes','queue','_queue','heapq','_heapq'} <= set(names))
        self.assertNotIn('unknown_provider', names)
        selected = runner.import_source_names(['src/anno1503_overhaul/legacy_worker.py',
            'legacy/launcher/launch_world_settings.pyw', 'legacy/launcher/activation_once.py',
            'legacy/launcher/test_launcher.py', 'legacy/world_settings/activation/activate_world_settings.py'])
        self.assertNotIn('legacy/launcher/test_launcher.py', selected)
        self.assertEqual(len(selected), 4)

    def test_import_preflight_uses_child_path_without_running_main(self):
        sentinel = self.base / 'main-was-called.txt'
        raw = ('import queue\nfrom pathlib import Path\n'
               'def main():Path(' + repr(str(sentinel)) + ').write_text("unsafe")\n'
               'if __name__=="__main__":main()\n').encode()
        write(self.script, raw)
        runner._trusted_release_sha256 = manifest(self.app / 'release-files.json', dict(self.index,
            files={'src/anno1503_overhaul/legacy_worker.py':sha(raw)}))
        old_path, old_args = sys.path[:], sys.argv
        with patch.object(runner, 'external_dependency_names', return_value=['heapq','queue']), \
             patch.object(sys, 'frozen', True, create=True), patch('anno1503_overhaul.selector.main') as gui:
            checked = runner.import_preflight(self.script, root=self.app)
        self.assertTrue(checked['passed'])
        self.assertFalse(checked['main_called'] or checked['game_started'] or checked['ui_created'])
        self.assertFalse(sentinel.exists());gui.assert_not_called()
        self.assertEqual(sys.path, old_path);self.assertIs(sys.argv, old_args)
        other = self.app / 'src/anno1503_overhaul/other.py'
        write(other, raw)
        runner._trusted_release_sha256 = manifest(self.app / 'release-files.json', dict(self.index,
            files={'src/anno1503_overhaul/legacy_worker.py':sha(raw),
                   'src/anno1503_overhaul/other.py':sha(raw)}))
        with patch('runpy.run_path') as execute, self.assertRaises(runner.RunnerError):
            runner.import_preflight(other, root=self.app)
        execute.assert_not_called()

    def test_both_flat_import_preflights_require_the_complete_helper_chain(self):
        root, activation, data, unused = self.package()
        raw = b'def main():raise AssertionError("main must not run")\nif __name__=="__main__":main()\n'
        files = {}
        for entry in runner._FLAT_ENTRIES:
            write(root / 'launcher' / entry, raw);files['launcher/' + entry] = sha(raw)
        expected = {}
        for index, name in enumerate(runner._FLAT_HELPER_IMPORTS):
            directory = root / ('launcher' if index < 6 else 'world' if name == 'world_mod' else 'world/activation')
            path = directory / (name + '.py');write(path, b'# exact helper fixture\n')
            expected[name] = path;files[path.relative_to(root).as_posix()] = sha(path.read_bytes())
        data = dict(data, files=files);manifest(root / 'manifest.json', data)
        original_import = runner.importlib.import_module
        def imported(name):
            return SimpleNamespace(__file__=str(expected[name])) if name in expected else original_import(name)
        with patch('anno1503_overhaul.beta_package.validate_beta_package', return_value=dict(data, verified=True)), \
             patch.object(runner, 'external_dependency_names', return_value=['heapq','queue']), \
             patch.object(runner.importlib, 'import_module', side_effect=imported):
            for entry in sorted(runner._FLAT_ENTRIES):
                with self.subTest(entry=entry):
                    checked = runner.import_preflight(root / 'launcher' / entry, root=self.app)
                    self.assertEqual(checked['helper_modules'], list(runner._FLAT_HELPER_IMPORTS))
            expected['native_ready'] = self.script
            with self.assertRaisesRegex(runner.RunnerError, 'unexpected identity'):
                runner.import_preflight(activation, root=self.app)

    def test_changed_source_or_release_index_never_executes(self):
        sentinel = self.base / 'unexpected.txt'
        hostile = ('from pathlib import Path\nPath(' + repr(str(sentinel)) + ').write_text("executed")\n').encode()
        write(self.script, hostile)
        with self.assertRaises(runner.RunnerError):
            self.observed()
        altered = dict(self.index, files={'src/anno1503_overhaul/legacy_worker.py': sha(hostile)})
        manifest(self.app / 'release-files.json', altered)
        with self.assertRaises(runner.RunnerError):
            self.observed()
        self.assertFalse(sentinel.exists())

    def test_unlisted_external_and_parent_traversal_scripts_are_refused(self):
        external = self.base / 'other.py'
        write(external, b'raise RuntimeError("must never execute")\n')
        unlisted = self.app / 'src/unlisted.py'
        write(unlisted, external.read_bytes())
        for path in (external, unlisted, self.app / 'src/../src/anno1503_overhaul/legacy_worker.py'):
            with self.subTest(path=path), self.assertRaises(runner.RunnerError):
                runner.dispatch(['-B', str(path)], root=self.app)
        for args in (['-c', 'print(1)'], ['-m', 'os'], ['--help'], ['-B']):
            with self.subTest(args=args), self.assertRaises(runner.RunnerError):
                runner.dispatch(args, root=self.app)

    def test_flat_package_runs_only_after_version_owned_validator(self):
        root, script, data, unused = self.package()
        with patch('anno1503_overhaul.beta_package.validate_beta_package', return_value=dict(data, verified=True)) as validate:
            self.assertEqual(self.observed(script, args=('once',))['args'], ['once'])
        validate.assert_called_once_with(root)
        write(script, b'raise RuntimeError("changed package helper executed")\n')
        with patch('anno1503_overhaul.beta_package.validate_beta_package', return_value=dict(data, verified=True)):
            with self.assertRaises(runner.RunnerError):
                self.observed(script)

    def test_unknown_package_and_failed_recipe_never_reach_runpy(self):
        root, script, data, unused = self.package(kind='anno1503-local-installer-package')
        with patch('runpy.run_path') as execute:
            with self.assertRaises(runner.RunnerError):
                self.observed(script)
        execute.assert_not_called()
        manifest(root / 'manifest.json', dict(data, kind=runner.PACKAGE_KIND))
        with patch('anno1503_overhaul.beta_package.validate_beta_package', side_effect=ValueError('forged recipe')), patch('runpy.run_path') as execute:
            with self.assertRaises(ValueError):
                self.observed(script)
        execute.assert_not_called()

    def test_generic_installed_closure_accepts_recorded_version_without_current_pins(self):
        root, unused, data, digest = self.package()
        value = runner.validate_package_closure(root, digest, copy_root=self.base / 'game')
        self.assertEqual(value['version'], 'historical-version-owned')
        self.assertEqual(value['package_manifest_sha256'], digest)
        write(root / 'launcher/logs/run.jsonl', b'{"event":"test"}\n')
        runner.validate_package_closure(root, digest, copy_root=self.base / 'game')
        with self.assertRaises(runner.RunnerError):
            runner.validate_package_closure(root, digest, copy_root=self.base / 'other-game')
        write(root / 'launcher/extra.py', b'pass\n')
        with self.assertRaises(runner.RunnerError):
            runner.validate_package_closure(root, digest)

    def test_package_manifest_or_payload_change_is_refused(self):
        root, script, data, digest = self.package()
        write(script, b'changed')
        with self.assertRaises(runner.RunnerError):
            runner.validate_package_closure(root, digest)
        write(script, self.raw)
        manifest(root / 'manifest.json', dict(data, version='forged version'))
        with self.assertRaises(runner.RunnerError):
            runner.validate_package_closure(root, digest)

    def test_retained_worker_survives_release_removal_and_rejects_tampering(self):
        record = runner.retain_worker(self.app, self.base / 'cache')
        self.assertEqual(runner.retain_worker(self.app, self.base / 'cache'), record)
        worker = runner.verify_retained_worker(record)
        self.assertEqual(worker.name, runner.WORKER)
        self.assertFalse((worker.parent / 'tools/compiler').exists())
        self.script.unlink()
        self.assertEqual(self.observed(worker.parent / 'src/anno1503_overhaul/legacy_worker.py', root=worker.parent)['name'], '__main__')
        write(worker.parent / '_internal/python-runtime.bin', b'changed')
        with self.assertRaises(runner.RunnerError):
            runner.verify_retained_worker(record)

    def test_retention_preserves_unknown_existing_cache(self):
        record = runner.retain_worker(self.app, self.base / 'cache')
        sentinel = Path(record['runtime_root']) / 'independent.txt'
        write(sentinel, b'preserve this file')
        with self.assertRaises(runner.RunnerError):
            runner.retain_worker(self.app, self.base / 'cache')
        self.assertEqual(sentinel.read_bytes(), b'preserve this file')

    def test_changed_retained_gui_or_launcher_binding_is_refused(self):
        record = runner.retain_worker(self.app, self.base / 'cache')
        self.assertEqual(Path(record['launcher_path']).name, runner.LAUNCHER)
        with self.assertRaises(runner.RunnerError):
            runner.verify_retained_worker(dict(record, launcher_path=record['worker_path']))
        write(Path(record['launcher_path']), b'changed GUI executable')
        with self.assertRaises(runner.RunnerError):
            runner.verify_retained_worker(record)

    def test_too_long_runtime_cache_is_refused_before_copying(self):
        cache = self.base / ('long-cache-' + 'x' * 150)
        with self.assertRaises(runner.RunnerError):
            runner.retain_worker(self.app, cache)
        self.assertFalse(cache.exists())

    def test_worker_interpreter_is_bound_to_setup_and_needs_embedded_source_identity(self):
        with patch.object(sys, 'frozen', True, create=True):
            runner._trusted_release_sha256 = None
            with self.assertRaises(runner.RunnerError):
                runner.configure_worker(self.app)
            worker = runner.configure_worker(self.app, trusted_release_sha256=self.release_sha,
                expected_worker_sha256=sha((self.app / runner.WORKER).read_bytes()))
            self.assertEqual(sys.executable, str(worker))
            self.assertEqual(runner.source_script('legacy_worker.py', root=self.app), self.script)
            with self.assertRaises(runner.RunnerError):
                runner.configure_worker(self.app, expected_worker_sha256='0' * 64)

    def test_duplicate_json_keys_and_case_colliding_paths_are_refused(self):
        write(self.app / 'release-files.json', b'{"kind":"x","kind":"y"}')
        runner._trusted_release_sha256 = None
        with self.assertRaises(runner.RunnerError):
            runner.source_script('legacy_worker.py', root=self.app)
        manifest(self.app / 'release-files.json', dict(self.index, files={
            'src/anno1503_overhaul/legacy_worker.py': sha(self.raw),
            'src/anno1503_overhaul/Legacy_Worker.py': sha(self.raw)}))
        with self.assertRaises(runner.RunnerError):
            runner.source_script('legacy_worker.py', root=self.app)

    def test_reparse_attribute_refuses_script_before_execution(self):
        original = Path.lstat
        script = self.script
        def attributed(path, *args, **kwargs):
            value = original(path, *args, **kwargs)
            if path == script:
                return SimpleNamespace(st_mode=value.st_mode, st_file_attributes=0x400)
            return value
        with patch.object(Path, 'lstat', attributed), patch('runpy.run_path') as execute:
            with self.assertRaises(runner.RunnerError):
                self.observed()
        execute.assert_not_called()
    def test_unbuffered_child_output_is_visible_before_process_exit(self):
        raw = b'import time\nprint("ready")\ntime.sleep(.5)\nprint("finished")\n'
        write(self.script, raw)
        self.release_sha = manifest(self.app / 'release-files.json', dict(self.index,
            files={'src/anno1503_overhaul/legacy_worker.py': sha(raw)}))
        code = 'import sys;sys.path.insert(0,sys.argv.pop(1));from anno1503_overhaul.frozen_runner import dispatch;dispatch(sys.argv[1:],root=' + repr(str(self.app)) + ')'
        process = subprocess.Popen([sys.executable, '-B', '-c', code, str(ROOT / 'src'), '-B', '-u', str(self.script)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(process.stdout.readline().strip(), 'ready')
            self.assertIsNone(process.poll())
            self.assertEqual(process.communicate(timeout=10)[0].strip(), 'finished')
            self.assertEqual(process.returncode, 0)
        finally:
            if process.poll() is None:
                process.terminate();process.wait(timeout=5)

    def test_purpose_built_installer_cli_features_uses_production_parser_without_gui(self):
        output = io.StringIO()
        with patch.object(sys, 'frozen', True, create=True), \
             patch.object(runner, 'application_root', return_value=self.app), \
             patch('anno1503_overhaul.selector.main') as gui, patch.object(runner, 'dispatch') as generic, \
             redirect_stdout(output):
            self.assertEqual(runner.main(['--installer-cli', 'features']), 0)
        features = {item['id']:item for item in json.loads(output.getvalue())['features']}
        self.assertTrue(features['world_settings']['default_enabled'])
        self.assertFalse(features['food_overhaul']['default_enabled'])
        gui.assert_not_called();generic.assert_not_called()

    def test_invalid_installer_cli_command_returns_parser_failure_without_execution(self):
        before = (self.app / 'release-files.json').read_bytes()
        with patch.object(sys, 'frozen', True, create=True), \
             patch.object(runner, 'application_root', return_value=self.app), \
             patch('anno1503_overhaul.selector.main') as gui, patch.object(runner, 'dispatch') as generic:
            for args in ([], ['unknown-command'], ['-c', 'print(1)']):
                with self.subTest(args=args), redirect_stderr(io.StringIO()):
                    self.assertEqual(runner.main(['--installer-cli', *args]), 2)
        self.assertEqual((self.app / 'release-files.json').read_bytes(), before)
        gui.assert_not_called();generic.assert_not_called()


if __name__ == '__main__':
    unittest.main()
