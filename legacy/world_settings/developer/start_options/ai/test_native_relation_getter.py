"""Execute native player ID, war-state getter and hostility query; no doubles."""
from pathlib import Path
import hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'WorldSettings_Work/engine_audit'));from audit import Module
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64
from unicorn.x86_const import *
m=Module(str(ROOT/'AnnoWelt.dll'));assert hashlib.sha256(m.data).hexdigest()=='ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9'
assert m.image[0x8d00:0x8d05]==bytes.fromhex('48634108c3')
cases=[]
for base in [0x180000000,0x280000000]:
 u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,(len(m.image)+4095)&~4095);u.mem_write(base,m.image)
 u.mem_map(0x31000000,0x10000);u.mem_map(0x32000000,0x10000);u.mem_map(0x33000000,0x1000)
 src=0x32002000;tgt=0x32004000;vt=base+0xfabe0
 def put(p,fmt,*v):u.mem_write(p,struct.pack(fmt,*v))
 put(src,'<Q',vt);put(tgt,'<Q',vt);put(vt+0x88,'<Q',base+0x8d00);put(vt+0x100,'<Q',base+0x9a6d0)
 def call(rva,rcx,rdx,r8):
  sp=0x31008008;put(sp,'<Q',0x33000000)
  for reg,value in [(UC_X86_REG_RSP,sp),(UC_X86_REG_RCX,rcx),(UC_X86_REG_RDX,rdx),(UC_X86_REG_R8,r8)]:u.reg_write(reg,value)
  u.emu_start(base+rva,0x33000000,count=10000);assert u.reg_read(UC_X86_REG_RIP)==0x33000000
  return u.reg_read(UC_X86_REG_RAX)
 for ident in [0,1,3,31]:
  put(tgt+8,'<I',ident)
  for state in range(5):
   put(src+0x1da+ident*6,'<B',state)
   assert call(0x9a6d0,src,2,tgt)==state and call(0xd3cf0,0,src,tgt)==int(state!=0)
   cases.append(dict(image_base=hex(base),target_id=ident,state=state,getter=state,native_hostile=state!=0))
result=dict(scope=__doc__,cases=cases,passed=True,native_instruction_cases=len(cases),actual_game_runs=0,getter_layout='source + target.GetId()*6 + 0x1da',native_getid_rva='0x8d00',native_getstate_rva='0x9a6d0',native_hostility_rva='0xd3cf0')
(HERE/'native_relation_getter_results.json').write_text(json.dumps(result,indent=2)+'\n','utf-8');print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2))
