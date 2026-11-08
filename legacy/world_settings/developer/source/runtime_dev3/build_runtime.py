"""Build start options with nine reviewed native hooks. No game writes."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import argparse
HERE=Path(__file__).resolve().parent
WORK=HERE.parent
ENGINE_PATCH_COUNT=int(__import__('re').search(r'#define WS_ENGINE_PATCH_COUNT (\d+)',(WORK/'engine_resume/ai_loader/engine_patch_plan.h').read_text())[1])
ENGINE_PLAN=json.loads((WORK.parent/'huge_world/runtime_engine_edits.json').read_bytes())
assert ENGINE_PATCH_COUNT==ENGINE_PLAN['engine_instruction_count']==len(ENGINE_PLAN['edits'])
PRIVATE=WORK/'engine_resume/ai_food/experiment_runtime'
sources=[PRIVATE/'WorldSettings.c',PRIVATE/'world_backend.c',PRIVATE/'world_ai.c',
         WORK/'world_factory.c',WORK/'engine_resume/ai_loader/ai_loader.c',
         WORK/'engine_resume/route_coverage/selection.c',HERE/'compiled_hooks.c']
headers=[PRIVATE/name for name in ['world_backend.h','world_ai.h','stock_ai_profiles.h',
         'world_catalogue.h','world_ship_reserves.h','world_factions.h','native_faction_options.h',
         'special_scene.inc','special_certificate.inc','special_activity.inc','validated_world.inc','ai_scene.inc']]
headers += [WORK/'engine_resume/ai_loader/ai_loader.h',WORK/'engine_resume/ai_loader/install_test_hooks.c',WORK/'engine_resume/ai_loader/engine_patch_plan.h',
            WORK/'engine_resume/route_coverage/stock_endless_paths.h',WORK/'engine_resume/route_coverage/runtime_integration.inc',
            HERE/'runtime_test_blobs.h',HERE/'generate_blobs.py',HERE/'frame_payload.py',
            PRIVATE/'attempt_bridge.py',PRIVATE/'postprofile_bridge.py']
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tools',type=Path,default=HERE.parents[3]/'_tools')
    args=parser.parse_args()
    # Consume frozen reviewed blobs. Regeneration uses the explicit original
    # game root through ANNO1503_SOURCE_GAME, never an assumed package neighbor.
    expected=(HERE/'REVIEWED_HOOKS_SHA256.txt').read_text().strip()
    assert len(expected)==64 and sha(HERE/'runtime_test_blobs.h')==expected
    for name in ['start_options.inc','starting_fleet_certificate.inc','world_diplomacy.inc','world_diplomacy.h','world_policy_bridge.py','plant_fertility.inc','mineral_fertility.inc','mineral_persistence.inc','balanced_layout.inc','selection_policy.inc','world_size.inc','preview_state.inc','world_menu_preview.inc','world_preview_coasts.h']:
        path=PRIVATE/name
        if path.exists():headers.append(path)
    before={str(p.relative_to(WORK)):sha(p) for p in sources+headers}
    out=HERE/'_build';out.mkdir(exist_ok=True)
    env=os.environ.copy()
    for name,child in [('ZIG_GLOBAL_CACHE_DIR','global-cache'),('ZIG_LOCAL_CACHE_DIR','local-cache'),('TEMP','tmp'),('TMP','tmp')]:
        directory=out/child;directory.mkdir(exist_ok=True);env[name]=str(directory)
    command=[str(args.tools.resolve()/'ziglang/zig.exe'),'cc','-target','x86_64-windows-gnu','-shared','-O2','-Wall','-Wextra','-Werror',
             '-I',str(HERE),'-o',str(HERE/'AnnoWorldSettings.dll'),*[str(p) for p in sources],'-lbcrypt','-luser32','-lgdi32','-lkernel32']
    subprocess.run(command,check=True,cwd=HERE,env=env)
    assert all(sha(WORK/name)==digest for name,digest in before.items()),'Source changed during build'
    result=dict(command=command,sha256=sha(HERE/'AnnoWorldSettings.dll'),source_sha256=before,
                status='UNFINISHED',backend_registered_in_ui=False,explicit_copy_test_backend_available=True,
                abi_size=56,ai_input_bound=3,ai_bound_scope='Existing stock placeholders common to all three source difficulty scenes; not the engine maximum',
                native_hooks=9,actual_game_run=False,build_revision='huge-engine-recenter-dev1',engine_profile=ENGINE_PLAN['profile'],engine_patch_count=ENGINE_PATCH_COUNT,
                retained_previous_native_hook_sites=8,central_diplomacy_hook_added=True)
    (HERE/'build_result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
