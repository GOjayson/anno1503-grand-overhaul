"""Read stock endless COMPPROFIL2 entries; do not assign or invent profiles."""
from pathlib import Path
import hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE.parents[1]/'world_data'))
from scene_catalogue import chunks
reports=[]
for difficulty,filename in enumerate(['01_1024_easy_256.sze','03_1024_med_256.sze','06_1024_heavy_256.sze']):
 path=ROOT/'Languages/Nl/Scenes/0010SingleEndlos'/filename;data=path.read_bytes()
 c=next(c for c in chunks(data,32,len(data)) if c.tag=='COMPPROFIL2');at=0;records=[];other=[]
 while at<len(c.payload):
  assert len(c.payload)-at>=8
  tag=c.payload[at:at+6].rstrip(b'\0').decode('ascii');length=struct.unpack_from('<H',c.payload,at+6)[0];header=8
  if length>=0xff00:header=10;length=(length&255)<<16|struct.unpack_from('<H',c.payload,at+8)[0]
  assert length<=len(c.payload)-at-header
  value=c.payload[at+header:at+header+length]
  if tag=='ENTRY':
   assert len(value)==168
   records.append(dict(ordinal=len(records),guid=value[0x4c:0x5c].hex(),name=value[0x5c:0x75].split(b'\0')[0].decode('cp1252'),page=value[0x75:0xa7].split(b'\0')[0].decode('cp1252'),bytes_hex=value.hex()))
  else:other.append(dict(tag=tag,payload_hex=value.hex()))
  at+=header+length
 reports.append(dict(difficulty=difficulty,path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(data).hexdigest(),profiles=records,selection=other))
(HERE/'stock_profile_inputs.json').write_text(json.dumps(dict(scope=__doc__,sources=reports),indent=2)+'\n','utf-8')
for source in reports:print(source['difficulty'],[(p['ordinal'],p['name'],p['guid']) for p in source['profiles']],source['selection'])
