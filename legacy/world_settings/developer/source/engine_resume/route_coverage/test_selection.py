"""Compile and exercise the private bounded selection helper (no game UI)."""
from pathlib import Path
import ctypes
import hashlib
import json
import os
import subprocess
HERE=Path(__file__).resolve().parent; WORK=HERE.parents[1]


def main():
    build=HERE/'_build';build.mkdir(exist_ok=True)
    environment=os.environ.copy()
    for name,child in [('ZIG_GLOBAL_CACHE_DIR','zig_global_cache'),('ZIG_LOCAL_CACHE_DIR','zig_local_cache'),('TEMP','tmp'),('TMP','tmp')]:
        directory=build/child;directory.mkdir(exist_ok=True);environment[name]=str(directory)
    command=[str(WORK/'_tools/ziglang/zig.exe'),'cc','-target','x86_64-windows-gnu',
             '-shared','-O2','-Wall','-Wextra','-Werror','-o',str(build/'RouteSelection.dll'),str(HERE/'selection.c')]
    subprocess.run(command,check=True,cwd=build,env=environment)
    dll=ctypes.CDLL(str(build/'RouteSelection.dll'))
    classify=dll.WorldSettingsClassifyDirectSelection
    classify.argtypes=[ctypes.c_char_p,ctypes.c_uint32,ctypes.c_void_p];classify.restype=ctypes.c_int
    records=json.loads((HERE/'stock_endless.json').read_text())['records'];cases=[]
    def check(name,filename,capacity,digest,expected):
        value=classify(filename,capacity,digest)
        assert value==expected,(name,value,expected)
        cases.append(dict(name=name,result=value,passed=True))
    for row in records:
        filename=row['filename'].encode();digest=bytes.fromhex(row['md5'])
        check(row['filename'],filename,260,digest,1)
        check('upper:'+row['filename'],filename.upper(),len(filename)+1,digest,1)
        altered=bytes([digest[0]^1])+digest[1:]
        check('changed:'+row['filename'],filename,260,altered,-1)
        check('truncated:'+row['filename'],filename,len(filename),digest,-1)
        for spelling in [b'X'+filename,filename+b'.sav',b'..\\'+filename,b'folder\\'+filename]:
            check('other:'+spelling.decode(),spelling,260,digest,0)
    for filename in [b'Single_01.sze',b'01Discover01.sze',b'ws5.sav',b'Lastgame.sav',b'',b'endless04.sze']:
        check('unrelated:'+filename.decode(),filename,260,bytes(16),0)
    for name,filename,capacity,digest in [('null_name',None,260,bytes(16)),('null_digest',b'X',260,None),
                                         ('zero_capacity',b'X',0,bytes(16)),('large_capacity',b'X',261,bytes(16)),
                                         ('no_terminator',b'X'*260,260,bytes(16))]:
        check(name,filename,capacity,digest,-1)
    result=dict(scope=__doc__.strip(),game_executed=False,cases=len(cases),results=cases,
                binary_sha256=hashlib.sha256((build/'RouteSelection.dll').read_bytes()).hexdigest())
    (HERE/'selection_results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(cases=len(cases),passed=True,game_executed=False)))


if __name__=='__main__':main()
