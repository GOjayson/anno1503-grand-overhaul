"""Preserve native home towns for the two optional New Earth factions."""

from hashlib import sha256
from struct import pack, unpack_from

from .world_island_catalogue import _chunks, coastal_shape
from .world_options_factions import MERCHANT_TAG, PIRATE_TAG
from .world_settings_multiplayer_ai import _subfields
from .world_settings_multiplayer_island import _chunk, _crop_fields, _occurrences


# Native New Earth roles, current aliases, and reviewed standalone home-town aliases.
_FACTIONS = {
    5: (2, 16, b"VENECIA\0", b"VENEZIANER", b"VENEZIA01"),
    6: (1, 15, b"PIRATEN\0", b"PIRAT", b"PIRAT01"),
}
_BY_MASK = {entry[0]: entry for entry in _FACTIONS.values()}
_VENETIAN_TEMPLATE = 443
_DISCOVERY_MASK = 0x0381


def faction_for_template(entry: dict) -> int:
    """Identify a reviewed special template by catalogue classification and identity."""
    if not entry["fields"][6]:
        return 0
    if entry["fields"][3] or not entry["path"].startswith("WorldSettingsIslands/Nord/"):
        raise ValueError("The special faction island differs from the reviewed catalogue.")
    return 2 if entry["index"] == _VENETIAN_TEMPLATE else 1


def _field(tag: bytes, value: bytes) -> bytes:
    return tag.ljust(6, b"\0") + pack("<H", len(value)) + value


def _script(payload: bytes, enabled: int) -> bytes:
    seen = set()
    result = []
    aliases = {b'"' + old + b'" ' + str(seat).encode("ascii"): (mask, new)
               for seat, (mask, _, _, old, new) in _FACTIONS.items()}
    for line in payload.splitlines(keepends=True):
        text = line.rstrip(b"\r\n")
        if text not in aliases:
            result.append(line)
            continue
        mask, new = aliases[text]
        if mask in seen:
            raise ValueError("The New Earth faction script contains duplicate mappings.")
        seen.add(mask)
        if enabled & mask:
            result.append(b'"' + new + text[text.rfind(b'"'):] + line[len(text):])
    if seen != _BY_MASK.keys():
        raise ValueError("The New Earth faction script mappings are missing.")
    return b"".join(result)


def faction_players(base: list[tuple[bytes, bytes]], enabled: int, *,
                    pirate_frequency: int = 1, merchant_frequency: int = 1) -> list[tuple[bytes, bytes]]:
    """Select native scene players and bind both sides of the existing alias lookup."""
    if any(type(mode) is not int or not 0 <= mode <= 2 for mode in (pirate_frequency, merchant_frequency)):
        raise ValueError("Faction frequency must be Rare, Normal or Frequent.")
    records = []
    seen: set[tuple[int, bool]] = set()
    script = False
    for tag, value in base:
        if tag == b"BIGBROTHER":
            if script:
                raise ValueError("The New Earth faction script is duplicated.")
            value = _script(value, enabled)
            script = True
        if tag == b"SPIELER" and len(value) >= 8:
            version, seat = unpack_from("<II", value)
            if seat in _FACTIONS:
                mask, kind, culture, old, new = _FACTIONS[seat]
                fields = list(_subfields(value[8:]))
                head = bool(fields and fields[0][0] == b"HEAD")
                key = (seat, head)
                if version or key in seen:
                    raise ValueError("The New Earth faction player identity differs.")
                seen.add(key)
                if head:
                    if (len(fields[0][1]) != 108 or unpack_from("<I", fields[0][1])[0] != kind
                            or [data for name, data in fields if name == b"ALIAS"] != [old + b"\0"]
                            or [data for name, data in fields if name == b"VOLK"] != [culture]):
                        raise ValueError("The New Earth faction profile differs.")
                    value = value[:8] + b"".join(_field(name, new + b"\0" if name == b"ALIAS" else data)
                                                for name, data in fields)
                else:
                    controllers = [data for name, data in fields if name == b"COMP"]
                    if (len(controllers) != 1 or controllers[0][:8] != pack("<II", kind, seat)
                            or not controllers[0].endswith(b"\0")):
                        raise ValueError("The New Earth faction controller differs.")
                    frequency = pirate_frequency if mask == 1 else merchant_frequency
                    if enabled & mask and frequency != 1:
                        controller = controllers[0]
                        if any(token.startswith(b"SPEZFLAG=") for token in controller[8:].split(b"\0")):
                            raise ValueError("The New Earth faction controller already has special flags.")
                        # The native ASCII COMP loader reads the same saved word on each peer.
                        # Keep the single-player tag encoding and Normal pirate armament.
                        policy = (PIRATE_TAG | (1 << 10) if mask == 1 else MERCHANT_TAG) | (frequency << 8)
                        controller += f"SPEZFLAG={policy:d}".encode("ascii") + b"\0"
                        value = value[:8] + b"".join(
                            _field(name, controller if name == b"COMP" else data) for name, data in fields
                        )
                if not enabled & mask:
                    continue
        records.append((tag, value))
    if seen != {(seat, head) for seat in _FACTIONS for head in (False, True)} or not script:
        raise ValueError("The New Earth faction players or native script are missing.")
    return records


def linked_faction_island(entry: dict, row: dict, template: bytes, ware_types: bytes,
                           visibility: int) -> tuple[bytes, str, bytes]:
    """Use the verified standalone loader to import a populated island and its town."""
    faction = faction_for_template(entry)
    if not faction or row["rotation"] or row["cultures"]:
        raise ValueError("The selected special faction island cannot be rotated or change culture.")
    _, _, culture, _, alias = _BY_MASK[faction]
    return _linked_populated_island(entry, row, template, ware_types, visibility, culture, alias)


def _linked_populated_island(entry: dict, row: dict, template: bytes, ware_types: bytes,
                             visibility: int, culture: bytes, alias: bytes) -> tuple[bytes, str, bytes]:
    if row["rotation"] or sha256(template).hexdigest() != entry["sha256"]:
        raise ValueError("The populated island must be unrotated and match the reviewed file.")
    shape = coastal_shape(template)
    geometry = tuple(row[key] for key in ("width", "height", "climate"))
    if geometry != tuple(entry["fields"][:3]) or geometry != tuple(shape[key] for key in ("width", "height", "climate")):
        raise ValueError("The populated island geometry or climate differs.")

    root_end = 16 + unpack_from("<I", template, 12)[0]
    chunks = list(_chunks(template, 16, root_end))
    if (template[:12] != b"ANNO".ljust(12, b"\0") or
            [tag for tag, _ in chunks] != [b"WARETYPE", b"INSEL5", b"SPIELER"] or chunks[0][1] != ware_types):
        raise ValueError("The populated island native envelope differs.")
    island, resident = chunks[1][1], chunks[2][1]
    identity = pack("<II", 0, 0) + _field(b"VOLK", culture) + _field(b"ALIAS", alias + b"\0")
    if not resident.startswith(identity + b"STADT2"):
        raise ValueError("The populated island settlement owner differs.")

    updated = []
    types = set()
    for tag, data in _chunks(island, 12, len(island)):
        if tag in (b"ANBAU", b"OCCUR", b"DISCOVER"):
            if tag in types:
                raise ValueError("The populated island repeats a native resource or discovery record.")
            types.add(tag)
            if tag == b"ANBAU":
                data = _crop_fields(row["cropMask"], row["climate"])
            elif tag == b"OCCUR":
                # Some licensed populated islands carry the native final flag set.
                data = _occurrences(data, row["mineralMask"], row["climate"], row["width"], row["height"],
                                    entry["fields"][4], stocked=True)
            else:
                if len(data) != 4:
                    raise ValueError("The populated island discovery record differs.")
                flags, = unpack_from("<H", data)
                flags = (flags & ~_DISCOVERY_MASK) | (_DISCOVERY_MASK if visibility == 2 else 0)
                data = pack("<H", flags) + data[2:]
        updated.append(_chunk(tag, data))
    if types != {b"ANBAU", b"OCCUR", b"DISCOVER"} or not any(p.startswith(b"PROD2") for p in updated):
        raise ValueError("The populated island resources or native buildings are missing.")

    local = bytes(4) + island[4:8] + bytes(4) + b"".join(updated)
    asset = _chunk(b"ANNO", _chunk(b"WARETYPE", ware_types) + _chunk(b"INSEL5", local)
                   + _chunk(b"SPIELER", resident)) + template[root_end:]
    digest = sha256(asset).hexdigest()
    link = pack("<4HI", row["x"], row["y"], row["width"], row["height"], row["id"])
    link += f"WS\\{digest}.scp".encode("ascii") + b"\0"
    return _chunk(b"INSELLNK", link), digest, asset
