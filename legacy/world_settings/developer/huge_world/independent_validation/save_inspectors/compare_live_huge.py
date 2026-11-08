"""Compare captured game-owned previews with committed state and an actual save.

This is an independent read-only serialized/captured-state check. The operator
must separately observe or obtain the user's report of preview rendering,
Regenerate, Start and native saving. Diagnostic JSON alone does not prove UI
actions. No game process is opened and no game, save, source, copy or backup is
written. Only a new additive report under this outside-package folder is made.
"""
from pathlib import Path
from array import array
import argparse,hashlib,importlib.util,json,math,re,struct,sys

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
GAME=HERE.parents[2]
PACKAGE=GAME/'WorldSettings_Work/anno1503_food_world_dev8'
PRIVATE=PACKAGE/'developer/source/engine_resume/ai_food/experiment_runtime'
SF=['size','difficulty','islandSize','islandCount','spacing','aiCount','cultures',
    'factions','startingMoney','startingFleet','aiDifficulty','plantFertility','mineralFertility','worldSize']
IF=['id','x','y','width','height','templateIndex','cropMask','mineralMask','cultures','climate']
ERRORS=['factory_error','hook_error','ai_loader_error','ai_profile_error']
SNAPSHOT_SIZE=5192


def require(ok,message):
    if not ok:raise ValueError(message)


def sha(data):return hashlib.sha256(data).hexdigest()
def file_sha(path):return sha(path.read_bytes())


def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    spec.loader.exec_module(module);return module


FERTILITY=load_module('huge_actual_fertility_inspector',HERE/'inspect_fertility_huge.py')
START=load_module('huge_actual_start_inspector',HERE/'inspect_start_huge.py')
DECODER=None


def configure_package(path):
    global PACKAGE,PRIVATE,DECODER
    PACKAGE=Path(path).resolve();PRIVATE=PACKAGE/'developer/source/engine_resume/ai_food/experiment_runtime'
    DECODER=load_module('huge_actual_snapshot_decoder',PACKAGE/'activation/preview_snapshot.py')


def stable_bytes(path):
    a=path.stat();data=path.read_bytes();b=path.stat()
    require((a.st_size,a.st_mtime_ns,a.st_ino)==(b.st_size,b.st_mtime_ns,b.st_ino),'Input changed while reading: '+str(path))
    require(len(data)==b.st_size,'Input was not read completely: '+str(path))
    return data


def json_bytes(data):return json.loads(data.decode('utf-8-sig'))


def integer(value):return type(value) is int


def snapshot(diag,state):
    require(isinstance(diag,dict) and isinstance(diag.get('preview'),dict),'Diagnostic has no captured preview')
    p=diag['preview'];s=p.get('settings');rows=p.get('islands')
    require(isinstance(s,dict) and set(s)==set(SF),'Preview settings fields differ from ABI56')
    require(all(integer(s[k]) for k in SF),'Non-integer preview setting')
    require(s['size']==56 and 1<=s['islandCount']<=128 and 0<=s['spacing']<=256 and s['worldSize']in[256,512,1024,2048],'Invalid preview settings dimensions')
    require(s['difficulty'] in range(3) and s['islandSize'] in range(5) and s['aiCount'] in range(4),'Invalid preview difficulty, size or AI count')
    require(0<=s['cultures']<=255 and 0<=s['factions']<=3,'Invalid culture/faction selection')
    require(s['startingMoney'] in [10000,30000,50000,80000,100000] and s['startingFleet'] in range(3),'Invalid money/fleet selection')
    require(all(s[k] in range(4) for k in ['aiDifficulty','plantFertility','mineralFertility']),'Invalid AI/fertility selection')
    require(p.get('state')==state and p.get('state_name')==DECODER.STATES[state],'Captured preview state differs from expected '+DECODER.STATES[state])
    require(integer(p.get('seed')) and 0<p['seed']<=0xffffffff,'Invalid nonzero menu seed')
    require(integer(p.get('count')) and p['count']==s['islandCount'],'Preview count and settings disagree')
    require(isinstance(rows,list) and len(rows)==p['count'],'Preview row count differs')
    raw=bytearray(SNAPSHOT_SIZE);struct.pack_into('<4I',raw,0,SNAPSHOT_SIZE,state,p['seed'],p['count'])
    struct.pack_into('<I5i2I6i',raw,16,*(s[k] for k in SF))
    for i,row in enumerate(rows):
        require(isinstance(row,dict) and set(row)==set(IF),'Preview island fields differ from ABI40')
        require(all(integer(row[k]) and 0<=row[k]<=0xffffffff for k in IF),'Non-u32 preview island field')
        struct.pack_into('<10I',raw,72+i*40,*(row[k] for k in IF))
    decoded=DECODER.decode(bytes(raw))
    require(decoded['plan_sha256']==p.get('plan_sha256'),'Preview plan hash does not match its exact40-byte rows')
    require(decoded['snapshot_sha256']==p.get('snapshot_sha256'),'Preview snapshot hash does not match its exact5192-byte envelope')
    return decoded


def check_diagnostic(diag,expected_runtime,expected_spec,expected_exe,expected_engine_count):
    require(integer(diag.get('pid')) and diag['pid']>0,'Invalid diagnostic PID')
    require(integer(diag.get('process_creation_time')) and diag['process_creation_time']>0,'Invalid process creation identity')
    require(diag.get('runtime_sha256')==expected_runtime,'Diagnostic runtime differs from the current executed package')
    require(diag.get('world_spec_sha256')==expected_spec,'Diagnostic executed specification differs from the current package')
    require(diag.get('executable_sha256')==expected_exe,'Diagnostic executable differs from the inspected History Edition executable')
    require(diag.get('installed_files_modified') is False,'Diagnostic does not retain the no-installed-file-write scope')
    require(all(diag.get(k)=='' for k in ERRORS),'A native factory/hook/AI error is present or unavailable')
    require(diag.get('hook_site_count')==9 and diag.get('central_war_site_state')=='guard-jump','Expected nine guarded native hooks are not established')
    require(sum(len(v) for v in diag.get('hook_bytes',{}).values())==9,'Diagnostic hook byte inventory differs')
    require(type(expected_engine_count)is int and expected_engine_count>104,'Executed engine profile omits the navigation capacity repair')
    require(diag.get('engine_state')=='expanded' and diag.get('engine_patch_count')==expected_engine_count and diag.get('engine_patch_status')==expected_engine_count,'Diagnostic does not establish the entire executed expanded native engine transaction')


def same_process(a,b):
    require(a['pid']==b['pid'] and a['process_creation_time']==b['process_creation_time'],'Captured states came from different game processes')
    require(a.get('copy_root')==b.get('copy_root'),'Captured states came from different marked game copies')


def canonical_heights(parts,width,height):
    result=bytearray(width*height);seen=bytearray(width*height)
    for item in parts:
        if item.tag!='HEIGHT':continue
        require(len(item.payload)>=6,'Truncated native HEIGHT rectangle')
        x,y,w,h=struct.unpack_from('<HHBB',item.payload)
        require(w and h and x+w<=width and y+h<=height and len(item.payload)==6+w*h,'Invalid native HEIGHT rectangle')
        for yy in range(h):
            for xx in range(w):
                at=(y+yy)*width+x+xx
                require(not seen[at],'Overlapping native HEIGHT rectangles')
                seen[at]=1;result[at]=item.payload[6+yy*w+xx]
    require(all(seen),'Native HEIGHT rectangles do not cover the entire island')
    return bytes(result)


def thumbnail(heights,width,height,size=64):
    require(width>=size and height>=size,'Unsupported preview reduction dimensions')
    result=bytearray(size*size//8)
    for y in range(size):
        top,bottom=y*height//size,(y+1)*height//size
        for x in range(size):
            left,right=x*width//size,(x+1)*width//size
            if any(heights[yy*width+xx]>=48 for yy in range(top,bottom) for xx in range(left,right)):
                bit=y*size+x;result[bit//8]|=1<<(bit%8)
    return bytes(result)


def saved_islands(data):
    root=FERTILITY.chunk(data,0,len(data));result={}
    require(root.tag=='ANNOADDON1' and root.end==len(data),'Expected one complete native full save')
    for item in FERTILITY.chunks(data,16,root.end):
        if item.tag!='INSEL5':continue
        require(len(item.payload)>=12,'Truncated saved island geometry')
        x,y,width,height,ident=struct.unpack_from('<HHHHI',item.payload)
        require(ident not in result,'Duplicate native saved island identity')
        parts=list(FERTILITY.chunks(item.payload,12,len(item.payload)))
        info=FERTILITY.one(parts,'INFO');require(len(info)==12 and info[0]<6,'Invalid saved island climate')
        result[ident]=dict(id=ident,x=x,y=y,width=width,height=height,climate=info[0],
                          heights=canonical_heights(parts,width,height))
    return result


def catalogue():
    path=PRIVATE/'world_catalogue.h';rows=[]
    pattern=re.compile(r'^\{"([^"\r\n]*)",(\d+(?:,\d+){8}),\{([\d,]+)\}\},?$',re.M)
    for index,m in enumerate(pattern.finditer(path.read_text(encoding='utf-8'))):
        values=list(map(int,m[2].split(',')))
        rows.append(dict(index=index,path=json.loads('"'+m[1]+'"').replace('\\','/'),
                         width=values[0],height=values[1],climate=values[2],cultures=values[3],
                         sha256=bytes(map(int,m[3].split(','))).hex()))
    require(len(rows)==444,'Incomplete actual compiled catalogue')
    return rows


def reserves(world_size):
    require(world_size in [256,512,1024,2048],'Unsupported reserve world size')
    if world_size==256:
        return [dict(x=x-24,y=200,width=49,height=49)for x in[128,32,80,176,224]]
    if world_size in (512,2048):
        q=world_size//4
        return [dict(x=x-24,y=y-24,width=49,height=49)for x,y in[(world_size//2,world_size//3),(q,q),(3*q,q),(3*q,3*q),(q,3*q)]]
    text=(PRIVATE/'world_ship_reserves.h').read_text()
    values=[tuple(map(int,m.groups())) for m in re.finditer(r'\{0,(\d+),(\d+),(\d+),(\d+),0,0,0,0,0\}',text)]
    require(len(values)==7,'The stock ship reserve inventory differs')
    return [dict(x=x,y=y,width=w,height=h) for x,y,w,h in values]


def separated(a,b,gap):
    return (a['x']+a['width']+gap<=b['x'] or b['x']+b['width']+gap<=a['x'] or
            a['y']+a['height']+gap<=b['y'] or b['y']+b['height']+gap<=a['y'])


def rectangle_metrics(rows,spacing,world_size):
    middle=world_size/2
    for i,r in enumerate(rows):
        require(r['id']==i and r['x']%8==r['y']%8==0,'Native grid/island identity differs')
        require(r['x']>=spacing and r['y']>=spacing and r['x']+r['width']+spacing<=world_size and r['y']+r['height']+spacing<=world_size,'Native bounds/minimum border spacing failed')
        for other in rows[:i]:require(separated(r,other,spacing),'Native island rectangles overlap or violate the minimum spacing')
        for reserve in reserves(world_size):require(separated(r,reserve,spacing),'Native island intersects a selected-world ship reserve')
    total=sum(r['width']*r['height'] for r in rows)
    centers=[(r['x']+r['width']/2,r['y']+r['height']/2) for r in rows]
    quadrants=[sum((x>=middle)==bool(q&1) and (y>=middle)==bool(q&2) for x,y in centers) for q in range(4)]
    half_shares=[]
    for axis,extent in [('x','width'),('y','height')]:
        low=sum(max(0,min(r[axis]+r[extent],middle)-r[axis])*r['height' if axis=='x' else 'width'] for r in rows)
        half_shares.extend([low/total,1-low/total])
    distances=[]
    for y in range(16,world_size,32):
        for x in range(16,world_size,32):
            distances.append(min(math.hypot(max(r['x']-x,0,x-r['x']-r['width']),max(r['y']-y,0,y-r['y']-r['height'])) for r in rows))
    return dict(scope='Actual saved island bounding rectangles, verified identical to the preview. Ocean-margin cells are included in these footprint metrics.',
                native_grid_and_requested_minimum_spacing_passed=True,selected_world_ship_reserves_clear=True,world_size=world_size,ship_reserve_count=len(reserves(world_size)),
                bounding_width=max(r['x']+r['width'] for r in rows)-min(r['x'] for r in rows),
                bounding_height=max(r['y']+r['height'] for r in rows)-min(r['y'] for r in rows),
                island_centers_in_quadrants=quadrants,rectangle_area_share_in_halves=half_shares,
                quadrant_order=['top-left','top-right','bottom-left','bottom-right'],half_order=['left','right','top','bottom'],
                rectangle_footprint_fraction_of_map=total/(world_size*world_size),
                sampled_maximum_distance_to_an_island_rectangle=max(distances),sample_grid_step=32,
                sampled_points=len(distances),navigation_proven=False)


def distance_transform_1d(values):
    """Exact squared Euclidean lower envelope for finite integer site costs."""
    n=len(values);v=[0]*n;z=[0.0]*(n+1);k=0;z[0]=-math.inf;z[1]=math.inf
    for q in range(1,n):
        while True:
            p=v[k];s=((values[q]+q*q)-(values[p]+p*p))/(2*(q-p))
            if s>z[k]:break
            k-=1
        k+=1;v[k]=q;z[k]=s;z[k+1]=math.inf
    result=[0]*n;k=0
    for q in range(n):
        while z[k+1]<q:k+=1
        delta=q-v[k];result[q]=delta*delta+values[v[k]]
    return result


def sampled_land_distances(mask,width,height,xs,ys):
    require(len(mask)==width*height and any(mask),'Missing native land for the coast-distance metric')
    infinity=2*(width*width+height*height)+1
    horizontal=array('I',[0])*(height*len(xs))
    for y in range(height):
        row=mask[y*width:(y+1)*width]
        transformed=distance_transform_1d([0 if b else infinity for b in row])
        for at,x in enumerate(xs):horizontal[y*len(xs)+at]=transformed[x]
    result=[]
    for at,x in enumerate(xs):
        transformed=distance_transform_1d([horizontal[y*len(xs)+at] for y in range(height)])
        result.extend(math.sqrt(transformed[y]) for y in ys)
    return result


def native_land_metrics(islands,world_size):
    mask=bytearray(world_size*world_size);halves=[0,0,0,0];quadrants=[0,0,0,0];total=0;middle=world_size/2
    minimum_x=minimum_y=world_size;maximum_x=maximum_y=-1
    for r in islands.values():
        require(0<=r['x']<=world_size-r['width'] and 0<=r['y']<=world_size-r['height'],'Native terrain leaves the world')
        for local_y in range(r['height']):
            y=r['y']+local_y
            for local_x in range(r['width']):
                if r['heights'][local_y*r['width']+local_x]<48:continue
                x=r['x']+local_x;at=y*world_size+x
                require(not mask[at],'Native saved land overlaps');mask[at]=1;total+=1
                halves[int(x>=middle)]+=1;halves[2+int(y>=middle)]+=1
                quadrants[int(x>=middle)+2*int(y>=middle)]+=1
                minimum_x=min(minimum_x,x);minimum_y=min(minimum_y,y)
                maximum_x=max(maximum_x,x);maximum_y=max(maximum_y,y)
    require(total>0,'Native save has no land')
    distances=sampled_land_distances(mask,world_size,world_size,list(range(16,world_size,32)),list(range(16,world_size,32)))
    return dict(scope='Actual saved HEIGHT>=48 native land tiles. Coast distance is Euclidean distance between native tile centers on a32-tile sample grid; it is not sailing accessibility.',
                native_land_tiles=total,native_land_fraction_of_map=total/(world_size*world_size),world_size=world_size,
                native_land_tiles_in_quadrants=quadrants,native_land_share_in_halves=[n/total for n in halves],
                quadrant_order=['top-left','top-right','bottom-left','bottom-right'],half_order=['left','right','top','bottom'],
                native_land_bounding_width=maximum_x-minimum_x+1,native_land_bounding_height=maximum_y-minimum_y+1,
                sampled_maximum_distance_to_native_land=max(distances),sampled_mean_distance_to_native_land=sum(distances)/len(distances),
                sample_grid_step=32,sampled_points=len(distances),navigation_proven=False)


def far_half_geometry(islands,world_size):
    """Report actual native objects beyond the old1024 lookup boundary."""
    rows=list(islands.values())
    beyond_x=[r['id'] for r in rows if r['x']+r['width']>1024]
    beyond_y=[r['id'] for r in rows if r['y']+r['height']>1024]
    wholly_x=[r['id'] for r in rows if r['x']>=1024]
    wholly_y=[r['id'] for r in rows if r['y']>=1024]
    far_land=[0,0,0]
    for r in rows:
        for y in range(r['height']):
            for x in range(r['width']):
                if r['heights'][y*r['width']+x]<48:continue
                gx,gy=r['x']+x,r['y']+y
                far_land[0]+=gx>=1024;far_land[1]+=gy>=1024;far_land[2]+=gx>=1024 and gy>=1024
    return dict(world_size=world_size,islands_crossing_or_beyond_x1024=beyond_x,
        islands_crossing_or_beyond_y1024=beyond_y,islands_wholly_beyond_x1024=wholly_x,
        islands_wholly_beyond_y1024=wholly_y,native_land_tiles_x1024_or_greater=far_land[0],
        native_land_tiles_y1024_or_greater=far_land[1],native_land_tiles_both1024_or_greater=far_land[2],
        old1024_square_is_not_the_entire_test_world=bool(far_land[0] and far_land[1]),
        access_rendering_or_navigation_proven_by_serialized_geometry=False)


def saved_ships(data,world_size):
    root,trailer=START.read_container(data)
    require(root.tag=='ANNOADDON1' and not trailer,'Expected one full native save for ships')
    ships=[];ids=set()
    for player in START.chunks(data,16,root.end):
        if player.tag!='SPIELER':continue
        require(len(player.payload)>=8,'Truncated saved player prefix')
        version,owner=struct.unpack_from('<II',player.payload)
        require(version==0 and owner<32,'Unsupported player prefix')
        for tag,p,at in START.fields(player.payload,8):
            if tag not in ('SCHIFF','SCHI64'):continue
            if tag=='SCHIFF':
                require(len(p)>=16,'Truncated SCHIFF');ident,definition=struct.unpack_from('<HH',p);native_owner=p[4];x,y=struct.unpack_from('<ff',p,8);prefix=16
            else:
                require(len(p)>=20,'Truncated SCHI64');ident=struct.unpack_from('<I',p)[0];definition=struct.unpack_from('<H',p,4)[0];native_owner=p[6];x,y=struct.unpack_from('<ff',p,12);prefix=20
            require(ident!=0xffffffff and ident not in ids,'Duplicate/unassigned saved ship ID');ids.add(ident)
            require(native_owner==owner,'Saved ship owner differs from its containing player')
            require(math.isfinite(x) and math.isfinite(y) and 0<=x<world_size and 0<=y<world_size,'Saved ship leaves native world')
            fields=START.fields(p,prefix);head=START.one(fields,'HEAD');cargo=START.one(fields,'WAREN')
            require(len(head)==16 and len(cargo)%8==0,'Unsupported saved ship state/cargo shape')
            ships.append(dict(id=ident,owner=owner,definition=definition,native_tag=tag,x=x,y=y,
                far_x=x>=1024,far_y=y>=1024,equipped_cannons=head[8],health=head[9],
                cargo=[dict(good=struct.unpack_from('<H',cargo,i)[0],quantity=struct.unpack_from('<H',cargo,i+2)[0])for i in range(0,len(cargo),8)]))
    require(ships,'Native save has no ships')
    return dict(count=len(ships),ships=sorted(ships,key=lambda r:r['id']),
        ships_in_far_x_half=sum(r['far_x']for r in ships),ships_in_far_y_half=sum(r['far_y']for r in ships),
        positions_are_saved_snapshots_only=True,navigation_verified=False)


def compare(before,after,committed,data,context):
    expected_runtime=context['runtime_sha256'];expected_spec=context['world_spec_sha256'];expected_exe=context['exe_sha256'];expected_engine_count=context['engine_patch_count']
    require(before is not None or after is not None,'At least one ready-state diagnostic is required')
    ready=after if after is not None else before
    for diag in [d for d in [before,after,committed] if d is not None]:
        check_diagnostic(diag,expected_runtime,expected_spec,expected_exe,expected_engine_count);same_process(ready,diag)
    selected=snapshot(ready,1);final=snapshot(committed,3)
    for key in ['seed','count','settings','islands','plan_sha256']:
        require(selected[key]==final[key],'Start/commit changed the displayed preview: '+key)
    require(committed.get('ai_profile_validated') is True and committed.get('validated_ai_count')==selected['settings']['aiCount'] and committed.get('ai_profile_status')==selected['settings']['aiCount']+1,'Committed native AI/controller validation does not match selected count')
    regeneration=None
    if before is not None and after is not None:
        first=snapshot(before,1);second=snapshot(after,1)
        require(first['settings']==second['settings'],'Regeneration capture also changed settings')
        require(first['seed']!=second['seed'] and first['plan_sha256']!=second['plan_sha256'],'Two captured previews do not establish a changed seed and map')
        regeneration=dict(captured_seed_changed=True,captured_plan_changed=True,settings_unchanged=True,
                          first_seed=first['seed'],second_seed=second['seed'],first_plan_sha256=first['plan_sha256'],
                          second_plan_sha256=second['plan_sha256'],ui_button_action_proven_by_this_check=False)
    s=selected['settings'];rows=selected['islands'];native=saved_islands(data)
    root=FERTILITY.chunk(data,0,len(data));top=list(FERTILITY.chunks(data,16,root.end));world=FERTILITY.one(top,'WELT')
    require(len(world)==32,'Native saved WELT header is unsupported')
    world_width,world_height=struct.unpack_from('<II',world)
    require((world_width,world_height)==(s['worldSize'],s['worldSize']),'Native saved world dimensions differ from selected preview')
    require(sorted(native)==list(range(selected['count'])),'Saved island IDs/count differ from the preview')
    fertility=FERTILITY.inspect(data,FERTILITY.MODES[s['plantFertility']],FERTILITY.MODES[s['mineralFertility']])
    catalog=context['catalogue'];coasts=context['coasts'];coast_rows=coasts['templates'];per_island=[];height_exact=True;coast_exact=True
    for i,p in enumerate(rows):
        saved=native[i];resources=fertility['islands'][i];template=catalog[p['templateIndex']];coast=coast_rows[p['templateIndex']]
        for key in ['id','x','y','width','height','climate']:require(saved[key]==p[key],'Saved island differs from the displayed preview: '+str(i)+' '+key)
        for key in ['width','height','climate','cultures']:require(template[key]==p[key],'Preview row differs from compiled template: '+key)
        require(coast['index']==p['templateIndex'] and coast['path']==template['path'] and coast['template_sha256']==template['sha256'],'Generated coast source identity differs from preview template')
        require(all(coast[k]==p[k] for k in ['width','height','climate']),'Generated coast dimensions/climate differ from preview')
        expected_crop=(p['cropMask']|0xf009)&0x1fff
        require(int(resources['saved_crop_name_mask'],0)==expected_crop,'Saved crop flags differ from the preview plan: '+str(i))
        require(int(resources['positive_saved_mineral_mask'],0)==p['mineralMask'],'Saved positive mineral types differ from the preview plan: '+str(i))
        height_hash=sha(saved['heights']);mask=thumbnail(saved['heights'],p['width'],p['height'],coasts['resolution']);mask_hash=sha(mask)
        equal_height=height_hash==coast['height_sha256'];equal_coast=mask_hash==coast['mask_sha256']
        height_exact &= equal_height;coast_exact &= equal_coast
        per_island.append(dict(id=i,x=p['x'],y=p['y'],width=p['width'],height=p['height'],climate=p['climate'],
            template_index=p['templateIndex'],template_path=template['path'],planned_culture_mask=p['cultures'],
            saved_geometry_matches_preview=True,saved_crop_flags_match_preview=True,saved_positive_mineral_types_match_preview=True,
            planned_crop_mask=hex(p['cropMask']),saved_crop_mask=resources['saved_crop_name_mask'],
            planned_mineral_mask=hex(p['mineralMask']),saved_positive_mineral_mask=resources['positive_saved_mineral_mask'],
            saved_height_sha256=height_hash,selected_template_height_sha256=coast['height_sha256'],
            full_native_height_matches_selected_template=equal_height,
            saved_land_thumbnail_sha256=mask_hash,compiled_preview_thumbnail_sha256=coast['mask_sha256'],
            native_land_thumbnail_matches_preview=equal_coast))
    far_half=far_half_geometry(native,s['worldSize'])
    if s['worldSize']==2048:
        require(far_half['old1024_square_is_not_the_entire_test_world'],'Huge test lacks native land beyond both old1024 axes')
    result=dict(scope=__doc__,runtime_sha256=expected_runtime,executed_world_spec_sha256=expected_spec,engine_patch_count=expected_engine_count,expanded_engine_verified_in_all_captures=True,
        source_executable_sha256=expected_exe,pid=ready['pid'],process_creation_time=ready['process_creation_time'],
        settings=s,seed=selected['seed'],island_count=selected['count'],preview_plan_sha256=selected['plan_sha256'],
        regeneration=regeneration,preview_to_commit=dict(ready_state=1,committed_state=3,
            same_process_identity=True,exact56_byte_settings_seed_count_and_all40_byte_island_rows_retained=True,
            fresh_native_controller_validation_passed=True,ui_render_or_start_action_proven_by_this_check=False),
        native_saved_islands=per_island,
        native_saved_world_size_matches_preview=True,native_saved_world_dimensions=dict(native_chunk='WELT',native_chunk_bytes=32,width=world_width,height=world_height,selected_world_size=s['worldSize'],matches_preview=True),
        native_saved_geometry_crop_and_positive_mineral_masks_match_preview=True,
        all_saved_height_arrays_match_selected_templates=bool(height_exact),all_saved_coast_thumbnails_match_preview=bool(coast_exact),
        terrain_mismatch_scope=None if height_exact else 'HEIGHT changed relative to the selected template. This checker does not assume whether native gameplay/terraforming caused the change; exact source-terrain identity is not established for affected islands.',
        layout_quality=dict(saved_rectangles=rectangle_metrics([native[i] for i in range(len(native))],s['spacing'],s['worldSize']),
                            saved_native_land=native_land_metrics(native,s['worldSize'])),
        fertility=fertility,all_essential_crops_and_positive_mineral_goods_present=True,
        starting_fleet=START.inspect(data,['easy','medium','hard'][s['difficulty']],s['startingMoney'],['single','war','merchant'][s['startingFleet']],observed=True),
        far_half_geometry=far_half,
        saved_ship_inventory=saved_ships(data,s['worldSize']),
        crop_or_mineral_quantity_multipliers_claimed=False,initial_cash_or_ship_coordinates_claimed=False,
        native_culture_ownership_inspected_by_this_check=False,actual_harvesting_mining_or_navigation_tested=False,
        actual_game_run_proven_by_this_check=False,game_or_copy_modified_by_this_check=False,
        passed=bool(height_exact and coast_exact))
    return result


def package_context(world_spec_path=None):
    world_spec_path=Path(world_spec_path)if world_spec_path else PACKAGE/'world_patch.json'
    world_data=stable_bytes(world_spec_path);world=json_bytes(world_data)
    runtime=file_sha(PACKAGE/'native/AnnoWorldSettings.dll')
    require(world['version']=='0.11.0-dev.1' and world['settings_abi_size']==56,'The current package is not the inspected dev8 ABI56 build')
    require(world['payloads']['native/AnnoWorldSettings.dll']==runtime,'Packaged runtime differs from current world specification')
    engine_data=stable_bytes(PACKAGE/'developer/huge_world/runtime_engine_edits.json');engine=json_bytes(engine_data)
    require(world.get('expanded_engine_patch_count')==engine.get('engine_instruction_count')==len(engine.get('edits',[])) and world.get('expanded_engine_plan_sha256')==sha(engine_data),'Executed engine specification differs from its complete native transaction')
    require(world['payloads']['native/AnnoWelt.world.dll']==engine.get('patched_welt_sha256')==file_sha(PACKAGE/'native/AnnoWelt.world.dll'),'Copied native engine payload differs from the reviewed expanded profile')
    build=json_bytes(stable_bytes(PACKAGE/'developer/source/runtime_dev3/build_result.json'))
    require(build['sha256']==runtime and build['abi_size']==56 and build['native_hooks']==9 and len(build['source_sha256'])>=42,'Compiled runtime metadata differs')
    fingerprints={name.replace('\\','/'):digest for name,digest in build['source_sha256'].items()}
    for key,digest in fingerprints.items():
        target=(PACKAGE/'developer/source'/key).resolve()
        require(target.is_relative_to((PACKAGE/'developer/source').resolve()),'Compiled source path escapes package')
        require(file_sha(target)==digest,'Current compiled source differs: '+key)
    coasts_data=stable_bytes(PACKAGE/'developer/layout_preview/coasts/coastline_manifest.json');coasts=json_bytes(coasts_data)
    require(coasts['resolution']==64 and coasts['template_count']==444 and coasts['all_template_hashes_verified'],'Incomplete generated coast manifest')
    require(coasts['generated_header_sha256']==file_sha(PRIVATE/'world_preview_coasts.h') and coasts['catalogue_sha256']==file_sha(PRIVATE/'world_catalogue.h'),'Coast manifest does not bind current compiled thumbnails/catalogue')
    require(world['exe_sha256']==file_sha(GAME/'Anno1503.exe'),'Original executable fingerprint differs')
    return dict(runtime_sha256=runtime,world_spec_sha256=sha(world_data),exe_sha256=world['exe_sha256'],engine_patch_count=engine['engine_instruction_count'],
                catalogue=catalogue(),coasts=coasts,coast_manifest_sha256=sha(coasts_data),
                compiler_metadata_sha256=file_sha(PACKAGE/'developer/source/runtime_dev3/build_result.json'),world_spec_path=world_spec_path)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,default=PACKAGE);parser.add_argument('--preview-before',type=Path);parser.add_argument('--preview-after',type=Path)
    parser.add_argument('--save',type=Path,required=True);parser.add_argument('--committed',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--world-spec',type=Path,help='Exact executed world_patch.json snapshot; defaults to current package metadata')
    args=parser.parse_args();configure_package(args.package);output=args.output.resolve()
    require(output.is_relative_to(HERE) and not output.exists(),'Report must be a new file under the outside-package huge_engine_work/validation folder')
    paths={'save':args.save,'committed':args.committed}
    if args.preview_before:paths['preview_before']=args.preview_before
    if args.preview_after:paths['preview_after']=args.preview_after
    require(all(path.resolve()!=output for path in paths.values()),'Report cannot replace an input')
    raw={key:stable_bytes(path) for key,path in paths.items()};context=package_context(args.world_spec)
    result=compare(json_bytes(raw['preview_before']) if 'preview_before' in raw else None,
                   json_bytes(raw['preview_after']) if 'preview_after' in raw else None,
                   json_bytes(raw['committed']),raw['save'],context)
    result.update(save_path=str(args.save.resolve()),save_sha256=sha(raw['save']),save_bytes=len(raw['save']),
                  inspector_sha256=file_sha(Path(__file__)),
                  preview_snapshot_decoder_sha256=file_sha(PACKAGE/'activation/preview_snapshot.py'),
                  fertility_inspector_sha256=file_sha(HERE/'inspect_fertility_huge.py'),
                  coastline_manifest_sha256=context['coast_manifest_sha256'],
                  compiled_runtime_metadata_sha256=context['compiler_metadata_sha256'],
                  input_sha256={key:dict(path=str(paths[key].resolve()),sha256=sha(data)) for key,data in raw.items()})
    for key,path in paths.items():require(file_sha(path)==sha(raw[key]),'Input changed during comparison: '+str(path))
    require(file_sha(context['world_spec_path'])==context['world_spec_sha256'],'Executed metadata changed during comparison')
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(passed=result['passed'],save_sha256=result['save_sha256'],island_count=result['island_count'],
                         preview_plan_sha256=result['preview_plan_sha256'],
                         all_height_arrays_match=result['all_saved_height_arrays_match_selected_templates'],
                         native_land_metrics=result['layout_quality']['saved_native_land'],report=str(output)),indent=2))
    if not result['passed']:raise SystemExit(2)


if __name__=='__main__':main()
