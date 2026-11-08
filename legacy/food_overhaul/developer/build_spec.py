"""Rebuild the combined specification from the original inspection workspace.

python developer/build_spec.py INSPECTION_WORKSPACE
No original game binaries are included in the package.
"""
import base64
import json
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import food_mod as mod
from pe_builder import extend_pe, pe_info
fm, tr = mod.fm, mod.tr


def patches(before, after, origin=0):
    result=[]; at=0
    while at < min(len(before),len(after)):
        if before[at] == after[at]: at+=1; continue
        start=at
        while at < min(len(before),len(after)) and before[at] != after[at]: at+=1
        result.append(dict(offset=origin+start,before=before[start:at].hex(),after=after[start:at].hex()))
    return result


def binary_change(before, after):
    return dict(patches=patches(before,after), result_size=len(after),
                append_base64=base64.b64encode(after[len(before):]).decode())


def branch(data, at, target, kind=b'\xe9', length=5):
    *_, offset = pe_info(data)
    return offset(at), data[offset(at):offset(at)+length], kind+struct.pack('<i',target-at-5)+b'\x90'*(length-5)


def old_binary(data, entry):
    assert fm.sha(data)==entry['before_sha256']
    return fm.patched_bytes(data,entry['patches'])+base64.b64decode(entry['append_base64'])


def build(base):
    files=base/'anno1503_binary_inspection/files'
    definitions=base/'anno1503_definitions_inspection'
    fish=json.loads((base/'anno1503_fish_mod/fish_patch.json').read_bytes())
    game=json.loads((base/'anno1503_game_meat_test/game_patch.json').read_bytes())
    market=json.loads((base/'anno1503_food_market/game_patch.json').read_bytes())
    previous=json.loads((HERE/'compat-0.4.0.json').read_bytes())
    previous041=json.loads((HERE/'compat-0.4.1.json').read_bytes())
    stages=['vanilla','fish-0.1.4','game-0.2.2','market-0.3-full','market-0.3-fish-only','combined-0.4.0','combined-0.4.1',mod.FINAL_STATE]
    spec=dict(version=mod.VERSION, description='Unified five-food diet, consumer category menus, six-slot market, visible prices and improved layout.',
              exe_sha256=fm.file_sha(files/'Anno1503.exe'), text_files=fish['text_files'],
              icon_source_files=fish['icon_source_files'], native_modules=[],files={},archives=[],artwork_hashes={})
    for name in mod.artwork.ICON_SLOTS:
        spec['artwork_hashes'][name]=fm.file_sha(HERE.parent/'assets'/(name.replace('-','_')+'_icon.json'))
    natives={}
    ai_by_name={m['name']:m for m in game['ai_modules']}
    for name in ['AnnoGame.dll','AnnoWelt.dll','View.dll','AnnoFrame.dll','CompLogic.dll','CompLogicClassic.dll']:
        vanilla=(files/name).read_bytes()
        fishdata=fm.patched_bytes(vanilla,fish['engine_patches']) if name=='AnnoGame.dll' else vanilla
        gamedata=fm.patched_bytes(fishdata,game['engine_patches']) if name=='AnnoGame.dll' else fishdata
        if name in ai_by_name:gamedata=fm.patched_bytes(gamedata,ai_by_name[name]['patches'])
        market_entry=next((m for m in market['native_modules'] if m['name']==name),None)
        marketdata=old_binary(gamedata,market_entry) if market_entry else gamedata
        old_entry=next((m for m in previous['native_modules'] if m['name']==name),None)
        old_combined=mod.apply_native(vanilla,old_entry) if old_entry else vanilla
        old041=mod.apply_native(vanilla,next(m for m in previous041['native_modules'] if m['name']==name))
        natives[name]=[vanilla,fishdata,gamedata,marketdata,marketdata,old_combined,old041,old041]
    # Rebuild original modules, keeping source fingerprints for every supported
    # upgrade. The house selector's original body remains available as fallback.
    world=natives['AnnoWelt.dll'][0]
    def world_edits(names):
        *_,offset=pe_info(world)
        result=[branch(world,0x81020,names['market_enabled']),branch(world,0x810b0,names['market_set_enabled']),
                branch(world,0xb4fb0,names['food_record_sale'],length=6)]
        at=0xad3df
        code=bytes.fromhex('4889d94889c24189e84189f9')
        code+=b'\xe8'+struct.pack('<i',names['food_income_total']-(at+len(code)+5))
        code+=bytes.fromhex('488b7b28')
        code+=b'\xe9'+struct.pack('<i',0xad65a-(at+len(code)+5))
        result.append((offset(at),world[offset(at):offset(0xad65a)],code.ljust(0xad65a-at,b'\x90')))
        at=offset(0xa6f33)
        assert world[at:at+4]==bytes.fromhex('66894628')
        result.append((at,world[at:at+4],bytes.fromhex('48894628')))
        at=0x8120f
        code=bytes.fromhex('4889f90fb6542458')
        code+=b'\xe8'+struct.pack('<i',names['market_load_flags']-(at+len(code)+5))
        code+=b'\xe9'+struct.pack('<i',0x81258-(at+len(code)+5))
        result.append((offset(at),world[offset(at):offset(0x81258)],code.ljust(0x81258-at,b'\x90')))
        at=0x81284
        code=b'\xe8'+struct.pack('<i',names['market_pack_flags']-at-5)+bytes.fromhex('4c8bd241b801000000')
        result.append((offset(at),world[offset(at):offset(0x81296)],code.ljust(0x81296-at,b'\x90')))
        at=offset(0xf9ee8+0x1b0)
        assert struct.unpack_from('<Q',world,at)[0]==0x180088b10
        result.append((at,world[at:at+8],struct.pack('<Q',0x180000000+names['house_choose_good'])))
        return result
    final_world,world_symbols,world_section=extend_pe(world,HERE/'world.S',
        {'NATIVE_NOTIFY':0x842e0,'NATIVE_HOUSE_CHOOSE':0x88b10,'NATIVE_HOUSE_SCORE':0x88120,
         'NATIVE_SALE_BODY':0xb4fb8,'NATIVE_SALE_RETURN':0xb4fef},edits=world_edits)
    natives['AnnoWelt.dll'][-1]=final_world
    frame=natives['AnnoFrame.dll'][0]
    final_frame,frame_symbols,frame_section=extend_pe(frame,HERE/'frame.S',edits=lambda names:[
        branch(frame,rva,names['market_command_count'],kind=b'\xe8',length=7) for rva in [0x78667,0x7fa7e]])
    natives['AnnoFrame.dll'][-1]=final_frame
    view=natives['View.dll'][0]
    def view_edits(names):
        *_,offset=pe_info(view)
        result=[branch(view,0x4ab56,names['ui_create'],kind=b'\xe8')]
        for relative,label in [(0xe0,'ui_set_prod'),(0xf0,'ui_layout'),(0x120,'ui_tick'),(0x148,'ui_update')]:
            at=offset(0xa6b20+relative)
            result.append((at,view[at:at+8],struct.pack('<Q',0x180000000+names[label])))
        # All category changes are confined to View: city inventory, the
        # general goods chooser, and the ship's eight-visible-cell chooser.
        # No stock, need, production or saved-game ID changes.
        result += [branch(view,0x39677,names['category_next_edi'],kind=b'\xe8'),
                   branch(view,0x78edc,names['category_next_esi'],kind=b'\xe8'),
                   branch(view,0x39621,names['category_grid_gfx'],kind=b'\xe8',length=9),
                   branch(view,0x78e0a,names['category_city_gfx'],kind=b'\xe8',length=10)]
        def immediate(rva, before, after):
            at=offset(rva);assert view[at:at+len(before)]==before
            result.append((at,before,after))
        for rva,before,after in [(0x38a0d,45,44),(0x39ea2,25,23),
                                  (0x789b0,45,44),(0x7a1c8,25,23),
                                  (0x65878,45,44),(0x66fc5,25,23),
                                  (0x6681b,8,12),(0x65a2d,8,12),(0x65a32,8,12),
                                  (0x659e1,16,20)]:
            immediate(rva,bytes([before]),bytes([after]))
        # Use a static 20-entry category list. The original ship object's
        # 16-entry member array and following scroll state remain in bounds.
        for rva,prefix,length in [(0x659bc,b'\x48\x8d\x05',7),
                                   (0x65c98,b'\x4c\x8d\x3d',7)]:
            code=prefix+struct.pack('<i',names['consumer_goods']-rva-7)
            at=offset(rva);result.append((at,view[at:at+length],code))
        # R14 is the current scroll offset; replace object-relative arithmetic
        # with the same immutable category list used by redraw/search.
        rva=0x65a82
        code=b'\x4c\x8d\x3d'+struct.pack('<i',names['consumer_goods']-rva-7)
        code+=bytes.fromhex('4f8d3cb7') # lea r15,[r15+r14*4]
        at=offset(rva);result.append((at,view[at:offset(0x65a90)],code.ljust(14,b'\x90')))
        immediate(0x659ff,b'\x8e',b'\x8c') # the next cell lies outside an 8-cell page
        return result
    native={'NATIVE_INIT' :0x54ef0,'NATIVE_SET_PROD':0x54300,'NATIVE_LAYOUT':0x4a910,
            'NATIVE_UPDATE':0x4ab90,'NATIVE_TICK':0x54440,'NATIVE_SET_OVERLAY':0x58d0,
            'GOOD_GFX':0xce490,'GOOD_LABELS':0xce010,'ITOA_IAT':0xa1288}
    final_view,view_symbols,view_section=extend_pe(view,HERE/'view.S',native,edits=view_edits)
    natives['View.dll'][-1]=final_view
    for name,variants in natives.items():
        target=variants[-1]
        prior=next((m for m in market['native_modules'] if m['name']==name),{})
        changes={fm.sha(data):binary_change(data,target) for data in variants if data!=target}
        item=dict(name=name,after_sha256=fm.sha(target),sources={s:fm.sha(d) for s,d in zip(stages,variants)},changes=changes)
        if name=='View.dll':item.update(symbols=view_symbols,section=view_section)
        elif name=='AnnoWelt.dll':item.update(symbols=world_symbols,section=world_section)
        elif name=='AnnoFrame.dll':item.update(symbols=frame_symbols,section=frame_section)
        elif prior:item.update(symbols=prior['symbols'],section=prior['section'])
        spec['native_modules'].append(item)
    for name in ['Data/BGruppen.dat',*fish['text_files'],*fish['icon_source_files']]:
        original=(definitions/'assets'/name).read_bytes() if name in fish['text_files'] else (files/name).read_bytes()
        if name=='Data/BGruppen.dat':
            one=fm.split_food_demand(original);two=tr.add_definition(one)
            three=tr.diet(two);three_test=tr.diet(two,'fish-only');target=three
        elif name in fish['text_files']:
            one=fm.update_labels(original);two=tr.game_labels(one);three=tr.food_labels(two);three_test=three;target=three
        else:
            one=fm.update_icon_sources(original);two=tr.game_icon_sources(one);three=three_test=two
            # The previous 0.3 runtime UI had these extra frames; synchronize
            # the developer source group sizes as well in the unified mod.
            text=two.decode('cp1252')
            import re
            for group,old,new in [('WARENICONS_ROHSTOFF',22,23),('WARENICONS_ROHSTOFF_GREY',22,23),
                                  ('WARENICONS_BAUMATERIAL',4,5),('WARENICONS_BAUMATERIAL_GREY',4,5)]:
                pattern=re.compile(r'(Access:[ \t]*"'+group+r'"(?:(?!Access:).)*?Segments:[ \t]*)'+str(old)+r'([ \t]*,[ \t]*1)',re.S)
                text,count=pattern.subn(r'\g<1>'+str(new)+r'\2',text);assert count==1,(name,group)
            target=text.encode('cp1252')
        variants=[original,one,two,three,three_test,target,target,target]
        spec['files'][name]=dict(sources={s:fm.sha(d) for s,d in zip(stages,variants)},after_sha256=fm.sha(target))
    manifest=json.loads((definitions/'definitions-manifest.json').read_text(encoding='utf-8-sig'))
    for source in manifest['definitions']:
        name=source['source_name'];original=(definitions/source['zip_entry']).read_bytes()
        f=next(a for a in fish['archives'] if a['name']==name);g=next(a for a in game['archives'] if a['name']==name);m=next(a for a in market['archives'] if a['name']==name)
        origin=f['region_offset'];one=fm.patched_bytes(original,f['patches'],origin);two=fm.patched_bytes(one,g['patches'],origin);three=fm.patched_bytes(two,m['patches'],origin)
        variants=[original,one,two,three,three,three,three,three]
        assert fm.sha(three)==m['after_sha256']
        spec['archives'].append(dict(name=name,source_size=f['source_size'],region_offset=origin,region_size=len(original),
            sources={s:fm.sha(d) for s,d in zip(stages,variants)},after_sha256=fm.sha(three),
            changes={fm.sha(d):patches(d,three,origin) for d in variants}))
    return spec


if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit(__doc__)
    spec=build(Path(sys.argv[1]).resolve())
    (HERE.parent/'food_patch.json').write_text(json.dumps(spec,indent=2)+'\n')
    print('Created standalone vanilla-to-food-mod and prototype-upgrade specification.')
