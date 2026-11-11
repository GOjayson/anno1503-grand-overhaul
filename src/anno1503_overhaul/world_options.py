"""Reviewed settings ABI and staged native transformations for World options.

Historical compiled inputs are immutable. These transformations apply only to
fresh staging dictionaries and are shared by the stock and Food host builds.
"""
from pathlib import Path
import hashlib
import json

from .world_runtime_build import RuntimeBuildError


ROOT = Path(__file__).resolve().parents[2]
PRIVATE = 'developer/source/engine_resume/ai_food/experiment_runtime/'
SETTINGS_SIZE = 120
PREVIEW_SIZE = 5256
FIELDS = ('mapSeed', 'startClimate', 'startIsland', 'cargoMode', 'cargoTools',
          'cargoWood', 'cargoFood', 'climateBalance', 'layoutStyle', 'disasters',
          'fairStarts', 'startSeparation', 'resourceDistribution', 'guaranteeBasics',
          'mapVisibility', 'enemyVisibility')
VERSION = '0.6.0-dev.7'


def generator_id() -> str:
    """Bind saved seeds/presets to the reviewed generator's public inputs."""
    directory = ROOT / 'src/anno1503_overhaul'
    paths = [directory / (name + '.py') for name in
             ('world_options', 'world_options_planner', 'world_options_start', 'world_options_menu',
              'world_options_visibility', 'world_options_visibility_hooks',
              'world_options_visibility_calls')]
    paths += sorted((directory / 'native/world_options').glob('*.h'))
    paths += sorted((directory / 'native/world_options').glob('*.inc'))
    inputs = {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in paths}
    inputs['frozen_compiled_sources'] = json.loads((ROOT / 'provenance/legacy_import.json').read_bytes())['compiled_source_sha256']
    return 'ws6-' + hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()


def replace(data: bytes, before: bytes, after: bytes, label: str, count: int = 1) -> bytes:
    if b'\r\n' in data and b'\r\n' not in before:
        before = before.replace(b'\n', b'\r\n')
        after = after.replace(b'\n', b'\r\n')
    if data.count(before) != count:
        raise RuntimeBuildError('Advanced World Settings source differs: ' + label)
    return data.replace(before, after, count)


def authored(name: str) -> bytes:
    path = ROOT / 'src/anno1503_overhaul/native/world_options' / name
    if path.is_symlink() or path.parent.resolve() != path.parent or not path.is_file():
        raise RuntimeBuildError('Missing reviewed World options source: ' + name)
    return path.read_bytes()


def apply_common(files: dict[str, bytes]) -> None:
    header = PRIVATE + 'world_backend.h'
    files[header] = replace(files[header], b' int32_t worldSize;',
        b' int32_t worldSize;\n uint32_t mapSeed;\n'
        b' int32_t startClimate,startIsland,cargoMode,cargoTools,cargoWood,cargoFood;\n'
        b' int32_t climateBalance,layoutStyle,disasters;\n'
        b' int32_t fairStarts,startSeparation,resourceDistribution,guaranteeBasics;\n'
        b' int32_t mapVisibility,enemyVisibility;', 'settings extension')
    files[header] = replace(files[header], b'#endif',
        b'typedef struct WSIslandDetails {\n'
        b' uint32_t size,index,fertileLand,oreSlots,whales,faction,startEligible;\n'
        b' int32_t startOwner;\n'
        b' uint32_t nearbyCrops,nearbyMinerals,resourceRadius;\n'
        b'} WSIslandDetails;\n'
        b'__declspec(dllexport) int WorldSettingsIslandDetails(uint32_t,WSIslandDetails*);\n'
        b'__declspec(dllexport) int WorldSettingsStartOwner(uint32_t);\n'
        b'__declspec(dllexport) int WorldSettingsDescribeStarts(char*,uint32_t);\n'
        b'#endif', 'island details query declarations')
    files[header] = replace(files[header], b'#endif',
        b'#include "advanced_settings.h"\n#endif', 'shared settings validation')
    files[PRIVATE + 'advanced_settings.h'] = authored('advanced_settings.h')
    preview = PRIVATE + 'preview_state.inc'
    files[preview] = replace(files[preview], b'sizeof(WSWorldSettings)==56',
                             b'sizeof(WSWorldSettings)==120', 'settings ABI assertion')
    files[preview] = replace(files[preview], b'sizeof(WSPreviewSnapshot)==5192',
                             b'sizeof(WSPreviewSnapshot)==5256', 'snapshot ABI assertion')
    backend = PRIVATE + 'world_backend.c'
    files[backend] = replace(files[backend], b' wsPreviewClear();\n planCount=0;',
        b' wsPreviewClear();\n planCount=0;\n'
        b' if(!wsAdvancedValidateSettings(s,error,cap))return 0;\n'
        b' if(s->mapSeed!=seed){wsMessage(error,cap,"The displayed map seed differs from the generation request.");return 0;}',
        'generation advanced validation')
    menu = PRIVATE + 'WorldSettings.c'
    files[menu] = replace(files[menu],
        b'    if (!s || s->size != sizeof(*s)) {message(err,cap,"Invalid settings structure.");return 0;}',
        b'    if (!wsAdvancedValidateSettings(s,err,cap)) return 0;', 'menu advanced validation')


def apply_options(files: dict[str, bytes]) -> dict[str, bytes]:
    """Return transformed source without changing the caller's frozen inputs."""
    from .world_options_planner import apply_planner
    from .world_options_start import apply_start
    from .world_options_menu import apply_menu
    from .world_options_visibility_hooks import apply_visibility_hooks
    from .world_options_visibility import apply_visibility
    from .world_options_visibility_calls import apply_visibility_calls
    result = dict(files)
    apply_common(result)
    apply_planner(result)
    apply_start(result)
    apply_visibility(result)
    apply_menu(result)
    apply_visibility_calls(result)
    apply_visibility_hooks(result)
    backend = PRIVATE + 'world_backend.c'
    result[backend] = replace(result[backend], b'#include "mineral_persistence.inc"',
        b'#include "mineral_persistence.inc"\n#include "island_details.inc"', 'read-only island details query')
    result[PRIVATE + 'island_details.inc'] = authored('island_details.inc')
    name = PRIVATE + 'advanced_settings.h'
    result[name] = replace(result[name], b'"pending-build"',
                           ('"' + generator_id() + '"').encode(), 'generator fingerprint')
    return result
