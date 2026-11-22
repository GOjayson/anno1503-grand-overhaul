"""Build the optional native-menu map without updating any loaded game inputs."""
from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from hashlib import sha256
import os
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile

from .filesystem import file_sha, read_copy_marker, safe_child
from .world_options_snapshot import decode
from .world_settings_multiplayer import FEATURE, export_snapshot, validate_offer
from .world_settings_multiplayer_linked import ISLAND_DIR, link_generated_islands, stock_trailer
from .world_settings_multiplayer_native import build_start_plan, choose_preview, supports_start_layout


WORLD_RUNTIME = "AnnoGrandWorldSettings/AnnoWorldSettings.dll"
WORLD_MARKER = "ingame_world_settings_selected"
MATCH_DIR = "AnnoGrandMatches"
MAX_SCENE_SIZE = 16 * 1024 * 1024


def _catalogue_root() -> Path:
    bundled = getattr(sys, "_MEIPASS", None)
    return Path(bundled) if bundled else Path(__file__).resolve().parents[2]


def require_runtime(game: Path, pin: str | None) -> Path:
    if pin is None:
        raise ValueError("This copy has no reviewed World Settings companion build.")
    if read_copy_marker(game).get(WORLD_MARKER) is False:
        raise ValueError("World Settings was not selected for this multiplayer copy.")
    runtime = safe_child(game, WORLD_RUNTIME)
    if not runtime.is_file() or file_sha(runtime) != pin:
        raise ValueError("Enable the matching World Settings submod on this copy.")
    return runtime


def select_world(game: Path, pin: str, owner: int) -> bytes | None:
    runtime = require_runtime(game, pin)
    return choose_preview(
        runtime, pin, owner=owner, allow_start_layout=supports_start_layout(runtime, pin), preset_root=game,
    )


def start_resolver(game: Path, pin: str, *, allow_huge: bool = False):
    """Return the optional local reader for builds that can verify all starts."""
    runtime = require_runtime(game, pin)
    if supports_start_layout(runtime, pin):
        return partial(build_start_plan, runtime, pin, allow_huge=allow_huge)
    return None


@dataclass(frozen=True)
class GeneratedWorld:
    offer: dict
    scene_size: int
    map_visibility: int
    enemy_visibility: int

    @property
    def digest(self) -> bytes:
        return bytes.fromhex(self.offer["artifact_sha256"])


def _checked_shadow(target: Path, size: int, digest: str) -> None:
    if (not target.is_file() or target.stat().st_nlink != 1 or target.stat().st_size != size
            or file_sha(target) != digest):
        raise ValueError("A generated multiplayer map differs from its verified content.")


def _publish_artifact(folder: Path, data: bytes, digest: str, extension: str) -> None:
    if not 0 < len(data) <= MAX_SCENE_SIZE:
        raise ValueError("A generated multiplayer file exceeds the native size limit.")
    folder.mkdir(exist_ok=True)
    target = safe_child(folder, digest + extension)
    if not target.exists():
        staging = None
        try:
            with NamedTemporaryFile(dir=folder, prefix=".world-", suffix=".tmp", delete=False) as output:
                staging = Path(output.name)
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            # Rename on Windows publishes the complete map and refuses replacement.
            try:
                if os.name == "nt":
                    staging.rename(target)
                else:
                    os.link(staging, target)
                    staging.unlink()
            except FileExistsError:
                pass
        finally:
            if staging is not None:
                staging.unlink(missing_ok=True)
    _checked_shadow(safe_child(folder, target.name, exists=True), len(data), digest)


def _generated(game: Path, scene: bytes, offer: dict, islands: dict[str, bytes] | None = None) -> GeneratedWorld:
    digest = offer["artifact_sha256"]
    if islands:
        folder = safe_child(game, ISLAND_DIR)
        for island_digest, island in islands.items():
            _publish_artifact(folder, island, island_digest, ".scp")
    _publish_artifact(safe_child(game, MATCH_DIR), scene, digest, ".sze")
    settings = decode(offer["payload"])["settings"]
    return GeneratedWorld(offer, len(scene), settings["mapVisibility"], settings["enemyVisibility"])


def _linked_world(game: Path, snapshot: bytes, allow_unexplored: bool, resolve_starts, *,
                  allow_reveal_activity: bool = False,
                  allow_huge: bool = False, allow_ai: bool = False, allow_disasters: bool = False,
                  human_slots: int = 4, allow_factions: bool = False, allow_cultures: bool = False,
                  allow_peaceful_ai: bool = False, allow_faction_activity: bool = False):
    populated_assets = {} if allow_factions or allow_cultures else None
    inline = export_snapshot(game, snapshot, catalogue_root=_catalogue_root(), allow_unexplored=allow_unexplored,
                             allow_fully_explored=allow_unexplored, allow_huge=allow_huge, allow_ai=allow_ai,
                             allow_reveal_activity=allow_reveal_activity, allow_peaceful_ai=allow_peaceful_ai,
                             resolve_starts=resolve_starts, allow_disasters=allow_disasters, human_slots=human_slots,
                             populated_assets=populated_assets, allow_factions=allow_factions, allow_cultures=allow_cultures,
                             allow_faction_activity=allow_faction_activity)
    discover_humans = decode(snapshot)["settings"]["mapVisibility"] == 2
    return link_generated_islands(inline, stock_trailer(game), discover_humans=discover_humans,
                                  populated_assets=populated_assets)


def make_world(game: Path, snapshot: bytes, *, allow_unexplored: bool = False, allow_reveal_activity: bool = False,
               allow_huge: bool = False, allow_ai: bool = False, allow_disasters: bool = False, resolve_starts=None,
               human_slots: int = 4, allow_factions: bool = False, allow_cultures: bool = False,
               allow_peaceful_ai: bool = False, allow_faction_activity: bool = False) -> GeneratedWorld:
    scene, islands = _linked_world(game, snapshot, allow_unexplored, resolve_starts,
                                   allow_huge=allow_huge, allow_ai=allow_ai,
                                   allow_reveal_activity=allow_reveal_activity, allow_peaceful_ai=allow_peaceful_ai,
                                   allow_disasters=allow_disasters, human_slots=human_slots, allow_factions=allow_factions,
                                   allow_cultures=allow_cultures, allow_faction_activity=allow_faction_activity)
    offer = {"feature": FEATURE[0], "schema": FEATURE[1], "payload": snapshot,
             "artifact_sha256": sha256(scene).hexdigest()}
    return _generated(game, scene, offer, islands)


def receive_world(game: Path, offer: dict, *, allow_unexplored: bool = False, allow_reveal_activity: bool = False,
                  allow_huge: bool = False, allow_ai: bool = False, allow_disasters: bool = False, resolve_starts=None,
                  human_slots: int = 4, allow_factions: bool = False, allow_cultures: bool = False,
                  allow_peaceful_ai: bool = False, allow_faction_activity: bool = False) -> GeneratedWorld:
    validate_offer(offer)
    scene, islands = _linked_world(game, offer["payload"], allow_unexplored, resolve_starts,
                                   allow_huge=allow_huge, allow_ai=allow_ai,
                                   allow_reveal_activity=allow_reveal_activity, allow_peaceful_ai=allow_peaceful_ai,
                                   allow_disasters=allow_disasters, human_slots=human_slots, allow_factions=allow_factions,
                                   allow_cultures=allow_cultures, allow_faction_activity=allow_faction_activity)
    if sha256(scene).hexdigest() != offer["artifact_sha256"]:
        raise ValueError("The generated map differs from the host's preview.")
    return _generated(game, scene, offer, islands)
