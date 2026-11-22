"""Build native standalone islands for the in-game multiplayer scene loader."""

from hashlib import sha256
from pathlib import Path
from struct import pack, unpack_from

from .filesystem import safe_child
from .world_island_catalogue import _chunks
from .world_settings_multiplayer_island import _ISLAND_FIELDS, _chunk


ISLAND_DIR = "Scenes/WS"
_INLINE_STATE = {b"DISCOVER", b"KONTORID", b"PROD2", b"HIRSCH", b"EVENTINSEL"}
_TRAILER_SOURCE = "Scenes/Islands/Dschungel/D_064x064_0001_0B.scp"
_TRAILER_SOURCE_SHA = "a9a3429a23c451c576f23941aabc62cab60b006bcf1d3f24e9681c696dd809a8"
_TRAILER_SHA = "614a2810ea249aab06ad5f0620a90eaffef27b383eb54e7e86a15f7642493a39"
_HUMAN_DISCOVERY_MASK = 0x0381  # Native New Earth seats 0, 7, 8 and 9.


def stock_trailer(game: Path) -> bytes:
    source = safe_child(game, _TRAILER_SOURCE, exists=True)
    with source.open("rb") as stream:
        sample = stream.read(16 * 1024 * 1024 + 1)
    if sha256(sample).hexdigest() != _TRAILER_SOURCE_SHA:
        raise ValueError("The licensed standalone island has changed.")
    trailer = sample[16 + unpack_from("<I", sample, 12)[0]:]
    if len(trailer) != 60 or sha256(trailer).hexdigest() != _TRAILER_SHA:
        raise ValueError("The licensed standalone island trailer differs.")
    return trailer


def link_generated_islands(scene: bytes, trailer: bytes, *, discover_humans: bool = False,
                           populated_assets: dict[str, bytes] | None = None) -> tuple[bytes, dict[str, bytes]]:
    """Use the same island loader for both World classes, with local verified inputs."""
    [(container, body)] = _chunks(scene, 0, len(scene))
    [(section, content)] = _chunks(body, 0, len(body))
    if (container, section) != (b"ANNO", b"SCENE"):
        raise ValueError("The generated New Earth container differs.")
    records = list(_chunks(content, 0, len(content)))
    definitions = [value for tag, value in records if tag == b"WARETYPE"]
    if len(definitions) != 1:
        raise ValueError("The generated New Earth object table is missing or duplicated.")
    ware_types = _chunk(b"WARETYPE", definitions[0])
    populated_assets = populated_assets or {}
    populated_paths = {f"WS\\{digest}.scp".encode("ascii") + b"\0": digest
                     for digest, data in populated_assets.items() if sha256(data).hexdigest() == digest}
    if len(populated_paths) != len(populated_assets):
        raise ValueError("The generated New Earth contains an invalid special faction asset.")
    found_populated = set()
    linked, assets = [], {}
    for tag, value in records:
        if tag == b"INSELLNK":
            digest = populated_paths.get(value[12:])
            if digest is None:
                raise ValueError("The generated New Earth contains an unexpected island link.")
            found_populated.add(value[12:])
            assets[digest] = populated_assets[digest]
        if tag == b"INSEL5":
            fields = list(_chunks(value, 12, len(value)))
            if any(name not in _ISLAND_FIELDS | _INLINE_STATE for name, _ in fields):
                raise ValueError("The generated island contains unsupported standalone fields.")
            # Position and ID belong to the scene. Stock SCPs have zero for both.
            geometry = bytes(4) + value[4:8] + bytes(4)
            local = geometry + b"".join(_chunk(name, data) for name, data in fields if name in _ISLAND_FIELDS)
            if discover_humans:
                discovery_fields = [data for name, data in fields if name == b"DISCOVER"]
                if len(discovery_fields) != 1 or len(discovery_fields[0]) != 4:
                    raise ValueError("The generated island has invalid native discovery state.")
                discovery = discovery_fields[0]
                discovered, = unpack_from("<H", discovery)
                local += _chunk(b"DISCOVER", pack("<H", discovered | _HUMAN_DISCOVERY_MASK) + discovery[2:])
            island = _chunk(b"ANNO", ware_types + _chunk(b"INSEL5", local)) + trailer
            digest = sha256(island).hexdigest()
            assets[digest] = island
            path = f"WS\\{digest}.scp".encode("ascii") + b"\0"
            tag, value = b"INSELLNK", value[:12] + path
        linked.append(_chunk(tag, value))
    if not assets or found_populated != populated_paths.keys():
        raise ValueError("The generated New Earth is missing the reviewed island links.")
    return _chunk(b"ANNO", _chunk(b"SCENE", b"".join(linked))), assets
