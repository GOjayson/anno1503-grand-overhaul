import json,hashlib,struct,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from audit import Module
root=Path(__file__).resolve().parents[2]
rows=[]
for name in ['Anno1503.exe','AnnoGame.dll','AnnoFrame.dll','AnnoWelt.dll','AnnoScene.dll','View.dll','CompLogic.dll','CompLogicClassic.dll','AnnoGameAddOn.dll','AnnoFrameAddOn.dll','AnnoWeltAddOn.dll']:
 import pefile
 p=pefile.PE(str(root/name));b=(root/name).read_bytes()
 rows.append({'file':name,'machine':hex(p.FILE_HEADER.Machine),'optional_magic':hex(p.OPTIONAL_HEADER.Magic),'image_base':hex(p.OPTIONAL_HEADER.ImageBase),'sha256':hashlib.sha256(b).hexdigest(),'size':len(b),'sections':[s.Name.rstrip(b'\0').decode('ascii') for s in p.sections]})
(root/'WorldSettings_Work/engine_audit/architecture.json').write_text(json.dumps(rows,indent=2))
m=Module(str(root/'AnnoFrame.dll'))
for name,a,b in [('start',0x47d00,0x47d6c),('commit',0x476e0,0x47882),('screen_create',0x46500,0x46d77),('scene_load',0x55a10,0x55cc6)]:
 (root/f'WorldSettings_Work/engine_audit/frame_{name}.asm').write_text(m.dis(a,b))
