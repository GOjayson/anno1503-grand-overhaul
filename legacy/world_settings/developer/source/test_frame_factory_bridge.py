"""Actual x64 bridge instructions; runtime export is an explicit boundary double."""
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / '_tools'))
import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_64, UC_HOOK_CODE
from unicorn.x86_const import *
from frame_factory_bridge import build_factory_code, FACTORY_IAT_RVA, transform_full_frame


class FactoryBridgeChecks(unittest.TestCase):
    def test_argument_and_return_preservation_at_two_image_bases(self):
        for base in [0x180000000, 0x1b3000000]:
            for seed in range(16):
                with self.subTest(base=hex(base), seed=seed):
                    uc = Uc(UC_ARCH_X86, UC_MODE_64)
                    uc.mem_map(base, 0x200000)
                    stack, stop, runtime = 0x30000000, base+0x110000, base+0x110100
                    uc.mem_map(stack, 0x20000)
                    rsp = stack+0x18008
                    code, symbols = build_factory_code(0x100000)
                    uc.mem_write(base+0x100000, code)
                    uc.mem_write(base+FACTORY_IAT_RVA, struct.pack('<Q', base+0x55555))
                    uc.mem_write(base+symbols['factory_export_iat'], struct.pack('<Q', runtime))
                    arguments = [0x123400000000+seed*16+i for i in range(7)]
                    uc.mem_write(rsp, struct.pack('<Q', stop))
                    uc.mem_write(rsp+0x28, struct.pack('<QQQ', *arguments[4:]))
                    for reg, value in zip([UC_X86_REG_RCX, UC_X86_REG_RDX, UC_X86_REG_R8, UC_X86_REG_R9], arguments):
                        uc.reg_write(reg, value)
                    nonvolatile = [UC_X86_REG_RBX, UC_X86_REG_RSI, UC_X86_REG_RDI,
                                   UC_X86_REG_R12, UC_X86_REG_R13, UC_X86_REG_R14, UC_X86_REG_R15]
                    sentinels = [0x112233440000+i for i in range(len(nonvolatile))]
                    for reg, value in zip(nonvolatile, sentinels):
                        uc.reg_write(reg, value)
                    result = [0, 0x80004005, 0x12345678, 0xffffffff80070057][seed % 4]
                    calls = []
                    def callback(cpu, address, size, _):
                        if address != runtime:
                            return
                        current_rsp = cpu.reg_read(UC_X86_REG_RSP)
                        self.assertEqual(current_rsp % 16, 8)
                        got = [cpu.reg_read(r) for r in [UC_X86_REG_RCX, UC_X86_REG_RDX, UC_X86_REG_R8, UC_X86_REG_R9]]
                        got += list(struct.unpack('<QQQQ', cpu.mem_read(current_rsp+0x28, 32)))
                        self.assertEqual(got, arguments+[base+0x55555])
                        calls.append(got)
                        # Deliberately clobber every volatile integer register.
                        for reg in [UC_X86_REG_RCX, UC_X86_REG_RDX, UC_X86_REG_R8, UC_X86_REG_R9, UC_X86_REG_R10, UC_X86_REG_R11]:
                            cpu.reg_write(reg, 0x7777777777777777)
                        cpu.reg_write(UC_X86_REG_RAX, result)
                        cpu.reg_write(UC_X86_REG_RIP, struct.unpack('<Q', cpu.mem_read(current_rsp, 8))[0])
                        cpu.reg_write(UC_X86_REG_RSP, current_rsp+8)
                    uc.hook_add(UC_HOOK_CODE, callback)
                    uc.reg_write(UC_X86_REG_RSP, rsp)
                    uc.emu_start(base+symbols['factory_bridge'], stop, count=1000)
                    self.assertEqual(len(calls), 1)
                    self.assertEqual(uc.reg_read(UC_X86_REG_RAX), result)
                    self.assertEqual(uc.reg_read(UC_X86_REG_RSP), rsp+8)
                    self.assertEqual([uc.reg_read(reg) for reg in nonvolatile], sentinels)

    def test_pe_imports_and_unwind_with_preserved_food(self):
        original = (HERE.parent / 'AnnoFrame.dll').read_bytes()
        patched, metadata = transform_full_frame(original)
        before, after = pefile.PE(data=original), pefile.PE(data=patched)
        self.assertEqual(after.FILE_HEADER.Machine, 0x8664)
        self.assertEqual(after.OPTIONAL_HEADER.CheckSum, after.generate_checksum())
        food = next(s for s in before.sections if s.Name.rstrip(b'\0') == b'.fmarket')
        self.assertEqual(food.get_data(), after.get_data(food.VirtualAddress, food.SizeOfRawData))
        imports = {entry.dll: {i.name for i in entry.imports} for entry in after.DIRECTORY_ENTRY_IMPORT}
        self.assertIn(b'WorldSettingsCreateScene', imports[b'AnnoWorldSettings.dll'])
        self.assertEqual(len(after.DIRECTORY_ENTRY_EXCEPTION), len(before.DIRECTORY_ENTRY_EXCEPTION)+3)
        entries = [(e.struct.BeginAddress, e.struct.EndAddress) for e in after.DIRECTORY_ENTRY_EXCEPTION]
        self.assertTrue(all(a[1] <= b[0] for a, b in zip(entries, entries[1:])))


if __name__ == '__main__':
    unittest.main(verbosity=2)
