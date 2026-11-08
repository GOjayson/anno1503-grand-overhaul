"""Compile only. Does not load a DLL, inspect a game process or install hooks."""
from pathlib import Path
import hashlib,json,os,subprocess

HERE=Path(__file__).resolve().parent
WORK=HERE.parents[1]
env=os.environ.copy()
for name,child in [('ZIG_GLOBAL_CACHE_DIR','zig_global_cache'),('ZIG_LOCAL_CACHE_DIR','zig_local_cache'),('TEMP','tmp'),('TMP','tmp')]:
    directory=HERE/child;directory.mkdir(exist_ok=True);env[name]=str(directory)
cmd=[str(WORK/'_tools/ziglang/zig.exe'),'cc','-target','x86_64-windows-gnu','-shared','-O2','-Wall','-Wextra','-Werror','-o',str(HERE/'TestHookInstallerCompileOnly.dll'),str(HERE/'install_test_hooks.c'),'-lbcrypt','-lkernel32']
subprocess.run(cmd,check=True,cwd=HERE,env=env)
result=dict(scope=__doc__,command=cmd,source_sha256=hashlib.sha256((HERE/'install_test_hooks.c').read_bytes()).hexdigest(),header_sha256=hashlib.sha256((WORK/'runtime_test_blobs.h').read_bytes()).hexdigest(),output_sha256=hashlib.sha256((HERE/'TestHookInstallerCompileOnly.dll').read_bytes()).hexdigest())
(HERE/'compile_check.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
