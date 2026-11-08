"""Private compiled special-faction certificate and scoped-lifetime fixtures.

Actual original AMD64 World/controller property getters execute against private
native-shaped objects. No game is loaded, attached, executed or modified.
"""
from pathlib import Path
import ctypes as C
import hashlib
import itertools
import json
import os
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[2]
ROOT = WORK.parent
SOURCE = HERE/"special_activity"
sys.path[:0] = [str(WORK/"engine_audit"),str(WORK/"_tools")]
from audit import Module


def require(ok,message):
    if not ok:
        raise RuntimeError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


manifest = json.loads((SOURCE/"candidate_sources.json").read_bytes())
for name,digest in manifest["candidates"].items():
    require(sha((SOURCE/name).read_bytes()) == digest,"Candidate changed: "+name)
out = SOURCE/"_build"
out.mkdir(exist_ok=True)
text = (SOURCE/"world_ai.c").read_text()
require(text.count("void *approved=NULL;") == 1,"Fixture approved-module boundary changed")
text = "static void *fixtureApproved;\n"+text.replace("void *approved=NULL;","void *approved=fixtureApproved;")
text += """
static int fixturePending;
int WorldSettingsIsActive(void){return fixturePending;}
void WorldSettingsFinishAttempt(int success){fixturePending=0;WorldSettingsAIProfileAttemptFinished(success);}
__declspec(dllexport) void FixtureApprove(void*p){fixtureApproved=p;}
__declspec(dllexport) void FixtureExpect(int count,unsigned int factions){WorldSettingsExpectAIProfiles(count,factions);}
__declspec(dllexport) void FixtureFinish(int success){WorldSettingsAIProfileAttemptFinished(success);}
"""
(out/"fixture.c").write_text(text)
cache = HERE.parent/"compiler_cache"
env = os.environ.copy()
for variable,name in [("ZIG_GLOBAL_CACHE_DIR","global"),("ZIG_LOCAL_CACHE_DIR","special-activity-local"),("TEMP","tmp"),("TMP","tmp")]:
    target = cache/name
    target.mkdir(exist_ok=True)
    env[variable] = str(target)
subprocess.run([str(WORK/"_tools/ziglang/zig.exe"),"cc","-shared","-O2","-Wall","-Wextra","-Werror","-DWS_AI_FIXTURE",
                "-I",str(SOURCE),str(out/"fixture.c"),"-o",str(out/"SpecialActivityFixture.dll")],env=env,check=True)
lib = C.CDLL(str(out/"SpecialActivityFixture.dll"))


def function(name,args,restype=C.c_int):
    fn = getattr(lib,name)
    fn.argtypes = args
    fn.restype = restype
    return fn


check = function("WorldSettingsCheckSpecialControllers",[C.c_void_p,C.c_uint32,C.c_void_p,C.c_void_p,C.c_uint32])
world_module = function("WorldSettingsAITestWorldModule",[C.c_void_p],None)
approve = function("FixtureApprove",[C.c_void_p],None)
expect = function("FixtureExpect",[C.c_int,C.c_uint32],None)
finish = function("FixtureFinish",[C.c_int],None)
begin = function("WorldSettingsBeginNativeWorldStart",[],C.c_uint32)
end = function("WorldSettingsEndNativeWorldStart",[C.c_uint32,C.c_int])
bind = function("WorldSettingsBindAIProfileWorld",[C.c_void_p,C.c_void_p,C.c_uint32])
after = function("WorldSettingsAfterProfiles",[C.c_void_p])
status = function("WorldSettingsAIProfileStatus",[C.c_void_p],C.c_uint32)
k = C.WinDLL("kernel32",use_last_error=True)
k.VirtualAlloc.argtypes = [C.c_void_p,C.c_size_t,C.c_uint32,C.c_uint32]
k.VirtualAlloc.restype = C.c_void_p
k.VirtualFree.argtypes = [C.c_void_p,C.c_size_t,C.c_uint32]
modules = {name:Module(str(ROOT/name)) for name in ["AnnoWelt.dll","CompLogic.dll","CompLogicClassic.dll"]}
expected_hashes = {"AnnoWelt.dll":"ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9",
                   "CompLogic.dll":"7f2c7e818d8c25a0b6c48cda2d21bfa0c4096c5dcd8be91c2ab93d877c22afee",
                   "CompLogicClassic.dll":"0a7692879e15e8cbaed73ec3b59eaa6419165faaea6d8696cddfd68c92000f22"}
for name,module in modules.items():
    require(sha(module.data) == expected_hashes[name],"Original native module changed: "+name)
    require(module.pe.FILE_HEADER.Machine == 0x8664 and module.pe.OPTIONAL_HEADER.Magic == 0x20b,"Expected inspected AMD64")
factory_proof = []
for name,table,cases,initializer,setter,getter in [
        ("CompLogic.dll",0x59b98,[(15,0x597f7,0x59812,0x88ba8),(16,0x59907,0x59922,0x883c0)],0x80e0,0x6090,0x6640),
        ("CompLogicClassic.dll",0x56e5c,[(15,0x56c47,0x56c62,0x85aa0),(16,0x56d57,0x56d72,0x85258)],0x6480,0x4260,0x4a10)]:
    m = modules[name]
    for typ,branch,lea,vtable in cases:
        require(struct.unpack_from("<I",m.image,table+(typ-11)*4)[0] == branch,"Native special constructor branch differs")
        instruction = next(m.cs.disasm(m.image[lea:lea+7],m.base+lea))
        require(instruction.mnemonic == "lea" and instruction.address+instruction.size+instruction.disp-m.base == vtable,
                "Native special constructor vtable differs")
        for offset,method in [(0,initializer),(8,setter),(16,getter)]:
            require(struct.unpack_from("<Q",m.image,vtable+offset)[0] == m.base+method,"Native special method identity differs")
        factory_proof.append(dict(module=name,type=typ,constructor_branch=hex(branch),vtable=hex(vtable),
                                  initializer=hex(initializer),setter=hex(setter),getter=hex(getter)))
w_module = modules["AnnoWelt.dll"]
for vt in [0xff650,0xff1d8]:
    require(struct.unpack_from("<Q",w_module.image,vt+0xf0)[0] == w_module.base+0xd1910,"Native World getter vtable differs")
require(struct.unpack_from("<I",w_module.image,0xd19cc+6*4)[0] == 0xd1967 and
        w_module.image[0xd1967:0xd196e] == bytes.fromhex("8b81ec6e0000c3"),"Native World flags getter differs")
allocated = []


def mapped(name):
    image = modules[name].image
    size = (len(image)+4095)&~4095
    base = k.VirtualAlloc(None,size,0x3000,0x40)
    require(base,"Private native-image allocation failed")
    C.memmove(base,image,len(image))
    allocated.append(base)
    return base


def put(address,fmt,*values):
    C.memmove(address,struct.pack("<"+fmt,*values),struct.calcsize("<"+fmt))


w = mapped("AnnoWelt.dll")
for vt in [0xff650,0xff1d8]:
    put(w+vt+0xf0,"Q",w+0xd1910)
put(w+0xfdbc0+0x10,"Q",w+0xc6d80)
put(w+0xfdbc0+0x18,"Q",w+0x95990)
world_module(w)
err = C.create_string_buffer(512)
rows = []
matrix = []
lifetimes = []


def make(classic,factions,count=1):
    name = "CompLogicClassic.dll" if classic else "CompLogic.dll"
    a = mapped(name)
    owned = []
    def buffer(size):
        value = C.create_string_buffer(size)
        owned.append(value)
        return C.addressof(value)
    world = buffer(0x8000)
    table = buffer(0x110)
    scene = buffer(0x200)
    put(world,"Q",w+0xff650)
    put(world+0x210,"Q",table)
    put(world+0x6e48,"B",0)
    put(world+0x6eec,"I",0 if factions&1 else 0x20)
    put(table,"Q",w+0xfdbc0)
    put(scene+0x160,"Q",world)
    players = {}
    controllers = {}
    getter,setter,initializer = (0x4a10,0x4260,0x6480) if classic else (0x6640,0x6090,0x80e0)
    ordinary = 0x84fc8 if classic else 0x88128
    special_vtables = {15:0x85aa0 if classic else 0x88ba8,16:0x85258 if classic else 0x883c0}
    def player(ident,typ,culture,alias,controller=True):
        p = buffer(0x600)
        players[ident] = p
        put(p,"Q",w+0xfabe0)
        put(p+8,"I",ident)
        put(p+0x10,"Q",world)
        put(p+0x9c,"HH",typ,culture)
        C.memmove(p+0x68,alias.encode()+b"\0",len(alias)+1)
        put(table+8+ident*8,"Q",p)
        if controller:
            c = buffer(0x2200)
            controllers[ident] = c
            cv = a+(ordinary if typ==12 else special_vtables[typ])
            put(cv,"Q",a+initializer)
            put(cv+8,"Q",a+setter)
            put(cv+0x10,"Q",a+getter)
            put(c,"Q",cv)
            put(p+0x18,"Q",c)
            put(c+0xa4c,"I",typ)
            put(c+0xa64,"H",ident)
            put(c+0xab4,"I",0 if typ!=12 or ident<=count else 1)
            put(c+0xab0,"I",0 if typ!=12 or ident<=count else 1)
            put(c+0x1e9d,"B",1 if typ!=12 or ident<=count else 0)
        return p
    player(0,11,1,"HUMAN01",False)
    for ident in range(1,4):
        player(ident,12,1,"CG0"+str(ident))
    if factions&1:
        player(6,15,11,"PIRAT01")
    if factions&2:
        player(5,16,12,"VENEZIA01")
    return dict(a=a,owned=owned,world=world,table=table,scene=scene,players=players,controllers=controllers,
                classic=classic,factions=factions,count=count,new_player=player,getter=getter,setter=setter,initializer=initializer)


def inspect(f,expected=1,label="valid"):
    before = [bytes(value) for value in f["owned"]]
    actual = check(f["world"],f["factions"],f["a"],err,len(err))
    require(actual == expected,(label,actual,err.value.decode()))
    require(before == [bytes(value) for value in f["owned"]],"Read-only checker changed objects")
    rows.append(dict(case=label,classic=f["classic"],factions=f["factions"],accepted=bool(actual),error=err.value.decode()))
    return actual


try:
    for classic,count,factions in itertools.product([False,True],range(4),range(4)):
        f = make(classic,factions,count)
        inspect(f,label="selected identities and native flag")
        approve(f["a"])
        expect(count,factions)
        token = begin()
        require(token and bind(f["scene"],err,len(err)) == 1,"Native scope binding failed")
        require(after(f["world"]) == 1 and status(None) == count+1,"Post-profile count/faction check failed")
        require(end(token,1) == 1 and status(None) == count+1,"Successful native completion changed")
        unrelated = begin()
        require(unrelated and unrelated != token and after(None) == 1 and end(unrelated,1) == 1 and status(None) == 0,
                "Completed factions leaked into an unrelated native start")
        lifetimes.append(dict(classic=classic,count=count,factions=factions,generated_then_unrelated=True))
    for classic,ident,suspend,thinking in itertools.product([False,True],[5,6],range(3),range(3)):
        f = make(classic,3)
        put(f["controllers"][ident]+0xab4,"I",suspend)
        put(f["controllers"][ident]+0x1e9d,"B",thinking)
        accepted = inspect(f,int(suspend==0 and thinking==1),"special suspend/thinking matrix")
        matrix.append(dict(classic=classic,controller_owner=ident,suspend=suspend,thinking=thinking,accepted=bool(accepted)))
    mutators = [
        ("native Pirates flag off",lambda f: put(f["world"]+0x6eec,"I",0x20)),
        ("unsupported generated mode",lambda f: put(f["world"]+0x6e48,"B",1)),
        ("missing pirate player",lambda f: put(f["table"]+8+6*8,"Q",0)),
        ("pirate type mismatch",lambda f: put(f["players"][6]+0x9c,"H",11)),
        ("pirate culture mismatch",lambda f: put(f["players"][6]+0x9e,"H",1)),
        ("pirate alias mismatch",lambda f: C.memmove(f["players"][6]+0x68,b"HUMAN01\0",8)),
        ("player ID mismatch",lambda f: put(f["players"][6]+8,"I",7)),
        ("foreign parent world",lambda f: put(f["players"][6]+0x10,"Q",f["scene"])),
        ("wrong special controller class",lambda f: put(f["controllers"][6],"Q",f["a"]+0x88128)),
        ("controller type mismatch",lambda f: put(f["controllers"][6]+0xa4c,"I",12)),
        ("controller owner mismatch",lambda f: put(f["controllers"][6]+0xa64,"H",5)),
        ("native world getter mismatch",lambda f: put(w+0xff650+0xf0,"Q",w+0xd1911)),
        ("missing controller",lambda f: put(f["players"][6]+0x18,"Q",0)),
        ("duplicate pirate",lambda f: f["new_player"](7,15,11,"PIRAT01")),
        ("unsupported faction bits",lambda f: f.__setitem__("factions",7)),
    ]
    for label,mutate in mutators:
        f = make(False,3)
        mutate(f)
        inspect(f,0,label)
        put(w+0xff650+0xf0,"Q",w+0xd1910)
    # The callback must reject a native Pirates mismatch and End must clear the
    # incomplete token so no later load inherits its selected NPC expectations.
    f = make(False,3,3)
    approve(f["a"])
    expect(3,3)
    token = begin()
    require(bind(f["scene"],err,len(err)) == 1,"Failure fixture bind")
    put(f["world"]+0x6eec,"I",0x20)
    require(after(f["world"]) == 0 and status(None) == 0 and end(token,1) == 0,"Native special failure not blocked")
    unrelated = begin()
    require(after(None) == 1 and end(unrelated,1) == 1 and status(None) == 0,"Failed special selection leaked")
    lifetimes.append(dict(case="special failure clears count/faction/token and blocks native success"))
    for classic in [False,True]:
        f = make(classic,1,2)
        approve(f["a"])
        expect(2,1)
        old = begin()
        require(bind(f["scene"],err,len(err)) == 1,"Late-failure fixture bind")
        require(after(f["world"]) == 1 and status(None) == 3 and end(old,0) == 0 and status(None) == 0,
                "Late failure retained special verification")
        lifetimes.append(dict(case="late native failure clears prior count and special success",classic=classic))
        # A new native token must use its own faction mask, and completion of
        # the old token cannot consume or alter this new selection.
        g = make(classic,2,0)
        approve(g["a"])
        expect(0,2)
        current = begin()
        require(current and current != old and not begin(),"Reentrant native token was accepted")
        require(end(old,1) == 0 and bind(g["scene"],err,len(err)) == 1,"Stale completion consumed new selection")
        require(after(g["world"]) == 1 and status(None) == 1 and end(current,1) == 1,"New special selection inherited old bits")
        lifetimes.append(dict(case="stale completion and reentry preserve new independent faction mask",classic=classic))
        f = make(classic,3,1)
        approve(f["a"])
        expect(1,3)
        token = begin()
        require(bind(f["scene"],err,len(err)) == 1 and end(token,1) == 0 and status(None) == 0,
                "Native success without faction callback was accepted")
        unrelated = begin()
        require(after(None) == 1 and end(unrelated,1) == 1 and status(None) == 0,"Missing callback leaked faction expectation")
        lifetimes.append(dict(case="missing profile callback fails closed then disarms factions",classic=classic))
        expect(1,3)
        token = begin()
        require(bind(f["scene"],err,len(err)) == 1,"Factory-failure fixture bind")
        finish(0)
        require(end(token,0) == 0 and status(None) == 0,"Factory failure retained factions")
        unrelated = begin()
        require(after(None) == 1 and end(unrelated,1) == 1,"Factory failure leaked factions to unrelated load")
        lifetimes.append(dict(case="factory failure disarms expected count and factions",classic=classic))
finally:
    approve(None)
    world_module(None)
    for address in allocated:
        k.VirtualFree(address,0,0x8000)
for name,digest in manifest["candidates"].items():
    require(sha((SOURCE/name).read_bytes()) == digest,"Candidate changed during test: "+name)
report = dict(scope=__doc__,candidate_sha256=manifest["candidates"],fixture_dll_sha256=sha((out/"SpecialActivityFixture.dll").read_bytes()),
              original_native_sha256=expected_hashes,native_factory_and_method_proof=factory_proof,
              read_only_certificate_cases=rows,special_flag_matrix=matrix,
              scoped_count_faction_lifetimes=lifetimes,actual_game_runs=0,production_source_changed=False)
(SOURCE/"test_results.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(dict(certificate_cases=len(rows),special_state_matrix=len(matrix),scoped_lifetimes=len(lifetimes),actual_game_runs=0)))
