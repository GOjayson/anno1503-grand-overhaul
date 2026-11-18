"""Public combined package guards with synthetic native boundaries.

Compilation and original/native derivation are substituted explicitly here;
the byte recipe, closed helper inventory and refusal paths are real. Actual
native construction has separate build evidence, never implied by fixtures.
"""
import ast
import json
from pathlib import Path
import sys
import tempfile
from contextlib import ExitStack
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from anno1503_overhaul import food_world_public as public, packages as common
from anno1503_overhaul import food_world_package as combined, food_world_runtime as native
import test_food_world_package as fixtures
import test_world_only_package as world_fixtures


class PublicFoodWorldTests(unittest.TestCase):
    _payload = fixtures.FoodWorldPackageTests._payload
    _pin = fixtures.FoodWorldPackageTests._pin

    def setUp(self):
        fixtures.FoodWorldPackageTests.setUp(self)
        self.source_proof = dict(source_native_profile='vanilla', source_native_sha256={'Anno1503.exe':self.host['Anno1503.exe']},
                                 source_recovery_files=[])
        self.originals = dict(self.stock)
        self.originals['Anno1503.exe'] = world_fixtures.native()
        self.assets = {name:(self.provider/'world_settings'/name).read_bytes() for name in self.frozen['data_payloads']}
        self.stack.enter_context(patch.object(public, '_originals', return_value=(self.originals,self.source_proof)))
        self.host_builder = self.stack.enter_context(patch.object(public, '_native_host', return_value=self.originals))
        self.stack.enter_context(patch.object(public, '_private_ai', return_value=(self.ai,{'fixture':True})))
        self.stack.enter_context(patch.object(public.beta_inputs, 'derive_beta_assets', return_value=(self.assets,{'fixture':True})))
        policy = (dict(self.frozen['introduced_files']), dict(self.frozen['data_payloads']), {name:lambda *_:None for name in self.assets})
        self.stack.enter_context(patch.object(public.beta_package, '_asset_policy', return_value=policy))
        self.private_spec = self.stack.enter_context(patch.object(common,'_world_spec',side_effect=AssertionError('private frozen corpus read')))
        self.private_runtime = self.stack.enter_context(patch.object(combined,'_runtime_path',side_effect=AssertionError('private runtime profile read')))
        self.runtime_builder = self.stack.enter_context(patch.object(native,'build_public_food_world_runtime',
            return_value=dict(runtime_path=str(self.runtime))))

    def prepare(self, enabled=False):
        return public.prepare_public_food_world_package(self.output,self.source,self.copy,
            compiler_path=self.compiler,bug_fixes_enabled=enabled)

    def bless(self, name):
        path=self.output/'manifest.json'
        manifest=json.loads(path.read_bytes())
        manifest['files'][name]=common._sha((self.output/name).read_bytes())
        path.write_bytes(common._encoded(manifest))

    def test_public_build_has_exact_combined_profile_and_no_historical_corpus(self):
        self.prepare()
        value=common.validate_package(self.output,self.source)
        self.assertEqual(value['kind'],public.KIND)
        self.assertEqual(value['profile'],'food06-world')
        self.assertTrue(value['food_enabled'])
        self.assertTrue(value['public_beta_source'])
        self.assertFalse(value['historical_private_inputs_used'])
        self.assertEqual(value['runtime_sha256'],self.runtime_pin)
        self.assertEqual(value['feature_versions'],{'food_overhaul':public.VERSION,'world_settings':public.WORLD_VERSION})
        spec=json.loads((self.output/'world/world_patch.json').read_bytes())
        self.assertEqual(spec['native_sha256'],self.host)
        self.assertEqual(len(spec['introduced_files']),19)
        self.assertEqual(spec['food_files'],public.food_files())
        self.assertNotIn('frozen_world_spec_sha256',spec)
        self.assertFalse((self.output/'world/frozen-inputs').exists())
        self.assertFalse((self.output/'world/frozen_world_patch.json').exists())
        self.private_spec.assert_not_called();self.private_runtime.assert_not_called()
        self.assertFalse(self.copy.exists());self.assertEqual(list(self.source.iterdir()),[])

    def test_public_build_passes_only_explicit_fresh_host_assets_and_compiler(self):
        self.prepare()
        args,kwargs=self.runtime_builder.call_args
        host,source,assets,compiler,ai=args
        self.assertEqual(source,self.source);self.assertEqual(compiler,self.compiler)
        self.assertEqual(host.parent,assets.parent)
        self.assertRegex(host.parent.name,r'^build-food-world-[0-9a-f]{16}$')
        self.assertEqual(kwargs['output'],host.parent/'runtime')
        self.assertEqual(kwargs['source_proof'],{name:self.source_proof[name] for name in ('source_native_profile','source_native_sha256')})
        self.assertEqual(ai[0],self.ai)
        self.assertEqual({item.name for item in host.iterdir()},set(self.originals))
        for name,value in self.originals.items():self.assertEqual((host/name).read_bytes(),value)

    def test_public_helpers_food_outputs_runtime_ai_and_assets_cannot_be_blessed(self):
        self.prepare()
        names=('world/native/AnnoWorldSettings.dll','world/native/CompLogic.food06.dll',
               'food/native/View.food06.dll','world/food_mod.py','world/support/food_world_policy.py',
               'launcher/source_readiness.py','world/'+next(iter(self.assets)))
        for name in names:
            with self.subTest(name=name):
                path=self.output/name;original=path.read_bytes();path.write_bytes(original+b'unreviewed');self.bless(name)
                with self.assertRaises(common.PackageError):public.validate_public_food_world_package(self.output)
                path.write_bytes(original);self.bless(name)

    def test_public_manifest_cannot_change_profile_food_or_private_input_claim(self):
        self.prepare();path=self.output/'manifest.json';original=path.read_bytes()
        for key,value in (('kind',combined.KIND),('profile','world-only'),('food_enabled',False),
                          ('public_beta_source',False),('historical_private_inputs_used',True)):
            with self.subTest(key=key):
                manifest=json.loads(original);manifest[key]=value;path.write_bytes(common._encoded(manifest))
                with self.assertRaises(common.PackageError):public.validate_public_food_world_package(self.output)
        path.write_bytes(original)

    def test_optional_bug_fixes_uses_exact_asset_recipe_with_food_and_world(self):
        recipe=world_fixtures.bug_fix_recipe_fixture(self.stack)
        self.prepare(True)
        checked=common.validate_package(self.output,self.source)
        self.assertTrue(checked['bug_fixes_enabled']);self.assertTrue(checked['food_enabled'])
        self.assertTrue(checked['city_statistics_guard'])
        self.assertEqual((self.output/public.food.WELT_PAYLOAD).read_bytes(), self.guarded_welt)
        self.assertEqual(checked['feature_versions']['bug_fixes'],'1.2')
        spec=json.loads((self.output/'world/world_patch.json').read_bytes())
        self.assertEqual(spec['bug_fixes'],recipe)
        self.assertEqual(spec['native_sha256'],self.guarded_host)
        for item in (self.output/'world/support').glob('_combined_*.py'):
            ast.parse(item.read_bytes())
        changed=self.output/'world/support/_combined_bugfix_recipe.py'
        changed.write_bytes(changed.read_bytes()+b'\n# modified\n')
        self.bless(changed.relative_to(self.output).as_posix())
        with self.assertRaises(common.PackageError):common.validate_package(self.output,self.source)

    def test_invalid_bug_fix_selection_refuses_before_build(self):
        for flag in (None,'true',1):
            with self.subTest(flag=flag),self.assertRaises(common.PackageError):self.prepare(flag)
        self.runtime_builder.assert_not_called();self.view_builder.assert_not_called()

    def test_unknown_files_or_directories_and_wrong_source_are_refused(self):
        self.prepare()
        with self.assertRaises(common.PackageError):public.validate_public_food_world_package(self.output,self.copy)
        for is_dir in (False,True):
            path=self.output/('unexpected-folder' if is_dir else 'unexpected.py')
            if is_dir:path.mkdir()
            else:path.write_bytes(b'pass')
            with self.assertRaises(common.PackageError):public.validate_public_food_world_package(self.output)
            if is_dir:path.rmdir()
            else:path.unlink()

    def test_existing_and_overlapping_outputs_preserved_before_build(self):
        self.output.mkdir();sentinel=self.output/'keep';sentinel.write_bytes(b'keep')
        for output in (self.output,self.source/'package',self.copy/'package'):
            with self.subTest(output=output),self.assertRaises(common.PackageError):
                public.prepare_public_food_world_package(output,self.source,self.copy,compiler_path=self.compiler)
        self.assertEqual(sentinel.read_bytes(),b'keep');self.view_builder.assert_not_called()


class PublicRuntimeInputTests(unittest.TestCase):
    """Guards run before compilation; this fixture does not produce a DLL."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.host=self.root/'host';self.host.mkdir()
        self.source=self.root/'source';self.source.mkdir()
        (self.host/'fixture.dll').write_bytes(b'bounded native input')
        self.assets=self.root/'assets';(self.assets/'WorldSettingsIslands/Nord').mkdir(parents=True)
        (self.assets/'WorldSettingsIslands/Nord/fixture.scp').write_bytes(b'exact island')
        self.compiler=self.root/'zig.exe';self.compiler.write_bytes(b'fixture compiler')
        self.proof=dict(source_native_profile='vanilla',source_native_sha256={'fixture':'a'*64})
        self.ai={'CompLogic.dll':b'private AI1','CompLogicClassic.dll':b'private AI2'}
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        from anno1503_overhaul import food_household, food_world_ai
        self.stack.enter_context(patch.object(public.beta_inputs,'verify_beta_source',return_value=self.proof))
        self.stack.enter_context(patch.object(public.beta_inputs,'derive_beta_assets',return_value=(
            {'assets/WorldSettingsIslands/Nord/fixture.scp':b'exact island'},{'fixture':True})))
        self.stack.enter_context(patch.object(food_household,'_compiler',return_value=(self.compiler,{})))
        self.stack.enter_context(patch.object(native,'HOST_SHA256',{'fixture.dll':common._sha(b'bounded native input')}))
        self.stack.enter_context(patch.object(food_world_ai,'OUTPUT_SHA256',{name:common._sha(value) for name,value in self.ai.items()}))
        self.builder=self.stack.enter_context(patch.object(native.options,'_build_options_runtime',return_value={'matches_reviewed_runtime':True}))

    def build(self,**changes):
        values=dict(game=self.host,source_game=self.source,assets_root=self.assets,compiler_path=self.compiler,
                    activity_inputs=(self.ai,{}),output=self.root/'build',source_proof=self.proof)
        values.update(changes)
        return native.build_public_food_world_runtime(**values)

    def test_exact_public_inputs_have_explicit_profile_source_assets_and_no_private_fallback(self):
        with patch.object(native,'derive_activity_ai_inputs',side_effect=AssertionError('private AI lookup')):
            self.build()
        inputs=self.builder.call_args.kwargs['_public_inputs']
        self.assertEqual(inputs['profile'],'food06-world')
        self.assertEqual(inputs['verified']['source_data_root'],self.source)
        self.assertEqual(inputs['verified']['assets_root'],self.assets)
        self.assertEqual(inputs['verified']['compiler_path'],self.compiler)
        self.assertFalse(inputs['verified']['manifest']['historical_private_inputs_used'])
        self.assertEqual(inputs['activity_inputs'][0],self.ai)

    def test_foreign_profile_source_or_ai_refuses_before_compilation(self):
        for changes in (dict(source_proof={}),dict(activity_inputs=({'CompLogic.dll':b'unknown'},{})),dict(game=self.source)):
            with self.subTest(changes=changes),self.assertRaises(native.base.RuntimeBuildError):self.build(**changes)
        self.builder.assert_not_called()

    def test_unexpected_island_inputs_directories_and_host_members_refuse(self):
        for path,is_dir in ((self.assets/'unreviewed.py',False),(self.assets/'empty',True),(self.host/'extra.dll',False)):
            if is_dir:path.mkdir()
            else:path.write_bytes(b'unknown')
            with self.subTest(path=path),self.assertRaises(native.base.RuntimeBuildError):self.build()
            if is_dir:path.rmdir()
            else:path.unlink()
        self.builder.assert_not_called()

    def test_changed_island_or_unreviewed_runtime_refuses(self):
        path=self.assets/'WorldSettingsIslands/Nord/fixture.scp';path.write_bytes(b'changed')
        with self.assertRaises(native.base.RuntimeBuildError):self.build()
        self.builder.assert_not_called();path.write_bytes(b'exact island')
        self.builder.return_value={'matches_reviewed_runtime':False}
        with self.assertRaises(native.base.RuntimeBuildError):self.build()


if __name__=='__main__':unittest.main()
