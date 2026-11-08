"""Read-only native fertility/ore certificate, including dimensions through2048.

The caller supplies the settings selected in-game. Native ANBAU lower13 flags,
physical occurrence IDs, saved whole quantities and island/climate geometry are
checked. Current native disabled flags, actual harvesting/mining, accessibility
and the UI/reload event itself cannot be proved by this offline inspector.
"""
from pathlib import Path
from collections import Counter
from dataclasses import dataclass
import argparse,hashlib,json,math,re,struct

CROPS=['GETREIDE','TABAKBAUM','GEWUERZBAUM','FLACHSBAUM','ZUCKERROHR',
       'BAUMWOLLE','WEINTRAUBEN','KAKAOBAUM','HOPFENBAUM','SEIDENRAUPE',
       'FARBBAUM','KRÄUTER','KARTOFFEL']
CROP_MASKS=[0x18000,0xf009,0xf949,0xf06b,0xf6b9,0xf04d]
CLIMATES=['Polar','Tundra','North','Prairie','Jungle','Steppe']
ORE_IDS={1560:'EISENERZ',1661:'EISENERZ',1561:'GOLD',1562:'SALZSTEIN',1563:'EDELSTEINE',1564:'MAMORSTEIN'}
ORE_BITS={'EISENERZ':1,'GOLD':2,'SALZSTEIN':4,'EDELSTEINE':8,'MAMORSTEIN':32}
ORE_MASKS=[0,5,37,1,3,11]
MODES=['very','medium','low','mixed']
OPTIONAL=0xff6

def require(ok,message):
    if not ok:raise ValueError(message)
def sha(data):return hashlib.sha256(data).hexdigest()
@dataclass(frozen=True)
class Chunk:
    tag:str;offset:int;payload:bytes;end:int
def chunk(data,at,end):
    require(0<=at<=end<=len(data) and end-at>=16,'Truncated native chunk')
    tag=data[at:at+12];require(re.fullmatch(rb'[A-Z0-9_]{1,12}\0*',tag) is not None,'Invalid native chunk tag')
    n=struct.unpack_from('<I',data,at+12)[0];require(n<=end-at-16,'Native chunk crosses parent')
    return Chunk(tag.rstrip(b'\0').decode('ascii'),at,data[at+16:at+16+n],at+16+n)
def chunks(data,start,end):
    at=start
    while at<end:
        item=chunk(data,at,end);yield item;at=item.end
    require(at==end,'Native children do not consume their parent')
def one(items,name):
    found=[c.payload for c in items if c.tag==name];require(len(found)==1,'Expected one '+name+' island record');return found[0]
def fields(data):
    at=0
    while at<len(data):
        require(len(data)-at>=8 and data[at:at+6]==b'ENTRY2','Unsupported occurrence entry header')
        n=struct.unpack_from('<H',data,at+6)[0];header=8
        if n>=0xff00:
            require(len(data)-at>=10,'Truncated extended occurrence size')
            n=((n&255)<<16)|struct.unpack_from('<H',data,at+8)[0];header=10
        require(n>=16 and n<=len(data)-at-header,'Truncated occurrence body')
        yield data[at+header:at+header+n];at+=header+n
    require(at==len(data),'Occurrence bodies do not consume their parent')
def fertile_land(items,width,height):
    raw=one(items,'FRUCHTBAR');require(len(raw)==width*height,'Unsupported native fertility array')
    heights=bytearray(width*height);seen=bytearray(width*height)
    for item in items:
        if item.tag!='HEIGHT':continue
        require(len(item.payload)>=6,'Truncated native height tile')
        x,y,w,h=struct.unpack_from('<HHBB',item.payload)
        require(w and h and len(item.payload)==6+w*h and x+w<=width and y+h<=height,'Invalid native height tile')
        for yy in range(h):
            for xx in range(w):
                dest=(y+yy)*width+x+xx;require(not seen[dest],'Overlapping native height tiles')
                seen[dest]=1;heights[dest]=item.payload[6+yy*w+xx]
    require(all(seen),'Native height tiles do not cover island')
    return sum(bool(v&15) and heights[i]>=48 for i,v in enumerate(raw))

def inspect(data,plant,minerals,baseline=None):
    require(plant in MODES and minerals in MODES,'Unsupported selected fertility level')
    require(32<=len(data)<=128*1024*1024,'Native full-save size is unsupported')
    root=chunk(data,0,len(data));require(root.tag=='ANNOADDON1' and root.end==len(data),'Expected one fully consumed native full save')
    top=list(chunks(data,16,root.end))
    require(not any(c.tag in ['SCENE','INSELLNK','INSELDUMMY'] for c in top),'An external/source scene cannot certify loaded fertility')
    world=one(top,'WELT');require(len(world)==32,'Unsupported native WELT header')
    world_width,world_height=struct.unpack_from('<II',world)
    require(world_width==world_height and world_width in (256,512,1024,2048),'Unsupported native world dimensions')
    islands=[];all_minerals=Counter();positive_minerals=Counter();zero_count=0;whales=0;crop_union=0;optional_count=0;quota_excess=0
    for item in top:
        if item.tag!='INSEL5':continue
        require(len(item.payload)>=12,'Truncated saved island geometry')
        x,y,width,height,ident=struct.unpack_from('<HHHHI',item.payload)
        require(0<width<=256 and 0<height<=256 and x+width<=world_width and y+height<=world_height,'Saved island leaves the supported world')
        parts=list(chunks(item.payload,12,len(item.payload)));info=one(parts,'INFO');require(len(info)==12 and info[0]<6,'Unsupported saved island climate')
        climate=info[0];raw_names=one(parts,'ANBAU')
        require(raw_names and raw_names.endswith(b'\0'),'Unterminated saved crop flags')
        names=[value.decode('cp1252') for value in raw_names.split(b'\0') if value]
        require(len(names)==len(set(names)) and all(n in CROPS for n in names),'Unknown or duplicate native saved crop flag')
        raw_mask=sum(1<<CROPS.index(n) for n in names);supported=(CROP_MASKS[climate]|0xf009)&0x1fff
        require(raw_mask&0x1009==0x1009 and not(raw_mask&~supported),'Saved crop availability violates native climate/forced flags')
        fertile=fertile_land(parts,width,height);eligible=raw_mask&CROP_MASKS[climate]&0x1fff if fertile else 0
        if climate:require(fertile>0,'A growing climate has no saved fertile land coverage')
        crop_union|=eligible;optional=raw_mask&OPTIONAL;n_optional=optional.bit_count();possible=(CROP_MASKS[climate]&OPTIONAL).bit_count()
        optional_count+=n_optional
        quota=possible if plant=='very' else ((possible+1)//2 if plant=='medium' else (1 if possible else 0))
        if plant=='very':require(raw_mask==supported,'Very fertile island is missing a supported favorable crop')
        elif plant in ['low','medium']:
            require(n_optional>=quota,'Saved favorable crop count is below the selected quota')
            quota_excess+=max(0,n_optional-quota)
        deposits=[];active=[];local_minerals=Counter();active_mask=0;coordinates=set()
        for part in parts:
            if part.tag!='OCCUR':continue
            for raw in fields(part.payload):
                packed=struct.unpack_from('<I',raw)[0];definition=(packed>>14)&0xfff
                if definition not in ORE_IDS and definition!=1559:continue
                local_x,local_y,z=struct.unpack_from('<fff',raw,4)
                require(all(math.isfinite(v) for v in [local_x,local_y,z]) and 0<=local_x<width and 0<=local_y<height,'A saved resource occurrence lies outside its island')
                if definition==1559:
                    require(b'WHALE' in raw[16:],'Saved whale lacks its native payload');whales+=1;continue
                require(len(raw)==24,'Unsupported native ore payload length')
                amount,padding,discovery=struct.unpack_from('<HHI',raw,16);require(padding==0,'Unsupported native ore payload padding')
                good=ORE_IDS[definition];bit=ORE_BITS[good];position=(local_x,local_y)
                require(position not in coordinates,'Duplicate saved mineral occurrence position');coordinates.add(position)
                all_minerals[good]+=1;local_minerals[good]+=1
                row=dict(native_figure_id=definition,good=good,saved_whole_quantity=amount,local_x=local_x,local_y=local_y,
                         generic_packed_flags=(packed>>26)&15,saved_discovery_mask=discovery)
                deposits.append(row)
                if amount:
                    require(ORE_MASKS[climate]&bit,'Positive saved mineral is unsupported in this climate')
                    require(definition!=1560,'New fertility policy must use shallow1661 for its active iron')
                    require(not(active_mask&bit),'The selected world duplicated a distinct active mineral good on one island')
                    active_mask|=bit;active.append(row);positive_minerals[good]+=1
                else:
                    require(definition==1661,'A zero-quantity non1661 deposit could regain resources on reload')
                    zero_count+=1
        slot_count=len(deposits);maximum=min(slot_count,ORE_MASKS[climate].bit_count())
        require(len(active)<=maximum,'Positive saved mineral count exceeds native distinct-good capacity')
        if minerals=='very':require(len(active)==maximum,'Very mineral fertility did not fill saved native climate/slot capacity')
        islands.append(dict(id=ident,x=x,y=y,width=width,height=height,climate=climate,climate_name=CLIMATES[climate],
            fertile_land_height_proxy_cells=fertile,saved_crop_name_mask=hex(raw_mask),eligible_saved_crop_mask=hex(eligible),
            crop_names=names,optional_favorable_crop_count=n_optional,native_optional_crop_count=possible,
            saved_mineral_slot_count=slot_count,native_distinct_good_capacity=maximum,positive_saved_mineral_count=len(active),
            positive_saved_mineral_mask=hex(active_mask),positive_saved_mineral_goods=sorted(ORE_IDS[d['native_figure_id']] for d in active),
            deposits=deposits))
    require(1<=len(islands)<=128,'Unsupported loaded island count')
    require(sorted(i['id'] for i in islands)==list(range(len(islands))),'Loaded island IDs are missing or duplicated')
    islands.sort(key=lambda i:i['id'])
    for i,a in enumerate(islands):
        for b in islands[:i]:require(a['x']+a['width']<=b['x'] or b['x']+b['width']<=a['x'] or a['y']+a['height']<=b['y'] or b['y']+b['height']<=a['y'],'Saved island rectangles overlap')
    require(crop_union==0x1fff,'Saved world is missing an essential favorable crop on supported fertile land')
    require(set(positive_minerals)==set(ORE_BITS),'Saved world is missing an essential positive mineral good')
    if minerals=='low':require(all(n==1 for n in positive_minerals.values()),'Low mineral fertility must retain exactly the five mandatory world deposits')
    if plant in ['low','medium']:require(quota_excess<=OPTIONAL.bit_count(),'Saved crop quota excess exceeds possible global essential anchors')
    require(whales>0,'Saved world has no native whale occurrence')
    report=dict(scope=__doc__,save_sha256=sha(data),bytes=len(data),selected=dict(plant_fertility=plant,mineral_fertility=minerals),
        world_width=world_width,world_height=world_height,island_count=len(islands),all_saved_mineral_records=dict(all_minerals),positive_saved_quantity_deposits=dict(positive_minerals),
        positive_saved_quantity_total=sum(positive_minerals.values()),zero_quantity_native1661_records=zero_count,
        ore_free_island_count=sum(i['positive_saved_mineral_count']==0 for i in islands),
        favorable_crop_union_on_supported_fertile_land=hex(crop_union),total_optional_favorable_crop_flags=optional_count,
        optional_crop_quota_excess_from_essential_anchors=quota_excess if plant in ['low','medium'] else None,
        saved_whale_records=whales,islands=islands,
        checks=dict(native_saved_ore_shape=True,zero_quantity_nonreserve_encoding=True,all_five_mineral_goods_positive=True,
                    all_thirteen_crop_flags_supported_with_fertile_land=True,positions_inside_nonoverlapping_islands=True),
        automatic_serialized_check=True,actual_game_run_proven_by_this_inspector=False,passed=True)
    if baseline is not None:
        require(baseline.get('passed') and baseline.get('selected')==report['selected'],'Baseline is not a matching passed fertility report')
        before=baseline.get('islands',[]);require(len(before)==len(islands),'Reload changed saved island count')
        for a,b in zip(before,islands):
            for field in ['id','x','y','width','height','climate','saved_crop_name_mask','positive_saved_mineral_mask','positive_saved_mineral_goods','saved_mineral_slot_count']:
                require(a.get(field)==b.get(field),'Reload changed per-island fertility: '+field)
            def zeroes(row):return sorted((d['local_x'],d['local_y'],d['native_figure_id']) for d in row['deposits'] if d['saved_whole_quantity']==0)
            require(zeroes(a)==zeroes(b),'Reload changed persistent mineral absence positions')
        report['baseline_comparison']=dict(before_save_sha256=baseline['save_sha256'],
            per_island_crop_flags_identical=True,per_island_positive_goods_identical=True,
            per_island_zero_quantity_positions_identical=True,
            positive_quantities_required_identical=False,
            scope='Serialized availability comparison only; the caller must establish the separate game process/load/resave event.')
    return report

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('save',type=Path)
    ap.add_argument('--plant',choices=MODES,required=True);ap.add_argument('--minerals',choices=MODES,required=True)
    ap.add_argument('--name');ap.add_argument('--baseline',type=Path);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    require(args.output.resolve()!=args.save.resolve(),'Refusing to write an inspection report over the input save')
    if args.baseline:require(args.output.resolve()!=args.baseline.resolve(),'Refusing to replace the baseline report')
    data=args.save.read_bytes()
    baseline=json.loads(args.baseline.read_bytes()) if args.baseline else None
    result=inspect(data,args.plant,args.minerals,baseline)
    result.update(save_path=str(args.save.resolve()),save_name=args.name,inspector_sha256=sha(Path(__file__).read_bytes()))
    if args.baseline:result['baseline_report_sha256']=sha(args.baseline.read_bytes())
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['passed','save_sha256','island_count','positive_saved_quantity_deposits','ore_free_island_count','total_optional_favorable_crop_flags']},indent=2))
if __name__=='__main__':main()
