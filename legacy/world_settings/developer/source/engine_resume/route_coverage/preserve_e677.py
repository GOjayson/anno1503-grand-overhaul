"""Preserve the exact tested package and its installed copy journal before restore."""
from pathlib import Path
import hashlib
import json
import shutil

WORK = Path(__file__).resolve().parents[2]
PACKAGE = WORK / "anno1503_food_world_dev3"
RUNTIME_SHA = "e677b4f7b6dbcf943e70db16828e38f8320d7765b7eb0a9dca0781a4f9772acf"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_exact(source, target):
    if target.exists():
        raise ValueError("Preservation target already exists: " + str(target))
    shutil.copytree(source, target)
    inventory = {}
    for original in sorted(source.rglob("*")):
        if original.is_file():
            name = original.relative_to(source).as_posix()
            value = sha(original)
            if sha(target / name) != value:
                raise ValueError("Preservation mismatch: " + name)
            inventory[name] = value
    return inventory


def main():
    if sha(PACKAGE / "native/AnnoWorldSettings.dll") != RUNTIME_SHA:
        raise ValueError("Expected actually tested e677 package")
    base = WORK / "package_history/e677b4f7"
    base.mkdir(parents=True, exist_ok=False)
    package_files = copy_exact(PACKAGE, base / "package")
    journal_files = copy_exact(WORK / "game_copy/WorldFoodMod_Backup_0_6_Dev3", base / "installed_copy_backup")
    compiled = json.loads((PACKAGE / "SOURCE_BASELINES.json").read_bytes())["runtime_build_metadata"]
    for name, digest in compiled["source_sha256"].items():
        if sha(PACKAGE / "developer/source" / name) != digest:
            raise ValueError("Frozen runtime source mismatch: " + name)
    history = WORK / "runtime_dev3/history/e677b4f7"
    history.mkdir(parents=True, exist_ok=False)
    preserved = {}
    for name in ["SOURCE_BASELINES.json", "world_patch.json", "activation_session.json", "COPY_INSTALL_RESULTS.json",
                 "installer_test_results.json", "LIVE_TESTS.md", "LIVE_TEST_RESULTS.json"]:
        source = PACKAGE / name
        if source.is_file():
            shutil.copyfile(source, history / name)
            preserved[name] = sha(source)
    for name in ["AnnoWorldSettings.dll", "build_result.json"]:
        shutil.copyfile(WORK / "runtime_dev3" / name, history / name)
        preserved[name] = sha(history / name)
    copy_exact(PACKAGE / "native", history / "native")
    copy_exact(PACKAGE / "assets/WorldSettingsIslands", history / "WorldSettingsIslands")
    report = dict(scope="Exact tested e677 package, native/data/build/session and pre-restoration installed-copy journal preservation; no game or copy changes.",
                  runtime_sha256=RUNTIME_SHA, package_root=str(base / "package"),
                  package_files=len(package_files), files=package_files,
                  installed_copy_backup_files=journal_files, runtime_history_files=preserved,
                  compiled_source_fingerprints_verified=len(compiled["source_sha256"]))
    (base / "preservation_manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    summary = {k: v for k, v in report.items() if k not in {"files", "installed_copy_backup_files", "runtime_history_files"}}
    (history / "PACKAGE_HISTORY.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
