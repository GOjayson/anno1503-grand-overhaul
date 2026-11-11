"""Build new in-game options on either exact native host, in fresh staging.

The historical builders and runtime profiles remain available byte-for-byte.
Candidate builds never publish/install themselves. Publication requires the
separately reviewed canonical fingerprint in PINNED_RUNTIMES.
"""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

from . import world_runtime_build as old
from .filesystem import checked_path
from .world_options import apply_options, generator_id, PRIVATE, SETTINGS_SIZE, PREVIEW_SIZE, VERSION
from .world_options_visibility_calls import CALLS, DISPLAY_SHA256, verify_visibility_call_preimages
from .world_options_visibility_hooks import IMPORT_HOOKS, verify_import_visibility_preimages
from .world_options_disasters import DISASTER_CALLS, verify_disaster_preimages


PINNED_RUNTIMES = {
    'world-only': '91f0d2acbd3ad17f23cd4bfe4e0813c5e55c394ca06426b835b0015b3b926140',
    'food-world': '1b7248098910f550d7cb5ffc74bcb415f41b47a34f6ac8585bd67f9b79869677',
}
PINNED_GENERATOR = 'ws6-a2d7e8ee018ab1e6a18a933efbb8482391c78e35a54e29b05523e5af24a6ea2e'
REQUIRED_EXPORTS = old.REQUIRED_EXPORTS | {'WorldSettingsSettingsSize', 'WorldSettingsBuildPlan',
    'WorldSettingsPlanCount', 'WorldSettingsPlanIsland', 'WorldSettingsStartingIslandEligible',
    'WorldSettingsStartingIslandChosen', 'WorldSettingsIslandDetails',
    'WorldSettingsStartOwner', 'WorldSettingsDescribeStarts', 'WorldSettingsExpectedFairOwners',
    'WorldSettingsVisibilityDrawTerrain', 'WorldSettingsVisibilityDrawTerrainClipped',
    'WorldSettingsVisibilityCreateMap', 'WorldSettingsVisibilityPatchStatus',
    'WorldSettingsCopyVisibilityDiagnostics', 'WorldSettingsCopyVisibilityRenderTargets',
    'WorldSettingsVisibilityRenderStatic180', 'WorldSettingsVisibilityRenderStatic188',
    'WorldSettingsVisibilityDrawWildlife',
    'WorldSettingsVisibilityDrawWildlifeClipped',
    'WorldSettingsVisibilitySaveBlob', 'WorldSettingsVisibilityStageBlob',
    'WorldSettingsVisibilityApplyBlob', 'WorldSettingsVisibilityCancelBlob',
    'WorldSettingsVisibilityBeforeLoad', 'WorldSettingsVisibilityAfterLoad',
    'WorldSettingsVisibilityCancelLoad', 'WorldSettingsVisibilityReleaseUnpublishedScene',
    'WorldSettingsVisibilityCommitFresh', 'WorldSettingsVisibilityCancelFresh',
    'WorldSettingsVisibilityBuildingCommand', 'WorldSettingsVisibilityShipQueue',
    'WorldSettingsCopyMemoryError',
    'WorldSettingsCopyVisibilityChartDiagnostics',
    'WorldSettingsCopyVisibilityPerformance'} | {row[4] for row in CALLS} | {row[5] for row in IMPORT_HOOKS} | {row[4] for row in DISASTER_CALLS}
UNITS = [PRIVATE + name for name in ('WorldSettings.c', 'world_backend.c', 'world_ai.c')]
UNITS += ['developer/source/world_factory.c', old.AI_LOADER,
          'developer/source/engine_resume/route_coverage/selection.c',
          'developer/source/runtime_dev3/compiled_hooks.c']


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def derive_activity_ai_inputs(profile: str, game: Path):
    """Derive the new policy from each profile's exact historical AI inputs."""
    from .world_native import derive_ai_candidate
    from .world_options_factions import PROFILE_INPUT_SHA256, derive_faction_ai
    if profile not in PROFILE_INPUT_SHA256:
        raise old.RuntimeBuildError('Unknown faction activity native profile.')
    frozen = checked_path(old.ROOT / '.local/baselines/world_settings/native')
    result, proof = {}, {}
    for name in ('CompLogic.dll', 'CompLogicClassic.dll'):
        payload = name.removesuffix('.dll') + '.food-ai.dll'
        prior = checked_path(frozen / payload).read_bytes()
        if profile == 'world-only':
            prior = derive_ai_candidate(name, checked_path(game / name).read_bytes(), prior)
        expected = PROFILE_INPUT_SHA256[profile][name]
        result[name], proof[name] = derive_faction_ai(name, prior, expected)
    return result, proof


def derive_sources(profile: str, files: dict[str, bytes], game: Path):
    """Preserved historical local-input build route."""
    return _derive_sources_exact(profile, files, game)


def _derive_sources_exact(profile: str, files: dict[str, bytes], game: Path, *,
                          asset_source=None, asset_root=None, activity_inputs=None):
    if profile not in PINNED_RUNTIMES:
        raise old.RuntimeBuildError('Choose the stock World-only or Food + World native profile.')
    files = dict(files)
    if profile == 'world-only':
        from .world_native import WORLD_ONLY_AI_SHA256
        files.update(old.transform_sources(files[old.BLOBS], files[old.AI_LOADER],
                                           files[old.WORLD_SETTINGS], WORLD_ONLY_AI_SHA256))
        plan = old.derive_engine_plan((game / 'AnnoWelt.dll').read_bytes(), files[old.ENGINE_PLAN])
        files[old.ENGINE_HEADER] = old.derive_engine_header(files[old.ENGINE_HEADER])
        expected = old.STOCK_SHA256
    else:
        plan = files[old.ENGINE_PLAN]
        from .packages import FOOD_SPEC_SHA256
        food_raw = (old.ROOT / 'legacy/food_overhaul/food_patch.json').read_bytes()
        if _sha(food_raw) != FOOD_SPEC_SHA256:
            raise old.RuntimeBuildError('The reviewed Food native specification changed.')
        food = json.loads(food_raw)
        expected = {**old.STOCK_SHA256,
                    **{item['name']: item['sources']['combined-0.5.0'] for item in food['native_modules']}}
    expected = {**expected, 'AnnoDisplay.dll': DISPLAY_SHA256}
    files[old.ENGINE_PLAN] = plan
    proof = old.verify_native_preimages(game, files[old.BLOBS], plan, expected_hashes=expected)
    from .world_options_visibility_hooks import (verify_visibility_preimages,
                                                verify_renderer_visibility_preimages,
                                                verify_control_visibility_preimages)
    proof['visibility_dispatch'] = verify_visibility_preimages(
        (game / 'AnnoWelt.dll').read_bytes(), expected['AnnoWelt.dll'])
    proof['visibility_renderer_dispatch'] = verify_renderer_visibility_preimages(
        (game / 'AnnoDisplay.dll').read_bytes(), expected['AnnoDisplay.dll'])
    proof['visibility_control_dispatch'] = verify_control_visibility_preimages(
        (game / 'AnnoFrame.dll').read_bytes(), expected['AnnoFrame.dll'])
    proof['visibility_import_dispatch'] = verify_import_visibility_preimages(
        {name: (game / name).read_bytes() for row in IMPORT_HOOKS for name in (row[0], row[2])}, expected)
    proof['strict_visibility_calls'] = verify_visibility_call_preimages(
        {name: (game / name).read_bytes() for name in {row[0] for row in CALLS}}, expected)
    proof['disasters'] = verify_disaster_preimages(
        {name: (game / name).read_bytes() for name in {row[0] for row in DISASTER_CALLS}}, expected)
    from .world_options_rotation import verify_rotation_native_image
    proof['island_rotation_native'] = verify_rotation_native_image(
        (game / 'AnnoWelt.dll').read_bytes(), expected['AnnoWelt.dll'])
    from .world_island_catalogue import IslandCatalogueError, validate_island_shapes, template_resolver
    try:
        proof['island_shapes'] = validate_island_shapes(
            files[PRIVATE + 'world_catalogue.h'],
            (old.ROOT / 'src/anno1503_overhaul/native/world_options/island_shapes.h').read_bytes(),
            template_resolver(game if asset_source is None else asset_source,
                              old.ROOT / '.local/baselines/world_settings/assets' if asset_root is None else asset_root))
    except IslandCatalogueError as exc:
        raise old.RuntimeBuildError('Exact island shape metadata or source inputs differ.') from exc
    from .world_island_rotation import definition_dimensions, validate_rotation_metadata
    try:
        native_options = old.ROOT / 'src/anno1503_overhaul/native/world_options'
        proof['island_rotation'] = validate_rotation_metadata(
            files[PRIVATE + 'world_catalogue.h'],
            (native_options / 'island_rotation_plan.h').read_bytes(),
            (native_options / 'island_rotation_definitions.h').read_bytes(),
            template_resolver(game if asset_source is None else asset_source,
                              old.ROOT / '.local/baselines/world_settings/assets' if asset_root is None else asset_root),
            [definition_dimensions(game / name) for name in ('Anlagen.dat', 'Anlagen.addon')])
    except IslandCatalogueError as exc:
        raise old.RuntimeBuildError('Exact island rotation metadata or landscape dimensions differ.') from exc
    result = apply_options(files)
    activity_ai, activity_proof = (derive_activity_ai_inputs(profile, game)
                                   if activity_inputs is None else activity_inputs)
    from .world_options_factions import PROFILE_INPUT_SHA256
    from .world_options import replace
    for name, value in activity_ai.items():
        result[old.AI_LOADER] = replace(result[old.AI_LOADER],
            PROFILE_INPUT_SHA256[profile][name].encode('ascii'), _sha(value).encode('ascii'),
            'exact faction activity private AI fingerprint: ' + name)
    proof['faction_activity_ai'] = activity_proof
    proof['faction_activity_ai_sha256'] = {name: _sha(value) for name, value in activity_ai.items()}
    # These exact profile-specific fingerprints also guard new read-only data
    # interfaces and original renderer delegates in the live transaction.
    names = ('AnnoWelt.dll', 'AnnoFrame.dll', 'AnnoScene.dll',
             'AnnoGame.dll', 'View.dll', 'AnnoDisplay.dll')
    pins = ['/* Generated from this profile\'s independently verified images. */',
            'typedef struct WSVisibilityModulePin {const wchar_t*name;unsigned char sha256[32];} WSVisibilityModulePin;',
            'static const WSVisibilityModulePin wsVisibilityModulePins[]={']
    for name in names:
        digest = ','.join('0x' + expected[name][at:at + 2] for at in range(0, 64, 2))
        pins.append(' {L"%s",{%s}},' % (name, digest))
    pins.append('};')
    result['developer/source/engine_resume/ai_loader/visibility_native_pins.h'] = ('\n'.join(pins) + '\n').encode('ascii')
    proof['visibility_runtime_module_pins'] = {name: expected[name] for name in names}
    return result, proof


def build_options_runtime(profile, game, tools=None, *, output=None, publish=False):
    """Preserved historical builder and publication location."""
    return _build_options_runtime(profile, game, tools, output=output, publish=publish)


def _public_runtime_inputs(input_root):
    from .beta_inputs import validate_beta_inputs
    from .world_options_factions import PROFILE_INPUT_SHA256, derive_faction_ai
    verified = validate_beta_inputs(input_root)
    values, proof = {}, {}
    for name in ('CompLogic.dll', 'CompLogicClassic.dll'):
        prior = checked_path(verified['ai_base_root'] / name).read_bytes()
        values[name], proof[name] = derive_faction_ai(name, prior, PROFILE_INPUT_SHA256['world-only'][name])
        if checked_path(verified['private_ai_root'] / name).read_bytes() != values[name]:
            raise old.RuntimeBuildError('Public beta private AI differs from its exact stock-derived policy.')
    return dict(verified=verified, activity_inputs=(values, proof))


def build_public_options_runtime(input_root, *, output, require_reviewed=True):
    """Compile the World-only beta from freshly reconstructed public inputs.

    No historical local runtime, Food AI or frozen private package is opened.
    The default accepts only the currently reviewed generator/runtime pair;
    maintainers may create an uninstalled candidate before reviewing its pin.
    """
    if type(require_reviewed) is not bool:
        raise old.RuntimeBuildError('Choose an explicit reviewed-runtime policy.')
    if require_reviewed and generator_id() != PINNED_GENERATOR:
        raise old.RuntimeBuildError('Public beta generator source changed after runtime review; nothing was compiled.')
    inputs = _public_runtime_inputs(checked_path(input_root))
    verified = inputs['verified']
    game = verified.get('native_host_root', verified['source_game'])
    report = _build_options_runtime('world-only', game, output=output, _public_inputs=inputs)
    if require_reviewed and (not report['matches_reviewed_runtime'] or report['generator_id'] != PINNED_GENERATOR):
        raise old.RuntimeBuildError('The public beta candidate differs from the reviewed runtime; nothing was installed.')
    return report


def _build_options_runtime(profile, game, tools=None, *, output=None, publish=False, _public_inputs=None):
    if os.name != 'nt':
        raise old.RuntimeBuildError('Native compilation requires 64-bit Windows and the reviewed Zig toolchain.')
    repo, game = checked_path(old.ROOT), checked_path(game)
    compiled = old._verified_sources(repo)
    source = repo / old.SOURCE_PREFIX
    # Include metadata required by generation and all public source files. Only
    # our explicit transformations may change staged bytes.
    provenance = json.loads((repo / 'provenance/legacy_import.json').read_bytes())
    original = {}
    for record in provenance['source_files']:
        if not record['path'].startswith(old.SOURCE_PREFIX):
            continue
        name = record['path'].removeprefix(old.SOURCE_PREFIX)
        value = checked_path(source / name).read_bytes()
        if _sha(value) != record['imported_sha256']:
            raise old.RuntimeBuildError('Reviewed staged source changed: ' + name)
        original[name] = value
    generation = generator_id()
    if _public_inputs is None:
        files, proof = derive_sources(profile, original, game)
        tools = checked_path(tools if tools is not None else repo / '.local/toolchain')
        zig = checked_path(tools / 'ziglang/zig.exe')
    else:
        if profile != 'world-only' or publish:
            raise old.RuntimeBuildError('Public beta inputs belong only to a separate World-only build.')
        verified = _public_inputs['verified']
        files, proof = _derive_sources_exact(profile, original, game,
            asset_source=verified['source_data_root'], asset_root=verified['assets_root'],
            activity_inputs=_public_inputs['activity_inputs'])
        proof['public_beta_inputs'] = verified['manifest']
        zig = checked_path(verified['compiler_path'])
    compiler_options = ({'creationflags':subprocess.CREATE_NO_WINDOW}
                        if _public_inputs is not None and os.name == 'nt' else {})
    version = subprocess.check_output([str(zig), 'version'], text=True, **compiler_options).strip()
    if version != '0.16.0':
        raise old.RuntimeBuildError('This native build requires the reviewed Zig 0.16.0 toolchain.')
    if _public_inputs is None:
        builds = checked_path(repo / '.local/builds', exists=False)
        builds.mkdir(parents=True, exist_ok=True)
        output = checked_path(output if output is not None else builds / ('options-' + profile + '-' + uuid.uuid4().hex), exists=False)
        if output == builds or not output.is_relative_to(builds) or output.exists() or output.is_relative_to(game):
            raise old.RuntimeBuildError('Choose a new build folder beneath ignored .local/builds.')
    else:
        output = checked_path(output, exists=False)
        protected = (repo, game, verified['source_game'], verified['root'])
        if output.exists() or any(output == p or output in p.parents for p in protected) or any(
                output.is_relative_to(p) for p in protected if p != repo):
            raise old.RuntimeBuildError('Choose a new independent public beta build folder.')
    stage = output / 'package'
    stage.mkdir(parents=True)
    for name, data in files.items():
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    closure = {name: _sha(value) for name, value in files.items() if name in UNITS
               or name.startswith(PRIVATE) and name.endswith(('.h', '.inc'))
               or name in (old.BLOBS, old.AI_LOADER, old.ENGINE_HEADER,
                           'developer/source/engine_resume/ai_loader/visibility_hooks.inc',
                           'developer/source/engine_resume/ai_loader/disaster_hooks.inc',
                           'developer/source/engine_resume/ai_loader/visibility_native_pins.h')
               or name.startswith('developer/source/') and name.endswith(('.c', '.h', '.inc'))
               and name in {n.removeprefix(old.SOURCE_PREFIX) for n in compiled}}
    report = dict(schema_version=1, version=VERSION, profile=profile, generator_id=generation,
                  created_at=datetime.now(timezone.utc).isoformat(), settings_size=SETTINGS_SIZE,
                  preview_snapshot_size=PREVIEW_SIZE, engine_plan_sha256=_sha(files[old.ENGINE_PLAN]),
                  native_preimage_proof=proof, imported_compiled_source_sha256=compiled,
                  staged_compiled_source_sha256=closure,
                  transformations=[dict(path=n, before_sha256=_sha(original[n]) if n in original else None,
                                        after_sha256=_sha(value))
                                   for n, value in files.items() if original.get(n) != value],
                  toolchain_version=version, game_executed=False, installed=False,
                  game_files_modified=False, output_root=str(output))
    (output / 'SOURCE_PROOF.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    working = stage / 'developer/source/runtime_dev3'
    build = output / 'compiler'
    build.mkdir()
    environment = os.environ.copy()
    for key, child in (('ZIG_GLOBAL_CACHE_DIR', 'global'), ('ZIG_LOCAL_CACHE_DIR', 'local'), ('TEMP', 'tmp'), ('TMP', 'tmp')):
        directory = build / child
        directory.mkdir(exist_ok=True)
        environment[key] = str(directory)
    runtime = working / 'AnnoWorldSettings.dll'
    command = [str(zig), 'cc', '-target', 'x86_64-windows-gnu', '-shared', '-O2', '-Wall', '-Wextra', '-Werror',
               '-I', str(working), '-o', str(runtime), *[str(stage / name) for name in UNITS],
               '-lbcrypt', '-luser32', '-lgdi32', '-lkernel32']
    result = subprocess.run(command, cwd=working, env=environment, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, encoding='utf-8', errors='replace', **compiler_options)
    (output / 'build.log').write_text(result.stdout, encoding='utf-8')
    if result.returncode:
        raise old.RuntimeBuildError('World options compilation failed; staged sources and build.log were retained: ' + str(output))
    if any(_sha((stage / name).read_bytes()) != value for name, value in closure.items()):
        raise old.RuntimeBuildError('A staged native input changed during compilation.')
    if old._verified_sources(repo) != compiled or generator_id() != generation:
        raise old.RuntimeBuildError('Historical native inputs changed during compilation.')
    normalized, metadata = old.normalize_pe_metadata(runtime.read_bytes())
    runtime.write_bytes(normalized)
    module = importlib.util.spec_from_file_location('_options_exports', repo / 'legacy/world_settings/activation/pe_exports.py')
    parser = importlib.util.module_from_spec(module)
    module.loader.exec_module(parser)
    exports = parser.exports(normalized, REQUIRED_EXPORTS)
    report.update(built=True, runtime_path=str(runtime), runtime_sha256=_sha(normalized),
                  normalized_metadata=metadata, exports=exports,
                  matches_reviewed_runtime=_sha(normalized) == PINNED_RUNTIMES[profile])
    (output / 'BUILD_RESULT.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    if publish:
        if not report['matches_reviewed_runtime'] or generation != PINNED_GENERATOR:
            raise old.RuntimeBuildError('Candidate differs from its reviewed runtime pin; no profile was published.')
        profiles = checked_path(repo / '.local/runtime-profiles', exists=False)
        profiles.mkdir(parents=True, exist_ok=True)
        target = profiles / ('options-' + profile + '-' + report['runtime_sha256'][:16])
        if target.exists():
            raise old.RuntimeBuildError('Runtime profile exists; it was preserved.')
        candidates, candidate_proof = derive_activity_ai_inputs(profile, game)
        if (candidate_proof != report['native_preimage_proof']['faction_activity_ai'] or
                {name: _sha(data) for name, data in candidates.items()} !=
                report['native_preimage_proof']['faction_activity_ai_sha256']):
            raise old.RuntimeBuildError('The private AI derivation changed after compilation.')
        target.mkdir()
        (target / 'AnnoWorldSettings.dll').write_bytes(normalized)
        (target / 'runtime_engine_edits.json').write_bytes(files[old.ENGINE_PLAN])
        private = target / 'WorldSettingsAI'
        private.mkdir()
        for name, data in candidates.items():
            (private / name).write_bytes(data)
        report['profile_root'] = str(target)
        (target / 'runtime-profile.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report
