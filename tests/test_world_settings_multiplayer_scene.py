from hashlib import sha256
from struct import pack, pack_into, unpack_from
import unittest
from unittest.mock import patch

from anno1503_overhaul import world_settings_multiplayer_scene as exporter
from anno1503_overhaul.world_island_catalogue import _chunks
from anno1503_overhaul.world_options_snapshot import (
    ROWS_OFFSET, SETTINGS_FIELDS, SETTINGS_FORMAT, SETTINGS_SIZE, SNAPSHOT_SIZE,
)


def chunk(tag, data):
    return tag.ljust(12, b"\0") + pack("<I", len(data)) + data


def stock_seat(seat, kind, gold):
    head = (pack("<II", kind, gold) + b"fixture").ljust(108, b"\0")
    return chunk(b"SPIELER", pack("<II", 0, seat) + b"HEAD\0\0l\0" + head)


def field(tag, data):
    return tag.ljust(6, b"\0") + pack("<H", len(data)) + data


def ship_fields(data):
    offset = 0
    while offset < len(data):
        length = unpack_from("<H", data, offset + 6)[0]
        yield data[offset:offset + 6].rstrip(b"\0"), data[offset + 8:offset + 8 + length]
        offset += 8 + length


def stock_ship(seat, food, last_tools, *, anchor=None):
    cargo = b"".join(pack("<HHI", good, tons, 0) for good, tons in (
        (42, 50), (26, food), (41, 50), (41, last_tools),
    ))
    x, y = anchor or exporter._HUMAN_SHIP_TILES.get(seat, (109, 901))
    definition, owner = (1505, 1029) if seat == 5 else (1502, seat)
    ship = (pack("<HHIff", seat + 5, definition, owner, x + 0.5, y + 0.5) + field(b"HEAD", bytes(16)) +
            field(b"WAREN", cargo) + field(b"PRIVAT", b"fixture name"))
    player = pack("<II", 0, seat).ljust(104, b"\0") + field(b"SCHIFF", ship)
    return chunk(b"SPIELER", player)


def stock_scene(alias=b"[#441#]".ljust(128, b"\0")):
    parts = [
        chunk(b"HEAD", pack("<II", 1024, 1024) + bytes(24)),
        chunk(b"GUID", bytes(range(16))),
        chunk(b"ALIASNAME", alias),
        chunk(b"WARETYPE", b"verified definition map"),
        stock_seat(5, 16, 10_000),
        *(stock_seat(seat, 8, 30_000) for seat in (0, 7, 8, 9)),
        chunk(b"INSELLNK", b"stock dummy link"),
        chunk(b"ROHSTOFF", bytes(range(16))),
        chunk(b"ERZE", bytes(range(10))),
        chunk(b"SCHATZ", b"\x10\0"),
        chunk(b"INSELLNK", b"stock dummy link"),
        stock_ship(5, 0, 0),
        *(stock_ship(seat, 50, 50) if seat == 7 else stock_ship(seat, 10, 30) for seat in (0, 7, 8, 9)),
        chunk(b"BIGBROTHER", b"stock script"),
    ]
    return chunk(b"ANNO", chunk(b"SCENE", b"".join(parts)))



def eight_slot_source(*, repeated_object=False):
    stock = stock_scene()
    records = list(_chunks(stock, 32, len(stock)))
    records[0] = (b"HEAD", records[0][1][:10] + b"\x02" + records[0][1][11:])
    roster = (0, 7, 8, 9)
    neutrals = (5, 6, 10, 11, 12, 13)
    output = []
    for tag, data in records:
        if tag == b"SPIELER":
            seat = unpack_from("<I", data, 4)[0]
            if data[8:12] == b"HEAD":
                if seat in roster:
                    role = f"HUMAN{roster.index(seat) + 1:02d}\0".encode("ascii")
                    data = data[:92] + pack("<I", 255) + data[96:] + field(b"ALIAS", role)
                    data += field(b"DIPL", field(b"TRADE", b"\x05\x03\0\0"))
                elif seat == 5:
                    data += field(b"DIPL", field(b"TRADE", b"\0\x03\0\0"))
            else:
                selections = b"".join(field(f"SEL_{i}".encode("ascii"), bytes(4)) for i in range(8))
                data = data[:8] + selections + data[104:]
                if seat in roster:
                    lead = data[112:128]
                    subfields = dict(ship_fields(data[128:]))
                    crew_id = 50 if repeated_object else 50 + seat * 2
                    donkey = field(b"ESEL", pack("<4H", 718, crew_id + 1, 0, 0))
                    entry = pack("<3H", crew_id, 717, 0) + field(b"PRIVAT", donkey)
                    private = field(b"NAME", b"Fixture trader\0") + field(b"CREW", field(b"ENTRY", entry))
                    data = data[:104] + field(b"SCHIFF", lead + field(b"HEAD", subfields[b"HEAD"])
                                               + field(b"WAREN", subfields[b"WAREN"]) + field(b"PRIVAT", private))
                else:
                    data = data[:104] + field(b"SCHIFF", data[112:128] + field(b"PRIVAT", b""))
        elif tag == b"BIGBROTHER":
            data = (b'[PLAYERMAPPER_DEFINE]\n"HUMAN01" 0\n"HUMAN02" 7\n"HUMAN03" 8\n'
                    b'"HUMAN04" 9\n[SCRIPT_KERNEL]\n')
        output.append(chunk(tag, data))
        if tag == b"SPIELER" and data[:16] == pack("<II", 0, 5) + b"HEAD\0\0l\0":
            for neutral in (*neutrals[1:], 31):
                kind = 15 if neutral == 6 else 14 if neutral != 31 else 2
                record = stock_seat(neutral, kind, 10_000)[16:]
                if neutral != 31:
                    role = b"WAR" if neutral == 6 else b"TRADE"
                    record += field(b"DIPL", field(role, b"\0\x03\0\0"))
                output.append(chunk(b"SPIELER", record))
    return chunk(b"ANNO", chunk(b"SCENE", b"".join(output)))


def snapshot(*, state=1, first=(64, 64), last=(896, 896), crop=0xF009, minerals=0,
             last_minerals=0, rotation=0, extra=(), **changes):
    settings = dict.fromkeys(SETTINGS_FIELDS, 0)
    settings.update(size=SETTINGS_SIZE, worldSize=1024, difficulty=1, islandCount=6 + len(extra), spacing=8,
                    startingMoney=80_000, aiDifficulty=1, startIsland=-1, startClimate=-1,
                    plantFertility=1, mineralFertility=1, startSeparation=1, mapVisibility=1,
                    pirateFrequency=1, pirateStrength=1, merchantFrequency=1, maxPolar=128,
                    maxTemperate=128, maxTropical=128, disasters=1, disasterMask=31,
                    disasterFrequency=341, disasterSeverity=341, mapSeed=12345)
    for field in SETTINGS_FIELDS:
        if field.startswith(("climateMax", "islandSizeMax")):
            settings[field] = 128
    settings.update(changes)
    world = settings["worldSize"]
    reserves = exporter.WORLD_SHIP_TILES[world]
    positions = [first, last, *extra]
    for y in range(8, world - 71, 72):
        for x in range(8, world - 71, 72):
            if (all(abs(x - px) >= 72 or abs(y - py) >= 72 for px, py in positions)
                    and all(not (x - exporter.SHIP_RESERVE <= sx < x + 64 + exporter.SHIP_RESERVE
                                 and y - exporter.SHIP_RESERVE <= sy < y + 64 + exporter.SHIP_RESERVE)
                            for sx, sy in reserves)):
                positions.append((x, y))
                if len(positions) == settings["islandCount"]:
                    break
        if len(positions) == settings["islandCount"]:
            break
    assert len(positions) == settings["islandCount"], positions
    layouts = [(0, crop, minerals, 2, rotation), (1, 0xF009, last_minerals, 4, 0)]
    layouts.extend((0, 0xF009, 0, 2, 0) for _ in extra)
    layouts.extend((index, 0x18000 if climate == 0 else 0xF009, 0, climate, 0)
                   for index, climate in enumerate((0, 1, 3, 5), 2))
    data = bytearray(SNAPSHOT_SIZE)
    pack_into("<4I", data, 0, SNAPSHOT_SIZE, state, settings["mapSeed"], len(positions))
    pack_into(SETTINGS_FORMAT, data, 16, *(settings[key] for key in SETTINGS_FIELDS))
    for index, ((x, y), (template, crops, ore, climate, turn)) in enumerate(zip(positions, layouts, strict=True)):
        pack_into("<11I", data, ROWS_OFFSET + index * 44, index, x, y, 64, 64, template, crops, ore, 0, climate, turn)
    return bytes(data)



def eight_slot_snapshot(**changes):
    return snapshot(extra=((800, 160), (128, 768)), **changes)


def templates():
    files = {}
    entries = []
    for folder, climate in (("Nord", 2), ("Dschungel", 4), ("Polar", 0), ("Tundra", 1), ("Praerie", 3), ("Steppe", 5)):
        info = chunk(b"INFO", bytes([climate]) + bytes(11))
        height_values = bytearray(64 * 64)
        height_values[8 * 64 + 7] = 0x31
        height = chunk(b"HEIGHT", pack("<HHBB", 0, 0, 64, 64) + height_values)
        graphics = chunk(b"GFXID", pack("<HHBB", 0, 0, 64, 64) + bytes(2 * 64 * 64))
        crops = chunk(b"ANBAU", b"GETREIDE\0FLACHSBAUM\0KARTOFFEL\0")
        entries_raw = b"".join(field(b"ENTRY2", pack("<IfffHHI", 1560 << 14, x, 9.5, 0, 400, 0, 0))
                               for x in (5.5, 15.5))
        occurrences = chunk(b"OCCUR", entries_raw)
        island = chunk(b"INSEL5", pack("<4HI", 0, 0, 64, 64, 0) +
                       info + height + graphics + crops + occurrences + chunk(b"FRUCHTBAR", bytes(64 * 64)))
        path = f"Scenes/Islands/{folder}/Island.scp"
        data = chunk(b"ANNO", chunk(b"WARETYPE", b"verified definition map") + island)
        files[path] = data
        entries.append({"path": path, "sha256": sha256(data).hexdigest(),
                        "fields": [64, 64, climate, 0, 2, 0, 0, 0, 32 if climate in (2, 4) else 0]})
    return files, entries


class NativeMultiplayerSceneTests(unittest.TestCase):
    def export(self, preview, change_template=None, *, source=None, allow_unexplored=False,
               allow_fully_explored=False, allow_huge=False, allow_ai=False, human_slots=4,
               read_dimensions=None, resolve_starts=None, allow_disasters=False, allow_reveal_activity=False):
        if source is None:
            source = stock_scene()
        files, entries = templates()
        if change_template:
            change_template(files, entries)
        with (
            patch.object(exporter, "SOURCE_SHA256", sha256(source).hexdigest()),
            patch.object(exporter, "catalogue_rows", return_value=entries),
        ):
            return exporter.export_multiplayer_scene(
                source, preview, b"fixture catalogue", files.__getitem__, allow_unexplored=allow_unexplored,
                allow_fully_explored=allow_fully_explored, allow_huge=allow_huge, allow_ai=allow_ai,
                human_slots=human_slots, read_dimensions=read_dimensions, resolve_starts=resolve_starts,
                allow_disasters=allow_disasters, allow_reveal_activity=allow_reveal_activity,
            )

    def test_eight_dynamic_humans_get_unique_owners_and_fleets(self):
        source = eight_slot_source()
        preview = eight_slot_snapshot()
        four = self.export(preview, source=source)
        eight = self.export(preview, source=source, human_slots=8)
        self.assertEqual(four, self.export(preview, source=source, human_slots=4))
        self.assertEqual(eight, self.export(preview, source=source, human_slots=8))

        chunks = list(_chunks(eight, 32, len(eight)))
        self.assertEqual(dict(chunks)[b"HEAD"][10], 2)
        mapper = dict(chunks)[b"BIGBROTHER"]
        ids, aliases, anchors = set(), {}, {}
        human_owners = (0, 1, 2, 3, 4, 7, 8, 9)
        for tag, data in chunks:
            if tag != b"SPIELER":
                continue
            _, owner = unpack_from("<II", data)
            fields = dict(ship_fields(data[8:]))
            if b"HEAD" in fields and owner in human_owners:
                aliases[owner] = fields[b"ALIAS"]
                self.assertEqual(unpack_from("<II", fields[b"HEAD"]), (8, 80_000))
                self.assertEqual(unpack_from("<I", fields[b"HEAD"], 76)[0], 255)
            if b"HEAD" in fields and owner in (5, 6, 10, 11, 12, 13):
                relation_tag = b"WAR" if owner == 6 else b"TRADE"
                self.assertEqual(list(ship_fields(fields[b"DIPL"])),
                                 [(relation_tag, bytes((seat, 3, 0, 0))) for seat in range(5)])
            if b"SCHIFF" in fields:
                ship = fields[b"SCHIFF"]
                lead, definition, ship_owner, x, y = unpack_from("<HHIff", ship)
                ship_ids = (lead,)
                if owner in human_owners:
                    self.assertEqual((definition, ship_owner), (1502, owner))
                    anchors[owner] = (int(x), int(y))
                    private = dict(ship_fields(dict(ship_fields(ship[16:]))[b"PRIVAT"]))
                    crew = dict(ship_fields(private[b"CREW"]))[b"ENTRY"]
                    donkey = dict(ship_fields(dict(ship_fields(crew[6:]))[b"PRIVAT"]))[b"ESEL"]
                    ship_ids += unpack_from("<H", crew) + unpack_from("<H", donkey, 2)
                self.assertTrue(ids.isdisjoint(ship_ids))
                ids.update(ship_ids)

        self.assertEqual(set(aliases), set(human_owners))
        self.assertEqual(set(anchors), set(human_owners))
        self.assertEqual(len(ids), 25)
        for number, seat in enumerate((0, 7, 8, 9, 1, 2, 3, 4), 1):
            alias = f"HUMAN{number:02d}".encode("ascii")
            self.assertEqual(aliases[seat], alias + b"\0")
            self.assertIn(b'"' + alias + f'" {seat}\n'.encode("ascii"), mapper)
        for seat, (x, y) in anchors.items():
            self.assertGreaterEqual(min(x, y), exporter.SHIP_RESERVE)
            self.assertTrue(all(abs(x - ox) > 2 * exporter.SHIP_RESERVE or abs(y - oy) > 2 * exporter.SHIP_RESERVE
                                for other, (ox, oy) in anchors.items() if other != seat))

    def test_eight_human_scene_gates_unverified_options_and_bad_native_ids(self):
        source = eight_slot_source()
        with self.assertRaisesRegex(ValueError, "four or eight"):
            self.export(eight_slot_snapshot(), source=source, human_slots=7)
        with self.assertRaisesRegex(ValueError, "too few clear human starting positions"):
            self.export(snapshot(worldSize=512, first=(8, 128), last=(160, 128)), source=source, human_slots=8)
        with self.assertRaisesRegex(ValueError, "cannot supply eight human starts"):
            self.export(eight_slot_snapshot(), source=eight_slot_source(repeated_object=True), human_slots=8)
        for changes in ({"aiCount": 1}, {"fairStarts": 1}, {"mapVisibility": 2}):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "Eight human slots require"):
                self.export(eight_slot_snapshot(**changes), source=source, human_slots=8, allow_ai=True,
                            allow_fully_explored=True, resolve_starts=lambda _: self.fail("Unexpected four-start plan"))

    def test_reproduces_preview_rows_and_preserves_stock_metadata(self):
        source = stock_scene()
        preview = snapshot()
        data = self.export(preview)
        self.assertEqual(data, self.export(preview))
        [(root_tag, root)] = _chunks(data, 0, len(data))
        [(scene_tag, scene)] = _chunks(root, 0, len(root))
        self.assertEqual((root_tag, scene_tag), (b"ANNO", b"SCENE"))

        result = list(_chunks(scene, 0, len(scene)))
        self.assertNotIn(b"INSELLNK", {tag for tag, _ in result})
        islands = [body for tag, body in result if tag == b"INSEL5"]
        expected = (
            (64, 64, 64, 64, 0),
            (896, 896, 64, 64, 1),
        )
        self.assertEqual([unpack_from("<4HI", body) for body in islands[:2]], list(expected))
        before = [(tag, body) for tag, body in _chunks(source, 32, len(source)) if tag != b"INSELLNK"]
        after = [(tag, body) for tag, body in result if tag != b"INSEL5"]
        for (tag, body), (new_tag, changed) in zip(before, after, strict=True):
            self.assertEqual(tag, new_tag)
            if tag == b"SPIELER" and body[8:16] == b"HEAD\0\0l\0" and unpack_from("<I", body, 16)[0] == 8:
                self.assertEqual(changed, body[:20] + pack("<I", 80_000) + body[24:])
            elif tag == b"SPIELER" and body[104:110] == b"SCHIFF" and unpack_from("<I", body, 4)[0] == 7:
                self.assertEqual(changed, body[:170] + pack("<H", 10) + body[172:186] + pack("<H", 30) + body[188:])
            elif tag == b"ALIASNAME":
                self.assertEqual(changed, b"Custom world (2-4)".ljust(128, b"\0"))
            elif tag in (b"ROHSTOFF", b"ERZE", b"SCHATZ"):
                self.assertEqual(changed, bytes(len(body)))
            else:
                self.assertEqual(changed, body)

    def test_inline_islands_start_with_stock_empty_state_and_local_production_tiles(self):
        scene = self.export(snapshot())
        islands = [body for tag, body in _chunks(scene, 32, len(scene)) if tag == b"INSEL5"]
        self.assertEqual(len(islands), 6)
        expected = [(b"DISCOVER", bytes(4)), (b"KONTORID", pack("<H", 1))]
        expected.extend((b"PROD2", pack("<HHBB", x, y, 32, 32)) for y in (0, 32) for x in (0, 32))
        expected.extend(((b"HIRSCH", b""), (b"EVENTINSEL", b"")))
        for island in islands:
            parts = list(_chunks(island, 12, len(island)))
            self.assertEqual(parts[-len(expected):], expected)

    def test_ordinary_island_can_carry_only_the_complete_empty_state(self):
        preview = snapshot()
        expected_scene = self.export(preview)
        tiles = [(b"PROD2", pack("<HHBB", x, y, 32, 32)) for y in (0, 32) for x in (0, 32)]
        empty_state = [(b"DISCOVER", bytes(4)), (b"KONTORID", pack("<H", 1)), *tiles]

        def add_records(records):
            def change_template(files, entries):
                entry = next(entry for entry in entries if entry["fields"][2] == 0)
                source = files[entry["path"]]
                [(ware_tag, ware_types), (island_tag, island)] = _chunks(source, 16, len(source))
                source = chunk(b"ANNO", chunk(ware_tag, ware_types) +
                               chunk(island_tag, island + b"".join(chunk(tag, body) for tag, body in records)))
                files[entry["path"]] = source
                entry["sha256"] = sha256(source).hexdigest()
            return change_template

        self.assertEqual(self.export(preview, add_records(empty_state)), expected_scene)
        for invalid in (
            [(b"DISCOVER", b"\x01\0\0\0"), *empty_state[1:]],
            [*empty_state[:-1], (b"PROD2", tiles[-1][1] + b"building data")],
            empty_state[:-1],
            [*empty_state, tiles[0]],
            [*empty_state, (b"EVENTINSEL", b"event")],
        ):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, "state unrelated to geography"):
                self.export(preview, add_records(invalid))

    def test_difficulty_matches_native_default_tools_without_overriding_custom_cargo(self):
        for difficulty, tools in ((0, 50), (1, 30), (2, 30)):
            with self.subTest(difficulty=difficulty):
                result = self.export(snapshot(difficulty=difficulty))
                for seat in (0, 7, 8, 9):
                    [body] = [body for tag, body in _chunks(result, 32, len(result))
                              if tag == b"SPIELER" and body[104:110] == b"SCHIFF"
                              and unpack_from("<I", body, 4)[0] == seat]
                    self.assertEqual(unpack_from("<HHI", body, exporter._CARGO_OFFSET + 24), (41, tools, 0))
        for settings in ({"cargoMode": 1, "cargoTools": 10}, {"startingFleet": 2}):
            self.assertEqual(self.export(snapshot(difficulty=0, **settings)),
                             self.export(snapshot(difficulty=1, **settings)))

    def test_rejects_a_changed_human_ship_cargo(self):
        source = stock_scene().replace(stock_ship(7, 50, 50), stock_ship(7, 49, 50))
        with self.assertRaisesRegex(ValueError, "human ship or starting cargo differs"):
            self.export(snapshot(), source=source)

    def test_custom_cargo_splits_goods_into_equal_native_holds(self):
        source = stock_scene()
        data = self.export(snapshot(cargoMode=1, cargoTools=25, cargoWood=75, cargoFood=40), source=source)
        expected = b"".join(pack("<HHI", good, tons, 0) for good, tons in ((41, 25), (42, 50), (42, 25), (26, 40)))
        for seat in (0, 7, 8, 9):
            old = next(body for tag, body in _chunks(source, 32, len(source))
                       if tag == b"SPIELER" and body[104:110] == b"SCHIFF" and unpack_from("<I", body, 4)[0] == seat)
            self.assertIn(chunk(b"SPIELER", old[:160] + expected + old[192:]), data)
        self.assertIn(stock_ship(5, 0, 0), data)

    def test_empty_custom_cargo_empties_all_holds_and_extra_holds_are_refused(self):
        data = self.export(snapshot(cargoMode=1))
        ships = [body for tag, body in _chunks(data, 32, len(data)) if tag == b"SPIELER" and body[104:110] == b"SCHIFF"
                 and unpack_from("<I", body, 4)[0] in (0, 7, 8, 9)]
        self.assertEqual(len(ships), 4)
        self.assertTrue(all(body[160:192] == bytes(32) for body in ships))
        with self.assertRaisesRegex(ValueError, "exceeds trade-ship holds"):
            self.export(snapshot(cargoMode=1, cargoTools=51, cargoWood=51, cargoFood=1))

    def test_native_fleets_are_equal_with_correct_owners_and_hold_counts(self):
        merchant = pack("<HHIHHI", 41, 40, 0, 42, 40, 0)
        cargo = {
            "standard": b"".join(pack("<HHI", good, tons, 0) for good, tons in (
                (42, 50), (26, 10), (41, 50), (41, 30),
            )),
            "custom": b"".join(pack("<HHI", good, tons, 0) for good, tons in (
                (41, 50), (41, 1), (42, 50), (42, 1), (26, 1),
            )),
        }
        for settings, definition, guns, lead_cargo, escort_cargo in (
            ({"startingFleet": 1}, 1504, 6, cargo["standard"].ljust(64, b"\0"), bytes(16)),
            ({"startingFleet": 2}, 1502, 0, merchant.ljust(64, b"\0"), merchant.ljust(32, b"\0")),
            ({"startingFleet": 1, "cargoMode": 1, "cargoTools": 51, "cargoWood": 51, "cargoFood": 1},
             1504, 6, cargo["custom"].ljust(64, b"\0"), bytes(16)),
        ):
            with self.subTest(settings=settings):
                data = self.export(snapshot(**settings))
                result = list(_chunks(data, 32, len(data)))
                self.assertEqual(result[-1], (b"BIGBROTHER", b"stock script"))
                self.assertIn(stock_ship(5, 0, 0), data)
                expected_head = bytes([3, 255, 0, 0, 0, 255, 255, 0, guns, 128, 0, 0, 0, 0, 0, 0])
                for seat, (x, y) in exporter._HUMAN_SHIP_TILES.items():
                    main = next(body for tag, body in result
                                if tag == b"SPIELER" and body[104:110] == b"SCHIFF"
                                and unpack_from("<I", body, 4)[0] == seat)
                    [(which, lead)] = ship_fields(main[104:])
                    self.assertEqual(which, b"SCHIFF")
                    self.assertEqual(unpack_from("<HHIff", lead), (seat + 5, 1503, seat, x + 0.5, y + 0.5))
                    self.assertEqual(dict(ship_fields(lead[16:])),
                                     {b"HEAD": expected_head, b"WAREN": lead_cargo, b"PRIVAT": b"fixture name"})
                    [extras] = [body for tag, body in result[-5:-1] if tag == b"SPIELER"
                                and unpack_from("<II", body) == (0, seat)]
                    ships = list(ship_fields(extras[8:]))
                    self.assertEqual([which for which, _ in ships], [b"SCHI64", b"SCHI64"])
                    for index, (_, escort) in enumerate(ships, 1):
                        self.assertEqual(unpack_from("<IHB5xff", escort),
                                         (0xFFFFFFFF, definition, seat, x + 0.5 + (2 * index - 3) * 6, y + 6.5))
                        parts = dict(ship_fields(escort[20:]))
                        self.assertEqual(parts[b"HEAD"], expected_head)
                        self.assertEqual(parts[b"WAREN"], escort_cargo)
                        self.assertEqual(dict(ship_fields(parts[b"PRIVAT"])),
                                         {b"NAME": f"World Escort {index}".encode().ljust(15, b"\0"),
                                          b"VERK": b"\xff\xff"})

    def test_fleet_escort_positions_require_the_native_reserve_and_capacity(self):
        source = stock_scene().replace(stock_ship(0, 10, 30), stock_ship(0, 10, 30, anchor=(495, 357)))
        with self.assertRaisesRegex(ValueError, "ship anchor differs"):
            self.export(snapshot(startingFleet=1), source=source)
        with self.assertRaisesRegex(ValueError, "exceeds trade-ship holds"):
            self.export(snapshot(startingFleet=2, cargoMode=1, cargoTools=51, cargoWood=51, cargoFood=1))

    def test_smaller_worlds_resize_the_native_map_and_all_five_ship_anchors(self):
        for size, last in ((256, (160, 80)), (512, (432, 432))):
            with self.subTest(size=size):
                data = self.export(snapshot(worldSize=size, first=(8, 8), last=last, startingFleet=2))
                parts = list(_chunks(data, 32, len(data)))
                self.assertIn((b"HEAD", pack("<II", size, size) + bytes(24)), parts)
                for seat, (x, y) in zip((0, 7, 8, 9, 5), exporter.WORLD_SHIP_TILES[size], strict=True):
                    [ship] = [body for tag, body in parts if tag == b"SPIELER" and body[104:110] == b"SCHIFF"
                              and unpack_from("<II", body) == (0, seat)]
                    self.assertEqual(unpack_from("<ff", ship, 120), (x + 0.5, y + 0.5))
                    if seat != 5:
                        [extra] = [body for tag, body in parts if tag == b"SPIELER" and body[8:14] == b"SCHI64"
                                   and unpack_from("<II", body) == (0, seat)]
                        self.assertEqual([unpack_from("<ff", body, 12) for _, body in ship_fields(extra[8:])],
                                         [(x - 5.5, y + 6.5), (x + 6.5, y + 6.5)])

    def test_opt_in_huge_scene_preserves_far_edge_geometry_and_all_starting_anchors(self):
        preview = snapshot(worldSize=2048, last=(1976, 1976), startingFleet=2)
        with self.assertRaisesRegex(ValueError, "cannot apply yet"):
            self.export(preview)
        scene = self.export(preview, allow_huge=True)
        self.assertEqual(scene, self.export(preview, allow_huge=True))
        parts = list(_chunks(scene, 32, len(scene)))
        self.assertIn((b"HEAD", pack("<II", 2048, 2048) + bytes(24)), parts)
        islands = [unpack_from("<4H", payload) for tag, payload in parts if tag == b"INSEL5"]
        self.assertEqual(islands[:2], [(64, 64, 64, 64), (1976, 1976, 64, 64)])
        anchors = {0: (1024.5, 682.5), 7: (512.5, 512.5), 8: (1536.5, 512.5),
                   9: (1536.5, 1536.5), 5: (512.5, 1536.5)}
        ships = {unpack_from("<I", payload, 4)[0]: unpack_from("<ff", payload, 120)
                 for tag, payload in parts if tag == b"SPIELER" and payload[104:110] == b"SCHIFF"}
        self.assertEqual(ships, anchors)
        with self.assertRaisesRegex(ValueError, "too close"):
            self.export(snapshot(worldSize=2048, last=(1536, 1536)), allow_huge=True)
        with self.assertRaisesRegex(ValueError, "grid or bounds"):
            self.export(snapshot(worldSize=2048, last=(1984, 1984)), allow_huge=True)

    def test_materializes_planned_fertility_and_deterministic_native_ore(self):
        preview = snapshot(crop=0xF949, minerals=33, plantFertility=0, mineralFertility=0, resourceDistribution=1)
        data = self.export(preview)
        self.assertEqual(data, self.export(preview))
        islands = [body for tag, body in _chunks(data, 32, len(data)) if tag == b"INSEL5"]
        first, second = (dict(_chunks(body, 12, len(body))) for body in islands[:2])
        self.assertEqual(first[b"ANBAU"], b"GETREIDE\0FLACHSBAUM\0WEINTRAUBEN\0HOPFENBAUM\0KR\xc4UTER\0KARTOFFEL\0")
        self.assertEqual(second[b"ANBAU"], b"GETREIDE\0FLACHSBAUM\0KARTOFFEL\0")
        for island, expected in (
            (first, [(1661, 5.5, 400), (1564, 15.5, 400)]),
            (second, []),
        ):
            ore = [(packed >> 14 & 4095, x, quantity)
                   for tag, body in ship_fields(island[b"OCCUR"])
                   for packed, x, _, _, quantity in [unpack_from("<IfffH", body)]
                   if tag == b"ENTRY2"]
            self.assertEqual(ore, expected)
        for changes, diagnostic in (
            ({"crop": 0xF00B}, "crop availability"),
            ({"minerals": 2}, "mineral availability"),
            ({"minerals": 37}, "deposit slots"),
        ):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, diagnostic):
                self.export(snapshot(**changes))

    def test_materializes_the_native_rotated_coast_and_resource_positions(self):
        preview = snapshot(islandRotation=1, rotation=1, minerals=1)
        with self.assertRaisesRegex(ValueError, "verified native terrain definitions"):
            self.export(preview)
        data = self.export(preview, read_dimensions=lambda: {})
        first = next(body for tag, body in _chunks(data, 32, len(data)) if tag == b"INSEL5")
        parts = list(_chunks(first, 12, len(first)))
        heights = [body for tag, body in parts if tag == b"HEIGHT"]
        match = next(body for body in heights if unpack_from("<HHBB", body) == (32, 0, 32, 32))
        self.assertEqual(match[6 + 7 * 32 + 24], 0x31)
        occur = next(body for tag, body in parts if tag == b"OCCUR")
        self.assertEqual([unpack_from("<ff", body, 4) for _, body in ship_fields(occur)], [(54.5, 5.5)])

    def test_requires_planned_resources_near_every_human_ship_if_selected(self):
        settings = dict(worldSize=256, first=(8, 128), last=(160, 128), minerals=4, guaranteeBasics=1)
        self.assertTrue(self.export(snapshot(**settings, last_minerals=1)))
        with self.assertRaisesRegex(ValueError, "Every starting fleet needs nearby"):
            self.export(snapshot(**settings))

        # With larger spacing the first and last human anchor groups can
        # land in disjoint resource regions, so one good is insufficient.
        with self.assertRaisesRegex(ValueError, "Every starting fleet needs nearby"):
            self.export(snapshot(guaranteeBasics=1, first=(256, 128), last=(648, 456),
                                 minerals=5, last_minerals=1))

    def test_rebuilds_preferred_start_locally_before_moving_host_fleet(self):
        preview = snapshot(startIsland=0, startingFleet=1)
        with self.assertRaisesRegex(ValueError, "cannot apply yet"):
            self.export(preview)

        unchanged_guests = ((394, 461, 0xFFFFFFFF), (357, 521, 0xFFFFFFFF), (419, 679, 0xFFFFFFFF))
        starts = ((160, 128, 0), *unchanged_guests)
        data = self.export(preview, resolve_starts=lambda _: (preview, starts))
        host = next(body for tag, body in _chunks(data, 32, len(data)) if tag == b"SPIELER"
                    and body[104:110] == b"SCHIFF" and unpack_from("<II", body) == (0, 0))
        self.assertEqual(unpack_from("<ff", host, 120), (160.5, 128.5))
        for rebuilt, initial in (
            (snapshot(), starts),  # A different local native map may never be accepted.
            (preview, ((136, 96, 0), *unchanged_guests)),  # Reserved water crosses the island.
            (preview, ((160, 96, 1), *unchanged_guests)),  # Native result must honor the host's preference.
        ):
            with self.subTest(initial=initial), self.assertRaisesRegex(ValueError, "rebuilt multiplayer starting fleets"):
                self.export(preview, resolve_starts=lambda _: (rebuilt, initial))

    def test_rejects_a_changed_source_name_record(self):
        with self.assertRaisesRegex(ValueError, "scenario name record differs"):
            self.export(snapshot(), source=stock_scene(b"unexpected".ljust(128, b"\0")))

    def test_rejects_unavailable_preview_options_and_ship_conflicts(self):
        for preview, error in (
            (snapshot(state=2), "ready World Settings"),
            (snapshot(factions=1), "cannot apply yet"),
            (snapshot(worldSize=2048), "cannot apply yet"),
            (snapshot(first=(456, 320)), "too close"),
            (snapshot(worldSize=256, first=(8, 8), last=(160, 160)), "too close"),
        ):
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                self.export(preview)

    def test_rejects_visibility_and_other_runtime_only_choices(self):
        for key, value in (
            ("mapVisibility", 0),  # Terra Incognita
            ("mapVisibility", 2),
            ("enemyVisibility", 1),  # Line of sight
            ("disasterMask", 30),  # Fire and plague split
            ("disasterMask", 27),  # Weather events split
            ("disasterFrequency", 342),
            ("disasterSeverity", 325),
            ("pirateStrength", 2),
        ):
            with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, "cannot apply yet"):
                self.export(snapshot(**{key: value}))

    def test_disaster_groups_and_master_preserve_other_scene_flags_and_records(self):
        before = pack("<II", 1024, 1024) + bytes(24)
        # Include native pirate/other low bits and an unrelated high flag byte.
        header = before[:16] + b"\x21\x02" + before[18:]
        source = stock_scene().replace(chunk(b"HEAD", before), chunk(b"HEAD", header), 1)
        stock = self.export(snapshot(), source=source)
        active = list(_chunks(stock, 32, len(stock)))
        self.assertIn((b"HEAD", header), active)
        for mask, group_flags in ((0, 0x8E), (3, 0x86), (28, 0x08), (31, 0)):
            for master in (0, 1):
                with self.subTest(mask=mask, master=master):
                    result = self.export(snapshot(disasters=master, disasterMask=mask), source=source)
                    flags = header[16] | (group_flags if master else 0x8E)
                    expected_head = header[:16] + bytes([flags]) + header[17:]
                    self.assertEqual(
                        list(_chunks(result, 32, len(result))),
                        [(tag, expected_head if tag == b"HEAD" else payload) for tag, payload in active],
                    )

    def test_opt_in_visibility_accepts_unexplored_without_changing_scene_bytes(self):
        self.assertEqual(self.export(snapshot(mapVisibility=0), allow_unexplored=True), self.export(snapshot()))
        for settings in ({"mapVisibility": 2}, {"enemyVisibility": 1}):
            with self.subTest(settings=settings), self.assertRaisesRegex(ValueError, "cannot apply yet"):
                self.export(snapshot(**settings), allow_unexplored=True)

    def test_individual_disasters_bind_scene_identity_and_preserve_unrelated_flags(self):
        before = pack("<II", 1024, 1024) + bytes(24)
        header = before[:16] + b"\x21\x02" + before[18:]
        source = stock_scene().replace(chunk(b"HEAD", before), chunk(b"HEAD", header), 1)
        for mask, disabled in ((1, 0x86), (2, 0x86), (4, 0x8C), (8, 0x0E), (16, 0x8A), (31, 0)):
            with self.subTest(mask=mask):
                chosen = snapshot(disasterMask=mask, disasterFrequency=342, disasterSeverity=325)
                data = self.export(chosen, source=source, allow_disasters=True)
                records = list(_chunks(data, 32, len(data)))
                self.assertIn((b"HEAD", header[:16] + bytes([header[16] | disabled]) + header[17:]), records)
                self.assertIn((b"GUID", exporter.multiplayer_disaster_guid(chosen)), records)
                self.assertNotEqual(exporter.multiplayer_disaster_guid(snapshot(disasterMask=mask)),
                                    exporter.multiplayer_disaster_guid(chosen))

    def test_fully_explored_is_separately_gated_for_the_linked_companion(self):
        self.assertEqual(self.export(snapshot(mapVisibility=2), allow_fully_explored=True), self.export(snapshot()))
        with self.assertRaisesRegex(ValueError, "cannot apply yet"):
            self.export(snapshot(mapVisibility=2, enemyVisibility=1), allow_fully_explored=True)

    def test_opt_in_reveal_activity_does_not_change_the_shared_scene(self):
        for mode in (0, 1, 2):
            with self.subTest(mode=mode):
                options = dict(allow_unexplored=True, allow_fully_explored=True)
                strict = self.export(snapshot(mapVisibility=mode), **options)
                reveal = self.export(snapshot(mapVisibility=mode, enemyVisibility=1),
                                     allow_reveal_activity=True, **options)
                self.assertEqual(strict, reveal)

    def test_rejects_replaced_local_islands_and_optional_private_aliases(self):
        def replace_island(files, entries):
            files[entries[0]["path"]] += b"unexpected"

        def private_alias(files, entries):
            entries[0]["path"] = "WorldSettingsIslands/Nord/Private.scp"

        def add_player_state(files, entries):
            entry = entries[0]
            files[entry["path"]] = chunk(b"ANNO", files[entry["path"]][16:] + stock_seat(5, 16, 10_000))
            entry["sha256"] = sha256(files[entry["path"]]).hexdigest()

        with self.assertRaisesRegex(ValueError, "differs from the reviewed"):
            self.export(snapshot(), replace_island)
        with self.assertRaisesRegex(ValueError, "unsupported local scenario state"):
            self.export(snapshot(), private_alias)
        with self.assertRaisesRegex(ValueError, "outside its native geography"):
            self.export(snapshot(), add_player_state)

    def test_rejects_an_unpinned_source_before_using_templates(self):
        with self.assertRaisesRegex(ValueError, "licensed New Earth"):
            exporter.export_multiplayer_scene(stock_scene(), snapshot(), b"fixture", lambda _: b"")


if __name__ == "__main__":
    unittest.main()
