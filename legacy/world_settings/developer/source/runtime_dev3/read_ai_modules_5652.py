"""Bounded read-only loaded-module proof for exact development session5652.

Uses process identity and module metadata only. Reads no process memory, heap,
command line, authentication/session data, or controller pointers. Mapping an
approved copy does not alone establish that post-profile validation executed.
"""
from pathlib import Path
import ctypes as C,json,sys
HERE=Path(__file__).resolve().parent;PACKAGE=HERE.parent/'anno1503_food_world_dev3'
sys.path.insert(0,str(PACKAGE/'activation'))
import activate_world_settings as api
EXPECTED_PID=5652
EXPECTED_CREATED=134382753740235607
EXPECTED_RUNTIME='b49757850043992ef7cc5209eedc0838fcfc0a465b54a04c4b67f9798b04ba0c'
EXPECTED_SPEC='f2b8a307e0af8a8d434f1d9ca36354fe9573fe0c22bc5b8aade82bc6694365cb'
EXPECTED_RUNTIME_BASE=140729464324096
def main():
 inputs=api.verify();saved=json.loads(api.SESSION.read_bytes())
 assert saved['pid']==EXPECTED_PID and saved['process_creation_time']==EXPECTED_CREATED
 assert saved['runtime_sha256']==EXPECTED_RUNTIME==inputs['runtime_sha256']
 assert saved['world_spec_sha256']==EXPECTED_SPEC==inputs['spec_sha256']
 assert saved['executable_sha256']==inputs['exe_sha256'] and saved['hooks_installed'] is True
 assert saved['runtime_base']==EXPECTED_RUNTIME_BASE
 assert api.all_processes()==[EXPECTED_PID]
 handle=api.check(api.open_process(0x1000,False,EXPECTED_PID),'Open exact Anno process read-only')
 try:
  assert api.creation_time(handle)==EXPECTED_CREATED
  executable=C.create_unicode_buffer(32768);length=api.W.DWORD(len(executable))
  api.check(api.query_path(handle,0,executable,C.byref(length)),'Read exact process executable path')
  assert api.same(executable.value,inputs['source']/'Anno1503.exe') and api.sha(executable.value)==inputs['exe_sha256']
  mods=api.modules(EXPECTED_PID);api.verify_modules(mods,inputs,api.same,api.sha)
  runtime=[m for m in mods['__all__'] if m['name'].lower()=='annoworldsettings.dll']
  assert len(runtime)==1 and runtime[0]['base']==saved['runtime_base']
  assert api.same(runtime[0]['path'],api.DLL) and api.sha(runtime[0]['path'])==EXPECTED_RUNTIME
  ai=[m for m in mods['__all__'] if m['name'].lower() in ['complogic.dll','complogicclassic.dll']]
  assert 1<=len(ai)<=4
  approved=[];original=[]
  for m in ai:
   record=dict(name=m['name'],path=m['path'],sha256=api.sha(m['path']),image_size=m['size'],module_base=m['base'])
   choices=[(relative,digest) for relative,digest in inputs['private_native_sha256'].items() if api.same(m['path'],inputs['copy']/relative)]
   if choices:
    assert len(choices)==1 and record['sha256']==choices[0][1]
    approved.append(record)
   else:
    matches=[digest for name,digest in inputs['native_sha256'].items() if name.lower()==m['name'].lower() and api.same(m['path'],inputs['source']/name)]
    assert len(matches)==1 and record['sha256']==matches[0];original.append(record)
  assert approved,'No inspected copied AI module is mapped in the exact session.'
  result=dict(scope=__doc__,pid=EXPECTED_PID,process_creation_time=EXPECTED_CREATED,runtime_sha256=EXPECTED_RUNTIME,
   world_spec_sha256=EXPECTED_SPEC,runtime_base=EXPECTED_RUNTIME_BASE,exact_process_and_runtime_verified=True,approved_copied_ai_modules=approved,
   original_ai_modules=original,post_profile_execution_proven=False,process_memory_bytes_read=0,
   process_memory_modified=False,remote_threads_created=0,
   operator_observations=dict(source='Root operator report; not independently read by this module-only script',
    route='Burger preset',back_cancel_returned_to_list=True,reopened=True,gameplay_rendered=True,
    settings=dict(difficulty='medium',size='mixed',island_count=24,spacing=16,cultures=255,ai_count=1,pirates=False,venetians=True),
    factory_error='',hook_error='',ai_loader_error='',ai_profile_error='',ai_profile_status=2,validated_ai_count=1))
  (HERE/'live_ai_modules_5652.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')
  print(json.dumps(result,indent=2))
 finally:api.close(handle)
if __name__=='__main__':main()
