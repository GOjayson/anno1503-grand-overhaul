"""Private Windows backend staging using copied alias assets and new catalogue.

Only a temporary root below this directory is populated. No game copy,
installed template or backup is modified. Native scene nodes are buffers.
"""
from pathlib import Path
import ctypes as C,hashlib,itertools,json,os,shutil,struct,subprocess,tempfile
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[2]
out=HERE/'_stage_backend';out.mkdir(exist_ok=True);source=(HERE.parent/'runtime/world_backend.c').read_text()
for name in ['world_backend.h','world_ship_reserves.h','world_factions.h','special_scene.inc','validated_world.inc']:source=source.replace('"'+name+'"','"../../runtime/'+name+'"')
source=source.replace('"world_catalogue.h"','"../alias_runtime/world_catalogue.h"');(out/'world_backend.c').write_text(source)
cache=HERE.parent/'compiler_cache';env=os.environ.copy()
for key,name in [('ZIG_LOCAL_CACHE_DIR','alias-stage-local'),('ZIG_GLOBAL_CACHE_DIR','global'),('TEMP','tmp'),('TMP','tmp')]:
 p=cache/name;p.mkdir(exist_ok=True);env[key]=str(p)
subprocess.run([str(WORK/'_tools/ziglang/zig.exe'),'cc','-target','x86_64-windows-gnu','-shared','-O2','-Wall','-Wextra','-Werror','-o',str(out/'AliasStageFixture.dll'),str(out/'world_backend.c'),'-lbcrypt','-lkernel32'],cwd=out,env=env,check=True)
lib=C.CDLL(str(out/'AliasStageFixture.dll'));err=C.create_string_buffer(512);destination=C.create_string_buffer(260)
class Settings(C.Structure):_fields_=[('size',C.c_uint32),('difficulty',C.c_int32),('islandSize',C.c_int32),('islandCount',C.c_int32),('spacing',C.c_int32),('aiCount',C.c_int32),('cultures',C.c_uint32),('factions',C.c_uint32)]
class Island(C.Structure):_fields_=[(n,C.c_uint32) for n in ['id','x','y','width','height','templateIndex','cropMask','mineralMask','cultures','climate']]
lib.WorldSettingsBuildPlan.argtypes=[C.POINTER(Settings),C.c_uint32,C.c_void_p,C.c_uint32];lib.WorldSettingsPlanIsland.argtypes=[C.c_uint32,C.POINTER(Island)];lib.WorldSettingsStageScene.argtypes=[C.POINTER(Settings),C.c_char_p,C.c_uint32,C.c_void_p,C.c_uint32,C.c_void_p,C.c_uint32];lib.WorldSettingsPrepareScene.argtypes=[C.c_void_p,C.c_void_p]
ROOT=WORK.parent;cat=json.loads((WORK/'world_data/catalogue.json').read_text());manifest=json.loads((HERE/'alias_manifest.json').read_text());aliases={p['template_index']:p for p in manifest['copies']};rows=[]
def plan(s):
 assert lib.WorldSettingsBuildPlan(C.byref(s),913,err,len(err)),err.value;plans=[]
 for i in range(lib.WorldSettingsPlanCount()):p=Island();assert lib.WorldSettingsPlanIsland(i,C.byref(p));plans.append(p)
 return plans
with tempfile.TemporaryDirectory(prefix='alias-stage-',dir=HERE) as directory:
 root=Path(directory).resolve();assert root.is_relative_to(HERE.resolve())
 (root/'Scenes').mkdir()
 def populate(plans):
  for p in plans:
   if p.templateIndex in aliases:
    relative=aliases[p.templateIndex]['copy_relative_path'];source=HERE/'alias_payload'/relative
   else:relative=cat['templates'][p.templateIndex]['path'];source=ROOT/relative
   target=root/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
   folder=['polar','tundra','nord','praerie','dschungel','steppe'][p.climate];prefix=['Po','T','N','Pr','D','S'][p.climate]
   dummy=Path('Scenes')/'islands'/folder/f'{prefix}_{p.width:03}x{p.height:03}_dummy.scp';target=root/dummy;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/dummy,target)
 for difficulty,factions in itertools.product(range(3),range(4)):
  s=Settings(32,difficulty,0,24,16,0,255,factions);plans=plan(s);populate(plans);destination.value=b''
  try:
   assert lib.WorldSettingsStageScene(C.byref(s),str(root).encode(),913,destination,len(destination),err,len(err)),err.value
   generated=Path(destination.value.decode());assert generated.resolve().is_relative_to(root/'Scenes') and generated.exists()
   scene=C.create_string_buffer(0x5400);nodes=[C.create_string_buffer(0x170) for p in plans]
   for i,(p,node) in enumerate(zip(plans,nodes)):
    struct.pack_into('<Q',node,8,C.addressof(nodes[i+1]) if i+1<len(nodes) else 0);struct.pack_into('<HHHHIH',node,0x10,p.x,p.y,p.width,p.height,p.id,p.climate)
   struct.pack_into('<Q',scene,0x53f0,C.addressof(nodes[0]));assert lib.WorldSettingsPrepareScene(scene,0)
   pirates=0
   for p,node in zip(plans,nodes):
    path=node.raw[0x1e:0x122].split(b'\0')[0].decode();expected=root/(aliases[p.templateIndex]['copy_relative_path'] if p.templateIndex in aliases else cat['templates'][p.templateIndex]['path']);assert path==str(expected)
    if p.templateIndex in aliases:pirates+=1;assert expected.parent==root/'WorldSettingsIslands/Nord';assert hashlib.sha256(expected.read_bytes()).hexdigest()==aliases[p.templateIndex]['copy_sha256']
   assert pirates==bool(factions&1);rows.append(dict(difficulty=difficulty,factions=factions,selected_alias_assets=pirates,committed_nodes=len(plans),path_and_hash_verified=True))
  finally:lib.WorldSettingsFinishAttempt(0)
  assert not generated.exists()
 s=Settings(32,1,0,24,16,0,255,1);plans=plan(s);populate(plans);selected=next(p for p in plans if p.templateIndex in aliases);target=root/aliases[selected.templateIndex]['copy_relative_path'];original=target.read_bytes();failures=[]
 for kind in ['missing','changed']:
  if kind=='missing':target.unlink()
  else:target.write_bytes(original+b'changed')
  assert not lib.WorldSettingsStageScene(C.byref(s),str(root).encode(),913,destination,len(destination),err,len(err)) and b'catalogue' in err.value
  assert not list((root/'Scenes').glob('WorldSettings_*.sze'));failures.append(dict(kind=kind,rejected=True,error=err.value.decode()));target.write_bytes(original)
 result=dict(scope=__doc__,private_fixture_dll_sha256=hashlib.sha256((out/'AliasStageFixture.dll').read_bytes()).hexdigest(),catalogue_sha256=hashlib.sha256((HERE/'alias_runtime/world_catalogue.h').read_bytes()).hexdigest(),stage_cases=rows,missing_or_changed_alias_rejections=failures,temporary_root_deleted_after_checks=True,actual_game_runs=0)
(HERE/'alias_staging_results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'stage_cases':len(rows),'fail_closed_alias_cases':len(failures),'actual_game_runs':0}))
