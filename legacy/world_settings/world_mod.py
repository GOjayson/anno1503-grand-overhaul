#!/usr/bin/env python3
"""UNFINISHED Food 0.5 + World Settings development installer; marked copies only."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
PACKAGE = Path(__file__).resolve().parent
sys.path.insert(0, str(PACKAGE / "support"))
import food_mod as food
import world_transactions as tx
import package_alias_assets as alias_assets
import package_world_assets as world_assets

VERSION = "0.11.0-dev.1"
FINAL_STATE = "food-world-0.11.0-dev.1"
MARKER = ".anno1503-worldsettings-test-copy.json"


def assert_copy(root, spec):
    """A copied marker cannot authorize writes to its original or a different copy."""
    requested = Path(root)
    try:
        root = requested.resolve(strict=True)
    except FileNotFoundError as exc:
        raise food.fm.ModError("Development game copy folder was not found: " + str(requested)) from exc
    tx._path(root, MARKER)
    path = root / MARKER
    if not path.is_file():
        raise food.fm.ModError("UNFINISHED: only an explicitly marked development game copy is allowed")
    marker = json.loads(path.read_bytes())
    source = Path(marker.get("source_root", "")).resolve()
    if (marker.get("schema") != 1 or marker.get("development_copy") is not True
            or Path(marker.get("copy_root", "")).resolve() != root
            or source != Path(spec["original_game_root"]).resolve()
            or source == root or root == Path(spec["original_game_root"]).resolve()
            or marker.get("source_exe_sha256") != spec["exe_sha256"]):
        raise food.fm.ModError("Development-copy marker does not match this copy; original game root is forbidden")
    return root


def resolve_copy(spec, root=None, package=None):
    """Find an existing marked copy without trusting the extraction layout.

    Explicit targets never fall back. Discovery is bounded to the conventional
    sibling/work folders and the inspected source's work folder; each marked
    candidate must pass the same copy/source/executable binding as installation.
    Two different matching copies require an explicit choice.
    """
    if spec.get("repository_source_snapshot", {}).get("source_only") is True:
        raise food.fm.ModError("Source-only repository snapshot cannot install or activate. Build a reviewed local package using the repository tools first.")
    if root is not None:
        return assert_copy(root, spec)
    package = PACKAGE if package is None else Path(package)
    source = Path(spec["original_game_root"])
    candidates = [package.parent / "game_copy",
                  package.parent / "WorldSettings_Work" / "game_copy",
                  source / "WorldSettings_Work" / "game_copy"]
    checked, matches = {}, {}
    for candidate in candidates:
        resolved = candidate.resolve()
        key = os.path.normcase(str(resolved))
        if key in checked:
            continue
        checked[key] = resolved
        if not os.path.lexists(resolved / MARKER):
            continue
        try:
            valid = assert_copy(resolved, spec)
        except (OSError, ValueError, TypeError, KeyError, food.fm.ModError, tx.TransactionError) as exc:
            raise food.fm.ModError("Invalid development-copy marker at " + str(resolved) + ": " + str(exc)) from exc
        matches[os.path.normcase(str(valid))] = valid
    if len(matches) == 1:
        return next(iter(matches.values()))
    if matches:
        raise food.fm.ModError("Multiple matching marked game copies were found; use --game-dir to select one: "
                               + "; ".join(str(path) for path in matches.values()))
    raise food.fm.ModError("No matching marked development game copy was found. Checked: "
                           + "; ".join(str(path) for path in checked.values())
                           + ". Keep the existing marked copy, or select it with --game-dir. The original game folder is never used as a fallback.")


def require_amd64(data, name):
    try:
        pe = struct.unpack_from("<I", data, 60)[0]
        good = (data[:2] == b"MZ" and data[pe:pe+4] == b"PE\0\0"
                and struct.unpack_from("<H", data, pe+4)[0] == 0x8664
                and struct.unpack_from("<H", data, pe+24)[0] == 0x20B)
    except (struct.error, IndexError):
        good = False
    if not good:
        raise food.fm.ModError("Expected inspected AMD64 PE32+ module: " + name)


def assert_game_closed():
    # Toolhelp reads process names directly; tasklist can fail on restricted
    # Windows hosts even when a process snapshot is available. Fail closed if
    # enumeration itself fails. No process is terminated or modified.
    if os.name != "nt":
        return
    import ctypes
    from ctypes import wintypes
    class Entry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
                    ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260)]
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    api.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    for name in ["Process32FirstW", "Process32NextW"]:
        fn = getattr(api, name)
        fn.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
        fn.restype = wintypes.BOOL
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.CloseHandle.restype = wintypes.BOOL
    snapshot = api.CreateToolhelp32Snapshot(2, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        raise food.fm.ModError("Could not enumerate game processes: " + str(ctypes.get_last_error()))
    try:
        entry = Entry()
        entry.dwSize = ctypes.sizeof(entry)
        more = api.Process32FirstW(snapshot, ctypes.byref(entry))
        while more:
            if entry.szExeFile.casefold() == "anno1503.exe":
                raise food.fm.ModError("Close Anno 1503 before installing or restoring this copy")
            more = api.Process32NextW(snapshot, ctypes.byref(entry))
        error = ctypes.get_last_error()
        if error != 18:  # ERROR_NO_MORE_FILES is the expected complete snapshot.
            raise food.fm.ModError("Incomplete game process enumeration: " + str(error))
    finally:
        api.CloseHandle(snapshot)


def payloads(spec):
    if spec.get("version") != VERSION or spec.get("status") != "UNFINISHED":
        raise food.fm.ModError("Installer and development specification differ")
    alias_hashes=alias_assets.data_payload_hashes()
    world_hashes=world_assets.data_payload_hashes()
    if set(alias_hashes)&set(world_hashes):
        raise food.fm.ModError("World data payload policies overlap")
    data_hashes={**alias_hashes,**world_hashes}
    native_names={"native/AnnoFrame.food05.dll","native/AnnoFrame.world.dll",
                  "native/AnnoScene.source.dll","native/AnnoScene.world.dll",
                  "native/AnnoWelt.source.dll","native/AnnoWelt.world.dll",
                  "native/AnnoWorldSettings.dll","native/CompLogic.food-ai.dll",
                  "native/CompLogicClassic.food-ai.dll"}
    if spec.get("data_payloads")!=data_hashes or set(spec["payloads"])!=native_names|set(data_hashes):
        raise food.fm.ModError("Unexpected native or pirate-island data payload manifest")
    result = {}
    for name, digest in spec["payloads"].items():
        path = tx._path(PACKAGE, name)
        data = path.read_bytes()
        if food.fm.sha(data) != digest:
            raise food.fm.ModError("Package payload fingerprint differs: " + name)
        if name in data_hashes:
            (alias_assets if name in alias_hashes else world_assets).validate_data_payload(name,data)
        else:
            require_amd64(data, name)
        result[name] = data
    for name, overlay in spec["native_overlays"].items():
        if food.fm.sha(result[overlay["baseline_payload"]]) != spec["source_baselines"][name]:
            raise food.fm.ModError("Incorrect source baseline: " + name)
    introduced = spec.get("introduced_files")
    expected = {"AnnoWorldSettings.dll":"native/AnnoWorldSettings.dll",
                "WorldSettingsAI/CompLogic.dll":"native/CompLogic.food-ai.dll",
                "WorldSettingsAI/CompLogicClassic.dll":"native/CompLogicClassic.food-ai.dll"}
    expected.update(alias_assets.introduced_files())
    expected.update(world_assets.introduced_files())
    if introduced != expected:
        raise food.fm.ModError("Unexpected introduced runtime/AI/island targets")
    if set(introduced) & set(spec["native_overlays"]):
        raise food.fm.ModError("Introduced and overlaid native targets overlap")
    for name, payload in introduced.items():
        tx._name(name)
        if payload not in result:
            raise food.fm.ModError("Missing introduced native payload: " + name)
    return result


def build_edits(root, spec, progress=print):
    root = assert_copy(root, spec)
    try:
        world_assets.validate_required_copy(root)
    except (OSError, ValueError) as exc:
        raise food.fm.ModError("Required stock island-loading input differs: " + str(exc)) from exc
    native = payloads(spec)
    # Reject a changed or legacy executable independently of food state selection.
    exe = tx._path(root, "Anno1503.exe").read_bytes()
    require_amd64(exe, "Anno1503.exe")
    if food.fm.sha(exe) != spec["exe_sha256"]:
        raise food.fm.ModError("Unsupported Anno1503.exe fingerprint")
    for name, digest in spec["unchanged_native"].items():
        data = tx._path(root, name).read_bytes()
        require_amd64(data, name)
        if food.fm.sha(data) != digest:
            raise food.fm.ModError("Unsupported native fingerprint: " + name)
    current = {}
    patched = {}
    for name, overlay in spec["native_overlays"].items():
        current[name] = tx._path(root, name).read_bytes()
        require_amd64(current[name], name)
        patched[name] = current[name] == native[overlay["output_payload"]]
    if any(patched.values()) and not all(patched.values()):
        raise food.fm.ModError("Partial or mixed World Settings native installation; restore with its original installer first")
    introduced = {name:native[payload] for name,payload in spec["introduced_files"].items()}
    installed = all(patched.values())
    if installed:
        for name,data in introduced.items():
            path=tx._path(root,name)
            if not path.is_file() or path.read_bytes()!=data:
                raise food.fm.ModError("Introduced runtime/AI/island file is missing or changed; restore before reinstalling: " + name)
        record = tx.read_manifest(root)
        if not record or record["status"] != "installed":
            raise food.fm.ModError("Exact payloads lack an active matching installation journal; refusing an unrestorable no-op")
        recorded = {entry["name"]:entry for entry in record["edits"]}
        expected = {name:native[o["output_payload"]] for name,o in spec["native_overlays"].items()}
        expected.update(introduced)
        for name, data in expected.items():
            entry = recorded.get(name)
            if not entry or (entry["after_size"], entry["after_sha256"]) != (len(data), food.fm.sha(data)):
                raise food.fm.ModError("Installed native payloads do not match the restoration journal: " + name)
        backup = tx._path(root, tx.BACKUP, target=False)
        for entry in record["edits"]:
            tx._require(root, entry, [tx._after(entry)])
            if entry["existed"]:
                original = tx._path(backup, "before/" + entry["name"], target=False)
                if tx._state(original) != tx._before(entry):
                    raise food.fm.ModError("Restoration backup missing or changed: " + entry["name"])
    else:
        for name in introduced:
            if os.path.lexists(tx._path(root,name)):
                raise food.fm.ModError("Introduced runtime/AI/island target already exists; refusing to overwrite it: " + name)
    if not installed:
        for name, overlay in spec["native_overlays"].items():
            if not overlay["food_native"] and current[name] != native[overlay["baseline_payload"]]:
                raise food.fm.ModError("Unsupported native source fingerprint: " + name)
    food_spec = json.loads((PACKAGE / "food_patch.json").read_bytes())
    food_native_names={entry["name"] for entry in food_spec["native_modules"]}
    overrides = {name: native[o["baseline_payload"]] for name,o in spec["native_overlays"].items()
                 if name in food_native_names} if installed else None
    state, edits = food.build_edits(root, food_spec, progress, native_overrides=overrides)
    if installed:
        if state != food.FINAL_STATE or edits:
            raise food.fm.ModError("Installed development files do not match exact Food 0.5 outputs")
        progress("Verified exact development Frame/Scene/Welt/runtime/AI/island copies and preserved Food 0.5 semantics")
        return FINAL_STATE, []
    combined = [tx.Edit(e.name, e.before, e.after, e.file_size, e.offset) for e in edits]
    for name, overlay in spec["native_overlays"].items():
        native_edits = [e for e in combined if e.name == name]
        baseline = native[overlay["baseline_payload"]]
        if native_edits:
            if (name not in food_native_names or len(native_edits) != 1
                    or native_edits[0].offset is not None or native_edits[0].after != baseline):
                raise food.fm.ModError("Food native output differs from inspected World Settings baseline: " + name)
            combined.remove(native_edits[0])
        elif current[name] != baseline:
            raise food.fm.ModError("Unrecognized native source fingerprint; no writes: " + name)
        combined.append(tx.Edit(name, current[name], native[overlay["output_payload"]], len(current[name])))
    for name,data in introduced.items():
        combined.append(tx.Edit(name,None,data))
    if len({e.name.casefold() for e in combined}) != len(combined):
        raise food.fm.ModError("Combined transaction selected a file twice")
    return state, combined


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["check", "install", "restore"])
    parser.add_argument("--game-dir", type=Path, help="Explicit marked game copy; otherwise discover the existing validated copy")
    args = parser.parse_args(argv)
    print("Anno 1503 Food + World Settings " + VERSION + " — UNFINISHED DEVELOPMENT")
    print("Development build: ACTIVATE_WORLD_SETTINGS.cmd enables guarded copy testing; choose all world options inside the game.")
    try:
        spec = json.loads((PACKAGE / "world_patch.json").read_bytes())
        root = resolve_copy(spec, args.game_dir)
        print("Game copy: " + str(root))
        if args.action == "restore":
            assert_game_closed()
            state = tx.restore(root, progress=print)
            print("Restored exact preceding setup: " + state)
        else:
            state, edits = build_edits(root, spec)
            print("Validated " + str(len(edits)) + " combined transaction changes; all five food needs retained.")
            if state == FINAL_STATE and not edits:
                print("Development package already installed and verified; no writes.")
            elif args.action == "install":
                assert_game_closed()
                tx.install(root, edits, state, progress=print)
                print("Installed on marked COPY only. RESTORE.cmd restores exact preceding files.")
        return 0
    except (OSError, ValueError, KeyError, TypeError, struct.error, subprocess.SubprocessError,
            food.fm.ModError, tx.TransactionError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
