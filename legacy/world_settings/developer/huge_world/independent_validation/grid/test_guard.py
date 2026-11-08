"""Compile and run the actual guard against this test process only."""
from pathlib import Path
import ctypes
import hashlib
import json
import os
import subprocess
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
env = os.environ.copy()
env['ZIG_GLOBAL_CACHE_DIR'] = str(HERE / 'zig_global_cache')
env['ZIG_LOCAL_CACHE_DIR'] = str(HERE / 'zig_local_cache')
zig = ROOT / 'WorldSettings_Work/_tools/ziglang/zig.exe'
output = HERE / 'guard_fixture.dll'
cmd = [str(zig), 'cc', '-shared', '-O2', '-std=c11', '-target', 'x86_64-windows-gnu', str(HERE / 'guard_fixture.c'), '-o', str(output)]
subprocess.run(cmd, check=True, env=env, cwd=HERE)
dll = ctypes.WinDLL(str(output))
dll.test_existing_world_guard.restype = ctypes.c_int
rc = dll.test_existing_world_guard()
assert rc == 0, rc
result = dict(passed=True, native_guard_fixture_return=rc,
    guard_sha256=hashlib.sha256((HERE / 'existing_world_guard.inc').read_bytes()).hexdigest(),
    fixture_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
    cases=['empty process', '2048 server World detected', 'zero-dimension base World detected',
           'vtable-only spill rejected', 'rectangular 1024x512 detected', 'released World no longer detected'],
    process_scope='test process only', game_executed=False, game_process_modified=False)
(HERE / 'guard_test_results.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result))
