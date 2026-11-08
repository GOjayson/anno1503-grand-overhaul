"""Bind the final visibility repair and preserve its failed119-site evidence.

Writes only this new border investigation folder; no game/copy/release writes.
"""
from pathlib import Path
import hashlib,importlib.util,json,shutil,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;GAME=HERE.parents[3];WORK=GAME/'WorldSettings_Work'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok,message):
    if not ok:raise ValueError(message)


def main():
    s=importlib.util.spec_from_file_location('final_visibility_transform',HERE/'world_visibility_patch.py');M=importlib.util.module_from_spec(s);sys.modules[s.name]=M;s.loader.exec_module(M)
    plan=M.plan();candidate=(HERE/'AnnoWelt.visibility_candidate2.dll').read_bytes();candidate_sha=M.sha(candidate)
    require(candidate_sha=='8a6f73e1f015e30685063dc3418305e6b3a0bf51f9fe49d6074c296fc1e33aa8','Final complete candidate changed')
    require(M.transform_welt_visibility(candidate)[0]==candidate and M.transform_welt_visibility(candidate)[1]['idempotent']is True,'Complete repaired output is not idempotent')
    bad=bytearray(candidate);bad[0x200]^=1
    try:M.transform_welt_visibility(bytes(bad))
    except ValueError:pass
    else:raise ValueError('Unknown complete DLL accepted')
    producer=json.loads((HERE/'visibility_producer_results.json').read_bytes())
    require(producer.get('passed')is True and producer.get('candidate_sha256')==candidate_sha and len(producer['cases'])==36,'Complete native producer fixture is stale')
    require(producer.get('source_sha256')==sha(HERE/'test_visibility_producer.py'),'Producer test source changed after its run')
    grid=WORK/'huge_engine_work/grid/border';nav=WORK/'huge_engine_work/navigation/render_stack'
    helper=json.loads((grid/'visibility_mask_results.json').read_bytes());consumption=json.loads((grid/'render_consumption_results.json').read_bytes())
    require(helper.get('passed')is True and consumption.get('passed')is True,'Native helper/consumer review failed')
    closure=json.loads((nav/'visibility_candidate_closure_audit.json').read_bytes());stack=json.loads((nav/'visibility_candidate2_stack_results.json').read_bytes())
    require(closure.get('status')=='PASS'and closure.get('candidate_sha256')==candidate_sha and closure.get('plan_sha256')==M.PLAN_SHA256 and closure.get('stack_operand_count')==117,'Independent complete native operand/byte closure differs')
    require(stack.get('status')=='PASS'and any(p.get('sha256')==candidate_sha for p in stack.get('profiles',[])),'Native Windows unwind/stack/EH review belongs to a different candidate')
    copied={}
    paths={
        'grid':[grid/name for name in ['prove_visibility_mask.py','visibility_helper_edits.json','visibility_mask_results.json','prove_render_consumption.py','render_consumption_results.json','FINDINGS.md']],
        'stack':[nav/name for name in ['test_render_stack.py','audit_render_stack_closure.py','visibility_candidate_closure_audit.json','visibility_candidate2_stack_results.json','h11_thread_stack_budget_interpretation.json','h11_thread_stacks.json','observe_thread_stacks.py','REVIEW.md']]
    }
    for category,items in paths.items():
        for source in items:
            before=sha(source);target=HERE/'review_evidence'/category/source.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
            require(sha(source)==sha(target)==before,'Evidence changed during publication');copied[target.relative_to(HERE).as_posix()]=before
    for name in ['world_visibility_patch.py','build_visibility_plan.py','visibility_repair_plan.json','visibility_output_hashes.json','test_visibility_producer.py','visibility_producer_results.json',
                 'observe_camera.py','h11_camera_initial.json','h11_camera_far_click.json','h11_preview_save_comparison.json','publish_visibility_review.py']:
        copied[name]=sha(HERE/name)
    report=dict(scope=__doc__,passed=True,architecture='AMD64 PE32+',game_executed_for_repair=False,
        source119_welt_sha256='bc4de21e6c92ab5a94d9fc50d25f0609d9e1cdb2ff119c29238d3354f978fb29',
        repaired_full_welt_sha256=candidate_sha,repair_plan_sha256=M.PLAN_SHA256,new_native_regions=47,combined_runtime_regions=166,
        old_visibility_mask_bytes=512,new_visibility_mask_bytes=2048,new_mask_columns=128,new_cache_columns=128,
        old_stack_frame_bytes=878952,new_stack_frame_bytes=920808,stack_growth_bytes=41856,visible_record_capacity_unchanged=8192,
        matrix_zero_sentinel_and_recycling_on_capacity_drop=True,
        automated_complete_native_producer_cases=36,exact_native_supported_size_equivalence=[256,512,1024],native_2048_far_cells_and_8192_cap_verified=True,
        prior_texture_handle_ownership_accounted_for=True,independent_stack_operands_verified=117,
        native_windows_unwind_cases=26,native_stack_probe_cases=10,native_cpp_cleanup_funclet_cases=4,
        all_other_file_bytes_and_prior_engine_regions_preserved=True,
        proven_original_failures=['Visibility mask aliases(1024,0)with(0,16).','Far-cell mask writes escape the512-byte buffer and are then erased by adjacent pointer-cache clearing.','80-column per-cell cache aliases(80,0)with(0,1).'],
        failed_actual119_run=dict(save_name='h11',save_sha256='0c28f8fc32702c84e95cd6429ad70b05b5e1b5c1395766a51a005fe59a282b92',
            runtime_sha256='d7844e29bb7d53552c2998754b89ebbb8cb76d429904ed62e7253dc1b335424d',
            actual_world_geometry_and_resources_saved_correctly=True,actual_rendering_failed=True,
            observations=['Regular terrain bands/rectangular ocean holes and repeated town geometry.','Camera targets can reach y1588, so the reported border is not the examined camera clamp.'],
            counted_as_a_successful_repaired_game_run=False),
        evidence_sha256=copied,
        limits=['Repaired166-site native loading/rendering/minimap/navigation/save/reload require a new actual game run.',
            'Native producer fixtures model visibility clipping, ocean geometry and CRT services; they do not draw textures.',
            'Full C++ exception propagation is not executed; Windows unwind mechanics and both native cleanup funclets are separately checked.',
            'Actual prior main-thread stack high-water leaves roughly113KiB after the added frame. Synthetic1MiB probes fit112KiB caller depth and reject128KiB; arbitrary call depth is not claimed.'])
    output=HERE/'VISIBILITY_REPAIR_REVIEW.json';output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(passed=True,repaired_full_welt_sha256=candidate_sha,combined_runtime_regions=166,evidence_files=len(copied),actual_repaired_game_run=False),indent=2))


if __name__=='__main__':main()
