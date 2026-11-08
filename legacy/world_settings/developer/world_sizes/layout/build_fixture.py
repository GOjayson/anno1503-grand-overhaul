"""Build isolated native helper fixture only. No game/copy process or scene is touched."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess
HERE=Path(__file__).resolve().parent
PACKAGE=HERE.parents[2]
SOURCE=PACKAGE/'developer/source/engine_resume/ai_food/experiment_runtime'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tools',type=Path,default=PACKAGE.parent/'_tools')
    args=parser.parse_args()
    output=HERE/'_build';output.mkdir(exist_ok=True)
    inputs=[HERE/'layout_fixture.c']+[SOURCE/name for name in ['world_backend.h','world_catalogue.h','world_factions.h','world_ship_reserves.h','selection_policy.inc','balanced_layout.inc']]
    before={str(p.relative_to(PACKAGE)).replace('\\','/'):sha(p) for p in inputs}
    env=os.environ.copy()
    for name,subdir in [('ZIG_GLOBAL_CACHE_DIR','global-cache'),('ZIG_LOCAL_CACHE_DIR','local-cache'),('TEMP','tmp'),('TMP','tmp')]:
        path=output/subdir;path.mkdir(exist_ok=True);env[name]=str(path)
    command=[str(args.tools.resolve()/'ziglang/zig.exe'),'cc','-target','x86_64-windows-gnu','-shared','-O2','-Wall','-Wextra','-Werror','-o',str(output/'layout_fixture.dll'),str(HERE/'layout_fixture.c')]
    subprocess.run(command,check=True,cwd=HERE,env=env)
    assert before=={str(p.relative_to(PACKAGE)).replace('\\','/'):sha(p) for p in inputs}
    result=dict(scope=__doc__,command=command,input_sha256=before,fixture_dll_sha256=sha(output/'layout_fixture.dll'),game_executed=False,game_or_copy_mutated=False)
    (HERE/'fixture_build.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
