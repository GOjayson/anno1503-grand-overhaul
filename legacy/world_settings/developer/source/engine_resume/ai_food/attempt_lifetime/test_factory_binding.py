"""Compiled candidate factory binding/discard policy with explicit doubles.

The factory, validator, binder, release and report boundaries are fixtures.
No native game scene is created and no UI or process attachment is used.
"""
from pathlib import Path
import ctypes as C,hashlib,itertools,json,os,subprocess
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[2]
manifest=json.loads((HERE/'candidate_sources.json').read_text())
current={name:hashlib.sha256((WORK/name).read_bytes()).hexdigest() for name in manifest['compiled_sources_unchanged']}
for name,digest in current.items():assert digest in [manifest['compiled_sources_unchanged'][name],manifest['candidate_sha256'][Path(name).name+'.candidate']]
out=HERE/'_build';out.mkdir(exist_ok=True);(out/'tmp').mkdir(exist_ok=True)
fixture=(WORK/'world_certificate/factory_fixture.c').read_text('utf-8');assert fixture.count('#include "../world_factory.c"')==1
fixture=fixture.replace('#include "../world_factory.c"','#include "world_factory.c.candidate"')
fixture+='''
static int fixtureBindingAllowed;
int WorldSettingsBindAIProfileWorld(void *scene,char *error,uint32_t cap){
 fixtureStats[58]++;fixtureStats[59]=(uintptr_t)scene;
 if(!fixtureBindingAllowed){if(error&&cap)snprintf(error,cap,"Synthetic binding failure.");return 0;}return 1;
}
__declspec(dllexport) void BindingFixtureSet(int allowed){fixtureBindingAllowed=allowed;}
'''
(out/'factory_binding_fixture.c').write_text(fixture,'utf-8')
env=dict(os.environ,ZIG_GLOBAL_CACHE_DIR=str(out/'global-cache'),ZIG_LOCAL_CACHE_DIR=str(out/'local-cache'),TEMP=str(out/'tmp'),TMP=str(out/'tmp'))
subprocess.run([str(WORK/'_tools/ziglang/zig.exe'),'cc','-shared','-O2','-Wall','-Wextra','-Werror','-I',str(HERE),str(out/'factory_binding_fixture.c'),'-o',str(out/'FactoryBindingFixture.dll')],check=True,env=env)
lib=C.CDLL(str(out/'FactoryBindingFixture.dll'))
lib.FactoryFixtureConfigure.argtypes=[C.c_int,C.c_int,C.c_int32,C.c_int,C.c_int,C.c_int]
lib.FactoryFixtureStat.argtypes=[C.c_uint32];lib.FactoryFixtureStat.restype=C.c_uint64
for name in ['FactoryFixtureOriginal','FactoryFixtureObject','FactoryFixturePath','WorldSettingsLastFactoryError']:getattr(lib,name).restype=C.c_void_p
lib.WorldSettingsCreateScene.argtypes=[C.c_int32,C.c_void_p,C.c_void_p,C.POINTER(C.c_void_p),C.c_void_p,C.c_uint32,C.c_uint32,C.c_void_p];lib.WorldSettingsCreateScene.restype=C.c_int32
lib.BindingFixtureSet.argtypes=[C.c_int]
original=lib.FactoryFixtureOriginal();obj=lib.FactoryFixtureObject();path=C.create_string_buffer(b'original.sze')
FAIL=C.c_int32(0x80004005).value;NATIVE_FAIL=C.c_int32(0x80070057).value;rows=[]
for active,native,has_scene,valid,binding in itertools.product([0,1],[0,1,NATIVE_FAIL],[0,1],[0,1],[0,1]):
 lib.FactoryFixtureConfigure(active,2,native,has_scene,valid,1 if not valid else 0);lib.BindingFixtureSet(binding);lib.FactoryFixtureEnableReporter()
 output=C.c_void_p(0x1122334455667788)
 result=lib.WorldSettingsCreateScene(0,C.addressof(path),0x1234,C.byref(output),0x5678,19,23,original)
 stat=[lib.FactoryFixtureStat(i) for i in range(64)]
 should_bind=active and native>=0 and has_scene and valid
 success=not active or (native>=0 and has_scene and valid and binding)
 assert stat[58]==int(bool(should_bind))
 if not active:
  assert result==native and output.value==(obj if has_scene else None) and stat[3]==stat[4]==stat[5]==stat[60]==0
 elif success:
  assert result==native and output.value==obj and stat[4]==0 and stat[5]==1 and stat[6]==1 and stat[60]==0
 else:
  assert output.value is None and result==(native if native<0 else FAIL)
  assert stat[4]==int(native>=0 and bool(has_scene)) and stat[5]==1 and stat[6]==0 and stat[17]==0 and stat[60]==1
  assert stat[61]==1 and stat[62]==0 and stat[63]==1
  if should_bind:assert C.string_at(lib.WorldSettingsLastFactoryError())==b'Synthetic binding failure.'
 rows.append(dict(active=bool(active),native_result=native,has_scene=bool(has_scene),validation=bool(valid),binding_allowed=bool(binding),binder_calls=stat[58],release_calls=stat[4],finish_success=stat[6],result=result,passed=True))
for name,digest in current.items():assert hashlib.sha256((WORK/name).read_bytes()).hexdigest()==digest
report=dict(scope=__doc__,actual_game_runs=0,compiled_sources_unchanged_during_test=True,current_source_sha256=current,candidate_factory_sha256=manifest['candidate_sha256']['world_factory.c.candidate'],fixture_sha256=hashlib.sha256((out/'FactoryBindingFixture.dll').read_bytes()).hexdigest(),cases=rows)
(HERE/'factory_binding_results.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
print(json.dumps(dict(factory_cases=len(rows),actual_game_runs=0,compiled_sources_changed=False)))
