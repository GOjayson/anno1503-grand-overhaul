"""Prepare African-style player building records for the local prototype."""

from hashlib import sha256
from pathlib import Path

from .fountain import FOUNTAIN_SOURCE_HASHES, ORNAMENTAL_WELL_ID, make_player_ornament, read_entries
from .residence import TIER_SOURCES, TIER_STEP, make_residences


AFRICAN_ORNAMENT = 1751
AFRICAN_RESIDENCE = 1760
HEARTH_ART = 3310
AFRICAN_TIER_ART = (3304, 3303, 3309, 3306, 3305)
AFRICAN_HOUSES = tuple(AFRICAN_RESIDENCE + TIER_STEP * tier for tier in range(len(AFRICAN_TIER_ART)))
AFRICAN_TIER_SOURCES = tuple(
    (tier, ordinary, art)
    for (tier, ordinary, _), art in zip(TIER_SOURCES, AFRICAN_TIER_ART, strict=True)
)
HEARTH_PREIMAGES = {
    "anlagen.dat": "8a382f9154432584fe08f1e90e60c909ccd4a0a237945f4663e0a52c65a3154a",
    "anlagen.addon": "b113c188be825c563c60ceb6f977f5bd30082fec2c5d47842dcf083b407261d7",
    "anlagen.classic": "cb5d4789b905a679f519204a18dc389b2098db0094411c479b64fbd6a7eb6802",
}


def native_entries(path: Path) -> tuple[bytes, ...]:
    """Return the hearth followed by the five residence definitions."""
    entries = read_entries(path)
    if AFRICAN_ORNAMENT in entries:
        raise ValueError(f"African ornament ID {AFRICAN_ORNAMENT} is occupied")
    donor_name = path.name.lower()
    hearth = entries[HEARTH_ART]
    player_ornament = entries[ORNAMENTAL_WELL_ID]
    preimages = FOUNTAIN_SOURCE_HASHES.get(donor_name)
    if (preimages is None or sha256(player_ornament).hexdigest() != preimages[0]
            or sha256(hearth).hexdigest() != HEARTH_PREIMAGES.get(donor_name)):
        raise ValueError(f"Unexpected African ornament sources in {path.name}")
    ornament = make_player_ornament(player_ornament, hearth, AFRICAN_ORNAMENT)
    housing = make_residences(entries, AFRICAN_RESIDENCE, AFRICAN_TIER_SOURCES, b"AfLehm")
    return (ornament, *housing)
