"""Bind current dev8 helper sources to the isolated native fixture results."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent
PACKAGE=HERE.parents[2]
SOURCE=PACKAGE/'developer/source/engine_resume/ai_food/experiment_runtime'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    build=json.loads((HERE/'fixture_build.json').read_text())
    tested=json.loads((HERE/'layout_results.json').read_text())
    assert tested['passed'] and not tested['game_executed'] and tested['native_fixture_cases']>=100
    assert tested['exact_repeat_cases']==tested['native_fixture_cases']
    assert tested['input_sha256']==build['input_sha256']
    for name,digest in build['input_sha256'].items():assert sha(PACKAGE/name)==digest
    assert sha(HERE/'_build/layout_fixture.dll')==build['fixture_dll_sha256']
    evidence={name:sha(HERE/name) for name in ['README.txt','layout_fixture.c','build_fixture.py','test_layout.py','make_review.py','fixture_build.json','layout_results.json']}
    evidence.update({name:digest for name,digest in build['input_sha256'].items() if not name.endswith('/layout_fixture.c')})
    result=dict(passed=True,game_executed=False,ui_or_gameplay_verified=False,game_or_copy_mutated=False,
        scope='Exact dev8 production selection/layout/reserve includes in an isolated native helper fixture; no full-runtime, native-loader or Anno execution.',
        helper_sha256=sha(SOURCE/'balanced_layout.inc'),selection_policy_sha256=sha(SOURCE/'selection_policy.inc'),ship_reserves_sha256=sha(SOURCE/'world_ship_reserves.h'),
        native_fixture_architecture='AMD64 PE32+; isolated helper only, not shipped32-bit runtime',fixture_dll_sha256=build['fixture_dll_sha256'],
        native_fixture_cases=tested['native_fixture_cases'],exact_repeat_cases=tested['exact_repeat_cases'],supported_world_sizes=tested['supported_world_sizes'],unsupported_4096_rejected=tested['unsupported_4096_rejected'],
        template_count=tested['template_count'],settings_abi_bytes=tested['settings_abi_bytes'],fill_sequence_cases=tested['fill_sequence_cases'],strict_lenient_contrast_cases=len(tested['strict_lenient_contrasts']),
        quality_24island_cases=tested['quality_24island_cases'],quality_minimum_bounding_width_fraction=tested['quality_minimum_bounding_width_fraction'],quality_minimum_bounding_height_fraction=tested['quality_minimum_bounding_height_fraction'],quality_minimum_land_share_any_half=tested['quality_minimum_land_share_any_half'],selection_ms=tested['selection_ms'],
        limitations=['Not a live-game or native-loader proof.','Rectangle-bound/sample-grid quality does not measure exact coastline gaps.','Bounded placement may reject configurations that a more exhaustive packer could fit.','Culture/faction/resource anchors can force unequal climate counts; balanced fillers do not guarantee equal acreage.','Geometry fixtures do not certify native loading or navigation at any size.'],evidence_sha256=evidence)
    (HERE/'LAYOUT_REVIEW.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['passed','helper_sha256','selection_policy_sha256','ship_reserves_sha256','native_fixture_cases','exact_repeat_cases']},indent=2))
if __name__=='__main__':main()
