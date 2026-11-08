"""Compiled Windows adopted path/SHA checks on real files and an isolated copy.

The live game runtime and its mapped source files are not changed. No game run.
"""
from pathlib import Path
import ctypes as C
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[1];ROOT=WORK.parent


def main():
    build=HERE/'_build';build.mkdir(exist_ok=True)
    env=os.environ.copy()
    for name,child in [('ZIG_GLOBAL_CACHE_DIR','zig_global_cache'),('ZIG_LOCAL_CACHE_DIR','zig_local_cache'),('TEMP','tmp'),('TMP','tmp')]:
        path=build/child;path.mkdir(exist_ok=True);env[name]=str(path)
    source=build/'selection_path.c';shutil.copyfile(HERE/'selection.c',source)
    command=[str(WORK/'_tools/ziglang/zig.exe'),'cc','-target','x86_64-windows-gnu','-shared','-O2','-Wall','-Wextra','-Werror',
             '-I',str(HERE),str(source),'-lbcrypt','-lkernel32','-o']
    production=build/'RoutePathSelection.dll';testing=build/'RoutePathSelectionTest.dll'
    subprocess.run(command+[str(production)],check=True,cwd=build,env=env)
    subprocess.run(command[:-1]+['-DWS_ROUTE_TESTING','-o',str(testing)],check=True,cwd=build,env=env)
    prod=C.CDLL(str(production));lib=C.CDLL(str(testing))
    assert not hasattr(prod,'WorldSettingsClassifyDirectSelectionAtRoot')
    classify=lib.WorldSettingsClassifyDirectSelectionAtRoot
    classify.argtypes=[C.c_char_p,C.c_uint32,C.c_wchar_p];classify.restype=C.c_int
    normal=prod.WorldSettingsClassifyDirectSelection
    normal.argtypes=[C.c_char_p,C.c_uint32,C.c_void_p];normal.restype=C.c_int
    records=json.loads((HERE/'stock_endless_paths.json').read_text())['records'];rows=[]
    def check(name,filename,capacity,root,expected):
        result=classify(filename,capacity,str(root) if root is not None else None)
        assert result==expected,(name,result,expected)
        rows.append(dict(name=name,result=result,passed=True))
    for record in records:
        filename=record['path'].encode('ascii')
        assert hashlib.sha256((ROOT/record['path']).read_bytes()).hexdigest()==record['sha256']
        for value in [filename,filename.upper(),filename.replace(b'\\',b'/')]:
            check('actual:'+value.decode(),value,260,ROOT,1)
        check('exact_capacity:'+record['filename'],filename,len(filename)+1,ROOT,1)
        check('truncated:'+record['filename'],filename,len(filename),ROOT,-1)
        check('wrong_root:'+record['filename'],filename,260,build,-1)
    for filename in [b'Languages\\Nl\\Scenes\\Tutorial\\01Discover01.sze',
                     b'Languages\\Nl\\Scenes\\0200Single\\Single_01.sze',
                     b'Scenes\\0500MultiEndlos\\Multi01_04.sze',b'ws5.sav',b'Lastgame.sav',b'']:
        check('unrelated:'+filename.decode(),filename,260,None,0)
        assert normal(filename,260,None)==0
    for filename in [b'Scenes\\0010SingleEndlos\\unknown.sze',
                     b'Languages\\Nl\\Scenes\\0010SingleEndlos\\unknown.sze',
                     b'Languages\\Fr\\Scenes\\0011SingleEndlosAddon\\endless01.sze']:
        check('uninspected_endless:'+filename.decode(),filename,260,ROOT,-1)
    for filename in [b'..\\Languages\\Nl\\Scenes\\0010SingleEndlos\\00_1024_easyentry_01.sze',
                     b'Languages\\Nl\\Scenes\\0010SingleEndlos\\..\\00_1024_easyentry_01.sze',
                     b'C:\\Languages\\Nl\\Scenes\\0010SingleEndlos\\00_1024_easyentry_01.sze',
                     b'\\\\server\\share\\00_1024_easyentry_01.sze',b'/absolute.sze',b'./scene.sze',
                     b'Languages\\\\Nl\\Scenes\\map.sze',b'Languages\\Nl.\\Scenes\\map.sze',b'file.sze ',b'x*',b'x?']:
        check('unsafe:'+filename.decode(),filename,260,ROOT,-1)
    for name,filename,capacity in [('null_name',None,260),('zero_capacity',b'X',0),('oversize_capacity',b'X',261),('no_terminator',b'X'*260,260)]:
        check(name,filename,capacity,ROOT,-1)
    selected=records[0];relative=selected['path'];filename=relative.encode('ascii')
    with tempfile.TemporaryDirectory(prefix='route-path-fixture-',dir=build) as temporary:
        fixture=Path(temporary).resolve();fixture.relative_to(build.resolve())
        target=fixture/relative;target.parent.mkdir(parents=True,exist_ok=True);data=(ROOT/relative).read_bytes();target.write_bytes(data)
        check('isolated_actual_file',filename,260,fixture,1)
        target.write_bytes(data[:-1]+bytes([data[-1]^1]));check('changed_file_sha256',filename,260,fixture,-1)
        target.unlink();check('missing_file',filename,260,fixture,-1)
        target.mkdir();check('directory_at_file_target',filename,260,fixture,-1)
    result=dict(scope=__doc__,game_executed=False,mapped_sources_changed=False,cases=len(rows),results=rows,
                source='selection.c',adopted_source_sha256=hashlib.sha256((HERE/'selection.c').read_bytes()).hexdigest(),
                registry_sha256=hashlib.sha256((HERE/'stock_endless_paths.h').read_bytes()).hexdigest(),
                production_binary_sha256=hashlib.sha256(production.read_bytes()).hexdigest(),
                no_production_root_override_export=True)
    (HERE/'path_selection_results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(cases=len(rows),passed=True,game_executed=False,mapped_sources_changed=False)))


if __name__=='__main__':main()
