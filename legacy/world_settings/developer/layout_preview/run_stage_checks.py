"""Run preview and production staging checks on an isolated actual-asset fixture.

All catalogue assets, dummy aliases, stock scenes and the executable are copied
from inspected files. Only this owned temporary fixture receives generated SZE
files. No installed game/game-copy file is changed and no Anno process is run.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[1]
WORK = PACKAGE.parent
GAME = WORK.parent
COPY = WORK / "game_copy"
EXE_SHA = "1a4bebe7c676a5904834b9e67e936187729dc67c013a4fb4fd64986a3cb8e95a"
MARKER = ".anno1503-worldsettings-test-copy.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, default=PACKAGE / "developer/source/runtime_dev3/AnnoWorldSettings.dll")
    parser.add_argument("--skip-production", action="store_true")
    args = parser.parse_args()
    runtime = args.runtime.resolve(strict=True)
    source = PACKAGE / "developer/fertility/verify_policy.py"
    spec = importlib.util.spec_from_file_location("preview_actual_catalogue", source)
    policy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(policy)
    rows, catalogue = policy.catalogue()
    assert len(rows) == 444 and sha(GAME / "Anno1503.exe") == EXE_SHA
    temporary = tempfile.TemporaryDirectory(prefix="preview-stage-", dir=WORK / "layout_preview")
    fixture = Path(temporary.name).resolve()
    assert fixture.is_relative_to((WORK / "layout_preview").resolve())
    copied = {}

    def copy_actual(relative, expected=None):
        target = fixture / relative
        assert target.resolve().is_relative_to(fixture)
        if target.exists():
            assert expected is None or sha(target) == expected
            return
        original = GAME / relative
        if not original.is_file():
            original = COPY / relative
        if not original.is_file():
            original = PACKAGE / "assets" / relative
        assert original.is_file(), original
        digest = sha(original)
        assert expected is None or digest == expected, original
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
        assert sha(target) == digest
        copied[target.relative_to(fixture).as_posix()] = dict(source=str(original), sha256=digest, bytes=target.stat().st_size)

    try:
        copy_actual("Anno1503.exe", EXE_SHA)
        folder = ["polar", "tundra", "nord", "praerie", "dschungel", "steppe"]
        prefix = ["Po", "T", "N", "Pr", "D", "S"]
        for row in rows:
            copy_actual(row["path"], row["sha256"])
            name = f"Scenes/islands/{folder[row['climate']]}/{prefix[row['climate']]}_{row['width']:03}x{row['height']:03}_dummy.scp"
            copy_actual(name)
        for name in ["01_1024_easy_256.sze", "03_1024_med_256.sze", "06_1024_heavy_256.sze"]:
            copy_actual("Languages/Nl/Scenes/0010SingleEndlos/" + name)
        (fixture / MARKER).write_text(json.dumps(dict(schema=1, development_copy=True,
            copy_root=str(fixture), source_root=str(GAME.resolve()), source_exe_sha256=EXE_SHA)), encoding="utf-8")
        assert (fixture / "Scenes").is_dir()
        before = {name: sha(fixture / name) for name in copied}
        subprocess.run([sys.executable, "-B", str(HERE / "test_preview_runtime.py"),
                        "--fixture", str(fixture), "--runtime", str(runtime)], check=True)
        if not args.skip_production:
            subprocess.run([sys.executable, "-B", str(PACKAGE / "developer/start_options/economy/test_production_stage.py"),
                            "--copy", str(fixture), "--package", str(PACKAGE), "--runtime", str(runtime)], check=True)
        subprocess.run([sys.executable, "-B", str(PACKAGE / "developer/world_sizes/test_world_runtime.py"),
                        "--fixture", str(fixture), "--runtime", str(runtime)], check=True)
        assert before == {name: sha(fixture / name) for name in copied}
        assert not list((fixture / "Scenes").glob("WorldSettings_*.sze"))
        assert all(sha(Path(item["source"])) == item["sha256"] for item in copied.values())
        report = dict(scope=__doc__, runtime_sha256=sha(runtime),
                      catalogue_sha256=sha(catalogue), copied_actual_catalogue_assets=len(rows),
                      copied_files=copied, generated_scene_files_cleaned=True,
                      fixture_inputs_unchanged=True, original_assets_unchanged=True,
                      shared_game_copy_modified=False, game_executed=False,
                      production_checks_run=not args.skip_production,
                      fixture_directory=str(fixture), fixture_removed_after_check=True,
                      runner_sha256=sha(Path(__file__)), passed=True)
    finally:
        assert fixture.is_relative_to((WORK / "layout_preview").resolve())
        temporary.cleanup()
    assert not fixture.exists()
    (HERE / "asset_fixture_results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(passed=True, catalogue_assets=len(rows), copied_files=len(copied),
                         copied_bytes=sum(row["bytes"] for row in copied.values()),
                         production_checks_run=not args.skip_production,
                         game_executed=False, fixture_removed=True), indent=2))


if __name__ == "__main__":
    main()
