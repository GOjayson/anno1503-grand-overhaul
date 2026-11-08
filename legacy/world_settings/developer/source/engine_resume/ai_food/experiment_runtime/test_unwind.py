"""Actual Windows RtlVirtualUnwind on synthetic native+bridge stack snapshots.

The game is never launched or attached. Original prologues and added bridge
instructions run in Unicorn, then Windows unwinds the corresponding copied
image and private stack buffers. This is not an actual exception in the game.
"""
from pathlib import Path
import ctypes as C,json,os,struct,subprocess,sys
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[2];ROOT=WORK.parent
sys.path.insert(0,str(WORK/'engine_audit'))
from audit import Module
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *
from postprofile_bridge import *
out=HERE/'_build';out.mkdir(exist_ok=True);(out/'tmp').mkdir(exist_ok=True)
env=dict(os.environ,ZIG_GLOBAL_CACHE_DIR=str(out/'global-cache'),ZIG_LOCAL_CACHE_DIR=str(out/'local-cache'),TEMP=str(out/'tmp'),TMP=str(out/'tmp'))
subprocess.run([str(WORK/'_tools/ziglang/zig.exe'),'cc','-shared','-O2','-Wall','-Wextra','-Werror',str(HERE/'unwind_fixture.c'),'-o',str(out/'UnwindFixture.dll'),'-lkernel32'],check=True,env=env)
lib=C.CDLL(str(out/'UnwindFixture.dll'));call=lib.WSUnwindFixture
call.argtypes=[C.c_size_t,C.c_uint32,C.c_uint32,C.c_uint32,C.POINTER(C.c_uint64),C.POINTER(C.c_uint64)]
k=C.WinDLL('kernel32',use_last_error=True);k.VirtualAlloc.argtypes=[C.c_void_p,C.c_size_t,C.c_uint32,C.c_uint32];k.VirtualAlloc.restype=C.c_void_p;k.VirtualFree.argtypes=[C.c_void_p,C.c_size_t,C.c_uint32]
module=k.VirtualAlloc(None,0x120000,0x3000,4);stack=k.VirtualAlloc(None,0x20000,0x3000,4);obj=k.VirtualAlloc(None,0x10000,0x3000,4)
assert module and stack and obj
rows=[];bad=[]
try:
 m=Module(str(ROOT/'AnnoFrame.dll'));C.memmove(module,m.image,len(m.image))
 code,names,funcs=build_postprofile_code(0x100000);C.memmove(module+0x100000,code,len(code));C.memmove(module+0x110000,UNWIND,len(UNWIND))
 patch=b'\xe8'+struct.pack('<i',names['postprofile']-SITE-5);C.memmove(module+SITE,patch,len(patch))
 NV=[UC_X86_REG_RBX,UC_X86_REG_RBP,UC_X86_REG_RSI,UC_X86_REG_RDI,UC_X86_REG_R12,UC_X86_REG_R13,UC_X86_REG_R14,UC_X86_REG_R15]
 for valid in [0,1]:
  u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(module,0x120000);u.mem_write(module,C.string_at(module,0x120000));u.mem_map(stack,0x20000);u.mem_map(obj,0x10000)
  EXT=0x33000000;CALLBACK=EXT+0x100;STOP=EXT+0x800;u.mem_map(EXT,0x10000);u.mem_write(CALLBACK,b'\xc3');u.mem_write(STOP,b'\xc3')
  u.mem_write(module+names['after_profiles_iat'],struct.pack('<Q',CALLBACK));rsp=stack+0x10008;u.mem_write(rsp,struct.pack('<Q',STOP));u.reg_write(UC_X86_REG_RSP,rsp)
  original=[0x10101010+i for i in range(8)];xmm=0x123456789abcdef00112233445566778
  for reg,value in zip(NV,original):u.reg_write(reg,value)
  u.reg_write(UC_X86_REG_RCX,obj);u.reg_write(UC_X86_REG_XMM6,xmm)
  u.emu_start(module+0x55a10,module+0x55a47,count=100)
  parent_stack=u.reg_read(UC_X86_REG_RSP)
  site_values=[0x20202020+i for i in range(8)];site_values[2]=obj;site_values[5]=0
  for reg,value in zip(NV,site_values):u.reg_write(reg,value)
  u.reg_write(UC_X86_REG_RDX,obj);u.reg_write(UC_X86_REG_R8,obj+0x8000)
  def hook(machine,address,size,_):
   if address==module+0x55330:
    s=machine.reg_read(UC_X86_REG_RSP);target=struct.unpack('<Q',machine.mem_read(s,8))[0]
    machine.reg_write(UC_X86_REG_RSP,s+8);machine.reg_write(UC_X86_REG_RIP,target);return
   if address==CALLBACK:machine.reg_write(UC_X86_REG_RAX,valid)
   if address in [module+0x55f40,module+0x56b30]:machine.emu_stop();return
   if not module+names['postprofile']<=address<module+names['postprofile_end']:return
   C.memmove(stack,bytes(machine.mem_read(stack,0x20000)),0x20000)
   xx=machine.reg_read(UC_X86_REG_XMM6)
   inputs=(C.c_uint64*12)(*[machine.reg_read(reg) for reg in NV],machine.reg_read(UC_X86_REG_RSP),address,xx&((1<<64)-1),xx>>64)
   outputs=(C.c_uint64*12)();call(module,names['postprofile'],names['postprofile_end'],0x110000,inputs,outputs)
   native_return=struct.unpack('<Q',machine.mem_read(parent_stack-8,8))[0]
   expected=site_values+[parent_stack,native_return,xmm&((1<<64)-1),xmm>>64]
   okay=list(outputs)==expected
   parent_output=(C.c_uint64*12)();call(module,*PARENT,outputs,parent_output)
   parent_expected=original+[rsp+8,STOP,xmm&((1<<64)-1),xmm>>64]
   parent_okay=list(parent_output)==parent_expected
   row=dict(valid=valid,offset=hex(address-module),passed=okay and parent_okay,ordinary_wrapper_passed=okay,native_parent_passed=parent_okay)
   rows.append(row)
   if not okay or not parent_okay:bad.append(dict(**row,actual=[hex(x) for x in outputs],expected=[hex(x) for x in expected],parent_actual=[hex(x) for x in parent_output],parent_expected=[hex(x) for x in parent_expected]))
  u.hook_add(UC_HOOK_CODE,hook);u.emu_start(module+SITE,module+names['postprofile_end'],count=1000)
finally:
 for pointer in [module,stack,obj]:k.VirtualFree(pointer,0,0x8000)
result=dict(scope=__doc__,actual_game_runs=0,positions=len(rows),passed=sum(x['passed'] for x in rows),failures=bad,positions_checked=rows)
(HERE/'unwind_results.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')
print(json.dumps(dict(positions=len(rows),passed=result['passed'],failures=len(bad))))
assert not bad,bad[:2]
