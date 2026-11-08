"""Recover inspected stock files into a new independent copy, never the source.

Old Food journals do not form a reliable "restore vanilla" button: the latest
journal may restore another mod. This adapter instead selects only original
bytes whose fingerprints match the reviewed vanilla inputs. It never runs the
old restoration scripts or rewrites their journals.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import uuid


class VanillaError(RuntimeError):
    """The available local inputs cannot establish an exact stock baseline."""


FOOD_SPEC_SHA256 = "aa88900d4f55661720c5927ba7e66cb3dc3dfaa17a55ddedb89d4fb5a61bdae5"
MARKER = ".anno1503-grand-overhaul-copy.json"
# Reviewed stock archive fingerprints from the earliest preserved Fish backup.
# Region hashes alone cannot establish that the remainder of an archive is stock.
VANILLA_ARCHIVE_HASHES = {
    "Anlagen.dat": "bcbaf29c584bbd4d4a892500e28bfe3249c809f2c00a1463ae62804602faaec4",
    "Anlagen.addon": "b2317a5c24b8c9fe796cf40f3fedaefcfa30ad3f185df9e69b2dca6a03d8dd75",
    "Anlagen.classic": "0f356a649cc6eab98e8239d3077882383ddab9e983f3222458d74b83e5bf2c46",
}
VANILLA_UI_HASHES = {
    "ToolGfx/fenster.inc": "e223b51dce9c5f693d21a40cdb0a28a824a8cbf84b147de62ee2730ce469a4c0",
    "ToolGfx/fenster.tex": "8cc32a5e92594d0f915e72329349bb2b915eb5e4ba75afcc22a86da4ef4732b8",
    "ToolGfx/fenster8.inc": "634341be7c876af8b27d673ded2d5d57ca4511d1f11452b384b5a7b40499220a",
    "ToolGfx/fenster8.tex": "f0b97e0c83f5e4fd36c2d3f21555bcbfe1b04eaa05b1e372eb17c8e0597438ec",
    "Languages/Nl/ToolGfx/fenster.inc": "634341be7c876af8b27d673ded2d5d57ca4511d1f11452b384b5a7b40499220a",
    "Languages/Nl/ToolGfx/fenster.tex": "2135e79aa74e906ef25d10cf79ac98fdbd70ab40f23c851685d1ef1a4c5ca777",
}
_BACKUP = re.compile(
    r"(?:FishMod_Backup_0_1|GameMeat_Test_Backup_0_2|FoodMarket_Backup_0_3|"
    r"FoodMod_Backup_0_4|FoodMod_Backup_0_4_1|FoodMod_Backup_0_5)"
    r"(?:\.previous-[1-9][0-9]{0,3})?\Z"
)
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class Recovery:
    name: str
    source_file: Path
    sha256: str
    size: int
    offset: int | None
    file_size: int
    whole_sha256: str
    current_sha256: str


def _pairs(values):
    result = {}
    for key, value in values:
        if key in result:
            raise VanillaError("Duplicate key in local JSON input.")
        result[key] = value
    return result


def _json(path):
    if path.stat().st_size > 5 * 1024 * 1024:
        raise VanillaError("Local JSON input is too large.")
    try:
        return json.loads(path.read_bytes(), object_pairs_hook=_pairs)
    except (ValueError, TypeError) as exc:
        raise VanillaError("Malformed local JSON input.") from exc


def _reparse(path):
    value = path.lstat()
    return path.is_symlink() or bool(getattr(value, "st_file_attributes", 0) & 0x400)


def _root(path):
    candidate = Path(path).absolute()
    for item in (candidate, *candidate.parents):
        if os.path.lexists(item) and _reparse(item):
            raise VanillaError("Linked game folders are not supported.")
    candidate = candidate.resolve(strict=True)
    if not candidate.is_dir():
        raise VanillaError("The game folder is not a directory.")
    return candidate


def _path(root, name):
    if (not isinstance(name, str) or not name or "\\" in name
            or PureWindowsPath(name).drive or name.startswith("/")):
        raise VanillaError("Unsafe file name in local input.")
    parts = name.split("/")
    if any(p in ("", ".", "..") or p.endswith((".", " "))
           or any(c in '<>:"|?*' or ord(c) < 32 for c in p)
           or re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", p)
           for p in parts):
        raise VanillaError("Unsafe file name in local input.")
    candidate = root
    for part in parts:
        candidate = candidate / part
        if os.path.lexists(candidate) and _reparse(candidate):
            raise VanillaError("Linked input or target refused: " + name)
    return candidate


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _file_info(path):
    if not path.is_file() or _reparse(path):
        raise VanillaError("A required file is missing or linked: " + path.name)
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    after = path.stat()
    if (before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_ino, after.st_size, after.st_mtime_ns):
        raise VanillaError("A file changed during verification: " + path.name)
    return after.st_size, digest.hexdigest()


def _spec(food_package):
    package = _root(food_package)
    path = _path(package, "food_patch.json")
    if not path.is_file() or path.stat().st_size > 5 * 1024 * 1024:
        raise VanillaError("Unsupported Food specification for stock recovery.")
    raw = path.read_bytes()
    if _sha(raw) != FOOD_SPEC_SHA256:
        raise VanillaError("Unsupported Food specification for stock recovery.")
    try:
        return json.loads(raw, object_pairs_hook=_pairs)
    except (ValueError, TypeError) as exc:
        raise VanillaError("Malformed Food specification.") from exc


def _items(root, spec):
    result = []
    for item in spec["native_modules"]:
        result.append((item["name"], item["sources"]["vanilla"], None, None,
                       None, item["sources"]["vanilla"]))
    for name, item in spec["files"].items():
        result.append((name, item["sources"]["vanilla"], None, None,
                       None, item["sources"]["vanilla"]))
    for item in spec["archives"]:
        name = item["name"]
        if name not in VANILLA_ARCHIVE_HASHES:
            raise VanillaError("Unsupported archive for exact stock recovery.")
        result.append((name, item["sources"]["vanilla"], item["region_offset"],
                       item["region_size"], item["source_size"], VANILLA_ARCHIVE_HASHES[name]))
    # Enumerate exactly the same optional UI pairs as the Food transformer.
    folders = [root / "ToolGfx"]
    languages = _path(root, "Languages")
    if languages.is_dir():
        for item in sorted(languages.iterdir()):
            if _reparse(item):
                raise VanillaError("Linked language folder refused.")
            if item.is_dir():
                folders.append(item / "ToolGfx")
    for folder in folders:
        for stem in ("fenster", "fenster8"):
            pair = [folder / (stem + suffix) for suffix in (".inc", ".tex")]
            if not any(os.path.lexists(p) for p in pair):
                continue
            for path in pair:
                name = path.relative_to(root).as_posix()
                _path(root, name)
                if name not in VANILLA_UI_HASHES:
                    raise VanillaError("No reviewed stock fingerprint for UI file: " + name)
                result.append((name, VANILLA_UI_HASHES[name], None, None, None,
                               VANILLA_UI_HASHES[name]))
    if not {"ToolGfx/fenster.inc", "ToolGfx/fenster.tex"}.issubset(item[0] for item in result):
        raise VanillaError("The required main-game UI pair is missing.")
    names = [item[0].casefold() for item in result]
    if len(set(names)) != len(names):
        raise VanillaError("Duplicate stock-recovery target.")
    return result


def _backups(root):
    """Read only known historical layouts; journal claims never establish trust."""
    result = []
    for directory in sorted(root.iterdir()):
        if not _BACKUP.fullmatch(directory.name):
            continue
        _path(root, directory.name)
        if not directory.is_dir():
            raise VanillaError("Historical backup is not a directory.")
        for journal_name in ("backup-manifest.json", "manifest.json"):
            journal = _path(directory, journal_name)
            if not journal.exists():
                continue
            record = _json(journal)
            if not isinstance(record, dict):
                raise VanillaError("Malformed historical backup journal.")
            entries = record.get("files", record.get("edits", []))
            if not isinstance(entries, list) or len(entries) > 500:
                raise VanillaError("Malformed historical backup entries.")
            for entry in entries:
                if not isinstance(entry, dict):
                    raise VanillaError("Malformed historical backup entry.")
                name = entry.get("name")
                _path(root, name)
                digest = entry.get("original_sha256", entry.get("before_sha256"))
                if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
                    raise VanillaError("Malformed historical backup digest.")
                offset = entry.get("region_offset", entry.get("offset"))
                if offset is not None and (type(offset) is not int or offset < 0):
                    raise VanillaError("Malformed historical backup region.")
                storage = "files/" if journal_name == "backup-manifest.json" else "regions/"
                result.append((name, digest, offset, _path(directory, storage + name)))
    return result


def _choose_backup(candidates, name, digest, offset, size, whole_digest, file_size):
    for entry_name, entry_digest, entry_offset, path in candidates:
        if entry_name != name or entry_offset != offset:
            continue
        # Some early region journals pin the whole original file rather than
        # the saved region. The reviewed desired hash always decides acceptance.
        if offset is None and entry_digest != digest:
            continue
        actual_size, actual_digest = _file_info(path)
        if offset is not None and (actual_size, actual_digest) == (file_size, whole_digest):
            # Earliest Fish snapshots retained the whole original archive even
            # though their journals describe the modified region.
            return path, actual_size, None, actual_digest
        if actual_digest == digest and (size is None or actual_size == size):
            return path, actual_size, offset, actual_digest
    raise VanillaError("Verified original bytes are unavailable for " + name
                       + ". Select a clean supported game source or retain its original backups.")


def plan_vanilla_recovery(source_game, food_package):
    """Return verified recovery inputs without changing any file."""
    source = _root(source_game)
    spec = _spec(food_package)
    if _file_info(_path(source, "Anno1503.exe"))[1] != spec["exe_sha256"]:
        raise VanillaError("Unsupported Anno 1503 executable.")
    candidates = None
    plan = []
    for name, digest, offset, length, expected_size, whole_digest in _items(source, spec):
        path = _path(source, name)
        file_size, current_digest = _file_info(path)
        if expected_size is not None and file_size != expected_size:
            raise VanillaError("Unsupported archive size: " + name)
        if offset is None:
            current_region = current_digest
        else:
            with path.open("rb") as stream:
                stream.seek(offset)
                region = stream.read(length)
            if len(region) != length:
                raise VanillaError("Incomplete archive region: " + name)
            current_region = _sha(region)
        if current_digest == whole_digest:
            continue
        if offset is not None and current_region == digest:
            raise VanillaError("Archive differs outside the supported mod region: " + name)
        if candidates is None:
            candidates = _backups(source)
        original, original_size, restore_offset, backup_digest = _choose_backup(
            candidates, name, digest, offset, length, whole_digest, file_size)
        plan.append(Recovery(name, original, backup_digest, original_size, restore_offset, file_size,
                             whole_digest, current_digest))
    return plan


def verify_vanilla(game, food_package):
    """Verify every inspected stock input, including whole archive and UI hashes."""
    root = _root(game)
    spec = _spec(food_package)
    if _file_info(_path(root, "Anno1503.exe"))[1] != spec["exe_sha256"]:
        raise VanillaError("Unsupported Anno 1503 executable.")
    verified = {"Anno1503.exe": spec["exe_sha256"]}
    for name, digest, offset, length, expected_size, whole_digest in _items(root, spec):
        size, actual = _file_info(_path(root, name))
        if (expected_size is not None and size != expected_size) or actual != whole_digest:
            raise VanillaError("Copy is not the exact inspected stock baseline: " + name)
        verified[name] = actual
    return {"state": "vanilla", "files": verified}


def _managed_copy(copy_game, source_game):
    target, source = _root(copy_game), _root(source_game)
    if target == source or target in source.parents or source in target.parents:
        raise VanillaError("Stock recovery requires a separate independent game copy.")
    marker = _json(_path(target, MARKER))
    if (not isinstance(marker, dict) or type(marker.get("schema")) is not int
            or marker.get("schema") != 1 or marker.get("managed_copy") is not True
            or marker.get("phase") != "copied"
            or Path(marker.get("copy_root", "")).resolve() != target
            or Path(marker.get("source_root", "")).resolve() != source):
        raise VanillaError("The managed game-copy marker does not match these folders.")
    if os.path.lexists(_path(target, "GrandOverhaul_Backup_v1")):
        raise VanillaError("Recover stock inputs only before the first modular installation.")
    return target, source


def apply_vanilla_recovery(copy_game, source_game, food_package, progress=print):
    """Prepare all stock outputs, then publish them only into a marked new copy.

    Failure during publication can leave this new copy incomplete. Its marker
    must not be promoted to an installed state until this function and the
    installer finish. The original game and historical journals remain intact.
    """
    target, source = _managed_copy(copy_game, source_game)
    plan = plan_vanilla_recovery(source, food_package)
    spec = _spec(food_package)
    # Check every inspected copied input before writing any replacement.
    for name in ["Anno1503.exe", *(item[0] for item in _items(source, spec))]:
        original, copied = _path(source, name), _path(target, name)
        if copied.stat().st_nlink != 1 or os.path.samefile(original, copied):
            raise VanillaError("Game copy shares a file with another location: " + name)
        if _file_info(copied) != _file_info(original):
            raise VanillaError("Game copy changed before stock recovery: " + name)
    stage = target / (".grand-overhaul-vanilla-" + uuid.uuid4().hex)
    stage.mkdir()
    staged = []
    try:
        for index, entry in enumerate(plan):
            progress("Preparing original " + entry.name)
            source_info = _file_info(entry.source_file)
            if source_info != (entry.size, entry.sha256):
                raise VanillaError("Original backup changed after planning: " + entry.name)
            output = stage / f"{index:04d}.bin"
            copied = _path(target, entry.name)
            if entry.offset is None:
                with entry.source_file.open("rb") as incoming, output.open("xb") as outgoing:
                    shutil.copyfileobj(incoming, outgoing, 1024 * 1024)
                    outgoing.flush()
                    os.fsync(outgoing.fileno())
            else:
                with copied.open("rb") as incoming, output.open("xb") as outgoing:
                    shutil.copyfileobj(incoming, outgoing, 1024 * 1024)
                    outgoing.flush()
                    os.fsync(outgoing.fileno())
                data = entry.source_file.read_bytes()
                if len(data) != entry.size or _sha(data) != entry.sha256:
                    raise VanillaError("Original archive region changed during staging.")
                with output.open("r+b") as outgoing:
                    outgoing.seek(entry.offset)
                    outgoing.write(data)
                    outgoing.flush()
                    os.fsync(outgoing.fileno())
            if _file_info(output)[1] != entry.whole_sha256:
                raise VanillaError("Original whole-file verification failed: " + entry.name)
            staged.append((entry, output))
        # All outputs, including large archives, passed before first publication.
        for entry, output in staged:
            copied = _path(target, entry.name)
            if copied.stat().st_nlink != 1 or _file_info(copied)[1] != entry.current_sha256:
                raise VanillaError("Game copy changed during stock recovery: " + entry.name)
            os.replace(output, copied)
        report = verify_vanilla(target, food_package)
        report["recovered_files"] = [entry.name for entry in plan]
        return report
    finally:
        # Only this function's newly-created, path-bound staging directory.
        if (stage.exists() and not _reparse(stage) and stage.resolve().parent == target
                and stage.name.startswith(".grand-overhaul-vanilla-")):
            shutil.rmtree(stage)
