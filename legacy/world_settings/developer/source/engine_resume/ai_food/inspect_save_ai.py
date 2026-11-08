"""Read-only saved AI-controller audit with native suspend/dispatch fixtures.

No process attachment, DLL loading or save writes. A COMP record establishes a
serialized controller; SUSPEND establishes its saved scheduler setting, not
whether a later game event resumes it. Output is confined beside this script.
"""
from pathlib import Path
import argparse,hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[1];ROOT=WORK.parent
sys.path.insert(0,str(WORK/'world_data'));sys.path.insert(0,str(WORK/'engine_audit'))
from scene_catalogue import chunks,read_container
from audit import Module
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *
parser=argparse.ArgumentParser();parser.add_argument('save',type=Path);args=parser.parse_args()
b=args.save.read_bytes();root,trailing=read_container(b);assert not trailing
players={};states={}
for c in chunks(b,16,root.end):
 if c.tag!='SPIELER':continue
 assert len(c.payload)>=8
 ident=struct.unpack_from('<I',c.payload,4)[0]
 if c.payload[8:14]==b'HEAD\0\0':
  players[ident]=dict(id=ident,type=struct.unpack_from('<I',c.payload,16)[0],basic_offset=c.offset)
 else:
  candidates=[];start=0
  while True:
   at=c.payload.find(b'COMP\0\0',start)
   if at<0:break
   start=at+1
   if at+16>len(c.payload):continue
   size=struct.unpack_from('<H',c.payload,at+6)[0]
   if size<8 or at+8+size>len(c.payload):continue
   typ,pid=struct.unpack_from('<II',c.payload,at+8)
   if pid!=ident:continue
   if typ!=12:continue
   text=c.payload[at+16:at+8+size]
   assert text.endswith(b'\0')
   fields={}
   for item in text.rstrip(b'\0').split(b'\0'):
    key,separator,value=item.partition(b'=');assert separator
    fields.setdefault(key.decode('ascii'),[]).append(value.decode('ascii'))
   candidates.append(dict(type=typ,id=pid,offset=c.offset+16+at,bytes=size,fields=fields))
  assert len(candidates)<=1,(ident,'ambiguous COMP')
  states[ident]=dict(state_offset=c.offset,controller=candidates[0] if candidates else None)
computers=[]
for ident,player in sorted(players.items()):
 if player['type']!=12:continue
 state=states.get(ident,{}).get('controller');assert state and state['type']==12
 suspend=state['fields'].get('SUSPEND');assert suspend and len(suspend)==1
 assert suspend[0] in ['0','1']
 computers.append(dict(**player,controller_offset=state['offset'],suspend=int(suspend[0]),
  saved_scheduler_enabled=suspend[0]=='0',fields=state['fields']))

m=Module(str(ROOT/'CompLogic.dll'))
expected='7f2c7e818d8c25a0b6c48cda2d21bfa0c4096c5dcd8be91c2ab93d877c22afee'
assert hashlib.sha256(m.data).hexdigest()==expected and m.pe.FILE_HEADER.Machine==0x8664
assert struct.unpack_from('<I',m.image,0x65b0+0x1a*4)[0]==0x6299
assert struct.unpack_from('<I',m.image,0x6a78+0x1a*4)[0]==0x684c
native=[]
for base in [0x180000000,0x280000000]:
 u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,(len(m.image)+4095)&~4095);u.mem_write(base,m.image)
 u.mem_map(0x31000000,0x10000);u.mem_map(0x32000000,0x10000);u.mem_map(0x33000000,0x1000)
 controller=0x32002000;vtable=0x32005000;variant=0x32006000
 u.mem_write(controller,struct.pack('<Q',vtable));u.mem_write(vtable+0x40,struct.pack('<Q',base+0x1020))
 u.mem_write(controller+0xa4c,struct.pack('<I',12))
 for suspend in [0,1]:
  u.mem_write(variant+0x18,struct.pack('<I',suspend));u.mem_write(0x31008008,struct.pack('<Q',0x33000000))
  for register,value in [(UC_X86_REG_RSP,0x31008008),(UC_X86_REG_RCX,controller),(UC_X86_REG_RDX,0x1a),(UC_X86_REG_R8,variant)]:u.reg_write(register,value)
  u.emu_start(base+0x6090,0x33000000,count=5000)
  assert u.reg_read(UC_X86_REG_RAX)==1
  flag=bytes(u.mem_read(controller+0x1e9d,1))[0];field=struct.unpack('<I',u.mem_read(controller+0xab4,4))[0]
  assert flag==1-suspend and field==suspend
  calls=[]
  def intercept_tick(machine,address,size,user):
   calls.append(address);stack=machine.reg_read(UC_X86_REG_RSP)
   target=struct.unpack('<Q',machine.mem_read(stack,8))[0]
   machine.reg_write(UC_X86_REG_RAX,0);machine.reg_write(UC_X86_REG_RSP,stack+8);machine.reg_write(UC_X86_REG_RIP,target)
  hook=u.hook_add(UC_HOOK_CODE,intercept_tick,begin=base+0x5080,end=base+0x5080)
  for register,value in [(UC_X86_REG_RSP,0x31008008),(UC_X86_REG_RBX,controller),(UC_X86_REG_RSI,100),(UC_X86_REG_RDI,1),(UC_X86_REG_R14,55)]:u.reg_write(register,value)
  u.ctl_remove_cache(base+0x59165,base+0x59182)
  u.emu_start(base+0x59165,base+0x59182,count=100)
  u.hook_del(hook);assert len(calls)==1-suspend
  native.append(dict(image_base=hex(base),suspend=suspend,scheduler_flag=flag,thinking_dispatch_calls=len(calls)))
result=dict(save_sha256=hashlib.sha256(b).hexdigest(),save_alias=next(c.payload.split(b'\0')[0].decode('cp1252') for c in chunks(b,16,root.end) if c.tag=='ALIASNAME'),
 basic_player_count=len(players),state_player_count=len(states),computer_controllers=computers,
 saved_enabled_cpu_count=sum(x['saved_scheduler_enabled'] for x in computers),native_suspend_cases=native,
 source_sha256=expected,actual_game_runs=0,
 conclusion='CPU controller records exist. Saved SUSPEND=1 suppresses their main thinking dispatch. Later resumption events and current live flags are outside this read-only audit.')
(HERE/'saved_ai_audit.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')
print(json.dumps(result,indent=2))
