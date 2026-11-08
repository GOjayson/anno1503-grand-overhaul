"""Reproduce the 18 readiness classifications and four pointer rejection checks.

Every process, window, identity and memory read is a local fixture. This test
does not enumerate/open a process, invoke a native export, write remote memory,
read an actual window or control the game. It makes no actual-game claim.
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import sys
import types
import unittest

SIDECAR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SIDECAR))
import native_ready as n

# The production verifier's required-set lookup uses the helper's globals.
REQUIRED_NATIVE = {"annoframe.dll", "annoscene.dll", "annowelt.dll", "annogame.dll", "view.dll"}
BASE = 0x180000000
OBJECT = 0x200000000
HWND = 42
EXE = str(Path("Anno1503.exe").resolve())


class FakeProcess:
    def __init__(self, change):
        self.change = change
        self.read_count = 0
        self.closed = 0
        self.handle = 1
        self.pid = 7

    def read(self, address, size):
        if self.change == "unreadable":
            raise OSError("startup object not readable")
        if address == OBJECT:
            self.read_count += 1
            vt = n.BINK_VTABLE if self.change == "bink" else n.SPLASH_VTABLE
            closing = self.change == "closing" or self.change == "racing" and self.read_count > 1
            return struct.pack("<QB", BASE + vt, int(closing))
        if address == OBJECT + 0x2210:
            return (struct.pack("<i", 2 if self.change == "starting" else -1)
                    + bytes(4) + bytes([0 if self.change == "stopped" else 1])
                    + bytes(7) + struct.pack("<Q", 43 if self.change == "backlink" else HWND))
        if address == BASE + n.SPLASH_VTABLE + 0x170:
            return struct.pack("<Q", BASE + 0x57A60)
        for rva, data in n.FRAME_EVIDENCE.items():
            if address == BASE + rva:
                return bytes(size) if self.change == "code" else data
        raise OSError("Unexpected fixture read")


def fake_verify_modules(*_):
    return True


def fixture(change):
    process = FakeProcess(change)
    # Bypass all production Win32 initialization. Every collaborator below is a
    # local Python fake; the actual observer's inspect logic remains unchanged.
    observer = n.NativeReadiness.__new__(n.NativeReadiness)
    observer.inputs = dict(source=Path(EXE).parent, exe_sha256="fixture-exe",
                           native_sha256={"AnnoFrame.dll": n.FRAME_SHA256}, copy=Path("."))
    observer._hashes = {}
    modules = {name: dict(name=name, path=name, base=BASE, size=0xE0000)
               for name in REQUIRED_NATIVE}
    if change == "missing":
        modules.pop("annogame.dll")
    if change == "loaded":
        modules["annoworldsettings.dll"] = dict(name="AnnoWorldSettings.dll", path="wrong", base=1, size=1)
    modules["__all__"] = list(modules.values())

    def query_path(_handle, _flags, buffer, _length):
        buffer.value = EXE
        return True

    def close(_handle):
        process.closed += 1

    def check(value, label):
        if not value:
            raise OSError(label)
        return value

    observer.a = types.SimpleNamespace(
        Session=lambda *_: process, check=check, query_path=query_path,
        creation_time=lambda _: 123, same=lambda a, b: str(a) == str(b),
        modules=lambda _: modules, verify_modules=fake_verify_modules, close=close)
    observer._sha = lambda path: (("bad" if change == "hash" else "fixture-exe")
                                  if str(path) == EXE else n.FRAME_SHA256)
    observer._owned_windows = lambda _: [HWND]

    def window_owner(_hwnd, target):
        target._obj.value = 8 if change == "owner" else 7
        return 100

    observer.windows = dict(visible=lambda _: change != "hidden",
                            iconic=lambda _: change == "minimized",
                            valid=lambda _: change != "destroyed", pid=window_owner)
    calls = [0]

    def window_value(_hwnd, offset):
        if offset != n.GWLP_USERDATA:
            raise AssertionError("Unsupported cross-process WndProc query")
        calls[0] += 1
        if change == "empty":
            return 0
        return OBJECT + 8 if change == "userdata_race" and calls[0] > 1 else OBJECT

    observer._window_value = window_value
    return observer, process


CASES = {
    "valid": "menu", "bink": "waiting", "closing": "waiting",
    "starting": "waiting", "stopped": "waiting", "racing": "waiting",
    "backlink": "waiting", "code": "unsafe", "hash": "unsafe",
    "missing": "waiting", "loaded": "unsafe", "hidden": "waiting",
    "minimized": "waiting", "owner": "waiting", "destroyed": "waiting",
    "empty": "waiting", "userdata_race": "waiting", "unreadable": "waiting",
}
BAD_POINTERS = (0, -8, 1, 0x800000000000)


class NativeReadinessTests(unittest.TestCase):
    def test_eighteen_classifications_with_contract_and_handle_closure(self):
        for name, wanted in CASES.items():
            with self.subTest(case=name):
                observer, process = fixture(None if name == "valid" else name)
                result = observer.inspect(7)
                self.assertEqual(result["state"], wanted)
                self.assertEqual(process.closed, 1)
                self.assertIs(result["menu_proof_verified"], wanted == "menu")
                self.assertNotIn("native_window_proc_verified", result["positive_flags"])
                if name == "valid":
                    self.assertEqual(result["frame_pointer"], OBJECT)
                    self.assertEqual(result["frame_pointer"], result["userptr"])
                    self.assertEqual(result["identity"], dict(pid=7, creation_time=123, path=EXE))
                    self.assertIs(result["positive_flags"]["ownership_read_twice"], True)
                    self.assertEqual((result["field8"], result["field2210"], result["field2218"]), (0, -1, 1))

    def test_four_invalid_pointer_rejections(self):
        for pointer in BAD_POINTERS:
            with self.subTest(pointer=pointer):
                with self.assertRaises(ValueError):
                    n._snapshot(FakeProcess(None), pointer)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(NativeReadinessTests))
    report = dict(status="PASS" if result.wasSuccessful() else "FAIL", automated_only=True,
                  actual_game_run=False, mocked_process_and_window_memory=True,
                  readiness_classification_cases=18, invalid_pointer_cases=4,
                  unittest_methods=result.testsRun, source_sha256=sha(Path(n.__file__)),
                  test_source_sha256=sha(Path(__file__)),
                  case_expectations=CASES, invalid_pointers=list(BAD_POINTERS),
                  safety_checks=["No cross-process WndProc query", "No native export execution",
                                 "No process/window enumeration or real memory access",
                                 "Every fake process handle closed", "Proof flag and pointer aliases match policy"])
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    else:
        print(json.dumps(report, indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
