"""Snapshot the rebuilt map-preview runtime and reviewed native copies; no live writes."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import sys
sys.dont_write_bytecode=True
PACKAGE=Path(__file__).resolve().parents[1];WORK=PACKAGE.parent;GAME=WORK.parent
sys.path.insert(0,str(PACKAGE/'support'))
import package_alias_assets as alias_assets
import package_world_assets as world_assets
VERSION='0.11.0-dev.1'


def digest(data):return hashlib.sha256(data).hexdigest()


def snapshot_tree(source,destination):
    destination.mkdir(parents=True,exist_ok=True);inventory={}
    skip={'__pycache__','tmp','_build','compiler_cache','.zig-cache','global-cache','local-cache','zig_global_cache','zig_local_cache'}
    for path in sorted(source.rglob('*')):
        relative=path.relative_to(source)
        if (not path.is_file() or any(x in skip for x in relative.parts) or path.name=='activation_session.json'
                or path.suffix.lower() in {'.dll','.pdb','.lib','.pyc','.obj','.o','.a'}):continue
        target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True)
        if path.resolve()!=target.resolve():shutil.copyfile(path,target)
        inventory[relative.as_posix()]=digest(target.read_bytes())
    return inventory


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,default=WORK)
    parser.add_argument('--game-dir',type=Path,default=GAME)
    args=parser.parse_args(argv);source=args.source_root.resolve(strict=True);game=args.game_dir.resolve(strict=True)
    sys.path[:0]=[str(WORK/'_tools'),str(source/'runtime_dev3'),str(source/'engine_resume/ai_loader'),
                 str(source/'engine_audit'),str(source/'engine_resume/ai_food'),str(source)]
    from frame_payload import transform_full_frame3
    from loader_bridge import transform_welt
    from native_world.patch_scene_copy import transform_scene
    frame=(game/'AnnoFrame.dll').read_bytes();scene=(game/'AnnoScene.dll').read_bytes();welt=(game/'AnnoWelt.dll').read_bytes()
    previous_source_game=os.environ.get('ANNO1503_SOURCE_GAME')
    os.environ['ANNO1503_SOURCE_GAME']=str(game)
    try:
        new_frame,frame_bridge=transform_full_frame3(frame)
    finally:
        if previous_source_game is None:os.environ.pop('ANNO1503_SOURCE_GAME',None)
        else:os.environ['ANNO1503_SOURCE_GAME']=previous_source_game
    new_scene,scene_bridge=transform_scene(scene)
    new_welt,welt_bridge=transform_welt(welt)
    runtime=(source/'runtime_dev3/AnnoWorldSettings.dll').read_bytes()
    build=json.loads((source/'runtime_dev3/build_result.json').read_bytes())
    if (build.get('sha256')!=digest(runtime) or build.get('status')!='UNFINISHED'
            or build.get('backend_registered_in_ui') is not False or build.get('abi_size')!=56
            or build.get('native_hooks')!=9):
        raise ValueError('Rebuilt guarded dev8 runtime with the 56-byte settings ABI is required before snapshot')
    if not build.get('source_sha256'):raise ValueError('Runtime build has no source fingerprints')
    for name,expected in build['source_sha256'].items():
        path=(source/name).resolve(strict=True);path.relative_to(source)
        if digest(path.read_bytes())!=expected:raise ValueError('Runtime source changed after build: '+name)
    sys.path.insert(0,str(PACKAGE/'developer/fertility'))
    from review_inputs import collect,check_prior_archives
    fertility_review=collect(PACKAGE,source,build)
    sys.path.insert(0,str(PACKAGE/'developer/layout_preview'))
    from preview_review import collect_preview
    preview_review=collect_preview(PACKAGE,source,build)
    sys.path.insert(0,str(PACKAGE/'developer/huge_world'))
    from collector import collect_huge_world as collect_world_sizes
    sizes_review=collect_world_sizes(PACKAGE,source,build)
    frozen_prior_releases=check_prior_archives(WORK)
    ai_dir=source/'engine_resume/ai_food/_build/preload'
    ai_manifest=json.loads((source/'engine_resume/ai_food/candidate_manifest.json').read_bytes())
    ai=(ai_dir/'CompLogic.dll').read_bytes();classic=(ai_dir/'CompLogicClassic.dll').read_bytes()
    expected_ai={'CompLogic.dll':'0612873c32c95252144f4b4fd2bed45dddddc177303981833b673ddc4ed51453',
                 'CompLogicClassic.dll':'29d1759bd3beb39f9a5a3364946a24b36f8bb4fa546c6a999b6ca994aeeaab34'}
    for name,data in [('CompLogic.dll',ai),('CompLogicClassic.dll',classic)]:
        if digest(data)!=expected_ai[name]:raise ValueError('Reviewed Food-compatible AI world-policy candidate changed: '+name)
    policy_root=PACKAGE/'developer/start_options/ai'
    policy_review=json.loads((policy_root/'AI_POLICY_REVIEW.json').read_bytes())
    if policy_review.get('candidate_sha256')!=expected_ai or policy_review.get('actual_game_runs')!=0:
        raise ValueError('Exact reviewed AI policy evidence is required; historical game runs cannot certify it')
    for name,expected in policy_review['evidence_sha256'].items():
        if Path(name).name!=name or digest((policy_root/name).read_bytes())!=expected:
            raise ValueError('Reviewed AI policy source/evidence changed: '+name)
    policy_manifest=json.loads((policy_root/'candidate_manifest.json').read_bytes())
    if {item['module']:item['sha256'] for item in policy_manifest['payloads']}!=expected_ai:
        raise ValueError('Reviewed AI policy manifest differs from exact private payloads')
    expected_welt='059ecd1dcb2139b350f50a2805d811eff89e61cead2733ca9aedb6da83058319'
    welt_policy_manifest=json.loads((policy_root/'welt_policy_manifest.json').read_bytes())
    if (policy_review.get('central_welt_sha256')!=expected_welt
            or welt_policy_manifest.get('sha256')!=expected_welt
            or welt_policy_manifest.get('source_sha256')!=digest(new_welt)):
        raise ValueError('Exact central native Welt policy review is required')
    sys.path.insert(0,str(policy_root))
    from transform_welt_policy import transform_bytes
    new_welt,welt_policy=transform_bytes(new_welt)
    if digest(new_welt)!=expected_welt:
        raise ValueError('Central native Welt policy output changed')
    welt_bridge['central_war_policy']=welt_policy
    sys.path.insert(0,str(PACKAGE/'developer/huge_world'))
    from engine_patch import transform_huge_welt,transform_huge_frame
    new_welt,engine_manifest=transform_huge_welt(new_welt)
    new_frame,depth_manifest=transform_huge_frame(new_frame)
    if digest(new_welt)!=sizes_review['patched_welt_sha256']:
        raise ValueError('Expanded engine output differs from reviewed complete patch')
    if digest(new_frame)!=sizes_review['patched_frame_sha256']:
        raise ValueError('Size-aware drawing depth output differs from reviewed Frame patch')
    welt_bridge['expanded_engine']=engine_manifest
    frame_bridge['expanded_world_depth']=depth_manifest
    alias_root=source/'engine_resume/faction_options/pirate_transfer'
    if digest((alias_root/'FROZEN_ALIAS_MANIFEST.json').read_bytes())!=alias_assets.FROZEN_MANIFEST_SHA256:
        raise ValueError('Frozen pirate alias manifest changed')
    catalogue=(source/'engine_resume/ai_food/experiment_runtime/world_catalogue.h').read_bytes()
    data_hashes=alias_assets.validate_source_bundle(game,alias_root/'alias_payload',catalogue)
    world_hashes=world_assets.validate_source_bundle(game,PACKAGE/'assets',catalogue)
    if set(data_hashes)&set(world_hashes):raise ValueError('World data payload policies overlap')
    data_hashes.update(world_hashes)
    payloads={'native/AnnoFrame.food05.dll':frame,'native/AnnoFrame.world.dll':new_frame,
              'native/AnnoScene.source.dll':scene,'native/AnnoScene.world.dll':new_scene,
              'native/AnnoWelt.source.dll':welt,'native/AnnoWelt.world.dll':new_welt,
              'native/AnnoWorldSettings.dll':runtime,'native/CompLogic.food-ai.dll':ai,
              'native/CompLogicClassic.food-ai.dll':classic}
    for target,payload in alias_assets.introduced_files().items():
        data=(alias_root/'alias_payload'/target).read_bytes()
        alias_assets.validate_data_payload(payload,data);payloads[payload]=data
    for target,payload in world_assets.introduced_files().items():
        data=(PACKAGE/'assets'/target).read_bytes()
        world_assets.validate_data_payload(payload,data);payloads[payload]=data
    for name,data in payloads.items():
        path=PACKAGE/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    sources={}
    for folder in ['engine_audit','engine_resume','native_world','runtime_integrated','runtime_dev3','world_certificate']:
        sources[folder]=snapshot_tree(source/folder,PACKAGE/'developer/source'/folder)
    for name in ['frame_factory_bridge.py','test_frame_factory_bridge.py','world_factory.c','world_plan.py',
                 'test_world_plan.py','ui_smoke_host.py','runtime_test_blobs.h','generate_runtime_test_blobs.py','inspect_pe.py']:
        target=PACKAGE/'developer/source'/name;target.parent.mkdir(parents=True,exist_ok=True)
        if (source/name).resolve()!=target.resolve():shutil.copyfile(source/name,target)
        sources[name]=digest(target.read_bytes())
    # Catch a rebuild/source edit racing the snapshot. The manifest must never
    # attribute newly copied source to an older compiled runtime.
    for name,expected in build['source_sha256'].items():
        if (digest((source/name).read_bytes())!=expected
                or digest((PACKAGE/'developer/source'/name).read_bytes())!=expected):
            raise ValueError('Compiled source changed during snapshot: '+name)
    evidence={}
    for name in ['LIVE_TESTS.md','LIVE_TEST_RESULTS.json','test_save_results.json','inspect_test_save.py',
                 'ws5_save_results.json','inspect_ws5_save.py','ws6_save_results.json','inspect_ws6_save.py',
                 'ws7_save_results.json','inspect_ws7_save.py',
                 'installer_audit/final_preservation_check.json',
                 'engine_resume/faction_options/pirate_transfer/actual_faction_save_matrix.json',
                 'engine_resume/faction_options/pirate_transfer/ws9_v2_save_results.json',
                 'engine_resume/faction_options/pirate_transfer/ws10_save_results.json',
                 'engine_resume/faction_options/pirate_transfer/ws11_save_results.json']:
        path=source/name
        if path.is_file():
            target=PACKAGE/name;target.parent.mkdir(parents=True,exist_ok=True)
            if path.resolve()!=target.resolve():shutil.copyfile(path,target)
            evidence[name]=digest(target.read_bytes())
    observed=json.loads((PACKAGE/'LIVE_TEST_RESULTS.json').read_bytes())
    # A later documentation snapshot may change the spec hash without changing
    # tested code. Keep the executed spec hash explicit and bind gameplay claims
    # to the exact DLL, never to a preceding development runtime.
    runtime_hash=digest(runtime)
    matching_runs=[item for item in observed.values() if isinstance(item,dict)
                   and item.get('runtime_sha256')==runtime_hash and isinstance(item.get('runs'),list)]
    live=next((item for item in matching_runs if item['runs'] and
               all(row.get('gameplay_rendered') and row.get('loaded_geometry_resource_ownership_certificate_passed')
                   and row.get('fresh_generation_ordinary_and_special_controller_checks_passed')
                   for row in item['runs'])),None)
    gameplay_evidence=None if live is None else dict(
        runtime_sha256=runtime_hash,executed_world_spec_sha256=live['world_spec_sha256'],
        game_run_names=[row['save_name'] for row in live['runs']],
        scope='Fresh generated worlds reached gameplay; later packaging metadata is not a new game run.',
        complete_feature_verified=False,fresh_process_reload_tested=live.get('fresh_process_reload_tested',False),
        fresh_process_reload=live.get('fresh_process_reload'),
        extended_trade_combat_food_production_tested=live.get('extended_trade_combat_food_production_tested',False))
    # Current live reports are additive to immutable historical evidence. The
    # executed specification hash stays in each report; repackaging is not a run.
    if live is not None:
        for name in ['README.txt','VALIDATION.txt','LIVE_TESTS.md','LIVE_TEST_RESULTS.json','developer/start_options/preservation.json',
                     'developer/fertility/aggregate_live_results.py','developer/fertility/inspect_fertility_save.py',
                     'developer/fertility/test_fertility_save_inspector.py','developer/fertility/fertility_save_inspector_tests.json',
                     'developer/fertility/actual_format_parser_regression.json',
                     'developer/fertility/native_mineral_factory_order.json','developer/fertility/native_mineral_factory_order.asm',
                     'developer/layout_preview/run_infrastructure.py']:
            path=PACKAGE/name
            if path.is_file():evidence[name]=digest(path.read_bytes())
        # Derived installer reports bind this specification themselves. The
        # final package inventory binds those reports without a hash cycle.
        for live_root in [PACKAGE/'developer/start_options/live',PACKAGE/'developer/fertility/live',PACKAGE/'developer/layout_preview/live',PACKAGE/'developer/world_sizes/live',PACKAGE/'developer/huge_world/live']:
            if live_root.is_dir():
                for path in sorted(live_root.iterdir()):
                    if path.is_file():evidence[path.relative_to(PACKAGE).as_posix()]=digest(path.read_bytes())
    fertility_path=PACKAGE/'developer/fertility/FERTILITY_REVIEW.json'
    fertility_path.write_text(json.dumps(fertility_review,indent=2)+'\n',encoding='utf-8')
    preview_path=PACKAGE/'developer/layout_preview/PREVIEW_REVIEW.json'
    preview_path.write_text(json.dumps(preview_review,indent=2)+'\n',encoding='utf-8')
    sizes_path=PACKAGE/'developer/world_sizes/WORLD_SIZES_REVIEW.json'
    sizes_path.write_text(json.dumps(sizes_review,indent=2)+'\n',encoding='utf-8')
    baselines=dict(status='UNFINISHED',version=VERSION,files=sources,runtime_sha256=digest(runtime),
                   runtime_build_metadata=build,ai_candidate_manifest_sha256=digest(json.dumps(ai_manifest,sort_keys=True).encode()),
                   ai_policy_review_sha256=digest((policy_root/'AI_POLICY_REVIEW.json').read_bytes()),
                   ai_policy_evidence_sha256=policy_review['evidence_sha256'],
                   fertility_review_sha256=digest(fertility_path.read_bytes()),
                   fertility_evidence_sha256=fertility_review['evidence_sha256'],
                   preview_review_sha256=digest(preview_path.read_bytes()),
                   preview_evidence_sha256=preview_review['evidence_sha256'],
                   world_sizes_review_sha256=digest(sizes_path.read_bytes()),
                   world_sizes_evidence_sha256=sizes_review['evidence_sha256'],
                   frozen_prior_release_sha256=frozen_prior_releases)
    (PACKAGE/'SOURCE_BASELINES.json').write_text(json.dumps(baselines,indent=2)+'\n',encoding='utf-8')
    overlays={name:dict(baseline_payload=baseline,output_payload=output,food_native=food)
              for name,baseline,output,food in [
                  ('AnnoFrame.dll','native/AnnoFrame.food05.dll','native/AnnoFrame.world.dll',True),
                  ('AnnoScene.dll','native/AnnoScene.source.dll','native/AnnoScene.world.dll',False),
                  ('AnnoWelt.dll','native/AnnoWelt.source.dll','native/AnnoWelt.world.dll',False)]}
    introduced={'AnnoWorldSettings.dll':'native/AnnoWorldSettings.dll',
                'WorldSettingsAI/CompLogic.dll':'native/CompLogic.food-ai.dll',
                'WorldSettingsAI/CompLogicClassic.dll':'native/CompLogicClassic.food-ai.dll'}
    introduced.update(alias_assets.introduced_files())
    introduced.update(world_assets.introduced_files())
    if len(introduced)!=19 or len(payloads)!=25:raise ValueError('Expected 19 introduced files and 25 native/data payloads')
    manifest=dict(version=VERSION,status='UNFINISHED',original_game_root=str(game),
        exe_sha256=digest((game/'Anno1503.exe').read_bytes()),
        source_baselines={name:digest(payloads[item['baseline_payload']]) for name,item in overlays.items()},
        payloads={name:digest(data) for name,data in payloads.items()},data_payloads=data_hashes,
        required_copy_inputs=world_assets.required_copy_inputs(),
        native_overlays=overlays,introduced_files=introduced,
        unchanged_native={name:digest((game/name).read_bytes()) for name in ['CompLogic.dll','CompLogicClassic.dll']},
        bridges={'Frame':frame_bridge,'Scene':scene_bridge,'Welt':welt_bridge},
        candidate_food_ai_range=[0,3],hard_engine_ai_maximum=None,
        settings_abi_size=56,starting_money_choices=[10000,30000,50000,80000,100000],
        starting_fleet_choices=['Single ship','War fleet','Merchant fleet'],
        ai_difficulty_choices=['Peaceful','Easy','Medium','Hard'],
        plant_fertility_choices=['Very fertile','Medium fertility','Low fertility','Mixed'],
        mineral_fertility_choices=['Very fertile','Medium fertility','Low fertility','Mixed'],
        fertility_review='developer/fertility/FERTILITY_REVIEW.json',
        fertility_review_sha256=digest(fertility_path.read_bytes()),
        fertility_evidence_sha256=fertility_review['evidence_sha256'],
        preview_review='developer/layout_preview/PREVIEW_REVIEW.json',
        preview_review_sha256=digest(preview_path.read_bytes()),
        preview_evidence_sha256=preview_review['evidence_sha256'],
        world_sizes_review='developer/world_sizes/WORLD_SIZES_REVIEW.json',
        world_sizes_review_sha256=digest(sizes_path.read_bytes()),
        world_sizes_evidence_sha256=sizes_review['evidence_sha256'],
        island_distribution=dict(policy='Automatic whole-map max-clearance spreading after feasible packing',
            requested_spacing_is_minimum=True,native_grid_tiles=8,world_size_choices=[256,512,1024,2048],
            independent_layout_rng=True,template_resource_assignments_preserved=True),
        world_size_choices=[256,512,1024,2048],unsupported_world_sizes={4096:'Outside the inspected expanded engine profile'},expanded_engine_profile=build['engine_profile'],expanded_engine_patch_count=build['engine_patch_count'],expanded_engine_plan_sha256=digest((PACKAGE/'developer/huge_world/runtime_engine_edits.json').read_bytes()),
        island_size_choices=['Small','Medium','Big (strict)','Mixed','Big (lenient)'],
        island_size_semantics=dict(strict='Largest available per climate and exact native culture group; refuses infeasible packing',lenient='Prefers largest available, permits smaller native templates to fit',venetian_town_exception='Verified stock 80x80 island in all island-size modes'),
        climate_selection='Balanced filler counts across the six climates, independent of template-pool size',
        venetian_town=dict(enabled_switch_requires_exactly_one_island=True,template_index=443,preview_marker='V',native_owner_type=16,native_owner_culture=12),
        map_preview=dict(configuration='in_game_only',regenerate=True,settings_refresh_preview=True,
            coastline_source='Fingerprint-checked native HEIGHT tiles simplified to 64x64 land silhouettes',
            exact_preview_plan_used_at_start=True,stage_replans=False,settings_abi_size=56,
            read_only_snapshot_size=5192,snapshot_states=['absent','ready','staged','committed','cancelled-or-failed']),
        frozen_prior_release_sha256=frozen_prior_releases,
        fertility_semantics=dict(
            independent_of_island_geometry=True,global_essential_resources_required=True,
            plant='Native climate-compatible favorable crop flags; original unfavorable-growth fallback retained',
            native_forced_crop_mask='0xf009',optional_harvest_crop_mask='0xff6',
            terrain_fertility_cells_modified=False,production_multiplier_added=False,
            minerals='Distinct active mineral goods within each native island climate and physical ore-slot capacity',
            assigned_mineral_goods=['iron','gold','salt','gems','marble'],
            unused_mineral_persistence='Native exhausted Figure1661 with zero quantity and no reserve; unsupported disabled-positive state blocks start'),
        ai_policy_review_sha256=digest((policy_root/'AI_POLICY_REVIEW.json').read_bytes()),
        central_war_policy=dict(module='AnnoWelt.dll',entry_rva=0xdf460,output_sha256=expected_welt,
                               configuration='in-game AI difficulty; ordinary tagged CPUs only'),
        settings_configuration='in_game_only',
        actual_game_run=live is not None,packaged_runtime_gameplay_verified=live is not None,
        complete_feature_verified=False,runtime_gameplay_evidence=gameplay_evidence,
        game_evidence=observed,game_evidence_sha256=evidence,
        readiness_gates=['Actual in-game map preview, Regenerate, changed settings, Back/cancel and Start behavior',
                         'Actual generated-world/save comparison against the exact displayed preview seed and island plan',
                         'Broader live map layouts and spacing at different island sizes/counts',
                         'Actual in-game selection of plant/mineral fertility, favorable crop display and active mineral availability',
                         'Actual fresh-process save/reload preserving lower plant availability and mineral-free islands',
                         'Broader live coverage of all fertility levels, native capacities, climates and harvesting/mining accessibility',
                         'Actual in-game selection and start/save/reload of every new money, fleet and AI-difficulty option',
                         'Peaceful never-initiates-war behavior and comparative Easy/Medium/Hard war likelihood in a running game',
                         'Extended positive-AI Food production, consumption, diplomacy, trading and combat',
                         ('Broader fresh-process save loading and activation sequencing beyond the documented case'
                          if live and live.get('fresh_process_reload_tested') else
                          'Fresh-process save loading and activation/load sequencing'),
                         'Broader route, numeric-input, culture-toggle and world-combination live coverage',
                         'Full combined-installer transaction tests against this exact metadata snapshot'])
    (PACKAGE/'world_patch.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    (PACKAGE/'BUILD_PENDING.json').write_text(json.dumps(dict(status='UNFINISHED',version=VERSION,
        payload_ready=True,runtime_sha256=digest(runtime),settings_abi_size=56,native_hooks=9,
        installer_tests_pending=True,actual_game_run=live is not None,complete_feature_verified=False,
        final_shared_copy_acceptance_pending=True,
        exact_runtime_actual_game_runs=[] if live is None else [row['save_name'] for row in live['runs']],
        fertility_review_sha256=digest(fertility_path.read_bytes()),
        preview_review_sha256=digest(preview_path.read_bytes()),preview_snapshot_size=5192,
        world_sizes_review_sha256=digest(sizes_path.read_bytes()),
        world_spec_sha256=digest((PACKAGE/'world_patch.json').read_bytes()),
        source_baselines_sha256=digest((PACKAGE/'SOURCE_BASELINES.json').read_bytes())),indent=2)+'\n')
    print(json.dumps(dict(version=VERSION,status='UNFINISHED',payloads=manifest['payloads']),indent=2))


if __name__=='__main__':main()
