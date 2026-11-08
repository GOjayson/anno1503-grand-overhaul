"""Read original Food-Mod building recipe inputs without modifying game files."""
from pathlib import Path
import hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[1];ROOT=WORK.parent
sys.path.insert(0,str(WORK/'world_data'))
from scene_catalogue import chunks
IDS=[713,805,809,810,820,1002,1004,1018]
def entries(path):
 with path.open('rb') as f:
  header=f.read(16);assert header[:12]==b'ANNO'.ljust(12,b'\0')
  end=16+struct.unpack_from('<I',header,12)[0];assert end==path.stat().st_size;at=16;body=None
  while at<end:
   f.seek(at);header=f.read(16);size=struct.unpack_from('<I',header,12)[0];assert size<=end-at-16
   if header[:12]==b'ANLAGEN'.ljust(12,b'\0'):assert body is None and size<8*1024*1024;body=f.read(size)
   at+=size+16
 assert body is not None
 return {struct.unpack_from('<II',entry.payload)[1]:{field.tag:field.payload for field in chunks(entry.payload,8,len(entry.payload))} for entry in chunks(body,0,len(body))}
def main():
 reports=[]
 for filename in ['Anlagen.dat','Anlagen.addon']:
  path=ROOT/filename;data=entries(path);records=[]
  for ident in IDS:
   fields=data[ident];record=dict(id=ident,fields={})
   for tag,payload in fields.items():
    if tag in ['HEAD','WARE','ROHSTOFF','PRODTYPE','BAUSTUFE','BAUMATERIAL','INFRA','PROD','ANLAGE','PRODHEAD'] or (len(payload)<256 and (b'MEHL' in payload or b'GETREIDE' in payload or b'FLEISCH' in payload)):
     record['fields'][tag]=dict(hex=payload.hex(),text=payload.decode('cp1252',errors='replace') if all(v>=32 or v in [0,9,10,13] for v in payload) else None)
   records.append(record)
  reports.append(dict(path=filename,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),records=records))
 result=dict(scope=__doc__,sources=reports,actual_game_runs=0)
 (HERE/'food_chain_inputs.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')
 for source in reports:
  print(source['path'])
  for record in source['records']:print(record)
if __name__=='__main__':main()
