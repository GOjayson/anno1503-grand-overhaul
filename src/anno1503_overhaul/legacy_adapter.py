"""Isolated legacy preparation and a separately named restoration transaction.

Preparation calls the existing exact-build validators in a fresh interpreter.
It never calls their installers. Prepared data is bound to one game directory,
and the transaction rechecks every original immediately before publication.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Callable


class AdapterError(RuntimeError):
    """Preparation or a guarded installation transaction could not complete."""


Progress = Callable[[str], None]
_SCHEMA = 1
_MAX_REPORT = 4 * 1024 * 1024
_MAX_PAYLOAD = 1024 * 1024 * 1024


def _reparse(path: Path) -> bool:
    info = path.lstat()
    return path.is_symlink() or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _plain_path(path: Path, *, directory: bool = True) -> Path:
    requested = Path(os.path.abspath(path))
    current = Path(requested.anchor)
    for part in requested.parts[1:]:
        current /= part
        if os.path.lexists(current) and _reparse(current):
            raise AdapterError("Symbolic links and junctions are not supported: " + str(current))
    resolved = requested.resolve(strict=True)
    if directory and not resolved.is_dir():
        raise AdapterError("Expected a directory: " + str(requested))
    if not directory and not resolved.is_file():
        raise AdapterError("Expected a regular file: " + str(requested))
    return resolved


def _overlap(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def _unique_json(raw: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise AdapterError("Duplicate key in prepared report: " + str(key))
            result[key] = value
        return result

    if len(raw) > _MAX_REPORT:
        raise AdapterError("Prepared report is too large")
    try:
        value = json.loads(raw, object_pairs_hook=pairs)
    except (ValueError, UnicodeError) as exc:
        raise AdapterError("Prepared report is not valid JSON") from exc
    if not isinstance(value, dict):
        raise AdapterError("Prepared report must be an object")
    return value


@lru_cache(maxsize=1)
def _transactions():
    """Reuse the reviewed transaction engine, without sharing old backup names."""
    path = Path(__file__).resolve().parents[2] / "legacy/world_settings/support/world_transactions.py"
    if not path.is_file():
        raise AdapterError("The checkout's restoration transaction source is missing")
    name = "_anno1503_grand_overhaul_transactions_v1"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AdapterError("Cannot load the restoration transaction engine")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses resolve the declaring module.
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    module.BACKUP = "GrandOverhaul_Backup_v1"
    module.LOCK = ".grand-overhaul-transaction.lock"
    module.VERSION = "1.0-modular-transactions"
    return module


def prepare_edits(kind: str, package: Path, game: Path, output_dir: Path,
                  progress: Progress = lambda _: None) -> dict:
    """Validate a local package/game and prepare payloads outside both folders.

    The package is a trusted local, separately validated package, not arbitrary
    downloaded Python. World preparation retains ``resolve_copy`` and its
    source-only and path-bound marker guards. Output must not already exist.
    """
    if kind not in {"food", "world"}:
        raise AdapterError("Unknown legacy feature: " + str(kind))
    try:
        package = _plain_path(Path(package))
        game = _plain_path(Path(game))
        output = Path(os.path.abspath(output_dir))
        # Check existing ancestors before mkdir or launching the worker.
        ancestor = output
        while not os.path.lexists(ancestor):
            ancestor = ancestor.parent
        _plain_path(ancestor)
        if os.path.lexists(output):
            raise AdapterError("Preparation output already exists; choose a new folder")
        if _overlap(output, game) or _overlap(output, package):
            raise AdapterError("Preparation output must be separate from the game and package")
        worker = Path(__file__).with_name("legacy_worker.py")
        if getattr(sys, 'frozen', False):
            from .frozen_runner import source_script
            worker = source_script('legacy_worker.py')
        progress("Checking " + ("World Settings" if kind == "world" else "Food overhaul") + " inputs…")
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        result = subprocess.run(
            [sys.executable, "-B", str(worker), "--kind", kind,
             "--package", str(package), "--game", str(game), "--output", str(output)],
            cwd=package, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            encoding="utf-8", errors="replace", timeout=600, check=False,
            **options,
        )
        errors = []
        for line in result.stdout.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("event") == "progress":
                progress(str(event.get("message", "")))
            elif event.get("event") == "error":
                errors.append(str(event.get("message", "Legacy validation failed")))
        if result.returncode:
            raise AdapterError("; ".join(errors) if errors else "Legacy validation could not complete")
        report_path = _plain_path(output / "prepared.json", directory=False)
        report = _unique_json(report_path.read_bytes())
        _validated_edits(game, report)
        return report
    except AdapterError:
        raise
    except (OSError, ValueError, TypeError, subprocess.SubprocessError) as exc:
        raise AdapterError("Could not prepare feature changes: " + str(exc)) from exc


def _validated_edits(root: Path, prepared: dict):
    tx = _transactions()
    root = _plain_path(root)
    if (not isinstance(prepared, dict) or type(prepared.get("schema_version")) is not int
            or prepared["schema_version"] != _SCHEMA):
        raise AdapterError("Unsupported prepared transaction")
    if prepared.get("kind") not in {"food", "world"}:
        raise AdapterError("Unsupported prepared feature")
    if not isinstance(prepared.get("state"), str) or not prepared["state"] or len(prepared["state"]) > 128:
        raise AdapterError("Invalid prepared source state")
    try:
        bound = _plain_path(Path(prepared["game_root"]))
        directory = _plain_path(Path(prepared["prepared_dir"]))
    except (KeyError, TypeError) as exc:
        raise AdapterError("Prepared transaction lacks its directory binding") from exc
    if root != bound or _overlap(root, directory):
        raise AdapterError("Prepared transaction belongs to a different game folder")
    report_file = _plain_path(directory / "prepared.json", directory=False)
    if report_file.stat().st_size > _MAX_REPORT:
        raise AdapterError("Prepared report is too large")
    if _unique_json(report_file.read_bytes()) != prepared:
        raise AdapterError("Prepared transaction report changed")
    entries = prepared.get("edits")
    if not isinstance(entries, list) or len(entries) > 4096:
        raise AdapterError("Invalid prepared edit list")
    result, names = [], set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise AdapterError("Invalid prepared edit")
        try:
            name = tx._name(entry["name"])
            tx._path(root, name)  # Reject existing destination reparse paths now.
            if name.casefold() in names:
                raise AdapterError("Duplicate prepared target: " + name)
            names.add(name.casefold())
            if entry["after_file"] != f"after/{index:04d}.bin":
                raise AdapterError("Invalid prepared output path")
            after = _payload(directory, entry["after_file"], entry["after_sha256"])
            if entry["before_file"] is None:
                if any(entry[key] is not None for key in ("before_sha256", "file_size", "offset")):
                    raise AdapterError("Invalid new-file preimage metadata")
                before = None
            else:
                if entry["before_file"] != f"before/{index:04d}.bin":
                    raise AdapterError("Invalid prepared preimage path")
                before = _payload(directory, entry["before_file"], entry["before_sha256"])
                size, offset = entry["file_size"], entry["offset"]
                if type(size) is not int or size < 0:
                    raise AdapterError("Invalid original file size")
                if offset is None:
                    if len(before) != size:
                        raise AdapterError("Prepared whole-file preimage size differs")
                elif (type(offset) is not int or offset < 0 or len(before) != len(after)
                      or offset + len(before) > size):
                    raise AdapterError("Invalid prepared archive region")
            result.append(tx.Edit(name, before, after, entry["file_size"], entry["offset"]))
        except tx.TransactionError as exc:
            raise AdapterError(str(exc)) from exc
        except (KeyError, TypeError) as exc:
            raise AdapterError("Incomplete prepared edit metadata") from exc
    return result


def _payload(directory: Path, name: str, expected: str) -> bytes:
    path = _plain_path(directory / name, directory=False)
    if directory not in path.parents:
        raise AdapterError("Prepared payload leaves its folder")
    if path.stat().st_size > _MAX_PAYLOAD:
        raise AdapterError("Prepared payload is too large")
    value = path.read_bytes()
    if hashlib.sha256(value).hexdigest() != expected:
        raise AdapterError("Prepared payload changed: " + name)
    return value


def install_prepared(root: Path, prepared: dict, source_state: str,
                     progress: Progress = lambda _: None) -> dict:
    """Install one prepared plan with exact full-file backups and rollback."""
    try:
        edits = _validated_edits(Path(root), prepared)
        if not isinstance(source_state, str) or not source_state:
            raise AdapterError("A source-state description is required")
        tx = _transactions()
        return tx.install(_plain_path(Path(root)), edits, source_state, progress=progress)
    except AdapterError:
        raise
    except (OSError, ValueError, TypeError, _transactions().TransactionError) as exc:
        raise AdapterError(str(exc)) from exc


def restore(root: Path, progress: Progress = lambda _: None) -> str:
    """Restore this installer's exact preceding files; retain every backup."""
    tx = _transactions()
    try:
        return tx.restore(_plain_path(Path(root)), progress=progress)
    except (OSError, ValueError, TypeError, tx.TransactionError) as exc:
        raise AdapterError(str(exc)) from exc


def read_manifest(root: Path) -> dict | None:
    """Read only this installer's journal, never a legacy mod's backup."""
    tx = _transactions()
    try:
        return tx.read_manifest(_plain_path(Path(root)))
    except (OSError, ValueError, TypeError, tx.TransactionError) as exc:
        raise AdapterError(str(exc)) from exc
