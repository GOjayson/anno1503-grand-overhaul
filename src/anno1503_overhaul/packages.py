"""Prepare a local, pinned installer package without distributing game files.

Only the reviewed frozen payloads are accepted. Python helpers come from this
checkout, never from an arbitrary package provider. The preserved baselines and
the public source-only specification are not changed by package preparation.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import struct
import uuid


class PackageError(ValueError):
    """A package or its local input differs from the reviewed baseline."""


FROZEN_WORLD_SPEC_SHA256 = "f43d4a136a0625836889a1379a70ecb60c589aa34d7acdc9a75db5206e2b5fec"
FOOD_SPEC_SHA256 = "aa88900d4f55661720c5927ba7e66cb3dc3dfaa17a55ddedb89d4fb5a61bdae5"
RUNTIME_SHA256 = "2f9d1156f3ac53d92a900e41c38a169138c2b4ac7145f2dc92b93c48736cf089"
ADAPTER_VERSION = "1.0"
TRANSACTION_BACKUP = "GrandOverhaul_Backup_v1"
TRANSACTION_LOCK = ".grand-overhaul-transaction.lock"
TRANSACTION_VERSION = "1.0-modular-transactions"
ROOT = Path(__file__).resolve().parents[2]

_FOOD = (
    "food_mod.py", "food_patch.json", "support/artwork.py", "support/formats.py",
    "support/transactions.py", "support/transforms.py",
)
_ARTWORK = (
    "assets/ARTWORK.txt", "assets/bread.png", "assets/bread_icon.json",
    "assets/butcher-meat.png", "assets/butcher_meat_icon.json", "assets/fish.png",
    "assets/fish_icon.json", "assets/game-meat.png", "assets/game_meat_icon.json",
    "assets/icon-preview.png", "assets/potatoes.png", "assets/potatoes_icon.json",
    "assets/source/bread.png", "assets/source/butcher-meat.png",
    "assets/source/game-meat.png", "assets/source/potatoes.png",
)
_WORLD = _FOOD + (
    "world_mod.py", "support/world_transactions.py", "support/package_alias_assets.py",
    "support/package_world_assets.py", "activation/activate_world_settings.py",
    "activation/module_checks.py", "activation/pe_exports.py", "activation/preflight.py",
    "activation/preview_snapshot.py", "developer/huge_world/runtime_engine_edits.json",
)
_LAUNCHER = (
    "launch_world_settings.pyw", "launcher_core.py", "native_ready.py", "activation_once.py",
)
_LAYOUT = {"food": ("food_overhaul", _FOOD + _ARTWORK),
           "world": ("world_settings", _WORLD + _ARTWORK),
           "launcher": ("launcher", _LAUNCHER)}
_NATIVE = {
    "native/AnnoFrame.food05.dll", "native/AnnoFrame.world.dll",
    "native/AnnoScene.source.dll", "native/AnnoScene.world.dll",
    "native/AnnoWelt.source.dll", "native/AnnoWelt.world.dll",
    "native/AnnoWorldSettings.dll", "native/CompLogic.food-ai.dll",
    "native/CompLogicClassic.food-ai.dll",
}
_MAX_FILE = 16 * 1024 * 1024


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(data: bytes, label: str) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise PackageError("Duplicate JSON field in " + label)
            result[key] = value
        return result
    try:
        value = json.loads(data, object_pairs_hook=pairs)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise PackageError("Invalid JSON in " + label) from exc
    if not isinstance(value, dict):
        raise PackageError("Expected a JSON object in " + label)
    return value


def _encoded(value: dict) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _name(value: str) -> str:
    if not isinstance(value, str) or "\\" in value or ":" in value or "\0" in value:
        raise PackageError("Invalid package relative path")
    p = PurePosixPath(value)
    if not value or p.is_absolute() or any(x in ("", ".", "..") for x in value.split("/")):
        raise PackageError("Invalid package relative path")
    return value


def _checked_path(path: Path, *, exists: bool = True) -> Path:
    """Refuse symlinks and Windows junctions before resolving any component."""
    absolute = Path(os.path.abspath(path))
    for part in [*reversed(absolute.parents), absolute]:
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise PackageError("Linked or reparse-point package path is not allowed: " + str(part))
    try:
        return absolute.resolve(strict=exists)
    except (OSError, RuntimeError) as exc:
        raise PackageError("Local package path was not found: " + str(absolute)) from exc


def _read(root: Path, name: str) -> bytes:
    path = _checked_path(root / _name(name))
    if not path.is_relative_to(root) or not path.is_file() or path.stat().st_size > _MAX_FILE:
        raise PackageError("Unsupported package file: " + name)
    return path.read_bytes()


def _require_sha(data: bytes, expected: str, label: str) -> bytes:
    if _sha(data) != expected:
        raise PackageError("File fingerprint differs: " + label)
    return data


def _amd64(data: bytes, name: str) -> None:
    try:
        pe, = struct.unpack_from("<I", data, 60)
        valid = (data[:2] == b"MZ" and data[pe:pe+4] == b"PE\0\0"
                 and struct.unpack_from("<H", data, pe+4)[0] == 0x8664
                 and struct.unpack_from("<H", data, pe+24)[0] == 0x20b)
    except (struct.error, IndexError):
        valid = False
    if not valid:
        raise PackageError("Expected the reviewed AMD64 PE32+ module: " + name)


def _replace(data: bytes, before: bytes, after: bytes, label: str) -> bytes:
    if data.count(before) != 1:
        raise PackageError("Reviewed adapter source changed: " + label)
    return data.replace(before, after, 1)


def _adapt(name: str, data: bytes, copy_game: str | None) -> bytes:
    if name == "world/support/world_transactions.py":
        for before, after in (
            (b'VERSION = "0.11.0-dev.1-transactions"', ('VERSION = "' + TRANSACTION_VERSION + '"').encode()),
            (b'BACKUP = "WorldFoodMod_Backup_0_11_Dev1"', ('BACKUP = "' + TRANSACTION_BACKUP + '"').encode()),
            (b'LOCK = ".worldfoodmod-0.11-dev1.lock"', ('LOCK = "' + TRANSACTION_LOCK + '"').encode()),
        ):
            data = _replace(data, before, after, name)
    if name == "world/world_mod.py":
        newline = b"\r\n" if b"\r\n" in data else b"\n"
        def block(value: str) -> bytes:
            return value.encode().replace(b"\n", newline)
        before = '''    for name, digest in spec["unchanged_native"].items():
        data = tx._path(root, name).read_bytes()
        require_amd64(data, name)
        if food.fm.sha(data) != digest:
            raise food.fm.ModError("Unsupported native fingerprint: " + name)
'''
        after = '''    deferred_native = {}
    for name, digest in spec["unchanged_native"].items():
        data = tx._path(root, name).read_bytes()
        require_amd64(data, name)
        deferred_native[name] = data
'''
        data = _replace(data, block(before), block(after), name)
        overlay_before = '''    if not installed:
        for name, overlay in spec["native_overlays"].items():
            if not overlay["food_native"] and current[name] != native[overlay["baseline_payload"]]:
                raise food.fm.ModError("Unsupported native source fingerprint: " + name)
    food_spec = json.loads((PACKAGE / "food_patch.json").read_bytes())
    food_native_names={entry["name"] for entry in food_spec["native_modules"]}
'''
        overlay_after = '''    food_spec = json.loads((PACKAGE / "food_patch.json").read_bytes())
    food_native_names={entry["name"] for entry in food_spec["native_modules"]}
    if not installed:
        for name, overlay in spec["native_overlays"].items():
            if name not in food_native_names and current[name] != native[overlay["baseline_payload"]]:
                raise food.fm.ModError("Unsupported native source fingerprint: " + name)
'''
        data = _replace(data, block(overlay_before), block(overlay_after), name)
        helper = '''def _require_composed_food_native(name, data, digest, installed, edits):
    """Accept stock input only with an exact whole-file Food output proof."""
    if food.fm.sha(data) == digest:
        return
    changes = [edit for edit in edits if edit.name == name]
    if (installed or len(changes) != 1 or changes[0].before != data
            or changes[0].offset is not None or food.fm.sha(changes[0].after) != digest):
        raise food.fm.ModError("Unsupported native fingerprint: " + name)


'''
        data = _replace(data, b"def build_edits(root, spec, progress=print):",
                        block(helper) + b"def build_edits(root, spec, progress=print):", name)
        anchor = "    state, edits = food.build_edits(root, food_spec, progress, native_overrides=overrides)"
        proof = '''
    for name, digest in spec["unchanged_native"].items():
        _require_composed_food_native(name, deferred_native[name], digest, installed, edits)'''
        data = _replace(data, block(anchor), block(anchor + proof), name)
    if copy_game is not None and name == "launcher/launch_world_settings.pyw":
        data = _replace(data, b"self.inputs = preflight.verify()",
                        b"self.inputs = preflight.verify(self.config['copy_root'])", name)
    if copy_game is not None and name == "launcher/activation_once.py":
        data = _replace(data, b"inputs=a.verify()", b"inputs=a.verify(config['copy_root'])", name)
    return data


def _source_recipe(copy_game: str | None, baselines: Path | None = None,
                   *, kinds: tuple[str, ...] = ("food", "world", "launcher")) -> dict[str, bytes]:
    """Trusted source whitelist; provider code is checked but is never executed."""
    provenance = _json(_read(ROOT, "provenance/legacy_import.json"), "source provenance")
    records = {item["path"]: item for item in provenance["source_files"]}
    result = {}
    for destination in kinds:
        family, files = _LAYOUT[destination]
        for name in files:
            public = "legacy/" + family + "/" + name
            record = records.get(public)
            if record is None:
                raise PackageError("Source is absent from reviewed provenance: " + public)
            data = _require_sha(_read(ROOT, public), record["imported_sha256"], public)
            if baselines is not None:
                _require_sha(_read(baselines / family, name), record["original_sha256"], family + "/" + name)
            target = destination + "/" + name
            result[target] = _adapt(target, data, copy_game)
    for destination in ("food", "world"):
        name = destination + "/food_patch.json"
        if destination in kinds:
            _require_sha(result[name], FOOD_SPEC_SHA256, name)
    return result


def _world_spec(raw: bytes, source_game: str, copy_game: str | None) -> tuple[dict, bytes]:
    frozen = _json(_require_sha(raw, FROZEN_WORLD_SPEC_SHA256, "frozen World Settings specification"), "frozen World Settings specification")
    if (frozen.get("version") != "0.11.0-dev.1" or frozen.get("status") != "UNFINISHED"
            or frozen.get("payloads", {}).get("native/AnnoWorldSettings.dll") != RUNTIME_SHA256
            or len(frozen.get("payloads", {})) != 25
            or set(frozen["payloads"]) != _NATIVE | set(frozen.get("data_payloads", {}))):
        raise PackageError("The frozen World Settings payload policy differs")
    spec = deepcopy(frozen)
    spec["original_game_root"] = source_game
    spec["actual_game_run"] = False
    spec["packaged_runtime_gameplay_verified"] = False
    spec["complete_feature_verified"] = False
    spec["local_installer_package"] = {
        "schema_version": 1, "adapter_version": ADAPTER_VERSION,
        "frozen_world_spec_sha256": FROZEN_WORLD_SPEC_SHA256,
        "source_root": source_game, "copy_root": copy_game,
        "actual_game_test_performed": False,
        "historical_evidence": "Retained in frozen_world_patch.json; relocation is not a new game test.",
    }
    return frozen, _encoded(spec)


def _recipe(raw: bytes, source_game: str, copy_game: str | None, baselines: Path | None = None) -> tuple[dict, dict[str, bytes]]:
    frozen, spec = _world_spec(raw, source_game, copy_game)
    result = _source_recipe(copy_game, baselines)
    _require_sha(result["world/developer/huge_world/runtime_engine_edits.json"],
                 frozen["expanded_engine_plan_sha256"], "World Settings engine instruction plan")
    result["world/frozen_world_patch.json"] = raw
    result["world/world_patch.json"] = spec
    config = {
        "version": "1.0.0", "package_relative": "../world", "package_spec_sha256": _sha(spec),
        "runtime_sha256": RUNTIME_SHA256, "engine_patch_count": 173, "timeout_seconds": 300,
        "modular_adapter_version": ADAPTER_VERSION,
    }
    if copy_game is not None:
        config["copy_root"] = copy_game
    result["launcher/launcher_config.json"] = _encoded(config)
    return frozen, result


def _manifest(source_game: str, copy_game: str | None, files: dict[str, str], *, food_only: bool = False) -> dict:
    result = {
        "schema_version": 1,
        "kind": "anno1503-food-installer-package" if food_only else "anno1503-local-installer-package",
        "adapter_version": ADAPTER_VERSION,
        "feature_versions": {"food_overhaul": "0.5.0"},
        "source_root": source_game, "copy_root": copy_game, "files": files,
        "transaction": {"backup": TRANSACTION_BACKUP, "lock": TRANSACTION_LOCK, "version": TRANSACTION_VERSION, "schema": 1},
        "actual_game_test_performed": False,
    }
    if not food_only:
        result["feature_versions"].update(world_settings="0.11.0-dev.1", launcher="1.0.0")
        result.update(frozen_world_spec_sha256=FROZEN_WORLD_SPEC_SHA256, runtime_sha256=RUNTIME_SHA256)
    return result


def _mutable(name: str) -> bool:
    # Existing helpers write only diagnostic data here. It is never executable
    # input, never hashed as an immutable package file, and must not be a link.
    return name == "world/activation_session.json" or (
        name.startswith("launcher/logs/") and name.count("/") == 2
        and name.endswith(".jsonl") and len(name) <= 180
    )


def validate_package(path: Path | str, source_game: Path | str | None = None) -> dict:
    """Recompute every immutable expected byte; a manifest cannot bless new code."""
    root = _checked_path(Path(path))
    if not root.is_dir():
        raise PackageError("Select a prepared installer package folder")
    manifest = _json(_read(root, "manifest.json"), "package manifest")
    kind = manifest.get("kind")
    if kind not in ("anno1503-food-installer-package", "anno1503-local-installer-package"):
        raise PackageError("Unknown installer package kind")
    food_only = kind == "anno1503-food-installer-package"
    source_value = manifest.get("source_root")
    copy_value = manifest.get("copy_root")
    if not isinstance(source_value, str) or (copy_value is not None and not isinstance(copy_value, str)):
        raise PackageError("Invalid package game paths")
    source = _checked_path(Path(source_value))
    if not source.is_dir() or str(source) != source_value:
        raise PackageError("Package source-game path is not canonical")
    if source_game is not None and _checked_path(Path(source_game)) != source:
        raise PackageError("This package was prepared for a different source game")
    if copy_value is not None:
        copy = _checked_path(Path(copy_value), exists=False)
        if str(copy) != copy_value or copy == source:
            raise PackageError("Package copy-game path is not independent and canonical")
    if food_only:
        expected = _source_recipe(copy_value, kinds=("food",))
    else:
        frozen, expected = _recipe(_read(root, "world/frozen_world_patch.json"), source_value, copy_value)
        for name, digest in frozen["payloads"].items():
            target = "world/" + _name(name)
            if target in expected:
                raise PackageError("World payload and helper paths overlap")
            data = _require_sha(_read(root, target), digest, target)
            if name in _NATIVE:
                _amd64(data, name)
            expected[target] = data
    digests = {name: _sha(data) for name, data in sorted(expected.items())}
    canonical = _manifest(source_value, copy_value, digests, food_only=food_only)
    if _encoded(manifest) != _encoded(canonical):
        raise PackageError("Installer manifest differs from the reviewed package recipe")
    for name, data in expected.items():
        if _read(root, name) != data:
            raise PackageError("Installer helper or configuration changed: " + name)
    expected_names = set(expected) | {"manifest.json"}
    directories = {str(parent) for name in expected_names for parent in PurePosixPath(name).parents if str(parent) != "."}
    if not food_only:
        directories.add("launcher/logs")
    for directory, child_dirs, child_files in os.walk(root, followlinks=False):
        for child in child_dirs + child_files:
            item = Path(directory) / child
            checked = _checked_path(item)
            name = item.relative_to(root).as_posix()
            if not checked.is_relative_to(root):
                raise PackageError("Installer package path leaves its root")
            if item.is_dir():
                if name not in directories:
                    raise PackageError("Unexpected installer package directory: " + name)
            elif not item.is_file() or (name not in expected_names and (food_only or not _mutable(name))):
                raise PackageError("Unexpected installer package file: " + name)
            elif _mutable(name) and item.stat().st_size > _MAX_FILE:
                raise PackageError("Installer diagnostic file exceeds its bound")
    return dict(canonical, root=root, path=root, world_path=None if food_only else root / "world", food_path=root / "food",
                launcher_path=None if food_only else root / "launcher", verified=True)


def _package_output(output_dir: Path | str, source: Path, copy: Path | None,
                    baselines: Path | None = None) -> Path:
    output = _checked_path(Path(output_dir), exists=False)
    forbidden = (ROOT / "legacy", ROOT / ".local/baselines", source,
                 *((copy,) if copy is not None else ()), *((baselines,) if baselines is not None else ()))
    if any(output == p or output.is_relative_to(p) or p.is_relative_to(output) for p in forbidden):
        raise PackageError("Prepared packages must stay separate from game inputs and preserved baselines")
    if output.is_relative_to(ROOT) and not output.is_relative_to(ROOT / ".local"):
        raise PackageError("Prepared packages inside the repository belong in ignored .local")
    if os.path.lexists(output):
        raise PackageError("Package output already exists; choose a new folder")
    return output


def _publish(files: dict[str, bytes], output: Path, source: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    _checked_path(output.parent)
    stage = output.parent / (".installer-package-staging-" + uuid.uuid4().hex)
    stage.mkdir()
    try:
        for name, data in files.items():
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(data)
        validate_package(stage, source)
        if os.path.lexists(output):
            raise PackageError("Package output appeared during preparation; refusing to overwrite it")
        stage.rename(output)
    except BaseException:
        # Only this freshly generated staging tree is removed. Preserved input
        # directories and any pre-existing output are never cleanup targets.
        if stage.exists() and stage.parent == output.parent and stage.name.startswith(".installer-package-staging-"):
            checked = _checked_path(stage)
            if checked.parent == output.parent and checked.is_relative_to(output.parent):
                shutil.rmtree(checked)
        raise
    return output


def prepare_food_package(output_dir: Path | str, source_game: Path | str,
                         copy_game: Path | str | None = None) -> Path:
    """Build Food-only installation inputs using public authored source alone."""
    source = _checked_path(Path(source_game))
    copy = None if copy_game is None else _checked_path(Path(copy_game), exists=False)
    if not source.is_dir() or source == copy:
        raise PackageError("Select an existing source game and an independent copy")
    output = _package_output(output_dir, source, copy)
    files = _source_recipe(None if copy is None else str(copy), kinds=("food",))
    manifest = _manifest(str(source), None if copy is None else str(copy),
                         {name: _sha(data) for name, data in sorted(files.items())}, food_only=True)
    files["manifest.json"] = _encoded(manifest)
    return _publish(files, output, source)


def prepare_package(baselines_dir: Path | str, output_dir: Path | str,
                    source_game: Path | str, copy_game: Path | str | None = None) -> Path:
    """Create a new local package; never overwrite a package, game or baseline."""
    baselines = _checked_path(Path(baselines_dir))
    source = _checked_path(Path(source_game))
    copy = None if copy_game is None else _checked_path(Path(copy_game), exists=False)
    if not baselines.is_dir() or not source.is_dir() or source == copy:
        raise PackageError("Select existing baselines and an independent source game")
    output = _package_output(output_dir, source, copy, baselines)
    raw = _read(baselines / "world_settings", "world_patch.json")
    frozen, files = _recipe(raw, str(source), None if copy is None else str(copy), baselines)
    for name, digest in frozen["payloads"].items():
        data = _require_sha(_read(baselines / "world_settings", name), digest, name)
        if name in _NATIVE:
            _amd64(data, name)
        files["world/" + _name(name)] = data
    manifest = _manifest(str(source), None if copy is None else str(copy),
                         {name: _sha(data) for name, data in sorted(files.items())})
    files["manifest.json"] = _encoded(manifest)
    return _publish(files, output, source)
