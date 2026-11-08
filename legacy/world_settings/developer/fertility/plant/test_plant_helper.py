"""Exercise the compiled production plant helper, not a mirrored algorithm.

Independent properties: climate compatibility, essential coverage, no unrelated
plan mutations, deterministic modes, density nesting and fail-closed atomicity.
No game is run. The C fixture supplies island plans to the production include.
"""
from pathlib import Path
import ctypes as C
import hashlib,json,sys
HERE=Path(__file__).resolve().parent;GAME=next(p for p in HERE.parents if (p/'Anno1503.exe').is_file())
PACKAGE=next((p for p in HERE.parents if (p/'developer/source/engine_audit/audit.py').is_file()),GAME/'WorldSettings_Work/anno1503_food_world_dev5')
DLL=HERE/'_build/plant_fixture.dll'
class Plan(C.Structure):
    _fields_=[(name,C.c_uint32) for name in ['id','x','y','width','height','templateIndex','cropMask','mineralMask','cultures','climate']]
assert C.sizeof(Plan)==40
lib=C.CDLL(str(DLL));lib.PlantFixture.argtypes=[C.c_int,C.c_uint32,C.c_uint32,C.POINTER(C.c_uint32),C.POINTER(Plan),C.c_char_p,C.c_uint32];lib.PlantFixture.restype=C.c_int
MASKS=[0x18000,0xf009,0xf949,0xf06b,0xf6b9,0xf04d]
OPTIONAL=0xff6
def call(mode,seed,climates,count=None):
    count=len(climates) if count is None else count
    inp=(C.c_uint32*max(len(climates),128))(*climates);out=(Plan*128)();err=C.create_string_buffer(512)
    ok=lib.PlantFixture(mode,seed,count,inp,out,err,len(err))
    rows=[{name:getattr(p,name) for name,_ in Plan._fields_} for p in out[:min(count,128)]]
    return ok,rows,err.value.decode()
def main():
    cases=0;strict_levels=0;observed_mixed=False;example=None
    for seed in [0,1,2,3,17,42,0x15032026,0xffffffff]+list(range(101,117)):
        for count in [6,8,16,24,64,128]:
            climates=[i%6 for i in range(count)];all_modes=[]
            for mode in range(4):
                ok,rows,error=call(mode,seed,climates);assert ok and not error,(mode,seed,count,error)
                assert call(mode,seed,climates)==(ok,rows,error)
                union=0
                for i,row in enumerate(rows):
                    expected=dict(id=i,x=i*8,y=8,width=64,height=64,templateIndex=100+i,mineralMask=0x5a5a0000+i,cultures=0xff,climate=climates[i])
                    assert {k:v for k,v in row.items() if k!='cropMask'}==expected
                    mask=row['cropMask'];assert not(mask&~MASKS[climates[i]])
                    assert (mask&~OPTIONAL)==(MASKS[climates[i]]&~OPTIONAL)
                    if mode==0:assert mask==MASKS[climates[i]]
                    union|=mask
                assert union==0x1ffff
                all_modes.append(rows);cases+=1
            very,medium,low,mixed=all_modes
            for v,m,l in zip(very,medium,low):assert not(l['cropMask']&~m['cropMask']) and not(m['cropMask']&~v['cropMask'])
            totals=[sum((row['cropMask']&OPTIONAL).bit_count() for row in rows) for rows in all_modes]
            assert totals[0]>=totals[1]>=totals[2]
            if count>=24:
                assert totals[0]>totals[1]>totals[2],(seed,count,totals)
                strict_levels+=1
                observed_mixed|=all(mixed!=rows for rows in all_modes[:3])
            if seed==42 and count==24:example=dict(seed=seed,islands=count,optional_crop_totals=dict(zip(['very','medium','low','mixed'],totals)),masks_by_mode=[[hex(row['cropMask']) for row in rows] for rows in all_modes])
    assert observed_mixed
    invalid=[]
    for mode,count,climates in [(-1,6,list(range(6))),(4,6,list(range(6))),(1,0,[]),(1,129,[0]*128),(1,6,[0,1,2,3,4,6]),(1,6,[1]*6)]:
        ok,rows,error=call(mode,1,climates,count);assert not ok and error
        assert all(row['cropMask']==0xdeadbeef for row in rows)
        invalid.append(dict(mode=mode,count=count,climates=climates[:8],error=error))
    src=PACKAGE/'developer/source/engine_resume/ai_food/experiment_runtime/plant_fertility.inc'
    report=dict(scope=__doc__,passed=True,compiled_production_helper_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),fixture_dll_sha256=hashlib.sha256(DLL.read_bytes()).hexdigest(),successful_mode_cases=cases,identical_repeats=cases,nesting_comparisons=cases//4,strict_density_comparisons=strict_levels,invalid_atomic_cases=invalid,mixed_distinct_from_uniform=True,example=example,game_executed=False)
    (HERE/'plant_helper_results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['invalid_atomic_cases','scope']},indent=2))
if __name__=='__main__':main()
