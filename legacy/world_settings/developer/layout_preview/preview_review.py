"""Bind balanced placement, native coast masks and exact preview staging proofs."""
from pathlib import Path, PurePosixPath
import hashlib
import json

PRIVATE = "engine_resume/ai_food/experiment_runtime/"
NEW_COMPILED_INPUTS = ["balanced_layout.inc", "selection_policy.inc", "world_size.inc", "preview_state.inc", "world_menu_preview.inc", "world_preview_coasts.h"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def collect_preview(package, source, build):
    """Return deterministic bindings only; no tests, game access or writes."""
    package, source = Path(package).resolve(), Path(source).resolve()
    runtime_hash = sha(source / "runtime_dev3/AnnoWorldSettings.dll")
    require(build.get("sha256") == runtime_hash and build.get("abi_size") == 56 and build.get("native_hooks") == 9,
            "Map preview requires the exact rebuilt ABI56/nine-hook runtime")
    compiled = {name.replace("\\", "/"): value for name, value in build["source_sha256"].items()}
    evidence, inputs = {}, {}

    def bind(name, expected=None):
        relative = PurePosixPath(name)
        require(not relative.is_absolute() and ".." not in relative.parts and "\\" not in name,
                "Unsafe map-preview evidence path")
        path = package.joinpath(*relative.parts).resolve(strict=True)
        require(path.is_relative_to(package), "Map-preview evidence is outside this package")
        actual = sha(path)
        require(expected is None or actual == expected, "Map-preview evidence changed: " + name)
        evidence[name] = actual
        return json.loads(path.read_bytes()) if path.suffix == ".json" else None

    for name in NEW_COMPILED_INPUTS:
        relative = PRIVATE + name
        actual = sha(source / relative)
        require(compiled.get(relative) == actual, "Map-preview source differs from the compiled runtime: " + name)
        inputs["developer/source/" + relative] = actual
    coast = bind("developer/layout_preview/coasts/coastline_manifest.json")
    bind("developer/layout_preview/coasts/generate_coasts.py", coast.get("generator_sha256"))
    require(coast.get("template_count") == 444 and coast.get("resolution") == 64
            and coast.get("bytes_per_template") == 512 and coast.get("all_template_hashes_verified") is True
            and coast.get("generated_header_sha256") == inputs["developer/source/" + PRIVATE + "world_preview_coasts.h"]
            and coast.get("catalogue_sha256") == sha(source / (PRIVATE + "world_catalogue.h"))
            and coast.get("actual_game_run") is False and coast.get("original_game_or_alias_assets_modified") is False,
            "Coast masks are absent or differ from the compiled catalogue")
    require(len(coast.get("templates", [])) == 444 and [row["index"] for row in coast["templates"]] == list(range(444)),
            "Coast proof must cover every ordered catalogue template")
    layout_directory = "developer/world_sizes/layout/"
    layout = bind(layout_directory + "LAYOUT_REVIEW.json")
    require(layout.get("passed") is True and layout.get("game_executed") is False
            and layout.get("helper_sha256") == inputs["developer/source/" + PRIVATE + "balanced_layout.inc"]
            and layout.get("evidence_sha256"), "Reviewed balanced-placement proof is absent")
    for name, expected in layout["evidence_sha256"].items():
        relative = layout_directory + name if Path(name).name == name else name
        bind(relative, expected)
    layout_results = bind(layout_directory + "layout_results.json")
    require(layout_results.get("passed") is True and layout_results.get("game_executed") is False
            and layout_results.get("input_sha256", {}).get("developer/source/" + PRIVATE + "balanced_layout.inc") == layout["helper_sha256"]
            and layout_results.get("supported_world_sizes") == [256,512,1024,2048]
            and layout_results.get("unsupported_4096_rejected") is True
            and layout_results.get("template_count") == 444 and layout_results.get("settings_abi_bytes") == 56
            and layout_results.get("native_fixture_cases", 0) >= 100
            and layout_results.get("exact_repeat_cases", 0) == layout_results.get("native_fixture_cases"),
            "Balanced-placement native fixture results are incomplete")
    runtime = bind("developer/layout_preview/preview_runtime_results.json")
    bind("developer/layout_preview/test_preview_runtime.py", runtime.get("verifier_sha256"))
    bind("activation/preview_snapshot.py", runtime.get("snapshot_decoder_sha256"))
    require(runtime.get("passed") is True and runtime.get("actual_game_run") is False
            and runtime.get("runtime_sha256") == runtime_hash and runtime.get("settings_abi") == 56
            and runtime.get("plan_island_size") == 40 and runtime.get("snapshot_size") == 5192
            and runtime.get("build_result_sha256") == sha(source / "runtime_dev3/build_result.json")
            and runtime.get("seed_count", 0) >= 8 and runtime.get("staged_scene_count", 0) >= 2
            and runtime.get("cached_rows_equal_staged_links") is True and runtime.get("no_stage_replan") is True
            and runtime.get("no_stage_replan_source_checked") is True
            and runtime.get("staging_backend_source_sha256") == compiled.get(PRIVATE + "world_backend.c")
            and runtime.get("stale_settings_seed_rows_rejected_before_publication") is True
            and runtime.get("pending_plan_immutable") is True and runtime.get("cancelled_preview_cannot_start") is True
            and runtime.get("temporary_scenes_cleaned") is True and runtime.get("shared_game_copy_modified") is False
            and runtime.get("ui_or_gameplay_verified") is False
            and len(runtime.get("snapshot_decoder_rejected_cases", [])) >= 15,
            "Exact cached-preview runtime tests are stale, incomplete or overclaim gameplay")
    require(runtime.get("compiled_source_sha256") == build["source_sha256"],
            "Preview staging test compiled-source provenance differs")
    fixture = bind("developer/layout_preview/asset_fixture_results.json")
    bind("developer/layout_preview/run_stage_checks.py", fixture.get("runner_sha256"))
    require(fixture.get("passed") is True and fixture.get("runtime_sha256") == runtime_hash
            and fixture.get("copied_actual_catalogue_assets") == 444
            and fixture.get("production_checks_run") is True
            and fixture.get("generated_scene_files_cleaned") is True
            and fixture.get("fixture_inputs_unchanged") is True and fixture.get("original_assets_unchanged") is True
            and fixture.get("fixture_removed_after_check") is True
            and fixture.get("shared_game_copy_modified") is False and fixture.get("game_executed") is False,
            "Actual-asset isolated staging fixture is absent or incomplete")
    bind("developer/layout_preview/preview_review.py")
    return dict(scope="Automated balanced-placement native fixture, exact native coast-mask inputs and compiled preview-to-stage lifecycle. Actual menu interaction and game loading require separate live evidence.",
                runtime_sha256=runtime_hash, settings_abi=56, snapshot_size=5192,
                compiled_inputs_sha256=inputs, coastline_templates=444,
                layout_native_fixture_cases=layout_results["native_fixture_cases"],
                preview_seed_count=runtime["seed_count"], staged_exact_preview_scenes=runtime["staged_scene_count"],
                snapshot_decoder_rejected_cases=len(runtime["snapshot_decoder_rejected_cases"]),
                evidence_sha256=evidence, game_executed=False, ui_or_gameplay_verified=False, passed=True)
