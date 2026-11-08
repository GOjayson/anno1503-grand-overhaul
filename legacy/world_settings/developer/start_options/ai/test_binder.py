"""Compile integrated dev4 world_ai.c in an independent fixture; no game actions."""
from pathlib import Path
import ctypes as C,hashlib,json,os,struct,subprocess,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];WORK=ROOT/'WorldSettings_Work'
SOURCE=WORK/'anno1503_food_world_dev4/developer/source/engine_resume/ai_food/experiment_runtime'
sys.path.insert(0,str(WORK/'engine_audit'));from audit import Module
native=Module(str(ROOT/'AnnoWelt.dll'))
tracked={n:hashlib.sha256((SOURCE/n).read_bytes()).hexdigest() for n in ['world_ai.c','world_ai.h','world_diplomacy.inc','world_diplomacy.h','stock_ai_profiles.h','special_activity.inc']}
out=HERE/'_build_binder';out.mkdir(exist_ok=True);(out/'tmp').mkdir(exist_ok=True)
text=(SOURCE/'world_ai.c').read_text('utf-8')
assert text.count('void *approved=NULL;')==1
text='static void *wsAttemptFixtureApproved,*wsFixtureReadFault;static int wsFixtureFaultCountdown;\n'+text.replace('void *approved=NULL;','void *approved=wsAttemptFixtureApproved;')
text=text.replace('static int wsAIRead(','static int wsRealAIRead(',1)
wrapper='static int wsAIRead(const void *pointer,void *out,SIZE_T n){if(pointer==wsFixtureReadFault&&n==4&&--wsFixtureFaultCountdown==0)return 0;return wsRealAIRead(pointer,out,n);}\n'
text=text.replace('static void *wsAIPointer(',wrapper+'static void *wsAIPointer(',1)
text+='\nint WorldSettingsIsActive(void){return 0;}\nvoid WorldSettingsFinishAttempt(int success){WorldSettingsAIProfileAttemptFinished(success);}\n'
text+='__declspec(dllexport) void FixtureApprove(void *p){wsAttemptFixtureApproved=p;}\n'
text+='__declspec(dllexport) void FixtureReadFault(void *p,int n){wsFixtureReadFault=p;wsFixtureFaultCountdown=n;}\n'
text+='__declspec(dllexport) void FixtureExpect(int n,unsigned int f,int m){WorldSettingsExpectAIProfiles(n,f,m);}\n'
(out/'binder_fixture.c').write_text(text,'utf-8')
env=dict(os.environ,ZIG_GLOBAL_CACHE_DIR=str(out/'global-cache'),ZIG_LOCAL_CACHE_DIR=str(out/'local-cache'),TEMP=str(out/'tmp'),TMP=str(out/'tmp'))
subprocess.run([str(WORK/'_tools/ziglang/zig.exe'),'cc','-shared','-O2','-Wall','-Wextra','-Werror','-DWS_AI_FIXTURE','-I',str(SOURCE),str(out/'binder_fixture.c'),'-o',str(out/'WorldDiplomacyBinderFixture.dll')],check=True,env=env)
lib=C.CDLL(str(out/'WorldDiplomacyBinderFixture.dll'))
def fn(name,args,ret=C.c_int):f=getattr(lib,name);f.argtypes=args;f.restype=ret;return f
ptr=C.c_void_p;i32=C.c_int32;u32=C.c_uint32
bind=fn('WorldSettingsBindAIDiplomacy',[ptr,i32,i32,ptr,ptr,u32]);expect=fn('FixtureExpect',[i32,u32,i32],None)
begin=fn('WorldSettingsBeginNativeWorldStart',[],u32);end=fn('WorldSettingsEndNativeWorldStart',[u32,C.c_int]);bindworld=fn('WorldSettingsBindAIProfileWorld',[ptr,ptr,u32]);after=fn('WorldSettingsAfterProfiles',[ptr]);status=fn('WorldSettingsAIProfileStatus',[ptr],u32)
approve=fn('FixtureApprove',[ptr],None);worldmod=fn('WorldSettingsAITestWorldModule',[ptr],None);readfault=fn('FixtureReadFault',[ptr,C.c_int],None)
k=C.WinDLL('kernel32',use_last_error=True);k.VirtualAlloc.argtypes=[ptr,C.c_size_t,u32,u32];k.VirtualAlloc.restype=ptr;k.VirtualFree.argtypes=[ptr,C.c_size_t,u32];k.VirtualProtect.argtypes=[ptr,C.c_size_t,u32,C.POINTER(u32)]
owned=[]
def alloc(n,protection=4):
 p=k.VirtualAlloc(None,n,0x3000,protection);assert p;owned.append(p);return p
def put(p,fmt,*v):C.memmove(p,struct.pack(fmt,*v),struct.calcsize(fmt))
def word(p):return struct.unpack('<I',C.string_at(p,4))[0]
w=alloc(0x110000,0x40);a=alloc(0xa0000);err=C.create_string_buffer(512);rows=[]
try:
 worldmod(w);approve(a);put(w+0xfdbc0+0x10,'<Q',w+0xc6d80);put(w+0xfdbc0+0x18,'<Q',w+0x95990)
 C.memmove(w+0xd1910,native.image[0xd1910:0xd1a10],0x100)
 for vt in [0xff1d8,0xff650]:put(w+vt+0xf0,'<Q',w+0xd1910)
 def fixture(count,classic=False,special=False):
  p=alloc(0x40000);table=p+0x1000;scene=p+0x3e000;vt=a+(0x84fc8 if classic else 0x88128)
  put(vt+8,'<Q',a+(0x4260 if classic else 0x6090));put(vt+0x10,'<Q',a+(0x4a10 if classic else 0x6640))
  put(p,'<Q',w+0xff1d8);put(p+0x210,'<Q',table);put(table,'<Q',w+0xfdbc0);put(scene+0x160,'<Q',p);put(p+0x6eec,'<I',0x20)
  cs=[]
  for ident in range(1,4):
   player=p+0x2000+ident*0x100;c=p+0x8000+ident*0x4000;active=ident<=count;cs.append(c)
   put(table+8+ident*8,'<Q',player);put(player,'<Q',w+0xfabe0);put(player+8,'<I',ident);put(player+0x10,'<Q',p);put(player+0x9c,'<H',12);put(player+0x18,'<Q',c)
   put(c,'<Q',vt);put(c+0xa4c,'<I',12);put(c+0xab4,'<I',0 if active else 1);put(c+0xab0,'<I',0 if active else 1);put(c+0x1e9d,'<B',1 if active else 0);put(c+0xab8,'<I',ident*4)
  if special:
   for ident,typ in [(0,11),(5,16),(6,15),(7,13)]:
    player=p+0x2000+ident*0x100;c=p+0x20000+ident*0x2000
    put(table+8+ident*8,'<Q',player);put(player,'<Q',w+0xfabe0);put(player+0x9c,'<H',typ);put(player+0x18,'<Q',c);put(c+0xab8,'<I',0x42)
  return p,scene,cs
 for classic in [False,True]:
  for count in range(4):
   for mode in range(4):
    p,scene,cs=fixture(count,classic,True);old=C.string_at(p,0x40000)
    assert bind(p,count,mode,a,err,len(err))==1 and not err.value
    wanted=bytearray(old)
    for i,c in enumerate(cs):
     if i<count:struct.pack_into('<I',wanted,c+0xab8-p,0x57530000|(mode<<8)|((i+1)*4))
    assert C.string_at(p,0x40000)==wanted # no resumed dormant/special/native controllers
    unchanged=C.string_at(p,0x40000)
    if count:assert bind(p,count,mode,a,err,len(err))==0 and err.value and C.string_at(p,0x40000)==unchanged
    rows.append(dict(case='fresh bind and repeat rejection',classic=classic,count=count,mode=mode,passed=True))
    # Entire integrated expectation/native-start/post-profile sequence.
    p,scene,cs=fixture(count,classic);expect(count,0,mode);token=begin();assert token and bindworld(scene,err,len(err))==1
    assert after(p)==1 and status(None)==count+1 and after(p)==1 and end(token,1)==1
    assert all(word(c+0xab8)==(0x57530000|(mode<<8)|((i+1)*4) if i<count else (i+1)*4) for i,c in enumerate(cs))
    snap=C.string_at(p,0x40000);unarmed=begin();assert after(p)==1 and end(unarmed,1)==1 and C.string_at(p,0x40000)==snap
    rows.append(dict(case='integrated callback and unarmed saved-world path',classic=classic,count=count,mode=mode,passed=True))
 for fault in ['unsupported second flags','third destination read-only','readback failure','count mismatch','invalid mode']:
  p,scene,cs=fixture(3);oldprotect=u32()
  if fault=='unsupported second flags':put(cs[1]+0xab8,'<I',0x100)
  if fault=='third destination read-only':assert k.VirtualProtect(cs[2],0x1000,2,C.byref(oldprotect))
  if fault=='readback failure':readfault(cs[0]+0xab8,2)
  snap=C.string_at(p,0x40000);n=2 if fault=='count mismatch' else 3;mode=4 if fault=='invalid mode' else 0
  assert bind(p,n,mode,a,err,len(err))==0 and err.value and C.string_at(p,0x40000)==snap
  readfault(None,0)
  if fault=='third destination read-only':restore=u32();assert k.VirtualProtect(cs[2],0x1000,oldprotect.value,C.byref(restore))
  rows.append(dict(case=fault,atomic_no_change=True,passed=True))
 # Failure through the actual integrated callback blocks native completion.
 p,scene,cs=fixture(2);put(cs[1]+0xab8,'<I',0x100);snap=C.string_at(p,0x40000)
 expect(2,0,0);token=begin();assert bindworld(scene,err,len(err))==1
 assert after(p)==0 and status(None)==0 and end(token,1)==0 and C.string_at(p,0x40000)==snap
 rows.append(dict(case='integrated bind failure blocks completion',atomic_no_change=True,passed=True))
finally:
 worldmod(None);approve(None)
 for p in owned:k.VirtualFree(p,0,0x8000)
assert all(hashlib.sha256((SOURCE/n).read_bytes()).hexdigest()==v for n,v in tracked.items()),'Integration source changed during test; rerun required'
result=dict(scope=__doc__,cases=rows,source_sha256=tracked,fixture_sha256=hashlib.sha256((out/'WorldDiplomacyBinderFixture.dll').read_bytes()).hexdigest(),actual_game_runs=0,passed=True)
(HERE/'binder_test_results.json').write_text(json.dumps(result,indent=2)+'\n','utf-8');print(json.dumps(dict(passed=True,cases=len(rows),actual_game_runs=0),indent=2))
