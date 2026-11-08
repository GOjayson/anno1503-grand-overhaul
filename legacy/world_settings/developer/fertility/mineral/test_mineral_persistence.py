"""Compiled production absence normalizer with actual Windows/native ore calls.

Original mapped AMD64 getter, definition-setter and extraction instructions run
directly. Synthetic native objects, occurrence enumerators and world flags are
explicit fixtures. This does not create a complete world, launch Anno or prove
gameplay/save UI; native serialization has a separate instruction proof.
"""
from pathlib import Path
import ctypes as C,struct,json,sys,hashlib
from ctypes import wintypes as WT
HERE=Path(__file__).resolve().parent
GAME=next(p for p in HERE.parents if (p/'Anno1503.exe').is_file() and (p/'WorldSettings_Work/_tools').is_dir())
PACKAGE=next((p for p in HERE.parents if (p/'world_patch.json').is_file()),GAME/'WorldSettings_Work/anno1503_food_world_dev5')
sys.path.insert(0,str(GAME/'WorldSettings_Work/_tools'))
sys.path.insert(0,str(PACKAGE/'developer/source/engine_audit'))
from audit import Module
k=C.WinDLL('kernel32',use_last_error=True)
k.VirtualAlloc.argtypes=[C.c_void_p,C.c_size_t,WT.DWORD,WT.DWORD];k.VirtualAlloc.restype=C.c_void_p
k.VirtualProtect.argtypes=[C.c_void_p,C.c_size_t,WT.DWORD,C.POINTER(WT.DWORD)]
k.VirtualFree.argtypes=[C.c_void_p,C.c_size_t,WT.DWORD]
k.FlushInstructionCache.argtypes=[C.c_void_p,C.c_void_p,C.c_size_t];k.GetCurrentProcess.restype=C.c_void_p
lib=C.CDLL(str(HERE/'_build/mineral_persistence_fixture.dll'))
class Island(C.Structure):_fields_=[(n,C.c_uint32) for n in ['id','x','y','width','height','templateIndex','cropMask','mineralMask','cultures','climate']]
lib.PersistenceModules.argtypes=[C.c_void_p,C.c_void_p]
lib.PersistencePlan.argtypes=[C.POINTER(Island),C.c_uint32,C.c_uint32]
lib.PersistencePending.argtypes=[C.c_void_p,C.c_int,C.c_int]
lib.PersistenceApply.argtypes=[C.c_void_p,C.c_void_p,C.c_uint32]
buffers=[];allocations=[]
def buf(n):
    b=C.create_string_buffer(n);buffers.append(b);return C.addressof(b)
def page():
    p=k.VirtualAlloc(None,4096,0x3000,4);assert p;allocations.append(p);return p
def put(at,fmt,*v):C.memmove(at,struct.pack('<'+fmt,*v),struct.calcsize('<'+fmt))
def get(at,fmt):return struct.unpack('<'+fmt,C.string_at(at,struct.calcsize('<'+fmt)))[0]
def map_module(name):
    m=Module(str(GAME/name));p=k.VirtualAlloc(None,m.pe.OPTIONAL_HEADER.SizeOfImage,0x3000,0x40);assert p;allocations.append(p)
    m.pe.relocate_image(p);data=bytes(m.pe.get_memory_mapped_image());C.memmove(p,data,len(data));return p,m
w,wm=map_module('AnnoWelt.dll');g,gm=map_module('AnnoGame.dll');lib.PersistenceModules(w,g)
collections={};flags=2;errors=[]
CALL=C.CFUNCTYPE(C.c_size_t,C.c_void_p,C.c_size_t,C.c_size_t,C.c_size_t)
@CALL
def first(obj,x,y,z):
    try:return collections[obj][0] if collections[obj] else 0
    except Exception as e:errors.append(str(e));return 0
@CALL
def next_item(obj,current,b,c):
    try:
        a=collections[obj];i=a.index(current)+1;return a[i] if i<len(a) else 0
    except Exception as e:errors.append(str(e));return 0
@CALL
def world_flags(obj,a,b,c):return flags
world=buf(0x7000);put(world,'Q',w+0xff650)
@CALL
def get_world(obj,a,b,c):return world
for rva,cb in [(0x5b340,first),(0x5b6c0,next_item)]:
    code=b'\x48\xb8'+struct.pack('<Q',C.cast(cb,C.c_void_p).value)+b'\xff\xe0';C.memmove(w+rva,code,len(code));k.FlushInstructionCache(k.GetCurrentProcess(),w+rva,len(code))
# Only the synthetic occurrence->world flag boundary is doubled. Everything
# in the ore getter/setter/extraction methods themselves remains unmodified.
world_vt=buf(0x200);put(world_vt+0xf0,'Q',C.cast(world_flags,C.c_void_p).value)
parent=buf(0x900);put(parent,'Q',parent+0x100);put(parent+0x100+0x38,'Q',C.cast(get_world,C.c_void_p).value)
native_flags_ptr=get(w+0xff650+0xf0,'Q');put(w+0xff650+0xf0,'Q',C.cast(world_flags,C.c_void_p).value)
construct=C.CFUNCTYPE(C.c_void_p,C.c_void_p)(w+0x71960)
setdef=C.CFUNCTYPE(C.c_size_t,C.c_void_p,C.c_void_p)(w+0x718f0)
def figure(ident):
    a=buf(0x168);put(a,'Q',g+0x211b0);put(a+8,'I',ident);put(a+0x108,'B',1);return a
def ore(ident,quantity=0,reserve=0,disabled=0):
    a=page();assert construct(a)==a;assert setdef(a,figure(ident))==0
    put(a+0x10,'Q',parent);put(a+0x38,'I',quantity);put(a+0x40,'BB',reserve,disabled);return a
scene=buf(0x168);put(scene+0x160,'Q',world)
island=buf(0x158);put(island,'Q',w+0xf33e8);put(world+0x6640,'Q',island)
collection=buf(0x60);put(collection,'Q',w+0xf42f8);put(island+0x48,'Q',collection)
plans=(Island*1)(Island(0,8,8,128,128,0,0xf949,1,0,2));assert lib.PersistencePlan(plans,1,64)
err=C.create_string_buffer(512);results=[]
def setup(rows,active=1,ready=1,capacity=64):
    global flags
    flags=2;collections[collection]=rows
    assert lib.PersistencePlan(plans,1,capacity);lib.PersistencePending(scene,active,ready);err.value=b''
def run(label,expect,contains=''):
    result=lib.PersistenceApply(scene,err,len(err));message=err.value.decode()
    assert result==expect,(label,result,message)
    if contains:assert contains in message,(label,message)
    assert not errors,errors
    results.append(dict(case=label,result=result,message=message));return result
for original in [1560,1561,1562,1563,1564]:
    anchor=ore(1661,0x19000);candidate=ore(original);untouched=ore(1561,123456,1)
    whale=buf(0x30);put(whale,'Q',w+0xf66d0);put(whale+8,'Q',figure(1559))
    unchanged={p:C.string_at(p,0x48 if p!=whale else 0x30) for p in [anchor,untouched,whale]}
    setup([anchor,candidate,untouched,whale]);run('native conversion/exhaustion '+str(original),1)
    assert get(get(candidate+8,'Q')+8,'I')==1661 and get(candidate+0x38,'I')==get(candidate+0x40,'B')==0
    for p,data in unchanged.items():assert C.string_at(p,len(data))==data
    snapshot=C.string_at(candidate,0x48);run('idempotent second absence pass '+str(original),1);assert C.string_at(candidate,0x48)==snapshot
for label,active,ready in [('inactive old/world/save path',0,1),('unprepared generation',1,0)]:
    anchor=ore(1661,0x19000);candidate=ore(1560);before=C.string_at(candidate,0x48);setup([anchor,candidate],active,ready)
    run(label,0,'pending');assert C.string_at(candidate,0x48)==before
for label,rows in [
    ('no verified1661 anchor',[ore(1560)]),
    ('negative native quantity',[ore(1661,0x19000),ore(1560,0xffffffff)]),
    ('disabled positive deposit',[ore(1661,0x19000),ore(1562,1234,0,1)]),
    ('unexpected shallow reserve',[ore(1661,0x19000),ore(1661,0,1)]),
]:
    setup(rows);before=[C.string_at(p,0x48) for p in rows];run(label,0)
    assert [C.string_at(p,0x48) for p in rows]==before
anchor=ore(1661,0x19000);a=ore(1560);b=ore(1561);setup([anchor,a,b],capacity=1)
before=[C.string_at(p,0x48) for p in [a,b]];run('all candidates prechecked before capacity failure',0,'safely persisted')
assert [C.string_at(p,0x48) for p in [a,b]]==before
anchor=ore(1661,0x19000);a=ore(1560);b=ore(1561);setup([anchor,a,b]);old=WT.DWORD()
assert k.VirtualProtect(b,4096,2,C.byref(old));before=[C.string_at(p,0x48) for p in [a,b]]
try:run('later read-only candidate refuses before first write',0,'safely persisted');assert [C.string_at(p,0x48) for p in [a,b]]==before
finally:assert k.VirtualProtect(b,4096,old.value,C.byref(WT.DWORD()))
for slot in [0x58,0x120]:
    anchor=ore(1661,0x19000);a=ore(1560);setup([anchor,a]);before=C.string_at(a,0x48)
    at=w+0xf58e8+slot;old=get(at,'Q');put(at,'Q',w+0x6ba0)
    try:run('spoofed original native method '+hex(slot),0,'safely persisted');assert C.string_at(a,0x48)==before
    finally:put(at,'Q',old)
anchor=ore(1661,0x19000);a=ore(1560);setup([anchor,a]);flags=0
run('native extraction refusal is detected by actual quantity',0,'not started')
assert get(a+0x38,'I')==0x19000
source=PACKAGE/'developer/source/engine_resume/ai_food/experiment_runtime/mineral_persistence.inc'
report=dict(scope=__doc__,passed=True,cases=len(results),results=results,
    source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    fixture_dll_sha256=hashlib.sha256((HERE/'_build/mineral_persistence_fixture.dll').read_bytes()).hexdigest(),
    fingerprints={'AnnoWelt.dll':hashlib.sha256(wm.data).hexdigest(),'AnnoGame.dll':hashlib.sha256(gm.data).hexdigest()},
    active_deposits_whales_and_other_state_unchanged=True,all_preconditions_before_first_conversion=True,
    native_refusal_rejects_pending_world=True,actual_game_run=False)
(HERE/'mineral_persistence_helper_results.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(passed=True,cases=len(results),game_executed=False),indent=2))
put(w+0xff650+0xf0,'Q',native_flags_ptr)
for a in allocations:k.VirtualFree(a,0,0x8000)
