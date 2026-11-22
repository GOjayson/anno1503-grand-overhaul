"""Serialize the native World Settings island plan into an inline HE island."""
from __future__ import annotations

from math import isfinite
from struct import pack, unpack_from

from .world_island_catalogue import _chunks
from .world_island_rotation import rotate_island


# World Settings' native climate tables, with the mineral table's shallow
# iron normalization. ANBAU stores the named low 13 crop bits only.
_CROP_MASKS = (0x18000, 0xF009, 0xF949, 0xF06B, 0xF6B9, 0xF04D)
_CROP_NAMES = (
    b"GETREIDE", b"TABAKBAUM", b"GEWUERZBAUM", b"FLACHSBAUM", b"ZUCKERROHR", b"BAUMWOLLE",
    b"WEINTRAUBEN", b"KAKAOBAUM", b"HOPFENBAUM", b"SEIDENRAUPE", b"FARBBAUM", b"KR\xc4UTER",
    b"KARTOFFEL",
)
_MINERAL_MASKS = (0, 5, 37, 1, 3, 11)
_MINERAL_DEFINITIONS = ((1, 1661), (2, 1561), (4, 1562), (8, 1563), (32, 1564))
_NATIVE_ORE = {1560, 1561, 1562, 1563, 1564, 1661}
_OTHER_OCCURRENCES = {1559, 1565}
NO_START_ISLAND = 0xFFFFFFFF
_ISLAND_FIELDS = {
    b"INFO", b"HEIGHT", b"GFXID", b"GELAENDE", b"FRUCHTBAR", b"FLUESSE", b"BERGWERK2", b"OCCUR", b"ANBAU",
}


def _chunk(tag: bytes, data: bytes) -> bytes:
    return tag.ljust(12, b"\0") + pack("<I", len(data)) + data


def _crop_fields(mask: int, climate: int) -> bytes:
    supported = _CROP_MASKS[climate]
    baseline = supported & ~0xFF6
    if mask & ~supported or mask & baseline != baseline:
        raise ValueError("The preview crop availability differs from its native climate.")
    return b"".join(name + b"\0" for index, name in enumerate(_CROP_NAMES) if mask & (1 << index))


def _occurrences(data: bytes, mask: int, climate: int, width: int, height: int, ore_slots: int, *,
                 stocked: bool = False) -> bytes:
    if mask & ~_MINERAL_MASKS[climate] or mask.bit_count() > ore_slots:
        raise ValueError("The preview mineral availability exceeds its native climate or deposit slots.")
    assigned = iter(definition for bit, definition in _MINERAL_DEFINITIONS if mask & bit)
    slots = 0
    offset = 0
    result = bytearray()
    while offset < len(data):
        if len(data) - offset < 8 or data[offset:offset + 6] != b"ENTRY2":
            raise ValueError("The island contains an unknown native occurrence field.")
        length = unpack_from("<H", data, offset + 6)[0]
        end = offset + 8 + length
        if length < 16 or end > len(data):
            raise ValueError("A native occurrence field is truncated.")
        raw = data[offset + 8:end]
        packed, x, y, z = unpack_from("<Ifff", raw)
        ident = packed >> 14 & 0xFFF
        if ident in _NATIVE_ORE:
            if (length != 24 or not all(isfinite(v) for v in (x, y, z))
                    or not 0 <= x < width or not 0 <= y < height
                    or unpack_from("<H", raw, 16)[0] not in ((400, 2000) if stocked else (400,))
                    or unpack_from("<H", raw, 18)[0] != 0
                    or unpack_from("<I", raw, 20)[0] > int(stocked)):
                raise ValueError("A stock island has an unsupported mineral occurrence.")
            # Stock inline scenes omit unused deposits. Keep selected deposits
            # at their template position with their native reserve and flags.
            selected = next(assigned, None)
            slots += 1
            if selected is None:
                offset = end
                continue
            raw = pack("<I", (packed & ~(0xFFF << 14)) | (selected << 14)) + raw[4:]
        elif ident not in _OTHER_OCCURRENCES:
            raise ValueError("The island contains an occurrence outside its reviewed geography.")
        result.extend(data[offset:offset + 8])
        result.extend(raw)
        offset = end
    if slots != ore_slots or next(assigned, None) is not None:
        raise ValueError("The licensed island's mineral occurrence count differs from the catalogue.")
    return bytes(result)


def inline_island(template: bytes, row: dict, ore_slots: int, ware_types: bytes,
                  dimensions: dict[int, tuple[int, int]]) -> bytes:
    """Use the verified template and planned resource masks in native INSEL5."""
    if row["rotation"]:
        template = rotate_island(template, row["rotation"], dimensions)
    root_end = 16 + unpack_from("<I", template, 12)[0]
    [(ware_tag, definitions), (island_tag, island)] = _chunks(template, 16, root_end)
    if ware_tag != b"WARETYPE" or island_tag != b"INSEL5" or definitions != ware_types:
        raise ValueError("The island's object definitions differ from the licensed scenario.")
    width, height, climate = row["width"], row["height"], row["climate"]
    records = [pack("<4HI", row["x"], row["y"], width, height, row["id"])]
    # Some licensed empty islands already carry the stock initialization
    # records. Verify the complete empty state before regenerating it once.
    empty_state = [(b"DISCOVER", bytes(4)), (b"KONTORID", pack("<H", 1))]
    empty_state.extend(
        (b"PROD2", pack("<HHBB", x, y, min(32, width - x), min(32, height - y)))
        for y in range(0, height, 32) for x in range(0, width, 32)
    )
    template_state = []
    resources = set()
    for tag, body in _chunks(island, 12, len(island)):
        if tag not in _ISLAND_FIELDS:
            template_state.append((tag, body))
            continue
        if tag in (b"ANBAU", b"OCCUR"):
            if tag in resources:
                raise ValueError("The island has duplicated native resource fields.")
            resources.add(tag)
            if tag == b"ANBAU":
                body = _crop_fields(row["cropMask"], climate)
            else:
                body = _occurrences(body, row["mineralMask"], climate, width, height, ore_slots)
        records.append(_chunk(tag, body))
    if template_state and template_state != empty_state:
        raise ValueError("The island includes player or scenario state unrelated to geography.")
    if resources != {b"ANBAU", b"OCCUR"}:
        raise ValueError("The island is missing native crop or occurrence records.")
    records.extend(_chunk(tag, body) for tag, body in empty_state)
    records.extend((_chunk(b"HIRSCH", b""), _chunk(b"EVENTINSEL", b"")))
    return _chunk(b"INSEL5", b"".join(records))


def verify_starting_resources(rows: list[dict], catalogue: list[dict],
                              ship_tiles: tuple[tuple[int, int, int], ...], size: int) -> None:
    """Verify the native nearest-island resource guarantee for each starting fleet."""
    radius_squared = max(size // 4, 128) ** 2
    fertile = {row["id"] for row in rows
               if row["climate"] and catalogue[row["templateIndex"]]["fields"][8]}
    diagnostic = "Every starting fleet needs nearby grain, flax, potatoes, iron and salt."
    if not fertile:
        raise ValueError(diagnostic)
    for x, y, island in ship_tiles:
        # Native World Settings truncates its centre-of-tile ship positions.
        # Decode has already fixed row order to the stable native island IDs.
        def to_ship(row):
            return (max(0, row["x"] - x, x - row["x"] - row["width"]) ** 2 +
                    max(0, row["y"] - y, y - row["y"] - row["height"]) ** 2)

        if island == NO_START_ISLAND:
            anchor = min((row for row in rows if row["id"] in fertile), key=to_ship)
            if to_ship(anchor) > radius_squared:
                raise ValueError(diagnostic)
        elif 0 <= island < len(rows):
            anchor = rows[island]
        else:
            raise ValueError(diagnostic)
        crops = minerals = 0
        for row in rows:
            dx = max(0, row["x"] - anchor["x"] - anchor["width"], anchor["x"] - row["x"] - row["width"])
            dy = max(0, row["y"] - anchor["y"] - anchor["height"], anchor["y"] - row["y"] - row["height"])
            if dx * dx + dy * dy <= radius_squared:
                if row["id"] in fertile:
                    crops |= row["cropMask"]
                minerals |= row["mineralMask"]
        if crops & 0x1009 != 0x1009 or minerals & 5 != 5:
            raise ValueError(diagnostic)
