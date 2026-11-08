"""Synthetic bounded-save inspector mutation tests; no game is executed."""
from pathlib import Path
import hashlib,json,struct,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;PACKAGE=HERE.parents[2]
sys.path[:0]=[str(HERE),str(PACKAGE/'support')]
import generate_venetian_assets as g
import inspect_venetian_save as v
import package_world_assets as a
GAME=next(p for p in HERE.parents if (p/'Anno1503.exe').is_file() and not (p/'.anno1503-worldsettings-test-copy.json').is_file())


def sha(d):return hashlib.sha256(d).hexdigest()


def main():
    source=(GAME/g.SOURCE).read_bytes();parts,_=g.envelope(source,True);parts=[(k,p)for k,p,*_ in parts]
    asset=(PACKAGE/'assets'/a.ASSET).read_bytes()
    def packed(ps):return g.chunk('ANNOADDON1',b''.join(g.chunk(k,p)for k,p in ps))
    def player5(p):return len(p)>=8 and p[:8]==struct.pack('<II',0,5)
    def state5(p):return player5(p) and next(g.fields(p))[0]!='HEAD'
    def change_city(ps,fn):
        result=[]
        for k,p in ps:
            if k=='SPIELER'and state5(p):
                p=p[:8]+b''.join(g.field(tag,fn(value)if tag=='STADT2'else value,head==10)for tag,value,_,head in g.fields(p))
            result.append((k,p))
        return result
    base=packed(parts);positive=v.inspect(base,asset,28,184,288,1024)
    assert positive['passed'] and positive['saved_building_entries']==73
    disabled=packed([(k,p)for k,p in parts if not(k=='SPIELER'and player5(p))])
    assert v.inspect(disabled,asset,0,0,0,1024,False)['passed']
    mutations=[]
    def rejected(label,ps,**options):
        kw=dict(island_id=28,x=184,y=288,world_size=1024);kw.update(options)
        try:v.inspect(packed(ps),asset,**kw)
        except ValueError:mutations.append(label)
        else:raise AssertionError('Mutation accepted: '+label)
    rejected('wrong_selected_island_id',parts,island_id=27)
    rejected('wrong_preview_origin',parts,x=192)
    rejected('unsupported_world_size',parts,world_size=2048)
    rejected('anchor_on_old_world_position',change_city(parts,lambda c:c[:2]+struct.pack('<HH',28,33)+c[6:]))
    rejected('wrong_city_slot',change_city(parts,lambda c:struct.pack('<H',1)+c[2:]))
    rejected('duplicate_city',[(k,p+(next(g.field(t,z,h==10)for t,z,_,h in g.fields(p)if t=='STADT2')if k=='SPIELER'and state5(p)else b''))for k,p in parts])
    rejected('missing_city',[(k,p[:8]+b''.join(g.field(t,z,h==10)for t,z,_,h in g.fields(p)if t!='STADT2')if k=='SPIELER'and state5(p)else p)for k,p in parts])
    rejected('foreign_owner_identity',[(k,p.replace(b'VENEZIA01\0',b'VENEZIA02\0'))if k=='SPIELER'and player5(p)else(k,p)for k,p in parts])
    rejected('suspended_controller',[(k,p.replace(b'SUSPEND=0\0',b'SUSPEND=1\0'))if k=='SPIELER'and state5(p)else(k,p)for k,p in parts])
    def altered_building(c,remove=False):
        output=c[:6]
        for t,p,_,h in g.fields(c,6):
            if t=='PROD':
                entries=list(g.fields(p,0))
                if remove:entries=entries[1:]
                else:entries=[(entries[0][0],struct.pack('<HH',80,33)+entries[0][1][4:],entries[0][2],entries[0][3])]+entries[1:]
                p=b''.join(g.field(k,z,head==10)for k,z,_,head in entries)
            output+=g.field(t,p,h==10)
        return output
    rejected('building_out_of_bounds',change_city(parts,altered_building))
    rejected('missing_initial_building',change_city(parts,lambda c:altered_building(c,True)))
    bad=[]
    for k,p in parts:
        if k=='INSEL5':
            items=list(g.chunks(p,12,len(p)));changed=False;new=p[:12]
            for t,z,*_ in items:
                if t=='HEIGHT'and not changed:z=z[:6]+bytes([z[6]^1])+z[7:];changed=True
                new+=g.chunk(t,z)
            p=new
        bad.append((k,p))
    rejected('terrain_mismatch',bad)
    foreign_city=next(z for k,p in parts if k=='SPIELER'and state5(p)for t,z,*_ in g.fields(p)if t=='STADT2')
    rejected('foreign_city_on_venetian_island',parts+[('SPIELER',struct.pack('<II',0,29)+g.field('STADT2',foreign_city,True))])
    result=dict(scope=__doc__,passed=True,game_executed=False,synthetic_positive_cases=2,rejected_cases=mutations,original_source_sha256=sha(source),asset_sha256=sha(asset),inspector_sha256=sha((HERE/'inspect_venetian_save.py').read_bytes()),test_sha256=sha(Path(__file__).read_bytes()))
    (HERE/'save_inspector_tests.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,synthetic_positive_cases=2,rejected_cases=len(mutations),game_executed=False),indent=2))


if __name__=='__main__':main()
