"""Read-only peer audit of frozen copied-island package and installed journal.

No install, restoration, process inspection or game execution is performed.
Only this private audit's JSON report is written.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
WORK = HERE.parents[2]
GAME = WORK.parent
PACKAGE = WORK/"anno1503_food_world_dev3"
COPY = WORK/"game_copy"
SPEC_SHA = "eeaf0c8eea8586a5f14791f38ad3558288d3ed7a797b86fb99f83c8295cc0ca4"
RUNTIME_SHA = "cffc701402849183ffcb690017f2995c77db8f8b14bc04f156c86341defd4dcc"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


spec_bytes = (PACKAGE/"world_patch.json").read_bytes()
require(sha(spec_bytes) == SPEC_SHA, "Frozen package specification changed")
spec = json.loads(spec_bytes)
module_spec = importlib.util.spec_from_file_location("peer_world_mod",PACKAGE/"world_mod.py")
mod = importlib.util.module_from_spec(module_spec)
sys.path.insert(0, str(PACKAGE))
module_spec.loader.exec_module(mod)
require((PACKAGE/"support/package_alias_assets.py").read_bytes() == (HERE/"package_alias_assets.py").read_bytes(), "Packaged data validator differs from reviewed helper")
require(sha((PACKAGE/"support/package_alias_assets.py").read_bytes()) == "c6755cb59dcea6af1f4be59258a5e5371687b0161205e9afcfead1b89fbd3078", "Validator fingerprint changed")
payloads = mod.payloads(spec)
require(len(payloads) == 24 and len(spec["data_payloads"]) == 15 and len(spec["introduced_files"]) == 18, "Package target counts differ")
native_names = set(payloads)-set(spec["data_payloads"])
require(len(native_names) == 9, "Native validation count differs")
for name in native_names:
    mod.require_amd64(payloads[name],name)
require(sha(payloads["native/AnnoWorldSettings.dll"]) == RUNTIME_SHA, "Packaged runtime changed")
require(spec["data_payloads"] == mod.alias_assets.data_payload_hashes(), "Data policy and spec differ")
require({n:p for n,p in spec["introduced_files"].items() if n.startswith("WorldSettingsIslands/")} == mod.alias_assets.introduced_files(), "Installed island target mapping differs")
catalogue = WORK/"engine_resume/ai_food/experiment_runtime/world_catalogue.h"
mod.alias_assets.validate_source_bundle(GAME,HERE/"alias_payload",catalogue.read_bytes())
build = json.loads((WORK/"runtime_dev3/build_result.json").read_bytes())
require(build["sha256"] == RUNTIME_SHA and build["abi_size"] == 32 and build["native_hooks"] == 8, "Compiled runtime metadata differs")
catalogue_key = next(n for n in build["source_sha256"] if n.replace("\\","/") == "engine_resume/ai_food/experiment_runtime/world_catalogue.h")
require(build["source_sha256"][catalogue_key] == mod.alias_assets.CATALOGUE_SHA256, "Compiled source metadata does not bind promoted catalogue")
for name,digest in build["source_sha256"].items():
    require(sha((WORK/name).read_bytes()) == digest, "Compiled source changed: "+name)
    require(sha((PACKAGE/"developer/source"/name).read_bytes()) == digest, "Packaged compiled source differs: "+name)
state, edits = mod.build_edits(COPY,spec,progress=lambda _:None)
require(state == mod.FINAL_STATE and not edits, "Installed copy is not an exact journal-backed no-op")
journal = mod.tx.read_manifest(COPY)
targets = set(spec["native_overlays"])|set(spec["introduced_files"])
require(journal["status"] == "installed" and len(journal["edits"]) == 21 and {e["name"] for e in journal["edits"]} == targets, "Installed journal targets differ")
introduced_entries = []
for entry in journal["edits"]:
    name = entry["name"]
    expected = payloads[spec["introduced_files"][name]] if name in spec["introduced_files"] else payloads[spec["native_overlays"][name]["output_payload"]]
    require((entry["after_size"],entry["after_sha256"]) == (len(expected),sha(expected)), "Installed journal payload differs: "+name)
    require((COPY/name).read_bytes() == expected, "Installed file differs: "+name)
    if name in spec["introduced_files"]:
        require(entry["existed"] is False and entry["before_size"] is None and entry["before_sha256"] is None,
                "Introduced file would restore over an existing original: "+name)
        introduced_entries.append(name)
    else:
        baseline = payloads[spec["native_overlays"][name]["baseline_payload"]]
        before = COPY/mod.tx.BACKUP/"before"/name
        require(before.read_bytes() == baseline and entry["before_sha256"] == sha(baseline), "Native whole-file restoration source differs: "+name)
source_catalogue = json.loads((WORK/"world_data/catalogue.json").read_bytes())
originals = {}
for record in source_catalogue["templates"]:
    name,digest = record["path"],record["sha256"]
    require(sha((GAME/name).read_bytes()) == digest, "Original source island changed: "+name)
    require(sha((COPY/name).read_bytes()) == digest, "Copied original island changed: "+name)
    originals[name] = digest
require(len(originals) == 443, "Original template inventory differs")
fixture = json.loads((PACKAGE/"installer_test_results.json").read_bytes())
require(fixture["world_spec_sha256"] == SPEC_SHA and fixture["count"] == len(fixture["checks"]) == 35, "Combined installer fixture is stale")
for name,digest in fixture["tested_source_sha256"].items():
    require(sha((PACKAGE/name).read_bytes()) == digest, "Installer source changed after fixtures: "+name)
tests = (PACKAGE/"developer/test_combined_installer.py").read_text()
transaction = (PACKAGE/"support/world_transactions.py").read_text()
required_tests = ["for index in range(len(overlays)+len(introduced)):", "assert len(edits)==21",
                  "for name in introduced:", "for name,data in installed.items():",
                  "assert sentinel.read_bytes()==b'KEEP' and island_sentinel.read_bytes()==b'KEEP-ISLAND-CONTENT'",
                  "assert backups(GAME)==original_backups"]
require(all(text in tests for text in required_tests), "Restoration fixture coverage changed")
require("target.unlink()" in transaction and "path.rmdir()" in transaction and
        "# Verify all originals and all current files before the first target write." in transaction,
        "New-data restoration/preflight mechanism changed")
require("'compiler_cache'" in (PACKAGE/"developer/build_world_payload.py").read_text(), "Compiler cache exclusion missing")
require((PACKAGE/"world_patch.json").read_bytes() == spec_bytes, "Package changed during read-only audit")
report = dict(scope=__doc__,package_spec_sha256=SPEC_SHA,runtime_sha256=RUNTIME_SHA,
              validator_sha256=sha((PACKAGE/"support/package_alias_assets.py").read_bytes()),
              compiled_catalogue_sha256=mod.alias_assets.CATALOGUE_SHA256,
              native_amd64_payloads=9,strict_scp_payloads=15,introduced_targets=18,
              exact_installed_journal_targets=21,introduced_entries_restore_to_absent=introduced_entries,
              whole_native_original_restoration_backups=3,compiled_source_fingerprints=len(build["source_sha256"]),
              unchanged_original_source_and_copy_templates=443,
              original_inventory_sha256=sha(json.dumps(originals,sort_keys=True).encode()),
              reviewed_combined_installer_fixture_groups=35,
              restoration_source_review={"preflight_all_targets_before_restoring":True,
                                         "remove_only_exact_created_data_files":True,
                                         "preserve_foreign_directory_content":True,
                                         "every_publication_failure_position_tested":True,
                                         "all_installed_targets_tamper_tested":True,
                                         "prior_backups_preservation_asserted_in_bound_fixture":True},
              blocking_findings=[],actual_game_runs=0,process_operations=0,install_or_restore_operations=0)
(HERE/"package_alias_review.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
