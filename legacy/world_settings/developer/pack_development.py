"""Create a SHA-256 inventory and ZIP of this UNFINISHED development package."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import struct
import sys
import zipfile

PACKAGE = Path(__file__).resolve().parents[1]
GAME = PACKAGE.parent.parent
VERSION = "0.10.0-dev.1"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(root):
    return [p for p in sorted(root.rglob("*")) if p.is_file() and
            not any(x in p.parts for x in ["__pycache__", "tmp", "_build", "compiler_cache", ".zig-cache",
                                          "global-cache", "local-cache", "zig_global_cache", "zig_local_cache"])
            and p.suffix.lower() not in {".pyc", ".obj", ".o", ".a", ".lib", ".pdb"}
            and p.name != "activation_session.json"]


def main():
    spec = json.loads((PACKAGE / "world_patch.json").read_bytes())
    tested = json.loads((PACKAGE / "installer_test_results.json").read_bytes())
    if (spec.get("version") != VERSION or spec.get("status") != "UNFINISHED"
            or tested.get("version") != spec["version"] or not tested.get("count")
            or tested.get("world_spec_sha256") != sha(PACKAGE / "world_patch.json")
            or tested.get("source_baselines_sha256") != sha(PACKAGE / "SOURCE_BASELINES.json")):
        raise ValueError("Final dev7 snapshot and matching combined installer tests are required before packaging")
    readiness=json.loads((PACKAGE/'BUILD_PENDING.json').read_bytes())
    if (not readiness.get('payload_ready') or readiness.get('installer_tests_pending') is not False
            or readiness.get('settings_abi_size')!=56 or readiness.get('native_hooks')!=9
            or readiness.get('world_spec_sha256')!=sha(PACKAGE/'world_patch.json')
            or readiness.get('source_baselines_sha256')!=sha(PACKAGE/'SOURCE_BASELINES.json')
            or readiness.get('final_shared_copy_acceptance_pending',False)):
        raise ValueError('Final fertility payload, installer and shared-copy acceptance state is not ready')
    for name, digest in tested.get("tested_source_sha256", {}).items():
        if sha(PACKAGE/name) != digest:
            raise ValueError("Installer source changed after testing: " + name)
    if not tested.get("tested_source_sha256"):
        raise ValueError("Installer tests did not fingerprint their sources")
    for name, digest in spec["payloads"].items():
        if sha(PACKAGE/name) != digest:
            raise ValueError("Payload changed after testing: " + name)
    for name,digest in spec.get("game_evidence_sha256",{}).items():
        if sha(PACKAGE/name)!=digest:
            raise ValueError("Game evidence changed after testing: " + name)
    baselines = json.loads((PACKAGE / "SOURCE_BASELINES.json").read_bytes())
    runtime_digest = spec["payloads"].get("native/AnnoWorldSettings.dll")
    build = baselines.get("runtime_build_metadata", {})
    if (baselines.get("version") != VERSION or baselines.get("status") != "UNFINISHED"
            or build.get("abi_size") != 56 or build.get("sha256") != runtime_digest
            or baselines.get("runtime_sha256") != runtime_digest):
        raise ValueError("Runtime, source snapshot and 56-byte settings ABI must describe the same dev7 build")
    policy_root = PACKAGE / "developer/start_options/ai"
    review_digest = sha(policy_root / "AI_POLICY_REVIEW.json")
    if (baselines.get("ai_policy_review_sha256") != review_digest
            or spec.get("ai_policy_review_sha256") != review_digest):
        raise ValueError("Reviewed AI policy evidence changed after the runtime snapshot")
    for name, digest in baselines.get("ai_policy_evidence_sha256", {}).items():
        if Path(name).name != name or sha(policy_root/name) != digest:
            raise ValueError("Reviewed AI policy source/evidence changed: " + name)
    if not baselines.get("ai_policy_evidence_sha256"):
        raise ValueError("Reviewed AI policy source/evidence fingerprints are required")
    sys.path.insert(0,str(PACKAGE/'developer/fertility'))
    from review_inputs import collect,check_prior_archives
    fertility_path=PACKAGE/'developer/fertility/FERTILITY_REVIEW.json'
    fertility=json.loads(fertility_path.read_bytes())
    expected_fertility=collect(PACKAGE,PACKAGE/'developer/source',build)
    if fertility!=expected_fertility:
        raise ValueError('Reviewed fertility evidence differs from the compiled runtime snapshot')
    if (spec.get('fertility_review_sha256')!=sha(fertility_path)
            or baselines.get('fertility_review_sha256')!=sha(fertility_path)
            or spec.get('fertility_evidence_sha256')!=fertility['evidence_sha256']
            or baselines.get('fertility_evidence_sha256')!=fertility['evidence_sha256']):
        raise ValueError('Fertility proof bindings changed after the installer snapshot')
    sys.path.insert(0,str(PACKAGE/'developer/layout_preview'))
    from preview_review import collect_preview
    preview_path=PACKAGE/'developer/layout_preview/PREVIEW_REVIEW.json'
    preview=json.loads(preview_path.read_bytes())
    if preview!=collect_preview(PACKAGE,PACKAGE/'developer/source',build):
        raise ValueError('Map-preview proof differs from the exact compiled runtime')
    if (spec.get('preview_review_sha256')!=sha(preview_path)
            or baselines.get('preview_review_sha256')!=sha(preview_path)
            or readiness.get('preview_review_sha256')!=sha(preview_path)
            or spec.get('preview_evidence_sha256')!=preview['evidence_sha256']
            or baselines.get('preview_evidence_sha256')!=preview['evidence_sha256']):
        raise ValueError('Map-preview proof bindings changed after the installer snapshot')
    sys.path.insert(0,str(PACKAGE/'developer/world_sizes'))
    from world_sizes_review import collect_world_sizes
    sizes_path=PACKAGE/'developer/world_sizes/WORLD_SIZES_REVIEW.json'
    sizes=json.loads(sizes_path.read_bytes())
    if sizes!=collect_world_sizes(PACKAGE,PACKAGE/'developer/source',build):
        raise ValueError('World-size and Venetian proofs differ from the exact compiled runtime')
    if (spec.get('world_sizes_review_sha256')!=sha(sizes_path)
            or baselines.get('world_sizes_review_sha256')!=sha(sizes_path)
            or readiness.get('world_sizes_review_sha256')!=sha(sizes_path)
            or spec.get('world_sizes_evidence_sha256')!=sizes['evidence_sha256']
            or baselines.get('world_sizes_evidence_sha256')!=sizes['evidence_sha256']):
        raise ValueError('World-size or Venetian proof bindings changed after testing')
    frozen=check_prior_archives(PACKAGE.parent)
    if spec.get('frozen_prior_release_sha256')!=frozen or baselines.get('frozen_prior_release_sha256')!=frozen:
        raise ValueError('Prior release preservation bindings changed')
    expected_dlls={name for name in spec['payloads'] if name.endswith('.dll')}
    expected_dlls.add('developer/source/runtime_dev3/AnnoWorldSettings.dll')
    actual_dlls={p.relative_to(PACKAGE).as_posix() for p in files(PACKAGE) if p.suffix.lower()=='.dll'}
    if actual_dlls!=expected_dlls or len(expected_dlls)!=10:
        raise ValueError('Unexpected native/test DLL in the development package')
    for name in actual_dlls:
        data=(PACKAGE/name).read_bytes();pe=struct.unpack_from('<I',data,60)[0]
        if data[pe:pe+4]!=b'PE\0\0' or struct.unpack_from('<H',data,pe+4)[0]!=0x8664 or struct.unpack_from('<H',data,pe+24)[0]!=0x20b:
            raise ValueError('Non-AMD64 payload in development package: '+name)
    if sha(PACKAGE/'developer/source/runtime_dev3/AnnoWorldSettings.dll')!=runtime_digest:
        raise ValueError('Snapshotted verification DLL differs from the native runtime')
    if spec.get("actual_game_run") or spec.get("packaged_runtime_gameplay_verified"):
        live = spec.get("runtime_gameplay_evidence") or {}
        if live.get("runtime_sha256") != runtime_digest or not live.get("game_run_names"):
            raise ValueError("Historical game evidence cannot certify a changed runtime")
    # Never replace an existing release, including one created by an earlier
    # invocation. Check before creating/replacing any pending archive.
    output = PACKAGE.with_suffix(".zip")
    staged = output.with_suffix(".zip.pending")
    if output.exists() or staged.exists():
        raise ValueError("Preserving an existing development archive; choose a new output/version")
    for name, item in baselines["files"].items():
        values = {name+"/"+relative:digest for relative,digest in item.items()} if isinstance(item,dict) else {name:item}
        for relative,digest in values.items():
            if sha(PACKAGE / "developer/source" / relative) != digest:
                raise ValueError("Snapshotted source/evidence changed: " + relative)
    original = GAME / "anno1503_food_mod"
    shutil.copyfile(original / "food_mod.py", PACKAGE / "developer/food_mod_original_0_5.py")
    matches = {}
    exceptions = {"food_mod.py":"Copied food preflight supports in-memory native baseline override; direct old installer entrypoint disabled",
                  "RUN.cmd":"Routes only to copy-only combined installer"}
    for path in files(original):
        name = path.relative_to(original).as_posix()
        if name in exceptions:
            continue
        mapped = {"README.txt":"FOOD_0_5_README.txt", "VALIDATION.txt":"FOOD_0_5_VALIDATION.txt"}.get(name, name)
        target = PACKAGE / mapped
        if not target.is_file() or sha(path) != sha(target):
            raise ValueError("Food package copy differs unexpectedly: " + name)
        matches[name] = sha(path)
    preservation_report = "developer/start_options/preservation.json"
    if not (PACKAGE/preservation_report).is_file():
        preservation_report = "installer_audit/final_preservation_check.json"
    preservation = dict(status="UNFINISHED", preserved_original_file_count=len(matches),
                        exact_copied_source_files=matches, intentional_copy_only_changes=exceptions,
                        original_food_installer_sha256=sha(original / "food_mod.py"),
                        original_installation_read_only_check=dict(
                            file=preservation_report,
                            sha256=sha(PACKAGE / preservation_report),
                            result=json.loads((PACKAGE / preservation_report).read_bytes())))
    (PACKAGE / "FOOD_PRESERVATION.json").write_text(json.dumps(preservation, indent=2) + "\n", encoding="utf-8")
    inventory = {p.relative_to(PACKAGE).as_posix():sha(p) for p in files(PACKAGE)
                 if p.name != "PACKAGE_SHA256.json"}
    (PACKAGE / "PACKAGE_SHA256.json").write_text(json.dumps(dict(status="UNFINISHED", version=spec["version"], files=inventory), indent=2) + "\n", encoding="utf-8")
    with zipfile.ZipFile(staged, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in files(PACKAGE):
            archive.write(path, PACKAGE.name + "/" + path.relative_to(PACKAGE).as_posix())
    with zipfile.ZipFile(staged) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP integrity verification failed")
    if output.exists():
        raise ValueError("Preserving an existing development archive; choose a new version before packaging again")
    os.replace(staged, output)
    print(json.dumps(dict(status="UNFINISHED", files=len(inventory)+1,
                         preserved_food_files=len(matches), zip=str(output), zip_sha256=sha(output)), indent=2))


if __name__ == "__main__":
    main()
