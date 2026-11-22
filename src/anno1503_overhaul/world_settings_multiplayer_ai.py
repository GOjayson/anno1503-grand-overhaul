"""Author stock ordinary computer players from a verified licensed scene."""

from hashlib import sha256
from pathlib import Path
from struct import pack, pack_into, unpack_from

from .filesystem import safe_child
from .world_island_catalogue import _chunks


_DONOR_DIRECTORY = "Languages/Nl/Scenes/0010SingleEndlos"
_DONORS = (
    ("01_1024_easy_256.sze", "3e0d2c72e1ae87b76cc817f0aead7198b4f0509cb11a5246463e338ccf060e05", (3, 5, 2)),
    ("03_1024_med_256.sze", "f25b19ca1806b3e0d7093167fc240cb5c027efff4049781fe9df4973636d2de8", (1, 6, 9)),
    ("06_1024_heavy_256.sze", "d31527dc6902de498e5bb43053939fba0d6460cbfe10abef9ec5eed2f71e4453", (4, 0, 5)),
)
_DONOR_LIMIT = 64 * 1024
_HEAD_COLOR = 16 + 76
_SHIP_OFFSET = 104
_CPU_COLORS = (5, 6, 8)


def read_donor(game: Path, difficulty: int) -> bytes:
    path = safe_child(game, f"{_DONOR_DIRECTORY}/{_DONORS[difficulty][0]}", exists=True)
    with path.open("rb") as stream:
        return stream.read(_DONOR_LIMIT + 1)


def _subfields(payload: bytes):
    cursor = 0
    while cursor < len(payload):
        if len(payload) - cursor < 8:
            raise ValueError("The licensed computer-player record is truncated.")
        tag, length = unpack_from("<6sH", payload, cursor)
        cursor += 8
        if len(payload) - cursor < length:
            raise ValueError("The licensed computer-player record is truncated.")
        yield tag.rstrip(b"\0"), payload[cursor:cursor + length]
        cursor += length


def _profiles(chunks: list[tuple[bytes, bytes]]) -> tuple[bytes, tuple[int, ...]]:
    tables = [data for tag, data in chunks if tag == b"COMPPROFIL2"]
    if len(tables) != 1:
        raise ValueError("A reviewed scene is missing its computer profile table.")
    [table] = tables
    fields = tuple(_subfields(table))
    if (len(fields) != 13 or any(tag != b"ENTRY" or len(data) != 168 for tag, data in fields[:-1])
            or fields[-1][0] != b"DEF" or len(fields[-1][1]) != 128):
        raise ValueError("The licensed computer profile table differs.")
    return table[:-128], unpack_from("<32i", fields[-1][1])


def _ships_near_islands(plan, starts, venetian, origins, reserve, *, kind="computer"):
    settings = plan["settings"]
    world = settings["worldSize"]
    margin = reserve + settings["spacing"]
    islands = plan["islands"]
    occupied = [(x, y) for x, y, _ in starts] + [venetian]
    assigned = {island for _, _, island in starts}
    candidates = []
    for index, island in enumerate(islands):
        if index in assigned or island["climate"] == 0:
            continue
        left, top = island["x"], island["y"]
        width, height = island["width"], island["height"]
        outside_x = ((left - margin - 1) // 8 * 8, (left + width + margin + 7) // 8 * 8)
        outside_y = ((top - margin - 1) // 8 * 8, (top + height + margin + 7) // 8 * 8)
        for fraction in (1, 2, 3):
            x = (left + width * fraction // 4) // 8 * 8
            y = (top + height * fraction // 4) // 8 * 8
            candidates.extend((point, index) for point in (
                (outside_x[0], y), (outside_x[1], y), (x, outside_y[0]), (x, outside_y[1]),
            ))

    def clear(point):
        x, y = point
        return (reserve <= x < world - reserve and reserve <= y < world - reserve
                and all(not (x - margin < row["x"] + row["width"] and row["x"] <= x + margin
                             and y - margin < row["y"] + row["height"] and row["y"] <= y + margin)
                        for row in islands))

    candidates = [(point, index) for point, index in candidates if clear(point)]
    for origin_x, origin_y in origins:
        x = (int(origin_x * 2) * world) // 2048
        y = (int(origin_y * 2) * world) // 2048
        choices = (((px - x) ** 2 + (py - y) ** 2, px, py, index) for (px, py), index in candidates
                   if index not in assigned and all(abs(px - ox) > 2 * reserve or abs(py - oy) > 2 * reserve
                                                     for ox, oy in occupied))
        nearest = min(choices, default=None)
        if nearest is None:
            raise ValueError(f"This map has too few clear {kind} starting positions. Regenerate the preview.")
        _, px, py, index = nearest
        occupied.append((px, py))
        assigned.add(index)
        yield px, py, index


def _verified_donor(donor: bytes, difficulty: int):
    _, digest, expected_profiles = _DONORS[difficulty]
    if (not isinstance(donor, bytes) or len(donor) > _DONOR_LIMIT
            or sha256(donor).hexdigest() != digest):
        raise ValueError("The local stock computer-player scene differs from the reviewed donor.")
    [(outer_tag, outer)] = _chunks(donor, 0, len(donor))
    [(inner_tag, inner)] = _chunks(outer, 0, len(outer))
    if (outer_tag, inner_tag) != (b"ANNOADDON1", b"SCENE"):
        raise ValueError("The local stock computer-player scene envelope differs.")
    chunks = list(_chunks(inner, 0, len(inner)))
    entries, defaults = _profiles(chunks)
    if defaults[1:4] != expected_profiles:
        raise ValueError("The stock computer profiles disagree between the two scenes.")
    return chunks, entries, defaults


def _donor_seats(donor_chunks, seats):
    headers, spawns, controllers, origins = {}, {}, {}, {}
    for tag, data in donor_chunks:
        if tag != b"SPIELER" or len(data) < 16:
            continue
        version, seat = unpack_from("<II", data)
        if seat not in seats:
            continue
        if version:
            raise ValueError("The native computer-player record version differs.")
        if data[8:16] == b"HEAD\0\0l\0":
            if (len(data) < 124 or seat in headers or unpack_from("<I", data, 16)[0] != 12
                    or unpack_from("<I", data, _HEAD_COLOR)[0] != 255):
                raise ValueError("The native computer-player HEAD differs.")
            head = bytearray(data)
            # Fixed ordinary computer colors used by the licensed Multiplayer scenario.
            pack_into("<I", head, _HEAD_COLOR, _CPU_COLORS[seat - 1])
            headers[seat] = bytes(head)
        else:
            fields = tuple(_subfields(data[_SHIP_OFFSET:]))
            if seat in spawns or tuple(tag for tag, _ in fields) != (b"SCHIFF", b"COMP"):
                raise ValueError("The native computer-player ship and controller records differ.")
            (_, ship), (_, controller) = fields
            if len(ship) < 16:
                raise ValueError("The native computer-player ship is truncated.")
            _, definition, owner, x, y = unpack_from("<HHIff", ship)
            if (definition != 1502 or owner != seat or not 0 < x < 1024 or not 0 < y < 1024
                    or controller[:8] != pack("<II", 12, seat) or not controller.endswith(b"\0SUSPEND=0\0")):
                raise ValueError("The native computer-player ship ownership or active controller differs.")
            spawns[seat] = data[:_SHIP_OFFSET + 8 + len(ship)]
            controllers[seat] = data[_SHIP_OFFSET + 8 + len(ship):]
            origins[seat] = x, y
    if headers.keys() != seats or spawns.keys() != seats:
        raise ValueError("The native computer-player seats are incomplete.")

    return headers, spawns, controllers, origins


def computer_player_records(read_donor, base, plan, starts, venetian, reserve):
    """Return the profile table, native HEAD/spawn records, and start positions."""
    difficulty = plan["settings"]["difficulty"]
    count = plan["settings"]["aiCount"]
    if not 1 <= count <= len(_CPU_COLORS):
        raise ValueError("Choose one to three stock computer players.")
    ordered_seats = range(1, count + 1)
    seats = set(ordered_seats)
    standard_chunks, standard_entries, selected_defaults = _verified_donor(read_donor(1), 1)
    new_entries, current_defaults = _profiles(base)
    if new_entries != standard_entries or current_defaults != (-1,) * 32:
        raise ValueError("The stock computer profiles disagree between the two scenes.")
    headers, spawns, controllers, origins = _donor_seats(standard_chunks, seats)
    if difficulty != 1:
        chosen_chunks, chosen_entries, selected_defaults = _verified_donor(read_donor(difficulty), difficulty)
        if chosen_entries != standard_entries:
            raise ValueError("The stock computer profiles disagree between the two scenes.")
        headers, _, controllers, _ = _donor_seats(chosen_chunks, seats)

    used_ids = set()
    for tag, data in base:
        if tag != b"SPIELER":
            continue
        if len(data) < 16 or unpack_from("<I", data, 4)[0] in seats:
            raise ValueError("A computer-player start overlaps a native seat.")
        if data[_SHIP_OFFSET:_SHIP_OFFSET + 6] == b"SCHIFF":
            if len(data) < _SHIP_OFFSET + 10:
                raise ValueError("The native ship ID record is truncated.")
            used_ids.add(unpack_from("<H", data, _SHIP_OFFSET + 8)[0])
    next_ship = max(used_ids, default=0) + 1
    if next_ship + count >= 0xFFFF:
        raise ValueError("The scene does not have capacity for the computer players' ships.")
    defaults = list(current_defaults)
    adjusted = []
    locations = tuple(_ships_near_islands(plan, starts, venetian, [origins[seat] for seat in ordered_seats], reserve))
    for seat, (x, y, _) in zip(ordered_seats, locations, strict=True):
        defaults[seat] = selected_defaults[seat]
        data = bytearray(spawns[seat])
        pack_into("<H", data, _SHIP_OFFSET + 8, next_ship)
        pack_into("<ff", data, _SHIP_OFFSET + 16, x + 0.5, y + 0.5)
        # The stock presets share controller fields, but their ships can carry state
        # specific to the original map. Keep the already-reviewed Medium ships.
        adjusted.append(bytes(data) + controllers[seat])
        next_ship += 1
    return new_entries + pack("<32i", *defaults), tuple(headers[seat] for seat in ordered_seats), tuple(adjusted), locations
