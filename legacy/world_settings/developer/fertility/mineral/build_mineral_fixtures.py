"""Compile focused policy/persistence fixtures; does not build or modify Anno."""
from pathlib import Path
import os,subprocess
HERE=Path(__file__).resolve().parent
GAME=next(p for p in HERE.parents if (p/'Anno1503.exe').is_file() and (p/'WorldSettings_Work/_tools').is_dir())
PACKAGE=next((p for p in HERE.parents if (p/'world_patch.json').is_file()),GAME/'WorldSettings_Work/anno1503_food_world_dev5')
runtime=PACKAGE/'developer/source/engine_resume/ai_food/experiment_runtime'
certificate=PACKAGE/'developer/source/world_certificate'
build=HERE/'_build';build.mkdir(exist_ok=True)
zig=GAME/'WorldSettings_Work/_tools/ziglang/zig.exe'
for name in ['mineral_helper_fixture','mineral_persistence_fixture']:
    subprocess.run([str(zig),'cc','-shared','-O2','-Wall','-Wextra','-Werror','-std=c11',
                    '-I',str(certificate),'-I',str(runtime),'-o',str(build/(name+'.dll')),
                    str(HERE/(name+'.c')),'-lkernel32'],check=True)
print('Both mineral fixtures compiled with warnings treated as errors.')
