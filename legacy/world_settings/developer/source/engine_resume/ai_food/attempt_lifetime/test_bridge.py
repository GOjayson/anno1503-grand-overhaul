"""Private native-attempt wrapper argument, token, return and register checks."""
from pathlib import Path
import hashlib,itertools,json,struct,sys
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[2];ROOT=WORK.parent
sys.path.insert(0,str(WORK/'engine_audit'))
from audit import Module
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *
from attempt_bridge import *
m=Module(str(ROOT/'AnnoFrame.dll'));assert hashlib.sha256(m.data).hexdigest()=='046b5ad6f351dfe867ed38ce29fb50a594485b43a32ee90adadc48e850466baf'
assert m.image[SITE:SITE+len(BEFORE)]==BEFORE
assert PARENT in [(e.struct.BeginAddress,e.struct.EndAddress,e.struct.UnwindData) for e in m.pe.DIRECTORY_ENTRY_EXCEPTION]
NV=[UC_X86_REG_RBX,UC_X86_REG_RBP,UC_X86_REG_RSI,UC_X86_REG_RDI,UC_X86_REG_R12,UC_X86_REG_R13,UC_X86_REG_R14,UC_X86_REG_R15]
rows=[]
for base,token,native_bool,final_bool in itertools.product([0x180000000,0x280000000],[0,17,0xfffffffd],[0,1],[0,1]):
 u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,0x120000);u.mem_write(base,m.image)
 STACK=0x31000000;EXT=0x33000000;BEGIN=EXT+0x100;END=EXT+0x200
 u.mem_map(STACK,0x20000);u.mem_map(EXT,0x1000)
 code,names,functions=build_attempt_code(0x100000);u.mem_write(base+0x100000,code)
 u.mem_write(base+SITE,b'\xe8'+struct.pack('<i',names['native_attempt']-SITE-5))
 for address in [BEGIN,END]:u.mem_write(address,b'\xc3')
 u.mem_write(base+names['begin_attempt_iat'],struct.pack('<Q',BEGIN));u.mem_write(base+names['end_attempt_iat'],struct.pack('<Q',END))
 parent_stack=STACK+0x10000;u.reg_write(UC_X86_REG_RSP,parent_stack)
 original={reg:0x1010101000000000+i for i,reg in enumerate(NV)}
 for reg,value in original.items():u.reg_write(reg,value)
 args=[0x1111222233334444,0x5555666677778888,0x9999aaaabbbbcccc,0xddddeeeeffff0001]
 for reg,value in zip([UC_X86_REG_RCX,UC_X86_REG_RDX,UC_X86_REG_R8,UC_X86_REG_R9],args):u.reg_write(reg,value)
 calls=[]
 def ret(machine,result):
  sp=machine.reg_read(UC_X86_REG_RSP);target=struct.unpack('<Q',machine.mem_read(sp,8))[0]
  machine.reg_write(UC_X86_REG_RAX,result);machine.reg_write(UC_X86_REG_RSP,sp+8);machine.reg_write(UC_X86_REG_RIP,target)
 def hook(machine,address,size,_):
  if address in [BEGIN,END,base+0x55a10]:assert machine.reg_read(UC_X86_REG_RSP)%16==8
  if address==BEGIN:
   calls.append('begin');machine.reg_write(UC_X86_REG_RAX,token)
   for reg in [UC_X86_REG_RCX,UC_X86_REG_RDX,UC_X86_REG_R8,UC_X86_REG_R9]:machine.reg_write(reg,0xfeedface)
  if address==base+0x55a10:
   assert [machine.reg_read(reg) for reg in [UC_X86_REG_RCX,UC_X86_REG_RDX,UC_X86_REG_R8,UC_X86_REG_R9]]==args
   calls.append('native-world-start');ret(machine,0xf1e2d3c4b5a69700|native_bool)
  if address==END:
   assert machine.reg_read(UC_X86_REG_RCX)==token and machine.reg_read(UC_X86_REG_RDX)==native_bool
   calls.append('end')
   for reg in NV:
    if reg!=UC_X86_REG_RBP:machine.reg_write(reg,0xabababab)
   machine.reg_write(UC_X86_REG_RAX,final_bool)
  if address==base+SITE+5:machine.emu_stop()
 u.hook_add(UC_HOOK_CODE,hook);u.emu_start(base+SITE,base+SITE+6,count=1000)
 assert calls==(['begin','native-world-start','end'] if token else ['begin'])
 assert u.reg_read(UC_X86_REG_RAX)==(final_bool if token else 0)
 assert u.reg_read(UC_X86_REG_RSP)==parent_stack
 assert all(u.reg_read(reg)==value for reg,value in original.items())
 rows.append(dict(base=hex(base),token=token,native_AL=native_bool,end_result=final_bool,calls=calls,passed=True))
result=dict(scope=__doc__,actual_game_runs=0,source_sha256=hashlib.sha256(m.data).hexdigest(),hook_rva=hex(SITE),preimage=BEFORE.hex(),unwind_type='ordinary unchained',cases=rows)
(HERE/'bridge_results.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')
print(json.dumps(dict(bridge_cases=len(rows),actual_game_runs=0)))
