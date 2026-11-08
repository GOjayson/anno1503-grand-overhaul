from pathlib import Path
import os,subprocess
HERE=Path(__file__).resolve().parent
explicit=os.environ.get('ANNO1503_SOURCE_GAME')
ROOT=Path(explicit).resolve(strict=True) if explicit else next(p for p in HERE.parents if (p/'Anno1503.exe').is_file() and (p/'AnnoWelt.dll').is_file())
if not (ROOT/'AnnoGame.dll').is_file():raise ValueError('Explicit original game root is invalid')
zig=ROOT/'WorldSettings_Work/_tools/ziglang/zig.exe'
BUILD=HERE/'_build';BUILD.mkdir(exist_ok=True)
env=os.environ.copy()
for name,child in [('ZIG_GLOBAL_CACHE_DIR','zig_global_cache'),('ZIG_LOCAL_CACHE_DIR','zig_local_cache'),('TEMP','tmp'),('TMP','tmp')]:
 p=BUILD/child;p.mkdir(exist_ok=True);env[name]=str(p)
subprocess.run([str(zig),'cc','-target','x86_64-windows-gnu','-shared','-O2','-Wall','-Wextra','-Werror','-o',str(BUILD/'CertificateFixture.dll'),str(HERE/'certificate_fixture.c'),'-lkernel32'],env=env,check=True,cwd=BUILD)
print('Certificate fixture compiled with -Wall -Wextra -Werror')
