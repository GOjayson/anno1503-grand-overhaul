"""Bind dev7 native world limits, placement/selection and Venetian town evidence."""
from pathlib import Path,PurePosixPath
import hashlib,importlib.util,json

PRIVATE='engine_resume/ai_food/experiment_runtime/'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok,message):
    if not ok:raise ValueError(message)


def collect_world_sizes(package,source,build):
    """Deterministic read-only collector; it performs no tests or game access."""
    package,source=Path(package).resolve(),Path(source).resolve()
    runtime=sha(source/'runtime_dev3/AnnoWorldSettings.dll')
    require(build.get('sha256')==runtime and build.get('abi_size')==56 and build.get('native_hooks')==9,'World-size evidence requires the rebuilt ABI56/nine-hook runtime')
    compiled={name.replace('\\','/'):value for name,value in build['source_sha256'].items()}
    require(len(compiled)==42,'World-size runtime compilation closure must contain42 inputs')
    evidence,inputs={},{}
    def bind(name,expected=None):
        relative=PurePosixPath(name)
        require(not relative.is_absolute() and '..'not in relative.parts and '\\'not in name,'Unsafe world-size evidence path')
        path=package.joinpath(*relative.parts).resolve(strict=True);require(path.is_relative_to(package),'World-size evidence leaves package')
        actual=sha(path);require(expected is None or actual==expected,'Stale world-size evidence: '+name);evidence[name]=actual
        return json.loads(path.read_bytes())if path.suffix=='.json'else None
    for name,expected in compiled.items():
        actual=sha(source/name);require(actual==expected,'Runtime input changed since compilation: '+name);inputs['developer/source/'+name]=actual
    bind('developer/source/runtime_dev3/build_result.json')
    native=bind('developer/world_size/native_dimensions_results.json')
    bind('developer/world_size/native_dimensions_evidence.py');bind('developer/world_size/native_dimensions.asm')
    # The native proof hashes its generated UTF-8 text before Windows newline
    # translation. Bind exact file bytes above and independently reproduce that
    # documented text digest here.
    require(hashlib.sha256((package/'developer/world_size/native_dimensions.asm').read_text().encode()).hexdigest()==native.get('snippets_sha256'),'Native dimension assembly text differs')
    require(native.get('game_executed')is False and native.get('game_or_copy_mutated')is False and native.get('supported_generated_sizes')==[256,512,1024] and native.get('blocked_size')==2048,'Native dimension evidence overclaims support')
    require(native.get('stock_scene_count')==55 and len(native.get('stock_scenes',[]))==55 and len(native.get('native_getter_cases',[]))==16 and len(native.get('native_lookup_cases',[]))==40,'Native world dimension/index evidence incomplete')
    require(native.get('inline_island_lookup_bytes')==25600 and native.get('island_pointer_table_start')=='0x6640' and native.get('native_world_server_allocation_bytes')==28776,'Native inline world lookup limits changed')
    lookups=native['native_lookup_cases']
    require(all(row['inside_fixed_lookup'] and row['inside_native_world_object']for row in lookups if row['world_size']in[256,512,1024]),'Supported world size leaves native lookup bounds')
    require(any(not row['inside_fixed_lookup'] and not row['inside_native_world_object']for row in lookups if row['world_size']==2048),'Unsafe2048 native overflow not demonstrated')
    for row in native['native_getter_cases']:require(row['value']==row['size'],'Native dimension getter disagrees')
    scene=bind('developer/world_size/world_size_test_results.json');fixture=bind('developer/world_size/fixture_build.json')
    bind('developer/world_size/build_fixture.py');bind('developer/world_size/test_world_size.py');bind('developer/world_size/WORLD_SIZE_REVIEW.md')
    require(scene.get('abi_size')==56 and scene.get('successful_scene_cases')==108 and len(scene.get('cases',[]))==108 and scene.get('ships_checked')==648 and len(scene.get('rejected_cases',[]))==17,'World serializer/ship fixtures incomplete')
    require(scene.get('game_executed')is False and scene.get('game_or_copy_mutated')is False and scene.get('preset_fleet_faction_independent_reservations')is True and scene.get('stock1024_ship_payloads_preserved')is True and scene.get('exact_all_ship_tuple_matcher_executed')is True,'World serializer fixtures are unscoped or omit complete ship contracts')
    require(fixture.get('fixture_dll_sha256')==scene.get('fixture_dll_sha256') and fixture.get('game_executed')is False and fixture.get('game_or_copy_mutated')is False,'World fixture build provenance differs')
    require(len(fixture.get('input_sha256',{}))==22,'World fixture must bind its recursive22-input closure')
    for name,expected in fixture['input_sha256'].items():
        name=name.replace('\\','/');bind(name,expected)
        if name.startswith('developer/source/'):
            require(compiled.get(name[len('developer/source/'):])==expected,'World fixture input differs from the full compiled runtime: '+name)
        else:require(name=='developer/world_size/world_size_fixture.c','Unknown non-runtime world fixture input')
    layout_dir='developer/world_sizes/layout/'
    layout=bind(layout_dir+'LAYOUT_REVIEW.json');layout_results=bind(layout_dir+'layout_results.json')
    require(layout.get('passed')is True and layout.get('game_executed')is False and layout.get('ui_or_gameplay_verified')is False and layout.get('supported_world_sizes')==[256,512,1024] and layout.get('unsupported_2048_rejected')is True and layout.get('template_count')==444 and layout.get('settings_abi_bytes')==56,'World-size layout/selection fixture scope differs')
    for key,name in [('helper_sha256','balanced_layout.inc'),('selection_policy_sha256','selection_policy.inc'),('ship_reserves_sha256','world_ship_reserves.h')]:require(layout.get(key)==compiled.get(PRIVATE+name),'Layout proof differs from the compiled source: '+name)
    require(layout.get('native_fixture_cases')==417 and layout.get('exact_repeat_cases')==417 and layout.get('fill_sequence_cases')==240 and layout.get('strict_lenient_contrast_cases')==4,'Layout/selection matrix evidence incomplete')
    for name,expected in layout.get('evidence_sha256',{}).items():bind(layout_dir+name if Path(name).name==name else name,expected)
    layout_build=bind(layout_dir+'fixture_build.json')
    require(layout_results.get('input_sha256')==layout_build.get('input_sha256'),'Layout runtime evidence compilation closure differs')
    for name,expected in layout_build['input_sha256'].items():
        name=name.replace('\\','/');bind(name,expected)
        if name.startswith('developer/source/'):require(compiled.get(name[len('developer/source/'):])==expected,'Layout fixture input differs from compiled runtime')
    venice=bind('developer/world_sizes/venetians/VENETIAN_REVIEW.json')
    for name,expected in venice.get('evidence_sha256',{}).items():bind(name,expected)
    require(venice.get('passed')is True and venice.get('game_executed')is False and venice.get('ui_or_gameplay_verified')is False and venice.get('catalogue_templates')==444,'Venetian town evidence missing or overclaims a game run')
    for key,value in [('venetian_scene_controller_cases',12),('venetian_rejected_cases',23),('venetian_native_owner_selection_cases',4),('venetian_native_relocation_cases',10),('venetian_native_building_coordinate_cases',730),('venetian_save_inspector_synthetic_cases',2),('venetian_save_inspector_rejected_cases',13)]:require(venice.get(key)==value,'Incomplete Venetian fixture: '+key)
    owner_source=(source/(PRIVATE+'validated_world.inc')).read_text();owner=owner_source[owner_source.index('/* Venetian owner gate:'):owner_source.index('/* Welt a28e0 property1c')]
    require(hashlib.sha256(owner.encode()).hexdigest()==venice.get('owner_gate_sha256'),'Compiled Venetian owner helper differs from reviewed fixture')
    runtime_proof=bind('developer/world_sizes/world_runtime_results.json')
    require(runtime_proof.get('passed')is True and runtime_proof.get('game_executed')is False and runtime_proof.get('actual_game_runs')==0 and runtime_proof.get('ui_or_gameplay_verified')is False and runtime_proof.get('native_loading_verified')is False and runtime_proof.get('native_finish_status_is_emulated')is True and runtime_proof.get('shared_game_copy_modified')is False,'Full-runtime world proof overclaims native game execution')
    require(runtime_proof.get('runtime_sha256')==runtime and runtime_proof.get('build_result_sha256')==sha(source/'runtime_dev3/build_result.json') and runtime_proof.get('compiled_source_sha256')==build['source_sha256'],'Full-runtime world proof belongs to different compiled inputs')
    require(runtime_proof.get('settings_abi')==56 and runtime_proof.get('snapshot_size')==5192 and runtime_proof.get('plan_island_size')==40 and runtime_proof.get('template_count')==444 and runtime_proof.get('supported_world_sizes_tested')==[256,512,1024],'Full-runtime world proof dimensions/ABI differ')
    require(runtime_proof.get('staged_scene_count')==26 and runtime_proof.get('exact_head_and_cached_preview_link_scenes')==26 and runtime_proof.get('all_ship_tuple_cases')==155 and len(runtime_proof.get('rejected_cases',[]))==10,'Full-runtime world scene/ship matrix incomplete')
    for flag in ['strict51224_rejected_lenient51224_staged','balanced_unanchored_climate_counts_verified','full_settings_seed_and_all40byte_rows_retained','stale_worldSize_rejected_before_publication','unsupported_2048_rejected_before_publication','fixture_inputs_unchanged','temporary_scenes_cleaned']:
        require(runtime_proof.get(flag)is True,'Full-runtime world proof lacks '+flag)
    require(len(runtime_proof.get('cases',[]))==26 and {r['configuration'][0]for r in runtime_proof['cases']}=={256,512,1024},'Full-runtime world proof must exercise all three supported sizes')
    for row in runtime_proof['cases']:
        require(row['head_dimensions']==[row['configuration'][0]]*2 and row['exact_cached_link_rows']==row['configuration'][2] and row['essential_resources_valid']is True and row['all_ship_positions_exact_and_in_world']is True and row['all_ship_water_clearance_valid']is True,'Full-runtime scene has an unchecked dimension/preview/resource/ship contract')
    require(sum(row['ship_count']for row in runtime_proof['cases'])==155,'Full-runtime world ship total differs')
    for name,expected in runtime_proof.get('test_source_sha256',{}).items():bind(name,expected)
    bind('developer/world_sizes/world_sizes_review.py')
    return dict(scope=__doc__,passed=True,game_executed=False,ui_or_gameplay_verified=False,runtime_sha256=runtime,settings_abi=56,snapshot_size=5192,supported_world_sizes=[256,512,1024],rejected_world_sizes=[2048],catalogue_templates=444,compiled_inputs_sha256=inputs,native_dimension_getter_cases=16,native_dimension_lookup_cases=40,serialized_scene_cases=108,serialized_ship_cases=648,scene_rejected_cases=17,layout_native_fixture_cases=417,layout_exact_repeat_cases=417,balanced_fill_sequences=240,strict_lenient_contrast_cases=4,full_runtime_staged_world_scenes=26,full_runtime_ship_tuple_cases=155,full_runtime_rejected_cases=10,full_runtime_strict_lenient_and_stale_world_size_guards_passed=True,venetian_scene_controller_cases=12,venetian_rejected_cases=23,venetian_native_building_coordinate_cases=730,venetian_save_inspector_synthetic_cases=2,venetian_save_inspector_rejected_cases=13,evidence_sha256=evidence,limits=['Complete native navigation/rendering/minimap/save/reload at changed world sizes require separate live evidence.','Native2048 specifically overflows this fixed inline layout; no universal engine maximum is claimed.','Old ABI52 loaded-certificate fixtures certify only their historical resource/owner helper scope, not new world dimensions or this runtime.','Venetian native-coordinate fixtures do not replace actual city/building construction and save/reload checks.'])


if __name__=='__main__':
    here=Path(__file__).resolve().parent;package=here.parents[1];source=package/'developer/source';build=json.loads((source/'runtime_dev3/build_result.json').read_bytes());result=collect_world_sizes(package,source,build)
    (here/'WORLD_SIZES_REVIEW.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,runtime_sha256=result['runtime_sha256'],evidence_files=len(result['evidence_sha256']),compiled_inputs=len(result['compiled_inputs_sha256']),game_executed=False),indent=2))
