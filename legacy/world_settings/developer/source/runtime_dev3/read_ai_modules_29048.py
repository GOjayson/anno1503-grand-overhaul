"""Bounded read-only loaded-module proof for exact development session29048.

Uses process identity and module metadata only. Reads no process memory, heap,
command line, authentication/session data, or controller pointers. Mapping an
approved copy does not alone establish that post-profile validation executed.
"""
from pathlib import Path
import ctypes as C,json,sys
HERE=Path(__file__).resolve().parent;PACKAGE=HERE.parent/'anno1503_food_world_dev3'
sys.path.insert(0,str(PACKAGE/'activation'))
import activate_world_settings as api
EXPECTED_PID=29048
EXPECTED_CREATED=134382733808473811
EXPECTED_RUNTIME='7dbc0ee42fd9d4957e9eb0ac4158eebffb64442e639b05cbc1392f477a52f0b5'
EXPECTED_SPEC='cd76f236bef372ae5008420eb617e6164960209a7cf5060bc5ff0ffd585c3b4a'
def main():
 inputs=api.verify();saved=json.loads(api.SESSION.read_bytes())
 assert saved['pid']==EXPECTED_PID and saved['process_creation_time']==EXPECTED_CREATED
 assert saved['runtime_sha256']==EXPECTED_RUNTIME==inputs['runtime_sha256']
 assert saved['world_spec_sha256']==EXPECTED_SPEC==inputs['spec_sha256']
 assert saved['executable_sha256']==inputs['exe_sha256'] and saved['hooks_installed'] is True
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
   record=dict(name=m['name'],path=m['path'],sha256=api.sha(m['path']),image_size=m['size'])
   choices=[(relative,digest) for relative,digest in inputs['private_native_sha256'].items() if api.same(m['path'],inputs['copy']/relative)]
   if choices:
    assert len(choices)==1 and record['sha256']==choices[0][1]
    approved.append(record)
   else:
    matches=[digest for name,digest in inputs['native_sha256'].items() if name.lower()==m['name'].lower() and api.same(m['path'],inputs['source']/name)]
    assert len(matches)==1 and record['sha256']==matches[0];original.append(record)
  assert approved,'No inspected copied AI module is mapped in the exact session.'
  result=dict(scope=__doc__,pid=EXPECTED_PID,process_creation_time=EXPECTED_CREATED,runtime_sha256=EXPECTED_RUNTIME,
   world_spec_sha256=EXPECTED_SPEC,exact_process_and_runtime_verified=True,approved_copied_ai_modules=approved,
   original_ai_modules=original,post_profile_execution_proven=False,process_memory_bytes_read=0,
   process_memory_modified=False,remote_threads_created=0)
  (HERE/'live_ai_modules_29048.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')
  print(json.dumps(result,indent=2))
 finally:api.close(handle)
if __name__=='__main__':main()
