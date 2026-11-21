"""Closed Food06 + World Settings package for an independent managed host.

Neither the preserved Food05 combined package nor the stock World-only recipe
is changed. Original Food recovery inputs and the frozen World corpus remain
byte-exact; new native derivatives have their own complete fingerprints.
"""
from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import re

from . import packages as common
from . import food06_package as food
from . import world_only_package as stock
from .food_world_policy import KIND, PROFILE, food_files
from .food_diet import VERSION
from .world_options import VERSION as WORLD_VERSION, generator_id, SETTINGS_SIZE, PREVIEW_SIZE


def _policy(*, city_statistics_guard=False):
    from . import food_world_runtime as native
    from .world_options_build import PINNED_GENERATOR
    if any(not isinstance(pin, str) or re.fullmatch(r'[0-9a-f]{64}', pin) is None
           for pin in (native.runtime_hash(city_statistics_guard),
                       native.engine_plan_hash(city_statistics_guard))):
        raise common.PackageError('The combined Food06 native runtime has not passed build review.')
    if generator_id() != PINNED_GENERATOR:
        raise common.PackageError('World generator source changed after runtime review.')
    return native


def _runtime_path(*, city_statistics_guard=False):
    native = _policy(city_statistics_guard=city_statistics_guard)
    pin = native.runtime_hash(city_statistics_guard)
    return common.ROOT / '.local/runtime-profiles' / ('options-' + PROFILE + '-' + pin[:16]) / 'AnnoWorldSettings.dll'


def _private_ai(corpus):
    from .world_options_factions import PROFILE_INPUT_SHA256, derive_faction_ai
    from .food_world_ai import derive_food06_ai
    result = {}
    for name in ('CompLogic.dll', 'CompLogicClassic.dll'):
        prior = corpus['native/' + name.removesuffix('.dll') + '.food-ai.dll']
        activity, _ = derive_faction_ai(name, prior, PROFILE_INPUT_SHA256['food-world'][name])
        result[name], _ = derive_food06_ai(name, activity)
    return result


def _native_food_policy(*, city_statistics_guard):
    path = 'src/anno1503_overhaul/food_world_policy.py'
    source = common._read(common.ROOT, path)
    policy = food_files()
    if city_statistics_guard:
        world = policy['AnnoWelt.dll']
        plain = world['after_sha256']
        guarded = food._welt_policy(city_statistics_guard=True)
        source = common._replace(source, plain.encode('ascii'), guarded.encode('ascii'), path)
        world['after_sha256'] = guarded
    return source, policy


def _source_readiness():
    """Two coherent exact source profiles; no mixture of historical versions."""
    return b'''"""Read-only normal-client source check for the combined Food06 host."""
from pathlib import Path
import hashlib,json
from native_ready import NativeReadiness
from managed_filesystem import checked_path,safe_child

def build_source_probe(package,spec):
    source=checked_path(Path(spec['input_source_root']))
    food=json.loads((package/'food_patch.json').read_bytes())
    def sha(name):
        return hashlib.sha256(safe_child(source,name,exists=True).read_bytes()).hexdigest()
    if sha('Anno1503.exe')!=spec['exe_sha256']:
        raise RuntimeError('The normal Ubisoft executable differs from the supported build.')
    profiles={
        'vanilla':{entry['name']:entry['sources']['vanilla'] for entry in food['native_modules']},
        'food05':{entry['name']:entry['after_sha256'] for entry in food['native_modules']},
    }
    native={name:sha(name) for name in profiles['vanilla']}
    matches=[name for name,expected in profiles.items() if native==expected]
    if len(matches)!=1:
        raise RuntimeError('The normal Ubisoft source must be one exact stock or Food 0.5 native profile.')
    resident=food['files']['Data/BGruppen.dat']
    expected=resident['sources']['vanilla'] if matches[0]=='vanilla' else resident['after_sha256']
    if sha('Data/BGruppen.dat')!=expected:
        raise RuntimeError('The normal Ubisoft resident data and native source profile differ.')
    for name in ('AnnoScene.dll','AnnoDisplay.dll'):
        native[name]=spec['native_sha256'][name]
        if sha(name)!=native[name]:
            raise RuntimeError('A normal Ubisoft source module differs: '+name)
    inputs=dict(source=source,copy=source,exe_sha256=spec['exe_sha256'],
                native_sha256=native,private_native_sha256={})
    return source,NativeReadiness(package,inputs,frame_sha=native['AnnoFrame.dll'])
'''


def _bug_fix_support():
    """Stage the authored transforms with a private, closed import namespace."""
    files = {}
    transformations = {
        'bug_fixes.py': ('_combined_bug_fixes.py', (
            (b'from .filesystem import file_sha, safe_child', b'from _combined_filesystem import file_sha, safe_child'),)),
        'ambient_sound.py': ('_combined_ambient_sound.py', (
            (b'from .ambient_sound_baselines import localized_sample_baselines', b'from _combined_ambient_sound_baselines import localized_sample_baselines'),
            (b'from .bug_fixes import BugFixError', b'from _combined_bug_fixes import BugFixError'),
            (b'from .filesystem import safe_child', b'from _combined_filesystem import safe_child'))),
        'filesystem.py': ('_combined_filesystem.py', ()),
        'ambient_sound_baselines.py': ('_combined_ambient_sound_baselines.py', ()),
        'food_world_bug_fixes.py': ('_combined_bugfix_recipe.py', (
            (b'from .ambient_sound import ambient_sound_assets', b'from _combined_ambient_sound import ambient_sound_assets'),
            (b'from .bug_fixes import king_of_ore_assets', b'from _combined_bug_fixes import king_of_ore_assets'))),
    }
    for original, (staged, substitutions) in transformations.items():
        value = common._read(common.ROOT, 'src/anno1503_overhaul/' + original)
        for before, after in substitutions:
            value = common._replace(value, before, after, original)
        files['world/support/' + staged] = value
    return files


def _recipe(raw, corpus, runtime, view, welt, source, copy, baselines=None, *, bug_fixes_enabled=False,
            city_statistics_guard=False):
    if (type(bug_fixes_enabled) is not bool or type(city_statistics_guard) is not bool
            or city_statistics_guard and not bug_fixes_enabled):
        raise common.PackageError('Choose an explicit Bug Fixes selection for this combined package.')
    native = _policy(city_statistics_guard=city_statistics_guard)
    runtime_pin = native.runtime_hash(city_statistics_guard)
    engine_pin = native.engine_plan_hash(city_statistics_guard)
    host = native.expected_native_hashes(city_statistics_guard=True) if city_statistics_guard else native.HOST_SHA256
    frozen, files = common._recipe(raw, source, copy, baselines)
    if set(corpus) != set(frozen['payloads']):
        raise common.PackageError('The combined frozen World inventory differs.')
    for name, digest in frozen['payloads'].items():
        common._require_sha(corpus[name], digest, 'combined frozen/' + name)
    common._require_sha(runtime, runtime_pin, 'combined Food06 World runtime')
    common._amd64(runtime, 'combined Food06 World runtime')
    food_inputs = food._recipe(source, copy, view, welt, city_statistics_guard=city_statistics_guard)
    files.update(food_inputs)
    files.update({'world/' + name.removeprefix('food/'): value for name, value in food_inputs.items()})
    files.update({'world/frozen-inputs/' + name: value for name, value in corpus.items()})
    files['world/frozen_world_patch.json'] = raw
    files['world/world_mod.py'] = common._read(common.ROOT, 'src/anno1503_overhaul/food_world_backend.py')
    policy_source, native_food_policy = _native_food_policy(city_statistics_guard=city_statistics_guard)
    files['world/support/food_world_policy.py'] = policy_source
    files['world/support/stock_baseline.py'] = common._read(common.ROOT, 'src/anno1503_overhaul/vanilla.py')
    bug_fixes = None
    if bug_fixes_enabled:
        from .food_world_bug_fixes import recipe as bug_fix_recipe
        bug_fixes = bug_fix_recipe(Path(source))
        files.update(_bug_fix_support())
    files['world/activation/preflight.py'] = stock._preflight_source()
    files['world/activation/preview_snapshot.py'] = common._read(common.ROOT, 'src/anno1503_overhaul/world_options_snapshot.py')
    engine_name = 'world/developer/huge_world/runtime_engine_edits.json'
    engine = native.derive_engine_plan(welt, files[engine_name])
    common._require_sha(engine, engine_pin, 'combined Food06 active engine plan')
    files[engine_name] = engine
    introduced = {'AnnoWorldSettings.dll': 'native/AnnoWorldSettings.dll',
                  'WorldSettingsAI/CompLogic.dll': 'native/CompLogic.food06.dll',
                  'WorldSettingsAI/CompLogicClassic.dll': 'native/CompLogicClassic.food06.dll'}
    introduced.update({name: payload for name, payload in frozen['introduced_files'].items()
                       if payload in frozen['data_payloads']})
    ai = _private_ai(corpus)
    payloads = {'native/AnnoWorldSettings.dll': runtime,
                'native/CompLogic.food06.dll': ai['CompLogic.dll'],
                'native/CompLogicClassic.food06.dll': ai['CompLogicClassic.dll']}
    payloads.update({name: corpus[name] for name in frozen['data_payloads']})
    files.update({'world/' + name: value for name, value in payloads.items()})
    spec = dict(profile=PROFILE, version=WORLD_VERSION, food_version=VERSION, status='DEVELOPMENT',
                food_enabled=True, host_root=copy, input_source_root=source, original_game_root=copy,
                exe_sha256=frozen['exe_sha256'], native_sha256=host,
                food_files=native_food_policy, new_world_required=True, old_save_migration_supported=False,
                introduced_files=introduced,
                payloads={name: common._sha(value) for name, value in sorted(payloads.items())},
                expanded_engine_patch_count=173, expanded_engine_plan_sha256=engine_pin,
                frozen_world_spec_sha256=common.FROZEN_WORLD_SPEC_SHA256,
                world_options=dict(version=WORLD_VERSION, generator_id=generator_id(),
                                   settings_size=SETTINGS_SIZE, preview_size=PREVIEW_SIZE, food_enabled=True),
                actual_game_run=False, packaged_runtime_gameplay_verified=False, complete_feature_verified=False)
    if bug_fixes_enabled:
        spec['bug_fixes'] = bug_fixes
    files['world/world_patch.json'] = common._encoded(spec)
    config = dict(version='1.0.0', profile=PROFILE, food_version=VERSION, food_enabled=True,
                  package_relative='../world', package_spec_sha256=common._sha(files['world/world_patch.json']),
                  runtime_sha256=runtime_pin, engine_patch_count=173, timeout_seconds=300,
                  copy_root=copy, input_source_root=source, world_options_version=WORLD_VERSION,
                  generator_id=generator_id(), modular_adapter_version='1.0')
    files['launcher/launcher_config.json'] = common._encoded(config)
    # Keep the existing single owned normal-client handoff. Only the copied
    # host's default Frame pin differs from stock; the source probe stays exact.
    stock._launcher_recipe(files, source, copy)
    files['launcher/source_readiness.py'] = _source_readiness()
    name = 'launcher/native_ready.py'
    files[name] = common._replace(files[name],
        b'FRAME_SHA256 = "dfd7c76dfc0b017fa5142c46a2bb084c01fc750a049d85ca70b56dca2f555ccd"',
        b'FRAME_SHA256 = "046b5ad6f351dfe867ed38ce29fb50a594485b43a32ee90adadc48e850466baf"', name)
    files[name] = common._replace(files[name],
        b'frame_sha not in (FRAME_SHA256,"046b5ad6f351dfe867ed38ce29fb50a594485b43a32ee90adadc48e850466baf")',
        b'frame_sha not in (FRAME_SHA256,"dfd7c76dfc0b017fa5142c46a2bb084c01fc750a049d85ca70b56dca2f555ccd")', name)
    return files


def _manifest(source, copy, files, *, bug_fixes_enabled=False, city_statistics_guard=False):
    native = _policy(city_statistics_guard=city_statistics_guard)
    versions = {'food_overhaul': VERSION, 'world_settings': WORLD_VERSION}
    if bug_fixes_enabled:
        from .food_world_bug_fixes import VERSION as BUG_FIXES_VERSION
        versions['bug_fixes'] = BUG_FIXES_VERSION
    result = dict(schema_version=1, kind=KIND, profile=PROFILE, version=VERSION,
                source_root=source, copy_root=copy, food_enabled=True,
                feature_versions=versions,
                runtime_sha256=native.runtime_hash(city_statistics_guard),
                engine_plan_sha256=native.engine_plan_hash(city_statistics_guard),
                view_sha256=food._view_policy(), welt_sha256=food._welt_policy(city_statistics_guard=city_statistics_guard),
                generator_id=generator_id(),
                world_settings_supported=True, new_world_required=True, old_save_migration_supported=False,
                frozen_world_spec_sha256=common.FROZEN_WORLD_SPEC_SHA256,
                files={name: common._sha(value) for name, value in sorted(files.items())},
                actual_game_test_performed=False)
    if bug_fixes_enabled:
        result['bug_fixes_enabled'] = True
    if city_statistics_guard:
        result['city_statistics_guard'] = True
    return result


def validate_food_world_package(path, source_game=None):
    root = common._checked_path(Path(path))
    manifest = common._json(common._read(root, 'manifest.json'), 'combined Food06 manifest')
    if manifest.get('kind') != KIND:
        raise common.PackageError('Unknown combined Food06 package kind.')
    source, copy = stock._paths(manifest.get('source_root'), manifest.get('copy_root'))
    if source_game is not None and common._checked_path(Path(source_game)) != source:
        raise common.PackageError('This combined package belongs to another original game.')
    raw = common._read(root, 'world/frozen_world_patch.json')
    frozen, _ = common._world_spec(raw, str(source), str(copy))
    corpus = {name: common._read(root, 'world/frozen-inputs/' + common._name(name)) for name in frozen['payloads']}
    bug_fixes_enabled = manifest.get('bug_fixes_enabled', False)
    city_statistics_guard = manifest.get('city_statistics_guard', False)
    if type(bug_fixes_enabled) is not bool:
        raise common.PackageError('The combined package has no explicit Bug Fixes selection.')
    files = _recipe(raw, corpus, common._read(root, 'world/native/AnnoWorldSettings.dll'),
                    common._read(root, food.VIEW_PAYLOAD), common._read(root, food.WELT_PAYLOAD), str(source), str(copy),
                    bug_fixes_enabled=bug_fixes_enabled, city_statistics_guard=city_statistics_guard)
    expected = _manifest(str(source), str(copy), files, bug_fixes_enabled=bug_fixes_enabled,
                         city_statistics_guard=city_statistics_guard)
    if common._encoded(manifest) != common._encoded(expected):
        raise common.PackageError('The combined Food06 manifest differs from its reviewed recipe.')
    for name, value in files.items():
        if common._read(root, name) != value:
            raise common.PackageError('A combined helper, input or payload changed: ' + name)
    names = set(files) | {'manifest.json'}
    directories = {str(p) for name in names for p in PurePosixPath(name).parents if str(p) != '.'}
    directories.add('launcher/logs')
    for folder, dirs, entries in os.walk(root, followlinks=False):
        for name in dirs + entries:
            item = Path(folder) / name
            common._checked_path(item)
            relative = item.relative_to(root).as_posix()
            if item.is_dir():
                if relative not in directories:
                    raise common.PackageError('Unexpected combined package directory: ' + relative)
            elif not item.is_file() or (relative not in names and not common._mutable(relative)):
                raise common.PackageError('Unexpected combined package file: ' + relative)
            elif common._mutable(relative) and item.stat().st_size > common._MAX_FILE:
                raise common.PackageError('A combined diagnostic exceeds its bound.')
    return dict(expected, root=root, path=root, food_path=root / 'food', world_path=root / 'world',
                launcher_path=root / 'launcher', verified=True)


def prepare_food_world_package(baselines_dir, output_dir, source_game, copy_game, *, runtime_path=None, compiler_path=None,
                               bug_fixes_enabled=False):
    """Prepare a new combined package; never write to either game directory."""
    if type(bug_fixes_enabled) is not bool:
        raise common.PackageError('Choose an explicit Bug Fixes selection for this combined package.')
    _policy(city_statistics_guard=bug_fixes_enabled)
    baselines = common._checked_path(Path(baselines_dir) if baselines_dir is not None else common.ROOT / '.local/baselines')
    source, copy = stock._paths(str(common._checked_path(Path(source_game))),
                                str(common._checked_path(Path(copy_game), exists=False)))
    output = common._package_output(output_dir, source, copy, baselines)
    if compiler_path is None:
        from .beta_paths import compiler_path as find_compiler
        compiler_path = find_compiler()
    compiler = common._checked_path(Path(compiler_path))
    view, _ = food._build_view_from_source(source, compiler)
    welt, _ = food._build_welt_from_source(source, city_statistics_guard=bug_fixes_enabled)
    runtime = common._checked_path(Path(runtime_path) if runtime_path is not None
                                   else _runtime_path(city_statistics_guard=bug_fixes_enabled))
    if not runtime.is_file() or runtime.stat().st_size > common._MAX_FILE:
        raise common.PackageError('The reviewed combined Food06 runtime is missing or too large.')
    raw = common._read(baselines / 'world_settings', 'world_patch.json')
    frozen, _ = common._world_spec(raw, str(source), str(copy))
    corpus = {name: common._read(baselines / 'world_settings', common._name(name)) for name in frozen['payloads']}
    files = _recipe(raw, corpus, runtime.read_bytes(), view, welt, str(source), str(copy), baselines,
                    bug_fixes_enabled=bug_fixes_enabled, city_statistics_guard=bug_fixes_enabled)
    files['manifest.json'] = common._encoded(_manifest(str(source), str(copy), files,
                                                     bug_fixes_enabled=bug_fixes_enabled,
                                                     city_statistics_guard=bug_fixes_enabled))
    return common._publish(files, output, source)
