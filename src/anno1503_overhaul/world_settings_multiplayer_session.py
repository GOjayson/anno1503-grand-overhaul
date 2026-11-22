"""Stage and restore the optional World Settings scene on a managed LAN copy."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from .filesystem import atomic_json, read_copy_marker, safe_child
from .lan_preflight import SCENARIO, SCENE_CACHE
from .processes import require_game_closed
from .world_settings_multiplayer import encode_offer, installed_companion, prepare_offer
from .world_settings_multiplayer_catalogue import derive_generated_world_catalogue


RECEIPT = "world-settings-session.json"
_WORLD_FILES = (SCENARIO, SCENE_CACHE)


def licensed_game(copy: Path) -> Path:
    marker = read_copy_marker(copy)
    if marker["phase"] != "vanilla":
        raise ValueError("World Settings multiplayer requires an isolated stock-game copy.")
    return Path(marker["source_root"])


def require_companion(local: Path) -> None:
    if installed_companion(local) is None:
        raise ValueError("Enable the World Settings submod before using a generated world.")


def prepared_scene(copy: Path, local: Path, offer: dict) -> bytes:
    require_companion(local)
    return prepare_offer(licensed_game(copy), offer)


def _entries(copy: Path, offer: dict):
    source = licensed_game(copy)
    scene = safe_child(source, SCENARIO, exists=True).read_bytes()
    cache = safe_child(source, SCENE_CACHE, exists=True).read_bytes()
    return (
        (safe_child(copy, SCENARIO, exists=True), scene, prepare_offer(source, offer)),
        (safe_child(copy, SCENE_CACHE, exists=True), cache, derive_generated_world_catalogue(cache)),
    )


def restore_world(copy: Path, tools: Path, *, write_file) -> None:
    """Restore a previous generated map under the caller's game-copy lock."""
    require_game_closed()
    receipt = safe_child(tools, RECEIPT)
    if not receipt.exists():
        return
    if receipt.stat().st_size > 10240:
        raise RuntimeError("The saved World Settings session is invalid.")
    record = json.loads(receipt.read_bytes())
    if (not isinstance(record, dict) or record.keys() != {"version", "offer", "files"}
            or type(record["version"]) is not int or record["version"] != 1
            or not isinstance(record["files"], dict) or record["files"].keys() != set(_WORLD_FILES)):
        raise ValueError("Invalid staged World Settings record.")
    source = licensed_game(copy)
    replacements = []
    for name in _WORLD_FILES:
        original = safe_child(source, name, exists=True).read_bytes()
        target = safe_child(copy, name, exists=True)
        active = target.read_bytes()
        pins = record["files"][name]
        if (not isinstance(pins, dict) or pins.keys() != {"original", "staged"}
                or sha256(original).hexdigest() != pins["original"]):
            raise RuntimeError(f"The licensed world file differs from the staged baseline: {target.name}")
        if active == original:
            continue
        if sha256(active).hexdigest() != pins["staged"]:
            raise RuntimeError(f"The isolated world file was changed externally: {target.name}")
        replacements.append((target, original, active))
    for target, original, active in replacements:
        write_file(target, original, active)
    receipt.unlink()


def stage_world(copy: Path, tools: Path, offer: dict, *, write_file) -> None:
    """Stage a locally reconstructed map under the caller's game-copy lock."""
    require_game_closed()
    require_companion(tools.parent)
    receipt = safe_child(tools, RECEIPT)
    if receipt.exists():
        raise RuntimeError("Restore the previous World Settings session before staging.")
    entries = _entries(copy, offer)
    for path, original, _ in entries:
        if path.read_bytes() != original:
            raise RuntimeError(f"The isolated world file differs from its licensed source: {path.name}")
    files = {name: {"original": sha256(original).hexdigest(), "staged": sha256(generated).hexdigest()}
             for name, (_, original, generated) in zip(_WORLD_FILES, entries, strict=True)}
    atomic_json(receipt, {"version": 1, "offer": encode_offer(offer), "files": files})
    try:
        for path, original, generated in entries:
            if generated != original:
                write_file(path, generated, original)
        for path, _, generated in entries:
            if path.read_bytes() != generated:
                raise RuntimeError(f"The staged World Settings file changed: {path.name}")
    except (OSError, ValueError, RuntimeError):
        restore_world(copy, tools, write_file=write_file)
        raise
