"""Execute generated call wrapper and native failure epilogue/caller cleanup.

Original instructions execute in Unicorn. The validation callback, operating
system calls, facade resource-close primitive and deleting-destructor body are
explicit boundaries. No real game, renderer or strategy simulation executes.
"""
from pathlib import Path
import hashlib,itertools,json,struct,sys
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[2];ROOT=WORK.parent
sys.path.insert(0,str(WORK/'engine_audit'))
from audit import Module
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *
from postprofile_bridge import *
m=Module(str(ROOT/'AnnoFrame.dll'))
assert hashlib.sha256(m.data).hexdigest()=='046b5ad6f351dfe867ed38ce29fb50a594485b43a32ee90adadc48e850466baf'
assert m.image[SITE:SITE+len(BEFORE)]==BEFORE
assert PARENT in [(e.struct.BeginAddress,e.struct.EndAddress,e.struct.UnwindData) for e in m.pe.DIRECTORY_ENTRY_EXCEPTION]
assert struct.unpack_from('<Q',m.image,0xa1788+0xb0)[0]-m.base==0x1ed30
assert struct.unpack_from('<Q',m.image,0xa1788+0x18)[0]-m.base==0x24250
assert m.image[0x57470:0x57478]==bytes.fromhex('84c00f849b000000')
rows=[];cleanup=[]
NV=[UC_X86_REG_RBX,UC_X86_REG_RBP,UC_X86_REG_RSI,UC_X86_REG_RDI,UC_X86_REG_R12,UC_X86_REG_R13,UC_X86_REG_R14,UC_X86_REG_R15]
for base,valid,r13 in itertools.product([0x180000000,0x280000000],[0,1,2,0xffffffff],[0,0x12345fffffffd]):
 u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,0x120000);u.mem_write(base,m.image)
 STACK=0x31000000;OBJ=0x32000000;EXT=0x33000000;STOP=EXT+0x800;CALLBACK=EXT+0x100
 for address,size in [(STACK,0x20000),(OBJ,0x10000),(EXT,0x10000)]:u.mem_map(address,size)
 code,names,functions=build_postprofile_code(0x100000);u.mem_write(base+0x100000,code)
 u.mem_write(base+SITE,b'\xe8'+struct.pack('<i',names['postprofile']-SITE-5))
 u.mem_write(base+names['after_profiles_iat'],struct.pack('<Q',CALLBACK));u.mem_write(CALLBACK,b'\xc3');u.mem_write(STOP,b'\xc3')
 rsp=STACK+0x10008;u.mem_write(rsp,struct.pack('<Q',STOP));u.reg_write(UC_X86_REG_RSP,rsp)
 original={reg:0x10101010+i for i,reg in enumerate(NV)}
 for reg,value in original.items():u.reg_write(reg,value)
 u.reg_write(UC_X86_REG_RCX,OBJ);u.reg_write(UC_X86_REG_RDX,0);u.reg_write(UC_X86_REG_XMM6,0x123456789abcdef00112233445566778)
 u.emu_start(base+0x55a10,base+0x55a47,count=100)
 parent_stack=u.reg_read(UC_X86_REG_RSP);assert parent_stack%16==0
 site_regs={reg:0x20202020+i for i,reg in enumerate(NV)};site_regs[UC_X86_REG_RSI]=OBJ;site_regs[UC_X86_REG_R13]=r13
 for reg,value in site_regs.items():u.reg_write(reg,value)
 u.reg_write(UC_X86_REG_RDX,OBJ);u.reg_write(UC_X86_REG_R8,OBJ+0x8000)
 calls=[]
 def hook(machine,address,size,_):
  if address==base+0x55330:
   assert machine.reg_read(UC_X86_REG_RDX)==OBJ and machine.reg_read(UC_X86_REG_R8)==OBJ+0x8000 and machine.reg_read(UC_X86_REG_RSP)%16==8
   calls.append('native_profiles');stack=machine.reg_read(UC_X86_REG_RSP);target=struct.unpack('<Q',machine.mem_read(stack,8))[0]
   machine.reg_write(UC_X86_REG_RSP,stack+8);machine.reg_write(UC_X86_REG_RIP,target);return
  if address==CALLBACK:
   assert machine.reg_read(UC_X86_REG_RCX)==OBJ and machine.reg_read(UC_X86_REG_RSP)%16==8
   calls.append('validation')
   for reg in NV:
    if reg!=UC_X86_REG_RBP:machine.reg_write(reg,0xabababab)
   machine.reg_write(UC_X86_REG_RAX,valid)
  if address in [base+0x55f40,STOP]:machine.emu_stop()
 u.hook_add(UC_HOOK_CODE,hook);u.emu_start(base+SITE,STOP,count=1000)
 assert calls==['native_profiles','validation']
 if valid==1:
  for reg,value in site_regs.items():assert u.reg_read(reg)==((r13&0xffffffff) if reg==UC_X86_REG_RDI else value)
  assert u.reg_read(UC_X86_REG_RSP)==parent_stack and u.reg_read(UC_X86_REG_RIP)==base+0x55f40
 else:
  for reg,value in original.items():assert u.reg_read(reg)==value
  assert u.reg_read(UC_X86_REG_RSP)==rsp+8 and u.reg_read(UC_X86_REG_RAX)&255==0
  assert u.reg_read(UC_X86_REG_XMM6)==0x123456789abcdef00112233445566778, (hex(u.reg_read(UC_X86_REG_XMM6)),hex(parent_stack),bytes(u.mem_read(rsp-0x48,16)).hex())
 rows.append(dict(base=hex(base),callback_result=valid,accepted=valid==1,original_r13=hex(r13),aligned_callback=True,registers_and_native_stack_preserved=True))
for base in [0x180000000,0x280000000]:
 u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,0x120000);u.mem_write(base,m.image)
 STACK=0x31000000;OBJ=0x32000000;EXT=0x33000000;STOP=EXT+0x800;STUB=EXT+0x100
 for address,size in [(STACK,0x20000),(OBJ,0xd0000),(EXT,0x10000)]:u.mem_map(address,size)
 u.mem_write(STUB,b'\xc3');u.mem_write(STOP,b'\xc3')
 # All native Win32/logging imports are fixture boundaries returning0.
 for descriptor in m.pe.DIRECTORY_ENTRY_IMPORT:
  for imported in descriptor.imports:u.mem_write(base+imported.address-m.base,struct.pack('<Q',STUB))
 facade=OBJ;page=OBJ+0xc2000;metadata=OBJ+0xc8000;vt=OBJ+0xca000
 u.mem_write(facade,struct.pack('<Q',vt));u.mem_write(vt+0xb0,struct.pack('<Q',base+0x1ed30));u.mem_write(vt+0x18,struct.pack('<Q',base+0x24250))
 deleting=EXT+0x200;u.mem_write(deleting,b'\xc3');u.mem_write(vt,struct.pack('<Q',deleting))
 u.mem_write(facade+0xc03e8,struct.pack('<Q',metadata))
 u.mem_write(page+0x2220,struct.pack('<Q',1))
 rsp=STACK+0x10000;u.reg_write(UC_X86_REG_RSP,rsp);u.reg_write(UC_X86_REG_RDI,page);u.reg_write(UC_X86_REG_RBX,facade);u.reg_write(UC_X86_REG_RAX,0)
 seen=[]
 def finish(machine,value=0):
  stack=machine.reg_read(UC_X86_REG_RSP);target=struct.unpack('<Q',machine.mem_read(stack,8))[0]
  machine.reg_write(UC_X86_REG_RAX,value);machine.reg_write(UC_X86_REG_RSP,stack+8);machine.reg_write(UC_X86_REG_RIP,target)
 def hook(machine,address,size,_):
  if address==STUB:machine.reg_write(UC_X86_REG_RAX,0)
  if address==base+0x1ed30:seen.append('native_facade_close')
  if address==base+0x62b90:seen.append('resource_close_boundary');finish(machine)
  if address==base+0x24250:seen.append('native_release_wrapper')
  if address==deleting:
   assert machine.reg_read(UC_X86_REG_RCX)==facade and machine.reg_read(UC_X86_REG_RDX)==1
   seen.append('deleting_destructor_boundary')
  if address in [base+0x57478,base+0x56de0]:raise AssertionError('rejected world entered success/play path')
  if address==base+0x576e8:machine.emu_stop()
 u.hook_add(UC_HOOK_CODE,hook);u.emu_start(base+0x57470,base+0x576e9,count=5000)
 assert seen==['native_facade_close','resource_close_boundary','native_release_wrapper','deleting_destructor_boundary'],seen
 assert u.reg_read(UC_X86_REG_RSI)&255==0
 cleanup.append(dict(base=hex(base),native_false_branch=True,original_facade_close_and_release=True,deleting_flag=1,success_path_and_play_dispatch_not_called=True,boundaries=['Win32/logging imports','resource close primitive62b90','deleting destructor body']))
result=dict(scope=__doc__,actual_game_runs=0,source_sha256=hashlib.sha256(m.data).hexdigest(),hook_rva=hex(SITE),preimage=BEFORE.hex(),hook_type='CALL replacement',unwind_type='ordinary unchained wrapper',native_caller_unwind_entry=[hex(x) for x in PARENT],generated_unwind=UNWIND.hex(),bridge_cases=rows,native_caller_cleanup_cases=cleanup)
(HERE/'postprofile_results.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')
(HERE/'postprofile_native.asm').write_text('\n'.join(m.dis(a,b) for a,b in [(0x55d03,0x55d38),(0x55f28,0x55f40),(0x56b23,0x56b59),(0x57454,0x5760a),(0x1ed30,0x1eda2),(0x24250,0x24261)]),'utf-8')
print(json.dumps(dict(bridge_cases=len(rows),native_caller_cleanup_cases=len(cleanup),actual_game_runs=0)))
