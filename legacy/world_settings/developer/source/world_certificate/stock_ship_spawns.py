"""Strict stock player subrecord parsing. Read-only source scene ship reserves.

Welt c1e49 reads definition u16 at ship payload+2, c1f48 reads owner u8
at+4, c1ea1/c1ea7 read x/y float32 at+8/+12. Normal scene origin is0,0.
"""
from pathlib import Path
import sys,json,struct,hashlib,math
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'world_data'))
from scene_catalogue import read_container,chunks,SceneError
ROOT=HERE.parents[1]

def records(data):
 at=8
 while at<len(data):
  if at+8>len(data):raise SceneError('Short player record')
  tag=data[at:at+6].rstrip(b'\0').decode('ascii');n=struct.unpack_from('<H',data,at+6)[0];header=8
  if n==0xffff:
   if at+12>len(data):raise SceneError('Short extended player record')
   n=struct.unpack_from('<I',data,at+8)[0];header=12
  if at+header+n>len(data):raise SceneError('Player record crosses parent')
  yield tag,data[at+header:at+header+n],at
  at+=header+n

def extract(path):
 data=path.read_bytes();root,_=read_container(data);ships=[]
 for chunk in chunks(data,32,root.end):
  if chunk.tag!='SPIELER':continue
  owner=struct.unpack_from('<I',chunk.payload,4)[0]
  if owner>4:continue
  for tag,body,offset in records(chunk.payload):
   if tag!='SCHIFF':continue
   if len(body)<16:raise SceneError('Short ship data')
   ident,definition,packed_owner,x,y=struct.unpack_from('<HHIff',body)
   if packed_owner!=owner or not all(math.isfinite(z) and 0<z<1024 for z in (x,y)):raise SceneError('Invalid stock ship')
   ships.append(dict(owner=owner,definition=definition,ship_id=ident,x=x,y=y,scene_offset=chunk.offset+16+offset+8))
 return dict(path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(data).hexdigest(),ships=ships)

def main():
 result=[]
 for name in ['01_1024_easy_256.sze','03_1024_med_256.sze','06_1024_heavy_256.sze']:
  result.append(extract(ROOT/'Languages/Nl/Scenes/0010SingleEndlos'/name))
 (HERE/'stock_ship_spawns.json').write_text(json.dumps(result,indent=2))
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
