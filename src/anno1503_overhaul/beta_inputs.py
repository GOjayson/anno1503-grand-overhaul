"""Reconstruct World-only beta inputs from tracked source and a user's game.

No historical private package, Food AI DLL or patched game DLL is an input.
Known original backup bytes may be read, but the source game is never changed.
The prepared cache contains locally owned game derivatives, not release files.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import uuid

from .filesystem import CopyError, checked_path, relative_name, safe_child, file_sha
from . import vanilla
from . import world_runtime_build as native
from .world_native import derive_public_ai_candidate
from .world_options_factions import derive_faction_ai, PROFILE_INPUT_SHA256
from .world_options_visibility_calls import DISPLAY_SHA256
from .world_options import generator_id, SETTINGS_SIZE, PREVIEW_SIZE, VERSION

ROOT = Path(__file__).resolve().parents[2]
KIND = 'anno1503-public-world-only-inputs'
MANIFEST = 'beta-inputs.json'
COMPILER_VERSION = '0.16.0'
_ASSET_POLICIES = {
    'pirate': 'legacy/world_settings/support/package_alias_assets.py',
    'venetian': 'legacy/world_settings/developer/world_sizes/venetians/generate_venetian_assets.py',
    'world': 'legacy/world_settings/support/package_world_assets.py',
}
_CURRENT_AI = {
    'CompLogic.dll': 'd4dbe1844b2b3e3c3eddcc22d55a62b50d3e0d3fafcdb51ee5781395b812bc68',
    'CompLogicClassic.dll': '6227218f09e57db2211eb1afa11cb471d2dfd5228e7213fe2d54f717d6ef49d3',
}


class BetaInputError(ValueError):
    """The supported original inputs or a reproducible output are unavailable."""


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode('utf-8')


def _pairs(values):
    result = {}
    for key, value in values:
        if key in result:
            raise BetaInputError('The beta manifest contains a duplicate field: ' + key)
        result[key] = value
    return result


def _source_module(kind):
    """Import only a named, provenance-checked tracked data transformer."""
    relative = _ASSET_POLICIES[kind]
    provenance = json.loads((ROOT / 'provenance/legacy_import.json').read_bytes())
    records = {record['path']: record['imported_sha256'] for record in provenance['source_files']}
    path = checked_path(ROOT / relative)
    if relative not in records or file_sha(path) != records[relative]:
        raise BetaInputError('A tracked island construction recipe changed: ' + relative)
    spec = importlib.util.spec_from_file_location('_anno_beta_' + kind + '_' + uuid.uuid4().hex, path)
    if spec is None or spec.loader is None:
        raise BetaInputError('Cannot read the tracked island construction recipe.')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def derive_beta_assets(source_game):
    """Return all sixteen exact assets in memory; never write into the game."""
    game = checked_path(Path(source_game))
    pirate, venetian, world = (_source_module(kind) for kind in ('pirate', 'venetian', 'world'))
    result, inputs = {}, {}
    for record in pirate.RECORDS:
        source = safe_child(game, record['source'], exists=True).read_bytes()
        if _sha(source) != record['source_sha256']:
            raise BetaInputError('Unsupported original pirate island: ' + record['source'])
        position = pirate.inspect_alias(source, b'\0')
        at, stop = position['alias_offset'], position['alias_end']
        output = bytearray(source[:at] + b'ALIAS\0' + struct.pack('<H', 8) + b'PIRAT01\0' + source[stop:])
        struct.pack_into('<I', output, 12, position['root_end'] - 16 + 7)
        struct.pack_into('<I', output, position['profile_offset'] + 12, position['profile_size'] + 7)
        pirate.validate_source_copy(record, source, bytes(output))
        result['assets/' + record['copy_relative_path']] = bytes(output)
        inputs[record['source']] = _sha(source)
    scene_path = safe_child(game, venetian.SOURCE, exists=False)
    if not scene_path.is_file():
        raise BetaInputError(
            'The supported Dutch endless-game scene needed for the Venetian town is missing: '
            + venetian.SOURCE + '. This beta cannot yet derive the town from another language.')
    scene = scene_path.read_bytes()
    if _sha(scene) != venetian.SOURCE_SHA:
        raise BetaInputError('The supported endless-game scene for the Venetian town differs: ' + venetian.SOURCE)
    world.validate_required_copy(game)
    trailer_source = safe_child(game, venetian.TRAILER_SOURCE, exists=True).read_bytes()
    unused, trailer = venetian.envelope(trailer_source)
    if trailer != world.TRAILER:
        raise BetaInputError('The inspected stock island loading trailer differs.')
    output, detail = venetian.extract(scene, trailer)
    name = 'assets/' + venetian.ASSET
    world.validate_data_payload(name, output)
    result[name] = output
    inputs[venetian.SOURCE] = _sha(scene)
    inputs.update(world.required_copy_inputs())
    if len(result) != 16:
        raise BetaInputError('The complete pirate and Venetian asset inventory differs.')
    return result, dict(source_sha256=inputs, pirate_assets=15, venetian_assets=1,
                        venetian_buildings=detail['city_building_entry_count'])


def verify_beta_source(source_game):
    """Certify one coherent approved native set for the normal client handoff."""
    source = checked_path(Path(source_game))
    food = ROOT / 'legacy/food_overhaul'
    source_native = {name: file_sha(safe_child(source, name, exists=True))
                     for name in {**native.STOCK_SHA256, 'AnnoDisplay.dll': DISPLAY_SHA256}}
    food_spec = vanilla._spec(food)
    source_profile = None
    for profile in ('vanilla', 'combined-0.5.0'):
        approved = {**native.STOCK_SHA256, 'AnnoDisplay.dll': DISPLAY_SHA256}
        for entry in food_spec['native_modules']:
            if entry['name'] in approved:
                approved[entry['name']] = entry['sources'][profile]
        if source_native == approved:
            source_profile = profile
            break
    if source_profile is None:
        raise BetaInputError('Use the supported stock game or the exact supported Food 0.5 installation with verified original backups; this native source combination is not approved.')
    return dict(source_native_profile=source_profile, source_native_sha256=source_native)


def _stock_sources(source):
    """Select only verified originals; this deliberately performs no recovery writes."""
    food = ROOT / 'legacy/food_overhaul'
    source_proof = verify_beta_source(source)
    recovery = {record.name: record for record in vanilla.plan_vanilla_recovery(source, food)}
    expected = {**native.STOCK_SHA256, 'AnnoDisplay.dll': DISPLAY_SHA256,
                **{name: vanilla.VANILLA_ARCHIVE_HASHES[name] for name in ('Anlagen.dat', 'Anlagen.addon')}}
    selected = {}
    for name, digest in expected.items():
        original = safe_child(source, name, exists=True)
        record = recovery.get(name)
        if record is None:
            if file_sha(original) != digest:
                raise BetaInputError('The beta needs an exact supported original file or verified original backup: ' + name)
            selected[name] = dict(path=original, sha256=digest, offset=None, patch=None)
        else:
            backup = checked_path(record.source_file)
            if backup.stat().st_size != record.size or file_sha(backup) != record.sha256 or record.whole_sha256 != digest:
                raise BetaInputError('A verified original backup changed or belongs to another build: ' + name)
            selected[name] = dict(path=backup if record.offset is None else original, sha256=digest,
                                  offset=record.offset, patch=backup if record.offset is not None else None,
                                  current_sha256=record.current_sha256, patch_sha256=record.sha256)
    return selected, sorted(recovery), source_proof


def _compiler(path):
    path = checked_path(Path(path))
    if not path.is_file():
        raise BetaInputError('Select the Zig ' + COMPILER_VERSION + ' compiler executable.')
    process_options = {'creationflags':subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    result = subprocess.run([str(path), 'version'], capture_output=True, text=True, timeout=15, check=False,
                            **process_options)
    if result.returncode or result.stdout.strip() != COMPILER_VERSION:
        raise BetaInputError('This beta requires Zig ' + COMPILER_VERSION + '; no compiler was downloaded or installed.')
    return dict(path=str(path), sha256=file_sha(path), version=COMPILER_VERSION)


def _output_path(output, source):
    output = checked_path(Path(output), exists=False)
    protected = (source, ROOT / 'legacy', ROOT / '.local/baselines')
    if any(output == path or output.is_relative_to(path) or path.is_relative_to(output) for path in protected):
        raise BetaInputError('Choose a new beta cache outside the game and preserved source/baselines.')
    if output == ROOT or ROOT.is_relative_to(output) or (output.is_relative_to(ROOT) and not output.is_relative_to(ROOT / '.local')):
        raise BetaInputError('Beta caches inside this checkout must stay under ignored .local.')
    if os.path.lexists(output):
        raise BetaInputError('The beta cache already exists and was preserved; select a new output folder.')
    return output


def _small_stock(record):
    if record['offset'] is not None:
        raise BetaInputError('A native module unexpectedly requires an archive-region recovery.')
    data = record['path'].read_bytes()
    if _sha(data) != record['sha256']:
        raise BetaInputError('A supported native input changed during preparation.')
    return data


def _construction(source, compiler):
    compiled = native._verified_sources(ROOT)
    selected, recovery, source_proof = _stock_sources(source)
    assets, asset_proof = derive_beta_assets(source)
    files, ai_proofs = dict(assets), {}
    for name in ('CompLogic.dll', 'CompLogicClassic.dll'):
        base = derive_public_ai_candidate(name, _small_stock(selected[name]))
        prior = _sha(base)
        if prior != PROFILE_INPUT_SHA256['world-only'][name]:
            raise BetaInputError('The public World AI predecessor differs: ' + name)
        current, proof = derive_faction_ai(name, base, prior)
        if _sha(current) != _CURRENT_AI[name]:
            raise BetaInputError('The public World AI derivative differs: ' + name)
        files['ai-base/' + name] = base
        files['WorldSettingsAI/' + name] = current
        ai_proofs[name] = proof
    public_plan = checked_path(ROOT / native.SOURCE_PREFIX / native.ENGINE_PLAN).read_bytes()
    files['runtime_engine_edits.json'] = native.derive_engine_plan(
        _small_stock(selected['AnnoWelt.dll']), public_plan)
    if _sha(files['runtime_engine_edits.json']) != native.WORLD_ONLY_ENGINE_PLAN_SHA256:
        raise BetaInputError('The public stock engine instruction plan differs.')
    prerequisites = dict(profile='world-only', generator_id=generator_id(), version=VERSION,
        settings_size=SETTINGS_SIZE, preview_size=PREVIEW_SIZE, compiler=compiler,
        imported_compiled_source_sha256=compiled, assets=asset_proof, activity_ai=ai_proofs,
        source_recovery_files=recovery, historical_private_inputs_used=False, **source_proof)
    return files, selected, prerequisites


def _result(root, source, compiler, manifest):
    host = root / 'native-host'
    return dict(root=root, source_game=source, source_data_root=source,
        compiler_path=Path(compiler['path']), native_host_root=host,
        stock_native_bytes={name: (host / name).read_bytes() for name in {**native.STOCK_SHA256, 'AnnoDisplay.dll': DISPLAY_SHA256}},
        assets_root=root / 'assets', ai_base_root=root / 'ai-base',
        private_ai_root=root / 'WorldSettingsAI', engine_plan_path=root / 'runtime_engine_edits.json',
        manifest=manifest, runtime_built=False)


def _manifest(source, compiler, prerequisites, digests):
    assets = {name: digest for name, digest in digests.items() if name.startswith('assets/')}
    value = dict(schema=1, kind=KIND, source_root=str(source), compiler=compiler,
        prerequisites=prerequisites, files=digests,
        introduced_files={name.removeprefix('assets/'): name for name in assets},
        data_payloads=assets, game_executed=False, original_game_files_modified=False)
    # Return the same JSON-native value before and after publication. Native
    # proof helpers may expose tuples, whose JSON representation is a list.
    return json.loads(_encoded(value))


def prepare_beta_inputs(source_game, output_root, *, compiler_path):
    """Publish exact local prerequisites for the additive public World-only builder.

    This prepares an independent compiler host, not a playable game copy. The
    public native builder must consume its explicit asset and AI paths; no
    historical frozen-package specification is created or impersonated.
    """
    try:
        source = checked_path(Path(source_game))
        if not source.is_dir():
            raise BetaInputError('Select the supported Anno 1503 History Edition game folder.')
        output = _output_path(output_root, source)
        compiler = _compiler(compiler_path)
        files, selected, prerequisites = _construction(source, compiler)
        required = sum(record['path'].stat().st_size for record in selected.values()) + sum(map(len, files.values()))
        ancestor = output.parent
        while not ancestor.exists():
            ancestor = ancestor.parent
        if shutil.disk_usage(ancestor).free < required + 64 * 1024 * 1024:
            raise BetaInputError('There is not enough free space for the independent beta compiler inputs.')
        output.parent.mkdir(parents=True, exist_ok=True)
        checked_path(output.parent)
        stage = output.parent / ('.beta-input-staging-' + uuid.uuid4().hex)
        stage.mkdir()
        # A failed cache is deliberately retained for inspection. It never
        # becomes the named published output and no game/backup is a target.
        for relative, record in selected.items():
            target = stage / 'native-host' / relative_name(relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            checked_path(target.parent)
            with record['path'].open('rb') as incoming, target.open('x+b') as outgoing:
                shutil.copyfileobj(incoming, outgoing, 1024 * 1024)
                if record['offset'] is not None:
                    patch = record['patch'].read_bytes()
                    if _sha(patch) != record['patch_sha256']:
                        raise BetaInputError('A supported archive backup changed during preparation.')
                    outgoing.seek(record['offset']); outgoing.write(patch)
                outgoing.flush(); os.fsync(outgoing.fileno())
            if file_sha(target) != record['sha256']:
                raise BetaInputError('A reconstructed stock compiler input differs: ' + relative)
        for relative, data in files.items():
            target = stage / relative_name(relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(data)
        digests = {name: _sha(data) for name, data in files.items()}
        digests.update({'native-host/' + name: record['sha256'] for name, record in selected.items()})
        manifest = _manifest(source, compiler, prerequisites, digests)
        with (stage / MANIFEST).open('xb') as stream:
            stream.write(_encoded(manifest)); stream.flush(); os.fsync(stream.fileno())
        if os.path.lexists(output):
            raise BetaInputError('The beta output appeared during preparation and was preserved.')
        stage.rename(output)
        return _result(output, source, compiler, manifest)
    except BetaInputError:
        raise
    except (OSError, KeyError, TypeError, ValueError, CopyError, vanilla.VanillaError,
            native.RuntimeBuildError, subprocess.SubprocessError) as exc:
        raise BetaInputError('Cannot prepare public World-only inputs: ' + str(exc)) from exc


def validate_beta_inputs(input_root, source_game=None):
    """Reconstruct the recipe; a modified local manifest cannot bless payloads."""
    try:
        root = checked_path(Path(input_root))
        manifest_path = safe_child(root, MANIFEST, exists=True)
        if manifest_path.stat().st_size > 4 * 1024 * 1024:
            raise BetaInputError('The beta input manifest exceeds its supported bound.')
        manifest = json.loads(manifest_path.read_bytes(), object_pairs_hook=_pairs)
        if not isinstance(manifest, dict) or manifest.get('kind') != KIND or type(manifest.get('schema')) is not int or manifest.get('schema') != 1:
            raise BetaInputError('Unknown public beta input generation.')
        source = checked_path(Path(manifest['source_root']))
        if source_game is not None and checked_path(Path(source_game)) != source:
            raise BetaInputError('These beta inputs belong to another source game.')
        compiler = _compiler(manifest['compiler']['path'])
        files, selected, prerequisites = _construction(source, compiler)
        digests = {name: _sha(data) for name, data in files.items()}
        digests.update({'native-host/' + name: record['sha256'] for name, record in selected.items()})
        expected = _manifest(source, compiler, prerequisites, digests)
        if _encoded(manifest) != _encoded(expected):
            raise BetaInputError('The beta input manifest differs from the exact public recipe.')
        names = set(digests) | {MANIFEST}
        directories = {parent.as_posix() for name in names for parent in Path(name).parents if parent.as_posix() != '.'}
        for folder, dirs, entries in os.walk(root, followlinks=False):
            for name in dirs + entries:
                path = checked_path(Path(folder) / name)
                relative = path.relative_to(root).as_posix()
                if path.is_dir():
                    if relative not in directories:
                        raise BetaInputError('Unexpected beta input directory: ' + relative)
                elif relative not in names or not path.is_file() or (relative != MANIFEST and file_sha(path) != digests[relative]):
                    raise BetaInputError('A public beta input is unexpected or changed: ' + relative)
        for name in names:
            safe_child(root, name, exists=True)
        return _result(root, source, compiler, manifest)
    except BetaInputError:
        raise
    except (OSError, KeyError, TypeError, ValueError, CopyError, vanilla.VanillaError,
            native.RuntimeBuildError, subprocess.SubprocessError) as exc:
        raise BetaInputError('Cannot validate public World-only inputs: ' + str(exc)) from exc
