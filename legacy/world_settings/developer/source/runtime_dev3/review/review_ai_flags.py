"""Independent CPU certificate flag matrix, using synthetic native-shaped data.

Loads only the already compiled private profile fixture DLL into this Python
process. No game attachment or game execution occurs. Native scheduler paths
are executed in private Unicorn memory against an explicit dispatch double.
"""
from pathlib import Path
import ctypes as C,hashlib,itertools,json,struct,sys
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[1];ROOT=WORK.parent
sys.path[:0]=[str(WORK/'_tools'),str(WORK/'engine_audit')]
from audit import Module
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *
path=WORK/'engine_resume/ai_food/experiment_runtime/_build/WorldAIProfiles.dll';lib=C.CDLL(str(path))
check=lib.WorldSettingsCheckAIControllers;check.argtypes=[C.c_void_p,C.c_int32,C.c_void_p,C.c_void_p,C.c_uint32]
testmodule=lib.WorldSettingsAITestWorldModule;testmodule.argtypes=[C.c_void_p]
k=C.WinDLL('kernel32',use_last_error=True);k.VirtualAlloc.argtypes=[C.c_void_p,C.c_size_t,C.c_uint32,C.c_uint32];k.VirtualAlloc.restype=C.c_void_p;k.VirtualFree.argtypes=[C.c_void_p,C.c_size_t,C.c_uint32]
def put(at,fmt,*values):C.memmove(at,struct.pack('<'+fmt,*values),struct.calcsize('<'+fmt))
worldmodule=k.VirtualAlloc(None,0x110000,0x3000,4);ai=k.VirtualAlloc(None,0xa0000,0x3000,4);assert worldmodule and ai
results=[];err=C.create_string_buffer(512)
try:
 testmodule(worldmodule);put(worldmodule+0xfdbc0+0x10,'Q',worldmodule+0xc6d80);put(worldmodule+0xfdbc0+0x18,'Q',worldmodule+0x95990)
 for classic in [False,True]:
  vt=ai+(0x84fc8 if classic else 0x88128);put(vt+8,'Q',ai+(0x4260 if classic else 0x6090));put(vt+0x10,'Q',ai+(0x4a10 if classic else 0x6640))
  for disabled,suspend,thinking in itertools.product(range(2),repeat=3):
   storage=C.create_string_buffer(0x20000);root=C.addressof(storage);table=root+0x1000
   put(root,'Q',worldmodule+0xff650);put(root+0x210,'Q',table);put(table,'Q',worldmodule+0xfdbc0)
   for id in range(1,4):
    player=root+0x2000+id*0x100;controller=root+0x3000+id*0x2400;put(table+8+id*8,'Q',player);put(player,'Q',worldmodule+0xfabe0);put(player+0x9c,'H',12);put(player+0x18,'Q',controller);put(controller,'Q',vt);put(controller+0xa4c,'I',12)
    put(controller+0xab0,'I',disabled if id==1 else 1);put(controller+0xab4,'I',suspend if id==1 else 1);put(controller+0x1e9d,'B',thinking if id==1 else 0)
   before=bytes(storage);accepted=check(root,0,ai,err,len(err));assert bytes(storage)==before
   expected=int(suspend==1 and thinking==0)
   results.append(dict(classic=classic,disabled=disabled,suspend=suspend,thinking=thinking,accepted_for_zero_ai=bool(accepted),expected_accept=bool(expected),safe=accepted==expected,error=err.value.decode()))
finally:testmodule(None);k.VirtualFree(worldmodule,0,0x8000);k.VirtualFree(ai,0,0x8000)
m=Module(str(ROOT/'CompLogic.dll'));assert hashlib.sha256(m.data).hexdigest()=='7f2c7e818d8c25a0b6c48cda2d21bfa0c4096c5dcd8be91c2ab93d877c22afee'
dispatch=[]
for base,thinking,disabled in itertools.product([0x180000000,0x280000000],range(2),range(2)):
 u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,(len(m.image)+4095)&~4095);u.mem_write(base,m.image);u.mem_map(0x31000000,0x10000);u.mem_map(0x32000000,0x10000)
 cpu=0x32002000;u.mem_write(cpu+0x1e9d,bytes([thinking]));u.mem_write(cpu+0xab0,struct.pack('<I',disabled));u.reg_write(UC_X86_REG_RSP,0x31008000);u.reg_write(UC_X86_REG_RBX,cpu);u.reg_write(UC_X86_REG_RSI,100);u.reg_write(UC_X86_REG_RDI,1);u.reg_write(UC_X86_REG_R14,55);calls=[]
 def boundary(machine,address,size,user):
  calls.append(address);rsp=machine.reg_read(UC_X86_REG_RSP);target=struct.unpack('<Q',machine.mem_read(rsp,8))[0];machine.reg_write(UC_X86_REG_RAX,0);machine.reg_write(UC_X86_REG_RSP,rsp+8);machine.reg_write(UC_X86_REG_RIP,target)
 u.hook_add(UC_HOOK_CODE,boundary,begin=base+0x5080,end=base+0x5080);u.emu_start(base+0x59165,base+0x59182,count=100);assert len(calls)==thinking
 dispatch.append(dict(base=hex(base),thinking=thinking,disabled=disabled,thinking_dispatch_calls=len(calls)))
runtime=WORK/'runtime_dev3';build=json.loads((runtime/'build_result.json').read_text());fullSHA=hashlib.sha256((runtime/'AnnoWorldSettings.dll').read_bytes()).hexdigest();assert fullSHA==build['sha256']
source=WORK/'engine_resume/ai_food/experiment_runtime/world_ai.c';sourceSHA=hashlib.sha256(source.read_bytes()).hexdigest();assert build['source_sha256'][str(source.relative_to(WORK))]==sourceSHA
result=dict(scope=__doc__,fixture_dll_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),full_runtime_sha256=fullSHA,full_runtime_world_ai_source_sha256=sourceSHA,certificate_cases=results,incorrect_acceptances=[r for r in results if not r['safe']],native_dispatch_cases=dispatch,actual_game_runs=0)
(HERE/'ai_flag_review_results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'certificate_cases':len(results),'incorrect_acceptances':result['incorrect_acceptances'],'native_dispatch_cases':len(dispatch),'actual_game_runs':0},indent=2))
