"""Read player HEAD type values from installed source scenes without edits."""
from pathlib import Path
import hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'WorldSettings_Work/world_data'))
from scene_catalogue import read_container,chunks
records=[]
for p in sorted((ROOT/'Languages/Nl/Scenes/0010SingleEndlos').glob('*.sze')):
 d=p.read_bytes();r,t=read_container(d);assert not t
 sc=next(chunks(d,16,r.end));players=[]
 for c in chunks(sc.payload,0,len(sc.payload)):
  if c.tag=='SPIELER' and c.payload[8:14]==b'HEAD\0\0':
   players.append({'id':struct.unpack_from('<I',c.payload,4)[0],
                   'head_type':struct.unpack_from('<I',c.payload,16)[0]})
 records.append({'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(d).hexdigest(),
                 'players':players,'native_computer_type_0c_count':sum(x['head_type']==12 for x in players)})
print(json.dumps({'scope':'Stock single endless source player placeholders, not a hard engine or Food Mod AI compatibility maximum. Frame553f0 matches HEAD type0x0c and unassigned color0xff.',
                  'maximum_observed_stock_computer_placeholders':max(x['native_computer_type_0c_count'] for x in records),
                  'scenes':records},indent=2))
