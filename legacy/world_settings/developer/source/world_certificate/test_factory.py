"""Tests of the compiled world_factory.c boundary. All factory/backend/destructor
boundaries are mocks. Does not load a game scene, invoke a UI or touch game files.
"""
from pathlib import Path
import ctypes as C,json,hashlib
HERE=Path(__file__).resolve().parent
build=json.loads((HERE/'factory_build.json').read_text())
for key,path in [('source_sha256',HERE.parent/'world_factory.c'),('fixture_sha256',HERE/'factory_fixture.c'),('dll_sha256',HERE/'FactoryFixture.dll')]:
 assert hashlib.sha256(path.read_bytes()).hexdigest()==build[key], 'Rebuild factory fixture before testing modified inputs'
lib=C.CDLL(str(HERE/'FactoryFixture.dll'))
lib.FactoryFixtureConfigure.argtypes=[C.c_int,C.c_int,C.c_int32,C.c_int,C.c_int,C.c_int]
lib.FactoryFixtureStat.argtypes=[C.c_uint32];lib.FactoryFixtureStat.restype=C.c_uint64
for name in ['FactoryFixtureOriginal','FactoryFixtureObject','FactoryFixturePath','WorldSettingsLastFactoryError']:
 getattr(lib,name).restype=C.c_void_p
lib.WorldSettingsCreateScene.argtypes=[C.c_int32,C.c_void_p,C.c_void_p,C.POINTER(C.c_void_p),C.c_void_p,C.c_uint32,C.c_uint32,C.c_void_p]
lib.WorldSettingsCreateScene.restype=C.c_int32
lib.WorldSettingsCopyFactoryError.argtypes=[C.c_void_p];lib.WorldSettingsCopyFactoryError.restype=C.c_uint32
lib.FactoryFixtureEnableReporter.argtypes=[];lib.FactoryFixtureEnableReporter.restype=None
lib.WorldSettingsSetFailureReporter.argtypes=[C.c_void_p];lib.WorldSettingsSetFailureReporter.restype=None
FAIL=C.c_int32(0x80004005).value;POINTER=C.c_int32(0x80004003).value
NATIVE_FAIL=C.c_int32(0x80070057).value
original=lib.FactoryFixtureOriginal();obj=lib.FactoryFixtureObject();prepared=lib.FactoryFixturePath()
path=C.create_string_buffer(b'original scene path');pathptr=C.addressof(path);save=0x123456789abcdef;metadata=0x76543210fedcba9
results=[]
def stats():return [lib.FactoryFixtureStat(i) for i in range(64)]
def error():return C.string_at(lib.WorldSettingsLastFactoryError()).decode()
def config(active=1,preparedState=2,result=0,hasObject=1,validation=1,message=0):lib.FactoryFixtureConfigure(active,preparedState,result,hasObject,validation,message)
def invoke(mode=0,out=True,native=original,index=0xf1e2d3c4,flags=0xaabbccdd):
 output=C.c_void_p(0x1122334455667788);addr=C.addressof(output)
 result=lib.WorldSettingsCreateScene(mode,pathptr,save,C.byref(output) if out else None,metadata,index,flags,native)
 return result,output.value,addr,stats()
def record(name,result,values):results.append({'case':name,'hresult':hex(result&0xffffffff),'native_calls':values[2],'validator_calls':values[3],'release_calls':values[4],'finish_calls':values[5],'reporter_calls':values[60],'error':error(),'events':values[20:20+values[19]]})
# Inactive means literal seven-argument forwarding, even negative modes/results.
for mode in [0,1,-77,0x7fffffff]:
 for result in [0,1,NATIVE_FAIL]:
  config(active=0,result=result);ret,out,addr,s=invoke(mode)
  assert ret==result and out==obj
  assert s[:7]==[1,0,1,0,0,0,0]
  assert s[7:14]==[mode&0xffffffff,pathptr,save,addr,metadata,0xf1e2d3c4,0xaabbccdd]
  assert s[16]==0x1122334455667788 and error()==''
  record('inactive exact forwarding mode'+str(mode)+' result'+str(result),ret,s)
# Active substitutes only the prepared path and owns validation/discard.
for result in [0,1,0x12345678]:
 config(result=result);ret,out,addr,s=invoke()
 assert ret==result and out==obj
 assert s[:7]==[1,1,1,1,0,1,1]
 assert s[7:14]==[0,prepared,save,addr,metadata,0xf1e2d3c4,0xaabbccdd]
 assert s[14]==obj and s[16]==0 and s[17]==obj and s[20:25]==[1,2,3,4,6] and error()==''
 record('active full forwarding success'+str(result),ret,s)
# Every pre-factory active error clears caller output and finishes exactly once.
for active in [0,1]:
 for invalid in ['native','out','both']:
  config(active=active);ret,out,addr,s=invoke(out=invalid not in ['out','both'],native=None if invalid in ['native','both'] else original)
  assert ret==POINTER and s[2:5]==[0,0,0] and s[1]==0 and s[5]==active and s[6]==0
  if invalid=='native':assert out is None
  assert 'boundary' in error();record('invalid '+invalid+' active'+str(active),ret,s)
for mode in [1,2,-1]:
 config();ret,out,addr,s=invoke(mode)
 assert ret==FAIL and out is None and s[:7]==[1,1,0,0,0,1,0]
 assert s[20:23]==[1,2,6];record('active unsupported mode'+str(mode),ret,s)
for state in [0,1]:
 config(preparedState=state);ret,out,addr,s=invoke()
 assert ret==FAIL and out is None and s[:7]==[1,1,0,0,0,1,0]
 record('prepared path missing state'+str(state),ret,s)
for hasObject in [0,1]:
 config(result=NATIVE_FAIL,hasObject=hasObject);ret,out,addr,s=invoke()
 assert ret==NATIVE_FAIL and out is None and s[:7]==[1,1,1,0,0,1,0] and s[17]==0
 assert s[20:24]==[1,2,3,6] and 'rejected' in error()
 record('negative native HRESULT output'+str(hasObject),ret,s)
config(hasObject=0);ret,out,addr,s=invoke()
assert ret==FAIL and out is None and s[:7]==[1,1,1,0,0,1,0]
record('success HRESULT without scene object',ret,s)
for validation in [0,-1,2]:
 for message in [0,1,2]:
  config(validation=validation,message=message);ret,out,addr,s=invoke()
  assert ret==FAIL and out is None and s[:7]==[1,1,1,1,1,1,0]
  assert s[14]==obj and s[15]==obj and s[18]==1 and s[17]==0 and s[20:26]==[1,2,3,4,5,6]
  if message==0:assert 'failed validation' in error()
  elif message==1:assert error()=='Synthetic loaded-world failure.'
  else:assert error()=='Q'*511
  record('validator result'+str(validation)+' diagnostic'+str(message),ret,s)
# Copy diagnostics through a uint32 return; terminator and adjacent bytes checked.
copy=C.create_string_buffer(b'Z'*520);n=lib.WorldSettingsCopyFactoryError(copy)
assert n==512 and copy.raw[:511]==b'Q'*511 and copy.raw[511]==0 and copy.raw[512:]==b'Z'*8+b'\0'
assert lib.WorldSettingsCopyFactoryError(None)==0
results.append({'case':'copy512byte diagnostic with DWORD return and preserved adjacent memory','copied':n})
config(message=3);ret,out,addr,s=invoke();assert ret==0 and out==obj and error()==''
record('successful validator cannot leave stale error',ret,s)
copy=C.create_string_buffer(b'Z'*520);n=lib.WorldSettingsCopyFactoryError(copy)
assert n==1 and copy.raw[0]==0 and copy.raw[1:]==b'Z'*519+b'\0'
results.append({'case':'copy empty error emits only terminator','copied':n})
# A valid inactive call clears the previous failure diagnostic for callers.
config(validation=0,message=1);invoke();assert error()
config(active=0);ret,out,addr,s=invoke();assert error()==''
record('inactive call clears previous failure diagnostic',ret,s)
# Optional in-game feedback observes final diagnostic only after every cleanup
# and FinishAttempt. The callback is a C fixture, with no UI/game operations.
failure_cases=[]
for invalid in ['native','out','both']:
 failure_cases.append(('invalid '+invalid,{},dict(out=invalid not in ['out','both'],native=None if invalid in ['native','both'] else original),POINTER,0))
for mode in [1,2,-1]:failure_cases.append(('unsupported mode'+str(mode),{},dict(mode=mode),FAIL,0))
for state in [0,1]:failure_cases.append(('prepared state'+str(state),dict(preparedState=state),{},FAIL,0))
for hasObject in [0,1]:failure_cases.append(('native failure output'+str(hasObject),dict(result=NATIVE_FAIL,hasObject=hasObject),{},NATIVE_FAIL,0))
failure_cases.append(('missing scene object',dict(hasObject=0),{},FAIL,0))
for validation in [0,-1,2]:
 for message in [0,1,2]:failure_cases.append(('validator'+str(validation)+' message'+str(message),dict(validation=validation,message=message),{},FAIL,1))
for name,settings,arguments,expected,releases in failure_cases:
 config(**settings);lib.FactoryFixtureEnableReporter()
 ret,out,addr,s=invoke(**arguments)
 assert ret==expected and s[4]==releases and s[5:7]==[1,0]
 assert s[60:64]==[1,1,0,1] and s[20+s[19]-2:20+s[19]]==[6,7]
 if arguments.get('out',True):assert out is None
 if releases:assert s[20+s[19]-3:20+s[19]]==[5,6,7]
 record('reporter after cleanup '+name,ret,s)
for active in [0,1]:
 for result in [0,1,0x12345678]:
  config(active=active,result=result);lib.FactoryFixtureEnableReporter()
  ret,out,addr,s=invoke()
  assert ret==result and out==obj and s[60]==0 and 7 not in s[20:20+s[19]]
  record('no reporter on success active'+str(active)+' result'+str(result),ret,s)
for invalid in ['native','out','both']:
 config(active=0);lib.FactoryFixtureEnableReporter()
 ret,out,addr,s=invoke(out=invalid not in ['out','both'],native=None if invalid in ['native','both'] else original)
 assert ret==POINTER and s[5]==0 and s[60]==0
 record('no reporter on inactive invalid '+invalid,ret,s)
config(active=0,result=NATIVE_FAIL);lib.FactoryFixtureEnableReporter()
ret,out,addr,s=invoke();assert ret==NATIVE_FAIL and s[60]==0
record('no reporter on inactive native failure',ret,s)
config(validation=0);lib.FactoryFixtureEnableReporter();lib.WorldSettingsSetFailureReporter(None)
ret,out,addr,s=invoke();assert ret==FAIL and s[60]==0 and s[4:7]==[1,1,0]
record('NULL reporter unregisters feedback',ret,s)
report={'scope':__doc__,'source_sha256':hashlib.sha256((HERE.parent/'world_factory.c').read_bytes()).hexdigest(),'passed':len(results),'cases':results}
(HERE/'factory_results.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'status':'passed','cases':len(results),'source_sha256':report['source_sha256'],'scope':__doc__}))
