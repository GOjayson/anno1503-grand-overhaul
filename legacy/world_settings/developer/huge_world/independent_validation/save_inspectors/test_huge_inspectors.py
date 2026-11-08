"""Automated parser/reload checks on historical saves and synthetic2048 bytes.

No synthetic save is written or loaded by the game. Historical user saves are
read only. This test does not provide a2048 game run or a reload observation.
"""
from pathlib import Path
import copy,importlib.util,json,struct,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);mod=importlib.util.module_from_spec(spec)
    sys.modules[name]=mod;spec.loader.exec_module(mod);return mod


M=module('huge_parser_test_helpers',HERE/'compare_live_huge.py')
R=module('huge_reload_test_helpers',HERE/'compare_huge_reload.py')


def translate_small_save(data):
    changed=bytearray(data);root=M.FERTILITY.chunk(data,0,len(data))
    for item in M.FERTILITY.chunks(data,16,root.end):
        if item.tag=='WELT':struct.pack_into('<II',changed,item.offset+16,2048,2048)
        elif item.tag=='INSEL5':
            x,y=struct.unpack_from('<HH',item.payload)
            struct.pack_into('<HH',changed,item.offset+16,x+1792,y+1792)
        elif item.tag=='SPIELER':
            for tag,p,at in M.START.fields(item.payload,8):
                if tag not in ('SCHIFF','SCHI64'):continue
                header=10 if struct.unpack_from('<H',item.payload,at+6)[0]>=0xff00 else 8
                offset=8 if tag=='SCHIFF'else 12;x,y=struct.unpack_from('<ff',p,offset)
                struct.pack_into('<ff',changed,item.offset+16+at+header+offset,x+1792,y+1792)
    return bytes(changed)


def main():
    old=M.GAME/'WorldSettings_Work/world_sizes';checks=[];historical=[]
    for name in ['b10','m10','s10']:
        report=json.loads((old/(name+'_preview_comparison.json')).read_bytes());path=Path(report['save_path'])
        data=M.stable_bytes(path);M.require(M.sha(data)==report['save_sha256'],'Historical save fingerprint changed')
        s=report['settings'];f=M.FERTILITY.inspect(data,M.FERTILITY.MODES[s['plantFertility']],M.FERTILITY.MODES[s['mineralFertility']])
        fleet=M.START.inspect(data,['easy','medium','hard'][s['difficulty']],s['startingMoney'],['single','war','merchant'][s['startingFleet']],observed=True)
        ships=M.saved_ships(data,s['worldSize']);M.require(f['world_width']==fleet['world_width']==s['worldSize'],'Dynamic native world dimensions differ')
        M.require(M.file_sha(path)==M.sha(data),'Historical save modified')
        historical.append(dict(name=name,world_size=s['worldSize'],sha256=M.sha(data),all_ships=ships['count'],unchanged=True))
        if name=='s10':source=data;settings=dict(s,worldSize=2048)
    changed=translate_small_save(source);fertility=M.FERTILITY.inspect(changed,M.FERTILITY.MODES[settings['plantFertility']],M.FERTILITY.MODES[settings['mineralFertility']])
    native=M.saved_islands(changed);far=M.far_half_geometry(native,2048);ships=M.saved_ships(changed,2048)
    M.require(fertility['world_width']==2048 and far['old1024_square_is_not_the_entire_test_world'],'Synthetic far-half native geometry rejected')
    M.require(ships['ships_in_far_x_half']==ships['ships_in_far_y_half']==ships['count'],'Synthetic far-half ship positions not represented')
    M.START.inspect(changed,['easy','medium','hard'][settings['difficulty']],settings['startingMoney'],['single','war','merchant'][settings['startingFleet']],observed=True)
    first=dict(pid=100,process_creation_time=123,runtime_sha256='synthetic-runtime',executable_sha256='synthetic-exe',copy_root='synthetic-copy',installed_files_modified=False,engine_state='expanded',engine_patch_count=115,engine_patch_status=115,**{key:''for key in M.ERRORS})
    second=dict(first,pid=101,process_creation_time=124)
    observation=dict(observed_game_closed_before_reload=True,observed_new_process_loaded_source_save=True,source_save_sha256=M.sha(changed),resave_sha256=M.sha(changed))
    result=R.compare(changed,changed,first,second,observation,settings)
    M.require(result['passed']and not result['actual_game_run_proven_by_this_check'],'Reload comparator overclaims a game run')
    failures=[]
    def rejects(name,fn):
        try:fn()
        except (ValueError,struct.error):failures.append(name)
        else:raise AssertionError('Accepted invalid case: '+name)
    root=M.FERTILITY.chunk(changed,0,len(changed));top=list(M.FERTILITY.chunks(changed,16,root.end));world=next(c for c in top if c.tag=='WELT')
    for size in [1024,4096]:
        invalid=bytearray(changed);struct.pack_into('<II',invalid,world.offset+16,size,size)
        rejects('forged world '+str(size),lambda value=bytes(invalid):M.FERTILITY.inspect(value,M.FERTILITY.MODES[settings['plantFertility']],M.FERTILITY.MODES[settings['mineralFertility']]))
    rejects('same process creation',lambda:R.compare(changed,changed,first,first,observation,settings))
    rejects('different copied runtime',lambda:R.compare(changed,changed,first,dict(second,runtime_sha256='different'),observation,settings))
    rejects('unexpanded native engine',lambda:R.compare(changed,changed,first,dict(second,engine_state='original'),observation,settings))
    rejects('incomplete expanded engine transaction',lambda:R.compare(changed,changed,first,dict(second,engine_patch_status=114),observation,settings))
    rejects('missing game closure observation',lambda:R.compare(changed,changed,first,second,dict(observation,observed_game_closed_before_reload=False),settings))
    rejects('unbound loaded save',lambda:R.compare(changed,changed,first,second,dict(observation,source_save_sha256='f'*64),settings))
    moved=bytearray(changed);island=next(c for c in top if c.tag=='INSEL5');x=struct.unpack_from('<H',island.payload)[0];struct.pack_into('<H',moved,island.offset+16,x-8)
    obs=dict(observation,resave_sha256=M.sha(moved))
    rejects('reload changed native geometry',lambda:R.compare(changed,bytes(moved),first,second,obs,settings))
    output=HERE/'huge_inspector_test_results.engine_bound.json';M.require(not output.exists(),'Tests require a new report path')
    report=dict(scope=__doc__,passed=True,historical_native_save_cases=historical,
        synthetic2048_far_half_native_geometry_and_resources=True,synthetic2048_far_half_ship_coordinates=True,
        synthetic_reload_comparison_passed=True,rejected_cases=failures,rejected_count=len(failures),
        actual_game_run=False,actual_fresh_process_reload=False,game_or_save_or_copy_modified=False,
        source_sha256={p.name:M.file_sha(p)for p in [Path(__file__),HERE/'compare_live_huge.py',HERE/'compare_huge_reload.py',HERE/'inspect_fertility_huge.py',HERE/'inspect_start_huge.py']})
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(passed=True,historical_cases=len(historical),synthetic_far_half_world=2048,rejected_cases=len(failures),report=str(output)),indent=2))


if __name__=='__main__':main()
