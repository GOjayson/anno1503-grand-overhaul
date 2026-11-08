"""Read-only first-menu probe for the separately frozen World Settings build.

The native startup frame installs itself in the window's GWLP_USERDATA.  The
launcher therefore observes the active frame, rather than a cached heap object.
This is only a readiness gate: the unchanged native installer remains responsible
for the transactional no-existing-World and suspended-thread safety checks.
No export is called, no remote memory is written and no game input is generated.
"""
from __future__ import annotations

import argparse
import ctypes as C
from ctypes import wintypes as W
import importlib
import json
import os
from pathlib import Path
import struct
import sys


FRAME_SHA256 = "046b5ad6f351dfe867ed38ce29fb50a594485b43a32ee90adadc48e850466baf"
SPLASH_VTABLE = 0xA5818
BINK_VTABLE = 0xA30F0
BASE_VTABLE = 0xA2660
STARTUP_WNDPROC = 0x3A960
GWLP_USERDATA = -21
GWLP_WNDPROC = -4
# Original HE/Food Frame instructions, independent of ASLR and unchanged by v4.
# 3c980: HWND=[this+2220], GWLP_USERDATA=-21, value=this;
#        then HWND=[this+2220], GWLP_WNDPROC=-4, value=Frame+3a960.
FRAME_EVIDENCE = {
    0x3C991: bytes.fromhex("488b8e202200004c8bc6baebffffffff15221c0600"),
    0x3C9BD: bytes.fromhex("488b8e202200004c8d0595dfffffbafcffffffff15f21b0600"),
    # Splash's post-intro path enters the ordinary base message/menu loop.
    0x5454A: bytes.fromhex("e8e175feff"),
    # Base loop marks itself active, then tests a requested start transition.
    0x3BC8E: bytes.fromhex("c683182200000183f802"),
}


def _activation(package: Path):
    activation = (package / "activation").resolve(strict=True)
    path = str(activation)
    if path in sys.path:
        sys.path.remove(path)
    sys.path.insert(0, path)
    module = importlib.import_module("activate_world_settings")
    expected = activation / "activate_world_settings.py"
    if Path(module.__file__).resolve(strict=True) != expected:
        raise RuntimeError("Another activation helper was already imported; restart the launcher.")
    for name in ("preflight", "module_checks", "pe_exports", "preview_snapshot"):
        imported = sys.modules.get(name)
        if imported is None or Path(imported.__file__).resolve(strict=True) != activation / (name + ".py"):
            raise RuntimeError("Activation helper identity differs: " + name)
    return module


def _window_api():
    user = C.WinDLL("user32", use_last_error=True)
    enum_callback = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)

    def bind(name, args, result):
        fn = getattr(user, name)
        fn.argtypes = args
        fn.restype = result
        return fn

    return dict(
        callback=enum_callback,
        enum=bind("EnumWindows", [enum_callback, W.LPARAM], W.BOOL),
        pid=bind("GetWindowThreadProcessId", [W.HWND, C.POINTER(W.DWORD)], W.DWORD),
        # USERDATA is readable across processes. Windows denies reading another
        # process's GWLP_WNDPROC, so the probe never queries that unsupported slot.
        get=bind("GetWindowLongPtrA", [W.HWND, C.c_int], C.c_ssize_t),
        visible=bind("IsWindowVisible", [W.HWND], W.BOOL),
        iconic=bind("IsIconic", [W.HWND], W.BOOL),
        valid=bind("IsWindow", [W.HWND], W.BOOL),
    )


def _snapshot(session, pointer: int):
    """Only exact bounded fields; failure means an object changed while read."""
    if pointer <= 0 or pointer >= (1 << 47) or pointer & 7:
        raise ValueError("Window userdata is not an aligned native object pointer.")
    head = session.read(pointer, 9)
    state = session.read(pointer + 0x2210, 0x18)
    return dict(
        vtable=struct.unpack_from("<Q", head)[0],
        field8=head[8],
        field2210=struct.unpack_from("<i", state)[0],
        field2218=state[8],
        hwnd_backlink=struct.unpack_from("<Q", state, 0x10)[0],
    )


class NativeReadiness:
    """Read-only Windows observer; caller owns stable samples and one attempt.

    ``inspect`` returns waiting/menu/unsafe and does not perform installation.
    A menu result must be repeated for the same PID, creation time, HWND and
    userdata by the launcher.  Any activation invocation ends the polling phase;
    an unsuccessful/uncertain invocation must never be retried in that process.
    """

    def __init__(self, package, inputs):
        if os.name != "nt" or C.sizeof(C.c_void_p) != 8:
            raise RuntimeError("Use 64-bit Windows Python for the read-only menu probe.")
        self.package = Path(package).resolve(strict=True)
        self.inputs = inputs
        self.a = _activation(self.package)
        self.windows = _window_api()
        self._hashes = {}
        frame = [value for name, value in inputs["native_sha256"].items()
                 if name.lower() == "annoframe.dll"]
        if frame != [FRAME_SHA256]:
            raise RuntimeError("This launcher supports only the inspected Food/History Frame module.")

    def close(self):
        # Every inspection closes its own read-only process handle.
        self._hashes.clear()

    def processes(self):
        return self.a.all_processes()

    def _sha(self, path):
        path = Path(path).resolve(strict=True)
        stat = path.stat()
        key = (os.path.normcase(str(path)), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        if key not in self._hashes:
            digest = self.a.sha(path)
            after = path.stat()
            if (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns) != (
                    after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise OSError("A native file changed while its identity was checked.")
            self._hashes[key] = digest
        return self._hashes[key]

    def _owned_windows(self, pid):
        values = []

        @self.windows["callback"]
        def visit(hwnd, _):
            owner = W.DWORD()
            if self.windows["pid"](hwnd, C.byref(owner)) and owner.value == pid:
                values.append(int(hwnd))
            return True

        C.set_last_error(0)
        if not self.windows["enum"](visit, 0):
            raise OSError(C.get_last_error(), "Enumerate game windows")
        return values

    def _window_value(self, hwnd, offset):
        C.set_last_error(0)
        value = self.windows["get"](hwnd, offset)
        error = C.get_last_error()
        if not value and error:
            raise OSError(error, "Read game window ownership")
        return value & ((1 << 64) - 1)

    def inspect(self, pid):
        result = dict(state="waiting", pid=int(pid), reason="Game startup is not ready.",
                      identity=None, hwnd=None, userptr=None, vtable_rva=None,
                      field8=None, field2210=None, field2218=None,
                      frame_pointer=None, menu_proof_verified=False,
                      positive_flags={}, windows=[])
        session = None

        def finish(state, reason):
            result.update(state=state, reason=reason)
            return result

        try:
            session = self.a.Session(int(pid), False)
            path = C.create_unicode_buffer(32768)
            length = W.DWORD(len(path))
            self.a.check(self.a.query_path(session.handle, 0, path, C.byref(length)), "Read game path")
            created = self.a.creation_time(session.handle)
            result["identity"] = dict(pid=int(pid), creation_time=created, path=path.value)
            result["process_creation_time"] = created
            result["path"] = path.value
            expected = Path(self.inputs["source"]) / "Anno1503.exe"
            if not self.a.same(path.value, expected) or self._sha(path.value) != self.inputs["exe_sha256"]:
                return finish("unsafe", "The Anno process path or executable fingerprint differs.")
            result["positive_flags"]["executable_identity_verified"] = True

            modules = self.a.modules(int(pid))
            if any(m["name"].lower() == "annoworldsettings.dll" for m in modules["__all__"]):
                return finish("unsafe", "World Settings is already loaded; activation will not be retried.")
            result["positive_flags"]["runtime_absent"] = True
            required = self.a.verify_modules.__globals__["REQUIRED_NATIVE"]
            missing = sorted(required - set(modules))
            if missing:
                return finish("waiting", "Native game modules are still loading: " + ", ".join(missing))
            try:
                self.a.verify_modules(modules, self.inputs, self.a.same, self._sha)
            except RuntimeError as error:
                return finish("unsafe", str(error))
            result["positive_flags"]["native_modules_verified"] = True
            frame = modules["annoframe.dll"]
            base = frame["base"]
            if self._sha(frame["path"]) != FRAME_SHA256 or frame["size"] <= SPLASH_VTABLE + 0x178:
                return finish("unsafe", "The active Frame module differs from the inspected architecture.")
            for rva, expected_bytes in FRAME_EVIDENCE.items():
                if session.read(base + rva, len(expected_bytes)) != expected_bytes:
                    return finish("unsafe", "Native startup frame instructions differ from the inspected build.")
            # Bind the primary vtable to the exact Splash activation method.
            if session.read(base + SPLASH_VTABLE + 0x170, 8) != struct.pack("<Q", base + 0x57A60):
                return finish("unsafe", "The native main-menu vtable differs from the inspected build.")
            result["positive_flags"]["frame_instructions_verified"] = True
            result["positive_flags"]["native_window_userdata_setter_verified"] = True

            candidates = []
            for hwnd in self._owned_windows(int(pid)):
                row = dict(hwnd=hwnd, userptr=None, vtable_rva=None,
                           field8=None, field2210=None, field2218=None)
                result["windows"].append(row)
                if not self.windows["visible"](hwnd) or self.windows["iconic"](hwnd):
                    row["reason"] = "Window is hidden or minimized."
                    continue
                pointer = self._window_value(hwnd, GWLP_USERDATA)
                row.update(userptr=pointer)
                if not pointer:
                    row["reason"] = "Native startup window has not become active."
                    continue
                snap = _snapshot(session, pointer)
                row.update(snap)
                row["vtable_rva"] = snap["vtable"] - base
                if snap["hwnd_backlink"] != hwnd:
                    row["reason"] = "Startup frame window backlink changed."
                    continue
                if snap["vtable"] != base + SPLASH_VTABLE:
                    row["reason"] = ("Intro video is active." if snap["vtable"] == base + BINK_VTABLE
                                     else "Another startup screen is active.")
                    continue
                if snap["field8"] != 0 or snap["field2210"] != -1 or snap["field2218"] != 1:
                    row["reason"] = "Main-menu loop is transitioning or closing."
                    continue
                owner = W.DWORD()
                stable = (self.windows["valid"](hwnd)
                          and self.windows["pid"](hwnd, C.byref(owner))
                          and owner.value == int(pid)
                          and self._window_value(hwnd, GWLP_USERDATA) == pointer
                          and _snapshot(session, pointer) == snap)
                if not stable:
                    row["reason"] = "Native menu ownership changed while read."
                    continue
                row["reason"] = "Active native main-menu loop."
                candidates.append(row)

            if len(candidates) > 1:
                return finish("unsafe", "Multiple active native main-menu windows are ambiguous.")
            if not candidates:
                return finish("waiting", "Waiting for the visible native main menu after the intro.")
            selected = candidates[0]
            for name in ("hwnd", "userptr", "vtable_rva", "field8", "field2210", "field2218"):
                result[name] = selected[name]
            result["frame_pointer"] = selected["userptr"]
            result["menu_proof_verified"] = True
            result["positive_flags"].update(active_splash_vtable_verified=True,
                                            window_backlink_verified=True,
                                            menu_loop_active=True,
                                            ownership_read_twice=True)
            return finish("menu", "Native main menu is active; require a second stable sample before one activation attempt.")
        except (OSError, ValueError, struct.error) as error:
            return finish("waiting", "Startup observation is incomplete: " + str(error))
        finally:
            if session is not None:
                self.a.close(session.handle)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", action="store_true", help="Print one read-only observation of every Anno candidate")
    parser.add_argument("--package", type=Path,
                        default=Path(__file__).resolve().parents[1] / "anno1503_food_world_dev8")
    parser.add_argument("--game-dir", type=Path, help="Explicit installed marked copy")
    args = parser.parse_args()
    if not args.probe:
        parser.error("Use --probe; this module never activates or controls the game.")
    package = args.package.resolve(strict=True)
    activation = _activation(package)
    inputs = activation.verify(args.game_dir)
    observer = NativeReadiness(package, inputs)
    try:
        ids = observer.processes()
        print(json.dumps(dict(read_only=True, package=str(package),
                              processes=[observer.inspect(pid) for pid in ids]), indent=2))
    finally:
        observer.close()


if __name__ == "__main__":
    main()
