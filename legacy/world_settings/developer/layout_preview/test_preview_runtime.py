"""Exercise exact preview-to-stage lifecycle through the compiled runtime DLL.

This is an automated Python-host test on copied actual assets. No Anno process,
native hooks, menu input, rendered gameplay or successful native loading is
claimed. The separate production tests inspect retained fleet/player chunks.
"""
from pathlib import Path
import argparse
import ctypes as C
import hashlib
import importlib.util
import json
import os
import struct
import sys
import time

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[1]
SOURCE = PACKAGE / "developer/source"
WORK = PACKAGE.parent
EXE_SHA = "1a4bebe7c676a5904834b9e67e936187729dc67c013a4fb4fd64986a3cb8e95a"


class Settings(C.Structure):
    _fields_ = [("size", C.c_uint32)] + [(name, C.c_int32) for name in
        ["difficulty", "islandSize", "islandCount", "spacing", "aiCount"]] + [
        ("cultures", C.c_uint32), ("factions", C.c_uint32)] + [(name, C.c_int32) for name in
        ["startingMoney", "startingFleet", "aiDifficulty", "plantFertility", "mineralFertility", "worldSize"]]


class Island(C.Structure):
    _fields_ = [(name, C.c_uint32) for name in
                ["id", "x", "y", "width", "height", "templateIndex", "cropMask", "mineralMask", "cultures", "climate"]]


class Snapshot(C.Structure):
    _fields_ = [(name, C.c_uint32) for name in ["size", "state", "seed", "count"]] + [
        ("settings", Settings), ("islands", Island * 128)]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def settings(**changes):
    values = dict(size=56, difficulty=1, islandSize=3, islandCount=24, spacing=0,
                  aiCount=0, cultures=255, factions=3, startingMoney=30000,
                  startingFleet=0, aiDifficulty=1, plantFertility=1, mineralFertility=1, worldSize=1024)
    values.update(changes)
    return Settings(**values)


def clone(row):
    return type(row).from_buffer_copy(bytes(row))


def scene_links(data):
    assert len(data) >= 32 and struct.unpack_from("<I", data, 12)[0] == len(data) - 16
    assert data[16:28].split(b"\0", 1)[0] == b"SCENE"
    assert struct.unpack_from("<I", data, 28)[0] == len(data) - 32
    at, result = 32, []
    while at < len(data):
        assert len(data) - at >= 16
        tag = data[at:at + 12].split(b"\0", 1)[0]
        size = struct.unpack_from("<I", data, at + 12)[0]
        assert size <= len(data) - at - 16
        if tag == b"INSELLNK":
            payload = data[at + 16:at + 16 + size]
            assert len(payload) >= 14 and payload[12:].endswith(b"_dummy.scp\0")
            x, y, width, height, ident = struct.unpack_from("<HHHHI", payload)
            result.append((ident, x, y, width, height))
        assert tag != b"INSEL5"
        at += size + 16
    assert at == len(data)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, default=SOURCE / "runtime_dev3/AnnoWorldSettings.dll")
    args = parser.parse_args()
    fixture = args.fixture.resolve(strict=True)
    assert fixture.is_relative_to((WORK / "layout_preview").resolve())
    assert fixture.name.startswith("preview-stage-")
    marker = json.loads((fixture / ".anno1503-worldsettings-test-copy.json").read_bytes())
    assert marker["development_copy"] and Path(marker["copy_root"]).resolve() == fixture
    assert marker["source_exe_sha256"] == sha(fixture / "Anno1503.exe") == EXE_SHA
    runtime = args.runtime.resolve(strict=True)
    metadata = json.loads((SOURCE / "runtime_dev3/build_result.json").read_bytes())
    assert metadata["sha256"] == sha(runtime) and metadata["abi_size"] == 56
    assert all(sha(SOURCE / name) == digest for name, digest in metadata["source_sha256"].items())
    assert C.sizeof(Settings) == 56 and C.sizeof(Island) == 40 and C.sizeof(Snapshot) == 5192
    decoder_path = PACKAGE / "activation/preview_snapshot.py"
    decoder_spec = importlib.util.spec_from_file_location("actual_preview_snapshot_decoder", decoder_path)
    decoder = importlib.util.module_from_spec(decoder_spec)
    decoder_spec.loader.exec_module(decoder)
    backend_path = SOURCE / "engine_resume/ai_food/experiment_runtime/world_backend.c"
    backend_text = backend_path.read_text(encoding="utf-8")
    preview_stage_source = backend_text.split("int WorldSettingsStagePreviewScene(", 1)[1].split("__declspec(dllexport)", 1)[0]
    assert "WorldSettingsBuildPlan" not in preview_stage_source and "return wsStagePlan(" in preview_stage_source
    lib = C.CDLL(str(runtime))
    lib.WorldSettingsSettingsSize.restype = C.c_uint32
    lib.WorldSettingsPreviewSnapshotSize.restype = C.c_uint32
    assert lib.WorldSettingsSettingsSize() == 56 and lib.WorldSettingsPreviewSnapshotSize() == 5192
    build = lib.WorldSettingsBuildPlan
    build.argtypes = [C.POINTER(Settings), C.c_uint32, C.c_void_p, C.c_uint32]
    build.restype = C.c_int
    stage = lib.WorldSettingsStagePreviewScene
    stage.argtypes = [C.POINTER(Settings), C.c_char_p, C.c_uint32, C.POINTER(Island), C.c_uint32,
                     C.c_void_p, C.c_uint32, C.c_void_p, C.c_uint32]
    stage.restype = C.c_int
    copy_snapshot = lib.WorldSettingsCopyPreviewSnapshot
    copy_snapshot.argtypes = [C.c_void_p]
    copy_snapshot.restype = C.c_uint32
    lib.WorldSettingsPlanCount.restype = C.c_int
    lib.WorldSettingsPlanIsland.argtypes = [C.c_uint32, C.POINTER(Island)]
    lib.WorldSettingsPlanIsland.restype = C.c_int
    lib.WorldSettingsIsActive.restype = C.c_int
    lib.WorldSettingsPendingPath.restype = C.c_char_p
    lib.WorldSettingsFinishAttempt.argtypes = [C.c_int]
    error = C.create_string_buffer(512)
    path_out = C.create_string_buffer(260)
    root_bytes = str(fixture).encode("mbcs")
    before_scenes = {p.name: sha(p) for p in (fixture / "Scenes").glob("WorldSettings_*.sze")}
    assert not before_scenes and lib.WorldSettingsIsActive() == 0
    assert copy_snapshot(None) == 0
    checks, rejects, staged, timings = [], [], [], []

    def snapshot():
        out = Snapshot()
        assert copy_snapshot(C.byref(out)) == 5192
        assert out.size == 5192 and out.count <= 128
        parsed = decoder.decode(bytes(out))
        assert parsed["state"] == out.state and parsed["seed"] == out.seed and parsed["count"] == out.count
        assert parsed["plan_sha256"] == hashlib.sha256(bytes(out.islands)[:out.count * 40]).hexdigest()
        return out

    def rows_for(snap):
        return (Island * snap.count)(*(clone(row) for row in snap.islands[:snap.count]))

    def plan(selected, seed):
        error.value = b""
        started = time.perf_counter()
        assert build(C.byref(selected), seed, error, len(error)) == 1, error.value
        timings.append((time.perf_counter() - started) * 1000)
        snap = snapshot()
        assert snap.state == 1 and snap.seed == seed and snap.count == selected.islandCount
        assert bytes(snap.settings) == bytes(selected)
        assert lib.WorldSettingsPlanCount() == snap.count
        for i, expected in enumerate(snap.islands[:snap.count]):
            actual = Island()
            assert lib.WorldSettingsPlanIsland(i, C.byref(actual)) == 1
            assert expected.id == i and bytes(actual) == bytes(expected)
        return snap

    initial = snapshot()
    assert initial.state == 0 and initial.count == 0
    checks.append("Fresh DLL has no valid preview or pending staged world")
    signatures = {}
    for seed in [0, 1, 903, 0x15032026, 0xffffffff, 107, 9182, 27459]:
        selected = settings()
        first = plan(selected, seed)
        second = plan(selected, seed)
        assert bytes(first) == bytes(second), "The same settings/seed changed the actual preview"
        signatures[seed] = hashlib.sha256(bytes(rows_for(first))).hexdigest()
    assert len(set(signatures.values())) == len(signatures), "Regeneration seeds failed to produce distinct worlds"
    checks.append("Eight regeneration seeds yield distinct plans; every repeated seed reproduces all exact preview rows")
    selected, seed = settings(), 903
    snap = plan(selected, seed)
    rows = rows_for(snap)
    decoder_rejects = []

    def decoder_reject(label, data):
        try:
            decoder.decode(data)
        except ValueError:
            decoder_rejects.append(label)
        else:
            raise AssertionError("Snapshot decoder accepted " + label)

    for length in [0, 72, 5191, 5193]:
        decoder_reject("Truncated/oversized snapshot " + str(length), (bytes(snap) + b"\0")[:length])
    for label, offset, value in [
            ("Forged envelope size", 0, 5184), ("Unknown state", 4, 5),
            ("Count outside bound", 12, 129), ("Settings ABI mismatch", 16, 44),
            ("Count/settings disagreement", 12, 23), ("Forged island identity", 72, 99),
            ("Off-grid coordinate", 76, 1), ("Out-of-world coordinate", 76, 1024),
            ("Empty island dimensions", 84, 0), ("Invalid template", 92, 444),
            ("Invalid climate", 108, 6), ("Unexpected unused row", 72 + snap.count * 40, 1)]:
        malformed = bytearray(bytes(snap))
        struct.pack_into("<I", malformed, offset, value)
        decoder_reject(label, bytes(malformed))
    absent_seed = bytearray(bytes(initial))
    struct.pack_into("<I", absent_seed, 8, 5)
    decoder_reject("Absent snapshot with hidden seed", bytes(absent_seed))
    checks.append("Actual read-only snapshot bytes decode with exact plan SHA; malformed envelopes, hidden rows and forged geometry are rejected")

    def reject(label, selected_arg=None, seed_arg=None, rows_arg=None, count=None, root_arg=None, output_arg=None, output_cap=None):
        old = bytes(snapshot())
        error.value, path_out.value = b"", b""
        selected_arg = selected if selected_arg is None else selected_arg
        result = stage(C.byref(selected_arg), root_bytes if root_arg is None else root_arg,
                       seed if seed_arg is None else seed_arg, rows if rows_arg is None else rows_arg,
                       len(rows) if count is None else count, path_out if output_arg is None else output_arg,
                       len(path_out) if output_cap is None else output_cap, error, len(error))
        assert result == 0 and error.value, (label, result, error.value)
        assert lib.WorldSettingsIsActive() == 0 and lib.WorldSettingsPendingPath() is None
        assert not list((fixture / "Scenes").glob("WorldSettings_*.sze")), label
        assert bytes(snapshot()) == old, "Rejected stage mutated the cached preview: " + label
        rejects.append(dict(case=label, error=error.value.decode("mbcs", "replace")))

    variants = {"size": 44, "difficulty": 2, "islandSize": 2, "islandCount": 25, "spacing": 8,
                "aiCount": 1, "cultures": 254, "factions": 2, "startingMoney": 10000,
                "startingFleet": 1, "aiDifficulty": 2, "plantFertility": 0, "mineralFertility": 0, "worldSize": 512}
    for name, value in variants.items():
        changed = clone(selected)
        setattr(changed, name, value)
        reject("Changed setting " + name, selected_arg=changed)
    reject("Changed regeneration seed", seed_arg=seed + 1)
    for count in [0, len(rows) - 1, len(rows) + 1, 129]:
        reject("Changed preview count " + str(count), count=count)
    for name, _ctype in Island._fields_:
        changed_rows = (Island * len(rows)).from_buffer_copy(bytes(rows))
        setattr(changed_rows[0], name, getattr(changed_rows[0], name) ^ 8)
        reject("Changed preview island field " + name, rows_arg=changed_rows)
    reject("Null preview row pointer", rows_arg=C.POINTER(Island)())
    reject("Relative staging root", root_arg=b"relative")
    reject("Output buffer too short", output_cap=1)
    checks.append("Every settings field, seed, row count and island field mismatch is rejected without files or preview mutation")

    other = plan(selected, seed + 1)
    reject("Superseded preview rows and seed")
    assert snapshot().seed == other.seed
    invalid = clone(selected)
    invalid.size = 44
    assert build(C.byref(invalid), seed, error, len(error)) == 0
    assert snapshot().state == 0 and snapshot().count == 0
    reject("A failed replan invalidates the older preview")
    checks.append("Successful regeneration supersedes the previous plan; an invalid replan clears preview readiness")

    for finish_success in [0, 1]:
        snap = plan(selected, seed + finish_success)
        active_seed = snap.seed
        active_rows = rows_for(snap)
        error.value = path_out.value = b""
        assert stage(C.byref(selected), root_bytes, active_seed, active_rows, len(active_rows),
                     path_out, len(path_out), error, len(error)) == 1, error.value
        path = Path(path_out.value.decode("mbcs")).resolve()
        assert path.parent == fixture / "Scenes" and path.name.startswith("WorldSettings_" + str(os.getpid()) + "_")
        assert path.is_file() and lib.WorldSettingsIsActive() == 1
        assert Path(lib.WorldSettingsPendingPath().decode("mbcs")).resolve() == path
        committed_preview = snapshot()
        assert committed_preview.state == 2 and committed_preview.seed == active_seed
        assert bytes(rows_for(committed_preview)) == bytes(active_rows)
        assert scene_links(path.read_bytes()) == [(p.id, p.x, p.y, p.width, p.height) for p in active_rows]
        staged.append(dict(seed=active_seed, scene_sha256=sha(path), preview_rows_sha256=hashlib.sha256(bytes(active_rows)).hexdigest(),
                           exact_staged_link_count=len(active_rows), finish_success_flag=finish_success,
                           finish_is_emulated_in_python=True))
        before = bytes(committed_preview)
        assert build(C.byref(selected), active_seed + 99, error, len(error)) == 0
        assert bytes(snapshot()) == before and path.is_file()
        assert stage(C.byref(selected), root_bytes, active_seed, active_rows, len(active_rows),
                     path_out, len(path_out), error, len(error)) == 0
        assert bytes(snapshot()) == before and path.is_file()
        lib.WorldSettingsFinishAttempt(finish_success)
        assert not path.exists() and lib.WorldSettingsIsActive() == 0 and lib.WorldSettingsPendingPath() is None
        finished = snapshot()
        assert finished.state == (3 if finish_success else 4)
        assert bytes(rows_for(finished)) == bytes(active_rows)
        lib.WorldSettingsFinishAttempt(0)
        if finish_success:
            assert bytes(snapshot()) == bytes(finished), "An unrelated later cleanup overwrote the committed snapshot"
    checks.append("Preview staging emits exact INSELLNK rows without replanning; pending operations cannot replace its plan or file")
    checks.append("Emulated finish success/failure cleans temporary scenes and retains corresponding snapshot evidence")
    snap = plan(selected, seed)
    lib.WorldSettingsFinishAttempt(0)
    assert snapshot().state == 4 and lib.WorldSettingsIsActive() == 0
    reject("Back/cancel invalidates an unstaged preview")
    checks.append("Unstaged preview cancellation creates no file and cannot subsequently start the cancelled map")
    assert before_scenes == {p.name: sha(p) for p in (fixture / "Scenes").glob("WorldSettings_*.sze")}
    assert sha(runtime) == metadata["sha256"]
    report = dict(scope=__doc__, runtime_sha256=sha(runtime), build_result_sha256=sha(SOURCE / "runtime_dev3/build_result.json"),
                  compiled_source_sha256=metadata["source_sha256"], settings_abi=56, plan_island_size=40,
                  snapshot_size=5192, fixture_root=str(fixture), seed_count=len(signatures),
                  snapshot_decoder_sha256=sha(decoder_path), snapshot_decoder_rejected_cases=decoder_rejects,
                  deterministic_seed_signatures=signatures, rejected_stale_or_invalid_stages=rejects,
                  checks=checks, check_groups=len(checks), staged_exact_preview_scenes=staged,
                  staged_scene_count=len(staged), actual_plan_milliseconds=dict(samples=len(timings),
                      maximum=max(timings), mean=sum(timings) / len(timings)),
                  cached_rows_equal_staged_links=True, no_stage_replan=True,
                  no_stage_replan_source_checked=True, staging_backend_source_sha256=sha(backend_path),
                  stale_settings_seed_rows_rejected_before_publication=True,
                  pending_plan_immutable=True, cancelled_preview_cannot_start=True,
                  temporary_scenes_cleaned=True, shared_game_copy_modified=False,
                  native_finish_status_is_emulated=True, actual_game_run=False,
                  ui_or_gameplay_verified=False, verifier_sha256=sha(Path(__file__)), passed=True)
    (HERE / "preview_runtime_results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ["passed", "runtime_sha256", "seed_count", "check_groups", "staged_scene_count", "actual_game_run"]}, indent=2))


if __name__ == "__main__":
    main()
