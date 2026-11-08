"""Original x64 CreateAnnoSceneInstance control flow with explicit boundaries.
Allocation, constructors, init/load and deleting destructor bodies are doubles;
original factory/release instructions determine ownership and publication order.
No DLL is loaded into Anno and no real scene is created.
"""
from pathlib import Path
import sys,struct,json,hashlib
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE.parent/'engine_audit'))
from audit import Module
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *
M=Module(str(ROOT/'AnnoScene.dll'))
assert hashlib.sha256(M.data).hexdigest()=='f7d0685cf6156ff25c518f2f558863b351d7738280467e48dd585a1fefa9537a'
assert M.pe.FILE_HEADER.Machine==0x8664 and M.pe.OPTIONAL_HEADER.Magic==0x20b
assert next(s.address for s in M.pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name==b'CreateAnnoSceneInstance')==0x11a0
OBJ=0x40000000;OUT=0x40010000;PATH=0x40011000;SAVE=0x40012000;STACK=0x5000f008;STOP=0x60000000
FAIL=0x80004005;INIT_FAIL=0x80070057

def factory(base,init=0,load=0,path=b'prepared generated scene\0'):
 u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,0x80000);u.mem_write(base,M.image)
 u.mem_map(OBJ,0x20000);u.mem_map(0x50000000,0x10000);u.mem_map(STOP,0x1000)
 u.mem_write(OUT,struct.pack('<Q',0xdeadbeef));u.mem_write(PATH,path or b'\0')
 # Native fast-class check compares the exact tAnnoScene vtable3f648.
 vt=base+0x3f648;initialise=base+0x70000;loader=base+0x70100;deleting=base+0x70200
 for slot,target in [(0,deleting),(0x188,initialise),(0xb0,loader)]:u.mem_write(vt+slot,struct.pack('<Q',target))
 u.mem_write(STACK,struct.pack('<Q',STOP));u.mem_write(STACK+0x28,struct.pack('<QQQ',0,0xf1e2d3c4,0xaabbccdd))
 for reg,val in [(UC_X86_REG_RCX,0),(UC_X86_REG_RDX,PATH if path is not None else 0),(UC_X86_REG_R8,SAVE),(UC_X86_REG_R9,OUT),(UC_X86_REG_RSP,STACK)]:u.reg_write(reg,val)
 events=[]
 def ret(value):
  rsp=u.reg_read(UC_X86_REG_RSP);target=struct.unpack('<Q',u.mem_read(rsp,8))[0]
  u.reg_write(UC_X86_REG_RAX,value&0xffffffffffffffff);u.reg_write(UC_X86_REG_RSP,rsp+8);u.reg_write(UC_X86_REG_RIP,target)
 def boundary(cpu,address,size,_):
  if address==base+0x31be4:
   assert u.reg_read(UC_X86_REG_RCX)==0xb448;events.append('allocate');ret(OBJ)
  elif address==base+0xb3a0:
   assert u.reg_read(UC_X86_REG_RCX)==OBJ and u.reg_read(UC_X86_REG_RDX)==SAVE
   assert struct.unpack('<Q',u.mem_read(OUT,8))[0]==0
   events.append('construct');u.mem_write(OBJ,struct.pack('<Q',vt));ret(OBJ)
  elif address==initialise:
   assert struct.unpack('<Q',u.mem_read(OUT,8))[0]==0;assert u.reg_read(UC_X86_REG_RCX)==OBJ
   assert struct.unpack('<I',u.mem_read(OBJ+0x53c8,4))[0]==0xaabbccdd
   events.append('initialise');ret(init)
  elif address==loader:
   assert struct.unpack('<Q',u.mem_read(OUT,8))[0]==0
   assert u.reg_read(UC_X86_REG_RCX)==OBJ and u.reg_read(UC_X86_REG_RDX)==PATH and u.reg_read(UC_X86_REG_R8)==0xf1e2d3c4
   events.append('load');ret(load)
  elif address==deleting:
   assert struct.unpack('<Q',u.mem_read(OUT,8))[0]==0
   assert u.reg_read(UC_X86_REG_RCX)==OBJ and u.reg_read(UC_X86_REG_RDX)==1
   events.append('delete');ret(0)
 u.hook_add(UC_HOOK_CODE,boundary)
 try:u.emu_start(base+0x11a0,STOP,count=10000)
 except Exception as exc:raise AssertionError((hex(u.reg_read(UC_X86_REG_RIP)-base),events)) from exc
 assert u.reg_read(UC_X86_REG_RIP)==STOP
 return u.reg_read(UC_X86_REG_RAX)&0xffffffff,struct.unpack('<Q',u.mem_read(OUT,8))[0],events

def release(base,nonnull):
 u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,0x80000);u.mem_write(base,M.image)
 u.mem_map(OBJ,0x20000);u.mem_map(0x50000000,0x10000);u.mem_map(STOP,0x1000)
 vt=OBJ+0x100;deleting=base+0x70200;u.mem_write(OBJ,struct.pack('<Q',vt));u.mem_write(vt,struct.pack('<Q',deleting))
 u.mem_write(STACK,struct.pack('<Q',STOP));u.reg_write(UC_X86_REG_RSP,STACK);u.reg_write(UC_X86_REG_RCX,OBJ if nonnull else 0);calls=[]
 def boundary(cpu,address,size,_):
  if address!=deleting:return
  calls.append((u.reg_read(UC_X86_REG_RCX),u.reg_read(UC_X86_REG_RDX)))
  rsp=u.reg_read(UC_X86_REG_RSP);u.reg_write(UC_X86_REG_RIP,struct.unpack('<Q',u.mem_read(rsp,8))[0]);u.reg_write(UC_X86_REG_RSP,rsp+8)
 u.hook_add(UC_HOOK_CODE,boundary);u.emu_start(base+0x1b60,STOP,count=1000)
 assert u.reg_read(UC_X86_REG_RIP)==STOP and calls==([(OBJ,1)] if nonnull else [])
 return calls

def main():
 cases=[]
 for base in [0x180000000,0x280000000]:
  for label,kwargs,result,out,events in [
    ('native successful load',{},0,OBJ,['allocate','construct','initialise','load']),
    ('native init failure destroys before publishing',{'init':INIT_FAIL},INIT_FAIL,0,['allocate','construct','initialise','delete']),
    ('native load failure destroys before publishing',{'load':FAIL},FAIL,0,['allocate','construct','initialise','load','delete']),
    ('native null path has no load call',{'path':None},0,OBJ,['allocate','construct','initialise']),
    ('native empty path has no load call',{'path':b'\0'},0,OBJ,['allocate','construct','initialise']),
    ('native positive init/load statuses accepted',{'init':1,'load':1},0,OBJ,['allocate','construct','initialise','load'])]:
   got=factory(base,**kwargs);assert got==(result,out,events),(label,got)
   cases.append({'base':hex(base),'case':label,'hresult':hex(result),'output':hex(out),'events':events})
  for nonnull in [False,True]:
   calls=release(base,nonnull);cases.append({'base':hex(base),'case':'release wrapper nonnull'+str(nonnull),'deleting_calls':calls})
 report={'scope':__doc__,'source_sha256':hashlib.sha256(M.data).hexdigest(),'passed':len(cases),'cases':cases}
 (HERE/'factory_native_results.json').write_text(json.dumps(report,indent=2))
 (HERE/'factory_native.asm').write_text(M.dis(0x11a0)+'\n\n'+M.dis(0x1b60,0x1b71))
 print(json.dumps({'status':'passed','original_native_factory_release_cases':len(cases),'bases':2,'scope':__doc__}))
if __name__=='__main__':main()
