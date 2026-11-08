"""Execute the production layout helper in an isolated Windows-native fixture.

Template inputs come from the immutable dev5 runtime's real exported plans.
Only fixture memory is changed. No Anno process, native loader, scene staging,
game files, backup or old package is modified. Full-runtime and live-game
preview tests are separate from this bounded geometry proof.
"""
from pathlib import Path
import ctypes as C
import argparse
import hashlib
import json
import math
import statistics
import time

HERE=Path(__file__).resolve().parent
PACKAGE=HERE.parents[2]
WORK=PACKAGE.parent
SOURCE=PACKAGE/'developer/source/engine_resume/ai_food/experiment_runtime'
FIELDS=['id','x','y','width','height','templateIndex','cropMask','mineralMask','cultures','climate']


class Island(C.Structure):
    _fields_=[(name,C.c_uint32) for name in FIELDS]


class Settings(C.Structure):
    _fields_=[('size',C.c_uint32),('difficulty',C.c_int32),('islandSize',C.c_int32),
             ('islandCount',C.c_int32),('spacing',C.c_int32),('aiCount',C.c_int32),
             ('cultures',C.c_uint32),('factions',C.c_uint32),('startingMoney',C.c_int32),
             ('startingFleet',C.c_int32),('aiDifficulty',C.c_int32),
             ('plantFertility',C.c_int32),('mineralFertility',C.c_int32)]


RESERVES=[(320,230,49,49),(387,452,49,49),(426,398,49,49),
          (532,526,49,49),(542,411,49,49),(581,410,49,49),(668,510,49,49)]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(array):return [{name:int(getattr(item,name)) for name in FIELDS} for item in array]
def raw(array):return C.string_at(C.addressof(array),C.sizeof(array))
def separated(a,b,gap):
    return (a['x']+a['width']+gap<=b['x'] or b['x']+b['width']+gap<=a['x'] or
            a['y']+a['height']+gap<=b['y'] or b['y']+b['height']+gap<=a['y'])


def validate(before,after,spacing):
    assert len(before)==len(after)
    for index,(old,row) in enumerate(zip(before,after)):
        assert row['id']==index
        assert all(row[key]==old[key] for key in FIELDS if key not in ['x','y','id'])
        assert row['x']%8==row['y']%8==0
        assert row['x']>=spacing and row['y']>=spacing
        assert row['x']+row['width']+spacing<=1024
        assert row['y']+row['height']+spacing<=1024
        for previous in after[:index]:assert separated(row,previous,spacing)
        for x,y,w,h in RESERVES:
            assert separated(row,dict(x=x,y=y,width=w,height=h),spacing)


def distance(row,x,y):
    dx=max(row['x']-x,0,x-row['x']-row['width'])
    dy=max(row['y']-y,0,y-row['y']-row['height'])
    return math.sqrt(dx*dx+dy*dy)


def metrics(world):
    total=sum(r['width']*r['height'] for r in world)
    centers=[(r['x']+r['width']/2,r['y']+r['height']/2) for r in world]
    quadrants=[sum((x>=512)==bool(q&1) and (y>=512)==bool(q&2) for x,y in centers) for q in range(4)]
    halves=[]
    for axis,extent in [('x','width'),('y','height')]:
        low=sum(max(0,min(r[axis]+r[extent],512)-r[axis])*r['height' if axis=='x' else 'width'] for r in world)
        halves.extend([low/total,1-low/total])
    nearest=[min(distance(r,x,y) for r in world) for y in range(16,1024,32) for x in range(16,1024,32)]
    return dict(bounding_width=max(r['x']+r['width'] for r in world)-min(r['x'] for r in world),
                bounding_height=max(r['y']+r['height'] for r in world)-min(r['y'] for r in world),
                center_quadrant_counts=quadrants,land_share_in_four_halves=halves,
                maximum_sampled_ocean_distance_to_land=max(nearest),
                mean_sampled_ocean_distance_to_land=statistics.mean(nearest),
                map_samples_with_land_within128=sum(d<=128 for d in nearest)/len(nearest))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed-count',type=int,default=32)
    args=parser.parse_args();assert 1<=args.seed_count<=128
    old=WORK/'anno1503_food_world_dev5/developer/source/runtime_dev3/AnnoWorldSettings.dll'
    old_hash=sha(old)
    assert old_hash=='6e0f27734272e88590fa00556af2ae47cd14ea502e7af36fd051b3ccda357829'
    native=C.CDLL(str(HERE/'_build/layout_fixture.dll'))
    for name in ['LayoutPack','LayoutCompact']:getattr(native,name).restype=C.c_int
    native.LayoutPack.argtypes=[C.POINTER(Island),C.c_uint32,C.c_uint32,C.c_uint32,C.POINTER(Island)]
    native.LayoutCompact.argtypes=[C.POINTER(Island),C.c_uint32,C.c_uint32,C.POINTER(Island)]
    baseline=C.CDLL(str(old))
    baseline.WorldSettingsBuildPlan.argtypes=[C.POINTER(Settings),C.c_uint32,C.c_void_p,C.c_uint32]
    baseline.WorldSettingsPlanIsland.argtypes=[C.c_uint32,C.POINTER(Island)]
    cases=[];rejected=[];diverse=0;count_repeat=0
    scenarios=[dict(count=count,spacing=spacing,island_size=3,cultures=255,factions=3)
               for count,spacing in [(16,0),(20,0),(24,0),(24,16),(24,32),(32,0),(32,16),(40,0),(48,0),(64,0)]]
    scenarios += [dict(count=24,spacing=spacing,island_size=size,cultures=255,factions=3)
                  for size in [0,1,2] for spacing in [0,16]]
    scenarios += [dict(count=count,spacing=0,island_size=3,cultures=0,factions=0)
                  for count in [6,8,10,12]]
    for scenario in scenarios:
        count=scenario['count'];spacing=scenario['spacing']
        for seed_index in range(args.seed_count):
            seed=(0x15032611+seed_index*0x9e3779b9)&0xffffffff
            settings=Settings(52,1,scenario['island_size'],count,spacing,0,scenario['cultures'],scenario['factions'],30000,0,1,1,1)
            error=C.create_string_buffer(512)
            if not baseline.WorldSettingsBuildPlan(C.byref(settings),seed,error,len(error)):
                rejected.append(dict(**scenario,seed=seed,error=error.value.decode()));continue
            source=(Island*count)()
            assert baseline.WorldSettingsPlanCount()==count
            for i in range(count):assert baseline.WorldSettingsPlanIsland(i,C.byref(source[i]))
            compact=(Island*count)();balanced=(Island*count)();repeat=(Island*count)();other=(Island*count)()
            assert native.LayoutCompact(source,count,spacing,compact)
            assert raw(source)==raw(compact),'Compact feasibility baseline differs from the immutable runtime'
            start=time.perf_counter();assert native.LayoutPack(source,count,spacing,seed,balanced)
            elapsed=time.perf_counter()-start
            assert native.LayoutPack(source,count,spacing,seed,repeat)
            assert raw(repeat)==raw(balanced),'Identical seed/inputs changed layout'
            assert native.LayoutPack(source,count,spacing,seed^0xa5a5a5a5,other)
            diverse+=raw(other)!=raw(balanced);count_repeat+=1
            before=rows(source);after=rows(balanced);validate(before,after,spacing)
            before_metrics=metrics(before);after_metrics=metrics(after)
            if count==24:
                assert min(after_metrics['center_quadrant_counts'])>=2,after_metrics
                assert min(after_metrics['land_share_in_four_halves'])>=0.20,after_metrics
                assert min(after_metrics['bounding_width'],after_metrics['bounding_height'])>=864,after_metrics
                assert after_metrics['maximum_sampled_ocean_distance_to_land']<=280,after_metrics
            cases.append(dict(**scenario,seed=seed,elapsed_seconds=elapsed,
                              before=before_metrics,after=after_metrics,
                              before_layout_sha256=hashlib.sha256(raw(source)).hexdigest(),
                              after_layout_sha256=hashlib.sha256(raw(balanced)).hexdigest()))
    assert cases and diverse==count_repeat
    invalid=[]
    for count,spacing,width,height in [(0,0,64,64),(129,0,64,64),(1,600,64,64),(1,0,0,64),(1,0,2048,64),(1,0,0xffffffff,64)]:
        data=(Island*128)();out=(Island*128)();data[0].width=width;data[0].height=height
        assert not native.LayoutPack(data,count,spacing,1,out)
        invalid.append(dict(count=count,spacing=spacing,width=width,height=height))
    assert sha(old)==old_hash
    typical=[r['elapsed_seconds'] for r in cases if r['count']==24]
    result=dict(scope=__doc__,passed=True,helper_sha256=sha(SOURCE/'balanced_layout.inc'),
                fixture_source_sha256=sha(HERE/'layout_fixture.c'),
                fixture_dll_sha256=sha(HERE/'_build/layout_fixture.dll'),
                test_source_sha256=sha(Path(__file__)),baseline_runtime_sha256=old_hash,
                native_fixture_cases=len(cases),exact_repeat_cases=count_repeat,
                seed_count_per_scenario=args.seed_count,
                changed_seed_layouts=diverse,rejected_geometric_inputs=invalid,
                previous_runtime_infeasible_settings=rejected,
                preserved_constraints=['8-tile native grid','minimum requested spacing','1024 bounds',
                                       'seven stock ship reserves','template/resource/culture fields',
                                       'global template RNG unchanged'],
                quality_assertions_24_islands=dict(minimum_centers_in_each_quadrant=2,
                    minimum_land_share_per_half=0.20,minimum_bounding_extent_each_axis=864,
                    maximum_32tile_grid_sample_distance_to_land=280),
                typical24_native_timing=dict(cases=len(typical),median_seconds=statistics.median(typical),
                    maximum_seconds=max(typical),scope='Native isolated helper only; does not include UI/scene/engine loading'),
                cases=cases,game_executed=False,game_or_copy_mutated=False)
    (HERE/'layout_results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['passed','native_fixture_cases','exact_repeat_cases','changed_seed_layouts','typical24_native_timing']},indent=2))


if __name__=='__main__':main()
