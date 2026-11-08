from pathlib import Path
import os,subprocess,json,hashlib
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
zig=ROOT/'WorldSettings_Work/_tools/ziglang/zig.exe';env=os.environ.copy()
for name,child in [('ZIG_GLOBAL_CACHE_DIR','zig_global_cache'),('ZIG_LOCAL_CACHE_DIR','zig_local_cache'),('TEMP','tmp'),('TMP','tmp')]:
 p=HERE/child;p.mkdir(exist_ok=True);env[name]=str(p)
cmd=[str(zig),'cc','-target','x86_64-windows-gnu','-shared','-O2','-Wall','-Wextra','-Werror','-o',str(HERE/'FactoryFixture.dll'),str(HERE/'factory_fixture.c'),'-lkernel32']
subprocess.run(cmd,env=env,check=True,cwd=HERE)
report={'status':'compiled with -Wall -Wextra -Werror','source_sha256':hashlib.sha256((HERE.parent/'world_factory.c').read_bytes()).hexdigest(),'fixture_sha256':hashlib.sha256((HERE/'factory_fixture.c').read_bytes()).hexdigest(),'dll_sha256':hashlib.sha256((HERE/'FactoryFixture.dll').read_bytes()).hexdigest(),'command':cmd}
(HERE/'factory_build.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='command'}))
