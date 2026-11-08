"""Build actual dev8 transaction in a failure-injecting, private-page fixture."""
from pathlib import Path
import ctypes
import hashlib
import json
import os
import subprocess
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PACKAGE = ROOT / 'WorldSettings_Work/anno1503_food_world_dev8'
SOURCE = PACKAGE / 'developer/source/engine_resume/ai_loader/install_test_hooks.c'
BLOBS = PACKAGE / 'developer/source/runtime_dev3/runtime_test_blobs.h'
assert SOURCE.is_file() and BLOBS.is_file()
(HERE / 'transaction_source.inc').write_text('#define WS_RUNTIME_BLOBS_HEADER "' + BLOBS.as_posix() + '"\n#include "' + SOURCE.as_posix() + '"\n', encoding='utf-8')
env = os.environ.copy()
env['ZIG_GLOBAL_CACHE_DIR'] = str(HERE / 'zig_global_cache')
env['ZIG_LOCAL_CACHE_DIR'] = str(HERE / 'zig_local_cache')
output = HERE / 'transaction_fixture.dll'
cmd = [str(ROOT / 'WorldSettings_Work/_tools/ziglang/zig.exe'), 'cc', '-shared', '-O2', '-std=c11', '-target', 'x86_64-windows-gnu', str(HERE / 'transaction_fixture.c'), '-o', str(output), '-lbcrypt']
subprocess.run(cmd, check=True, env=env, cwd=HERE)
dll = ctypes.WinDLL(str(output))
dll.transaction_fixture.argtypes = [ctypes.c_uint64, ctypes.c_uint64, ctypes.c_int]
dll.transaction_fixture.restype = ctypes.c_int
assert dll.transaction_group_rejections() == 0
cases = []
def mask(calls):
    return sum(1 << (call - 1) for call in calls)
def run(name, protect=(), flush=(), expected=0):
    rc = dll.transaction_fixture(mask(protect), mask(flush), expected)
    assert rc == 0, (name, rc, dll.transaction_last_result())
    row = dict(name=name, fail_protect_calls=list(protect), fail_flush_calls=list(flush), result=dll.transaction_last_result(),
        protect_calls=dll.transaction_protect_calls(), flush_calls=dll.transaction_flush_calls(),
        before_restored=bool(dll.transaction_before_restored()), protections_restored=bool(dll.transaction_protections_restored()),
        outside_bytes_unchanged=bool(dll.transaction_no_outside_writes()))
    assert row['outside_bytes_unchanged']
    if expected == 0:
        assert row['before_restored'] and row['protections_restored']
    cases.append(row)
run('success', expected=1)
for call in range(1, 5):
    run('primary protect failure ' + str(call), protect=(call,))
for call in range(1, 4):
    run('primary flush failure ' + str(call), flush=(call,))
for call in range(2, 5):
    run('rollback flush failure after primary flush ' + str(call), flush=(1, call), expected=-1)
for call in range(5, 8):
    run('rollback protect failure after restored first page ' + str(call), protect=(4, call), expected=-1)
run('rollback protect after unlock failure', protect=(2, 3), expected=-1)
for call in (4, 5):
    run('rollback protect after restore failure ' + str(call), protect=(3, call), expected=-1)
for call in (4, 5, 6):
    run('rollback flush failure after restored first page ' + str(call), protect=(4,), flush=(call,), expected=-1)
result = dict(passed=True, native_source=str(SOURCE.relative_to(ROOT)), source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    blobs_sha256=hashlib.sha256(BLOBS.read_bytes()).hexdigest(),
    engine_plan_sha256=hashlib.sha256(SOURCE.with_name('engine_patch_plan.h').read_bytes()).hexdigest(),
    fixture_sha256=hashlib.sha256(output.read_bytes()).hexdigest(), cases=cases,
    page_layout='Two patches share first native page; third uses second page with different original protection',
    group_rejections=['cross-page patch', 'overlapping patches', 'zero page size'],
    actual_functions=['wsGroupPages', 'wsApplyPatches', 'wsRestorePatches'],
    rollback_failure_retains_allocations_contract='Native transaction returns -1; installer caller retains executable allocations on that result',
    game_executed=False, game_process_modified=False)
(HERE / 'transaction_test_results.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(dict(passed=True, cases=len(cases), source_sha256=result['source_sha256'], game_process_modified=False)))
