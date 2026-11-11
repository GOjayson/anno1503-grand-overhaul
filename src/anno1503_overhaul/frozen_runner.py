"""Bounded script dispatch and retained runtime for the standalone Windows beta.

The frozen entry embeds the public release-index digest. External Python code
is accepted only from that verified source tree, or from a beta package whose
complete version-owned recipe has been independently reconstructed.
"""
from __future__ import annotations

import ast
import hashlib
import importlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import runpy
import shutil
import sys
import uuid

RELEASE_KIND = 'anno1503-public-beta-release-files'
RUNTIME_KIND = 'anno1503-retained-beta-worker'
PACKAGE_KIND = 'anno1503-public-beta-world-package'
WORKER = 'OverhaulWorker.exe'
LAUNCHER = 'Anno1503OverhaulSetup.exe'
_trusted_release_sha256 = None
_MAX_JSON = 4 * 1024 * 1024
_MAX_FILES = 32768
_MAX_FILE = 512 * 1024 * 1024
_FLAT_ENTRIES = {'launch_world_settings.pyw', 'activation_once.py'}
_EXTERNAL_NATIVE_IMPORTS = {'heapq', '_heapq', 'queue', '_queue', 'ctypes.wintypes',
    'tkinter', 'tkinter.ttk', 'tkinter.filedialog', 'tkinter.messagebox', 'winreg', 'pefile', 'capstone'}
_LEGACY_IMPORT_FILES = {
    'food_mod.py', 'world_mod.py', 'support/artwork.py', 'support/formats.py',
    'support/transactions.py', 'support/transforms.py', 'support/world_transactions.py',
    'support/package_alias_assets.py', 'support/package_world_assets.py',
    'activation/activate_world_settings.py', 'activation/module_checks.py',
    'activation/pe_exports.py', 'activation/preflight.py', 'activation/preview_snapshot.py',
}
_FLAT_HELPER_IMPORTS = ('launcher_core', 'managed_filesystem', 'managed_processes',
    'client_context', 'native_ready', 'source_readiness', 'world_mod', 'preflight',
    'module_checks', 'pe_exports', 'preview_snapshot', 'activate_world_settings')


def import_source_names(names):
    """Select production Python, including scripts imported from flat packages."""
    selected = []
    for name in names:
        if name.startswith('src/anno1503_overhaul/') and name.endswith('.py'):
            selected.append(name)
        elif name.startswith('legacy/launcher/') and name.rsplit('/', 1)[-1] in (
                _FLAT_ENTRIES | {'launcher_core.py', 'native_ready.py'}):
            selected.append(name)
        else:
            for family in ('food_overhaul', 'world_settings'):
                prefix = 'legacy/' + family + '/'
                if name.startswith(prefix) and name[len(prefix):] in _LEGACY_IMPORT_FILES:
                    selected.append(name)
                    break
    return sorted(selected)


def external_dependency_names(sources):
    """Discover static stdlib/installed dependencies without running helper code."""
    result = set(_EXTERNAL_NATIVE_IMPORTS)
    roots = sys.stdlib_module_names | {'pefile', 'capstone'}
    for source in sources:
        for node in ast.walk(ast.parse(source)):
            names = ([item.name for item in node.names] if isinstance(node, ast.Import)
                     else [node.module] if isinstance(node, ast.ImportFrom) and not node.level else [])
            for name in names:
                if name and name.partition('.')[0] in roots and name != '__future__':
                    result.add(name)
    return sorted(result)


class RunnerError(RuntimeError):
    pass


def application_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _plain(path, *, exists=True):
    if '..' in Path(path).parts:
        raise RunnerError('Parent traversal is not supported in beta helper paths.')
    value = Path(os.path.abspath(path))
    at = Path(value.anchor)
    for piece in value.parts[1:]:
        at /= piece
        if os.path.lexists(at):
            info = at.lstat()
            if at.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise RunnerError('Links and junctions are not supported in beta helper paths.')
    try:
        return value.resolve(strict=exists)
    except OSError as exc:
        raise RunnerError('A required beta file or folder is missing.') from exc


def _name(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value or '\0' in value:
        raise RunnerError('Invalid beta manifest path.')
    parts = value.split('/')
    if PurePosixPath(value).is_absolute() or any(p in ('', '.', '..') for p in parts):
        raise RunnerError('Invalid beta manifest path.')
    return value


def _sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _hash(path):
    path = _plain(path)
    before = path.stat()
    if not path.is_file() or before.st_size > _MAX_FILE:
        raise RunnerError('A beta file exceeds its supported size or is not a regular file.')
    digest = hashlib.sha256()
    consumed = 0
    with path.open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            consumed += len(part)
            if consumed > _MAX_FILE:
                raise RunnerError('A beta file grew beyond its supported size while being checked.')
            digest.update(part)
    after = path.stat()
    if (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
        raise RunnerError('A beta file changed while it was being checked.')
    return digest.hexdigest()


def _json(path, expected=None):
    path = _plain(path)
    if not path.is_file() or path.stat().st_size > _MAX_JSON:
        raise RunnerError('A beta manifest is missing or exceeds its supported size.')
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise RunnerError('Duplicate beta manifest key.')
            result[key] = value
        return result
    before = path.stat()
    with path.open('rb') as stream:
        raw = stream.read(_MAX_JSON + 1)
    if len(raw) > _MAX_JSON:
        raise RunnerError('A beta manifest grew beyond its supported size.')
    after = path.stat()
    if (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
        raise RunnerError('A beta manifest changed while it was being checked.')
    if expected is not None and hashlib.sha256(raw).hexdigest() != expected:
        raise RunnerError('A beta manifest differs from its recorded identity.')
    try:
        value = json.loads(raw, object_pairs_hook=unique)
    except (ValueError, UnicodeError) as exc:
        raise RunnerError('A beta manifest is not valid JSON.') from exc
    if not isinstance(value, dict):
        raise RunnerError('A beta manifest must contain an object.')
    return value


def _files(value):
    if not isinstance(value, dict) or not value or len(value) > _MAX_FILES:
        raise RunnerError('The beta manifest has an invalid file inventory.')
    result = {}
    folded = set()
    for name, digest in value.items():
        _name(name)
        if not _sha(digest) or name.casefold() in folded:
            raise RunnerError('The beta manifest has an invalid digest or duplicate path.')
        folded.add(name.casefold())
        result[name] = digest
    return result


def _check_files(root, files):
    for name, digest in files.items():
        if _hash(root / name) != digest:
            raise RunnerError('A beta helper or payload changed: ' + name)


def _release(root, expected=None):
    root = _plain(root)
    manifest = root / 'release-files.json'
    bound = expected or _trusted_release_sha256
    if bound is None and getattr(sys, 'frozen', False):
        raise RunnerError('This executable has no embedded beta source identity.')
    if bound is not None and (not _sha(bound) or _hash(manifest) != bound):
        raise RunnerError('The beta release index differs from this executable.')
    value = _json(manifest, expected=bound)
    if type(value.get('schema_version')) is not int or value['schema_version'] != 1 or value.get('kind') != RELEASE_KIND:
        raise RunnerError('Unknown beta release index.')
    files = _files(value.get('files'))
    if any(n.startswith(('_internal/', '.local/', 'tools/compiler/')) or n.endswith(('.exe', '.dll', '.scp', '.sze', '.sav')) for n in files):
        raise RunnerError('The public release index contains a forbidden payload.')
    _check_files(root, files)
    for top in ('src', 'legacy', 'provenance'):
        directory = root / top
        if not directory.exists():
            continue
        for folder, dirs, names in os.walk(_plain(directory), followlinks=False):
            for name in dirs + names:
                item = _plain(Path(folder) / name)
                if item.is_file() and item.relative_to(root).as_posix() not in files:
                    raise RunnerError('An unlisted file was found in the beta source tree.')
    return value, files


def source_script(name, root=None) -> Path:
    if not isinstance(name, str) or '/' in name or '\\' in name or ':' in name or Path(name).name != name or not name.endswith('.py'):
        raise RunnerError('Unknown built-in beta helper.')
    if not getattr(sys, 'frozen', False) and root is None:
        return Path(__file__).with_name(name)
    root = _plain(root or application_root())
    unused, files = _release(root)
    relative = 'src/anno1503_overhaul/' + name
    if relative not in files:
        raise RunnerError('The beta helper is not part of this release.')
    return _plain(root / relative)


def configure_worker(root=None, *, trusted_release_sha256=None, expected_worker_sha256=None) -> Path:
    global _trusted_release_sha256
    if trusted_release_sha256 is not None:
        if not _sha(trusted_release_sha256):
            raise RunnerError('The embedded beta release identity is invalid.')
        if _trusted_release_sha256 not in (None, trusted_release_sha256):
            raise RunnerError('The beta release identity changed in this process.')
        _trusted_release_sha256 = trusted_release_sha256
    if not getattr(sys, 'frozen', False) and root is None:
        return Path(sys.executable)
    root = _plain(root or application_root())
    _release(root)
    worker = _plain(root / WORKER)
    if not worker.is_file():
        raise RunnerError('Extract the complete beta ZIP; its helper executable is missing.')
    if expected_worker_sha256 is not None and (not _sha(expected_worker_sha256) or _hash(worker) != expected_worker_sha256):
        raise RunnerError('The beta helper executable differs from this Setup release.')
    sys.executable = str(worker)
    return worker


def _mutable(name):
    return name == 'world/activation_session.json' or (
        name.startswith('launcher/logs/') and name.count('/') == 2 and name.endswith('.jsonl') and len(name) <= 180)


def _closed_tree(root, files, *, manifest_name, mutable=False):
    expected = set(files) | {manifest_name}
    directories = {str(p) for name in expected for p in PurePosixPath(name).parents if str(p) != '.'}
    if mutable:
        directories.add('launcher/logs')
    observed = set()
    for folder, dirs, names in os.walk(root, followlinks=False):
        for name in dirs + names:
            path = _plain(Path(folder) / name)
            relative = path.relative_to(root).as_posix()
            if path.is_dir():
                if relative not in directories:
                    raise RunnerError('An unexpected beta folder was found.')
            elif relative in expected:
                observed.add(relative)
            elif not (mutable and _mutable(relative) and path.stat().st_size <= 16 * 1024 * 1024):
                raise RunnerError('An unexpected beta file was found.')
    if observed != expected:
        raise RunnerError('The beta file inventory is incomplete.')


def validate_package_closure(package_root, expected_manifest_sha256, *, copy_root=None):
    """Check an installation-record binding without accepting new recipe/version pins."""
    if not _sha(expected_manifest_sha256):
        raise RunnerError('The installed beta package has no valid manifest binding.')
    root = _plain(package_root)
    if _hash(root / 'manifest.json') != expected_manifest_sha256:
        raise RunnerError('The installed beta package manifest changed.')
    value = _json(root / 'manifest.json', expected=expected_manifest_sha256)
    if type(value.get('schema_version')) is not int or value['schema_version'] != 1 or value.get('kind') != PACKAGE_KIND:
        raise RunnerError('Unknown installed beta package kind.')
    if copy_root is not None:
        bound_copy = value.get('copy_root')
        if not isinstance(bound_copy, str) or not Path(bound_copy).is_absolute() or _plain(bound_copy, exists=False) != _plain(copy_root, exists=False):
            raise RunnerError('The beta package belongs to another game copy.')
    files = _files(value.get('files'))
    _check_files(root, files)
    _closed_tree(root, files, manifest_name='manifest.json', mutable=True)
    return dict(value, root=str(root), package_manifest_sha256=expected_manifest_sha256)


def _script(script, root):
    script = _plain(script)
    if script.suffix.lower() not in ('.py', '.pyw'):
        raise RunnerError('The beta worker accepts verified Python helper scripts only.')
    if script.is_relative_to(root / 'src'):
        unused, files = _release(root)
        if script.relative_to(root).as_posix() not in files:
            raise RunnerError('This source helper is not listed in the beta release.')
        return script
    if script.parent.name != 'launcher' or script.name not in _FLAT_ENTRIES:
        raise RunnerError('This script is outside the beta helper entry points.')
    package = script.parent.parent
    manifest = _json(package / 'manifest.json')
    if manifest.get('kind') != PACKAGE_KIND:
        raise RunnerError('Only the public beta package can use the standalone worker.')
    _release(root)
    # Import only after the external public tree has matched the executable's
    # embedded release digest. This is the retained version's exact validator.
    from .beta_package import validate_beta_package
    checked = validate_beta_package(package)
    if checked.get('verified') is not True or checked.get('kind') != PACKAGE_KIND:
        raise RunnerError('The beta package recipe was not verified.')
    files = _files(checked.get('files'))
    relative = script.relative_to(package).as_posix()
    if relative not in files or _hash(script) != files[relative]:
        raise RunnerError('This beta launcher script changed.')
    return script


def _child_import_path(script, previous):
    # PyInstaller's first entry is base_library.zip, not a source-script
    # directory. Keep it: replacing it hides bootstrap modules such as heapq.
    return [str(script.parent), *(previous if getattr(sys, 'frozen', False) else previous[1:])]


def import_preflight(script, *, root=None):
    """Import certified helpers without calling their main, game or UI paths."""
    sys.dont_write_bytecode = True
    root = _plain(root or application_root())
    script = _script(script, root)
    source_entry = root / 'src/anno1503_overhaul/legacy_worker.py'
    if script != source_entry and not (script.parent.name == 'launcher' and script.name in _FLAT_ENTRIES):
        raise RunnerError('Import preflight is limited to the three production helper entries.')
    unused, files = _release(root)
    names = external_dependency_names((root / name).read_text(encoding='utf-8-sig')
                                      for name in import_source_names(files))
    old_argv, old_path = sys.argv, sys.path[:]
    loaded = []
    try:
        sys.argv = [str(script)]
        sys.path[:] = _child_import_path(script, old_path)
        for name in names:
            importlib.import_module(name)
        # Exercise both the Python bootstrap implementation and its collected
        # extensions. Merely checking import specifications missed this defect.
        import heapq
        import queue
        values = [3, 1, 2];heapq.heapify(values)
        if [heapq.heappop(values) for unused in range(3)] != [1, 2, 3]:
            raise RunnerError('The frozen heap implementation failed its import check.')
        pending = queue.PriorityQueue();pending.put(2);pending.put(1)
        if (pending.get_nowait(), pending.get_nowait()) != (1, 2):
            raise RunnerError('The frozen queue implementation failed its import check.')
        runpy.run_path(str(script), run_name='__anno1503_import_preflight__')
        if script != source_entry:
            package = script.parent.parent
            helper_dirs = [script.parent, package / 'world/activation', package / 'world', package / 'world/support']
            sys.path[:0] = [str(path) for path in helper_dirs]
            for name in _FLAT_HELPER_IMPORTS:
                expected = next((directory / (name + '.py') for directory in helper_dirs
                                 if (directory / (name + '.py')).is_file()), None)
                if expected is None:
                    raise RunnerError('A production import helper is missing: ' + name)
                module = importlib.import_module(name)
                if _plain(module.__file__) != _plain(expected):
                    raise RunnerError('A production import helper has an unexpected identity: ' + name)
                loaded.append(name)
        return dict(passed=True, script=str(script), entry=script.name, dependency_modules=names,
                    helper_modules=loaded, main_called=False, game_started=False, ui_created=False)
    except ImportError as exc:
        raise RunnerError('A required frozen helper dependency is unavailable: ' + str(exc)) from exc
    finally:
        sys.argv = old_argv;sys.path[:] = old_path


def dispatch(arguments, *, root=None):
    """Run a certified child script with ordinary Python argv and import semantics."""
    sys.dont_write_bytecode = True
    arguments = list(arguments)
    unbuffered = False
    while arguments and arguments[0].startswith('-'):
        flag = arguments.pop(0)
        if flag not in ('-B', '-u', '-Bu', '-uB'):
            raise RunnerError('Unsupported beta worker option.')
        sys.dont_write_bytecode = True
        unbuffered = unbuffered or 'u' in flag
    if not arguments:
        raise RunnerError('A beta helper script is required.')
    root = _plain(root or application_root())
    script = _script(arguments.pop(0), root)
    previous_argv, previous_path = sys.argv, sys.path[:]
    streams = []
    try:
        sys.argv = [str(script), *arguments]
        sys.path[:] = _child_import_path(script, previous_path)
        if unbuffered:
            for name in ('stdout', 'stderr'):
                old = getattr(sys, name)
                if old is None:
                    continue
                try:
                    new = io.TextIOWrapper(os.fdopen(os.dup(old.fileno()), 'wb', buffering=0),
                        encoding=getattr(old, 'encoding', None) or 'utf-8', errors=getattr(old, 'errors', None) or 'replace', write_through=True)
                except (AttributeError, OSError, io.UnsupportedOperation):
                    continue
                streams.append((name, old, new));setattr(sys, name, new)
        runpy.run_path(str(script), run_name='__main__')
        return 0
    finally:
        for name, old, new in streams:
            new.flush();setattr(sys, name, old);new.close()
        sys.argv = previous_argv;sys.path[:] = previous_path


def retain_worker(application, cache_root):
    """Retain a closed version-owned worker/source tree; never replace unknown cache data."""
    application, cache = _plain(application), _plain(cache_root, exists=False)
    if application == cache or application in cache.parents or cache in application.parents:
        raise RunnerError('The retained worker cache must be outside the release folder.')
    unused, public = _release(application)
    files = dict(public)
    files['release-files.json'] = _hash(application / 'release-files.json')
    files[WORKER] = _hash(application / WORKER)
    files[LAUNCHER] = _hash(application / LAUNCHER)
    internal = _plain(application / '_internal')
    for folder, dirs, names in os.walk(internal, followlinks=False):
        for name in dirs + names:
            path = _plain(Path(folder) / name)
            if path.is_file():
                files[path.relative_to(application).as_posix()] = _hash(path)
    if (application / 'licenses').exists():
        for folder, dirs, names in os.walk(_plain(application / 'licenses'), followlinks=False):
            for name in dirs + names:
                path = _plain(Path(folder) / name)
                if path.is_file():
                    files[path.relative_to(application).as_posix()] = _hash(path)
    if (application / 'THIRD_PARTY.txt').is_file():
        files['THIRD_PARTY.txt'] = _hash(application / 'THIRD_PARTY.txt')
    files = _files(files)
    identity = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    destination = cache / ('worker-' + identity[:24])
    if any(len(str(destination / name).encode('utf-16-le')) // 2 >= 248
           for name in files if name.startswith('_internal/')):
        raise RunnerError('The beta runtime cache path is too long for Windows. Choose a shorter cache folder.')
    cache.mkdir(parents=True, exist_ok=True);cache = _plain(cache)
    manifest = dict(schema_version=1, kind=RUNTIME_KIND, release_sha256=files['release-files.json'], files=files)
    encoded = (json.dumps(manifest, sort_keys=True, indent=2) + '\n').encode()
    record = dict(kind=RUNTIME_KIND, runtime_root=str(destination), worker_path=str(destination / WORKER),
                  launcher_path=str(destination / LAUNCHER),
                  manifest_sha256=hashlib.sha256(encoded).hexdigest(), release_sha256=files['release-files.json'])
    if os.path.lexists(destination):
        verify_retained_worker(record)
        return record
    staging = cache / ('.worker-staging-' + uuid.uuid4().hex)
    staging.mkdir(exist_ok=False)
    for name, digest in files.items():
        target = staging / name;target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_plain(application / name), target)
        if _hash(target) != digest:
            raise RunnerError('A beta runtime file changed during retention.')
    with (staging / 'worker-manifest.json').open('xb') as stream:
        stream.write(encoded)
    _check_files(staging, files)
    _closed_tree(staging, files, manifest_name='worker-manifest.json')
    if os.path.lexists(destination):
        raise RunnerError('The retained worker destination changed during preparation.')
    staging.rename(destination)
    verify_retained_worker(record)
    return record


def verify_retained_worker(record) -> Path:
    if not isinstance(record, dict) or record.get('kind') != RUNTIME_KIND or not _sha(record.get('manifest_sha256')):
        raise RunnerError('The retained beta worker binding is invalid.')
    root = _plain(record.get('runtime_root', ''))
    worker = _plain(record.get('worker_path', ''))
    if worker != root / WORKER or _hash(root / 'worker-manifest.json') != record['manifest_sha256']:
        raise RunnerError('The retained beta worker identity changed.')
    manifest = _json(root / 'worker-manifest.json', expected=record['manifest_sha256'])
    if type(manifest.get('schema_version')) is not int or manifest['schema_version'] != 1 or manifest.get('kind') != RUNTIME_KIND:
        raise RunnerError('Unknown retained beta runtime.')
    files = _files(manifest.get('files'))
    if manifest.get('release_sha256') != record.get('release_sha256') or files.get('release-files.json') != record.get('release_sha256'):
        raise RunnerError('The retained beta source binding changed.')
    if WORKER not in files or not any(n.startswith('_internal/') for n in files):
        raise RunnerError('The retained beta runtime is incomplete.')
    if record.get('launcher_path') is not None and (_plain(record['launcher_path']) != root / LAUNCHER or LAUNCHER not in files):
        raise RunnerError('The retained windowless launcher binding changed.')
    if any(n.startswith(('tools/compiler/', '.local/')) for n in files):
        raise RunnerError('The retained beta worker contains unexpected local inputs.')
    _check_files(root, files)
    _closed_tree(root, files, manifest_name='worker-manifest.json')
    return worker


def main(arguments=None, *, trusted_release_sha256=None, expected_worker_sha256=None):
    sys.dont_write_bytecode = True
    try:
        configure_worker(trusted_release_sha256=trusted_release_sha256, expected_worker_sha256=expected_worker_sha256)
        arguments = list(sys.argv[1:] if arguments is None else arguments)
        if arguments[:1] == ['--import-preflight']:
            if len(arguments) != 2:
                raise RunnerError('Import preflight needs one certified helper script.')
            print(json.dumps(import_preflight(arguments[1]), sort_keys=True), flush=True)
            return 0
        if arguments[:1] == ['--installer-cli']:
            from .__main__ import main as installer_cli
            try:
                return installer_cli(arguments[1:])
            except SystemExit as exc:
                return exc.code if isinstance(exc.code, int) else 2
        if arguments == ['--runtime-info']:
            root = application_root()
            _release(root)
            from . import packages, world_options, world_runtime_build
            import pefile
            import capstone
            import tkinter
            dependency_check = import_preflight(source_script('legacy_worker.py', root=root), root=root)
            value = dict(passed=True, frozen=bool(getattr(sys, 'frozen', False)), application_root=str(root),
                module_file=__file__, executable=sys.executable, release_files_sha256=_hash(root / 'release-files.json'),
                module_roots={'packages':str(packages.ROOT), 'world_options':str(world_options.ROOT),
                              'world_runtime_build':str(world_runtime_build.ROOT)},
                pefile_version=getattr(pefile, '__version__', 'unknown'),
                capstone_version=getattr(capstone, '__version__', 'unknown'),
                tcl_version=tkinter.TclVersion, tk_version=tkinter.TkVersion,
                source_tree=(root / 'src/anno1503_overhaul').is_dir(),
                compiler_present=(root / 'tools/compiler/zig.exe').is_file(),
                compiler_license_present=(root / 'tools/compiler/LICENSE').is_file(),
                bytecode_writes_disabled=sys.dont_write_bytecode,
                production_dependency_preflight=dependency_check)
            print(json.dumps(value, sort_keys=True), flush=True)
            return 0
        if arguments:
            return dispatch(arguments)
        from .selector import main as show_installer
        result = show_installer()
        return 0 if result is None else result
    except RunnerError as exc:
        if sys.stderr is not None:
            print('Cannot run the beta helper: ' + str(exc), file=sys.stderr, flush=True)
        else:
            # Only the GUI executable lacks stderr. Console child dispatch does
            # not import Tk merely to report a rejected helper or payload.
            from tkinter import messagebox
            messagebox.showerror('Cannot start Anno 1503 Overhaul', str(exc))
        return 2
