"""Bind the experimental2048 engine repair and current runtime evidence.

This is a deterministic read-only evidence collector. It neither runs tests nor
accesses a game process. Original-engine overflow and Venetian fixtures remain
historical evidence with their original scope; fresh reports must name the
current runtime and its entire compiled source closure.
"""
from pathlib import Path,PurePosixPath
import hashlib,json

PRIVATE='engine_resume/ai_food/experiment_runtime/'
ORIGINAL_WELT='ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9'
DEV7_WELT='059ecd1dcb2139b350f50a2805d811eff89e61cead2733ca9aedb6da83058319'
FOOD_FRAME='046b5ad6f351dfe867ed38ce29fb50a594485b43a32ee90adadc48e850466baf'
AI={'native/CompLogic.food-ai.dll':'0612873c32c95252144f4b4fd2bed45dddddc177303981833b673ddc4ed51453',
    'native/CompLogicClassic.food-ai.dll':'29d1759bd3beb39f9a5a3364946a24b36f8bb4fa546c6a999b6ca994aeeaab34'}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok,message):
    if not ok:raise ValueError(message)


def collect_huge_world(package,source,build):
    package,source=Path(package).resolve(),Path(source).resolve()
    runtime=sha(source/'runtime_dev3/AnnoWorldSettings.dll')
    require(build.get('sha256')==runtime and build.get('abi_size')==56 and build.get('native_hooks')==9,
        'Huge evidence requires the current ABI56/nine-hook runtime')
    compiled={name.replace('\\','/'):digest for name,digest in build.get('source_sha256',{}).items()}
    require(len(compiled)==43,'Huge runtime must bind its43 compiled inputs, including the engine plan')
    plans=[name for name in compiled if name.endswith('/engine_patch_plan.h')or name=='engine_patch_plan.h']
    require(len(plans)==1,'Runtime compilation closure lacks one unambiguous engine_patch_plan.h')
    inputs,evidence={},{}
    def bind(name,expected=None):
        relative=PurePosixPath(name)
        require(not relative.is_absolute()and '..'not in relative.parts and '\\'not in name,'Unsafe Huge evidence path')
        path=package.joinpath(*relative.parts).resolve(strict=True)
        require(path.is_relative_to(package),'Huge evidence leaves package')
        digest=sha(path);require(expected is None or digest==expected,'Huge evidence changed: '+name)
        evidence[name]=digest
        return json.loads(path.read_bytes())if path.suffix=='.json'else None
    for name,expected in compiled.items():
        relative=PurePosixPath(name)
        require(not relative.is_absolute()and '..'not in relative.parts,'Unsafe compiled source path')
        path=source.joinpath(*relative.parts).resolve(strict=True);require(path.is_relative_to(source),'Compiled source leaves source root')
        require(sha(path)==expected,'Huge runtime input changed since compilation: '+name)
        inputs['developer/source/'+name]=expected
    bind('developer/source/runtime_dev3/build_result.json')
    engine=bind('developer/huge_world/engine_patch_review.json')
    require(engine.get('passed')is True and engine.get('architecture')=='AMD64 PE32+'and engine.get('game_executed')is False,
        'Expanded native engine review is missing or overclaims gameplay')
    require(engine.get('original_welt_sha256')==ORIGINAL_WELT and engine.get('dev7_welt_sha256')==DEV7_WELT,
        'Expanded engine review does not identify the exact HE and Food-compatible baselines')
    require(engine.get('runtime_plan_sha256')==compiled[plans[0]],'Compiled engine plan differs from independent native review')
    require(type(engine.get('engine_instruction_count'))is int and engine['engine_instruction_count']>104,
        'Engine review omits the separate navigation repair')
    require(engine['engine_instruction_count']==build.get('engine_patch_count')and engine.get('world_instruction_count')==166 and engine.get('frame_instruction_count')==7 and engine['engine_instruction_count']==173 and build.get('engine_profile')=='history-amd64-world-ship-render-and-recenter-v4',
        'Huge centered-depth evidence requires166 retained World regions plus7 guarded Frame regions in v4')
    plan=bind('developer/huge_world/runtime_engine_edits.json')
    require(set(plan.get('modules',{}))=={'AnnoWelt.dll','AnnoFrame.dll'}and plan['modules']==engine.get('engine_modules'),
        'Independent review lacks exact loaded/copied/patched module fingerprints')
    require(plan.get('world_instruction_count')==166 and plan.get('frame_instruction_count')==7 and plan.get('engine_instruction_count')==173,
        'Module transaction counts differ from independent review')
    require(isinstance(engine.get('patched_welt_sha256'),str)and len(engine['patched_welt_sha256'])==64,
        'Expanded engine review lacks its exact disk-copy output fingerprint')
    require(engine.get('all_changes_explained_by_reviewed_operands')is True and engine.get('food_and_world_hooks_preserved')is True,
        'Independent expanded engine byte/preservation audit is incomplete')
    require(engine.get('evidence_sha256'),'Expanded engine review has no evidence bindings')
    for name,expected in engine['evidence_sha256'].items():bind(name,expected)
    depth=bind('developer/huge_world/depth/FRAME_DEPTH_REVIEW.json')
    bias=bind('developer/huge_world/bias/FRAME_BIAS_REVIEW.json')
    frame=plan['modules']['AnnoFrame.dll']
    require(depth.get('passed')is True and depth.get('runtime_edit_count')==7 and depth.get('disk_only_metadata_edit_count')==1,
        'Size-aware Frame depth review is incomplete')
    require(frame['source_sha256']==FOOD_FRAME and bias.get('source_to_output_sha256',{}).get(frame['copied_input_sha256'])==frame['patched_sha256']==engine.get('patched_frame_sha256'),
        'Frame source/copy/output fingerprint differs from complete centered-bias review')
    require(depth.get('native_frame_cases')==864 and depth.get('legacy_null_nonsquare_byte_exact_cases')==720 and depth.get('independent_projected_vertices')==5832 and depth.get('independent_Windows_unwind_cases')==168 and depth.get('independent_Windows_image_loader_cases')==4,
        'Frame depth native/legacy/consumer/Windows evidence is incomplete')
    require(depth.get('original_image_final_page_already_committed_RX')is True and depth.get('helper_no_stack_adjustment_or_nonvolatile_changes')is True and depth.get('exception_directories_and_unwind_metadata_unchanged')is True,
        'Frame native helper lifetime/loader/unwind contract is incomplete')
    require(depth.get('actual_repaired_game_run_verified')is False and depth.get('causal_observed166_failure',{}).get('current_runtime_failed_visual_acceptance')is True and depth['causal_observed166_failure'].get('counted_as_accepted_repaired_game_run')is False,
        'Failed166 visual acceptance must remain separate from this automated depth repair')
    require(bias.get('passed')is True and bias.get('automated_component_approved')is True and bias.get('runtime_edit_count')==7 and bias.get('disk_only_metadata_edit_count')==1,
        'Full-precision centered-bias component review is incomplete')
    require(bias.get('whole_camera_cases')==864 and bias.get('both_renderer_prefix_cases')==1440 and bias.get('legacy_null_nonsquare_byte_exact_cases')==720 and bias.get('independent_native_mesh_vertices')==5832 and bias.get('independent_native_Windows_unwind_cases')==240 and bias.get('independent_Windows_loader_RX_leaf_cases')==4,
        'Centered-bias native/legacy/consumer/Windows evidence is incomplete')
    require(bias.get('original_normalization_and_height_precision_preserved')is True and bias.get('original_state6_matrix_and_all_local_sprite_globals_preserved')is True and bias.get('exception_unwind_tables_and_all_Food_hooks_unchanged')is True,
        'Centered-bias precision/local-sprite/unwind/preservation invariant is incomplete')
    require(bias.get('prior_half_depth173_actual_visual_acceptance_failed')is True and bias.get('actual_repaired_game_run_verified')is False,
        'Failed half-depth173 cannot certify the distinct current centered-bias runtime')
    translated=bind('developer/huge_world/bias/FRAME_BIAS_TRANSLATED_PIXEL_SUPPLEMENT.json')
    require(translated.get('passed')is True and translated.get('approved_component_review_sha256')==sha(package/'developer/huge_world/bias/FRAME_BIAS_REVIEW.json') and translated.get('copied_frame_sha256')==frame['patched_sha256'],
        'Translated numerical supplement differs from the immutable approved Frame candidate')
    require(translated.get('native_projected_packed_vertices')==1944 and translated.get('native_water_ground_pixel_comparisons')==648 and translated.get('high16_quantization_bin_changes')==3 and translated.get('native_pixel_decision_changes')==3,
        'Translated numerical sample matrix or measured rounding differences are incomplete')
    require(translated.get('translated_depths_or_pixel_decisions_byte_identical')is False and translated.get('state6_bytes_and_original_depth_slopes_exact')is True and translated.get('actual_game_rendering_or_draw_order_verified_by_supplement')is False,
        'Translated numerical comparison must retain its Float32 differences and non-game scope')
    visibility=bind('developer/huge_world/visibility/VISIBILITY_REPAIR_REVIEW.json')
    require(visibility.get('passed')is True and visibility.get('game_executed_for_repair')is False and visibility.get('repaired_full_welt_sha256')==engine['patched_welt_sha256']and visibility.get('new_native_regions')==47 and visibility.get('combined_runtime_regions')==166,
        'Retained166-region World visibility repair differs from the exact reviewed World module')
    require(visibility.get('automated_complete_native_producer_cases')==36 and visibility.get('independent_stack_operands_verified')==117 and visibility.get('native_windows_unwind_cases')==26 and visibility.get('native_stack_probe_cases')==10 and visibility.get('native_cpp_cleanup_funclet_cases')==4,
        'Native visibility producer/stack/unwind/EH evidence is incomplete')
    require(visibility.get('new_visibility_mask_bytes')==2048 and visibility.get('new_cache_columns')==128 and visibility.get('new_stack_frame_bytes')==920808 and visibility.get('visible_record_capacity_unchanged')==8192 and visibility.get('matrix_zero_sentinel_and_recycling_on_capacity_drop')is True,
        'Reviewed renderer mask/cache/capacity contract differs')
    require(engine.get('visibility_repair_regions')==47 and engine.get('visibility_128_column_mask_cache_and_zero_sentinel_verified')is True,
        'Independent full engine review omits the renderer repair')
    require(visibility.get('failed_actual119_run',{}).get('actual_rendering_failed')is True and visibility['failed_actual119_run'].get('counted_as_a_successful_repaired_game_run')is False and engine.get('repaired_actual_game_run_verified')is False,
        'The failed119-site actual game run must not be counted as a repaired rendering pass')
    for name,expected in visibility['evidence_sha256'].items():bind('developer/huge_world/visibility/'+name,expected)
    require(sha(package/'native/AnnoWelt.source.dll')==ORIGINAL_WELT and sha(package/'native/AnnoFrame.food05.dll')==FOOD_FRAME,
        'Original native World or working Food baseline changed')
    for name,expected in AI.items():require(sha(package/name)==expected,'Working Food-compatible private AI changed: '+name)
    native=bind('developer/world_size/native_dimensions_results.json')
    bind('developer/world_size/native_dimensions_evidence.py');bind('developer/world_size/native_dimensions.asm')
    require(native.get('game_executed')is False and native.get('blocked_size')==2048 and native.get('inline_island_lookup_bytes')==25600,
        'Historical original-engine overflow evidence lost its scope')
    require(native.get('supported_generated_sizes')==[256,512,1024]and native.get('island_pointer_table_start')=='0x6640',
        'Historical original-engine layout identity differs')
    require(any(not row['inside_fixed_lookup']and not row['inside_native_world_object']for row in native.get('native_lookup_cases',[])if row['world_size']==2048),
        'Historical original2048 overflow not demonstrated')
    venice=bind('developer/world_sizes/venetians/VENETIAN_REVIEW.json')
    require(venice.get('passed')is True and venice.get('game_executed')is False and venice.get('ui_or_gameplay_verified')is False,
        'Historical Venetian fixtures are absent or overclaim a live run')
    for name,expected in venice.get('evidence_sha256',{}).items():bind(name,expected)
    owner_source=(source/(PRIVATE+'validated_world.inc')).read_text()
    owner=owner_source[owner_source.index('/* Venetian owner gate:'):owner_source.index('/* Welt a28e0 property1c')]
    require(hashlib.sha256(owner.encode()).hexdigest()==venice.get('owner_gate_sha256'),
        'Current Venetian owner gate differs from its unchanged historical native fixture')
    coast=bind('developer/layout_preview/coasts/coastline_manifest.json')
    require(coast.get('template_count')==444 and coast.get('resolution')==64 and coast.get('all_template_hashes_verified')is True,
        'Actual island coastline catalogue is incomplete')
    require(coast.get('generated_header_sha256')==compiled.get(PRIVATE+'world_preview_coasts.h')and coast.get('catalogue_sha256')==compiled.get(PRIVATE+'world_catalogue.h'),
        'Compiled preview coast masks/catalogue differ from their actual asset evidence')
    current=bind('developer/huge_world/huge_runtime_results.json')
    require(current.get('passed')is True and current.get('runtime_sha256')==runtime,
        'Fresh Huge runtime evidence is absent or belongs to a different runtime')
    require(current.get('build_result_sha256')==sha(source/'runtime_dev3/build_result.json')and current.get('compiled_source_sha256')==build['source_sha256'],
        'Fresh Huge runtime proof does not bind all current compiled inputs')
    require(current.get('settings_abi')==56 and current.get('snapshot_size')==5192 and current.get('plan_island_size')==40 and current.get('template_count')==444,
        'Fresh Huge runtime proof uses a different settings/preview ABI')
    for key,value in [('game_executed',False),('actual_game_runs',0),('ui_or_gameplay_verified',False),('native_loading_verified',False),('native_finish_status_is_emulated',True),('shared_game_copy_modified',False)]:
        require(current.get(key)is value if type(value)is bool else current.get(key)==value,'Huge runtime proof overclaims execution: '+key)
    require(current.get('supported_world_sizes_tested')==[256,512,1024,2048],
        'Fresh Huge proof lacks one of the four world dimensions')
    cases=current.get('cases',[])
    require(len(cases)==40 and {row['configuration'][0]for row in cases}=={256,512,1024,2048},
        'Fresh Huge world scene matrix is incomplete')
    huge=[]
    for row in cases:
        size=row['configuration'][0];count=row['configuration'][2];rows=row.get('plan_rows',[])
        require(row.get('head_dimensions')==[size,size]and row.get('exact_cached_link_rows')==count and len(rows)==count,
            'A fresh scene differs from its complete cached preview rows/dimensions')
        require(all(row.get(flag)is True for flag in ['essential_resources_valid','all_ship_positions_exact_and_in_world','all_ship_water_clearance_valid']),
            'A fresh scene has an unchecked resource/ship contract')
        require(len(row.get('serialized_ships',[]))==row.get('ship_count')and row['ship_count']>0,
            'A fresh scene lacks its complete serialized starting ship tuples')
        for p in rows:
            require(p['x']%8==p['y']%8==0 and 0<=p['x']<=size-p['width']and 0<=p['y']<=size-p['height'],
                'A fresh preview row leaves its dynamic native world')
        if size==2048:
            far_x=sum(p['x']+p['width']>1024 for p in rows);far_y=sum(p['y']+p['height']>1024 for p in rows)
            require(far_x or far_y,'A Huge fixture never leaves the old1024 square')
            huge.append(dict(seed=row['seed'],count=count,far_x_island_rows=far_x,far_y_island_rows=far_y,
                serialized_ship_tuples_in_far_half=sum(s['x']>=1024 or s['y']>=1024 for s in row['serialized_ships']),
                serialized_ship_scope='Includes inactive native scene placeholders; this does not prove live AI ships or navigation.'))
    require(len(huge)==14 and any(r['far_x_island_rows']and r['far_y_island_rows']for r in huge),
        'Huge proof lacks14 staged scenes and at least one full two-axis far-half map')
    for flag in ['far_half_geometry_verified','full_settings_seed_and_all40byte_rows_retained','stale_worldSize_rejected_before_publication','unsupported_4096_rejected_before_publication','fixture_inputs_unchanged','temporary_scenes_cleaned']:
        require(current.get(flag)is True,'Fresh Huge proof lacks '+flag)
    for name,expected in current.get('test_source_sha256',{}).items():bind(name,expected)
    bind('developer/huge_world/collector.py')
    return dict(scope=__doc__,passed=True,game_executed=False,ui_or_gameplay_verified=False,
        runtime_sha256=runtime,settings_abi=56,snapshot_size=5192,supported_world_sizes=[256,512,1024,2048],
        rejected_world_sizes=[4096],experimental_world_sizes=[2048],catalogue_templates=444,
        compiled_inputs_sha256=inputs,engine_instruction_count=engine['engine_instruction_count'],
        native_original_welt_sha256=ORIGINAL_WELT,dev7_welt_sha256=DEV7_WELT,
        patched_welt_sha256=engine['patched_welt_sha256'],patched_frame_sha256=frame['patched_sha256'],runtime_plan_sha256=compiled[plans[0]],
        world_instruction_count=166,frame_instruction_count=7,engine_modules=plan['modules'],
        engine_profile=build['engine_profile'],visibility_repair_regions=47,native_visibility_producer_cases=36,
        native_renderer_windows_unwind_cases=26,native_renderer_stack_probes=10,native_renderer_cpp_cleanup_cases=4,
        prior_actual119_rendering_failed=True,repaired_actual_rendering_verified_by_this_collector=False,
        prior_actual166_midpoint_rendering_failed=True,prior_actual173_half_depth_rendering_failed=True,
        frame_bias_whole_camera_cases=864,frame_bias_both_renderer_cases=1440,
        frame_bias_native_windows_unwind_cases=240,frame_bias_native_windows_image_loader_cases=4,
        original_full_depth_precision_and_state6_preserved=True,
        centered_bias_repair_actual_gameplay_verified_by_this_collector=False,
        translated_native_mesh_vertices=1944,translated_native_water_ground_pixel_comparisons=648,
        translated_float32_quantization_bin_changes=3,translated_native_pixel_decision_changes=3,
        translated_depth_or_pixel_decisions_byte_identical=False,
        original_engine_overflow_retained_as_historical_evidence=True,
        working_food_frame_and_private_ai_preserved=True,current_runtime_staged_scenes=len(cases),
        current_runtime_huge_scenes=len(huge),far_half_scene_details=huge,
        historical_venetian_fixture_scope='Unchanged native owner/coordinate helpers; this does not certify a new2048 game run.',
        evidence_sha256=evidence,
        limits=['Actual2048 loading, rendering, minimap/camera, navigation and fresh-process save/reload require separate observed game evidence.',
                'Native instruction emulation and runtime staging do not establish long-session stability, food production, trade or combat.',
                'Huge remains an experimental engine extension; original and prior released files/backups must remain preserved.'])


if __name__=='__main__':
    here=Path(__file__).resolve().parent;package=here.parents[1];source=package/'developer/source'
    build=json.loads((source/'runtime_dev3/build_result.json').read_bytes())
    result=collect_huge_world(package,source,build)
    (here/'HUGE_WORLD_REVIEW.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(passed=True,runtime_sha256=result['runtime_sha256'],compiled_inputs=len(result['compiled_inputs_sha256']),evidence_files=len(result['evidence_sha256']),game_executed=False),indent=2))
