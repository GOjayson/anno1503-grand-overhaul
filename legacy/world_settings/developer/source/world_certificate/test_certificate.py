"""Windows DLL tests of the reviewed loaded certificate against synthetic data.
Mapped original native getters execute directly. Only occurrence first/next
methods are doubles. No engine world/file load or gameplay is exercised.
"""
from pathlib import Path
import ctypes as C,sys,struct,json,math,os,hashlib
HERE=Path(__file__).resolve().parent
explicit=os.environ.get('ANNO1503_SOURCE_GAME')
ROOT=Path(explicit).resolve(strict=True) if explicit else next(p for p in HERE.parents if (p/'Anno1503.exe').is_file() and (p/'AnnoWelt.dll').is_file())
if not (ROOT/'AnnoGame.dll').is_file():raise ValueError('Explicit original game root is invalid')
sys.path.insert(0,str(ROOT/'WorldSettings_Work/_tools'))
sys.path.insert(0,str(HERE.parent/'engine_audit'))
from audit import Module
from ctypes import wintypes as WT
k=C.WinDLL('kernel32',use_last_error=True)
k.VirtualAlloc.argtypes=[C.c_void_p,C.c_size_t,WT.DWORD,WT.DWORD];k.VirtualAlloc.restype=C.c_void_p
k.VirtualProtect.argtypes=[C.c_void_p,C.c_size_t,WT.DWORD,C.POINTER(WT.DWORD)]
k.VirtualFree.argtypes=[C.c_void_p,C.c_size_t,WT.DWORD]
k.FlushInstructionCache.argtypes=[C.c_void_p,C.c_void_p,C.c_size_t]
k.GetCurrentProcess.restype=C.c_void_p
class Island(C.Structure):_fields_=[(x,C.c_uint32) for x in ['id','x','y','width','height','templateIndex','cropMask','mineralMask','cultures','climate']]
lib=C.CDLL(str(HERE/'_build/CertificateFixture.dll'))
lib.FixtureModules.argtypes=[C.c_void_p,C.c_void_p]
lib.FixturePlan.argtypes=[C.POINTER(Island),C.c_uint32,C.c_uint32]
lib.FixtureValidate.argtypes=[C.c_void_p,C.c_void_p,C.c_uint32]
lib.FixtureMethod.argtypes=[C.c_void_p,C.c_uint32];lib.FixtureMethod.restype=C.c_void_p
lib.FixtureMemory.argtypes=[C.c_void_p,C.c_size_t,C.c_int]
lib.FixtureCulture.argtypes=[C.c_uint32];lib.FixtureCulture.restype=C.c_uint32
buffers=[];allocations=[]
def buf(size):
 b=C.create_string_buffer(size);buffers.append(b);return C.addressof(b)
def put(at,fmt,*values):C.memmove(at,struct.pack('<'+fmt,*values),struct.calcsize('<'+fmt))
def get(at,fmt):return struct.unpack('<'+fmt,C.string_at(at,struct.calcsize('<'+fmt)))[0]
def map_module(name):
 m=Module(str(ROOT/name));size=(m.pe.OPTIONAL_HEADER.SizeOfImage+4095)&~4095
 expected={'AnnoWelt.dll':'ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9','AnnoGame.dll':'e6f01d19e8e16e6716c0a6c7d3ba00273c9df493e051b8ba62865ee4b53dfdea'}
 assert hashlib.sha256(m.data).hexdigest()==expected[name],name
 assert m.pe.FILE_HEADER.Machine==0x8664 and m.pe.OPTIONAL_HEADER.Magic==0x20b
 base=k.VirtualAlloc(None,size,0x3000,0x40);assert base,C.get_last_error();allocations.append(base)
 m.pe.relocate_image(base);data=bytes(m.pe.get_memory_mapped_image());C.memmove(base,data,len(data));return base,m
w,wm=map_module('AnnoWelt.dll');g,gm=map_module('AnnoGame.dll');lib.FixtureModules(w,g)
collections={};reverse={};callback_errors=[]
CALL=C.CFUNCTYPE(C.c_size_t,C.c_void_p,C.c_size_t,C.c_size_t,C.c_size_t)
@CALL
def first(obj,x,y,z):
 try:
  items=collections[obj];return items[0] if items else 0
 except Exception as e:callback_errors.append(repr(e));return 0
@CALL
def next_item(obj,current,b,c):
 try:
  items=collections[obj];index=items.index(current);return items[index+1] if index+1<len(items) else 0
 except Exception as e:callback_errors.append(repr(e));return 0
for rva,cb in [(0x5b340,first),(0x5b6c0,next_item)]:
 code=b'\x48\xb8'+struct.pack('<Q',C.cast(cb,C.c_void_p).value)+b'\xff\xe0';C.memmove(w+rva,code,len(code));k.FlushInstructionCache(k.GetCurrentProcess(),w+rva,len(code))
def obj(size,vt,module=w):
 a=buf(size);put(a,'Q',module+vt);return a
def figure(definition):
 a=obj(0x168,0x211b0,g);put(a+8,'I',definition);return a
def player(index,kind=14,culture=0):
 a=obj(0xd0,0xfabe0);put(a+8,'I',index);put(a+0x9c,'HH',kind,culture);return a
def occurrence(definition,x,y):
 a=obj(0x48,0xf66d0 if definition==1559 else 0xf58e8);put(a+8,'Q',figure(definition));put(a+0x20,'fff',x,0,y);put(a+0x38,'I',10000);return a
human=player(0,0xb)
ship=obj(0x278,0xee000);put(ship+0x10,'Q',figure(1502));put(ship+0x270,'Q',human);put(ship+0x28,'fff',566.5,0,435.5)
vector=buf(32);put(vector+24,'Q',ship)
table=obj(0x28,0xffa20);put(table+0x18,'QQ',vector,vector+32)
world=obj(0x7000,0xff650);put(world+0x208,'Q',table)
# The actual server constructor puts a distinct map object at+220. Keeping
# that decoy in fixtures prevents the original wrong-field inference recurring.
map_object=obj(0x28,0xff5e0);put(world+0x220,'Q',map_object)
scene=buf(0x168);put(scene+0x160,'Q',world)
masks=[0x18000,0xf009,0xf949,0xf06b,0xf6b9,0xf04d]
plans=(Island*6)();islands=[];ores=[];cities=[];owners=[]
for i in range(6):
 p=plans[i];p.id=i;p.x=20+i*80;p.y=20;p.width=p.height=64;p.climate=i;p.cropMask=masks[i]
 a=obj(0x158,0xf33e8);islands.append(a);put(world+0x6640+i*8,'Q',a);put(a+8,'HHHH',p.x,p.y,64,64);put(a+0x134,'I',masks[i]|0xf009);put(a+0x148,'B',i)
 heights=buf(65*65);C.memset(heights,48,65*65);fertility=buf(64*64);C.memset(fertility,15 if i else 0,64*64);put(a+0x20,'QQ',heights,fertility)
 t=obj(0x60,0xf42f8);put(a+0x48,'Q',t);collections[t]=[]
 needed={0:[1559],2:[1661,1562,1564],4:[1561],5:[1563]}.get(i,[])
 for definition in needed:
  o=occurrence(definition,p.x+30.5,p.y+30.5);collections[t].append(o)
  if definition!=1559:ores.append(o);p.mineralMask|={1661:1,1562:4,1564:32,1561:2,1563:8}[definition]
 if i==2:
  for c,enum in enumerate([2,4,3,6,5,8,7,9]):
   owner=player(10+c,14,enum);city=obj(0x30,0xfc678);put(city+0x28,'Q',owner);put(a+0x68+c*8,'Q',city);cities.append(city);owners.append(owner);p.cultures|=1<<c
assert lib.FixturePlan(plans,6,16)
err=C.create_string_buffer(512);results=[]
def validate(name,expected,contains=''):
 err.value=b'';actual=lib.FixtureValidate(scene,err,len(err));message=err.value.decode()
 assert actual==expected,(name,actual,message)
 if contains:assert contains in message,(name,message,contains)
 assert not callback_errors,callback_errors
 results.append({'case':name,'result':actual,'message':message})
def mutation(name,at,fmt,value,contains):
 old=get(at,fmt);put(at,fmt,value)
 try:validate(name,0,contains)
 finally:put(at,fmt,old)
validate('valid synthetic world using original native getters',1)
for slot,rva in [(0x58,0x718f0),(0x120,0x71800)]:
 assert lib.FixtureMethod(ores[0],slot)==w+rva
 address=w+0xf58e8+slot;old=get(address,'Q');put(address,'Q',w+0x6ba0)
 assert lib.FixtureMethod(ores[0],slot) is None
 put(address,'Q',old)
 results.append({'case':'persistence native ore method exact binding and spoof refusal '+hex(slot),'result':1})
# Availability is an exact per-island contract, not only worldwide presence.
# Wine remains available on other climates while this northern island omits it.
old_mask=plans[2].cropMask
plans[2].cropMask=old_mask&~(1<<6);assert lib.FixturePlan(plans,6,16)
put(islands[2]+0x134,'I',plans[2].cropMask|0xf009)
validate('reduced favorable crop set with worldwide essential coverage',1)
mutation('extra favorable crop defeats a reduced selection',islands[2]+0x134,'I',old_mask|0xf009,'crop availability')
mutation('unknown extra crop bit is rejected',islands[2]+0x134,'I',(plans[2].cropMask|0xf009)|(1<<20),'crop availability')
plans[2].cropMask=old_mask;assert lib.FixturePlan(plans,6,16);put(islands[2]+0x134,'I',old_mask|0xf009)
mutation('native forced grain bit missing on polar island',islands[0]+0x134,'I',(masks[0]|0xf009)&~1,'crop availability')
for value in [masks[2]|(1<<1),masks[2]&~(1<<14),masks[2]&~(1<<0)]:
 plans[2].cropMask=value;assert lib.FixturePlan(plans,6,16)
 validate('unsupported planned climate or missing native base crop '+hex(value),0,'planned crop availability')
plans[2].cropMask=old_mask;assert lib.FixturePlan(plans,6,16)
# An ore-free island may retain nonharvestable native marker objects. They
# must not count as resources, whereas an unexpected active deposit must fail.
bare_collection=get(islands[1]+0x48,'Q')
extra=occurrence(1560,plans[1].x+30.5,plans[1].y+30.5)
collections[bare_collection]=[extra]
validate('unexpected active physical mineral on selected ore-free island',0,'physical mineral')
put(extra+0x41,'B',1);validate('disabled leftover mineral marker does not add availability',1)
put(extra+0x41,'B',0);put(extra+0x38,'I',0)
validate('depleted leftover mineral marker does not add availability',1)
collections[bare_collection]=[]
# The native quantity query with argument1 includes reserved ore. Reserve-only
# assigned ore is usable and must be counted; a disabled assigned one is not.
put(ores[0]+0x40,'B',1);validate('assigned reserve-only mineral is counted by native getter',1)
mutation('disabled reserve-only assigned mineral fails availability',ores[0]+0x41,'B',1,'physical mineral')
put(ores[0]+0x40,'B',0)
old_minerals=plans[2].mineralMask
plans[2].mineralMask=(old_minerals&~1)|0x40;assert lib.FixturePlan(plans,6,16)
validate('native iron request variant normalizes to same physical good',1)
for value in [old_minerals|0x40,old_minerals|0x10,old_minerals|0x80]:
 plans[2].mineralMask=value;assert lib.FixturePlan(plans,6,16)
 validate('unknown or duplicate iron mineral request '+hex(value),0,'planned physical mineral')
plans[2].mineralMask=old_minerals;assert lib.FixturePlan(plans,6,16)
mutation('loaded geometry mismatch',islands[0]+8,'H',21,'geometry')
assert 'id=0 reason=rectangle-mismatch' in err.value.decode()
assert 'plan(id=0 xy=20,20 size=64,64 climate=0 template=0/1)' in err.value.decode()
assert 'loaded(read=1 xy=21,20 size=64,64 climate=0)' in err.value.decode()
assert 'class=Welt+0xf33e8 method190=verified' in err.value.decode()
mutation('loaded climate mismatch',islands[1]+0x148,'B',4,'climate')
assert 'id=1 reason=climate-mismatch' in err.value.decode() and 'climate=4)' in err.value.decode()
mutation('missing planned island',world+0x6640,'Q',0,'essential')
put(world+0x6640+200*8,'Q',islands[0]);validate('unexpected loaded island',0,'unexpected');put(world+0x6640+200*8,'Q',0)
mutation('essential physical mineral depleted',ores[0]+0x38,'I',0,'physical mineral')
mutation('disabled mineral does not count',ores[0]+0x41,'B',1,'physical mineral')
mutation('negative quantity is rejected',ores[0]+0x38,'I',0xffffffff,'physical mineral')
mutation('occurrence coordinates outside island',ores[0]+0x20,'f',math.nan,'outside')
mutation('native culture remapping mismatch',owners[0]+0x9e,'H',4,'culture owners')
mutation('unsupported native culture',owners[0]+0x9e,'H',1,'unsupported')
mutation('city still belongs to original template owner',owners[0]+0x9c,'H',11,'transferred')
mutation('native village owner missing',cities[0]+0x28,'Q',0,'no owner')
mutation('required crop flag missing',islands[2]+0x134,'I',0xf009,'crop')
fert=get(islands[2]+0x28,'Q');C.memset(fert,0,64*64);validate('no fertile land in growing climate',0,'fertile land');C.memset(fert,15,64*64)
mutation('terrain pointer unreadable',islands[2]+0x28,'Q',1,'terrain')
mutation('human starting ship moved',ship+0x28,'f',565.5,'starting ships')
assert 'reason=human-stock-position' in err.value.decode() and 'xy=565.5,435.5' in err.value.decode()
assert 'owner=0 def=1502 ownerClass=Welt+0xfabe0 figureClass=Game+0x211b0' in err.value.decode()
mutation('human ship NaN position',ship+0x28,'f',math.nan,'starting ships')
assert 'reason=position-bounds' in err.value.decode()
mutation('stock ship identity wrong',get(ship+0x10,'Q')+8,'I',1503,'starting ships')
assert 'reason=human-stock-definition' in err.value.decode() and 'def=1503' in err.value.decode()
mutation('human starting ship missing',vector+24,'Q',0,'starting ships')
assert 'reason=human-ship-count' in err.value.decode() and 'residents=1 live=0 playerShips=0 checked=0 humans=0' in err.value.decode()
mutation('resident vector malformed',table+0x20,'Q',vector+31,'starting ships')
assert 'reason=resident-vector-range' in err.value.decode()
mutation('resident table class mismatch',table,'Q',w+0xffa28,'resident-table-class')
mutation('missing actual resident table ignores map decoy',world+0x208,'Q',0,'resident-table-class')
mutation('empty resident vector',table+0x20,'Q',vector,'resident-vector-empty')
mutation('ship owner is NULL',ship+0x270,'Q',0,'ship-owner-null')
mutation('ship definition pointer is NULL',ship+0x10,'Q',0,'ship-figure-null')
mutation('unreviewed ship figure class',get(ship+0x10,'Q'),'Q',g+0x20ec0,'figure-definition-getter')
assert 'figureClass=Game+0x20ec0' in err.value.decode() and 'method=figure+88' in err.value.decode()
mutation('unreviewed ship owner class',human,'Q',w+0xfb090,'owner-id-getter')
assert 'ownerClass=Welt+0xfb090' in err.value.decode() and 'method=owner+88' in err.value.decode()
mutation('unreviewed ship X method',w+0xee000+0xb0,'Q',w+0x6ba0,'ship-x-getter')
mutation('unreviewed ship Y method',w+0xee000+0xc0,'Q',w+0x6ba0,'ship-y-getter')
mutation('known other ship class remains unaccepted',ship,'Q',w+0xee6a8,'human-ship-count')
assert 'otherShips=1' in err.value.decode() and 'firstOther=Welt+0xee6a8' in err.value.decode()
ai_ship=obj(0x278,0xee000);put(ai_ship+0x10,'Q',figure(1502));put(ai_ship+0x270,'Q',player(1,2));put(ai_ship+0x28,'fff',605.5,0,434.5)
two_ships=buf(64);put(two_ships+24,'Q',ship);put(two_ships+56,'Q',ai_ship);put(table+0x18,'QQ',two_ships,two_ships+64)
validate('human and an AI ship with open-water clearance',1)
put(ai_ship+0x28,'fff',50.5,0,50.5);validate('AI ship inside an actual island',0,'starting ships')
assert 'reason=island-clearance' in err.value.decode() and 'clearanceIsland=0' in err.value.decode()
put(ai_ship+0x28,'fff',19.5,0,90.5);validate('AI ship in16tile island margin',0,'starting ships')
put(table+0x18,'QQ',vector,vector+32)
put(ship+0x28,'f',565.5);shortShip=C.create_string_buffer(b'Z'*32)
assert lib.FixtureValidate(scene,shortShip,17)==0 and shortShip.raw[16]==0 and shortShip.raw[17:]==b'Z'*15+b'\0'
assert lib.FixtureValidate(scene,None,0)==0;put(ship+0x28,'f',566.5)
results.append({'case':'bounded ship diagnostic and NULL error buffer','result':1})
mutation('native island method table spoof',islands[0],'Q',w+0xf2da0,'geometry')
assert 'reason=native-method190' in err.value.decode() and 'class=Welt+0xf2da0 method190=no verified method' in err.value.decode()
mutation('native class outside expected module',islands[0],'Q',fert,'geometry')
assert 'class=outside Welt' in err.value.decode() and hex(fert) not in err.value.decode()
# Exact known class with unknown function pointer must fail before executing it.
mutation('native method address spoof',w+0xf33e8+0x190,'Q',w+0x6ba0,'geometry')
assert 'class=Welt+0xf33e8 method190=no verified method' in err.value.decode()
for field,value,reason in [('templateIndex',1,'template-index'),('climate',6,'plan-climate'),('width',0,'plan-dimensions'),('x',0xffffffff,'plan-world-bounds')]:
 previous=getattr(plans[0],field);setattr(plans[0],field,value);assert lib.FixturePlan(plans,6,16)
 validate('diagnostic for invalid planned '+field,0,reason)
 setattr(plans[0],field,previous);assert lib.FixturePlan(plans,6,16)
# A short caller buffer must remain NUL terminated without adjacent writes.
put(islands[0]+8,'H',21);short=C.create_string_buffer(b'Z'*32)
assert lib.FixtureValidate(scene,short,17)==0
assert short.raw[16]==0 and short.raw[17:]==b'Z'*15+b'\0'
assert lib.FixtureValidate(scene,None,0)==0
put(islands[0]+8,'H',20)
results.append({'case':'bounded island diagnostic and NULL error buffer','result':1})
# Missing whale cannot pass on crop bits alone.
polar_collection=get(islands[0]+0x48,'Q');saved=collections[polar_collection];collections[polar_collection]=[]
validate('whale flag without physical whale',0,'essential');collections[polar_collection]=saved
# Two-node cycle: the cap must stop it. This deliberately uses the collection double.
original_next=next_item
@CALL
def cyclic_next(obj,current,b,c):
 if obj==polar_collection:return saved[0]
 return original_next(obj,current,b,c)
code=b'\x48\xb8'+struct.pack('<Q',C.cast(cyclic_next,C.c_void_p).value)+b'\xff\xe0';C.memmove(w+0x5b6c0,code,len(code))
validate('occurrence collection self cycle',0,'does not advance')
code=b'\x48\xb8'+struct.pack('<Q',C.cast(original_next,C.c_void_p).value)+b'\xff\xe0';C.memmove(w+0x5b6c0,code,len(code))
validate('valid fixture restored after negative mutations',1)
# Real Windows page protection checks, including a span crossing two pages.
pages=k.VirtualAlloc(None,8192,0x3000,0x04);assert pages;allocations.append(pages);old=WT.DWORD()
assert lib.FixtureMemory(pages,8192,0)==1
assert k.VirtualProtect(pages+4096,4096,0x01,C.byref(old))
assert lib.FixtureMemory(pages+4090,10,0)==0
assert lib.FixtureMemory(pages,4096,0)==1
assert lib.FixtureMemory(pages,8,1)==0
assert lib.FixtureMemory(0xfffffffffffffff0,64,0)==0
assert lib.FixtureMemory(None,8,0)==0
results.append({'case':'Windows protection, spanning, execute, overflow and null checks','result':1})
for c,enum in enumerate([2,4,3,6,5,8,7,9]):assert lib.FixtureCulture(enum)==1<<c
for enum in [0,1,10,14,255,0xffffffff]:assert lib.FixtureCulture(enum)==0
results.append({'case':'all8native culture mappings and6unknown enums','result':1})
(HERE/'certificate_results.json').write_text(json.dumps({'scope':__doc__,'cases':results,'passed':len(results),'native_methods':'original mapped executable instructions except occurrence collection first/next doubles',
 'fixture_sha256':hashlib.sha256((HERE/'_build/CertificateFixture.dll').read_bytes()).hexdigest(),
 'source_sha256':{name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in ['validated_world.inc','certificate_fixture.c','test_certificate.py','build_certificate.py']},
 'exact_crop_availability_checked':True,'native_forced_crop_mask':'0xf009','exact_active_mineral_good_set_checked':True,
 'availability_not_harvesting_or_navigation':True,'game_executed':False},indent=2))
print(json.dumps({'cases':len(results),'status':'passed','scope':__doc__}))
for allocation in allocations:assert k.VirtualFree(allocation,0,0x8000)
