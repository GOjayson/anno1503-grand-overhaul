"""Bounded execution of original/patched HE machine code, never a game run."""
from pathlib import Path
import hashlib,json,struct,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'WorldSettings_Work/_tools'));sys.path.insert(0,str(HERE))
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE,UC_HOOK_MEM_WRITE,UcError
from unicorn.x86_const import *
from navigation_patch import transform_welt_navigation,PATCH_MANIFEST,runtime_navigation_edits
ORIGINAL=(ROOT/'AnnoWelt.dll').read_bytes();PATCHED=transform_welt_navigation(ORIGINAL)
assert hashlib.sha256(ORIGINAL).hexdigest()==PATCH_MANIFEST['original_sha256']
assert hashlib.sha256(PATCHED).hexdigest()==PATCH_MANIFEST['output_sha256_from_original']

REGS=[UC_X86_REG_RBX,UC_X86_REG_RBP,UC_X86_REG_RSI,UC_X86_REG_RDI,UC_X86_REG_R12,UC_X86_REG_R13,UC_X86_REG_R14,UC_X86_REG_R15]
class NewFailure(Exception):pass
class Native:
 def __init__(self,blob,base=0x180000000,nav=True):
  self.u=Uc(UC_ARCH_X86,UC_MODE_64);self.base=base;self.patched=blob==PATCHED
  p=pefile.PE(data=blob);p.relocate_image(base);im=p.get_memory_mapped_image()
  self.u.mem_map(base,(len(im)+4095)&~4095);self.u.mem_write(base,bytes(im))
  self.obj=0x40000100;self.pool=0x40010000;self.world=0x40020000;self.vt=0x40028000;self.rect=0x40029000;self.stop=0x60000000;self.stack=0x50000000
  self.u.mem_map(0x40000000,0x40000);self.u.mem_write(0x40000000,b'\xa5'*0x40000)
  self.u.mem_map(self.stack,0x20000);self.u.mem_map(self.stop,0x1000);self.u.mem_write(self.stop,b'\xcc')
  self.w64(0x40030010,self.stack);self.u.reg_write(UC_X86_REG_GS_BASE,0x40030000)
  self.u.mem_map(0x70000000,0x800000);self.heap=0x70000000;self.allocated={};self.freed=[];self.zeroes=[];self.native_writes=[];self.fail_new=False;self.vector_grows=0
  self.object_size=0x6000 if self.patched else 0x3e48
  self.allocated[self.obj]=self.object_size
  self.u.mem_write(self.pool,b'\0'*0x80);self.w32(self.pool+0x68,0x2000)
  self.w64(self.world,self.vt);self.w64(self.vt+0xb0,base+0xc7c90);self.w64(self.vt+0xb8,base+0xc7ca0)
  self.w64(self.vt+0x1e0,self.stop+0x100);self.raster_calls=[]
  self.u.hook_add(UC_HOOK_CODE,self.hook)
  self.u.hook_add(UC_HOOK_MEM_WRITE,self.write_hook)
 def w32(self,a,v):self.u.mem_write(a,struct.pack('<I',v&0xffffffff))
 def w64(self,a,v):self.u.mem_write(a,struct.pack('<Q',v&0xffffffffffffffff))
 def r32(self,a):return struct.unpack('<I',self.u.mem_read(a,4))[0]
 def r64(self,a):return struct.unpack('<Q',self.u.mem_read(a,8))[0]
 def ret(self,v=0):
  sp=self.u.reg_read(UC_X86_REG_RSP);pc=self.r64(sp);self.u.reg_write(UC_X86_REG_RAX,v);self.u.reg_write(UC_X86_REG_RSP,sp+8);self.u.reg_write(UC_X86_REG_RIP,pc)
 def alloc(self,n):
  if self.fail_new:raise NewFailure('Modeled throwing native operator new')
  assert 0<n<0x100000,n
  ptr=(self.heap+31)&~15;self.heap=ptr+n+32;assert self.heap<0x70800000
  self.u.mem_write(ptr-16,b'\xce'*16);self.u.mem_write(ptr,b'\xcd'*n);self.u.mem_write(ptr+n,b'\xec'*16);self.allocated[ptr]=n
  return ptr
 def hook(self,u,a,n,unused):
  rcx=u.reg_read(UC_X86_REG_RCX);rdx=u.reg_read(UC_X86_REG_RDX);r8=u.reg_read(UC_X86_REG_R8)
  if a==self.base+0xe46bc:self.ret(self.alloc(rcx))
  elif a==self.base+0xe46f8:
   if rcx:
    assert rcx in self.allocated,('unknown/delete twice',hex(rcx),hex(rdx))
    assert self.allocated[rcx]==rdx,('delete size mismatch',hex(rcx),self.allocated[rcx],rdx)
    self.freed.append((rcx,rdx));del self.allocated[rcx]
   self.ret()
  elif a==self.base+0xe58ea:
   assert r8<0x100000
   u.mem_write(rcx,bytes([rdx&255])*r8);self.zeroes.append((rcx,r8));self.ret(rcx)
  elif a==self.base+0xe62f6:
   assert r8<0x100000
   if r8:u.mem_write(rcx,bytes(u.mem_read(rdx,r8)))
   self.ret(rcx)
  elif a==self.stop+0x100:
   # Only world raster sampling is external. Native helper69140 builds its
   # 8x8 rectangle and supplies node+4; native70cd0 owns the node allocation.
   sp=u.reg_read(UC_X86_REG_RSP);dst=self.r64(sp+0x28);stride=self.r32(sp+0x30)
   rect=struct.unpack('<iiii',u.mem_read(u.reg_read(UC_X86_REG_R9),16))
   assert stride==8 and rect[2]-rect[0]==8 and rect[3]-rect[1]==8
   u.mem_write(dst,b'\x09'*64);self.raster_calls.append(rect);self.ret()
  elif a==self.base+0x2b480:self.vector_grows+=1
 def write_hook(self,u,access,address,size,value,unused):
  if self.obj-0x100<=address<self.obj+0x10000:self.native_writes.append((address,size))
 def run(self,rva,rcx=0,rdx=0,r8=0,r9=0,check_regs=True,count=1000000):
  sp=self.stack+0x1eff8;self.w64(sp,self.stop)
  saved={r:0x1111222233330000+i for i,r in enumerate(REGS)}
  for r,v in saved.items():self.u.reg_write(r,v)
  for r,v in [(UC_X86_REG_RSP,sp),(UC_X86_REG_RCX,rcx),(UC_X86_REG_RDX,rdx),(UC_X86_REG_R8,r8),(UC_X86_REG_R9,r9)]:self.u.reg_write(r,v&0xffffffffffffffff)
  self.u.emu_start(self.base+rva,self.stop,count=count)
  assert self.u.reg_read(UC_X86_REG_RIP)==self.stop,('not returned',hex(self.u.reg_read(UC_X86_REG_RIP)))
  assert self.u.reg_read(UC_X86_REG_RSP)==sp+8
  if check_regs:
   for r,v in saved.items():assert self.u.reg_read(r)==v,('nonvolatile changed',r,hex(self.u.reg_read(r)),hex(v))
  return self.u.reg_read(UC_X86_REG_RAX)
 def construct(self):
  assert self.run(0x6c120,self.obj,self.pool,self.world)==self.obj
  assert self.r64(self.obj+0x35e8)==self.base+0xf4f20
  assert self.r64(self.obj+0x3600)==self.pool
  assert self.r64(self.obj+0x3e38)==self.world
  assert self.r64(self.obj+0x3e08)!=0
  self.headers=[self.r64(self.obj+0x2030),self.r64(self.obj+0x3e08)]
 def initialize(self,size,refinement=True):
  self.w32(self.world+0x1d8,size);self.w32(self.world+0x1dc,size)
  self.u.mem_write(self.rect,struct.pack('<IIII',0,0,size,size))
  sp=self.stack+0x1d000;self.w32(sp+0x50,0)
  for r,v in [(UC_X86_REG_RSP,sp),(UC_X86_REG_RCX,self.obj+8),(UC_X86_REG_R8,self.rect),(UC_X86_REG_R9,0)]:self.u.reg_write(r,v)
  self.u.emu_start(self.base+0x691e0,self.base+0x69323,count=100000)
  assert(self.r32(self.obj+0x18),self.r32(self.obj+0x1c))==(size//64,size//64)
  if not refinement:return
  self.zeroes=[];self.u.reg_write(UC_X86_REG_RSP,sp);self.u.reg_write(UC_X86_REG_R13,self.obj);self.u.reg_write(UC_X86_REG_R15,sp+0x30)
  self.u.emu_start(self.base+0x6abc8,self.base+0x6ac67,count=100000)
  assert(self.r32(self.obj+0x35f0),self.r32(self.obj+0x35f4))==(size//8,size//8)
  rows=size//64;start=self.obj+(0x4000 if self.patched else 0x3608);stride=256 if self.patched else 128
  assert self.zeroes==([(start,8192)]if self.patched else[(start+y*stride,rows*8)for y in range(rows)])
  assert max(a+n for a,n in self.zeroes)<=self.obj+self.object_size
  assert all(a+n<=b for(a,n),(b,_)in zip(self.zeroes,self.zeroes[1:]))
  self.canaries()
 def canaries(self):
  assert bytes(self.u.mem_read(self.obj-16,16))==b'\xa5'*16
  assert bytes(self.u.mem_read(self.obj+self.object_size,16))==b'\xa5'*16
  for ptr,n in self.allocated.items():
   if ptr==self.obj:continue
   assert bytes(self.u.mem_read(ptr-16,16))==b'\xce'*16
   assert bytes(self.u.mem_read(ptr+n,16))==b'\xec'*16,(hex(ptr),n)
 def cells(self,size):
  n=size//64;out=[]
  for y in range(n):
   for x in range(n):
    p=self.run(0x67fe0,self.obj+0x35e8,x*8,y*8)
    slot=self.obj+(0x4000 if self.patched else 0x3608)+((32 if self.patched else 16)*y+x)*8
    assert self.r64(slot)==p
    assert bytes(self.u.mem_read(p,512))==b'\0'*512
    marker=struct.pack('<QQ',x,y);self.u.mem_write(p+496,marker)
    assert self.run(0x67fe0,self.obj+0x35e8,x*8+7,y*8+7)==p
    assert bytes(self.u.mem_read(p+496,16))==marker
    out.append(p)
  assert len(set(out))==n*n;self.canaries()
  return out
 def destruct(self):
  self.run(0x6c2f0,self.obj,1)
  assert(self.obj,self.object_size)in self.freed
  # Tree header/freelist allocation freed, pool block lifetime stays external.
  assert all((ptr,0x30)in self.freed for ptr in self.headers)
  self.canaries()

def main():
 results=[]
 for base in [0x180000000,0x2a0000000]:
  for size in [256,512,1024]:
   old,new=Native(ORIGINAL,base),Native(PATCHED,base)
   old.construct();new.construct()
   assert bytes(old.u.mem_read(old.obj,0x3e48))==bytes(new.u.mem_read(new.obj,0x3e48))
   old.initialize(size);new.initialize(size)
   a,b=old.cells(size),new.cells(size);assert a==b
   old.destruct();new.destruct()
   results.append(dict(case='old_size_equivalence',base=hex(base),size=size,cells=len(a),status='PASS'))
  for size in [2048]:
   n=Native(PATCHED,base);n.construct();n.initialize(size);cells=n.cells(size)
   assert len(cells)==1024
   blocks=[(p,z)for p,z in n.allocated.items()if z==0x2010]
   assert len(blocks)==64,(len(blocks),n.vector_grows)
   assert n.vector_grows>=2 # Execute native vector expansion as well as 8KiB pool rollover.
   count_before=len(blocks)
   n.run(0x69030,n.obj+0x35e8)
   n.initialize(size);again=n.cells(size)
   assert len([z for z in n.allocated.values()if z==0x2010])==count_before
   assert len(set(again))==1024
   n.destruct()
   results.append(dict(case='huge_full_grid_pool_reset_delete',base=hex(base),size=size,cells=1024,native_pool_blocks=len(blocks),native_vector_growths=n.vector_grows,status='PASS'))
  # Actual fine-node getter and initializer, with only world terrain sampling
  # modeled. Cover a node in every outer cell plus world/boundary edge cases.
  n=Native(PATCHED,base);n.construct();n.initialize(2048)
  coords=[(x*64,y*64)for y in range(32)for x in range(32)]+[(7,7),(63,63),(1023,1023),(1024,1024),(2047,2047),(2040,0),(0,2040)]
  nodes={};node_coords={}
  for x,y in coords:
   p=n.run(0x70490,n.obj+0x35e8,x,y)
   key=(x//8,y//8)
   if key not in node_coords:node_coords[key]=(x,y)
   assert struct.unpack('<HH',n.u.mem_read(p,4))==node_coords[key]
   assert bytes(n.u.mem_read(p+4,64))==b'\x09'*64
   assert n.run(0x70490,n.obj+0x35e8,x,y)==p
   if key in nodes:assert nodes[key]==p
   else:nodes[key]=p
  assert len(set(nodes.values()))==len(nodes)
  assert len(n.raster_calls)==len(nodes)
  for x,y in [(2048,0),(0,2048),(-8,0),(0,-8)]:assert n.run(0x70490,n.obj+0x35e8,x,y)==0
  n.canaries();n.run(0x69030,n.obj+0x35e8);n.destruct()
  results.append(dict(case='huge_native_fine_node_get_write_and_bounds',base=hex(base),outer_cells=1024,unique_nodes=len(nodes),status='PASS',modeled='Only world8x8 terrain raster sampling; getter, pooling, node initialization and pointer writes execute native code.'))
  # The shared helper must keep its original layout for every other vtable.
  for vt in [0xf4f20-8,0xf4f20+8,0xf4cd0]:
   old,new=Native(ORIGINAL,base),Native(PATCHED,base)
   old.construct();new.construct()
   for n in [old,new]:
    n.w64(n.obj+0x35e8,n.base+vt)
    n.u.mem_write(n.obj+0x3608,b'\0'*2048)
   for y in range(16):
    for x in range(16):
     assert old.run(0x67fe0,old.obj+0x35e8,x*8+7,y*8+7)==new.run(0x67fe0,new.obj+0x35e8,x*8+7,y*8+7)
   assert bytes(old.u.mem_read(old.obj,0x3e48))==bytes(new.u.mem_read(new.obj,0x3e48))
   assert bytes(new.u.mem_read(new.obj+0x4000,8192))==b'\xa5'*8192
   old.canaries();new.canaries()
   results.append(dict(case='shared_non_ship_helper_equivalence',base=hex(base),vtable_rva=hex(vt),cells=256,status='PASS'))
  # Invalid negative inputs are only checked for native arithmetic equivalence;
  # preseed cached pointers to avoid undefined/out-of-bound block allocations.
  for vt in [0xf4f20,0xf4cd0]:
   old,new=Native(ORIGINAL,base),Native(PATCHED,base)
   old.construct();new.construct()
   for n in [old,new]:n.w64(n.obj+0x35e8,n.base+vt)
   for x,y in [(-7,0),(0,-7),(-7,-7),(-8,8),(8,-8),(-9,-9),(127,127)]:
    trunc=lambda a:int(a/8)
    a=old.obj+0x3608+(trunc(x)+trunc(y)*16)*8
    b=new.obj+(0x4000 if vt==0xf4f20 else 0x3608)+(trunc(x)+trunc(y)*(32 if vt==0xf4f20 else 16))*8
    marker=0x1234567812345678;old.w64(a,marker);new.w64(b,marker)
    assert old.run(0x67fe0,old.obj+0x35e8,x,y)==marker
    assert new.run(0x67fe0,new.obj+0x35e8,x,y)==marker
   results.append(dict(case='signed_index_arithmetic',base=hex(base),vtable_rva=hex(vt),coordinates=7,status='PASS'))
 
 # Patch-composition and transaction preimage rejection, no mutations on failure.
 dev7=(ROOT/'WorldSettings_Work/anno1503_food_world_dev7/native/AnnoWelt.world.dll').read_bytes()
 assert hashlib.sha256(dev7).hexdigest()=='059ecd1dcb2139b350f50a2805d811eff89e61cead2733ca9aedb6da83058319'
 transform_welt_navigation(dev7)
 for candidate in [PATCHED,ORIGINAL[:100],ORIGINAL[:1000]+b'\0'+ORIGINAL[1001:]]:
  if len(candidate)==len(ORIGINAL)and candidate!=PATCHED:continue
  try:transform_welt_navigation(candidate)
  except ValueError:pass
  else:raise AssertionError('Expected preimage rejection')
 for e in PATCH_MANIFEST['edits']:
  p=pefile.PE(data=ORIGINAL).get_offset_from_rva(e['rva']);bad=bytearray(ORIGINAL);bad[p]^=1;snapshot=bytes(bad)
  try:transform_welt_navigation(bad)
  except ValueError:assert bytes(bad)==snapshot
  else:raise AssertionError('Expected corrupted site rejection')
 assert all(len(bytes.fromhex(e['before']))<=32 for e in runtime_navigation_edits())
 results.append(dict(case='original_dev7_composition_and_reject_partial_or_corrupt',regions=len(PATCH_MANIFEST['edits']),runtime_chunks=len(runtime_navigation_edits()),status='PASS'))
 
 # Model native throwing operator new; no successful object deletion may follow.
 for blob in [ORIGINAL,PATCHED]:
  n=Native(blob);n.fail_new=True
  try:n.construct()
  except NewFailure:pass
  else:raise AssertionError('Expected modeled new failure')
  assert n.freed==[]
  n.canaries()
 results.append(dict(case='modeled_throwing_new_failure_original_and_patch',status='PASS',limitation='Does not execute Windows exception unwinding or a real out-of-memory condition.'))
 
 report=dict(schema=1,test_type='Native bounded Unicorn execution, not an actual Anno game run',original_sha256=hashlib.sha256(ORIGINAL).hexdigest(),patched_sha256=hashlib.sha256(PATCHED).hexdigest(),external_models=['operator new / sized delete with allocation-size and guard checks','CRT memset returning destination and memmove','8x8 world terrain raster sampling callback','throwing operator-new interruption only'],native_executed=['constructor0x6c120','coarse initializer0x691e0 through0x69323','refinement initializer0x6abc8 through0x6ac67','shared accessor0x67fe0 including cached and fresh paths','fine node getter0x70490 and constructor0x70cd0 plus world rectangle builder0x69140','pool allocator0x5fc60','native vector growth0x2b480 and ownership replacement','pool reset0x69030/0x5f880','deleting destructor0x6c2f0 including native tree/header cleanup'],cases=results,status='PASS',not_proven=['end-to-end route search across actual island obstacles','live frame/rendering/AI/save behavior','Windows SEH unwinding and actual memory exhaustion'])
 (HERE/'navigation_native_results.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(dict(status='PASS',cases=len(results),report=str(HERE/'navigation_native_results.json'))))

if __name__=="__main__":main()
