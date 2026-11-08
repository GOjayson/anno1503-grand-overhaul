"""Build a copied runtime with frozen, unchanged native hook blobs. No game writes."""
from pathlib import Path
import hashlib,json,os,subprocess
HERE=Path(__file__).resolve().parent
GAME=HERE.parents[1]
PACKAGE=GAME/'WorldSettings_Work/anno1503_food_world_dev3_cityfix1'
SOURCE=PACKAGE/'developer/source'
BASELINE=GAME/'WorldSettings_Work/anno1503_food_world_dev3_pathfix1/developer/source/runtime_dev3/build_result.json'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 old=json.loads(BASELINE.read_bytes())
 names=list(old['source_sha256'])
 before={name:sha(SOURCE/name) for name in names}
 changed=[name for name in names if before[name]!=old['source_sha256'][name]]
 expected={'engine_resume\\ai_food\\experiment_runtime\\world_backend.c','engine_resume\\ai_food\\experiment_runtime\\special_scene.inc'}
 assert set(changed)==expected,changed
 assert before['runtime_dev3\\runtime_test_blobs.h']==old['source_sha256']['runtime_dev3\\runtime_test_blobs.h']
 build=HERE/'build';build.mkdir(exist_ok=True)
 env=os.environ.copy()
 for key,child in [('ZIG_GLOBAL_CACHE_DIR','global'),('ZIG_LOCAL_CACHE_DIR','local'),('TEMP','tmp'),('TMP','tmp')]:
  directory=build/child;directory.mkdir(exist_ok=True);env[key]=str(directory)
 output=SOURCE/'runtime_dev3/AnnoWorldSettings.dll'
 c_names=[str(Path(name).relative_to(GAME/'WorldSettings_Work')) for name in old['command'] if name.endswith('.c')]
 assert len(c_names)==7
 command=[str(GAME/'WorldSettings_Work/_tools/ziglang/zig.exe'),'cc','-target','x86_64-windows-gnu','-shared','-O2','-Wall','-Wextra','-Werror','-I',str(SOURCE/'runtime_dev3'),'-o',str(output),*[str(SOURCE/name) for name in c_names],'-lbcrypt','-luser32','-lgdi32','-lkernel32']
 subprocess.run(command,check=True,cwd=HERE,env=env)
 assert all(sha(SOURCE/name)==digest for name,digest in before.items())
 result={**old,'command':command,'sha256':sha(output),'source_sha256':before,'actual_game_run':False,'build_revision':'cityfix1','unchanged_native_hook_blobs':True,'compiled_source_changes':changed}
 (SOURCE/'runtime_dev3/build_result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(dict(sha256=result['sha256'],compiled_sources=len(before),changed=changed),indent=2))
if __name__=='__main__':main()
