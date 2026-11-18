"""Reviewed Food 0.6 tier diets; no native good, stock or save slot is added.

The input is the exact Food 0.5 BGruppen result. Existing Food preparation can
construct that result from the separately verified stock input first. Only
food quantities in the five resident groups change; zero-weight needs are
removed so a later global unlock cannot introduce them into an earlier tier.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal, localcontext
from fractions import Fraction
import hashlib
import re
from types import MappingProxyType


VERSION = "0.6.0-dev.1"
REQUIRES_NEW_WORLD = True  # Removed needs shift saved per-house supply indices.
STOCK_BGRUPPEN_SHA256 = "63e876fd3afedca214b3d9cc45f022f2c595f473839690e96f34e12ed7849e3b"
FOOD05_BGRUPPEN_SHA256 = "93b27c43a9b9b8ff37b450af4556fffcb7e1fceef9c371d6054548baae16f234"
FOOD06_BGRUPPEN_SHA256 = "398421349c12bdd5c0cb631e0fe784ee76a55cea8f9f8153c35bd30042715e77"

FOOD_ORDER = ("NAHRUNG", "KART2", "WILD2", "BROT2", "MEAT2")
FOOD_IDS: Mapping[str, int] = MappingProxyType(dict(zip(FOOD_ORDER, (26, 40, 24, 25, 45))))
# This is BGruppen record order, not a claim about a separate native enum.
TIER_ORDER = ("PIONIER", "SIEDLER", "BUERGER", "KAUFLEUTE", "ARISTOKRATEN")
TIER_DATA_INDEX: Mapping[str, int] = MappingProxyType({name: i for i, name in enumerate(TIER_ORDER)})
TIER_WEIGHTS: Mapping[str, Mapping[str, int]] = MappingProxyType({
    name: MappingProxyType(dict(zip(FOOD_ORDER, weights)))
    for name, weights in zip(TIER_ORDER, (
        (45, 45, 10, 0, 0),
        (40, 35, 10, 0, 15),
        (30, 25, 10, 20, 15),
        (20, 20, 10, 25, 25),
        (15, 10, 15, 25, 35),
    ))
})
_OLD_WEIGHTS = dict(zip(FOOD_ORDER, (60, 15, 15, 5, 5)))
_GROUP = re.compile(r"(?m)^[ \t]*BGruppeNr:[ \t]+([A-Z_]+)[ \t]*\r?$")
_NEED = re.compile(
    r"(?m)^(?P<head>[ \t]*Ware:[ \t]+(?P<good>[A-Z0-9_]+)[^\r\n]*\r?\n"
    r"[ \t]*Menge:[ \t]+)(?P<amount>[0-9]+(?:\.[0-9]+)?)"
    r"(?P<tail>[^\r\n]*\r?\n[ \t]*Priority:[^\r\n]*\r?\n"
    r"[ \t]*Force:[^\r\n]*(?:\r?\n|$))"
)


class FoodDietError(ValueError):
    """Resident data or a requested diet differs from the reviewed definition."""


def _digest(data: bytes) -> str:
    if not isinstance(data, bytes):
        raise FoodDietError("Resident definitions must be immutable bytes.")
    return hashlib.sha256(data).hexdigest()


def active_weights(tier: str, unlocked_foods: Iterable[str] | None = None) -> dict[str, int]:
    """Return positive tier weights, filtered by a caller-proven unlock set.

    This does not infer game unlocks or alter native demand amounts. Callers
    must obtain active needs from the actual house/engine. An empty result is
    deliberately empty; it is not evidence of a fully supplied household.
    """
    if not isinstance(tier, str) or tier not in TIER_WEIGHTS:
        raise FoodDietError("Unknown resident tier.")
    if unlocked_foods is None:
        unlocked = set(FOOD_ORDER)
    else:
        if isinstance(unlocked_foods, (str, bytes)):
            raise FoodDietError("Expected a collection of food identifiers.")
        try:
            unlocked = set(unlocked_foods)
        except TypeError as exc:
            raise FoodDietError("Invalid food identifier collection.") from exc
        if not unlocked.issubset(FOOD_IDS):
            raise FoodDietError("Unknown food identifier.")
    return {good: weight for good, weight in TIER_WEIGHTS[tier].items()
            if weight and good in unlocked}


def normalized_weights(tier: str, unlocked_foods: Iterable[str] | None = None) -> dict[str, Fraction]:
    """Exact proportions for the eligible foods; no consumption is performed."""
    weights = active_weights(tier, unlocked_foods)
    denominator = sum(weights.values())
    return {good: Fraction(weight, denominator) for good, weight in weights.items()}


def _sections(data: bytes) -> tuple[str, str, str]:
    try:
        text = data.decode("cp1252")
        if text.count("[BGRUPPE]") != 1 or text.count("[BAUSTUFEN]") != 1:
            raise FoodDietError("Expected one resident and one progression section.")
        header, rest = text.split("[BGRUPPE]", 1)
        groups, footer = rest.split("[BAUSTUFEN]", 1)
    except (UnicodeError, ValueError) as exc:
        raise FoodDietError("Malformed resident definitions.") from exc
    return header, groups, footer


def _groups(populations: str) -> tuple[str, tuple[tuple[str, str], ...]]:
    matches = tuple(_GROUP.finditer(populations))
    if tuple(match[1] for match in matches) != TIER_ORDER:
        raise FoodDietError("Unexpected resident group names, order or count.")
    groups = tuple((match[1], populations[match.start():matches[i + 1].start()
                    if i + 1 < len(matches) else len(populations)])
                   for i, match in enumerate(matches))
    return populations[:matches[0].start()], groups


def _food_needs(group: str) -> dict[str, re.Match[str]]:
    matches = [match for match in _NEED.finditer(group) if match["good"] in FOOD_IDS]
    if len(matches) != len({match["good"] for match in matches}):
        raise FoodDietError("Duplicate food need in a resident group.")
    return {match["good"]: match for match in matches}


def _without_food_needs(group: str) -> str:
    return _NEED.sub(lambda match: "" if match["good"] in FOOD_IDS else match[0], group)


def _rewrite_food05(data: bytes) -> bytes:
    """Pure structural rewrite, called only after the public fingerprint guard."""
    header, populations, footer = _sections(data)
    preamble, groups = _groups(populations)
    rewritten = []
    with localcontext() as context:
        context.prec = 50
        for tier, group in groups:
            needs = _food_needs(group)
            if set(needs) != set(FOOD_ORDER):
                raise FoodDietError("Expected all five Food 0.5 needs in each tier.")
            total = sum((Decimal(match["amount"]) for match in needs.values()), Decimal(0))
            if total <= 0 or any(Decimal(needs[good]["amount"]) * 100 != total * weight
                                 for good, weight in _OLD_WEIGHTS.items()):
                raise FoodDietError("Food 0.5 demand proportions differ.")

            def change(match: re.Match[str]) -> str:
                good = match["good"]
                if good not in FOOD_IDS:
                    return match[0]
                weight = TIER_WEIGHTS[tier][good]
                if not weight:
                    return ""
                amount = format((total * weight / 100).normalize(), "f")
                return match["head"] + amount + match["tail"]

            result = _NEED.sub(change, group)
            new = _food_needs(result)
            if (set(new) != set(active_weights(tier))
                    or sum((Decimal(match["amount"]) for match in new.values()), Decimal(0)) != total
                    or _without_food_needs(result) != _without_food_needs(group)):
                raise FoodDietError("Tier rewrite changed unrelated data or total food demand.")
            rewritten.append(result)
    return (header + "[BGRUPPE]" + preamble + "".join(rewritten) + "[BAUSTUFEN]" + footer).encode("cp1252")


def transform_food05(data: bytes) -> bytes:
    """Accept exact Food 0.5 input or return an exact already-built 0.6 no-op."""
    digest = _digest(data)
    if digest == FOOD06_BGRUPPEN_SHA256:
        return data
    if digest != FOOD05_BGRUPPEN_SHA256:
        raise FoodDietError("Unsupported Food resident definitions; expected the reviewed Food 0.5 input.")
    result = _rewrite_food05(data)
    if _digest(result) != FOOD06_BGRUPPEN_SHA256:
        raise FoodDietError("Food 0.6 resident definitions differ from the reviewed output.")
    return result


def validate_against_vanilla(food06: bytes, vanilla: bytes) -> dict:
    """Prove data-level totals and unrelated needs against exact stock bytes.

    This does not establish native rounding, unlock activation, household UI,
    starvation behavior, or a successful game run.
    """
    if _digest(food06) != FOOD06_BGRUPPEN_SHA256 or _digest(vanilla) != STOCK_BGRUPPEN_SHA256:
        raise FoodDietError("Unreviewed tier-diet or stock resident definitions.")
    _, current, _ = _sections(food06)
    _, original, _ = _sections(vanilla)
    _, current_groups = _groups(current)
    _, original_groups = _groups(original)
    proof = []
    with localcontext() as context:
        context.prec = 50
        for (tier, changed), (original_tier, stock) in zip(current_groups, original_groups):
            assert tier == original_tier
            needs = _food_needs(changed)
            original_food = _food_needs(stock)
            if set(original_food) != {"NAHRUNG"}:
                raise FoodDietError("Stock food definition differs.")
            total = Decimal(original_food["NAHRUNG"]["amount"])
            amounts = {good: Decimal(match["amount"]) for good, match in needs.items()}
            non_food = lambda group: tuple(match[0] for match in _NEED.finditer(group)
                                          if match["good"] not in FOOD_IDS)
            if sum(amounts.values(), Decimal(0)) != total or non_food(changed) != non_food(stock):
                raise FoodDietError("Original total or unrelated resident needs changed.")
            proof.append(dict(tier=tier, data_index=TIER_DATA_INDEX[tier], total=format(total, "f"),
                              amounts={good: format(amount, "f") for good, amount in amounts.items()}))
    return dict(version=VERSION, tiers=proof, original_totals_preserved=True,
                unrelated_needs_preserved=True, zero_weight_needs_omitted=True,
                actual_game_run=False)
