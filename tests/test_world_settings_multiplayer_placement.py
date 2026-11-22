"""Regression for the native construction layer and Reveal all activity."""

import os
from pathlib import Path
import re
from struct import pack, unpack
import unittest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "src/anno1503_overhaul/native/world_settings_multiplayer/visibility_multiplayer_install.inc"
PREVIEW = (1023, 1024)
LIVE = (1302, 1303)


def activity_leaves():
    table = INSTALLER.read_text(encoding="ascii").split("wsMpActivityBranches[] = {", 1)[1].split("};", 1)[0]
    pattern = r"\{(0x[0-9a-f]+)u,\s*(\d+),\s*(\d+),\s*\{([^}]*)\},\s*\{([^}]*)\}\}"
    for address, length, leaf_length, before, leaf in re.findall(pattern, table):
        original, replacement = (bytes(int(value, 0) for value in row.split(",")) for row in (before, leaf))
        yield int(address, 16), int(length), int(leaf_length), original, replacement


class PlacementTileTests(unittest.TestCase):
    def test_reveal_activity_keeps_the_native_construction_preview(self):
        source = os.environ.get("ANNO_MULTIPLAYER_STOCK_WORLD")
        if not source:
            self.skipTest("The reviewed local AnnoWelt.dll fixture is unavailable.")
        try:
            import pefile
            import unicorn as U
            from unicorn import x86_const as X
        except ImportError as error:
            self.skipTest(str(error))

        pe = pefile.PE(source, fast_load=True)
        base, image = pe.OPTIONAL_HEADER.ImageBase, pe.get_memory_mapped_image()
        patch = tuple(activity_leaves())
        self.assertEqual(tuple(row[0] for row in patch), (0xC96CE, 0xC9707, 0xC9A80))
        cases = (
            (False, 0, True, PREVIEW),
            (False, 1, True, (PREVIEW[0], 0)),
            (True, 0, True, PREVIEW),
            (True, 1, True, (PREVIEW[0], 0)),
            (True, 0x80, True, PREVIEW),
            (True, 0x81, True, (PREVIEW[0], LIVE[1])),
            (True, 0, False, (0, 0)),
            (True, 0x80, False, LIVE),
            (True, 0x81, False, LIVE),
        )
        for patched, flags, has_layer, expected in cases:
            with self.subTest(patched=patched, flags=flags, has_layer=has_layer):
                u = U.Uc(U.UC_ARCH_X86, U.UC_MODE_64)
                u.mem_map(base, 0x200000)
                u.mem_write(base, image)
                if patched:
                    for index, (rva, length, leaf_length, original, leaf) in enumerate(patch):
                        self.assertEqual(image[rva:rva + length], original)
                        self.assertEqual(len(leaf), leaf_length)
                        bridge = 0x1F0000 + index * 32
                        u.mem_write(base + bridge, leaf)
                        u.mem_write(base + rva, b"\xe8" + pack("<i", bridge - rva - 5) + b"\x90" * (length - 5))
                self.assertEqual(self.project(u, X, base, flags, has_layer), expected)

    def project(self, u, registers, base, flags, has_layer):
        world = 0x200000000
        island, row, tiles, layer, output = (world + n for n in (0x8000, 0xA000, 0xC000, 0xD000, 0xE000))
        catalogue, definition, stubs = world + 0xF000, world + 0x11000, world + 0x13000
        stop, stack = world + 0x14000, world + 0x1F008
        u.mem_map(world, 0x20000)

        def pointer(address, value):
            u.mem_write(address, pack("<Q", value))

        pointer(world + 0x6640, island)
        pointer(world + 0x200, catalogue)
        pointer(island, base + 0xF33E8)
        pointer(island + 0x10, tiles)
        u.mem_write(island + 0xC, pack("<HH", 8, 8))
        u.mem_write(island + 0x110, pack("<II", 1, 1))
        pointer(island + 0x118, row)
        if has_layer:
            u.mem_write(row + 8, b"\x20")
            pointer(row + 0x10, layer)
        pointer(layer, base + 0xF33B8)
        u.mem_write(layer + 0x228, b"\x02")  # Let the native Boolean choose tile 1's source.
        u.mem_write(layer + 0x230, b"\x05")
        physical = b"".join(pack("<II", 0x80000000 | item, 0x80000430) for item in LIVE) + bytes(62 * 8)
        preview = b"".join(pack("<II", 0x80000000 | item, 0x00000430) for item in PREVIEW) + bytes(62 * 8)
        u.mem_write(tiles, physical)
        u.mem_write(layer + 0x14, preview)

        # Synthetic catalogue getter, stock building kind, and empty frame query.
        pointer(catalogue, catalogue + 0x1000)
        pointer(catalogue + 0x1000 + 0xE8, stubs)
        pointer(definition, definition + 0x1000)
        pointer(definition + 0x1000 + 0xC0, stubs + 0x10)
        pointer(definition + 0x1000 + 0x150, stubs + 0x20)
        u.mem_write(stubs, b"\x48\xb8" + pack("<Q", definition) + b"\xc3")
        u.mem_write(stubs + 0x10, b"\xb8\x23\0\0\0\xc3")
        u.mem_write(stubs + 0x20, b"\x31\xc0\xc3")
        pointer(stack, stop)
        pointer(stack + 0x28, output)
        for register, value in ((registers.UC_X86_REG_RSP, stack), (registers.UC_X86_REG_RCX, world),
                                (registers.UC_X86_REG_RDX, row), (registers.UC_X86_REG_R8, 0),
                                (registers.UC_X86_REG_R9, flags)):
            u.reg_write(register, value)
        u.emu_start(base + 0xC9400, stop, count=75000)
        self.assertEqual(u.reg_read(registers.UC_X86_REG_RIP), stop)
        self.assertEqual(u.mem_read(tiles, len(physical)), physical)
        self.assertEqual(u.mem_read(layer + 0x14, len(preview)), preview)
        return tuple(unpack("<H", u.mem_read(output + 8 + i * 8, 2))[0] for i in range(2))


if __name__ == "__main__":
    unittest.main()
