"""Public-source Food 0.6 + World Settings preparation for the Windows release.

Original game bytes are reconstructed locally from the supported installation
and its verified original backups. No private development corpus or prebuilt
runtime profile is read. The resulting package contains local derivatives and
must not be redistributed as part of the public release archive.
"""
from pathlib import Path, PurePosixPath
import os
import uuid

from . import packages as common
from . import food06_package as food
from . import food_world_package as combined
from . import food_world_runtime as native
from . import beta_inputs, beta_package
from . import world_only_package as stock
from .food_world_policy import PROFILE, food_files
from .food_diet import VERSION
from .world_options import VERSION as WORLD_VERSION, generator_id, SETTINGS_SIZE, PREVIEW_SIZE

KIND = 'anno1503-public-food-world06-package'


def _originals(source):
    selected, recovery, proof = beta_inputs._stock_sources(source)
    values = {name: beta_inputs._small_stock(selected[name]) for name in native.HOST_SHA256}
    return values, dict(source_recovery_files=recovery, **proof)


def _private_ai(stock_native):
    from .food_world_public_ai import derive_food05_ai
    from .world_options_factions import PROFILE_INPUT_SHA256, derive_faction_ai
    from .food_world_ai import derive_food06_ai, OUTPUT_SHA256
    result, proof = {}, {}
    for name in ('CompLogic.dll', 'CompLogicClassic.dll'):
        base = derive_food05_ai(name, stock_native[name])
        common._require_sha(base, PROFILE_INPUT_SHA256['food-world'][name], 'public Food05 AI/'+name)
        activity, activity_proof = derive_faction_ai(name, base, PROFILE_INPUT_SHA256['food-world'][name])
        result[name], guard_proof = derive_food06_ai(name, activity)
        common._require_sha(result[name], OUTPUT_SHA256[name], 'public Food06 AI/'+name)
        proof[name] = dict(food05_sha256=common._sha(base), activity=activity_proof, guard=guard_proof)
    return result, proof


def _native_host(stock_native, view, welt, *, city_statistics_guard=False):
    raw = common._require_sha(common._read(common.ROOT, 'legacy/food_overhaul/food_patch.json'),
                              common.FOOD_SPEC_SHA256, 'preserved Food construction specification')
    spec = common._json(raw, 'preserved Food construction specification')
    changed = {item['name'] for item in spec['native_modules']}
    images = {name: food._food05_native(value, spec, name) if name in changed else value
              for name, value in stock_native.items()}
    images.update({'View.dll':view, 'AnnoWelt.dll':welt})
    host = native.expected_native_hashes(city_statistics_guard=True) if city_statistics_guard else native.HOST_SHA256
    if set(images) != set(host):
        raise common.PackageError('The public Food06 native host inventory differs.')
    for name, digest in host.items():
        common._require_sha(images[name], digest, 'public Food06 host/'+name)
        common._amd64(images[name], 'public Food06 host/'+name)
    return images


def _recipe(source, copy, runtime, view, welt, *, bug_fixes_enabled=False, city_statistics_guard=False):
    stock._bug_fix_manifest(bug_fixes_enabled)
    if type(city_statistics_guard) is not bool or (city_statistics_guard and not bug_fixes_enabled):
        raise common.PackageError('City statistics protection requires the selected Bug Fixes option.')
    combined._policy(city_statistics_guard=city_statistics_guard)
    host = native.expected_native_hashes(city_statistics_guard=True) if city_statistics_guard else native.HOST_SHA256
    runtime_pin = native.runtime_hash(city_statistics_guard)
    engine_pin = native.engine_plan_hash(city_statistics_guard)
    originals, source_proof = _originals(source)
    # Reconstruct the complete native host even during validation. This proves
    # the Food outputs belong to the reviewed coherent source, independently of
    # manifest hashes and without opening historical patched DLLs.
    _native_host(originals, view, welt, city_statistics_guard=city_statistics_guard)
    common._require_sha(runtime, runtime_pin, 'public Food06 World runtime')
    common._amd64(runtime, 'public Food06 World runtime')
    files = common._source_recipe(str(copy))
    food_inputs = food._recipe(str(source), str(copy), view, welt, city_statistics_guard=city_statistics_guard)
    files.update(food_inputs)
    files.update({'world/'+name.removeprefix('food/'):value for name,value in food_inputs.items()})
    files['world/world_mod.py'] = stock._source('food_world_backend.py')
    files['world/support/food_world_policy.py'] = stock._source('food_world_policy.py')
    files['world/support/stock_baseline.py'] = stock._source('vanilla.py')
    files['world/activation/preflight.py'] = stock._preflight_source()
    files['world/activation/preview_snapshot.py'] = stock._source('world_options_snapshot.py')
    introduced, hashes, validators = beta_package._asset_policy(files)
    assets, unused = beta_inputs.derive_beta_assets(source)
    if set(assets) != set(hashes):
        raise common.PackageError('The public combined island inventory differs.')
    for name, digest in hashes.items():
        common._require_sha(assets[name], digest, 'public combined/'+name)
        validators[name](name, assets[name])
    ai, unused = _private_ai(originals)
    payloads = {'native/AnnoWorldSettings.dll':runtime,
                'native/CompLogic.food06.dll':ai['CompLogic.dll'],
                'native/CompLogicClassic.food06.dll':ai['CompLogicClassic.dll'], **assets}
    introduced = {'AnnoWorldSettings.dll':'native/AnnoWorldSettings.dll',
                  'WorldSettingsAI/CompLogic.dll':'native/CompLogic.food06.dll',
                  'WorldSettingsAI/CompLogicClassic.dll':'native/CompLogicClassic.food06.dll', **introduced}
    files.update({'world/'+name:value for name,value in payloads.items()})
    engine_name = 'world/developer/huge_world/runtime_engine_edits.json'
    files[engine_name] = native.derive_engine_plan(welt, files[engine_name])
    common._require_sha(files[engine_name], engine_pin, 'public combined engine plan')
    spec = dict(profile=PROFILE, version=WORLD_VERSION, food_version=VERSION, status='BETA',
                food_enabled=True, host_root=str(copy), input_source_root=str(source), original_game_root=str(copy),
                exe_sha256=host['Anno1503.exe'], native_sha256=host,
                food_files=food_files(), new_world_required=True, old_save_migration_supported=False,
                introduced_files=introduced, payloads={name:common._sha(value) for name,value in sorted(payloads.items())},
                expanded_engine_patch_count=173, expanded_engine_plan_sha256=engine_pin,
                public_beta_source=True, historical_private_inputs_used=False, **source_proof,
                world_options=dict(version=WORLD_VERSION, generator_id=generator_id(),
                                   settings_size=SETTINGS_SIZE, preview_size=PREVIEW_SIZE, food_enabled=True),
                actual_game_run=False, packaged_runtime_gameplay_verified=False, complete_feature_verified=False)
    bug_fixes = stock._bug_fix_recipe(files, source, bug_fixes_enabled)
    if bug_fixes is not None:
        spec['bug_fixes'] = bug_fixes
    files['world/world_patch.json'] = common._encoded(spec)
    files['launcher/launcher_config.json'] = common._encoded(dict(
        version='1.0.0', profile=PROFILE, food_version=VERSION, food_enabled=True,
        package_relative='../world', package_spec_sha256=common._sha(files['world/world_patch.json']),
        runtime_sha256=runtime_pin, engine_patch_count=173, timeout_seconds=300,
        copy_root=str(copy), input_source_root=str(source), world_options_version=WORLD_VERSION,
        generator_id=generator_id(), modular_adapter_version='1.0', public_beta_source=True))
    stock._launcher_recipe(files, str(source), str(copy))
    source_reader = combined._source_readiness()
    anchor = b"    inputs=dict(source=source,copy=source,exe_sha256=spec['exe_sha256'],"
    source_reader = common._replace(source_reader, anchor,
        b"    if any(sha(name)!=digest for name,digest in spec['source_native_sha256'].items()):\n"
        b"        raise RuntimeError('The registered source changed after public combined preparation.')\n"+anchor,
        'public combined source readiness')
    files['launcher/source_readiness.py'] = source_reader
    name = 'launcher/native_ready.py'
    files[name] = common._replace(files[name],
        b'FRAME_SHA256 = "dfd7c76dfc0b017fa5142c46a2bb084c01fc750a049d85ca70b56dca2f555ccd"',
        b'FRAME_SHA256 = "046b5ad6f351dfe867ed38ce29fb50a594485b43a32ee90adadc48e850466baf"', name)
    files[name] = common._replace(files[name],
        b'frame_sha not in (FRAME_SHA256,"046b5ad6f351dfe867ed38ce29fb50a594485b43a32ee90adadc48e850466baf")',
        b'frame_sha not in (FRAME_SHA256,"dfd7c76dfc0b017fa5142c46a2bb084c01fc750a049d85ca70b56dca2f555ccd")', name)
    return files


def _manifest(source, copy, files, *, bug_fixes_enabled=False, city_statistics_guard=False):
    result = combined._manifest(str(source), str(copy), files, bug_fixes_enabled=bug_fixes_enabled,
                                city_statistics_guard=city_statistics_guard)
    result.pop('frozen_world_spec_sha256')
    spec = common._json(files['world/world_patch.json'], 'public combined specification')
    return dict(result, kind=KIND, public_beta_source=True, historical_private_inputs_used=False,
                source_native_profile=spec['source_native_profile'], source_native_sha256=spec['source_native_sha256'],
                source_recovery_files=spec['source_recovery_files'])


def validate_public_food_world_package(path, source_game=None):
    root = common._checked_path(Path(path))
    manifest = common._json(common._read(root, 'manifest.json'), 'public Food06 combined manifest')
    if manifest.get('kind') != KIND:
        raise common.PackageError('Unknown public Food06 combined package kind.')
    source, copy = stock._paths(manifest.get('source_root'), manifest.get('copy_root'))
    if source_game is not None and common._checked_path(Path(source_game)) != source:
        raise common.PackageError('The public combined package belongs to another original game.')
    enabled = manifest.get('bug_fixes_enabled', False)
    city_statistics_guard = manifest.get('city_statistics_guard', False)
    files = _recipe(source, copy, common._read(root, 'world/native/AnnoWorldSettings.dll'),
                    common._read(root, food.VIEW_PAYLOAD), common._read(root, food.WELT_PAYLOAD),
                    bug_fixes_enabled=enabled, city_statistics_guard=city_statistics_guard)
    expected = _manifest(source, copy, files, bug_fixes_enabled=enabled,
                         city_statistics_guard=city_statistics_guard)
    if common._encoded(manifest) != common._encoded(expected):
        raise common.PackageError('Public combined metadata differs from its exact public-source recipe.')
    for name, value in files.items():
        if common._read(root, name) != value:
            raise common.PackageError('A public combined helper, input or payload changed: '+name)
    names = set(files)|{'manifest.json'}
    directories = {str(parent) for name in names for parent in PurePosixPath(name).parents if str(parent) != '.'}
    directories.add('launcher/logs')
    for folder, dirs, entries in os.walk(root, followlinks=False):
        for child in dirs+entries:
            item = common._checked_path(Path(folder)/child)
            name = item.relative_to(root).as_posix()
            if item.is_dir():
                if name not in directories:
                    raise common.PackageError('Unexpected public combined directory: '+name)
            elif not item.is_file() or (name not in names and not common._mutable(name)):
                raise common.PackageError('Unexpected public combined file: '+name)
            elif common._mutable(name) and item.stat().st_size > common._MAX_FILE:
                raise common.PackageError('A public combined diagnostic exceeds its bound.')
    return dict(expected, root=root, path=root, food_path=root/'food', world_path=root/'world',
                launcher_path=root/'launcher', verified=True)


def prepare_public_food_world_package(output_dir, source_game, copy_game, *, compiler_path,
                                      bug_fixes_enabled=False):
    """Build one fresh closed package without reading any private input store."""
    stock._bug_fix_manifest(bug_fixes_enabled)
    combined._policy(city_statistics_guard=bug_fixes_enabled)
    source, copy = stock._paths(str(common._checked_path(Path(source_game))),
                               str(common._checked_path(Path(copy_game), exists=False)))
    output = common._package_output(output_dir, source, copy, None)
    compiler = common._checked_path(Path(compiler_path))
    originals, source_proof = _originals(source)
    view, unused = food._build_view_from_source(source, compiler)
    welt, unused = food._build_welt_from_source(source, city_statistics_guard=bug_fixes_enabled)
    host = _native_host(originals, view, welt, city_statistics_guard=bug_fixes_enabled)
    ai, ai_proof = _private_ai(originals)
    assets, unused = beta_inputs.derive_beta_assets(source)
    workspace = common._package_output(output.parent/('build-food-world-'+uuid.uuid4().hex[:16]), source, copy, None)
    workspace.mkdir(parents=True, exist_ok=False)
    for prefix, values in (('native-host', host), ('assets', {name.removeprefix('assets/'):value for name,value in assets.items()})):
        for name, value in values.items():
            target = workspace/prefix/common._name(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(value)
    report = native.build_public_food_world_runtime(workspace/'native-host', source, workspace/'assets', compiler,
        (ai, ai_proof), output=workspace/'runtime', source_proof={name:source_proof[name]
            for name in ('source_native_profile','source_native_sha256')},
        city_statistics_guard=bug_fixes_enabled)
    runtime_file = common._checked_path(Path(report['runtime_path']))
    files = _recipe(source, copy, common._read(runtime_file.parent, runtime_file.name), view, welt,
                    bug_fixes_enabled=bug_fixes_enabled, city_statistics_guard=bug_fixes_enabled)
    files['manifest.json'] = common._encoded(_manifest(source, copy, files, bug_fixes_enabled=bug_fixes_enabled,
                                                     city_statistics_guard=bug_fixes_enabled))
    return common._publish(files, output, source)
