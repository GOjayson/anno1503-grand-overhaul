from pathlib import Path
import subprocess,hashlib,json,os
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
zig=ROOT/'WorldSettings_Work/_tools/ziglang/zig.exe'
cmd=[str(zig),'cc','-target','x86_64-windows-gnu','-shared','-O2','-Wall','-Wextra','-Werror','-o',str(HERE/'WorldSettings.dll'),str(HERE/'WorldSettings.c'),'-luser32','-lgdi32','-lkernel32']
env=os.environ.copy()
for name,child in [('ZIG_GLOBAL_CACHE_DIR','zig_global_cache'),('ZIG_LOCAL_CACHE_DIR','zig_local_cache'),('TEMP','tmp'),('TMP','tmp')]:
 p=HERE/child;p.mkdir(exist_ok=True);env[name]=str(p)
subprocess.run(cmd,check=True,cwd=HERE,env=env)
print(json.dumps({'command':cmd,'sha256':hashlib.sha256((HERE/'WorldSettings.dll').read_bytes()).hexdigest()},indent=2))

