"""Read-only native Food AI unlock/stock/scoring audit.

Executes original AMD64 instructions on private Unicorn fixtures. Windows DLLs
are never loaded, installed, patched, or attached to the game. Enum strings and
Food unlock names come from the fingerprinted game and Food-modified data.
External property/object getters are explicit fixture boundaries. This is not a
complete resource-parser run, an AI game run, or proof of production strategy.
"""
from pathlib import Path
import hashlib, json, re, struct, sys

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]
ROOT = WORK.parent
sys.path.insert(0, str(WORK / 'engine_audit'))
from audit import Module
from unicorn import Uc, UC_ARCH_X86, UC_MODE_64, UC_HOOK_CODE
from unicorn.x86_const import *

SHAS = {
    'CompLogic.dll': '7f2c7e818d8c25a0b6c48cda2d21bfa0c4096c5dcd8be91c2ab93d877c22afee',
    'CompLogicClassic.dll': '0a7692879e15e8cbaed73ec3b59eaa6419165faaea6d8696cddfd68c92000f22',
    'AnnoGame.dll': 'e6f01d19e8e16e6716c0a6c7d3ba00273c9df493e051b8ba62865ee4b53dfdea',
}
mods = {name: Module(str(ROOT / name)) for name in SHAS}
for name, m in mods.items():
    assert hashlib.sha256(m.data).hexdigest() == SHAS[name]
    assert m.pe.FILE_HEADER.Machine == 0x8664
game = mods['AnnoGame.dll']
enums = []
for i in range(32):
    ptr = struct.unpack_from('<Q', game.image, 0x23280 + i * 8)[0] - game.base
    assert 0 <= ptr < len(game.image)
    enums.append(game.image[ptr:ptr + 64].split(b'\0')[0].decode('ascii'))
assert [enums[i] for i in (0, 5, 12)] == ['INFRA_EVER', 'INFRA_STUFE_2B', 'INFRA_STUFE_3B']
data = (ROOT / 'Data/BGruppen.dat').read_bytes()
text = data.decode('cp1252')
food = {'NAHRUNG': 26, 'WILD2': 24, 'KART2': 40, 'BROT2': 25, 'MEAT2': 45}
unlocks = {}
for name in food:
    match = re.search(r'(?m)^  Id:\s*' + name + r'\s*\r?\n  BauFirst:\s*(\w+)', text)
    assert match, name
    unlocks[name] = enums.index(match[1])
groups = re.split(r'(?m)(?=^  BGruppeNr:)', text.split('[BGRUPPE]', 1)[1].split('[BAUSTUFEN]', 1)[0])
population_stages = []
for group in groups:
    if not re.search(r'(?m)^  BGruppeNr:', group):
        continue
    need_names = re.findall(r'(?m)^  Ware:\s*(\w+)', group)
    assert all(name in need_names for name in food)
    stage = re.search(r'(?m)^  BauFirst:\s*(\w+)', group)[1]
    population_stages.append(enums.index(stage))
assert population_stages == [0, 4, 11, 17, 23]

def machine(m, base):
    u = Uc(UC_ARCH_X86, UC_MODE_64)
    u.mem_map(base, (len(m.image) + 4095) & ~4095)
    u.mem_write(base, m.image)
    for addr, length in [(0x31000000, 0x10000), (0x32000000, 0x30000), (0x33000000, 0x10000)]:
        u.mem_map(addr, length)
    u.reg_write(UC_X86_REG_RSP, 0x31008008)
    return u

def p64(u, addr, value): u.mem_write(addr, struct.pack('<Q', value))
def ret(u, value=1):
    sp = u.reg_read(UC_X86_REG_RSP)
    dst = struct.unpack('<Q', u.mem_read(sp, 8))[0]
    u.reg_write(UC_X86_REG_RAX, value)
    u.reg_write(UC_X86_REG_RSP, sp + 8)
    u.reg_write(UC_X86_REG_RIP, dst)

parser_cases = 0
for base in [0x180000000, 0x280000000]:
    for name, good in food.items():
        u = machine(game, base)
        stack = 0x31004000
        frame = stack + 0x100
        u.reg_write(UC_X86_REG_RSP, stack)
        u.reg_write(UC_X86_REG_RBP, frame)
        u.reg_write(UC_X86_REG_R13, 0x32001000)
        u.reg_write(UC_X86_REG_R15, 0x32003000)
        u.reg_write(UC_X86_REG_RSI, 0)
        p64(u, 0x32001000, 0x32002000)
        p64(u, 0x32002098, 0x33000100)
        u.mem_write(stack + 0x40, enums[unlocks[name]].encode('ascii') + b'\0')
        u.mem_write(0x32003000, b'\xa5' * 0x1a)
        def enum_getter(uc, address, size, user):
            if address != 0x33000100: return
            assert uc.reg_read(UC_X86_REG_RDX) == 0x21
            out = uc.reg_read(UC_X86_REG_R8)
            ordinal = struct.unpack('<I', uc.mem_read(out, 4))[0]
            uc.mem_write(out + 8, enums[ordinal].encode('ascii') + b'\0')
            ret(uc)
        u.hook_add(UC_HOOK_CODE, enum_getter)
        u.emu_start(base + 0x1baf0, base + 0x1bc34, count=10000)
        expected = bytearray(b'\xa5' * 0x1a)
        expected[2] = unlocks[name]
        assert u.mem_read(0x32003000, len(expected)) == expected
        parser_cases += 1

unlock_cases = 0
stock_cases = 0
scoring_cases = 0
observed_unlocks = []
assembly = []
for name in ['CompLogic.dll', 'CompLogicClassic.dll']:
    m = mods[name]
    unlock_start = 0x56490 if name == 'CompLogic.dll' else 0x539f0
    enable = 0x56340 if name == 'CompLogic.dll' else 0x538a0
    stock_start = 0x7330b if name == 'CompLogic.dll' else 0x7029b
    stock_end = 0x7338e if name == 'CompLogic.dll' else 0x7031e
    score = 0x84060 if name == 'CompLogic.dll' else 0x80bd0
    for a, b in [(unlock_start, unlock_start + 0x1f3), (stock_start, stock_end), (score, score + 0x17f)]:
        assembly.append(name + '\n' + m.dis(a, b))
    for base in [0x180000000, 0x280000000]:
        for highest in range(5):
            for future in [highest, highest + 1]:
                u = machine(m, base)
                provider, world, game_object = 0x32001000, 0x32002000, 0x32003000
                table, player, needs, definition = 0x32004000, 0x32005000, 0x32006000, 0x32007000
                profiles, metadata, states = 0x32008000, 0x32009000, 0x3200a000
                for obj, slot, method in [(world, 0x150, 1), (table, 0x18, 2), (player, 0xe0, 3), (needs, 0, 4), (game_object, 0xe8, 5), (definition, 0x98, 6)]:
                    p64(u, obj, obj + 0x400)
                    p64(u, obj + 0x400 + slot, 0x33000100 + method * 0x20)
                p64(u, provider, world)
                p64(u, provider + 8, game_object)
                for good in food.values():
                    u.mem_write(provider + 0x194 + good * 32, struct.pack('<I', 1000 + good))
                for level, stage in enumerate(population_stages):
                    start = profiles + level * 0x120
                    u.mem_write(start + 0xca, bytes([stage, 0, 5]))
                    p64(u, start + 0x118, metadata)
                    for ordinal, (label, good) in enumerate(food.items()):
                        u.mem_write(start + 0x64 + ordinal * 4, bytes([good]))
                        u.mem_write(metadata + good * 0x1a + 2, bytes([unlocks[label]]))
                p64(u, 0x31008008, 0x33000000)
                p64(u, 0x31008008 + 0x28, states)
                for reg, value in [(UC_X86_REG_RCX, provider), (UC_X86_REG_RDX, 1), (UC_X86_REG_R8, highest), (UC_X86_REG_R9, future)]:
                    u.reg_write(reg, value)
                methods = {1: table, 2: player, 3: needs, 4: profiles, 5: definition, 6: 0}
                def getter(uc, address, size, user):
                    index = (address - 0x33000100) // 0x20
                    if address in [0x33000100 + i * 0x20 for i in methods]:
                        if index == 6:
                            assert uc.reg_read(UC_X86_REG_RDX) == 0x44d
                            uc.mem_write(uc.reg_read(UC_X86_REG_R8), bytes(16))
                        ret(uc, methods[index])
                u.hook_add(UC_HOOK_CODE, getter)
                u.emu_start(base + unlock_start, 0x33000000, count=30000)
                flags = {}
                for label, good in food.items():
                    raw = u.mem_read(states + good * 0x5c, 0x5c)
                    enabled = unlocks[label] == 0 or unlocks[label] < population_stages[highest] or highest < future
                    assert raw[0x58] == (0xf if enabled else 0), (name, highest, future, label, raw.hex())
                    locked = enabled and unlocks[label] != 0 and unlocks[label] >= population_stages[highest]
                    assert raw[0x59] == (0x40 if locked else 0)
                    flags[label] = dict(enabled=enabled, locked=locked)
                if base == 0x180000000:
                    observed_unlocks.append(dict(module=name, highest=highest, requested=future, flags=flags))
                unlock_cases += 1
        # Both original loops execute: consumers26..40 and materials41..45.
        u = machine(m, base)
        city, foreign = 0x32010000, 0x32018000
        u.mem_write(city, b'\xa5' * 0x3000)
        p64(u, foreign, foreign + 0x400)
        p64(u, foreign + 0x500, 0x33000200)
        u.mem_write(0x33000200, bytes.fromhex('8bc2c1e008c3'))
        u.reg_write(UC_X86_REG_RDI, city)
        u.reg_write(UC_X86_REG_R14, foreign)
        u.emu_start(base + stock_start, base + stock_end, count=3000)
        for good in range(56):
            raw = u.mem_read(city + 0x5c4 + good * 0x5c + 0x30, 4)
            assert raw == (struct.pack('<f', float(good)) if 26 <= good <= 45 else b'\xa5' * 4)
        stock_cases += 1
        # One active state at a time, allowing the original helper83fb0 to run.
        for good in [26, 40, 24, 25, 45]:
            u = machine(m, base)
            city = 0x32010000
            p64(u, 0x31008008, 0x33000000)
            u.mem_write(city + 0x40, struct.pack('<I', 0xa5a5a5a5))
            state = city + good * 0x5c
            u.mem_write(state + 0x4b4, b'\x09')
            u.mem_write(state + 0x48c, struct.pack('<f', 10.0))
            u.reg_write(UC_X86_REG_RCX, city)
            u.reg_write(UC_X86_REG_RDX, 0)
            u.emu_start(base + score, 0x33000000, count=10000)
            output = struct.unpack('<I', u.mem_read(city + 0x40, 4))[0]
            assert (output != 0xa5a5a5a5) == (26 <= good <= 40), (name, good, hex(output))
            scoring_cases += 1

result = dict(scope=__doc__, source_sha256=SHAS,
              bgruppen_sha256=hashlib.sha256(data).hexdigest(), food_good_ids=food,
              unlock_indices=unlocks, native_enum_table_rva='0x23280',
              population_stage_indices=population_stages,
              native_parser_unlock_fragment_cases=parser_cases,
              native_complete_unlock_function_cases=unlock_cases,
              native_stock_consumer_and_material_loop_cases=stock_cases,
              native_scoring_function_cases=scoring_cases,
              observed_unlocks=observed_unlocks, actual_game_runs=0,
              installed_hooks=0,
              fixture_boundaries=['Enum property21 returns fingerprinted original native enum strings',
                                  'World/player/profile getters return fixture objects',
                                  'Food producer recipes are one bounded dummy entry per good',
                                  'Recipe property44d returns no dependencies',
                                  'Foreign city stock getter returns goodID*256'],
              conclusion='Native unlock path is data-driven and supports added Food IDs without a range patch. Stock24/25 and scoring24/25/45 need targeted iteration. Material45 stock is already covered.')
(HERE / 'results.json').write_text(json.dumps(result, indent=2) + '\n', 'utf-8')
(HERE / 'native.asm').write_text('\n\n'.join(assembly), 'utf-8')
print(json.dumps({k: v for k, v in result.items() if k not in ['observed_unlocks', 'scope']}, indent=2))
