"""Execute generated Start bridge + actual native Start under Unicorn.
LoadLibraryA/GetProcAddress and in-game UI callback are boundary doubles.
"""
import sys,struct,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'_tools'))
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE,UC_PROT_ALL
from unicorn.x86_const import *
from customize_bridge_codegen import build_bridge
ROOT=Path(__file__).resolve().parents[2]
results=[]
for base in [0x180000000,0x1b3000000]:
 for outcome in ['accept','cancel','missing_dll','missing_export','error']:
  STACK=0x40000000;OBJ=0x50000000;EXT=0x60000000;STOP=EXT+0x300;LOAD=EXT;GET=EXT+0x100;UI=EXT+0x200
  pe=pefile.PE(str(ROOT/'AnnoFrame.dll'));blob=pe.get_memory_mapped_image();bridge_rva=0x100000;code,names,hooks,funcs=build_bridge(bridge_rva)
  uc=Uc(UC_ARCH_X86,UC_MODE_64);uc.mem_map(base,0x120000,UC_PROT_ALL);uc.mem_write(base,blob);uc.mem_write(base+bridge_rva,code)
  for rva,before,after in hooks:assert bytes(uc.mem_read(base+rva,len(before)))==before;uc.mem_write(base+rva,after)
  for addr in [STACK,OBJ,EXT]:uc.mem_map(addr,0x20000,UC_PROT_ALL)
  for addr in [LOAD,GET,UI,STOP]:uc.mem_write(addr,b'\xc3')
  uc.mem_write(base+0x9e408,struct.pack('<Q',LOAD));uc.mem_write(base+0x9e410,struct.pack('<Q',GET))
  rsp=STACK+0x10008;uc.reg_write(UC_X86_REG_RSP,rsp);uc.mem_write(rsp,struct.pack('<Q',STOP))
  vt=OBJ+0x8000;uc.mem_write(OBJ,struct.pack('<Q',vt));uc.mem_write(vt+0x188,struct.pack('<Q',STOP+0x10));uc.mem_write(STOP+0x10,b'\xc3')
  source=bytes((x*13+7)&255 for x in range(0x498));uc.mem_write(OBJ+0x2288,source);uc.mem_write(OBJ+0x2280,bytes([1]*7))
  original_regs={UC_X86_REG_RBX:0x1111,UC_X86_REG_RSI:0x2222,UC_X86_REG_RDI:0x3333,UC_X86_REG_R12:0x4444,UC_X86_REG_R13:0x5555,UC_X86_REG_R14:0x6666,UC_X86_REG_R15:0x7777}
  for reg,val in original_regs.items():uc.reg_write(reg,val)
  uc.reg_write(UC_X86_REG_RCX,OBJ);calls=[]
  def cstring(a):
   o=bytearray()
   while True:
    b=bytes(uc.mem_read(a+len(o),1))
    if b==b'\0':return o.decode()
    o+=b
  def hook(uc,a,size,_):
   if a==STOP:uc.emu_stop();return
   if a in [LOAD,GET,UI]:
    assert uc.reg_read(UC_X86_REG_RSP)%16==8,hex(uc.reg_read(UC_X86_REG_RSP))
   if a==LOAD:
    calls.append(('load',cstring(uc.reg_read(UC_X86_REG_RCX))));uc.reg_write(UC_X86_REG_RAX,0 if outcome=='missing_dll' else 0x999)
   if a==GET:
    assert uc.reg_read(UC_X86_REG_RCX)==0x999
    calls.append(('get',cstring(uc.reg_read(UC_X86_REG_RDX))));uc.reg_write(UC_X86_REG_RAX,0 if outcome=='missing_export' else UI)
   if a==UI:
    assert uc.reg_read(UC_X86_REG_RCX)==OBJ;assert uc.reg_read(UC_X86_REG_RDX)==base
    calls.append(('ui',outcome));uc.reg_write(UC_X86_REG_RAX,1 if outcome=='accept' else (0xffffffff if outcome=='error' else 0))
   if a==base+0x476e0:calls.append(('native_commit',True))
  uc.hook_add(UC_HOOK_CODE,hook);uc.emu_start(base+0x47d00,STOP+1,count=10000)
  assert uc.reg_read(UC_X86_REG_RSP)==rsp+8
  for reg,val in original_regs.items():assert uc.reg_read(reg)==val
  committed=bytes(uc.mem_read(base+0xc75e0,0x498))
  assert committed==(source if outcome=='accept' else bytes(0x498)),outcome
  assert ('native_commit',True) in calls if outcome=='accept' else ('native_commit',True) not in calls
  results.append({'base':hex(base),'outcome':outcome,'native_start_executed':outcome=='accept','calls':calls,'passed':True})
print(json.dumps({'scope':'Generated in-process bridge and original AMD64 Start instructions; Windows loader/UI boundaries doubled; no actual game run','checks':results},indent=2))

