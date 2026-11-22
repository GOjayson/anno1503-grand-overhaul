"""Extend a verified New Earth scene with four native human starts."""

from struct import pack, pack_into, unpack_from

from .world_settings_multiplayer_ai import _ships_near_islands


EXTRA_HUMAN_SEATS = (1, 2, 3, 4)
_STOCK_HUMANS = (0, 7, 8, 9)
_STOCK_NEUTRALS = (5, 6, 10, 11, 12, 13)
_SHIP_START = 112
_ORIGINS = ((256, 256), (768, 256), (768, 768), (256, 768))
_SCRIPT_BOUNDARY = b'"HUMAN04" 9\n'
_ERROR = "The reviewed New Earth records cannot supply eight human starts."


def extra_human_starts(plan, starts, venetian, reserve):
    return tuple(_ships_near_islands(plan, starts, venetian, _ORIGINS, reserve, kind="human"))


def _fields(data: bytes, start: int, end: int) -> dict[bytes, tuple[int, int]]:
    fields = {}
    while start < end:
        if end - start < 8:
            raise ValueError(_ERROR)
        tag, length = unpack_from("<6sH", data, start)
        tag = tag.rstrip(b"\0")
        start += 8
        next_field = start + length
        if tag in fields or next_field > end:
            raise ValueError(_ERROR)
        fields[tag] = (start, next_field)
        start = next_field
    return fields


def _field_range(fields: dict, tag: bytes) -> tuple[int, int]:
    try:
        return fields[tag]
    except KeyError:
        raise ValueError(_ERROR) from None


def _stock_ship_ids(player: bytes, seat: int) -> tuple[int, ...]:
    fields = _fields(player, 8, len(player))
    ship_start, ship_end = _field_range(fields, b"SCHIFF")
    if ship_start != _SHIP_START or ship_end - ship_start < 16:
        raise ValueError(_ERROR)
    expected = (1505, 1029) if seat == 5 else (1502, seat)
    if unpack_from("<HI", player, ship_start + 2) != expected:
        raise ValueError(_ERROR)
    private = _field_range(_fields(player, ship_start + 16, ship_end), b"PRIVAT")
    if seat == 5:
        return (ship_start,)

    crew = _field_range(_fields(player, *private), b"CREW")
    entry, entry_end = _field_range(_fields(player, *crew), b"ENTRY")
    if entry_end - entry < 6 or unpack_from("<HH", player, entry + 2) != (717, 0):
        raise ValueError(_ERROR)
    private = _field_range(_fields(player, entry + 6, entry_end), b"PRIVAT")
    donkey, donkey_end = _field_range(_fields(player, *private), b"ESEL")
    if donkey_end - donkey < 8 or unpack_from("<H", player, donkey)[0] != 718:
        raise ValueError(_ERROR)
    return ship_start, entry, donkey + 2


def _with_neutral_relations(player: bytes, seat: int) -> bytes:
    begin, end = _field_range(_fields(player, 8, len(player)), b"DIPL")
    tag = b"WAR\0\0\0" if seat == 6 else b"TRADE\0"
    relation = tag + b"\x04\0"
    source = relation + b"\0\x03\0\0"
    if player[begin:end].count(source) != 1:
        raise ValueError(_ERROR)
    entries = b"".join(relation + bytes((owner, 3, 0, 0)) for owner in EXTRA_HUMAN_SEATS)
    after_host = player.index(source, begin, end) + len(source)
    return (player[:begin - 2] + pack("<H", end - begin + len(entries))
            + player[begin:after_host] + entries + player[after_host:])


def eight_human_records(
    base: list[tuple[bytes, bytes]], starts: tuple[tuple[int, int, int], ...],
) -> list[tuple[bytes, bytes]]:
    """Clone the pinned human HEAD and three-object starting fleet into free owners."""
    heads, spawns = {}, {}
    object_ids = set()
    parts = []
    script_found = False
    for tag, payload in base:
        if tag == b"SPIELER":
            if len(payload) < 16:
                raise ValueError(_ERROR)
            version, seat = unpack_from("<II", payload)
            if version or seat in EXTRA_HUMAN_SEATS:
                raise ValueError(_ERROR)
            if payload[8:16] == b"HEAD\0\0l\0":
                if seat in heads:
                    raise ValueError(_ERROR)
                heads[seat] = payload
                if seat in _STOCK_NEUTRALS:
                    payload = _with_neutral_relations(payload, seat)
            elif payload[_SHIP_START - 8:_SHIP_START - 2] == b"SCHIFF":
                if seat not in (*_STOCK_HUMANS, 5) or seat in spawns:
                    raise ValueError(_ERROR)
                positions = _stock_ship_ids(payload, seat)
                for offset in positions:
                    identifier, = unpack_from("<H", payload, offset)
                    if identifier in object_ids or identifier == 0xFFFF:
                        raise ValueError(_ERROR)
                    object_ids.add(identifier)
                spawns[seat] = (payload, positions)
        elif tag == b"BIGBROTHER":
            if (script_found or payload.count(_SCRIPT_BOUNDARY) != 1
                    or b"[PLAYERMAPPER_DEFINE]\n" not in payload or b"[SCRIPT_KERNEL]\n" not in payload):
                raise ValueError(_ERROR)
            additions = b"".join(f'"HUMAN{alias:02d}" {seat}\n'.encode("ascii")
                                 for alias, seat in enumerate(EXTRA_HUMAN_SEATS, 5))
            payload = payload.replace(_SCRIPT_BOUNDARY, _SCRIPT_BOUNDARY + additions)
            script_found = True
        parts.append((tag, payload))
    if (set(heads) != {*_STOCK_HUMANS, *_STOCK_NEUTRALS, 31}
            or set(spawns) != {*_STOCK_HUMANS, 5} or not script_found or len(starts) != 4):
        raise ValueError(_ERROR)

    template = heads[0]
    alias_start, alias_end = _field_range(_fields(template, 8, len(template)), b"ALIAS")
    if template[alias_start:alias_end] != b"HUMAN01\0" or unpack_from("<II", template, 16) != (8, 30_000):
        raise ValueError(_ERROR)
    if unpack_from("<I", template, 92)[0] != 0xFF:
        raise ValueError(_ERROR)

    spawn, positions = spawns[0]
    next_id = max(object_ids) + 1
    if next_id + len(positions) * len(EXTRA_HUMAN_SEATS) > 0xFFFF:
        raise ValueError(_ERROR)
    new_heads, new_spawns = [], []
    for alias, (seat, (x, y, _)) in enumerate(zip(EXTRA_HUMAN_SEATS, starts, strict=True), 5):
        name = f"HUMAN{alias:02d}\0".encode("ascii")
        head = template[:4] + pack("<I", seat) + template[8:alias_start] + name + template[alias_end:]
        new_heads.append((b"SPIELER", head))

        ships = bytearray(spawn)
        pack_into("<I", ships, 4, seat)
        pack_into("<Iff", ships, _SHIP_START + 4, seat, x + 0.5, y + 0.5)
        for offset in positions:
            pack_into("<H", ships, offset, next_id)
            next_id += 1
        new_spawns.append((b"SPIELER", bytes(ships)))

    # Keep all HEADs before island loads and all fleets after their player exists.
    head_end = max(index for index, (tag, payload) in enumerate(parts)
                   if tag == b"SPIELER" and payload[8:16] == b"HEAD\0\0l\0") + 1
    player_end = max(index for index, (tag, _) in enumerate(parts) if tag == b"SPIELER") + 1
    return [*parts[:head_end], *new_heads, *parts[head_end:player_end], *new_spawns, *parts[player_end:]]
