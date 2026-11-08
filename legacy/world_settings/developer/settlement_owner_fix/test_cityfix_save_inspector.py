"""Known-save replay and in-memory rejection checks; never writes game saves."""
from pathlib import Path
import json
import struct
import sys
import unittest

import inspect_cityfix_save as check
from scene_catalogue import chunks, read_container, make_chunk

HERE = Path(__file__).resolve().parent


def serialize(records):
    return make_chunk("ANNOADDON1", b"".join(make_chunk(tag, payload) for tag, payload in records))


def native_field(tag, payload):
    encoded = tag.encode().ljust(6, b"\0")
    if len(payload) >= 0xff00:
        return encoded + struct.pack("<HH", 0xff00 | (len(payload) >> 16), len(payload) & 65535) + payload
    return encoded + struct.pack("<H", len(payload)) + payload


class InspectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = json.loads((HERE / "ws9_reference.json").read_bytes())
        cls.path = Path(cls.reference["save_path"])
        cls.data = cls.path.read_bytes()
        if check.sha(cls.data) != cls.reference["save_sha256"]:
            raise AssertionError("Known reference save changed")
        root, _ = read_container(cls.data)
        cls.records = [(c.tag, c.payload) for c in chunks(cls.data, 16, root.end)]
        cls.report = check.parse_save(cls.data, "ws9", 3, True, True, 24, 16, "medium", 255)

    def test_known_actual_medium_save_full_inspection(self):
        report = check.inspect(self.path, self.reference["save_sha256"], "ws9", 3, True, True, "medium", "mixed", 24, 16, 255)
        self.assertEqual(report["saved_enabled_cpu_ids"], [1, 2, 3])
        self.assertEqual(len(report["basic_players"]), 16)
        self.assertEqual(report["special_factions"]["venetians"]["owned_cities"], [])

    def test_wrong_selections_are_rejected(self):
        cases = [
            ("wrong alias", ("wrong", 3, True, True, 24, 16, "medium", 255)),
            ("wrong AI", ("ws9", 0, True, True, 24, 16, "medium", 255)),
            ("Easy requires three CPU placeholders", ("ws9", 3, True, True, 24, 16, "easy", 255)),
            ("forbidden pirates", ("ws9", 3, False, True, 24, 16, "medium", 255)),
            ("forbidden Venetians", ("ws9", 3, True, False, 24, 16, "medium", 255)),
            ("wrong count", ("ws9", 3, True, True, 23, 16, "medium", 255)),
            ("wrong spacing", ("ws9", 3, True, True, 24, 17, "medium", 255)),
            ("forbidden culture", ("ws9", 3, True, True, 24, 16, "medium", 127)),
        ]
        for name, args in cases:
            with self.subTest(name=name), self.assertRaises(ValueError):
                check.parse_save(self.data, *args)

    def test_controller_parent_and_truncation_rejected(self):
        state = next(s for s in self.report["saved_player_states"] if s["id"] == 5)
        data = bytearray(self.data)
        struct.pack_into("<I", data, state["controller"]["field_offset"] + 8 + 4, 6)
        for name, altered in [("controller parent mismatch", bytes(data)), ("truncated save", self.data[:-1])]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                check.parse_save(altered, "ws9", 3, True, True, 24, 16, "medium", 255)

    def test_rogue_venetian_city_and_missing_native_city_rejected(self):
        native = next(p for p in self.report["basic_players"] if p["type"] == 14)
        native_id = native["id"]
        native_state = next(payload for tag, payload in self.records
                            if tag == "SPIELER" and struct.unpack_from("<I", payload, 4)[0] == native_id
                            and payload[8:14] != b"HEAD\0\0")
        city = check.one(check.fields(native_state, 8), "STADT2")
        for remove_original in [False, True]:
            records = []
            for tag, payload in self.records:
                if tag == "SPIELER" and payload[8:14] != b"HEAD\0\0":
                    owner = struct.unpack_from("<I", payload, 4)[0]
                    if owner == 5:
                        payload += native_field("STADT2", city)
                    elif owner == native_id and remove_original:
                        values = check.fields(payload, 8)
                        payload = payload[:8] + b"".join(native_field(k, v) for k, v, at in values if k != "STADT2")
                records.append((tag, payload))
            with self.subTest(native_city_removed=remove_original), self.assertRaises(ValueError):
                check.parse_save(serialize(records), "ws9", 3, True, True, 24, 16, "medium", 255)

    def test_in_memory_easy_three_cpu_policy(self):
        records = []
        for tag, payload in self.records:
            if tag == "SPIELER":
                owner = struct.unpack_from("<I", payload, 4)[0]
                if owner == 4:
                    continue
                if owner in [1, 2, 3] and payload[8:14] != b"HEAD\0\0":
                    self.assertEqual(payload.count(b"SUSPEND=0\0"), 1)
                    payload = payload.replace(b"SUSPEND=0\0", b"SUSPEND=1\0")
            elif tag == "BIGBROTHER":
                self.assertEqual(payload.count(b'"CG04" 4\n'), 1)
                payload = payload.replace(b'"CG04" 4\n', b"")
            records.append((tag, payload))
        synthetic = serialize(records)
        report = check.parse_save(synthetic, "ws9", 0, True, True, 24, 16, "easy", 255)
        self.assertEqual(len(report["basic_players"]), 15)
        self.assertEqual(len(report["saved_cpu_profiles"]), 3)
        self.assertEqual(report["saved_enabled_cpu_ids"], [])

    def test_wrong_size_and_changed_terrain_rejected(self):
        with self.assertRaises(ValueError):
            check.inspect_size(self.data, self.report, "large", 16)
        records = []
        changed = False
        for tag, payload in self.records:
            if tag == "INSEL5" and not changed:
                children = []
                for child in chunks(payload, 12, len(payload)):
                    value = child.payload
                    if child.tag == "HEIGHT" and not changed:
                        self.assertGreater(len(value), 6)
                        value = value[:6] + bytes([(value[6] + 1) & 255]) + value[7:]
                        changed = True
                    children.append(make_chunk(child.tag, value))
                payload = payload[:12] + b"".join(children)
            records.append((tag, payload))
        self.assertTrue(changed)
        with self.assertRaises(ValueError):
            check.inspect_size(serialize(records), self.report, "mixed", 16)

    def test_wrong_digest_and_read_only_source(self):
        with self.assertRaises(ValueError):
            check.inspect(self.path, "0" * 64, "ws9", 3, True, True, "medium", "mixed", 24, 16, 255)
        self.assertEqual(check.sha(self.path.read_bytes()), self.reference["save_sha256"])


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(InspectorTests))
    report = dict(status="passed" if result.wasSuccessful() else "failed", tests_run=result.testsRun,
                  failures=len(result.failures), errors=len(result.errors),
                  known_actual_save="ws9 Medium/Mixed24/16 AI3 both special factions on",
                  known_save_sha256=getattr(InspectorTests, "reference", {}).get("save_sha256"),
                  synthetic_easy_case_is_not_game_evidence=True, actual_game_runs=0, process_access=False,
                  inspector_sha256=check.sha((HERE / "inspect_cityfix_save.py").read_bytes()),
                  test_script_sha256=check.sha(Path(__file__).read_bytes()))
    (HERE / "cityfix_save_inspector_tests.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    sys.exit(not result.wasSuccessful())
