"""Full real input files in an isolated marked fixture; no game/copy writes."""
from pathlib import Path
import contextlib
import io
import json
import shutil
import sys
import tempfile
import zipfile
from unittest.mock import patch
sys.dont_write_bytecode=True
PACKAGE=Path(__file__).resolve().parents[1];WORK=PACKAGE.parent;GAME=WORK.parent
sys.path.insert(0,str(PACKAGE));import world_mod as mod
sys.path.insert(0,str(PACKAGE/'activation'));import preflight as activation
sys.path.insert(0,str(PACKAGE/'developer/fertility'))
from review_inputs import collect,check_prior_archives
sys.path.insert(0,str(PACKAGE/'developer/layout_preview'))
from preview_review import collect_preview
sys.path.insert(0,str(PACKAGE/'developer/huge_world'))
from collector import collect_huge_world as collect_world_sizes


def backups(root):
    return {p.relative_to(root).as_posix():mod.food.fm.file_sha(p)
            for folder in sorted(root.glob('*Backup*')) if folder.is_dir()
            for p in sorted(folder.rglob('*')) if p.is_file()}


def expect(call,fragment):
    try:call()
    except (mod.food.fm.ModError,mod.tx.TransactionError) as exc:
        assert fragment in str(exc),str(exc);return
    raise AssertionError('Expected rejection: '+fragment)


def fixture(root,food_spec,spec):
    names={'Anno1503.exe',*food_spec['files'],*spec['unchanged_native'],*spec['native_overlays'],*spec['required_copy_inputs'],
           *(x['name'] for x in food_spec['native_modules']),*(x['name'] for x in food_spec['archives'])}
    for pair in mod.food.ui_pairs(GAME):names.update(pair)
    for name in names:
        target=root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(GAME/name,target)
    for folder in ['FoodMod_Backup_0_5','WorldFoodMod_Backup_0_6','WorldFoodMod_Backup_0_6_Dev3','WorldFoodMod_Backup_0_10_Dev1']:
        old=root/folder;old.mkdir()
        source=GAME/'FoodMod_Backup_0_5/manifest.json'
        shutil.copyfile(source,old/'manifest.json')
    (root/mod.MARKER).write_text(json.dumps(dict(schema=1,development_copy=True,
        copy_root=str(root.resolve()),source_root=str(GAME.resolve()),source_exe_sha256=spec['exe_sha256'])))
    return names


def main():
    spec=json.loads((PACKAGE/'world_patch.json').read_bytes());food_spec=json.loads((PACKAGE/'food_patch.json').read_bytes())
    original_backups=backups(GAME)
    preserved={p:mod.food.fm.file_sha(p) for p in [WORK/'anno1503_food_world_dev.zip',
        WORK/'anno1503_food_world_dev4.zip',
        WORK/'anno1503_food_world_dev4/world_patch.json',
        WORK/'anno1503_food_world_dev4/SOURCE_BASELINES.json',
        *sorted((WORK/'anno1503_food_world_dev4/native').glob('*.dll')),
        WORK/'anno1503_food_world_dev3_cityfix1.zip',
        WORK/'anno1503_food_world_dev3_cityfix1/world_patch.json',
        WORK/'anno1503_food_world_dev3_cityfix1/SOURCE_BASELINES.json',
        *sorted((WORK/'anno1503_food_world_dev3_cityfix1/native').glob('*.dll')),
        WORK/'anno1503_food_world_dev2/world_patch.json',WORK/'anno1503_food_world_dev2/SOURCE_BASELINES.json',
        *sorted((WORK/'anno1503_food_world_dev2/native').glob('*.dll'))]}
    dev4_inventory=json.loads((WORK/'anno1503_food_world_dev4/PACKAGE_SHA256.json').read_bytes())['files']
    for relative,expected in dev4_inventory.items():
        path=WORK/'anno1503_food_world_dev4'/relative
        assert mod.food.fm.file_sha(path)==expected,relative
        preserved[path]=expected
    dev5_inventory=json.loads((WORK/'anno1503_food_world_dev5/PACKAGE_SHA256.json').read_bytes())['files']
    assert len(dev5_inventory)==849
    for relative,expected in dev5_inventory.items():
        path=WORK/'anno1503_food_world_dev5'/relative
        assert mod.food.fm.file_sha(path)==expected,relative
        preserved[path]=expected
    preserved[WORK/'anno1503_food_world_dev5/PACKAGE_SHA256.json']=mod.food.fm.file_sha(WORK/'anno1503_food_world_dev5/PACKAGE_SHA256.json')
    dev6_inventory=json.loads((WORK/'anno1503_food_world_dev6/PACKAGE_SHA256.json').read_bytes())['files']
    assert len(dev6_inventory)==904
    for relative,expected in dev6_inventory.items():
        path=WORK/'anno1503_food_world_dev6'/relative
        assert mod.food.fm.file_sha(path)==expected,relative
        preserved[path]=expected
    preserved[WORK/'anno1503_food_world_dev6/PACKAGE_SHA256.json']=mod.food.fm.file_sha(WORK/'anno1503_food_world_dev6/PACKAGE_SHA256.json')
    dev7_manifest=WORK/'anno1503_food_world_dev7/PACKAGE_SHA256.json'
    assert mod.food.fm.file_sha(dev7_manifest)=='cfde8f48c0c62f91853f3d6a2d07cc733c1a47ee043acb24f9c1a0f64c298228'
    dev7_inventory=json.loads(dev7_manifest.read_bytes())['files']
    assert len(dev7_inventory)==978
    for relative,expected in dev7_inventory.items():
        path=WORK/'anno1503_food_world_dev7'/relative
        assert mod.food.fm.file_sha(path)==expected,relative
        preserved[path]=expected
    preserved[dev7_manifest]=mod.food.fm.file_sha(dev7_manifest)
    dev7_archive=WORK/'anno1503_food_world_dev7.zip'
    assert mod.food.fm.file_sha(dev7_archive)=='8e7fbc2571c6f8f8c7d4db37b64dde440afd2a9c88264ee519bd2e556c3614c3'
    preserved[dev7_archive]=mod.food.fm.file_sha(dev7_archive)
    with zipfile.ZipFile(dev7_archive) as archive:
        assert len(archive.namelist())==979
        assert {name.removeprefix('anno1503_food_world_dev7/') for name in archive.namelist()}==set(dev7_inventory)|{'PACKAGE_SHA256.json'}
    frozen_archives=check_prior_archives(WORK)
    baselines=json.loads((PACKAGE/'SOURCE_BASELINES.json').read_bytes())
    fertility=json.loads((PACKAGE/'developer/fertility/FERTILITY_REVIEW.json').read_bytes())
    assert fertility==collect(PACKAGE,PACKAGE/'developer/source',baselines['runtime_build_metadata'])
    fertility_sha=mod.food.fm.file_sha(PACKAGE/'developer/fertility/FERTILITY_REVIEW.json')
    assert spec['fertility_review_sha256']==baselines['fertility_review_sha256']==fertility_sha
    assert spec['fertility_evidence_sha256']==baselines['fertility_evidence_sha256']==fertility['evidence_sha256']
    preview=json.loads((PACKAGE/'developer/layout_preview/PREVIEW_REVIEW.json').read_bytes())
    assert preview==collect_preview(PACKAGE,PACKAGE/'developer/source',baselines['runtime_build_metadata'])
    preview_sha=mod.food.fm.file_sha(PACKAGE/'developer/layout_preview/PREVIEW_REVIEW.json')
    assert spec['preview_review_sha256']==baselines['preview_review_sha256']==preview_sha
    assert spec['preview_evidence_sha256']==baselines['preview_evidence_sha256']==preview['evidence_sha256']
    sizes=json.loads((PACKAGE/'developer/world_sizes/WORLD_SIZES_REVIEW.json').read_bytes())
    assert sizes==collect_world_sizes(PACKAGE,PACKAGE/'developer/source',baselines['runtime_build_metadata'])
    sizes_sha=mod.food.fm.file_sha(PACKAGE/'developer/world_sizes/WORLD_SIZES_REVIEW.json')
    assert spec['world_sizes_review_sha256']==baselines['world_sizes_review_sha256']==sizes_sha
    assert spec['world_sizes_evidence_sha256']==baselines['world_sizes_evidence_sha256']==sizes['evidence_sha256']
    engine_path=PACKAGE/'developer/huge_world/runtime_engine_edits.json'
    engine_plan=json.loads(engine_path.read_bytes())
    engine_count=engine_plan['engine_instruction_count']
    assert engine_count==len(engine_plan['edits'])>104
    assert spec['expanded_engine_profile']==engine_plan['profile']=='history-amd64-world-ship-render-and-recenter-v4'
    assert set(engine_plan['modules'])=={'AnnoWelt.dll','AnnoFrame.dll'}
    engine_counts={name:sum(edit['module']==name for edit in engine_plan['edits']) for name in engine_plan['modules']}
    assert engine_counts['AnnoWelt.dll']==166 and engine_counts['AnnoFrame.dll']>0
    assert all(edit['module'] in engine_plan['modules'] for edit in engine_plan['edits'])
    for name,meta in engine_plan['modules'].items():
        native=spec['native_overlays'][name]
        assert meta['source_sha256']==spec['payloads'][native['baseline_payload']]
        assert meta['patched_sha256']==spec['payloads'][native['output_payload']]
    assert spec['expanded_engine_patch_count']==sizes['engine_instruction_count']==engine_count
    assert spec['expanded_engine_plan_sha256']==mod.food.fm.file_sha(engine_path)
    assert sizes['supported_world_sizes']==[256,512,1024,2048] and sizes['experimental_world_sizes']==[2048]
    assert sizes['game_executed'] is False and sizes['ui_or_gameplay_verified'] is False
    assert baselines['runtime_build_metadata']['native_hooks']==9
    assert baselines['runtime_build_metadata']['engine_patch_count']==engine_count
    assert spec['map_preview']['exact_preview_plan_used_at_start'] and not spec['map_preview']['stage_replans']
    assert spec['island_distribution']['requested_spacing_is_minimum']
    assert spec['frozen_prior_release_sha256']==baselines['frozen_prior_release_sha256']==frozen_archives
    checks=[];introduced=spec['introduced_files'];overlays=spec['native_overlays']
    assert spec['world_size_choices']==[256,512,1024,2048] and '4096' in spec['unsupported_world_sizes']
    assert spec['island_size_choices']==['Small','Medium','Big (strict)','Mixed','Big (lenient)']
    checks.append(f'Exact current ABI56 runtime, nine gameplay hooks and{engine_count} guarded engine edits across World and Frame are bound to the current four-size automated evidence; experimental2048 gameplay is not claimed')
    assert set(overlays)=={'AnnoFrame.dll','AnnoScene.dll','AnnoWelt.dll'} and len(introduced)==19
    assert spec['version']==mod.VERSION and spec['settings_abi_size']==56
    assert spec['starting_money_choices']==[10000,30000,50000,80000,100000]
    assert spec['starting_fleet_choices']==['Single ship','War fleet','Merchant fleet']
    assert spec['ai_difficulty_choices']==['Peaceful','Easy','Medium','Hard']
    assert spec['plant_fertility_choices']==spec['mineral_fertility_choices']==['Very fertile','Medium fertility','Low fertility','Mixed']
    assert len(spec['payloads'])==25 and spec['data_payloads']=={**mod.alias_assets.data_payload_hashes(),**mod.world_assets.data_payload_hashes()}
    assert {n:q for n,q in introduced.items() if n not in {'AnnoWorldSettings.dll','WorldSettingsAI/CompLogic.dll','WorldSettingsAI/CompLogicClassic.dll'}}=={**mod.alias_assets.introduced_files(),**mod.world_assets.introduced_files()}
    assert mod.VERSION=='0.11.0-dev.1' and mod.FINAL_STATE=='food-world-0.11.0-dev.1'
    assert mod.tx.BACKUP=='WorldFoodMod_Backup_0_11_Dev1' and mod.tx.LOCK=='.worldfoodmod-0.11-dev1.lock'
    temporary=tempfile.TemporaryDirectory(prefix='dev8-complete-input-copy-',dir=WORK/'installer_audit')
    root=Path(temporary.name).resolve();root.relative_to((WORK/'installer_audit').resolve())
    try:
        names=fixture(root,food_spec,spec);live_inputs={n:mod.food.fm.file_sha(GAME/n) for n in names}
        initial={n:mod.food.fm.file_sha(root/n) for n in names};old_backups=backups(root)
        baseline={n:(root/n).read_bytes() for n in overlays};native=mod.payloads(spec)
        build=lambda:mod.build_edits(root,spec,progress=lambda _:None)
        def restored():
            assert {n:mod.food.fm.file_sha(root/n) for n in names}==initial
            assert all(not (root/name).exists() for name in introduced)
            assert all(backups(root)[k]==v for k,v in old_backups.items())
        state,edits=build();assert state==mod.food.FINAL_STATE
        assert len(edits)==22 and {e.name for e in edits}==set(overlays)|set(introduced)
        checks.append('Complete actual Food 0.5 data/UI/archive/native fixture; 22 targets include three native overlays, runtime, two copied AI modules, 15 pirate aliases and one Venetian town copy')
        for name in spec['data_payloads']:(mod.alias_assets if name in mod.alias_assets.data_payload_hashes() else mod.world_assets).validate_data_payload(name,native[name])
        first_data=next(iter(spec['data_payloads']))
        expect(lambda:mod.require_amd64(native[first_data],'SCP data'),'Expected inspected AMD64')
        checks.append('All 16 private SCP payloads pass exact fingerprint and bounded PIRAT01/VENEZIA01 policies; the required stock80dummy remains unmodified and native PE checks reject SCP bytes')
        expect(lambda:mod.require_amd64((GAME/'AnnoSceneAddOn.dll').read_bytes(),'legacy SceneAddOn'),'Expected inspected AMD64')
        expect(lambda:mod.require_amd64(bytes(64),'malformed'),'Expected inspected AMD64')
        checks.append('Actual i386 legacy module and malformed PE refused by AMD64 PE32+ guard')
        with patch.object(mod,'assert_game_closed'),contextlib.redirect_stdout(io.StringIO()):
            for action in ['check','install','check']:assert mod.main([action,'--game-dir',str(root)])==0
            journal=(root/mod.tx.BACKUP/'manifest.json').read_bytes()
            assert mod.main(['install','--game-dir',str(root)])==0
            assert (root/mod.tx.BACKUP/'manifest.json').read_bytes()==journal
            for action in ['restore','restore']:assert mod.main([action,'--game-dir',str(root)])==0
        restored();assert not (root/'WorldSettingsIslands').exists()
        checks.append('Actual fixture CLI install/check/no-op/repeated restore removes introduced island directories; process-closed guard doubled for isolated fixture only')
        journal_path=root/mod.tx.BACKUP/'manifest.json';restored_journal=journal_path.read_bytes()
        for name,fragment in [('Anno1503.exe','Unsupported Anno1503.exe'),('AnnoFrame.dll','Native module'),
                              ('AnnoScene.dll','Unsupported native source fingerprint'),('AnnoWelt.dll','Unsupported native source fingerprint'),
                              ('CompLogic.dll','Unsupported native fingerprint'),('CompLogicClassic.dll','Unsupported native fingerprint')]:
            target=root/name;old=target.read_bytes();target.write_bytes(old[:-1]+bytes([old[-1]^1]))
            with patch.object(mod.tx,'install') as install:expect(build,fragment);install.assert_not_called()
            assert journal_path.read_bytes()==restored_journal;target.write_bytes(old)
        checks.append('Changed executable, Frame, Scene, Welt and either original AI module refused without writes')
        for name in spec['required_copy_inputs']:
            target=root/name;old=target.read_bytes();target.write_bytes(old+b'foreign')
            with patch.object(mod.tx,'install') as install:expect(build,'Required stock island-loading input differs');install.assert_not_called()
            assert journal_path.read_bytes()==restored_journal;target.write_bytes(old)
        checks.append('The pre-existing native80dummy is required and fingerprint-checked, remains outside introduced targets, and is preserved on restoration')
        marker=root/mod.MARKER;old_marker=marker.read_bytes()
        for key,value in [('copy_root',str(WORK/'unrelated-copy')),('source_root',str(WORK/'unrelated-source'))]:
            altered=json.loads(old_marker);altered[key]=value;marker.write_text(json.dumps(altered));expect(build,'marker does not match')
        marker.write_bytes(old_marker);expect(lambda:mod.assert_copy(GAME,spec),'only an explicitly marked')
        expect(lambda:mod.assert_copy(root,dict(spec,original_game_root=str(root))),'marker does not match')
        checks.append('Marker bound to resolved copy/source/executable; actual installed game root and copied marker aliases refused')
        for name in introduced:
            target=root/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b'foreign-existing-file')
            expect(build,'already exists');assert target.read_bytes()==b'foreign-existing-file';target.unlink()
            assert journal_path.read_bytes()==restored_journal
        checks.append('Every one of 19 introduced runtime/AI/island targets protected against overwriting an existing file')
        for name,overlay in overlays.items():
            (root/name).write_bytes(native[overlay['output_payload']]);expect(build,'Partial or mixed');(root/name).write_bytes(baseline[name])
        checks.append('Each partial Frame/Scene/Welt installation refused before writes')
        old_view=(GAME/'FoodMod_Backup_0_5/regions/View.dll').read_bytes();source_view=(root/'View.dll').read_bytes()
        (root/'View.dll').write_bytes(old_view);state,edits=build();assert state=='combined-0.4.1'
        assert {e.name for e in edits}==set(overlays)|set(introduced)|{'View.dll'}
        mod.tx.install(root,edits,state);assert build()==(mod.FINAL_STATE,[])
        assert (root/'View.dll').read_bytes()==source_view;assert mod.tx.restore(root)=='combined-0.4.1'
        assert (root/'View.dll').read_bytes()==old_view;(root/'View.dll').write_bytes(source_view);restored()
        checks.append('Actual Food 0.4.1 View migration joins the same transaction; exact previous Food bytes restored')
        for index in range(len(overlays)+len(introduced)):
            state,edits=build();next_name=edits[index].name
            def fail_before(message,next_name=next_name):
                if message=='Installing: '+next_name:raise OSError('Injected publication failure')
            expect(lambda:mod.tx.install(root,edits,state,progress=fail_before),'previous setup restored')
            restored();assert mod.tx.read_manifest(root)['status']=='rolled_back'
            checks.append('Publication failure before '+next_name+' rolls back all earlier publications and introduced files')
        state,edits=build();original_save=mod.tx._save;faulted=False
        def fail_final(directory,record):
            nonlocal faulted
            if record['status']=='installed' and not faulted:faulted=True;raise OSError('Injected final journal failure')
            return original_save(directory,record)
        with patch.object(mod.tx,'_save',side_effect=fail_final):expect(lambda:mod.tx.install(root,edits,state),'previous setup restored')
        restored();checks.append('Failure after all 22 publications restores whole native files and removes all 19 introduced files')
        ai_dir=root/'WorldSettingsAI';ai_dir.mkdir(exist_ok=True);sentinel=ai_dir/'keep-existing.txt';sentinel.write_bytes(b'KEEP')
        island_dir=root/'WorldSettingsIslands/Nord';island_dir.mkdir(parents=True,exist_ok=True)
        island_sentinel=island_dir/'keep-existing.txt';island_sentinel.write_bytes(b'KEEP-ISLAND-CONTENT')
        state,edits=build();mod.tx.install(root,edits,state)
        configured=activation.verify(root);assert configured['source']==GAME.resolve() and configured['copy']==root
        assert configured['private_native_sha256']=={n:spec['payloads'][p] for n,p in introduced.items() if n.startswith('WorldSettingsAI/')}
        food_build=mod.food.build_edits
        for source_state,source_edits in [('vanilla',[]),('combined-0.4.1',[]),(mod.food.FINAL_STATE,[object()])]:
            def classify_source(path,*args,**kwargs):
                if path.resolve()==GAME.resolve():return source_state,source_edits
                return food_build(path,*args,**kwargs)
            with patch.object(mod.food,'build_edits',side_effect=classify_source):
                expect(lambda:activation.verify(root),'original game to already contain exact Food 0.5')
        checks.append('Read-only activation preflight verifies exact source Food 0.5, three original native baselines and copied AI fingerprints')
        journal=journal_path.read_bytes();altered=json.loads(journal);altered['status']='restored';journal_path.write_text(json.dumps(altered))
        expect(build,'active matching installation journal');journal_path.write_bytes(journal)
        backup=root/mod.tx.BACKUP/'before/AnnoFrame.dll';backup_bytes=backup.read_bytes();backup.write_bytes(backup_bytes+b'foreign')
        expect(build,'Restoration backup missing or changed');backup.write_bytes(backup_bytes)
        checks.append('An exact installation still requires an active matching journal and unchanged whole-file backups')
        installed={n:(root/n).read_bytes() for n in [*overlays,*introduced]}
        for name,data in installed.items():
            (root/name).write_bytes(data+b'foreign-edit')
            with patch.object(mod.tx,'_publish') as publish:expect(lambda:mod.tx.restore(root),'Changed since preflight/installation');publish.assert_not_called()
            expect(build,'missing or changed' if name in introduced else 'Partial or mixed')
            for other,expected in installed.items():
                if other!=name:assert (root/other).read_bytes()==expected
            (root/name).write_bytes(data)
        mod.tx.restore(root);restored();assert sentinel.read_bytes()==b'KEEP' and island_sentinel.read_bytes()==b'KEEP-ISLAND-CONTENT'
        assert list(root.glob(mod.tx.BACKUP+'.previous-*'))
        checks.append('Foreign changes to any of 22 installed targets block restoration before publication; repaired files restore exactly and preserve existing AI/island-folder content')
    finally:
        root.relative_to((WORK/'installer_audit').resolve());temporary.cleanup()
    assert backups(GAME)==original_backups
    assert check_prior_archives(WORK)==frozen_archives
    assert all(mod.food.fm.file_sha(path)==expected for path,expected in preserved.items())
    assert {n:mod.food.fm.file_sha(GAME/n) for n in live_inputs}==live_inputs
    checks.append('Installed source native/data inputs, every existing source backup, all pinned old archives, full dev4/dev5/dev6 inventories and all978 dev7 inventory files plus its immutable979-entry ZIP unchanged; exact ABI56 current fertility source/native/certificate/policy evidence verified')
    files=['world_mod.py','food_mod.py','support/world_transactions.py','support/test_world_transactions.py','support/package_alias_assets.py','support/package_world_assets.py','developer/test_combined_installer.py',
           'developer/build_world_payload.py','developer/pack_development.py','developer/test_copy_location.py','activation/preflight.py',
           'activation/activate_world_settings.py','activation/test_activation.py','activation/module_checks.py','activation/pe_exports.py','ACTIVATE_WORLD_SETTINGS.cmd','RUN.cmd']
    files += ['developer/settlement_owner_fix/'+name for name in [
        'test_scene_sanitization.py','scene_fixture.c','scene_sanitization_results.json','FIXTURE_INPUTS.json',
        'inspect_cityfix_save.py','test_cityfix_save_inspector.py','cityfix_save_inspector_tests.json',
        'ROOT_CAUSE.json','build_cityfix.py']]
    policy_review=json.loads((PACKAGE/'developer/start_options/ai/AI_POLICY_REVIEW.json').read_bytes())
    files += ['developer/start_options/ai/AI_POLICY_REVIEW.json']
    files += ['developer/start_options/ai/'+name for name in policy_review['evidence_sha256']]
    files += ['developer/fertility/FERTILITY_REVIEW.json']
    files += list(fertility['evidence_sha256'])
    files += ['developer/layout_preview/PREVIEW_REVIEW.json']
    files += list(preview['evidence_sha256'])
    files += ['developer/world_sizes/WORLD_SIZES_REVIEW.json','developer/huge_world/collector.py',
              'developer/huge_world/runtime_engine_edits.json','developer/huge_world/engine_patch_review.json',
              'developer/huge_world/engine_patch.py']
    files += list(sizes['evidence_sha256'])
    files=list(dict.fromkeys(files))
    result=dict(status='UNFINISHED',version=mod.VERSION,count=len(checks),checks=checks,
        world_spec_sha256=mod.food.fm.file_sha(PACKAGE/'world_patch.json'),
        source_baselines_sha256=mod.food.fm.file_sha(PACKAGE/'SOURCE_BASELINES.json'),
        tested_source_sha256={n:mod.food.fm.file_sha(PACKAGE/n) for n in files},
        fixture_archives='complete actual files; no sparse/zero-filled replacement',
        existing_live_backup_files=len(original_backups),existing_live_backups_unchanged=True,
        preserved_dev4_inventory_files=len(dev4_inventory),preserved_dev5_inventory_files=len(dev5_inventory)+1,frozen_prior_release_sha256=frozen_archives,
        preserved_dev6_inventory_files=len(dev6_inventory)+1,preserved_dev7_inventory_files=len(dev7_inventory)+1,
        preserved_dev7_archive_sha256=preserved[dev7_archive],expanded_engine_patch_count=engine_count,native_gameplay_hook_count=9,
        fertility_review_sha256=fertility_sha,fertility_evidence_files=len(fertility['evidence_sha256']),
        preview_review_sha256=preview_sha,preview_evidence_files=len(preview['evidence_sha256']),
        world_sizes_review_sha256=sizes_sha,world_sizes_evidence_files=len(sizes['evidence_sha256']),
        live_native_and_food_inputs_unchanged=True,shared_game_copy_used=False,
        game_executed=False,backend_or_generated_world_verified=False)
    (PACKAGE/'installer_test_results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
