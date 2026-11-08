from pathlib import Path
import hashlib,json,os,subprocess
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[2]
cache=HERE.parent/'compiler_cache';env=os.environ.copy()
for key,name in [('ZIG_LOCAL_CACHE_DIR','transfer-local'),('ZIG_GLOBAL_CACHE_DIR','global'),('TEMP','tmp'),('TMP','tmp')]:
 p=cache/name;p.mkdir(parents=True,exist_ok=True);env[key]=str(p)
sources=[HERE/'transfer_fixture.c',HERE/'pirate_finalize.inc.candidate']+list((HERE.parent/'runtime').glob('*.c'))+list((HERE.parent/'runtime').glob('*.h'))+list((HERE.parent/'runtime').glob('*.inc'))
before={str(p.relative_to(WORK)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
command=[str(WORK/'_tools/ziglang/zig.exe'),'cc','-target','x86_64-windows-gnu','-shared','-O2','-Wall','-Wextra','-Werror','-o',str(HERE/'TransferFixture.dll'),str(HERE/'transfer_fixture.c'),'-lbcrypt','-lkernel32']
subprocess.run(command,cwd=HERE,env=env,check=True)
assert all(hashlib.sha256((WORK/n).read_bytes()).hexdigest()==h for n,h in before.items())
result=dict(scope='Private compiled pirate-initialization policy fixture; no game loaded',dll_sha256=hashlib.sha256((HERE/'TransferFixture.dll').read_bytes()).hexdigest(),source_sha256=before,game_runs=0)
(HERE/'fixture_build.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(dll_sha256=result['dll_sha256'],source_files=len(sources),game_runs=0)))
