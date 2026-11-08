"""Inspect/load the exact compiled runtime in Python only; no Anno process or UI."""
from pathlib import Path
import ctypes as C
import hashlib
import json
import itertools
import sys
HERE=Path(__file__).resolve().parent
WORK=HERE.parent
sys.path.insert(0,str(WORK/'_tools'))
import pefile
def main():
    dllpath=HERE/'AnnoWorldSettings.dll'
    metadata=json.loads((HERE/'build_result.json').read_bytes())
    digest=hashlib.sha256(dllpath.read_bytes()).hexdigest()
    assert digest==metadata['sha256']
    for name,expected in metadata['source_sha256'].items():
        assert hashlib.sha256((WORK/name).read_bytes()).hexdigest()==expected,name
    pe=pefile.PE(str(dllpath))
    assert pe.FILE_HEADER.Machine==0x8664 and pe.OPTIONAL_HEADER.Magic==0x20b
    exports={e.name.decode() for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name and not e.forwarder}
    required={'WorldSettingsEnginePatchStatus','WorldSettingsBeforeStart','WorldSettingsBeforeDirectStart','WorldSettingsAfterProfiles',
              'WorldSettingsLoadAiModule','WorldSettingsInstallTestHooks','WorldSettingsCreateScene',
              'WorldSettingsConfigureDevelopmentRoot','WorldSettingsCopyAIProfileError','WorldSettingsCopyAILoaderError',
              'WorldSettingsAIProfileStatus','WorldSettingsBeginNativeWorldStart',
              'WorldSettingsEndNativeWorldStart','WorldSettingsBindAIProfileWorld',
              'WorldSettingsStagePreviewScene','WorldSettingsPreviewSnapshotSize','WorldSettingsCopyPreviewSnapshot'}
    assert required<=exports
    lib=C.CDLL(str(dllpath))
    assert lib.WorldSettingsSettingsSize()==56
    status=lib.WorldSettingsAIProfileStatus;status.argtypes=[C.c_void_p];status.restype=C.c_uint32
    assert status(None)==0 and status(0x1234)==0
    after=lib.WorldSettingsAfterProfiles;after.argtypes=[C.c_void_p]
    assert after(None)==1 and status(None)==0 # unarmed callback cannot claim verification
    begin=lib.WorldSettingsBeginNativeWorldStart;begin.argtypes=[];begin.restype=C.c_uint32
    end=lib.WorldSettingsEndNativeWorldStart;end.argtypes=[C.c_uint32,C.c_int]
    token=begin();assert token and status(None)==0
    assert end(token,1)==1 and status(None)==0 # unrelated native load remains unverified
    token=begin();assert token and end(token,0)==0 and status(None)==0
    class Settings(C.Structure):
        _fields_=[('size',C.c_uint32),('difficulty',C.c_int32),('islandSize',C.c_int32),
                  ('islandCount',C.c_int32),('spacing',C.c_int32),('aiCount',C.c_int32),
                  ('cultures',C.c_uint32),('factions',C.c_uint32),
                  ('startingMoney',C.c_int32),('startingFleet',C.c_int32),('aiDifficulty',C.c_int32),
                  ('plantFertility',C.c_int32),('mineralFertility',C.c_int32),('worldSize',C.c_int32)]
    validate=lib.WorldSettingsValidateSettings;validate.argtypes=[C.POINTER(Settings),C.c_void_p,C.c_uint32]
    error=C.create_string_buffer(512)
    valid_cases=0
    for difficulty,money,fleet,aggression,factions in itertools.product(range(3),[10000,30000,50000,80000,100000],range(3),range(4),range(4)):
        s=Settings(56,difficulty,3,24,16,0,255,factions,money,fleet,aggression,1,1,1024)
        assert validate(C.byref(s),error,len(error))==1
        valid_cases+=1
    rejects=[('aiCount',1),('aiCount',4),('size',32),('size',44),('factions',4),
             ('startingMoney',0),('startingMoney',25000),('startingMoney',100001),
             ('startingFleet',-1),('startingFleet',3),('aiDifficulty',-1),('aiDifficulty',4),
             ('plantFertility',-1),('plantFertility',4),('mineralFertility',-1),('mineralFertility',4),('worldSize',0),('worldSize',768),('worldSize',4096),('islandSize',5)]
    for field,value in rejects:
        s=Settings(56,1,3,24,16,0,255,3,30000,0,1,1,1,1024);setattr(s,field,value)
        assert validate(C.byref(s),error,len(error))==0 and error.value
    # The same seed must produce the same islands regardless of the stock
    # difficulty, starting budget/fleet, or war policy. Every plan is separately
    # checked by the native planner's geometry and resource preflight.
    plan=lib.WorldSettingsBuildPlan;plan.argtypes=[C.POINTER(Settings),C.c_uint32,C.c_void_p,C.c_uint32]
    class Island(C.Structure):
        _fields_=[(name,C.c_uint32) for name in ['id','x','y','width','height','templateIndex','cropMask','mineralMask','cultures','climate']]
    get=lib.WorldSettingsPlanIsland;get.argtypes=[C.c_uint32,C.POINTER(Island)]
    reference=None;plans=0
    for difficulty,money,fleet,aggression in itertools.product(range(3),[10000,30000,50000,80000,100000],range(3),range(4)):
        s=Settings(56,difficulty,3,24,16,0,255,3,money,fleet,aggression,1,1,1024)
        assert plan(C.byref(s),903,error,len(error))==1,error.value
        count=lib.WorldSettingsPlanCount();assert count==24
        rows=[]
        for i in range(count):
            island=Island();assert get(i,C.byref(island))==1
            rows.append(bytes(island))
        if reference is None:reference=rows
        assert rows==reference,'A starting option changed island generation'
        plans+=1
    result=dict(scope=__doc__,runtime_sha256=digest,abi_size=56,required_exports=sorted(required),
                exact_build_sources=True,valid_settings_cases=valid_cases,rejected_settings_cases=len(rejects),
                independent_plan_cases=plans,game_executed=False,
                ai_profile_status_initial=0,unarmed_profile_callback_unverified=True,
                native_attempt_unarmed_success_and_failure_preserved=True,
                hooks_installed=False,positive_AI_blocked_until_verified_copy_activation=True)
    (HERE/'runtime_verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
