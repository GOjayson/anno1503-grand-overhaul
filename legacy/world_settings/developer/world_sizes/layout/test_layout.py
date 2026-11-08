"""Exercise exact production selection/layout includes in a local native fixture.

Only fixture memory and this new proof directory change. No Anno process,
runtime hooks, scene staging, game files, backup or earlier package is used.
The selection prelude in the fixture is an explicit test boundary; this is
not a replacement for full-runtime, native-loader or live-game validation.
"""
from pathlib import Path
import collections,ctypes as C,hashlib,json,math,re,statistics,time
HERE=Path(__file__).resolve().parent
PACKAGE=HERE.parents[2]
SOURCE=PACKAGE/'developer/source/engine_resume/ai_food/experiment_runtime'
FIELDS='id x y width height templateIndex cropMask mineralMask cultures climate'.split()
class Island(C.Structure):_fields_=[(n,C.c_uint32) for n in FIELDS]
class Settings(C.Structure):
    _fields_=[(n,C.c_uint32 if n in ('size','cultures','factions') else C.c_int32) for n in 'size difficulty islandSize islandCount spacing aiCount cultures factions startingMoney startingFleet aiDifficulty plantFertility mineralFertility worldSize'.split()]
def settings(world=1024,mode=3,count=24,gap=0,cultures=0,factions=0,**extra):
    s=Settings(C.sizeof(Settings),1,mode,count,gap,0,cultures,factions,30000,0,0,1,1,world)
    for k,v in extra.items():setattr(s,k,v)
    return s
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def raw(a):return C.string_at(C.addressof(a),C.sizeof(a))
def rows(a,count):return [{n:int(getattr(r,n)) for n in FIELDS} for r in a[:count]]
def separated(a,b,g):return a['x']+a['width']+g<=b['x'] or b['x']+b['width']+g<=a['x'] or a['y']+a['height']+g<=b['y'] or b['y']+b['height']+g<=a['y']
def catalogue():
    fields='width height climate cultures oreSlots whales excludedNative sizeChoices fertileLand'.split()
    result=[]
    for match in re.finditer(r'^\{"([^"\n]+)",((?:\d+,){8}\d+),\{', (SOURCE/'world_catalogue.h').read_text(),re.M):
        result.append(dict(path=match[1],**dict(zip(fields,map(int,match[2].split(','))))))
    text=(SOURCE/'world_factions.h').read_text()
    for name,key in [('wsTemplateFactions','faction'),('wsTemplateFactionSizes','factionSize')]:
        values=list(map(int,re.search(name+r'\[\]=\{([^}]+)\}',text)[1].split(',')))
        assert len(values)==len(result)
        for row,value in zip(result,values):row[key]=value
    return result
def metric(a,w):
    total=sum(r['width']*r['height'] for r in a)
    centers=[(r['x']+r['width']/2,r['y']+r['height']/2) for r in a]
    halves=[]
    for axis,extent,other in [('x','width','height'),('y','height','width')]:
        low=sum(max(0,min(r[axis]+r[extent],w/2)-r[axis])*r[other] for r in a)
        halves.extend([low/total,1-low/total])
    gap=[]
    for y in range(w//64,w,w//32):
        for x in range(w//64,w,w//32):
            gap.append(min(math.hypot(max(r['x']-x,0,x-r['x']-r['width']),max(r['y']-y,0,y-r['y']-r['height'])) for r in a))
    return dict(bounding_width=max(r['x']+r['width'] for r in a)-min(r['x'] for r in a),bounding_height=max(r['y']+r['height'] for r in a)-min(r['y'] for r in a),center_quadrant_counts=[sum((x>=w/2)==bool(q&1) and (y>=w/2)==bool(q&2) for x,y in centers) for q in range(4)],land_share_four_halves=halves,maximum_sampled_ocean_distance_to_land=max(gap),mean_sampled_ocean_distance_to_land=statistics.mean(gap),ocean_sample_grid='32x32; rectangle bounds, not exact coastline')
def main():
    started=time.perf_counter();templates=catalogue();build=json.loads((HERE/'fixture_build.json').read_text())
    for name,digest in build['input_sha256'].items():assert sha(PACKAGE/name)==digest
    dll=HERE/'_build/layout_fixture.dll';assert sha(dll)==build['fixture_dll_sha256']
    lib=C.CDLL(str(dll));P=C.POINTER
    lib.FixtureABI.restype=C.c_uint32;assert lib.FixtureABI()==C.sizeof(Settings)==56
    lib.FixtureCatalogue.restype=C.c_uint32;assert lib.FixtureCatalogue()==len(templates)==444
    lib.FixtureReserves.argtypes=[P(Settings),P(Island)];lib.FixtureReserves.restype=C.c_int
    lib.FixtureEligible.argtypes=[P(Settings),C.c_uint32];lib.FixtureEligible.restype=C.c_int
    lib.FixtureChoose.argtypes=[P(Settings),C.c_uint32,C.c_uint32,C.c_uint32]+[C.c_int]*5;lib.FixtureChoose.restype=C.c_int
    lib.FixtureFills.argtypes=[P(Settings),C.c_uint32,P(Island)];lib.FixtureFills.restype=C.c_int
    lib.LayoutPack.argtypes=[P(Settings),P(Island),C.c_uint32,C.c_uint32,P(Island)];lib.LayoutPack.restype=C.c_int
    lib.LayoutCompact.argtypes=[P(Settings),P(Island),C.c_uint32,P(Island)];lib.LayoutCompact.restype=C.c_int
    lib.SelectPlan.argtypes=[P(Settings),C.c_uint32,P(Island),P(C.c_uint32)];lib.SelectPlan.restype=C.c_int
    def reserves(s):
        a=(Island*32)();n=lib.FixtureReserves(C.byref(s),a);assert n>0;return rows(a,n)
    def choose(s,seed,attempt,culture=0,climate=-1,ore=0,whale=0,empty=1,faction=0):return lib.FixtureChoose(C.byref(s),seed,attempt,culture,climate,ore,whale,empty,faction)
    def validate(a,s,essential=False):
        rsv=reserves(s);seenclimate=cultures=crops=minerals=whales=0;factions=collections.Counter()
        for i,r in enumerate(a):
            t=templates[r['templateIndex']]
            assert r['id']==i and r['x']%8==r['y']%8==0
            assert r['x']>=s.spacing and r['y']>=s.spacing
            assert r['x']+r['width']+s.spacing<=s.worldSize and r['y']+r['height']+s.spacing<=s.worldSize
            assert all(separated(r,p,s.spacing) for p in a[:i]+rsv)
            assert all(r[k]==t[k] for k in ['width','height','cultures','climate'])
            assert lib.FixtureEligible(C.byref(s),r['templateIndex'])
            assert (r['mineralMask']&~[0,0x45,0x65,0x41,0x43,0x4b][r['climate']])==0
            assert r['mineralMask'].bit_count()<=t['oreSlots']
            seenclimate|=1<<r['climate'];cultures|=r['cultures'];crops|=r['cropMask'];minerals|=r['mineralMask'];whales+=t['whales'];factions[t['faction']]+=1
        if essential:assert seenclimate==63 and cultures==s.cultures and crops==0x1ffff and minerals&0x2f==0x2f and whales and factions[1]==bool(s.factions&1) and factions[2]==bool(s.factions&2)
    cases=[];rejects=[];times=[];independent=0;quality=[]
    configs=[]
    for w in (256,512,1024,2048):
        for mode in range(5):
            counts=(6,8) if w==256 else ((12,24) if w==512 else (12,24))
            for count in counts:configs.append((w,mode,count,0,0,0))
    configs.extend([(512,0,16,8,0,3),(512,4,12,0,255,3),(1024,0,24,8,255,3),(1024,1,24,8,255,3),(1024,2,16,0,255,3),(1024,3,24,16,255,3),(1024,4,24,8,255,3),(1024,0,96,0,0,0),(1024,0,128,0,0,0)])
    configs.extend([(2048,m,24,16,255,3) for m in range(5)])
    configs.extend([(2048,0,96,0,0,0),(2048,0,128,0,0,0)])
    for config in configs:
        s=settings(*config)
        for number in range(16):
            seed=(0x15032026+number*0x9e3779b9)&0xffffffff;a=(Island*128)();again=(Island*128)();at=C.c_uint32();at2=C.c_uint32();start=time.perf_counter();n=lib.SelectPlan(C.byref(s),seed,a,C.byref(at));elapsed=(time.perf_counter()-start)*1000
            n2=lib.SelectPlan(C.byref(s),seed,again,C.byref(at2));assert n2==n
            if not n:rejects.append(dict(configuration=config,seed=seed,reason='bounded selection/fit rejected; not an engine-limit claim'));continue
            assert at.value==at2.value and raw(a)==raw(again);times.append(elapsed)
            ar=rows(a,n);validate(ar,s,True)
            repacked=(Island*128)();repeat=(Island*128)();compact=(Island*128)()
            assert lib.LayoutPack(C.byref(s),a,n,seed,repacked)==1
            assert lib.LayoutPack(C.byref(s),a,n,seed,repeat)==1 and raw(repacked)==raw(repeat)
            rr=rows(repacked,n);validate(rr,s,True)
            assert all(all(x[k]==y[k] for k in FIELDS if k not in ('id','x','y')) for x,y in zip(ar,rr))
            assert lib.LayoutCompact(C.byref(s),a,n,compact)==1
            independent+=1
            for variation in [{'difficulty':0,'startingFleet':2,'startingMoney':100000,'aiCount':3,'aiDifficulty':3,'plantFertility':0,'mineralFertility':3},{'difficulty':2,'startingFleet':1,'startingMoney':10000,'plantFertility':2,'mineralFertility':0}]:
                changed=settings(*config,**variation);other=(Island*128)();assert lib.LayoutPack(C.byref(changed),a,n,seed,other)==1 and raw(repacked)==raw(other)
            m=metric(rr,s.worldSize);cm=metric(rows(compact,n),s.worldSize)
            row=dict(configuration=config,seed=seed,attempt=at.value,count=n,selection_plan_sha256=hashlib.sha256(raw(a)[:n*C.sizeof(Island)]).hexdigest(),geometry_plan_sha256=hashlib.sha256(raw(repacked)[:n*C.sizeof(Island)]).hexdigest(),climate_counts=[sum(r['climate']==c for r in ar) for c in range(6)],width_counts=dict(collections.Counter(r['width'] for r in ar)),elapsed_select_ms=elapsed,quality=m,compact_quality=cm)
            cases.append(row)
            if s.worldSize>=512 and n==24 and s.cultures==0 and s.factions==0 and s.spacing==0:quality.append(row)
    assert len(cases)>=100 and {c['configuration'][0] for c in cases}=={256,512,1024,2048}
    assert all(min(q['quality']['land_share_four_halves'])>0 for q in quality)
    assert all(q['quality']['bounding_width']>=q['configuration'][0]*0.75 and q['quality']['bounding_height']>=q['configuration'][0]*0.75 for q in quality)
    # Fill-only sequence checks do not assert that24large islands fit each map.
    fill_proofs=[];choices=0
    for w in (256,512,1024,2048):
        for mode in range(5):
            for seed in range(1,17):
                s=settings(w,mode,24);a=(Island*128)();assert lib.FixtureFills(C.byref(s),seed,a)==24
                count=[0]*6
                for r in rows(a,24):count[r['climate']]+=1;assert max(count)-min(count)<=1
                assert count==[4]*6;fill_proofs.append(dict(world=w,mode=mode,seed=seed,climate_counts=count))
    # Strict never downgrades; first Lenient phase matches largest per group;
    # final fallback chooses smallest actual template matching that filter.
    for mode in (0,1,2,3,4):
        s=settings(1024,mode,24,cultures=255,factions=3)
        for c in range(6):
            candidates=[(i,t) for i,t in enumerate(templates) if t['faction']==0 and not t['excludedNative'] and not t['cultures'] and t['climate']==c and (t['fertileLand'] or c==0)]
            for seed in range(1,33):
                i=choose(s,seed,0,climate=c);assert i>=0;choices+=1;t=templates[i]
                if mode<3:assert t['sizeChoices']&(1<<mode)
                if mode==4:assert t['width']==max(t['width'] for _,t in candidates)
                if mode==4:
                    j=choose(s,seed,31,climate=c);assert templates[j]['width']==min(t['width'] for _,t in candidates);choices+=1
        # Fixed stock Venetian town is an explicit exception in all modes.
        assert lib.FixtureEligible(C.byref(s),443)==1
        assert choose(s,7,0,faction=2,empty=0)==443
        s.factions=1;assert lib.FixtureEligible(C.byref(s),443)==0
    # Native cultures cannot leak through disabled options; ordinary fillers
    # never include a pirate/Venetian town.
    eligibility=0
    for mode in range(5):
        s=settings(1024,mode,24,cultures=0,factions=0)
        for i,t in enumerate(templates):
            eligible=lib.FixtureEligible(C.byref(s),i);eligibility+=1
            if t['cultures'] or t['faction']:assert not eligible
    contrasts=[]
    for w,count in [(512,24),(1024,24)]:
        for seed in (12345,0x15032026):
            strict=settings(w,2,count);lenient=settings(w,4,count);a=(Island*128)();b=(Island*128)();at=C.c_uint32();bt=C.c_uint32()
            sn=lib.SelectPlan(C.byref(strict),seed,a,C.byref(at));ln=lib.SelectPlan(C.byref(lenient),seed,b,C.byref(bt))
            if not sn and ln:
                validate(rows(b,ln),lenient,True);contrasts.append(dict(world=w,count=count,seed=seed,strict_rejected=True,lenient_attempt=bt.value,lenient_widths=[r.width for r in b[:ln]],lenient_climates=[r.climate for r in b[:ln]]))
    assert len(contrasts)>=2
    # Exact1-row corruption / invalid dimensions fail closed.
    malformed=0;s=settings();base=(Island*1)(Island(0,0,0,64,64,0,0,0,0,4));out=(Island*128)()
    for world in (0,255,768,4096,65536):
        bad=settings(world);assert lib.LayoutPack(C.byref(bad),base,1,7,out)==0;assert lib.SelectPlan(C.byref(bad),7,out,C.byref(C.c_uint32()))==0;malformed+=1
    for width,height in [(0,64),(64,0),(1025,64),(0xffffffff,64),(64,0xffffffff)]:
        bad=(Island*1)(Island(0,0,0,width,height,0,0,0,0,4));assert lib.LayoutPack(C.byref(s),bad,1,7,out)==0;malformed+=1
    for gap in (-1,513,1024,0x7fffffff):
        bad=settings(gap=gap);assert lib.LayoutPack(C.byref(bad),base,1,7,out)==0;malformed+=1
    assert lib.LayoutPack(C.byref(s),base,0,7,out)==0;malformed+=1
    assert lib.LayoutPack(C.byref(s),base,129,7,out)==0;malformed+=1
    # Regeneratingseed changes actual deterministic geometry for a valid plan.
    s=settings(1024,0,24);a=(Island*128)();assert lib.FixtureFills(C.byref(s),7,a)==24
    hashes=[]
    for seed in range(1,17):
        o=(Island*128)();assert lib.LayoutPack(C.byref(s),a,24,seed,o)==1;hashes.append(hashlib.sha256(raw(o)).hexdigest())
    assert len(set(hashes))==16
    for name,digest in build['input_sha256'].items():assert sha(PACKAGE/name)==digest
    result=dict(passed=True,scope=__doc__,game_executed=False,game_or_copy_mutated=False,native_fixture_cases=len(cases),exact_repeat_cases=len(cases),bounded_selection_rejection_cases=len(rejects),layout_option_independence_cases=independent*2,fill_sequence_cases=len(fill_proofs),direct_policy_choices=choices,eligibility_cases=eligibility,malformed_rejection_cases=malformed,regeneration_distinct_plans=len(set(hashes)),supported_world_sizes=[256,512,1024,2048],unsupported_4096_rejected=True,template_count=len(templates),settings_abi_bytes=C.sizeof(Settings),strict_lenient_contrasts=contrasts,quality_24island_cases=len(quality),quality_minimum_bounding_width_fraction=min(q['quality']['bounding_width']/q['configuration'][0] for q in quality),quality_minimum_bounding_height_fraction=min(q['quality']['bounding_height']/q['configuration'][0] for q in quality),quality_minimum_land_share_any_half=min(min(q['quality']['land_share_four_halves']) for q in quality),selection_ms=dict(minimum=min(times),median=statistics.median(times),maximum=max(times)),elapsed_seconds=time.perf_counter()-started,input_sha256=build['input_sha256'],cases=cases,rejected_cases=rejects,fill_proofs=fill_proofs)
    (HERE/'layout_results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('cases','rejected_cases','fill_proofs','input_sha256')},indent=2))
if __name__=='__main__':main()
