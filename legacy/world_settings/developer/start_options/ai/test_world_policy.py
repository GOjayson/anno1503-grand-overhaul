"""Execute central policy plus actual native relation endpoint/caller instructions.

Strict player interface doubles record side effects. Actual main/Classic AI,
three AnnoWelt attack/job call sites and Frame diplomacy dispatch call the same
patched native endpoint. No game is launched and combat balance is not proven.
"""
from pathlib import Path
import hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'WorldSettings_Work/engine_audit'));from audit import Module
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *
from world_policy_bridge import build_world_policy_code
transient='--transient' in sys.argv
wm=json.loads((HERE/'welt_policy_manifest.json').read_text());am=json.loads((HERE/'candidate_manifest.json').read_text())
worldm=Module(str(HERE/wm['output']));frame=Module(str(ROOT/'AnnoFrame.dll'));cases=[]
assert hashlib.sha256(worldm.data).hexdigest()==wm['sha256']
for classic in [False,True]:
 aiitem=am['payloads'][int(classic)];aim=Module(str(HERE/aiitem['output']))
 for worldbase in [0x180000000,0x480000000]:
  aibase=worldbase+0x100000000;framebase=worldbase+0x200000000
  u=Uc(UC_ARCH_X86,UC_MODE_64)
  for base,m in [(worldbase,worldm),(aibase,aim),(framebase,frame)]:u.mem_map(base,(len(m.image)+4095)&~4095);u.mem_write(base,m.image)
  if transient:
   pool=0x190000 if worldbase==0x180000000 else 0x1a0000
   bridge,names=build_world_policy_code(pool);u.mem_map(worldbase+pool,0x1000);u.mem_write(worldbase+pool,bridge)
   u.mem_write(worldbase+0xdf460,b'\xe9'+struct.pack('<i',pool-0xdf460-5)+b'\x90')
  u.mem_map(0x31000000,0x10000);u.mem_map(0x32000000,0x40000);u.mem_map(0x33000000,0x2000)
  world=0x32002000;table=0x32008000;controller=0x3200a000;src=0x32010000;tgt=0x32012000;job=0x32018000;frameobj=0x32019000;event=0x3201a000
  wvt=worldbase+0xff650;pvt=worldbase+0xfabe0;source_id=2;target_id=0
  def put(p,fmt,*v):u.mem_write(p,struct.pack(fmt,*v))
  def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
  put(world,'<Q',wvt);put(world+0x210,'<Q',table);put(table,'<Q',worldbase+0xfdbc0)
  put(wvt+0x210,'<Q',worldbase+0xdf460)
  put(src,'<Q',pvt);put(src+8,'<I',source_id);put(src+0x10,'<Q',world);put(src+0x18,'<Q',controller)
  put(tgt,'<Q',pvt);put(tgt+0x10,'<Q',world);put(controller,'<Q',aibase+aiitem['vtable_rva']);put(controller+8,'<Q',world);put(controller+0xa64,'<H',source_id)
  put(table+8+source_id*8,'<Q',src);put(job+0x20,'<Q',world);put(job+0x28,'<Q',world);put(frameobj+0x10,'<Q',world);put(event,'<B',2);put(event+3,'<I',3)
  for off,stub in [(0x100,0x33000100),(0x108,0x33000120),(0x190,0x33000140),(0x88,0x33000160),(0x188,0x33000180)]:put(pvt+off,'<Q',stub)
  relations={};effects=[]
  def ret(value=0):
   sp=u.reg_read(UC_X86_REG_RSP);to=struct.unpack('<Q',u.mem_read(sp,8))[0]
   u.reg_write(UC_X86_REG_RAX,value);u.reg_write(UC_X86_REG_RSP,sp+8);u.reg_write(UC_X86_REG_RIP,to)
  def player(machine,address,size,unused):
   rcx=u.reg_read(UC_X86_REG_RCX);rdx=u.reg_read(UC_X86_REG_RDX);r8=u.reg_read(UC_X86_REG_R8);r9=u.reg_read(UC_X86_REG_R9)
   if address==worldbase+0xdf3c0:effects.append(['native event',rdx,r8]);ret();return
   assert rcx in [src,tgt]
   if address==0x33000100:assert r8 in [src,tgt] and r8!=rcx;ret(relations[rcx][rdx])
   elif address==0x33000120:assert r8 in [src,tgt] and r8!=rcx;relations[rcx][rdx]=r9;effects.append(['relation',rcx,rdx,r9]);ret(1)
   elif address==0x33000140:ret(0)
   elif address==0x33000160:ret(source_id if rcx==src else target_id)
   elif address==0x33000180:assert rdx==7;effects.append(['native flags',rcx,r8]);ret(1)
   else:raise AssertionError(hex(address))
  for stub in [0x33000100,0x33000120,0x33000140,0x33000160,0x33000180,worldbase+0xdf3c0]:u.hook_add(UC_HOOK_CODE,player,begin=stub,end=stub)
  callers=['direct','main AI' if not classic else 'Classic AI','engine job bf47','engine job1656f','engine job166c8','Frame dispatch']
  def run(caller,typ=2,state=3):
   for owner,otherid in [(src,target_id),(tgt,source_id)]:
    for relation in range(3):put(owner+0x1d8+otherid*6+relation,'<B',relations[owner][relation])
   sp=0x31008000;stop=0x33000000
   regs={UC_X86_REG_RSP:sp,UC_X86_REG_RCX:world,UC_X86_REG_RDX:typ,UC_X86_REG_R8:state,UC_X86_REG_R9:src}
   put(sp+0x20,'<Q',tgt)
   if caller=='direct':sp+=8;regs[UC_X86_REG_RSP]=sp;put(sp,'<Q',stop);put(sp+0x28,'<Q',tgt);start=worldbase+0xdf460
   elif caller.endswith('AI'):
    start=aibase+aiitem['native_declaration_call_rva'];stop=start+7;regs[UC_X86_REG_R10]=wvt
   elif caller=='engine job bf47':start=worldbase+0xbf32;stop=worldbase+0xbf4d;regs.update({UC_X86_REG_RDI:job,UC_X86_REG_RSI:src,UC_X86_REG_R14:tgt})
   elif caller=='engine job1656f':start=worldbase+0x16557;stop=worldbase+0x16575;regs.update({UC_X86_REG_RDI:job,UC_X86_REG_RSI:src,UC_X86_REG_R14:tgt,UC_X86_REG_R15:typ})
   elif caller=='engine job166c8':start=worldbase+0x166b0;stop=worldbase+0x166cf;regs.update({UC_X86_REG_RDI:job,UC_X86_REG_RSI:src,UC_X86_REG_R14:tgt,UC_X86_REG_R15:typ})
   else:start=framebase+0x7f704;stop=framebase+0x7f723;regs.update({UC_X86_REG_R12:frameobj,UC_X86_REG_R14:event,UC_X86_REG_RDI:src,UC_X86_REG_RAX:tgt})
   for r,v in regs.items():u.reg_write(r,v)
   try:u.emu_start(start,stop,count=10000)
   except Exception as exc:raise AssertionError((caller,hex(u.reg_read(UC_X86_REG_RIP)))) from exc
   assert u.reg_read(UC_X86_REG_RIP)==stop and u.reg_read(UC_X86_REG_RSP)==sp+(8 if caller=='direct' else 0)
  for target_id in [0,1,3]:
   put(tgt+8,'<I',target_id);put(table+8+target_id*8,'<Q',tgt)
   for mode,wanted in enumerate([0,16,32,64]):
    for caller in callers:
     initial=0x5753000f|(mode<<8);put(controller+0xab8,'<I',initial);put(controller+0xa4c,'<I',12);put(src+0x9c,'<H',12);allowed=0
     for attempt in range(64):
      relations={src:{0:3,1:3,2:0},tgt:{0:3,1:3,2:0}};effects=[];run(caller)
      if relations[src][2]==3:allowed+=1;assert relations[src]==relations[tgt]=={0:0,1:0,2:3} and effects
      else:assert relations[src]==relations[tgt]=={0:3,1:3,2:0} and not effects
     assert allowed==wanted and word(controller+0xab8)==initial
     cases.append(dict(classic=classic,image_base=hex(worldbase),target=target_id,mode=mode,caller=caller,requests=64,permitted=allowed))
  # Incoming human declarations and all stock untagged/special initiators pass.
  for typ in [8,11,12,13,15,16]:
   for flags in [0,15,0x12345678,0x57530000] if typ!=12 else [0,15,0x12345678]:
    put(src+0x9c,'<H',typ);put(controller+0xa4c,'<I',typ);put(controller+0xab8,'<I',flags)
    relations={src:{0:3,1:3,2:0},tgt:{0:3,1:3,2:0}};effects=[];run('direct')
    assert relations[src][2]==relations[tgt][2]==3 and effects and word(controller+0xab8)==flags
  # A tagged Peaceful CPU can propose or accept peace; no policy/counter edit.
  put(src+0x9c,'<H',12);put(controller+0xa4c,'<I',12);put(controller+0xab8,'<I',0x5753000f)
  for state in [1,0]:
   relations={src:{0:0,1:0,2:3},tgt:{0:0,1:0,2:3}};effects=[];run('direct',state=state)
   assert (relations[src][2],relations[tgt][2])==((1,2) if state else (0,0)) and effects and word(controller+0xab8)==0x5753000f
  # Existing war passes every caller and every mode, without consuming cadence.
  for mode in range(4):
   flags=0x5753a40f|(mode<<8);put(controller+0xab8,'<I',flags)
   for existing in [1,2,3]:
    for caller in callers:
     relations={src:{0:0,1:0,2:existing},tgt:{0:0,1:0,2:existing}};effects=[];run(caller)
     assert relations[src][2]==relations[tgt][2]==3 and effects and word(controller+0xab8)==flags
   relations={src:{0:0,1:0,2:4},tgt:{0:0,1:0,2:4}};effects=[];run('direct')
   assert not effects and word(controller+0xab8)==flags
  put(controller+0xab8,'<I',0x5753000f)
  # Tagged controller with broken ownership is denied with no native effects.
  for loc,fmt,bad,good in [(src+0x10,'<Q',world+8,world),(controller+8,'<Q',world+8,world),(controller+0xa64,'<H',7,source_id),(src+8,'<I',32,source_id),(table+8+source_id*8,'<Q',tgt,src)]:
   put(loc,fmt,bad);relations={src:{0:0,1:0,2:0},tgt:{0:0,1:0,2:0}};effects=[];run('direct');assert not effects and relations[src][2]==relations[tgt][2]==0;put(loc,fmt,good)
  uw=wm['unwind_rva'];assert worldm.image[uw:uw+4]==bytes.fromhex('01000000')
result=dict(scope=__doc__,cases=cases,matrix_cases=len(cases),native_requests=sum(c['requests'] for c in cases),actual_game_runs=0,passed=True,world_sha256=wm['sha256'],ai_sha256={p['module']:p['sha256'] for p in am['payloads']},native_leaf_unwind_verified=True,existing_war_passes_all_modes_all_callers_without_cadence=True,bridge_source_sha256=hashlib.sha256((HERE/'world_policy_bridge.py').read_bytes()).hexdigest(),transient_arena=transient)
(HERE/('transient_policy_test_results.json' if transient else 'world_policy_test_results.json')).write_text(json.dumps(result,indent=2)+'\n','utf-8');print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2))
