"""Food 0.6 + World source/ABI composition; no game or native module loading."""
from pathlib import Path
import copy
import hashlib
import json
import re
import struct
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from anno1503_overhaul import food_world_runtime as food
from anno1503_overhaul import world_options_build as options
from anno1503_overhaul import world_runtime_build as base
from anno1503_overhaul.food_household import FOOD06_VIEW_SHA256
from anno1503_overhaul.food_supply import FOOD05_WELT_SHA256, FOOD_PROGRESSION_WELT_SHA256


ROOT = base.ROOT
SOURCE = ROOT / "legacy/world_settings"
HOST = ROOT / ".local/game-copies/Food 0.6 Development"
WELT_SOURCE = ROOT / ".local/baselines/world_settings/native/AnnoWelt.source.dll"


class ActiveTable:
    """Retain the stale table as well as a distinct loader-active table."""
    def __init__(self, *, duplicate=False, moved=False):
        self.rva = 0x157DF4 + (12 if moved else 0)
        entries = [struct.pack("<III", *e[1]) for e in food.UNWIND_EDITS]
        if duplicate:
            entries.append(entries[0])
        self.table = b"".join(entries)
        self.stale = {0x14BE8C: bytes.fromhex("4d800600"),
                      0x14BE94: bytes.fromhex("4d80060053800600")}

    def directory(self, index):
        assert index == 3
        return self.rva, len(self.table)

    def read(self, rva, size):
        if rva in self.stale:
            return self.stale[rva][:size]
        at = rva - self.rva
        if not 0 <= at <= len(self.table) - size:
            raise ValueError("fixture read outside active table")
        return self.table[at:at + size]


def frozen_plan():
    return json.loads((SOURCE / base.ENGINE_PLAN).read_bytes())


def imported_sources():
    manifest = json.loads((ROOT / "provenance/legacy_import.json").read_bytes())
    return {row["path"].removeprefix(base.SOURCE_PREFIX): (ROOT / row["path"]).read_bytes()
            for row in manifest["source_files"] if row["path"].startswith(base.SOURCE_PREFIX)}


def local_host_available():
    try:
        return (hashlib.sha256(WELT_SOURCE.read_bytes()).hexdigest() == FOOD05_WELT_SHA256
                and hashlib.sha256((HOST / "View.dll").read_bytes()).hexdigest() == FOOD06_VIEW_SHA256)
    except OSError:
        return False


def build_food_welt():
    from anno1503_overhaul.food_supply import build_progression_welt

    return build_progression_welt(WELT_SOURCE.read_bytes())[0]


class FoodWorldRuntimeTests(unittest.TestCase):
    def test_active_directory_wins_over_retained_matching_old_table(self):
        plan = frozen_plan()
        original = copy.deepcopy(plan)
        proof = food._active_unwind_edits(ActiveTable(), plan)
        self.assertEqual([p["active_rva"] for p in proof], [0x157DF8, 0x157E00])
        self.assertEqual([p["frozen_rva"] for p in proof], [0x14BE8C, 0x14BE94])
        self.assertEqual(sum(a != b for a, b in zip(original["edits"], plan["edits"])), 2)
        for before, after in zip(original["edits"], plan["edits"]):
            self.assertEqual({k: v for k, v in before.items() if k != "rva"},
                             {k: v for k, v in after.items() if k != "rva"})

    def test_absent_ambiguous_or_moved_active_tuple_refuses(self):
        missing = ActiveTable()
        missing.table = missing.table[12:]
        for pe in (missing, ActiveTable(duplicate=True), ActiveTable(moved=True)):
            with self.subTest(table=pe.table.hex(), rva=pe.rva):
                with self.assertRaises(base.RuntimeBuildError):
                    food._active_unwind_edits(pe, frozen_plan())

    def test_unreviewed_unwind_patch_is_not_rebound(self):
        plan = frozen_plan()
        entry = next(e for e in plan["edits"] if e["rva"] == 0x14BE8C)
        entry["after"] = "00000000"
        with self.assertRaises(base.RuntimeBuildError):
            food._active_unwind_edits(ActiveTable(), plan)

    def test_header_and_plan_targets_agree_without_modifying_source(self):
        header = (SOURCE / base.ENGINE_HEADER).read_bytes()
        result = food.derive_engine_header(header)
        for old, triplet, field, before, after, active in food.UNWIND_EDITS:
            self.assertIn(("0x%xu" % old).encode(), header)
            self.assertNotIn(("0x%xu" % old).encode(), result)
            self.assertIn(("0x%xu" % active).encode(), result)
        self.assertEqual((SOURCE / base.ENGINE_HEADER).read_bytes(), header)
        with self.assertRaises(base.RuntimeBuildError):
            food.derive_engine_header(result)

    def test_unknown_native_host_and_plan_refuse(self):
        for host, plan in ((b"unknown", (SOURCE / base.ENGINE_PLAN).read_bytes()),
                           (b"unknown", b"{}")):
            with self.assertRaises(base.RuntimeBuildError):
                food.derive_engine_plan(host, plan)
        self.assertEqual(food.HOST_SHA256["AnnoWelt.dll"], FOOD_PROGRESSION_WELT_SHA256)
        self.assertEqual(food.HOST_SHA256["View.dll"], FOOD06_VIEW_SHA256)
        self.assertNotEqual(food.HOST_SHA256["AnnoWelt.dll"], base.FOOD_SHA256["AnnoWelt.dll"])

    def test_managed_host_uses_reviewed_guards_with_food_native_pins(self):
        files = imported_sources()
        ai, world = food._managed_host_sources(files[base.AI_LOADER], files[base.WORLD_SETTINGS])
        reviewed = base.transform_sources(files[base.BLOBS], files[base.AI_LOADER],
                                          files[base.WORLD_SETTINGS], base.FOOD_AI_CANDIDATES)
        expected_ai = reviewed[base.AI_LOADER]
        for name in ("CompLogic.dll", "CompLogicClassic.dll"):
            expected_ai = expected_ai.replace(base.STOCK_SHA256[name].encode(), base.FOOD_SHA256[name].encode())
            self.assertIn(base.FOOD_SHA256[name].encode(), ai)
        self.assertEqual(ai, expected_ai)
        self.assertEqual(world, reviewed[base.WORLD_SETTINGS].replace(
            b"The copied World Settings AI support has not completed activation.",
            b"The copied Food AI support has not completed activation."))
        self.assertIn(b"FILE_ATTRIBUTE_REPARSE_POINT", world)
        self.assertIn(b"_wcsicmp(full,exe)", world)
        with self.assertRaises(base.RuntimeBuildError):
            food._managed_host_sources(ai, world)

    def test_world_overlap_is_rejected_before_native_delegate_use(self):
        files = imported_sources()
        with mock.patch.object(food, "progression_edited_spans", return_value=((0xC714D, 14),)):
            with self.assertRaisesRegex(base.RuntimeBuildError, "overlaps"):
                food._coexistence_proof({}, files[base.BLOBS], files[base.ENGINE_PLAN])

    def test_extension_cannot_silently_rebind_an_older_profile(self):
        pins = dict(options.PINNED_RUNTIMES)
        for profile in ("world-only", "food-world", "unknown"):
            with self.assertRaises(base.RuntimeBuildError):
                options._build_options_runtime(profile, HOST, _food06_profile=True)
        with self.assertRaises(base.RuntimeBuildError):
            options._build_options_runtime(food.PROFILE, HOST, _food06_profile=True, publish=True)
        with self.assertRaises(base.RuntimeBuildError):
            options._build_options_runtime("world-only", HOST, _food06_asset_source=HOST)
        self.assertEqual(options.PINNED_RUNTIMES, pins)
        self.assertEqual(options.generator_id(), options.PINNED_GENERATOR)

    @unittest.skipUnless(local_host_available(), "exact private Food 0.6 host unavailable")
    def test_exact_native_plan_uses_active_exception_entries(self):
        raw = (SOURCE / base.ENGINE_PLAN).read_bytes()
        image = build_food_welt()
        plan = food.derive_engine_plan(image, raw)
        self.assertEqual(hashlib.sha256(plan).hexdigest(), food.ENGINE_PLAN_SHA256)
        value = json.loads(plan)
        self.assertEqual(len(value["edits"]), 173)
        rvas = {e["rva"] for e in value["edits"]}
        self.assertTrue({0x157DF8, 0x157E00}.issubset(rvas))
        self.assertFalse({0x14BE8C, 0x14BE94} & rvas)
        self.assertEqual(value["food06_derivative"]["active_exception_directory_rva"], 0x153420)
        self.assertEqual((SOURCE / base.ENGINE_PLAN).read_bytes(), raw)
        with self.assertRaises(base.RuntimeBuildError):
            food.derive_engine_plan(image, plan)

    @unittest.skipUnless(local_host_available(), "exact private Food 0.6 host unavailable")
    def test_complete_native_preflight_with_separate_asset_source(self):
        sources = imported_sources()
        original = dict(sources)
        with tempfile.TemporaryDirectory() as directory:
            minimal = Path(directory).resolve()
            for name in food.HOST_SHA256:
                value = build_food_welt() if name == "AnnoWelt.dll" else (HOST / name).read_bytes()
                (minimal / name).write_bytes(value)
            derived, proof = food.derive_sources(sources, minimal, asset_source=HOST)
            self.assertFalse((minimal / "Anlagen.dat").exists())
        self.assertEqual(sources, original)
        self.assertEqual(proof["engine_sites_verified"], 173)
        self.assertEqual(proof["hook_sites_verified"], 9)
        self.assertEqual(proof["food06_coexistence"]["world_write_spans"], 218)
        self.assertEqual(proof["food06_coexistence"]["overlapping_write_spans"], 0)
        self.assertEqual(proof["visibility_runtime_module_pins"]["View.dll"], FOOD06_VIEW_SHA256)
        self.assertEqual(proof["visibility_runtime_module_pins"]["AnnoWelt.dll"], FOOD_PROGRESSION_WELT_SHA256)
        pin_header = derived["developer/source/engine_resume/ai_loader/visibility_native_pins.h"].decode("ascii")
        emitted = {name: base._hex_bytes(value).hex()
                   for name, value in re.findall(r'\{L"([^"]+)",\{([^}]+)\}\}', pin_header)}
        self.assertEqual(emitted, proof["visibility_runtime_module_pins"])
        self.assertTrue(proof["faction_activity_ai"]["food06_demand_guarded"])
        self.assertFalse(proof["world_generator_abi_changed"])
        self.assertIn(b'"Fish (tons)"', derived[options.PRIVATE + "menu_create.inc"])
        self.assertIn(b'"Food (tons)"', options.apply_options(original)[options.PRIVATE + "menu_create.inc"])
        self.assertEqual(options.generator_id(), options.PINNED_GENERATOR)


if __name__ == "__main__":
    unittest.main()
