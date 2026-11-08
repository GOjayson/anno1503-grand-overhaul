from pathlib import Path
import hashlib,json,os,subprocess
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
zig=ROOT/'WorldSettings_Work/_tools/ziglang/zig.exe'
cmd=[str(zig),'cc','-target','x86_64-windows-gnu','-shared','-O2','-Wall','-Wextra','-Werror','-o',str(HERE/'WorldBackend.dll'),str(HERE/'world_backend.c'),str(ROOT/'WorldSettings_Work/world_factory.c'),'-lbcrypt','-lkernel32']
env=os.environ.copy()
for name,child in [('ZIG_GLOBAL_CACHE_DIR','zig_global_cache'),('ZIG_LOCAL_CACHE_DIR','zig_local_cache'),('TEMP','tmp'),('TMP','tmp')]:
 p=HERE/child;p.mkdir(exist_ok=True);env[name]=str(p)
subprocess.run(cmd,check=True,cwd=HERE,env=env)
print(json.dumps({'command':cmd,'sha256':hashlib.sha256((HERE/'WorldBackend.dll').read_bytes()).hexdigest()},indent=2))
