"""Compile and exercise the actual candidate scene transformer, never a game.

Source SZE bytes and the exact failed-plan collision are real inputs. The
compiled DLL writes only supplied fixture buffers; no process is attached.
"""
from pathlib import Path
import ctypes as C
import hashlib
import itertools
import json
import os
import struct
import subprocess
import sys
import unittest

HERE = Path(__file__).resolve().parent
ROOT = next((p for p in HERE.parents if (p / "Anno1503.exe").is_file()
             and not (p / ".anno1503-worldsettings-test-copy.json").exists()), None)
if ROOT is None:
    raise RuntimeError("Extract the development package inside the original Anno 1503 game folder to run this fixture.")
WORK = ROOT / "WorldSettings_Work"
DATA = HERE / "fixture_data"
PRIVATE = HERE / "engine_resume/ai_food/experiment_runtime"
sys.path.insert(0, str(DATA))
from scene_catalogue import chunks


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fields(payload):
    result = []
    at = 8
    while at < len(payload):
        if len(payload) - at < 8:
            raise ValueError("short field")
        length, = struct.unpack_from("<H", payload, at + 6)
        head = 8
        if length >= 0xff00:
            if len(payload) - at < 10:
                raise ValueError("short extended field")
            head = 10
            length = ((length & 255) << 16) | struct.unpack_from("<H", payload, at + 8)[0]
        if length > len(payload) - at - head:
            raise ValueError("field outside parent")
        result.append((payload[at:at + 6].rstrip(b"\0"), at, head, payload[at + head:at + head + length]))
        at += head + length
    return result


def field(tag, value, extended=False):
    tag = tag.ljust(6, b"\0")
    if extended:
        return tag + struct.pack("<HH", 0xff00 | (len(value) >> 16), len(value) & 65535) + value
    if len(value) >= 0xff00:
        raise ValueError("extended length required")
    return tag + struct.pack("<H", len(value)) + value


def remove_city(payload):
    return payload[:8] + b"".join(payload[at:at + head + len(value)]
                                  for tag, at, head, value in fields(payload) if tag != b"STADT2")


class Settings(C.Structure):
    _fields_ = [("size", C.c_uint32), ("difficulty", C.c_int32), ("islandSize", C.c_int32),
                ("islandCount", C.c_int32), ("spacing", C.c_int32), ("aiCount", C.c_int32),
                ("cultures", C.c_uint32), ("factions", C.c_uint32)]


class SceneSanitization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_inputs = json.loads((HERE / "FIXTURE_INPUTS.json").read_bytes())["files"]
        for relative, digest in cls.fixture_inputs.items():
            if sha(HERE / relative) != digest:
                raise AssertionError("Packaged fixture input changed: " + relative)
        compiler = WORK / "_tools/ziglang/zig.exe"
        if not compiler.is_file():
            raise FileNotFoundError("This developer fixture requires the existing Zig compiler at " + str(compiler))
        cls.out = HERE / "_build"
        cls.out.mkdir(exist_ok=True)
        for name in ("global-cache", "local-cache", "tmp"):
            (cls.out / name).mkdir(exist_ok=True)
        cls.inputs = [Path(__file__).resolve(), HERE / "scene_fixture.c"] + sorted(p for p in (HERE / "engine_resume").rglob("*") if p.is_file())
        cls.before = {str(p.relative_to(HERE)): sha(p) for p in cls.inputs}
        env = dict(os.environ, ZIG_GLOBAL_CACHE_DIR=str(cls.out / "global-cache"),
                   ZIG_LOCAL_CACHE_DIR=str(cls.out / "local-cache"), TEMP=str(cls.out / "tmp"), TMP=str(cls.out / "tmp"))
        cls.command = [str(compiler), "cc", "-target", "x86_64-windows-gnu", "-shared",
                       "-O2", "-Wall", "-Wextra", "-Werror", "-o", str(cls.out / "SceneFixture.dll"),
                       str(HERE / "scene_fixture.c"), "-lbcrypt", "-lkernel32"]
        subprocess.run(cls.command, check=True, env=env)
        cls.lib = C.CDLL(str(cls.out / "SceneFixture.dll"))
        cls.lib.SceneFixtureBuild.argtypes = [C.POINTER(Settings), C.c_void_p, C.c_uint32, C.c_void_p, C.c_uint32]
        cls.lib.WorldSettingsBuildPlan.argtypes = [C.POINTER(Settings), C.c_uint32, C.c_void_p, C.c_uint32]
        cls.lib.SceneFixturePlayer.argtypes = [C.c_void_p, C.c_uint32, C.c_uint32, C.c_void_p, C.c_uint32,
                                              C.POINTER(C.c_uint32), C.c_void_p, C.c_uint32]
        cls.sources = []
        for name in ("01_1024_easy_256.sze", "03_1024_med_256.sze", "06_1024_heavy_256.sze"):
            p = DATA / "scenes" / name
            cls.sources.append((p, p.read_bytes()))
        cls.states = []
        for path, data in cls.sources:
            cls.states.append(next(c.payload for c in chunks(data, 32, len(data))
                                   if c.tag == "SPIELER" and struct.unpack_from("<I", c.payload, 4)[0] == 5
                                   and c.payload[8:14] != b"HEAD\0\0"))
        cls.cases = []

    def transform_player(self, payload, faction=2, capacity=None):
        initial = b"PREVIOUS"
        capacity = len(payload) + 64 if capacity is None else capacity
        output = C.create_string_buffer(max(capacity, len(initial)) + 32)
        C.memset(output, 0xa5, len(output))
        C.memmove(output, initial, len(initial))
        before = output.raw
        used = C.c_uint32(len(initial))
        error = C.create_string_buffer(512)
        source = C.create_string_buffer(payload)
        result = self.lib.SceneFixturePlayer(source, len(payload), faction, output, capacity,
                                             C.byref(used), error, len(error))
        return result, used.value, output.raw, before, error.value

    def test_all_source_difficulties_and_faction_combinations(self):
        for difficulty, factions in itertools.product(range(3), range(4)):
            with self.subTest(difficulty=difficulty, factions=factions):
                settings = Settings(32, difficulty, 0, 24, 16, 0, 255, factions)
                output, error = C.create_string_buffer(262144), C.create_string_buffer(512)
                self.assertEqual(self.lib.WorldSettingsBuildPlan(C.byref(settings), 903, error, len(error)), 1, error.value)
                length = self.lib.SceneFixtureBuild(C.byref(settings), output, len(output), error, len(error))
                self.assertGreater(length, 0, error.value)
                actual = output.raw[:length]
                self.assertEqual(struct.unpack_from("<I", actual, 12)[0], len(actual) - 16)
                self.assertEqual(struct.unpack_from("<I", actual, 28)[0], len(actual) - 32)
                old = list(chunks(self.sources[difficulty][1], 32, len(self.sources[difficulty][1])))
                new = list(chunks(actual, 32, len(actual)))
                players = [c for c in old if c.tag == "SPIELER"]
                types = {struct.unpack_from("<I", c.payload, 4)[0]: struct.unpack_from("<H", c.payload, 16)[0]
                         for c in players if c.payload[8:14] == b"HEAD\0\0"}
                expected = []
                for c in players:
                    payload = c.payload
                    owner = struct.unpack_from("<I", payload, 4)[0]
                    typ = types[owner]
                    bit = 1 if typ == 15 else 2 if typ == 16 else 0
                    if bit and not factions & bit:
                        continue
                    if typ == 16 and payload[8:14] != b"HEAD\0\0":
                        payload = remove_city(payload)
                    result = bytearray(payload)
                    for tag, at, head, value in fields(payload):
                        if tag == b"COMP" and struct.unpack_from("<I", value)[0] == 12:
                            self.assertEqual(value[8:].count(b"SUSPEND=0\0"), 1)
                            result[at + head + 8 + value[8:].index(b"SUSPEND=0\0") + 8] = ord("1")
                    expected.append(bytes(result))
                self.assertEqual([c.payload for c in new if c.tag == "SPIELER"], expected)
                ignored = {"INSELLNK", "INSEL5", "ROHSTOFF", "ERZE", "SCHATZ", "SPIELER", "BIGBROTHER"}
                self.assertEqual([(c.tag, c.payload) for c in new if c.tag not in ignored],
                                 [(c.tag, c.payload) for c in old if c.tag not in ignored])
                original_script = next(c.payload for c in old if c.tag == "BIGBROTHER")
                for owner, typ in types.items():
                    bit = 1 if typ == 15 else 2 if typ == 16 else 0
                    if bit and not factions & bit:
                        line = ('"%s" %u\n' % ("PIRAT01" if bit == 1 else "VENEZIA01", owner)).encode()
                        self.assertEqual(original_script.count(line), 1)
                        original_script = original_script.replace(line, b"")
                self.assertEqual(next(c.payload for c in new if c.tag == "BIGBROTHER"), original_script)
                self.cases.append(dict(difficulty=difficulty, factions=factions, bytes=length,
                                       player_and_controller_bytes_exact_except_declared_edits=True))

    def test_exact_failed_stock_city_is_removed_and_controller_retained(self):
        payload = self.states[0]
        city = next(value for tag, at, head, value in fields(payload) if tag == b"STADT2")
        self.assertEqual(struct.unpack_from("<HHH", city), (0, 212, 321))
        plan = json.loads((DATA / "failed_plan.json").read_bytes())
        island = next(p for p in plan["plans"] if p["id"] == 3)
        self.assertLessEqual(island["x"], 212)
        self.assertLess(212, island["x"] + island["width"])
        self.assertLessEqual(island["y"], 321)
        self.assertLess(321, island["y"] + island["height"])
        ok, used, actual, before, error = self.transform_player(payload)
        self.assertEqual(ok, 1, error)
        expected = remove_city(payload)
        self.assertEqual(used, 8 + 16 + len(expected))
        self.assertEqual(actual[:8], b"PREVIOUS")
        self.assertEqual(actual[8:used], b"SPIELER\0\0\0\0\0" + struct.pack("<I", len(expected)) + expected)
        self.assertEqual(next(v for tag, at, head, v in fields(expected) if tag == b"COMP"),
                         next(v for tag, at, head, v in fields(payload) if tag == b"COMP"))
        self.assertEqual(actual[used:], before[used:])

    def test_medium_and_hard_cityless_states_are_byte_exact(self):
        for payload in self.states[1:]:
            with self.subTest(length=len(payload)):
                ok, used, actual, before, error = self.transform_player(payload)
                self.assertEqual(ok, 1, error)
                self.assertEqual(actual[24:used], payload)

    def test_extended_city_and_unknown_nonspatial_fields(self):
        clean = remove_city(self.states[0])
        extra = field(b"EXTRA", bytes(range(256)) * 256, extended=True)
        city = field(b"STADT2", b"\0" * 65536, extended=True)
        payload = clean[:8] + extra + city + clean[8:]
        ok, used, actual, before, error = self.transform_player(payload)
        self.assertEqual(ok, 1, error)
        self.assertEqual(actual[24:used], clean[:8] + extra + clean[8:])

    def test_malformed_states_publish_no_partial_output(self):
        clean = remove_city(self.states[0])
        comp = next((at, head, value) for tag, at, head, value in fields(clean) if tag == b"COMP")
        at, head, value = comp
        bad_owner = bytearray(clean)
        struct.pack_into("<I", bad_owner, at + head + 4, 6)
        bad_type = bytearray(clean)
        struct.pack_into("<I", bad_type, at + head, 15)
        bad_id = bytearray(clean)
        struct.pack_into("<I", bad_id, 4, 32)
        bad_version = bytearray(clean)
        struct.pack_into("<I", bad_version, 0, 1)
        mutations = {
            "short player prefix": clean[:7], "missing controller": clean[:8],
            "short field header": clean + b"STADT2", "short extended header": clean + b"STADT2\x00\xff",
            "field exceeds parent": clean + b"STADT2\xff\x00\x00", "state owner mismatch": bytes(bad_owner),
            "state type mismatch": bytes(bad_type), "owner exceeds table": bytes(bad_id), "unsupported prefix": bytes(bad_version),
            "duplicate controller": clean + field(b"COMP", value), "short city anchor": clean + field(b"STADT2", b"\0" * 5),
            "duplicate cities": clean + field(b"STADT2", b"\0" * 6) * 2,
            "basic marker without basic fields": clean[:8] + field(b"HEAD", b"\0" * 108),
        }
        for name, payload in mutations.items():
            with self.subTest(name=name):
                ok, used, actual, before, error = self.transform_player(payload)
                self.assertEqual(ok, 0)
                self.assertEqual(used, 8)
                self.assertEqual(actual, before)
                self.assertTrue(error)
        self.malformed_count = len(mutations)

    def test_output_capacity_failure_is_atomic(self):
        payload = self.states[0]
        expected = remove_city(payload)
        for capacity in (0, 7, 8, 23, 24 + len(expected) - 1):
            with self.subTest(capacity=capacity):
                ok, used, actual, before, error = self.transform_player(payload, capacity=capacity)
                self.assertEqual(ok, 0)
                self.assertEqual(used, 8)
                self.assertEqual(actual, before)
                self.assertTrue(error)

    def test_loaded_certificate_and_other_inputs_remain_exact(self):
        originals = json.loads((HERE / "SOURCE_INPUTS.json").read_bytes())
        expected_changes = {"engine_resume/ai_food/experiment_runtime/world_backend.c",
                            "engine_resume/ai_food/experiment_runtime/special_scene.inc"}
        for relative, digest in originals.items():
            with self.subTest(relative=relative):
                original = DATA / "source_before" / relative
                self.assertEqual(sha(original), digest)
                if relative not in expected_changes:
                    self.assertEqual(sha(HERE / relative), digest)


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SceneSanitization))
    report = dict(status="passed" if result.wasSuccessful() else "failed", actual_game_runs=0,
                  compiled_fixture_only=True, tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                  source_sha256=getattr(SceneSanitization, "before", {}),
                  fixture_input_sha256=getattr(SceneSanitization, "fixture_inputs", {}),
                  game_root=str(ROOT), compiler_dependency=str(WORK / "_tools/ziglang/zig.exe"),
                  staged_scene_cases=getattr(SceneSanitization, "cases", []),
                  malformed_state_cases=13, output_capacity_failure_cases=5,
                  typed_player_payload_transform=True, loaded_owner_certificate_unchanged=True)
    if hasattr(SceneSanitization, "out") and (SceneSanitization.out / "SceneFixture.dll").is_file():
        report["fixture_sha256"] = sha(SceneSanitization.out / "SceneFixture.dll")
    (HERE / "scene_sanitization_results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    sys.exit(not result.wasSuccessful())
