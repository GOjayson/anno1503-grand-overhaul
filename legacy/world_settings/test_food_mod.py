"""Original-data installation, migration, artwork, transaction and native UI checks."""
from collections import Counter
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import food_mod as mod
import collect_crash
from developer.pe_builder import pe_info, checksum

BASE=Path(os.environ.get('ANNO_FISH_INSPECTION_BASE','/nonexistent-anno-inspections'))
PACKAGE=Path(__file__).resolve().parent


class OriginalFixture:
    def __init__(self):
        self.spec=json.loads((PACKAGE/'food_patch.json').read_bytes())
        binary=BASE/'anno1503_binary_inspection/files'
        definitions=BASE/'anno1503_definitions_inspection'
        assets=definitions/'assets'
        f=json.loads((BASE/'anno1503_fish_mod/fish_patch.json').read_bytes())
        g=json.loads((BASE/'anno1503_game_meat_test/game_patch.json').read_bytes())
        m=json.loads((BASE/'anno1503_food_market/game_patch.json').read_bytes())
        self.variants={s:{} for s in list(mod.STATE_NAMES)[:-1]}
        v=self.variants['vanilla']
        names=['Anno1503.exe',*[e['name'] for e in self.spec['native_modules']],
               'Data/BGruppen.dat',*f['icon_source_files']]
        v.update({n:(binary/n).read_bytes() for n in names})
        v.update({n:(assets/n).read_bytes() for n in f['text_files']})
        v['ToolGfx/fenster.inc']=(assets/'ToolGfx/fenster.inc').read_bytes()
        v['ToolGfx/fenster.tex']=(assets/'ToolGfx/fenster.tex').read_bytes()
        # Independent low-resolution and localized UI fixtures include the
        # native palette and mixed dimensions which broke early installers.
        idx,tex=self.lowres(v['ToolGfx/fenster.tex'])
        for stem in ['ToolGfx/fenster8','Languages/Nl/ToolGfx/fenster']:
            v[stem+'.inc'],v[stem+'.tex']=idx,tex
        one=dict(v)
        one['AnnoGame.dll']=mod.fm.patched_bytes(v['AnnoGame.dll'],f['engine_patches'])
        one['Data/BGruppen.dat']=mod.fm.split_food_demand(v['Data/BGruppen.dat'])
        for n in f['text_files']:one[n]=mod.fm.update_labels(v[n])
        for n in f['icon_source_files']:one[n]=mod.fm.update_icon_sources(v[n])
        asset=mod.artwork.load_assets(PACKAGE,self.spec['artwork_hashes'])['fish']
        for stem in ['ToolGfx/fenster','ToolGfx/fenster8','Languages/Nl/ToolGfx/fenster']:
            one[stem+'.inc'],one[stem+'.tex']=mod.fm.extend_fish_ui(v[stem+'.inc'],v[stem+'.tex'],icon_asset=asset)
        self.variants['fish-0.1.4']=one
        two=dict(one)
        two['AnnoGame.dll']=mod.fm.patched_bytes(one['AnnoGame.dll'],g['engine_patches'])
        for entry in g['ai_modules']:two[entry['name']]=mod.fm.patched_bytes(one[entry['name']],entry['patches'])
        two['Data/BGruppen.dat']=mod.tr.add_definition(one['Data/BGruppen.dat'])
        for n in f['text_files']:two[n]=mod.tr.game_labels(one[n])
        for n in f['icon_source_files']:two[n]=mod.tr.game_icon_sources(one[n])
        for stem in ['ToolGfx/fenster','ToolGfx/fenster8','Languages/Nl/ToolGfx/fenster']:
            two[stem+'.inc'],two[stem+'.tex']=mod.tr.game_extend_ui(one[stem+'.inc'],one[stem+'.tex'])
        self.variants['game-0.2.2']=two
        three=dict(two)
        for entry in m['native_modules']:
            import base64
            before=two[entry['name']]
            three[entry['name']]=mod.fm.patched_bytes(before,entry['patches'])+base64.b64decode(entry['append_base64'])
        three['Data/BGruppen.dat']=mod.tr.diet(two['Data/BGruppen.dat'])
        for n in f['text_files']:three[n]=mod.tr.food_labels(two[n])
        for stem in ['ToolGfx/fenster','ToolGfx/fenster8','Languages/Nl/ToolGfx/fenster']:
            three[stem+'.inc'],three[stem+'.tex']=mod.tr.food_extend_ui(two[stem+'.inc'],two[stem+'.tex'])
        self.variants['market-0.3-full']=three
        test=dict(three);test['Data/BGruppen.dat']=mod.tr.diet(two['Data/BGruppen.dat'],'fish-only')
        self.variants['market-0.3-fish-only']=test
        prior=json.loads((PACKAGE/'developer/compat-0.4.0.json').read_bytes())
        combined=dict(three)
        for entry in prior['native_modules']:
            combined[entry['name']]=mod.apply_native(v[entry['name']],entry)
        for name in prior['files']:
            combined[name]=mod.transform_file(name,three[name],'market-0.3-full',prior)
        art=mod.artwork.load_assets(PACKAGE,self.spec['artwork_hashes'])
        for stem in ['ToolGfx/fenster','ToolGfx/fenster8','Languages/Nl/ToolGfx/fenster']:
            combined[stem+'.inc'],combined[stem+'.tex']=mod.transform_ui(three[stem+'.inc'],three[stem+'.tex'],'market-0.3-full',art)
        self.variants['combined-0.4.0']=combined
        prior041=json.loads((PACKAGE/'developer/compat-0.4.1.json').read_bytes())
        current=dict(combined)
        for entry in prior041['native_modules']:
            current[entry['name']]=mod.apply_native(v[entry['name']],entry)
        self.variants['combined-0.4.1']=current
        manifest=json.loads((definitions/'definitions-manifest.json').read_text(encoding='utf-8-sig'))
        self.regions={s:{} for s in self.variants}
        for source in manifest['definitions']:
            name=source['source_name'];region=(definitions/source['zip_entry']).read_bytes()
            self.regions['vanilla'][name]=region
            for spec,state in [(f,'fish-0.1.4'),(g,'game-0.2.2'),(m,'market-0.3-full')]:
                entry=next(a for a in spec['archives'] if a['name']==name)
                region=mod.fm.patched_bytes(region,entry['patches'],entry['region_offset'])
                self.regions[state][name]=region
            self.regions['market-0.3-fish-only'][name]=region
            self.regions['combined-0.4.0'][name]=region
            self.regions['combined-0.4.1'][name]=region

    def lowres(self,source):
        fm=mod.fm
        access=[('FIRST',2),('WARENICONS_ROHSTOFF',12),('WARENICONS_ROHSTOFF_GREY',33),
                ('WARENICONS_BEDARF',54),('WARENICONS_BEDARF_GREY',68),
                ('WARENICONS_BAUMATERIAL',82),('WARENICONS_BAUMATERIAL_GREY',86),('LAST',100)]
        index=fm.make_chunk('ANNO',fm.make_chunk('ACCESS',b''.join(f'{n},{i}\0'.encode() for n,i in access)))
        palette=fm.read_palette(source,1)
        bgra=bytes(v for r,g,b in palette for v in (b,g,r,0))
        parts=[fm.make_chunk('COLOR',struct.pack('<II',0,1)+fm.make_chunk('BODY',bgra))]
        for ident in range(2,101):
            w,h=(40,39) if ident%3==0 else (39,39)
            head=struct.pack('<HHHH',w,h,1,8)+bytes(28)
            pixels=bytes([ident])*(w*h)
            parts.append(fm.make_chunk('TEXTURE',struct.pack('<II',0,ident)+fm.make_chunk('HEAD',head)+fm.make_chunk('BODY',fm.encode_bsh8(w,h,pixels))))
        return index,fm.make_chunk('ANNO',b''.join(parts))

    def make(self,root,state):
        for name,data in self.variants[state].items():
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        for entry in self.spec['archives']:
            with (root/entry['name']).open('wb') as stream:
                stream.truncate(entry['source_size']);stream.write(b'BEFORE_UNTOUCHED')
                stream.seek(entry['region_offset']);stream.write(self.regions[state][entry['name']]);stream.write(b'AFTER_UNTOUCHED')
        # Recognized file fingerprints work without old installer scripts or
        # backup files. Unrelated and existing backup records are retained.
        for folder,name in [('FishMod_Backup_0_1','backup-manifest.json'),('GameMeat_Test_Backup_0_2','manifest.json'),('FoodMarket_Backup_0_3','manifest.json'),('FoodMod_Backup_0_4','manifest.json'),('FoodMod_Backup_0_4_1','manifest.json')]:
            path=root/folder/name;path.parent.mkdir();path.write_text('{"kept":"original record"}')
        if state in {'combined-0.4.0','combined-0.4.1'}:
            old_names=[e['name'] for e in self.spec['native_modules'] if e['name']!='AnnoFrame.dll']
            old_names += ['ToolGfx/fenster.inc','ToolGfx/fenster.tex']
            oldfolder='FoodMod_Backup_0_4_1' if state=='combined-0.4.1' else 'FoodMod_Backup_0_4'
            (root/oldfolder/'manifest.json').write_text(json.dumps(dict(version=state.removeprefix('combined-'),status='installed',edits=[
                dict(name=n,offset=None,after_sha256=mod.fm.sha(self.variants[state][n])) for n in old_names])))


@unittest.skipUnless((BASE/'anno1503_binary_inspection/files/AnnoGame.dll').is_file(),'Original inspection files unavailable')
class FoodModChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=OriginalFixture();cls.spec=cls.fixture.spec
        cls.art=mod.artwork.load_assets(PACKAGE,cls.spec['artwork_hashes'])

    def edits(self,root):return mod.build_edits(root,self.spec,progress=lambda x:None)

    def test_one_install_from_all_seven_states_and_exact_restore(self):
        target_files=None
        for state in self.fixture.variants:
            with self.subTest(state=state),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);self.fixture.make(root,state)
                records={p.relative_to(root):p.read_bytes() for p in root.glob('*Backup*/**/*.json')}
                found,edits=self.edits(root);self.assertEqual(found,state)
                mod.tx.install(root,edits,state,progress=lambda x:None)
                for e in edits:self.assertEqual(mod.tx.read_region(root/e.name,e.offset,len(e.after)),e.after)
                found,again=self.edits(root)
                self.assertEqual(found,mod.FINAL_STATE);self.assertEqual(again,[])
                current={n:(root/n).read_bytes() for n in self.fixture.variants[state]}
                if target_files is None:target_files=current
                else:self.assertEqual(current,target_files)
                report=collect_crash.collect_state(root)
                self.assertTrue(all(e['matches_combined_food_mod'] for e in report['current_files'] if 'matches_combined_food_mod' in e))
                self.assertTrue(all(e['matches_combined_food_mod'] for e in report['building_regions']))
                self.assertEqual(mod.tx.restore(root,progress=lambda x:None),state)
                for n,d in self.fixture.variants[state].items():self.assertEqual((root/n).read_bytes(),d)
                for e in self.spec['archives']:
                    self.assertEqual(mod.tx.read_region(root/e['name'],e['region_offset'],e['region_size']),self.fixture.regions[state][e['name']])
                    self.assertEqual(mod.tx.read_region(root/e['name'],0,16),b'BEFORE_UNTOUCHED')
                    self.assertEqual(mod.tx.read_region(root/e['name'],e['region_offset']+e['region_size'],15),b'AFTER_UNTOUCHED')
                self.assertEqual({p:(root/p).read_bytes() for p in records},records)

    def test_failure_after_new_view_write_rolls_back_the_entire_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture.make(root,'vanilla');state,edits=self.edits(root)
            writer=mod.tx.write_region;failed=[False]
            def interrupt(path,offset,data):
                writer(path,offset,data)
                if path.name=='View.dll' and not failed[0]:failed[0]=True;raise OSError('Simulated failure after native file write')
            with patch.object(mod.tx,'write_region',side_effect=interrupt):
                with self.assertRaisesRegex(mod.fm.ModError,'previous setup was restored'):mod.tx.install(root,edits,state,progress=lambda x:None)
            for e in edits:self.assertEqual(mod.tx.read_region(root/e.name,e.offset,len(e.before)),e.before)
            self.assertEqual(mod.tx.read_manifest(root)['status'],'rolled_back')

    def test_unknown_module_refuses_before_backup_or_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture.make(root,'market-0.3-full')
            (root/'View.dll').write_bytes(b'Another mod')
            with self.assertRaisesRegex(mod.fm.ModError,'Native module does not match'):self.edits(root)
            self.assertFalse((root/mod.tx.BACKUP).exists())
            self.assertEqual((root/'Data/BGruppen.dat').read_bytes(),self.fixture.variants['market-0.3-full']['Data/BGruppen.dat'])

    def test_restore_preflights_every_file_before_writing_any(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture.make(root,'vanilla');state,edits=self.edits(root)
            mod.tx.install(root,edits,state,progress=lambda x:None)
            (root/'ToolGfx/fenster.tex').write_bytes(b'A later edit')
            with patch.object(mod.tx,'write_region') as writer:
                with self.assertRaisesRegex(mod.fm.ModError,'Changed since installation'):mod.tx.restore(root,progress=lambda x:None)
                writer.assert_not_called()

    def test_reinstall_after_restore_keeps_completed_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture.make(root,'market-0.3-full');state,edits=self.edits(root)
            mod.tx.install(root,edits,state,progress=lambda x:None);mod.tx.restore(root,progress=lambda x:None)
            old=(root/mod.tx.BACKUP/'manifest.json').read_bytes()
            state,edits=self.edits(root);mod.tx.install(root,edits,state,progress=lambda x:None)
            self.assertEqual((root/(mod.tx.BACKUP+'.previous-1')/'manifest.json').read_bytes(),old)

    def test_full_diet_is_identical_to_working_03_and_conserves_original_food(self):
        vanilla=self.fixture.variants['vanilla']['Data/BGruppen.dat']
        new=mod.transform_file('Data/BGruppen.dat',vanilla,'vanilla',self.spec)
        self.assertEqual(new,self.fixture.variants['market-0.3-full']['Data/BGruppen.dat'])
        def needs(data):
            groups=re.split(r'BGruppeNr:\s*',data.decode('cp1252').split('[BGRUPPE]')[1].split('[BAUSTUFEN]')[0])[1:]
            return {g.split()[0]:{m[1]:Decimal(m[2]) for m in re.finditer(r'Ware:\s+(\w+)[^\r\n]*\r?\n\s*Menge:\s*([0-9.]+)',g)} for g in groups}
        before,after=needs(vanilla),needs(new)
        for group,items in before.items():
            self.assertEqual(sum(after[group][g] for g,f in mod.tr.GOODS),items['NAHRUNG'])
            self.assertEqual({g:q for g,q in items.items() if g!='NAHRUNG'}, {g:q for g,q in after[group].items() if g not in dict(mod.tr.GOODS)})
            self.assertLessEqual(len(after[group]),18)
        self.assertIn(b'BauFirst: INFRA_STUFE_3B',new.split(b'Id:       BROT2')[1].split(b'Id:',1)[0])
        self.assertIn(b'BauFirst: INFRA_STUFE_2B',new.split(b'Id:       MEAT2')[1].split(b'Id:',1)[0])

    def test_five_icons_are_distinct_and_grey_versions_are_distinct_at_both_sizes(self):
        source=self.fixture.variants['vanilla']
        for stem in ['ToolGfx/fenster','ToolGfx/fenster8']:
            index,tex=mod.transform_ui(source[stem+'.inc'],source[stem+'.tex'],'vanilla',self.art)
            ids=dict(mod.fm.read_access(index));frames=mod.fm.texture_frames(tex)
            for suffix in ['','_GREY']:
                pixels=[]
                for name,(group,ordinal) in mod.artwork.ICON_SLOTS.items():
                    target=frames[ids[group+suffix]+ordinal]
                    w,h,p=mod.fm.decode_bsh8(target)
                    self.assertIn((w,h),[(50,50),(39,39),(40,39)])
                    self.assertEqual(len(p),w*h);pixels.append(bytes(p))
                self.assertEqual(len(set(pixels)),5)
            # Original Salt, consumer ordinal 2, is never repainted.
            original_ids=dict(mod.fm.read_access(source[stem+'.inc']))
            oldframe=mod.fm.texture_frames(source[stem+'.tex'])[original_ids['WARENICONS_BEDARF']+2]
            newframe=frames[ids['WARENICONS_BEDARF']+2]
            self.assertEqual(mod.fm.reidentify_texture(newframe,0),mod.fm.reidentify_texture(oldframe,0))

    def test_visual_upgrade_only_changes_ten_food_frames(self):
        source=self.fixture.variants['market-0.3-full']
        for stem in ['ToolGfx/fenster','ToolGfx/fenster8','Languages/Nl/ToolGfx/fenster']:
            index,tex=source[stem+'.inc'],source[stem+'.tex'];old=mod.fm.texture_frames(tex)
            after_index,after_tex=mod.transform_ui(index,tex,'market-0.3-full',self.art)
            self.assertEqual(index,after_index)
            ids=dict(mod.fm.read_access(index));targets={ids[group+suffix]+ordinal for group,ordinal in mod.artwork.ICON_SLOTS.values() for suffix in ['','_GREY']}
            new=mod.fm.texture_frames(after_tex);self.assertEqual(set(old),set(new))
            self.assertEqual({i:d for i,d in old.items() if i not in targets},{i:d for i,d in new.items() if i not in targets})

    def test_all_languages_group_counts_and_sources_match(self):
        for n in self.spec['text_files']:
            result=mod.transform_file(n,self.fixture.variants['vanilla'][n],'vanilla',self.spec).decode('cp1252')
            for group,count in [('WARE_ROHSTOFF',23),('WARE_BEDARF',15),('WARE_BAUMAT',5)]:
                self.assertEqual(len([x for x in result.split('['+group+']')[1].split('[')[0].splitlines() if x.strip()]),count)
        for n in self.spec['icon_source_files']:
            text=mod.transform_file(n,self.fixture.variants['vanilla'][n],'vanilla',self.spec).decode('cp1252')
            for group,count in [('WARENICONS_ROHSTOFF',23),('WARENICONS_BEDARF',15),('WARENICONS_BAUMATERIAL',5)]:
                for suffix in ['','_GREY']:
                    self.assertRegex(text,r'Access:\s*"'+group+suffix+r'"(?:(?!Access:)[\s\S])*?Segments:\s*'+str(count)+r'\s*,\s*1')

    def test_native_checksums_unwind_and_retained_game_engine(self):
        for entry in self.spec['native_modules']:
            original=self.fixture.variants['vanilla'][entry['name']]
            after=mod.apply_native(original,entry)
            pe,opt,table,sections,offset=pe_info(after)
            self.assertEqual(checksum(after),struct.unpack_from('<I',after,opt+64)[0])
            if entry['name'] in {'AnnoGame.dll','CompLogic.dll','CompLogicClassic.dll'}:
                self.assertEqual(after,self.fixture.variants['market-0.3-full'][entry['name']])
            if 'section' not in entry:continue
            self.assertEqual(sections[-1][0],b'.fmarket')
            rva,size=struct.unpack_from('<II',after,opt+112+3*8)
            entries=[struct.unpack_from('<III',after,offset(rva)+i) for i in range(0,size,12)]
            self.assertTrue(all(a[1]<=b[0] for a,b in zip(entries,entries[1:])))
            for start,end,unwind in entry['section']['new_functions']:
                self.assertIn((start,end,unwind),entries)
                self.assertEqual(after[offset(unwind):offset(unwind)+4],bytes([1,18,8,0]))

    @unittest.skipUnless(sys.platform.startswith('linux') and os.uname().machine=='x86_64','Native harness needs Linux x64')
    def test_actual_native_flags_stock_controls_layout_and_switching_markets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for entry in self.spec['native_modules']:
                (root/entry['name']).write_bytes(mod.apply_native(self.fixture.variants['vanilla'][entry['name']],entry))
            run=subprocess.run([sys.executable,str(PACKAGE/'developer/native_check.py'),str(root)],capture_output=True,text=True,timeout=25)
            self.assertEqual(run.returncode,0,run.stderr)
            result=json.loads(run.stdout)
            self.assertEqual(result['flag_and_getter_checks'],640)
            self.assertEqual(result['visible_slots_tested'],6)
            self.assertEqual(len(result['native_worker_transfers']),6)
            self.assertEqual(result['native_sale_toggle_commands'],12)
            self.assertEqual(result['red_cross_draws'],6)
            self.assertEqual(result['native_city_income_checks'],28)
            self.assertEqual(result['price_values_checked'],168)
            self.assertEqual(result['native_price_text_draws'],6)
            self.assertEqual(result['category_constructors'],9)
            self.assertEqual(result['consumer_goods'][:5],[26,24,40,25,45])
            self.assertEqual(result['ship_paging_and_selection'],'passed')
            self.assertTrue(result['original_market_layout_preserved'])
            self.assertEqual(result['compact_layout_and_panel_origin'],'passed')


if __name__=='__main__':unittest.main()
