"""Peer source review and adopted-source-bound replay of lifetime fixtures.

This reuses the published boundary fixtures with separate outputs and verifies
that every tested candidate byte equals its adopted source. It runs no game.
"""
from pathlib import Path
import hashlib
import json
import sys

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]
SOURCE = WORK/"engine_resume/ai_food/attempt_lifetime"
ADOPTED = WORK/"engine_resume/ai_food/experiment_runtime"
sys.path.insert(0, str(SOURCE))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


mapping = {"world_ai.c.candidate": ADOPTED/"world_ai.c",
           "world_ai.h.candidate": ADOPTED/"world_ai.h",
           "world_factory.c.candidate": WORK/"world_factory.c",
           "attempt_bridge.py": ADOPTED/"attempt_bridge.py"}
fingerprints = {}
for candidate, adopted in mapping.items():
    require((SOURCE/candidate).read_bytes() == adopted.read_bytes(), "Adopted source differs: "+candidate)
    fingerprints[str(adopted.relative_to(WORK))] = digest(adopted)

for test, output in [("test_lifecycle.py", "lifecycle_results.json"),
                     ("test_factory_binding.py", "factory_binding_results.json"),
                     ("test_bridge.py", "bridge_results.json")]:
    text = (SOURCE/test).read_text()
    # The pre-adoption check must now bind the candidates to their adopted bytes
    # above. It cannot require the deliberately superseded b497 source hashes.
    guard = "for name,digest in manifest['compiled_sources_unchanged'].items():assert hashlib.sha256((WORK/name).read_bytes()).hexdigest()==digest"
    if test != "test_bridge.py":
        if text.count(guard) == 2:
            text = text.replace(guard, "# Adopted source equality and fingerprints checked by peer wrapper.")
        else:
            require(text.count(guard) == 0 and
                    "for name,digest in current.items():assert digest in [manifest['compiled_sources_unchanged'][name],manifest['candidate_sha256'][Path(name).name+'.candidate']]" in text and
                    "for name,digest in current.items():assert hashlib.sha256((WORK/name).read_bytes()).hexdigest()==digest" in text,
                    "Unexpected adopted-source guard shape")
        require(text.count("out=HERE/'_build'") == 1, "Unexpected fixture output path")
        text = text.replace("out=HERE/'_build'", "out=PEER_REVIEW/'attempt_replay'")
    text = text.replace("(HERE/'"+output+"')", "(PEER_REVIEW/'attempt_"+output+"')")
    exec(compile(text, str(SOURCE/test), "exec"), {"__file__": str(SOURCE/test), "__name__": "__main__", "PEER_REVIEW": HERE})

for relative, expected in fingerprints.items():
    require(digest(WORK/relative) == expected, "Source changed while replaying: "+relative)
results = {name: json.loads((HERE/("attempt_"+name)).read_text()) for name in
           ["lifecycle_results.json", "factory_binding_results.json", "bridge_results.json"]}
report = dict(scope=__doc__,adopted_source_sha256=fingerprints,
              replay_test_sha256={n: digest(SOURCE/n) for n in ["test_lifecycle.py", "test_factory_binding.py", "test_bridge.py"]},
              lifecycle_cases=len(results["lifecycle_results.json"]["cases"]),
              factory_cases=len(results["factory_binding_results.json"]["cases"]),
              bridge_cases=len(results["bridge_results.json"]["cases"]),
              normal_path_source_review={
                  "original_call_arguments_preserved": True,
                  "native_AL_failure_remains_failure": True,
                  "original_caller_57470_success_and_cleanup_test_retained": True,
                  "scene_world_identity_bound_before_factory_success": True,
                  "expected_profile_count_limited_to_matching_native_token": True,
                  "late_native_failure_clears_prior_profile_status": True,
                  "unarmed_start_does_not_inherit_generated_world_expectation": True,
                  "stale_completion_and_reentry_cannot_consume_current_attempt": True,
                  "generated_native_success_without_profile_check_rejected": True},
              limitations=["Boundary fixtures are explicit doubles; they do not create a native scene or execute gameplay.",
                           "An escaping native exception can bypass End and leave the entry guard active; no exception translation is added."],
              actual_game_runs=0)
(HERE/"attempt_review_results.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
