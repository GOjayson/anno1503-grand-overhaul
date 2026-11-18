"""Distribution assembly policy and shared-runtime spec; no freezing or game."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('beta_bundle_builder', ROOT / 'tools/build_beta_bundle.py')
builder = importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)


class BetaBundle(unittest.TestCase):
    def test_public_selection_contains_runtime_sources_without_private_or_native_inputs(self):
        files = builder.public_inventory(ROOT)
        self.assertIn('src/anno1503_overhaul/frozen_runner.py', files)
        self.assertIn('tools/beta_entry.py', files)
        self.assertIn('provenance/legacy_import.json', files)
        self.assertTrue({'LICENSE', 'CODE_OF_CONDUCT.md', 'CONTRIBUTING.md',
                         'SECURITY.md', 'ACCESSIBILITY.md'} <= files.keys())
        self.assertTrue(all(not n.startswith(('.local/', 'tests/', '.git/')) for n in files))
        self.assertTrue(all(Path(n).suffix.lower() not in builder.FORBIDDEN for n in files))

    def test_modular_release_requires_food_artwork_c_and_the_reviewed_world_source_closure(self):
        files = builder.public_inventory(ROOT)
        for name in ('src/anno1503_overhaul/native/food_household.c',
                     'src/anno1503_overhaul/ambient_sound_baselines.py',
                     'src/anno1503_overhaul/food_world_package.py',
                     'src/anno1503_overhaul/food_world_public.py',
                     'src/anno1503_overhaul/food_world_public_ai.py',
                     'legacy/food_overhaul/assets/potatoes_icon.json',
                     'legacy/world_settings/developer/source/engine_resume/ai_food/make_market_candidate.py',
                     'legacy/world_settings/developer/source/runtime_dev3/compiled_hooks.c'):
            with self.subTest(missing=name):
                incomplete = {key: value for key, value in files.items() if key != name}
                with self.assertRaisesRegex(ValueError, 'incomplete|source closure'):
                    builder.validate_release_sources(ROOT, incomplete)
        altered = dict(files)
        altered['legacy/food_overhaul/assets/fish_icon.json'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'authored Food artwork'):
            builder.validate_release_sources(ROOT, altered)

    def test_release_index_records_independent_feature_versions_without_game_payloads(self):
        sys.path.insert(0, str(ROOT / 'src'))
        from anno1503_overhaul.food_diet import VERSION as food_version
        from anno1503_overhaul.food_world_bug_fixes import VERSION as fixes_version
        from anno1503_overhaul.world_options import VERSION as world_version
        files = {'fixture.py': 'a' * 64}
        index = builder.release_index(files)
        self.assertEqual(index['version'], '0.10.0-beta.1')
        self.assertEqual(index['feature_versions'], dict(food_overhaul=food_version,
            bug_fixes=fixes_version, world_settings=world_version))
        self.assertIs(index['files'], files)
        self.assertFalse(index['game_files_distributed'])
        self.assertTrue(index['food_requires_new_world'])
        self.assertEqual(builder.release_index(files, version='0.10.0-beta.2')['version'], '0.10.0-beta.2')
        for value in (None, 10, '../release', '0.10.0', '0.10.0-beta.0'):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'release version'):
                builder.release_index(files, version=value)

    def test_bundle_requires_the_exact_food_compiler_before_it_can_be_run(self):
        with tempfile.TemporaryDirectory(prefix='anno-bundle-compiler-') as folder:
            root = Path(folder)
            source = root / 'src/anno1503_overhaul/food_household.py'
            source.parent.mkdir(parents=True)
            compiler = root / 'zig.exe'
            compiler.write_bytes(b'non-executable reviewed compiler fixture')
            expected = builder.sha(compiler)
            source.write_text('COMPILER_SHA256 = ' + repr(expected) + '\n')
            self.assertEqual(builder.verify_food_compiler(compiler, root), expected)
            compiler.write_bytes(b'different compiler reporting the same version')
            with self.assertRaisesRegex(RuntimeError, 'exact Zig compiler'):
                builder.verify_food_compiler(compiler, root)
            source.write_text('COMPILER_SHA256 = None\n')
            with self.assertRaisesRegex(RuntimeError, 'identity is missing'):
                builder.verify_food_compiler(compiler, root)

    def test_spec_uses_two_executables_one_shared_runtime_and_sealed_worker_identity(self):
        text = builder.spec_text(Path('entry.py'), Path('src'), Path('deps'))
        compile(text, '<generated beta spec>', 'exec')
        self.assertEqual(text.count('a=Analysis('), 1)
        self.assertEqual(text.count('pyz=PYZ('), 1)
        self.assertEqual(text.count('contents_directory=\'_internal\''), 2)
        self.assertIn("name='Anno1503OverhaulSetup'", text)
        self.assertIn("name='OverhaulWorker'", text)
        self.assertIn('EXPECTED_WORKER_SHA256 = ', text)
        self.assertIn("collect_all('capstone')", text)
        for module in ('queue','_queue','heapq','_heapq','ctypes.wintypes'):
            self.assertIn(repr(module), text)
        self.assertNotIn('onefile=True', text)

    def test_external_scripts_and_nested_standard_dependencies_are_collected(self):
        value = builder.external_imports(ROOT, builder.public_inventory(ROOT))
        self.assertTrue({'legacy/launcher/launch_world_settings.pyw', 'legacy/launcher/activation_once.py',
                         'src/anno1503_overhaul/legacy_worker.py',
                         'legacy/world_settings/activation/activate_world_settings.py'} <= set(value['source_files']))
        self.assertFalse(any('/test_' in name for name in value['source_files']))
        required = {'queue','_queue','heapq','_heapq','ctypes.wintypes','winreg','tkinter.ttk',
                    'decimal','csv','base64','subprocess','threading','datetime','pefile','capstone',
                    'html','fractions','dataclasses'}
        self.assertTrue(required <= set(value['modules']))
        text = builder.spec_text(Path('entry.py'), Path('src'), Path('deps'), value['modules'])
        compile(text, '<external-import beta spec>', 'exec')
        self.assertTrue(all(repr(name) in text for name in required))

    def test_offline_license_files_are_complete_and_hashed_in_notices(self):
        class Metadata(dict):
            def get_all(self, key):
                return self.get(key)
        class Distribution:
            def __init__(self, root, name, version, filename, text):
                self.root, self.version = root, version
                self.files = [Path('licenses') / filename]
                self.metadata = Metadata(Name=name, **{'Home-page':'https://example.invalid/' + name})
                path = self.locate_file(self.files[0]);path.parent.mkdir(parents=True);path.write_bytes(text)
            def locate_file(self, name):
                return self.root / name
        with tempfile.TemporaryDirectory(prefix='anno-beta-license-') as folder:
            root = Path(folder);bundle = root / 'bundle';python = root / 'python';compiler = root / 'zig'
            python.mkdir();compiler.mkdir();(python / 'LICENSE.txt').write_bytes(b'Exact Python runtime notices\n')
            (compiler / 'LICENSE').write_bytes(b'Exact Zig MIT license\n')
            tcl = bundle / '_internal/_tcl_data';tk = bundle / '_internal/_tk_data'
            tcl.mkdir(parents=True);tk.mkdir(parents=True)
            (tcl / 'init.tcl').write_text('package require -exact Tcl 8.6.15\n')
            (tk / 'tk.tcl').write_text('package require -exact Tk  8.6.15\n')
            (tk / 'license.terms').write_bytes(b'Exact installed Tcl/Tk terms\r\n')
            packages = {
                'pyinstaller':Distribution(root / 'user-site', 'pyinstaller', '6.16.0', 'COPYING.txt', b'GPL terms\nBootloader Exception\n'),
                'pefile':Distribution(root / 'pefile-site', 'pefile', '2024.8.26', 'LICENSE', b'MIT terms\n'),
                'capstone':Distribution(root / 'capstone-site', 'capstone', '5.0.9', 'LICENSE.TXT', b'BSD terms\n'),
            }
            report = builder._license_copy(bundle, root / 'dependencies', python_root=python,
                compiler_root=compiler, distribution_resolver=packages.__getitem__)
            value = json.loads((bundle / 'licenses/third-party-manifest.json').read_bytes())
            self.assertEqual(len(value['components']), 6)
            self.assertEqual(report['manifest_sha256'], builder.sha(bundle / 'licenses/third-party-manifest.json'))
            names = {n for item in value['components'] for n in item['license_files']}
            self.assertEqual(names, {'licenses/Python.txt', 'licenses/PyInstaller.txt', 'licenses/pefile.txt',
                                     'licenses/Capstone.txt', 'licenses/TclTk.txt', 'licenses/Zig.txt'})
            for item in value['components']:
                for name, digest in item['license_files'].items():
                    self.assertEqual(hashlib.sha256((bundle / name).read_bytes()).hexdigest(), digest)
            self.assertIn(b'Bootloader Exception', (bundle / 'licenses/PyInstaller.txt').read_bytes())
            self.assertEqual((bundle / 'licenses/TclTk.txt').read_bytes(), (tk / 'license.terms').read_bytes())
            self.assertIn('pefile 2024.8.26', (bundle / 'THIRD_PARTY.txt').read_text())
            self.assertNotIn(str(root), (bundle / 'THIRD_PARTY.txt').read_text())
            with patch('importlib.metadata.distributions', return_value=[]), \
                 patch('importlib.metadata.distribution', return_value=packages['pyinstaller']) as fallback:
                self.assertIs(builder._offline_distribution('pyinstaller', root / 'dependencies'), packages['pyinstaller'])
            fallback.assert_called_once_with('pyinstaller')
            packages['pyinstaller'].locate_file(packages['pyinstaller'].files[0]).write_bytes(b'GPL without exception text\n')
            with self.assertRaisesRegex(RuntimeError, 'Bootloader Exception'):
                builder._license_copy(bundle, root / 'dependencies', python_root=python,
                    compiler_root=compiler, distribution_resolver=packages.__getitem__)


if __name__ == '__main__':
    unittest.main()
