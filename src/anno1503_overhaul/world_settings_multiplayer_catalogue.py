"""Expose the World Settings submod's generated scene in the native catalogue."""

from hashlib import sha256
from struct import Struct


STOCK_SCENE_CACHE_SHA256 = "fb45b61805480e3177df07d0dd073844ea816e8e4594040e6dfcf8b6f6160caf"
GENERATED_SCENARIO_ALIAS = b"Custom world (2-4)"

_ENTRY_HEADER = Struct("<12sI")
_ENTRY_PAYLOAD_SIZE = 384
_ENTRY_SIZE = _ENTRY_HEADER.size + _ENTRY_PAYLOAD_SIZE
_STOCK_ENTRY_COUNT = 55
_STOCK_MULTIPLAYER_COUNT = 5
_MULTIPLAYER_TYPES = {3, 5}
_NEW_EARTH_PATH = b"Scenes\\0500MultiEndlos\\"
_NEW_EARTH_NAME = b"NewEarth.sze"
_NEW_EARTH_GUID = bytes.fromhex("8c93300df2fe494880c43080ca511525")
_ALIAS_START = 136
_ALIAS_END = _ALIAS_START + 260
_GENERATED_ALIAS = GENERATED_SCENARIO_ALIAS.ljust(_ALIAS_END - _ALIAS_START, b"\0")


def derive_generated_world_catalogue(stock: bytes) -> bytes:
    """Rename the reviewed New Earth entry and retain the complete stock list."""
    if (
        not isinstance(stock, bytes)
        or len(stock) != _STOCK_ENTRY_COUNT * _ENTRY_SIZE
        or sha256(stock).hexdigest() != STOCK_SCENE_CACHE_SHA256
    ):
        raise ValueError("Expected the reviewed Dutch History Edition scenario cache.")

    entries = []
    multiplayer_count = 0
    generated_count = 0
    for offset in range(0, len(stock), _ENTRY_SIZE):
        entry = stock[offset:offset + _ENTRY_SIZE]
        tag, size = _ENTRY_HEADER.unpack_from(entry)
        if tag.rstrip(b"\0") != b"ENTRY" or size != _ENTRY_PAYLOAD_SIZE:
            raise ValueError("The scenario cache entry layout changed.")
        if entry[16] in _MULTIPLAYER_TYPES:
            multiplayer_count += 1
        directory = entry[40:88].split(b"\0", 1)[0]
        filename = entry[88:136].split(b"\0", 1)[0]
        if (directory, filename) == (_NEW_EARTH_PATH, _NEW_EARTH_NAME):
            if entry[16] != 5 or entry[18:20] != b"\x02\x04" or entry[24:40] != _NEW_EARTH_GUID:
                raise ValueError("The New Earth scenario cache identity changed.")
            entry = entry[:_ALIAS_START] + _GENERATED_ALIAS + entry[_ALIAS_END:]
            generated_count += 1
        entries.append(entry)

    if multiplayer_count != _STOCK_MULTIPLAYER_COUNT or generated_count != 1:
        raise ValueError("The expected multiplayer scenario cache entries changed.")
    return b"".join(entries)
