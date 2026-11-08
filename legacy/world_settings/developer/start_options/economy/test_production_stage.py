"""Stage180 actual SZE files through the complete production runtime DLL.

The DLL's real exported planner, catalogue SHA checks, complete scene builder,
filesystem writes, pending-attempt gate and cleanup execute. The marked game
copy is used only for asset reads and temporary scene files. No hooks are
installed, no game process is launched and no UI or gameplay is claimed.
"""
from pathlib import Path
import argparse,ctypes as C,hashlib,itertools,json,os,struct,sys
sys.dont_write_bytecode=True
from inspect_start_save import read_container,chunks,fields,one,require
HERE=Path(__file__).resolve().parent
MARKER='.anno1503-worldsettings-test-copy.json'
EXE_SHA='1a4bebe7c676a5904834b9e67e936187729dc67c013a4fb4fd64986a3cb8e95a'
STOCK=[('01_1024_easy_256.sze','3e0d2c72e1ae87b76cc817f0aead7198b4f0509cb11a5246463e338ccf060e05'),
       ('03_1024_med_256.sze','f25b19ca1806b3e0d7093167fc240cb5c027efff4049781fe9df4973636d2de8'),
       ('06_1024_heavy_256.sze','d31527dc6902de498e5bb43053939fba0d6460cbfe10abef9ec5eed2f71e4453')]
class Settings(C.Structure):
 _fields_=[('size',C.c_uint32)]+[(x,C.c_int32) for x in ['difficulty','islandSize','islandCount','spacing','aiCount']]+[(x,C.c_uint32) for x in ['cultures','factions']]+[(x,C.c_int32) for x in ['startingMoney','startingFleet','aiDifficulty','plantFertility','mineralFertility','worldSize']]
class Island(C.Structure):
 _fields_=[(name,C.c_uint32) for name in ['id','x','y','width','height','templateIndex','cropMask','mineralMask','cultures','climate']]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def field_bytes(payload,start=8):
 fs=fields(payload,start)
 return [(tag,body,payload[at:(fs[i+1][2] if i+1<len(fs) else len(payload))]) for i,(tag,body,at) in enumerate(fs)]
def scene(data):
 root,trailer=read_container(data);require(not trailer and root.end==len(data),'Source/generated scene has a trailer')
 items=list(chunks(data,16,root.end));require(len(items)==1 and items[0].tag=='SCENE' and items[0].offset==16,'Expected one native SCENE')
 return list(chunks(data,32,root.end))
def player_id(c):
 require(c.tag=='SPIELER' and len(c.payload)>=8,'Invalid player chunk')
 version,pid=struct.unpack_from('<II',c.payload);require(version==0 and pid<32,'Unexpected player prefix');return pid
def basic(c):return c.payload[8:14]==b'HEAD\0\0'
def classes(parts):
 out={}
 for c in parts:
  if c.tag=='SPIELER' and basic(c):
   pid=player_id(c);require(pid not in out,'Duplicate basic player')
   head=one(fields(c.payload,8),'HEAD');require(len(head)==108,'Unexpected basic HEAD length');out[pid]=struct.unpack_from('<I',head)[0]
 return out
def expected_cpu(p):
 out=bytearray(p);count=0
 for tag,body,at in fields(p,8):
  if tag!='COMP' or len(body)<8 or struct.unpack_from('<I',body)[0]!=12:continue
  text=body[8:];needle=b'SUSPEND=0\0';require(text.count(needle)==1,'Stock CPU suspension is not unique')
  header=8 if struct.unpack_from('<H',p,at+6)[0]<0xff00 else 10
  out[at+header+8+text.index(needle)+8]=ord('1');count+=1
 return bytes(out),count
def without_city(p):
 out=p[:8]
 for tag,body,raw in field_bytes(p):
  if tag!='STADT2':out+=raw
 return out
def ship(p,tag):
 if tag=='SCHIFF':
  require(len(p)>=16,'Truncated small-ID ship prefix');ident,definition,owner,x,y=struct.unpack_from('<HHIff',p);prefix=16
 elif tag=='SCHI64':
  require(len(p)>=20,'Truncated expanded-ID ship prefix');ident=struct.unpack_from('<I',p)[0];definition=struct.unpack_from('<H',p,4)[0];owner=p[6];x,y=struct.unpack_from('<ff',p,12);prefix=20
  require(p[7:12]==b'\0'*5,'Unexpected expanded ship prefix flags')
 else:raise ValueError('Unknown native ship field')
 fs=fields(p,prefix);head=one(fs,'HEAD');cargo=one(fs,'WAREN');private=one(fs,'PRIVAT')
 require(len(head)==16,'Unexpected ship HEAD')
 return dict(id=ident,definition=definition,owner=owner,x=x,y=y,head=head,cargo=cargo,private=private,fields=fs,prefix=p[:prefix],tag=tag)
def validate_fleet(original,actual,extra,s):
 old_ships=[(tag,body) for tag,body,raw in field_bytes(original) if tag in ('SCHIFF','SCHI64')]
 require(len(old_ships)==1 and old_ships[0][0]=='SCHIFF','Stock human fleet differs')
 old=ship(old_ships[0][1],'SCHIFF')
 fs=field_bytes(actual);main=[(tag,body) for tag,body,raw in fs if tag in ('SCHIFF','SCHI64')]
 require(len(main)==1 and main[0][0]=='SCHIFF','Main ship is absent or duplicated')
 require([(tag,raw) for tag,body,raw in field_bytes(original) if tag not in ('SCHIFF','SCHI64')]==[(tag,raw) for tag,body,raw in fs if tag not in ('SCHIFF','SCHI64')],'Human selection/controller/other state changed')
 require(actual[:8]==original[:8],'Human state identity changed')
 all_ships=[ship(main[0][1],main[0][0])]
 if s.startingFleet:
  require(extra is not None and extra[:8]==b'\0'*8,'Missing owner0 incremental escort record')
  e=field_bytes(extra);require([x[0] for x in e]==['SCHI64','SCHI64'],'Escorts must be two exact native SCHI64 fields')
  all_ships.extend(ship(body,tag) for tag,body,raw in e)
 else:
  require(extra is None,'Single fleet emitted an extra player record');require(main[0][1]==old_ships[0][1],'Single ship stock bytes changed')
 expected_types=[1502] if s.startingFleet==0 else [1503,1504 if s.startingFleet==1 else 1502,1504 if s.startingFleet==1 else 1502]
 positions=[(old['x'],old['y']),(old['x']-6,old['y']+6),(old['x']+6,old['y']+6)]
 require(len(all_ships)==len(expected_types),'Human starting ship count differs')
 result=[]
 for i,entry in enumerate(all_ships):
  require(entry['owner']==0 and entry['definition']==expected_types[i] and (entry['x'],entry['y'])==positions[i],'Human starting ship owner, definition or coordinates differ')
  require(entry['id']==(old['id'] if i==0 else 0xffffffff),'Main identity or native automatic escort ID differs')
  require(entry['head'][8]==(6 if s.startingFleet==1 else 0) and entry['head'][9]==128,'Fleet is not fully equipped/full health as selected')
  holds={1502:4,1503:8,1504:2}[entry['definition']];require(len(entry['cargo'])==holds*8,'Incorrect native cargo hold count')
  quantities=[struct.unpack_from('<HHI',entry['cargo'],j*8) for j in range(holds)]
  expected=[(0,0,0)]*holds
  if s.startingFleet==2:expected[:2]=[(41,40,0),(42,40,0)]
  elif i==0:expected[:4]=[struct.unpack_from('<HHI',old['cargo'],j*8) for j in range(4)]
  require(quantities==expected and all(q[1]<=50 for q in quantities),'Selected starting cargo differs or exceeds capacity')
  if i==0:require(entry['private']==old['private'],'Stock human crew/name/trade state changed')
  else:
   private=fields(entry['private']);require([tag for tag,value,at in private]==['NAME','VERK'],'Escort has unexpected private state')
   require(one(private,'VERK')==b'\xff\xff','Escort has an unwanted trade route')
  result.append(dict(native_tag=entry['tag'],definition=entry['definition'],cannons=entry['head'][8],cargo=[dict(good_id=q[0],tons=q[1]) for q in quantities],x=entry['x'],y=entry['y']))
 return result
def validate_players(stock_parts,out_parts,s):
 originals=[c for c in stock_parts if c.tag=='SPIELER'];actuals=[c for c in out_parts if c.tag=='SPIELER'];types=classes(stock_parts)
 faction={pid:1 if typ==15 else 2 for pid,typ in types.items() if typ in (15,16)}
 require(sorted(faction.values())==[1,2],'Stock special player identities differ')
 retained=[c for c in originals if player_id(c) not in faction or s.factions&faction[player_id(c)]]
 require(len(actuals)==len(retained)+(1 if s.startingFleet else 0),'Retained player/escort record count differs')
 base_actual=actuals[:-1] if s.startingFleet else actuals
 require([(player_id(c),basic(c)) for c in base_actual]==[(player_id(c),basic(c)) for c in retained],'Original player identities/order changed')
 if s.startingFleet:
  extra=actuals[-1];require(player_id(extra)==0 and not basic(extra),'Final player is not the incremental human escort record')
  extra_index=out_parts.index(extra);require(extra_index+1<len(out_parts) and out_parts[extra_index+1].tag=='BIGBROTHER','Escort record is not immediately after all original players/before scripting')
 else:extra=None
 suspended=0;fleet_report=None;venetian_removed=0
 for old,new in zip(retained,base_actual):
  pid=player_id(old);typ=types[pid]
  if pid==0 and basic(old):
   expected=bytearray(old.payload);head=one(fields(old.payload,8),'HEAD');require(struct.unpack_from('<I',head)[0]==11,'Human type differs')
   at=next(at for tag,body,at in fields(old.payload,8) if tag=='HEAD');struct.pack_into('<I',expected,at+8+4,s.startingMoney)
   require(new.payload==bytes(expected),'Human starting money/basic identity changed incorrectly')
  elif pid==0:
   fleet_report=validate_fleet(old.payload,new.payload,extra.payload if extra else None,s)
  elif typ==12:
   expected,count=expected_cpu(old.payload);suspended+=count;require(new.payload==expected,'Ordinary CPU changed beyond the exact initial suspension digit')
  elif typ==16 and not basic(old):
   expected=without_city(old.payload);venetian_removed+=len(old.payload)-len(expected);require(new.payload==expected,'Venetian map-city fix altered other controller/state bytes')
  else:require(new.payload==old.payload,'An unrelated player identity/state byte changed')
 require(suspended==(3 if s.difficulty==0 else 4),'Wrong ordinary CPU suspension count')
 require(fleet_report is not None,'Human state absent')
 return dict(ordinary_cpu_records_suspended=suspended,other_player_bytes_preserved=True,venetian_map_bytes_removed=venetian_removed,fleet=fleet_report,special_ids=faction)
def validate_scene(original,data,s,plan):
 old=scene(original);new=scene(data);players=validate_players(old,new,s)
 # Every non-map/non-player chunk is preserved except the three known native
 # resource request payloads and exact disabled faction alias lines.
 omitted={'SPIELER','INSEL5','INSELLNK'}
 expected=[]
 for c in old:
  if c.tag in omitted:continue
  payload=c.payload
  if c.tag in ('ROHSTOFF','ERZE','SCHATZ'):payload=b'\0'*len(payload)
  elif c.tag=='BIGBROTHER':
   remove={('"'+('PIRAT01' if flag==1 else 'VENEZIA01')+'" '+str(pid)).encode('ascii') for pid,flag in players['special_ids'].items() if not(s.factions&flag)}
   lines=payload.splitlines(keepends=True);found=[line.rstrip(b'\r\n') for line in lines if line.rstrip(b'\r\n') in remove]
   require(set(found)==remove and len(found)==len(remove),'Disabled special alias is absent or duplicated');payload=b''.join(line for line in lines if line.rstrip(b'\r\n') not in remove)
  expected.append((c.tag,payload))
 require([(c.tag,c.payload) for c in new if c.tag not in omitted]==expected,'Unrelated scene bytes/order changed')
 links=[c for c in new if c.tag=='INSELLNK'];require(len(links)==s.islandCount and not any(c.tag=='INSEL5' for c in new),'Wrong number or form of generated islands')
 for c,p in zip(links,plan):
  x,y,w,h,ident=struct.unpack_from('<HHHHI',c.payload);require((ident,x,y,w,h)==(p.id,p.x,p.y,p.width,p.height),'Generated link geometry differs from actual exported plan')
  require(c.payload[12:].endswith(b'_dummy.scp\0') and b'..' not in c.payload[12:],'Unexpected generated island alias')
  require(p.x%8==p.y%8==0 and p.x+p.width<=1024 and p.y+p.height<=1024,'Native island grid/bounds differ')
  for q in plan[:ident]:require(p.x>=q.x+q.width or q.x>=p.x+p.width or p.y>=q.y+q.height or q.y>=p.y+p.height,'Generated islands overlap')
  for boat in players['fleet']:require(not(p.x-16<=boat['x']<p.x+p.width+16 and p.y-16<=boat['y']<p.y+p.height+16),'A selected fleet ship violates the island water clearance')
 crops=minerals=cultures=climates=0
 for p in plan:crops|=p.cropMask;minerals|=p.mineralMask;cultures|=p.cultures;climates|=1<<p.climate
 require(crops==0x1ffff and minerals&0x2f==0x2f and cultures==255 and climates==63,'Exported plan lacks required crop/mineral/culture/climate coverage')
 return players
def architecture(path):
 d=path.read_bytes();require(d[:2]==b'MZ','Runtime is not a PE file');at=struct.unpack_from('<I',d,60)[0]
 require(d[at:at+4]==b'PE\0\0' and struct.unpack_from('<H',d,at+4)[0]==0x8664 and struct.unpack_from('<H',d,at+24)[0]==0x20b,'Runtime is not History Edition AMD64 PE32+')
 return dict(machine='AMD64',optional_header='PE32+')
def main():
 root=next((p for p in HERE.parents if (p/'Anno1503.exe').is_file() and not (p/MARKER).exists()),None)
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--package',type=Path,default=HERE.parents[2]);parser.add_argument('--copy',type=Path,default=root/'WorldSettings_Work/game_copy' if root else None);parser.add_argument('--runtime',type=Path);parser.add_argument('--output',type=Path,default=HERE/'production_stage_results.json');args=parser.parse_args()
 require(root is not None and args.package and args.copy,'Select the installed development package/copy under the original game folder')
 package=args.package.resolve();copy=args.copy.resolve();runtime=(args.runtime or package/'native/AnnoWorldSettings.dll').resolve();source=package/'developer/source';build_path=source/'runtime_dev3/build_result.json';build=json.loads(build_path.read_text())
 guard=json.loads((copy/MARKER).read_text());require(guard.get('development_copy') is True and Path(guard['copy_root']).resolve()==copy and Path(guard['source_root']).resolve()==root.resolve() and guard.get('source_exe_sha256')==EXE_SHA,'Game-copy marker is not the verified guarded copy')
 require(copy!=root.resolve() and sha(copy/'Anno1503.exe')==sha(root/'Anno1503.exe')==EXE_SHA,'Game-copy/original executable differs')
 require(build.get('abi_size')==56 and build['sha256']==sha(runtime),'Production DLL does not match its56byte ABI/source build result')
 require(all(sha(source/name)==digest for name,digest in build['source_sha256'].items()),'Production DLL source changed after compilation')
 build_sources={name.replace('\\','/'):digest for name,digest in build['source_sha256'].items()}
 actual_start=source/'engine_resume/ai_food/experiment_runtime/start_options.inc'
 require(build_sources.get('engine_resume/ai_food/experiment_runtime/start_options.inc')==sha(actual_start),'Production start-option source differs from compiled provenance')
 arch=architecture(runtime);before_runtime=sha(runtime)
 critical=['Anno1503.exe','AnnoFrame.dll','AnnoScene.dll','AnnoWelt.dll','AnnoGame.dll','AnnoWorldSettings.dll','WorldSettingsAI/CompLogic.dll','WorldSettingsAI/CompLogicClassic.dll']
 before_files={name:sha(copy/name) for name in critical if (copy/name).is_file()};before_scenes={p.name:sha(p) for p in (copy/'Scenes').glob('WorldSettings_*.sze')}
 originals=[]
 for name,digest in STOCK:
  path=root/'Languages/Nl/Scenes/0010SingleEndlos'/name;require(sha(path)==digest and sha(copy/path.relative_to(root))==digest,'Original/copied stock difficulty source differs');originals.append(path.read_bytes())
 require(C.sizeof(Settings)==56 and C.sizeof(Island)==40,'Host ABI layout differs')
 lib=C.CDLL(str(runtime));lib.WorldSettingsSettingsSize.restype=C.c_uint32;require(lib.WorldSettingsSettingsSize()==56,'Production exported settings ABI differs')
 stage=lib.WorldSettingsStageScene;stage.argtypes=[C.POINTER(Settings),C.c_char_p,C.c_uint32,C.c_void_p,C.c_uint32,C.c_void_p,C.c_uint32];stage.restype=C.c_int
 lib.WorldSettingsFinishAttempt.argtypes=[C.c_int];lib.WorldSettingsPendingPath.restype=C.c_char_p;lib.WorldSettingsIsActive.restype=C.c_int
 lib.WorldSettingsPlanCount.restype=C.c_int;lib.WorldSettingsPlanIsland.argtypes=[C.c_uint32,C.POINTER(Island)];lib.WorldSettingsPlanIsland.restype=C.c_int
 valid=lib.WorldSettingsValidateSettings;valid.argtypes=[C.POINTER(Settings),C.c_void_p,C.c_uint32];valid.restype=C.c_int
 output=C.create_string_buffer(260);error=C.create_string_buffer(512);rows=[];fixtures=[];geometries={};pending_rejection_checked=False
 require(lib.WorldSettingsIsActive()==0 and lib.WorldSettingsPendingPath() is None,'Production runtime begins with an unexpected pending scene')
 for difficulty,money,fleet,factions in itertools.product(range(3),[10000,30000,50000,80000,100000],range(3),range(4)):
  s=Settings(56,difficulty,3,24,0,0,255,factions,money,fleet,(difficulty+fleet+factions)%4,1,1,1024);output.value=b'';path=None
  try:
   require(valid(C.byref(s),error,len(error))==1,error.value.decode('mbcs','replace'))
   require(stage(C.byref(s),str(copy).encode('mbcs'),903,output,len(output),error,len(error))==1,error.value.decode('mbcs','replace'))
   path=Path(output.value.decode('mbcs')).resolve();require(path.parent==copy/'Scenes' and path.name.startswith('WorldSettings_'+str(os.getpid())+'_') and path.suffix=='.sze','Production stage wrote outside its guarded temporary scene path')
   require(path.is_file() and lib.WorldSettingsIsActive()==1 and Path(lib.WorldSettingsPendingPath().decode('mbcs')).resolve()==path,'Production stage did not publish its actual pending file')
   require(lib.WorldSettingsPlanCount()==24,'Production exported plan count differs');plan=[]
   for i in range(24):
    island=Island();require(lib.WorldSettingsPlanIsland(i,C.byref(island))==1,'Production plan island cannot be queried');require(island.id==i,'Exported plan IDs differ');plan.append(island)
   data=path.read_bytes();detail=validate_scene(originals[difficulty],data,s,plan)
   signature=[tuple(getattr(p,name) for name,typ in Island._fields_) for p in plan]
   if factions in geometries:require(signature==geometries[factions],'Difficulty or economic options unexpectedly changed the island plan')
   else:geometries[factions]=signature
   if not pending_rejection_checked:
    second=C.create_string_buffer(260);require(stage(C.byref(s),str(copy).encode('mbcs'),903,second,len(second),error,len(error))==0 and path.is_file() and lib.WorldSettingsIsActive()==1,'Production runtime allowed a second pending scene');pending_rejection_checked=True
   rows.append(dict(difficulty=difficulty,money=money,starting_fleet=fleet,factions=factions,ai_count=0,ai_difficulty=s.aiDifficulty,scene_sha256=hashlib.sha256(data).hexdigest(),scene_bytes=len(data),**detail))
   if factions==3:fixtures.append(dict(difficulty=difficulty,money=money,fleet=fleet,human_player_payloads_hex=[c.payload.hex() for c in scene(data) if c.tag=='SPIELER' and player_id(c)==0]))
  finally:
   lib.WorldSettingsFinishAttempt(0)
   require(lib.WorldSettingsIsActive()==0 and lib.WorldSettingsPendingPath() is None,'FinishAttempt did not clear actual pending state')
   if path:require(not path.exists(),'FinishAttempt did not delete its actual generated SZE file')
  if len(rows)%30==0:print('Production staged/inspected/cleaned',len(rows),'of180',flush=True)
 rejects=[]
 for field,value in [('size',32),('size',44),('size',48),('startingMoney',12000),('startingFleet',-1),('startingFleet',3),('aiDifficulty',-1),('aiDifficulty',4),('aiCount',4),('plantFertility',-1),('plantFertility',4),('mineralFertility',-1),('mineralFertility',4)]:
  s=Settings(56,1,3,24,0,0,255,3,50000,0,1,1,1,1024);setattr(s,field,value);require(valid(C.byref(s),error,len(error))==0 and error.value,'Production UI validator accepted an invalid option');require(stage(C.byref(s),str(copy).encode('mbcs'),903,output,len(output),error,len(error))==0 and error.value,'Production planner accepted an invalid option');require(lib.WorldSettingsIsActive()==0 and lib.WorldSettingsPendingPath() is None,'Rejected option left a pending scene');rejects.append(dict(field=field,value=value))
 require(sha(runtime)==before_runtime,'Production runtime changed during the test')
 require(before_files=={name:sha(copy/name) for name in before_files},'A guarded game-copy binary changed during staging tests')
 require(before_scenes=={p.name:sha(p) for p in (copy/'Scenes').glob('WorldSettings_*.sze')},'Temporary scenes were leaked or an existing generated scene changed')
 report=dict(scope=__doc__,actual_game_runs=0,runtime_path=str(runtime),runtime_sha256=before_runtime,runtime_architecture=arch,settings_abi=56,plant_fertility='Medium fertility',mineral_fertility='Medium fertility',build_result_sha256=sha(build_path),compiled_source_sha256=build['source_sha256'],guarded_copy=str(copy),source_difficulty_sha256={name:digest for name,digest in STOCK},staged_files=len(rows),staged_files_inspected=len(rows),staged_files_cleaned=len(rows),all_ordinary_cpus_suspended=True,all_other_player_state_bytes_preserved=True,deferred_escort_fields='SCHI64 after last stock SPIELER and before BIGBROTHER',geometry_independent_of_difficulty_money_fleet=True,second_pending_attempt_rejected=pending_rejection_checked,rejected_options=rejects,guarded_copy_binaries_unchanged=before_files,preexisting_staged_scenes_unchanged=True,cases=rows)
 fixture_report=dict(scope='Human player records captured from actual validated production StageScene API outputs. They are scene fixtures, not actual game saves.',runtime_sha256=before_runtime,cases=fixtures,actual_game_runs=0)
 (args.output.parent/'production_stage_fixtures.json').write_text(json.dumps(fixture_report,indent=2)+'\n')
 args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['runtime_sha256','settings_abi','staged_files','staged_files_inspected','staged_files_cleaned','actual_game_runs']}))
if __name__=='__main__':main()
