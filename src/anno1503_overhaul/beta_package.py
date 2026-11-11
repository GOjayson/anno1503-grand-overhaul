"""Public-source World-only beta package; no historical private corpus.

Game inputs stay local. This package kind has its own strict reconstruction
policy and cannot be accepted as a historical frozen World package.
"""
from pathlib import Path, PurePosixPath
import os
import types
import uuid

from . import packages as common
from . import world_only_package as stock
from . import world_runtime_build as native
from . import world_options_build as options
from .world_options import VERSION, SETTINGS_SIZE, PREVIEW_SIZE, generator_id
from .world_options_factions import PROFILE_INPUT_SHA256, derive_faction_ai

KIND = 'anno1503-public-beta-world-package'


def _policy():
    if generator_id() != options.PINNED_GENERATOR:
        raise common.PackageError('World Settings changed after its runtime review; prepare a reviewed beta build.')
    digest = options.PINNED_RUNTIMES['world-only']
    if not isinstance(digest,str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        raise common.PackageError('The public World-only beta runtime has not passed review.')
    return digest


def _native_pins():
    # Display is proved by the compiler host and coherent source profile.
    # It is not a derivation input for the shipped payloads and need not be
    # duplicated into this package (the original DLL exceeds the 16MiB cap).
    return {n:s for n,s in native.STOCK_SHA256.items() if n != 'Anno1503.exe'}


def _asset_policy(files):
    introduced, hashes, validators = {}, {}, {}
    for name in ('package_alias_assets','package_world_assets'):
        code = files['world/support/'+name+'.py']
        module = types.ModuleType('_beta_'+name)
        exec(compile(code,'<reviewed beta asset policy>','exec'),module.__dict__)
        records, digests = module.introduced_files(), module.data_payload_hashes()
        if set(introduced) & set(records) or set(hashes) & set(digests):
            raise common.PackageError('Public beta island policies overlap.')
        introduced.update(records);hashes.update(digests)
        validators.update({n:module.validate_data_payload for n in digests})
    if len(introduced) != 16 or set(introduced.values()) != set(hashes):
        raise common.PackageError('The public beta island inventory differs from its reviewed 16 outputs.')
    return introduced,hashes,validators


def _recipe(source,copy,stock_native,assets,private_ai,runtime):
    runtime_sha = _policy()
    from .beta_inputs import verify_beta_source
    source_proof = verify_beta_source(source)
    common._require_sha(common._read(source,'Anno1503.exe'),native.STOCK_SHA256['Anno1503.exe'],'owned game executable')
    common._require_sha(runtime,runtime_sha,'public beta World-only runtime')
    common._amd64(runtime,'public beta World-only runtime')
    pins = _native_pins()
    if set(stock_native) != set(pins):
        raise common.PackageError('The public beta needs every exact stock native host input.')
    for name,digest in pins.items():
        common._require_sha(stock_native[name],digest,'stock/'+name)
        common._amd64(stock_native[name],name)
    files = common._source_recipe(str(copy))
    introduced,hashes,validators = _asset_policy(files)
    if set(assets) != set(hashes) or set(private_ai) != {'CompLogic.dll','CompLogicClassic.dll'}:
        raise common.PackageError('Public beta payload membership differs.')
    for name,digest in hashes.items():
        common._require_sha(assets[name],digest,'public beta/'+name)
        validators[name](name,assets[name])
    from .world_native import derive_public_ai_candidate
    for name in ('CompLogic.dll','CompLogicClassic.dll'):
        predecessor = derive_public_ai_candidate(name,stock_native[name])
        expected,unused = derive_faction_ai(name,predecessor,PROFILE_INPUT_SHA256['world-only'][name])
        if private_ai[name] != expected:
            raise common.PackageError('The public beta AI policy differs from its exact stock derivation: '+name)
        common._amd64(private_ai[name],name)
    files['world/world_mod.py'] = stock._source('world_only_backend.py')
    files['world/support/stock_baseline.py'] = stock._source('vanilla.py')
    files['world/activation/preflight.py'] = stock._preflight_source()
    files.update({'world/stock/'+n:v for n,v in stock_native.items()})
    data = {'native/AnnoWorldSettings.dll':runtime,
            **{'native/'+n.removesuffix('.dll')+'.world-only.dll':v for n,v in private_ai.items()},
            **assets}
    introduced = {'AnnoWorldSettings.dll':'native/AnnoWorldSettings.dll',
                  'WorldSettingsAI/CompLogic.dll':'native/CompLogic.world-only.dll',
                  'WorldSettingsAI/CompLogicClassic.dll':'native/CompLogicClassic.world-only.dll',
                  **introduced}
    files.update({'world/'+n:v for n,v in data.items()})
    engine = native.derive_engine_plan(stock_native['AnnoWelt.dll'],files['world/developer/huge_world/runtime_engine_edits.json'])
    common._require_sha(engine,native.WORLD_ONLY_ENGINE_PLAN_SHA256,'public beta engine plan')
    files['world/developer/huge_world/runtime_engine_edits.json'] = engine
    spec = dict(profile=stock.PROFILE,version='0.3.0',status='BETA',food_enabled=False,
                host_root=str(copy),input_source_root=str(source),original_game_root=str(copy),
                exe_sha256=native.STOCK_SHA256['Anno1503.exe'],native_sha256=pins,
                payloads={n:common._sha(v) for n,v in sorted(data.items())},introduced_files=introduced,
                expanded_engine_patch_count=173,expanded_engine_plan_sha256=native.WORLD_ONLY_ENGINE_PLAN_SHA256,
                public_beta_source=True,actual_game_run=False,packaged_runtime_gameplay_verified=False,
                complete_feature_verified=False,
                **source_proof,
                world_options=dict(version=VERSION,generator_id=generator_id(),settings_size=SETTINGS_SIZE,
                                   preview_size=PREVIEW_SIZE,food_enabled=False))
    files['world/world_patch.json'] = common._encoded(spec)
    files['world/activation/preview_snapshot.py'] = common._read(common.ROOT,'src/anno1503_overhaul/world_options_snapshot.py')
    config = dict(version='1.0.0',profile=stock.PROFILE,food_enabled=False,
                  package_relative='../world',package_spec_sha256=common._sha(files['world/world_patch.json']),
                  runtime_sha256=runtime_sha,engine_patch_count=173,timeout_seconds=300,
                  copy_root=str(copy),input_source_root=str(source),modular_adapter_version=stock.VERSION,
                  world_options_version=VERSION,generator_id=generator_id(),public_beta_source=True)
    files['launcher/launcher_config.json'] = common._encoded(config)
    stock._launcher_recipe(files,str(source),str(copy))
    name = 'launcher/source_readiness.py'
    anchor = b"    inputs=dict(source=source,copy=source,exe_sha256=spec['exe_sha256'],native_sha256=native,private_native_sha256={})"
    files[name] = common._replace(files[name],anchor,
        b"    expected=spec['source_native_sha256']\n"
        b"    if any(sha(source/name)!=digest for name,digest in expected.items()):\n"
        b"        raise RuntimeError('The registered game changed after this beta package was prepared.')\n"+anchor,name)
    return files


def _manifest(source,copy,files):
    source_proof = common._json(files['world/world_patch.json'],'public beta World specification')
    return dict(schema_version=1,kind=KIND,version=VERSION,profile='world-only',food_enabled=False,
                source_root=str(source),copy_root=str(copy),host_root=str(copy),input_source_root=str(source),
                runtime_sha256=_policy(),engine_plan_sha256=native.WORLD_ONLY_ENGINE_PLAN_SHA256,
                generator_id=generator_id(),feature_versions={'world_settings':VERSION},public_beta_source=True,
                source_native_profile=source_proof['source_native_profile'],
                source_native_sha256=source_proof['source_native_sha256'],
                files={n:common._sha(v) for n,v in sorted(files.items())},actual_game_test_performed=False)


def validate_beta_package(path,source_game=None):
    root = common._checked_path(Path(path))
    manifest = common._json(common._read(root,'manifest.json'),'public beta package manifest')
    if manifest.get('kind') != KIND:
        raise common.PackageError('This is not a public beta World-only package.')
    source,copy = stock._paths(manifest.get('source_root'),manifest.get('copy_root'))
    if source_game is not None and common._checked_path(Path(source_game)) != source:
        raise common.PackageError('This public beta package belongs to another original game folder.')
    public = common._source_recipe(str(copy))
    unused,hashes,unused = _asset_policy(public)
    natives = {n:common._read(root,'world/stock/'+n) for n in _native_pins()}
    assets = {n:common._read(root,'world/'+n) for n in hashes}
    ai = {n:common._read(root,'world/native/'+n.removesuffix('.dll')+'.world-only.dll')
          for n in ('CompLogic.dll','CompLogicClassic.dll')}
    runtime = common._read(root,'world/native/AnnoWorldSettings.dll')
    files = _recipe(source,copy,natives,assets,ai,runtime)
    expected = _manifest(source,copy,files)
    if common._encoded(manifest) != common._encoded(expected):
        raise common.PackageError('Public beta metadata differs from its independently reconstructed recipe.')
    for name,value in files.items():
        if common._read(root,name) != value:
            raise common.PackageError('A public beta helper or payload changed: '+name)
    names = set(files)|{'manifest.json'}
    directories = {str(p) for n in names for p in PurePosixPath(n).parents if str(p) != '.'}|{'launcher/logs'}
    for folder,dirs,entries in os.walk(root,followlinks=False):
        for name in dirs+entries:
            item = common._checked_path(Path(folder)/name)
            relative = item.relative_to(root).as_posix()
            if item.is_dir():
                if relative not in directories:raise common.PackageError('Unexpected public beta directory: '+relative)
            elif not item.is_file() or (relative not in names and not common._mutable(relative)):
                raise common.PackageError('Unexpected public beta file: '+relative)
            elif common._mutable(relative) and item.stat().st_size>common._MAX_FILE:
                raise common.PackageError('A public beta diagnostic exceeds its bound.')
    return dict(expected,root=root,path=root,world_path=root/'world',food_path=root/'food',
                launcher_path=root/'launcher',verified=True)


def prepare_beta_package(output_dir,source_game,copy_game,*,compiler_path,runtime_path=None):
    """Reconstruct local game derivatives and publish one pinned beta package.

    Neither a private baseline store nor a pre-existing runtime profile is used.
    Build/input evidence is retained in a fresh sibling work directory.
    """
    from .beta_inputs import prepare_beta_inputs
    source,copy = stock._paths(str(common._checked_path(Path(source_game))),
                               str(common._checked_path(Path(copy_game),exists=False)))
    output = common._package_output(output_dir,source,copy,None)
    _policy()
    workspace = common._package_output(output.parent/('build-'+uuid.uuid4().hex[:16]),source,copy,None)
    workspace.mkdir(parents=True,exist_ok=False)
    inputs = prepare_beta_inputs(source,workspace/'inputs',compiler_path=compiler_path)
    if runtime_path is None:
        result = options.build_public_options_runtime(inputs['root'],output=workspace/'runtime')
        runtime_path = Path(result['runtime_path'])
    runtime_file = common._checked_path(Path(runtime_path))
    runtime = common._read(runtime_file.parent,runtime_file.name)
    public = common._source_recipe(str(copy))
    unused,hashes,unused = _asset_policy(public)
    assets = {n:common._read(inputs['assets_root'],n.removeprefix('assets/')) for n in hashes}
    ai = {n:common._read(inputs['private_ai_root'],n) for n in ('CompLogic.dll','CompLogicClassic.dll')}
    natives = {n:inputs['stock_native_bytes'][n] for n in _native_pins()}
    files = _recipe(source,copy,natives,assets,ai,runtime)
    files['manifest.json'] = common._encoded(_manifest(source,copy,files))
    return common._publish(files,output,source)
