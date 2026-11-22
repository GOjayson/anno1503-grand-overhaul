"""Export the supported native World Settings preview into a New Earth scene."""
from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256
from pathlib import Path, PurePosixPath
from struct import pack, unpack_from

from .filesystem import checked_path, file_sha, safe_child
from .vanilla import VANILLA_ARCHIVE_HASHES
from .world_island_catalogue import _chunks, catalogue_rows, coastal_shape
from .world_island_rotation import definition_dimensions
from .world_options_snapshot import decode
from .world_settings_multiplayer_ai import computer_player_records, read_donor
from .world_settings_multiplayer_catalogue import GENERATED_SCENARIO_ALIAS
from .world_settings_multiplayer_cultures import culture_players, donor_names, linked_culture_island
from .world_settings_multiplayer_factions import faction_for_template, faction_players, linked_faction_island
from .world_settings_multiplayer_island import NO_START_ISLAND, inline_island, verify_starting_resources
from .world_settings_multiplayer_roster import EXTRA_HUMAN_SEATS, eight_human_records, extra_human_starts


SCENARIO = "Scenes/0500MultiEndlos/NewEarth.sze"
SOURCE_SHA256 = "29a9edee36b319f56fa71124a4222a7c3bacccdfb0efdc2436acdd91de99b2a7"
_STOCK_ALIAS = b"[#441#]".ljust(128, b"\0")
# The pinned scene's four human trade ships each have four eight-byte holds.
_SHIP_OFFSET = 104
_CARGO_OFFSET = _SHIP_OFFSET + 8 + 48
_STANDARD_CARGO = pack("<HHIHHIHHIHHI", 42, 50, 0, 26, 10, 0, 41, 50, 0, 41, 30, 0)
_EASY_CARGO = _STANDARD_CARGO[:-8] + pack("<HHI", 41, 50, 0)
_SECOND_SEAT_CARGO = pack("<HHIHHIHHIHHI", 42, 50, 0, 26, 50, 0, 41, 50, 0, 41, 50, 0)
_MERCHANT_CARGO = pack("<HHIHHI", 41, 40, 0, 42, 40, 0)
_HUMAN_SHIP_TILES = {0: (494, 357), 7: (394, 461), 8: (357, 521), 9: (419, 679)}
_HUMAN_SEATS = set(_HUMAN_SHIP_TILES)
# Use the native single-player anchor layout outside stock New Earth. Each row is
# the four New Earth human seats (0, 7, 8, 9) followed by the Venetian seat (5).
HUGE_WORLD_SIZE = 2048
WORLD_SHIP_TILES = {
    256: ((128, 224), (32, 224), (80, 224), (176, 224), (224, 224)),
    512: ((256, 170), (128, 128), (384, 128), (384, 384), (128, 384)),
    1024: (*_HUMAN_SHIP_TILES.values(), (109, 901)),
    HUGE_WORLD_SIZE: ((1024, 682), (512, 512), (1536, 512), (1536, 1536), (512, 1536)),
}
SHIP_RESERVE = 24
_SHIP_SEATS = (*_HUMAN_SHIP_TILES, 5)
_MAX_TEMPLATE_BYTES = 4 * 1024 * 1024
_MAX_SCENE_BYTES = 16 * 1024 * 1024
_REQUEST_SIZES = {b"ROHSTOFF": 16, b"ERZE": 10, b"SCHATZ": 2}
_FIRE_PLAGUE_MASK = 0x03
_WEATHER_DISASTER_MASK = 0x1C
# Low byte of New Earth's HEAD + 0x10. Native multiplayer handles weather together.
_FIRE_PLAGUE_DISABLED = 0x08
_WEATHER_DISASTERS_DISABLED = 0x86
StartResolver = Callable[[dict], tuple[bytes, tuple[tuple[int, int, int], ...]]]


def _chunk(tag: bytes, payload: bytes) -> bytes:
    return tag.ljust(12, b"\0") + pack("<I", len(payload)) + payload


def _field(tag: bytes, payload: bytes) -> bytes:
    return tag.ljust(6, b"\0") + pack("<H", len(payload)) + payload


def multiplayer_disaster_guid(snapshot: bytes, *, peaceful_ai: bool = False) -> bytes:
    guid = sha256(b"Anno1503 multiplayer disaster settings\0" + snapshot).digest()[:16]
    return b"WSMPAI0!" + guid[8:] if peaceful_ai else guid


def _disaster_scene_flags(flags: int, settings: dict, *, individual: bool = False) -> int:
    active = settings["disasterMask"] if settings["disasters"] else 0
    flags &= ~(_FIRE_PLAGUE_DISABLED | _WEATHER_DISASTERS_DISABLED)
    if not active & _FIRE_PLAGUE_MASK:
        flags |= _FIRE_PLAGUE_DISABLED
    if individual:
        for disaster, disabled in ((4, 2), (8, 128), (16, 4)):
            if not active & disaster:
                flags |= disabled
    elif not active & _WEATHER_DISASTER_MASK:
        flags |= _WEATHER_DISASTERS_DISABLED
    return flags


def _source_chunks(source: bytes) -> list[tuple[bytes, bytes]]:
    if not isinstance(source, bytes) or sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError("The licensed New Earth scene differs from the reviewed input.")
    [(root_tag, root)] = _chunks(source, 0, len(source))
    [(scene_tag, scene)] = _chunks(root, 0, len(root))
    if (root_tag, scene_tag) != (b"ANNO", b"SCENE"):
        raise ValueError("The New Earth scene envelope differs.")
    return list(_chunks(scene, 0, len(scene)))


def _uses_resolved_starts(settings: dict) -> bool:
    return bool(settings["fairStarts"] or settings["startIsland"] >= 0 or settings["startClimate"] >= 0
                or settings["startSeparation"] != 1)


def _supported_preview(snapshot: bytes, allow_unexplored: bool, allow_start_layout: bool, *,
                       allow_fully_explored: bool = False, allow_huge: bool = False,
                       allow_ai: bool = False, allow_factions: bool = False, allow_cultures: bool = False, allow_disasters: bool = False,
                       allow_reveal_activity: bool = False, allow_peaceful_ai: bool = False,
                       allow_faction_activity: bool = False) -> dict:
    plan = decode(snapshot)
    if plan["state_name"] != "ready":
        raise ValueError("Choose and accept a ready World Settings preview.")
    settings = plan["settings"]
    tiles = WORLD_SHIP_TILES.get(settings["worldSize"])
    map_mode = settings["mapVisibility"]
    if (tiles is None
            or (settings["worldSize"] == HUGE_WORLD_SIZE and allow_huge is not True)
            or (settings["aiCount"] != 0 and allow_ai is not True)
            or (settings["aiDifficulty"] != 1 and not (allow_peaceful_ai and settings["aiDifficulty"] == 0))
            or (settings["factions"] != 0 and not allow_factions)
            or (settings["cultures"] != 0 and not allow_cultures)
            or (map_mode != 1 and not (map_mode == 0 and allow_unexplored)
                and not (map_mode == 2 and allow_fully_explored))
            or (settings["enemyVisibility"] != 0 and not allow_reveal_activity)
            or (not allow_disasters and (
                settings["disasterMask"] not in (0, _FIRE_PLAGUE_MASK, _WEATHER_DISASTER_MASK, 31)
                or settings["disasterFrequency"] != 341 or settings["disasterSeverity"] != 341))
            or (_uses_resolved_starts(settings) and not allow_start_layout)
            or settings["pirateStrength"] != 1
            or (not allow_faction_activity and
                (settings["pirateFrequency"] != 1 or settings["merchantFrequency"] != 1))):
        raise ValueError("The preview uses World Settings choices that multiplayer cannot apply yet.")
    for row in plan["islands"]:
        if any(row["x"] < x + SHIP_RESERVE + 1 and x - SHIP_RESERVE < row["x"] + row["width"] and
               row["y"] < y + SHIP_RESERVE + 1 and y - SHIP_RESERVE < row["y"] + row["height"]
               for x, y in tiles):
            raise ValueError("An island is too close to a multiplayer starting ship. Regenerate the preview.")
    return plan


def _resolved_starts(plan: dict, snapshot: bytes,
                     resolve: StartResolver | None) -> tuple[tuple[int, int, int], ...]:
    settings = plan["settings"]
    world = settings["worldSize"]
    stock = WORLD_SHIP_TILES[world]
    if not _uses_resolved_starts(settings):
        return tuple((x, y, NO_START_ISLAND) for x, y in stock[:-1])
    if resolve is None:
        raise ValueError("Starting fleets require the verified multiplayer World Settings planner.")
    rebuilt, starts = resolve(settings)
    failure = "The rebuilt multiplayer starting fleets differ from the verified preview."
    if rebuilt != snapshot or len(starts) != 4:
        raise ValueError(failure)
    boxes = list(stock)
    side = 2 * SHIP_RESERVE + 1
    assigned = set()
    for owner, ((x, y, island), origin) in enumerate(zip(starts, stock[:-1], strict=True)):
        moved = (x, y) != origin
        if ((not settings["fairStarts"] and owner > 0 and moved)
                or (settings["fairStarts"] and not moved)
                or (owner == 0 and (settings["startIsland"] >= 0 or settings["startClimate"] >= 0) and not moved)):
            raise ValueError(failure)
        if not moved:
            continue
        if (not 0 <= island < len(plan["islands"])
                or island in assigned
                or not SHIP_RESERVE <= x < world - SHIP_RESERVE
                or not SHIP_RESERVE <= y < world - SHIP_RESERVE
                or any(abs(x - px) < side and abs(y - py) < side for px, py in boxes)):
            raise ValueError(failure)
        row = plan["islands"][island]
        if owner == 0 and (settings["startIsland"] not in (-1, island)
                           or settings["startClimate"] not in (-1, row["climate"])):
            raise ValueError(failure)
        gap = settings["spacing"]
        if any(x - SHIP_RESERVE - gap < other["x"] + other["width"] and
               other["x"] < x + SHIP_RESERVE + 1 + gap and
               y - SHIP_RESERVE - gap < other["y"] + other["height"] and
               other["y"] < y + SHIP_RESERVE + 1 + gap for other in plan["islands"]):
            raise ValueError(failure)
        assigned.add(island)
        boxes.append((x, y))
    return starts


def _verified_island(entry: dict, read_template: Callable[[str], bytes]) -> tuple[bytes, tuple[int, int, int]]:
    relative = PurePosixPath(entry["path"])
    if relative.parts[:2] != ("Scenes", "Islands") or entry["fields"][3] or entry["fields"][6]:
        raise ValueError("The preview requires an island with unsupported local scenario state.")
    template = read_template(relative.as_posix())
    if (not isinstance(template, bytes) or len(template) > _MAX_TEMPLATE_BYTES
            or sha256(template).hexdigest() != entry["sha256"]):
        raise ValueError(f"The local World Settings island differs from the reviewed file: {relative}")
    shape = coastal_shape(template)
    root_end = 16 + unpack_from("<I", template, 12)[0]
    if tuple(tag for tag, _ in _chunks(template, 16, root_end)) != (b"WARETYPE", b"INSEL5"):
        raise ValueError("A local island contains records outside its native geography.")
    geometry = (shape["width"], shape["height"], shape["climate"])
    if geometry != tuple(entry["fields"][:3]):
        raise ValueError("The local island geometry or climate differs from the World Settings catalogue.")
    return template, geometry


def _islands(plan: dict, catalogue: bytes, read_template: Callable[[str], bytes], ware_types: bytes,
             read_dimensions: Callable[[], dict[int, tuple[int, int]]] | None,
             starts: tuple[tuple[int, int, int], ...], *,
             populate_factions: Callable[[str], bytes] | None, allow_cultures: bool,
             populated_assets: dict[str, bytes] | None) -> list[bytes]:
    entries = catalogue_rows(catalogue)
    dimensions = {}
    if any(row["rotation"] for row in plan["islands"]):
        if read_dimensions is None:
            raise ValueError("Island rotation requires verified native terrain definitions.")
        dimensions = read_dimensions()
    verified = {}
    islands = []
    size = 0
    settings = plan["settings"]
    remaining_factions = settings["factions"]
    for row in plan["islands"]:
        index = row["templateIndex"]
        entry = entries[index]
        faction = faction_for_template(entry)
        if faction:
            if populate_factions is None or populated_assets is None or not remaining_factions & faction:
                raise ValueError("The preview has an unselected or duplicate special faction island.")
            remaining_factions ^= faction
            island, digest, asset = linked_faction_island(entry, row, populate_factions(entry["path"]),
                                                          ware_types, settings["mapVisibility"])
            populated_assets[digest] = asset
        elif row["cultures"]:
            if not allow_cultures or populated_assets is None:
                raise ValueError("The preview requires an unavailable native culture settlement.")
            island, digest, asset = linked_culture_island(entry, row, read_template(entry["path"]),
                                                           ware_types, settings["mapVisibility"])
            populated_assets[digest] = asset
        else:
            if index not in verified:
                verified[index] = _verified_island(entry, read_template)
            template, geometry = verified[index]
            if (row["width"], row["height"], row["climate"]) != geometry or row["cultures"]:
                raise ValueError("The preview island differs from its reviewed template.")
            island = inline_island(template, row, entry["fields"][4], ware_types, dimensions)
        size += len(island)
        if size > _MAX_SCENE_BYTES:
            raise ValueError("The generated multiplayer world exceeds its native scene budget.")
        islands.append(island)
    if remaining_factions:
        raise ValueError("The preview is missing a selected special faction island.")
    if settings["guaranteeBasics"]:
        world = settings["worldSize"]
        verify_starting_resources(plan["islands"], entries, starts, world)
    return islands


def _starting_cargo(settings: dict, definition: int) -> bytes:
    capacity = {1502: 32, 1503: 64, 1504: 16}[definition]
    if definition == 1504:
        return bytes(capacity)
    if not settings["cargoMode"]:
        if settings["startingFleet"] == 2:
            cargo = _MERCHANT_CARGO
        else:
            cargo = _EASY_CARGO if settings["difficulty"] == 0 else _STANDARD_CARGO
        return cargo.ljust(capacity, b"\0")
    # Apply the same goods order and independent 50-ton slots as the native
    # World Settings writer. Remainders of different goods cannot share a hold.
    holds = bytearray()
    for good, key in ((41, "cargoTools"), (42, "cargoWood"), (26, "cargoFood")):
        amount = settings[key]
        while amount:
            tons = min(amount, 50)
            holds.extend(pack("<HHI", good, tons, 0))
            amount -= tons
    if len(holds) > capacity:
        raise ValueError("Custom cargo exceeds the starting trade ship holds.")
    return bytes(holds).ljust(capacity, b"\0")


def _move_starting_ship(player: bytes, seat: int, tiles: dict[int, tuple[int, int]]) -> bytes:
    index = _SHIP_SEATS.index(seat)
    stock_x, stock_y = WORLD_SHIP_TILES[1024][index]
    ship_start = _SHIP_OFFSET + 8
    expected = (1505, 1029) if seat == 5 else (1502, seat)
    if (len(player) < ship_start + 16
            or unpack_from("<HIff", player, ship_start + 2) != (*expected, stock_x + 0.5, stock_y + 0.5)):
        raise ValueError("The New Earth human or Venetian ship anchor differs from the preview reserve.")
    x, y = tiles[seat]
    if (x, y) == (stock_x, stock_y):
        return player
    return player[:ship_start + 8] + pack("<ff", x + 0.5, y + 0.5) + player[ship_start + 16:]


def _starting_ships(player: bytes, seat: int, settings: dict) -> tuple[bytes, bytes]:
    cargo_end = _CARGO_OFFSET + len(_STANDARD_CARGO)
    expected = _SECOND_SEAT_CARGO if seat == 7 else _STANDARD_CARGO
    if (player[_SHIP_OFFSET + 10:_SHIP_OFFSET + 16] != pack("<HI", 1502, seat)
            or player[_CARGO_OFFSET - 8:_CARGO_OFFSET] != b"WAREN\0\x20\0"
            or player[_CARGO_OFFSET:cargo_end] != expected):
        raise ValueError("The New Earth human ship or starting cargo differs.")
    fleet = settings["startingFleet"]
    if fleet == 0:
        cargo = _starting_cargo(settings, 1502)
        return player[:_CARGO_OFFSET] + cargo + player[cargo_end:], b""

    ship_start = _SHIP_OFFSET + 8
    head_start = ship_start + 16
    private_start = cargo_end + 8
    if (len(player) < private_start
            or unpack_from("<H", player, _SHIP_OFFSET + 6)[0] != len(player) - ship_start
            or player[head_start:head_start + 8] != b"HEAD\0\0\x10\0"
            or player[cargo_end:cargo_end + 6] != b"PRIVAT"
            or unpack_from("<H", player, cargo_end + 6)[0] != len(player) - private_start):
        raise ValueError("The New Earth human ship fields differ.")
    ship_id, _, _, x, y = unpack_from("<HHIff", player, ship_start)

    # Match World Settings' native starting fleet fields. Keep the original
    # lead ship ID and private data. The two SCHI64 escorts get native IDs.
    head = _field(b"HEAD", pack("<BBHIBB6x", 3, 255, 0, 0x00FFFF00, 6 if fleet == 1 else 0, 128))
    lead = pack("<HHIff", ship_id, 1503, seat, x, y)
    lead += head + _field(b"WAREN", _starting_cargo(settings, 1503)) + player[cargo_end:]
    escorts = [pack("<II", 0, seat)]
    definition = 1504 if fleet == 1 else 1502
    cargo = _field(b"WAREN", _starting_cargo(settings, definition))
    for index, delta in enumerate((-6, 6), 1):
        prefix = pack("<IHB5xff", 0xFFFFFFFF, definition, seat, x + delta, y + 6)
        name = f"World Escort {index}".encode("ascii").ljust(15, b"\0")
        private = _field(b"NAME", name) + _field(b"VERK", b"\xff\xff")
        escorts.append(_field(b"SCHI64", prefix + head + cargo + _field(b"PRIVAT", private)))
    return player[:_SHIP_OFFSET] + _field(b"SCHIFF", lead), _chunk(b"SPIELER", b"".join(escorts))


def export_multiplayer_scene(
    source: bytes, snapshot: bytes, catalogue: bytes, read_template: Callable[[str], bytes],
    *, allow_unexplored: bool = False, allow_fully_explored: bool = False, allow_reveal_activity: bool = False,
    allow_huge: bool = False, allow_ai: bool = False, allow_disasters: bool = False, human_slots: int = 4,
    allow_peaceful_ai: bool = False, allow_faction_activity: bool = False,
    read_dimensions: Callable[[], dict[int, tuple[int, int]]] | None = None,
    read_ai_donor: Callable[[int], bytes] | None = None,
    populate_factions: Callable[[str], bytes] | None = None,
    populated_assets: dict[str, bytes] | None = None,
    read_culture_names: Callable[[set[int]], dict[int, bytes]] | None = None,
    resolve_starts: StartResolver | None = None,
) -> bytes:
    """Export a reviewed preview. Eight slots require the separate multiplayer pairing flow."""
    if type(human_slots) is not int or human_slots not in (4, 8):
        raise ValueError("Choose four or eight human scenario slots.")
    allow_factions = populate_factions is not None
    allow_cultures = read_culture_names is not None
    if allow_faction_activity and not allow_factions:
        raise ValueError("Multiplayer faction frequency requires populated native faction islands.")
    if (allow_factions or allow_cultures) != (populated_assets is not None):
        raise ValueError("Populated multiplayer islands require the native asset resolver.")
    base = _source_chunks(source)
    plan = _supported_preview(snapshot, allow_unexplored, resolve_starts is not None,
                              allow_fully_explored=allow_fully_explored, allow_huge=allow_huge,
                              allow_ai=allow_ai, allow_disasters=allow_disasters,
                              allow_factions=allow_factions, allow_cultures=allow_cultures,
                              allow_reveal_activity=allow_reveal_activity, allow_peaceful_ai=allow_peaceful_ai,
                              allow_faction_activity=allow_faction_activity)
    settings = plan["settings"]
    peaceful_ai = bool(settings["aiCount"] and settings["aiDifficulty"] == 0)
    if human_slots == 8 and (settings["aiCount"] or _uses_resolved_starts(settings) or
                             settings["mapVisibility"] != 1 or settings["enemyVisibility"] != 0):
        raise ValueError("Eight human slots require standard visibility and no computer players or custom starts.")
    starts = _resolved_starts(plan, snapshot, resolve_starts)
    ware_types = [payload for tag, payload in base if tag == b"WARETYPE"]
    if len(ware_types) != 1:
        raise ValueError("The licensed multiplayer object definitions are missing or duplicated.")
    world_size = settings["worldSize"]
    tiles = {seat: (x, y) for seat, (x, y, _) in zip(_HUMAN_SHIP_TILES, starts, strict=True)}
    tiles[5] = WORLD_SHIP_TILES[world_size][-1]
    supported_humans = _HUMAN_SEATS
    if human_slots == 8:
        additional_starts = extra_human_starts(plan, starts, tiles[5], SHIP_RESERVE)
        base = eight_human_records(base, additional_starts)
        supported_humans = _HUMAN_SEATS.union(EXTRA_HUMAN_SEATS)
        starts = (*starts, *additional_starts)
    if allow_factions:
        base = faction_players(base, settings["factions"], pirate_frequency=settings["pirateFrequency"],
                               merchant_frequency=settings["merchantFrequency"])
    if allow_cultures:
        base = culture_players(base, plan["islands"], settings["cultures"], read_culture_names)
    cpu_profiles, cpu_heads, cpu_spawns, cpu_starts = None, (), (), ()
    if settings["aiCount"]:
        if read_ai_donor is None:
            raise ValueError("Stock computer players require the reviewed native scenario donor.")
        cpu_profiles, cpu_heads, cpu_spawns, cpu_starts = computer_player_records(
            read_ai_donor, base, plan, starts, tiles[5], SHIP_RESERVE,
        )
    islands = _islands(plan, catalogue, read_template, ware_types[0], read_dimensions, (*starts, *cpu_starts),
                       populate_factions=populate_factions, allow_cultures=allow_cultures, populated_assets=populated_assets)
    human_seats = set()
    human_ships = set()
    escorts = []
    last_player_index = 0
    output = []
    inserted = False
    renamed = False
    resized = False
    venetian_ship = allow_factions and not (settings["factions"] & 2)
    scenario_guid = False
    resource_requests = set()
    for tag, payload in base:
        if tag == b"INSELLNK":
            if not inserted:
                output.extend(_chunk(b"SPIELER", record) for record in cpu_heads)
                output.extend(islands)
                inserted = True
            continue
        if tag == b"COMPPROFIL2" and cpu_profiles is not None:
            payload = cpu_profiles
        if tag in _REQUEST_SIZES:
            if tag in resource_requests or len(payload) != _REQUEST_SIZES[tag]:
                raise ValueError("The New Earth resource request fields differ.")
            resource_requests.add(tag)
            # Native World Settings clears random resource requests after
            # materializing its plan. The inline fields already contain them.
            payload = bytes(len(payload))
        if tag == b"HEAD":
            if resized or len(payload) != 32 or unpack_from("<II", payload) != (1024, 1024):
                raise ValueError("The New Earth world dimensions differ.")
            flags = _disaster_scene_flags(payload[16], settings, individual=allow_disasters)
            payload = pack("<II", world_size, world_size) + payload[8:16] + bytes([flags]) + payload[17:]
            resized = True
        if (allow_disasters or peaceful_ai) and tag == b"GUID":
            if scenario_guid or len(payload) != 16:
                raise ValueError("The New Earth scenario GUID differs.")
            payload = multiplayer_disaster_guid(snapshot, peaceful_ai=peaceful_ai)
            scenario_guid = True
        if tag == b"ALIASNAME":
            if renamed or payload != _STOCK_ALIAS:
                raise ValueError("The New Earth scenario name record differs.")
            payload = GENERATED_SCENARIO_ALIAS.ljust(len(payload), b"\0")
            renamed = True
        if tag == b"SPIELER" and payload[8:16] == b"HEAD\0\0l\0":
            if len(payload) < 24:
                raise ValueError("The stock human seat record is truncated.")
            kind, gold = unpack_from("<II", payload, 16)
            if kind == 8:
                version, seat = unpack_from("<II", payload)
                if version or seat not in supported_humans or seat in human_seats or gold != 30_000:
                    raise ValueError("The New Earth human seat records differ.")
                human_seats.add(seat)
                payload = payload[:20] + pack("<I", settings["startingMoney"]) + payload[24:]
        if tag == b"SPIELER" and payload[_SHIP_OFFSET:_SHIP_OFFSET + 6] == b"SCHIFF":
            version, seat = unpack_from("<II", payload)
            if seat in supported_humans:
                if version or seat in human_ships:
                    raise ValueError("The New Earth human starting ship records differ.")
                human_ships.add(seat)
                if seat in _HUMAN_SEATS:
                    payload = _move_starting_ship(payload, seat, tiles)
                payload, escort_chunk = _starting_ships(payload, seat, settings)
                if escort_chunk:
                    escorts.append(escort_chunk)
            elif seat == 5:
                if version or venetian_ship:
                    raise ValueError("The New Earth Venetian ship record differs.")
                payload = _move_starting_ship(payload, seat, tiles)
                venetian_ship = True
        output.append(_chunk(tag, payload))
        if tag == b"SPIELER":
            last_player_index = len(output)
    if (not inserted or not renamed or not resized or not venetian_ship or ((allow_disasters or peaceful_ai) and not scenario_guid)
            or resource_requests != _REQUEST_SIZES.keys()
            or human_seats != supported_humans or human_ships != supported_humans):
        raise ValueError("The New Earth scene is missing required multiplayer records.")
    # Native World loads the extra fields into each already-created player.
    output[last_player_index:last_player_index] = [*(_chunk(b"SPIELER", payload) for payload in cpu_spawns), *escorts]
    scene = _chunk(b"ANNO", _chunk(b"SCENE", b"".join(output)))
    if len(scene) > _MAX_SCENE_BYTES:
        raise ValueError("The generated multiplayer world exceeds its native scene budget.")
    return scene


def export_multiplayer_scene_from_game(
    game: Path, snapshot: bytes, catalogue: bytes, *, allow_unexplored: bool = False,
    allow_fully_explored: bool = False, allow_reveal_activity: bool = False,
    allow_huge: bool = False, allow_ai: bool = False,
    allow_disasters: bool = False, allow_peaceful_ai: bool = False,
    human_slots: int = 4, resolve_starts: StartResolver | None = None,
    populated_assets: dict[str, bytes] | None = None, recipe_root: Path | None = None,
    allow_factions: bool = False, allow_cultures: bool = False, allow_faction_activity: bool = False,
) -> bytes:
    """Use a verified local installation as the scenario and island input root."""
    root = checked_path(game)
    source = safe_child(root, SCENARIO, exists=True).read_bytes()

    def read_template(relative: str) -> bytes:
        path = safe_child(root, relative, exists=True)
        with path.open("rb") as stream:
            return stream.read(_MAX_TEMPLATE_BYTES + 1)

    def read_dimensions() -> dict[int, tuple[int, int]]:
        definition = safe_child(root, "Anlagen.dat", exists=True)
        if file_sha(definition) != VANILLA_ARCHIVE_HASHES["Anlagen.dat"]:
            raise ValueError("Island rotation requires the licensed native terrain definitions.")
        return definition_dimensions(definition)

    licensed_factions = None

    def populate_factions(relative: str) -> bytes:
        nonlocal licensed_factions
        if licensed_factions is None:
            from .beta_inputs import derive_beta_assets

            licensed_factions, _ = derive_beta_assets(root, recipe_root=recipe_root)
        return licensed_factions["assets/" + relative]

    return export_multiplayer_scene(
        source, snapshot, catalogue, read_template, allow_unexplored=allow_unexplored,
        allow_fully_explored=allow_fully_explored, allow_huge=allow_huge, allow_ai=allow_ai,
        allow_disasters=allow_disasters, allow_reveal_activity=allow_reveal_activity, allow_peaceful_ai=allow_peaceful_ai,
        allow_faction_activity=allow_faction_activity,
        human_slots=human_slots, read_ai_donor=lambda difficulty: read_donor(root, difficulty),
        read_dimensions=read_dimensions, resolve_starts=resolve_starts,
        populate_factions=populate_factions if allow_factions else None, populated_assets=populated_assets,
        read_culture_names=(lambda requested: donor_names(root, requested)) if allow_cultures else None,
    )
