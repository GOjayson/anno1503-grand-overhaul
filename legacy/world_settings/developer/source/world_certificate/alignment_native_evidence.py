"""Execute original History World island-insertion alignment instructions.
World virtual+118 -> cfea0 is original code. Only downstream template-loading
virtual+3b0 is a boundary double returning NULL; no template/game load occurs.
"""
from pathlib import Path
import sys,struct,json,hashlib
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE.parent/'engine_audit'))
from audit import Module
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *
M=Module(str(ROOT/'AnnoWelt.dll'))
assert hashlib.sha256(M.data).hexdigest()=='ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9'
assert M.pe.FILE_HEADER.Machine==0x8664 and M.pe.OPTIONAL_HEADER.Magic==0x20b
for vt in [0xff1d8,0xff650]:
 assert struct.unpack_from('<Q',M.image,vt+0x118)[0]-M.base==0xcfea0
 assert struct.unpack_from('<Q',M.image,vt+0x3b0)[0]-M.base==0xcf070
WORLD=0x40000000;RECT=0x40010000;PATH=0x40011000;STACK=0x5000f008;STOP=0x60000000

def remainder8(value):return value-int(value/8)*8

def run_base(base):
 u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,0x200000);u.mem_write(base,M.image)
 u.mem_map(WORLD,0x20000);u.mem_map(0x50000000,0x10000);u.mem_map(STOP,0x1000)
 vt=base+0xff650;loader=base+0x190000
 u.mem_write(WORLD,struct.pack('<Q',vt));u.mem_write(vt+0x3b0,struct.pack('<Q',loader));u.mem_write(PATH,b'verified template path\0')
 calls=[]
 def boundary(cpu,address,size,_):
  if address!=loader:return
  rsp=u.reg_read(UC_X86_REG_RSP)
  args=[u.reg_read(r) for r in [UC_X86_REG_RCX,UC_X86_REG_RDX,UC_X86_REG_R8,UC_X86_REG_R9]]
  args.append(struct.unpack('<I',u.mem_read(rsp+0x28,4))[0]);calls.append(args)
  u.reg_write(UC_X86_REG_RAX,0);u.reg_write(UC_X86_REG_RIP,struct.unpack('<Q',u.mem_read(rsp,8))[0]);u.reg_write(UC_X86_REG_RSP,rsp+8)
 u.hook_add(UC_HOOK_CODE,boundary)
 count=0;samples=[]
 def one(x,y,width=128,height=128):
  nonlocal count
  calls.clear();u.mem_write(RECT,struct.pack('<4i',x,y,x+width,y+height));u.mem_write(STACK,struct.pack('<Q',STOP))
  for reg,value in [(UC_X86_REG_RCX,WORLD),(UC_X86_REG_RDX,PATH),(UC_X86_REG_R8,RECT),(UC_X86_REG_R9,10),(UC_X86_REG_RSP,STACK)]:u.reg_write(reg,value)
  u.emu_start(base+0xcfea0,STOP,count=2000)
  expected=(x-remainder8(x),y-remainder8(y),x+width-remainder8(x),y+height-remainder8(y))
  actual=struct.unpack('<4i',u.mem_read(RECT,16));assert actual==expected,(x,y,actual,expected)
  assert calls==[[WORLD,PATH,expected[0]&0xffffffff,expected[1]&0xffffffff,10]],(x,y,calls)
  assert u.reg_read(UC_X86_REG_RIP)==STOP and u.reg_read(UC_X86_REG_RSP)==STACK+8 and u.reg_read(UC_X86_REG_RAX)==0
  count+=1
  return actual
 # Every coordinate within the positive1024-square domain, and every x/y
 # residue pair at representative positions. Covers all widths used by plan.
 for x in range(1024):one(x,1023-x)
 for x in range(8):
  for y in range(8):one(376+x,160+y)
 for width in [64,80,128,256]:
  for x,y in [(377,160),(378,161),(383,167),(384,168)]:
   actual=one(x,y,width,width)
   samples.append({'input':[x,y,x+width,y+width],'loaded_rect':list(actual)})
 # Aligning candidates upward by8 yields exact native identity. The planner
 # must then test bounds/spacing/reserves using that aligned candidate.
 for coordinate in range(0,1017):
  aligned=(coordinate+7)&~7;assert one(aligned,aligned)==(aligned,aligned,aligned+128,aligned+128)
 for coordinate in [-17,-9,-8,-7,-1]:one(coordinate,coordinate)
 return {'base':hex(base),'passed':count,'samples':samples}

def main():
 results=[run_base(base) for base in [0x180000000,0x280000000]]
 report={'scope':__doc__,'source_sha256':hashlib.sha256(M.data).hexdigest(),'world_vtable_rvas':['0xff1d8','0xff650'],'insertion_slot':'0x118','insertion_method':'0xcfea0','alignment_block':'0xcff3a..0xcff72','downstream_slot':'0x3b0','native_alignment':8,'positive_formula':'x := x - (x % 8); y := y - (y % 8); right/bottom subtract the same remainders','planner_formula':'candidate := (candidate + 7) & ~7 before all fit tests','passed':sum(r['passed'] for r in results),'results':results}
 (HERE/'alignment_native_results.json').write_text(json.dumps(report,indent=2))
 (HERE/'alignment_native.asm').write_text(M.dis(0xcfea0,0xd008c))
 print(json.dumps({'status':'passed','native_alignment':8,'cases':report['passed'],'bases':2,'scope':__doc__}))
if __name__=='__main__':main()
