"""Optional World Settings provider for the multiplayer launcher."""
from __future__ import annotations

import base64
import binascii
from hashlib import sha256
import json
from pathlib import Path
import re

from .filesystem import safe_child
from .world_options_snapshot import SNAPSHOT_SIZE, decode


FEATURE = ("world-settings", 1)
COMPANION_DIR = "world-settings-multiplayer"
COMPANION_MANIFEST = "provider.json"
RUNTIME_NAME = "AnnoWorldSettings.dll"
CATALOGUE = (
    "legacy/world_settings/developer/source/engine_resume/"
    "ai_food/experiment_runtime/world_catalogue.h"
)
_REPO = Path(__file__).resolve().parents[2]
_SHA = re.compile(r"[0-9a-f]{64}")


def installed_companion(local: Path) -> dict | None:
    """Read the explicit World Settings companion registration, if enabled."""
    manifest = safe_child(local, f"{COMPANION_DIR}/{COMPANION_MANIFEST}")
    if not manifest.exists():
        return None
    if manifest.stat().st_size > 1024:
        raise ValueError("Invalid World Settings companion registration.")
    config = json.loads(manifest.read_bytes())
    if not isinstance(config, dict) or config.keys() != {"feature", "schema", "native_sha256"}:
        raise ValueError("Invalid World Settings companion registration.")
    if (config["feature"], config["schema"]) != FEATURE or type(config["schema"]) is not int:
        raise ValueError("Unsupported World Settings companion registration.")
    pin = config["native_sha256"]
    if pin is not None and (not isinstance(pin, str) or not _SHA.fullmatch(pin)):
        raise ValueError("Invalid World Settings companion runtime fingerprint.")
    return config


def encode_offer(offer: dict) -> str:
    return json.dumps({**offer, "payload": base64.b64encode(offer["payload"]).decode("ascii")},
                      separators=(",", ":"))


def decode_offer(value: str) -> dict:
    if not isinstance(value, str) or len(value) > 9000:
        raise ValueError("Invalid World Settings offer.")
    offer = json.loads(value)
    if not isinstance(offer, dict) or offer.keys() != {"feature", "schema", "payload", "artifact_sha256"}:
        raise ValueError("Invalid World Settings offer.")
    if not isinstance(offer["payload"], str):
        raise ValueError("Invalid World Settings offer.")
    try:
        payload = base64.b64decode(offer["payload"], validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Invalid World Settings preview encoding.") from exc
    if base64.b64encode(payload).decode("ascii") != offer["payload"]:
        raise ValueError("Invalid World Settings preview encoding.")
    return {**offer, "payload": payload}


def export_snapshot(licensed_game: Path, snapshot: bytes, *, catalogue_root: Path = _REPO,
                    allow_unexplored: bool = False, allow_fully_explored: bool = False, allow_reveal_activity: bool = False,
                    allow_huge: bool = False, allow_ai: bool = False, allow_disasters: bool = False, human_slots: int = 4,
                    resolve_starts=None, populated_assets: dict[str, bytes] | None = None, allow_peaceful_ai: bool = False,
                    allow_factions: bool = False, allow_cultures: bool = False, allow_faction_activity: bool = False) -> bytes:
    from .world_settings_multiplayer_scene import export_multiplayer_scene_from_game

    catalogue = safe_child(catalogue_root, CATALOGUE, exists=True).read_bytes()
    return export_multiplayer_scene_from_game(
        licensed_game, snapshot, catalogue, allow_unexplored=allow_unexplored,
        allow_fully_explored=allow_fully_explored, allow_huge=allow_huge, allow_ai=allow_ai,
        allow_disasters=allow_disasters, allow_reveal_activity=allow_reveal_activity, allow_peaceful_ai=allow_peaceful_ai,
        human_slots=human_slots, resolve_starts=resolve_starts, populated_assets=populated_assets,
        recipe_root=catalogue_root, allow_factions=allow_factions, allow_cultures=allow_cultures,
        allow_faction_activity=allow_faction_activity,
    )


def validate_offer(offer: dict) -> None:
    if (not isinstance(offer, dict) or offer.keys() != {"feature", "schema", "payload", "artifact_sha256"}
            or (offer["feature"], offer["schema"]) != FEATURE or type(offer["schema"]) is not int
            or not isinstance(offer["payload"], bytes) or len(offer["payload"]) != SNAPSHOT_SIZE
            or not isinstance(offer["artifact_sha256"], str) or not _SHA.fullmatch(offer["artifact_sha256"])):
        raise ValueError("Invalid multiplayer World Settings preview.")


def prepare_offer(licensed_game: Path, offer: dict, *, catalogue_root: Path = _REPO,
                  allow_unexplored: bool = False, resolve_starts=None) -> bytes:
    validate_offer(offer)
    scene = export_snapshot(licensed_game, offer["payload"], catalogue_root=catalogue_root,
                            allow_unexplored=allow_unexplored, resolve_starts=resolve_starts)
    if sha256(scene).hexdigest() != offer["artifact_sha256"]:
        raise ValueError("The generated map differs from the host's preview.")
    return scene


def choose_game_world(local: Path, licensed_game: Path) -> tuple[str, str] | None:
    from .world_settings_multiplayer_native import choose_preview

    config = installed_companion(local)
    if config is None or config["native_sha256"] is None:
        raise ValueError("Enable the World Settings host companion before generating a map.")
    runtime = safe_child(local, f"{COMPANION_DIR}/{RUNTIME_NAME}", exists=True)
    snapshot = choose_preview(runtime, config["native_sha256"])
    if snapshot is None:
        return None
    scene = export_snapshot(licensed_game, snapshot)
    view = decode(snapshot)
    offer = {"feature": FEATURE[0], "schema": FEATURE[1],
             "payload": snapshot, "artifact_sha256": sha256(scene).hexdigest()}
    return encode_offer(offer), f"World Settings map ready · seed {view['seed']} · {view['count']} islands"
