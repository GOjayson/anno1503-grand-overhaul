"""Independent policy checks on the actual compiled runtime in Python only.

No Anno process is opened, no hooks are installed, no scene is staged, and no
game or game-copy file is changed. These tests check exported settings/plans;
the separate loaded-certificate/native fixtures and real game runs have their
own evidence. Positive AI remains guarded until normal game activation.
"""
from pathlib import Path
import argparse
import ctypes as C
import hashlib
import itertools
import json
import re
import struct

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[1]
SOURCE = PACKAGE / "developer/source"
CROPS = [0x18000, 0xf009, 0xf949, 0xf06b, 0xf6b9, 0xf04d]
MINERALS = [0, 0x45, 0x65, 0x41, 0x43, 0x4b]
FIELDS = [("size", C.c_uint32), ("difficulty", C.c_int32),
          ("islandSize", C.c_int32), ("islandCount", C.c_int32),
          ("spacing", C.c_int32), ("aiCount", C.c_int32),
          ("cultures", C.c_uint32), ("factions", C.c_uint32),
          ("startingMoney", C.c_int32), ("startingFleet", C.c_int32),
          ("aiDifficulty", C.c_int32), ("plantFertility", C.c_int32),
          ("mineralFertility", C.c_int32), ("worldSize", C.c_int32)]


class Settings(C.Structure):
    _fields_ = FIELDS


class Island(C.Structure):
    _fields_ = [(name, C.c_uint32) for name in
                ["id", "x", "y", "width", "height", "templateIndex",
                 "cropMask", "mineralMask", "cultures", "climate"]]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def settings(**values):
    selected = dict(size=56, difficulty=1, islandSize=3, islandCount=24,
                    spacing=0, aiCount=0, cultures=255, factions=3,
                    startingMoney=30000, startingFleet=0, aiDifficulty=1,
                    plantFertility=1, mineralFertility=1, worldSize=1024)
    selected.update(values)
    return Settings(**selected)


def catalogue():
    source = SOURCE / "engine_resume/ai_food/experiment_runtime/world_catalogue.h"
    rows = []
    pattern = re.compile(r'^\{"([^"\r\n]*)",(\d+(?:,\d+){8}),\{([\d,]+)\}\},?$', re.M)
    for match in pattern.finditer(source.read_text(encoding="utf-8")):
        values = [int(x) for x in match[2].split(",")]
        names = ["width", "height", "climate", "cultures", "oreSlots", "whales",
                 "excludedNative", "sizeChoices", "fertileLand"]
        item = dict(zip(names, values))
        item["path"] = json.loads('"' + match[1] + '"')
        item["sha256"] = bytes(int(x) for x in match[3].split(",")).hex()
        assert len(item["sha256"]) == 64
        rows.append(item)
    assert len(rows) == 444, "The actual generated template catalogue was not parsed"
    return rows, source


def separated(a, b, gap):
    return (a["x"] + a["width"] + gap <= b["x"] or
            b["x"] + b["width"] + gap <= a["x"] or
            a["y"] + a["height"] + gap <= b["y"] or
            b["y"] + b["height"] + gap <= a["y"])


def geography(rows):
    return tuple(tuple(row[key] for key in
                       ["id", "x", "y", "width", "height", "templateIndex", "cultures", "climate"])
                 for row in rows)


def masks(rows, key):
    return tuple(row[key] for row in rows)


def check_world(rows, selected, templates):
    assert len(rows) == selected.islandCount
    climates = cultures = crop_union = mineral_union = whales = 0
    for i, row in enumerate(rows):
        assert row["id"] == i
        assert row["templateIndex"] < len(templates)
        template = templates[row["templateIndex"]]
        for key in ["width", "height", "climate", "cultures"]:
            assert row[key] == template[key], (key, row, template)
        assert row["x"] % 8 == row["y"] % 8 == 0
        assert row["x"] >= selected.spacing and row["y"] >= selected.spacing
        assert row["x"] + row["width"] + selected.spacing <= selected.worldSize
        assert row["y"] + row["height"] + selected.spacing <= selected.worldSize
        for previous in rows[:i]:
            assert separated(row, previous, selected.spacing), "Island overlap/spacing regression"
        climate = row["climate"]
        assert 0 <= climate < 6
        assert row["cropMask"] & ~CROPS[climate] == 0, "Unsupported climate crop"
        assert (row["cropMask"] ^ CROPS[climate]) & 0x1f009 == 0, "Native base/ecology was removed"
        assert row["mineralMask"] & ~(MINERALS[climate] & 0x2f) == 0
        assert row["mineralMask"].bit_count() <= template["oreSlots"], "Native ore-slot capacity exceeded"
        if selected.plantFertility == 0:
            assert row["cropMask"] == CROPS[climate], "Very fertile omitted a supported favorable crop"
        if selected.mineralFertility == 0:
            assert row["mineralMask"].bit_count() == min(template["oreSlots"],
                                                       (MINERALS[climate] & 0x2f).bit_count())
        climates |= 1 << climate
        cultures |= row["cultures"]
        crop_union |= row["cropMask"]
        mineral_union |= row["mineralMask"]
        whales += template["whales"]
    assert climates == 63 and cultures == selected.cultures
    assert crop_union == 0x1ffff and mineral_union == 0x2f and whales > 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dll", type=Path, default=SOURCE / "runtime_dev3/AnnoWorldSettings.dll")
    parser.add_argument("--seed-count", type=int, default=32)
    parser.add_argument("--output", type=Path, default=HERE / "real_runtime_policy_results.json")
    args = parser.parse_args()
    assert 4 <= args.seed_count <= 128
    dll = args.dll.resolve(strict=True)
    binary = dll.read_bytes()
    pe = struct.unpack_from("<I", binary, 0x3c)[0]
    assert binary[pe:pe+4] == b"PE\0\0"
    assert struct.unpack_from("<H", binary, pe+4)[0] == 0x8664
    assert struct.unpack_from("<H", binary, pe+24)[0] == 0x20b
    metadata_path = dll.with_name("build_result.json")
    metadata = json.loads(metadata_path.read_bytes())
    runtime_hash = sha(dll)
    assert runtime_hash == metadata["sha256"], "Runtime differs from its compiled source record"
    assert metadata["abi_size"] == 56, "New fertility runtime has not been built (expected ABI56)"
    for name, expected in metadata["source_sha256"].items():
        assert sha(SOURCE / name) == expected, ("Compiled source changed", name)
    templates, catalogue_path = catalogue()
    assert C.sizeof(Settings) == 56 and C.sizeof(Island) == 40
    lib = C.CDLL(str(dll))
    assert lib.WorldSettingsSettingsSize() == 56
    validate = lib.WorldSettingsValidateSettings
    validate.argtypes = [C.POINTER(Settings), C.c_void_p, C.c_uint32]
    validate.restype = C.c_int
    build = lib.WorldSettingsBuildPlan
    build.argtypes = [C.POINTER(Settings), C.c_uint32, C.c_void_p, C.c_uint32]
    build.restype = C.c_int
    count = lib.WorldSettingsPlanCount
    count.argtypes = []
    count.restype = C.c_int
    get = lib.WorldSettingsPlanIsland
    get.argtypes = [C.c_uint32, C.POINTER(Island)]
    get.restype = C.c_int
    error = C.create_string_buffer(512)

    def plan(selected, seed):
        error.value = b""
        assert validate(C.byref(selected), error, len(error)) == 1, error.value
        assert build(C.byref(selected), seed, error, len(error)) == 1, (seed, error.value)
        result = []
        for i in range(count()):
            value = Island()
            assert get(i, C.byref(value)) == 1
            result.append({name: int(getattr(value, name)) for name, _ in Island._fields_})
        assert get(len(result), C.byref(Island())) == 0
        check_world(result, selected, templates)
        return result

    valid_settings = 0
    for difficulty, money, fleet, ai, factions, plant, mineral in itertools.product(
            range(3), [10000, 30000, 50000, 80000, 100000], range(3), range(4),
            range(4), range(4), range(4)):
        selected = settings(difficulty=difficulty, startingMoney=money, startingFleet=fleet,
                            aiDifficulty=ai, factions=factions, plantFertility=plant,
                            mineralFertility=mineral)
        assert validate(C.byref(selected), error, len(error)) == 1, error.value
        valid_settings += 1

    rejected = []
    for field, value in [("plantFertility", -1), ("plantFertility", 4),
                         ("mineralFertility", -1), ("mineralFertility", 4),
                         ("size", 44), ("size", 32), ("aiCount", -1), ("aiCount", 4),
                         ("startingMoney", 25000), ("startingFleet", 3), ("aiDifficulty", 4)]:
        selected = settings(**{field: value})
        assert validate(C.byref(selected), error, len(error)) == 0 and error.value
        assert build(C.byref(selected), 903, error, len(error)) == 0 and error.value
        rejected.append(dict(field=field, value=value))
    assert validate(None, error, len(error)) == 0 and error.value
    assert build(None, 903, error, len(error)) == 0 and error.value
    for ai_count in [1, 2, 3]:
        selected = settings(aiCount=ai_count)
        assert validate(C.byref(selected), error, len(error)) == 0 and b"activation" in error.value
        assert build(C.byref(selected), 903, error, len(error)) == 0

    seed_rows = []
    capacity_one_islands = 0
    ore_free_eligible_low = 0
    plant_changes = mineral_changes = mixed_plant_changes = mixed_mineral_changes = 0
    nested_comparisons = 0
    for ordinal in range(args.seed_count):
        seed = 0 if ordinal == 0 else (903 + (ordinal-1) * 2654435761) & 0xffffffff
        matrix = {}
        for plant, mineral in itertools.product(range(4), range(4)):
            matrix[plant, mineral] = plan(settings(plantFertility=plant, mineralFertility=mineral), seed)
        reference = geography(matrix[0, 0])
        for rows in matrix.values():
            assert geography(rows) == reference, "Fertility changed island selection/placement"
        for plant in range(4):
            assert all(masks(matrix[plant, mineral], "cropMask") == masks(matrix[plant, 0], "cropMask")
                       for mineral in range(4)), "Mineral setting changed plant selection"
        for mineral in range(4):
            assert all(masks(matrix[plant, mineral], "mineralMask") == masks(matrix[0, mineral], "mineralMask")
                       for plant in range(4)), "Plant setting changed mineral selection"
        for i in range(len(reference)):
            low, medium, very = [matrix[level, 0][i]["cropMask"] for level in [2, 1, 0]]
            assert low & ~medium == medium & ~very == 0
            assert matrix[3, 0][i]["cropMask"] in [low, medium, very]
            nested_comparisons += 2
            low_ore, medium_ore, very_ore = [matrix[0, level][i]["mineralMask"] for level in [2, 1, 0]]
            assert low_ore & ~medium_ore == medium_ore & ~very_ore == 0
            assert matrix[0, 3][i]["mineralMask"] in [low_ore, medium_ore, very_ore]
            nested_comparisons += 2
            template = templates[matrix[0, 0][i]["templateIndex"]]
            if template["oreSlots"] == 1:
                capacity_one_islands += 1
            if template["oreSlots"] and template["climate"] and low_ore == 0:
                ore_free_eligible_low += 1
        crop_signatures = {level: masks(matrix[level, 0], "cropMask") for level in range(4)}
        mineral_signatures = {level: masks(matrix[0, level], "mineralMask") for level in range(4)}
        plant_changes += crop_signatures[2] != crop_signatures[0]
        mineral_changes += mineral_signatures[2] != mineral_signatures[0]
        mixed_plant_changes += crop_signatures[3] not in [crop_signatures[0], crop_signatures[2]]
        mixed_mineral_changes += mineral_signatures[3] not in [mineral_signatures[0], mineral_signatures[2]]
        seed_rows.append(dict(seed=seed, islands=len(reference),
            climate_supported_crop_counts={str(level): sum((x["cropMask"] & 0x1fff).bit_count() for x in matrix[level, 0]) for level in range(4)},
            mineral_good_counts={str(level): sum(x["mineralMask"].bit_count() for x in matrix[0, level]) for level in range(4)},
            ore_free_island_counts={str(level): sum(x["mineralMask"] == 0 for x in matrix[0, level]) for level in range(4)}))
    assert capacity_one_islands > 0, "No real capacity-one island exercised"
    assert ore_free_eligible_low > 0, "Low never left an ore-capable island without minerals"
    assert plant_changes and mineral_changes and mixed_plant_changes and mixed_mineral_changes

    # Every preceding preset/money/fleet/AI-difficulty option remains independent
    # of geography and both availability masks. Four representative fertility
    # pairs cover all new levels; the seed matrix above covers the full4x4.
    old_option_plans = 0
    for plant, mineral in [(0, 0), (1, 2), (2, 1), (3, 3)]:
        baseline = plan(settings(plantFertility=plant, mineralFertility=mineral), 903)
        for difficulty, money, fleet, ai in itertools.product(
                range(3), [10000, 30000, 50000, 80000, 100000], range(3), range(4)):
            rows = plan(settings(difficulty=difficulty, startingMoney=money, startingFleet=fleet,
                                 aiDifficulty=ai, plantFertility=plant, mineralFertility=mineral), 903)
            assert rows == baseline, "A preceding starting option changed fertility or geography"
            old_option_plans += 1
    result = dict(scope=__doc__, runtime_sha256=runtime_hash, abi_size=56,
                  verifier_sha256=sha(Path(__file__).resolve()),
                  compiled_build_metadata_sha256=sha(metadata_path),
                  compiled_source_files_verified=len(metadata["source_sha256"]),
                  catalogue_sha256=sha(catalogue_path), actual_template_count=len(templates),
                  valid_settings_cases=valid_settings, rejected_settings_cases=rejected,
                  null_settings_refused=True, old_44_byte_abi_refused=True,
                  positive_ai_counts_blocked_without_actual_game_activation=[1, 2, 3],
                  seed_count=args.seed_count, fertility_matrix_plan_count=args.seed_count*16,
                  old_starting_option_independence_plans=old_option_plans,
                  nested_per_island_comparisons=nested_comparisons,
                  capacity_one_real_template_islands=capacity_one_islands,
                  ore_free_eligible_islands_in_low=ore_free_eligible_low,
                  seeds_with_plant_change=plant_changes, seeds_with_mineral_change=mineral_changes,
                  seeds_with_mixed_plant_distribution=mixed_plant_changes,
                  seeds_with_mixed_mineral_distribution=mixed_mineral_changes,
                  all_essential_world_resources_preserved=True,
                  geo_and_plant_mineral_independence=True, seeds=seed_rows,
                  native_world_loader_executed=False, game_executed=False,
                  harvesting_yield_or_accessibility_proven=False, passed=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "seeds"}, indent=2))


if __name__ == "__main__":
    main()
