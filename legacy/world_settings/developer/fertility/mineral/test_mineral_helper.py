"""Compiled production mineral policy against synthetic plans/template capacities.

This checks pure helper behavior; it does not execute a full native loader,
change any game files, prove mineral mining, or launch Anno.
"""
from pathlib import Path
import ctypes as C
import hashlib
import itertools
import json

HERE=Path(__file__).resolve().parent
ROOT=next(p for p in HERE.parents if (p/'Anno1503.exe').is_file() and (p/'WorldSettings_Work/_tools').is_dir())
PACKAGE=next((p for p in HERE.parents if (p/'world_patch.json').is_file()),ROOT/'WorldSettings_Work/anno1503_food_world_dev5')
SOURCE=PACKAGE/'developer/source/engine_resume/ai_food/experiment_runtime/mineral_fertility.inc'
class Island(C.Structure):
    _fields_=[(n,C.c_uint32) for n in ['id','x','y','width','height','templateIndex','cropMask','mineralMask','cultures','climate']]
class Template(C.Structure):
    _fields_=[('climate',C.c_uint32),('oreSlots',C.c_uint32)]
lib=C.CDLL(str(HERE/'_build/mineral_helper_fixture.dll'))
lib.MineralFixture.argtypes=[C.c_int32,C.c_uint32,C.c_uint32,C.POINTER(Island),C.POINTER(Template),C.POINTER(Island)]
lib.MineralFixture.restype=C.c_int
templates=(Template*128)()
support=[0,5,37,1,3,11]
cases=0
strict_examples=[]
def invoke(mode,seed,rows):
    inputs=(Island*len(rows))(*rows);outputs=(Island*len(rows))()
    result=lib.MineralFixture(mode,seed,len(rows),inputs,templates,outputs)
    return result,list(outputs)
for climate,capacity,seed in itertools.product(range(6),range(6),range(64)):
    supported=support[climate]
    for mandatory in range(64):
        if mandatory&~supported or mandatory.bit_count()>capacity:continue
        templates[0]=Template(climate,capacity)
        p=Island(0,8,16,128,128,0,0xf009,mandatory,17,climate)
        values=[]
        for mode in range(4):
            ok,rows=invoke(mode,seed,[p]);assert ok
            current=rows[0];mask=current.mineralMask
            assert mask&mandatory==mandatory and not(mask&~supported)
            assert mask.bit_count()<=capacity
            for field,_ in Island._fields_:
                if field!='mineralMask':assert getattr(current,field)==getattr(p,field)
            ok2,repeat=invoke(mode,seed,[p]);assert ok2 and bytes(repeat[0])==bytes(current)
            values.append(mask);cases+=1
        very,medium,low,mixed=values
        assert low==mandatory and low&~medium==0 and medium&~very==0
        assert very.bit_count()==min(capacity,supported.bit_count())
        assert mixed in [very,medium,low]
        if low!=medium and medium!=very and len(strict_examples)<6:
            strict_examples.append(dict(climate=climate,capacity=capacity,seed=seed,masks=values))
# Explicit one-slot regression: Medium must never substitute a later optional
# good which fell outside the Very set because an earlier good used capacity.
for climate,seed in itertools.product([1,2,4,5],range(1024)):
    templates[0]=Template(climate,1)
    p=Island(0,8,16,128,128,0,0xf009,0,0,climate)
    very=invoke(0,seed,[p])[1][0].mineralMask
    medium=invoke(1,seed,[p])[1][0].mineralMask
    assert medium==0 or medium==very
    cases+=1
bad=[]
templates[0]=Template(2,3)
for mode,rows,label in [
    (-1,[Island(0,8,8,128,128,0,0,0,0,2)],'negative mode'),
    (4,[Island(0,8,8,128,128,0,0,0,0,2)],'mode above Mixed'),
    (1,[],'empty plan'),
    (1,[Island(0,8,8,128,128,0,0,64,0,2)],'duplicate iron index6 forbidden'),
    (1,[Island(0,8,8,128,128,0,0,16,0,2)],'unused native index4 forbidden'),
    (1,[Island(0,8,8,128,128,0,0,0,0,1)],'template climate mismatch'),
    (1,[Island(0,8,8,128,128,0,0,0,0,2),Island(1,8,8,128,128,129,0,0,0,2)],'later invalid island leaves entire plan unchanged'),
]:
    result,after=invoke(mode,7,rows)
    assert not result and [bytes(p) for p in after]==[bytes(p) for p in rows]
    bad.append(label)
report=dict(scope=__doc__,source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    compiled_fixture_sha256=hashlib.sha256((HERE/'_build/mineral_helper_fixture.dll').read_bytes()).hexdigest(),
    compiled_cases=cases,rejection_cases=bad,nested_low_medium_very=True,
    deterministic=True,geometry_and_other_fields_unchanged=True,strict_mode_examples=strict_examples,
    actual_game_run=False,passed=True)
(HERE/'mineral_helper_results.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
