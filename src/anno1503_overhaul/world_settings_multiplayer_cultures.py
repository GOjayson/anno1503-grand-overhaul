"""Prepare native owners for the culture settlements in generated New Earth."""

from collections import Counter
from hashlib import sha256
from pathlib import Path
from struct import pack, unpack_from

from .filesystem import safe_child
from .world_island_catalogue import _chunks
from .world_settings_multiplayer_ai import _subfields
from .world_settings_multiplayer_factions import _field, _linked_populated_island


_CULTURES = {
    1: b"MAUREN\0", 2: b"MONGOLEN\0", 4: b"BEDUINEN\0", 8: b"AZTEKEN\0",
    16: b"AFRIKANER\0", 32: b"INDIANER\0", 64: b"ESKIMOS\0", 128: b"SUEDSEE\0",
}
_STOCK_SEATS = {10: 32, 11: 8, 12: 16, 13: 64}
_SEATS = range(10, 31)
_CAPACITY = len(_SEATS)
_DONOR_LIMIT = 5 * 1024 * 1024
_DONORS = (
    ("Languages/Nl/Scenes/0011SingleEndlosAddon/endless01.sze",
     "236351e7e62c2a6f4ee6bb08a1d5b7dfdceeabe2510baa5def446af029ef8585", {2: 128, 4: 2, 5: 1}),
    ("Languages/Nl/Scenes/0011SingleEndlosAddon/endless02.sze",
     "a5a36ca6c7710cfe67b64e3b543dfcd1972511080bf5814d352155b02508e833", {6: 4}),
)


def donor_names(game: Path, requested: set[int]) -> dict[int, bytes]:
    """Take only the authentic 32-byte player names from the needed stock cultures."""
    names = {}
    for relative, digest, seats in _DONORS:
        expected = requested.intersection(seats.values())
        if not expected:
            continue
        path = safe_child(game, relative, exists=True)
        with path.open("rb") as stream:
            source = stream.read(_DONOR_LIMIT + 1)
        if len(source) > _DONOR_LIMIT or sha256(source).hexdigest() != digest:
            raise ValueError("The local culture donor scenario differs from the reviewed file.")
        [(root, body)] = _chunks(source, 0, len(source))
        [(section, body)] = _chunks(body, 0, len(body))
        if root != b"ANNOADDON1" or section != b"SCENE":
            raise ValueError("The native culture donor scenario envelope differs.")
        for tag, value in _chunks(body, 0, len(body)):
            if tag != b"SPIELER" or value[8:16] != b"HEAD\0\0l\0":
                continue
            version, seat = unpack_from("<II", value)
            if seat not in seats or seats[seat] not in expected:
                continue
            bit = seats[seat]
            fields = dict(_subfields(value[8:]))
            head = fields[b"HEAD"]
            name = head[8:40]
            if (version or bit in names or fields.get(b"VOLK") != _CULTURES[bit]
                    or unpack_from("<I", head)[0] != 14 or len(name) != 32 or not name[0] or name[-1]):
                raise ValueError("The native culture donor profile differs.")
            names[bit] = name
        if not expected.issubset(names):
            raise ValueError("The native culture donor profiles are incomplete.")
    return names


def culture_players(base: list[tuple[bytes, bytes]], islands: list[dict], enabled: int,
                    read_names) -> list[tuple[bytes, bytes]]:
    """Register one distinct native owner per planned settlement before island import."""
    count = Counter(row["cultures"] for row in islands if row["cultures"])
    if any(bit not in _CULTURES for bit in count) or sum(count) != enabled:
        raise ValueError("The preview culture settlements differ from the selected cultures.")
    if count.total() > _CAPACITY:
        raise ValueError("The native world has room for up to 21 culture towns. Regenerate with fewer islands.")

    heads, states, kept = {}, {}, []
    script_at, tail_at = None, None
    for tag, value in base:
        if tag == b"SPIELER":
            version, seat = unpack_from("<II", value)
            if seat in _SEATS and (version or seat not in _STOCK_SEATS):
                raise ValueError("A native culture owner overlaps another player.")
            if seat in _STOCK_SEATS:
                bit = _STOCK_SEATS[seat]
                fields = list(_subfields(value[8:]))
                alias = f"COM_NATIVE_{seat - 9:02d}".encode("ascii")
                if fields and fields[0][0] == b"HEAD":
                    head = fields[0][1]
                    if (bit in heads or len(head) != 108 or unpack_from("<I", head)[0] != 14
                            or [d for t, d in fields if t == b"VOLK"] != [_CULTURES[bit]]
                            or [d for t, d in fields if t == b"ALIAS"] != [alias + b"\0"]):
                        raise ValueError("The New Earth culture profile differs.")
                    heads[bit] = fields
                else:
                    if (bit in states or [t for t, _ in fields] != [*(f"SEL_{i}".encode() for i in range(8)), b"COMP"]
                            or fields[-1][1][:8] != pack("<II", 14, seat)
                            or not fields[-1][1].endswith(b"\0SUSPEND=0\0")):
                        raise ValueError("The New Earth culture controller differs.")
                    states[bit] = fields
                continue
            tail_at = len(kept) + 1
        elif tag == b"BIGBROTHER":
            if script_at is not None:
                raise ValueError("The New Earth culture script is duplicated.")
            script_at = len(kept)
        kept.append((tag, value))
    if heads.keys() != set(_STOCK_SEATS.values()) or states.keys() != heads.keys() or None in (script_at, tail_at):
        raise ValueError("The New Earth culture owners or native script are missing.")

    reserved = {bit: seat for seat, bit in _STOCK_SEATS.items() if bit in count}
    vacant = iter(seat for seat in _SEATS if seat not in reserved.values())
    missing = set(count).difference(heads)
    names = read_names(missing) if missing else {}
    if names.keys() != missing:
        raise ValueError("The selected culture donor names are incomplete.")
    new_heads, new_states, mappings = [], [], {}
    for bit in sorted(count):
        stock = bit if bit in heads else 32
        for index in range(count[bit]):
            seat = reserved[bit] if bit in reserved and index == 0 else next(vacant)
            alias = f"COM_NATIVE_{seat - 9:02d}".encode("ascii")
            mappings[seat] = alias
            prefix = pack("<II", 0, seat)
            fields = []
            for tag, value in heads[stock]:
                if tag == b"HEAD" and bit in names:
                    value = value[:8] + names[bit] + value[40:]
                elif tag == b"VOLK":
                    value = _CULTURES[bit]
                elif tag == b"ALIAS":
                    value = alias + b"\0"
                fields.append(_field(tag, value))
            new_heads.append((b"SPIELER", prefix + b"".join(fields)))
            fields = [_field(tag, pack("<II", 14, seat) + value[8:] if tag == b"COMP" else value)
                      for tag, value in states[stock]]
            new_states.append((b"SPIELER", prefix + b"".join(fields)))

    tag, script = kept[script_at]
    original = {f'"COM_NATIVE_{seat - 9:02d}" {seat}'.encode() for seat in _STOCK_SEATS}
    lines, seen = [], set()
    for line in script.splitlines(keepends=True):
        text = line.rstrip(b"\r\n")
        if text not in original:
            lines.append(line)
        elif text not in seen:
            if not seen:
                lines.extend(b'"' + alias + b'" ' + str(seat).encode("ascii") + b"\n"
                             for seat, alias in sorted(mappings.items()))
            seen.add(text)
        else:
            raise ValueError("The New Earth culture script contains duplicate mappings.")
    if seen != original:
        raise ValueError("The New Earth culture script mappings are missing.")
    kept[script_at] = tag, b"".join(lines)
    kept[tail_at:tail_at] = new_states
    first_island = next((i for i, (tag, _) in enumerate(kept) if tag == b"INSELLNK"), None)
    if first_island is None:
        raise ValueError("The New Earth culture island links are missing.")
    kept[first_island:first_island] = new_heads
    return kept


def linked_culture_island(entry: dict, row: dict, template: bytes, ware_types: bytes,
                           visibility: int) -> tuple[bytes, str, bytes]:
    """Keep the native settlement's culture and stock matching through its empty alias."""
    bit = row["cultures"]
    if bit not in _CULTURES or entry["fields"][3] != bit or entry["fields"][6]:
        raise ValueError("The selected native culture template differs from the preview.")
    return _linked_populated_island(entry, row, template, ware_types, visibility, _CULTURES[bit], b"")
