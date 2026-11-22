"""Prepare a separate player-owned Venetian fountain for a local prototype."""

from collections.abc import Iterable, Iterator
from hashlib import sha256
from mmap import ACCESS_READ, mmap
from pathlib import Path
from struct import pack, unpack_from


FOUNTAIN_ID = 1611
VENETIAN_FOUNTAIN_ID = 3971
ORNAMENTAL_WELL_ID = 2555
DEFINITION_LIMIT = 4000
HEADER_SIZE = 16
ENTRY_PREFIX_SIZE = 8

# Same game assets in each archive, with separate palette and pixel references.
FOUNTAIN_SOURCE_HASHES = {
    "anlagen.addon": (
        "dded4950260706acc8d5e4fae89e7521e0e537d79ef76e88a9f074b49d9ee3ea",
        "ea7287411d6a2df51e9b372ad64883dd39fcb0fcc2111edbb60d2f45e3cf5d1d",
    ),
    "anlagen.dat": (
        "461a08f68e08dc5fe104a779ebf8b374aa1b07d80024c3af85cc6c5917dc78ef",
        "273adae9e8e67c882c2cbd6da8082da46e27644a2cf6876d71bd40e6ec6e86ba",
    ),
    "anlagen.classic": (
        "9ba9b5e112c5942028246976ba10db16dbddf393835bac3fae22ba8619537443",
        "fa92f2f16c5e2aa38e06e6a96cfc0513920eb36b785fb237df1e13cd097559e7",
    ),
}


def _chunks(
    data: bytes | mmap, start: int, end: int
) -> Iterator[tuple[bytes, int, int]]:
    while start < end:
        if end - start < HEADER_SIZE:
            raise ValueError("Truncated ANNO chunk header")
        tag = data[start:start + 12].rstrip(b"\0")
        length, = unpack_from("<I", data, start + 12)
        following = start + HEADER_SIZE + length
        if following > end:
            raise ValueError(f"ANNO chunk {tag!r} exceeds its container")
        yield tag, start, following
        start = following


def _chunk(tag: bytes, payload: bytes) -> bytes:
    if not 1 <= len(tag) <= 12:
        raise ValueError(f"Invalid ANNO chunk name {tag!r}")
    return tag.ljust(12, b"\0") + pack("<I", len(payload)) + payload


def _archive_catalogue(data: mmap) -> tuple[int, int]:
    if len(data) < HEADER_SIZE or data[:12] != b"ANNO".ljust(12, b"\0"):
        raise ValueError("Archive lacks an ANNO header")
    length, = unpack_from("<I", data, 12)
    if length != len(data) - HEADER_SIZE:
        raise ValueError("Invalid ANNO archive length")
    sections = [
        (start, end)
        for tag, start, end in _chunks(data, HEADER_SIZE, len(data))
        if tag == b"ANLAGEN"
    ]
    if len(sections) != 1:
        raise ValueError("Archive must contain one ANLAGEN section")
    start, end = sections[0]
    if end - start > 8 * 1024 * 1024:
        raise ValueError("ANLAGEN section exceeds known size bound")
    return start, end


def _entry_id(entry: bytes) -> int:
    if len(entry) < HEADER_SIZE + ENTRY_PREFIX_SIZE:
        raise ValueError("Truncated ANLAGEN entry prefix")
    if entry[:12] != b"ENTRY".ljust(12, b"\0"):
        raise ValueError("Invalid ANLAGEN entry marker")
    length, ident = unpack_from("<I4xI", entry, 12)
    if length != len(entry) - HEADER_SIZE or not 0 < ident < DEFINITION_LIMIT:
        raise ValueError(f"Invalid ANLAGEN entry size or ID {ident}")
    return ident


def _catalogue_entries(data: mmap, start: int, end: int) -> dict[int, bytes]:
    entries = {}
    for _, entry_start, entry_end in _chunks(data, start + HEADER_SIZE, end):
        entry = data[entry_start:entry_end]
        ident = _entry_id(entry)
        if ident in entries:
            raise ValueError(f"Duplicate ANLAGEN entry {ident}")
        entries[ident] = entry
    return entries


def read_entries(path: Path) -> dict[int, bytes]:
    """Return original compiled entries including their outer chunk headers."""
    with path.open("rb") as source, mmap(source.fileno(), 0, access=ACCESS_READ) as data:
        return _catalogue_entries(data, *_archive_catalogue(data))


def entry_fields(entry: bytes) -> dict[bytes, bytes]:
    """Decode the ordered tagged payloads after an ANLAGEN entry prefix."""
    ident = _entry_id(entry)
    fields = {}
    for tag, start, end in _chunks(entry, HEADER_SIZE + ENTRY_PREFIX_SIZE, len(entry)):
        if tag in fields:
            raise ValueError(f"ANLAGEN entry {ident} contains duplicate {tag!r} fields")
        fields[tag] = entry[start + HEADER_SIZE:end]
    return fields


def make_entry(source: bytes, new_id: int, replacements: dict[bytes, bytes]) -> bytes:
    """Clone one entry with a new ID and verified replacements for existing fields."""
    if not 0 < new_id < DEFINITION_LIMIT:
        raise ValueError(f"Invalid ANLAGEN entry ID {new_id}")
    fields = entry_fields(source)
    if replacements.keys() - fields.keys():
        raise ValueError(f"Entry {_entry_id(source)} lacks required replacement fields")
    fields.update(replacements)
    prefix = source[HEADER_SIZE:HEADER_SIZE + 4] + pack("<I", new_id)
    return _chunk(b"ENTRY", prefix + b"".join(_chunk(tag, value) for tag, value in fields.items()))


def fountain_entry(path: Path, new_id: int = FOUNTAIN_ID) -> bytes:
    """Use the small Venetian fountain's sprite and footprint as a player ornament."""
    entries = read_entries(path)
    if new_id in entries:
        raise ValueError(f"ANLAGEN definition ID {new_id} is already occupied")
    player_well = entries[ORNAMENTAL_WELL_ID]
    venetian_fountain = entries[VENETIAN_FOUNTAIN_ID]
    source_hashes = (sha256(player_well).hexdigest(), sha256(venetian_fountain).hexdigest())
    if source_hashes != FOUNTAIN_SOURCE_HASHES.get(path.name.lower()):
        raise ValueError(f"Unexpected fountain source definitions in {path.name}")
    return make_player_ornament(player_well, venetian_fountain, new_id)


def make_player_ornament(player_entry: bytes, art_entry: bytes, new_id: int) -> bytes:
    """Copy player construction metadata onto a matching 2×2 ornament."""
    player = entry_fields(player_entry)
    art = entry_fields(art_entry)
    if art[b"HEAD"][:2] != player[b"HEAD"][:2] or len(art[b"WALKMASK"]) != 24:
        raise ValueError("Player and ornament footprints differ")
    # Keep the player's ornamental type, cost, faction availability and menu group.
    # Preserve the ornament's geometry, palette and inline references to existing pixels.
    return make_entry(art_entry, new_id, {
        tag: player[tag] for tag in (b"VERSION2", b"HEAD", b"PRODTYPE", b"PROD3")
    })


def append_entries(path: Path, additions: Iterable[bytes]) -> bytes:
    """Insert compiled entries by ID and preserve existing archive data."""
    with path.open("rb") as source, mmap(source.fileno(), 0, access=ACCESS_READ) as data:
        start, end = _archive_catalogue(data)
        entries = _catalogue_entries(data, start, end)
        if list(entries) != sorted(entries):
            raise ValueError("ANLAGEN definitions are out of order")
        for entry in additions:
            ident = _entry_id(entry)
            if ident in entries:
                raise ValueError(f"ANLAGEN definition ID {ident} is already occupied")
            entry_fields(entry)
            entries[ident] = entry
        catalogue = _chunk(b"ANLAGEN", b"".join(entries[ident] for ident in sorted(entries)))
        payload_size = len(data) - HEADER_SIZE + len(catalogue) - (end - start)
        with memoryview(data) as original:
            return b"".join((data[:12], pack("<I", payload_size), original[16:start],
                             catalogue, original[end:]))
