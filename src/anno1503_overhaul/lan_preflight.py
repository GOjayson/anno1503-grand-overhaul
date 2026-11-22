"""Check matching retail inputs and run the two-player LAN preflight."""
from __future__ import annotations

import argparse
from collections.abc import Mapping
import hashlib
import json
from pathlib import Path
import sys

from .filesystem import CopyError, checked_path, file_sha, is_reparse, safe_child
from .lan_identity import load_player, set_player_name
from .lan_room import host_preflight, join_preflight
from .vanilla import VANILLA_ARCHIVE_HASHES
from .world_runtime_build import STOCK_SHA256


SCENARIO = "Scenes/0500MultiEndlos/NewEarth.sze"
SCENE_CACHE = "Scenes/Scenes.cach"
DEFAULT_PORT = 51503

_WORLD_TREES = (
    ("Scenes/0500MultiEndlos", ".sze"),
    ("Scenes/0700Multi", ".sze"),
    ("Scenes/Islands", ".scp"),
)

# The exact stock engine and archive baselines already reviewed by the project.
# Other selected inputs are compared across peers by their actual bytes.
STOCK_INPUTS = {**STOCK_SHA256, **VANILLA_ARCHIVE_HASHES}
COMPARED_INPUTS = (
    "AnnoDisplay.dll",
    "AnnoDisplayAddOn.dll",
    "AnnoFrameAddOn.dll",
    "AnnoGameAddOn.dll",
    "AnnoSceneAddOn.dll",
    "AnnoWeltAddOn.dll",
    "Data/BGruppen.dat",
    "Data/Felder.dat",
    "Data/Highmap.dat",
    "Data/Wachstum.dat",
    "Data/wegspeed.dat",
    "Figuren.addon",
    "Figuren.classic",
    "Figuren.dat",
    SCENARIO,
    SCENE_CACHE,
)


def _world_inputs(root: Path) -> dict[str, str]:
    """Find every selectable multiplayer scene and its loose island inputs."""
    found = {}
    for directory, extension in _WORLD_TREES:
        start = safe_child(root, directory)
        if not start.is_dir():
            raise ValueError(f"Missing required LAN preflight directory: {directory}")
        pending = [start]
        while pending:
            for child in checked_path(pending.pop()).iterdir():
                relative = child.relative_to(root).as_posix()
                if is_reparse(child):
                    raise CopyError(f"Linked folders or files are not supported: {relative}")
                if child.is_dir():
                    pending.append(child)
                elif child.suffix.casefold() == extension:
                    key = relative.casefold()
                    if key in found:
                        raise ValueError(f"Conflicting Windows filenames in LAN preflight: {relative}")
                    found[key] = relative
    return found


def game_fingerprint(game: Path, *, native_baselines: Mapping[str, tuple[str, str]] | None = None) -> str:
    """Fingerprint the selected inputs independently of machine and copy location."""
    root = checked_path(game)
    native_baselines = native_baselines or {}
    files = {}
    paths = {name: safe_child(root, name) for name in (*STOCK_INPUTS, *COMPARED_INPUTS)}
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise ValueError("Missing required LAN preflight inputs: " + ", ".join(missing))
    # Endless maps link loose SCPs. The derived InselCache.txt stores absolute
    # machine paths, so compare the source templates instead of that cache.
    world_inputs = _world_inputs(root)
    paths.update({name: safe_child(root, name) for key, name in world_inputs.items() if key != SCENARIO.casefold()})
    for name, path in paths.items():
        if not path.is_file():
            raise ValueError(f"Missing required LAN preflight input: {name}")
        before = path.stat()
        digest = file_sha(path)
        after = path.stat()
        if (before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_ino, after.st_size, after.st_mtime_ns
        ):
            raise ValueError(f"LAN preflight input changed during verification: {name}")
        if name in native_baselines:
            derivative, baseline = native_baselines[name]
            if digest not in (derivative, baseline):
                raise ValueError(f"LAN preflight found an unverified native derivative: {name}")
            digest = baseline
        expected = STOCK_INPUTS.get(name)
        if expected is not None and digest != expected:
            raise ValueError(f"LAN preflight requires the supported stock game inputs: {name}")
        files[name.casefold()] = digest
    if world_inputs != _world_inputs(root):
        raise ValueError("The LAN scenario or island inventory changed during verification.")
    data = json.dumps({"version": 4, "files": files}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("ascii")).hexdigest()


def add_commands(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--player-file", type=Path, help="Use a specific local identity file")
    actions = parser.add_subparsers(dest="lan_action", required=True)
    identity = actions.add_parser("name", help="Show or change your local display name")
    identity.add_argument("display_name", nargs="?")
    check = actions.add_parser("check", help="Fingerprint the selected stock game and scenario files")
    host = actions.add_parser("host", help="Listen for one guest and check matching inputs")
    host.add_argument("--bind", default="127.0.0.1", help="Local IPv4 address to listen on")
    join = actions.add_parser("join", help="Connect to the host and check matching inputs")
    join.add_argument("address", help="Host's private IPv4 address")
    for action in (check, host, join):
        action.add_argument("--game", type=Path, required=True, help="Path to a stock History Edition copy")
    for action in (host, join):
        action.add_argument("--name", help="Change your saved display name before connecting")
        action.add_argument("--port", type=int, default=DEFAULT_PORT)


def run_command(args: argparse.Namespace) -> dict:
    if args.lan_action == "name":
        player = (
            load_player(args.player_file)
            if args.display_name is None
            else set_player_name(args.display_name, args.player_file)
        )
        if player is None:
            raise ValueError("Set a name with the lan name command.")
        return {"display_name": player.display_name}

    fingerprint = game_fingerprint(args.game)
    result = {"scenario": SCENARIO, "fingerprint": fingerprint}
    if args.lan_action == "check":
        return result

    player = (
        load_player(args.player_file)
        if args.name is None
        else set_player_name(args.name, args.player_file)
    )
    if player is None:
        raise ValueError("Supply --name or set a name with the lan name command.")

    if args.lan_action == "host":
        def listening(address: str, port: int) -> None:
            print(f"Waiting for one LAN guest at {address}:{port}.", file=sys.stderr, flush=True)

        peer = host_preflight(player, fingerprint, args.bind, args.port, on_listening=listening)
    else:
        peer = join_preflight(player, fingerprint, args.address, args.port)
    return {
        **result,
        "preflight": "passed",
        "display_name": player.display_name,
        "peer_display_name": peer.display_name,
    }
