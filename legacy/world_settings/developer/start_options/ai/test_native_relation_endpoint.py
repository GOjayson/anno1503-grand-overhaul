"""Execute actual AMD64 AnnoWelt diplomacy endpoint with strict player doubles.

This establishes that the gated type=2,state=3 operation sets reciprocal war
state and clears trade/alliance; state=1 is the existing peace proposal path.
It does not execute military simulation or a running game.
"""
from pathlib import Path
import hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'WorldSettings_Work/engine_audit'))
from audit import Module
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *
m=Module(str(ROOT/'AnnoWelt.dll'))
assert hashlib.sha256(m.data).hexdigest()=='ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9'
cases=[]
for base in [0x180000000,0x280000000]:
 u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,(len(m.image)+4095)&~4095);u.mem_write(base,m.image)
 u.mem_map(0x31000000,0x10000);u.mem_map(0x32000000,0x40000);u.mem_map(0x33000000,0x2000)
 world=0x32002000;src=0x32010000;tgt=0x32012000;pvt=0x32014000
 u.mem_write(src,struct.pack('<Q',pvt));u.mem_write(tgt,struct.pack('<Q',pvt))
 for off,stub in [(0x100,0x33000100),(0x108,0x33000120),(0x190,0x33000140),(0x88,0x33000160),(0x188,0x33000180)]:u.mem_write(pvt+off,struct.pack('<Q',stub))
 relations={};events=[]
 def ret(value=0):
  sp=u.reg_read(UC_X86_REG_RSP);to=struct.unpack('<Q',u.mem_read(sp,8))[0]
  u.reg_write(UC_X86_REG_RAX,value);u.reg_write(UC_X86_REG_RSP,sp+8);u.reg_write(UC_X86_REG_RIP,to)
 def player(machine,address,size,unused):
  rcx=u.reg_read(UC_X86_REG_RCX);rdx=u.reg_read(UC_X86_REG_RDX);r8=u.reg_read(UC_X86_REG_R8);r9=u.reg_read(UC_X86_REG_R9)
  if address==base+0xdf3c0:events.append([rdx,r8]);ret();return
  assert rcx in [src,tgt]
  if address==0x33000100:assert r8 in [src,tgt] and r8!=rcx;ret(relations[rcx][rdx])
  elif address==0x33000120:assert r8 in [src,tgt] and r8!=rcx;relations[rcx][rdx]=r9;ret(1)
  elif address==0x33000140:ret(0) # CPU/no local human notification; no GUI primitive
  elif address==0x33000160:ret(2 if rcx==src else 0)
  elif address==0x33000180:assert rdx==7;ret(1) # changed-relation notification bit
  else:raise AssertionError(hex(address))
 for stub in [0x33000100,0x33000120,0x33000140,0x33000160,0x33000180,base+0xdf3c0]:u.hook_add(UC_HOOK_CODE,player,begin=stub,end=stub)
 for state in [3,1,0]:
  relations={src:{0:3,1:3,2:3 if state!=3 else 0},tgt:{0:3,1:3,2:3 if state!=3 else 0}};events=[]
  sp=0x31008008;u.mem_write(sp,struct.pack('<Q',0x33000000));u.mem_write(sp+0x28,struct.pack('<Q',tgt))
  for reg,value in [(UC_X86_REG_RSP,sp),(UC_X86_REG_RCX,world),(UC_X86_REG_RDX,2),(UC_X86_REG_R8,state),(UC_X86_REG_R9,src)]:u.reg_write(reg,value)
  u.emu_start(base+0xdf460,0x33000000,count=10000)
  assert u.reg_read(UC_X86_REG_RIP)==0x33000000
  if state==3:assert relations[src]==relations[tgt]=={0:0,1:0,2:3}
  elif state==1:assert relations[src][2]==1 and relations[tgt][2]==2
  else:assert relations[src][2]==relations[tgt][2]==0
  cases.append(dict(image_base=hex(base),input_relation_type=2,input_state=state,source=relations[src],target=relations[tgt],native_events=events))
result=dict(scope=__doc__,cases=cases,passed=True,actual_game_runs=0)
(HERE/'native_endpoint_results.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')
print(json.dumps(dict(passed=True,native_endpoint_cases=len(cases),actual_game_runs=0),indent=2))
