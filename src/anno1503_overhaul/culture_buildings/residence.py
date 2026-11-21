"""Prepare a five-tier Venetian residence for the local History Edition prototype."""

from pathlib import Path

from .fountain import DEFINITION_LIMIT, entry_fields, make_entry, read_entries


RESIDENCE_ID = 1620
TIER_STEP = 20
TIER_SOURCES = (
    (b"PIONIER", 501, 3952),
    (b"SIEDLER", 520, 3954),
    (b"BUERGER", 540, 3953),
    (b"KAUFLEUTE", 560, 3969),
    (b"ARISTOKRATEN", 580, 3960),
)
APPEARANCE_FIELDS = (b"HAEUSER", b"COLORS", b"VERSION2")


def residence_entries(path: Path, first_id: int = RESIDENCE_ID) -> tuple[bytes, ...]:
    """Build the Venetian five-tier residence chain from this archive's art."""
    return make_residences(read_entries(path), first_id, TIER_SOURCES, b"Venez")


def make_residences(
    entries: dict[int, bytes],
    first_id: int,
    tier_sources: tuple[tuple[bytes, int, int], ...],
    artwork_marker: bytes,
) -> tuple[bytes, ...]:
    """Build the Pioneer entry and its four ordinary promotion targets.

    AnnoWelt resolves the next tier at the next multiple of 20. Demotion looks
    up the preceding multiple of 20, then tries that ID plus one. Substituting
    a separate entry at each multiple keeps the existing upgrade/demotion path
    without sending ordinary residents into the new series.
    """
    identifiers = tuple(first_id + TIER_STEP * tier for tier in range(len(TIER_SOURCES)))
    if first_id <= TIER_STEP or first_id % TIER_STEP or identifiers[-1] + TIER_STEP >= DEFINITION_LIMIT:
        raise ValueError("House definitions need their own complete twenty-ID groups")
    # Even inactive adjacent tiers would connect the new series to someone
    # else's native promotion or demotion path.
    occupied = set(entries).intersection(range(first_id, identifiers[-1] + TIER_STEP + 2))
    if occupied:
        raise ValueError(f"House tier groups overlap existing definitions {sorted(occupied)}")

    additions = []
    for ident, (tier, house_id, art_id) in zip(identifiers, tier_sources, strict=True):
        house = entry_fields(entries[house_id])
        art = entry_fields(entries[art_id])
        if house[b"PRODTYPE"] != tier + b"\0" or not house[b"HEAD"].startswith(b"\x04\x04"):
            raise ValueError(f"Unexpected native house definition {house_id}")
        if art[b"PRODTYPE"] != b"PIONIER\0" or artwork_marker not in art[b"HAEUSER"]:
            raise ValueError(f"Unexpected façade definition {art_id}")
        # AnnoGame HEAD byte 11 stores the random variant count and stride.
        # Stock tiers have several adjacent IDs. This prototype defines one
        # appearance per tier, so the engine must keep the looked-up base ID.
        head = bytearray(house[b"HEAD"])
        head[11] = 0
        replacements = {field: art[field] for field in APPEARANCE_FIELDS}
        replacements[b"HEAD"] = bytes(head)
        additions.append(make_entry(entries[house_id], ident, replacements))
    return tuple(additions)
