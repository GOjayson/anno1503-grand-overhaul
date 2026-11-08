"""Synthetic capture-to-native-save tests, including a translated2048 fixture.

The source is historical game saves. Diagnostic identities are explicitly
synthetic. A translated byte array is never written as a save or loaded by Anno.
These tests establish parser/comparator behavior, not a new engine game run.
"""
from pathlib import Path
import copy,importlib.util,json,struct,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


M=load('full_huge_comparison_helpers',HERE/'compare_live_huge.py')
T=load('full_huge_translation_helpers',HERE/'test_huge_inspectors.py')


def snapshot(settings,rows,state,seed):
    raw=bytearray(5192);struct.pack_into('<4I',raw,0,5192,state,seed,len(rows))
    struct.pack_into('<I5i2I6i',raw,16,*(settings[k]for k in M.SF))
    for i,row in enumerate(rows):struct.pack_into('<10I',raw,72+i*40,*(row[k]for k in M.IF))
    return M.DECODER.decode(bytes(raw))


def main():
    M.configure_package(M.PACKAGE)
    context=dict(runtime_sha256='synthetic-current-runtime-identity',world_spec_sha256='synthetic-current-spec-identity',exe_sha256='synthetic-executable-identity',engine_patch_count=115,
        catalogue=M.catalogue(),coasts=json.loads((M.PACKAGE/'developer/layout_preview/coasts/coastline_manifest.json').read_bytes()))
    old=M.GAME/'WorldSettings_Work/world_sizes';cases=[];rejected=[]
    for name,target_size in [('b10',1024),('s10',2048)]:
        historical=json.loads((old/(name+'_preview_comparison.json')).read_bytes());path=Path(historical['save_path']);original=M.stable_bytes(path)
        M.require(M.sha(original)==historical['save_sha256'],'Historical native save changed')
        menu=json.loads((old/(name+('_menu_regenerated.json'if name=='b10'else'_menu_before.json'))).read_bytes())
        settings=copy.deepcopy(menu['preview']['settings']);rows=copy.deepcopy(menu['preview']['islands']);settings['worldSize']=target_size
        data=T.translate_small_save(original)if target_size==2048 else original
        if target_size==2048:
            for row in rows:row['x']+=1792;row['y']+=1792
        common=dict(pid=123456,process_creation_time=987654321,runtime_sha256=context['runtime_sha256'],world_spec_sha256=context['world_spec_sha256'],executable_sha256=context['exe_sha256'],
            copy_root='synthetic-marked-copy',installed_files_modified=False,engine_state='expanded',engine_patch_count=115,engine_patch_status=115,
            hook_site_count=9,central_war_site_state='guard-jump',hook_bytes={'synthetic-module':{str(i):'synthetic-not-a-live-hook'for i in range(9)}},**{key:''for key in M.ERRORS})
        ready=dict(common,preview=snapshot(settings,rows,1,123))
        committed=dict(common,preview=snapshot(settings,rows,3,123),ai_profile_validated=True,validated_ai_count=settings['aiCount'],ai_profile_status=settings['aiCount']+1)
        result=M.compare(None,ready,committed,data,context)
        M.require(result['passed']and result['all_saved_height_arrays_match_selected_templates']and not result['actual_game_run_proven_by_this_check'],'Synthetic full comparison failed or overclaims an actual game run')
        for label,mutation in [('original engine',dict(engine_state='original')),('incomplete engine transaction',dict(engine_patch_status=114)),('wrong engine profile count',dict(engine_patch_count=116)),('stale runtime',dict(runtime_sha256='different-runtime'))]:
            bad=dict(committed,**mutation)
            try:M.compare(None,ready,bad,data,context)
            except ValueError:rejected.append(dict(world_size=target_size,case=label))
            else:raise AssertionError('Accepted '+label)
        M.require(M.file_sha(path)==M.sha(original),'Historical native save modified')
        cases.append(dict(world_size=target_size,source_historical_save_sha256=M.sha(original),translated_only_in_memory=target_size==2048,
            exact_native_geometry_resources_terrain_and_coast_match=True,native_ships=result['saved_ship_inventory']['count'],far_half_geometry=result['far_half_geometry'],
            actual_game_run=False))
    output=HERE/'full_huge_comparator_test_results.json';M.require(not output.exists(),'Expected a new test report')
    report=dict(scope=__doc__,passed=True,cases=cases,rejected_cases=rejected,actual_game_run=False,game_or_copy_or_native_save_modified=False,
        source_sha256={path.name:M.file_sha(path)for path in [Path(__file__),HERE/'compare_live_huge.py',HERE/'test_huge_inspectors.py',M.PACKAGE/'activation/preview_snapshot.py']})
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(passed=True,cases=len(cases),rejected_cases=len(rejected),actual_game_run=False,report=str(output)),indent=2))


if __name__=='__main__':main()
