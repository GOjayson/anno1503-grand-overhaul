"""Separate, closed Food 0.6 package recipe; Food 0.5 remains unchanged.

The original Food specification stays byte-exact for vanilla recovery. A
source-pinned preparation shim composes the new diet, artwork and reviewed
View and World derivatives with Food 0.5 edits before the existing transaction.
Food 0.6 is Food-only and requires a new world; it does not migrate old saves.
"""
from __future__ import annotations

import base64
from pathlib import Path, PurePosixPath
import os
import re

from . import packages as common
from .food_diet import VERSION, FOOD05_BGRUPPEN_SHA256, FOOD06_BGRUPPEN_SHA256


KIND = "anno1503-food06-installer-package"
PROFILE = "food-only-" + VERSION
VIEW_PAYLOAD = "food/native/View.food06.dll"
WELT_PAYLOAD = "food/native/AnnoWelt.food06.dll"
_NEW_SOURCES = {
    "food/support/food_diet.py": "src/anno1503_overhaul/food_diet.py",
    "food/support/food_artwork.py": "src/anno1503_overhaul/food_artwork.py",
}


def _view_policy() -> str:
    try:
        from .food_household import FOOD06_VIEW_SHA256
    except ImportError as exc:
        raise common.PackageError("The reviewed Food 0.6 household display is not ready.") from exc
    if not isinstance(FOOD06_VIEW_SHA256, str) or not re.fullmatch(r"[0-9a-f]{64}", FOOD06_VIEW_SHA256):
        raise common.PackageError("The Food 0.6 View derivative has not passed its build review.")
    return FOOD06_VIEW_SHA256


def _welt_policy() -> str:
    try:
        from .food_supply import FOOD06_WELT_SHA256
    except ImportError as exc:
        raise common.PackageError("The reviewed Food 0.6 household supply guards are not ready.") from exc
    if not isinstance(FOOD06_WELT_SHA256, str) or not re.fullmatch(r"[0-9a-f]{64}", FOOD06_WELT_SHA256):
        raise common.PackageError("The Food 0.6 World derivative has not passed its build review.")
    return FOOD06_WELT_SHA256


def _scope() -> dict:
    return dict(world_settings_supported=False, new_world_required=True,
                old_save_migration_supported=False, food05_profile_preserved=True)


def _spec(view_sha: str, welt_sha: str) -> dict:
    return dict(version=VERSION, profile=PROFILE,
                base_food_spec_sha256=common.FOOD_SPEC_SHA256,
                food05_resident_sha256=FOOD05_BGRUPPEN_SHA256,
                food06_resident_sha256=FOOD06_BGRUPPEN_SHA256,
                view_sha256=view_sha, view_payload="native/View.food06.dll",
                welt_sha256=welt_sha, welt_payload="native/AnnoWelt.food06.dll",
                scope=_scope(), actual_game_test_performed=False)


def _worker_source(view_sha: str, welt_sha: str) -> bytes:
    # This source is part of the reconstructed package recipe, never supplied
    # by a downloaded provider or imported from an editable Python install.
    source = '''"""Food-only 0.6 preparation; a new world is required."""
from pathlib import Path
import hashlib
import json
import sys

PACKAGE = Path(__file__).resolve().parent
sys.path.insert(0, str(PACKAGE))
import food05_mod as base
if Path(base.__file__).resolve() != PACKAGE / 'food05_mod.py':
    raise RuntimeError('Unexpected preserved Food preparation module.')
sys.path.insert(0, str(PACKAGE / 'support'))
import food_diet
import food_artwork
for helper in (food_diet, food_artwork):
    if Path(helper.__file__).resolve() != PACKAGE / 'support' / (helper.__name__ + '.py'):
        raise RuntimeError('Unexpected Food 0.6 preparation helper.')

EXPECTED_BASE_SPEC = '@@BASE@@'
EXPECTED_VIEW = '@@VIEW@@'
EXPECTED_WELT = '@@WELT@@'
EXPECTED_SPEC = @@SPEC@@


def build_edits(root, spec, progress=print):
    raw = (PACKAGE / 'food_patch.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXPECTED_BASE_SPEC or json.loads(raw) != spec:
        raise base.fm.ModError('Food 0.6 requires its exact preserved Food 0.5 construction inputs.')
    metadata = json.loads((PACKAGE / 'food06_patch.json').read_bytes())
    if metadata != EXPECTED_SPEC:
        raise base.fm.ModError('The Food 0.6 selection or new-world policy changed.')
    view = (PACKAGE / 'native/View.food06.dll').read_bytes()
    if hashlib.sha256(view).hexdigest() != EXPECTED_VIEW:
        raise base.fm.ModError('The reviewed Food 0.6 household display changed.')
    welt = (PACKAGE / 'native/AnnoWelt.food06.dll').read_bytes()
    if hashlib.sha256(welt).hexdigest() != EXPECTED_WELT:
        raise base.fm.ModError('The reviewed Food 0.6 household supply guards changed.')
    progress('Food 0.6 requires a NEW world. Existing Food 0.5 saves are not migrated.')
    state, edits = base.build_edits(root, spec, progress)
    if state != 'vanilla':
        raise base.fm.ModError('Restore the managed copy to verified original files before installing Food 0.6.')
    indexed = {edit.name: edit for edit in edits}
    if len(indexed) != len(edits) or not {'View.dll', 'AnnoWelt.dll', 'Data/BGruppen.dat'}.issubset(indexed):
        raise base.fm.ModError('The Food 0.5 composition targets differ.')
    changed = {edit.name: edit.after for edit in edits}
    changed['View.dll'] = view
    changed['AnnoWelt.dll'] = welt
    changed['Data/BGruppen.dat'] = food_diet.transform_food05(indexed['Data/BGruppen.dat'].after)
    for index_name, texture_name in base.ui_pairs(root):
        if index_name not in indexed or texture_name not in indexed:
            raise base.fm.ModError('A Food artwork composition target is missing.')
        index, texture = indexed[index_name], indexed[texture_name]
        new_index, new_texture, proof = food_artwork.transform(
            index.before, texture.before, index.after, texture.after)
        if not isinstance(new_index, bytes) or not isinstance(new_texture, bytes) or not isinstance(proof, dict):
            raise base.fm.ModError('Food artwork preparation returned invalid outputs.')
        changed[index_name], changed[texture_name] = new_index, new_texture
    result = [base.tx.Edit(edit.name, edit.before, changed[edit.name], edit.file_size, edit.offset)
              for edit in edits if edit.before != changed[edit.name]]
    if any(not isinstance(edit.after, bytes) for edit in result):
        raise base.fm.ModError('Food 0.6 returned a mutable output.')
    return state, result
'''
    # repr produces Python literals, including booleans; JSON does not.
    source = source.replace("@@BASE@@", common.FOOD_SPEC_SHA256).replace("@@VIEW@@", view_sha)
    source = source.replace("@@WELT@@", welt_sha).replace("@@SPEC@@", repr(_spec(view_sha, welt_sha)))
    return source.encode("utf-8")


def _recipe(source: str, copy: str | None, view: bytes, welt: bytes) -> dict[str, bytes]:
    view_pin, welt_pin = _view_policy(), _welt_policy()
    for name, value, pin in (("View", view, view_pin), ("World", welt, welt_pin)):
        if not isinstance(value, bytes):
            raise common.PackageError("The Food 0.6 " + name + " derivative must be immutable bytes.")
        common._require_sha(value, pin, "Food 0.6 household " + name + " derivative")
        common._amd64(value, "Food 0.6 household " + name + " derivative")
    files = common._source_recipe(copy, kinds=("food",))
    files["food/food05_mod.py"] = files["food/food_mod.py"]
    files["food/food_mod.py"] = _worker_source(view_pin, welt_pin)
    for destination, public in _NEW_SOURCES.items():
        files[destination] = common._read(common.ROOT, public)
    files["food/food06_patch.json"] = common._encoded(_spec(view_pin, welt_pin))
    files[VIEW_PAYLOAD] = view
    files[WELT_PAYLOAD] = welt
    return files


def _manifest(source: str, copy: str | None, files: dict[str, bytes]) -> dict:
    return dict(schema_version=1, kind=KIND, version=VERSION, profile=PROFILE,
                source_root=source, copy_root=copy,
                feature_versions={"food_overhaul": VERSION},
                base_food_spec_sha256=common.FOOD_SPEC_SHA256,
                view_sha256=_view_policy(), welt_sha256=_welt_policy(), scope=_scope(),
                files={name: common._sha(value) for name, value in sorted(files.items())},
                actual_game_test_performed=False)


def _paths(source_value, copy_value):
    if not isinstance(source_value, str) or copy_value is not None and not isinstance(copy_value, str):
        raise common.PackageError("Invalid Food 0.6 game paths.")
    source = common._checked_path(Path(source_value))
    if not source.is_dir() or str(source) != source_value:
        raise common.PackageError("The Food 0.6 source path is not a canonical directory.")
    copy = None if copy_value is None else common._checked_path(Path(copy_value), exists=False)
    if copy is not None and (str(copy) != copy_value or copy == source
                             or copy.is_relative_to(source) or source.is_relative_to(copy)):
        raise common.PackageError("Choose an independent, non-overlapping Food 0.6 copy.")
    return source, copy


def validate_food06_package(path, source_game=None):
    root = common._checked_path(Path(path))
    manifest = common._json(common._read(root, "manifest.json"), "Food 0.6 package manifest")
    if manifest.get("kind") != KIND:
        raise common.PackageError("Unknown Food 0.6 package kind.")
    source, copy = _paths(manifest.get("source_root"), manifest.get("copy_root"))
    if source_game is not None and common._checked_path(Path(source_game)) != source:
        raise common.PackageError("This Food 0.6 package belongs to another original game.")
    files = _recipe(str(source), None if copy is None else str(copy),
                    common._read(root, VIEW_PAYLOAD), common._read(root, WELT_PAYLOAD))
    expected = _manifest(str(source), None if copy is None else str(copy), files)
    if common._encoded(manifest) != common._encoded(expected):
        raise common.PackageError("The Food 0.6 manifest differs from its reviewed recipe.")
    for name, value in files.items():
        if common._read(root, name) != value:
            raise common.PackageError("A Food 0.6 helper, source or payload changed: " + name)
    names = set(files) | {"manifest.json"}
    directories = {str(parent) for name in names for parent in PurePosixPath(name).parents if str(parent) != "."}
    for folder, dirs, entries in os.walk(root, followlinks=False):
        for child in dirs + entries:
            item = Path(folder) / child
            common._checked_path(item)
            relative = item.relative_to(root).as_posix()
            if item.is_dir():
                if relative not in directories:
                    raise common.PackageError("Unexpected Food 0.6 package directory: " + relative)
            elif not item.is_file() or relative not in names:
                raise common.PackageError("Unexpected Food 0.6 package file: " + relative)
    return dict(expected, root=root, path=root, food_path=root / "food", world_path=None,
                launcher_path=None, verified=True, new_world_required=True,
                old_save_migration_supported=False, world_settings_supported=False)


def _food05_native(data: bytes, spec: dict, name: str) -> bytes:
    """Reconstruct one fixed Food 0.5 native input without legacy imports."""
    matches = [item for item in spec["native_modules"] if item["name"] == name]
    if len(matches) != 1:
        raise common.PackageError("The preserved Food native module is absent or ambiguous: " + name)
    entry = matches[0]
    common._amd64(data, "source " + name)
    digest = common._sha(data)
    if digest == entry["after_sha256"]:
        return data
    if digest not in set(entry["sources"].values()) or digest not in entry["changes"]:
        raise common.PackageError("The source " + name + " is outside the preserved Food inputs.")
    change = entry["changes"][digest]
    output, occupied = bytearray(data), set()
    for patch in change["patches"]:
        at = patch["offset"]
        before, after = bytes.fromhex(patch["before"]), bytes.fromhex(patch["after"])
        if type(at) is not int or at < 0:
            raise common.PackageError("A preserved Food native patch has an invalid offset.")
        indices = set(range(at, at + len(before)))
        if (len(before) != len(after) or at + len(before) > len(data)
                or occupied & indices or data[at:at + len(before)] != before):
            raise common.PackageError("A preserved Food native preimage differs.")
        occupied.update(indices)
        output[at:at + len(before)] = after
    output += base64.b64decode(change["append_base64"], validate=True)
    result = bytes(output[:change["result_size"]])
    common._require_sha(result, entry["after_sha256"], "reconstructed Food 0.5 " + name)
    return result


def _food05_view(data: bytes, spec: dict) -> bytes:
    """Compatibility wrapper for the fixed Food 0.5 View reconstruction."""
    return _food05_native(data, spec, "View.dll")


def _build_view_from_source(source: Path, compiler: Path) -> tuple[bytes, dict]:
    raw_spec = common._require_sha(common._read(common.ROOT, "legacy/food_overhaul/food_patch.json"),
                                   common.FOOD_SPEC_SHA256, "preserved Food specification")
    spec = common._json(raw_spec, "preserved Food specification")
    exe = common._read(source, "Anno1503.exe")
    common._require_sha(exe, spec["exe_sha256"], "supported History Edition executable")
    food05 = _food05_view(common._read(source, "View.dll"), spec)
    from .food_household import build_view
    return build_view(food05, compiler)


def _build_welt_from_source(source: Path) -> tuple[bytes, dict]:
    raw_spec = common._require_sha(common._read(common.ROOT, "legacy/food_overhaul/food_patch.json"),
                                   common.FOOD_SPEC_SHA256, "preserved Food specification")
    spec = common._json(raw_spec, "preserved Food specification")
    common._require_sha(common._read(source, "Anno1503.exe"), spec["exe_sha256"],
                        "supported History Edition executable")
    food05 = _food05_native(common._read(source, "AnnoWelt.dll"), spec, "AnnoWelt.dll")
    from .food_supply import build_welt
    return build_welt(food05)


def prepare_food06_package(output_dir, source_game, copy_game=None, *, compiler_path=None):
    """Build reviewed Food-only inputs in a fresh folder, never in the game."""
    view_pin, welt_pin = _view_policy(), _welt_policy()
    source, copy = _paths(str(common._checked_path(Path(source_game))),
                          None if copy_game is None else str(common._checked_path(Path(copy_game), exists=False)))
    output = common._package_output(output_dir, source, copy)
    if compiler_path is None:
        from .beta_paths import compiler_path as find_compiler
        compiler_path = find_compiler()
    compiler = common._checked_path(Path(compiler_path))
    if not compiler.is_file():
        raise common.PackageError("Select the reviewed Food 0.6 compiler executable.")
    view, proof = _build_view_from_source(source, compiler)
    if not isinstance(proof, dict):
        raise common.PackageError("The Food household build returned no review proof.")
    common._require_sha(view, view_pin, "compiled Food 0.6 household display")
    welt, supply_proof = _build_welt_from_source(source)
    if not isinstance(supply_proof, dict):
        raise common.PackageError("The Food household supply build returned no review proof.")
    common._require_sha(welt, welt_pin, "reviewed Food 0.6 household supply guards")
    files = _recipe(str(source), None if copy is None else str(copy), view, welt)
    files["manifest.json"] = common._encoded(_manifest(str(source), None if copy is None else str(copy), files))
    return common._publish(files, output, source)
