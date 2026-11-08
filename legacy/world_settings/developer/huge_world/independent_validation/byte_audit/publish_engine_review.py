"""Publish additive reviewed native evidence into the new experimental package.

Only the new dev8 huge_world/independent_validation folder and review JSON are
written. Original/game-copy/released dev7 files and backups are read only.
"""
from pathlib import Path
import hashlib,json,shutil,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;GAME=HERE.parents[2]
WORK=GAME/'WorldSettings_Work';PACKAGE=WORK/'anno1503_food_world_dev8';ENGINE=PACKAGE/'developer/huge_world'


def require(ok,message):
    if not ok:raise ValueError(message)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    audit=json.loads((HERE/'engine_candidate_independent_audit.json').read_bytes())
    grid=WORK/'huge_engine_work/grid';nav=WORK/'huge_engine_work/navigation'
    grid_tests=json.loads((grid/'native_test_results.json').read_bytes());allocation=json.loads((grid/'allocation_reference_audit.json').read_bytes())
    guard=json.loads((grid/'guard_test_results.json').read_bytes());transaction=json.loads((grid/'transaction_test_results.json').read_bytes())
    native=json.loads((nav/'navigation_native_results.json').read_bytes());unwind=json.loads((nav/'navigation_unwind_results.json').read_bytes())
    backtrack=json.loads((nav/'navigation_backtrack_results.json').read_bytes());independent_backtrack=json.loads((HERE/'backtracking_guard_independent_results.json').read_bytes())
    visibility_path=ENGINE/'visibility/VISIBILITY_REPAIR_REVIEW.json'
    if audit['engine_instruction_count']>119:
        local_review=HERE/'border/VISIBILITY_REPAIR_REVIEW.json';publication=json.loads(local_review.read_bytes())
        for name,expected in publication['evidence_sha256'].items():
            relative=Path(name);require(not relative.is_absolute()and '..'not in relative.parts,'Unsafe local visibility evidence path')
            source=HERE/'border'/relative;require(sha(source)==expected,'Final visibility source changed: '+name)
            destination=ENGINE/'visibility'/relative;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,destination)
            require(sha(destination)==expected,'Visibility publication changed bytes')
        visibility_path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(local_review,visibility_path)
    visibility=json.loads(visibility_path.read_bytes())if audit['engine_instruction_count']>119 else None
    depth_source=HERE/'frame_depth/FRAME_DEPTH_REVIEW.json'
    depth=json.loads(depth_source.read_bytes())
    require(depth.get('passed')is True and depth.get('runtime_edit_count')==audit['frame_instruction_count']==7,
        'Size-aware Frame depth review is incomplete')
    require(depth.get('actual_repaired_game_run_verified')is False and depth.get('original_image_final_page_already_committed_RX')is True,
        'Frame depth review must retain its automated/original-page scope')
    require(depth.get('source_to_output_sha256',{}).get(audit['engine_modules']['AnnoFrame.dll']['copied_input_sha256'])=='6b9972ec85f05e2b417096b5f0343daebd07daf53d4554758353a7c9cd4c6c80',
        'Historical failed half-depth copied output differs')
    depth_published={}
    for name,expected in depth['evidence_sha256'].items():
        relative=Path(name);require(not relative.is_absolute()and '..'not in relative.parts,'Unsafe Frame evidence path')
        if name.startswith('validation/frame_depth/'):
            source=HERE/'frame_depth'/Path(name).name;destination=ENGINE/'depth'/Path(name).name
        else:
            source=HERE/'frame_depth/review_evidence'/relative;destination=ENGINE/'depth/review_evidence'/relative
        require(sha(source)==expected,'Frame source evidence changed: '+name)
        destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,destination)
        require(sha(destination)==expected,'Frame publication changed bytes')
        depth_published[destination.relative_to(PACKAGE).as_posix()]=expected
    depth_path=ENGINE/'depth/FRAME_DEPTH_REVIEW.json';depth_path.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(depth_source,depth_path);require(sha(depth_source)==sha(depth_path),'Frame review publication changed bytes')
    bias_source=HERE/'frame_bias/FRAME_BIAS_REVIEW.json';bias=json.loads(bias_source.read_bytes())
    require(bias.get('passed')is True and bias.get('automated_component_approved')is True and bias.get('runtime_edit_count')==7 and bias.get('actual_repaired_game_run_verified')is False,
        'Centered full-precision Frame review is incomplete or overclaims gameplay')
    require(bias.get('source_to_output_sha256',{}).get(audit['engine_modules']['AnnoFrame.dll']['copied_input_sha256'])==audit['patched_frame_sha256'],
        'Centered Frame exact copied output differs')
    require(bias.get('prior_half_depth173_actual_visual_acceptance_failed')is True and bias.get('original_normalization_and_height_precision_preserved')is True and bias.get('original_state6_matrix_and_all_local_sprite_globals_preserved')is True,
        'Centered Frame review lacks precision and historical-failure scope')
    bias_published={}
    for name,expected in bias['evidence_sha256'].items():
        relative=Path(name);require(not relative.is_absolute()and '..'not in relative.parts,'Unsafe centered Frame evidence path')
        if name.startswith('validation/frame_bias/'):
            source=HERE/'frame_bias'/relative.name;destination=ENGINE/'bias'/relative.name
        else:
            source=HERE/'frame_bias/review_evidence'/relative;destination=ENGINE/'bias/review_evidence'/relative
        require(sha(source)==expected,'Centered Frame evidence changed: '+name)
        destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,destination)
        require(sha(destination)==expected,'Centered Frame publication changed bytes')
        bias_published[destination.relative_to(PACKAGE).as_posix()]=expected
    bias_path=ENGINE/'bias/FRAME_BIAS_REVIEW.json';bias_path.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(bias_source,bias_path);require(sha(bias_source)==sha(bias_path),'Centered Frame review changed bytes')
    supplement_source=HERE/'frame_bias/FRAME_BIAS_TRANSLATED_PIXEL_SUPPLEMENT.json'
    supplement=json.loads(supplement_source.read_bytes())
    require(supplement.get('passed')is True and supplement.get('approved_component_review_sha256')==sha(bias_source) and supplement.get('patch_source_sha256')==bias['source_sha256'],
        'Translated-pixel supplement does not bind the immutable approved Frame component')
    require(supplement.get('copied_frame_sha256')==audit['patched_frame_sha256'] and supplement.get('native_projected_packed_vertices')==1944 and supplement.get('native_water_ground_pixel_comparisons')==648,
        'Translated-pixel supplement belongs to a different candidate or incomplete native matrix')
    require(supplement.get('translated_depths_or_pixel_decisions_byte_identical')is False and supplement.get('high16_quantization_bin_changes')==3 and supplement.get('native_pixel_decision_changes')==3 and supplement.get('actual_game_rendering_or_draw_order_verified_by_supplement')is False,
        'Translated-pixel rounding differences and numerical-only scope must remain explicit')
    translated_published={}
    for name,expected in supplement['copied_evidence_sha256'].items():
        relative=Path(name);require(not relative.is_absolute()and '..'not in relative.parts and relative.parts[0]=='translated_evidence','Unsafe translated numerical evidence path')
        source=HERE/'frame_bias'/relative;destination=ENGINE/'bias'/relative
        require(sha(source)==expected,'Translated numerical source changed: '+name)
        destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,destination)
        require(sha(destination)==expected,'Translated numerical publication changed bytes')
        translated_published[destination.relative_to(PACKAGE).as_posix()]=expected
    supplement_path=ENGINE/'bias/FRAME_BIAS_TRANSLATED_PIXEL_SUPPLEMENT.json'
    shutil.copyfile(supplement_source,supplement_path);require(sha(supplement_source)==sha(supplement_path),'Translated supplement publication changed bytes')
    require(audit.get('passed')is True and grid_tests.get('passed')is True and allocation.get('passed')is True,'Native grid/byte audit has not passed')
    require(guard.get('passed')is True and len(guard['cases'])==6 and transaction.get('passed')is True and len(transaction['cases'])==20,'Guard/transaction native fixtures incomplete')
    current=PACKAGE/'developer/source/engine_resume/ai_loader/install_test_hooks.c'
    require(transaction['source_sha256']==sha(current),'Atomic transaction tests belong to different actual runtime C source')
    header=PACKAGE/'developer/source/engine_resume/ai_loader/engine_patch_plan.h'
    require(transaction['engine_plan_sha256']==sha(header)==audit['runtime_plan_sha256'],'Atomic transaction tests use a different engine plan')
    require(native.get('status')=='PASS'and len(native.get('cases',[]))==22 and all(row.get('status')=='PASS'for row in native['cases']),'Native navigation matrix incomplete')
    require(unwind.get('status')=='PASS'and len(unwind.get('profiles',[]))==4,'Native Windows unwind profiles incomplete')
    unwind_cases=[r for p in unwind['profiles']for key in ['native_windows_virtual_unwind','native_windows_backtrack_failure_unwind']for r in p.get(key,[])]
    require(len(unwind_cases)==96 and all(r['status']=='PASS'for r in unwind_cases),'Native Windows unwind cases failed')
    navigation_unwind_sha=visibility['source119_welt_sha256']if visibility else audit['patched_welt_sha256']
    require(any(p['output_sha256']==navigation_unwind_sha for p in unwind['profiles']),'Exact retained navigation profile not covered by Windows unwind proof')
    if visibility:
        require(audit['world_instruction_count']==166 and visibility.get('passed')is True and visibility.get('repaired_full_welt_sha256')==audit['patched_welt_sha256']and visibility.get('new_native_regions')==47,'Expanded visibility review differs from retained166-region World engine')
        require(visibility.get('all_other_file_bytes_and_prior_engine_regions_preserved')is True and visibility.get('automated_complete_native_producer_cases')==36,'Expanded visibility producer/retained navigation proof incomplete')
        require(visibility.get('game_executed_for_repair')is False and visibility.get('failed_actual119_run',{}).get('actual_rendering_failed')is True,'Failed119 rendering must remain explicit and cannot certify this repair')
    require(backtrack.get('status')=='PASS'and len(backtrack.get('cases',[]))==20,'Native backtracking capacity/caller tests incomplete')
    require(independent_backtrack.get('passed')is True and independent_backtrack.get('engine_patch_count')==audit['engine_instruction_count']and len(independent_backtrack.get('cases',[]))==16,'Independent backtracking capacity proof is stale or incomplete')
    require(independent_backtrack['runtime_plan_sha256']==sha(ENGINE/'runtime_engine_edits.json'),'Independent backtracking proof belongs to a different native transaction')
    target=ENGINE/'independent_validation';target.mkdir(parents=True,exist_ok=True);evidence={}
    sources={
        'byte_audit':[HERE/'audit_engine_candidate.py',HERE/'engine_candidate_independent_audit.json',HERE/'publish_engine_review.py',HERE/'verify_backtracking_guard.py',HERE/'backtracking_guard_independent_results.json'],
        'crossmodule':[HERE/'crossmodule_scan.py',HERE/'crossmodule_scan_results.json'],
        'camera':[HERE/'verify_camera_bounds.py',HERE/'camera_bounds_results.json'],
        'save_inspectors':[HERE/name for name in ['compare_live_huge.py','compare_huge_reload.py','inspect_fertility_huge.py','inspect_start_huge.py','test_huge_inspectors.py','huge_inspector_test_results.engine_bound.json','test_full_huge_comparison.py','full_huge_comparator_test_results.json']],
        'grid':[grid/name for name in ['native_test_results.json','allocation_reference_audit.json','guard_test_results.json','transaction_test_results.json','test_world_grid.py','audit_world_grid.py','test_guard.py','test_transaction.py','guard_fixture.c','transaction_fixture.c','transaction_source.inc','existing_world_guard.inc','README.md']],
        'navigation':[nav/name for name in ['navigation_native_results.json','navigation_unwind_results.json','navigation_backtrack_results.json','test_navigation_patch.py','test_navigation_unwind.py','test_navigation_backtrack.py','patched_accessor.asm']]
    }
    for category,paths in sources.items():
        for source in paths:
            before=sha(source);destination=target/category/source.name;destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,destination);require(sha(source)==sha(destination)==before,'Evidence changed during publication')
            evidence[destination.relative_to(PACKAGE).as_posix()]=before
    for name in ['engine_patch.py','runtime_engine_edits.json','grid/world_grid_patch.py','grid/grid_plan_source.json','grid/runtime_grid_edits.json','navigation/navigation_patch.py','navigation/navigation_patch_manifest.json']:
        path=ENGINE/name;evidence[path.relative_to(PACKAGE).as_posix()]=sha(path)
    if visibility:
        evidence[visibility_path.relative_to(PACKAGE).as_posix()]=sha(visibility_path)
        for name,expected in visibility['evidence_sha256'].items():
            relative=Path(name);require(not relative.is_absolute()and '..'not in relative.parts,'Unsafe visibility evidence path')
            path=ENGINE/'visibility'/relative;require(sha(path)==expected,'Visibility evidence changed: '+name)
            evidence[path.relative_to(PACKAGE).as_posix()]=expected
    evidence[depth_path.relative_to(PACKAGE).as_posix()]=sha(depth_path)
    evidence.update(depth_published)
    for name in ['depth/frame_depth_manifest.json','depth/frame_depth_patch.py']:
        evidence[(ENGINE/name).relative_to(PACKAGE).as_posix()]=sha(ENGINE/name)
    evidence[bias_path.relative_to(PACKAGE).as_posix()]=sha(bias_path);evidence.update(bias_published)
    evidence[supplement_path.relative_to(PACKAGE).as_posix()]=sha(supplement_path);evidence.update(translated_published)
    for name in ['bias/frame_bias_manifest.json','bias/frame_bias_patch.py']:
        evidence[(ENGINE/name).relative_to(PACKAGE).as_posix()]=sha(ENGINE/name)
    report=dict(audit,scope='Independent native-byte, allocation, crossmodule, camera-bounds and test-provenance review. Native emulation/private Windows unwind tests are automated checks and do not prove a game run.',
        native_world_grid_test_image_bases=len(grid_tests['native_runs']),native_navigation_component_cases=22,
        windows_private_image_virtual_unwind_cases=96,existing_world_guard_cases=6,atomic_transaction_cases=20,native_backtracking_and_caller_cases=20,independent_backtracking_canary_cases=16,
        active_original_and_copied_exception_directories_verified=True,
        historical_save_parser_sizes=[256,512,1024],synthetic2048_save_parser_is_not_a_game_run=True,
        native_camera_bounds_cases=96,minimap_all_paths_verified=False,
        original_world_grid_bytes=0x6400,appended_world_grid_offset=0x10000,appended_world_grid_bytes=0x10000,enlarged_world_allocation_bytes=0x20000,
        appended_ship_grid_offset=0x4000,ship_pointer_capacity=1024,enlarged_ship_navigator_allocation_bytes=0x6000,
        native_backtracking_coordinate_pairs_capacity=1024,overlong_or_cyclic_backtracking_returns_native_failure_before_stack_overwrite=True,
        visibility_repair_regions=47 if visibility else 0,native_visibility_producer_cases=36 if visibility else 0,
        native_renderer_windows_unwind_cases=26 if visibility else 0,native_renderer_stack_probe_cases=10 if visibility else 0,native_renderer_cpp_cleanup_cases=4 if visibility else 0,
        visibility_128_column_mask_cache_and_zero_sentinel_verified=bool(visibility),
        failed_actual119_rendering_retained=visibility['failed_actual119_run']if visibility else None,
        failed_actual166_midpoint_rendering_retained=depth['causal_observed166_failure'],
        historical_half_depth173_numerical_evidence_retained=True,
        failed_actual173_half_depth_rendering_retained=bias.get('prior_half_depth173_actual_visual_acceptance_failed'),
        frame_bias_runtime_regions=7,frame_bias_disk_only_metadata_edits=1,
        frame_bias_whole_camera_cases=bias['whole_camera_cases'],frame_bias_both_renderer_cases=bias['both_renderer_prefix_cases'],
        frame_bias_legacy_byte_exact_cases=bias['legacy_null_nonsquare_byte_exact_cases'],
        frame_bias_projected_vertices=bias['independent_native_mesh_vertices'],
        frame_bias_native_windows_unwind_cases=bias['independent_native_Windows_unwind_cases'],
        frame_bias_native_windows_image_loader_cases=bias['independent_Windows_loader_RX_leaf_cases'],
        centered_world_depth_full_precision_and_stock_invariants_verified=True,
        translated_native_mesh_vertices=1944,translated_native_water_ground_pixel_comparisons=648,
        translated_float32_high16_bin_changes=3,translated_native_pixel_decision_changes=3,
        translated_depth_and_pixel_decisions_byte_identical=False,
        translated_numerical_comparison_does_not_verify_game_rendering=True,
        repaired_actual_game_run_verified=False if visibility else None,
        evidence_sha256=evidence,
        remaining_live_scope=['Actual2048 load/render across far-half land and all corners','Minimap preview/click transforms and camera edge scrolling','Actual ship orders across old1024 boundary and obstacle routing','Native save and fresh-process reload/resave','1024 regression, installer restoration and longer gameplay/food/trade/combat'])
    output=ENGINE/'engine_patch_review.json';output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(passed=True,patched_welt_sha256=report['patched_welt_sha256'],evidence_files=len(evidence),report=str(output)),indent=2))


if __name__=='__main__':main()
