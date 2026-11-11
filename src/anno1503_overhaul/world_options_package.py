"""Separate pinned installer generation for the expanded in-game World menu.

Old packages retain their original validators and runtime pins. New packages
recompute their whole recipe from the frozen corpus and reviewed new source.
"""
import os
from pathlib import Path, PurePosixPath
import re

from . import packages as common
from . import world_only_package as stock
from . import world_runtime_build as base
from .world_options import VERSION, SETTINGS_SIZE, PREVIEW_SIZE, generator_id
from .world_options_build import PINNED_RUNTIMES

ROOT = common.ROOT
KIND = 'anno1503-world-options-installer-package'


def _policy(food):
    from .world_options_build import PINNED_GENERATOR
    profile = 'food-world' if food else 'world-only'
    digest = PINNED_RUNTIMES[profile]
    if not re.fullmatch(r'[0-9a-f]{64}', digest):
        raise common.PackageError('The expanded World Settings runtime has not passed its build review yet.')
    if generator_id() != PINNED_GENERATOR:
        raise common.PackageError('World generator source changed after its runtime review. Rebuild and review both native profiles.')
    return profile, digest


def _runtime_path(food):
    profile, digest = _policy(food)
    return ROOT / '.local/runtime-profiles' / ('options-' + profile + '-' + digest[:16]) / 'AnnoWorldSettings.dll'


def _recipe(raw, corpus, native, runtime, source, copy, food, baselines=None):
    profile, runtime_sha = _policy(food)
    frozen, unused = common._world_spec(raw, source, copy)
    if set(corpus) != set(frozen['payloads']):
        raise common.PackageError('The frozen World options input inventory differs.')
    for name, digest in frozen['payloads'].items():
        common._require_sha(corpus[name], digest, 'frozen/' + name)
    common._require_sha(runtime, runtime_sha, 'expanded World Settings runtime')
    common._amd64(runtime, 'expanded World Settings runtime')
    if food:
        unused, files = common._recipe(raw, source, copy, baselines)
        files.update({'world/' + name: value for name, value in corpus.items()})
        files.update({'world/frozen-inputs/' + name: value for name, value in corpus.items()})
        spec = common._json(files['world/world_patch.json'], 'World specification')
        spec['payloads']['native/AnnoWorldSettings.dll'] = runtime_sha
        engine_sha = frozen['expanded_engine_plan_sha256']
    else:
        engine_sha = base.WORLD_ONLY_ENGINE_PLAN_SHA256
        files = stock._recipe(raw, native, corpus, runtime, source, copy, baselines=baselines,
                              runtime_policy=(runtime_sha, engine_sha, base.STOCK_SHA256))
        spec = common._json(files['world/world_patch.json'], 'World-only specification')
    files['world/native/AnnoWorldSettings.dll'] = runtime
    # Preserve frozen inputs and historical recipes. Only the two private AI
    # payloads in this new options generation receive the reviewed activity
    # derivative; original host modules and Food changes stay byte-exact.
    from .world_options_factions import PROFILE_INPUT_SHA256, derive_faction_ai
    for name in ('CompLogic.dll', 'CompLogicClassic.dll'):
        target = 'WorldSettingsAI/' + name
        payload = spec['introduced_files'][target]
        key = 'world/' + payload
        try:
            value, unused_proof = derive_faction_ai(name, files[key], PROFILE_INPUT_SHA256[profile][name])
        except base.RuntimeBuildError as exc:
            raise common.PackageError('The exact private faction AI input or native policy differs: ' + name) from exc
        files[key] = value
        spec['payloads'][payload] = common._sha(value)
    spec['world_options'] = dict(version=VERSION, generator_id=generator_id(), settings_size=SETTINGS_SIZE,
                                 preview_size=PREVIEW_SIZE, food_enabled=food)
    files['world/world_patch.json'] = common._encoded(spec)
    files['world/activation/preview_snapshot.py'] = common._read(ROOT, 'src/anno1503_overhaul/world_options_snapshot.py')
    config = common._json(files['launcher/launcher_config.json'], 'launcher configuration')
    config.update(runtime_sha256=runtime_sha, package_spec_sha256=common._sha(files['world/world_patch.json']),
                  world_options_version=VERSION, food_enabled=food, generator_id=generator_id())
    files['launcher/launcher_config.json'] = common._encoded(config)
    return files, engine_sha


def _manifest(source, copy, food, files, engine):
    profile, runtime = _policy(food)
    return dict(schema_version=1, kind=KIND, version=VERSION, profile=profile,
                source_root=source, copy_root=copy, food_enabled=food,
                runtime_sha256=runtime, engine_plan_sha256=engine, generator_id=generator_id(),
                feature_versions={'world_settings': VERSION, **({'food_overhaul': '0.5.0'} if food else {})},
                frozen_world_spec_sha256=common.FROZEN_WORLD_SPEC_SHA256,
                files={name: common._sha(value) for name, value in sorted(files.items())},
                actual_game_test_performed=False)


def validate_options_package(path, source_game=None):
    root = common._checked_path(Path(path))
    manifest = common._json(common._read(root, 'manifest.json'), 'World options manifest')
    if manifest.get('kind') != KIND or type(manifest.get('food_enabled')) is not bool:
        raise common.PackageError('Unknown World options package profile.')
    food = manifest['food_enabled']
    source, copy = stock._paths(manifest.get('source_root'), manifest.get('copy_root'))
    if source_game is not None and common._checked_path(Path(source_game)) != source:
        raise common.PackageError('These World options belong to another original game folder.')
    raw = common._read(root, 'world/frozen_world_patch.json')
    frozen, unused = common._world_spec(raw, str(source), str(copy))
    corpus = {name: common._read(root, 'world/frozen-inputs/' + common._name(name)) for name in frozen['payloads']}
    native = {} if food else {name: common._read(root, 'world/stock/' + name) for name in stock._STOCK_NAMES}
    runtime = common._read(root, 'world/native/AnnoWorldSettings.dll')
    files, engine = _recipe(raw, corpus, native, runtime, str(source), str(copy), food)
    expected = _manifest(str(source), str(copy), food, files, engine)
    if common._encoded(manifest) != common._encoded(expected):
        raise common.PackageError('The World options manifest differs from its reviewed recipe.')
    for name, value in files.items():
        if common._read(root, name) != value:
            raise common.PackageError('A World options helper, input or payload changed: ' + name)
    names = set(files) | {'manifest.json'}
    directories = {str(p) for name in names for p in PurePosixPath(name).parents if str(p) != '.'}
    directories.add('launcher/logs')
    for folder, dirs, entries in os.walk(root, followlinks=False):
        for name in dirs + entries:
            path = Path(folder) / name
            common._checked_path(path)
            relative = path.relative_to(root).as_posix()
            if path.is_dir():
                if relative not in directories:
                    raise common.PackageError('Unexpected World options package directory: ' + relative)
            elif not path.is_file() or (relative not in names and not common._mutable(relative)):
                raise common.PackageError('Unexpected World options package file: ' + relative)
            elif common._mutable(relative) and path.stat().st_size > common._MAX_FILE:
                raise common.PackageError('A World options diagnostic exceeds its bound.')
    return dict(expected, root=root, path=root, world_path=root / 'world', food_path=root / 'food',
                launcher_path=root / 'launcher', verified=True)


def prepare_options_package(baselines_dir, output_dir, source_game, copy_game, *, food_enabled, runtime_path=None):
    if type(food_enabled) is not bool:
        raise common.PackageError('Choose an exact Food feature selection.')
    baselines = common._checked_path(Path(baselines_dir))
    source, copy = stock._paths(str(common._checked_path(Path(source_game))),
                                str(common._checked_path(Path(copy_game), exists=False)))
    output = common._package_output(output_dir, source, copy, baselines)
    raw = common._read(baselines / 'world_settings', 'world_patch.json')
    frozen, unused = common._world_spec(raw, str(source), str(copy))
    corpus = {name: common._read(baselines / 'world_settings', common._name(name)) for name in frozen['payloads']}
    native = {} if food_enabled else stock._stock_inputs(source)
    runtime = common._checked_path(Path(runtime_path) if runtime_path is not None else _runtime_path(food_enabled))
    if not runtime.is_file() or runtime.stat().st_size > common._MAX_FILE:
        raise common.PackageError('The reviewed World options runtime is missing or too large.')
    files, engine = _recipe(raw, corpus, native, runtime.read_bytes(), str(source), str(copy), food_enabled, baselines)
    files['manifest.json'] = common._encoded(_manifest(str(source), str(copy), food_enabled, files, engine))
    return common._publish(files, output, source)
