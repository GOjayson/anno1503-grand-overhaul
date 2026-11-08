"""Validate private alias assets and catalogue against all original443 assets.

No installed file is written. No game is run or attached.
"""
from pathlib import Path
import hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[2];ROOT=WORK.parent
sys.path[:0]=[str(HERE),str(WORK/'world_data'),str(WORK/'engine_audit')]
from alias_templates import fields
from scene_catalogue import chunks,read_container,read_island
from audit import Module
manifest=json.loads((HERE/'alias_manifest.json').read_text());catalogue=json.loads((WORK/'world_data/catalogue.json').read_text());cases=[]
for item in catalogue['templates']:assert hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest()==item['sha256']
for item in manifest['copies']:
 original=(ROOT/item['source']).read_bytes();modified=(HERE/'alias_payload'/item['copy_relative_path']).read_bytes()
 assert hashlib.sha256(original).hexdigest()==item['source_sha256'] and hashlib.sha256(modified).hexdigest()==item['copy_sha256']
 oldRoot,oldTrailer=read_container(original);newRoot,newTrailer=read_container(modified);assert oldTrailer==newTrailer and len(modified)-len(original)==7 and newRoot.length-oldRoot.length==7
 before=list(chunks(original,16,oldRoot.end));after=list(chunks(modified,16,newRoot.end));assert len(before)==len(after)
 changed=0
 for a,b in zip(before,after):
  assert a.tag==b.tag
  if a.payload==b.payload:continue
  assert a.tag=='SPIELER' and a.payload[:8]==b.payload[:8] and a.length+7==b.length
  fs,ft=fields(a.payload),fields(b.payload);assert len(fs)==len(ft) and all(x[0]==y[0] for x,y in zip(fs,ft))
  assert not any(key=='HEAD' for key,at,h,v in fs)
  for (key,at,h,v),(other,at2,h2,new) in zip(fs,ft):
   if key=='ALIAS':assert v==b'\0' and new==b'PIRAT01\0' and h==h2==8
   else:assert h==h2 and v==new
  changed+=1
 assert changed==1
 sourceInfo=read_island(original);copyInfo=read_island(modified)
 # These describe the changed container envelope only; all physical islands,
 # crops, occurrences, fertility, ownership-profile and building bytes match.
 for key in ['root_declared_end','top_level_tags']:
  sourceInfo.pop(key);copyInfo.pop(key)
 assert sourceInfo==copyInfo
 cases.append(dict(source=item['source'],unchanged_physical_island=True,unchanged_nonalias_profile_fields=True,unchanged_dummy_trailer=True,player_head_absent=True,exact_byte_growth=7))
source=(HERE.parent/'runtime/world_catalogue.h').read_text().splitlines();new=(HERE/'alias_runtime/world_catalogue.h').read_text().splitlines();assert len(source)==len(new)
changedRows=[i for i,(a,b) in enumerate(zip(source,new)) if a!=b];assert len(changedRows)==15
for i in changedRows:
 a,b=source[i],new[i];assert a.startswith('{"Scenes\\\\Islands\\\\Nord\\\\N_') and b.startswith('{"WorldSettingsIslands\\\\Nord\\\\N_')
 # Everything between path and fingerprint is preserved exactly.
 assert a.split('"',2)[2].rsplit('{',1)[0]==b.split('"',2)[2].rsplit('{',1)[0]
w=Module(str(ROOT/'AnnoWelt.dll'));s=Module(str(ROOT/'AnnoScene.dll'))
assert hashlib.sha256(w.data).hexdigest()=='ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9'
assert hashlib.sha256(s.data).hexdigest()=='f7d0685cf6156ff25c518f2f558863b351d7738280467e48dd585a1fefa9537a'
createFile=next(w.cs.disasm(w.image[0xcf0ce:0xcf0d5],w.base+0xcf0ce));iat=createFile.address+createFile.size+createFile.disp
api=next(i.name.decode() for d in w.pe.DIRECTORY_ENTRY_IMPORT for i in d.imports if i.address==iat);assert api=='CreateFileA'
assert struct.unpack_from('<Q',w.image,0xff650+0x118)[0]==w.base+0xcfea0
assert struct.unpack_from('<Q',w.image,0xff650+0x3b0)[0]==w.base+0xcf070
call=next(w.cs.disasm(w.image[0xcff8c:0xcff93],w.base+0xcff8c));assert call.mnemonic=='call' and call.operands[0].mem.disp==0x3b0
result=dict(scope=__doc__,original_template_sha256_checks=443,private_template_cases=cases,catalogue_changed_rows=len(changedRows),unchanged_other_catalogue_lines=len(source)-len(changedRows),catalogue_sha256=hashlib.sha256((HERE/'alias_runtime/world_catalogue.h').read_bytes()).hexdigest(),native_read_path={'scene_virtual':'World+118','native_world_entry':'0xcfea0','file_loader_virtual':'World+3b0','native_file_loader':'0xcf070','first_file_api':api,'first_file_api_call':'0xcf0ce'},actual_game_runs=0)
(HERE/'alias_test_results.json').write_text(json.dumps(result,indent=2)+'\n');(HERE/'alias_file_path.asm').write_text(s.dis(0xc3a4,0xc3c8)+'\n\n'+w.dis(0xcff72,0xcff95)+'\n\n'+w.dis(0xcf070,0xcf0e5))
print(json.dumps({'original_template_checks':443,'private_alias_assets':len(cases),'changed_catalogue_rows':15,'native_filename_open_api':api,'actual_game_runs':0}))
