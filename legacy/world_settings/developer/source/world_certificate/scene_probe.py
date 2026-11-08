from pathlib import Path
import sys, json,struct
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'world_data'))
from scene_catalogue import *
ROOT=HERE.parents[1]
out=[]
for name in ['01_1024_easy_256.sze','03_1024_med_256.sze','06_1024_heavy_256.sze']:
 p=ROOT/'Languages/Nl/Scenes/0010SingleEndlos'/name;d=p.read_bytes();r,_=read_container(d)
 record={'path':str(p.relative_to(ROOT)),'tags':[]}
 for c in chunks(d,32,r.end):
  if c.tag not in ['HEAD','INSELLNK']:
   record['tags'].append({'tag':c.tag,'offset':hex(c.offset),'size':c.length,'head':c.payload[:128].hex()})
 out.append(record)
print(json.dumps(out,indent=2))
