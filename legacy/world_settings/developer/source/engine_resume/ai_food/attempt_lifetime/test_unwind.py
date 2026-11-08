"""Actual Windows two-frame unwinding of future native-attempt wrapper snapshots.

Native prologue and wrapper execute in private Unicorn memory. Windows reads
matching private image/stack copies. No game is launched, attached or patched.
"""
from pathlib import Path
import ctypes as C,hashlib,itertools,json,os,struct,subprocess,sys
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[2];ROOT=WORK.parent;SOURCE=HERE.parent/'experiment_runtime'
sys.path.insert(0,str(WORK/'engine_audit'))
from audit import Module
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *
from attempt_bridge import *
out=HERE/'_build';out.mkdir(exist_ok=True);(out/'tmp').mkdir(exist_ok=True)
env=dict(os.environ,ZIG_GLOBAL_CACHE_DIR=str(out/'global-cache'),ZIG_LOCAL_CACHE_DIR=str(out/'local-cache'),TEMP=str(out/'tmp'),TMP=str(out/'tmp'))
subprocess.run([str(WORK/'_tools/ziglang/zig.exe'),'cc','-shared','-O2','-Wall','-Wextra','-Werror',str(SOURCE/'unwind_fixture.c'),'-o',str(out/'AttemptUnwindFixture.dll'),'-lkernel32'],check=True,env=env)
lib=C.CDLL(str(out/'AttemptUnwindFixture.dll'));call=lib.WSUnwindFixture
call.argtypes=[C.c_size_t,C.c_uint32,C.c_uint32,C.c_uint32,C.POINTER(C.c_uint64),C.POINTER(C.c_uint64)]
k=C.WinDLL('kernel32',use_last_error=True);k.VirtualAlloc.argtypes=[C.c_void_p,C.c_size_t,C.c_uint32,C.c_uint32];k.VirtualAlloc.restype=C.c_void_p;k.VirtualFree.argtypes=[C.c_void_p,C.c_size_t,C.c_uint32]
module=k.VirtualAlloc(None,0x120000,0x3000,4);stack=k.VirtualAlloc(None,0x20000,0x3000,4);obj=k.VirtualAlloc(None,0x10000,0x3000,4);assert module and stack and obj
rows=[];bad=[]
try:
 m=Module(str(ROOT/'AnnoFrame.dll'));assert hashlib.sha256(m.data).hexdigest()=='046b5ad6f351dfe867ed38ce29fb50a594485b43a32ee90adadc48e850466baf'
 assert PARENT in [(e.struct.BeginAddress,e.struct.EndAddress,e.struct.UnwindData) for e in m.pe.DIRECTORY_ENTRY_EXCEPTION]
 C.memmove(module,m.image,len(m.image));code,names,functions=build_attempt_code(0x100000)
 C.memmove(module+0x100000,code,len(code));C.memmove(module+0x110000,UNWIND,len(UNWIND))
 patch=b'\xe8'+struct.pack('<i',names['native_attempt']-SITE-5);C.memmove(module+SITE,patch,len(patch))
 NV=[UC_X86_REG_RBX,UC_X86_REG_RBP,UC_X86_REG_RSI,UC_X86_REG_RDI,UC_X86_REG_R12,UC_X86_REG_R13,UC_X86_REG_R14,UC_X86_REG_R15]
 for token,native_bool,final_bool in itertools.product([0,0xfffffffd],[0,1],[0,1]):
  u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(module,0x120000);u.mem_write(module,C.string_at(module,0x120000));u.mem_map(stack,0x20000);u.mem_map(obj,0x10000)
  EXT=0x33000000;BEGIN=EXT+0x100;END=EXT+0x200;STOP=EXT+0x800;u.mem_map(EXT,0x10000)
  for p in [BEGIN,END,STOP]:u.mem_write(p,b'\xc3')
  u.mem_write(module+names['begin_attempt_iat'],struct.pack('<Q',BEGIN));u.mem_write(module+names['end_attempt_iat'],struct.pack('<Q',END))
  rsp=stack+0x10008;u.mem_write(rsp,struct.pack('<Q',STOP));u.reg_write(UC_X86_REG_RSP,rsp)
  original=[0x10101010+i for i in range(8)];xmm=0x123456789abcdef00112233445566778
  for reg,value in zip(NV,original):u.reg_write(reg,value)
  u.reg_write(UC_X86_REG_RCX,obj);u.reg_write(UC_X86_REG_XMM6,xmm)
  u.emu_start(module+0x57060,module+0x57083,count=100);parent_stack=u.reg_read(UC_X86_REG_RSP)
  site=[0x20202020+i for i in range(8)];site[5]=original[5] # native57060 never modifies/saves R13
  for reg,value in zip(NV,site):u.reg_write(reg,value)
  for reg,value in zip([UC_X86_REG_RCX,UC_X86_REG_RDX,UC_X86_REG_R8,UC_X86_REG_R9],[obj,obj+8,obj+16,1]):u.reg_write(reg,value)
  def ret(machine,result):
   sp=machine.reg_read(UC_X86_REG_RSP);target=struct.unpack('<Q',machine.mem_read(sp,8))[0]
   machine.reg_write(UC_X86_REG_RAX,result);machine.reg_write(UC_X86_REG_RSP,sp+8);machine.reg_write(UC_X86_REG_RIP,target)
  def hook(machine,address,size,_):
   if address==BEGIN:machine.reg_write(UC_X86_REG_RAX,token)
   if address==END:machine.reg_write(UC_X86_REG_RAX,final_bool)
   if address==module+0x55a10:ret(machine,native_bool);return
   if address==module+SITE+5:machine.emu_stop();return
   if not module+names['native_attempt']<=address<module+names['native_attempt_end']:return
   C.memmove(stack,bytes(machine.mem_read(stack,0x20000)),0x20000);xx=machine.reg_read(UC_X86_REG_XMM6)
   inputs=(C.c_uint64*12)(*[machine.reg_read(reg) for reg in NV],machine.reg_read(UC_X86_REG_RSP),address,xx&((1<<64)-1),xx>>64)
   child=(C.c_uint64*12)();call(module,names['native_attempt'],names['native_attempt_end'],0x110000,inputs,child)
   expected=site+[parent_stack,module+SITE+5,xmm&((1<<64)-1),xmm>>64];child_ok=list(child)==expected
   parent=(C.c_uint64*12)();call(module,*PARENT,child,parent)
   outer=original+[rsp+8,STOP,xmm&((1<<64)-1),xmm>>64];parent_ok=list(parent)==outer
   row=dict(token=token,native_bool=native_bool,final_bool=final_bool,rva=hex(address-module),child_passed=child_ok,parent_passed=parent_ok)
   rows.append(row)
   if not child_ok or not parent_ok:bad.append(dict(**row,child=[hex(x) for x in child],child_expected=[hex(x) for x in expected],parent=[hex(x) for x in parent],parent_expected=[hex(x) for x in outer]))
  u.hook_add(UC_HOOK_CODE,hook);u.emu_start(module+SITE,module+names['native_attempt_end'],count=1000)
finally:
 for pointer in [module,stack,obj]:k.VirtualFree(pointer,0,0x8000)
report=dict(scope=__doc__,actual_game_runs=0,positions=len(rows),passed=sum(r['child_passed'] and r['parent_passed'] for r in rows),failures=bad,positions_checked=rows)
(HERE/'unwind_results.json').write_text(json.dumps(report,indent=2)+'\n','utf-8');print(json.dumps(dict(positions=len(rows),passed=report['passed'],failures=len(bad))))
assert not bad,bad[:1]
