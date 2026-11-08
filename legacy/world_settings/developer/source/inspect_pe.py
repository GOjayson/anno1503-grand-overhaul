"""Read-only PE disassembly helper for the inspected History Edition binaries."""
import argparse
from pathlib import Path
import re
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / '_tools'))
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_MODE_32
from capstone.x86 import X86_OP_MEM, X86_REG_RIP, X86_OP_IMM


def inspect(path, pattern=None, start=None, length=512):
    pe = pefile.PE(str(path))
    base = pe.OPTIONAL_HEADER.ImageBase
    mode = CS_MODE_64 if pe.FILE_HEADER.Machine == 0x8664 else CS_MODE_32
    md = Cs(CS_ARCH_X86, mode)
    md.detail = True
    if start is not None:
        for ins in md.disasm(pe.get_data(start, length), start):
            print(f'{ins.address:08x} {ins.bytes.hex():24} {ins.mnemonic} {ins.op_str}')
        return
    needles = {}
    for m in re.finditer(rb'[ -~]{4,}', pe.__data__):
        text = m.group().decode('ascii')
        if re.search(pattern, text, re.I):
            rva = pe.get_rva_from_offset(m.start())
            needles[base + rva] = text
            print(f'STRING {rva:08x} {text}')
    for section in pe.sections:
        if not section.Characteristics & 0x20000000:
            continue
        # skipdata is needed for jump tables between functions.
        md.skipdata = True
        for ins in md.disasm(section.get_data(), base + section.VirtualAddress):
            if ins.id == 0:
                continue
            for op in ins.operands:
                address = None
                if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                    address = ins.address + ins.size + op.mem.disp
                elif op.type == X86_OP_IMM:
                    address = op.imm
                if address in needles:
                    print(f'REF {ins.address-base:08x} {ins.mnemonic} {ins.op_str}: {needles[address]}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('module', type=Path)
    parser.add_argument('--strings', default='endlos|customize|dummy|cache|insel')
    parser.add_argument('--start', type=lambda s: int(s, 0))
    parser.add_argument('--length', type=lambda s: int(s, 0), default=512)
    args = parser.parse_args()
    inspect(args.module, args.strings, args.start, args.length)
