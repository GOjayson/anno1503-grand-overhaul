"""Execute original server-world constructor assignments for resident/map fields.
Only allocation, child construction/initialisation and memset calls are doubles.
The original instructions choose vtables and write world+208/world+220.
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
WORLD=0x40000000;PLAYERS=0x40010000;RESIDENTS=0x41000000;MAP=0x42000000;MAPDATA=0x43000000;VIRTUAL=0x44000000;STACK=0x5000f000

def run(base):
 u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,0x200000);u.mem_write(base,M.image)
 for at,size in [(WORLD,0x20000),(RESIDENTS,0x410000),(MAP,0x1000),(MAPDATA,0x10000),(VIRTUAL,0x1000),(0x50000000,0x10000)]:u.mem_map(at,size)
 for r,val in [(UC_X86_REG_RSI,WORLD),(UC_X86_REG_RDI,PLAYERS),(UC_X86_REG_R12,0),(UC_X86_REG_R14,1024),(UC_X86_REG_R15,1024),(UC_X86_REG_RSP,STACK)]:u.reg_write(r,val)
 events=[]
 def ret(value):
  rsp=u.reg_read(UC_X86_REG_RSP);u.reg_write(UC_X86_REG_RAX,value);u.reg_write(UC_X86_REG_RIP,struct.unpack('<Q',u.mem_read(rsp,8))[0]);u.reg_write(UC_X86_REG_RSP,rsp+8)
 def boundary(cpu,address,size,_):
  if address==base+0xe46bc:
   n=u.reg_read(UC_X86_REG_RCX);assert n in [0x4001e0,0x418,0x28];events.append(['allocate',n]);ret({0x4001e0:RESIDENTS,0x418:VIRTUAL,0x28:MAP}[n])
  elif address==base+0xc2470:
   assert u.reg_read(UC_X86_REG_RCX)==RESIDENTS;events.append(['resident-child-constructor']);ret(RESIDENTS)
  elif address==base+0xe4b54:events.append(['array-child-construction']);ret(0)
  elif address==base+0xbfdf0:
   assert u.reg_read(UC_X86_REG_RCX)==RESIDENTS and u.reg_read(UC_X86_REG_R9)==WORLD
   assert struct.unpack('<Q',u.mem_read(RESIDENTS,8))[0]==base+0xffa20
   events.append(['resident-child-initialization',hex(0xffa20)]);ret(0)
  elif address==base+0xe472c:
   assert u.reg_read(UC_X86_REG_RCX)==0x10000;events.append(['map-array-allocation']);ret(MAPDATA)
  elif address==base+0xe58ea:
   dst=u.reg_read(UC_X86_REG_RCX);value=u.reg_read(UC_X86_REG_RDX)&255;n=u.reg_read(UC_X86_REG_R8)
   assert dst==MAPDATA and n==0x10000;u.mem_write(dst,bytes([value])*n);events.append(['map-array-fill',value,n]);ret(dst)
 u.hook_add(UC_HOOK_CODE,boundary);u.emu_start(base+0xdbaf5,base+0xdbc08,count=3000)
 assert u.reg_read(UC_X86_REG_RIP)==base+0xdbc08 and u.reg_read(UC_X86_REG_RSP)==STACK
 actual208,actual220=struct.unpack('<Q',u.mem_read(WORLD+0x208,8))[0],struct.unpack('<Q',u.mem_read(WORLD+0x220,8))[0]
 assert actual208==RESIDENTS and actual220==MAP
 assert struct.unpack('<Q',u.mem_read(actual208,8))[0]==base+0xffa20
 assert struct.unpack('<Q',u.mem_read(actual220,8))[0]==base+0xff5e0
 return {'base':hex(base),'resident_field':'0x208','resident_class':'0xffa20','map_field':'0x220','map_class':'0xff5e0','events':events}

def main():
 results=[run(b) for b in [0x180000000,0x280000000]]
 report={'scope':__doc__,'source_sha256':hashlib.sha256(M.data).hexdigest(),'passed':len(results),'results':results}
 (HERE/'ship_field_native_results.json').write_text(json.dumps(report,indent=2))
 (HERE/'ship_field_native.asm').write_text(M.dis(0xdbaf5,0xdbc08)+'\n\n'+M.dis(0xd1a40,0xd1a48))
 print(json.dumps({'status':'passed','cases':len(results),'resident_offset':'0x208','map_offset':'0x220','scope':__doc__}))
if __name__=='__main__':main()
