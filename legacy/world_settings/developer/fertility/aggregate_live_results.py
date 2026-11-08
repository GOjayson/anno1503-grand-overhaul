"""Bind root-observed game runs to independent, read-only saved-state reports.

This aggregation does not operate Anno or establish UI events itself. The root
agent supplies the explicit observation/closure flags after conducting the game
runs. Default operation writes only an additive draft in the live directory;
--finalize requires --game-closed and updates the package's live-results index.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import sys

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[1]
GAME = PACKAGE.parent.parent
WORK = GAME / "WorldSettings_Work/fertility"
LIVE = HERE / "live"
RUNTIME = "6e0f27734272e88590fa00556af2ae47cd14ea502e7af36fd051b3ccda357829"
EXECUTED = "0158c58eb212e575078757b16f686a349427b6fc2e93a9e4800c8519698ebaa5"
MODE_NAMES = {"very": "Very fertile", "medium": "Medium fertility", "low": "Low fertility", "mixed": "Mixed"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((LIVE / name).read_bytes())


def capture(source_name, destination_name=None):
    source = WORK / source_name
    destination = LIVE / (destination_name or source_name)
    if destination.exists():
        assert destination.read_bytes() == source.read_bytes(), destination
    else:
        shutil.copyfile(source, destination)
    return destination


def diagnostics(name, pid, fresh):
    path = capture(name)
    data = json.loads(path.read_bytes())
    assert data["pid"] == pid
    assert data["runtime_sha256"] == RUNTIME and data["world_spec_sha256"] == EXECUTED
    assert data["hook_site_count"] == 9 and data["central_war_site_state"] == "guard-jump"
    assert all(data[k] == "" for k in ["factory_error", "hook_error", "ai_loader_error", "ai_profile_error"])
    assert data["ai_profile_status"] == (2 if fresh else 0)
    assert data["ai_profile_validated"] is fresh
    assert data["validated_ai_count"] == (1 if fresh else None)
    return data, path


def inspected(alias, diagnostic, fertility):
    docs = {kind: read(alias + "_" + kind + ".json")
            for kind in ["resources", "geometry", "fleet_observed", "policy"]}
    resource = docs["resources"]
    expected_hash = resource["save_sha256"]
    assert all(doc["passed"] and doc["save_sha256"] == expected_hash for doc in docs.values())
    assert sha(Path(resource["save_path"])) == expected_hash
    assert resource["selected"] == {"plant_fertility": fertility, "mineral_fertility": fertility}
    assert resource["island_count"] == 24 and resource["favorable_crop_union_on_supported_fertile_land"] == "0x1fff"
    for kind in ["geometry", "fleet_observed", "policy"]:
        doc = docs[kind]
        assert doc["runtime_sha256"] == RUNTIME and doc["executed_world_spec_sha256"] == EXECUTED
        assert doc["diagnostics"] == diagnostic
    return docs


def generation(alias, fertility, diagnostic_name, activation_name, pid):
    diag, diag_path = diagnostics(diagnostic_name, pid, True)
    capture(activation_name)
    docs = inspected(alias, diag, fertility)
    resources, geometry = docs["resources"], docs["geometry"]
    selected = dict(geometry["operator_selected_settings"])
    selected.update(docs["fleet_observed"]["selected"])
    selected.update(docs["policy"]["selected"])
    selected.update(plant_fertility=MODE_NAMES[fertility], mineral_fertility=MODE_NAMES[fertility])
    return dict(save_name=alias, save_path=resources["save_path"], save_sha256=resources["save_sha256"],
                save_bytes=resources["bytes"], pid=pid, process_creation_time=diag["process_creation_time"],
                settings=selected, settings_selected_inside_game_by_user=True,
                user_reported_world_loaded_and_saved=True, gameplay_rendered=True,
                ui_events_observed_or_reported_to_root_agent=True,
                loaded_geometry_resource_ownership_certificate_passed=True,
                fresh_generation_ordinary_and_special_controller_checks_passed=True,
                ai_profile_status=2, validated_ai_count=1,
                diagnostics_report=diag_path.relative_to(PACKAGE).as_posix(),
                diagnostic_errors_empty=True, native_hook_sites=9, central_war_guard_present=True,
                resource_report="developer/fertility/live/" + alias + "_resources.json",
                geometry_report="developer/fertility/live/" + alias + "_geometry.json",
                fleet_report="developer/fertility/live/" + alias + "_fleet_observed.json",
                ai_policy_report="developer/fertility/live/" + alias + "_policy.json",
                positive_saved_quantity_deposits=resources["positive_saved_quantity_deposits"],
                positive_saved_quantity_total=resources["positive_saved_quantity_total"],
                zero_quantity_native1661_records=resources["zero_quantity_native1661_records"],
                ore_free_island_count=resources["ore_free_island_count"],
                total_optional_favorable_crop_flags=resources["total_optional_favorable_crop_flags"],
                all_thirteen_supported_crop_flags_on_fertile_land=True,
                mineral_amount_equivalence_claimed=False,
                actual_harvesting_mining_accessibility_or_ui_crop_list_verified=False)


def markdown(result):
    rows = ["# Current 0.8.0-dev.1 actual-game evidence", "",
            "The current runtime is `" + RUNTIME + "`.",
            "These game runs executed specification `" + EXECUTED + "`.",
            "Later packaging metadata is not another game run. Exact diagnostics, save hashes",
            "and independent read-only reports are bound in `developer/fertility/live/LIVE_DEV5_RESULTS.json`.", "",
            "The user chose both fertility controls inside Anno, started each new world and saved",
            "through the native game. The root assistant observed rendered gameplay and checked",
            "the runtime diagnostics. All new runs below used Medium stock preset, Mixed islands,",
            "24 islands, spacing 0, 30,000, Single ship, one Easy AI, all eight cultures, Pirates",
            "and Venetians. Each generation had nine hooks, four empty errors and profile status2",
            "confirming one ordinary AI and the selected special controllers.", "",
            "| Save | Plant / mineral fertility | Optional favorable crop flags | Positive mineral deposits | Mineral-free islands |",
            "| --- | --- | ---: | ---: | ---: |"]
    for run in result["runs"]:
        rows.append("| {save_name} | {mode} / {mode} | {total_optional_favorable_crop_flags} | {positive_saved_quantity_total} | {ore_free_island_count} |".format(
            mode=run["settings"]["plant_fertility"], **run))
    rows += ["", "These are different random worlds, not an exact-seed replay. The separate automated",
             "32-seed matrix verifies the density hierarchy on identical geometry. Every saved world",
             "retained all thirteen supported favorable crop flags somewhere on fertile land and all",
             "five positive mineral goods. Saved zero-quantity1661 records are exhausted slots, not",
             "additional available iron deposits. World maps and native slot counts limit Very fertile.", "",
             "## Fresh-process Low reload", "",
             "The Low save fl1 was loaded after another normal launch and activation, then saved as fl2.",
             "The saved lower13 crop flags, per-island positive mineral good sets/counts and all114",
             "zero-quantity1661 positions matched exactly. Five positive deposits and22 mineral-free",
             "islands remained. Geometry/template identities, culture/faction ownership, ship identity,",
             "type, health, cannons/cargo and AI policy/native flags were retained. The ship continued",
             "an existing movement order, so unchanged positions and initial spawn coordinates are not claimed.",
             "Profile status0 on the saved-world load is expected and does not certify a new generation",
             "or mean zero opponents. Nine hooks and four empty errors were observed after the reload.", "",
             "## Scope and remaining checks", "",
             "The saved-state inspectors establish serialized availability; they do not observe UI events",
             "or prove current native disabled flags, mining/farm accessibility, harvesting yield or navigation.",
             "The fresh-generation runtime certificate and native persistence fixtures are separate checks.",
             "The Single ship had moved into a coastal island bounding rectangle: the legacy rectangle-only",
             "water proxy rejected that position. Retained ship state and bounded HEIGHT water-consistency",
             "samples were checked separately; the rejection remains recorded and is not called navigation proof.",
             "Optional favorable crop flags affect native growth conditions, with the original unfavorable",
             "growth fallback retained. They do not forbid harvesting or alter FRUCHTBAR terrain cells.",
             "Mineral quantities were not required to remain byte-identical across the reload.",
             "Automatic tests cover all four levels and their combinations. Actual autonomous AI war balance,",
             "extended positive-AI Food production, trade, combat and mine/farm usability remain unverified.",
             "Activate once in every fresh Anno process before starting a new world OR loading a saved one.", ""]
    automated = result["mode_coverage"]["automated_only"]
    rows.append("Levels without a current live generation test: " + (", ".join(automated) if automated else "none") + ".")
    rows.append("")
    return "\n".join(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--include-mixed", metavar="SAVE_ALIAS")
    ap.add_argument("--mixed-pid", type=int)
    ap.add_argument("--include-medium", metavar="SAVE_ALIAS")
    ap.add_argument("--medium-pid", type=int)
    ap.add_argument("--game-closed", action="store_true")
    ap.add_argument("--finalize", action="store_true")
    args = ap.parse_args()
    assert not args.finalize or args.game_closed, "Final aggregation requires the root-observed game closure"
    if args.finalize:
        sys.path.insert(0, str(PACKAGE))
        import world_mod
        world_mod.assert_game_closed()
    LIVE.mkdir(exist_ok=True)
    runs = [generation("fl1", "low", "diagnostics_low.json", "activation_low.log", 13556),
            generation("fv1", "very", "diagnostics_very.json", "activation_very.log", 23372)]
    if args.include_mixed:
        assert args.mixed_pid
        runs.append(generation(args.include_mixed, "mixed", "diagnostics_mixed.json", "activation_mixed.log", args.mixed_pid))
    if args.include_medium:
        assert args.medium_pid
        runs.append(generation(args.include_medium, "medium", "diagnostics_medium.json", "activation_medium.log", args.medium_pid))
    reload_diag, reload_path = diagnostics("diagnostics_low_reload.json", 25568, False)
    capture("activation_low_reload.log")
    reload_docs = inspected("fl2", reload_diag, "low")
    before = runs[0]
    after = reload_docs["resources"]
    comparison = read("fl1_fl2_retained_comparison.json")
    assert comparison["passed"] and comparison["separately_launched_process_verified"]
    assert comparison["before_save_sha256"] == before["save_sha256"]
    assert comparison["after_save_sha256"] == after["save_sha256"]
    assert before["pid"] != reload_diag["pid"] and before["process_creation_time"] != reload_diag["process_creation_time"]
    assert all(after["baseline_comparison"][key] for key in
               ["per_island_crop_flags_identical", "per_island_positive_goods_identical", "per_island_zero_quantity_positions_identical"])
    # These files capture the exact operator-side scripts used for reports.
    # Their work-directory-relative paths are preserved as audit text, not
    # presented as relocatable package entry points.
    capture("inspect_retained_actual_save.py", "operator_inspect_retained_actual_save.py.txt")
    capture("compare_low_reload.py", "operator_compare_low_reload.py.txt")
    tested_modes = [MODE_NAMES[k] for k in ["very", "medium", "low", "mixed"]
                    if MODE_NAMES[k] in {run["settings"]["plant_fertility"] for run in runs}]
    result = dict(scope="Root-observed/reported actual game starts, saves and fresh-process reload, with independent automated native-save checks kept separate.",
                  date="2026-11-07", runtime_sha256=RUNTIME, world_spec_sha256=EXECUTED,
                  source_exe_sha256=reload_diag["executable_sha256"], settings_abi=52,
                  report_status="FINAL" if args.finalize else "DRAFT_UNTIL_ROOT_CLOSES_GAME",
                  aggregation_source_sha256=sha(Path(__file__)), runs=runs,
                  fresh_process_reload_tested=True,
                  fresh_process_reload=dict(before_save="fl1", after_save="fl2",
                      before_save_sha256=before["save_sha256"], after_save_sha256=after["save_sha256"],
                      pid=reload_diag["pid"], process_creation_time=reload_diag["process_creation_time"],
                      gameplay_rendered=True, activated_before_loading=True,
                      diagnostics_report=reload_path.relative_to(PACKAGE).as_posix(),
                      diagnostics_empty=True, native_hook_sites=9, profile_status=0,
                      profile_scope="Unarmed saved-world load; no new generation profile certificate claimed.",
                      resource_report="developer/fertility/live/fl2_resources.json",
                      retained_state_comparison="developer/fertility/live/fl1_fl2_retained_comparison.json",
                      all24_saved_lower13_crop_masks_exact=True,
                      all24_positive_mineral_good_sets_and_counts_exact=True,
                      all114_zero_quantity1661_positions_exact=True,
                      positive_mineral_deposits=5, mineral_free_islands=22,
                      mineral_amount_equivalence_claimed=False,
                      extended_trade_combat_food_production_tested=False),
                  mode_coverage=dict(live_new_generation=tested_modes,
                      automated_only=[name for name in MODE_NAMES.values() if name not in tested_modes]),
                  different_live_density_worlds_are_exact_seed_replay=False,
                  current_native_disabled_flags_proven_by_offline_save=False,
                  actual_crop_resource_ui_list_or_harvest_mine_usability_tested=False,
                  complete_feature_verified=False, extended_trade_combat_food_production_tested=False,
                  game_closed_after_tests=args.game_closed,
                  activation_requirement="Activate once in every new Anno process before starting a new world OR loading a saved world.",
                  source_capture_scope="operator_*.py.txt are exact source captures from the work directory, not package entry points.")
    if (WORK / 'final_copy_restored.json').is_file():
        restored_path = capture('final_copy_restored.json')
        restored = json.loads(restored_path.read_bytes())
        assert restored['runtime_sha256'] == RUNTIME and restored['world_spec_sha256'] == EXECUTED
        assert restored['restored_food_state'] == 'combined-0.5.0' and restored['original_food_pending_edits'] == 0
        assert len(restored['native_baselines']) == 3 and len(restored['introduced_files_absent']) == 18
        capture('final_copy_restore.log')
        capture('final_copy_audit.py', 'operator_final_copy_audit.py.txt')
        capture('backup_before.json')
        capture('backup_after_live_checks.json')
        capture('initial_copy_install.log')
        capture('initial_copy_check.log')
        result['post_game_restoration_report'] = restored_path.relative_to(PACKAGE).as_posix()
        result['post_game_restoration_verified'] = True
        result['post_game_restoration_executed_world_spec_sha256'] = EXECUTED
    output = LIVE / "LIVE_DEV5_RESULTS.json"
    (LIVE / "LIVE_DEV5_NOTES.md").write_text(markdown(result), encoding="utf-8")
    result["evidence_sha256"] = {path.name: sha(path) for path in sorted(LIVE.iterdir())
                                 if path.is_file() and path != output}
    output.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    if args.finalize:
        aggregate = json.loads((PACKAGE / "LIVE_TEST_RESULTS.json").read_bytes())
        aggregate["fertility_dev5"] = result
        aggregate["complete_feature_verified"] = False
        (PACKAGE / "LIVE_TEST_RESULTS.json").write_text(json.dumps(aggregate, indent=2)+"\n", encoding="utf-8")
        old = (PACKAGE / "LIVE_TESTS.md").read_text(encoding="utf-8")
        marker = "<!-- DEV5_LIVE_AGGREGATE_END -->"
        if marker in old:
            old = old.split(marker, 1)[1].lstrip("\n")
        old = old.replace("# Current 0.7.0-dev.1 actual-game evidence", "# Historical 0.7.0-dev.1 actual-game evidence", 1)
        (PACKAGE / "LIVE_TESTS.md").write_text(markdown(result)+"\n"+marker+"\n\n"+old, encoding="utf-8")
    print(json.dumps(dict(report=str(output), sha256=sha(output), report_status=result["report_status"],
                         generated_worlds=[run["save_name"] for run in runs],
                         fresh_reload="fl1 -> fl2", game_closed=args.game_closed,
                         package_live_index_updated=args.finalize), indent=2))


if __name__ == "__main__":
    main()
