"""Compiled pirate initialization policy with original native transfer methods.

No game process is started. Original native owner/list/refcount/mask routines
run in private PE images. Allocation, memcpy/memset, World cache update and
AI message delivery are explicit test boundaries. Placeholder policy values
are supplied by fixtures, not claimed as an observation from an actual game.
"""
from pathlib import Path
import ctypes as C,hashlib,json,struct,sys
from ctypes import wintypes as WT
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[2];ROOT=WORK.parent
sys.path[:0]=[str(WORK/'_tools'),str(WORK/'engine_audit')]
from audit import Module
class Settings(C.Structure):_fields_=[('size',C.c_uint32),('difficulty',C.c_int32),('islandSize',C.c_int32),('islandCount',C.c_int32),('spacing',C.c_int32),('aiCount',C.c_int32),('cultures',C.c_uint32),('factions',C.c_uint32)]
class Island(C.Structure):_fields_=[(n,C.c_uint32) for n in ['id','x','y','width','height','templateIndex','cropMask','mineralMask','cultures','climate']]
lib=C.CDLL(str(HERE/'TransferFixture.dll'));lib.TransferFixtureModules.argtypes=[C.c_void_p,C.c_void_p,C.c_void_p];lib.TransferFixtureFinalize.argtypes=[C.c_void_p,C.c_uint32,C.c_uint32,C.c_void_p,C.c_uint32];lib.WorldSettingsBuildPlan.argtypes=[C.POINTER(Settings),C.c_uint32,C.c_void_p,C.c_uint32];lib.WorldSettingsPlanIsland.argtypes=[C.c_uint32,C.POINTER(Island)]
k=C.WinDLL('kernel32',use_last_error=True);k.VirtualAlloc.argtypes=[C.c_void_p,C.c_size_t,WT.DWORD,WT.DWORD];k.VirtualAlloc.restype=C.c_void_p;k.VirtualFree.argtypes=[C.c_void_p,C.c_size_t,WT.DWORD];k.FlushInstructionCache.argtypes=[C.c_void_p,C.c_void_p,C.c_size_t];k.GetCurrentProcess.restype=C.c_void_p
modules=[];buffers=[];events=[];errors=[];allocations=[]
def buf(n):b=C.create_string_buffer(n);buffers.append(b);return C.addressof(b)
def put(at,fmt,*v):C.memmove(at,struct.pack('<'+fmt,*v),struct.calcsize('<'+fmt))
def get(at,fmt):return struct.unpack('<'+fmt,C.string_at(at,struct.calcsize('<'+fmt)))[0]
def image(name):
 m=Module(str(ROOT/name));size=(m.pe.OPTIONAL_HEADER.SizeOfImage+4095)&~4095;base=k.VirtualAlloc(None,size,0x3000,0x40);assert base;m.pe.relocate_image(base);data=bytes(m.pe.get_memory_mapped_image());C.memmove(base,data,len(data));modules.append(base);return base,m
w,wm=image('AnnoWelt.dll');g,gm=image('AnnoGame.dll');a,am=image('CompLogic.dll');lib.TransferFixtureModules(w,g,a)
CALL=C.CFUNCTYPE(C.c_size_t,C.c_void_p,C.c_size_t,C.c_size_t,C.c_size_t)
@CALL
def allocate(n,b,c,d):
 try:
  assert n==24,n;target=buf(n);events.append('allocate-node');allocations.append(target);return target
 except Exception as e:errors.append(repr(e));return 0
@CALL
def clear(target,value,n,d):
 try:assert n<=4096;C.memset(target,value&255,n);return target
 except Exception as e:errors.append(repr(e));return 0
@CALL
def cache(world,city,owner,d):events.append(('world-city-cache',city,owner));return 0
@CALL
def notification(controller,message,c,d):
 try:events.append(('ai-event',get(message,'H'),controller));return 1
 except Exception as e:errors.append(repr(e));return 0
def patch(base,rva,callback):
 code=b'\x48\xb8'+struct.pack('<Q',C.cast(callback,C.c_void_p).value)+b'\xff\xe0';C.memmove(base+rva,code,len(code));assert k.FlushInstructionCache(k.GetCurrentProcess(),base+rva,len(code))
patch(w,0xe46bc,allocate);patch(w,0xe58ea,clear);patch(w,get(w+0xff650+0x1d8,'Q')-w,cache);patch(a,0x7050,notification)
cat=json.loads((HERE.parent/'candidate_sources.json').read_text());pirateTemplates={p['index'] for p in cat['pirate_templates']};err=C.create_string_buffer(512);rows=[]
def obj(n,vt,base=w):p=buf(n);put(p,'Q',base+vt);return p
def fixture(cityCount=1,oldType=2,oldCulture=11):
 events.clear();allocations.clear();errors.clear()
 settings=Settings(32,1,0,12,16,0,0,1);assert lib.WorldSettingsBuildPlan(C.byref(settings),913,err,len(err)),err.value
 plans=[]
 for i in range(lib.WorldSettingsPlanCount()):p=Island();assert lib.WorldSettingsPlanIsland(i,C.byref(p));plans.append(p)
 selected=[p for p in plans if p.templateIndex in pirateTemplates];assert len(selected)==1;p=selected[0]
 world=obj(0x7000,0xff650);table=obj(0x598,0xfdbc0);put(world+0x210,'Q',table)
 island=obj(0x158,0xf33e8);put(island+8,'HHHH',p.x,p.y,p.width,p.height);put(island+0x10,'I',p.id);put(island+0x38,'Q',world);put(world+0x6640+p.id*8,'Q',island)
 old=obj(0x570,0xfabe0);pirate=obj(0x570,0xfabe0)
 for player,id,kind,culture in [(old,31,oldType,oldCulture),(pirate,6,15,11)]:
  put(player+8,'I',id);put(player+0x10,'Q',world);put(player+0x9c,'HH',kind,culture);put(table+8+id*8,'Q',player)
 controller=obj(0x21b0,0x88ba8,a);put(controller+0xa4c,'I',15);put(pirate+0x18,'Q',controller)
 vector=buf(4*8);put(pirate+0x2f8,'QQQ',vector,vector+32,vector+32)
 cities=[];nodes=[]
 for i in range(cityCount):
  city=obj(0x3260,0xfc678);put(city+8,'I',i+3);put(city+0x1b,'B',5);put(city+0x20,'Q',island);put(city+0x28,'Q',old);put(city+0x470,'Q',old);put(city+0x760,'I',1<<31);put(island+0x68+i*8,'Q',city);cities.append(city)
  node=buf(24);put(node+0x10,'Q',city);nodes.append(node)
 for i,node in enumerate(nodes):put(node,'QQ',nodes[i-1] if i else 0,nodes[i+1] if i+1<len(nodes) else 0)
 put(old+0x318,'QQ',nodes[0],nodes[-1]);scene=buf(0x168);put(scene+0x160,'Q',world)
 return dict(scene=scene,world=world,table=table,island=island,old=old,pirate=pirate,controller=controller,cities=cities,nodes=nodes,settings=settings)
def finalize(f,type=2,culture=11):return lib.TransferFixtureFinalize(f['scene'],type,culture,err,len(err))
def recorded(name,f,expected,type=2,culture=11):
 before=[C.string_at(v,size) for v,size in [(f['world'],0x7000),(f['old'],0x570),(f['pirate'],0x570),(f['island'],0x158),*[(c,0x3260) for c in f['cities']]]]
 actual=finalize(f,type,culture);assert actual==expected,(name,actual,err.value);assert not errors,errors
 if not expected:
  after=[C.string_at(v,size) for v,size in [(f['world'],0x7000),(f['old'],0x570),(f['pirate'],0x570),(f['island'],0x158),*[(c,0x3260) for c in f['cities']]]];assert before==after and not events,(name,'failed preflight mutated native objects')
 rows.append(dict(case=name,accepted=bool(actual),error=err.value.decode() if not actual else '',native_write_boundaries=len(events)))
for n in [1,2]:
 f=fixture(n);recorded('native transfer '+str(n)+' cities',f,1)
 assert len(allocations)==n and len([e for e in events if isinstance(e,tuple) and e[0]=='ai-event'])==n
 for city in f['cities']:assert get(city+0x28,'Q')==get(city+0x470,'Q')==f['pirate'] and get(city+0x760,'I')==1<<6 and get(city+0x1b,'B')==5
 assert not get(f['old']+0x318,'Q') and not get(f['old']+0x320,'Q')
 events.clear();recorded('idempotent verified native ownership '+str(n),f,1);assert not events
for name,change,expectedType,expectedCulture in [
 ('wrong placeholder type',lambda f:None,11,11),('wrong placeholder culture',lambda f:None,2,1),
 ('missing native pirate controller',lambda f:put(f['pirate']+0x18,'Q',0),2,11),
 ('wrong pirate controller class',lambda f:put(f['controller'],'Q',a+0x88128),2,11),
 ('wrong controller native type',lambda f:put(f['controller']+0xa4c,'I',12),2,11),
 ('wrong island geometry',lambda f:put(f['island']+8,'H',999),2,11),
 ('city belongs to different island',lambda f:put(f['cities'][0]+0x20,'Q',0),2,11),
 ('city missing from native owner list',lambda f:put(f['old']+0x318,'Q',0),2,11),
 ('broken previous membership link',lambda f:put(f['nodes'][0],'Q',1),2,11),
 ('duplicate native city slots',lambda f:put(f['island']+0x70,'Q',f['cities'][0]),2,11),
 ('owner is absent from native table',lambda f:put(f['table']+8+31*8,'Q',0),2,11),
 ('city reference count at zero',lambda f:put(f['cities'][0]+0x1b,'B',0),2,11),
 ('false already-owned pointer without membership',lambda f:put(f['cities'][0]+0x28,'Q',f['pirate']),2,11),
 ('last city malformed prevents first city writes',lambda f:put(f['cities'][-1]+0x28,'Q',0),2,11)]:
 f=fixture(2 if name.startswith('last') else 1);change(f);recorded(name,f,0,expectedType,expectedCulture)
f=fixture();previous=get(w+0xfabe0+0x130,'Q');put(w+0xfabe0+0x130,'Q',w+0x9ad00)
try:recorded('unreviewed native remove method',f,0)
finally:put(w+0xfabe0+0x130,'Q',previous)
result=dict(scope=__doc__,dll_sha256=hashlib.sha256((HERE/'TransferFixture.dll').read_bytes()).hexdigest(),policy_values_are_synthetic=True,cases=rows,original_native_source_sha256={'AnnoWelt.dll':hashlib.sha256((ROOT/'AnnoWelt.dll').read_bytes()).hexdigest(),'AnnoGame.dll':hashlib.sha256((ROOT/'AnnoGame.dll').read_bytes()).hexdigest(),'CompLogic.dll':hashlib.sha256((ROOT/'CompLogic.dll').read_bytes()).hexdigest()},game_runs=0)
(HERE/'fixture_results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'cases':len(rows),'native_transfer_cases':2,'policy_values_synthetic':True,'game_runs':0}))
for module in modules:assert k.VirtualFree(module,0,0x8000)
