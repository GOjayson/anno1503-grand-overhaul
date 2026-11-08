"""Execute original record decoding, placement bounds, HEAD dimensions and rotation.

No game process. Synthetic object/stack buffers and explicit definition-vtable
bindings stand at native object boundaries; no production or navigation runs.
"""
from pathlib import Path
import hashlib
import json
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE.parent / 'engine_audit'))
from audit import Module
from unicorn import Uc, UC_ARCH_X86, UC_MODE_64, UC_HOOK_CODE
from unicorn.x86_const import *

W = Module(str(ROOT / 'AnnoWelt.dll'))
G = Module(str(ROOT / 'AnnoGame.dll'))
EXPECTED = {'AnnoWelt.dll': 'ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9',
            'AnnoGame.dll': 'e6f01d19e8e16e6716c0a6c7d3ba00273c9df493e051b8ba62865ee4b53dfdea'}
for module in (W, G):
    assert hashlib.sha256(module.data).hexdigest() == EXPECTED[Path(module.name).name]
    assert module.pe.FILE_HEADER.Machine == 0x8664 and module.pe.OPTIONAL_HEADER.Magic == 0x20b

OBJ, STACK, STOP = 0x40000000, 0x50000000, 0x60000000
RSP, RBP = STACK + 0x1000, STACK + 0x4000


def machine(base):
    u = Uc(UC_ARCH_X86, UC_MODE_64)
    for module, address in ((W, base), (G, base + 0x10000000)):
        u.mem_map(address, (len(module.image) + 4095) & ~4095)
        u.mem_write(address, module.image)
    u.mem_map(OBJ, 0x10000)
    u.mem_map(STACK, 0x10000)
    u.mem_map(STOP, 4096)
    u.reg_write(UC_X86_REG_RSP, RSP)
    u.reg_write(UC_X86_REG_RBP, RBP)
    u.reg_write(UC_X86_REG_RSI, OBJ)
    u.reg_write(UC_X86_REG_R13, 0x3fff)
    return u


def run(u, start, stops):
    visited = []
    def boundary(uc, address, size, user):
        if address in stops:
            visited.append(address)
            uc.emu_stop()
    hook = u.hook_add(UC_HOOK_CODE, boundary)
    u.emu_start(start, 0, count=1000)
    u.hook_del(hook)
    assert len(visited) == 1, (hex(start), hex(u.reg_read(UC_X86_REG_RIP)))
    return visited[0]


def decode_case(base, rotation, dx, dy, island_x, island_y, tile_x, tile_y, ident, flags, stage):
    u = machine(base)
    u.mem_write(OBJ + 8, struct.pack('<4H', island_x, island_y, 64, 64))
    u.mem_write(RSP + 0x30, struct.pack('<HHBB', tile_x, tile_y, 32, 32))
    u.mem_write(RBP + 0x10a8, struct.pack('<HBBbb', ident | (rotation << 14), flags, stage, dx, dy))
    x, y = (tile_x + dx) & 0xffff, (tile_y + dy) & 0xffff
    expected = struct.pack('<HHHBBB', ident, x, y, rotation, flags & 63, stage)
    # Original GELAENDE decoder; the following short block applies low6 flags.
    run(u, base + 0x4b6f8, {base + 0x4b740})
    run(u, base + 0x4b75f, {base + 0x4b76c})
    assert bytes(u.mem_read(RSP + 0x38, 9)) == expected
    # Original PROD2 decoder and actual native anchor-in-island decision.
    u.mem_write(RSP + 0x38, b'\0' * 16)
    stop = run(u, base + 0x4ba50, {base + 0x4bacf, base + 0x4bae6})
    assert bytes(u.mem_read(RSP + 0x38, 9)) == expected
    inside = island_x <= x < island_x + 64 and island_y <= y < island_y + 64
    assert (stop == base + 0x4bacf) == inside
    return dict(base=hex(base), rotation=rotation, id=ident, offset=[dx, dy],
                island=[island_x, island_y], tile=[tile_x, tile_y], accepted=inside)


def dimensions_case(base, width, height, rotation):
    u = machine(base)
    game_base = base + 0x10000000
    # Original HEAD loader reads first two serialized bytes into +a/+b.
    u.mem_write(RSP + 0x40, bytes((width, height)) + b'\0' * 54)
    run(u, game_base + 0x2a96, {game_base + 0x2aa6})
    assert bytes(u.mem_read(OBJ + 0xa, 2)) == bytes((width, height))
    # Explicit synthetic definition-vtable boundary, bound to reviewed methods.
    # Original production getters choose a8/b0 according to rotation parity.
    definition, table, production = OBJ, OBJ + 0x1000, OBJ + 0x2000
    u.mem_write(definition, struct.pack('<Q', table))
    u.mem_write(table + 0xa8, struct.pack('<QQ', game_base + 0x10a0, game_base + 0x10b0))
    u.mem_write(production + 0x20, struct.pack('<Q', definition))
    u.mem_write(production + 0x10, bytes((rotation,)))
    results = []
    for entry in (0x831e0, 0x83200):
        u.mem_write(RSP, struct.pack('<Q', STOP))
        u.reg_write(UC_X86_REG_RSP, RSP)
        u.reg_write(UC_X86_REG_RCX, production)
        run(u, base + entry, {STOP})
        results.append(u.reg_read(UC_X86_REG_RAX))
    assert results == ([height, width] if rotation & 1 else [width, height])
    return dict(base=hex(base), dimensions=[width, height], rotation=rotation, native_results=results)


def main():
    table_assertions = []
    for vt in (0x1f888, 0x1fac8, 0x1fcf8):
        for slot, method in ((0xa8, 0x10a0), (0xb0, 0x10b0)):
            assert struct.unpack_from('<Q', G.image, vt + slot)[0] - G.base == method
            table_assertions.append(dict(vtable=hex(vt), slot=hex(slot), method=hex(method)))
    cases, dims = [], []
    vectors = [(0, 0, 0, 0, -128, 0), (0, 0, 0, 0, -1, 0),
               (0, 0, 0, 0, 0, -1), (0, 0, 0, 0, 0, 0),
               (0, 0, 32, 32, 31, 31), (0, 0, 32, 32, 32, 0),
               (0, 0, 32, 32, 0, 32), (0, 0, 32, 32, 127, 127),
               (160, 240, 192, 272, -32, -32), (160, 240, 192, 272, 31, 31),
               (160, 240, 192, 272, -33, 0), (160, 240, 192, 272, 0, 32)]
    for base in (0x180000000, 0x280000000):
        for rotation in range(4):
            for i, (ix, iy, tx, ty, dx, dy) in enumerate(vectors):
                cases.append(decode_case(base, rotation, dx, dy, ix, iy, tx, ty,
                                         [0, 1, 105, 3506, 16383][i % 5],
                                         [0, 63, 255][i % 3], [0, 48, 255][i % 3]))
            for width, height in ((1, 1), (3, 4), (4, 3), (32, 64), (255, 1)):
                dims.append(dimensions_case(base, width, height, rotation))
    result = dict(scope=__doc__, fingerprints=EXPECTED, native_vtable_assertions=table_assertions,
                  record_cases=cases, dimension_cases=dims,
                  original_native_paths_executed=len(cases) * 2 + len(dims) * 3)
    (HERE / 'placement_native_results.json').write_text(json.dumps(result, indent=2) + '\n')
    parts = [(W, 0x4b6f8, 0x4b740), (W, 0x4b75f, 0x4b76c),
             (W, 0x4ba50, 0x4bae6), (G, 0x2a96, 0x2aa6),
             (G, 0x10a0, 0x10ba), (W, 0x831e0, 0x8321e)]
    (HERE / 'placement_native.asm').write_text('\n\n'.join(Path(m.name).name + '\n' + m.dis(a, b) for m, a, b in parts))
    print(f'PASS: 96 record cases (terrain+production), 40 HEAD/rotated-dimension cases; {result["original_native_paths_executed"]} native paths at2bases; 6 vtable assertions.')


if __name__ == '__main__':
    main()
