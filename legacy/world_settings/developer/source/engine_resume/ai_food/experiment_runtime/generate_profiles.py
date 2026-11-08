"""Bind only exact stock profile records for the private AI experiment."""
from pathlib import Path
import hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent
WORK=HERE.parents[2];ROOT=WORK.parent
sys.path.insert(0,str(WORK/'world_data'))
from scene_catalogue import chunks
sources=json.loads((HERE.parent/'stock_profile_inputs.json').read_text())['sources']
rows=[];evidence=[]
for s in sources:
 data=(ROOT/s['path']).read_bytes()
 assert hashlib.sha256(data).hexdigest()==s['sha256']
 source=next(c for c in chunks(data,32,len(data)) if c.tag=='COMPPROFIL2')
 records=[];selection=None;at=0
 while at<len(source.payload):
  assert len(source.payload)-at>=8
  tag=source.payload[at:at+6].rstrip(b'\0');n=struct.unpack_from('<H',source.payload,at+6)[0]
  assert n<0xff00 and n<=len(source.payload)-at-8
  value=source.payload[at+8:at+8+n]
  if tag==b'ENTRY': assert n==168;records.append(value)
  elif tag==b'DEF': assert selection is None and n==128;selection=struct.unpack('<32i',value)
  at+=8+n
 assert selection and selection[0]==-1
 chosen=[];names=[]
 for index in selection[1:4]:
  assert 0<=index<len(records)
  record=records[index]
  assert record[0x4c:0x5c] not in [bytes(16),bytes([255])*16]
  assert struct.unpack_from('<I',record,0x34)[0]==0 # native property1a, SUSPEND
  chosen.append(record);names.append(record[0x5c:0x75].split(b'\0')[0].decode('cp1252'))
 rows.append(chosen)
 evidence.append(dict(difficulty=s['difficulty'],source=s['path'],source_sha256=s['sha256'],
   stock_default_indices=list(selection[1:4]),names=names,
   profile_sha256=[hashlib.sha256(r).hexdigest() for r in chosen]))
out=['/* Generated from fingerprinted original single endless COMPPROFIL2. */',
     'static const unsigned char wsAIProfiles[3][3][168] = {']
for row in rows:
 out.append(' {')
 for record in row:out.append('  {'+','.join('0x%02x'%x for x in record)+'},')
 out.append(' },')
out.append('};\n')
(HERE/'stock_ai_profiles.h').write_text('\n'.join(out),'ascii')
(HERE/'profile_sources.json').write_text(json.dumps(evidence,indent=2)+'\n','utf-8')
print(json.dumps(evidence,indent=2))
