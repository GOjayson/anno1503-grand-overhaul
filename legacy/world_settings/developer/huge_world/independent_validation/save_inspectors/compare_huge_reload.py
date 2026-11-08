"""Read-only comparison of two native saves around an observed fresh reload.

The caller supplies separate launch diagnostics and an explicit observation
record. This checks process identities and serialized continuity; matching files
alone cannot prove a UI action, a live load, navigation or gameplay behavior.
"""
from pathlib import Path
import argparse,importlib.util,json,struct,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('huge_live_reload_helpers',HERE/'compare_live_huge.py')
M=importlib.util.module_from_spec(spec);sys.modules[spec.name]=M;spec.loader.exec_module(M)


def compare(first,second,first_diag,second_diag,observation,settings,expected_engine_count=None):
    first_identity=(first_diag.get('pid'),first_diag.get('process_creation_time'))
    second_identity=(second_diag.get('pid'),second_diag.get('process_creation_time'))
    M.require(all(type(v)is int and v>0 for v in first_identity+second_identity),'Missing process launch identity')
    M.require(first_identity!=second_identity,'Reload inspection needs a different game process creation identity')
    for key in ['runtime_sha256','executable_sha256','copy_root']:
        M.require(first_diag.get(key) and first_diag.get(key)==second_diag.get(key),'Fresh process uses a different '+key)
    for d in [first_diag,second_diag]:
        M.require(all(d.get(k)==''for k in M.ERRORS),'Native error in a launch diagnostic')
        M.require(d.get('installed_files_modified')is False,'Diagnostic no-installed-write scope missing')
    if expected_engine_count is None:expected_engine_count=first_diag.get('engine_patch_count')
    M.require(type(expected_engine_count)is int and expected_engine_count>104,'Reload source lacks a complete expanded engine transaction identity')
    for d in [first_diag,second_diag]:
        M.require(d.get('engine_state')=='expanded' and d.get('engine_patch_count')==d.get('engine_patch_status')==expected_engine_count,'A reload launch lacks the exact expanded engine transaction')
    source_sha=M.sha(first);resave_sha=M.sha(second)
    M.require(observation.get('observed_game_closed_before_reload')is True,'Caller has not recorded game closure')
    M.require(observation.get('observed_new_process_loaded_source_save')is True,'Caller has not recorded loading the source save in the new process')
    M.require(observation.get('source_save_sha256')==source_sha,'Observed loaded-source fingerprint differs from first save')
    M.require(observation.get('resave_sha256')==resave_sha,'Observed resave fingerprint differs from second save')
    world_size=settings['worldSize'];fertility_before=M.FERTILITY.inspect(first,M.FERTILITY.MODES[settings['plantFertility']],M.FERTILITY.MODES[settings['mineralFertility']])
    fertility_after=M.FERTILITY.inspect(second,M.FERTILITY.MODES[settings['plantFertility']],M.FERTILITY.MODES[settings['mineralFertility']],baseline=fertility_before)
    M.require(fertility_before['world_width']==fertility_after['world_width']==world_size,'Reload changed world dimensions')
    before_islands=M.saved_islands(first);after_islands=M.saved_islands(second)
    M.require(set(before_islands)==set(after_islands),'Reload changed native island IDs')
    for ident,a in before_islands.items():
        b=after_islands[ident]
        for key in ['id','x','y','width','height','climate','heights']:
            M.require(a[key]==b[key],'Reload changed saved island '+str(ident)+' '+key)
    def deposits(row):
        return sorted((d['native_figure_id'],d['local_x'],d['local_y'],d['saved_whole_quantity']==0)for d in row['deposits'])
    for a,b in zip(fertility_before['islands'],fertility_after['islands']):
        M.require(deposits(a)==deposits(b),'Reload moved/retyped a resource occurrence or changed persistent absence')
    ships_before=M.saved_ships(first,world_size);ships_after=M.saved_ships(second,world_size)
    def ships(inventory):
        return [(r['id'],r['owner'],r['definition'],r['equipped_cannons'],r['cargo'])for r in inventory['ships']]
    M.require(ships(ships_before)==ships(ships_after),'Reload changed ship IDs/owners/classes/cannons/cargo')
    return dict(passed=True,scope=__doc__,source_save_sha256=source_sha,resave_sha256=resave_sha,
        settings=settings,engine_patch_count=expected_engine_count,expanded_engine_verified_in_both_launches=True,first_launch=dict(pid=first_identity[0],process_creation_time=first_identity[1]),
        reloaded_launch=dict(pid=second_identity[0],process_creation_time=second_identity[1]),
        process_creation_identities_differ=True,operator_observation=observation,
        native_world_size_identical=True,native_island_geometry_climate_and_full_heights_identical=True,
        native_crop_flags_and_positive_mineral_good_sets_identical=True,native_resource_positions_and_zero_quantity_absence_identical=True,
        positive_mineral_quantities_required_identical=False,
        native_ship_ids_owners_classes_cannons_and_cargo_identical=True,ship_health_or_coordinates_required_identical=False,
        before_ships=ships_before,after_ships=ships_after,
        far_half_geometry=M.far_half_geometry(after_islands,world_size),
        fertility_after=fertility_after,actual_game_run_proven_by_this_check=False,
        gameplay_food_production_navigation_or_combat_tested_by_this_check=False,game_or_save_or_copy_modified=False)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ['first-save','second-save','first-diagnostic','second-diagnostic','observation','initial-comparison','output']:
        ap.add_argument('--'+name,type=Path,required=True)
    a=ap.parse_args();output=a.output.resolve()
    M.require(output.is_relative_to(HERE)and not output.exists(),'Output must be a new file under this outside validation folder')
    paths={name:getattr(a,name.replace('-','_'))for name in ['first-save','second-save','first-diagnostic','second-diagnostic','observation','initial-comparison']}
    raw={name:M.stable_bytes(path)for name,path in paths.items()}
    initial=M.json_bytes(raw['initial-comparison'])
    M.require(initial.get('passed')is True and initial.get('save_sha256')==M.sha(raw['first-save']),'Initial preview-to-native-save comparison is absent or belongs to a different source save')
    result=compare(raw['first-save'],raw['second-save'],M.json_bytes(raw['first-diagnostic']),M.json_bytes(raw['second-diagnostic']),M.json_bytes(raw['observation']),initial['settings'],initial['engine_patch_count'])
    result.update(inspector_sha256=M.file_sha(Path(__file__)),helper_sha256=M.file_sha(HERE/'compare_live_huge.py'),
        input_sha256={name:dict(path=str(paths[name].resolve()),sha256=M.sha(data))for name,data in raw.items()})
    for name,path in paths.items():M.require(M.file_sha(path)==M.sha(raw[name]),'Input changed during inspection: '+name)
    output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(passed=True,source_save_sha256=result['source_save_sha256'],resave_sha256=result['resave_sha256'],world_size=result['settings']['worldSize'],report=str(output)),indent=2))


if __name__=='__main__':main()
