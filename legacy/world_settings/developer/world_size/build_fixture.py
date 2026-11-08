"""Build an isolated serializer/ship-contract fixture; no game/copy writes."""
from pathlib import Path
import hashlib,json,os,re,subprocess
HERE=Path(__file__).resolve().parent;PACKAGE=HERE.parents[1];WORK=PACKAGE.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    output=HERE/'_build';output.mkdir(exist_ok=True);env=os.environ.copy()
    for name,folder in [('ZIG_GLOBAL_CACHE_DIR','global-cache'),('ZIG_LOCAL_CACHE_DIR','local-cache'),('TEMP','tmp'),('TMP','tmp')]:
        path=output/folder;path.mkdir(exist_ok=True);env[name]=str(path)
    pending=[HERE/'world_size_fixture.c'];found=set()
    while pending:
        path=pending.pop().resolve();assert path.is_relative_to(PACKAGE)
        if path in found:continue
        assert path.is_file();found.add(path)
        pending.extend(path.parent/name for name in re.findall(r'^\s*#include\s+"([^"]+)"',path.read_text(),re.M))
    inputs=sorted(found)
    before={str(p.relative_to(PACKAGE)):sha(p) for p in inputs}
    command=[str(WORK/'_tools/ziglang/zig.exe'),'cc','-target','x86_64-windows-gnu','-shared','-O2','-Wall','-Wextra','-o',str(output/'world_size_fixture.dll'),str(HERE/'world_size_fixture.c'),'-lbcrypt']
    subprocess.run(command,check=True,env=env,cwd=HERE)
    assert before=={str(p.relative_to(PACKAGE)):sha(p) for p in inputs}
    result=dict(scope=__doc__,command=command,input_sha256=before,fixture_dll_sha256=sha(output/'world_size_fixture.dll'),game_executed=False,game_or_copy_mutated=False)
    (HERE/'fixture_build.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
