"""Build only the plant helper fixture with the local verified Zig toolchain."""
from pathlib import Path
import os,subprocess
HERE=Path(__file__).resolve().parent
GAME=next(p for p in HERE.parents if (p/'Anno1503.exe').is_file())
PACKAGE=next((p for p in HERE.parents if (p/'developer/source/engine_audit/audit.py').is_file()),GAME/'WorldSettings_Work/anno1503_food_world_dev5')
OUT=HERE/'_build';OUT.mkdir(exist_ok=True)
env=os.environ.copy()
for name,directory in [('ZIG_GLOBAL_CACHE_DIR','global-cache'),('ZIG_LOCAL_CACHE_DIR','local-cache')]:
    path=OUT/directory;path.mkdir(exist_ok=True);env[name]=str(path)
subprocess.run([str(GAME/'WorldSettings_Work/_tools/ziglang/zig.exe'),'cc','-target','x86_64-windows-gnu',
                '-shared','-O2','-Wall','-Wextra','-Werror','-I',str(PACKAGE/'developer/source/engine_resume/ai_food/experiment_runtime'),
                str(HERE/'plant_fixture.c'),'-o',str(OUT/'plant_fixture.dll')],check=True,env=env)
print('Plant fixture compiled; no game files changed.')
