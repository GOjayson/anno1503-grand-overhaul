"""Execute compiled production SZE rewriting and exact starting-ship contracts.

Synthetic one-island fixtures isolate serialization, dimensions and reservations;
they do not certify map feasibility, native loading or a running game.
"""
from pathlib import Path
import ctypes as C,hashlib,json,math,struct
HERE=Path(__file__).resolve().parent;PACKAGE=HERE.parents[1];ROOT=HERE.parents[3]
class Settings(C.Structure):
    _fields_=[('size',C.c_uint32)]+[(n,C.c_int32) for n in ['difficulty','islandSize','islandCount','spacing','aiCount']]+[(n,C.c_uint32) for n in ['cultures','factions']]+[(n,C.c_int32) for n in ['startingMoney','startingFleet','aiDifficulty','plantFertility','mineralFertility','worldSize']]
class Ship(C.Structure):_fields_=[('owner',C.c_uint32),('definition',C.c_uint32),('x',C.c_float),('y',C.c_float)]
class Island(C.Structure):_fields_=[(n,C.c_uint32) for n in ['id','x','y','width','height','templateIndex','cropMask','mineralMask','cultures','climate']]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def chunks(data):
    assert data[:12].rstrip(b'\0') in [b'ANNO',b'ANNOADDON1'] and struct.unpack_from('<I',data,12)[0]==len(data)-16
    assert data[16:28].rstrip(b'\0')==b'SCENE' and struct.unpack_from('<I',data,28)[0]==len(data)-32
    at=32
    while at<len(data):
        assert len(data)-at>=16;n=struct.unpack_from('<I',data,at+12)[0];assert n<=len(data)-at-16
        yield data[at:at+12].rstrip(b'\0'),data[at+16:at+16+n],at
        at+=16+n
    assert at==len(data)
def fields(p):
    at=8
    while at<len(p):
        assert len(p)-at>=8;n=struct.unpack_from('<H',p,at+6)[0];h=8
        if n>=0xff00:h=10;n=((n&255)<<16)|struct.unpack_from('<H',p,at+8)[0]
        assert n<=len(p)-at-h
        yield p[at:at+6].rstrip(b'\0'),p[at+h:at+h+n],at+h
        at+=h+n
    assert at==len(p)
def ships(data):
    result=[]
    for tag,p,offset in chunks(data):
        if tag!=b'SPIELER':continue
        assert len(p)>=8;owner=struct.unpack_from('<I',p,4)[0]
        for tag,f,field_at in fields(p):
            if tag not in [b'SCHIFF',b'SCHI64']:continue
            wide=tag==b'SCHI64';pos=12 if wide else 8;definition=struct.unpack_from('<H',f,4 if wide else 2)[0]
            packed_owner=struct.unpack_from('<I',f,8 if wide else 4)[0];assert packed_owner==owner
            x,y=struct.unpack_from('<ff',f,pos);assert math.isfinite(x) and math.isfinite(y)
            result.append(dict(owner=owner,definition=definition,x=x,y=y,payload=f,position_at=offset+16+field_at+pos))
    return result
def main():
    assert C.sizeof(Settings)==56 and C.sizeof(Island)==40
    fixture=HERE/'_build/world_size_fixture.dll';build=json.loads((HERE/'fixture_build.json').read_bytes());assert sha(fixture)==build['fixture_dll_sha256']
    assert all(sha(PACKAGE/name)==digest for name,digest in build['input_sha256'].items())
    lib=C.CDLL(str(fixture));lib.SizeFixtureScene.argtypes=[C.POINTER(Settings),C.c_void_p,C.c_uint32,C.c_void_p,C.c_uint32]
    lib.SizeFixtureExpected.argtypes=[C.POINTER(Ship),C.c_uint32];lib.SizeFixtureExpected.restype=C.c_uint32
    lib.SizeFixtureReserves.argtypes=[C.POINTER(Island),C.c_uint32];lib.SizeFixtureReserves.restype=C.c_uint32
    lib.SizeFixtureMatch.argtypes=[C.c_uint32,C.c_uint32,C.c_float,C.c_float,C.POINTER(C.c_uint32)]
    lib.SizeFixtureRewrite.argtypes=[C.c_void_p,C.c_uint32,C.c_void_p,C.c_uint32]
    lib.WorldSettingsBuildPlan.argtypes=[C.POINTER(Settings),C.c_uint32,C.c_void_p,C.c_uint32]
    buf=C.create_string_buffer(262144);error=C.create_string_buffer(1024);expected=(Ship*32)();reserves=(Island*32)();report=[];reserve_sets={};negative=[]
    stock_names=['01_1024_easy_256.sze','03_1024_med_256.sze','06_1024_heavy_256.sze']
    stock=[ships((ROOT/'Languages/Nl/Scenes/0010SingleEndlos'/name).read_bytes()) for name in stock_names]
    for size in [2048,256,512,1024]:
      for difficulty in range(3):
       for fleet in range(3):
        for factions in range(4):
            s=Settings(56,difficulty,3,1,0,0,255,factions,100000,fleet,0,1,1,size)
            used=lib.SizeFixtureScene(C.byref(s),buf,len(buf),error,len(error));assert used>0,error.value.decode()
            data=bytes(buf.raw[:used]);rows=ships(data);head=[p for tag,p,_ in chunks(data) if tag==b'HEAD'];assert len(head)==1 and struct.unpack_from('<II',head[0])==(size,size)
            count=lib.SizeFixtureExpected(expected,32);assert count==len(rows)==(4 if difficulty==0 else 5)+(2 if fleet else 0)
            tuples={(r['owner'],r['definition'],r['x'],r['y']) for r in rows};want={(r.owner,r.definition,r.x,r.y) for r in expected[:count]};assert tuples==want and len(tuples)==count
            for row in rows:
                assert 16<=row['x']<size-16 and 16<=row['y']<size-16
                if size==1024 and row['owner']:
                    source=next(r for r in stock[difficulty] if r['owner']==row['owner']);assert row['payload']==source['payload']
                if size==1024 and not fleet and not row['owner']:assert row['payload']==stock[difficulty][0]['payload']
            rc=lib.SizeFixtureReserves(reserves,32);assert rc==(7 if size==1024 else 5)
            active=bytes(reserves)[:rc*C.sizeof(Island)];assert reserve_sets.setdefault(size,active)==active
            for ship in rows:
                assert any(r.x<=ship['x']-16 and r.y<=ship['y']-16 and r.x+r.width>ship['x']+16 and r.y+r.height>ship['y']+16 for r in reserves[:rc])
            seen=C.c_uint32()
            for row in rows:assert lib.SizeFixtureMatch(row['owner'],row['definition'],row['x'],row['y'],C.byref(seen))==1
            assert seen.value==(1<<count)-1
            duplicate=rows[0];assert lib.SizeFixtureMatch(duplicate['owner'],duplicate['definition'],duplicate['x'],duplicate['y'],C.byref(seen))==0
            report.append(dict(size=size,difficulty=difficulty,fleet=fleet,factions=factions,serialized_ships=count,ship_tuple_sha256=hashlib.sha256(repr(sorted(tuples)).encode()).hexdigest(),reserve_sha256=hashlib.sha256(active).hexdigest()))
    # Rejections execute production matching and the complete serializer walker.
    seen=C.c_uint32();r=rows[0]
    for label,owner,definition,x,y in [('moved ship',r['owner'],r['definition'],r['x']+1,r['y']),('wrong owner',31,r['definition'],r['x'],r['y']),('wrong definition',r['owner'],65535,r['x'],r['y']),('NaN coordinate',r['owner'],r['definition'],math.nan,r['y'])]:
        assert lib.SizeFixtureMatch(owner,definition,x,y,C.byref(seen))==0;negative.append(label)
    original=bytes(buf.raw[:used]);position=rows[0]['position_at']
    golden=C.create_string_buffer(original);assert lib.SizeFixtureRewrite(golden,len(original),error,len(error))==1
    ai=next(row for row in rows if row['owner']==1)
    for label,offset,value in [('serialized moved human',position,struct.pack('<f',r['x']+1)),('serialized out of bounds',position,struct.pack('<f',2048.5)),
                              ('serialized moved AI',ai['position_at'],struct.pack('<f',ai['x']+1)),('serialized AI NaN',ai['position_at'],struct.pack('<f',math.nan)),
                              ('mismatched source HEAD',48,struct.pack('<I',512))]:
        mutated=bytearray(original);mutated[offset:offset+len(value)]=value;raw=C.create_string_buffer(bytes(mutated));assert lib.SizeFixtureRewrite(raw,len(mutated),error,len(error))==0;negative.append(label)
    truncated=C.create_string_buffer(original[:-1]);assert lib.SizeFixtureRewrite(truncated,len(original)-1,error,len(error))==0;negative.append('truncated scene')
    for size in [0,255,257,800,4096,65536,-1]:
        s.worldSize=size;assert lib.SizeFixtureScene(C.byref(s),buf,len(buf),error,len(error))==0
        assert lib.WorldSettingsBuildPlan(C.byref(s),123,error,len(error))==0
        negative.append(f'unsupported size {size}')
    result=dict(scope=__doc__,fixture_dll_sha256=sha(fixture),abi_size=56,successful_scene_cases=len(report),cases=report,rejected_cases=negative,
                ships_checked=sum(r['serialized_ships'] for r in report),preset_fleet_faction_independent_reservations=True,stock1024_ship_payloads_preserved=True,
                exact_all_ship_tuple_matcher_executed=True,game_executed=False,game_or_copy_mutated=False)
    (HERE/'world_size_test_results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ['cases','scope']}))
if __name__=='__main__':main()
