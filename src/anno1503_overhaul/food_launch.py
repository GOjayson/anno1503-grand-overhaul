"""Verified Food 0.6 startup through the normal Ubisoft client.

The handoff is the existing owned-main-menu transaction. Food startup never
activates World Settings. Its observer is derived from the preserved readiness
code with a read-only dependency closure: no remote calls, allocation or writes.
Authentication arguments and environment values remain in the existing opaque,
single-use client context and are never persisted by this module.
"""
from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import ctypes as C
import json
import os
from pathlib import Path
import sys
from types import ModuleType

from . import packages as common
from .filesystem import checked_path, file_sha, read_copy_marker, safe_child
from .food_diet import FOOD06_BGRUPPEN_SHA256
from .food06_package import KIND, VERSION, validate_food06_package
from .processes import require_game_closed


class FoodLaunchError(RuntimeError):
    pass


def _imported_source(name: str) -> bytes:
    provenance = common._json(common._read(common.ROOT, "provenance/legacy_import.json"), "source provenance")
    matches = [record for record in provenance["source_files"] if record["path"] == name]
    if len(matches) != 1:
        raise FoodLaunchError("The reviewed Food startup source is absent from provenance.")
    return common._require_sha(common._read(common.ROOT, name), matches[0]["imported_sha256"], name)


def verify_food06_installation(copy_game) -> dict:
    """Check disk/journal/profile identity without starting or controlling Anno."""
    from . import installer
    from .world_runtime_build import STOCK_SHA256

    root = checked_path(Path(copy_game))
    marker = read_copy_marker(root)
    record = installer._read_install(root)
    features = record.get("profile", {}).get("features", {}) if isinstance(record, dict) and isinstance(record.get("profile"), dict) else {}
    if (marker["phase"] != "installed" or not record or record["status"] != "installed"
            or record.get("food_version") != VERSION
            or not isinstance(features, dict) or features.get("food_overhaul") is not True
            or features.get("world_settings") is not False):
        raise FoodLaunchError("Install the explicit Food 0.6 Food-only profile on this managed copy before starting it.")
    if any(not isinstance(record.get(name), str) for name in ("source_root", "package_root", "package_manifest_sha256")):
        raise FoodLaunchError("The installed Food package binding is incomplete.")
    source = checked_path(Path(marker["source_root"]))
    if checked_path(Path(record["source_root"])) != source:
        raise FoodLaunchError("The Food installation and managed copy have different original-game bindings.")
    package = checked_path(Path(record["package_root"]))
    if file_sha(package / "manifest.json") != record.get("package_manifest_sha256"):
        raise FoodLaunchError("The installed Food package identity changed.")
    if getattr(sys, "frozen", False):
        from .frozen_runner import application_root, validate_package_closure, verify_retained_worker
        retained = record.get("launcher_runtime")
        if not isinstance(retained, dict):
            raise FoodLaunchError("This Food copy has no retained Windows launcher. Restore and reinstall it with the current installer.")
        worker = verify_retained_worker(retained)
        if checked_path(application_root()) != worker.parent or checked_path(Path(sys.executable)) != worker:
            raise FoodLaunchError("Start Food through this installation's retained Windows launcher.")
        closure = validate_package_closure(package, record["package_manifest_sha256"], copy_root=root)
        if closure.get("kind") != KIND:
            raise FoodLaunchError("The retained Food launcher requires its exact Food-only package.")
    metadata = validate_food06_package(package, source)
    if metadata["kind"] != KIND or Path(metadata.get("copy_root") or "").resolve() != root:
        raise FoodLaunchError("The Food package belongs to another selected-feature copy.")
    city_statistics_guard = metadata.get("city_statistics_guard", False)
    if (city_statistics_guard is not record.get("city_statistics_guard", False)
            or city_statistics_guard and features.get("bug_fixes") is not True):
        raise FoodLaunchError("The Food package and installation have different city statistics guard selections.")
    journal = installer._verify_journal(root)
    installer._verify_food06_bug_fixes(root, record, journal)

    raw = common._require_sha(common._read(package / "food", "food_patch.json"),
                              common.FOOD_SPEC_SHA256, "preserved Food recovery specification")
    food = common._json(raw, "preserved Food recovery specification")
    if file_sha(safe_child(source, "Anno1503.exe", exists=True)) != food["exe_sha256"]:
        raise FoodLaunchError("The normal Ubisoft executable differs from the supported History Edition build.")
    if file_sha(safe_child(root, "Anno1503.exe", exists=True)) != food["exe_sha256"]:
        raise FoodLaunchError("The Food copy does not use the identical supported executable.")
    source_profile, current = verified_ubisoft_native(source, food)
    expected_copy = {entry["name"]: entry["after_sha256"] for entry in food["native_modules"]}
    expected_copy.update({"View.dll": metadata["view_sha256"], "AnnoWelt.dll": metadata["welt_sha256"]})
    expected_copy["AnnoScene.dll"] = STOCK_SHA256["AnnoScene.dll"]
    for name, digest in expected_copy.items():
        if file_sha(safe_child(root, name, exists=True)) != digest:
            raise FoodLaunchError("The selected Food 0.6 native profile differs: " + name)
    if file_sha(safe_child(root, "Data/BGruppen.dat", exists=True)) != FOOD06_BGRUPPEN_SHA256:
        raise FoodLaunchError("The selected Food copy does not have its reviewed 0.6 tier diets.")

    return dict(source_root=source, copy_root=root, package_root=package,
                source_profile=source_profile,
                source_inputs=menu_observer_inputs(source, food["exe_sha256"], current),
                copy_inputs=menu_observer_inputs(root, food["exe_sha256"], expected_copy), metadata=metadata)


def verified_ubisoft_native(source, food) -> tuple[str, dict]:
    """Accept the reviewed original game or the preserved Food 0.5 source."""
    from .world_runtime_build import STOCK_SHA256

    profiles = {
        "vanilla": {entry["name"]: entry["sources"]["vanilla"] for entry in food["native_modules"]},
        "food05": {entry["name"]: entry["after_sha256"] for entry in food["native_modules"]},
    }
    current = {name: file_sha(safe_child(source, name, exists=True)) for name in profiles["vanilla"]}
    matches = [name for name, expected in profiles.items() if current == expected]
    if len(matches) != 1:
        raise FoodLaunchError("The normal Ubisoft game is neither the exact stock nor preserved Food 0.5 native profile.")
    source_profile = matches[0]
    residents = food["files"]["Data/BGruppen.dat"]
    expected_residents = residents["sources"]["vanilla"] if source_profile == "vanilla" else residents["after_sha256"]
    if file_sha(safe_child(source, "Data/BGruppen.dat", exists=True)) != expected_residents:
        raise FoodLaunchError("The normal Ubisoft game's resident data and native Food profile differ.")
    current["AnnoScene.dll"] = STOCK_SHA256["AnnoScene.dll"]
    if file_sha(safe_child(source, "AnnoScene.dll", exists=True)) != current["AnnoScene.dll"]:
        raise FoodLaunchError("The normal Ubisoft Scene module is outside the inspected build.")
    return source_profile, current


def menu_observer_inputs(folder, exe_sha256, native) -> dict:
    return dict(source=folder, copy=folder, exe_sha256=exe_sha256,
                native_sha256=native, private_native_sha256={})


def _readonly_backend_source() -> bytes:
    """Extract only the exact preserved observer's non-mutating dependencies."""
    native = ast.parse(_imported_source("legacy/world_settings/activation/activate_world_settings.py"))
    checks = ast.parse(_imported_source("legacy/world_settings/activation/module_checks.py"))
    assignments = {"K", "SIZE", "PTR", "INVALID", "snapshot", "close", "process_first", "process_next",
                   "module_first", "module_next", "open_process", "query_path", "read", "process_times"}
    functions = {"bind", "check", "sha", "same", "creation_time", "all_processes", "modules"}
    classes = {"Process", "Module", "Session"}
    body = ast.parse("from pathlib import Path\nimport ctypes as C\nfrom ctypes import wintypes as W\nimport hashlib,os\n").body
    found = set()
    for original in native.body:
        names = {target.id for target in original.targets if isinstance(target, ast.Name)} if isinstance(original, ast.Assign) else set()
        selected = ((isinstance(original, ast.Assign) and names and names.issubset(assignments))
                    or isinstance(original, ast.FunctionDef) and original.name in functions
                    or isinstance(original, ast.ClassDef) and original.name in classes)
        if not selected:
            continue
        node = deepcopy(original)
        found.update(names if names else {node.name})
        if isinstance(node, ast.ClassDef) and node.name == "Session":
            reads = [method for method in node.body if isinstance(method, ast.FunctionDef) and method.name == "read"]
            if len(reads) != 1:
                raise FoodLaunchError("The preserved read-only process reader changed.")
            initializer = ast.parse('''def __init__(self,pid,mutate=False):
    if mutate is not False:
        raise RuntimeError('The Food startup observer is read-only.')
    self.pid=pid
    self.handle=check(open_process(0x1000|0x10,False,pid),'Open read-only Anno process')
''').body[0]
            node.body = [initializer, reads[0]]
        body.append(node)
    if found != assignments | functions | classes:
        raise FoodLaunchError("The preserved read-only startup dependency closure changed.")
    policy = [deepcopy(node) for node in checks.body
              if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "REQUIRED_NATIVE" for target in node.targets)
              or isinstance(node, ast.FunctionDef) and node.name == "verify_modules"]
    if len(policy) != 2:
        raise FoodLaunchError("The preserved native module identity policy changed.")
    body.extend(policy)
    return (ast.unparse(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[]))) + "\n").encode("utf-8")


def _readiness_sources() -> dict[str, bytes]:
    from .world_only_package import _launcher_recipe
    files = common._source_recipe(None, kinds=("launcher",))
    _launcher_recipe(files, "", "")
    tree = ast.parse(files["launcher/native_ready.py"])
    body, replaced = [], 0
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            continue
        if isinstance(node, ast.If) and "__name__" in ast.unparse(node.test):
            continue
        if isinstance(node, ast.FunctionDef) and node.name == "_activation":
            node = ast.parse("def _activation(package):\n    return _FOOD_READ_ONLY_BACKEND\n").body[0]
            replaced += 1
        body.append(node)
    if replaced != 1:
        raise FoodLaunchError("The preserved menu observer dependency point changed.")
    ready = (ast.unparse(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[]))) + "\n").encode("utf-8")
    return {"food_read_only.py": _readonly_backend_source(), "native_ready.py": ready}


def _make_probes(verified):
    sources = _readiness_sources()
    backend = ModuleType("_anno1503_food06_read_only")
    exec(compile(sources["food_read_only.py"], "<verified Food read-only backend>", "exec"), backend.__dict__)
    ready = ModuleType("_anno1503_food06_readiness")
    ready._FOOD_READ_ONLY_BACKEND = backend
    exec(compile(sources["native_ready.py"], "<verified Food menu observer>", "exec"), ready.__dict__)
    source = ready.NativeReadiness(verified["package_root"], verified["source_inputs"],
                                  frame_sha=verified["source_inputs"]["native_sha256"]["AnnoFrame.dll"])
    try:
        copied = ready.NativeReadiness(verified["package_root"], verified["copy_inputs"],
                                      frame_sha=verified["copy_inputs"]["native_sha256"]["AnnoFrame.dll"])
    except BaseException:
        source.close()
        raise
    return source, copied


def find_registered_uri(source):
    """Use the preserved launcher's exact, read-only registry selection logic."""
    raw = _imported_source("legacy/launcher/launch_world_settings.pyw")
    tree = ast.parse(raw)
    selected = [method for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Backend"
                for method in node.body if isinstance(method, ast.FunctionDef) and method.name == "find_uri"]
    if len(selected) != 1:
        raise FoodLaunchError("The reviewed registered launch-route reader changed.")
    method = deepcopy(selected[0])
    method.decorator_list = []
    namespace = dict(Path=Path, LaunchError=FoodLaunchError)
    code = ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))
    exec(compile(code, "<verified registered Anno route>", "exec"), namespace)
    return namespace["find_uri"](Path(source))


def _require_source_host():
    if os.name != "nt" or C.sizeof(C.c_void_p) != 8:
        raise FoodLaunchError("The Food 0.6 launcher requires a 64-bit Windows host.")


def launch_food06(copy_game, *, progress=None, event=None, timeout=300):
    """Launch only this checked Food copy; no runtime activation is performed."""
    _require_source_host()
    require_game_closed()
    verified = verify_food06_installation(copy_game)
    source_probe, copy_probe = _make_probes(verified)
    try:
        uri = find_registered_uri(verified["source_root"])
        from .client_context import start_game
        if progress:
            progress("Food 0.6: start a NEW endless world; Food 0.5 saves are not migrated.")
        return start_game(uri, verified["source_root"], verified["copy_root"], source_probe,
                          copy_probe=copy_probe, event=event, progress=progress, timeout=timeout)
    finally:
        source_probe.close()
        copy_probe.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--copy", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        process = launch_food06(args.copy, progress=lambda message: print(message, file=sys.stderr, flush=True))
        print(json.dumps(dict(food06_started=True, pid=process.pid,
                              world_settings_activated=False, new_world_required=True)))
        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
