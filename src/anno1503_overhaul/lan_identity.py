"""Persist a local player identity for the LAN multiplayer preflight."""

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import unicodedata
from uuid import UUID, uuid4

from .beta_paths import application_data
from .filesystem import atomic_json, checked_path


_IDENTITY_FILENAME = "lan-player.json"
_MAX_IDENTITY_BYTES = 1024
_MAX_DISPLAY_NAME_LENGTH = 24


class PlayerIdentityError(ValueError):
    """The local identity or player data is invalid."""


@dataclass(frozen=True)
class PlayerIdentity:
    player_id: str
    display_name: str


def validate_display_name(name: str) -> str:
    """Return a trimmed NFC display name with no non-printing characters."""
    message = f"Use a display name with 1 to {_MAX_DISPLAY_NAME_LENGTH} printable characters."
    if not isinstance(name, str) or not name.isprintable():
        raise PlayerIdentityError(message)
    normalized = unicodedata.normalize("NFC", name).strip()
    if not 1 <= len(normalized) <= _MAX_DISPLAY_NAME_LENGTH:
        raise PlayerIdentityError(message)
    return normalized


def validate_player_id(player_id: str) -> str:
    """Require the canonical, lowercase spelling of a random UUID."""
    message = "The LAN player ID must be a canonical UUIDv4."
    if not isinstance(player_id, str):
        raise PlayerIdentityError(message)
    try:
        parsed = UUID(player_id)
    except ValueError as exc:
        raise PlayerIdentityError(message) from exc
    if parsed.version != 4 or str(parsed) != player_id:
        raise PlayerIdentityError(message)
    return player_id


def _identity_path(path: str | Path | None) -> Path:
    target = application_data() / _IDENTITY_FILENAME if path is None else Path(path)
    return checked_path(target, exists=False)


def _unique_keys(pairs):
    values = dict(pairs)
    if len(values) != len(pairs):
        raise ValueError("Duplicate player identity field.")
    return values


def load_player(path: str | Path | None = None) -> PlayerIdentity | None:
    """Read the player's saved name and stable ID, if an identity exists."""
    target = _identity_path(path)
    try:
        with target.open("rb") as stream:
            raw = stream.read(_MAX_IDENTITY_BYTES + 1)
    except FileNotFoundError:
        return None
    try:
        if len(raw) > _MAX_IDENTITY_BYTES:
            raise ValueError("Player identity is too large.")
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_keys)
        if (not isinstance(value, dict) or set(value) != {"schema_version", "player_id", "display_name"}
                or type(value["schema_version"]) is not int or value["schema_version"] != 1):
            raise ValueError("Unknown player identity format.")
        player_id = validate_player_id(value["player_id"])
        name = validate_display_name(value["display_name"])
        if name != value["display_name"]:
            raise ValueError("The saved player name is not normalized.")
    except (ValueError, RecursionError) as exc:
        raise PlayerIdentityError("The saved LAN player identity is invalid.") from exc
    return PlayerIdentity(player_id, name)


def _publish_new_player(path: Path, document: dict) -> None:
    """Publish the complete identity without replacing a concurrent first save."""
    staged = path.with_name(f".{path.name}.{uuid4().hex}.new")
    try:
        atomic_json(staged, document)
        if os.name == "nt":
            staged.rename(path)
        else:
            os.link(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def set_player_name(display_name: str, path: str | Path | None = None) -> PlayerIdentity:
    """Save a new name, keeping the existing ID for this local player."""
    name = validate_display_name(display_name)
    target = _identity_path(path)
    existing = load_player(target)
    if existing is None:
        new = PlayerIdentity(str(uuid4()), name)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            _publish_new_player(target, dict(schema_version=1, **asdict(new)))
        except FileExistsError:
            existing = load_player(target)
            if existing is None:
                raise PlayerIdentityError("The saved LAN player identity changed while setting the name.")
        else:
            return new
    updated = PlayerIdentity(existing.player_id, name)
    if updated != existing:
        atomic_json(target, dict(schema_version=1, **asdict(updated)))
    return updated
