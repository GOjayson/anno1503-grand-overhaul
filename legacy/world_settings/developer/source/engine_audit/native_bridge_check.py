"""Native single-player flag bridge checks; not an Anno game run.
Loader, modal export, and final state/online callback are boundary doubles.
The scene/geometry/resource backend does not run and is not verified here.
"""
import sys,struct,json,itertools
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'_tools'))
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE,UC_PROT_ALL
from unicorn.x86_const import *
from bridge_codegen import build_bridge,START_RVA
ROOT=Path(__file__).resolve().parents[2]
results=[]
for base,flag,outcome in itertools.product([0x180000000,0x1b3000000],range(1,9),['accept','cancel','missing_dll','missing_export','error','non_endless','missing_array','missing_child']):
 STACK=0x40000000;OBJ=0x50000000;SETUP=OBJ+0x10000;EXT=0x60000000;STOP=EXT+0x400;LOAD=EXT;GET=EXT+0x100;UI=EXT+0x200;NATIVEFLAG=EXT+0x300
 pe=pefile.PE(str(ROOT/'AnnoFrame.dll'));blob=pe.get_memory_mapped_image();bridge_rva=0x100000;code,names,hooks,funcs=build_bridge(bridge_rva)
 uc=Uc(UC_ARCH_X86,UC_MODE_64);uc.mem_map(base,0x120000,UC_PROT_ALL);uc.mem_write(base,blob);uc.mem_write(base+bridge_rva,code)
 for rva,before,after in hooks:assert bytes(uc.mem_read(base+rva,len(before)))==before;uc.mem_write(base+rva,after)
 for addr,sz in [(STACK,0x20000),(OBJ,0x30000),(EXT,0x20000)]:uc.mem_map(addr,sz,UC_PROT_ALL)
 for addr in [LOAD,GET,UI,NATIVEFLAG,STOP]:uc.mem_write(addr,b'\xc3')
 uc.mem_write(base+0x9e408,struct.pack('<Q',LOAD));uc.mem_write(base+0x9e410,struct.pack('<Q',GET))
 rsp=STACK+0x10008;uc.reg_write(UC_X86_REG_RSP,rsp);uc.mem_write(rsp,struct.pack('<Q',STOP))
 vt=OBJ+0x8000;array=OBJ+0x9000
 uc.mem_write(OBJ,struct.pack('<Q',vt));uc.mem_write(vt+0x178,struct.pack('<Q',NATIVEFLAG));uc.mem_write(OBJ+0x2260,b'\0' if outcome=='non_endless' else b'\1')
 uc.mem_write(OBJ+0x21b0,struct.pack('<Q',0 if outcome=='missing_array' else array));uc.mem_write(array,struct.pack('<Q',0 if outcome=='missing_child' else SETUP))
 source=bytes((x*13+7)&255 for x in range(0x498));uc.mem_write(SETUP+0x2288,source);uc.mem_write(SETUP+0x2280,bytes([1]*7))
 guard=b'UNCHANGED-GUARD!';assert len(guard)==16
 uc.mem_write(base+0xc75e0-16,guard);uc.mem_write(base+0xc75e0+0x498,guard);uc.mem_write(SETUP+0x2288+0x498,guard)
 original_regs={UC_X86_REG_RBX:0x1111,UC_X86_REG_RSI:0x2222,UC_X86_REG_RDI:0x3333,UC_X86_REG_R12:0x4444,UC_X86_REG_R13:0x5555,UC_X86_REG_R14:0x6666,UC_X86_REG_R15:0x7777}
 for reg,val in original_regs.items():uc.reg_write(reg,val)
 uc.reg_write(UC_X86_REG_RCX,OBJ);uc.reg_write(UC_X86_REG_RDX,flag);calls=[]
 def cstring(a):
  o=bytearray()
  while True:
   b=bytes(uc.mem_read(a+len(o),1))
   if b==b'\0':return o.decode()
   o+=b
 def hook(uc,a,size,_):
  if a==STOP:uc.emu_stop();return
  if a in [LOAD,GET,UI,NATIVEFLAG]:assert uc.reg_read(UC_X86_REG_RSP)%16==8
  if a==LOAD:
   assert cstring(uc.reg_read(UC_X86_REG_RCX))=='AnnoWorldSettings.dll';calls.append('load');uc.reg_write(UC_X86_REG_RAX,0 if outcome=='missing_dll' else 0x999)
  if a==GET:
   assert uc.reg_read(UC_X86_REG_RCX)==0x999;assert cstring(uc.reg_read(UC_X86_REG_RDX))=='WorldSettingsBeforeStart';calls.append('get');uc.reg_write(UC_X86_REG_RAX,0 if outcome=='missing_export' else UI)
  if a==UI:
   assert uc.reg_read(UC_X86_REG_RCX)==SETUP;assert uc.reg_read(UC_X86_REG_RDX)==base
   calls.append('ui');uc.reg_write(UC_X86_REG_RAX,1 if outcome=='accept' else (0xffffffff if outcome=='error' else 0))
   if outcome=='accept':uc.mem_write(SETUP+0x2280,bytes(7)) # accepted callback contract; real candidate has no backend
  if a==base+0x476e0:
   assert uc.reg_read(UC_X86_REG_RCX)==SETUP;calls.append('native_commit')
  if a==NATIVEFLAG:
   assert uc.reg_read(UC_X86_REG_RCX)==OBJ;assert uc.reg_read(UC_X86_REG_RDX)==0
   assert uc.reg_read(UC_X86_REG_R8)==1 and uc.reg_read(UC_X86_REG_R9)==8
   assert bytes(uc.mem_read(base+0xc5040,1))==bytes([flag]);calls.append('native_flag');uc.reg_write(UC_X86_REG_RAX,0x1234)
 uc.hook_add(UC_HOOK_CODE,hook);uc.emu_start(base+START_RVA,STOP+1,count=10000)
 assert uc.reg_read(UC_X86_REG_RSP)==rsp+8
 for reg,val in original_regs.items():assert uc.reg_read(reg)==val
 committed=bytes(uc.mem_read(base+0xc75e0,0x498));expected=bytearray(source)
 for i in range(7):expected[i*0xa8+0x4c:i*0xa8+0x5c]=bytes(16)
 assert committed==(expected if outcome=='accept' else bytes(0x498)),outcome
 assert ('native_commit' in calls)==(outcome=='accept')
 assert ('native_flag' in calls)==(outcome in ['accept','non_endless'])
 if outcome=='accept':assert calls.index('ui')<calls.index('native_commit')<calls.index('native_flag')
 if outcome=='non_endless':assert calls==['native_flag']
 if outcome in ['missing_array','missing_child']:assert calls==[]
 for addr in [base+0xc75e0-16,base+0xc75e0+0x498,SETUP+0x2288+0x498]:assert bytes(uc.mem_read(addr,16))==guard
 results.append({'base':hex(base),'flag':flag,'outcome':outcome,'calls':calls,'passed':True})
print(json.dumps({'scope':'Generated bridge and actual AMD64 flag callback/commit instructions; loader/UI/final state callback doubled; no actual game run or generated-world proof','count':len(results),'checks':results},indent=2))

