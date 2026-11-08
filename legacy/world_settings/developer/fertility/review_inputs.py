"""Validate the reviewed fertility inputs against the exact compiled runtime."""
from pathlib import Path
import hashlib
import json

HELPERS = {
    "plant_fertility.inc": "63dca709b9886bd136692596a087b0814dd570cfdf9aea5ffef43d82c3f24f40",
    "mineral_fertility.inc": "8bdc8373573682e81c5ffb83dfc1beaa7aa285b0656954598ec08feafcb4c20e",
    "mineral_persistence.inc": "e15d64b98a15b82e6350c7300c287744626c20949cc10d659710d29d89cca854",
}
FROZEN_ARCHIVES = {
    "anno1503_food_world_dev7.zip": "8e7fbc2571c6f8f8c7d4db37b64dde440afd2a9c88264ee519bd2e556c3614c3",
    "anno1503_food_world_dev6.zip": "3860c6784a266fcf0af0a7280844b00bc6905d1b759253ee75ee4b0427650828",
    "anno1503_food_world_dev3.zip": "3698c79a50813599d9da2a808e605058f8d435d44a0e2d69416ac73fe1233d6a",
    "anno1503_food_world_dev3_pathfix1.zip": "e3e5913a8503bff8405f46c984c01af501333a4411c3890e68be7c43537de851",
    "anno1503_food_world_dev3_cityfix1.zip": "b7d101368a12297d2bc1106f556b8ff418497039cbdafa84c4f35af660da9797",
    "anno1503_food_world_dev4.zip": "67846e524099e6307d464ac7bd5ac1493f814e58cadeb9a85edf3764d5e58d10",
    "anno1503_food_world_dev5.zip": "11b155795e159ae6d335dfadbbe5f58737af0ca89f458b92ef57f0db16085604",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def collect(package, source, build):
    """Return deterministic proof bindings; never write or execute a test/game."""
    package, source = Path(package), Path(source)
    runtime = source / "runtime_dev3/AnnoWorldSettings.dll"
    runtime_hash = sha(runtime)
    require(build.get("sha256") == runtime_hash and build.get("abi_size") == 56,
            "Fertility review requires the exact ABI56 runtime")
    compiled = {name.replace("\\", "/"): value for name, value in build["source_sha256"].items()}
    evidence, helpers, reviews = {}, {}, {}

    def bind(name, expected=None):
        path = package / name
        path.resolve(strict=True).relative_to(package.resolve())
        actual = sha(path)
        require(expected is None or actual == expected, "Fertility evidence changed: " + name)
        evidence[name] = actual
        return json.loads(path.read_bytes()) if path.suffix == ".json" else None

    for name, expected in HELPERS.items():
        relative = "engine_resume/ai_food/experiment_runtime/" + name
        require(sha(source / relative) == expected and compiled.get(relative) == expected,
                "Reviewed fertility helper differs from compiled input: " + name)
        helpers["developer/source/" + relative] = expected

    for kind, manifest in [("plant", "PLANT_FERTILITY_REVIEW.json"),
                           ("mineral", "MINERAL_FERTILITY_REVIEW.json")]:
        directory = "developer/fertility/" + kind + "/"
        review = bind(directory + manifest)
        require(review.get("game_executed") is False and review.get("evidence_sha256"),
                "Fertility native review must retain its automated-only scope")
        for name, expected in review["evidence_sha256"].items():
            require(Path(name).name == name and "\\" not in name,
                    "Fertility review contains a nonlocal evidence path")
            bind(directory + name, expected)
        if kind == "plant":
            require(review.get("compiled_helper_sha256") == HELPERS["plant_fertility.inc"]
                    and review.get("settings_abi") == 52
                    and review.get("native_scene_application_cases", 0) >= 228
                    and review.get("absolute_harvest_prohibition") is False,
                    "Plant review does not describe the reviewed native availability policy")
        else:
            require(review.get("implementation_sha256") == {name: HELPERS[name] for name in
                    ["mineral_fertility.inc", "mineral_persistence.inc"]}
                    and review.get("passed") is True
                    and review.get("native_roundtrip_cases", 0) >= 26
                    and review.get("persistence_compiled_native_cases", 0) >= 21,
                    "Mineral review does not describe the reviewed native persistence policy")
        reviews[kind] = dict(manifest=directory + manifest,
                             sha256=evidence[directory + manifest],
                             native_tests_are_gameplay=False)

    policy = bind("developer/fertility/real_runtime_policy_results.json")
    bind("developer/fertility/verify_policy.py", policy.get("verifier_sha256"))
    require(policy.get("runtime_sha256") == runtime_hash and policy.get("abi_size") == 56
            and policy.get("passed") is True and policy.get("game_executed") is False
            and policy.get("all_essential_world_resources_preserved") is True
            and policy.get("geo_and_plant_mineral_independence") is True
            and policy.get("seed_count", 0) >= 4,
            "Real-runtime fertility policy checks are absent, stale or incomplete")
    require(policy.get("compiled_build_metadata_sha256") == sha(source / "runtime_dev3/build_result.json"),
            "Fertility policy report belongs to a different compiled build record")
    generic = bind("developer/source/runtime_dev3/runtime_verification.json")
    require(generic.get("runtime_sha256") == runtime_hash and generic.get("abi_size") == 56
            and generic.get("game_executed") is False,
            "Generic runtime report belongs to an older runtime")
    bind("developer/source/runtime_dev3/verify_runtime.py")
    production = bind("developer/start_options/economy/production_stage_results.json")
    require(production.get("runtime_sha256") == runtime_hash and production.get("settings_abi") == 56
            and production.get("actual_game_runs") == 0,
            "Production scene tests belong to an older runtime")
    bind("developer/start_options/economy/test_production_stage.py")
    bind("developer/start_options/economy/production_stage_fixtures.json")
    certificate = bind("developer/source/world_certificate/certificate_results.json")
    require(certificate.get("passed", 0) >= 66 and certificate.get("game_executed") is False
            and certificate.get("exact_crop_availability_checked") is True
            and certificate.get("exact_active_mineral_good_set_checked") is True,
            "Exact availability certificate fixture checks are absent")
    for name, expected in certificate["source_sha256"].items():
        require(Path(name).name == name, "Certificate fixture has a nonlocal source path")
        bind("developer/source/world_certificate/" + name, expected)
    bind("developer/fertility/review_inputs.py")
    return dict(scope="Automated reviewed fertility implementation and current-runtime evidence; no actual game run is claimed by this review.",
                settings_abi=56, runtime_sha256=runtime_hash, compiled_helpers_sha256=helpers,
                reviews=reviews, evidence_sha256=evidence,
                policy_seed_count=policy["seed_count"],
                policy_fertility_matrix_plans=policy["fertility_matrix_plan_count"],
                policy_old_option_independence_plans=policy["old_starting_option_independence_plans"],
                loaded_certificate_cases=certificate["passed"],
                game_executed=False, passed=True)


def check_prior_archives(work):
    work = Path(work)
    for name, expected in FROZEN_ARCHIVES.items():
        require(sha(work / name) == expected, "A frozen prior release archive changed: " + name)
    return dict(FROZEN_ARCHIVES)
