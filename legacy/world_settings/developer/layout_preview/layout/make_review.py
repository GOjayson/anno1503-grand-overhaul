"""Bind the completed native layout-helper proof; never access Anno processes."""
from pathlib import Path
import hashlib,json,statistics,struct
HERE=Path(__file__).resolve().parent
PACKAGE=HERE.parents[2]
HELPER='developer/source/engine_resume/ai_food/experiment_runtime/balanced_layout.inc'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    tested=json.loads((HERE/'layout_results.json').read_bytes())
    build=json.loads((HERE/'fixture_build.json').read_bytes())
    assert tested['passed'] and not tested['game_executed'] and not tested['game_or_copy_mutated']
    assert not build['game_executed'] and not build['game_or_copy_mutated']
    assert tested['helper_sha256']==sha(PACKAGE/HELPER)
    assert tested['fixture_source_sha256']==sha(HERE/'layout_fixture.c')
    assert tested['test_source_sha256']==sha(HERE/'test_layout.py')
    assert tested['fixture_dll_sha256']==build['fixture_dll_sha256']==sha(HERE/'_build/layout_fixture.dll')
    for name,digest in build['input_sha256'].items():assert sha(PACKAGE/name)==digest,name
    binary=(HERE/'_build/layout_fixture.dll').read_bytes();pe=struct.unpack_from('<I',binary,60)[0]
    assert binary[:2]==b'MZ' and binary[pe:pe+4]==b'PE\0\0'
    assert struct.unpack_from('<H',binary,pe+4)[0]==0x8664 and struct.unpack_from('<H',binary,pe+24)[0]==0x20b
    evidence=[HELPER,'developer/source/engine_resume/ai_food/experiment_runtime/world_backend.h',
              'developer/source/engine_resume/ai_food/experiment_runtime/world_ship_reserves.h']
    evidence += ['developer/layout_preview/layout/'+name for name in
                 ['layout_fixture.c','build_fixture.py','fixture_build.json','test_layout.py',
                  'layout_results.json','README.txt','make_review.py']]
    typical=[r for r in tested['cases'] if r['count']==24]
    result=dict(passed=True,scope=__doc__,helper=HELPER,helper_sha256=tested['helper_sha256'],
                algorithm='Validated compact feasibility layout followed by bounded deterministic max-clearance relocation across the complete native map',
                native_fixture_architecture='AMD64 PE32+',native_fixture_cases=tested['native_fixture_cases'],
                exact_repeat_cases=tested['exact_repeat_cases'],changed_seed_layouts=tested['changed_seed_layouts'],
                previous_runtime_infeasible_requests=len(tested['previous_runtime_infeasible_settings']),
                typical24_cases=len(typical),typical24_quality_assertions=tested['quality_assertions_24_islands'],
                typical24_observed=dict(
                    minimum_centers_per_quadrant=min(min(r['after']['center_quadrant_counts']) for r in typical),
                    minimum_land_share_in_a_half=min(min(r['after']['land_share_in_four_halves']) for r in typical),
                    minimum_bounding_width=min(r['after']['bounding_width'] for r in typical),
                    minimum_bounding_height=min(r['after']['bounding_height'] for r in typical),
                    mean_largest_sampled_ocean_gap_before=statistics.mean(r['before']['maximum_sampled_ocean_distance_to_land'] for r in typical),
                    mean_largest_sampled_ocean_gap_after=statistics.mean(r['after']['maximum_sampled_ocean_distance_to_land'] for r in typical),
                    maximum_sampled_ocean_gap_after=max(r['after']['maximum_sampled_ocean_distance_to_land'] for r in typical)),
                typical24_native_timing=tested['typical24_native_timing'],
                evidence_sha256={name:sha(PACKAGE/name) for name in evidence},
                full_runtime_preview_or_scene_staging_tested=False,actual_native_loader_tested=False,
                game_executed=False,game_or_copy_mutated=False)
    target=HERE/'LAYOUT_REVIEW.json';target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(passed=True,review=str(target),sha256=sha(target),helper_sha256=result['helper_sha256'],
                         native_fixture_cases=result['native_fixture_cases'],typical24_observed=result['typical24_observed']),indent=2))


if __name__=='__main__':main()
