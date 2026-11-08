"""Compiled grouped-page commit and injected rollback failures; no game process."""
from pathlib import Path
import ctypes as C
import hashlib
import json
import os
import subprocess
HERE=Path(__file__).resolve().parent
WORK=HERE.parents[1]
out=HERE/'_build';out.mkdir(exist_ok=True)
for name in ['tmp','global-cache','local-cache']:(out/name).mkdir(exist_ok=True)
env=dict(os.environ,ZIG_GLOBAL_CACHE_DIR=str(out/'global-cache'),ZIG_LOCAL_CACHE_DIR=str(out/'local-cache'),TEMP=str(out/'tmp'),TMP=str(out/'tmp'))
dllpath=out/'PageContract.dll'
subprocess.run([str(WORK/'_tools/ziglang/zig.exe'),'cc','-shared','-O2','-Wall','-Wextra','-Werror',str(HERE/'page_fixture.c'),'-lbcrypt','-o',str(dllpath)],check=True,env=env)
dll=C.CDLL(str(dllpath));test=dll.WorldSettingsPageFixture;test.argtypes=[C.c_int];test.restype=C.c_int
cases=[]
for mode in [*range(11),20,21,22]:
    result=test(mode)
    assert result==0,(mode,'C assertion line',result)
    cases.append(mode)
result=dict(scope=__doc__,cases=cases,source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [HERE/'install_test_hooks.c',HERE/'page_fixture.c']},
            api_boundary='VirtualProtect/FlushInstructionCache success and failure substituted; original grouping, writes and rollback run compiled',actual_game_tested=False)
(HERE/'page_results.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
