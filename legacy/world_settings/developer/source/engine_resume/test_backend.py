"""Actual Windows DLL planner/staging tests; native scene nodes are test buffers.

This is not a game run, renderer test, save/reload, or loaded-resource proof.
"""
import ctypes as C
import hashlib,itertools,json,os,re,struct,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'WorldSettings_Work/world_data'))
from scene_catalogue import chunks,read_container,read_link,geometry_errors
class Settings(C.Structure):
 _fields_=[('size',C.c_uint32),('difficulty',C.c_int32),('islandSize',C.c_int32),('islandCount',C.c_int32),('spacing',C.c_int32),('aiCount',C.c_int32),('cultures',C.c_uint32)]
class Island(C.Structure):
 _fields_=[(x,C.c_uint32) for x in ['id','x','y','width','height','templateIndex','cropMask','mineralMask','cultures','climate']]
dll=C.CDLL(str(HERE/'runtime/WorldBackend.dll'))
dll.WorldSettingsBuildPlan.argtypes=[C.POINTER(Settings),C.c_uint32,C.c_void_p,C.c_uint32]
dll.WorldSettingsPlanIsland.argtypes=[C.c_uint32,C.POINTER(Island)]
dll.WorldSettingsStageScene.argtypes=[C.POINTER(Settings),C.c_char_p,C.c_uint32,C.c_void_p,C.c_uint32,C.c_void_p,C.c_uint32]
dll.WorldSettingsPendingPath.restype=C.c_char_p
dll.WorldSettingsPrepareScene.argtypes=[C.c_void_p,C.c_void_p]
dll.WorldSettingsValidateScene.argtypes=[C.c_void_p,C.c_void_p,C.c_uint32]
err=C.create_string_buffer(512)
cat=json.loads((ROOT/'WorldSettings_Work/world_data/catalogue.json').read_text('utf-8'))
profiles=[];group_widths={}
for t in cat['templates']:
 raw=(ROOT/t['path']).read_bytes()
 names={raw[m.start()+8:m.start()+8+struct.unpack_from('<H',raw,m.start()+6)[0]].rstrip(b'\0').decode('ascii') for m in re.finditer(b'VOLK\0\0',raw)}
 profiles.append(names)
 if not names-set(cat['cultures'])-{'SPIELER'} and (t['climate_index']==0 or any(int(k)>0 and v>0 for k,v in t['land_fertility_low_nibble_histogram'].items())):
  bits=sum(1<<cat['cultures'].index(n) for n in names if n in cat['cultures'])
  group_widths.setdefault((t['climate_index'],bits),set()).add(t['width'])
forbidden=[i for i,names in enumerate(profiles) if names-set(cat['cultures'])-{'SPIELER'}]
assert len(forbidden)==15 and all('PIRATEN' in profiles[i] for i in forbidden)
spawns=json.loads((ROOT/'WorldSettings_Work/world_certificate/stock_ship_spawns.json').read_text('utf-8'))
reserve_positions={(int(s['x'])-16,int(s['y'])-16) for entry in spawns for s in entry['ships']}
def plan(s,seed=1):
 ok=dll.WorldSettingsBuildPlan(C.byref(s),seed,err,len(err))
 out=[]
 if not ok:return out,err.value.decode()
 for i in range(dll.WorldSettingsPlanCount()):
  item=Island();assert dll.WorldSettingsPlanIsland(i,C.byref(item))
  out.append({n:getattr(item,n) for n,_ in item._fields_})
 assert len(out)==s.islandCount
 assert not geometry_errors(out,1024,1024,s.spacing)
 for p in out:
  assert p['x']%8==p['y']%8==0, 'Native island insertion must not shift planned coordinates'
  for x,y in reserve_positions:
   assert p['x']+p['width']+s.spacing<=x or x+33+s.spacing<=p['x'] or p['y']+p['height']+s.spacing<=y or y+33+s.spacing<=p['y']
 cultures=climates=crops=minerals=whales=0
 for p in out:
  t=cat['templates'][p['templateIndex']]
  assert p['templateIndex'] not in forbidden
  assert not profiles[p['templateIndex']]-set(cat['cultures'])-{'SPIELER'}
  if not p['cultures']:assert profiles[p['templateIndex']]=={'SPIELER'}
  widths=group_widths[(p['climate'],p['cultures'])]
  if s.islandSize<3:
   expected=[min(widths),128,max(widths)][s.islandSize]
   assert p['width']==p['height']==expected
  cultures|=p['cultures'];climates|=1<<p['climate'];crops|=p['cropMask'];minerals|=p['mineralMask']
  whales+=sum(x['native_definition_id']==1559 for x in t['occurrences'])
  assert p['mineralMask'].bit_count()<=sum(t['verified_mineral_counts'].values())
  assert not(p['mineralMask']&0x10)
 assert cultures==s.cultures and climates==63 and crops==0x1ffff and minerals&0x2f==0x2f and whales
 return out,''

results={'scope':__doc__,'dll_sha256':hashlib.sha256((HERE/'runtime/WorldBackend.dll').read_bytes()).hexdigest()}
valid=invalid=0
for size,bits in itertools.product(range(4),range(256)):
 s=Settings(28,1,size,12 if size==2 else 24,16,0,bits)
 items,message=plan(s)
 if items:valid+=1
 else:invalid+=1;assert message
results.update(planner_combinations=1024,valid_plans=valid,rejected_infeasible_plans=invalid,forbidden_native_templates_excluded=len(forbidden))
for size,bits in itertools.product(range(4),[0,1,85,170,255]):
 previous=None
 for difficulty in range(3):
  items,message=plan(Settings(28,difficulty,size,12 if size==2 else 24,16,0,bits),913)
  assert items,message
  if previous is not None:assert items==previous
  previous=items
results['difficulty_independent_layouts']=60
for spacing in [0,1,7,9,17,23]:
 items,message=plan(Settings(28,1,0,24,spacing,0,255),913)
 assert items,message
results['native_eight_tile_grid_and_nonmultiple_spacing_checks']=6
for s in [Settings(28,1,3,1,16,0,255),Settings(28,1,3,128,256,0,0),Settings(28,1,3,24,16,1,0),Settings(28,1,3,24,16,7,0),Settings(28,1,2,1,16,0,255),Settings(28,1,2,24,64,0,255)]:
 assert not plan(s)[0]
results['invalid_settings_and_impossible_geometry_rejected']=6
assert plan(Settings(28,1,0,24,16,0,255),913)[0]
assert plan(Settings(28,1,2,12,16,0,255),913)[0]
results['small_and_large_all_native_cultures_feasible']=True

# Write only into the independent game copy, inspect and delete this run's file.
game=ROOT/'WorldSettings_Work/game_copy'
keep=lambda seq:[(c.tag,c.payload) for c in seq if c.tag not in ['INSELLNK','INSEL5','ROHSTOFF','ERZE','SCHATZ']]
staged_links=[]
for difficulty,scene_name in enumerate(['01_1024_easy_256.sze','03_1024_med_256.sze','06_1024_heavy_256.sze']):
 stage_settings=Settings(28,difficulty,3,24,16,0,255);stage_path=C.create_string_buffer(260)
 assert dll.WorldSettingsStageScene(C.byref(stage_settings),str(game).encode(),913,stage_path,len(stage_path),err,len(err)),err.value
 stage_file=Path(stage_path.value.decode())
 try:
  data=stage_file.read_bytes();outer,trailer=read_container(data);assert not trailer
  stage_scene=next(chunks(data,16,outer.end));parts=list(chunks(stage_scene.payload,0,len(stage_scene.payload)))
  staged_links.append([{k:v for k,v in read_link(c).items() if k!='chunk_offset'} for c in parts if c.tag=='INSELLNK'])
  original=(game/'Languages/Nl/Scenes/0010SingleEndlos'/scene_name).read_bytes()
  old_root,_=read_container(original);old_scene=next(chunks(original,16,old_root.end))
  assert keep(parts)==keep(chunks(old_scene.payload,0,len(old_scene.payload)))
 finally:
  dll.WorldSettingsFinishAttempt(0)
 assert not stage_file.exists()
assert staged_links[0]==staged_links[1]==staged_links[2]
results['all_three_difficulty_scenes_preserved_with_identical_links']=True
s=Settings(28,1,3,24,16,0,255);path=C.create_string_buffer(260)
assert dll.WorldSettingsStageScene(C.byref(s),str(game).encode(),913,path,len(path),err,len(err)),err.value
generated=Path(path.value.decode());assert generated.parent==game/'Scenes' and generated.exists()
try:
 assert dll.WorldSettingsPendingPath()==path.value and dll.WorldSettingsIsActive()==1
 assert dll.WorldSettingsBuildPlan(C.byref(s),914,err,len(err))==0
 assert dll.WorldSettingsPlanCount()==24
 data=generated.read_bytes();root,trailer=read_container(data);assert not trailer
 scene=next(chunks(data,16,root.end));parts=list(chunks(scene.payload,0,len(scene.payload)))
 links=[read_link(c) for c in parts if c.tag=='INSELLNK'];assert len(links)==24
 assert not geometry_errors(links,1024,1024,16)
 for c in parts:
  if c.tag in ['ROHSTOFF','ERZE','SCHATZ']:assert set(c.payload)<={0}
 original=(game/'Languages/Nl/Scenes/0010SingleEndlos/03_1024_med_256.sze').read_bytes()
 old_root,_=read_container(original);old_scene=next(chunks(original,16,old_root.end))
 assert keep(parts)==keep(chunks(old_scene.payload,0,len(old_scene.payload)))
 # Native linked-list test buffers, malformed last node must not modify first.
 planned=[]
 for i in range(24):
  p=Island();assert dll.WorldSettingsPlanIsland(i,C.byref(p));planned.append(p)
 scene_obj=C.create_string_buffer(0x5400);nodes=[C.create_string_buffer(0x170) for _ in planned]
 for i,(p,node) in enumerate(zip(planned,nodes)):
  struct.pack_into('<Q',node,8,C.addressof(nodes[i+1]) if i+1<len(nodes) else 0)
  struct.pack_into('<HHHHIH',node,0x10,p.x,p.y,p.width,p.height,p.id,p.climate)
 struct.pack_into('<Q',scene_obj,0x53f0,C.addressof(nodes[0]))
 struct.pack_into('<I',nodes[-1],0x18,256)
 before=[node.raw for node in nodes]
 assert dll.WorldSettingsPrepareScene(C.addressof(scene_obj),0)==0
 assert [node.raw for node in nodes]==before
 struct.pack_into('<I',nodes[-1],0x18,23)
 assert dll.WorldSettingsPrepareScene(C.addressof(scene_obj),0)==1
 for p,node in zip(planned,nodes):
  selected=node.raw[0x1e:0x122].split(b'\0',1)[0].decode()
  assert selected==str(game/cat['templates'][p.templateIndex]['path'])
  crop=struct.unpack_from('<20H',node,0x122);ore=struct.unpack_from('<9H',node,0x14a)
  assert sum(bool(n)<<i for i,n in enumerate(crop))==p.cropMask
  assert sum(bool(n)<<i for i,n in enumerate(ore))==p.mineralMask and ore[4]==ore[7]==ore[8]==0
  assert node.raw[0x15c]==bool(p.cultures) and node.raw[0x15d]==0
 assert dll.WorldSettingsValidateScene(C.addressof(scene_obj),err,len(err))==0
 results['staged_scene_checks']={'count_and_spacing':True,'nonisland_difficulty_chunks_preserved':True,'native_allocator_requests_zero':True,'exact_template_node_commit':True,'invalid_node_list_has_no_partial_writes':True,'uncertified_loaded_world_rejected':True}
finally:
 dll.WorldSettingsFinishAttempt(0)
assert not generated.exists() and dll.WorldSettingsIsActive()==0 and dll.WorldSettingsPendingPath() is None
results['generated_file_restored']=True
collision=game/'Scenes'/f'WorldSettings_{os.getpid()}_5.sze'
assert not collision.exists()
collision.write_bytes(b'existing file must survive')
try:
 assert not dll.WorldSettingsStageScene(C.byref(s),str(game).encode(),913,path,len(path),err,len(err))
 assert collision.read_bytes()==b'existing file must survive'
 assert dll.WorldSettingsIsActive()==0
finally:
 collision.unlink()
results['create_new_collision_preserves_existing_file']=True
(HERE/'backend_results.json').write_text(json.dumps(results,indent=2)+'\n','utf-8')
print(json.dumps(results,indent=2))
