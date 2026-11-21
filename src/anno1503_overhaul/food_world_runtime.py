"""Separate, exact Food 0.6 + World Settings runtime construction.

The original World-only and Food 0.5 builders retain their inputs and pins.
This profile uses the Food 0.6 disk modules and the existing World transaction;
it does not compose the old, already-patched World DLLs with Food 0.6 DLLs.
Only fresh staged source is changed. Building does not install or run a game.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct

from . import city_statistics
from . import world_options_build as options
from . import world_runtime_build as base
from .filesystem import checked_path
from .food_household import FOOD06_VIEW_SHA256, HOUSE_VTABLE as VIEW_HOUSE_VTABLE, HOOKS as VIEW_HOOKS
from .food_supply import (FOOD_PROGRESSION_WELT_SHA256, HOUSE_VTABLE, GETTERS,
                          PROMOTION, progression_edited_spans)


PROFILE = "food06-world"
# Filled only after independent candidate builds and native proof review.
RUNTIME_SHA256 = "928667ae84f54f9401103acdf81431cbc9d3d056b11da0eecaf2cb2c02b88fc9"
ENGINE_PLAN_SHA256 = "229e625e32ee69c13de4e2e619e6df66ed43c56ac61a603099e83f1793b46c0d"
GUARDED_RUNTIME_SHA256 = "c9d87dadd3f6319c25c2a9d2c71915105cc95f0def76b71c9fc76b5aede6a1cc"
GUARDED_ENGINE_PLAN_SHA256 = "6c62b49e5cbb7c5b958f712d2ebd31734e6c7f626354b408e382194ee556cf65"
UNWIND_EDITS = (
    (0x14BE8C, (0x68024, 0x6804D, 0x115800), 4,
     "4d800600", "59800600", 0x157DF8),
    (0x14BE94, (0x6804D, 0x68053, 0x115814), 0,
     "4d80060053800600", "598006005f800600", 0x157E00),
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def runtime_hash(city_statistics_guard: bool = False) -> str:
    return GUARDED_RUNTIME_SHA256 if city_statistics_guard else RUNTIME_SHA256


def engine_plan_hash(city_statistics_guard: bool = False) -> str:
    return GUARDED_ENGINE_PLAN_SHA256 if city_statistics_guard else ENGINE_PLAN_SHA256


def expected_native_hashes(*, city_statistics_guard: bool = False) -> dict[str, str]:
    """One exact host, never an alternative list accepted by older profiles."""
    from .packages import FOOD_SPEC_SHA256
    raw = (base.ROOT / "legacy/food_overhaul/food_patch.json").read_bytes()
    if _sha(raw) != FOOD_SPEC_SHA256:
        raise base.RuntimeBuildError("The preserved Food native specification changed.")
    food = json.loads(raw)
    return {**base.STOCK_SHA256,
            **{item["name"]: item["sources"]["combined-0.5.0"]
               for item in food["native_modules"]},
            "AnnoWelt.dll": (city_statistics.FOOD06_GUARDED_WELT_SHA256
                             if city_statistics_guard else FOOD_PROGRESSION_WELT_SHA256),
            "View.dll": FOOD06_VIEW_SHA256,
            "AnnoDisplay.dll": options.DISPLAY_SHA256}


HOST_SHA256 = expected_native_hashes()


def _active_unwind_edits(pe: base.PE, plan: dict) -> list[dict]:
    """Rebind by unique active RUNTIME_FUNCTION tuple, not retained old bytes."""
    table_rva, size = pe.directory(3)
    if not table_rva or not size or size % 12:
        raise base.RuntimeBuildError("Food 0.6 has no bounded active exception table.")
    table = pe.read(table_rva, size)
    relocations = []
    for old, triplet, field, before, after, reviewed in UNWIND_EDITS:
        needle = struct.pack("<III", *triplet)
        matches = [at for at in range(0, size, 12) if table[at:at + 12] == needle]
        if len(matches) != 1:
            raise base.RuntimeBuildError("An active World exception tuple is absent or ambiguous.")
        target = table_rva + matches[0] + field
        if target != reviewed or pe.read(target, len(bytes.fromhex(before))).hex() != before:
            raise base.RuntimeBuildError("The reviewed Food 0.6 exception edit moved or changed.")
        edits = [e for e in plan["edits"] if e.get("module", plan.get("module")) == "AnnoWelt.dll"
                 and e.get("rva") == old]
        if (len(edits) != 1 or edits[0].get("category") != "unwind"
                or edits[0].get("before") != before or edits[0].get("after") != after):
            raise base.RuntimeBuildError("The preserved World exception edit changed.")
        edits[0]["rva"] = target
        relocations.append(dict(module="AnnoWelt.dll", frozen_rva=old, active_rva=target,
                                parent_triplet=list(triplet), before=before, after=after))
    return relocations


def derive_engine_plan(welt: bytes, frozen: bytes) -> bytes:
    welt_hash = _sha(welt)
    guarded = welt_hash == city_statistics.FOOD06_GUARDED_WELT_SHA256
    if (not guarded and welt_hash != FOOD_PROGRESSION_WELT_SHA256) or _sha(frozen) != base.ENGINE_PLAN_SHA256:
        raise base.RuntimeBuildError("The Food 0.6 World image or frozen engine plan differs.")
    pe, plan = base.PE(welt), json.loads(frozen)
    relocations = _active_unwind_edits(pe, plan)
    plan["profile"] += "-food06-world-v1"
    if guarded:
        plan["profile"] += "-city-statistics"
    plan["food06_derivative"] = dict(
        frozen_engine_plan_sha256=base.ENGINE_PLAN_SHA256,
        food06_welt_sha256=welt_hash,
        active_exception_directory_rva=pe.directory(3)[0],
        active_exception_directory_size=pe.directory(3)[1],
        native_disk_hash_metadata="Inherited artifact hashes describe the frozen Food 0.5 World overlay, not this Food 0.6 disk host.",
        unwind_table_relocations=relocations)
    result = (json.dumps(plan, indent=2) + "\n").encode("utf-8")
    if _sha(result) != engine_plan_hash(guarded):
        raise base.RuntimeBuildError("The Food 0.6 World engine plan differs from its reviewed pin.")
    return result


def derive_engine_header(header: bytes) -> bytes:
    for old, unused_tuple, unused_field, unused_before, unused_after, active in UNWIND_EDITS:
        header = base._replace(header, ("0x%xu" % old).encode("ascii"),
                               ("0x%xu" % active).encode("ascii"), 1,
                               "Food 0.6 active exception table entry")
    return header


def _managed_host_sources(ai_loader: bytes, world_settings: bytes) -> tuple[bytes, bytes]:
    """Adopt the existing managed-host guard without adopting stock Food pins."""
    ai_loader = base._replace(ai_loader,
        b"!absolute(copyRoot)||!absolute(sourceRoot)||!_stricmp(copyRoot,sourceRoot)",
        b"!absolute(copyRoot)||!absolute(sourceRoot)", 1, "Food 0.6 managed AI host")
    ai_loader = base._replace(ai_loader, b"AI modules require distinct absolute source and copy folders.",
        b"AI modules require verified absolute source and copy folders.", 1, "Food 0.6 AI diagnostic")
    world_settings = base._replace(world_settings, b".anno1503-worldsettings-test-copy.json",
        b".anno1503-grand-overhaul-copy.json", 2, "Food 0.6 managed-copy marker")
    world_settings = base._replace(world_settings,
        b"attributes==INVALID_FILE_ATTRIBUTES||(attributes&FILE_ATTRIBUTE_DIRECTORY)",
        b"attributes==INVALID_FILE_ATTRIBUTES||(attributes&(FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT))",
        1, "regular Food 0.6 managed-copy marker")
    newline = b"\r\n" if b"\r\n" in world_settings else b"\n"
    before = b'        configurationFailure("Development-copy root must differ from the actual game executable folder, including directory aliases.");goto done;'
    after = (b"        /* This derivative permits only its Python-verified managed host as the data root. */" + newline
        + b'        if(_wcsicmp(full,exe)){configurationFailure("Managed host root must match the actual executable folder without aliases.");goto done;}' + newline
        + b"        attributes=GetFileAttributesW(marker);" + newline
        + b'        if(attributes==INVALID_FILE_ATTRIBUTES||(attributes&(FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT))){configurationFailure("A regular Grand Overhaul managed-copy marker is required for the host root.");goto done;}')
    return ai_loader, base._replace(world_settings, before, after, 1, "Food 0.6 managed native host")


def derive_activity_ai_inputs(game: Path) -> tuple[dict[str, bytes], dict]:
    """Keep faction activity, then bound demand lookups for omitted needs."""
    from .food_world_ai import derive_food06_ai, OUTPUT_SHA256
    values, proof = options.derive_activity_ai_inputs("food-world", game)
    guarded, guards = {}, {}
    for name, value in values.items():
        guarded[name], guards[name] = derive_food06_ai(name, value)
    if {name: _sha(value) for name, value in guarded.items()} != OUTPUT_SHA256:
        raise base.RuntimeBuildError("The combined Food 0.6 private AI outputs differ.")
    return guarded, {"food05_activity": proof, "food06_demand_guarded": True,
                     "food06_demand_guards": guards}


def _coexistence_proof(images: dict[str, bytes], header: bytes, plan: bytes, *,
                       city_statistics_guard=False) -> dict:
    """Every World write is disjoint from the Food 0.6 native changes."""
    from .world_options_visibility_hooks import HOOKS, RENDER_HOOKS, CONTROL_HOOKS, IMPORT_HOOKS
    from .world_options_visibility_calls import CALLS
    from .world_options_disasters import DISASTER_CALLS
    parsed = json.loads(plan)
    world = [(e.get("module", parsed.get("module")), e["rva"], len(bytes.fromhex(e["before"])))
             for e in parsed["edits"]]
    for blob in base.blob_metadata(header):
        world.extend((blob["module"], h["rva"], len(h["before"])) for h in blob["hooks"])
    world.extend((m, rva, len(before)) for m, prefix, rva, before, export in CALLS + DISASTER_CALLS)
    for module, hooks in (("AnnoWelt.dll", HOOKS), ("AnnoDisplay.dll", RENDER_HOOKS),
                          ("AnnoFrame.dll", CONTROL_HOOKS)):
        world.extend((module, row[0], 8) for row in hooks)
    world.extend((row[0], row[1], 8) for row in IMPORT_HOOKS)
    food = [("AnnoWelt.dll", HOUSE_VTABLE + g["slot"], 8) for g in GETTERS.values()]
    food.extend(("AnnoWelt.dll", rva, size) for rva, size in progression_edited_spans())
    if city_statistics_guard:
        food.extend(("AnnoWelt.dll", rva, size) for rva, size in city_statistics.edited_spans())
    food.extend(("View.dll", VIEW_HOUSE_VTABLE + slot, 8) for slot in VIEW_HOOKS)
    for module, start, size in food:
        if any(module == other and max(start, at) < min(start + size, at + length)
               for other, at, length in world):
            raise base.RuntimeBuildError("A World transaction write overlaps a Food 0.6 native hook.")
    pe = base.PE(images["AnnoWelt.dll"])
    for getter in GETTERS.values():
        if _sha(pe.read(getter["original"], getter["size"])) != getter["sha256"]:
            raise base.RuntimeBuildError("An original Food 0.6 supply delegate changed.")
    if PROMOTION["parent"] not in pe.function_table():
        raise base.RuntimeBuildError("The Food 0.6 promotion unwind parent is absent.")
    return dict(world_write_spans=len(world), food_original_image_spans=len(food),
                overlapping_write_spans=0, original_supply_delegates_unchanged=True,
                food06_promotion_unwind_parent_retained=True,
                actual_game_test_performed=False)


def derive_sources(files: dict[str, bytes], game: Path, *, asset_source=None, asset_root=None,
                   activity_inputs=None, city_statistics_guard=False) -> tuple[dict[str, bytes], dict]:
    """Derive and preflight only the new exact profile, without writing inputs."""
    from .world_options import PRIVATE, apply_options, replace
    from .world_options_visibility_hooks import (verify_visibility_preimages,
        verify_renderer_visibility_preimages, verify_control_visibility_preimages,
        verify_import_visibility_preimages)
    from .world_options_visibility_calls import verify_visibility_call_preimages, CALLS
    from .world_options_disasters import verify_disaster_preimages, DISASTER_CALLS
    from .world_options_rotation import verify_rotation_native_image
    from .world_island_catalogue import IslandCatalogueError, validate_island_shapes, template_resolver
    from .world_island_rotation import definition_dimensions, validate_rotation_metadata
    from .world_options_factions import PROFILE_INPUT_SHA256
    game, staged = checked_path(game), dict(files)
    asset_source = None if asset_source is None else checked_path(asset_source)
    asset_root = None if asset_root is None else checked_path(asset_root)
    expected = expected_native_hashes(city_statistics_guard=True) if city_statistics_guard else HOST_SHA256
    images = {name: checked_path(game / name).read_bytes() for name in expected}
    for name, pin in expected.items():
        if _sha(images[name]) != pin:
            raise base.RuntimeBuildError("The combined Food 0.6 host differs: " + name)
    plan = derive_engine_plan(images["AnnoWelt.dll"], staged[base.ENGINE_PLAN])
    staged[base.ENGINE_PLAN] = plan
    staged[base.ENGINE_HEADER] = derive_engine_header(staged[base.ENGINE_HEADER])
    staged[base.BLOBS] = base._replace(staged[base.BLOBS], base._c_digest(base.FOOD_SHA256["AnnoWelt.dll"]),
        base._c_digest(expected["AnnoWelt.dll"]), 2, "Food 0.6 Welt native blob identity")
    staged[base.AI_LOADER], staged[base.WORLD_SETTINGS] = _managed_host_sources(
        staged[base.AI_LOADER], staged[base.WORLD_SETTINGS])
    proof = base.verify_native_preimages(game, staged[base.BLOBS], plan, expected_hashes=expected)
    proof["food06_coexistence"] = _coexistence_proof(images, staged[base.BLOBS], plan,
                                                   city_statistics_guard=city_statistics_guard)
    proof["visibility_dispatch"] = verify_visibility_preimages(images["AnnoWelt.dll"], expected["AnnoWelt.dll"])
    proof["visibility_renderer_dispatch"] = verify_renderer_visibility_preimages(images["AnnoDisplay.dll"], expected["AnnoDisplay.dll"])
    proof["visibility_control_dispatch"] = verify_control_visibility_preimages(images["AnnoFrame.dll"], expected["AnnoFrame.dll"])
    proof["visibility_import_dispatch"] = verify_import_visibility_preimages(images, expected)
    proof["strict_visibility_calls"] = verify_visibility_call_preimages(images, expected)
    proof["disasters"] = verify_disaster_preimages(images, expected)
    proof["island_rotation_native"] = verify_rotation_native_image(images["AnnoWelt.dll"], expected["AnnoWelt.dll"])
    catalogue = staged[PRIVATE + "world_catalogue.h"]
    native = base.ROOT / "src/anno1503_overhaul/native/world_options"
    resolver = template_resolver(game if asset_source is None else asset_source,
        base.ROOT / ".local/baselines/world_settings/assets" if asset_root is None else asset_root)
    try:
        proof["island_shapes"] = validate_island_shapes(catalogue, (native / "island_shapes.h").read_bytes(), resolver)
        proof["island_rotation"] = validate_rotation_metadata(catalogue,
            (native / "island_rotation_plan.h").read_bytes(),
            (native / "island_rotation_definitions.h").read_bytes(), resolver,
            [definition_dimensions((game if asset_source is None else asset_source) / name)
             for name in ("Anlagen.dat", "Anlagen.addon")])
    except IslandCatalogueError as exc:
        raise base.RuntimeBuildError("Combined Food 0.6 island source/rotation metadata differs.") from exc
    result = apply_options(staged)
    result[PRIVATE + "menu_create.inc"] = replace(result[PRIVATE + "menu_create.inc"],
        b'label(d,"Food (tons)"', b'label(d,"Fish (tons)"',
        "Food 0.6 starting cargo names the actual staple good")
    ai, ai_proof = derive_activity_ai_inputs(game) if activity_inputs is None else activity_inputs
    from .food_world_ai import OUTPUT_SHA256
    if (set(ai) != set(OUTPUT_SHA256)
            or any(not isinstance(value, bytes) or _sha(value) != OUTPUT_SHA256[name]
                   for name, value in ai.items())):
        raise base.RuntimeBuildError("The combined private AI inventory differs.")
    for name, value in ai.items():
        result[base.AI_LOADER] = replace(result[base.AI_LOADER],
            PROFILE_INPUT_SHA256["food-world"][name].encode("ascii"), _sha(value).encode("ascii"),
            "combined Food 0.6 private AI fingerprint: " + name)
    proof["faction_activity_ai"] = ai_proof
    proof["faction_activity_ai_sha256"] = {name: _sha(value) for name, value in ai.items()}
    names = ("AnnoWelt.dll", "AnnoFrame.dll", "AnnoScene.dll", "AnnoGame.dll", "View.dll", "AnnoDisplay.dll")
    pins = ["/* Generated from this profile's independently verified images. */",
            "typedef struct WSVisibilityModulePin {const wchar_t*name;unsigned char sha256[32];} WSVisibilityModulePin;",
            "static const WSVisibilityModulePin wsVisibilityModulePins[]={"]
    pins.extend(' {L"%s",{%s}},' % (name, base._c_digest(expected[name]).decode("ascii")) for name in names)
    pins.append("};")
    result["developer/source/engine_resume/ai_loader/visibility_native_pins.h"] = ("\n".join(pins) + "\n").encode("ascii")
    proof["visibility_runtime_module_pins"] = {name: expected[name] for name in names}
    proof["profile"] = PROFILE
    proof["food06_new_world_required"] = True
    proof["world_generator_abi_changed"] = False
    return result, proof


def build_food_world_runtime(game, tools=None, *, output=None, publish=False,
                             asset_source=None, asset_root=None, city_statistics_guard=False):
    """Build a candidate; publishing additionally requires the reviewed pin."""
    if type(publish) is not bool or publish:
        raise base.RuntimeBuildError("Combined Food 0.6 runtime publication requires separate candidate review.")
    return options._build_options_runtime(PROFILE, game, tools, output=output,
        publish=False, _food06_profile=True,
        _food06_asset_source=asset_source, _food06_asset_root=asset_root,
        city_statistics_guard=city_statistics_guard)


def build_public_food_world_runtime(game, source_game, assets_root, compiler_path,
                                   activity_inputs, *, output, source_proof, city_statistics_guard=False):
    """Compile the reviewed combined host from explicit public-source inputs.

    The host, island assets and AI are freshly reconstructed by the public
    package recipe. There is no historical baseline or runtime-profile lookup.
    All native host and AI fingerprints are rechecked by derive_sources.
    """
    from .beta_inputs import verify_beta_source, derive_beta_assets
    from .food_household import _compiler
    from .food_world_ai import OUTPUT_SHA256
    from .filesystem import safe_child
    from .world_options import generator_id
    game, source, assets = map(checked_path, (Path(game), Path(source_game), Path(assets_root)))
    if game == source or game.is_relative_to(source) or source.is_relative_to(game):
        raise base.RuntimeBuildError('The public combined compiler host must be independent of the game.')
    compiler, unused = _compiler(compiler_path)
    if source_proof != verify_beta_source(source):
        raise base.RuntimeBuildError('The public combined source profile changed.')
    expected_assets, asset_proof = derive_beta_assets(source)
    expected_names = {name.removeprefix('assets/') for name in expected_assets}
    expected_dirs = {parent.as_posix() for name in expected_names for parent in Path(name).parents if str(parent) != '.'}
    actual_names = set()
    for item in assets.rglob('*'):
        checked_path(item)
        if item.is_file():
            actual_names.add(item.relative_to(assets).as_posix())
        elif not item.is_dir() or item.relative_to(assets).as_posix() not in expected_dirs:
            raise base.RuntimeBuildError('An unexpected public combined island input exists.')
    if actual_names != expected_names:
        raise base.RuntimeBuildError('The public combined island input inventory differs.')
    for name, value in expected_assets.items():
        if safe_child(assets, name.removeprefix('assets/'), exists=True).read_bytes() != value:
            raise base.RuntimeBuildError('A public combined island derivative changed.')
    ai, proof = activity_inputs
    if set(ai) != set(OUTPUT_SHA256) or {name: _sha(value) for name, value in ai.items()} != OUTPUT_SHA256:
        raise base.RuntimeBuildError('The public combined AI derivatives differ.')
    expected = expected_native_hashes(city_statistics_guard=True) if city_statistics_guard else HOST_SHA256
    if {item.name for item in game.iterdir()} != set(expected):
        raise base.RuntimeBuildError('The public combined compiler host inventory differs.')
    verified = dict(root=game, source_game=source, source_data_root=source,
        assets_root=assets, compiler_path=compiler,
        manifest=dict(profile=PROFILE, historical_private_inputs_used=False,
                      source_proof=source_proof, assets=asset_proof,
                      native_sha256=expected, private_ai_sha256=OUTPUT_SHA256))
    if generator_id() != options.PINNED_GENERATOR:
        raise base.RuntimeBuildError('The public combined generator changed after runtime review.')
    report = options._build_options_runtime(PROFILE, game, output=output,
        _food06_profile=True, _public_inputs=dict(profile=PROFILE, verified=verified,
                                                 activity_inputs=(ai, proof)),
        city_statistics_guard=city_statistics_guard)
    if not report['matches_reviewed_runtime']:
        raise base.RuntimeBuildError('The public combined build differs from its reviewed runtime.')
    return report
