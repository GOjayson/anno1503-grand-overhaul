"""Independently reverse the staged alias change and require exact originals."""
from pathlib import Path
import hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[3];ROOT=WORK.parent
sys.path.insert(0,str(WORK/'world_data'))
from scene_catalogue import chunks,read_container
candidate=WORK/'engine_resume/faction_options/pirate_transfer'
manifest=json.loads((candidate/'alias_manifest.json').read_text());rows=[]
for item in manifest['copies']:
 original=(ROOT/item['source']).read_bytes();copy=(candidate/'alias_payload'/item['copy_relative_path']).read_bytes()
 assert hashlib.sha256(original).hexdigest()==item['source_sha256']
 assert hashlib.sha256(copy).hexdigest()==item['copy_sha256']
 r,trailer=read_container(copy);oroot,ot=read_container(original);assert trailer==ot and len(trailer)==60
 parts=[];reversed_fields=0
 for part in chunks(copy,16,r.end):
  if part.tag!='SPIELER':parts.append(copy[part.offset:part.end]);continue
  p=part.payload;at=8;alias=None;head=False;volk=[]
  while at<len(p):
   assert len(p)-at>=8;n=struct.unpack_from('<H',p,at+6)[0];h=8
   if n>=0xff00:h=10;n=((n&255)<<16)|struct.unpack_from('<H',p,at+8)[0]
   assert n<=len(p)-at-h;tag=p[at:at+6].rstrip(b'\0')
   if tag==b'VOLK':volk.append(p[at+h:at+h+n])
   if tag==b'HEAD':head=True
   if tag==b'ALIAS':assert alias is None;alias=(at,h,n,p[at+h:at+h+n])
   at+=h+n
  assert volk==[b'PIRATEN\0'] and not head and alias
  at,h,n,value=alias;assert h==8 and n==8 and value==b'PIRAT01\0'
  restored=p[:at]+b'ALIAS\0\x01\x00\0'+p[at+h+n:]
  header=bytearray(copy[part.offset:part.offset+16]);struct.pack_into('<I',header,12,len(restored))
  parts.append(bytes(header)+restored);reversed_fields+=1
 assert reversed_fields==1
 payload=b''.join(parts);root_header=bytearray(copy[:16]);struct.pack_into('<I',root_header,12,len(payload))
 assert bytes(root_header)+payload+trailer==original
 rows.append(dict(template=item['source'],exact_reverse_match=True,only_alias_and_two_containing_lengths_changed=True,trailer_identical=True))
result=dict(scope=__doc__,actual_game_runs=0,cases=rows,manual_owner_transfer_used=False,native_cache_identity_verified=False,
 cache_limit='Private paths differ under WorldSettingsIslands, but static cache-key identity has not been independently traced; actual game validation still required.')
(HERE/'alias_results.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')
print(json.dumps(dict(exact_reverse_matches=len(rows),originals_changed=False,actual_game_runs=0)))
