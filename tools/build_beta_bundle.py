"""Build a standalone source-only Windows beta ZIP using installed offline tools.

Nothing is downloaded. Native game files, prepared mod DLLs, saves, baselines
and private evidence are never inputs to this distribution build.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import uuid
import zipfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
PUBLIC_ROOTS = {'src', 'legacy', 'provenance', 'docs', 'assets', 'tools'}
PUBLIC_TOP = {'README.md', 'LICENSE', 'LICENSE.md', 'LICENSE.txt', 'NOTICE', 'NOTICE.md',
              'pyproject.toml', 'INSTALLER.cmd', 'FEATURE_SELECTOR.cmd', 'AGENTS.md'}
FORBIDDEN = {'.dll', '.exe', '.scp', '.sze', '.sav', '.dmp', '.dat', '.zip', '.7z', '.lnk',
             '.pyc', '.pyo', '.pdb', '.obj', '.o', '.a', '.lib', '.key', '.pem', '.pfx'}
RELEASE_KIND = 'anno1503-public-beta-release-files'


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(part)
    return digest.hexdigest()


def plain(path):
    path = Path(path)
    absolute = Path(os.path.abspath(path))
    at = Path(absolute.anchor)
    for piece in absolute.parts[1:]:
        at /= piece
        if os.path.lexists(at) and (at.is_symlink() or getattr(at.lstat(), 'st_file_attributes', 0) & 0x400):
            raise ValueError('Distribution inputs cannot use links or junctions.')
    return path.resolve(strict=True)


def public_inventory(root=ROOT):
    """Select public repository source only; ignored local inputs cannot enter."""
    root = plain(root)
    spec = importlib.util.spec_from_file_location('_beta_public_boundary_check', root / 'tools/check_repository.py')
    checker = importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
    checker.check(root=root)
    raw = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=root)
    names = sorted({n.decode('utf-8') for n in raw.split(b'\0') if n})
    files = {}
    for name in names:
        p = PurePosixPath(name)
        if p.parts[0] not in PUBLIC_ROOTS and name not in PUBLIC_TOP:
            continue
        if p.is_absolute() or any(part in ('', '.', '..', '.local') for part in p.parts) or '\\' in name or ':' in name:
            raise ValueError('Invalid distribution source path.')
        source = plain(root / name)
        if not source.is_relative_to(root) or not source.is_file() or source.suffix.lower() in FORBIDDEN:
            raise ValueError('A distribution source is not an approved public text/artwork file: ' + name)
        with source.open('rb') as stream:
            signature = stream.read(2)
        if signature == b'MZ':
            raise ValueError('Executable payload in the public source selection.')
        files[name] = sha(source)
    required = {'src/anno1503_overhaul/frozen_runner.py', 'src/anno1503_overhaul/legacy_worker.py',
                'tools/beta_entry.py', 'provenance/legacy_import.json', 'README.md'}
    if not required <= files.keys():
        raise ValueError('The public beta source selection is incomplete.')
    return files


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def external_imports(root, public):
    """Collect dependencies from authored and preserved external helper source."""
    location = root / 'src/anno1503_overhaul/frozen_runner.py'
    spec = importlib.util.spec_from_file_location('_beta_import_dependencies', location)
    runtime = importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)
    names = runtime.import_source_names(public)
    dependencies = runtime.external_dependency_names((root / name).read_text(encoding='utf-8-sig') for name in names)
    return dict(source_files=names, modules=dependencies)


def spec_text(entry, source, dependency_root, external=()):
    external = sorted(set(external) | {'queue', '_queue', 'heapq', '_heapq', 'ctypes.wintypes'})
    return f'''# Generated into a fresh ignored build directory.
from pathlib import Path
import hashlib
import sys
sys.path.insert(0,{str(dependency_root)!r})
from PyInstaller.utils.hooks import collect_all, collect_submodules
cap_data,cap_bins,cap_hidden=collect_all('capstone')
a=Analysis([{str(entry)!r}],pathex=[{str(source)!r},{str(dependency_root)!r}],
 binaries=cap_bins,datas=cap_data,
 hiddenimports=collect_submodules('anno1503_overhaul')+cap_hidden+{external!r}+['pefile','tkinter','tkinter.ttk','tkinter.filedialog','tkinter.messagebox'],
 hookspath=[],hooksconfig={{}},runtime_hooks=[],excludes=[],noarchive=False,optimize=1)
pyz=PYZ(a.pure)
worker=EXE(pyz,a.scripts,[],exclude_binaries=True,name='OverhaulWorker',debug=False,
 bootloader_ignore_signals=False,strip=False,upx=False,console=True,contents_directory='_internal')
worker_sha=hashlib.sha256(Path(worker.name).read_bytes()).hexdigest()
gui_entry=Path({str(entry)!r}).with_name('beta_gui_entry.py')
gui_text=Path({str(entry)!r}).read_text(encoding='utf-8')
assert gui_text.count('EXPECTED_WORKER_SHA256 = None')==1
gui_entry.write_text(gui_text.replace('EXPECTED_WORKER_SHA256 = None','EXPECTED_WORKER_SHA256 = '+repr(worker_sha)),encoding='utf-8')
gui_scripts=[(name,str(gui_entry),kind) if Path(path)==Path({str(entry)!r}) else (name,path,kind) for name,path,kind in a.scripts]
assert sum(Path(path)==gui_entry for name,path,kind in gui_scripts)==1
gui=EXE(pyz,gui_scripts,[],exclude_binaries=True,name='Anno1503OverhaulSetup',debug=False,
 bootloader_ignore_signals=False,strip=False,upx=False,console=False,contents_directory='_internal')
coll=COLLECT(gui,worker,a.binaries,a.datas,strip=False,upx=False,name='Anno1503GrandOverhaul')
'''


def _offline_distribution(name, dependency_root):
    """Resolve installed package metadata, including user-site installations."""
    import importlib.metadata as metadata
    matches = [d for d in metadata.distributions(path=[str(dependency_root)])
               if d.metadata.get('Name', '').casefold() == name.casefold()]
    if len(matches) > 1:
        raise RuntimeError('Ambiguous offline third-party metadata: ' + name)
    return matches[0] if matches else metadata.distribution(name)


def _distribution_url(distribution):
    home = distribution.metadata.get('Home-page')
    if home and home.startswith(('https://', 'http://')):
        return home
    for value in distribution.metadata.get_all('Project-URL') or []:
        label, separator, url = value.partition(',')
        if separator and label.strip().casefold() in ('homepage', 'source code') and url.strip().startswith(('https://', 'http://')):
            return url.strip()
    return None


def _license_copy(bundle, dependency_root, *, python_root=None, compiler_root=None, distribution_resolver=None):
    """Keep exact offline license texts and a versioned SHA256 notice inventory."""
    bundle, dependency_root = Path(bundle), Path(dependency_root)
    python_root = Path(python_root or sys.base_prefix)
    compiler_root = Path(compiler_root or bundle / 'tools/compiler')
    resolve = distribution_resolver or (lambda name: _offline_distribution(name, dependency_root))
    components = []
    def retain(component, version, license_name, source, destination, url=None):
        source = plain(source)
        if not source.is_file() or not 1 <= source.stat().st_size <= 4 * 1024 * 1024:
            raise RuntimeError('An offline third-party license is missing or invalid: ' + component)
        target = bundle / destination;target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        digest = sha(target)
        if digest != sha(source):
            raise RuntimeError('A third-party license changed during copying.')
        components.append(dict(component=component, version=version, license=license_name,
                               source_url=url, license_files={destination:digest}))

    retain('Python', sys.version.split()[0], 'Python Software Foundation License Agreement and included notices',
           python_root / 'LICENSE.txt', 'licenses/Python.txt', 'https://www.python.org/psf/')
    for package, component, license_name, destination in (
        ('pyinstaller', 'PyInstaller bootloader', 'GPLv2-or-later with Bootloader Exception', 'licenses/PyInstaller.txt'),
        ('pefile', 'pefile', 'MIT', 'licenses/pefile.txt'),
        ('capstone', 'Capstone', 'BSD 3-Clause and included notices', 'licenses/Capstone.txt'),
    ):
        distribution = resolve(package)
        texts = [Path(distribution.locate_file(p)) for p in distribution.files or []
                 if Path(str(p)).name.casefold().startswith(('license', 'copying'))]
        if not texts:
            raise RuntimeError('The installed third-party package has no license file: ' + package)
        texts.sort(key=lambda p: (p.name.casefold() != 'copying.txt' if package == 'pyinstaller' else False, str(p)))
        if package == 'pyinstaller' and b'Bootloader Exception' not in plain(texts[0]).read_bytes():
            raise RuntimeError('The installed PyInstaller license omits its Bootloader Exception.')
        retain(component, distribution.version, license_name, texts[0], destination, _distribution_url(distribution))
        for index, extra in enumerate(texts[1:], 1):
            relative = 'licenses/' + package + '/additional-' + str(index) + '-' + extra.name
            target = bundle / relative;target.parent.mkdir(parents=True, exist_ok=True);shutil.copyfile(plain(extra), target)
            components[-1]['license_files'][relative] = sha(target)
    tcl = (bundle / '_internal/_tcl_data/init.tcl').read_text(encoding='utf-8')
    tk = (bundle / '_internal/_tk_data/tk.tcl').read_text(encoding='utf-8')
    tcl_version = re.search(r'package require -exact Tcl\s+([0-9.]+)', tcl)
    tk_version = re.search(r'package require -exact Tk\s+([0-9.]+)', tk)
    if not tcl_version or not tk_version:
        raise RuntimeError('The bundled Tcl/Tk runtime versions could not be read.')
    retain('Tcl/Tk', tcl_version[1] + ' / ' + tk_version[1], 'Bundled permissive Tcl/Tk terms',
           bundle / '_internal/_tk_data/license.terms', 'licenses/TclTk.txt')
    retain('Zig compiler', '0.16.0', 'MIT (Expat)', compiler_root / 'LICENSE', 'licenses/Zig.txt', 'https://ziglang.org/')
    value = dict(schema_version=1, kind='anno1503-beta-third-party-notices', components=components)
    record = bundle / 'licenses/third-party-manifest.json';record.write_bytes(encoded(value))
    lines = ['Third-party notices for Anno 1503 Grand Overhaul beta', '',
             'The full release bundles the following offline tools and runtimes.',
             'Exact license texts are retained at the paths below; this notice does not replace them.',
             'The retained game launcher omits the compiler but keeps the notices.', '']
    for item in components:
        lines += [item['component'] + ' ' + item['version'], 'License: ' + item['license'],
                  'Texts: ' + ', '.join(item['license_files'])]
        if item['source_url']:
            lines.append('Primary project reference: ' + item['source_url'])
        lines.append('')
    lines += ['Exact license SHA256 values: licenses/third-party-manifest.json',
              'No Anno game assets, modified game DLLs or save files are distributed.']
    (bundle / 'THIRD_PARTY.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return dict(manifest_sha256=sha(record), components=components)


def build(*, output=None, compiler=None, dependencies=None):
    if os.name != 'nt':
        raise RuntimeError('Standalone beta bundles must be built and checked on Windows.')
    import importlib.metadata
    if importlib.metadata.version('pyinstaller') != '6.16.0':
        raise RuntimeError('Use the reviewed installed PyInstaller 6.16.0.')
    compiler = plain(compiler or ROOT / '.local/toolchain/ziglang')
    dependency_root = plain(dependencies or ROOT / '.local/toolchain/world-options-validation')
    for required in (compiler / 'zig.exe', compiler / 'LICENSE', dependency_root / 'capstone', dependency_root / 'pefile.py'):
        plain(required)
    version = subprocess.check_output([str(compiler / 'zig.exe'), 'version'], text=True).strip()
    if version != '0.16.0':
        raise RuntimeError('Use the reviewed Zig 0.16.0 compiler.')
    releases = ROOT / '.local/releases';releases.mkdir(parents=True, exist_ok=True)
    requested = Path(output or releases / ('beta-bundle-' + uuid.uuid4().hex))
    if '..' in requested.parts:
        raise ValueError('The beta output cannot use parent traversal.')
    output = Path(os.path.abspath(requested))
    if output.exists() or not output.is_relative_to(releases.resolve()) or output == releases.resolve():
        raise ValueError('Use a new output folder beneath ignored .local/releases/.')
    parent = plain(output.parent)
    if not parent.is_relative_to(releases.resolve()):
        raise ValueError('The resolved beta output leaves the local release workspace.')
    output = parent / output.name;output.mkdir(exist_ok=False)
    public = public_inventory()
    imports = external_imports(ROOT, public)
    index = encoded(dict(schema_version=1, kind=RELEASE_KIND, files=public))
    index_sha = hashlib.sha256(index).hexdigest()
    entry = output / 'beta_entry.py'
    text = (ROOT / 'tools/beta_entry.py').read_text(encoding='utf-8')
    marker = 'TRUSTED_RELEASE_FILES_SHA256 = None'
    if text.count(marker) != 1:
        raise ValueError('The beta entry identity anchor changed.')
    entry.write_text(text.replace(marker, 'TRUSTED_RELEASE_FILES_SHA256 = ' + repr(index_sha)), encoding='utf-8')
    specification = output / 'beta.spec'
    specification.write_text(spec_text(entry, ROOT / 'src', dependency_root, imports['modules']), encoding='utf-8')
    result = subprocess.run([sys.executable, '-B', '-m', 'PyInstaller', '--noconfirm', '--distpath', str(output / 'dist'),
                             '--workpath', str(output / 'build'), str(specification)], capture_output=True, text=True)
    (output / 'freeze.log').write_text(result.stdout + result.stderr, encoding='utf-8')
    if result.returncode:
        raise RuntimeError('Freezing the beta failed; the private build log is preserved in ' + str(output))
    if public_inventory() != public:
        raise RuntimeError('Public source changed during freezing. The candidate was retained without publication.')
    bundle = plain(output / 'dist/Anno1503GrandOverhaul')
    for name, expected in public.items():
        source = plain(ROOT / name)
        if sha(source) != expected:
            raise RuntimeError('A public source changed during bundle assembly.')
        target = bundle / name;target.parent.mkdir(parents=True, exist_ok=True);shutil.copyfile(source, target)
    (bundle / 'release-files.json').write_bytes(index)
    # The only non-Python runtime native tool is the licensed third-party
    # compiler. No prepared World DLL or original game file is selected here.
    compiler_target = bundle / 'tools/compiler';compiler_target.mkdir()
    for source in (compiler / 'zig.exe', compiler / 'LICENSE'):
        shutil.copyfile(source, compiler_target / source.name)
    for folder, dirs, names in os.walk(plain(compiler / 'lib'), followlinks=False):
        for name in dirs + names:
            plain(Path(folder) / name)
    shutil.copytree(compiler / 'lib', compiler_target / 'lib')
    notices = _license_copy(bundle, dependency_root)
    inventory = {p.relative_to(bundle).as_posix(): sha(p) for p in sorted(bundle.rglob('*')) if p.is_file()}
    (output / 'bundle-files.json').write_bytes(encoded(dict(schema_version=1, files=inventory)))
    archive = output / 'Anno1503GrandOverhaul-Beta.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zipped:
        for name in sorted(inventory):
            zipped.write(bundle / name, 'Anno1503GrandOverhaul/' + name)
    report = dict(passed=True, status='candidate', game_executed=False, original_game_assets_included=False, source_files=len(public),
        external_import_source_files=len(imports['source_files']), external_import_modules=imports['modules'],
        release_files_sha256=index_sha, bundle_root=str(bundle), archive=str(archive), archive_sha256=sha(archive),
        compiler_version=version, compiler_sha256=sha(compiler / 'zig.exe'), bundle_files=len(inventory),
        third_party_notices_manifest_sha256=notices['manifest_sha256'],
        setup=str(bundle / 'Anno1503OverhaulSetup.exe'), worker=str(bundle / 'OverhaulWorker.exe'))
    (output / 'BUILD_RESULT.json').write_bytes(encoded(report))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--compiler', type=Path)
    parser.add_argument('--dependencies', type=Path)
    args = parser.parse_args()
    print(json.dumps(build(output=args.output, compiler=args.compiler, dependencies=args.dependencies), indent=2))


if __name__ == '__main__':
    main()
