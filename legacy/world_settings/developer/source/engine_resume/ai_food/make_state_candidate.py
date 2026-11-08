"""Wire consumer initialization/preparation/recipes/dependencies on copies.

This builds on the queue/demand candidate. It is an unfinished AI experiment;
it neither installs modules nor enables opponents in World Settings.
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
prior=json.loads((HERE/'market_candidate_manifest.json').read_text())
goods=list(range(26,41))+[24,25,45];reports=[];cases={}
def count(key):cases[key]=cases.get(key,0)+1
for item in prior['modules']:
 path=HERE/item['output'];assert hashlib.sha256(path.read_bytes()).hexdigest()==item['output_sha256']
 m=Module(str(path));name=item['module'];e=Extension(m)
 sd=0 if name=='CompLogic.dll' else -0x16a0
 rd=0 if name=='CompLogic.dll' else -0x1880
 def state_tail(c,loop,end,word=False,pointer='rbx',tag=False):
  # Only the consumer set is changed. No broad24..45 numeric interval.
  compare='6683ff' if word else '83ff'
  for good,label in [(40,'to24'),(25,'to45'),(45,'exit')]:c.add(compare+bytes([good]).hex());c.branch('0f84',label)
  c.add('66ffc7' if word else 'ffc7');c.add('4883c35c' if pointer=='rbx' else '4983c25c')
  if tag:c.add('41ffc1')
  c.branch('e9',loop)
  c.mark('to24');c.add('bf18000000');c.add('4881ebc0050000' if pointer=='rbx' else '4981eac0050000')
  if tag:c.add('41b9ffffffff')
  c.branch('e9',loop)
  c.mark('to45');c.add('bf2d000000');c.add('4881c330070000' if pointer=='rbx' else '4981c230070000')
  if tag:c.add('41b914000000')
  c.branch('e9',loop);c.mark('exit');c.branch('e9',end)
 for label,hook,end,loop,word,expected in [
  ('state_dependency18',0x31945+sd,0x31950+sd,0x31927+sd,False,'ffc74883c35c83ff287ed7'),
  ('consumer_prepare18',0x32227+sd,0x32238+sd,0x32100+sd,True,'66ffc74883c35c6683ff280f86c8feffff'),
 ]:
  assert m.image[hook:end]==bytes.fromhex(expected),(name,label)
  target=e.function(label,hook,lambda c,loop=loop,end=end,word=word:state_tail(c,loop,end,word))
  e.jump(hook,end,target)
 #45 is now processed in the consumer pass, so remove only that final material
 #iteration.41..44 retain their original order and arithmetic.
 for at,before,after in [(0x31984+sd,'83ff2d','83ff2c'),(0x3232d+sd,'6683ff2d','6683ff2c'),(0x36c51+rd,'83fd2d','83fd2c')]:e.patch(at,bytes.fromhex(before),bytes.fromhex(after))
 hook=0x36ce0+rd;end=0x36cee+rd;loop=0x36c70+rd
 assert m.image[hook:end]==bytes.fromhex('ffc54981c6e003000083fd287e82')
 def recipe(c):
  for good,label in [(40,'to24'),(25,'to45'),(45,'exit')]:c.add('83fd'+bytes([good]).hex());c.branch('0f84',label)
  c.add('ffc54981c6e0030000');c.branch('e9',loop)
  c.mark('to24');c.add('bd180000004981ee003e0000');c.branch('e9',loop)
  c.mark('to45');c.add('bd2d0000004981c6804d0000');c.branch('e9',loop)
  c.mark('exit');c.branch('e9',end)
 target=e.function('consumer_recipes18',hook,recipe);e.jump(hook,end,target)
 # The native dependency walker is unrolled in five-good groups. Preserve it
 #unchanged and append three singleton walks with its exact flag predicates.
 hook=0x37289+rd;end=0x3728e+rd
 assert m.image[hook:end]==bytes.fromhex('4c8b742420')
 def dependencies(c):
  c.add('bf18000000');c.mark('good');c.add('4869c7e00300004c8d9418a42300004531db')
  c.mark('recipe');c.add('4983fb08');c.branch('0f83','nextgood')
  c.add('41807a6000');c.branch('0f84','nextgood')
  c.add('418b426c8583b4010000');c.branch('0f84','nextrecipe')
  c.add('486bc75c808c181d06000090')
  c.add('4531c94d8d4208');c.mark('ingredient')
  c.add('410fb7088d41f76683f810');c.branch('0f86','mark')
  c.add('8d41c86683f815');c.branch('0f87','nextingredient')
  c.mark('mark');c.add('480fbfd1486bc25c808c181d06000090')
  c.mark('nextingredient');c.add('41ffc14983c00c410fb64260443bc8');c.branch('0f82','ingredient')
  c.mark('nextrecipe');c.add('49ffc34983c27c');c.branch('e9','recipe')
  c.mark('nextgood');c.add('83ff18');c.branch('0f84','to25');c.add('83ff19');c.branch('0f84','to45')
  c.add('4c8b742420');c.branch('e9',end)
  c.mark('to25');c.add('bf19000000');c.branch('e9','good')
  c.mark('to45');c.add('bf2d000000');c.branch('e9','good')
 target=e.function('added_consumer_dependencies',hook,dependencies);e.jump(hook,end,target)
 # Add24/25 to native consumer removal accounting.45 already belongs to the
 #native material removal pass, whose zero-guarded decrement is preserved.
 hook=0x38fa8+rd;end=0x38fbc+rd;loop=0x38f50+rd
 assert m.image[hook:end]==bytes.fromhex('4981c2e00300004983c1084981f9400100007e94')
 def removal(c):
  c.add('4981f940010000');c.branch('0f84','to24')
  c.add('4981f9c8000000');c.branch('0f84','exit')
  c.add('4981c2e00300004983c108');c.branch('e9',loop)
  c.mark('to24');c.add('41b9c00000004981ea003e0000');c.branch('e9',loop)
  c.mark('exit');c.branch('e9',end)
 target=e.function('remove_added_food_plans',hook,removal);e.jump(hook,end,target)
 data=e.finish(checksum);output=HERE/'_build'/(Path(name).stem+'.state_candidate.dll');output.write_bytes(data);candidate=Module(str(output))
 def machine(base):
  u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,(len(candidate.image)+4095)&~4095);u.mem_write(base,candidate.image)
  u.mem_map(0x31000000,0x10000);u.mem_map(0x32000000,0x40000);u.mem_map(0x33000000,0x2000)
  u.reg_write(UC_X86_REG_RSP,0x31008008);return u
 for base in [0x180000000,0x280000000]:
  # Execute complete consumer state pass with native predicates; only external
  #provider dependency expansion is replaced by a call-recording primitive.
  u=machine(base);city=0x32002000;seen=[]
  for good in goods:u.mem_write(city+0x5c4+good*0x5c+0x58,b'\x01\x00\x00')
  u.reg_write(UC_X86_REG_RSI,city);u.reg_write(UC_X86_REG_RDI,26);u.reg_write(UC_X86_REG_RBX,city+0xf76)
  def record_call(machine,address,size,user):
   seen.append(machine.reg_read(UC_X86_REG_R8)&0xffffffff)
   sp=machine.reg_read(UC_X86_REG_RSP);ret=struct.unpack('<Q',machine.mem_read(sp,8))[0]
   machine.reg_write(UC_X86_REG_RSP,sp+8);machine.reg_write(UC_X86_REG_RIP,ret)
  target=base+(0x56200 if name=='CompLogic.dll' else 0x53760);u.hook_add(UC_HOOK_CODE,record_call,begin=target,end=target)
  u.emu_start(base+0x31927+sd,base+0x31950+sd,count=10000);assert seen==goods,(name,'state pass',seen);count('native_state_passes')
  # Native preparation walks the same explicit set and forwards the correct
  #good to recipe scheduling. Availability/cost and scheduling are fixture
  #boundaries here, not proof of the external game economy.
  u=machine(base);city=0x32002000;seen=[];raw=bytearray(0xfd10)
  struct.pack_into('<I',raw,0x194,3)
  for good in goods:
   p=0x5c4+good*0x5c;raw[p+0x58:p+0x5a]=b'\x03\x10'
   struct.pack_into('<4f',raw,p+0x24,2.0,1.0,-1.0,0.0)
  u.mem_write(city,bytes(raw));u.reg_write(UC_X86_REG_RSI,city);u.reg_write(UC_X86_REG_RBX,city+0xf48)
  u.reg_write(UC_X86_REG_RDI,26);u.reg_write(UC_X86_REG_RBP,33);u.reg_write(UC_X86_REG_R14,27)
  cost=base+(0x3da10 if name=='CompLogic.dll' else 0x3b020);schedule=base+(0x58730 if name=='CompLogic.dll' else 0x55c90)
  def preparation_call(machine,address,size,user):
   if address==schedule:seen.append(machine.reg_read(UC_X86_REG_R9)&0xffff)
   sp=machine.reg_read(UC_X86_REG_RSP);ret=struct.unpack('<Q',machine.mem_read(sp,8))[0]
   machine.reg_write(UC_X86_REG_RAX,1);machine.reg_write(UC_X86_REG_RSP,sp+8);machine.reg_write(UC_X86_REG_RIP,ret)
  for target in [cost,schedule]:u.hook_add(UC_HOOK_CODE,preparation_call,begin=target,end=target)
  u.emu_start(base+0x32100+sd,base+0x32238+sd,count=20000)
  assert seen==goods,(name,'preparation pass',seen);assert u.mem_read(city,len(raw))==raw;count('native_preparation_passes')
  # Execute the entire native city recipe initializer. The external generic
  #recipe builder supplies bounded two-step fixtures; this checks the actual
  #candidate indexing, eight-recipe stop rules and consumer terminal flags.
  u=machine(base);city=0x32002000;seen=[];builder=base+(0x3a910 if name=='CompLogic.dll' else 0x39090)
  raw=bytearray([0xa5])*0xfd10;u.mem_write(city,bytes(raw))
  def build_recipe(machine,address,size,user):
   good=machine.reg_read(UC_X86_REG_R8)&0xffffffff;ordinal=machine.reg_read(UC_X86_REG_R9)&0xffffffff
   sp=machine.reg_read(UC_X86_REG_RSP);dest=struct.unpack('<Q',machine.mem_read(sp+0x30,8))[0]
   assert dest==city+0x23a4+good*0x3e0+ordinal*0x7c,(name,good,ordinal,'recipe address')
   seen.append((good,ordinal));ret=struct.unpack('<Q',machine.mem_read(sp,8))[0]
   if ordinal<2:
    plan=bytearray(0x7c);struct.pack_into('<I',plan,0,1);struct.pack_into('<I',plan,12,2);plan[0x60]=2
    machine.mem_write(dest,bytes(plan));value=1
   else:value=0
   machine.reg_write(UC_X86_REG_RAX,value);machine.reg_write(UC_X86_REG_RSP,sp+8);machine.reg_write(UC_X86_REG_RIP,ret)
  u.hook_add(UC_HOOK_CODE,build_recipe,begin=builder,end=builder)
  u.reg_write(UC_X86_REG_RCX,city);u.mem_write(0x31008008,struct.pack('<Q',0x33000000))
  u.emu_start(base+0x36b40+rd,0x33000000,count=30000)
  order=[15]+list(range(41,45))+goods+[19]+list(range(46,56))
  assert seen==[(good,ordinal) for good in order for ordinal in range(3)],(name,'whole recipe order',seen)
  expected=bytearray(raw)
  for good in order:
   for ordinal in range(2):
    p=0x23a4+good*0x3e0+ordinal*0x7c;plan=bytearray(0x7c)
    struct.pack_into('<I',plan,0,1 if good in goods else 5);struct.pack_into('<I',plan,12,4 if good in goods else 2)
    plan[0x60]=2;plan[0x61]=1 if good in goods else 0;struct.pack_into('<H',plan,0x62,good);plan[0x79]=1
    expected[p:p+0x7c]=plan
  assert u.mem_read(city,len(raw))==expected,(name,'whole recipe writes');count('native_whole_recipe_initializers')
  # All added dependency recipes use the actual instruction walker. Unlocked
  #and locked recipes plus selected/unselected ingredient classes are covered.
  for unlocked in [False,True]:
   u=machine(base);city=0x32002000;raw=bytearray(0xfd10)
   struct.pack_into('<I',raw,0x1b4,4 if unlocked else 2)
   for good in [24,25,45]:
    plan=0x23a4+good*0x3e0;raw[plan+0x60]=3;struct.pack_into('<I',raw,plan+0x6c,4)
    for ordinal,ingredient in enumerate([9,25,40]):struct.pack_into('<H',raw,plan+8+ordinal*12,ingredient)
   expected=bytearray(raw)
   if unlocked:
    for good in [24,25,45,9]:expected[0x61d+good*0x5c]|=0x90
   u.mem_write(city,bytes(raw));u.reg_write(UC_X86_REG_RBX,city)
   u.emu_start(base+0x37289+rd,base+0x3728e+rd,count=10000)
   assert u.mem_read(city,len(raw))==expected,(name,'dependencies',unlocked);count('native_added_dependency_walks')
  # Execute the complete native removal loops through both consumer and
  #material passes. Each matching step is decremented once;45 retains its
  #native material zero guard and unrelated bytes remain identical.
  for initial in [0,3]:
   u=machine(base);city=0x32002000;raw=bytearray([0xa5])*0xfd10
   for good in list(range(26,46))+[24,25]:
    plan=0x23a4+good*0x3e0;raw[plan:plan+0x3e0]=bytes(0x3e0);raw[plan+0x60]=1
    struct.pack_into('<I',raw,plan+4,1234);raw[plan+10]=initial
   expected=bytearray(raw)
   for good in list(range(26,46))+[24,25]:expected[0x23a4+good*0x3e0+10]=(initial-1)&255 if good<=40 else max(0,initial-1)
   u.mem_write(city,bytes(raw));u.reg_write(UC_X86_REG_RDI,city);u.reg_write(UC_X86_REG_RBX,1234)
   u.emu_start(base+0x38f3e+rd,base+0x39045+rd,count=10000)
   assert u.mem_read(city,len(raw))==expected,(name,'removal',initial);count('native_consumer_material_removal_passes')
 reports.append(dict(module=name,input_sha256=item['input_sha256'],market_input_sha256=item['output_sha256'],
  output=str(output.relative_to(HERE)),output_sha256=hashlib.sha256(data).hexdigest(),
  functions=e.functions,edits=[dict(rva=hex(a),before=b.hex(),after=c.hex()) for a,b,c in e.edits]))
 assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==item['input_sha256']
result=dict(scope=__doc__,modules=reports,cases=cases,actual_game_runs=0,installed_hooks=0,
 status='CANDIDATE ONLY; scoring, native recipe-builder fixtures, unlock-data audit and positive-AI gameplay remain')
(HERE/'state_candidate_manifest.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['modules','scope']},indent=2))
