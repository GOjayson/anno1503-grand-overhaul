"""Tier-diet behavior and trust boundaries, without installing or running Anno.

Portable fixtures are authored miniature definitions, not game data. Fixture
fingerprints are substituted only in isolated wrapper tests. The optional
original-data check retains every real trust pin and opens local inputs read-only.
"""
from __future__ import annotations

from decimal import Decimal, localcontext
from fractions import Fraction
import hashlib
import importlib.util
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from anno1503_overhaul import food_diet as diet


# Native Food 0.5 presentation/need order differs from the design table order.
NEED_ORDER = ("NAHRUNG", "WILD2", "KART2", "BROT2", "MEAT2")
BEFORE = (
    ("0.6", "0.15", "0.15", "0.05", "0.05"),
    ("0.54", "0.135", "0.135", "0.045", "0.045"),
    ("0.7404", "0.1851", "0.1851", "0.0617", "0.0617"),
    ("0.018", "0.0045", "0.0045", "0.0015", "0.0015"),
    ("0.402", "0.1005", "0.1005", "0.0335", "0.0335"),
)
# Independently calculated expectations for totals 1, .9, 1.234, .03 and .67.
AFTER = (
    ("0.45", "0.1", "0.45", None, None),
    ("0.36", "0.09", "0.315", None, "0.135"),
    ("0.3702", "0.1234", "0.3085", "0.2468", "0.1851"),
    ("0.006", "0.003", "0.006", "0.0075", "0.0075"),
    ("0.1005", "0.1005", "0.067", "0.1675", "0.2345"),
)
TIERS = ("PIONIER", "SIEDLER", "BUERGER", "KAUFLEUTE", "ARISTOKRATEN")
HEADER = ("; authored fixture: production and unlocks must survive\r\n[WAREN]\r\n"
          "  Id: BROT2\r\n  BauFirst: INFRA_STUFE_3B\r\n"
          "  Id: MEAT2\r\n  BauFirst: INFRA_STUFE_2B\r\n[BGRUPPE]\r\n\r\n")
FOOTER = "[BAUSTUFEN]\r\n; authored progression fixture\r\nPreserve: yes\r\n"


def need(good, amount):
    return (f"  Ware:       {good}\r\n  Menge:      {amount}\r\n"
            "  Priority:   HIGH\r\n  Force:      TRUE\r\n")


def fixture(rows=BEFORE):
    text = HEADER
    for i, (tier, amounts) in enumerate(zip(TIERS, rows)):
        text += f"  BGruppeNr:  {tier}\r\n  Wohnmax: {8 + i}\r\n  CustomMetadata: tier-{i}\r\n"
        for good, amount in zip(NEED_ORDER, amounts):
            if amount is not None:
                text += need(good, amount)
        text += ("\r\n  Ware:       SALZ ; independent advancement need\r\n"
                 "  Menge:      0.2\r\n  Priority:   LOW\r\n  Force:      FALSE\r\n"
                 "; Infrastructure is not food\r\n  Ware:       KAPELLE\r\n"
                 "  Menge:      1\r\n  Priority:   NORMAL\r\n  Force:      FALSE\r\n\r\n")
    return (text + FOOTER).encode("cp1252")


def sha(data):
    return hashlib.sha256(data).hexdigest()


class TierDietRewriteTests(unittest.TestCase):
    def test_tier_changes_conserve_each_total_and_every_unrelated_byte(self):
        source = fixture()
        self.assertEqual(diet._rewrite_food05(source), fixture(AFTER))
        self.assertEqual(source, fixture())
        self.assertTrue(diet._rewrite_food05(source).startswith(HEADER.encode("cp1252")))
        self.assertTrue(diet._rewrite_food05(source).endswith(FOOTER.encode("cp1252")))

    def test_zero_foods_are_absent_even_with_all_chain_unlocks(self):
        result = diet._rewrite_food05(fixture()).decode("cp1252")
        groups = re.split(r"(?m)^  BGruppeNr:  ", result)[1:]
        self.assertNotIn("BROT2", groups[0])
        self.assertNotIn("MEAT2", groups[0])
        self.assertNotIn("BROT2", groups[1])
        self.assertIn("MEAT2", groups[1])
        self.assertEqual(tuple(diet.active_weights("PIONIER", diet.FOOD_ORDER)),
                         ("NAHRUNG", "KART2", "WILD2"))
        self.assertNotIn("BROT2", diet.active_weights("SIEDLER", diet.FOOD_ORDER))
        self.assertTrue(diet.REQUIRES_NEW_WORLD)

    def test_decimal_context_does_not_change_reviewed_output(self):
        with localcontext() as context:
            context.prec = 2
            self.assertEqual(diet._rewrite_food05(fixture()), fixture(AFTER))

    def test_unknown_or_ambiguous_group_structure_and_wrong_baseline_refuse(self):
        source = fixture()
        bad_inputs = (
            source.replace(b"PIONIER", b"OTHER", 1),
            source.replace(b"BGruppeNr:  SIEDLER", b"BGruppeNr:  PIONIER", 1),
            source.replace(need("WILD2", "0.15").encode(), b"", 1),
            source.replace(need("WILD2", "0.15").encode(),
                           2 * need("WILD2", "0.15").encode(), 1),
            source.replace(b"Menge:      0.6", b"Menge:      0.61", 1),
            source.replace(b"[BGRUPPE]", b"[OTHER]", 1),
            source + b"[BGRUPPE]",
        )
        for data in bad_inputs:
            with self.subTest(data_sha256=sha(data)), self.assertRaises(diet.FoodDietError):
                diet._rewrite_food05(data)

    def test_guarded_transform_accepts_only_the_pinned_input_and_output(self):
        source, expected = fixture(), fixture(AFTER)
        with patch.object(diet, "FOOD05_BGRUPPEN_SHA256", sha(source)), \
                patch.object(diet, "FOOD06_BGRUPPEN_SHA256", sha(expected)):
            self.assertEqual(diet.transform_food05(source), expected)
            self.assertIs(diet.transform_food05(expected), expected)
            with patch.object(diet, "_rewrite_food05") as rewrite:
                for invalid in (source + b"changed", b"", bytearray(source), "text"):
                    with self.subTest(kind=type(invalid)), self.assertRaises(diet.FoodDietError):
                        diet.transform_food05(invalid)
                rewrite.assert_not_called()
            with patch.object(diet, "_rewrite_food05", return_value=expected + b"changed"):
                with self.assertRaises(diet.FoodDietError):
                    diet.transform_food05(source)

    def test_real_pins_do_not_accept_an_authored_fixture(self):
        with self.assertRaises(diet.FoodDietError):
            diet.transform_food05(fixture())


class TierWeightTests(unittest.TestCase):
    def test_lock_filter_reweights_only_eligible_foods_without_mutating_demand(self):
        active = {"NAHRUNG", "KART2", "WILD2"}
        self.assertEqual(diet.normalized_weights("SIEDLER", active),
                         {"NAHRUNG": Fraction(8, 17), "KART2": Fraction(7, 17),
                          "WILD2": Fraction(2, 17)})
        self.assertEqual(sum(diet.normalized_weights("SIEDLER", active).values()), 1)
        self.assertEqual(diet.TIER_WEIGHTS["SIEDLER"]["MEAT2"], 15)
        self.assertEqual(diet.normalized_weights("PIONIER", {"BROT2", "MEAT2"}), {})
        self.assertEqual(diet.normalized_weights("BUERGER", set()), {})
        self.assertEqual(diet.normalized_weights("ARISTOKRATEN")["MEAT2"], Fraction(7, 20))

    def test_invalid_tier_and_food_identifiers_refuse(self):
        for tier in ("OTHER", "pionier", 0, None):
            with self.subTest(tier=tier), self.assertRaises(diet.FoodDietError):
                diet.active_weights(tier)
        for available in ({"SALZ"}, "NAHRUNG", b"NAHRUNG", [None], [["NAHRUNG"]]):
            with self.subTest(available=available), self.assertRaises(diet.FoodDietError):
                diet.active_weights("PIONIER", available)

    def test_metadata_and_returned_filters_cannot_rewrite_the_shared_policy(self):
        selected = diet.active_weights("BUERGER")
        selected["NAHRUNG"] = 100
        self.assertEqual(diet.active_weights("BUERGER")["NAHRUNG"], 30)
        with self.assertRaises(TypeError):
            diet.TIER_WEIGHTS["PIONIER"]["NAHRUNG"] = 100
        self.assertEqual(diet.FOOD_IDS["NAHRUNG"], 26)
        self.assertEqual(tuple(diet.TIER_DATA_INDEX), TIERS)


class OriginalTierDietTests(unittest.TestCase):
    def test_actual_stock_to_food05_to_tier_diet_retains_real_fingerprints(self):
        source = ROOT / ".local/game-copies/World Settings/Data/BGruppen.dat"
        if not source.is_file():
            self.skipTest("Reviewed locally owned stock resident input is unavailable.")
        vanilla = source.read_bytes()
        self.assertEqual(sha(vanilla), diet.STOCK_BGRUPPEN_SHA256)
        # Load the immutable public transforms under an isolated import alias.
        sources = (
            ("formats", "16ccf7bb69171b12760ce7ffb7b1c86f1269e0483935834103b4d7e13dd6a3de"),
            ("transforms", "1e3b418b4b00b0e190583246933e8418fc570f29d7ab3ffdb290145c30ebd067"),
        )
        loaded = {}
        for name, pin in sources:
            path = ROOT / "legacy/food_overhaul/support" / (name + ".py")
            self.assertEqual(sha(path.read_bytes()), pin)
            spec = importlib.util.spec_from_file_location("food06_original_" + name, path)
            module = importlib.util.module_from_spec(spec)
            with patch.dict(sys.modules, {"formats": loaded.get("formats", module)}):
                spec.loader.exec_module(module)
            loaded[name] = module
        fm, tr = loaded["formats"], loaded["transforms"]
        food05 = tr.diet(tr.add_definition(fm.split_food_demand(vanilla)))
        self.assertEqual(sha(food05), diet.FOOD05_BGRUPPEN_SHA256)
        result = diet.transform_food05(food05)
        self.assertEqual(sha(result), diet.FOOD06_BGRUPPEN_SHA256)
        self.assertEqual(diet.transform_food05(result), result)
        proof = diet.validate_against_vanilla(result, vanilla)
        self.assertTrue(proof["original_totals_preserved"])
        self.assertTrue(proof["unrelated_needs_preserved"])
        self.assertFalse(proof["actual_game_run"])
        self.assertEqual([tier["tier"] for tier in proof["tiers"]], list(TIERS))
        self.assertEqual(source.read_bytes(), vanilla)
        for changed, stock in ((result + b"changed", vanilla), (result, vanilla + b"changed")):
            with self.assertRaises(diet.FoodDietError):
                diet.validate_against_vanilla(changed, stock)


if __name__ == "__main__":
    unittest.main()
