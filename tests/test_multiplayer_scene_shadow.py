import ctypes
from ctypes import wintypes
from hashlib import sha256
import os
from pathlib import Path
from struct import pack, unpack
import subprocess
import tempfile
import unittest

from anno1503_overhaul.multiplayer_scene_frame import (
    FRAME_SHADOW_CALLS, SCENE_SHADOW_CALLS, verified_shadow_calls,
)


_NATIVE = Path(__file__).resolve().parents[1] / "src/anno1503_overhaul/native/multiplayer_menu"


def native_chunk(tag, payload):
    return tag.ljust(12, b"\0") + pack("<I", len(payload)) + payload


def native_scene(records, *, width=1024, height=None):
    head = native_chunk(b"HEAD", pack("<II", width, width if height is None else height) + bytes(24))
    return native_chunk(b"ANNO", native_chunk(b"SCENE", head + records))


_FIXTURE = r"""
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include "scene_shadow.h"

_Static_assert(__builtin_types_compatible_p(__typeof__(&AnnoTrialOpenScene), __typeof__(&CreateFileA)),
               "Scene-open callback must match the complete native ABI");

__declspec(dllexport) int ShadowFixtureArm(const WCHAR *file, uint64_t size, const unsigned char digest[32],
                                          const WCHAR *executable)
{
    return anno_shadow_arm_for_executable(file, size, digest, executable);
}

__declspec(dllexport) void ShadowFixtureClear(void)
{
    anno_shadow_clear();
}

__declspec(dllexport) DWORD ShadowFixtureWidth(void)
{
    return anno_shadow_world_width();
}

__declspec(dllexport) int ShadowFixtureSelection(LPCSTR directory, LPCSTR scenario)
{
    return anno_shadow_selection_allowed(directory, scenario);
}
"""


class SceneShadowSiteTests(unittest.TestCase):
    def test_all_site_preimages_are_complete_native_create_file_calls(self):
        for calls, destination in ((FRAME_SHADOW_CALLS, 0x9E3E0), (SCENE_SHADOW_CALLS, 0x35058)):
            for address, before, name in calls:
                with self.subTest(address=hex(address)):
                    self.assertEqual((len(before), before[:2], name), (6, b"\xff\x15", "AnnoTrialOpenScene"))
                    self.assertEqual(address + 6 + unpack("<i", before[2:])[0], destination)

    def test_refuses_unknown_or_modified_input(self):
        for module in ("AnnoFrame.dll", "AnnoScene.dll", "Unknown.dll"):
            with self.subTest(module=module), self.assertRaisesRegex(ValueError, "reviewed History Edition"):
                verified_shadow_calls(module, b"MZ" + bytes(1024))

    def test_matches_pinned_stock_images_when_available(self):
        variables = {"AnnoFrame.dll": "ANNO_MULTIPLAYER_STOCK_FRAME", "AnnoScene.dll": "ANNO_MULTIPLAYER_STOCK_SCENE"}
        if not all(os.environ.get(variable) for variable in variables.values()):
            self.skipTest("Exact local stock multiplayer modules are unavailable.")
        for module, variable in variables.items():
            with self.subTest(module=module):
                original = Path(os.environ[variable]).read_bytes()
                self.assertTrue(verified_shadow_calls(module, original))
                derivative = original[:-1] + bytes([original[-1] ^ 1])
                with self.assertRaisesRegex(ValueError, "reviewed History Edition"):
                    verified_shadow_calls(module, derivative)


@unittest.skipUnless(os.name == "nt", "The native adapter uses Windows file handles.")
class SceneShadowNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import _ctypes

        compiler = os.environ.get("ANNO_MULTIPLAYER_ZIG")
        if not compiler or not Path(compiler).is_file():
            raise unittest.SkipTest("The reviewed local Zig compiler is unavailable.")
        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        base = Path(temporary.name)
        source, output = base / "shadow_fixture.c", base / "shadow_fixture.dll"
        source.write_text(_FIXTURE, encoding="ascii")
        subprocess.run([compiler, "cc", "-target", "x86_64-windows-gnu", "-shared", "-O2", "-Wall", "-Wextra",
                        "-Werror", "-std=c11", "-I", str(_NATIVE), "-o", str(output), str(source), "-lbcrypt"],
                       check=True, capture_output=True)
        cls.native = ctypes.WinDLL(str(output), use_last_error=True)
        cls.addClassCleanup(_ctypes.FreeLibrary, cls.native._handle)
        cls.native.ShadowFixtureArm.argtypes = (wintypes.LPCWSTR, ctypes.c_uint64, ctypes.c_char_p, wintypes.LPCWSTR)
        cls.native.ShadowFixtureArm.restype = ctypes.c_int
        cls.native.ShadowFixtureClear.argtypes = ()
        cls.native.ShadowFixtureClear.restype = None
        cls.native.ShadowFixtureWidth.argtypes = ()
        cls.native.ShadowFixtureWidth.restype = wintypes.DWORD
        cls.native.ShadowFixtureSelection.argtypes = (wintypes.LPCSTR, wintypes.LPCSTR)
        cls.native.ShadowFixtureSelection.restype = ctypes.c_int
        cls.native.AnnoTrialOpenScene.argtypes = (wintypes.LPCSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                                  wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
        cls.native.AnnoTrialOpenScene.restype = wintypes.HANDLE

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.addCleanup(self.native.ShadowFixtureClear)
        self.copy = Path(temporary.name).resolve()
        self.stock = self.copy / "Scenes" / "0500MultiEndlos" / "NewEarth.sze"
        self.stock.parent.mkdir(parents=True)
        self.stock.write_bytes(b"stock scene")
        self.set_artifact(native_scene(native_chunk(b"NOTES", b"verified data " * 2048)))

    def set_artifact(self, data):
        self.artifact = data
        self.digest = sha256(self.artifact).digest()
        self.shadow = self.copy / "AnnoGrandMatches" / (self.digest.hex() + ".sze")
        self.shadow.parent.mkdir(exist_ok=True)
        self.shadow.write_bytes(self.artifact)

    def arm(self, *, path=None, size=None, digest=None):
        return self.native.ShadowFixtureArm(str(self.shadow if path is None else path),
                                           len(self.artifact) if size is None else size,
                                           self.digest if digest is None else digest,
                                           str(self.copy / "Anno1503.exe"))

    def open_native(self, path, *, access=0x80000000, share=1, disposition=3, flags=0x80):
        import msvcrt

        handle = self.native.AnnoTrialOpenScene(os.fspath(path).encode("mbcs"), access, share, None,
                                                disposition, flags, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        return os.fdopen(msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY), "rb", buffering=0)

    def test_same_pinned_artifact_is_read_by_both_native_open_abis(self):
        self.assertTrue(self.arm())
        with (self.open_native(self.stock) as first,
              self.open_native(self.stock, share=3, flags=0x08000080) as second):
            self.assertEqual(first.read(37), self.artifact[:37])
            self.assertEqual(second.read(), self.artifact)
            self.assertEqual(first.read(), self.artifact[37:])

            with self.assertRaises(PermissionError):
                self.shadow.write_bytes(b"mutated")
            with self.assertRaises(PermissionError):
                self.shadow.rename(self.shadow.with_name("renamed.sze"))
        self.assertEqual(self.stock.read_bytes(), b"stock scene")

    def test_other_paths_pass_through_when_armed_and_natively_open_after_clear(self):
        other = self.stock.with_name("Other.sze")
        other.write_bytes(b"other scene")
        sibling = self.copy / "Unrelated" / "NewEarth.sze"
        sibling.parent.mkdir()
        sibling.write_bytes(b"same name, different location")
        self.assertTrue(self.arm())
        for path, data in ((other, b"other scene"), (sibling, b"same name, different location")):
            with self.open_native(path) as stream:
                self.assertEqual(stream.read(), data)
        with self.assertRaises(PermissionError):
            self.open_native(self.stock, access=0x40000000, disposition=2)

        self.native.ShadowFixtureClear()
        with self.open_native(self.stock) as stream:
            self.assertEqual(stream.read(), b"stock scene")

    def test_invalid_input_keeps_stock_route(self):
        other = self.shadow.with_name("Wrong.sze")
        other.write_bytes(self.artifact)
        self.assertFalse(self.arm(path=other))
        self.assertFalse(self.arm(size=len(self.artifact) - 1))
        self.assertFalse(self.arm(size=16 * 1024 * 1024 + 1))
        self.shadow.write_bytes(b"\0" * len(self.artifact))
        self.assertFalse(self.arm())
        with self.open_native(self.stock) as stream:
            self.assertEqual(stream.read(), b"stock scene")

    def test_only_new_earth_can_be_selected_when_the_shadow_is_armed(self):
        directory = os.fspath(self.copy).encode("mbcs")
        new_earth = b"Scenes\\0500MultiEndlos\\NewEarth.sze"
        wrong_scene = b"Scenes\\0500MultiEndlos\\LastWager.sze"
        self.assertTrue(self.native.ShadowFixtureSelection(directory, wrong_scene))
        self.assertTrue(self.arm())
        self.assertTrue(self.native.ShadowFixtureSelection(directory, new_earth))
        self.assertFalse(self.native.ShadowFixtureSelection(directory, wrong_scene))
        self.assertFalse(self.native.ShadowFixtureSelection(directory, b".\\" + new_earth))

    def test_world_size_is_read_from_the_locked_native_header(self):
        self.assertEqual(self.native.ShadowFixtureWidth(), 0)
        self.set_artifact(native_scene(b"", width=2048))
        self.assertTrue(self.arm())
        self.assertEqual(self.native.ShadowFixtureWidth(), 2048)
        self.native.ShadowFixtureClear()
        self.assertEqual(self.native.ShadowFixtureWidth(), 0)
        for scene in (native_scene(b"", width=2048, height=1024), native_scene(b"", width=4096),
                      native_scene(native_chunk(b"HEAD", pack("<II", 2048, 2048) + bytes(24))),
                      native_chunk(b"ANNO", native_chunk(b"SCENE", b""))):
            self.set_artifact(scene)
            self.assertFalse(self.arm())

    def test_linked_island_must_match_and_stays_locked_until_clear(self):
        contents = b"stock-derived island"
        name = sha256(contents).hexdigest() + ".scp"
        island = self.copy / "Scenes" / "WS" / name
        island.parent.mkdir()
        link = bytes(12) + ("WS\\" + name).encode("ascii") + b"\0"
        self.set_artifact(native_scene(native_chunk(b"INSELLNK", link)))
        self.assertFalse(self.arm())
        island.write_bytes(b"wrong file")
        self.assertFalse(self.arm())
        island.write_bytes(contents)
        self.assertTrue(self.arm())
        with self.open_native(island, share=3, flags=0x08000080) as stream:
            self.assertEqual(stream.read(), contents)
        with self.assertRaises(PermissionError):
            island.write_bytes(b"replace")
        self.native.ShadowFixtureClear()
        island.write_bytes(b"replace")
        self.assertFalse(self.arm())

    def test_malformed_link_releases_other_verified_islands(self):
        contents = b"another island"
        name = sha256(contents).hexdigest() + ".scp"
        island = self.copy / "Scenes" / "WS" / name
        island.parent.mkdir()
        island.write_bytes(contents)
        link = bytes(12) + ("WS\\" + name).encode("ascii") + b"\0"
        self.set_artifact(native_scene(native_chunk(b"INSELLNK", link) + native_chunk(b"INSELLNK", link[:-1])))
        self.assertFalse(self.arm())
        island.write_bytes(b"ready for a new trial")


if __name__ == "__main__":
    unittest.main()
