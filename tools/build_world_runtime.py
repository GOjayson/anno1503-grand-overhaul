"""Build an uninstalled native candidate in .local/builds; never write the game."""
from pathlib import Path
import argparse,datetime,hashlib,importlib.util,json,os,shutil,subprocess,sys

ROOT=Path(__file__).resolve().parents[1]
KNOWN_RUNTIME='2f9d1156f3ac53d92a900e41c38a169138c2b4ac7145f2dc92b93c48736cf089'


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--tools',type=Path,help='Directory containing the local ziglang installation')
    args=ap.parse_args()
    source=ROOT/'legacy/world_settings'
    if not (source/'developer/source/runtime_dev3/build_runtime.py').is_file():
        raise ValueError('Import the legacy source before building.')
    tools=args.tools
    if tools is None:
        candidate=ROOT/'.local/toolchain'
        if (candidate/'ziglang/zig.exe').is_file():tools=candidate
        else:
            spec=importlib.util.find_spec('ziglang')
            if not spec or not spec.origin:raise ValueError('Install ziglang==0.16.0 or pass --tools.')
            tools=Path(spec.origin).parent.parent
    tools=tools.resolve(strict=True)
    if not (tools/'ziglang/zig.exe').is_file():raise ValueError('This native builder currently requires the Windows Zig toolchain.')
    version=subprocess.check_output([str(tools/'ziglang/zig.exe'),'version'],text=True).strip()
    if version!='0.16.0':raise ValueError('The imported baseline uses Zig 0.16.0.')
    builds=(ROOT/'.local/builds').resolve()
    builds.mkdir(parents=True,exist_ok=True)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out=builds/('world-runtime-'+stamp)
    assert out.resolve().is_relative_to(builds) and not out.exists()
    stage=out/'package'
    shutil.copytree(source,stage,ignore=shutil.ignore_patterns('__pycache__','*.pyc','_build','*.dll','*.exe'))
    command=[sys.executable,'-B',str(stage/'developer/source/runtime_dev3/build_runtime.py'),'--tools',str(tools)]
    result=subprocess.run(command,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (out/'build.log').write_text(result.stdout,encoding='utf-8')
    if result.returncode:
        print(result.stdout);raise RuntimeError('Native candidate build failed; local output retained.')
    dll=stage/'developer/source/runtime_dev3/AnnoWorldSettings.dll'
    digest=hashlib.sha256(dll.read_bytes()).hexdigest()
    report=dict(built=True,runtime_sha256=digest,known_tested_runtime_sha256=KNOWN_RUNTIME,
        byte_identical_to_known_runtime=digest==KNOWN_RUNTIME,game_executed=False,
        installed=False,game_files_modified=False,toolchain_version=version,
        compiled_inputs=json.loads((stage/'developer/source/runtime_dev3/build_result.json').read_bytes())['source_sha256'])
    (out/'BUILD_RESULT.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(**{k:v for k,v in report.items()if k!='compiled_inputs'},output=str(out)),indent=2))


if __name__=='__main__':main()
