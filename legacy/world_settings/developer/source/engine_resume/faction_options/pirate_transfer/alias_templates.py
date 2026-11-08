"""Prepare private pirate SCP copies with exact stock-owner aliases.

The originals remain untouched. Only the top-level PIRATEN SPIELER ALIAS field
and its containing lengths change. No top-level player HEAD is permitted.
"""
from pathlib import Path
import hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[2];ROOT=WORK.parent
sys.path.insert(0,str(WORK/'world_data'))
from scene_catalogue import chunks,read_container,make_chunk
def fields(data):
 out=[];at=8
 while at<len(data):
  assert len(data)-at>=8
  length=struct.unpack_from('<H',data,at+6)[0];header=8
  if length>=0xff00:
   assert len(data)-at>=10;header=10;length=((length&255)<<16)|struct.unpack_from('<H',data,at+8)[0]
  assert length<=len(data)-at-header
  out.append((data[at:at+6].rstrip(b'\0').decode(),at,header,data[at+header:at+header+length]));at+=header+length
 return out
def transform(original):
 root,trailer=read_container(original);parts=list(chunks(original,16,root.end));changes=0;result=[]
 for part in parts:
  if part.tag!='SPIELER':result.append(original[part.offset:part.end]);continue
  values=fields(part.payload)
  names=[v for key,at,h,v in values if key=='VOLK']
  if names!=[b'PIRATEN\0']:result.append(original[part.offset:part.end]);continue
  assert struct.unpack_from('<II',part.payload)==(0,0)
  assert not any(key=='HEAD' for key,at,h,v in values),'Named profile loading must never import a player HEAD'
  aliases=[(at,h,v) for key,at,h,v in values if key=='ALIAS'];assert len(aliases)==1
  at,h,value=aliases[0];assert h==8 and value==b'\0'
  assert any(key=='STADT2' for key,at,h,v in values)
  payload=part.payload[:at]+b'ALIAS\0'+struct.pack('<H',8)+b'PIRAT01\0'+part.payload[at+9:]
  result.append(make_chunk(part.tag,payload));changes+=1
 assert changes==1 and len(trailer)==60
 output=make_chunk(root.tag,b''.join(result))+trailer
 newRoot,newTrailer=read_container(output);assert newTrailer==trailer and len(output)==len(original)+7
 return output
def main():
 cat=json.loads((HERE.parent/'candidate_sources.json').read_text());records=[];header=(HERE.parent/'runtime/world_catalogue.h').read_text()
 lines=header.splitlines();rows=[i for i,line in enumerate(lines) if line.startswith('{"Scenes\\\\Islands')]
 assert len(rows)==443
 payload=HERE/'alias_payload';(payload/'WorldSettingsIslands/Nord').mkdir(parents=True,exist_ok=True)
 for item in cat['pirate_templates']:
  source=ROOT/item['path'];original=source.read_bytes();assert hashlib.sha256(original).hexdigest()==item['sha256'];out=transform(original)
  relative='WorldSettingsIslands/Nord/'+source.name;target=payload/relative;target.write_bytes(out)
  index=rows[item['index']];before=lines[index];oldHash='{'+','.join(str(x) for x in bytes.fromhex(item['sha256']))+'}'
  newHash=hashlib.sha256(out).hexdigest();after=before.replace(json.dumps(item['path'].replace('/','\\')),json.dumps(relative.replace('/','\\'))).replace(oldHash,'{'+','.join(str(x) for x in bytes.fromhex(newHash))+'}')
  assert before!=after and after.count(newHash)==0 and after.count(json.dumps(relative.replace('/','\\')))==1
  lines[index]=after;assert source.read_bytes()==original
  records.append(dict(template_index=item['index'],source=item['path'],source_sha256=item['sha256'],copy_relative_path=relative,copy_sha256=newHash,source_bytes=len(original),copy_bytes=len(out),top_level_player_head_absent=True,old_alias='',new_alias='PIRAT01',unchanged_trailer_sha256=hashlib.sha256(out[-60:]).hexdigest()))
 (HERE/'alias_runtime').mkdir(exist_ok=True);(HERE/'alias_runtime/world_catalogue.h').write_text('\n'.join(lines)+'\n')
 manifest=dict(scope=__doc__,copies=records,catalogue_sha256=hashlib.sha256((HERE/'alias_runtime/world_catalogue.h').read_bytes()).hexdigest(),original_template_count=443,changed_copy_templates=15,game_runs=0)
 (HERE/'alias_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(dict(changed_copy_templates=len(records),catalogue_sha256=manifest['catalogue_sha256'],originals_unchanged=True)))
if __name__=='__main__':main()
