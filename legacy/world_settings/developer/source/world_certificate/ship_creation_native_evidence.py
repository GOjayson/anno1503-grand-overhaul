"""Original player SCHIFF creation call-site instructions, before factory return.
The resident creation method is an explicit boundary double. The native call
site selects world+208 despite a distinct map-object decoy at world+220.
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
WORLD=0x40000000;PLAYER=0x40002000;FIGURE=0x40004000;RESIDENTS=0x40006000;MAP=0x40008000;SHIP=0x4000a000;BP=0x50004000;SP=0x5000f000

def run(base,ship_id,x,y):
 u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,0x200000);u.mem_write(base,M.image);u.mem_map(WORLD,0x10000);u.mem_map(0x50000000,0x10000)
 worldvt=base+0xff650;residentvt=base+0xffa20;create=base+0x190000
 u.mem_write(WORLD,struct.pack('<Q',worldvt));u.mem_write(worldvt+0x148,struct.pack('<Q',base+0xd1a40))
 u.mem_write(PLAYER+0x10,struct.pack('<Q',WORLD));u.mem_write(WORLD+0x208,struct.pack('<Q',RESIDENTS));u.mem_write(WORLD+0x220,struct.pack('<Q',MAP))
 u.mem_write(RESIDENTS,struct.pack('<Q',residentvt));u.mem_write(residentvt,struct.pack('<Q',create));u.mem_write(MAP,struct.pack('<Q',base+0xff5e0));u.mem_write(BP,struct.pack('<fff',x,0.93,y))
 for reg,val in [(UC_X86_REG_R13,PLAYER),(UC_X86_REG_RBX,FIGURE),(UC_X86_REG_RBP,BP),(UC_X86_REG_RSP,SP),(UC_X86_REG_RSI,ship_id)]:u.reg_write(reg,val)
 calls=[]
 def boundary(cpu,address,size,_):
  if address!=create:return
  rsp=u.reg_read(UC_X86_REG_RSP);out=struct.unpack('<Q',u.mem_read(rsp+0x30,8))[0]
  values=[u.reg_read(r) for r in [UC_X86_REG_RCX,UC_X86_REG_RDX,UC_X86_REG_R8,UC_X86_REG_R9]]
  flags=struct.unpack('<I',u.mem_read(rsp+0x28,4))[0]
  assert values==[RESIDENTS,BP,FIGURE,ship_id] and flags==0 and out==BP-0x80
  position=struct.unpack('<fff',u.mem_read(BP,12));assert position[0]==x and position[2]==y
  calls.append({'resident_field':'0x208','position':[x,y],'definition_pointer_forwarded':True,'id':ship_id})
  u.mem_write(out,struct.pack('<Q',SHIP));u.reg_write(UC_X86_REG_RAX,0);u.reg_write(UC_X86_REG_RIP,struct.unpack('<Q',u.mem_read(rsp,8))[0]);u.reg_write(UC_X86_REG_RSP,rsp+8)
 u.hook_add(UC_HOOK_CODE,boundary);u.emu_start(base+0x9d5ba,base+0x9d606,count=1000)
 assert u.reg_read(UC_X86_REG_RIP)==base+0x9d606 and u.reg_read(UC_X86_REG_RSP)==SP and len(calls)==1
 assert struct.unpack('<Q',u.mem_read(BP-0x80,8))[0]==SHIP
 return {'base':hex(base),'call':calls[0]}

def main():
 cases=[run(base,ident,x,y) for base in [0x180000000,0x280000000] for ident in [0,5,7,65535] for x,y in [(566.5,435.5),(450.5,422.5)]]
 (HERE/'ship_creation_native_results.json').write_text(json.dumps({'scope':__doc__,'source_sha256':hashlib.sha256(M.data).hexdigest(),'passed':len(cases),'cases':cases},indent=2))
 (HERE/'ship_creation_native.asm').write_text(M.dis(0xe1025,0xe110b)+'\n\n'+M.dis(0x9d3ca,0x9d650))
 print(json.dumps({'status':'passed','cases':len(cases),'bases':2,'scope':__doc__}))
if __name__=='__main__':main()
