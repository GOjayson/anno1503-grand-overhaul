"""Execute original native village selection and city transfer instructions.

Private Unicorn memory only. Allocation, World color-cache update and queued
AI notification delivery are explicit boundary doubles. Membership mutation,
reference counts, native city owner attach/detach and discovery-mask changes
execute original instructions. This does not prove an actual game transfer.
"""
from pathlib import Path
import hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[2];ROOT=WORK.parent
sys.path[:0]=[str(WORK/'_tools'),str(WORK/'engine_audit')]
from audit import Module
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE,UC_HOOK_MEM_INVALID
from unicorn.x86_const import *
W=Module(str(ROOT/'AnnoWelt.dll'));S=Module(str(ROOT/'AnnoScene.dll'))
assert hashlib.sha256(W.data).hexdigest()=='ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9'
assert hashlib.sha256(S.data).hexdigest()=='f7d0685cf6156ff25c518f2f558863b351d7738280467e48dd585a1fefa9537a'
def mapped(m,base):
 image=bytearray(m.image)
 for block in m.pe.DIRECTORY_ENTRY_BASERELOC:
  for e in block.entries:
   if e.type==10:struct.pack_into('<Q',image,e.rva,struct.unpack_from('<Q',image,e.rva)[0]+base-m.base)
   else:assert e.type==0
 return bytes(image)
selection=[]
for base in [0x180000000,0x280000000]:
 for culture in range(1,14):
  u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,0x60000);u.mem_write(base,mapped(S,base));u.mem_map(0x40000000,0x10000)
  u.reg_write(UC_X86_REG_RAX,1<<culture);u.reg_write(UC_X86_REG_R13,2);u.reg_write(UC_X86_REG_RBP,0x40001000)
  u.hook_add(UC_HOOK_CODE,lambda cpu,address,size,user:cpu.emu_stop(),begin=base+0xc7f9,end=base+0xc7f9)
  u.emu_start(base+0xc8b0,base+0xc8c4,count=100)
  reached=u.reg_read(UC_X86_REG_RIP)==base+0xc8c4
  assert reached==(2<=culture<=10)
  selection.append(dict(base=hex(base),culture=culture,accepted_by_original_village_selector=reached))
STACK=0x40000000;OBJ=0x41000000;EXT=0x42000000
OLD=OBJ;NEW=OBJ+0x1000;CITY=OBJ+0x4000;ISLAND=OBJ+0x8000;WORLD=OBJ+0xa000;OLDNODE=OBJ+0xb000;NEWNODE=OBJ+0xb100;VECTOR=OBJ+0xc000;OLDCTRL=OBJ+0xd000;NEWCTRL=OBJ+0xd100;CV=OBJ+0xe000
cases=[]
for base,oldId,newId in [(b,o,n) for b in [0x180000000,0x280000000] for o,n in [(0,6),(31,6),(2,7)]]:
 sceneBase=base+0x1000000;u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,0x160000);u.mem_write(base,mapped(W,base));u.mem_map(sceneBase,0x60000);u.mem_write(sceneBase,mapped(S,sceneBase));u.mem_map(STACK,0x20000);u.mem_map(OBJ,0x10000);u.mem_map(EXT,0x1000)
 def put(at,fmt,*values):u.mem_write(at,struct.pack('<'+fmt,*values))
 def get(at,fmt):return struct.unpack('<'+fmt,u.mem_read(at,struct.calcsize('<'+fmt)))[0]
 def pointer(at,value):put(at,'Q',value)
 for player,ident in [(OLD,oldId),(NEW,newId)]:
  pointer(player,base+0xfabe0);put(player+8,'I',ident);put(player+0x1c,'I',10);pointer(player+0x10,WORLD);put(player+0xcc,'B',0)
 pointer(OLD+0x18,OLDCTRL);pointer(NEW+0x18,NEWCTRL)
 pointer(OLDCTRL,CV);pointer(NEWCTRL,CV);pointer(CV+0x20,EXT+0x100);u.mem_write(EXT+0x100,b'\xc3')
 pointer(CITY,base+0xfc678);put(CITY+8,'I',3);put(CITY+0x1b,'B',5);pointer(CITY+0x20,ISLAND);pointer(CITY+0x28,OLD);pointer(CITY+0x470,OLD);put(CITY+0x760,'I',1<<oldId)
 pointer(ISLAND,base+0xf33e8);put(ISLAND+8,'HHHH',64,64,128,128);put(ISLAND+0x10,'I',9);pointer(ISLAND+0x38,WORLD);pointer(ISLAND+0x68,CITY)
 pointer(WORLD,base+0xff650)
 pointer(OLD+0x318,OLDNODE);pointer(OLD+0x320,OLDNODE);pointer(OLDNODE+0x10,CITY)
 # Native membership vector already has an empty slot, so native a3d60
 # need not exercise its unrelated growth/reallocation boundary.
 pointer(NEW+0x2f8,VECTOR);pointer(NEW+0x300,VECTOR+8);pointer(NEW+0x308,VECTOR+8)
 rsp=STACK+0x10000;rbp=STACK+0x2000;put(rsp+0x30,'Q',ISLAND);put(rsp+0x38,'Q',NEW)
 u.reg_write(UC_X86_REG_RSP,rsp);u.reg_write(UC_X86_REG_RBP,rbp);u.reg_write(UC_X86_REG_R12,CITY)
 calls=[];last=[]
 worldUpdate=struct.unpack_from('<Q',W.image,0xff650+0x1d8)[0]-W.base
 def ret(cpu,value=0):
  sp=cpu.reg_read(UC_X86_REG_RSP);target=struct.unpack('<Q',cpu.mem_read(sp,8))[0];cpu.reg_write(UC_X86_REG_RAX,value);cpu.reg_write(UC_X86_REG_RSP,sp+8);cpu.reg_write(UC_X86_REG_RIP,target)
 def hook(cpu,address,size,_):
  last.append(hex(address-base));last[:]=last[-8:]
  if address==base+0xe46bc:
   assert cpu.reg_read(UC_X86_REG_RCX)==24;calls.append('allocate-membership-node');ret(cpu,NEWNODE)
  elif address==base+0xe58ea:
   target=cpu.reg_read(UC_X86_REG_RCX);value=cpu.reg_read(UC_X86_REG_RDX)&255;n=cpu.reg_read(UC_X86_REG_R8);assert n<=4096;cpu.mem_write(target,bytes([value])*n);ret(cpu,target)
  elif address==base+worldUpdate:
   assert cpu.reg_read(UC_X86_REG_RCX)==WORLD and cpu.reg_read(UC_X86_REG_RDX)==CITY and cpu.reg_read(UC_X86_REG_R8)==newId
   calls.append('world-city-owner-update');ret(cpu,0)
  elif address==EXT+0x100:
   controller=cpu.reg_read(UC_X86_REG_RCX);message=cpu.reg_read(UC_X86_REG_RDX);kind=struct.unpack('<H',cpu.mem_read(message,2))[0]
   assert controller in [OLDCTRL,NEWCTRL] and kind==(0xe if controller==OLDCTRL else 0x19)
   calls.append('old-owner-remove-event' if controller==OLDCTRL else 'new-owner-add-event');ret(cpu,1)
 def invalid(cpu,access,address,size,value,_):
  print('INVALID',hex(address),access,'recent',last);return False
 u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_MEM_INVALID,invalid)
 u.emu_start(sceneBase+0xc947,sceneBase+0xca19,count=200000)
 assert get(CITY+0x28,'Q')==NEW and get(CITY+0x470,'Q')==NEW
 assert get(OLD+0x318,'Q')==get(OLD+0x320,'Q')==0
 assert get(NEW+0x318,'Q')==get(NEW+0x320,'Q')==NEWNODE
 assert get(NEWNODE+0x10,'Q')==CITY
 assert get(CITY+0x760,'I')==1<<newId
 assert get(CITY+0x1b,'B')==5
 assert calls==['old-owner-remove-event','allocate-membership-node','world-city-owner-update','new-owner-add-event'],calls
 cases.append(dict(base=hex(base),old_id=oldId,new_id=newId,city_owner=newId,city_discovery_mask=hex(get(CITY+0x760,'I')),old_list_empty=True,new_list_registered=True,city_refcount_preserved=True,boundaries=calls))
result=dict(scope=__doc__,village_selection_cases=selection,native_transfer_cases=cases,actual_game_runs=0)
(HERE/'native_transfer_results.json').write_text(json.dumps(result,indent=2)+'\n')
(HERE/'native_transfer.asm').write_text(S.dis(0xc841,0xca19)+'\n\n'+W.dis(0x9ad00)+'\n\n'+W.dis(0x9b690)+'\n\n'+W.dis(0xb8300)+'\n\n'+W.dis(0xb83d0))
print(json.dumps({'selection_cases':len(selection),'native_transfer_cases':len(cases),'actual_game_runs':0}))
