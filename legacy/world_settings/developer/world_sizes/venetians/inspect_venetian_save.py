"""Read a native save and verify the relocated Venetian town against its SCP.

Checks serialized owner identity, a single correctly anchored town, the exact
native terrain and all73 original island-local building-entry anchors. These
facts establish saved town/terrain placement, not trading or later behavior.
"""
from pathlib import Path
import argparse,hashlib,json,struct,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;PACKAGE=HERE.parents[2]
sys.path[:0]=[str(PACKAGE/'support')]
import package_world_assets as a


def sha(data):return hashlib.sha256(data).hexdigest()


def inspect(data,asset,island_id,x,y,world_size,enabled=True):
    a._require(world_size in {256,512,1024},'Unsupported selected world size')
    a._require(len(data)>=16 and data[:12].rstrip(b'\0')==b'ANNOADDON1','Expected a fully saved native ANNOADDON1 world')
    parts,trailer=a._root(data);a._require(not trailer,'Save has trailing bytes')
    basics={};states={};islands={}
    for tag,p in parts:
        if tag=='INSEL5':
            a._require(len(p)>=12,'Truncated saved island');ix,iy,w,h,ident=struct.unpack_from('<HHHHI',p)
            a._require(ident not in islands and w and h and ix+w<=world_size and iy+h<=world_size,'Invalid saved island bounds/ID')
            islands[ident]=(ix,iy,w,h,p)
        elif tag=='SPIELER':
            a._require(len(p)>=8,'Truncated saved player');version,ident=struct.unpack_from('<II',p)
            a._require(version==0 and ident<32,'Unsupported saved player prefix')
            fs=list(a._fields(p,8));a._require(fs,'Empty saved player record')
            target=basics if fs[0][0]=='HEAD' else states
            a._require(ident not in target,'Duplicate saved player record');target[ident]=fs
    venetians=[]
    for ident,fs in basics.items():
        head=a._one(fs,'HEAD');a._require(len(head)==108,'Unsupported saved player HEAD')
        typ=struct.unpack_from('<I',head)[0];volk=a._one(fs,'VOLK');alias=a._one(fs,'ALIAS')
        if typ==16 or volk==b'VENECIA\0' or alias==b'VENEZIA01\0':
            a._require(typ==16 and volk==b'VENECIA\0' and alias==b'VENEZIA01\0','Conflicting saved Venetian identity')
            venetians.append(ident)
    a._require(len(venetians)==int(enabled),'Saved Venetian presence differs from selected setting')
    if not enabled:
        a._require(not any(b'VENEZIA01\0'==p for fs in states.values()for k,p in fs),'Disabled Venetian state remains')
        return dict(passed=True,enabled=False,venetian_players=0,actual_save_parser=True)
    ident=venetians[0];a._require(ident==5 and ident in states,'Stock Venetian player identity/state differs')
    fs=states[ident];controller=a._one(fs,'COMP')
    a._require(len(controller)>=9 and struct.unpack_from('<II',controller)==(16,ident) and controller[-1]==0,'Saved Venetian controller is not the native selected owner')
    options={}
    for setting in controller[8:-1].split(b'\0'):
        key,separator,value=setting.partition(b'=')
        a._require(separator and key and key not in options,'Saved Venetian controller options are malformed or duplicated')
        options[key]=value
    a._require(options.get(b'SUSPEND')==b'0','Saved Venetian controller is suspended or its suspension status is missing')
    cities=[p for k,p in fs if k=='STADT2'];a._require(len(cities)==1,'Expected exactly one saved Venetian town')
    city=cities[0];a._require(len(city)>=6,'Truncated saved Venetian city')
    slot,anchor_x,anchor_y=struct.unpack_from('<HHH',city)
    a._require(slot==0 and (anchor_x,anchor_y)==(x+28,y+33),'Venetian town anchor was not relocated with selected island')
    a._require(island_id in islands,'Selected Venetian island ID is missing')
    ix,iy,w,h,island=islands[island_id];a._require((ix,iy,w,h)==(x,y,80,80),'Saved Venetian island geometry differs from preview')
    containing=[i for i,(sx,sy,sw,sh,_)in islands.items()if sx<=anchor_x<sx+sw and sy<=anchor_y<sy+sh]
    a._require(containing==[island_id],'Venetian town is attached to a different or overlapping island')
    expected=a.inspect_venetian(asset);saved_terrain=list(a._chunks(island,12,len(island)))
    heights=a._tile_grid(saved_terrain,'HEIGHT',80,80,1)
    a._require(heights==expected['heights'],'Saved Venetian terrain differs from extracted stock town island')
    expected_fields=list(a._fields(expected['city'],6));city_fields=list(a._fields(city,6))
    a._require(a._one(city_fields,'HEAD2')[4:36]==a._one(expected_fields,'HEAD2')[4:36],'Saved Venetian town name differs')
    entries=list(a._fields(a._one(city_fields,'PROD'),0));anchors=[]
    for k,p in entries:
        a._require(k=='ENTRY' and len(p)>=4,'Unsupported saved Venetian building entry')
        bx,by=struct.unpack_from('<HH',p)
        a._require(bx<80 and by<80,'Saved Venetian building anchor leaves its local island')
        anchors.append((bx,by))
    missing=sorted(set(expected['building_anchors'])-set(anchors))
    a._require(not missing,'Initial Venetian building entries are missing from save: '+repr(missing))
    # No other player may own a city on the dedicated Venetian island.
    foreign=[]
    for other,other_fields in states.items():
        if other==ident:continue
        for key,p in other_fields:
            if key=='STADT2':
                a._require(len(p)>=6,'Truncated foreign city')
                _,cx,cy=struct.unpack_from('<HHH',p)
                if x<=cx<x+80 and y<=cy<y+80:foreign.append(dict(owner=other,anchor=[cx,cy]))
    a._require(not foreign,'Another player owns a town on the dedicated Venetian island')
    return dict(passed=True,enabled=True,player_id=ident,native_type=16,native_culture_name='VENECIA',alias='VENEZIA01',island_id=island_id,island_geometry=[x,y,80,80],city_anchor=[anchor_x,anchor_y],city_count=1,terrain_height_sha256=sha(heights),terrain_exact=True,source_building_entries=73,saved_building_entries=len(entries),all_initial_building_anchors_saved=True,city_id3_sha256=sha(a._one(city_fields,'ID3')),source_city_id3_sha256=sha(a._one(expected_fields,'ID3')),controller_sha256=sha(controller),serialized_suspend=0,serialized_controller_options={k.decode('ascii'):p.decode('ascii')for k,p in options.items()},current_controller_activity_verified=False,foreign_towns_on_venetian_island=foreign,actual_save_parser=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--save',type=Path,required=True);parser.add_argument('--island-id',type=int,required=True);parser.add_argument('--x',type=int,required=True);parser.add_argument('--y',type=int,required=True);parser.add_argument('--world-size',type=int,required=True);parser.add_argument('--disabled',action='store_true');parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    data=args.save.read_bytes();asset=(PACKAGE/'assets'/a.ASSET).read_bytes()
    result=inspect(data,asset,args.island_id,args.x,args.y,args.world_size,not args.disabled)
    result.update(scope=__doc__,save_path=str(args.save.resolve()),save_sha256=sha(data),asset_sha256=sha(asset),inspector_sha256=sha(Path(__file__).read_bytes()),behavior_verified=False)
    args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
