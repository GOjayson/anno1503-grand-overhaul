"""Copy-based transactions for a possible combined food/world installer.

Infrastructure only: this module does not implement or install World Settings.
All target files, including edited archive regions, are staged and published as
whole files. Original whole files are retained for exact restoration. Each file
publication is atomic; the multi-file transaction uses verified rollback and a
recoverable journal. This is not a filesystem-wide atomic commit.

The lock serializes this module's writers. Digest checks detect ordinary races;
arbitrary external writers cannot be locked out by a user-space installer.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import tempfile
import uuid

VERSION = "0.11.0-dev.1-transactions"
BACKUP = "WorldFoodMod_Backup_0_11_Dev1"
LOCK = ".worldfoodmod-0.11-dev1.lock"
SCHEMA = 1


class TransactionError(Exception):
    pass


@dataclass(frozen=True)
class Edit:
    name: str
    before: bytes | None
    after: bytes
    file_size: int | None = None
    offset: int | None = None


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _reparse(path):
    stat = path.lstat()
    return path.is_symlink() or bool(getattr(stat, "st_file_attributes", 0) & 0x400)


def _root(root):
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise TransactionError("Game root is not a directory")
    return root


def _name(name, *, target=True):
    if not isinstance(name, str) or not name or "\\" in name:
        raise TransactionError("Use a nonempty relative path with forward slashes")
    parts = name.split("/")
    if PureWindowsPath(name).drive or name.startswith("/") or any(
        p in {"", ".", ".."} or any(c in '<>:"|?*' or ord(c) < 32 for c in p) or p.endswith((".", " "))
        for p in parts
    ):
        raise TransactionError("Unsafe relative path: " + repr(name))
    if any(re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", p) for p in parts):
        raise TransactionError("Reserved path: " + name)
    if target and ("backup" in parts[0].casefold() or parts[0].casefold() == LOCK.casefold()):
        raise TransactionError("Backup and transaction paths are protected: " + name)
    return name


def _path(root, name, *, target=True):
    _name(name, target=target)
    path = root / name
    current = root
    for part in name.split("/"):
        current = current / part
        if os.path.lexists(current) and _reparse(current):
            raise TransactionError("Reparse/symlink path refused: " + name)
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise TransactionError("Path leaves game root: " + name) from exc
    return path


def _atomic_json(path, record):
    fd, temporary = tempfile.mkstemp(prefix=".journal-", dir=path.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write((json.dumps(record, indent=2) + "\n").encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def _lock(root, action):
    path = _path(root, LOCK, target=False)
    token = uuid.uuid4().hex
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise TransactionError("Another transaction or an interrupted lock exists: " + str(path)) from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({"token": token, "pid": os.getpid(), "action": action}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        yield
    finally:
        if path.is_file() and not _reparse(path):
            try:
                if json.loads(path.read_bytes()).get("token") == token:
                    path.unlink()
            except (OSError, ValueError):
                pass


def _state(path):
    if not os.path.lexists(path):
        return None
    if _reparse(path) or not path.is_file():
        raise TransactionError("Target is not a regular file: " + str(path))
    first = path.stat()
    digest = file_sha(path)
    second = path.stat()
    if (first.st_size, first.st_mtime_ns, first.st_ino) != (second.st_size, second.st_mtime_ns, second.st_ino):
        raise TransactionError("File changed while reading: " + str(path))
    return (second.st_size, digest)


def _before(entry):
    return (entry["before_size"], entry["before_sha256"]) if entry["existed"] else None


def _after(entry):
    return (entry["after_size"], entry["after_sha256"])


def _require(root, entry, allowed):
    actual = _state(_path(root, entry["name"]))
    if actual not in allowed:
        raise TransactionError("Changed since preflight/installation: " + entry["name"])
    return actual


def _load(root):
    directory = _path(root, BACKUP, target=False)
    if not directory.exists():
        return None
    path = _path(directory, "manifest.json", target=False)
    if not path.is_file():
        raise TransactionError("Backup directory has no manifest")
    record = json.loads(path.read_bytes())
    if record.get("schema") != SCHEMA or record.get("version") != VERSION:
        raise TransactionError("Unsupported transaction manifest")
    if record.get("status") not in {"prepared", "installing", "installed", "restoring", "restored", "rolled_back", "rollback_failed"}:
        raise TransactionError("Invalid transaction status")
    names = set()
    for entry in record["edits"]:
        name = _name(entry["name"])
        if name.casefold() in names:
            raise TransactionError("Duplicate target in manifest")
        names.add(name.casefold())
        if type(entry["existed"]) is not bool:
            raise TransactionError("Invalid existence marker")
        for key in ("after_size", "before_size"):
            value = entry[key]
            if key == "before_size" and not entry["existed"] and value is None:
                continue
            if type(value) is not int or value < 0:
                raise TransactionError("Invalid file size in manifest")
        for key in ("after_sha256", "before_sha256"):
            value = entry[key]
            if key == "before_sha256" and not entry["existed"] and value is None:
                continue
            if not isinstance(value, str) or not re.fullmatch("[0-9a-f]{64}", value):
                raise TransactionError("Invalid digest in manifest")
    for name in record.get("created_dirs", []):
        _name(name)
        if not any(entry["name"].startswith(name + "/") for entry in record["edits"]):
            raise TransactionError("Unrelated created-directory record")
    return record


def read_manifest(root):
    return _load(_root(root))


def _save(directory, record):
    _atomic_json(_path(directory, "manifest.json", target=False), record)


def _copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as incoming, target.open("xb") as outgoing:
        shutil.copyfileobj(incoming, outgoing, 1024 * 1024)
        outgoing.flush()
        os.fsync(outgoing.fileno())


def _publish(stage, target, *, new=False):
    if new:
        # Windows rename refuses an existing destination atomically. POSIX
        # rename replaces it, so use an atomic no-overwrite hard link there.
        if os.name == "nt":
            os.rename(stage, target)
        else:
            os.link(stage, target)
    else:
        os.replace(stage, target)


def _restore_file(root, directory, entry, allowed):
    target = _path(root, entry["name"])
    current = _require(root, entry, allowed)
    if current == _before(entry):
        return
    if not entry["existed"]:
        _require(root, entry, allowed)
        target.unlink()
        return
    original = _path(directory, "before/" + entry["name"], target=False)
    if _state(original) != _before(entry):
        raise TransactionError("Backup missing or changed: " + entry["name"])
    fd, temporary = tempfile.mkstemp(prefix=".restore-", dir=target.parent)
    os.close(fd)
    temporary = Path(temporary)
    temporary.unlink()
    try:
        _copy(original, temporary)
        if _state(temporary) != _before(entry):
            raise TransactionError("Restoration copy failed verification")
        _require(root, entry, allowed)
        _publish(temporary, target, new=current is None)
    finally:
        temporary.unlink(missing_ok=True)


def _remove_dirs(root, record):
    for name in reversed(record.get("created_dirs", [])):
        path = _path(root, name)
        if path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass  # Retain a directory if somebody has added other files.


def install(root, edits, source_state, progress=lambda _: None):
    root = _root(root)
    with _lock(root, "install"):
        prior = _load(root)
        if prior and prior["status"] not in {"restored", "rolled_back"}:
            raise TransactionError("An active 0.11 development backup exists; restore it first")
        edits = list(edits)
        if not edits:
            raise TransactionError("No changes to install")
        names = set()
        entries = []
        # Validate every edit and capture whole-file guards before staging.
        for edit in edits:
            name = _name(edit.name)
            if name.casefold() in names:
                raise TransactionError("Duplicate target: " + name)
            names.add(name.casefold())
            if not isinstance(edit.after, bytes) or edit.before is not None and not isinstance(edit.before, bytes):
                raise TransactionError("Edits require immutable byte strings")
            path = _path(root, name)
            state = _state(path)
            if edit.before is None:
                if edit.offset is not None or edit.file_size is not None or state is not None:
                    raise TransactionError("New-file target already exists or has invalid metadata: " + name)
            else:
                if state is None or type(edit.file_size) is not int or state[0] != edit.file_size:
                    raise TransactionError("Original size mismatch: " + name)
                if edit.offset is None:
                    if len(edit.before) != edit.file_size or state[1] != sha(edit.before):
                        raise TransactionError("Original file mismatch: " + name)
                else:
                    if type(edit.offset) is not int or edit.offset < 0 or len(edit.before) != len(edit.after) or edit.offset + len(edit.before) > edit.file_size:
                        raise TransactionError("Invalid fixed-size region: " + name)
                    with path.open("rb") as stream:
                        stream.seek(edit.offset)
                        if stream.read(len(edit.before)) != edit.before:
                            raise TransactionError("Original region mismatch: " + name)
                    if _state(path) != state:
                        raise TransactionError("File changed during region preflight: " + name)
            entries.append(dict(name=name, existed=edit.before is not None,
                                before_size=state[0] if state else None,
                                before_sha256=state[1] if state else None,
                                after_size=None, after_sha256=None, offset=edit.offset))
        # Parent and child target paths cannot both be files.
        if any(a.startswith(b + "/") for a in names for b in names if a != b):
            raise TransactionError("Conflicting parent/child targets")
        pending = Path(tempfile.mkdtemp(prefix=BACKUP + ".pending-", dir=root))
        record = dict(schema=SCHEMA, version=VERSION, source_state=source_state,
                      status="prepared", created_dirs=[], edits=entries)
        directory = root / BACKUP
        published = False
        try:
            for edit, entry in zip(edits, entries):
                progress("Preparing: " + entry["name"])
                _require(root, entry, [_before(entry)])
                original = pending / "before" / entry["name"]
                stage = pending / "after" / entry["name"]
                if entry["existed"]:
                    _copy(_path(root, entry["name"]), original)
                    if _state(original) != _before(entry):
                        raise TransactionError("Original changed during backup: " + entry["name"])
                stage.parent.mkdir(parents=True, exist_ok=True)
                if edit.offset is not None:
                    _copy(original, stage)
                    with stage.open("r+b") as stream:
                        stream.seek(edit.offset)
                        stream.write(edit.after)
                        stream.flush()
                        os.fsync(stream.fileno())
                else:
                    with stage.open("xb") as stream:
                        stream.write(edit.after)
                        stream.flush()
                        os.fsync(stream.fileno())
                entry["after_size"], entry["after_sha256"] = _state(stage)
                _require(root, entry, [_before(entry)])
            # A later preparation callback may have changed an earlier target.
            for entry in entries:
                _require(root, entry, [_before(entry)])
            _save(pending, record)
            if prior:
                number = 1
                while os.path.lexists(root / (BACKUP + ".previous-" + str(number))):
                    number += 1
                os.replace(_path(root, BACKUP, target=False), root / (BACKUP + ".previous-" + str(number)))
            os.rename(pending, directory)
            published = True
        finally:
            if not published:
                # This exact temporary path was created by this invocation.
                pending.resolve().relative_to(root)
                shutil.rmtree(pending, ignore_errors=True)
        touched = []
        try:
            record["status"] = "installing"
            _save(directory, record)
            for entry in entries:
                progress("Installing: " + entry["name"])
                _require(root, entry, [_before(entry)])
                target = _path(root, entry["name"])
                current = root
                for component in entry["name"].split("/")[:-1]:
                    current = current / component
                    if not current.exists():
                        current.mkdir()
                        record["created_dirs"].append(current.relative_to(root).as_posix())
                        _save(directory, record)
                    _path(root, current.relative_to(root).as_posix())
                    if not current.is_dir():
                        raise TransactionError("Target parent is not a directory")
                _require(root, entry, [_before(entry)])
                stage = _path(directory, "after/" + entry["name"], target=False)
                if _state(stage) != _after(entry):
                    raise TransactionError("Prepared output changed: " + entry["name"])
                _publish(stage, target, new=not entry["existed"])
                touched.append(entry)
                if not entry["existed"]:
                    stage.unlink(missing_ok=True)
                _require(root, entry, [_after(entry)])
            record["status"] = "installed"
            _save(directory, record)
        except BaseException as exc:
            failures = []
            for entry in reversed(touched):
                try:
                    _restore_file(root, directory, entry, [_before(entry), _after(entry)])
                    _require(root, entry, [_before(entry)])
                except BaseException as error:
                    failures.append(entry["name"] + ": " + str(error))
            _remove_dirs(root, record)
            record.update(status="rollback_failed" if failures else "rolled_back",
                          error=str(exc), rollback_errors=failures)
            try:
                _save(directory, record)
            except OSError:
                pass
            if failures:
                raise TransactionError("Installation failed; rollback requires recovery: " + "; ".join(failures)) from exc
            raise TransactionError("Installation failed; previous setup restored: " + str(exc)) from exc
        return record


def restore(root, progress=lambda _: None):
    root = _root(root)
    with _lock(root, "restore"):
        record = _load(root)
        if not record:
            raise TransactionError("No compatible 0.11 development backup exists")
        directory = _path(root, BACKUP, target=False)
        # Verify all originals and all current files before the first target write.
        for entry in record["edits"]:
            if entry["existed"]:
                original = _path(directory, "before/" + entry["name"], target=False)
                if _state(original) != _before(entry):
                    raise TransactionError("Backup missing or changed: " + entry["name"])
            _require(root, entry, [_before(entry), _after(entry)])
        record["status"] = "restoring"
        _save(directory, record)
        for entry in reversed(record["edits"]):
            progress("Restoring: " + entry["name"])
            _restore_file(root, directory, entry, [_before(entry), _after(entry)])
            _require(root, entry, [_before(entry)])
        _remove_dirs(root, record)
        record["status"] = "restored"
        _save(directory, record)
        return record["source_state"]
