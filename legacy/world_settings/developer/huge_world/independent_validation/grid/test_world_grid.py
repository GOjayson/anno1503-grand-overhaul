"""Native instruction emulation and strict image transform checks.

Unicorn executes exact patched History Edition instructions. External CRT/API
calls and unrelated service notifications use explicit fixture stubs. This is
an automated engine component test, not a real Anno run.
"""
from pathlib import Path
import json
import random
import struct
import sys
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'WorldSettings_Work/_tools'))
import world_grid_patch as patch
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_MEM
from unicorn import Uc, UC_ARCH_X86, UC_MODE_64, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
import unicorn.x86_const as xr

OBJ = 0x40001000
STACK = 0x50000000
FIX = 0x60000000
STOP = FIX + 0xff00
SIZE = patch.ALLOCATION_BYTES
GRID = patch.GRID_OFFSET
CS = Cs(CS_ARCH_X86, CS_MODE_64)
CS.detail = True
RECTS = [(1, 0, 0, 80, 80), (2, 1968, 1968, 80, 80),
         (3, 1016, 792, 96, 96), (4, 1536, 256, 128, 128),
         (5, 256, 1536, 256, 256), (6, 1984, 0, 64, 64)]
REG64 = ('rax', 'rbx', 'rcx', 'rdx', 'rsi', 'rdi', 'rbp', 'rsp',
         'r8', 'r9', 'r10', 'r11', 'r12', 'r13', 'r14', 'r15')


def uc_reg(name):
    return getattr(xr, 'UC_X86_REG_' + name.upper())


def putq(u, addr, value):
    u.mem_write(addr, struct.pack('<Q', value))


def pointer(identifier):
    return 0 if identifier == 255 else FIX + 0x1000 + identifier * 0x100


class Engine:
    def __init__(self, blob, base):
        self.base = base
        self.pe = pefile.PE(data=blob)
        self.pe.relocate_image(base)
        self.image = bytes(self.pe.get_memory_mapped_image())
        self.u = Uc(UC_ARCH_X86, UC_MODE_64)
        self.u.mem_map(base, (len(self.image) + 4095) & ~4095)
        self.u.mem_write(base, self.image)
        self.u.mem_map(OBJ - 4096, SIZE + 8192)
        self.u.mem_map(STACK, 0x20000)
        self.u.mem_map(FIX, 0x40000)
        self.u.mem_write(FIX, b'\xc3' * 0x1000)
        self.u.mem_write(OBJ - 4096, b'\xa5' * (SIZE + 8192))
        self.stubs = {}
        self.counts = {}
        self.writes = []
        self.u.hook_add(UC_HOOK_CODE, self.hook)
        self.u.hook_add(UC_HOOK_MEM_WRITE, self.write_hook)
        self.memsets = []
        self.stubs[base + 0xe58ea] = self.memset
        self.stubs[base + 0xe46bc] = self.allocate
        self.allocations = []
        # Stub actual CRT imports reached by the base constructor: time/srand/rand.
        for iat in (0xea020, 0xea2a0, 0xea2a8):
            putq(self.u, base + iat, FIX + iat % 0x1000)

    def write_hook(self, u, access, address, size, value, data):
        self.writes.append((address, size))
        if OBJ - 4096 <= address < OBJ or OBJ + SIZE <= address < OBJ + SIZE + 4096:
            raise AssertionError(('World allocation canary write', hex(address), size))

    def hook(self, u, address, size, data):
        self.counts[address] = self.counts.get(address, 0) + 1
        if address in self.stubs:
            value = self.stubs[address]()
            if value is not None:
                u.reg_write(xr.UC_X86_REG_RAX, value)
            sp = u.reg_read(xr.UC_X86_REG_RSP)
            dest = struct.unpack('<Q', u.mem_read(sp, 8))[0]
            u.reg_write(xr.UC_X86_REG_RSP, sp + 8)
            u.reg_write(xr.UC_X86_REG_RIP, dest)

    def memset(self):
        u = self.u
        dst, val, size = (u.reg_read(uc_reg(n)) for n in ('rcx', 'rdx', 'r8'))
        assert size <= SIZE
        self.memsets.append((dst, val & 255, size))
        u.mem_write(dst, bytes([val & 255]) * size)
        return dst

    def allocate(self):
        amount = self.u.reg_read(xr.UC_X86_REG_RCX)
        self.allocations.append(amount)
        assert amount == SIZE
        return OBJ

    def run(self, entry, regs=None, stop=None, max_count=2000000, stack_args=()):
        u = self.u
        for name in REG64:
            u.reg_write(uc_reg(name), 0)
        sp = STACK + 0x1f008
        u.reg_write(xr.UC_X86_REG_RSP, sp)
        putq(u, sp, STOP)
        for index, value in enumerate(stack_args):
            putq(u, sp + 0x28 + index * 8, value)
        for name, value in (regs or {}).items():
            u.reg_write(uc_reg(name), value)
        u.emu_start(self.base + entry, STOP if stop is None else self.base + stop,
                    count=max_count)
        actual_stop = u.reg_read(xr.UC_X86_REG_RIP)
        assert actual_stop == (STOP if stop is None else self.base + stop), ('instruction limit', hex(actual_stop))
        assert bytes(u.mem_read(OBJ - 4096, 4096)) == b'\xa5' * 4096
        assert bytes(u.mem_read(OBJ + SIZE, 4096)) == b'\xa5' * 4096

    def setup_world(self, size, rectangles=RECTS):
        u = self.u
        u.mem_write(OBJ, b'\x00' * SIZE)
        u.mem_write(OBJ + GRID, b'\xff' * 65536)
        u.mem_write(OBJ + 0x1d8, struct.pack('<II', size, size))
        # Isolated service vtables; notifications return without mutating World.
        world_vt, island_vt, svc, svc_vt = FIX + 0x30000, FIX + 0x31000, FIX + 0x32000, FIX + 0x33000
        for vt in (world_vt, island_vt, svc_vt):
            u.mem_write(vt, struct.pack('<Q', FIX) * 128)
        putq(u, OBJ, world_vt)
        putq(u, OBJ + 0x220, svc)
        putq(u, svc, svc_vt)
        # Real native inline geometry getters are used by rebuild/removal.
        for offset, rva in ((0xa8, 0x3a190), (0xb0, 0xc8f0), (0xb8, 0x3a1a0), (0xc0, 0x3a1b0)):
            putq(u, island_vt + offset, self.base + rva)
        # ID getter fixture has no knowledge of lookup geometry.
        u.mem_write(FIX + 0x100, bytes.fromhex('0fb64120c3'))
        putq(u, island_vt + 0x88, FIX + 0x100)
        # Optional island nodes return NULL (native object list loop runs fully).
        u.mem_write(FIX + 0x120, bytes.fromhex('31c0c3'))
        putq(u, island_vt + 0x1f8, FIX + 0x120)
        putq(u, world_vt + 0x148, FIX + 0x120)
        # Update dimensions callback used by rebuild.
        self.stubs[FIX + 0x140] = lambda: u.mem_write(OBJ + 0x1d8, struct.pack('<II', u.reg_read(xr.UC_X86_REG_EDX), u.reg_read(xr.UC_X86_REG_R8D)))
        putq(u, world_vt + 0x308, FIX + 0x140)
        for identifier, x, y, width, height in rectangles:
            island = pointer(identifier)
            u.mem_write(island, b'\x00' * 0x100)
            putq(u, island, island_vt)
            u.mem_write(island + 8, struct.pack('<HHHH', x, y, width, height))
            u.mem_write(island + 0x20, bytes([identifier]))
            putq(u, OBJ + 0x6640 + identifier * 8, island)

    def expected_grid(self, size, rectangles):
        result = bytearray(b'\xff' * 65536)
        stride = size // 8
        for identifier, x, y, width, height in rectangles:
            for gy in range(y // 8, (y + height) // 8):
                offset = gy * stride + x // 8
                result[offset:offset + width // 8] = bytes([identifier]) * (width // 8)
        return bytes(result)


def transform_tests():
    rows = []
    for name, path in [('original', ROOT / 'AnnoWelt.dll'), ('dev7', ROOT / 'WorldSettings_Work/anno1503_food_world_dev7/native/AnnoWelt.world.dll')]:
        blob = path.read_bytes()
        output, manifest = patch.transform_welt_grid(blob)
        again, second = patch.transform_welt_grid(output)
        assert again == output and second['idempotent']
        assert len(blob) == len(output)
        for offset in [0, len(blob) // 2, len(blob) - 1, manifest['edits'][0]['operand_file_offset']]:
            bad = bytearray(blob)
            bad[offset] ^= 1
            try:
                patch.transform_welt_grid(bytes(bad))
            except ValueError:
                pass
            else:
                raise AssertionError('Unknown/partial source accepted')
        allowed = {p for item in manifest['edits'] for p in range(item['operand_file_offset'], item['operand_file_offset'] + 4)}
        differences = [i for i, (a, b) in enumerate(zip(blob, output)) if a != b]
        assert differences and set(differences) <= allowed
        rows.append(dict(source=name, source_sha256=patch.sha256(blob), output_sha256=patch.sha256(output), changed_bytes=len(differences), instruction_sites=104, idempotent=True, altered_sources_rejected=4))
    return rows


def direct_read_tests(engine):
    u = engine.u
    u.mem_write(OBJ, b'\xa5' * SIZE)
    values = bytes((i * 17 + 13) % 256 for i in range(65536))
    u.mem_write(OBJ + GRID, values)
    native_before = bytes(u.mem_read(OBJ, 0x7068))
    rows = [row for row in patch.instruction_edits() if row['role'] == 'direct one-byte island lookup read']
    assert len(rows) == 87
    executions = 0
    for row in rows:
        inst = next(CS.disasm(bytes.fromhex(row['after_instruction']), row['rva']))
        mem = next(op.mem for op in inst.operands if op.type == X86_OP_MEM)
        assert mem.base and mem.index and mem.scale == 1
        for index in [0, 1, 255, 256, 25599, 25600, 32767, 65534, 65535]:
            for reg in REG64:
                u.reg_write(uc_reg(reg), 0)
            # Both bases are algebraic additions, so either can carry World.
            u.reg_write(uc_reg(inst.reg_name(mem.base)), OBJ)
            u.reg_write(uc_reg(inst.reg_name(mem.index)), index)
            before_writes = len(engine.writes)
            u.emu_start(engine.base + row['rva'], engine.base + row['rva'] + inst.size, count=1)
            assert u.reg_read(uc_reg(inst.reg_name(inst.operands[0].reg))) == values[index], (row['rva'], index)
            assert len(engine.writes) == before_writes
            executions += 1
    assert bytes(u.mem_read(OBJ, 0x7068)) == native_before
    return dict(native_read_sites=87, executions=executions, all_lookup_boundaries_checked=True, writes=0)


def lifecycle_tests(engine):
    u = engine.u
    u.mem_write(OBJ, b'\xa5' * SIZE)
    engine.run(0xd1de0, {'rcx': OBJ})
    assert bytes(u.mem_read(OBJ + GRID, 65536)) == b'\xff' * 65536
    assert bytes(u.mem_read(OBJ + 0x240, 0x6400)) == b'\xa5' * 0x6400
    assert (OBJ + GRID, 255, 65536) in engine.memsets
    assert bytes(u.mem_read(OBJ + 0x6640, 0x800)) == b'\x00' * 0x800
    assert bytes(u.mem_read(OBJ + 0x7068, GRID - 0x7068)) == b'\xa5' * (GRID - 0x7068)
    # Exercise all native rebuild + both island removal paths with real loops.
    removal_counts = []
    for entry in [0xd02e0, 0xd0830]:
        engine.setup_world(2048)
        old_lookup = bytes(u.mem_read(OBJ + 0x240, 0x6400))
        engine.run(0xd00e0, {'rcx': OBJ, 'rdx': 2048, 'r8': 2048, 'r9': OBJ})
        assert bytes(u.mem_read(OBJ + GRID, 65536)) == engine.expected_grid(2048, RECTS)
        # Remove the island straddling the old fixed grid's y=800 boundary.
        engine.run(entry, {'rcx': OBJ, 'rdx': pointer(3)})
        remaining = [row for row in RECTS if row[0] != 3]
        assert bytes(u.mem_read(OBJ + GRID, 65536)) == engine.expected_grid(2048, remaining)
        assert bytes(u.mem_read(OBJ + 0x6640 + 3 * 8, 8)) == b'\x00' * 8
        assert bytes(u.mem_read(OBJ + 0x240, 0x6400)) == old_lookup
        removal_counts.append(dict(entry_rva=hex(entry), full_function=True, fixture_service_calls=True, surviving_islands=len(remaining)))
    # Real server reset calls native removal/reinsert for the complete island table.
    engine.setup_world(2048)
    engine.run(0xd00e0, {'rcx': OBJ, 'rdx': 2048, 'r8': 2048, 'r9': OBJ})
    # Avoid ce940's unrelated service object graph in this fixture; the reset
    # function and native removal are still fully executed. Reinsert itself is
    # tested separately by its actual native row writer.
    def reinsert():
        island = u.reg_read(xr.UC_X86_REG_RDX)
        ident = bytes(u.mem_read(island + 0x20, 1))[0]
        putq(u, OBJ + 0x6640 + ident * 8, island)
        return 0
    engine.stubs[engine.base + 0xce940] = reinsert
    engine.run(0xe2990, {'rcx': OBJ})
    assert bytes(u.mem_read(OBJ + GRID, 65536)) == b'\xff' * 65536
    del engine.stubs[engine.base + 0xce940]
    return dict(constructor_full_function=True, constructor_grid_clear_bytes=65536,
                constructor_gap_and_legacy_lookup_preserved=True,
                rebuild_full_function=True, removal_paths=removal_counts,
                reset_full_function=True, reset_reinsert_service_stub=True,
                canary_pages_preserved=True,
                external_stubs=['CRT memset', 'CRT time/srand/rand', 'World notifications', 'island identifier/node getters', 'reset reinsert service'])


def query_iterator_write_tests(engine, original_engine):
    u, base = engine.u, engine.base
    rng = random.Random(20482026)
    variants = [(0xc8b20, 0xc8b6d, 'r9', False),
                (0xc8be0, 0xc8c30, 'r9', False),
                (0xc8cc0, 0xc8d14, 'r10', True),
                (0xc8db0, 0xc8df8, 'rcx', True),
                (0xd0090, 0xd00d6, 'rax', False)]
    cases = []
    for size in [256, 512, 1024, 2048]:
        engine.setup_world(size, [])
        values = bytes((i * 17 + 13) % 256 for i in range((size // 8) ** 2))
        u.mem_write(OBJ + GRID, values)
        if size <= 1024:
            original_engine.setup_world(size, [])
            original_engine.u.mem_write(OBJ + 0x240, values)
        for identifier in range(256):
            putq(u, OBJ + 0x6640 + identifier * 8, pointer(identifier))
            if size <= 1024:
                putq(original_engine.u, OBJ + 0x6640 + identifier * 8, pointer(identifier))
        protected = bytes(u.mem_read(OBJ, 0x7068))
        edges = sorted({0, 7, 8, size // 2, size - 8, size - 1, *([799, 800, 1023, 1024, 1279, 1280] if size == 2048 else [])})
        points = [(x, y) for x in edges for y in edges]
        points += [(rng.randrange(size), rng.randrange(size)) for _ in range(64)]
        for x, y in points:
            expected = pointer(values[(y // 8) * (size // 8) + x // 8])
            for start, stop, result, floating in variants:
                regs = {'rcx': OBJ, 'rdx': x, 'r8': y}
                if floating:
                    regs['xmm1'] = struct.unpack('<I', struct.pack('<f', x + .25))[0]
                    regs['xmm2'] = struct.unpack('<I', struct.pack('<f', y + .25))[0]
                engine.run(start, regs, stop=stop)
                assert u.reg_read(uc_reg(result)) == expected, (hex(start), size, x, y)
                if size <= 1024:
                    original_engine.run(start, regs, stop=stop)
                    assert original_engine.u.reg_read(uc_reg(result)) == expected
        assert bytes(u.mem_read(OBJ, 0x7068)) == protected
        cases.append(dict(world_size=size, points=len(points), query_executions=len(points) * 5,
                          exact_original_equivalence=size <= 1024))
    # Native insertion row loop at all edges including past the old capacity.
    engine.setup_world(2048, [])
    protected = bytes(u.mem_read(OBJ, 0x7068))
    rows = 0
    for identifier, x, y, width, height in RECTS:
        for gy in range(y // 8, (y + height) // 8):
            engine.run(0xcea60, {'rbx': OBJ, 'rsi': identifier, 'r8': gy,
                       'rcx': x // 8, 'r9': (x + width) // 8}, stop=0xcea86)
            rows += 1
    assert bytes(u.mem_read(OBJ + GRID, 65536)) == engine.expected_grid(2048, RECTS)
    assert bytes(u.mem_read(OBJ, 0x7068)) == protected
    # Complete rectangular native iterator, including indirect lookup at c8a90.
    engine.setup_world(2048)
    engine.run(0xd00e0, {'rcx': OBJ, 'rdx': 2048, 'r8': 2048, 'r9': OBJ})
    callbacks = []
    def record():
        callbacks.append(bytes(u.mem_read(u.reg_read(xr.UC_X86_REG_RCX) + 0x20, 1))[0])
        return 0
    engine.stubs[FIX + 0x180] = record
    putq(u, FIX + 0x31000 + 0x268, FIX + 0x180)
    grid = engine.expected_grid(2048, RECTS)
    iterator_cases = []
    for x, y, radius in [(0, 0, 40), (1024, 800, 64), (2000, 2000, 80), (2047, 0, 255), (2047, 2047, 1)]:
        callbacks.clear()
        engine.run(0xc8970, {'rcx': OBJ, 'rdx': x, 'r8': y, 'r9': radius}, stack_args=(0, 0))
        last, expected = 255, []
        for gy in range(max(y - radius, 0) // 8, (min(y + 1 + radius, 2048) + 7) // 8):
            for gx in range(max(x - radius, 0) // 8, (min(x + 1 + radius, 2048) + 7) // 8):
                ident = grid[gy * 256 + gx]
                if ident != 255 and ident != last:
                    expected.append(ident)
                    last = ident
        assert callbacks == expected, (x, y, radius, callbacks, expected)
        iterator_cases.append(dict(x=x, y=y, radius=radius, callbacks=list(callbacks)))
    return dict(query_cases=cases, native_query_executions=sum(row['query_executions'] for row in cases),
                original_equivalence_executions=sum(row['query_executions'] for row in cases if row['exact_original_equivalence']),
                insertion_rows=rows, iterator_full_function=True, iterator_cases=iterator_cases,
                native_members_and_canaries_preserved=True)


def factory_tests(engine):
    u, base = engine.u, engine.base
    u.mem_write(OBJ, b'\xa5' * SIZE)
    # Ancillary vector growth is outside the World layout change.
    def vector_reserve():
        vector = u.reg_read(xr.UC_X86_REG_RCX)
        for offset, value in [(0, FIX + 0x34000), (8, FIX + 0x34000), (16, FIX + 0x34060)]:
            putq(u, vector + offset, value)
        return 0
    engine.stubs[base + 0xc620] = vector_reserve
    vtable = struct.unpack('<Q', engine.image[0xff650 + 0xa8:0xff650 + 0xb0])[0]
    init_rva = vtable - engine.pe.OPTIONAL_HEADER.ImageBase
    assert 0 < init_rva < len(engine.image)
    def initialize():
        u.mem_write(OBJ + 0x1d8, struct.pack('<II', u.reg_read(xr.UC_X86_REG_EDX), u.reg_read(xr.UC_X86_REG_R8D)))
        return 0
    engine.stubs[base + init_rva] = initialize
    u.mem_write(FIX + 0x35000, struct.pack('<HH', 2048, 2048))
    engine.run(0x21c0, {'rcx': 1, 'rdx': 0, 'r8': FIX + 0x35000, 'r9': 0}, stack_args=(FIX + 0x35010,))
    assert engine.allocations == [SIZE]
    assert struct.unpack('<Q', u.mem_read(FIX + 0x35010, 8))[0] == OBJ
    assert bytes(u.mem_read(OBJ + 0x1d8, 8)) == struct.pack('<II', 2048, 2048)
    assert bytes(u.mem_read(OBJ + GRID, 65536)) == b'\xff' * 65536
    assert bytes(u.mem_read(OBJ + 0x7068, GRID - 0x7068)) == b'\xa5' * (GRID - 0x7068)
    return dict(export_factory_full_function=True, allocated_bytes=SIZE,
                native_base_constructor_executed=True, derived_tail_initialized=True,
                fixture_stubs=['vector reserve', 'server initialize service'],
                initialization_rva=hex(init_rva), server_vtable_rva='0xff650')


def destruction_tests(engine):
    u, base = engine.u, engine.base
    frees = []
    def free_call():
        frees.append((u.reg_read(xr.UC_X86_REG_RCX), u.reg_read(xr.UC_X86_REG_RDX)))
        return 0
    putq(u, base + 0xea1c0, FIX + 0x1c0)
    engine.stubs[FIX + 0x1c0] = free_call
    rows = []
    for entry in [0xd1da0, 0xe2b80]:
        engine.setup_world(2048, [])
        # Empty native optional members use the real destructor branches.
        putq(u, OBJ + 0x220, 0)
        before = bytes(u.mem_read(OBJ + 0x7068, SIZE - 0x7068))
        engine.run(entry, {'rcx': OBJ, 'rdx': 1})
        assert frees[-1] == (OBJ, SIZE), (entry, frees)
        assert bytes(u.mem_read(OBJ + 0x7068, SIZE - 0x7068)) == before
        rows.append(dict(entry_rva=hex(entry), full_function=True,
                         native_free_chain_executed=True, sized_delete_bytes=SIZE))
    assert len(frees) == 2
    return dict(paths=rows, CRT_free_stub=True, appended_grid_no_separate_lifetime=True)


def main():
    transforms = transform_tests()
    original = (ROOT / 'AnnoWelt.dll').read_bytes()
    blob, _ = patch.transform_welt_grid(original)
    results = []
    for base in [0x180000000, 0x280000000]:
        e = Engine(blob, base)
        original_engine = Engine(original, base)
        readers = direct_read_tests(e)
        lifecycle = lifecycle_tests(e)
        queries = query_iterator_write_tests(e, original_engine)
        factory = factory_tests(e)
        destruction = destruction_tests(e)
        results.append(dict(image_base=hex(base), readers=readers, lifecycle=lifecycle, queries=queries, factory=factory, destruction=destruction))
    result = dict(passed=True, scope=__doc__, transforms=transforms, native_runs=results,
                  game_executed=False, game_files_modified=False)
    (HERE / 'native_test_results.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
