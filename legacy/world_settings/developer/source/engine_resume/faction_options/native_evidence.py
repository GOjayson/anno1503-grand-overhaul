"""Original AMD64 instruction evidence for special player identities.

Unicorn fixtures use private buffers and stop before allocation/constructors.
No DLL is loaded into a game and no player AI is simulated.
"""
from pathlib import Path
import hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[1];ROOT=WORK.parent
sys.path.insert(0,str(WORK/'engine_audit'))
from audit import Module
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *
expected={'AnnoGame.dll':'e6f01d19e8e16e6716c0a6c7d3ba00273c9df493e051b8ba62865ee4b53dfdea','AnnoWelt.dll':'ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9','CompLogic.dll':'7f2c7e818d8c25a0b6c48cda2d21bfa0c4096c5dcd8be91c2ab93d877c22afee','CompLogicClassic.dll':'0a7692879e15e8cbaed73ec3b59eaa6419165faaea6d8696cddfd68c92000f22'}
modules={n:Module(str(ROOT/n)) for n in expected}
for n,m in modules.items():assert hashlib.sha256(m.data).hexdigest()==expected[n] and m.pe.FILE_HEADER.Machine==0x8664 and m.pe.OPTIONAL_HEADER.Magic==0x20b
def machine(m,base):
 image=bytearray(m.image)
 for block in m.pe.DIRECTORY_ENTRY_BASERELOC:
  for entry in block.entries:
   if entry.type==10:struct.pack_into('<Q',image,entry.rva,struct.unpack_from('<Q',image,entry.rva)[0]+base-m.base)
   else:assert entry.type==0
 u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,(len(image)+4095)&~4095);u.mem_write(base,bytes(image))
 for at,n in [(0x31000000,0x10000),(0x32000000,0x10000),(0x33000000,0x1000)]:u.mem_map(at,n)
 u.mem_write(0x31008008,struct.pack('<Q',0x33000000));u.reg_write(UC_X86_REG_RSP,0x31008008)
 return u
dispatch=[];assembly=[]
for name,start,allocate,table in [('CompLogic.dll',0x59560,0x84b74,0x59b98),('CompLogicClassic.dll',0x569b0,0x81678,0x56e5c)]:
 m=modules[name];assembly.append(name+'\n'+m.dis(start,start+0x70))
 for base in [0x180000000,0x280000000]:
  for typ,allocation in [(11,0x2838),(12,0x21d0),(14,0x2188),(15,0x21b0),(16,0x21a0)]:
   u=machine(m,base);u.reg_write(UC_X86_REG_RCX,0x32000000);u.reg_write(UC_X86_REG_RDX,typ);u.reg_write(UC_X86_REG_R8,5);u.reg_write(UC_X86_REG_R9,0)
   called=[]
   def stop(cpu,address,size,user):
    called.append(cpu.reg_read(UC_X86_REG_RCX));cpu.emu_stop()
   u.hook_add(UC_HOOK_CODE,stop,begin=base+allocate,end=base+allocate);u.emu_start(base+start,0x33000000,count=500)
   assert called==[allocation],(name,typ,called)
   dispatch.append(dict(module=name,base=hex(base),type=typ,allocation=allocation,switch_target=hex(struct.unpack_from('<I',m.image,table+(typ-11)*4)[0])))
w=modules['AnnoWelt.dll'];g=modules['AnnoGame.dll'];reads=[]
assert w.image[0xdbaf5:0xdbafc]==bytes.fromhex('4889be10020000')
assert struct.unpack_from('<Q',w.image,0xff650+0x150)[0]==w.base+0xd1a30
assert struct.unpack_from('<Q',w.image,0xfdbc0+0x18)[0]==w.base+0x95990
enums={}
for i in [11,12]:
 ptr=struct.unpack_from('<Q',g.image,0x23c90+i*8)[0];enums[i]=g.image[ptr-g.base:].split(b'\0')[0].decode()
assert enums=={11:'PIRATEN',12:'VENECIA'}
for base in [0x180000000,0x280000000]:
 for id in [0,5,6,31]:
  u=machine(w,base);world=0x32000000;players=0x32004000;expectedPlayer=0x32006000
  u.mem_write(world+0x210,struct.pack('<Q',players));u.reg_write(UC_X86_REG_RCX,world);u.emu_start(base+0xd1a30,0x33000000,count=50);assert u.reg_read(UC_X86_REG_RAX)==players
  u.mem_write(players+8+id*8,struct.pack('<Q',expectedPlayer));u.reg_write(UC_X86_REG_RSP,0x31008008);u.reg_write(UC_X86_REG_RCX,players);u.reg_write(UC_X86_REG_RDX,id);u.emu_start(base+0x95990,0x33000000,count=50);assert u.reg_read(UC_X86_REG_RAX)==expectedPlayer
  reads.append(dict(base=hex(base),slot=id,world_field='0x210',table_field='8+id*8'))
assembly.append('AnnoWelt.dll\n'+w.dis(0xdba32,0xdbafc)+'\n'+w.dis(0xd1a30,0xd1a38)+'\n'+w.dis(0x95990,0x95999))
result=dict(scope=__doc__,source_sha256=expected,controller_dispatch_cases=dispatch,original_player_table_read_cases=reads,native_culture_enums=enums,game_runs=0)
(HERE/'native_results.json').write_text(json.dumps(result,indent=2)+'\n');(HERE/'native.asm').write_text('\n\n'.join(assembly))
print(json.dumps({'controller_dispatch_cases':len(dispatch),'native_table_read_cases':len(reads),'native_culture_enums':enums,'actual_game_runs':0}))
