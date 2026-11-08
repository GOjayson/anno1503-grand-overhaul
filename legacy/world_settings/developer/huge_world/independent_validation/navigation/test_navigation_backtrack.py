"""Run real HE predecessor backtracking against adversarial seeded paths."""
from pathlib import Path
import json,struct,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from test_navigation_patch import *

def snake(count):
 coords=[]
 for y in range(256):
  for x in(range(256)if y%2==0 else range(255,-1,-1)):
   coords.append((x,y))
   if len(coords)==count:return coords
 raise ValueError('Too long')

def seed(n,coords,cycle=False):
 blocks={};directions={(1,0):0,(1,-1):1,(0,-1):2,(-1,-1):3,(-1,0):4,(-1,1):5,(0,1):6,(1,1):7}
 for x,y in coords:
  key=(x//8,y//8)
  if key not in blocks:
   p=n.alloc(0x104);n.u.mem_write(p,b'\0'*0x104);n.u.mem_write(p+0x100,struct.pack('<HH',key[0]*8,key[1]*8));n.w64(n.obj+0x30+(key[0]+key[1]*32)*8,p);blocks[key]=p
 for k,(x,y)in enumerate(coords):
  p=blocks[(x//8,y//8)]+((x%8)+(y%8)*8)*4
  if k+1<len(coords):nx,ny=coords[k+1]
  elif cycle:nx,ny=coords[0]
  else:n.u.mem_write(p+2,b'\0');continue
  n.u.mem_write(p+2,bytes([0x80+directions[(nx-x,ny-y)]]))
 return blocks

def prepare(n):
 n.construct();n.initialize(2048,refinement=False)

def start_frame(n):
 entrysp=n.stack+0x1eff8;n.w64(entrysp,n.stop)
 saved={r:0x1111222233330000+i for i,r in enumerate(REGS)}
 for r,v in saved.items():n.u.reg_write(r,v)
 xmm6=0x12345678123456781234567812345678;xmm7=0x23456789234567892345678923456789
 for r,v in[(UC_X86_REG_RSP,entrysp),(UC_X86_REG_RCX,n.obj),(UC_X86_REG_XMM1,0),(UC_X86_REG_XMM2,0),(UC_X86_REG_XMM6,xmm6),(UC_X86_REG_XMM7,xmm7)]:n.u.reg_write(r,v)
 n.u.emu_start(n.base+0x6aa70,n.base+0x6ab4b,count=100000)
 frame=n.u.reg_read(UC_X86_REG_RSP)
 assert frame==entrysp-0x1088
 assert bytes(n.u.mem_read(frame+0x1030,16))==xmm7.to_bytes(16,'little')
 assert bytes(n.u.mem_read(frame+0x1040,16))==xmm6.to_bytes(16,'little')
 return entrysp,frame,saved,xmm6,xmm7

reports=[]
for base in [0x180000000,0x2a0000000]:
 for count in [1,2,16,256,1023,1024]:
  output=[]
  for blob in [ORIGINAL,PATCHED]:
   n=Native(blob,base);prepare(n);coords=snake(count);seed(n,coords)
   entrysp,frame,saved,xmm6,xmm7=start_frame(n)
   n.u.emu_start(n.base+0x6ab4b,n.base+0x6aba5,count=2000000)
   assert n.u.reg_read(UC_X86_REG_RIP)==n.base+0x6aba5
   out=bytes(n.u.mem_read(frame+0x30,count*4));assert out==b''.join(struct.pack('<HH',*xy)for xy in coords)
   assert n.u.reg_read(UC_X86_REG_R15)==frame+0x30+count*4
   assert bytes(n.u.mem_read(frame+0x1030,16))==xmm7.to_bytes(16,'little')
   assert bytes(n.u.mem_read(frame+0x1040,16))==xmm6.to_bytes(16,'little')
   assert n.u.reg_read(UC_X86_REG_R14)==saved[UC_X86_REG_R14]
   n.canaries();output.append(out)
  assert output[0]==output[1]
  reports.append(dict(case='predecessor_chain_original_equivalence',base=hex(base),total_pairs=count,status='PASS'))
 for case in ['overlong_1025','cycle']:
  n=Native(PATCHED,base);prepare(n);coords=snake(1025)if case!='cycle'else[(0,0),(1,0)];seed(n,coords,cycle=case=='cycle')
  entrysp,frame,saved,xmm6,xmm7=start_frame(n)
  n.u.emu_start(n.base+0x6ab4b,n.stop,count=2000000)
  assert n.u.reg_read(UC_X86_REG_RIP)==n.stop
  assert n.u.reg_read(UC_X86_REG_RAX)==0xffffffff
  assert n.u.reg_read(UC_X86_REG_RSP)==entrysp+8
  for r,v in saved.items():assert n.u.reg_read(r)==v,(case,r)
  assert n.u.reg_read(UC_X86_REG_XMM6)==xmm6
  assert n.u.reg_read(UC_X86_REG_XMM7)==xmm7
  assert bytes(n.u.mem_read(frame+0x1030,16))==xmm7.to_bytes(16,'little')
  assert bytes(n.u.mem_read(frame+0x1040,16))==xmm6.to_bytes(16,'little')
  expected=(coords[:1024]if case!='cycle'else[coords[k%2]for k in range(1024)])
  assert bytes(n.u.mem_read(frame+0x30,4096))==b''.join(struct.pack('<HH',*xy)for xy in expected)
  n.canaries()
  reports.append(dict(case='guard_'+case,base=hex(base),total_pairs_written=1024,failure_return=-1,all_nonvolatile_registers_and_saved_xmm='intact',status='PASS'))
 # Demonstrate the defect with the original code in bounded emulation only.
 n=Native(ORIGINAL,base);prepare(n);coords=snake(1025);seed(n,coords)
 _,frame,_,_,xmm7=start_frame(n)
 n.u.emu_start(n.base+0x6ab4b,n.base+0x6aba5,count=2000000)
 assert n.u.reg_read(UC_X86_REG_R15)==frame+0x1034
 assert bytes(n.u.mem_read(frame+0x1030,4))==struct.pack('<HH',*coords[-1])
 assert bytes(n.u.mem_read(frame+0x1030,16))!=xmm7.to_bytes(16,'little')
 reports.append(dict(case='original_overwrite_reproduced_in_emulator',base=hex(base),overwritten='first4bytes of savedXMM7',status='PASS_EXPECTED_ORIGINAL_DEFECT'))
 # Execute the real caller's -1 branch, native fine reset and native coarse
 # reset. Only its A* queue result/source virtuals are supplied by fixtures;
 # the complete guarded backtracker and failure epilog execute again.
 n=Native(PATCHED,base);prepare(n);seed(n,snake(1025))
 private_vt=n.vt+0x400;n.u.mem_write(private_vt,bytes(n.u.mem_read(n.r64(n.obj+8),0x200)))
 for off,stub in[(0x110,0x200),(0x130,0x210),(0x138,0x220),(0x140,0x230)]:n.w64(private_vt+off,n.stop+stub)
 n.w64(n.obj+8,private_vt);calls={'guard':0,'fine_reset':0,'coarse_reset':0}
 def fixture(u,a,length,unused):
  if a==n.stop+0x200:n.ret(1)
  elif a==n.stop+0x210:n.ret(n.rect+0x100)
  elif a in[n.stop+0x220,n.stop+0x230]:u.reg_write(UC_X86_REG_XMM0,0);n.ret()
  elif a==n.base+PATCH_MANIFEST['backtrack_failure_rva']:calls['guard']+=1
  elif a==n.base+0x69030:calls['fine_reset']+=1
  elif a==n.base+0x69950:calls['coarse_reset']+=1
 n.u.hook_add(UC_HOOK_CODE,fixture)
 assert n.run(0x6b490,n.obj)==0
 assert calls==dict(guard=1,fine_reset=1,coarse_reset=1),calls
 assert n.r64(n.pool+0x50)==0 and n.r64(n.pool+0x58)==0
 n.canaries();n.destruct()
 reports.append(dict(case='native_caller_minus_one_cleanup',base=hex(base),caller_return=0,calls=calls,status='PASS',fixtures='A* result queue/source virtuals; backtracker and both resets native.'))

report=dict(status='PASS',type='Bounded native Unicorn execution; not a game run or complete A* route search',input_sha256=PATCH_MANIFEST['original_sha256'],patched_sha256=PATCH_MANIFEST['output_sha256_from_original'],cases=reports,real_native_functions=['0x6aa70 frame and predecessor backtracking','0x6f0b0 direction traversal','0x70d40 coarse block-neighbour lookup','0x70550 coarse grid accessor','new in-frame guard/failure epilog','0x6b490 failure consumer','0x69030 fine reset','0x69950 coarse reset'],external_models=['global allocation/deletion and CRT routines','seeded valid predecessor path and fixture A* queue/source virtuals for caller test'],limitation='Does not prove optimality or complete A* behavior for all island-obstacle arrangements. Overlong/cyclic predecessor paths are safely rejected before saved-frame overwrite.')
(HERE/'navigation_backtrack_results.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(status='PASS',cases=len(reports))))
