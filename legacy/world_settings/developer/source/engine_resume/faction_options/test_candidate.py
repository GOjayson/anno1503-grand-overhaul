"""Actual Windows fixture DLL tests of faction planning, scene bytes and owners.

All worlds/nodes are synthetic buffers. Native property getters run in private
mapped PE images. This is not a game run or proof of trader/pirate simulation.
"""
from pathlib import Path
import ctypes as C,hashlib,itertools,json,struct,sys
from ctypes import wintypes as WT
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[1];ROOT=WORK.parent
sys.path.insert(0,str(WORK/'world_data'));sys.path.insert(0,str(WORK/'engine_audit'))
from scene_catalogue import chunks,read_container,geometry_errors
from audit import Module
class Settings(C.Structure):_fields_=[('size',C.c_uint32),('difficulty',C.c_int32),('islandSize',C.c_int32),('islandCount',C.c_int32),('spacing',C.c_int32),('aiCount',C.c_int32),('cultures',C.c_uint32),('factions',C.c_uint32)]
class Island(C.Structure):_fields_=[(n,C.c_uint32) for n in ['id','x','y','width','height','templateIndex','cropMask','mineralMask','cultures','climate']]
lib=C.CDLL(str(HERE/'FactionFixture.dll'));err=C.create_string_buffer(512)
lib.WorldSettingsBuildPlan.argtypes=[C.POINTER(Settings),C.c_uint32,C.c_void_p,C.c_uint32]
lib.WorldSettingsPlanIsland.argtypes=[C.c_uint32,C.POINTER(Island)]
lib.FactionFixtureScene.argtypes=[C.POINTER(Settings),C.c_void_p,C.c_uint32,C.c_void_p,C.c_uint32]
lib.FactionFixtureSpecialMap.argtypes=[C.c_void_p,C.c_uint32,C.c_void_p,C.c_void_p,C.c_uint32]
lib.FactionFixtureModules.argtypes=[C.c_void_p,C.c_void_p]
lib.FactionFixturePlayers.argtypes=[C.c_void_p,C.c_uint32,C.c_void_p,C.c_uint32]
lib.FactionFixturePreparedRoot.argtypes=[C.c_char_p]
lib.WorldSettingsPrepareScene.argtypes=[C.c_void_p,C.c_void_p]
cat=json.loads((WORK/'world_data/catalogue.json').read_text());candidate=json.loads((HERE/'candidate_sources.json').read_text());pirateIds={p['index'] for p in candidate['pirate_templates']}
def plan(s,seed=913):
 assert lib.WorldSettingsBuildPlan(C.byref(s),seed,err,len(err)),err.value
 out=[]
 for i in range(lib.WorldSettingsPlanCount()):
  p=Island();assert lib.WorldSettingsPlanIsland(i,C.byref(p));out.append(p)
 assert len(out)==s.islandCount
 assert not geometry_errors([{n:getattr(p,n) for n,_ in p._fields_} for p in out],1024,1024,s.spacing)
 actual=[p for p in out if p.templateIndex in pirateIds]
 assert len(actual)==bool(s.factions&1)
 for p in actual:
  assert p.cultures==0 and p.climate==2
  if s.islandSize<3:assert p.width==[64,128,256][s.islandSize]
 return out
count=0
for size,mask,factions in itertools.product(range(4),[0,1,85,170,254,255],range(4)):
 s=Settings(32,1,size,12 if size==2 else 24,16,0,mask,factions);p=plan(s);count+=1
 old=[bytes(x) for x in p]
 s.factions^=2;assert [bytes(x) for x in plan(s)]==old
 for difficulty in [0,2]:s.difficulty=difficulty;assert [bytes(x) for x in plan(s)]==old
results=dict(scope=__doc__,dll_sha256=hashlib.sha256((HERE/'FactionFixture.dll').read_bytes()).hexdigest(),planner_faction_size_culture_cases=count,venetians_do_not_change_layout_cases=count,difficulty_independent_comparisons=count*2,pirate_template_count=len(pirateIds),game_runs=0)
sources=['01_1024_easy_256.sze','03_1024_med_256.sze','06_1024_heavy_256.sze']
sceneCases=[]
for difficulty,factions in itertools.product(range(3),range(4)):
 s=Settings(32,difficulty,0,24,16,0,255,factions);plan(s)
 out=C.create_string_buffer(262144);n=lib.FactionFixtureScene(C.byref(s),out,len(out),err,len(err));assert n,err.value
 b=out.raw[:n];r,t=read_container(b);assert not t and r.end==len(b)
 parts=list(chunks(b,32,len(b)));original=(ROOT/'Languages/Nl/Scenes/0010SingleEndlos'/sources[difficulty]).read_bytes();old=list(chunks(original,32,len(original)))
 bas={};state={}
 for c in parts:
  if c.tag!='SPIELER':continue
  pid=struct.unpack_from('<I',c.payload,4)[0]
  if c.payload[8:14]==b'HEAD\0\0':bas[pid]=struct.unpack_from('<H',c.payload,16)[0]
  else:state[pid]=c
 for typ,bit in [(15,1),(16,2)]:
  ids=[pid for pid,t in bas.items() if t==typ];assert len(ids)==bool(factions&bit)
  if ids:assert ids[0] in state
 ignored={'INSELLNK','INSEL5','ROHSTOFF','ERZE','SCHATZ','SPIELER','BIGBROTHER'}
 assert [(x.tag,x.payload) for x in parts if x.tag not in ignored]==[(x.tag,x.payload) for x in old if x.tag not in ignored]
 basicSpecial={struct.unpack_from('<I',c.payload,4)[0]:1 if struct.unpack_from('<H',c.payload,16)[0]==15 else 2 for c in old if c.tag=='SPIELER' and c.payload[8:14]==b'HEAD\0\0' and struct.unpack_from('<H',c.payload,16)[0] in [15,16]}
 expected=[c.payload for c in old if c.tag=='SPIELER' and (struct.unpack_from('<I',c.payload,4)[0] not in basicSpecial or factions&basicSpecial[struct.unpack_from('<I',c.payload,4)[0]])]
 assert [c.payload for c in parts if c.tag=='SPIELER']==expected
 script=next(c.payload for c in parts if c.tag=='BIGBROTHER');oldscript=next(c.payload for c in old if c.tag=='BIGBROTHER')
 for pid,bit in basicSpecial.items():
  label='PIRAT01' if bit==1 else 'VENEZIA01';line=f'"{label}" {pid}\n'.encode();assert oldscript.count(line)==1
  if not factions&bit:oldscript=oldscript.replace(line,b'')
 assert script==oldscript
 sceneCases.append(dict(difficulty=difficulty,factions=factions,bytes=n,basic_players=len(bas),state_players=len(state)))
results['source_scene_transform_cases']=sceneCases
# Parser failures must not publish partial special maps.
original=(ROOT/'Languages/Nl/Scenes/0010SingleEndlos'/sources[1]).read_bytes();raw=C.create_string_buffer(original);mapping=C.create_string_buffer(32)
assert lib.FactionFixtureSpecialMap(raw,len(original),mapping,err,len(err))
mutations=[]
specialComp=original.index(b'COMP\0\0'+struct.pack('<HII',191,16,5))
for label,at,value in [('truncated final chunk',len(original)-1,None),('special VOLK corruption',original.index(b'VENECIA\0'),ord('X')),('special state owner mismatch',specialComp+12,255)]:
 b=bytearray(original)
 if value is None:b=b[:at]
 else:b[at]=value
 mapping.raw=b'\xa5'*32;data=C.create_string_buffer(bytes(b));assert not lib.FactionFixtureSpecialMap(data,len(b),mapping,err,len(err)),label
 assert mapping.raw==b'\xa5'*32
 mutations.append(label)
results['malformed_special_records_no_partial_output']=mutations
# Full queued-node preparation sets pirate village bits even with culture mask0.
s=Settings(32,1,0,24,16,0,255,1);islands=plan(s);nodes=[C.create_string_buffer(0x170) for p in islands];scene=C.create_string_buffer(0x5400)
for i,(p,node) in enumerate(zip(islands,nodes)):
 struct.pack_into('<Q',node,8,C.addressof(nodes[i+1]) if i+1<len(nodes) else 0);struct.pack_into('<HHHHIH',node,0x10,p.x,p.y,p.width,p.height,p.id,p.climate)
struct.pack_into('<Q',scene,0x53f0,C.addressof(nodes[0]));assert lib.FactionFixturePreparedRoot(str(ROOT).encode());assert lib.WorldSettingsPrepareScene(scene,0)
assert all(n.raw[0x15c]==bool(p.cultures or p.templateIndex in pirateIds) for p,n in zip(islands,nodes));lib.WorldSettingsFinishAttempt(0)
results['queued_node_village_bits_verified']=len(nodes)
k=C.WinDLL('kernel32',use_last_error=True);k.VirtualAlloc.argtypes=[C.c_void_p,C.c_size_t,WT.DWORD,WT.DWORD];k.VirtualAlloc.restype=C.c_void_p;k.VirtualFree.argtypes=[C.c_void_p,C.c_size_t,WT.DWORD]
alloc=[];buffers=[]
def buf(n):b=C.create_string_buffer(n);buffers.append(b);return C.addressof(b)
def put(at,fmt,*v):C.memmove(at,struct.pack('<'+fmt,*v),struct.calcsize('<'+fmt))
def module(name):
 m=Module(str(ROOT/name));base=k.VirtualAlloc(None,(m.pe.OPTIONAL_HEADER.SizeOfImage+4095)&~4095,0x3000,0x40);assert base;alloc.append(base);m.pe.relocate_image(base);image=bytes(m.pe.get_memory_mapped_image());C.memmove(base,image,len(image));return base
def obj(n,vt):a=buf(n);put(a,'Q',w+vt);return a
w=module('AnnoWelt.dll');g=module('AnnoGame.dll');lib.FactionFixtureModules(w,g);world=obj(0x7000,0xff650);players=obj(0x110,0xfdbc0);put(world+0x210,'Q',players)
def player(id,type,culture):a=obj(0xd0,0xfabe0);put(a+8,'I',id);put(a+0x9c,'HH',type,culture);return a
pirate=player(6,15,11);trader=player(5,16,12);human=player(0,11,1);put(players+8,'Q',human)
cert=[]
def check(name,flags,expect):
 actual=lib.FactionFixturePlayers(world,flags,err,len(err));assert actual==expect,(name,err.value);cert.append(dict(case=name,result=actual,message=err.value.decode() if not actual else ''))
for flags in range(4):
 put(players+8+6*8,'Q',pirate if flags&1 else 0);put(players+8+5*8,'Q',trader if flags&2 else 0);check('exact selected players '+str(flags),flags,1)
 check('opposite settings rejected '+str(flags),flags^3,0)
put(players+8+6*8,'Q',pirate);put(players+8+5*8,'Q',trader)
put(pirate+0x9e,'H',12);check('pirates with Venetian VOLK rejected',3,0);put(pirate+0x9e,'H',11)
put(trader+0x9e,'H',11);check('Venetians with pirate VOLK rejected',3,0);put(trader+0x9e,'H',12)
put(players+8+7*8,'Q',pirate);check('crossed player slot rejected',3,0);put(players+8+7*8,'Q',0)
put(players,'Q',w+0xfdb58);check('unreviewed table class rejected',3,0);put(players,'Q',w+0xfdbc0)
put(world+0x210,'Q',1);check('unreadable player table rejected',3,0);put(world+0x210,'Q',players)
put(pirate,'Q',1);check('unreadable owner vtable rejected',3,0);put(pirate,'Q',w+0xfabe0)
check('restored complete player fixture',3,1)
results['loaded_native_player_getter_cases']=cert
lib.FactionFixtureLoaded.argtypes=[C.c_void_p,C.c_void_p,C.c_uint32]
# Full certificate, with one actual planned pirate island and its exact loaded
# owner. Occurrence first/next is the same explicit boundary double used by
# the existing certificate harness; every property getter remains native code.
s=Settings(32,1,0,24,16,0,255,3);planned=plan(s)
collections={};callbackErrors=[]
CALL=C.CFUNCTYPE(C.c_size_t,C.c_void_p,C.c_size_t,C.c_size_t,C.c_size_t)
@CALL
def first(collection,x,y,z):
 try:return collections[collection][0] if collections[collection] else 0
 except Exception as e:callbackErrors.append(repr(e));return 0
@CALL
def nextItem(collection,current,b,c):
 try:
  items=collections[collection];i=items.index(current);return items[i+1] if i+1<len(items) else 0
 except Exception as e:callbackErrors.append(repr(e));return 0
k.GetCurrentProcess.restype=C.c_void_p;k.FlushInstructionCache.argtypes=[C.c_void_p,C.c_void_p,C.c_size_t]
for rva,callback in [(0x5b340,first),(0x5b6c0,nextItem)]:
 code=b'\x48\xb8'+struct.pack('<Q',C.cast(callback,C.c_void_p).value)+b'\xff\xe0';C.memmove(w+rva,code,len(code));assert k.FlushInstructionCache(k.GetCurrentProcess(),w+rva,len(code))
def figure(definition):a=buf(0x168);put(a,'Q',g+0x211b0);put(a+8,'I',definition);return a
def occurrence(definition,x,y):
 a=obj(0x48,0xf66d0 if definition==1559 else 0xf58e8);put(a+8,'Q',figure(definition));put(a+0x20,'fff',x,0,y);put(a+0x38,'I',10000);return a
put(players+8+5*8,'Q',trader);put(players+8+6*8,'Q',pirate)
nativeEnum=[2,4,3,6,5,8,7,9];nativeId=10;pirateCity=None;ordinaryCity=None
for p in planned:
 a=obj(0x158,0xf33e8);put(world+0x6640+p.id*8,'Q',a);put(a+8,'HHHH',p.x,p.y,p.width,p.height);put(a+0x134,'I',p.cropMask);put(a+0x148,'B',p.climate)
 heights=buf((p.width+1)*(p.height+1));C.memset(heights,48,(p.width+1)*(p.height+1));fertility=buf(p.width*p.height);C.memset(fertility,15 if p.climate else 0,p.width*p.height);put(a+0x20,'QQ',heights,fertility)
 collection=obj(0x60,0xf42f8);put(a+0x48,'Q',collection);collections[collection]=[]
 for bit,definition in [(1,1661),(2,1561),(4,1562),(8,1563),(32,1564)]:
  if p.mineralMask&bit:collections[collection].append(occurrence(definition,p.x+20.5,p.y+20.5))
 if p.id==0:collections[collection].append(occurrence(1559,p.x+20.5,p.y+20.5))
 slot=0
 for bit,enum in enumerate(nativeEnum):
  if p.cultures&(1<<bit):
   owner=player(nativeId,14,enum);put(players+8+nativeId*8,'Q',owner);nativeId+=1;city=obj(0x30,0xfc678);put(city+0x28,'Q',owner);put(a+0x68+slot*8,'Q',city);slot+=1;ordinaryCity=ordinaryCity or city
 if p.templateIndex in pirateIds:
  pirateCity=obj(0x30,0xfc678);put(pirateCity+0x28,'Q',pirate);put(a+0x68+slot*8,'Q',pirateCity)
assert pirateCity and ordinaryCity
ship=obj(0x278,0xee000);put(ship+0x10,'Q',figure(1502));put(ship+0x270,'Q',human);put(ship+0x28,'fff',450.5,0,422.5)
vector=buf(32);put(vector+24,'Q',ship);residents=obj(0x28,0xffa20);put(residents+0x18,'QQ',vector,vector+32);put(world+0x208,'Q',residents)
loadedScene=buf(0x168);put(loadedScene+0x160,'Q',world);full=[]
def fullCheck(name,expected):
 actual=lib.FactionFixtureLoaded(loadedScene,err,len(err));assert actual==expected,(name,err.value);assert not callbackErrors,callbackErrors;full.append(dict(case=name,result=actual,message=err.value.decode() if not actual else ''))
fullCheck('selected pirate city and Venetian player accepted',1)
put(pirateCity+0x28,'Q',trader);fullCheck('pirate city transferred to Venetian owner rejected',0);put(pirateCity+0x28,'Q',pirate)
put(pirateCity+0x28,'Q',human);fullCheck('pirate city still owned by template human rejected',0);put(pirateCity+0x28,'Q',pirate)
put(pirateCity+0x28,'Q',0);fullCheck('pirate city with no owner rejected',0);put(pirateCity+0x28,'Q',pirate)
ordinaryOwner=struct.unpack('<Q',C.string_at(ordinaryCity+0x28,8))[0];put(ordinaryCity+0x28,'Q',pirate);fullCheck('extra pirate settlement on ordinary culture island rejected',0);put(ordinaryCity+0x28,'Q',ordinaryOwner)
put(players+8+5*8,'Q',0);fullCheck('missing enabled Venetian player rejected after world verification',0);put(players+8+5*8,'Q',trader)
fullCheck('restored full certificate fixture accepted',1)
results['full_loaded_world_faction_cases']=full
for base in alloc:assert k.VirtualFree(base,0,0x8000)
(HERE/'test_results.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps({k:v for k,v in results.items() if k not in ['scope','source_scene_transform_cases','loaded_native_player_getter_cases']},indent=2))
