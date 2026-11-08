"""Add full consumer stock/risk scoring to isolated AMD64 AI copies.

This stage preserves native45 stock collection and the native risk arithmetic.
Positive-AI gameplay remains untested and public AI controls remain disabled.
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
prior=json.loads((HERE/'state_candidate_manifest.json').read_text());reports=[];cases={};goods=list(range(26,41))+[24,25,45]
def count(key):cases[key]=cases.get(key,0)+1
for item in prior['modules']:
 path=HERE/item['output'];assert hashlib.sha256(path.read_bytes()).hexdigest()==item['output_sha256']
 m=Module(str(path));name=item['module'];e=Extension(m)
 sd=0 if name=='CompLogic.dll' else -0x16a0;ld=0 if name=='CompLogic.dll' else -0x3070;hd=0 if name=='CompLogic.dll' else -0x3490
 hook=0x7334a+ld;end=0x7334f+ld;loop=0x73320+ld
 assert m.image[hook:end]==bytes.fromhex('83fb287ed1')
 def stock(c):
  #The original body has already incrementedEBX/RBP before reaching this tail.
  c.add('83fb29');c.branch('0f84','to24');c.add('83fb1a');c.branch('0f84','exit');c.branch('e9',loop)
  c.mark('to24');c.add('bb180000004881ed1c060000');c.branch('e9',loop)
  c.mark('exit');c.branch('e9',end)
 target=e.function('added_consumer_stock',hook,stock);e.jump(hook,end,target)
 for label,hook,end,loop,compare,increment,expected in [
  ('city_consumer_risk18',0x32577+sd,0x32588+sd,0x324e2+sd,'6683ff','66ffc7','66ffc74983c25c6683ff280f865affffff'),
  ('generic_consumer_risk18',0x84189+hd,0x8419c+hd,0x840f0+hd,'664183f9','6641ffc1','6641ffc14983c25c664183f9280f8654ffffff'),
 ]:
  assert m.image[hook:end]==bytes.fromhex(expected),(name,label)
  def risk(c,loop=loop,end=end,compare=compare,increment=increment):
   for good,label in [(40,'to24'),(25,'to45'),(45,'exit')]:c.add(compare+bytes([good]).hex());c.branch('0f84',label)
   c.add(increment);c.add('4983c25c');c.branch('e9',loop)
   c.mark('to24');c.add('bf18000000' if increment=='66ffc7' else '41b918000000');c.add('4981eac0050000');c.branch('e9',loop)
   c.mark('to45');c.add('bf2d000000' if increment=='66ffc7' else '41b92d000000');c.add('4981c230070000');c.branch('e9',loop)
   c.mark('exit');c.branch('e9',end)
  target=e.function(label,hook,risk);e.jump(hook,end,target)
 data=e.finish(checksum);output=HERE/'_build'/(Path(name).stem+'.scoring_candidate.dll');output.write_bytes(data);candidate=Module(str(output))
 def machine(base):
  u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,(len(candidate.image)+4095)&~4095);u.mem_write(base,candidate.image)
  u.mem_map(0x31000000,0x10000);u.mem_map(0x32000000,0x40000);u.mem_map(0x33000000,0x2000);u.reg_write(UC_X86_REG_RSP,0x31008008);return u
 for base in [0x180000000,0x280000000]:
  u=machine(base);city=0x32002000;foreigncity=0x32014000;vtable=0x32015000;seen=[];raw=bytearray([0xa5])*0xfd10
  u.mem_write(city,bytes(raw));u.mem_write(foreigncity,struct.pack('<Q',vtable));u.mem_write(vtable+0x100,struct.pack('<Q',0x33000100))
  def stock_call(machine,address,size,user):
   good=machine.reg_read(UC_X86_REG_RDX)&0xffff;seen.append(good);sp=machine.reg_read(UC_X86_REG_RSP);ret=struct.unpack('<Q',machine.mem_read(sp,8))[0]
   machine.reg_write(UC_X86_REG_RAX,good*256+128);machine.reg_write(UC_X86_REG_RSP,sp+8);machine.reg_write(UC_X86_REG_RIP,ret)
  u.hook_add(UC_HOOK_CODE,stock_call,begin=0x33000100,end=0x33000100)
  u.reg_write(UC_X86_REG_RDI,city);u.reg_write(UC_X86_REG_R14,foreigncity)
  u.emu_start(base+0x7330b+ld,base+0x7338e+ld,count=10000)
  order=list(range(26,41))+[24,25]+list(range(41,46));assert seen==order,(name,'native stock order',seen)
  expected=bytearray(raw)
  for good in order:struct.pack_into('<f',expected,0x5f4+good*0x5c,float(good))
  assert u.mem_read(city,len(raw))==expected;count('native_consumer_and_material_stock_passes')
  #Zero risk forces the complete loop rather than its intentional early-fail
  #path. Actual arithmetic stays original; the narrow risk getter boundary
  #records which goods it receives, including explicit24/25/45.
  for kind in ['generic','city']:
   u=machine(base);view=0x32002000;seen=[];raw=bytearray(0x1800)
   for good in goods:raw[0x4b4+good*0x5c]=8
   u.mem_write(view,bytes(raw));getter=base+0x83fb0+hd
   def risk_call(machine,address,size,user):
    seen.append(machine.reg_read(UC_X86_REG_RDX)&0xffff);sp=machine.reg_read(UC_X86_REG_RSP);ret=struct.unpack('<Q',machine.mem_read(sp,8))[0]
    machine.reg_write(UC_X86_REG_XMM0,0);machine.reg_write(UC_X86_REG_RSP,sp+8);machine.reg_write(UC_X86_REG_RIP,ret)
   u.hook_add(UC_HOOK_CODE,risk_call,begin=getter,end=getter)
   if kind=='generic':
    u.reg_write(UC_X86_REG_RCX,view);u.reg_write(UC_X86_REG_RDX,0);u.mem_write(0x31008008,struct.pack('<Q',0x33000000))
    u.emu_start(base+0x84060+hd,0x33000000,count=20000);slot=0x40
   else:
    u.reg_write(UC_X86_REG_RSI,view-0x168);u.reg_write(UC_X86_REG_RBX,view);u.reg_write(UC_X86_REG_RBP,0);u.reg_write(UC_X86_REG_R10,view+0xe0d)
    u.emu_start(base+0x32498+sd,base+0x32597+sd,count=20000);slot=0x3c
   assert seen==goods,(name,kind,'risk good order',seen)
   expected=bytearray(raw);struct.pack_into('<i',expected,slot,127)
   assert u.mem_read(view,len(raw))==expected,(name,kind,'unrelated risk writes');count('native_'+kind+'_risk_passes')
 reports.append(dict(module=name,input_sha256=item['input_sha256'],state_input_sha256=item['output_sha256'],
  output=str(output.relative_to(HERE)),output_sha256=hashlib.sha256(data).hexdigest(),
  functions=e.functions,edits=[dict(rva=hex(a),before=b.hex(),after=c.hex()) for a,b,c in e.edits]))
 assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==item['input_sha256']
result=dict(scope=__doc__,modules=reports,cases=cases,actual_game_runs=0,installed_hooks=0,
 status='CANDIDATE ONLY; foreign-shortage classification audit, real chain fixture and positive-AI gameplay remain')
(HERE/'scoring_candidate_manifest.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['modules','scope']},indent=2))
