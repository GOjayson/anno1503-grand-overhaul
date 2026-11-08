"""Check dev8 world sizes through the complete runtime on copied actual assets.

BuildPlan, the real cached-preview StagePreviewScene API, catalogue hashing,
complete SZE generation, filesystem publication and cancellation execute in a
Python host. Only an existing marked preview-stage-* asset fixture receives
temporary scenes. No Anno process, native hooks, native world loading, UI,
navigation, rendered minimap or gameplay is exercised or claimed.
"""
from pathlib import Path
import argparse,collections,ctypes as C,hashlib,importlib.util,json,math,os,struct,sys,time
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
PACKAGE=HERE.parents[1]
SOURCE=PACKAGE/'developer/source'
WORK=PACKAGE.parent
EXE_SHA='1a4bebe7c676a5904834b9e67e936187729dc67c013a4fb4fd64986a3cb8e95a'
MARKER='.anno1503-worldsettings-test-copy.json'
EXPECTED_RUNTIME=json.loads((SOURCE/'runtime_dev3/build_result.json').read_bytes())['sha256']
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture',type=Path,required=True)
    parser.add_argument('--runtime',type=Path,default=SOURCE/'runtime_dev3/AnnoWorldSettings.dll')
    args=parser.parse_args();fixture=args.fixture.resolve(strict=True);runtime=args.runtime.resolve(strict=True)
    assert fixture.is_relative_to((WORK/'layout_preview').resolve()) and fixture.name.startswith('preview-stage-')
    marker=json.loads((fixture/MARKER).read_bytes())
    assert marker['development_copy'] is True and Path(marker['copy_root']).resolve()==fixture
    assert marker['source_exe_sha256']==sha(fixture/'Anno1503.exe')==EXE_SHA
    build_path=SOURCE/'runtime_dev3/build_result.json';build=json.loads(build_path.read_bytes())
    assert sha(runtime)==build['sha256']==EXPECTED_RUNTIME and build['abi_size']==56 and len(build['source_sha256'])==43
    assert all(sha(SOURCE/name)==digest for name,digest in build['source_sha256'].items())
    # Reuse the production parser and independent resource-policy inspector.
    # Import only; neither module's main/game-copy test is invoked.
    economy=PACKAGE/'developer/start_options/economy';sys.path.insert(0,str(economy))
    production_path=economy/'test_production_stage.py';production=load('world_runtime_production_parser',production_path)
    preview_path=PACKAGE/'developer/layout_preview/test_preview_runtime.py';preview=load('world_runtime_preview_types',preview_path)
    policy_path=PACKAGE/'developer/fertility/verify_policy.py';policy=load('world_runtime_resource_policy',policy_path)
    templates,catalogue_path=policy.catalogue()
    metadata_path=SOURCE/'engine_resume/ai_food/experiment_runtime/world_factions.h'
    import re
    factions=list(map(int,re.search(r'wsTemplateFactions\[\]=\{([^}]+)\}',metadata_path.read_text())[1].split(',')))
    assert len(templates)==len(factions)==444
    Settings,Island,Snapshot=preview.Settings,preview.Island,preview.Snapshot
    assert C.sizeof(Settings)==56 and C.sizeof(Island)==40 and C.sizeof(Snapshot)==5192
    lib=C.CDLL(str(runtime));P=C.POINTER
    lib.WorldSettingsSettingsSize.restype=C.c_uint32;assert lib.WorldSettingsSettingsSize()==56
    lib.WorldSettingsPreviewSnapshotSize.restype=C.c_uint32;assert lib.WorldSettingsPreviewSnapshotSize()==5192
    plan=lib.WorldSettingsBuildPlan;plan.argtypes=[P(Settings),C.c_uint32,C.c_void_p,C.c_uint32];plan.restype=C.c_int
    stage=lib.WorldSettingsStagePreviewScene;stage.argtypes=[P(Settings),C.c_char_p,C.c_uint32,P(Island),C.c_uint32,C.c_void_p,C.c_uint32,C.c_void_p,C.c_uint32];stage.restype=C.c_int
    copy=lib.WorldSettingsCopyPreviewSnapshot;copy.argtypes=[C.c_void_p];copy.restype=C.c_uint32
    lib.WorldSettingsFinishAttempt.argtypes=[C.c_int];lib.WorldSettingsIsActive.restype=C.c_int;lib.WorldSettingsPendingPath.restype=C.c_char_p
    lib.WorldSettingsPlanCount.restype=C.c_int;lib.WorldSettingsPlanIsland.argtypes=[C.c_uint32,P(Island)];lib.WorldSettingsPlanIsland.restype=C.c_int
    valid=lib.WorldSettingsValidateSettings;valid.argtypes=[P(Settings),C.c_void_p,C.c_uint32];valid.restype=C.c_int
    error=C.create_string_buffer(512);output=C.create_string_buffer(260);root_bytes=str(fixture).encode('mbcs')
    original_files={p.relative_to(fixture).as_posix():sha(p) for p in fixture.rglob('*') if p.is_file()}
    assert not list((fixture/'Scenes').glob('WorldSettings_*.sze')) and lib.WorldSettingsIsActive()==0
    helper_path=HERE/'layout/layout_results.json';helper=json.loads(helper_path.read_bytes());assert helper['passed'] and helper['native_fixture_cases']>=417
    source_hashes={str(p.relative_to(PACKAGE)).replace('\\','/'):sha(p) for p in [Path(__file__),production_path,economy/'inspect_start_save.py',preview_path,policy_path,catalogue_path,metadata_path,helper_path]}
    def snapshot():
        s=Snapshot();assert copy(C.byref(s))==C.sizeof(s) and s.size==C.sizeof(s) and s.count<=128;return s
    def exact_rows(s):return (Island*s.count).from_buffer_copy(bytes(s.islands)[:s.count*40])
    def as_rows(s):return [{name:int(getattr(p,name)) for name,_ in Island._fields_} for p in s]
    def build_plan(s,seed):
        error.value=b'';t=time.perf_counter();assert plan(C.byref(s),seed,error,len(error))==1,error.value.decode('mbcs','replace')
        elapsed=(time.perf_counter()-t)*1000;cached=snapshot()
        assert cached.state==1 and cached.seed==seed and cached.count==s.islandCount and bytes(cached.settings)==bytes(s)
        assert lib.WorldSettingsPlanCount()==cached.count
        for i,row in enumerate(cached.islands[:cached.count]):
            actual=Island();assert lib.WorldSettingsPlanIsland(i,C.byref(actual))==1 and bytes(actual)==bytes(row)
        return cached,elapsed
    def all_ships(data):
        found=[]
        for chunk in production.scene(data):
            if chunk.tag!='SPIELER':continue
            owner=production.player_id(chunk)
            for tag,payload,_ in production.fields(chunk.payload,8):
                if tag not in ('SCHIFF','SCHI64'):continue
                boat=production.ship(payload,tag);assert boat['owner']==owner
                assert math.isfinite(boat['x']) and math.isfinite(boat['y'])
                found.append(boat)
        return found
    stock=[]
    for name,digest in production.STOCK:
        path=fixture/'Languages/Nl/Scenes/0010SingleEndlos'/name;assert sha(path)==digest;stock.append(all_ships(path.read_bytes()))
    def wanted_ships(s):
        result=[]
        if s.worldSize==256:anchors=[(128.5,224.5),(32.5,224.5),(80.5,224.5),(176.5,224.5),(224.5,224.5)]
        elif s.worldSize==512:anchors=[(256.5,170.5),(128.5,128.5),(384.5,128.5),(384.5,384.5),(128.5,384.5)]
        elif s.worldSize==2048:anchors=[(1024.5,682.5),(512.5,512.5),(1536.5,512.5),(1536.5,1536.5),(512.5,1536.5)]
        else:anchors=None
        for old in stock[s.difficulty]:
            owner=old['owner'];x,y=anchors[owner] if anchors else (old['x'],old['y'])
            result.append((owner,1503 if owner==0 and s.startingFleet else old['definition'],x,y))
        if s.startingFleet:
            human=next(t for t in result if t[0]==0);kind=1504 if s.startingFleet==1 else 1502
            result.extend([(0,kind,human[2]-6,human[3]+6),(0,kind,human[2]+6,human[3]+6)])
        return result
    def inspect_scene(data,s,cached,rows):
        parts=production.scene(data);heads=[p.payload for p in parts if p.tag=='HEAD'];assert len(heads)==1
        assert struct.unpack_from('<II',heads[0])==(s.worldSize,s.worldSize)
        links=[]
        for part in parts:
            assert part.tag!='INSEL5'
            if part.tag!='INSELLNK':continue
            assert len(part.payload)>=14
            x,y,w,h,ident=struct.unpack_from('<HHHHI',part.payload);alias=part.payload[12:]
            assert alias.endswith(b'\0') and b'\0' not in alias[:-1]
            links.append((ident,x,y,w,h,alias[:-1].decode('ascii')))
        expected=[];folders=['polar','tundra','nord','praerie','dschungel','steppe'];prefix=['Po','T','N','Pr','D','S']
        for p in rows:expected.append((p.id,p.x,p.y,p.width,p.height,f'islands\\{folders[p.climate]}\\{prefix[p.climate]}_{p.width:03}x{p.height:03}_dummy.scp'))
        assert links==expected and len(links)==cached.count
        plan_rows=as_rows(rows);policy.check_world(plan_rows,s,templates)
        actual=all_ships(data);tuples=[(r['owner'],r['definition'],r['x'],r['y']) for r in actual];wanted=wanted_ships(s)
        assert sorted(tuples)==sorted(wanted) and len(set(tuples))==len(tuples)
        for boat in actual:
            assert 16<=boat['x']<s.worldSize-16 and 16<=boat['y']<s.worldSize-16
            assert all(not(p.x-16<=boat['x']<p.x+p.width+16 and p.y-16<=boat['y']<p.y+p.height+16) for p in rows)
        fc=collections.Counter(factions[p.templateIndex] for p in rows)
        assert fc[1]==bool(s.factions&1) and fc[2]==bool(s.factions&2)
        return dict(plan_rows=plan_rows,head_dimensions=[s.worldSize,s.worldSize],exact_cached_link_rows=len(links),serialized_ships=[dict(owner=o,definition=d,x=x,y=y) for o,d,x,y in tuples],ship_count=len(actual),climate_counts=[sum(p.climate==c for p in rows) for c in range(6)],faction_counts=dict(fc),venetian_template_indices=[p.templateIndex for p in rows if factions[p.templateIndex]==2],essential_resources_valid=True,all_ship_positions_exact_and_in_world=True,all_ship_water_clearance_valid=True)
    profiles=[(256,0,6,0,0,0),(256,0,8,0,0,0),(512,0,12,0,0,0),(512,0,24,0,0,0),(512,4,24,0,0,0),(512,0,16,8,0,3),(1024,2,12,0,0,0),(1024,4,24,0,0,0),(1024,0,24,8,255,3),(1024,1,24,8,255,3),(1024,3,24,16,255,3),(1024,4,24,8,255,3)]
    profiles.extend([(2048,m,24,16,255,3) for m in range(5)])
    profiles.extend([(2048,0,96,0,0,0),(2048,0,128,0,0,0)])
    candidates=[]
    for config in profiles:
        matches=[case for case in helper['cases'] if case['configuration']==list(config)];assert matches,config
        for match in [matches[0],matches[-1]]:candidates.append((config,match['seed'],'417-case helper success'))
    candidates.extend([((256,0,8,0,0,3),12345,'additional tiny world with both special factions'),((512,4,24,0,0,0),12345,'strict versus lenient contrast')])
    staged=[];rejects=[];validated_dims=set();started=time.perf_counter()
    def no_publication():
        assert lib.WorldSettingsIsActive()==0 and lib.WorldSettingsPendingPath() is None
        assert not list((fixture/'Scenes').glob('WorldSettings_*.sze'))
    for index,(config,seed,provenance) in enumerate(candidates):
        world,mode,count,gap,cultures,factions_on=config
        s=preview.settings(worldSize=world,islandSize=mode,islandCount=count,spacing=gap,cultures=cultures,factions=factions_on,difficulty=index%3,startingFleet=(index//3)%3)
        cached,elapsed=build_plan(s,seed);rows=exact_rows(cached);again,_=build_plan(s,seed);assert bytes(again)==bytes(cached)
        counts=[sum(p.climate==c for p in rows) for c in range(6)]
        if cultures==0 and factions_on==0 and count%6==0:assert counts==[count//6]*6
        if world not in validated_dims:
            # World size is part of cache identity, even when both dimensions
            # are individually supported. Rejection must not touch the cache.
            for changed_size in [512 if world!=512 else 1024,4096]:
                changed=preview.clone(s);changed.worldSize=changed_size;old=bytes(snapshot());output.value=error.value=b''
                assert stage(C.byref(changed),root_bytes,seed,rows,len(rows),output,len(output),error,len(error))==0 and error.value
                no_publication();assert bytes(snapshot())==old
                rejects.append(dict(case='Stale cached worldSize',preview_world_size=world,requested_world_size=changed_size,error=error.value.decode('mbcs','replace')))
            validated_dims.add(world)
        path=None
        try:
            output.value=error.value=b'';assert stage(C.byref(s),root_bytes,seed,rows,len(rows),output,len(output),error,len(error))==1,error.value.decode('mbcs','replace')
            path=Path(output.value.decode('mbcs')).resolve();assert path.parent==fixture/'Scenes' and path.name.startswith('WorldSettings_'+str(os.getpid())+'_') and path.suffix=='.sze'
            assert path.is_file() and lib.WorldSettingsIsActive()==1 and Path(lib.WorldSettingsPendingPath().decode('mbcs')).resolve()==path
            active=snapshot();assert active.state==2 and active.seed==seed and active.count==cached.count and bytes(active.settings)==bytes(s)
            assert bytes(exact_rows(active))==bytes(rows)
            data=path.read_bytes();detail=inspect_scene(data,s,cached,rows)
            staged.append(dict(configuration=config,seed=seed,seed_provenance=provenance,difficulty=s.difficulty,starting_fleet=s.startingFleet,settings_sha256=hashlib.sha256(bytes(s)).hexdigest(),preview_plan_sha256=hashlib.sha256(bytes(rows)).hexdigest(),scene_sha256=hashlib.sha256(data).hexdigest(),scene_bytes=len(data),plan_ms=elapsed,**detail))
        finally:
            lib.WorldSettingsFinishAttempt(0)
            if path:assert not path.exists()
            no_publication()
    assert len(staged)==40 and validated_dims=={256,512,1024,2048}
    huge=[r for r in staged if r['configuration'][0]==2048];assert len(huge)==14
    # A failed strict plan and invalid dimensions clear older readiness and
    # cannot leave any published scene. This executes the actual BuildPlan.
    for world in [256,512,1024,2048]:
        known=next(c for c in staged if c['configuration'][0]==world)
        _,mode,count,gap,cultures,factions_on=known['configuration']
        ready=preview.settings(worldSize=world,islandSize=mode,islandCount=count,spacing=gap,cultures=cultures,factions=factions_on,difficulty=known['difficulty'],startingFleet=known['starting_fleet'])
        build_plan(ready,known['seed'])
        bad=preview.settings(worldSize=4096);assert valid(C.byref(bad),error,len(error))==0 and error.value
        assert plan(C.byref(bad),12345,error,len(error))==0 and error.value
        cleared=snapshot();assert cleared.state==0 and cleared.count==0;no_publication();rejects.append(dict(case='Unsupported4096 failed replan clears readiness',previous_ready_world_size=world,error=error.value.decode('mbcs','replace')))
    strict=preview.settings(worldSize=512,islandSize=2,islandCount=24,cultures=0,factions=0)
    assert plan(C.byref(strict),12345,error,len(error))==0 and error.value;no_publication();assert snapshot().state==0
    rejects.append(dict(case='Strict51224 cannot fit',error=error.value.decode('mbcs','replace')))
    contrast=next(c for c in staged if c['configuration']==(512,4,24,0,0,0) and c['seed']==12345)
    assert contrast['climate_counts']==[4]*6
    assert original_files=={p.relative_to(fixture).as_posix():sha(p) for p in fixture.rglob('*') if p.is_file()}
    assert sha(runtime)==EXPECTED_RUNTIME and all(sha(SOURCE/name)==digest for name,digest in build['source_sha256'].items())
    assert source_hashes=={name:sha(PACKAGE/name) for name in source_hashes}
    report=dict(scope=__doc__,passed=True,game_executed=False,actual_game_runs=0,ui_or_gameplay_verified=False,native_loading_verified=False,native_finish_status_is_emulated=True,shared_game_copy_modified=False,
        runtime_sha256=sha(runtime),build_result_sha256=sha(build_path),compiled_source_sha256=build['source_sha256'],test_source_sha256=source_hashes,settings_abi=56,plan_island_size=40,snapshot_size=5192,template_count=444,
        fixture_root=str(fixture),fixture_inputs_unchanged=True,temporary_scenes_cleaned=True,supported_world_sizes_tested=sorted(validated_dims),unsupported_4096_rejected_before_publication=True,expanded_engine_not_installed_in_python_host=True,far_half_geometry_verified=all(any(p['x']>=1024 or p['y']>=1024 for p in row['plan_rows']) for row in huge),
        staged_scene_count=len(staged),exact_head_and_cached_preview_link_scenes=len(staged),all_ship_tuple_cases=sum(c['ship_count'] for c in staged),strict51224_rejected_lenient51224_staged=True,
        balanced_unanchored_climate_counts_verified=True,full_settings_seed_and_all40byte_rows_retained=True,stale_worldSize_rejected_before_publication=True,
        rejected_cases=rejects,cases=staged,elapsed_seconds=time.perf_counter()-started,
        limitations=['Python-host full-DLL test; no native game loading, navigation, minimap, UI or save/reload execution.','Ship initial scene positions are checked; this is not an observed game save or later fleet/cash claim.','Cancellation status is supplied by the test host; native success/commit has not been exercised.'])
    (PACKAGE/'developer/huge_world/huge_runtime_results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['passed','runtime_sha256','staged_scene_count','all_ship_tuple_cases','supported_world_sizes_tested','game_executed']},indent=2))
if __name__=='__main__':main()
