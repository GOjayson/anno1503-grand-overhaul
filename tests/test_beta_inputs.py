"""Public beta reconstruction and cache trust; never runs or modifies Anno."""
import sys
sys.dont_write_bytecode = True
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from anno1503_overhaul import beta_inputs as b
from anno1503_overhaul import world_native as n


def sha(data):
    return hashlib.sha256(data).hexdigest()


class BetaCacheTrustTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='anno-beta-inputs-')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name).resolve()
        self.game = self.folder / 'game'; self.game.mkdir()
        self.compiler = self.folder / 'zig.exe'; self.compiler.write_bytes(b'synthetic compiler')
        self.output = self.folder / 'prepared'
        self.compiler_info = dict(path=str(self.compiler), sha256=sha(self.compiler.read_bytes()), version='0.16.0')
        self.selected = {}
        for name in {**b.native.STOCK_SHA256, 'AnnoDisplay.dll': b.DISPLAY_SHA256}:
            path = self.game / name; data = ('synthetic native ' + name).encode(); path.write_bytes(data)
            self.selected[name] = dict(path=path, sha256=sha(data), offset=None, patch=None)
        self.files = {'assets/WorldSettingsIslands/example.scp': b'synthetic island',
                      'ai-base/CompLogic.dll': b'synthetic predecessor',
                      'WorldSettingsAI/CompLogic.dll': b'synthetic derivative',
                      'runtime_engine_edits.json': b'{}\n'}
        self.prerequisites = dict(generator_id='synthetic recipe', historical_private_inputs_used=False)
        self.construct = patch.object(b, '_construction', return_value=(self.files, self.selected, self.prerequisites))
        self.construct.start(); self.addCleanup(self.construct.stop)
        self.compiler_patch = patch.object(b, '_compiler', return_value=self.compiler_info)
        self.compiler_patch.start(); self.addCleanup(self.compiler_patch.stop)

    def prepare(self):
        return b.prepare_beta_inputs(self.game, self.output, compiler_path=self.compiler)

    def test_preparation_keeps_source_separate_and_returns_explicit_builder_paths(self):
        before = {p.name: p.read_bytes() for p in self.game.iterdir()}
        value = self.prepare()
        self.assertEqual(value['native_host_root'], self.output / 'native-host')
        self.assertEqual(value['source_data_root'], self.game)
        self.assertEqual(value['assets_root'], self.output / 'assets')
        self.assertFalse(value['runtime_built'])
        self.assertIn('AnnoDisplay.dll', value['stock_native_bytes'])
        self.assertEqual(value['manifest']['introduced_files'],
                         {'WorldSettingsIslands/example.scp': 'assets/WorldSettingsIslands/example.scp'})
        checked = b.validate_beta_inputs(self.output, self.game)
        self.assertEqual(checked['manifest'], value['manifest'])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.game.iterdir()})

    def test_a_manifest_cannot_rebless_a_changed_payload(self):
        self.prepare()
        path = self.output / 'assets/WorldSettingsIslands/example.scp'; path.write_bytes(b'changed')
        manifest_path = self.output / b.MANIFEST
        manifest = json.loads(manifest_path.read_bytes())
        manifest['files']['assets/WorldSettingsIslands/example.scp'] = sha(b'changed')
        manifest['data_payloads']['assets/WorldSettingsIslands/example.scp'] = sha(b'changed')
        manifest_path.write_bytes(b._encoded(manifest))
        with self.assertRaises(b.BetaInputError):
            b.validate_beta_inputs(self.output, self.game)

    def test_unknown_files_and_duplicate_manifest_keys_are_refused(self):
        self.prepare(); extra = self.output / 'unexpected.txt'; extra.write_text('not owned')
        with self.assertRaises(b.BetaInputError): b.validate_beta_inputs(self.output)
        extra.unlink()
        path = self.output / b.MANIFEST
        path.write_bytes(path.read_bytes().replace(b'"schema": 1', b'"schema": 1, "schema": 1'))
        with self.assertRaisesRegex(b.BetaInputError, 'duplicate'):
            b.validate_beta_inputs(self.output)

    def test_existing_output_and_source_overlap_are_preserved(self):
        self.output.mkdir(); marker = self.output / 'keep.txt'; marker.write_text('preserve')
        with self.assertRaises(b.BetaInputError): self.prepare()
        self.assertEqual(marker.read_text(), 'preserve')
        with self.assertRaises(b.BetaInputError):
            b.prepare_beta_inputs(self.game, self.game / 'cache', compiler_path=self.compiler)
        self.assertFalse((self.game / 'cache').exists())

    def test_cache_is_bound_to_its_source_and_compiler(self):
        self.prepare(); other = self.folder / 'other'; other.mkdir()
        with self.assertRaises(b.BetaInputError): b.validate_beta_inputs(self.output, other)
        changed = {**self.compiler_info, 'sha256': '0' * 64}
        with patch.object(b, '_compiler', return_value=changed):
            with self.assertRaises(b.BetaInputError): b.validate_beta_inputs(self.output)


class BetaSourceProfileTests(unittest.TestCase):
    def test_only_coherent_stock_or_food05_native_sets_are_approved(self):
        with tempfile.TemporaryDirectory(prefix='anno-beta-source-') as folder:
            game = Path(folder)
            base = {'Anno1503.exe': b'exe', 'CompLogic.dll': b'ai', 'AnnoFrame.dll': b'frame'}
            food = {'CompLogic.dll': b'food ai', 'AnnoFrame.dll': b'food frame'}
            spec = {'native_modules': [dict(name=name, sources={'vanilla': sha(base[name]),
                     'combined-0.5.0': sha(data)}) for name, data in food.items()]}
            for name, data in {**base, 'AnnoDisplay.dll': b'display'}.items(): (game / name).write_bytes(data)
            with patch.dict(b.native.STOCK_SHA256, {name: sha(data) for name, data in base.items()}, clear=True), \
                 patch.object(b, 'DISPLAY_SHA256', sha(b'display')), patch.object(b.vanilla, '_spec', return_value=spec):
                self.assertEqual(b.verify_beta_source(game)['source_native_profile'], 'vanilla')
                (game / 'CompLogic.dll').write_bytes(food['CompLogic.dll'])
                with self.assertRaises(b.BetaInputError): b.verify_beta_source(game)
                (game / 'AnnoFrame.dll').write_bytes(food['AnnoFrame.dll'])
                self.assertEqual(b.verify_beta_source(game)['source_native_profile'], 'combined-0.5.0')
                (game / 'CompLogic.dll').write_bytes(b'unknown native changes')
                with self.assertRaises(b.BetaInputError): b.verify_beta_source(game)


class BetaCompilerWindowTests(unittest.TestCase):
    def test_version_probe_keeps_failure_checks_and_hides_only_windows_console(self):
        with tempfile.TemporaryDirectory()as folder:
            compiler=Path(folder)/'zig.exe';compiler.write_bytes(b'compiler fixture')
            for platform in ('nt','posix'):
                for code,version in ((0,'0.16.0\n'),(1,'0.16.0\n'),(0,'0.15.0\n')):
                    with (self.subTest(platform=platform,code=code,version=version),
                          patch.object(b,'os',SimpleNamespace(name=platform)),
                          patch.object(b.subprocess,'CREATE_NO_WINDOW',0x08000000,create=True),
                          patch.object(b.subprocess,'run',return_value=SimpleNamespace(returncode=code,stdout=version))as invoke):
                        if code or version.strip()!='0.16.0':
                            with self.assertRaises(b.BetaInputError):b._compiler(compiler)
                        else:self.assertEqual(b._compiler(compiler)['version'],'0.16.0')
                        options=invoke.call_args.kwargs
                        self.assertEqual({k:options[k]for k in ('capture_output','text','timeout','check')},
                                         dict(capture_output=True,text=True,timeout=15,check=False))
                        if platform=='nt':self.assertEqual(options['creationflags'],0x08000000)
                        else:self.assertNotIn('creationflags',options)


class PublicNativeConstructionTests(unittest.TestCase):
    def source(self):
        value = os.environ.get('ANNO1503_TEST_STOCK_GAME')
        game = Path(value) if value else ROOT / '.local/game-copies/World Settings'
        if not (game / 'CompLogic.dll').is_file():
            self.skipTest('Exact locally owned stock game inputs are unavailable.')
        return game

    def test_public_ai_outputs_match_existing_pins_without_reading_private_inputs(self):
        game = self.source()
        for name, digest in n.WORLD_ONLY_AI_SHA256.items():
            stock = (game / name).read_bytes()
            if sha(stock) != n._STOCK_AI_SHA256[name]: self.skipTest('The local host is not the supported stock native build.')
            with patch.object(Path, 'read_bytes', side_effect=AssertionError('AI constructor must use supplied bytes only.')):
                output = n.derive_public_ai_candidate(name, stock)
            self.assertEqual(sha(output), digest)
            with self.assertRaises(n.NativeProfileError): n.derive_public_ai_candidate(name, stock[:-1])

    def test_all_sixteen_assets_reproduce_the_published_data_fingerprints(self):
        game = self.source(); original = Path.read_bytes
        def guarded(path):
            if '/.local/baselines/' in path.as_posix() or '/.local/runtime-profiles/' in path.as_posix():
                raise AssertionError('Private developer payloads must not be inputs.')
            return original(path)
        with patch.object(Path, 'read_bytes', guarded):
            assets, proof = b.derive_beta_assets(game)
        self.assertEqual((len(assets), proof['pirate_assets'], proof['venetian_assets'], proof['venetian_buildings']),
                         (16, 15, 1, 73))
        for module in (b._source_module('pirate'), b._source_module('world')):
            for name, digest in module.data_payload_hashes().items(): self.assertEqual(sha(assets[name]), digest)


if __name__ == '__main__':
    unittest.main()
