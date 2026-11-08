"""Build the development in-process UI, native backend and factory boundary."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
backend = WORK / 'engine_resume/runtime'
command = [str(WORK / '_tools/ziglang/zig.exe'), 'cc', '-target',
           'x86_64-windows-gnu', '-shared', '-O2', '-Wall', '-Wextra', '-Werror',
           '-o', str(HERE / 'AnnoWorldSettings.dll'), str(HERE / 'WorldSettings.c'),
           str(backend / 'world_backend.c'), str(WORK / 'world_factory.c'),
           str(WORK / 'engine_resume/runtime_test/install_test_hooks.c'),
           '-lbcrypt', '-luser32', '-lgdi32', '-lkernel32']
environment = os.environ.copy()
for name, child in [('ZIG_GLOBAL_CACHE_DIR', 'zig_global_cache'),
                    ('ZIG_LOCAL_CACHE_DIR', 'zig_local_cache'), ('TEMP', 'tmp'), ('TMP', 'tmp')]:
    directory = HERE / child
    directory.mkdir(exist_ok=True)
    environment[name] = str(directory)
subprocess.run(command, check=True, cwd=HERE, env=environment)
sources = [HERE / 'WorldSettings.c', backend / 'world_backend.c', backend / 'world_backend.h',
           backend / 'validated_world.inc', backend / 'world_catalogue.h',
           backend / 'world_ship_reserves.h', WORK / 'world_factory.c',
           WORK / 'engine_resume/runtime_test/install_test_hooks.c',
           WORK / 'runtime_test_blobs.h']
result = dict(command=command, sha256=hashlib.sha256((HERE / 'AnnoWorldSettings.dll').read_bytes()).hexdigest(),
              source_sha256={str(p.relative_to(WORK)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
              status='UNFINISHED', backend_registered_in_ui=False,
              explicit_copy_test_backend_available=True)
(HERE / 'build_result.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
