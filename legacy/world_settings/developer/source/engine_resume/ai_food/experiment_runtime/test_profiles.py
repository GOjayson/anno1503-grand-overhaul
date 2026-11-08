"""Compiled profile writer plus native Frame commit/application instructions.

Runs in a Python fixture process. Table/player/property operations are explicit
doubles. It does not attach to, launch, patch or configure an actual game.
"""
from pathlib import Path
import ctypes as C,hashlib,itertools,json,os,struct,subprocess,sys
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[2];ROOT=WORK.parent
sys.path.insert(0,str(WORK/'engine_audit'))
from audit import Module
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *
out=HERE/'_build';out.mkdir(exist_ok=True);(out/'tmp').mkdir(exist_ok=True)
env=dict(os.environ,ZIG_GLOBAL_CACHE_DIR=str(out/'global-cache'),ZIG_LOCAL_CACHE_DIR=str(out/'local-cache'),TEMP=str(out/'tmp'),TMP=str(out/'tmp'))
fixture=out/'profiles_fixture.c'
fixture.write_text('#include "'+(HERE/'world_ai.c').as_posix()+'"\nint WorldSettingsIsActive(void){return 0;}\nvoid WorldSettingsFinishAttempt(int success){WorldSettingsAIProfileAttemptFinished(success);}\n','utf-8')
command=[str(WORK/'_tools/ziglang/zig.exe'),'cc','-shared','-O2','-Wall','-Wextra','-Werror','-DWS_AI_FIXTURE',str(fixture),'-o',str(out/'WorldAIProfiles.dll')]
subprocess.run(command,check=True,env=env)
lib=C.CDLL(str(out/'WorldAIProfiles.dll'))
bind=lib.WorldSettingsBindStockAIProfiles;bind.argtypes=[C.c_void_p,C.c_int32,C.c_int32,C.c_void_p,C.c_uint32]
error=C.create_string_buffer(512)
m=Module(str(ROOT/'AnnoFrame.dll'))
assert hashlib.sha256(m.data).hexdigest()=='046b5ad6f351dfe867ed38ce29fb50a594485b43a32ee90adadc48e850466baf'
evidence=json.loads((HERE/'profile_sources.json').read_text());results=[]
for difficulty in range(3):
 for count in range(4):
  storage=C.create_string_buffer(bytes([0xa5])*0x2800,0x2800)
  assert bind(storage,difficulty,count,error,len(error))==1 and not error.value
  value=bytes(storage);assert value[:0x2280]==bytes([0xa5])*0x2280 and value[0x2720:]==bytes([0xa5])*(0x2800-0x2720)
  assert value[0x2287]==0xa5 and value[0x2280:0x2287]==bytes([1]*count+[0]*(7-count))
  for i in range(7):
   row=value[0x2288+i*168:0x2288+(i+1)*168]
   assert (hashlib.sha256(row).hexdigest()==evidence[difficulty]['profile_sha256'][i]) if i<count else row==bytes(168)
  for base,classic in itertools.product([0x180000000,0x280000000],[False,True]):
   u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,(len(m.image)+4095)&~4095);u.mem_write(base,m.image)
   ai=Module(str(ROOT/('CompLogicClassic.dll' if classic else 'CompLogic.dll')));aibase=base+0x300000000
   assert hashlib.sha256(ai.data).hexdigest()==('0a7692879e15e8cbaed73ec3b59eaa6419165faaea6d8696cddfd68c92000f22' if classic else '7f2c7e818d8c25a0b6c48cda2d21bfa0c4096c5dcd8be91c2ab93d877c22afee')
   u.mem_map(aibase,(len(ai.image)+4095)&~4095);u.mem_write(aibase,ai.image)
   STACK=0x31000000;OBJ=0x32000000;EXT=0x33000000;STOP=EXT+0x800
   for address,length in [(STACK,0x20000),(OBJ,0x60000),(EXT,0x10000)]:u.mem_map(address,length)
   u.mem_write(OBJ,value);u.mem_write(STOP,b'\xc3')
   def call(rva,rcx=OBJ,rdx=0,r8=0):
    rsp=STACK+0x10008;u.mem_write(rsp,struct.pack('<Q',STOP))
    for register,v in [(UC_X86_REG_RSP,rsp),(UC_X86_REG_RCX,rcx),(UC_X86_REG_RDX,rdx),(UC_X86_REG_R8,r8)]:u.reg_write(register,v)
    u.emu_start(base+rva,STOP,count=100000)
   call(0x476e0)
   assert bytes(u.mem_read(base+0xc75e0,7*168))==value[0x2288:0x2720]
   table=OBJ+0x8000;world=OBJ+0x9000;players=[OBJ+0x10000+i*0x100 for i in range(1+(3 if difficulty==0 else 4))]
   controllers={p:OBJ+0x30000+i*0x2400 for i,p in enumerate(players) if i}
   tablevt=OBJ+0xa000;playervt=OBJ+0xb000;worldvt=OBJ+0xc000;controllervt=OBJ+0xd000
   def pointer(address,value):u.mem_write(address,struct.pack('<Q',value))
   def fn(vt,slot,offset):pointer(vt+slot,EXT+offset);u.mem_write(EXT+offset,b'\xc3')
   pointer(table,tablevt);fn(tablevt,0x10,0);fn(tablevt,0x18,0x10)
   pointer(world,worldvt);fn(worldvt,0xf0,0x20);fn(worldvt,0xe8,0x30)
   for p in players:pointer(p,playervt)
   fn(playervt,0x88,0x40);fn(playervt,0x98,0x50)
   for controller in controllers.values():
    pointer(controller,controllervt);u.mem_write(controller+0xab4,struct.pack('<I',1))
   fn(controllervt,8,0x60)
   sets={p:[] for p in controllers};worldflags=[]
   def hook(machine,address,size,_):
    if not EXT<=address<EXT+0x70:return
    rcx=machine.reg_read(UC_X86_REG_RCX);rdx=machine.reg_read(UC_X86_REG_RDX);r8=machine.reg_read(UC_X86_REG_R8)
    result=0
    if address==EXT:result=32
    elif address==EXT+0x10:result=players[rdx] if rdx<len(players) else 0
    elif address==EXT+0x20:result=0
    elif address==EXT+0x30:worldflags.append((rdx,r8));result=1
    elif address==EXT+0x40:result=players.index(rcx)
    elif address==EXT+0x50:
     i=players.index(rcx)
     v=(11 if i==0 else 12) if rdx==9 else (255 if rdx==11 else controllers.get(rcx,0))
     assert rdx in [9,11,0x2c]
     u.mem_write(r8+8,struct.pack('<Q',v));result=1
    elif address==EXT+0x60:
     p=next(p for p,c in controllers.items() if c==rcx)
     v=struct.unpack('<I',u.mem_read(r8+0x18,4))[0] if r8 else None
     sets[p].append((rdx,v));result=1
     if rdx in [0x1a,0x22]:
      machine.reg_write(UC_X86_REG_RIP,aibase+(0x4260 if classic else 0x6090));return
    machine.reg_write(UC_X86_REG_RAX,result)
   u.hook_add(UC_HOOK_CODE,hook)
   call(0x55330,0,world,table)
   selected=0
   for i,p in enumerate(players[1:]):
    if i<count:
     assert (0x1a,0) in sets[p] and not any(prop==0x22 for prop,v in sets[p]),sets[p]
     c=controllers[p];assert bytes(u.mem_read(c+0x1e9d,1))==b'\1' and struct.unpack('<II',u.mem_read(c+0xab0,8))==(0,0)
     selected+=1
    else:
     assert sets[p]==[(0x22,None)],sets[p]
     c=controllers[p];assert bytes(u.mem_read(c+0x1e9d,1))==b'\0' and struct.unpack('<II',u.mem_read(c+0xab0,8))==(1,1)
   assert selected==count and len(worldflags)==2
   results.append(dict(difficulty=difficulty,ai_count=count,image_base=hex(base),classic_ai=classic,stock_cpu_placeholders=len(players)-1,profile_selected_count=selected,native_commit=True,native_application=True,native_suspend_and_disable_setters=True))
badcases=[]
for difficulty,count in [(-1,0),(3,0),(0,-1),(0,4),(1,7),(2,31)]:
 storage=C.create_string_buffer(bytes([0xb6])*0x2800,0x2800);before=bytes(storage)
 assert not bind(storage,difficulty,count,error,len(error)) and error.value and bytes(storage)==before
 badcases.append(dict(difficulty=difficulty,count=count,no_write=True))
assert not bind(None,0,0,error,len(error))
check=lib.WorldSettingsCheckAIControllers;check.argtypes=[C.c_void_p,C.c_int32,C.c_void_p,C.c_void_p,C.c_uint32]
testmodule=lib.WorldSettingsAITestWorldModule;testmodule.argtypes=[C.c_void_p]
k=C.WinDLL('kernel32',use_last_error=True)
k.VirtualAlloc.argtypes=[C.c_void_p,C.c_size_t,C.c_uint32,C.c_uint32];k.VirtualAlloc.restype=C.c_void_p
k.VirtualFree.argtypes=[C.c_void_p,C.c_size_t,C.c_uint32]
worldmodule=k.VirtualAlloc(None,0x110000,0x3000,4);aimodule=k.VirtualAlloc(None,0xa0000,0x3000,4)
assert worldmodule and aimodule
certcases=[];flagmatrix=[]
try:
 testmodule(worldmodule)
 def put(address,fmt,*values):C.memmove(address,struct.pack(fmt,*values),struct.calcsize(fmt))
 put(worldmodule+0xfdbc0+0x10,'<Q',worldmodule+0xc6d80);put(worldmodule+0xfdbc0+0x18,'<Q',worldmodule+0x95990)
 for classic in [False,True]:
  vt=aimodule+(0x84fc8 if classic else 0x88128)
  put(vt+8,'<Q',aimodule+(0x4260 if classic else 0x6090));put(vt+0x10,'<Q',aimodule+(0x4a10 if classic else 0x6640))
  for stock in [3,4]:
   for expected in range(4):
    fixture=C.create_string_buffer(0x20000);start=C.addressof(fixture);world=start;table=start+0x1000
    put(world,'<Q',worldmodule+0xff1d8);put(world+0x210,'<Q',table);put(table,'<Q',worldmodule+0xfdbc0)
    for i in range(stock+1):
     player=start+0x2000+i*0x100;controller=start+0x3000+i*0x2200
     put(table+8+i*8,'<Q',player);put(player,'<Q',worldmodule+0xfabe0);put(player+0x9c,'<H',11 if i==0 else 12)
     if not i:continue
     put(player+0x18,'<Q',controller);put(controller,'<Q',vt);put(controller+0xa4c,'<I',12)
     enabled=i<=expected
     put(controller+0xab4,'<I',0 if enabled else 1);put(controller+0xab0,'<I',0 if enabled else 1);put(controller+0x1e9d,'<B',1 if enabled else 0)
    before=bytes(fixture)
    assert check(world,expected,aimodule,error,len(error))==1 and not error.value
    assert bytes(fixture)==before
    if expected<3:assert not check(world,expected+1,aimodule,error,len(error)) and error.value
    assert not check(world,expected,None,error,len(error))
    first=start+0x3000+0x2200
    put(first,'<Q',vt+8);assert not check(world,expected,aimodule,error,len(error));put(first,'<Q',vt)
    put(first+0xab4,'<I',2);assert not check(world,expected,aimodule,error,len(error))
    put(first+0xab4,'<I',0);put(first+0xab0,'<I',1);put(first+0x1e9d,'<B',1)
    assert not check(world,expected,aimodule,error,len(error))
    certcases.append(dict(classic=classic,stock=stock,expected=expected,read_only_valid=True,wrong_count_and_class_and_flags_rejected=True))
 # Explicit native-state truth table: an ordinary selected CPU is0/0/1
 # (disabled/suspend/thinking). Dormant states have suspend1/thinking0.
 vt=aimodule+0x88128
 for disabled,suspend,thinking,expected in itertools.product(range(2),repeat=4):
  fixture=C.create_string_buffer(0x20000);start=C.addressof(fixture);world=start;table=start+0x1000
  put(world,'<Q',worldmodule+0xff1d8);put(world+0x210,'<Q',table);put(table,'<Q',worldmodule+0xfdbc0)
  for i in range(1,4):
   player=start+0x2000+i*0x100;controller=start+0x3000+i*0x2200
   put(table+8+i*8,'<Q',player);put(player,'<Q',worldmodule+0xfabe0);put(player+0x9c,'<H',12)
   put(player+0x18,'<Q',controller);put(controller,'<Q',vt);put(controller+0xa4c,'<I',12)
   put(controller+0xab4,'<I',suspend if i==1 else 1);put(controller+0xab0,'<I',disabled if i==1 else 1);put(controller+0x1e9d,'<B',thinking if i==1 else 0)
  active=disabled==0 and suspend==0 and thinking==1
  dormant=suspend==1 and thinking==0
  wanted=(active and expected==1) or (dormant and expected==0)
  assert bool(check(world,expected,aimodule,error,len(error)))==wanted
  flagmatrix.append(dict(disabled=disabled,suspend=suspend,thinking=thinking,expected=expected,accepted=wanted))
finally:
 testmodule(None);k.VirtualFree(worldmodule,0,0x8000);k.VirtualFree(aimodule,0,0x8000)
result=dict(scope=__doc__,actual_game_runs=0,source_sha256=hashlib.sha256(m.data).hexdigest(),helper_source_sha256={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in ['world_ai.c','world_ai.h','stock_ai_profiles.h','special_activity.inc']},compiled_dll_sha256=hashlib.sha256((out/'WorldAIProfiles.dll').read_bytes()).hexdigest(),native_cases=results,rejected_without_mutation=badcases,null_setup_rejected=True,controller_certificate_fixtures=certcases,explicit_flag_matrix=flagmatrix)
(HERE/'profile_results.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')
print(json.dumps(dict(native_cases=len(results),rejected_without_mutation=len(badcases),controller_certificate_fixtures=len(certcases),explicit_flag_matrix=len(flagmatrix),actual_game_runs=0)))
