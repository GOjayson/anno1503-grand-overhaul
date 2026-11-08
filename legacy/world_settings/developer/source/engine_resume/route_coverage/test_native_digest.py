"""Verify native selected-file digest routine against independent MD5.

Execute the inspected AMD64 Frame3e500 and its complete MD5 update/final/block
functions. File, allocation and byte-copy APIs are bounded doubles. No game run.
"""
from pathlib import Path
import hashlib
import json
import struct
import sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'WorldSettings_Work/_tools'))
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE,UC_PROT_ALL
from unicorn.x86_const import *
import pefile
from direct_bridge import EXPECTED_FRAME_SHA


def main():
    original=(ROOT/'AnnoFrame.dll').read_bytes();assert hashlib.sha256(original).hexdigest()==EXPECTED_FRAME_SHA
    pe=pefile.PE(data=original);image=pe.get_memory_mapped_image();rows=[]
    registry=json.loads((HERE/'stock_endless.json').read_text())['records']
    inputs=[(r['filename'],(ROOT/r['path']).read_bytes()) for r in registry]
    inputs += [('MD5-vector-'+str(n),bytes((i*13+19)&255 for i in range(n))) for n in [1,3,55,56,63,64,65,128]]
    for base in [0x180000000,0x1b3000000]:
        for name,data in inputs:
            STACK=0x40000000;OUT=0x50000000;EXT=0x60000000;ARENA=0x70000000
            SIZE=EXT;READ=EXT+0x100;STOP=EXT+0x200
            uc=Uc(UC_ARCH_X86,UC_MODE_64);uc.mem_map(base,(len(image)+4095)&~4095,UC_PROT_ALL);uc.mem_write(base,image)
            for at,size in [(STACK,0x20000),(OUT,0x1000),(EXT,0x1000),(ARENA,(len(data)+8191)&~4095)]:uc.mem_map(at,size,UC_PROT_ALL)
            for at in [SIZE,READ,STOP,base+0x97930,base+0x978ec,base+0x99bfc,base+0x987ca]:uc.mem_write(at,b'\xc3')
            uc.mem_write(base+0x9e3f0,struct.pack('<Q',SIZE));uc.mem_write(base+0x9e3c8,struct.pack('<Q',READ))
            rsp=STACK+0x10008;uc.reg_write(UC_X86_REG_RSP,rsp);uc.mem_write(rsp,struct.pack('<Q',STOP))
            uc.reg_write(UC_X86_REG_RCX,OUT+32);uc.reg_write(UC_X86_REG_RDX,123)
            guard=b'KEEP-THIS-GUARD!';assert len(guard)==16;uc.mem_write(OUT+16,guard);uc.mem_write(OUT+48,guard)
            def hook(uc,at,size,_):
                if at==STOP:uc.emu_stop();return
                if at==SIZE:
                    assert uc.reg_read(UC_X86_REG_RCX)==123
                    uc.mem_write(uc.reg_read(UC_X86_REG_RDX),bytes(4));uc.reg_write(UC_X86_REG_RAX,len(data))
                elif at==READ:
                    assert uc.reg_read(UC_X86_REG_RCX)==123
                    assert uc.reg_read(UC_X86_REG_R8)==len(data)
                    uc.mem_write(uc.reg_read(UC_X86_REG_RDX),data)
                    uc.mem_write(uc.reg_read(UC_X86_REG_R9),struct.pack('<I',len(data)))
                    uc.reg_write(UC_X86_REG_RAX,1)
                elif at==base+0x97930:
                    assert uc.reg_read(UC_X86_REG_RCX)==len(data)
                    uc.reg_write(UC_X86_REG_RAX,ARENA)
                elif at==base+0x99bfc:
                    target=uc.reg_read(UC_X86_REG_RCX);source=uc.reg_read(UC_X86_REG_RDX);length=uc.reg_read(UC_X86_REG_R8)
                    assert length<=64
                    if length:uc.mem_write(target,bytes(uc.mem_read(source,length)))
                    uc.reg_write(UC_X86_REG_RAX,target)
                elif at==base+0x987ca:
                    target=uc.reg_read(UC_X86_REG_RCX);value=uc.reg_read(UC_X86_REG_RDX)&255;length=uc.reg_read(UC_X86_REG_R8)
                    assert length<=64
                    if length:uc.mem_write(target,bytes([value])*length)
                    uc.reg_write(UC_X86_REG_RAX,target)
            for at in [SIZE,READ,STOP,base+0x97930,base+0x978ec,base+0x99bfc,base+0x987ca]:
                uc.hook_add(UC_HOOK_CODE,hook,begin=at,end=at)
            uc.emu_start(base+0x3e500,STOP+1,count=200000000)
            digest=bytes(uc.mem_read(OUT+32,16));assert digest==hashlib.md5(data).digest(),(name,digest.hex())
            assert uc.reg_read(UC_X86_REG_RSP)==rsp+8 and uc.reg_read(UC_X86_REG_RAX)==OUT+32
            assert bytes(uc.mem_read(OUT+16,16))==guard and bytes(uc.mem_read(OUT+48,16))==guard
            rows.append(dict(base=hex(base),input=name,bytes=len(data),md5=digest.hex(),passed=True))
    assert image[0x40102:0x40109]==bytes.fromhex('0f11052b740800')
    target=0x40109+struct.unpack_from('<i',image,0x40105)[0];assert target==0xc7534
    result=dict(scope=__doc__.strip(),source_sha256=EXPECTED_FRAME_SHA,game_executed=False,cases=len(rows),
                native_digest_global=hex(target),results=rows)
    (HERE/'native_digest_results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(cases=len(rows),passed=True,game_executed=False)))


if __name__=='__main__':main()
