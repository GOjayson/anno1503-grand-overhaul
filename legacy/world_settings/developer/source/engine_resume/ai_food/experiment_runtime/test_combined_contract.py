"""Compile private combined UI/backend ABI; no game UI or process hooks run.

This intentionally omits the hook installer and is NOT a playable runtime.
The native loader gate stays false, so positive AI cannot pass configuration.
"""
from pathlib import Path
import ctypes as C,hashlib,itertools,json,os,struct,subprocess,sys
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[2]
out=HERE/'_build';out.mkdir(exist_ok=True);(out/'tmp').mkdir(exist_ok=True)
env=dict(os.environ,ZIG_GLOBAL_CACHE_DIR=str(out/'global-cache'),ZIG_LOCAL_CACHE_DIR=str(out/'local-cache'),TEMP=str(out/'tmp'),TMP=str(out/'tmp'))
sources=[HERE/'WorldSettings.c',HERE/'world_backend.c',HERE/'world_ai.c',WORK/'world_factory.c',WORK/'engine_resume/ai_loader/ai_loader.c',WORK/'engine_resume/route_coverage/selection.c']
command=[str(WORK/'_tools/ziglang/zig.exe'),'cc','-target','x86_64-windows-gnu','-shared','-O2','-Wall','-Wextra','-Werror','-o',str(out/'CombinedContractOnly.dll'),*[str(p) for p in sources],'-lbcrypt','-luser32','-lgdi32','-lkernel32']
before={str(p.relative_to(WORK)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
subprocess.run(command,check=True,env=env)
assert all(hashlib.sha256((WORK/n).read_bytes()).hexdigest()==h for n,h in before.items())
lib=C.CDLL(str(out/'CombinedContractOnly.dll'))
status=lib.WorldSettingsAIProfileStatus;status.argtypes=[C.c_void_p];status.restype=C.c_uint32
assert status(None)==0
after=lib.WorldSettingsAfterProfiles;after.argtypes=[C.c_void_p]
assert after(None)==1 and status(None)==0
start_body=(HERE/'WorldSettings.c').read_text().split('static void start(DialogState*d){',1)[1].split('static LRESULT',1)[0]
assert start_body.index('WorldSettingsAIProfileAttemptFinished(0);')<start_body.index('if(!collect(d))return;')
class Settings(C.Structure):
 _fields_=[('size',C.c_uint32),('difficulty',C.c_int32),('islandSize',C.c_int32),('islandCount',C.c_int32),('spacing',C.c_int32),('aiCount',C.c_int32),('cultures',C.c_uint32),('factions',C.c_uint32)]
assert C.sizeof(Settings)==lib.WorldSettingsSettingsSize()==32
validate=lib.WorldSettingsValidateSettings;validate.argtypes=[C.POINTER(Settings),C.c_void_p,C.c_uint32]
plan=lib.WorldSettingsBuildPlan;plan.argtypes=[C.POINTER(Settings),C.c_uint32,C.c_void_p,C.c_uint32]
err=C.create_string_buffer(512);rows=[]
for difficulty,size,factions in itertools.product(range(3),range(4),range(4)):
 s=Settings(32,difficulty,size,12 if size==2 else 24,16,0,255,factions)
 assert validate(C.byref(s),err,len(err))==1,err.value
 assert plan(C.byref(s),903,err,len(err))==1,err.value
 assert lib.WorldSettingsPlanCount()==s.islandCount
 rows.append(dict(difficulty=difficulty,island_size=size,island_count=s.islandCount,factions=factions,ai=0,valid=True))
rejects=[]
for field,value in [('size',28),('size',36),('difficulty',3),('islandSize',4),('aiCount',-1),('aiCount',1),('aiCount',2),('aiCount',3),('aiCount',4),('factions',4),('cultures',256)]:
 s=Settings(32,1,3,24,16,0,255,3);setattr(s,field,value)
 assert not validate(C.byref(s),err,len(err)) and err.value
 rejects.append(dict(field=field,value=value,error=err.value.decode()))
sys.path.insert(0,str(WORK/'world_data'))
from scene_catalogue import chunks
def fields(payload):
 at=8
 while at<len(payload):
  assert len(payload)-at>=8
  n=struct.unpack_from('<H',payload,at+6)[0];h=8
  if n>=0xff00:h=10;n=((n&255)<<16)|struct.unpack_from('<H',payload,at+8)[0]
  assert n<=len(payload)-at-h
  yield payload[at:at+6].rstrip(b'\0'),at+h,payload[at+h:at+h+n]
  at+=h+n
stage=lib.WorldSettingsStageScene;stage.argtypes=[C.POINTER(Settings),C.c_char_p,C.c_uint32,C.c_void_p,C.c_uint32,C.c_void_p,C.c_uint32]
sources=json.loads((HERE.parent/'stock_profile_inputs.json').read_text())['sources'];stages=[];copy=WORK/'game_copy';destination=C.create_string_buffer(260)
for difficulty,factions in itertools.product(range(3),range(4)):
 s=Settings(32,difficulty,0,24,16,0,255,factions);destination.value=b''
 try:
  assert stage(C.byref(s),str(copy).encode('mbcs'),903,destination,len(destination),err,len(err))==1,err.value
  generated=Path(destination.value.decode('mbcs'));assert generated.is_relative_to(copy/'Scenes')
  data=generated.read_bytes();source=(WORK.parent/sources[difficulty]['path']).read_bytes()
  originals=[c for c in chunks(source,32,len(source)) if c.tag=='SPIELER'];actual=[c for c in chunks(data,32,len(data)) if c.tag=='SPIELER']
  types={struct.unpack_from('<I',c.payload,4)[0]:struct.unpack_from('<H',c.payload,16)[0] for c in originals if c.payload[8:14]==b'HEAD\0\0'}
  wanted=[];suspended=0
  for c in originals:
   p=c.payload;pid=struct.unpack_from('<I',p,4)[0];typ=types[pid]
   if typ in [15,16] and not factions&(1 if typ==15 else 2):continue
   expected=bytearray(p)
   for tag,start,value in fields(p):
    if tag==b'COMP' and struct.unpack_from('<I',value)[0]==12:
     text=value[8:];assert text.count(b'SUSPEND=0\0')==1
     relative=8+text.index(b'SUSPEND=0\0')+8
     expected[start+relative]=ord('1');suspended+=1
   wanted.append(bytes(expected))
  assert [c.payload for c in actual]==wanted
  assert suspended==(3 if difficulty==0 else 4)
  stages.append(dict(difficulty=difficulty,factions=factions,ordinary_cpu_initially_suspended=suspended,other_player_bytes_exact=True))
 finally:
  lib.WorldSettingsFinishAttempt(0)
  if destination.value:assert not Path(destination.value.decode('mbcs')).exists()
report=dict(scope=__doc__,actual_game_runs=0,playable_runtime=False,abi_size=32,compiled_sha256=hashlib.sha256((out/'CombinedContractOnly.dll').read_bytes()).hexdigest(),source_sha256=before,ai_profile_status_initial=0,unarmed_profile_callback_unverified=True,new_start_reset_before_collect_source_check=True,valid_world_cases=rows,rejected_settings=rejects,staged_player_preservation_cases=stages)
(HERE/'combined_contract_results.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
print(json.dumps(dict(valid_world_cases=len(rows),rejected_settings=len(rejects),staged_player_preservation_cases=len(stages),abi=32,playable_runtime=False)))
