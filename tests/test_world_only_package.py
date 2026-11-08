"""Package-boundary fixtures, with explicit synthetic native/runtime trust pins.

Native derivation and stock recovery are exercised separately by their own
tests. Here those stages return bounded fixture bytes while real public helper
recipes, immutable manifests, path guards and publication are exercised.
"""
from contextlib import ExitStack
import ast
import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from anno1503_overhaul import packages as common,world_only_package as world
from anno1503_overhaul import world_runtime_build as build


def native(machine=0x8664):
    data=bytearray(256);data[:2]=b'MZ';struct.pack_into('<I',data,60,128)
    data[128:132]=b'PE\0\0';struct.pack_into('<H',data,132,machine);struct.pack_into('<H',data,152,0x20b)
    return bytes(data)


class WorldOnlyPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.source=self.root/'source';self.source.mkdir()
        self.copy=self.root/'host-copy';self.output=self.root/'package'
        self.provider=self.root/'provider';self.runtime=self.root/'runtime.dll'
        self.runtime.write_bytes(native()+b'world-only-runtime')
        for _,(family,names)in common._LAYOUT.items():
            for name in names:
                data=(ROOT/'legacy'/family/name).read_bytes()
                if family=='world_settings'and name=='world_mod.py':
                    lines=data.splitlines(keepends=True)
                    at=next(i for i,line in enumerate(lines)if b'if spec.get("repository_source_snapshot", {}).get("source_only") is True:'in line)
                    del lines[at:at+2];data=b''.join(lines)
                dest=self.provider/family/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
        self.stock={name:native()+name.encode()for name in world._STOCK_NAMES}
        self.engine=b'{"fixture":"stock-engine-plan"}\n'
        self.frozen=dict(version='0.11.0-dev.1',status='UNFINISHED',
                         original_game_root='historical-input',payloads={},data_payloads={},introduced_files={},
                         exe_sha256=common._sha(native()),
                         expanded_engine_plan_sha256=common._sha((ROOT/'legacy/world_settings/developer/huge_world/runtime_engine_edits.json').read_bytes()))
        for name in common._NATIVE:
            self._payload(name,native()+name.encode())
        for i in range(16):
            path=f'assets/WorldSettingsIslands/Nord/fixture{i}.scp'
            self._payload(path,b'bounded-island-fixture'+bytes([i]))
            self.frozen['data_payloads'][path]=self.frozen['payloads'][path]
            self.frozen['introduced_files'][path.removeprefix('assets/')]=path
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self._pin()
        hashes={name:common._sha(value)for name,value in self.stock.items()}
        hashes['AnnoScene.dll']=self.frozen['payloads']['native/AnnoScene.source.dll']
        hashes['Anno1503.exe']=self.frozen['exe_sha256']
        self.stack.enter_context(patch.object(world,'_runtime_policy',return_value=(common._sha(self.runtime.read_bytes()),common._sha(self.engine),hashes)))
        self.stack.enter_context(patch.object(world,'_stock_inputs',return_value=self.stock))
        self.stack.enter_context(patch.object(build,'derive_engine_plan',return_value=self.engine))
        derived={f'WorldSettingsAI/{name}':value+b'world-policy'for name,value in self.stock.items()if name.startswith('CompLogic')}
        self.stack.enter_context(patch.object(world,'derive_native_profile',return_value=(derived,{'fixture':True})))

    def _payload(self,name,data):
        self.frozen['payloads'][name]=common._sha(data)
        path=self.provider/'world_settings'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)

    def _pin(self):
        raw=common._encoded(self.frozen)
        (self.provider/'world_settings/world_patch.json').write_bytes(raw)
        self.stack.enter_context(patch.object(common,'FROZEN_WORLD_SPEC_SHA256',common._sha(raw)))
        self.stack.enter_context(patch.object(common,'RUNTIME_SHA256',self.frozen['payloads']['native/AnnoWorldSettings.dll']))

    def prepare(self):
        return world.prepare_world_only_package(self.provider,self.output,self.source,self.copy,self.runtime)

    def test_world_only_targets_are_introduced_files_and_host_native_stays_stock(self):
        raw=(self.provider/'world_settings/world_patch.json').read_bytes()
        path=self.prepare();result=world.validate_world_only_package(path,self.source)
        self.assertTrue(result['verified']);self.assertFalse(result['food_enabled'])
        self.assertEqual(result['host_root'],str(self.copy));self.assertEqual(result['input_source_root'],str(self.source))
        spec=json.loads((path/'world/world_patch.json').read_bytes())
        self.assertEqual(spec['original_game_root'],str(self.copy));self.assertFalse(spec['food_enabled'])
        self.assertEqual(len(spec['introduced_files']),19)
        for name in world._STOCK_NAMES:
            self.assertNotIn(name,spec['introduced_files'])
            self.assertEqual((path/'world/stock'/name).read_bytes(),self.stock[name])
        self.assertNotIn('native_overlays',spec)
        self.assertEqual((path/'world/frozen_world_patch.json').read_bytes(),raw)
        self.assertFalse(self.copy.exists());self.assertEqual(list(self.source.iterdir()),[])
        self.assertNotIn('food_overhaul',result['feature_versions'])
        self.assertIn(b'mod.verify_activation',(path/'world/activation/preflight.py').read_bytes())
        self.assertEqual((path/'world/world_mod.py').read_bytes(),(ROOT/'src/anno1503_overhaul/world_only_backend.py').read_bytes())

    def test_manifest_cannot_bless_a_changed_runtime(self):
        self.prepare();path=self.output/'world/native/AnnoWorldSettings.dll'
        path.write_bytes(native()+b'changed-runtime')
        self._bless_manifest('world/native/AnnoWorldSettings.dll')
        with self.assertRaises(common.PackageError):world.validate_world_only_package(self.output)

    def test_copy_probe_is_stock_by_default_and_source_probe_is_instance_bound(self):
        self.prepare()
        text=(self.output/'launcher/native_ready.py').read_bytes()
        tree=ast.parse(text)
        cls=next(node for node in tree.body if isinstance(node,ast.ClassDef)and node.name=='NativeReadiness')
        ctor=next(node for node in cls.body if isinstance(node,ast.FunctionDef)and node.name=='__init__')
        stock='dfd7c76dfc0b017fa5142c46a2bb084c01fc750a049d85ca70b56dca2f555ccd'
        food='046b5ad6f351dfe867ed38ce29fb50a594485b43a32ee90adadc48e850466baf'
        namespace=dict(os=SimpleNamespace(name='nt'),C=SimpleNamespace(c_void_p=object(),sizeof=lambda _:8),
                       Path=Path,FRAME_SHA256=stock,_activation=lambda _:None,_window_api=lambda:{})
        exec(compile(ast.Module(body=[ctor],type_ignores=[]),'<derived readiness constructor>','exec'),namespace)
        build_probe=namespace['__init__'];a,b=SimpleNamespace(),SimpleNamespace()
        build_probe(a,self.output/'world',{'native_sha256':{'AnnoFrame.dll':stock}})
        build_probe(b,self.output/'world',{'native_sha256':{'AnnoFrame.dll':food}},frame_sha=food)
        self.assertEqual((a.frame_sha,b.frame_sha),(stock,food));self.assertEqual(namespace['FRAME_SHA256'],stock)
        with self.assertRaises(RuntimeError):
            build_probe(SimpleNamespace(),self.output/'world',{'native_sha256':{'AnnoFrame.dll':food}})
        with self.assertRaises(RuntimeError):
            build_probe(SimpleNamespace(),self.output/'world',{'native_sha256':{'AnnoFrame.dll':'0'*64}},frame_sha='0'*64)
        inspect=next(node for node in cls.body if isinstance(node,ast.FunctionDef)and node.name=='inspect')
        self.assertIn('self.frame_sha',ast.unparse(inspect))

    def test_normal_client_handoff_code_is_pinned_flat_and_separate_from_activation(self):
        self.prepare()
        text=(self.output/'launcher/launch_world_settings.pyw').read_bytes()
        self.assertIn(b'self.find_uri(self.normal_source)',text)
        self.assertIn(b"start_game(self.uri,self.normal_source,self.inputs['source'],self.source_probe",text)
        self.assertIn(b'copy_probe=self.native',text)
        self.assertNotIn(b'os.startfile(self.uri)',text)
        self.assertIn(b'self.source_probe.close()',text)
        context=(self.output/'launcher/client_context.py').read_bytes()
        self.assertIn(b'from managed_filesystem import ',context)
        self.assertNotIn(b'from .filesystem import ',context)
        self.assertEqual((self.output/'launcher/managed_processes.py').read_bytes(),(ROOT/'src/anno1503_overhaul/processes.py').read_bytes())

    def test_manifest_cannot_bless_changed_backend_code(self):
        self.prepare();path=self.output/'world/world_mod.py';path.write_bytes(path.read_bytes()+b'\n# unexpected\n')
        self._bless_manifest('world/world_mod.py')
        with self.assertRaises(common.PackageError):world.validate_world_only_package(self.output)

    def test_manifest_cannot_bless_changed_stock_input_or_frozen_corpus(self):
        self.prepare()
        for relative in ('world/stock/AnnoGame.dll','world/frozen-inputs/native/AnnoFrame.world.dll'):
            path=self.output/relative;original=path.read_bytes();path.write_bytes(original+b'!');self._bless_manifest(relative)
            with self.assertRaises(common.PackageError):world.validate_world_only_package(self.output)
            path.write_bytes(original);self._bless_manifest(relative)

    def _bless_manifest(self,relative):
        path=self.output/'manifest.json';record=json.loads(path.read_bytes())
        record['files'][relative]=common._sha((self.output/relative).read_bytes());path.write_bytes(common._encoded(record))

    def test_unreviewed_provider_python_is_not_copied_or_executed(self):
        path=self.provider/'launcher/activation_once.py';path.write_bytes(b'raise RuntimeError("provider must not run")')
        with self.assertRaises(common.PackageError):self.prepare()
        self.assertFalse(self.output.exists());self.assertFalse(self.copy.exists())

    def test_runtime_architecture_is_checked_even_with_fixture_hash_pin(self):
        self.runtime.write_bytes(native(0x14c)+b'world-only-runtime')
        hashes={name:common._sha(value)for name,value in self.stock.items()}
        with patch.object(world,'_runtime_policy',return_value=(common._sha(self.runtime.read_bytes()),common._sha(self.engine),hashes)):
            with self.assertRaisesRegex(common.PackageError,'AMD64'):self.prepare()
        self.assertFalse(self.output.exists())

    def test_derived_engine_plan_cannot_be_substituted(self):
        with patch.object(build,'derive_engine_plan',return_value=b'other-plan'):
            with self.assertRaises(common.PackageError):self.prepare()
        self.assertFalse(self.output.exists())

    def test_unknown_files_and_directories_are_refused(self):
        self.prepare();extra=self.output/'arbitrary';extra.mkdir()
        with self.assertRaises(common.PackageError):world.validate_world_only_package(self.output)
        extra.rmdir();(self.output/'extra.py').write_text('pass')
        with self.assertRaises(common.PackageError):world.validate_world_only_package(self.output)

    def test_bounded_diagnostics_are_allowed_but_not_executable_files(self):
        self.prepare();logs=self.output/'launcher/logs';logs.mkdir()
        (logs/'startup.jsonl').write_text('{}\n');(self.output/'world/activation_session.json').write_text('{}')
        self.assertTrue(world.validate_world_only_package(self.output)['verified'])
        (logs/'startup.py').write_text('pass')
        with self.assertRaises(common.PackageError):world.validate_world_only_package(self.output)

    def test_source_binding_and_source_as_host_are_refused(self):
        self.prepare();other=self.root/'other';other.mkdir()
        with self.assertRaises(common.PackageError):world.validate_world_only_package(self.output,other)
        with self.assertRaises(common.PackageError):world.prepare_world_only_package(self.provider,self.root/'other-package',self.source,self.source,self.runtime)

    def test_outputs_cannot_replace_or_enter_source_baselines_or_existing_package(self):
        self.prepare()
        for output in (self.output,self.source/'package',self.provider/'package',self.copy):
            with self.subTest(output=output),self.assertRaises(common.PackageError):
                world.prepare_world_only_package(self.provider,output,self.source,self.copy,self.runtime)

    def test_linked_package_file_is_refused(self):
        self.prepare();path=self.output/'world/native/AnnoWorldSettings.dll';target=self.root/'outside.dll'
        shutil.copyfile(path,target);path.unlink()
        try:path.symlink_to(target)
        except OSError:self.skipTest('Creating symbolic links requires Windows privileges.')
        with self.assertRaises(common.PackageError):world.validate_world_only_package(self.output)


if __name__=='__main__':unittest.main()
