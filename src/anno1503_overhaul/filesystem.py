"""Bounded, independent game-copy creation. Never shares writable game files."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import shutil
import stat
import uuid


class CopyError(RuntimeError):
    pass


COPY_MARKER = '.anno1503-grand-overhaul-copy.json'
GAME_DIRECTORIES = frozenset({
    'ahe', 'bonuscontent', 'data', 'help', 'languages', 'music', 'scenes',
    'support', 'textures', 'toolgfx', 'videos',
})
GAME_EXTENSIONS = frozenset({'.dll', '.exe', '.dat', '.addon', '.classic', '.gfx', '.edit'})
GAME_FILES = frozenset({'readme.txt', 'instanthelplinks.txt', 'uplay_install.manifest', 'uplay_install.state'})
EXCLUDED_EXTENSIONS = frozenset({'.sav', '.dmp', '.log', '.tmp', '.bak', '.py', '.pyw', '.cmd', '.ps1'})


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def is_reparse(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400)


def checked_path(value: Path, *, exists: bool = True) -> Path:
    """Check the requested spelling before resolve can conceal junctions."""
    path = Path(os.path.abspath(value))
    for parent in (*reversed(path.parents), path):
        if os.path.lexists(parent) and is_reparse(parent):
            raise CopyError('Linked folders or files are not supported: ' + str(parent))
    result = path.resolve(strict=exists)
    return result


def relative_name(value: str) -> str:
    if not isinstance(value, str) or not value or '\\' in value or PureWindowsPath(value).drive:
        raise CopyError('Invalid relative game path.')
    parts = value.split('/')
    if value.startswith('/') or any(
        p in ('', '.', '..') or p.endswith((' ', '.'))
        or any(c in '<>:"|?*' or ord(c) < 32 for c in p) for p in parts
    ):
        raise CopyError('Invalid relative game path: ' + repr(value))
    import re
    if any(re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', p) for p in parts):
        raise CopyError('Reserved game path: ' + value)
    return value


def safe_child(root: Path, name: str, *, exists: bool = False) -> Path:
    root = checked_path(root)
    path = checked_path(root / relative_name(name), exists=exists)
    if not path.is_relative_to(root):
        raise CopyError('Game path leaves its selected folder.')
    return path


def atomic_json(path: Path, value: dict) -> None:
    checked_path(path, exists=False)
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(value, stream, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def validate_roots(source: Path, destination: Path, repo: Path | None = None, *, source_exists: bool = True) -> tuple[Path, Path]:
    source = checked_path(source, exists=source_exists)
    destination = checked_path(destination, exists=False)
    if ((source_exists and not source.is_dir()) or source == destination
            or source.is_relative_to(destination) or destination.is_relative_to(source)):
        raise CopyError('Choose a separate modded-copy folder outside the original game folder.')
    if repo is not None:
        repo = checked_path(repo)
        if destination == repo or repo.is_relative_to(destination):
            raise CopyError('The modded copy cannot replace or contain the development repository.')
        if destination.is_relative_to(repo) and not destination.is_relative_to(repo / '.local'):
            raise CopyError('Game copies inside the repository belong in its ignored .local folder.')
    return source, destination


def game_inventory(source: Path) -> list[dict]:
    """Copy stock game locations; omit existing mods, workspaces, logs and backups."""
    source = checked_path(source)
    result = []
    for top in sorted(source.iterdir(), key=lambda p: p.name.casefold()):
        allowed_directory = top.name.casefold() in GAME_DIRECTORIES
        allowed_file = top.suffix.casefold() in GAME_EXTENSIONS or top.name.casefold() in GAME_FILES
        if not (allowed_directory or allowed_file):
            continue
        if is_reparse(top):
            raise CopyError('A game input is a linked file or folder: ' + top.name)
        if top.is_dir():
            if not allowed_directory:
                continue
            files = []
            for folder, dirs, names in os.walk(top, followlinks=False):
                for item in dirs + names:
                    child = Path(folder) / item
                    if is_reparse(child):
                        raise CopyError('A game input is a linked file or folder: ' + str(child.relative_to(source)))
                dirs[:] = [name for name in dirs if not (
                    'backup' in name.casefold() or name.casefold() in {'logs', '__pycache__', '.git', '.local'}
                )]
                files.extend(Path(folder) / name for name in names
                             if Path(name).suffix.casefold() not in EXCLUDED_EXTENSIONS)
        else:
            files = [top] if top.is_file() and allowed_file else []
        for path in files:
            name = relative_name(path.relative_to(source).as_posix())
            info = path.stat()
            if not stat.S_ISREG(info.st_mode):
                raise CopyError('Game input is not a regular file: ' + name)
            result.append(dict(name=name, size=info.st_size, mtime_ns=info.st_mtime_ns))
    if not any(item['name'].casefold() == 'anno1503.exe' for item in result):
        raise CopyError('Anno1503.exe was not found in the selected game folder.')
    keys = [item['name'].casefold() for item in result]
    if len(set(keys)) != len(keys):
        raise CopyError('Game inputs contain conflicting Windows filenames.')
    return sorted(result, key=lambda x: x['name'].casefold())


def read_copy_marker(root: Path) -> dict:
    root = checked_path(root)
    path = safe_child(root, COPY_MARKER, exists=True)
    if path.stat().st_size > 64 * 1024:
        raise CopyError('Invalid modded-copy record.')
    marker = json.loads(path.read_bytes())
    if not isinstance(marker, dict):
        raise CopyError('Invalid modded-copy record.')
    if (type(marker.get('schema')) is not int or marker.get('schema') != 1 or marker.get('managed_copy') is not True
            or not isinstance(marker.get('copy_root'), str) or not isinstance(marker.get('source_root'), str)
            or checked_path(Path(marker.get('copy_root', '')), exists=False) != root
            or not marker.get('source_root')):
        raise CopyError('This folder is not a matching Grand Overhaul copy.')
    if not Path(marker['source_root']).is_absolute():
        raise CopyError('The original game path in this copy is invalid.')
    source, target = validate_roots(Path(marker['source_root']), root, source_exists=False)
    if marker.get('phase') not in {'copying', 'copied', 'vanilla', 'installed', 'restored', 'failed'}:
        raise CopyError('Unknown modded-copy state.')
    if source == target:
        raise CopyError('The original game folder cannot be a modded copy.')
    return marker


def update_copy_marker(root: Path, **fields) -> dict:
    marker = read_copy_marker(root)
    if set(fields) & {'schema', 'managed_copy', 'source_root', 'copy_root', 'source_exe_sha256'}:
        raise CopyError('The identity of a modded copy cannot be changed.')
    marker.update(fields)
    atomic_json(root / COPY_MARKER, marker)
    return marker


def clone_game(source: Path, destination: Path, *, repo: Path | None = None, progress=lambda _: None) -> dict:
    source, destination = validate_roots(source, destination, repo)
    if os.path.lexists(destination):
        raise CopyError('The copy folder already exists. Select its existing managed copy, or choose a new empty location.')
    inventory = game_inventory(source)
    required = sum(item['size'] for item in inventory)
    ancestor = destination.parent
    while not ancestor.exists():
        ancestor = ancestor.parent
    # Leave room for native patch backups, whole-file archive staging and UI files.
    if shutil.disk_usage(ancestor).free < required + 2 * 1024**3:
        raise CopyError('There is not enough free space for the game copy and restoration files.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    checked_path(destination.parent)
    destination.mkdir()
    marker = dict(schema=1, managed_copy=True, source_root=str(source), copy_root=str(destination),
                  source_exe_sha256=file_sha(source / 'Anno1503.exe'), phase='copying',
                  created_at=datetime.now(timezone.utc).isoformat())
    atomic_json(destination / COPY_MARKER, marker)
    copied = []
    try:
        for index, item in enumerate(inventory, 1):
            progress(f"Copying game files ({index}/{len(inventory)}): {item['name']}")
            original = safe_child(source, item['name'], exists=True)
            before = original.stat()
            if (before.st_size, before.st_mtime_ns) != (item['size'], item['mtime_ns']):
                raise CopyError('A game input changed during copying: ' + item['name'])
            target = safe_child(destination, item['name'])
            target.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            with original.open('rb') as incoming, target.open('xb') as outgoing:
                for block in iter(lambda: incoming.read(1024 * 1024), b''):
                    digest.update(block)
                    outgoing.write(block)
                outgoing.flush()
                os.fsync(outgoing.fileno())
            after = original.stat()
            if ((before.st_size, before.st_mtime_ns, before.st_ino) !=
                    (after.st_size, after.st_mtime_ns, after.st_ino)
                    or file_sha(target) != digest.hexdigest()):
                raise CopyError('A game input changed or could not be copied exactly: ' + item['name'])
            if os.path.samefile(original, target):
                raise CopyError('Game copies must not share writable files with the original.')
            copied.append(dict(name=item['name'], size=item['size'], sha256=digest.hexdigest()))
        atomic_json(destination / '.grand-overhaul-copy-inventory.json', dict(schema=1, files=copied))
        return update_copy_marker(destination, phase='copied', copied_files=len(copied), copied_bytes=required)
    except BaseException:
        update_copy_marker(destination, phase='failed')
        raise


@contextmanager
def operation_lock(root: Path):
    """Serialize preparation and restore, in addition to the native-file journal lock."""
    root = checked_path(root)
    lock = safe_child(root, '.grand-overhaul-operation.lock')
    token = uuid.uuid4().hex
    try:
        with lock.open('x', encoding='utf-8') as stream:
            json.dump(dict(pid=os.getpid(), token=token), stream)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise CopyError('Another installer operation or an interrupted operation needs attention in this copy.') from exc
    try:
        yield
    finally:
        try:
            if not is_reparse(lock) and json.loads(lock.read_bytes()).get('token') == token:
                lock.unlink()
        except (OSError, ValueError, TypeError):
            pass  # Preserve an unrelated or corrupted lock for explicit recovery.
