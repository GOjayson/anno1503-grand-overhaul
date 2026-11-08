"""Execute the original Anlagen ware/input-name decoding on real source chunks.

Only private Unicorn memory is written. No DLL is loaded into Windows and no
game file/process is changed. The native chunk-reading/copying prologue is the
boundary: fixture buffers contain exact original WARE/ROHSTOFF payload bytes.
Name matching, native property20 dispatch, ID/name lookup, and destination byte
writes all execute original Game instructions. Base relocations are applied to
the private image for the second address, as the Windows loader would do.
"""
from pathlib import Path
import hashlib, json, struct, sys
HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]
ROOT = WORK.parent
sys.path.insert(0, str(WORK / 'engine_resume/ai_food'))
from inspect_food_chains import entries
sys.path.insert(0, str(WORK / 'engine_audit'))
from audit import Module
from unicorn import Uc, UC_ARCH_X86, UC_MODE_64
from unicorn.x86_const import *
m = Module(str(ROOT / 'AnnoGame.dll'))
assert hashlib.sha256(m.data).hexdigest() == 'e6f01d19e8e16e6716c0a6c7d3ba00273c9df493e051b8ba62865ee4b53dfdea'

def machine(base):
    image = bytearray(m.image)
    for block in m.pe.DIRECTORY_ENTRY_BASERELOC:
        for e in block.entries:
            if e.type == 10:
                before = struct.unpack_from('<Q', image, e.rva)[0]
                struct.pack_into('<Q', image, e.rva, before + base - m.base)
            else:
                assert e.type == 0
    u = Uc(UC_ARCH_X86, UC_MODE_64)
    u.mem_map(base, (len(image) + 4095) & ~4095)
    u.mem_write(base, bytes(image))
    u.mem_map(0x31000000, 0x10000)
    u.mem_map(0x32000000, 0x10000)
    u.mem_map(0x33000000, 0x1000)
    return u

cases = 0
reports = []
resolved = {}
for source in ['Anlagen.dat', 'Anlagen.addon']:
    path = ROOT / source
    definitions = entries(path)
    outputs = []
    for ident in [713, 805, 809, 810, 811, 820, 1002, 1004, 1018]:
        definition = definitions[ident]
        result = {'id': ident}
        for field, start, offset in [('WARE', 0x3f50, 0x20e), ('ROHSTOFF', 0x4030, 0x208)]:
            payload = definition[field]
            names = payload.split(b'\0')[:2]
            expected_ids = None
            for base in [0x180000000, 0x280000000]:
                u = machine(base)
                stack, frame, target = 0x31006008, 0x31006500, 0x32001000
                game, vt, buf = 0x32002000, 0x32003000, 0x32004000
                u.mem_write(game, struct.pack('<Q', vt))
                u.mem_write(vt + 0x98, struct.pack('<Q', base + 0xe3d0))
                u.mem_write(target + 0x10, struct.pack('<Q', game))
                u.mem_write(buf, payload)
                for reg, value in [(UC_X86_REG_RSP, stack), (UC_X86_REG_RBP, frame),
                                   (UC_X86_REG_RBX, 0), (UC_X86_REG_RSI, target),
                                   (UC_X86_REG_R14, buf), (UC_X86_REG_R12, buf + len(payload)),
                                   (UC_X86_REG_R15, 0), (UC_X86_REG_R13, 0xffffffffffffffff)]:
                    u.reg_write(reg, value)
                u.emu_start(base + start, base + 0x4193, count=50000)
                values = list(u.mem_read(target + offset, 2))
                if expected_ids is None: expected_ids = values
                assert values == expected_ids
                for label, good in zip(names, values):
                    label = label.decode('ascii')
                    if not label: continue
                    if label in resolved: assert resolved[label] == good
                    resolved[label] = good
                if field == 'ROHSTOFF':
                    assert u.mem_read(target + 0x203, 1)[0] == sum(v != 0 for v in values)
                cases += 1
            result[field] = {'source_payload_hex': payload.hex(),
                             'names': [s.decode('ascii') for s in names],
                             'ids': expected_ids}
        outputs.append(result)
    reports.append(dict(path=source, sha256=hashlib.sha256(path.read_bytes()).hexdigest(), records=outputs))
assert {name: resolved[name] for name in ['FLEISCH', 'KORN', 'MEHL', 'FLEISCHTIER', 'GRAS', 'GETREIDE']} == {
    'FLEISCH': 12, 'KORN': 13, 'MEHL': 14, 'FLEISCHTIER': 137, 'GRAS': 69, 'GETREIDE': 56}
result = dict(scope=__doc__, game_sha256=hashlib.sha256(m.data).hexdigest(),
              original_native_chunk_decode_cases=cases, resolved_names=resolved,
              sources=reports, actual_game_runs=0, installed_hooks=0)
(HERE / 'enum_translation_results.json').write_text(json.dumps(result, indent=2) + '\n', 'utf-8')
(HERE / 'enum_translation_native.asm').write_text('\n\n'.join(m.dis(a, b) for a, b in [(0x3f50, 0x40d1), (0xe3d0, 0xe5f1), (0x199e0, 0x19bd6)]), 'utf-8')
print(json.dumps({k: v for k, v in result.items() if k not in ['sources', 'scope']}, indent=2))
