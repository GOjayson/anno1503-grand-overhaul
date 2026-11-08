"""Execute the actual eight-control construction loop, with UI factory doubles.

Complements native_bridge_check.py, which starts at the common callback itself.
Does not run Windows, actual game UI rendering, world generation or simulation.
"""
import json,struct,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'WorldSettings_Work'/'_tools'))
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE,UC_PROT_ALL
from unicorn.x86_const import *

def run(base):
    pe=pefile.PE(str(ROOT/'AnnoFrame.dll'))
    uc=Uc(UC_ARCH_X86,UC_MODE_64)
    uc.mem_map(base,0x120000,UC_PROT_ALL)
    uc.mem_write(base,pe.get_memory_mapped_image())
    obj,stack,external=0x50000000,0x40000000,0x60000000
    for addr in [obj,stack,external]:uc.mem_map(addr,0x20000,UC_PROT_ALL)
    stub=external
    uc.mem_write(stub,b'\xc3')
    parent_vt=obj+0x8000;control_vt=obj+0x9000
    uc.mem_write(obj,struct.pack('<Q',parent_vt))
    for vt in [parent_vt,control_vt]:
        for off in [0x58,0x80,0xa0,0xa8,0xc0]:uc.mem_write(vt+off,struct.pack('<Q',stub))
    uc.mem_write(control_vt+0x120,struct.pack('<Q',base+0x964c0))
    uc.mem_write(base+0x8f5b0,b'\xc3')
    uc.reg_write(UC_X86_REG_RDI,obj)
    uc.reg_write(UC_X86_REG_RBP,stack+0x8000)
    uc.reg_write(UC_X86_REG_RSP,stack+0x6000)
    uc.reg_write(UC_X86_REG_R14,0)
    uc.reg_write(UC_X86_REG_R12,base)
    created=[];ids=[]
    def hook(uc,a,size,_):
        if a==base+0x44787:uc.emu_stop();return
        if a==base+0x8f5b0:
            ctrl=obj+0x10000+len(created)*0x100
            created.append(ctrl)
            uc.mem_write(ctrl,struct.pack('<Q',control_vt))
            uc.mem_write(uc.reg_read(UC_X86_REG_RCX),struct.pack('<Q',ctrl))
            uc.reg_write(UC_X86_REG_RAX,0)
        if a==base+0x44698:
            ids.append(uc.reg_read(UC_X86_REG_RDX))
    uc.hook_add(UC_HOOK_CODE,hook)
    uc.emu_start(base+0x44620,base+0x44788,count=2000)
    assert len(created)==8
    assert ids==list(range(1,9)),ids
    callbacks=[struct.unpack('<Q',uc.mem_read(c+0x50,8))[0]-base for c in created]
    owners=[struct.unpack('<Q',uc.mem_read(c+0x58,8))[0] for c in created]
    assert callbacks==[0x44bb0]*8,callbacks
    assert owners==[obj]*8,owners
    return {'base':hex(base),'control_ids':ids,'callback_rvas':[hex(x) for x in callbacks],'passed':True}

if __name__=='__main__':
    print(json.dumps({'scope':__doc__,'checks':[run(x) for x in [0x180000000,0x1b3000000]]},indent=2))
