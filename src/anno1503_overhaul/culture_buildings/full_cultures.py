"""Build verified local player-owned variants of the ten native art sets."""

from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from pathlib import Path
import re
from struct import pack, unpack_from

from .african import AFRICAN_HOUSES, AFRICAN_ORNAMENT, AFRICAN_TIER_ART, native_entries
from .fountain import FOUNTAIN_ID, _entry_id, entry_fields, fountain_entry, make_entry, read_entries
from .residence import APPEARANCE_FIELDS, RESIDENCE_ID, TIER_SOURCES, TIER_STEP, residence_entries


@dataclass(frozen=True)
class Style:
    key: str
    labels: str
    residence_labels: str
    first: int
    housing: tuple[int, ...]
    source_ids: range
    ornament: tuple[int, int, str] | None = None

    @property
    def houses(self) -> tuple[int, ...]:
        return tuple(self.first + TIER_STEP * index for index in range(5))


STYLES = (
    Style("VENETIAN", "Venetian Buildings|Venezianische Gebäude|Venetiaanse gebouwen",
          "Venetian Residence|Venezianisches Wohnhaus|Venetiaans woonhuis", RESIDENCE_ID,
          tuple(art for _, _, art in TIER_SOURCES), range(3950, 3999),
          (3971, FOUNTAIN_ID, "Venetian Fountain|Venezianischer Brunnen|Venetiaanse fontein")),
    Style("AFRICAN", "African Buildings|Afrikanische Gebäude|Afrikaanse gebouwen",
          "African Residence|Afrikanisches Wohnhaus|Afrikaans woonhuis", AFRICAN_HOUSES[0],
          AFRICAN_TIER_ART, range(3301, 3316),
          (3310, AFRICAN_ORNAMENT, "African Cooking Hearth|Afrikanische Kochstelle|Afrikaanse kookplaats")),
    Style("MOORISH", "Moorish Buildings|Maurische Gebäude|Moorse gebouwen",
          "Moorish Residence|Maurisches Wohnhaus|Moors woonhuis", 840,
          (3017, 3001, 3003, 3008, 3008), range(3000, 3019)),
    Style("BEDOUIN", "Bedouin Buildings|Beduinische Gebäude|Bedoeïense gebouwen",
          "Bedouin Residence|Beduinisches Wohnzelt|Bedoeïenentent", 1040,
          (3107, 3103, 3102, 3101, 3101), range(3100, 3111)),
    Style("MONGOLIAN", "Mongolian Buildings|Mongolische Gebäude|Mongoolse gebouwen",
          "Mongolian Residence|Mongolische Jurte|Mongoolse joert", 1880,
          (3205, 3208, 3205, 3208, 3203), range(3200, 3216)),
    Style("AZTEC", "Aztec Buildings|Aztekische Gebäude|Azteekse gebouwen",
          "Aztec Residence|Aztekisches Wohnhaus|Azteeks woonhuis", 1980,
          (3401, 3407, 3415, 3407, 3415), range(3400, 3417)),
    Style("INUIT", "Inuit Buildings|Inuit-Gebäude|Inuitgebouwen",
          "Inuit Residence|Inuit-Wohnhaus|Inuitwoning", 2080,
          (3501, 3501, 3508, 3505, 3505), range(3500, 3518)),
    Style("NATIVEAM", "Native American Buildings|Nordamerikanische Gebäude|Inheems-Amerikaanse gebouwen",
          "Native American Residence|Nordamerikanisches Wohnzelt|Inheems-Amerikaanse tent", 2300,
          (3601, 3608, 3609, 3604, 3604), range(3600, 3615)),
    Style("POLYNESIAN", "Polynesian Buildings|Polynesische Gebäude|Polynesische gebouwen",
          "Polynesian Residence|Polynesisches Wohnhaus|Polynesisch woonhuis", 2400,
          (3707, 3704, 3707, 3704, 3704), range(3700, 3714)),
    Style("PIRATE", "Pirate Buildings|Piratengebäude|Piratengebouwen",
          "Pirate Residence|Piratenwohnhaus|Piratenwoning", 2580,
          (3854, 3851, 3852, 3853, 3853), range(3850, 3873)),
)


# Local display labels describe the original art, whose game name tables have no entries.
# Housing artworks named by a tier are omitted here unless also offered as a separate ornament.
LABEL_ROWS = """
3000|Market hall|Markthalle|Markthal
3002|Mosque|Moschee|Moskee
3004|Muezzin tower|Muezzinturm|Muezzintoren
3005|Garrison|Garnison|Garnizoen
3006|Covered stall|Überdachter Stand|Overdekte kraam
3007|Well|Brunnen|Waterput
3009|Market shelter|Marktverschlag|Marktafdak
3010|Jeweler's workshop|Goldschmiedewerkstatt|Juweliersatelier
3011|Goat pen|Ziegenstall|Geitenstal
3012|Spice grower's hut|Gewürzbauerhütte|Specerijentelershut
3013|Camel stable|Kamelstall|Kamelenstal
3014|Paving tile I|Pflasterfeld I|Bestrating I
3015|Paving tile II|Pflasterfeld II|Bestrating II
3016|Paving tile III|Pflasterfeld III|Bestrating III
3018|Trading post|Kontor|Handelspost
3100|Market tent|Marktzelt|Markttent
3104|Animal watering place|Viehtränke|Drinkplaats
3105|Market stall|Marktstand|Marktkraam
3106|Military tent|Militärzelt|Legertent
3108|Jester's square|Gauklerplatz|Narrenplein
3109|Spice tent|Gewürzzelt|Specerijentent
3110|Prayer tent|Betzelt|Gebedstent
3200|Market|Markt|Markt
3201|Temple|Tempel|Tempel
3202|Monastery|Kloster|Klooster
3203|Harvest tent|Erntezelt|Oogsttent
3204|Portal|Portal|Poort
3206|Stonecutter's yurt|Steinmetzjurte|Joert van de steenhouwer
3207|Empty yurts|Leere Jurten|Lege joerten
3209|Square garrison yurt|Eckige Militärjurte|Vierkante legerjoert
3210|Market stall|Marktstand|Marktkraam
3211|Animal enclosure|Tiergehege|Dierenverblijf
3212|Prayer flags|Gebetsfahnen|Gebedsvlaggen
3213|Sheep shelter|Schafunterstand|Schapenstal
3214|Armorer's workshop|Waffenwerkstatt|Wapensmederij
3301|Conical hall|Kegelhaus|Kegelvormige hal
3302|Clay market hall|Lehm-Markthalle|Leemmarkthal
3307|Cooking place|Kochplatz|Kookplek
3308|Temple|Tempel|Tempel
3311|Market stall|Marktstand|Marktkraam
3312|Large hearth|Große Feuerstelle|Grote vuurplaats
3313|Goat shed|Ziegenstall|Geitenstal
3314|Trading post|Kontor|Handelspost
3315|Herbalist's farm|Heilkräuterfarm|Kruidenboerderij
3400|Market|Markt|Markt
3402|Garrison|Garnison|Garnizoen
3403|Temple|Tempel|Tempel
3404|Fire temple|Feuertempel|Vuurtempel
3405|Four-entrance temple|Tempel mit vier Eingängen|Tempel met vier ingangen
3406|Market ruins|Marktruine|Marktruïne
3408|Statue|Standbild|Standbeeld
3409|Cocoa farm|Kakaofarm|Cacaoboerderij
3410|Goldsmith's workshop|Goldschmiede|Goudsmidse
3411|Paving tile I|Pflasterfeld I|Bestrating I
3412|Paving tile II|Pflasterfeld II|Bestrating II
3413|Ceremonial paving|Festplatzpflaster|Ceremoniële bestrating
3414|Elephant graveyard|Elefantenfriedhof|Olifantenkerkhof
3416|Chicken coop|Hühnerstall|Kippenhok
3500|Main hall|Haupthalle|Hoofdgebouw
3502|Polar bear display|Eisbärplatz|IJsbeeropstelling
3503|Fish display|Fischplatz|Visopstelling
3504|Fire pit|Feuerstelle|Vuurplaats
3505|Twin huts|Doppelhütte|Tweelinghutten
3507|Snow well|Schneebrunnen|Sneeuwput
3509|Shelter hall|Verbandshaus|Schuilhal
3511|Market stall|Marktstand|Marktkraam
3512|Snow mound|Schneehaufen|Sneeuwhoop
3513|Trading post|Kontor|Handelspost
3514|Jester's square|Gauklerplatz|Narrenplein
3515|Blubber hut|Walspeckhütte|Walvisspekhut
3516|Ice sculpture|Eisskulptur|IJssculptuur
3517|Ruins marker|Ruinenzeichen|Ruïnemarkering
3600|Market stall|Marktstand|Marktkraam
3602|Chief's tent|Häuptlingszelt|Tent van het stamhoofd
3603|Totem|Totem|Totem
3605|Fire pit|Feuerstelle|Vuurplaats
3606|Fur hunter's camp|Felljägerlager|Kamp van de pelsjager
3607|Paddock|Koppel|Paardenweide
3610|Horse shelter|Pferdeunterstand|Paardenoverkapping
3611|Fence I|Zaun I|Hek I
3612|Fence II|Zaun II|Hek II
3613|Sugarcane grower's tent|Zuckerrohrzelt|Suikerriettent
3614|Cotton grower's tent|Baumwollzelt|Katoentent
3700|Chief's hall|Häuptlingshalle|Hal van het stamhoofd
3702|Animal shelter|Tierunterstand|Dierenverblijf
3703|Square tower|Eckiger Turm|Vierkante toren
3705|Figure|Figur|Beeld
3706|Boatbuilder's hut|Bootsbauerhütte|Botenbouwhut
3708|Water hole|Wasserloch|Waterpoel
3709|Market stall|Marktstand|Marktkraam
3710|Garrison|Garnison|Garnizoen
3711|Silkworm farm|Seidenraupenfarm|Zijderupskwekerij
3712|Trading post|Kontor|Handelspost
3713|Swing|Schaukel|Schommel
3850|Market hall|Markthalle|Markthal
3855|Trading post|Kontor|Handelspost
3856|Market stall|Marktstand|Marktkraam
3857|Tavern|Wirtshaus|Herberg
3858|Pirate square|Piratenplatz|Piratenplein
3859|Wall I|Mauer I|Muur I
3860|Wall II|Mauer II|Muur II
3861|Wall III|Mauer III|Muur III
3862|Watchtower|Wachturm|Wachttoren
3863|Ruined garrison|Verfallene Garnison|Vervallen garnizoen
3864|Warehouse|Lagerhaus|Pakhuis
3865|Cage|Zwinger|Kooi
3866|Carriage|Kutsche|Koets
3867|Jester's square|Gauklerplatz|Narrenplein
3868|Wall corner I|Mauerecke I|Muurhoek I
3869|Wall corner II|Mauerecke II|Muurhoek II
3870|Wall corner III|Mauerecke III|Muurhoek III
3871|Roasting spit|Spanferkelgrill|Braadspit
3872|Pigsty|Schweinestall|Varkensstal
3950|Fish hall|Fischhalle|Vishal
3951|Town house|Stadthaus|Stadshuis
3957|Doge's Palace|Dogenpalast|Dogenpaleis
3958|Campanile|Campanile|Campanile
3959|Lighthouse|Leuchtturm|Vuurtoren
3962|Large fountain|Großer Brunnen|Grote fontein
3963|Obelisk|Obelisk|Obelisk
3964|Paving tile I|Pflasterfeld I|Bestrating I
3965|Paving tile II|Pflasterfeld II|Bestrating II
3966|Jester's paving|Gauklerpflaster|Narrenbestrating
3967|Piazza I|Piazza I|Piazza I
3968|Piazza II|Piazza II|Piazza II
3970|Lion statue|Löwenstatue|Leeuwenbeeld
3972|Tower house|Wohnturm|Woontoren
3973|Basilica|Basilika|Basiliek
3979|Shoemaker's house|Schusterhaus|Schoenmakershuis
3980|Market stall|Marktstand|Marktkraam
3984|Bollard|Poller|Meerpaal
3985|Tree square|Baumplatz|Bomenplein
3986|Shrub square|Buschplatz|Struikenplein
3987|Single square tile|Einzelnes Platzfeld|Losse pleintegel
3989|Trading post|Kontor|Handelspost
"""


EXCLUDED = {
    3215: "Duplicate monastery model wired as a scenario raw resource",
    3506: "Ice hole needs ice terrain and its native fishing logic",
    3510: "Inuit fishing operation requires shore placement and workers",
    3701: "Polynesian suspension bridge needs custom river and path conditions",
    3978: "Venetian fishing operation requires shore placement and workers",
    **dict.fromkeys((3955, 3956, 3961, 3990, 3991, 3992, 3993, 3997, 3998),
                   "Venetian bridge or segment requires bridge placement and path rules"),
    **dict.fromkeys((3974, 3975, 3976, 3977, 3981, 3982, 3983, 3988, 3994, 3995, 3996),
                   "Venetian pier or segment requires coastal or water placement rules"),
}
PAVING = {3014, 3015, 3016, 3108, 3411, 3412, 3413, 3514, 3867, 3964, 3965, 3966, 3967, 3968, 3987}
ASSETS = {int(line.partition("|")[0]): line.partition("|")[2] for line in LABEL_ROWS.strip().splitlines()}
# Reserve a persistent ID for every source in the ordered catalogue, including exclusions.
# None of these object IDs may touch any housing variant slot.
_SOURCE_ORDER = tuple(source for style in STYLES for source in style.source_ids)
_RESIDENCE_SLOTS = {base + offset for style in STYLES for base in style.houses for offset in (0, 1)}
_OBJECT_BANK = tuple(ident for ident in (*range(2284, 2500), *range(2711, 2740)) if ident not in _RESIDENCE_SLOTS)
OBJECT_IDS = dict(zip(_SOURCE_ORDER, _OBJECT_BANK[:len(_SOURCE_ORDER)], strict=True))
ORNAMENT_TEMPLATES = (2552, 2564)
VISUAL_FIELDS = (b"HAEUSER", b"COLORS", b"WALKMASK", b"SHOTMASK", b"OWNMASK", b"VERSION2")
HEAD_BYTES = 56


def _labels(value: str) -> dict[str, str]:
    return dict(zip(("en", "de", "nl"), value.split("|"), strict=True))


def categories():
    """Return the ten ordered data-only menu categories and 3-language labels."""
    from .culture_menu import CultureBuilding, CultureCategory

    groups = []
    for style in STYLES:
        house_labels = _labels(style.residence_labels)
        aristocrat_labels = {
            "en": house_labels["en"].replace("Residence", "Aristocrat Residence"),
            "de": house_labels["de"] + " (Aristokraten)",
            "nl": house_labels["nl"] + " (aristocraten)",
        }
        buildings = [
            CultureBuilding(style.first, house_labels, "residence", style.houses[1:4],
                            art_source=style.housing[0]),
            CultureBuilding(style.houses[-1], aristocrat_labels, "aristocrat",
                            art_source=style.housing[-1]),
        ]
        if style.ornament:
            source, ident, labels = style.ornament
            buildings.append(CultureBuilding(ident, _labels(labels), art_source=source))
        for source in style.source_ids:
            if source not in ASSETS:
                continue
            labels = _labels(ASSETS[source])
            if source not in PAVING:
                labels["en"] += " (decorative)"
                labels["de"] += " (Dekoration)"
                labels["nl"] += " (decoratie)"
            buildings.append(CultureBuilding(OBJECT_IDS[source], labels, art_source=source))
        groups.append(CultureCategory(style.key, _labels(style.labels), tuple(buildings)))
    return tuple(groups)


def save_targets() -> dict[int, tuple[str, str, bool]]:
    """Map all player-owned IDs to their style, English label and residence flag."""
    tiers = ("Pioneer", "Settler", "Citizen", "Merchant", "Aristocrat")
    targets = {}
    for category in categories():
        style = category.labels["en"].removesuffix(" Buildings")
        for building in category.buildings:
            if building.icon == "residence":
                for ident, tier in zip((building.ident, *building.alternate_ids), tiers[:4], strict=True):
                    targets[ident] = (style, tier, True)
            elif building.icon == "aristocrat":
                targets[building.ident] = (style, tiers[-1], True)
            else:
                targets[building.ident] = (style, building.labels["en"], False)
    return targets


def require_endpoint_rules(path: Path) -> None:
    """Refuse group rules that could cross into the neighboring residence series."""
    raw = path.read_text(encoding="cp1252")
    groups = {name: body for name, body in re.findall(
        r"(?ms)^[ \t]*BGruppeNr:[ \t]+([A-Z]+)[^\n]*\n(.*?)(?=^[ \t]*BGruppeNr:|^\s*\[|\Z)", raw
    )}
    for name, required in (("PIONIER", "NoDowngrade"), ("KAUFLEUTE", "NoUpgrade"),
                           ("ARISTOKRATEN", "NoUpgrade"), ("ARISTOKRATEN", "NoDowngrade")):
        if re.findall(r"(?m)^\s*" + required + r":[ \t]+(\w+)", groups.get(name, "")) != ["TRUE"]:
            raise ValueError(f"The stock {name} group must have {required} enabled")


def _residence(entry: bytes, art: bytes, ident: int, expected_tier: bytes) -> bytes:
    house = entry_fields(entry)
    donor = entry_fields(art)
    if house[b"PRODTYPE"] != expected_tier + b"\0" or house[b"HEAD"][:2] != b"\x04\x04":
        raise ValueError(f"Unexpected stock residence for {ident}")
    if donor[b"PRODTYPE"] not in {b"PIONIER\0", b"STEINMETZ\0"}:
        raise ValueError(f"Unexpected residence façade for {ident}")
    head = bytearray(house[b"HEAD"])
    head[11] = 0  # No lookups into unidentified random-variant slots.
    return make_entry(entry, ident, {b"HEAD": bytes(head), **{tag: donor[tag] for tag in APPEARANCE_FIELDS}})


def _ornament(template: bytes, art: bytes, ident: int) -> bytes:
    stock = entry_fields(template)
    donor = entry_fields(art)
    head = bytearray(stock[b"HEAD"])
    native = donor[b"HEAD"]
    if len(head) != HEAD_BYTES or len(native) != HEAD_BYTES or stock[b"PRODTYPE"] != b"ZIERDE\0":
        raise ValueError(f"Unexpected decorative source for {ident}")
    width, height = native[:2]
    scale, = unpack_from("<f", native, 20)
    if (not 1 <= width <= 8 or not 1 <= height <= 8 or not isfinite(scale) or not 0 <= scale <= 12
            or any(len(donor[tag]) != 3 * height * 4 for tag in (b"WALKMASK", b"SHOTMASK", b"OWNMASK"))):
        raise ValueError(f"Unexpected decorative footprint or scale for art {_entry_id(art)}")
    head[:2] = native[:2]
    head[11] = 0
    head[19] = 0xff  # Decorative build placement can use every standard land climate.
    head[20:24] = native[20:24]
    # The structural masks and model references are cosmetic. Keep neutral player
    # behavior fields and exclude NPC entrances, production, and object links.
    fields = {tag: donor[tag] for tag in VISUAL_FIELDS}
    fields.update({b"HEAD": bytes(head), b"INFRAMIN": b"INFRA_EVER\0"})
    return make_entry(template, ident, fields)


def _faction_digest(entries: dict[int, bytes]) -> str:
    digest = sha256()
    for ident in (*_SOURCE_ORDER, *ORNAMENT_TEMPLATES, *(template for _, template, _ in TIER_SOURCES)):
        if ident not in entries and ident == 3215:
            continue
        digest.update(pack("<I", ident))
        digest.update(entries[ident])
    return digest.hexdigest()


PINNED_INPUTS = {
    "anlagen.dat": "8e06856c7d1543dbeb2a9cd5522088c897e9448b83245be0333a11154269f561",
    "anlagen.addon": "8d3fb4478f7d43a9c7d383db679c880e5f1ad586aaf4efbcf4ac63fb41cc1ef3",
    "anlagen.classic": "77c4bc557a3d5ae2b3de1a0c303087306580740acc243c1aacbcef8472c8c559",
}


def archive_entries(path: Path, *, include_prototype: bool = True) -> tuple[bytes, ...]:
    """Return new archive chunks for all ten styles. Existing NPC IDs stay intact.

    Passing include_prototype=False extends an already-patched Venetian/African archive.
    The caller must verify the stock Pioneer/Aristocrat endpoint gates before applying
    the packed housing chain allocation to a playtest profile.
    """
    entries = read_entries(path)
    if _faction_digest(entries) != PINNED_INPUTS.get(path.name.lower()):
        raise ValueError(f"Unrecognized faction definition preimages in {path.name}")
    original_pairs = (FOUNTAIN_ID, *STYLES[0].houses, AFRICAN_ORNAMENT, *STYLES[1].houses)
    new_entries = []
    if include_prototype:
        new_entries.extend((fountain_entry(path), *residence_entries(path), *native_entries(path)))
    elif not all(ident in entries for ident in original_pairs):
        raise ValueError("Expected the complete existing Venetian and African prototypes")

    for style in STYLES[2:]:
        occupied = tuple(ident for base in style.houses for ident in (base, base + 1) if ident in entries)
        if occupied:
            raise ValueError(f"Reserved home IDs are occupied by existing definitions: {occupied}")
        new_entries.extend(_residence(entries[player], entries[art], ident, tier)
                           for ident, art, (tier, player, _) in zip(style.houses, style.housing, TIER_SOURCES, strict=True))
    for source in ASSETS:
        ident = OBJECT_IDS[source]
        template = ORNAMENT_TEMPLATES[0 if source in PAVING else 1]
        new_entries.append(_ornament(entries[template], entries[source], ident))
    identities = [_entry_id(entry) for entry in new_entries]
    if len(set(identities)) != len(identities) or set(identities) & entries.keys():
        raise ValueError("An assigned culture-building ID overlaps a loaded definition")
    uncovered = set(_SOURCE_ORDER) - EXCLUDED.keys() - ASSETS.keys()
    uncovered -= {ident for style in STYLES for ident in style.housing}
    uncovered -= {style.ornament[0] for style in STYLES if style.ornament}
    if uncovered:
        raise ValueError(f"Unclassified culture sources: {sorted(uncovered)}")
    return tuple(new_entries)
