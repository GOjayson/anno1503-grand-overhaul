"""Execute installed AMD64 Scene allocator/application instructions with engine doubles.

This is a CPU emulation check, not a game run. The occurrence setters and world
objects are explicit boundary doubles; the native branching, resource loops,
climate selection and resulting assignments execute from the inspected DLL.
"""
from pathlib import Path
import sys,struct,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'_tools'))
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE,UC_PROT_ALL
from unicorn.x86_const import *

ROOT=Path(__file__).resolve().parents[2]
Q=lambda x:struct.pack('<Q',x)
I=lambda x:struct.pack('<I',x)
H=lambda x:struct.pack('<H',x)

class NativeScene:
 def __init__(self,base=0x180000000,patched=False,active=True):
  self.base=base;self.u=Uc(UC_ARCH_X86,UC_MODE_64);self.calls=[];self.callbacks={};self.next_stub=0x60000000
  p=pefile.PE(str(ROOT/'AnnoScene.dll'))
  if patched:
   from patch_scene_copy import transform_scene
   blob,self.meta=transform_scene((ROOT/'AnnoScene.dll').read_bytes());p=pefile.PE(data=blob)
  self.u.mem_map(base,0x60000,UC_PROT_ALL);self.u.mem_write(base,p.get_memory_mapped_image())
  for a,n in [(0x40000000,0x200000),(0x50000000,0x800000),(0x60000000,0x100000)]:self.u.mem_map(a,n,UC_PROT_ALL)
  self.obj=0x50000000;self.world=self.obj+0x10000;self.defs=self.obj+0x20000
  self.counts=self.obj+0x30000;self.cropcounts=self.obj+0x31000
  self.next_obj=self.obj+0x40000;self.stop=self.stub(lambda:None,'stop')
  self.object(self.world,{0x170:lambda:7});self.object(self.defs,{0xe0:lambda:self.reg(UC_X86_REG_RDX)})
  self.write(self.obj+0x160,Q(self.world));self.write(self.obj+0x158,Q(self.defs))
  self.callbacks[base+0x32b40]=(lambda:None,'chkstk')
  self.callbacks[base+0x32ac0]=(self.memset,'memset')
  self.write(base+0x32b40,b'\xc3');self.write(base+0x32ac0,b'\xc3')
  # strrchr is the only CRT import used by the application path.
  self.write(base+0x351c8,Q(self.stub(self.strrchr,'strrchr')))
  if patched:
   self.write(base+self.meta['symbols']['active_iat'],Q(self.stub(lambda:int(active),'WorldSettingsIsActive')))
   self.write(base+self.meta['symbols']['prepare_iat'],Q(self.stub(lambda:1,'WorldSettingsPrepareScene')))
  self.u.hook_add(UC_HOOK_CODE,self.hook)
 def reg(self,n):return self.u.reg_read(n)
 def write(self,a,b):self.u.mem_write(a,b)
 def read(self,a,n):return bytes(self.u.mem_read(a,n))
 def u16(self,a):return struct.unpack('<H',self.read(a,2))[0]
 def u64(self,a):return struct.unpack('<Q',self.read(a,8))[0]
 def cstr(self,a):
  r=bytearray()
  while True:
   b=self.read(a+len(r),1)
   if b==b'\0':return bytes(r)
   r+=b
 def memset(self):self.write(self.reg(UC_X86_REG_RCX),bytes([self.reg(UC_X86_REG_RDX)&255])*self.reg(UC_X86_REG_R8));return self.reg(UC_X86_REG_RCX)
 def strrchr(self):
  a=self.reg(UC_X86_REG_RCX);p=self.cstr(a).rfind(bytes([self.reg(UC_X86_REG_RDX)&255]));return 0 if p<0 else a+p
 def stub(self,fn,name):
  a=self.next_stub;self.next_stub+=0x10;self.write(a,b'\xc3');self.callbacks[a]=(fn,name);return a
 def object(self,addr,methods):
  vt=addr+0x800;self.write(addr,Q(vt))
  for off,fn in methods.items():self.write(vt+off,Q(self.stub(fn,hex(addr)+'+'+hex(off))))
  return addr
 def new_object(self,methods):
  a=self.next_obj;self.next_obj+=0x2000;return self.object(a,methods)
 def hook(self,u,a,n,data):
  if a==self.stop:u.emu_stop();return
  if a in self.callbacks:
   f,name=self.callbacks[a];self.calls.append(name);v=f()
   if v is not None:u.reg_write(UC_X86_REG_RAX,v)
 def run(self,rva,*args):
  sp=0x40100008;self.write(sp,Q(self.stop));self.u.reg_write(UC_X86_REG_RSP,sp)
  for r,v in zip([UC_X86_REG_RCX,UC_X86_REG_RDX,UC_X86_REG_R8,UC_X86_REG_R9],args):self.u.reg_write(r,v)
  self.write(sp+0x28,Q(self.cropcounts));self.write(sp+0x30,Q(8))
  self.u.emu_start(self.base+rva,self.stop+1,count=1000000)
  assert self.reg(UC_X86_REG_RIP)==self.stop,'Native function did not return'
  assert self.reg(UC_X86_REG_RSP)==sp+8,'Unbalanced native stack'
  return self.reg(UC_X86_REG_RAX)&0xffffffff
 def nodes(self,climates,size=128):
  ns=[self.obj+0x100000+i*0x1000 for i in range(len(climates))]
  for i,(a,cl) in enumerate(zip(ns,climates)):
   self.write(a,Q(ns[i-1] if i else 0)+Q(ns[i+1] if i+1<len(ns) else 0))
   self.write(a+0x10,struct.pack('<HHHHIHH',0,0,size,size,i,cl,1))
   self.write(a+0x1e,b'islands\\nord\\n_128x128_0001_2b.scp\0')
   self.write(a+0x15c,b'\1')
  self.write(self.obj+0x53f0,Q(ns[0] if ns else 0));self.write(self.obj+0x53c4,I(len(ns)))
  return ns
 def apply(self,assignments,occurrence_count):
  nodes=self.nodes([2]);node=nodes[0]
  for i in assignments:self.write(node+0x14a+2*i,H(1))
  occurrences=[];changed={};removed=[];crop_masks=[]
  for i in range(occurrence_count):
   slot={}
   def setdef(slot=slot):changed[slot['addr']]=self.reg(UC_X86_REG_RDX)
   def remove(slot=slot):removed.append(slot['addr'])
   addr=self.new_object({0x110:lambda:1,0xf8:lambda:0,0x58:setdef,0xb0:lambda:self.u.reg_write(UC_X86_REG_XMM0,int.from_bytes(struct.pack('<f',40.0),'little')),0xc0:lambda:self.u.reg_write(UC_X86_REG_XMM0,int.from_bytes(struct.pack('<f',40.0),'little')),0xf0:remove,0x118:lambda:1,0x120:lambda:0})
   slot['addr']=addr;occurrences.append(addr)
  def next_occ():
   current=self.reg(UC_X86_REG_RDX);i=occurrences.index(current)+1;return occurrences[i] if i<len(occurrences) else 0
  collection=self.new_object({0x28:lambda:occurrences[0] if occurrences else 0,0x20:next_occ})
  terrain=self.new_object({0x20:lambda:0})
  def property_set():
   if self.reg(UC_X86_REG_RDX)==0xb:crop_masks.append(self.reg(UC_X86_REG_R8))
  island=self.new_object({0x180:property_set,0xa0:lambda:0,0x238:lambda:collection,0x230:lambda:terrain,0xb0:lambda:128,0xa8:lambda:128,0x1f8:lambda:0})
  manager=self.new_object({0x28:lambda:0})
  self.object(self.world,{0x118:lambda:island,0x170:lambda:7,0x150:lambda:manager})
  result=self.run(0xc250,self.obj)
  # Native clears its local copy; occurrence setters above are the observable
  # successful assignments. The original function returns S_OK on shortage.
  return dict(hresult=result,applied=list(changed.values()),removed=len(removed),crop_masks=crop_masks,requested=list(assignments))

def main():
 results=[]
 for base in [0x180000000,0x1a1000000]:
  for climate in range(6):
   for resource in range(7):
    e=NativeScene(base);ns=e.nodes([climate]);r=e.run(0xd4c0,e.obj,0,resource,e.counts)
    expected=resource in [(),(0,2,6),(0,2,5,6),(0,6),(0,1,6),(0,1,3,6)][climate]
    assert r==(0 if expected else 0xffffffff)
    assert e.u16(ns[0]+0x14a+2*resource)==int(expected)
    results.append(dict(kind='mineral_allocator',base=hex(base),climate=climate,resource=resource,result=r,assignment=e.u16(ns[0]+0x14a+2*resource)))
  for climate in range(6):
   for resource in range(17):
    e=NativeScene(base);ns=e.nodes([climate]);r=e.run(0xd1c0,e.obj,0,resource,e.counts)
    expected=bool([0x18000,0xf009,0xf949,0xf06b,0xf6b9,0xf04d][climate]&(1<<resource))
    assert r==(0 if expected else 0xffffffff)
    assert e.u16(ns[0]+0x122+2*resource)==int(expected)
    results.append(dict(kind='crop_allocator',base=hex(base),climate=climate,resource=resource,result=r,assignment=e.u16(ns[0]+0x122+2*resource)))
  for patched,active in [(False,True),(True,True),(True,False)]:
   for assignments,count in [([0,1,2,3,5,6],6),([0,1,2,3,5,6],2),([5],1),([5],0),([],2)]:
    e=NativeScene(base,patched,active);r=e.apply(assignments,count)
    expect=[1661,1561,1562,1563,0,1564,1560]
    assert r['applied']==[expect[i] for i in assignments[:count]]
    assert r['hresult']==(0x80004005 if patched and active and count<len(assignments) else 0)
    results.append(dict(kind='native_application',base=hex(base),patched=patched,active=active,**r))
 out=dict(scope='Original AMD64 allocator and c250 CPU instructions; world, file loading, occurrence methods, rendering and simulation are boundary doubles; no actual game run',checks=results)
 (Path(__file__).parent/'native_results.json').write_text(json.dumps(out,indent=2))
 print(json.dumps(dict(checks=len(results),applications=[x for x in results if x['kind']=='native_application']),indent=2))
if __name__=='__main__':main()
