"""Actual Windows RtlVirtualUnwind at direct CALL-wrapper instruction boundaries.

Original Frame prologue and wrapper run under Unicorn; private copied buffers
are passed to Windows twice, wrapper -> real native return -> original caller.
No game is launched, attached, or given an actual exception by this test.
"""
from pathlib import Path
import ctypes as C
import hashlib
import json
import shutil
import struct
import sys
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[1];ROOT=WORK.parent
sys.path.insert(0,str(WORK/'engine_audit'))
from audit import Module
from direct_bridge import build_direct_bridge,DIRECT_RVA,DIRECT_BEFORE,DIRECT_CANCEL,COMMON_UNWIND
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *


def main():
    # Use the same tiny compiled Windows API harness as the independently
    # checked post-profile fixture, copied here so it is not held open there.
    build=HERE/'_build';build.mkdir(exist_ok=True)
    harness=WORK/'engine_resume/ai_food/experiment_runtime'
    shutil.copyfile(harness/'_build/UnwindFixture.dll',build/'RouteUnwindFixture.dll')
    shutil.copyfile(harness/'unwind_fixture.c',HERE/'unwind_fixture.c')
    lib=C.CDLL(str(build/'RouteUnwindFixture.dll'));call=lib.WSUnwindFixture
    call.argtypes=[C.c_size_t,C.c_uint32,C.c_uint32,C.c_uint32,C.POINTER(C.c_uint64),C.POINTER(C.c_uint64)]
    k=C.WinDLL('kernel32',use_last_error=True)
    k.VirtualAlloc.argtypes=[C.c_void_p,C.c_size_t,C.c_uint32,C.c_uint32];k.VirtualAlloc.restype=C.c_void_p
    k.VirtualFree.argtypes=[C.c_void_p,C.c_size_t,C.c_uint32]
    module=k.VirtualAlloc(None,0x140000,0x3000,4);stack=k.VirtualAlloc(None,0x20000,0x3000,4);page=k.VirtualAlloc(None,0x30000,0x3000,4)
    assert module and stack and page;rows=[];failures=[]
    try:
        m=Module(str(ROOT/'AnnoFrame.dll'));C.memmove(module,m.image,len(m.image))
        code,names,hooks,functions=build_direct_bridge(0x100000)
        assert functions[0][2]==COMMON_UNWIND
        C.memmove(module+0x100000,code,len(code));C.memmove(module+0x110000,COMMON_UNWIND,len(COMMON_UNWIND))
        NV=[UC_X86_REG_RBX,UC_X86_REG_RBP,UC_X86_REG_RSI,UC_X86_REG_RDI,UC_X86_REG_R12,UC_X86_REG_R13,UC_X86_REG_R14,UC_X86_REG_R15]
        for result in [0,1,2]:
            u=Uc(UC_ARCH_X86,UC_MODE_64)
            for at,size in [(module,0x140000),(stack,0x20000),(page,0x30000)]:u.mem_map(at,size)
            u.mem_write(module,C.string_at(module,0x140000))
            for rva,before,after in hooks:
                assert bytes(u.mem_read(module+rva,len(before)))==before;u.mem_write(module+rva,after)
            EXT=0x33000000;LOAD=EXT;GET=EXT+0x100;UI=EXT+0x200;STATE=EXT+0x300;STOP=EXT+0x800
            u.mem_map(EXT,0x1000)
            for at in [LOAD,GET,UI,STATE,STOP]:u.mem_write(at,b'\xc3')
            u.mem_write(module+0x9e408,struct.pack('<Q',LOAD));u.mem_write(module+0x9e410,struct.pack('<Q',GET))
            vt=page+0x8000;array=page+0x9000;setup=page+0x10000
            u.mem_write(page,struct.pack('<Q',vt));u.mem_write(vt+0x178,struct.pack('<Q',STATE))
            u.mem_write(page+0x21b0,struct.pack('<Q',array));u.mem_write(array,struct.pack('<Q',setup))
            u.mem_write(setup+0x2280,bytes(7));u.mem_write(setup+0x2288,bytes(0x498))
            rsp=stack+0x10008;u.reg_write(UC_X86_REG_RSP,rsp);u.mem_write(rsp,struct.pack('<Q',STOP))
            original=[0x10101010+i for i in range(8)];xmm=0x123456789abcdef00112233445566778
            for reg,value in zip(NV,original):u.reg_write(reg,value)
            u.reg_write(UC_X86_REG_RCX,page);u.reg_write(UC_X86_REG_XMM6,xmm)
            u.emu_start(module+0x43c70,module+0x43c83,count=100)
            native=list(original);native[0]=1;native[3]=123;native[6]=page
            for reg,value in zip(NV,native):u.reg_write(reg,value)
            native_rsp=u.reg_read(UC_X86_REG_RSP);entry_rsp=native_rsp-8
            u.reg_write(UC_X86_REG_RAX,vt)
            for reg,value in [(UC_X86_REG_RCX,page),(UC_X86_REG_RDX,0),(UC_X86_REG_R8,1),(UC_X86_REG_R9,8)]:u.reg_write(reg,value)
            def hook(machine,address,size,_):
                if address==LOAD:machine.reg_write(UC_X86_REG_RAX,0x999)
                elif address==GET:machine.reg_write(UC_X86_REG_RAX,UI)
                elif address==UI:machine.reg_write(UC_X86_REG_RAX,result)
                if address in [module+DIRECT_RVA+5,module+DIRECT_CANCEL]:machine.emu_stop();return
                if not module+names['direct_start']<=address<module+names['direct_start_end']:return
                C.memmove(stack,bytes(machine.mem_read(stack,0x20000)),0x20000)
                xx=machine.reg_read(UC_X86_REG_XMM6)
                inputs=(C.c_uint64*12)(*[machine.reg_read(reg) for reg in NV],machine.reg_read(UC_X86_REG_RSP),address,xx&((1<<64)-1),xx>>64)
                outputs=(C.c_uint64*12)();call(module,names['direct_start'],names['direct_start_end'],0x110000,inputs,outputs)
                saved_return=struct.unpack('<Q',machine.mem_read(entry_rsp,8))[0]
                expected_native=native+[native_rsp,saved_return,xmm&((1<<64)-1),xmm>>64]
                okay=list(outputs)==expected_native
                parent=next(e.struct for e in m.pe.DIRECTORY_ENTRY_EXCEPTION if e.struct.BeginAddress<=saved_return-module<e.struct.EndAddress)
                outer=(C.c_uint64*12)();call(module,parent.BeginAddress,parent.EndAddress,parent.UnwindData,outputs,outer)
                expected=original+[rsp+8,STOP,xmm&((1<<64)-1),xmm>>64]
                outer_okay=list(outer)==expected
                row=dict(route_result=result,offset=hex(address-module),wrapper_passed=okay,parent_passed=outer_okay,passed=okay and outer_okay)
                rows.append(row)
                if not row['passed']:failures.append(dict(**row,actual_native=[hex(x) for x in outputs],expected_native=[hex(x) for x in expected_native],actual_outer=[hex(x) for x in outer],expected_outer=[hex(x) for x in expected]))
            u.hook_add(UC_HOOK_CODE,hook);u.emu_start(module+DIRECT_RVA,module+names['direct_start_end'],count=2000)
    finally:
        for pointer in [module,stack,page]:k.VirtualFree(pointer,0,0x8000)
    report=dict(scope=__doc__,game_executed=False,process_access=False,positions=len(rows),passed=sum(r['passed'] for r in rows),
                harness_sha256=hashlib.sha256((build/'RouteUnwindFixture.dll').read_bytes()).hexdigest(),failures=failures,positions_checked=rows)
    (HERE/'unwind_results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(positions=len(rows),passed=report['passed'],failures=len(failures))))
    assert not failures,failures[:2]


if __name__=='__main__':main()
