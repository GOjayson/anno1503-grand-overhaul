"""Pinned local package for World Settings with a stock native/data host.

The frozen combined package is an input corpus, never an executable provider.
World-only helpers come from the reviewed checkout. Every use recomputes its
recipe, native AI derivation, stock fingerprints and exact runtime/engine pins.
"""
from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import re
import shutil
import uuid

from . import packages as common
from .vanilla import plan_vanilla_recovery
from .world_native import derive_native_profile


ROOT = Path(__file__).resolve().parents[2]
KIND = 'anno1503-world-only-installer-package'
PROFILE = 'world-only-0.3.0'
VERSION = '1.0'
_STOCK_NAMES = ('AnnoGame.dll','AnnoWelt.dll','View.dll','AnnoFrame.dll','CompLogic.dll','CompLogicClassic.dll')


def _runtime_policy():
    from .world_runtime_build import WORLD_ONLY_RUNTIME_SHA256, WORLD_ONLY_ENGINE_PLAN_SHA256, STOCK_SHA256
    if any(not re.fullmatch('[0-9a-f]{64}',value) for value in (WORLD_ONLY_RUNTIME_SHA256,WORLD_ONLY_ENGINE_PLAN_SHA256)):
        raise common.PackageError('The reviewed World-only runtime build is not available yet.')
    return WORLD_ONLY_RUNTIME_SHA256, WORLD_ONLY_ENGINE_PLAN_SHA256, STOCK_SHA256


def _source(name: str) -> bytes:
    return common._read(ROOT,'src/anno1503_overhaul/'+name)


def _preflight_source() -> bytes:
    return b'''"""Exact stock-host World-only activation preflight."""
from pathlib import Path
import sys
PACKAGE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PACKAGE))
import world_mod as mod
if Path(mod.__file__).resolve()!=PACKAGE/'world_mod.py':
    raise RuntimeError('Unexpected World-only activation helper.')
def verify(copy_root=None):
    return mod.verify_activation(copy_root)
'''


def _launcher_recipe(files: dict[str, bytes], source_game: str, copy_game: str) -> None:
    """Retain exact readiness guards and use the normal-client context bridge."""
    name='launcher/native_ready.py'
    files[name]=common._replace(files[name],
        b'046b5ad6f351dfe867ed38ce29fb50a594485b43a32ee90adadc48e850466baf',
        b'dfd7c76dfc0b017fa5142c46a2bb084c01fc750a049d85ca70b56dca2f555ccd',name)
    newline=b'\r\n'if b'\r\n'in files[name]else b'\n'
    def block(value):return value.encode().replace(b'\n',newline)
    files[name]=common._replace(files[name],b'def __init__(self, package, inputs):',
                               b'def __init__(self, package, inputs, frame_sha=FRAME_SHA256):',name)
    anchor=b'        if frame != [FRAME_SHA256]:'
    replacement='''        if frame_sha not in (FRAME_SHA256,"046b5ad6f351dfe867ed38ce29fb50a594485b43a32ee90adadc48e850466baf"):
            raise RuntimeError("Unsupported exact normal-client Frame fingerprint.")
        self.frame_sha=frame_sha
        if frame != [self.frame_sha]:'''
    files[name]=common._replace(files[name],anchor,block(replacement),name)
    files[name]=common._replace(files[name],b'self._sha(frame["path"]) != FRAME_SHA256',
                               b'self._sha(frame["path"]) != self.frame_sha',name)
    files[name]=common._replace(files[name],b'    def inspect(self, pid):',block('''    def inspect_owned_bootstrap(self, pid, identity):
        # Only the exact fresh source menu the handoff already certified and
        # hid may omit the visible-window requirement. Ordinary inspection and
        # the copied game's activation gate retain all existing requirements.
        if (not isinstance(identity, tuple) or len(identity) != 4
                or any(type(value) is not int or value <= 0 for value in identity)
                or type(pid) is not int or pid != identity[0]):
            raise RuntimeError("The owned hidden bootstrap identity is invalid.")
        return self.inspect(pid, _owned_bootstrap=identity)

    def inspect(self, pid, *, _owned_bootstrap=None):'''),name)
    files[name]=common._replace(files[name],
        b'            result["process_creation_time"] = created',block('''            result["process_creation_time"] = created
            if _owned_bootstrap is not None and created != _owned_bootstrap[1]:
                return finish("unsafe", "The owned hidden bootstrap process changed.")'''),name)
    files[name]=common._replace(files[name],
        b'                if not self.windows["visible"](hwnd) or self.windows["iconic"](hwnd):',block('''                if _owned_bootstrap is not None and hwnd != _owned_bootstrap[2]:
                    row["reason"] = "This is not the exact owned bootstrap window."
                    continue
                if _owned_bootstrap is None and (not self.windows["visible"](hwnd) or self.windows["iconic"](hwnd)):'''),name)
    files[name]=common._replace(files[name],b'                row.update(userptr=pointer)',block('''                row.update(userptr=pointer)
                if _owned_bootstrap is not None and pointer != _owned_bootstrap[3]:
                    return finish("unsafe", "The owned hidden bootstrap frame changed.")'''),name)
    # Flat package copies have no dependency on the user's editable install or
    # PYTHONPATH. Only these reviewed relative imports change spelling.
    context=_source('client_context.py')
    context=common._replace(context,b'from .filesystem import ',b'from managed_filesystem import ','client context')
    context=common._replace(context,b'from .processes import ',b'from managed_processes import ','client context')
    files['launcher/client_context.py']=context
    files['launcher/managed_filesystem.py']=_source('filesystem.py')
    files['launcher/managed_processes.py']=_source('processes.py')
    files['launcher/source_readiness.py']=b'''"""Exact native inputs for a read-only ordinary Ubisoft main-menu probe."""
from pathlib import Path
import hashlib,json
from native_ready import NativeReadiness
STOCK_FRAME="dfd7c76dfc0b017fa5142c46a2bb084c01fc750a049d85ca70b56dca2f555ccd"
FOOD_FRAME="046b5ad6f351dfe867ed38ce29fb50a594485b43a32ee90adadc48e850466baf"
def build_source_probe(package,spec):
    source=Path(spec['input_source_root']).resolve(strict=True)
    food=json.loads((package/'food_patch.json').read_bytes())
    sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    if sha(source/'Anno1503.exe')!=spec['exe_sha256']:
        raise RuntimeError('The ordinary Ubisoft executable differs from the inspected build.')
    native={}
    for entry in food['native_modules']:
        actual=sha(source/entry['name'])
        if actual not in set(entry['sources'].values())|{entry['after_sha256']}:
            raise RuntimeError('An ordinary Ubisoft native module differs from its inspected versions.')
        native[entry['name']]=actual
    native['AnnoScene.dll']=spec['native_sha256']['AnnoScene.dll']
    if sha(source/'AnnoScene.dll')!=native['AnnoScene.dll'] or native['AnnoFrame.dll']not in(STOCK_FRAME,FOOD_FRAME):
        raise RuntimeError('The normal-client startup architecture differs.')
    inputs=dict(source=source,copy=source,exe_sha256=spec['exe_sha256'],native_sha256=native,private_native_sha256={})
    return source,NativeReadiness(package,inputs,frame_sha=native['AnnoFrame.dll'])
'''
    name='launcher/launch_world_settings.pyw'
    files[name]=common._replace(files[name],
        b"        self.uri = self.find_uri(self.inputs['source'])",
        block('''        from source_readiness import build_source_probe
        self.normal_source,self.source_probe=build_source_probe(self.package,self.spec)
        self.uri = self.find_uri(self.normal_source)'''),name)
    files[name]=common._replace(files[name],b'        os.startfile(self.uri)',
        block('''        from client_context import start_game
        try:
            start_game(self.uri,self.normal_source,self.inputs['source'],self.source_probe,
                       copy_probe=self.native,event=self.event,
                       progress=lambda message:self.event('handoff_progress',dict(message=message)))
        finally:
            self.source_probe.close()'''),name)


def _recipe(raw_frozen: bytes, stock: dict[str,bytes], frozen_payloads: dict[str,bytes],
            runtime: bytes, source_game: str, copy_game: str, *, baselines=None,
            runtime_policy=None) -> dict[str,bytes]:
    runtime_sha, engine_sha, stock_hashes=_runtime_policy() if runtime_policy is None else runtime_policy
    if set(stock)!=set(_STOCK_NAMES):
        raise common.PackageError('The complete stock World-only native inputs are missing.')
    for name,data in stock.items():
        common._require_sha(data,stock_hashes[name],'stock/'+name)
        common._amd64(data,name)
    common._require_sha(runtime,runtime_sha,'World-only runtime')
    common._amd64(runtime,'World-only runtime')
    frozen, ignored=common._world_spec(raw_frozen,source_game,copy_game)
    if set(frozen_payloads)!=set(frozen['payloads']):
        raise common.PackageError('The frozen World payload inventory differs.')
    for name,digest in frozen['payloads'].items():
        common._require_sha(frozen_payloads[name],digest,'frozen/'+name)
        if name.startswith('native/'):
            common._amd64(frozen_payloads[name],name)
    files=common._source_recipe(copy_game,baselines)
    food_spec=files['food/food_patch.json']
    outputs,proof=derive_native_profile(stock,frozen_payloads,food_spec=food_spec,world_spec=raw_frozen)
    # The actual executable host and its native DLLs remain entirely stock.
    # Derived disk Frame/Scene/Welt overlays are deliberately not installed.
    files['world/world_mod.py']=_source('world_only_backend.py')
    files['world/support/stock_baseline.py']=_source('vanilla.py')
    files['world/activation/preflight.py']=_preflight_source()
    files['world/frozen_world_patch.json']=raw_frozen
    files.update({'world/stock/'+name:data for name,data in stock.items()})
    files.update({'world/frozen-inputs/'+name:data for name,data in frozen_payloads.items()})
    from .world_runtime_build import derive_engine_plan
    engine=derive_engine_plan(stock['AnnoWelt.dll'],files['world/developer/huge_world/runtime_engine_edits.json'])
    common._require_sha(engine,engine_sha,'World-only engine plan')
    files['world/developer/huge_world/runtime_engine_edits.json']=engine
    introduced={
        'AnnoWorldSettings.dll':'native/AnnoWorldSettings.dll',
        'WorldSettingsAI/CompLogic.dll':'native/CompLogic.world-only.dll',
        'WorldSettingsAI/CompLogicClassic.dll':'native/CompLogicClassic.world-only.dll',
    }
    introduced.update({target:payload for target,payload in frozen['introduced_files'].items()
                       if payload in frozen['data_payloads']})
    data={'native/AnnoWorldSettings.dll':runtime,
          'native/CompLogic.world-only.dll':outputs['WorldSettingsAI/CompLogic.dll'],
          'native/CompLogicClassic.world-only.dll':outputs['WorldSettingsAI/CompLogicClassic.dll']}
    data.update({name:frozen_payloads[name] for name in frozen['data_payloads']})
    files.update({'world/'+name:value for name,value in data.items()})
    source_native={name:stock_hashes[name] for name in (*_STOCK_NAMES,'AnnoScene.dll')}
    spec=dict(profile=PROFILE,version='0.3.0',status='UNFINISHED',food_enabled=False,
              host_root=copy_game,input_source_root=source_game,original_game_root=copy_game,
              exe_sha256=frozen['exe_sha256'],native_sha256=source_native,
              payloads={name:common._sha(value) for name,value in sorted(data.items())},
              introduced_files=introduced,expanded_engine_patch_count=173,
              expanded_engine_plan_sha256=engine_sha,
              frozen_world_spec_sha256=common.FROZEN_WORLD_SPEC_SHA256,
              actual_game_run=False,packaged_runtime_gameplay_verified=False,
              complete_feature_verified=False,
              evidence_scope='Pinned stock-host derivative; building a package is not a new game test.')
    files['world/world_patch.json']=common._encoded(spec)
    config=dict(version='1.0.0',profile=PROFILE,food_enabled=False,
                package_relative='../world',package_spec_sha256=common._sha(files['world/world_patch.json']),
                runtime_sha256=runtime_sha,engine_patch_count=173,timeout_seconds=300,
                copy_root=copy_game,input_source_root=source_game,
                modular_adapter_version=VERSION)
    files['launcher/launcher_config.json']=common._encoded(config)
    _launcher_recipe(files,source_game,copy_game)
    return files


def _manifest(source: str,copy: str,files: dict[str,bytes]) -> dict:
    runtime_sha,engine_sha,stock_hashes=_runtime_policy()
    return dict(schema_version=1,kind=KIND,profile=PROFILE,adapter_version=VERSION,
                food_enabled=False,source_root=source,input_source_root=source,copy_root=copy,host_root=copy,
                feature_versions={'world_settings':'0.3.0-world-only','launcher':'1.0.0-world-only'},
                runtime_sha256=runtime_sha,engine_plan_sha256=engine_sha,
                frozen_world_spec_sha256=common.FROZEN_WORLD_SPEC_SHA256,
                files={name:common._sha(data) for name,data in sorted(files.items())},
                transaction=dict(backup=common.TRANSACTION_BACKUP,lock=common.TRANSACTION_LOCK,
                                 version=common.TRANSACTION_VERSION,schema=1),
                actual_game_test_performed=False)


def _paths(source_value,copy_value):
    if not isinstance(source_value,str) or not isinstance(copy_value,str):
        raise common.PackageError('World-only package game paths are missing.')
    source=common._checked_path(Path(source_value))
    copy=common._checked_path(Path(copy_value),exists=False)
    if (not source.is_dir() or str(source)!=source_value or str(copy)!=copy_value
            or source==copy or source.is_relative_to(copy) or copy.is_relative_to(source)):
        raise common.PackageError('World-only package needs separate canonical source and host folders.')
    return source,copy


def validate_world_only_package(path,source_game=None) -> dict:
    root=common._checked_path(Path(path))
    if not root.is_dir():
        raise common.PackageError('Select a prepared World-only package folder.')
    record=common._json(common._read(root,'manifest.json'),'World-only package manifest')
    if record.get('kind')!=KIND:
        raise common.PackageError('Unknown World-only package kind.')
    source,copy=_paths(record.get('source_root'),record.get('copy_root'))
    if source_game is not None and common._checked_path(Path(source_game))!=source:
        raise common.PackageError('This World-only package belongs to another original game.')
    raw=common._read(root,'world/frozen_world_patch.json')
    frozen,ignored=common._world_spec(raw,str(source),str(copy))
    stock={name:common._read(root,'world/stock/'+name)for name in _STOCK_NAMES}
    corpus={name:common._read(root,'world/frozen-inputs/'+common._name(name))for name in frozen['payloads']}
    runtime=common._read(root,'world/native/AnnoWorldSettings.dll')
    files=_recipe(raw,stock,corpus,runtime,str(source),str(copy))
    expected=_manifest(str(source),str(copy),files)
    if common._encoded(record)!=common._encoded(expected):
        raise common.PackageError('World-only manifest differs from its reviewed recipe.')
    for name,data in files.items():
        if common._read(root,name)!=data:
            raise common.PackageError('World-only helper, payload or configuration changed: '+name)
    names=set(files)|{'manifest.json'}
    directories={str(p)for name in names for p in PurePosixPath(name).parents if str(p)!='.'}
    directories.add('launcher/logs')
    for folder,dirs,entries in os.walk(root,followlinks=False):
        for name in dirs+entries:
            path=Path(folder)/name
            checked=common._checked_path(path)
            relative=path.relative_to(root).as_posix()
            if not checked.is_relative_to(root):
                raise common.PackageError('World-only package path leaves its folder.')
            if path.is_dir():
                if relative not in directories:
                    raise common.PackageError('Unexpected World-only package directory: '+relative)
            elif not path.is_file()or(relative not in names and not common._mutable(relative)):
                raise common.PackageError('Unexpected World-only package file: '+relative)
            elif common._mutable(relative)and path.stat().st_size>common._MAX_FILE:
                raise common.PackageError('World-only diagnostic exceeds its bounds.')
    return dict(expected,root=root,path=root,world_path=root/'world',food_path=root/'food',
                launcher_path=root/'launcher',verified=True)


def _stock_inputs(source: Path) -> dict[str,bytes]:
    food=ROOT/'legacy/food_overhaul'
    recoveries={item.name:item for item in plan_vanilla_recovery(source,food)}
    result={}
    for name in _STOCK_NAMES:
        recovery=recoveries.get(name)
        if recovery is not None and recovery.offset is not None:
            raise common.PackageError('Native World-only input must be a complete original file.')
        path=recovery.source_file if recovery is not None else source/name
        path=common._checked_path(path)
        if path.stat().st_size>common._MAX_FILE:
            raise common.PackageError('World-only native input is too large.')
        result[name]=path.read_bytes()
    return result


def prepare_world_only_package(baselines_dir,output_dir,source_game,copy_game,runtime_path=None) -> Path:
    baselines=common._checked_path(Path(baselines_dir))
    source,copy=_paths(str(common._checked_path(Path(source_game))),
                       str(common._checked_path(Path(copy_game),exists=False)))
    output=common._package_output(output_dir,source,copy,baselines)
    raw=common._read(baselines/'world_settings','world_patch.json')
    frozen,ignored=common._world_spec(raw,str(source),str(copy))
    corpus={name:common._read(baselines/'world_settings',common._name(name))for name in frozen['payloads']}
    stock=_stock_inputs(source)
    runtime_path=common._checked_path(Path(runtime_path) if runtime_path is not None
                                    else ROOT/'.local/runtime-profiles/world-only-v1/AnnoWorldSettings.dll')
    if not runtime_path.is_file()or runtime_path.stat().st_size>common._MAX_FILE:
        raise common.PackageError('The pinned World-only runtime is missing or too large.')
    files=_recipe(raw,stock,corpus,runtime_path.read_bytes(),str(source),str(copy),baselines=baselines)
    record=_manifest(str(source),str(copy),files)
    files['manifest.json']=common._encoded(record)
    # Use this profile's validator before publication, rather than asking an
    # older catalogue to recognize the new package kind during staged creation.
    output.parent.mkdir(parents=True,exist_ok=True)
    common._checked_path(output.parent)
    stage=output.parent/('.world-only-package-staging-'+uuid.uuid4().hex)
    stage.mkdir()
    try:
        for name,data in files.items():
            path=stage/name;path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('xb')as stream:stream.write(data)
        validate_world_only_package(stage,source)
        if os.path.lexists(output):
            raise common.PackageError('World-only package output appeared during preparation.')
        stage.rename(output)
    except BaseException:
        if stage.exists()and stage.parent==output.parent and stage.name.startswith('.world-only-package-staging-'):
            checked=common._checked_path(stage)
            if checked.parent==output.parent:shutil.rmtree(checked)
        raise
    return output
