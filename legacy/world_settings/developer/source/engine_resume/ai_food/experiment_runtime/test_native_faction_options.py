"""Execute original AMD64 Frame/World/Pirate instructions in a bounded fixture.

No game process is opened. Native UI text, callback, profile application, World
flags getter/setter and pirate tick branch are bound to exact source hashes.
Only the table/player enumeration boundary is doubled. The active pirate path
stops at its normal continuation; this does not prove later pirate gameplay.
"""
from pathlib import Path
import ctypes as C,hashlib,itertools,json,os,struct,subprocess,sys
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[2];ROOT=WORK.parent
sys.path.insert(0,str(WORK/'engine_audit'))
from audit import Module
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
frame=Module(str(ROOT/'AnnoFrame.dll'));world=Module(str(ROOT/'AnnoWelt.dll'));ai=Module(str(ROOT/'CompLogic.dll'))
expected={'AnnoFrame.dll':'046b5ad6f351dfe867ed38ce29fb50a594485b43a32ee90adadc48e850466baf','AnnoWelt.dll':'ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9','CompLogic.dll':'7f2c7e818d8c25a0b6c48cda2d21bfa0c4096c5dcd8be91c2ab93d877c22afee'}
for name,digest in expected.items():assert sha(ROOT/name)==digest
texts=(ROOT/'Languages/Nl/Texte.dat').read_bytes().split(b'[STARTUP:ENDLOSCUSTOMIZE]')[1].split(b'[')[0].strip().splitlines()
assert texts[2:6]==[b'Piraten: AAN',b'Piraten: UIT',b'Rampen: AAN',b'Rampen: UIT']
assert frame.image[0x47c09:0x47c10]==bytes.fromhex('803d69fe070000')
assert frame.image[0x47c31:0x47c45]==bytes.fromhex('0fb61541fe0700488bc8f6da4c8b001bd283c203')
assert struct.unpack_from('<I',world.image,0xd19cc+6*4)[0]==0xd1967
assert struct.unpack_from('<I',world.image,0xd18d4+6*4)[0]==0xd185a
candidate=Module(str(WORK/'anno1503_food_world_dev3/native/CompLogic.food-ai.dll'))
assert hashlib.sha256(candidate.data).hexdigest()=='e247ef8b755354cb5c9b2ff21bf81a5dd25646ee2012ac8204162a54daa72d9d'
assert ai.image[0x7f1f0:0x7f2ed]==candidate.image[0x7f1f0:0x7f2ed]
out=WORK/'_faction_build';out.mkdir(parents=True,exist_ok=True)
for name in ['global-cache','local-cache','tmp']:(out/name).mkdir(exist_ok=True)
fixture=out/'fixture.c';fixture.write_text('#include "'+(HERE/'native_faction_options.h').as_posix()+'"\n__declspec(dllexport) int bind(unsigned char*p,unsigned int f){return wsBindNativeFactionOptions(p,f);}\n')
env=dict(os.environ,ZIG_GLOBAL_CACHE_DIR=str(out/'global-cache'),ZIG_LOCAL_CACHE_DIR=str(out/'local-cache'),TEMP=str(out/'tmp'),TMP=str(out/'tmp'))
subprocess.run([str(WORK/'_tools/ziglang/zig.exe'),'cc','-shared','-O2','-Wall','-Wextra','-Werror',str(fixture),'-o',str(out/'NativeFactions.dll')],check=True,env=env)
lib=C.CDLL(str(out/'NativeFactions.dll'));bind=lib.bind;bind.argtypes=[C.c_void_p,C.c_uint32];bind.restype=C.c_int
binding=[]
for factions,prior in itertools.product(range(4),[0,1,255]):
 storage=C.create_string_buffer(bytes([0xa5])*0xd0000);storage[0xc7a79]=bytes([prior]);before=bytes(storage)
 assert bind(storage,factions)==1
 value=bytes(storage);assert value[:0xc7a79]==before[:0xc7a79] and value[0xc7a7a:]==before[0xc7a7a:]
 assert value[0xc7a79]==int(bool(factions&1))
 binding.append(dict(factions=factions,prior=prior,only_pirates_byte_changed=True))
for bad in [4,255,0xffffffff]:
 storage=C.create_string_buffer(bytes([0xa5])*0xd0000);before=bytes(storage);assert not bind(storage,bad) and bytes(storage)==before
assert not bind(None,0)
callbacks=[]
for base,disasters,prior in itertools.product([0x180000000,0x280000000],[False,True],[0,1,255]):
 u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,(len(frame.image)+4095)&~4095);u.mem_write(base,frame.image)
 STACK=0x31000000;OBJ=0x32000000;EXT=0x33000000;STOP=EXT+0x800
 for address,length in [(STACK,0x20000),(OBJ,0x10000),(EXT,0x1000)]:u.mem_map(address,length)
 def put(p,fmt,*v):u.mem_write(p,struct.pack(fmt,*v))
 def pointer(p,v):put(p,'<Q',v)
 lang=OBJ+0x3000;langvt=OBJ+0x4000;section=OBJ+0x5000;sectionvt=OBJ+0x6000;button=OBJ+0x7000;buttonvt=OBJ+0x8000
 pointer(base+0xc7148,lang);pointer(lang,langvt);pointer(langvt+0xc0,EXT)
 pointer(section,sectionvt);pointer(sectionvt+0x10,EXT+0x10)
 pointer(OBJ+0x21c8,OBJ+0x9000);pointer(OBJ+0x9000+(0x28 if disasters else 0x18),button)
 pointer(button,buttonvt);pointer(buttonvt+0xa0,EXT+0x20)
 selected=0xc7a78 if disasters else 0xc7a79;other=0xc7a79 if disasters else 0xc7a78
 put(base+selected,'<B',prior);put(base+other,'<B',0xa5)
 for x in [0,0x10,0x20,0x800]:u.mem_write(EXT+x,b'\xc3')
 chosen=[];published=[]
 def callback_hook(machine,address,size,_):
  if not EXT<=address<EXT+0x30:return
  rcx=machine.reg_read(UC_X86_REG_RCX);rdx=machine.reg_read(UC_X86_REG_RDX);r8=machine.reg_read(UC_X86_REG_R8)
  if address==EXT:
   assert rcx==lang and bytes(u.mem_read(rdx,23)).split(b'\0')[0]==b'STARTUP:ENDLOSCUSTOMIZE'
   result=section
  elif address==EXT+0x10:
   assert rcx==section;chosen.append(rdx);result=OBJ+0xa000
  else:
   assert rcx==button and rdx==0x1c4 and struct.unpack('<Q',u.mem_read(r8+8,8))[0]==OBJ+0xa000
   published.append(True);result=1
  machine.reg_write(UC_X86_REG_RAX,result)
 u.hook_add(UC_HOOK_CODE,callback_hook)
 rsp=STACK+0x10008;pointer(rsp,STOP);u.reg_write(UC_X86_REG_RSP,rsp);u.reg_write(UC_X86_REG_RCX,OBJ)
 u.emu_start(base+(0x47c80 if disasters else 0x47c00),STOP,count=1000)
 enabled=not prior;wanted=(4 if disasters else 2)+int(not enabled)
 assert chosen==[wanted] and published==[True] and bytes(u.mem_read(base+selected,1))==bytes([int(enabled)]) and bytes(u.mem_read(base+other,1))==b'\xa5'
 callbacks.append(dict(base=hex(base),disasters=disasters,prior=prior,native_text_index=wanted,text=texts[wanted].decode('ascii'),other_option_untouched=True))
cases=[]
for base,flags,disasters,factions,kind in itertools.product([0x180000000,0x280000000],[0,0x20,0xa6,0xffffffff,0x80000000,0x12345678],[0,1],range(4),[0,1]):
 wb=base+0x2000000;ab=base+0x4000000
 u=Uc(UC_ARCH_X86,UC_MODE_64)
 for module,address in [(frame,base),(world,wb),(ai,ab)]:
  u.mem_map(address,(len(module.image)+4095)&~4095);u.mem_write(address,module.image)
 STACK=0x31000000;OBJ=0x32000000;EXT=0x33000000;STOP=EXT+0x800
 for address,length in [(STACK,0x20000),(OBJ,0x20000),(EXT,0x1000)]:u.mem_map(address,length)
 def put(p,fmt,*v):u.mem_write(p,struct.pack(fmt,*v))
 def pointer(p,v):put(p,'<Q',v)
 table=OBJ;tablevt=OBJ+0x1000;w=OBJ+0x2000;pvt=OBJ+0xa000;ctrl=OBJ+0xb000;cvt=OBJ+0xe000
 players=[OBJ+0x9000+i*0x100 for i in range(3)];types=[11,16,15]
 pointer(table,tablevt);pointer(tablevt+0x10,EXT);pointer(tablevt+0x18,EXT+0x10)
 for p in players:pointer(p,pvt)
 pointer(pvt+0x88,EXT+0x20);pointer(pvt+0x98,EXT+0x30)
 pointer(w,wb+0xff650);pointer(wb+0xff650+0xf0,wb+0xd1910);pointer(wb+0xff650+0xe8,wb+0xd1800)
 put(w+0x6eec,'<I',flags);put(w+0x6e48,'<B',kind)
 put(base+0xc7a78,'<B',disasters);put(base+0xc7a79,'<B',int(bool(factions&1)))
 pointer(ctrl,cvt);pointer(cvt+0x40,ab+0x1020);put(ctrl+0xab4,'<I',0);put(ctrl+0x1e9d,'<B',1)
 pointer(players[2]+0x18,ctrl)
 pointer(ab+0x93770,w)
 for x in [0,0x10,0x20,0x30,0x800]:u.mem_write(EXT+x,b'\xc3')
 player_queries=[];normal=[False]
 def hook(machine,address,size,_):
  if address==ab+0x7f2ed:normal[0]=True;machine.emu_stop();return
  if not EXT<=address<EXT+0x40:return
  rcx=machine.reg_read(UC_X86_REG_RCX);rdx=machine.reg_read(UC_X86_REG_RDX);r8=machine.reg_read(UC_X86_REG_R8)
  if address==EXT:result=3
  elif address==EXT+0x10:result=players[rdx] if rdx<3 else 0
  elif address==EXT+0x20:result=[0,5,6][players.index(rcx)]
  else:
   assert rdx in [9,11],('Special player unexpectedly received controller/profile operation',rdx)
   player_queries.append((players.index(rcx),rdx));put(r8+8,'<Q',types[players.index(rcx)] if rdx==9 else 255);result=1
  machine.reg_write(UC_X86_REG_RAX,result)
 u.hook_add(UC_HOOK_CODE,hook)
 def call(address,rcx=0,rdx=0,r8=0):
  rsp=STACK+0x10008;pointer(rsp,STOP)
  for reg,value in [(UC_X86_REG_RSP,rsp),(UC_X86_REG_RCX,rcx),(UC_X86_REG_RDX,rdx),(UC_X86_REG_R8,r8)]:u.reg_write(reg,value)
  u.emu_start(address,STOP,count=10000)
 call(base+0x476e0,OBJ+0x10000)  # the real post-dialog stock profile commit
 assert bytes(u.mem_read(base+0xc7a78,2))==bytes([disasters,int(bool(factions&1))])
 call(base+0x55330,0,w,table)
 after=struct.unpack('<I',u.mem_read(w+0x6eec,4))[0]
 after_disasters=(flags&~0x86) if disasters else (flags|0x86)
 wanted=(after_disasters&~0x20) if factions&1 else (after_disasters|0x20)
 assert after==wanted and (after^after_disasters)&~0x20==0
 assert player_queries==[(i,p) for i in range(3) for p in [9,11]]
 assert struct.unpack('<I',u.mem_read(ctrl+0xab4,4))[0]==0 and bytes(u.mem_read(ctrl+0x1e9d,1))==b'\1'
 call(ab+0x7f1f0,ctrl,OBJ+0xf000)
 disabled=kind==0 and not(factions&1)
 assert normal[0]==(not disabled)
 assert struct.unpack('<I',u.mem_read(ctrl+0xab4,4))[0]==int(disabled)
 assert bytes(u.mem_read(ctrl+0x1e9d,1))==bytes([int(not disabled)])
 cases.append(dict(base=hex(base),initial_flags=hex(flags),disasters=disasters,factions=factions,world_kind=kind,result_flags=hex(after),pirate_suspended=disabled,native_commit_preserved_options=True,native_profile_ignored_specials=True,normal_tick_continuation=normal[0]))
result=dict(scope=__doc__,actual_game_runs=0,source_sha256=expected,candidate_ai_sha256=hashlib.sha256(candidate.data).hexdigest(),pirate_tick_region_unchanged_in_approved_candidate=True,ui_text_sha256=sha(ROOT/'Languages/Nl/Texte.dat'),helper_sha256=sha(HERE/'native_faction_options.h'),test_sha256=sha(Path(__file__)),compiled_dll_sha256=sha(out/'NativeFactions.dll'),binding_cases=binding,invalid_no_write_cases=4,native_ui_callbacks=callbacks,native_cases=cases,venetian_checkbox_does_not_change_native_pirate_or_disaster_option=True,disasters_global_preserved=True)
(HERE/'native_faction_options_results.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(binding_cases=len(binding),invalid_no_write_cases=4,native_ui_callbacks=len(callbacks),native_cases=len(cases),actual_game_runs=0)))
