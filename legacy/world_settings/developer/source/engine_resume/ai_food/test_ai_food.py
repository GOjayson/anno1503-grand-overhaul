"""Build and test isolated candidate helpers; never loads or starts Anno.

The original Food Mod binaries are fingerprinted by ai_instruction_evidence.
Unicorn executes the original pending writer, selection scan and demand body
on private fixtures. The candidate helper DLL is loaded only into this Python
test process. No native hook installation is attempted.
"""
from pathlib import Path
import ctypes as C,json,struct,sys,subprocess,os,hashlib,random
HERE=Path(__file__).resolve().parent
WORK=HERE.parents[1];ROOT=WORK.parent
sys.path.insert(0,str(WORK/'engine_audit'))
from audit import Module
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *

SOURCES={
 'CompLogic.dll':('7f2c7e818d8c25a0b6c48cda2d21bfa0c4096c5dcd8be91c2ab93d877c22afee',0x57c59,0x57c86,0x1ab90,0x1abe0,0x582e5,0x58401),
 'CompLogicClassic.dll':('0a7692879e15e8cbaed73ec3b59eaa6419165faaea6d8696cddfd68c92000f22',0x551b9,0x551e6,0x194f0,0x19540,0x55845,0x55961)}
out=HERE/'_build';out.mkdir(exist_ok=True)
(out/'tmp').mkdir(exist_ok=True)
env=dict(os.environ,ZIG_GLOBAL_CACHE_DIR=str(out/'global-cache'),ZIG_LOCAL_CACHE_DIR=str(out/'local-cache'),TEMP=str(out/'tmp'),TMP=str(out/'tmp'))
command=[str(WORK/'_tools/ziglang/zig.exe'),'cc','-shared','-O2','-ffp-contract=off','-Wall','-Wextra','-Werror','-std=c11',str(HERE/'ai_food.c'),'-o',str(out/'AnnoAIFoodCandidate.dll')]
subprocess.run(command,check=True,env=env)
dll=C.CDLL(str(out/'AnnoAIFoodCandidate.dll'))
u32=C.c_uint32;i32=C.c_int32;ptr=C.c_void_p
def bind(name,args,result=i32):
 f=getattr(dll,name);f.argtypes=args;f.restype=result;return f
offset=bind('AIFPendingRecordOffset',[u32],C.c_size_t)
init=bind('AIFPendingAfterConstructor',[ptr,C.c_size_t])
add=bind('AIFPendingAdd',[ptr,u32,i32,i32]);clear=bind('AIFPendingClear',[ptr,u32])
at=bind('AIFConsumerAt',[u32],u32);isconsumer=bind('AIFIsConsumer',[u32])
class Choice(C.Structure):_fields_=[('node',ptr),('good',u32),('count',u32),('x',i32),('y',i32)]
class Demand(C.Structure):_fields_=[('demand',C.c_float),('negative',C.c_float),('stock',C.c_float)]
select=bind('AIFPendingSelect',[ptr,u32,C.POINTER(Choice)])
demand=bind('AIFEvaluateDemand',[ptr,C.POINTER(i32),u32,u32,i32,C.POINTER(Demand)])
removeplans=bind('AIFRemoveAddedFoodPlans',[ptr,C.c_size_t,u32])
Getter=C.CFUNCTYPE(u32,ptr,C.c_uint8)
warecount=bind('AIFMarketWareCount',[ptr,u32,Getter],u32)
covers=bind('AIFMarketCovers',[ptr,u32,Getter,u32])
clearmarket=bind('AIFPendingClearMarket',[ptr,ptr,u32,Getter])
stand=bind('AIFConsumerStand',[ptr,u32,u32],u32)
assert bind('AIFReadyForGame',[])()==0
goods=[at(n) for n in range(18)]
assert goods==list(range(26,41))+[24,25,45] and at(18)==0
assert {x for x in range(80) if isconsumer(x)}==set(goods)

def machine(m,base):
 u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,(len(m.image)+4095)&~4095);u.mem_write(base,m.image)
 u.mem_map(0x31000000,0x10000);u.mem_map(0x32000000,0x20000);u.mem_map(0x33000000,0x1000)
 u.reg_write(UC_X86_REG_RSP,0x31008008)
 return u
def buf(data):return C.create_string_buffer(bytes(data),len(data))
def writesafe(node,good,x,y):
 p=offset(good);struct.pack_into('<ii',node,p,x,y);struct.pack_into('<H',node,p+12,1)
checks=dict(native_writer_comparisons=0,native_selection_comparisons=0,native_demand_comparisons=0,
 native_added_food_demand_comparisons=0,
 native_removal_comparisons=0,append_and_canary_cases=0,market_cases=0)
rng=random.Random(1503)

# All old offsets stay put. Append initialization must not modify native bytes.
for good in goods:
 raw=bytearray([0xa5])*0x388;b=buf(raw);node=C.addressof(b)+16
 assert init(node,0x340)==0 and b.raw==raw
 assert init(node,0x368)==1
 expected=bytearray(raw);expected[16+0x340:16+0x368]=bytes(40)
 assert b.raw==expected
 p=offset(good);C.memset(node+p,0,20)
 assert add(node,good,13,-7)==1
 assert C.string_at(node+p,8)==struct.pack('<ii',13,-7)
 assert C.string_at(node+p+12,2)==b'\x01\0'
 assert b.raw[:16]==raw[:16] and b.raw[-16:]==raw[-16:]
 checks['append_and_canary_cases']+=1
assert offset(23)==C.c_size_t(-1).value and offset(56)==C.c_size_t(-1).value
empty=buf(bytes(0x368));assert add(empty,23,1,1)==0
# Overflow rejection is atomic and intentionally stricter than native wrapping.
for sx,sy,count,x,y in [(2**31-1,0,1,1,0),(0,-2**31,1,0,-1),(0,0,65535,1,1)]:
 raw=bytearray(0x368);struct.pack_into('<ii',raw,0x340,sx,sy);struct.pack_into('<H',raw,0x34c,count)
 b=buf(raw);assert add(b,24,x,y)==0 and b.raw==raw

for name,(sha,writer,writer_end,scan,scan_end,evaluator,evaluator_end) in SOURCES.items():
 m=Module(str(ROOT/name));assert hashlib.sha256(m.data).hexdigest()==sha
 assert m.pe.FILE_HEADER.Machine==0x8664 and m.pe.OPTIONAL_HEADER.Magic==0x20b
 for base in [0x180000000,0x280000000]:
  u=machine(m,base)
  for good in range(26,41):
   raw=bytearray(0x368);p=offset(good)
   struct.pack_into('<ii',raw,p,700,-200);struct.pack_into('<H',raw,p+12,17)
   b=buf(raw);assert add(b,good,43,-29)==1
   u.mem_write(0x32002000,bytes(raw));u.mem_write(0x31008008+0x1f8,struct.pack('<h',43));u.mem_write(0x31008008+0x210,struct.pack('<h',-29))
   u.reg_write(UC_X86_REG_R12,0x32002000);u.reg_write(UC_X86_REG_R14,good);u.reg_write(UC_X86_REG_RDI,good)
   u.emu_start(base+writer,base+writer_end,count=100)
   assert bytes(u.mem_read(0x32002000,0x368))==b.raw,(name,good,'writer')
   checks['native_writer_comparisons']+=1
  # Compare original old-consumer scan, including ties and linked-node order.
  for fixture in range(8):
   a=bytearray(0x368);braw=bytearray(0x368);struct.pack_into('<Q',a,0,0x32003000)
   for row in [a,braw]:
    for good in range(26,41):
     p=offset(good);count=rng.randrange(0,4);struct.pack_into('<ii',row,p,count*11,count*-3);struct.pack_into('<H',row,p+12,count)
   u.mem_write(0x32002000,bytes(a));u.mem_write(0x32003000,bytes(braw))
   for reg in [UC_X86_REG_RAX,UC_X86_REG_RSI,UC_X86_REG_R11,UC_X86_REG_R12]:u.reg_write(reg,0)
   u.reg_write(UC_X86_REG_R10,0x32002000)
   u.emu_start(base+scan,base+scan_end,count=3000)
   localb=buf(braw);struct.pack_into('<Q',a,0,C.addressof(localb));locala=buf(a);choice=Choice()
   assert select(locala,2,C.byref(choice))==1
   assert choice.good==u.reg_read(UC_X86_REG_RBX)&65535 and choice.count==u.reg_read(UC_X86_REG_RAX)&65535
   expected_node=0x32002000 if choice.node==C.addressof(locala) else 0x32003000
   assert u.reg_read(UC_X86_REG_RDI)==expected_node
   checks['native_selection_comparisons']+=1
  # Native demand body with tiny private stand-ins for the two city getters
  # and population counts. Native float constants and all arithmetic execute.
  for highest in range(5):
   profiles=bytearray(5*0x120);counts=[0,23,65,131,400]
   for level in range(5):
    for index,good in enumerate(goods,1):
     profiles[level*0x120+good+3]=index
     struct.pack_into('<H',profiles,level*0x120+0x66+index*4,(index*7+level*3)%137)
   u.mem_write(0x32004000,bytes(profiles));u.mem_write(0x32002000,bytes(15*0x5c))
   for ordinal in range(15):u.mem_write(0x32002000+ordinal*0x5c+0x34,b'\x08')
   city=bytearray(0x400);struct.pack_into('<QQ',city,0,0x32009000,0x3200a000)
   for good in goods:struct.pack_into('<i',city,0x200+good*4,good*257)
   u.mem_write(0x32008000,bytes(city));vtable=bytearray(0x108)
   struct.pack_into('<Q',vtable,0xc0,0x33000100);struct.pack_into('<Q',vtable,0x100,0x33000120)
   u.mem_write(0x32009000,bytes(vtable));countobj=struct.pack('<Q5i',0x3200b000,*counts)
   u.mem_write(0x3200a000,countobj);u.mem_write(0x3200b000,struct.pack('<Q',0x33000140))
   u.mem_write(0x33000100,bytes.fromhex('488b4108c3'))
   u.mem_write(0x33000120,bytes.fromhex('8b849100020000c3'))
   u.mem_write(0x33000140,bytes.fromhex('8b449108c3'))
   u.reg_write(UC_X86_REG_RAX,0x32004000);u.reg_write(UC_X86_REG_RBP,0x32002000-0x97c)
   u.reg_write(UC_X86_REG_R13,0x32008000);u.reg_write(UC_X86_REG_RSI,highest)
   u.reg_write(UC_X86_REG_RSP,0x31008008)
   u.emu_start(base+evaluator,base+evaluator_end,count=20000)
   pbuf=buf(profiles);cbuf=(i32*5)(*counts)
   for ordinal,good in enumerate(range(26,41)):
    result=Demand();assert demand(pbuf,cbuf,highest,good,good*257,C.byref(result))==1
    native=bytes(u.mem_read(0x32002000+ordinal*0x5c,16))
    assert native[:4]==bytes(result)[:4] and native[8:16]==bytes(result)[4:12],(name,highest,good,'demand',native.hex(),bytes(result).hex())
    checks['native_demand_comparisons']+=1
   for good in [24,25,45]:
    u.mem_write(0x32002000,bytes(0x5c));u.mem_write(0x32002034,b'\x08')
    u.reg_write(UC_X86_REG_RAX,0x32004000);u.reg_write(UC_X86_REG_RBP,0x32002000-0x97c)
    u.reg_write(UC_X86_REG_R13,0x32008000);u.reg_write(UC_X86_REG_RSI,highest)
    u.reg_write(UC_X86_REG_RSP,0x31008008)
    # Run its setup, then substitute only the loop's good ID, which is the
    # precise future18-consumer-loop change. Stop before the next iteration.
    u.ctl_remove_cache(base+evaluator,base+evaluator_end)
    u.emu_start(base+evaluator,base+evaluator+0x30,count=100)
    u.reg_write(UC_X86_REG_R12,good)
    u.ctl_remove_cache(base+evaluator,base+evaluator_end)
    try:u.emu_start(base+evaluator+0x30,base+evaluator+0x108,count=10000)
    except Exception as exc:
     raise AssertionError((name,highest,good,hex(u.reg_read(UC_X86_REG_RIP)),hex(u.reg_read(UC_X86_REG_RBP)),hex(u.reg_read(UC_X86_REG_RAX)),hex(u.reg_read(UC_X86_REG_RDI)),hex(u.reg_read(UC_X86_REG_R15)))) from exc
    result=Demand();assert demand(pbuf,cbuf,highest,good,good*257,C.byref(result))==1
    native=bytes(u.mem_read(0x32002000,16))
    assert native[:4]==bytes(result)[:4] and native[8:16]==bytes(result)[4:12],(name,highest,good,'added demand')
    checks['native_added_food_demand_comparisons']+=1
  # Compare extra24/25 plan removal with the untouched native consumer
  # operation applied to equivalent26/27 fixtures. Every other byte stays put.
  raw=bytearray(0xfd10);native=bytearray(0xfd10)
  for added,old in [(24,26),(25,27)]:
   for candidate in range(3):
    plan=bytearray(0x7c);plan[0x60]=3
    for entry in range(3):
     struct.pack_into('<I',plan,entry*12+4,810 if entry!=1 else 805)
     plan[entry*12+10]=2+candidate
    for row,good in [(raw,added),(native,old)]:
     start=0x23a4+good*0x3e0+candidate*0x7c;row[start:start+0x7c]=plan
  b=buf(raw);assert removeplans(b,0xfd10,810)==1
  u.mem_write(0x32002000,bytes(native));u.reg_write(UC_X86_REG_RDI,0x32002000)
  u.reg_write(UC_X86_REG_RBX,810);u.reg_write(UC_X86_REG_R11,0)
  begin,end=(0x38f3e,0x38fbc) if name=='CompLogic.dll' else (0x376be,0x3773c)
  u.emu_start(base+begin,base+end,count=10000)
  native=bytes(u.mem_read(0x32002000,0xfd10));expected=bytearray(raw)
  for added,old in [(24,26),(25,27)]:
   source=0x23a4+old*0x3e0;target=0x23a4+added*0x3e0
   expected[target:target+0x3e0]=native[source:source+0x3e0]
  assert b.raw==expected,(name,'removal')
  checks['native_removal_comparisons']+=1

# New consumers select safely without touching node headers or candidates.
for good in [24,25,45]:
 raw=bytearray(0x368);writesafe(raw,good,9,-5);b=buf(raw);choice=Choice()
 assert select(b,1,C.byref(choice))==1 and (choice.good,choice.count,choice.x,choice.y)==(good,1,9,-5)
 before=b.raw;assert clear(b,good)==1
 expected=bytearray(before);struct.pack_into('<H',expected,offset(good)+12,0);assert b.raw==expected
# Bounded cycle detection: failure must not mutate output or nodes.
b=buf(bytes(0x368));struct.pack_into('<Q',b,0,C.addressof(b));choice=Choice(None,991,992,993,994)
assert select(b,3,C.byref(choice))==0 and choice.good==991

@Getter
def foodgetter(definition,index):return [26,28,24,40,25,45][index] if index<6 else 0
@Getter
def othergetter(definition,index):return [37,39][index] if index<2 else 0
for getter,typ,expected in [(foodgetter,0xa1,6),(foodgetter,0xa2,2),(othergetter,0xa1,2)]:
 assert warecount(1,typ,getter)==expected
 for good in goods:
  assert covers(1,typ,getter,good)==int(good in [getter(1,n) for n in range(expected)])
  checks['market_cases']+=1
raw=bytearray(0x368)
for good in goods:writesafe(raw,good,7,3)
b=buf(raw);assert clearmarket(b,1,0xa1,foodgetter)==1
for good in goods:assert struct.unpack_from('<H',b.raw,offset(good)+12)[0]==int(good not in [26,28,24,40,25,45])
provider=bytearray(0x300)
for good in range(26,41):struct.pack_into('<I',provider,0xf0+(good-26)*4,1000+good)
pb=buf(provider)
for good in goods:
 assert stand(pb,good,1310)==(1310 if good in [24,25,40,45] else 1000+good)
 assert pb.raw==provider
result=dict(checks=checks,candidate_dll_sha256=hashlib.sha256((out/'AnnoAIFoodCandidate.dll').read_bytes()).hexdigest(),
 native_source_sha256={name:value[0] for name,value in SOURCES.items()},actual_game_runs=0,
 installed_hooks=0,readiness='NOT READY: native hook wiring, persistence and gameplay still require completion')
(HERE/'test_results.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')
print(json.dumps(result,indent=2))
