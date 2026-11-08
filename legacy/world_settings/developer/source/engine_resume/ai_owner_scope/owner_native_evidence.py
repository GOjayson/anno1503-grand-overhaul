"""Original native house -> city -> owner/type evidence in private Unicorn maps.

Synthetic objects; original reviewed AMD64 code and relocated vtables. No game
process, runtime edit, needs clone, policy hook, harvest or AI simulation.
"""
from pathlib import Path
import hashlib
import json
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WORK = ROOT / 'WorldSettings_Work'
sys.path.insert(0, str(WORK / 'engine_audit'))
sys.path.insert(0, str(WORK / 'world_data'))
sys.path.insert(0, str(WORK / 'world_certificate'))
from audit import Module
from scene_catalogue import read_container, chunks
from unicorn import Uc, UC_ARCH_X86, UC_MODE_64, UC_HOOK_CODE
from unicorn.x86_const import *

EXPECTED = 'ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9'
W = Module(str(ROOT / 'AnnoWelt.dll'))
assert hashlib.sha256(W.data).hexdigest() == EXPECTED
assert W.pe.FILE_HEADER.Machine == 0x8664 and W.pe.OPTIONAL_HEADER.Magic == 0x20b
HOUSE, CITY, PLAYER, NEEDS, OUTPUT = 0x40000000, 0x40001000, 0x40002000, 0x40003000, 0x40004000
STACK, STOP = 0x50000000, 0x60000000


def machine(base, house_vtable, player_id, player_type):
    image = bytearray(W.image)
    delta = base - W.base
    if delta:
        for block in W.pe.DIRECTORY_ENTRY_BASERELOC:
            for entry in block.entries:
                if entry.type == 10:
                    old = struct.unpack_from('<Q', image, entry.rva)[0]
                    struct.pack_into('<Q', image, entry.rva, (old + delta) & 0xffffffffffffffff)
                else:
                    assert entry.type == 0
    u = Uc(UC_ARCH_X86, UC_MODE_64)
    u.mem_map(base, (len(image) + 4095) & ~4095)
    u.mem_write(base, bytes(image))
    u.mem_map(HOUSE, 0x10000)
    u.mem_map(STACK, 0x10000)
    u.mem_map(STOP, 4096)
    for address, value in [(HOUSE, base + house_vtable), (HOUSE + 0x18, CITY),
                           (HOUSE + 0x48, NEEDS), (CITY, base + 0xfc678),
                           (CITY + 0x28, PLAYER), (PLAYER, base + 0xfabe0)]:
        u.mem_write(address, struct.pack('<Q', value))
    u.mem_write(PLAYER + 8, struct.pack('<I', player_id))
    u.mem_write(PLAYER + 0x9c, struct.pack('<H', player_type))
    u.mem_write(NEEDS, bytes([0xa5]) * 0x140)
    return u


def invoke(u, base, rva, obj, a=0, b=0):
    rsp = STACK + 0xf008
    u.mem_write(rsp, struct.pack('<Q', STOP))
    for reg, value in [(UC_X86_REG_RSP, rsp), (UC_X86_REG_RCX, obj),
                       (UC_X86_REG_RDX, a), (UC_X86_REG_R8, b)]:
        u.reg_write(reg, value)
    trace = []
    def visit(uc, address, size, _):
        if address in (base + 0x84ff0, base + 0x8ca0, base + 0xa28e0,
                       base + 0x8d00, base + 0x1fa50, base + 0x87e40):
            trace.append(hex(address - base))
    hook = u.hook_add(UC_HOOK_CODE, visit)
    u.emu_start(base + rva, STOP, count=10000)
    u.hook_del(hook)
    assert u.reg_read(UC_X86_REG_RIP) == STOP
    return u.reg_read(UC_X86_REG_RAX), trace


def stock_head_types():
    result = []
    for name in ('01_1024_easy_256.sze', '03_1024_med_256.sze', '06_1024_heavy_256.sze'):
        path = ROOT / 'Languages/Nl/Scenes/0010SingleEndlos' / name
        data = path.read_bytes()
        root, _ = read_container(data)
        players = []
        for part in chunks(data, 32, root.end):
            if part.tag != 'SPIELER':
                continue
            player_id = struct.unpack_from('<I', part.payload, 4)[0]
            if part.payload[8:14] == b'HEAD\0\0':
                size = struct.unpack_from('<H', part.payload, 14)[0]
                body = part.payload[16:16 + size]
                assert size == len(body) == 0x6c
                kind = struct.unpack_from('<H', body)[0]
                if player_id == 0:
                    assert kind == 0xb
                if 1 <= player_id <= 4:
                    assert kind == 0xc
                players.append(dict(id=player_id, serialized_type=kind))
        result.append(dict(path=str(path.relative_to(ROOT)), sha256=hashlib.sha256(data).hexdigest(), players=players))
    return result


def main():
    bindings = [(0xf9c88, 0x40, 0x84ff0), (0xf9ee8, 0x40, 0x84ff0),
                (0xfc678, 0x40, 0x8ca0), (0xfabe0, 0x98, 0xa28e0),
                (0xfabe0, 0x88, 0x8d00), (0xf9c88, 0x110, 0x87e40),
                (0xf9ee8, 0x110, 0x88ed0), (0xf9c88, 0x118, 0x1fa50),
                (0xf9ee8, 0x118, 0x1fa50)]
    for vt, slot, expected in bindings:
        assert struct.unpack_from('<Q', W.image, vt + slot)[0] - W.base == expected
    cases = []
    for base in (0x180000000, 0x280000000):
        for house_vt in (0xf9c88, 0xf9ee8):
            # Crossed IDs/types prove the type decision is not a slot-ID guess.
            for player_id, player_type in ((0, 11), (1, 12), (4, 12), (1, 11),
                                            (0, 12), (8, 14), (6, 15), (5, 16)):
                u = machine(base, house_vt, player_id, player_type)
                before = bytes(u.mem_read(NEEDS, 0x140))
                owner, trace = invoke(u, base, 0x84ff0, HOUSE)
                assert owner == PLAYER and trace == ['0x84ff0', '0x8ca0']
                ok, _ = invoke(u, base, 0xa28e0, owner, 9, OUTPUT)
                assert ok == 1 and struct.unpack('<I', bytes(u.mem_read(OUTPUT + 8, 4)))[0] == player_type
                ident, _ = invoke(u, base, 0x8d00, owner)
                assert ident == player_id
                needs, _ = invoke(u, base, 0x1fa50, HOUSE)
                assert needs == NEEDS and bytes(u.mem_read(NEEDS, 0x140)) == before
                # Original base setter has no owner dependency and no shared edit.
                clone_pointer = NEEDS + 0x200
                invoke(u, base, 0x87e40, HOUSE, clone_pointer)
                assigned, _ = invoke(u, base, 0x1fa50, HOUSE)
                assert assigned == clone_pointer and bytes(u.mem_read(NEEDS, 0x140)) == before
                # Original loader block copies serialized HEAD type to +9c.
                rbp = STACK + 0x4000
                u.reg_write(UC_X86_REG_RBP, rbp)
                u.reg_write(UC_X86_REG_R13, PLAYER)
                u.mem_write(rbp + 0x20, struct.pack('<H', player_type))
                u.emu_start(base + 0x9bec2, base + 0x9bed3, count=10)
                assert struct.unpack('<H', bytes(u.mem_read(PLAYER + 0x9c, 2)))[0] == player_type
                cases.append(dict(base=hex(base), house_vtable=hex(house_vt), owner_id=ident,
                                  owner_type=player_type, original_shared_needs=True,
                                  independent_house_assignment=True, original_getter_chain=trace))
    report = dict(scope=__doc__, welt_sha256=EXPECTED,
                  exact_vtable_bindings=[dict(vtable=hex(vt), slot=hex(slot), method=hex(fn)) for vt, slot, fn in bindings],
                  cases=cases, original_native_invocations=len(cases) * 7,
                  stock_player_head_types=stock_head_types())
    (HERE / 'owner_native_results.json').write_text(json.dumps(report, indent=2) + '\n')
    slices = [(0x84ff0, 0x84ffb), (0x8ca0, 0x8ca5), (0xa28e0, 0xa294c),
              (0x9bec2, 0x9bed3), (0x87e40, 0x87e45), (0x1fa50, 0x1fa55),
              (0x885e6, 0x8864e), (0x89225, 0x89243)]
    (HERE / 'owner_native.asm').write_text('\n\n'.join(W.dis(a, b) for a, b in slices))
    print(f'PASS:{len(cases)} owner/house cases x7 native paths at2bases;9 exact vtable bindings;3 stock scene HEAD audits.')


if __name__ == '__main__':
    main()
