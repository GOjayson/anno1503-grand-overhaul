"""Compiled current attempt-lifetime replay after native faction activity checks; no game process or UI."""
from pathlib import Path
import ctypes as C,hashlib,json,os,struct,subprocess,sys
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[2];SOURCE=HERE
current={str(p.relative_to(WORK)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [SOURCE/'world_ai.c',SOURCE/'world_ai.h',SOURCE/'special_activity.inc',WORK/'world_factory.c']}
sys.path.insert(0,str(WORK/'engine_audit'))
from audit import Module
nativeWorld=Module(str(WORK.parent/'AnnoWelt.dll'))
assert hashlib.sha256(nativeWorld.data).hexdigest()=='ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9'
out=HERE/'_build';out.mkdir(exist_ok=True);(out/'tmp').mkdir(exist_ok=True)
adopted=True
text=(SOURCE/'world_ai.c').read_text('utf-8');assert text.count('void *approved=NULL;')==1
text='static void *wsAttemptFixtureApproved;\n'+text.replace('void *approved=NULL;','void *approved=wsAttemptFixtureApproved;')
text+='\n__declspec(dllexport) void FixtureExpect(int n){WorldSettingsExpectAIProfiles(n,0);}\n'
text+='__declspec(dllexport) void FixtureFinish(int n){WorldSettingsAIProfileAttemptFinished(n);}\n'
text+='__declspec(dllexport) void FixtureApprove(void *p){wsAttemptFixtureApproved=p;}\n'
text+='static int fixturePending,fixtureCleanups;\nint WorldSettingsIsActive(void){return fixturePending;}\nvoid WorldSettingsFinishAttempt(int success){fixturePending=0;fixtureCleanups++;WorldSettingsAIProfileAttemptFinished(success);}\n'
text+='__declspec(dllexport) void FixturePending(int n){fixturePending=n;fixtureCleanups=0;}\n__declspec(dllexport) int FixtureCleanups(void){return fixtureCleanups;}\n'
(out/'lifetime_current_fixture.c').write_text(text,'utf-8')
env=dict(os.environ,ZIG_GLOBAL_CACHE_DIR=str(out/'global-cache'),ZIG_LOCAL_CACHE_DIR=str(out/'local-cache'),TEMP=str(out/'tmp'),TMP=str(out/'tmp'))
subprocess.run([str(WORK/'_tools/ziglang/zig.exe'),'cc','-shared','-O2','-Wall','-Wextra','-Werror','-DWS_AI_FIXTURE','-I',str(SOURCE),str(out/'lifetime_current_fixture.c'),'-o',str(out/'AttemptLifetimeCurrentFixture.dll')],check=True,env=env)
lib=C.CDLL(str(out/'AttemptLifetimeCurrentFixture.dll'))
def fn(name,args,ret=C.c_int):f=getattr(lib,name);f.argtypes=args;f.restype=ret;return f
status=fn('WorldSettingsAIProfileStatus',[C.c_void_p],C.c_uint32)
begin=fn('WorldSettingsBeginNativeWorldStart',[],C.c_uint32)
end=fn('WorldSettingsEndNativeWorldStart',[C.c_uint32,C.c_int])
bind=fn('WorldSettingsBindAIProfileWorld',[C.c_void_p,C.c_void_p,C.c_uint32])
after=fn('WorldSettingsAfterProfiles',[C.c_void_p])
expect=fn('FixtureExpect',[C.c_int32]);finish=fn('FixtureFinish',[C.c_int32]);approve=fn('FixtureApprove',[C.c_void_p]);worldmod=fn('WorldSettingsAITestWorldModule',[C.c_void_p])
pending=fn('FixturePending',[C.c_int]);cleanups=fn('FixtureCleanups',[])
k=C.WinDLL('kernel32',use_last_error=True);k.VirtualAlloc.argtypes=[C.c_void_p,C.c_size_t,C.c_uint32,C.c_uint32];k.VirtualAlloc.restype=C.c_void_p;k.VirtualFree.argtypes=[C.c_void_p,C.c_size_t,C.c_uint32]
w=k.VirtualAlloc(None,0x110000,0x3000,0x40);a=k.VirtualAlloc(None,0xa0000,0x3000,4);assert w and a
rows=[];err=C.create_string_buffer(512);owned=[]
try:
 worldmod(w);approve(a)
 def put(address,fmt,*values):C.memmove(address,struct.pack(fmt,*values),struct.calcsize(fmt))
 put(w+0xfdbc0+0x10,'<Q',w+0xc6d80);put(w+0xfdbc0+0x18,'<Q',w+0x95990)
 C.memmove(w+0xd1910,nativeWorld.image[0xd1910:0xd1a10],0x100)
 for vt in [0xff1d8,0xff650]:put(w+vt+0xf0,'<Q',w+0xd1910)
 def fixture(count,classic=False):
  b=C.create_string_buffer(0x20000);owned.append(b);p=C.addressof(b);world=p;table=p+0x1000;scene=p+0x1f000
  vt=a+(0x84fc8 if classic else 0x88128);put(vt+8,'<Q',a+(0x4260 if classic else 0x6090));put(vt+0x10,'<Q',a+(0x4a10 if classic else 0x6640))
  put(world,'<Q',w+0xff1d8);put(world+0x210,'<Q',table);put(table,'<Q',w+0xfdbc0);put(scene+0x160,'<Q',world)
  put(world+0x6e48,'<B',0);put(world+0x6eec,'<I',0x20)
  for i in range(1,4):
   player=p+0x2000+i*0x100;controller=p+0x3000+i*0x2200;active=i<=count
   put(table+8+i*8,'<Q',player);put(player,'<Q',w+0xfabe0);put(player+0x9c,'<H',12);put(player+0x18,'<Q',controller)
   put(player+8,'<I',i);put(player+0x10,'<Q',world)
   put(controller,'<Q',vt);put(controller+0xa4c,'<I',12);put(controller+0xab4,'<I',0 if active else 1);put(controller+0xab0,'<I',0 if active else 1);put(controller+0x1e9d,'<B',1 if active else 0)
  return world,scene
 assert status(None)==0 and after(None)==1 and status(None)==0
 for classic in [False,True]:
  for count in range(4):
   world,scene=fixture(count,classic);other,other_scene=fixture(count,classic)
   expect(count);token=begin();assert token and bind(scene,err,len(err))==1
   assert after(world)==1 and status(None)==count+1 and end(token,1)==1 and status(None)==count+1
   unrelated=begin();assert unrelated and unrelated!=token and status(None)==0
   assert after(other)==1 and end(unrelated,1)==1 and status(None)==0
   rows.append(dict(case='generated then unrelated load',classic=classic,count=count,passed=True))
   expect(count);token=begin();assert bind(scene,err,len(err))==1;finish(1)
   assert end(token,0)==0 and status(None)==0
   # Reuse exactly the old pointer: the native-attempt boundary still disarmed it.
   unrelated=begin();assert after(world)==1 and end(unrelated,1)==1 and status(None)==0
   rows.append(dict(case='early native failure then same-address unrelated load',classic=classic,count=count,passed=True))
   expect(count);token=begin();assert bind(scene,err,len(err))==1
   assert after(other)==0 and status(None)==0 and end(token,0)==0
   rows.append(dict(case='different world rejected',classic=classic,count=count,passed=True))
   expect(count);token=begin();assert bind(scene,err,len(err))==1
   assert end(token,1)==0 and status(None)==0
   rows.append(dict(case='generated native success without callback rejected',classic=classic,count=count,passed=True))
   expect(count);token=begin();assert bind(None,err,len(err))==0;finish(0)
   assert end(token,0)==0 and status(None)==0
   rows.append(dict(case='factory failure disarms attempt',classic=classic,count=count,passed=True))
   expect(count);token=begin();assert bind(scene,err,len(err))==1
   assert bind(other_scene,err,len(err))==0
   assert after(world)==1 and status(None)==count+1 and end(token,0)==0 and status(None)==0
   rows.append(dict(case='duplicate bind rejected and late native failure clears status',classic=classic,count=count,passed=True))
   expect(count);new=begin();assert new and not begin() and bind(scene,err,len(err))==1
   assert after(world)==1 and status(None)==count+1
   assert end(token,1)==0 and status(None)==count+1
   assert end(new,1)==1 and status(None)==count+1
   rows.append(dict(case='stale completion and reentry do not consume current token',classic=classic,count=count,passed=True))
   tutorial=begin();assert status(None)==0 and end(tutorial,1)==1 and status(None)==0
   failed_load=begin();assert end(failed_load,0)==0 and status(None)==0
   rows.append(dict(case='unarmed native success and failure preserved',classic=classic,count=count,passed=True))
   expect(count);token=begin();pending(1)
   assert end(token,0)==0 and cleanups()==1 and status(None)==0
   rows.append(dict(case='early failure before factory cleans staged pending world',classic=classic,count=count,passed=True))
finally:
 approve(None);worldmod(None);k.VirtualFree(w,0,0x8000);k.VirtualFree(a,0,0x8000)
for name,digest in current.items():assert hashlib.sha256((WORK/name).read_bytes()).hexdigest()==digest
report=dict(scope=__doc__,actual_game_runs=0,compiled_sources_unchanged_during_test=True,adopted_source_tested=adopted,current_source_sha256=current,native_getter_source_sha256=hashlib.sha256(nativeWorld.data).hexdigest(),fixture_sha256=hashlib.sha256((out/'AttemptLifetimeCurrentFixture.dll').read_bytes()).hexdigest(),cases=rows)
(HERE/'current_lifecycle_results.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
print(json.dumps(dict(lifecycle_cases=len(rows),actual_game_runs=0,compiled_sources_changed=False)))
