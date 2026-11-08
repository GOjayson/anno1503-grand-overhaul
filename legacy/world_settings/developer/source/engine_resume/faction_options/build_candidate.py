from pathlib import Path
import hashlib,json,os,subprocess
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[1]
env=os.environ.copy()
for key,name in [('ZIG_LOCAL_CACHE_DIR','compiler_cache/local'),('ZIG_GLOBAL_CACHE_DIR','compiler_cache/global'),('TEMP','compiler_cache/tmp'),('TMP','compiler_cache/tmp')]:
 p=HERE/name;p.mkdir(parents=True,exist_ok=True);env[key]=str(p)
command=[str(WORK/'_tools/ziglang/zig.exe'),'cc','-target','x86_64-windows-gnu','-shared','-O2','-Wall','-Wextra','-Werror','-o',str(HERE/'FactionFixture.dll'),str(HERE/'faction_fixture.c'),'-lbcrypt','-lkernel32']
subprocess.run(command,env=env,cwd=HERE,check=True)
print(json.dumps({'sha256':hashlib.sha256((HERE/'FactionFixture.dll').read_bytes()).hexdigest(),'scope':'private automated fixture, not installed or game-loaded'}))
