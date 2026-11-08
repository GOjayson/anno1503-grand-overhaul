"""Wire explicit consumer queues/stand selection on isolated candidate copies.

The native evaluator and record lifecycle were wired in the preceding stages.
This stage adds safe24/25 record writes,18-good queue iteration/selection,
Food-stand routing and six-ware pending clear. It remains an incomplete food-AI
experiment until recipe/state scheduling and actual gameplay are verified.
"""
from pathlib import Path
import hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[1];ROOT=WORK.parent
sys.path.insert(0,str(WORK/'engine_audit'));sys.path.insert(0,str(ROOT/'anno1503_food_mod/developer'))
from audit import Module
from pe_builder import checksum
from code_support import Extension
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *
prior=json.loads((HERE/'demand_candidate_manifest.json').read_text());reports=[];selector_cases=0;writer_cases=0;tail_cases=0
goods=list(range(26,41))+[24,25,45]
def record_offset(good):return 0x340 if good==24 else 0x354 if good==25 else 0x48+(good-26)*20
for item in prior['modules']:
 path=HERE/item['output'];assert hashlib.sha256(path.read_bytes()).hexdigest()==item['output_sha256']
 m=Module(str(path));name=item['module'];e=Extension(m)
 sd=0 if name=='CompLogic.dll' else -0x16a0
 wd=0 if name=='CompLogic.dll' else -0x2aa0
 scanloop=0x1aba0+sd;scantail=0x1abcf+sd;scanexit=0x1abd8+sd
 def scan(c):
  for value,label in [(40,'to24'),(25,'to45'),(45,'exit')]:c.add('4183f8'+bytes([value]).hex());c.branch('0f84',label)
  c.add('41ffc0');c.branch('e9',scanloop)
  c.mark('to24');c.add('41b8180000004d8d8a4c030000');c.branch('e9',scanloop)
  c.mark('to45');c.add('41b82d0000004d8d8ad0010000');c.branch('e9',scanloop)
  c.mark('exit');c.branch('e9',scanexit)
 target=e.function('select18',scantail,scan);e.jump(scantail,scanexit,target)
 for hook,end,original,foodread in [(0x1ac02+sd,0x1ac0a+sd,'448bb4b1f0000000','448bb1f0000000'),(0x1ac79+sd,0x1ac80+sd,'8b94b0f0000000','8b90f0000000')]:
  assert m.image[hook:end]==bytes.fromhex(original)
  def mapping(c,original=original,foodread=foodread,end=end):
   for good in [24,25,40,45]:c.add('6683fb'+bytes([good]).hex());c.branch('0f84','food')
   c.add(original);c.branch('e9',end);c.mark('food');c.add(foodread);c.branch('e9',end)
  target=e.function('food_stand_'+hex(hook),hook,mapping);e.jump(hook,end,target)
 pointerhook=0x1ac3b+sd;pointerexit=0x1ac43+sd
 assert m.image[pointerhook:pointerexit]==bytes.fromhex('488d04b64c8d0487')
 def selected_record(c):
  c.add('488d04b66683fb18');c.branch('0f84','to24');c.add('6683fb19');c.branch('0f84','to25')
  c.add('4c8d0487');c.branch('e9',pointerexit)
  c.mark('to24');c.add('4c8d87f8020000');c.branch('e9',pointerexit)
  c.mark('to25');c.add('4c8d870c030000');c.branch('e9',pointerexit)
 target=e.function('selected_record',pointerhook,selected_record);e.jump(pointerhook,pointerexit,target)
 clearhook=0x1ac92+sd;clearexit=0x1acc9+sd
 def clear(c):
  c.add('4531f6');c.mark('loop');c.add('488b06488bce418bd6ff906001000085c0');c.branch('0f84','next')
  c.add('83f818');c.branch('0f84','to24');c.add('83f819');c.branch('0f84','to25')
  c.add('8d48e683f91d');c.branch('0f87','next')
  c.add('4898488d0c80664489a48f4cfeffff');c.branch('e9','next')
  c.mark('to24');c.add('664489a74c030000');c.branch('e9','next')
  c.mark('to25');c.add('664489a760030000')
  c.mark('next');c.add('41ffc64183fe06');c.branch('0f82','loop');c.branch('e9',clearexit)
 target=e.function('clear_covered',clearhook,clear);e.jump(clearhook,clearexit,target)
 writehook=0x57c55+wd;writeexit=0x57c86+wd
 assert m.image[writehook:writehook+4]==bytes.fromhex('410fb7fe')
 writebody=m.image[0x57c65+wd:writeexit]
 assert writebody==bytes.fromhex('4101848c40feffff0fbf8424100200004101848c44feffff6641ff848c4cfeffff')
 def writer(c):
  c.add('410fb7fe0fbf8424f8010000488d0cbf83ff18');c.branch('0f84','to24')
  c.add('83ff19');c.branch('0f84','to25');c.branch('e9','write')
  c.mark('to24');c.add('b940010000');c.branch('e9','write')
  c.mark('to25');c.add('b945010000')
  c.mark('write');c.add(writebody);c.branch('e9',writeexit)
 target=e.function('pending_write',writehook,writer);e.jump(writehook,writeexit,target)
 loophook=0x57c95+wd;loopexit=0x57cad+wd;loopbody=0x57ae2+wd
 assert m.image[loophook:loopexit]==bytes.fromhex('6641ffc64883c05c4889442458664183fe280f8635feffff')
 def iteration(c):
  for good,label in [(40,'to24'),(25,'to45'),(45,'exit')]:c.add('664183fe'+bytes([good]).hex());c.branch('0f84',label)
  c.add('6641ffc64883c05c');c.branch('e9','continue')
  c.mark('to24');c.add('41be18000000482dc0050000');c.branch('e9','continue')
  c.mark('to45');c.add('41be2d000000480530070000')
  c.mark('continue');c.add('4889442458');c.branch('e9',loopbody)
  c.mark('exit');c.branch('e9',loopexit)
 target=e.function('register18',loophook,iteration);e.jump(loophook,loopexit,target)
 # World virtual148 delegates to Game virtual160 (Welt76ae0). The installed
 # Food Mod getter returns0 beyond the original two wares for other stands.
 coverage=0x57c45+wd;e.patch(coverage,bytes.fromhex('83fb02'),bytes.fromhex('83fb06'))
 data=e.finish(checksum);output=HERE/'_build'/(Path(name).stem+'.market_candidate.dll');output.write_bytes(data);candidate=Module(str(output))
 def machine(base):
  u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,(len(candidate.image)+4095)&~4095);u.mem_write(base,candidate.image)
  u.mem_map(0x31000000,0x10000);u.mem_map(0x32000000,0x40000);u.mem_map(0x33000000,0x2000)
  u.reg_write(UC_X86_REG_RSP,0x31008008);return u
 for base in [0x180000000,0x280000000]:
  for good in goods:
   u=machine(base);node=bytearray([0xa5])*0x388;p=16+record_offset(good)
   struct.pack_into('<ii',node,p,700,-200);struct.pack_into('<H',node,p+12,17);expected=bytearray(node)
   struct.pack_into('<ii',expected,p,743,-229);struct.pack_into('<H',expected,p+12,18)
   u.mem_write(0x32001ff0,bytes(node));u.mem_write(0x31008008+0x1f8,struct.pack('<h',43));u.mem_write(0x31008008+0x210,struct.pack('<h',-29))
   u.reg_write(UC_X86_REG_R12,0x32002000);u.reg_write(UC_X86_REG_R14,good)
   u.emu_start(base+writehook,base+writeexit,count=1000)
   assert u.mem_read(0x32001ff0,len(node))==expected,(name,good,'safe pending write');writer_cases+=1
  for ordinal,current in enumerate(goods):
   u=machine(base);state=0x32008000+current*0x5c
   u.reg_write(UC_X86_REG_R14,current);u.reg_write(UC_X86_REG_RAX,state)
   end=loopexit if current==45 else loopbody
   u.emu_start(base+loophook,base+end,count=1000)
   if current!=45:
    following=goods[ordinal+1];assert u.reg_read(UC_X86_REG_R14)==following and u.reg_read(UC_X86_REG_RAX)==0x32008000+following*0x5c
    assert struct.unpack('<Q',u.mem_read(0x31008008+0x58,8))[0]==0x32008000+following*0x5c
   tail_cases+=1
  # Execute the whole original selector including the new helpers. Game
  # definition getter and affordability/file primitives are fixture boundaries.
  for chosen,wares,standid in [(24,[26,28,24,40,25,45],1310),(25,[26,28,24,40,25,45],1310),(45,[26,28,24,40,25,45],1310),(37,[37,39],1313)]:
   u=machine(base);city=0x32002000;provider=0x32006000;game=0x32007000;definition=0x32008000;defvt=0x32009000;node=0x32010000;task=0x32011000
   u.mem_write(city+0x50,struct.pack('<Q',provider));u.mem_write(city+0x571,b'\x01');u.mem_write(city+0x2350,struct.pack('<Q',node))
   u.mem_write(provider+8,struct.pack('<Q',game));u.mem_write(provider+0xf0,struct.pack('<I',1310))
   for old in range(27,41):u.mem_write(provider+0xf0+(old-26)*4,struct.pack('<I',1313 if old in [37,39] else 1400+old))
   u.mem_write(game,struct.pack('<Q',0x3200a000));u.mem_write(0x3200a000+0xe8,struct.pack('<Q',0x33000300))
   u.mem_write(definition,struct.pack('<Q',defvt));u.mem_write(defvt+0x160,struct.pack('<Q',0x33000320))
   raw=bytearray(0x368)
   for good in goods:
    p=record_offset(good);count=7 if good==chosen else 1;struct.pack_into('<ii',raw,p,count*11,count*-3);struct.pack_into('<H',raw,p+12,count)
   u.mem_write(node,bytes(raw))
   def primitive(machine,address,size,user):
    stack=machine.reg_read(UC_X86_REG_RSP);target=struct.unpack('<Q',machine.mem_read(stack,8))[0]
    if address==base+(0x3e6d0 if name=='CompLogic.dll' else 0x3bce0):value=0
    elif address==base+(0x85a42 if name=='CompLogic.dll' else 0x82532):
     dest=machine.reg_read(UC_X86_REG_RCX);length=machine.reg_read(UC_X86_REG_R8);machine.mem_write(dest,bytes(length));value=dest
    elif address==0x33000300:value=definition
    else:
     index=machine.reg_read(UC_X86_REG_RDX)&255;value=wares[index] if index<len(wares) else 0
    machine.reg_write(UC_X86_REG_RAX,value);machine.reg_write(UC_X86_REG_RSP,stack+8);machine.reg_write(UC_X86_REG_RIP,target)
   cost=0x3e6d0 if name=='CompLogic.dll' else 0x3bce0
   for target in [base+cost,base+(0x85a42 if name=='CompLogic.dll' else 0x82532),0x33000300,0x33000320]:u.hook_add(UC_HOOK_CODE,primitive,begin=target,end=target)
   u.mem_write(0x31008008,struct.pack('<Q',0x33000000));u.reg_write(UC_X86_REG_RCX,city);u.reg_write(UC_X86_REG_RDX,task)
   try:u.emu_start(base+0x1ab30+sd,0x33000000,count=10000)
   except Exception as exc:raise AssertionError((name,chosen,hex(u.reg_read(UC_X86_REG_RIP)),hex(u.reg_read(UC_X86_REG_RCX)),hex(u.reg_read(UC_X86_REG_RAX)))) from exc
   assert u.reg_read(UC_X86_REG_RAX)&255==1
   assert struct.unpack('<I',u.mem_read(task+0x50,4))[0]==standid
   assert struct.unpack('<ii',u.mem_read(task+0x58,8))==(11,-3)
   assert struct.unpack('<H',u.mem_read(task+0x68,2))[0]==chosen
   expected=bytearray(raw)
   for good in wares:struct.pack_into('<H',expected,record_offset(good)+12,0)
   assert u.mem_read(node,0x368)==expected,(name,chosen,'whole selector clear')
   selector_cases+=1
 reports.append(dict(module=name,input_sha256=item['input_sha256'],demand_input_sha256=item['output_sha256'],
  output=str(output.relative_to(HERE)),output_sha256=hashlib.sha256(data).hexdigest(),
  functions=e.functions,edits=[dict(rva=hex(a),before=b.hex(),after=c.hex()) for a,b,c in e.edits]))
 assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==item['input_sha256']
result=dict(scope=__doc__,modules=reports,safe_writer_cases=writer_cases,explicit_iteration_cases=tail_cases,
 whole_native_selector_cases=selector_cases,actual_game_runs=0,installed_hooks=0,
 status='QUEUE + DEMAND + LIFECYCLE WIRED ON COPIES; consumer recipe/state scheduling and positive-AI gameplay remain')
(HERE/'market_candidate_manifest.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['modules','scope']},indent=2))
