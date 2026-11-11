"""Public-beta package boundaries with explicit synthetic native trust pins.

These fixtures exercise helper reconstruction, inventory/path checks and
publication. They do not claim a native build or original-game compatibility.
"""
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
import json
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from anno1503_overhaul import beta_package as beta, packages as common, world_native, beta_inputs


def pe(suffix):
    raw=bytearray(256);raw[:2]=b'MZ';struct.pack_into('<I',raw,60,128)
    raw[128:132]=b'PE\0\0';struct.pack_into('<H',raw,132,0x8664);struct.pack_into('<H',raw,152,0x20b)
    return bytes(raw)+suffix


class BetaPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.source=self.root/'game';self.source.mkdir()
        self.copy=self.root/'managed-copy';self.output=self.root/'package'
        self.exe=pe(b'exe');(self.source/'Anno1503.exe').write_bytes(self.exe)
        self.runtime=pe(b'reviewed-runtime');self.engine=b'fixture-engine-plan'
        self.natives={n:pe(n.encode())for n in beta._native_pins()}
        self.ai={n:pe(('reviewed-policy-'+n).encode())for n in ('CompLogic.dll','CompLogicClassic.dll')}
        self.assets={'assets/WorldSettingsIslands/Nord/fixture%d.scp'%i:('fixture-island%d'%i).encode()for i in range(16)}
        self.introduced={n.removeprefix('assets/'):n for n in self.assets}
        self.public=common._source_recipe(str(self.copy))
        stack=ExitStack();self.addCleanup(stack.close);self.stack=stack
        stack.enter_context(patch.object(beta,'_policy',return_value=common._sha(self.runtime)))
        stack.enter_context(patch.object(beta_inputs,'verify_beta_source',return_value=dict(
            source_native_profile='vanilla',source_native_sha256={'Anno1503.exe':common._sha(self.exe)})))
        stack.enter_context(patch.object(beta,'_native_pins',return_value={n:common._sha(v)for n,v in self.natives.items()}))
        stack.enter_context(patch.object(beta.native,'STOCK_SHA256',{'Anno1503.exe':common._sha(self.exe)}))
        stack.enter_context(patch.object(beta.native,'WORLD_ONLY_ENGINE_PLAN_SHA256',common._sha(self.engine)))
        stack.enter_context(patch.object(beta.native,'derive_engine_plan',return_value=self.engine))
        stack.enter_context(patch.object(common,'_source_recipe',side_effect=lambda *_a,**_k:dict(self.public)))
        stack.enter_context(patch.object(beta,'_asset_policy',return_value=(self.introduced,
            {n:common._sha(v)for n,v in self.assets.items()},{n:lambda *_:None for n in self.assets})))
        stack.enter_context(patch.object(world_native,'derive_public_ai_candidate',side_effect=lambda n,_:b'base-'+n.encode()))
        stack.enter_context(patch.object(beta,'derive_faction_ai',side_effect=lambda n,*_:(self.ai[n],{})))
        self.historical=stack.enter_context(patch.object(common,'_world_spec',side_effect=AssertionError('historical corpus opened')))

    def publish(self):
        files=beta._recipe(self.source,self.copy,self.natives,self.assets,self.ai,self.runtime)
        files['manifest.json']=common._encoded(beta._manifest(self.source,self.copy,files))
        return common._publish(files,self.output,self.source)

    def bless(self,name):
        path=self.output/'manifest.json';value=json.loads(path.read_bytes())
        value['files'][name]=common._sha((self.output/name).read_bytes());path.write_bytes(common._encoded(value))

    def test_new_kind_publishes_self_contained_helpers_and_exact_introduced_payloads(self):
        self.publish();value=common.validate_package(self.output,self.source)
        self.assertTrue(value['verified']);self.assertEqual(value['kind'],beta.KIND)
        self.assertFalse(value['food_enabled']);self.assertEqual(value['profile'],'world-only')
        spec=json.loads((self.output/'world/world_patch.json').read_bytes())
        self.assertEqual(len(spec['introduced_files']),19)
        self.assertTrue(spec['public_beta_source']);self.assertNotIn('frozen_world_spec_sha256',spec)
        self.assertNotIn('native_overlays',spec)
        self.assertFalse((self.output/'world/frozen_world_patch.json').exists())
        self.assertFalse((self.output/'world/frozen-inputs').exists())
        self.assertIn(b'inspect_owned_bootstrap',(self.output/'launcher/native_ready.py').read_bytes())
        self.historical.assert_not_called();self.assertFalse(self.copy.exists())
        self.assertEqual(list(self.source.iterdir()),[self.source/'Anno1503.exe'])

    def test_manifest_cannot_bless_modified_helper(self):
        self.publish();name='launcher/client_context.py';(self.output/name).write_bytes(b'changed helper')
        self.bless(name)
        with self.assertRaises(common.PackageError):beta.validate_beta_package(self.output)

    def test_manifest_cannot_bless_modified_runtime(self):
        self.publish();name='world/native/AnnoWorldSettings.dll';(self.output/name).write_bytes(pe(b'changed runtime'))
        self.bless(name)
        with self.assertRaises(common.PackageError):beta.validate_beta_package(self.output)

    def test_manifest_cannot_bless_modified_ai(self):
        self.publish();name='world/native/CompLogic.world-only.dll';(self.output/name).write_bytes(pe(b'changed AI'))
        self.bless(name)
        with self.assertRaises(common.PackageError):beta.validate_beta_package(self.output)

    def test_manifest_cannot_bless_modified_island(self):
        self.publish();name='world/'+next(iter(self.assets));(self.output/name).write_bytes(b'changed island')
        self.bless(name)
        with self.assertRaises(common.PackageError):beta.validate_beta_package(self.output)

    def test_unknown_or_foreign_manifest_generation_refused(self):
        self.publish();path=self.output/'manifest.json';raw=path.read_bytes();data=json.loads(raw)
        for field,value in (('kind','anno1503-world-options-installer-package'),('food_enabled',True),('profile','food-world')):
            with self.subTest(field=field):
                changed=dict(data);changed[field]=value;path.write_bytes(common._encoded(changed))
                with self.assertRaises(common.PackageError):beta.validate_beta_package(self.output)
        path.write_bytes(raw)

    def test_changed_source_executable_and_foreign_source_binding_are_refused(self):
        self.publish();(self.source/'Anno1503.exe').write_bytes(pe(b'foreign game'))
        with self.assertRaises(common.PackageError):beta.validate_beta_package(self.output)
        (self.source/'Anno1503.exe').write_bytes(self.exe)
        foreign=self.root/'foreign';foreign.mkdir()
        with self.assertRaises(common.PackageError):beta.validate_beta_package(self.output,foreign)

    def test_extra_file_and_directory_are_refused(self):
        self.publish()
        for directory in (False,True):
            name=self.output/('unexpected-folder'if directory else'unexpected.py')
            if directory:name.mkdir()
            else:name.write_bytes(b'unknown')
            with self.subTest(directory=directory),self.assertRaises(common.PackageError):
                beta.validate_beta_package(self.output)
            if directory:name.rmdir()
            else:name.unlink()

    def test_known_bounded_logs_are_mutable_but_do_not_bless_code(self):
        self.publish();logs=self.output/'launcher/logs';logs.mkdir();(logs/'fixture.jsonl').write_bytes(b'{}\n')
        self.assertTrue(beta.validate_beta_package(self.output)['verified'])

    def test_duplicate_manifest_fields_are_refused(self):
        self.publish();path=self.output/'manifest.json';raw=path.read_bytes()
        path.write_bytes(b'{"kind":"'+beta.KIND.encode()+b'",'+raw.lstrip()[1:])
        with self.assertRaises(common.PackageError):beta.validate_beta_package(self.output)

    def test_public_preparation_builds_from_new_inputs_without_a_private_provider(self):
        runtime_path=self.root/'candidate.dll';runtime_path.write_bytes(self.runtime)
        prepared=self.root/'new-inputs';assets=prepared/'assets';private=prepared/'WorldSettingsAI'
        for name,value in self.assets.items():
            path=assets/name.removeprefix('assets/');path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(value)
        private.mkdir(parents=True)
        for name,value in self.ai.items():(private/name).write_bytes(value)
        result=dict(root=prepared,assets_root=assets,private_ai_root=private,stock_native_bytes=self.natives)
        with (patch.object(beta_inputs,'prepare_beta_inputs',return_value=result)as inputs,
              patch.object(beta.options,'build_public_options_runtime',return_value=dict(runtime_path=str(runtime_path)))as build):
            path=beta.prepare_beta_package(self.output,self.source,self.copy,compiler_path=self.root/'zig.exe')
        self.assertEqual(path,self.output);self.assertTrue(beta.validate_beta_package(path)['verified'])
        args,kwargs=inputs.call_args
        self.assertEqual(args[0],self.source);self.assertEqual(kwargs,dict(compiler_path=self.root/'zig.exe'))
        self.assertRegex(args[1].parent.name,r'^build-[0-9a-f]{16}$')
        self.assertEqual(args[1].parent.parent,self.output.parent)
        self.assertEqual(build.call_args.args,(prepared,));self.assertEqual(build.call_args.kwargs['output'].name,'runtime')
        self.historical.assert_not_called()

    def test_existing_or_overlapping_output_is_preserved_before_preparation(self):
        self.output.mkdir();sentinel=self.output/'keep.txt';sentinel.write_bytes(b'preserved')
        for output in (self.output,self.source/'package',self.copy/'package'):
            with (self.subTest(output=output),patch.object(beta_inputs,'prepare_beta_inputs')as prepare,
                  self.assertRaises(common.PackageError)):
                beta.prepare_beta_package(output,self.source,self.copy,compiler_path=self.root/'zig.exe')
            prepare.assert_not_called()
        self.assertEqual(sentinel.read_bytes(),b'preserved')

    def test_short_workspace_does_not_repeat_the_package_name(self):
        output=self.root/('package-'+('p'*96))
        runtime=self.root/'runtime.dll';runtime.write_bytes(self.runtime)
        class StopPreparation(Exception):pass
        with (patch.object(beta_inputs,'prepare_beta_inputs',side_effect=StopPreparation)as prepare,
              self.assertRaises(StopPreparation)):
            beta.prepare_beta_package(output,self.source,self.copy,compiler_path=self.root/'zig.exe',runtime_path=runtime)
        workspace=prepare.call_args.args[1].parent
        self.assertRegex(workspace.name,r'^build-[0-9a-f]{16}$')
        self.assertEqual(workspace.parent,output.parent)
        self.assertNotIn(output.name,str(workspace))
        self.assertEqual(list(workspace.iterdir()),[])
        self.assertFalse(output.exists())

    def test_workspace_collision_and_copy_overlap_are_refused_before_preparation(self):
        fixed=SimpleNamespace(hex='a'*32);workspace=self.root/('build-'+('a'*16))
        workspace.mkdir();sentinel=workspace/'keep.txt';sentinel.write_bytes(b'preserve existing build')
        with (patch.object(beta.uuid,'uuid4',return_value=fixed),
              patch.object(beta_inputs,'prepare_beta_inputs')as prepare,self.assertRaises(common.PackageError)):
            beta.prepare_beta_package(self.output,self.source,self.copy,compiler_path=self.root/'zig.exe')
        prepare.assert_not_called();self.assertEqual(sentinel.read_bytes(),b'preserve existing build')
        second=SimpleNamespace(hex='b'*32);copy=self.root/('build-'+('b'*16))
        with (patch.object(beta.uuid,'uuid4',return_value=second),
              patch.object(beta_inputs,'prepare_beta_inputs')as prepare,self.assertRaises(common.PackageError)):
            beta.prepare_beta_package(self.output,self.source,copy,compiler_path=self.root/'zig.exe')
        prepare.assert_not_called();self.assertFalse(copy.exists())


if __name__=='__main__':unittest.main()
