"""Read-only module proof for the current exact cffc development activation.

The activation journal supplies PID, creation time, runtime base, world-spec
fingerprint and copy root. Each is checked against the actual process, current
package and guarded-copy preflight. Only module metadata and process identity
are inspected. No private process memory, heap, command line, controller data
or authentication data is read; no remote thread or memory write is used.

Approved module mapping alone does not prove post-profile execution or gameplay.
"""
from pathlib import Path
import ctypes as C,hashlib,json,sys
HERE=Path(__file__).resolve().parent;PACKAGE=HERE.parent/'anno1503_food_world_dev3'
sys.path.insert(0,str(PACKAGE/'activation'))
import activate_world_settings as api
EXPECTED_RUNTIME='cffc701402849183ffcb690017f2995c77db8f8b14bc04f156c86341defd4dcc'
EXPECTED_EXE='1a4bebe7c676a5904834b9e67e936187729dc67c013a4fb4fd64986a3cb8e95a'
OUTPUT=HERE/'live_ai_modules_cffc.json'
def main():
 inputs=api.verify();journal=api.SESSION.read_bytes();saved=json.loads(journal)
 pid=saved['pid'];created=saved['process_creation_time'];base=saved['runtime_base'];spec=saved['world_spec_sha256']
 assert type(pid)is int and pid>0 and type(created)is int and created>0
 assert type(base)is int and base>0 and base%4096==0
 assert saved['runtime_sha256']==EXPECTED_RUNTIME==inputs['runtime_sha256']
 assert saved['executable_sha256']==EXPECTED_EXE==inputs['exe_sha256']
 assert spec==inputs['spec_sha256'] and len(spec)==64
 assert saved['hooks_installed'] is True and saved['installed_files_modified'] is False
 assert api.same(saved['copy_root'],inputs['copy'])
 assert api.all_processes()==[pid]
 handle=api.check(api.open_process(0x1000,False,pid),'Open exact Anno process read-only')
 try:
  assert api.creation_time(handle)==created
  executable=C.create_unicode_buffer(32768);length=api.W.DWORD(len(executable))
  api.check(api.query_path(handle,0,executable,C.byref(length)),'Read exact process executable path')
  assert api.same(executable.value,inputs['source']/'Anno1503.exe') and api.sha(executable.value)==EXPECTED_EXE
  modules=api.modules(pid);api.verify_modules(modules,inputs,api.same,api.sha)
  entries=modules['__all__'];runtime=[m for m in entries if m['name'].lower()=='annoworldsettings.dll']
  assert len(runtime)==1 and runtime[0]['base']==base
  assert api.same(runtime[0]['path'],api.DLL) and api.sha(runtime[0]['path'])==EXPECTED_RUNTIME
  ai=[m for m in entries if m['name'].lower()in ['complogic.dll','complogicclassic.dll']]
  assert 1<=len(ai)<=4,'Run the module-only proof after the game has loaded its AI modules.'
  approved=[];original=[]
  for module in ai:
   record=dict(name=module['name'],path=module['path'],sha256=api.sha(module['path']),image_size=module['size'],module_base=module['base'])
   copies=[digest for relative,digest in inputs['private_native_sha256'].items() if api.same(module['path'],inputs['copy']/relative)]
   if copies:
    assert len(copies)==1 and record['sha256']==copies[0];approved.append(record)
   else:
    originals=[digest for name,digest in inputs['native_sha256'].items() if name.lower()==module['name'].lower() and api.same(module['path'],inputs['source']/name)]
    assert len(originals)==1 and record['sha256']==originals[0];original.append(record)
  assert approved,'No approved copied AI module is mapped in this exact activation.'
  assert api.creation_time(handle)==created and api.SESSION.read_bytes()==journal
  assert api.sha(PACKAGE/'world_patch.json')==spec
  result=dict(scope=__doc__,pid=pid,process_creation_time=created,runtime_sha256=EXPECTED_RUNTIME,runtime_base=base,
   world_spec_sha256=spec,copy_root=saved['copy_root'],activation_journal_sha256=hashlib.sha256(journal).hexdigest(),
   exact_process_and_runtime_verified=True,approved_copied_ai_modules=approved,original_ai_modules=original,
   post_profile_execution_proven=False,gameplay_proven=False,process_memory_bytes_read=0,process_memory_modified=False,
   remote_threads_created=0,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
  OUTPUT.write_text(json.dumps(result,indent=2)+'\n','utf-8');print(json.dumps(result,indent=2))
 finally:api.close(handle)
if __name__=='__main__':main()
