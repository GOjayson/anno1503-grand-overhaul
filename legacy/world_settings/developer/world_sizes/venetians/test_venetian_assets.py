"""Automated data, scene/controller preservation and native-owner-gate checks.

This compiles actual dev7 special_scene.inc and the exact marked production
Venetian owner helper. Its file/controller/game objects are explicit fixture
boundaries. It does not launch Anno or establish save/reload persistence.
"""
from pathlib import Path
import ctypes as C
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import struct

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;PACKAGE=HERE.parents[2]
PRIVATE=PACKAGE/'developer/source/engine_resume/ai_food/experiment_runtime'
GAME=next(p for p in HERE.parents if (p/'Anno1503.exe').is_file() and not (p/'.anno1503-worldsettings-test-copy.json').is_file())
WORK=GAME/'WorldSettings_Work'
sys.path[:0]=[str(HERE),str(PACKAGE/'support')]
import generate_venetian_assets as g
import package_world_assets as a


def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    build=HERE/'_build';build.mkdir(exist_ok=True)
    source=(PRIVATE/'validated_world.inc').read_text()
    gate=source[source.index('/* Venetian owner gate:'):source.index('/* Welt a28e0 property1c')]
    (build/'owner_gate.generated.h').write_text(gate)
    compiler=WORK/'_tools/ziglang/zig.exe';dll=build/'venetian_fixture.dll'
    args=[str(compiler),'cc','-target','x86_64-windows-gnu','-shared','-O2','-Wall','-Wextra','-Werror','-Wno-unused-function','-I'+str(PRIVATE),'-I'+str(build),str(HERE/'scene_fixture.c'),'-o',str(dll)]
    environment=os.environ.copy()
    for key,folder in [('ZIG_GLOBAL_CACHE_DIR','zig-global'),('ZIG_LOCAL_CACHE_DIR','zig-local'),('TEMP','tmp'),('TMP','tmp')]:
        directory=build/folder;directory.mkdir(exist_ok=True);environment[key]=str(directory)
    run=subprocess.run(args,capture_output=True,text=True,check=True,env=environment)
    lib=C.WinDLL(str(dll));lib.TestScene.argtypes=[C.c_void_p,C.c_uint32,C.c_uint32,C.c_void_p,C.c_uint32,C.c_void_p,C.c_uint32];lib.TestScene.restype=C.c_uint32
    lib.TestPlayers.argtypes=[C.c_void_p,C.c_uint32,C.c_void_p,C.c_void_p,C.c_uint32];lib.TestPlayers.restype=C.c_int
    lib.TestOwner.argtypes=[C.c_void_p,C.c_void_p,C.c_int,C.c_int];lib.TestOwner.restype=C.c_int
    asset=(PACKAGE/'assets'/g.ASSET).read_bytes();dummy=(GAME/g.DUMMY).read_bytes()
    a.validate_source_bundle(GAME,PACKAGE/'assets',(PRIVATE/'world_catalogue.h').read_bytes())
    info=a.inspect_venetian(asset);a.inspect_dummy(dummy)
    assert len(info['building_anchors'])==73
    old=(GAME/g.SOURCE).read_bytes();_,trailer=g.envelope((GAME/g.TRAILER_SOURCE).read_bytes())
    assert g.extract(old,trailer)[0]==asset and sha(dummy)==g.DUMMY_SHA
    assert a.required_copy_inputs()=={g.DUMMY:g.DUMMY_SHA}
    assert a.validate_required_copy(GAME)==a.required_copy_inputs()
    # All generated products reproduce exactly, without touching originals.
    subprocess.run([sys.executable,str(HERE/'generate_venetian_assets.py'),'--game-dir',str(GAME),'--check'],capture_output=True,text=True,check=True)
    cases=[];rejected=[]
    def scene(p,f,capacity=32768):
        out=C.create_string_buffer(32768);error=C.create_string_buffer(512);before=bytes(out)
        n=lib.TestScene(p,len(p),f,out,capacity,error,len(error))
        return n,bytes(out[:n]) if n!=0xffffffff else b'',error.value.decode(),before,bytes(out)
    for preset,name in enumerate(['01_1024_easy_256.sze','03_1024_med_256.sze','06_1024_heavy_256.sze']):
        data=(GAME/'Languages/Nl/Scenes/0010SingleEndlos'/name).read_bytes();parts,_=g.envelope(data,True)
        special=(C.c_ubyte*32)();error=C.create_string_buffer(512)
        assert lib.TestPlayers(data,len(data),special,error,len(error))==1
        assert {i:v for i,v in enumerate(special)if v}=={5:2,6:1}
        for tag,p,*_ in parts:
            if tag!='SPIELER' or len(p)<8:continue
            ident=struct.unpack_from('<I',p,4)[0]
            if ident not in {5,6}:continue
            faction=2 if ident==5 else 1;n,out,err,*_=scene(p,faction)
            assert n!=0xffffffff,err
            want=p
            if faction==2:
                want=p[:8]+b''.join(p[at:at+h+len(v)]for k,v,at,h in g.fields(p)if k!='STADT2')
            assert out==g.chunk('SPIELER',want)
            before_comp=[v for k,v,*_ in g.fields(p)if k=='COMP']
            after_comp=[v for k,v,*_ in g.fields(want)if k=='COMP']
            assert before_comp==after_comp
            cases.append(dict(preset=preset,player_id=ident,controller_sha256=[sha(v)for v in before_comp],city_removed=len(p)-len(want),exact_other_bytes_preserved=True))
            if faction==2 and any(k=='STADT2'for k,*_ in g.fields(p)):
                for label,offset,value in [('wrong_city_id',114,b'\1\0'),('old_anchor_wrong_x',116,struct.pack('<H',211)),('old_anchor_wrong_y',118,struct.pack('<H',322))]:
                    bad=p[:offset]+value+p[offset+len(value):]
                    r,_,err,initial,final=scene(bad,faction)
                    assert r==0xffffffff and initial==final and err
                    rejected.append(label)
                r,_,err,initial,final=scene(p,2,4);assert r==0xffffffff and initial==final and err;rejected.append('capacity_before_output')
    # Exercise the production owner gate against wrong/foreign table members,
    # failed virtual ID reads, unreadable aliases and same-world violations.
    world=C.create_string_buffer(0x230);table=C.create_string_buffer(0x110);owner=C.create_string_buffer(0xd0)
    def put(buf,off,fmt,*values):struct.pack_into(fmt,buf,off,*values)
    wp,tp,op=map(C.addressof,[world,table,owner])
    def reset():
        C.memset(world,0,len(world));C.memset(table,0,len(table));C.memset(owner,0,len(owner))
        put(world,0x210,'<Q',tp);put(table,8+5*8,'<Q',op);put(owner,8,'<I',5);put(owner,0x10,'<Q',wp);C.memmove(op+0x68,b'VENEZIA01\0',10)
    reset();assert lib.TestOwner(wp,op,1,1)==1
    negatives=[('wrong_native_id',lambda:put(owner,8,'<I',6)),('oversized_native_id',lambda:put(owner,8,'<I',32)),('foreign_table_member',lambda:put(table,8+5*8,'<Q',0)),('foreign_world',lambda:put(owner,0x10,'<Q',0)),('wrong_alias',lambda:C.memmove(op+0x68,b'VENEZIA02\0',10))]
    for label,mutate in negatives:
        reset();mutate();assert lib.TestOwner(wp,op,1,1)==0;rejected.append(label)
    reset();assert lib.TestOwner(wp,op,0,1)==0;rejected.append('unreadable_alias')
    reset();assert lib.TestOwner(wp,op,1,0)==0;rejected.append('failed_native_id_call')
    # Strict data policy also rejects every wrong path, truncation and changed
    # city/terrain byte before the installer can use it.
    for record in a.RECORDS:
        data=(PACKAGE/record['payloadpath']).read_bytes()
        for label,mutated in [('truncated',data[:-1]),('appended',data+b'X'),('wrongbyte',data[:100]+bytes([data[100]^1])+data[101:])]:
            try:a.validate_data_payload(record['payloadpath'],mutated)
            except ValueError:rejected.append(record['targetpath']+':'+label)
            else:raise AssertionError('Data mutation accepted')
    required_root=(build/'required-input-case').resolve();assert required_root.is_relative_to(build.resolve())
    required=(required_root/g.DUMMY);required.parent.mkdir(parents=True,exist_ok=True)
    for label,mutated in [('truncated',dummy[:-1]),('appended',dummy+b'X'),('wrongbyte',dummy[:100]+bytes([dummy[100]^1])+dummy[101:])]:
        required.write_bytes(mutated)
        try:a.validate_required_copy(required_root)
        except ValueError:rejected.append('required_stock_dummy:'+label)
        else:raise AssertionError('Required stock dummy mutation accepted')
    required.write_bytes(dummy);assert a.validate_required_copy(required_root)==a.required_copy_inputs()
    for bad in ['assets/AnnoWelt.dll','../'+g.ASSET,'assets/'+g.ASSET.upper()]:
        try:a.validate_data_payload(bad,asset)
        except ValueError:rejected.append('wrongpath:'+bad)
        else:raise AssertionError('Unknown data path accepted')
    # Bounded parsers must reject forged lengths independently of the hash gate.
    for label,data in [('city_local_anchor',asset.replace(struct.pack('<HHH',0,28,33),struct.pack('<HHH',0,212,321),1)),('root_length',asset[:12]+struct.pack('<I',0xffffffff)+asset[16:]),('profile_alias',asset.replace(b'VENEZIA01\0',b'VENEZIA02\0',1))]:
        try:a.inspect_venetian(data)
        except ValueError:rejected.append(label)
        else:raise AssertionError('Malformed native profile accepted')
    result=dict(scope=__doc__,passed=True,game_executed=False,scene_controller_cases=cases,rejected_cases=rejected,native_city_building_count=73,required_existing_stock_dummy=dict(path=g.DUMMY,sha256=sha(dummy),bytes=len(dummy),bounded_format_verified=True,not_introduced_or_modified=True),source_sha256={str(p.relative_to(PACKAGE)).replace('\\','/'):sha(p.read_bytes())for p in [HERE/'scene_fixture.c',HERE/'test_venetian_assets.py',HERE/'generate_venetian_assets.py',PACKAGE/'support/package_world_assets.py',PRIVATE/'special_scene.inc']},owner_gate_sha256=sha(gate.encode()),fixture_dll_sha256=sha(dll.read_bytes()),compiler_command=args,compiler_stdout=run.stdout,compiler_stderr=run.stderr)
    (HERE/'automated_results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,scene_controller_cases=len(cases),rejected_cases=len(rejected),game_executed=False),indent=2))


if __name__=='__main__':main()
