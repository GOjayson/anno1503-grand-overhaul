"""Read-only human money/fleet/cargo inspection of a native full save.

The caller must identify the selected options. This checks serialized player
and fleet values; behavior, navigation, diplomacy and Food production require play.
The default requires exact chosen money and initial fleet positions. Optional
observed mode reports later cash/positions, bounds cash by the chosen start and
requires ships in world bounds outside saved island rectangles. It does not
prove initial cash/positions. Fleet types, health, cannons and cargo stay exact.
Cash/cargo/coordinates may change during play; a progressed save can fail
without implying that the initial runtime certificate failed.
"""
from pathlib import Path
from types import SimpleNamespace
import argparse,hashlib,json,math,re,struct,sys
HERE=Path(__file__).resolve().parent
sys.dont_write_bytecode=True

def read_chunk(data,at,end=None):
 end=len(data) if end is None else end
 require(0<=at<=end<=len(data) and end-at>=16,'Truncated native chunk header')
 raw=data[at:at+12];require(re.fullmatch(rb'[A-Z0-9_]{1,12}\x00*',raw) is not None,'Invalid native chunk tag')
 length=struct.unpack_from('<I',data,at+12)[0];require(length<=end-at-16,'Native chunk crosses parent')
 return SimpleNamespace(tag=raw.rstrip(b'\0').decode('ascii'),offset=at,length=length,payload=data[at+16:at+16+length],end=at+16+length)
def chunks(data,start,end):
 at=start
 while at<end:
  part=read_chunk(data,at,end);yield part;at=part.end
 require(at==end,'Native chunks do not consume parent')
def read_container(data):
 root=read_chunk(data,0);require(root.tag in ('ANNO','ANNOADDON1'),'Unsupported native root')
 return root,data[root.end:]

def require(ok,message):
 if not ok:raise ValueError(message)
def fields(p,at=0):
 result=[]
 while at<len(p):
  require(len(p)-at>=8,'Truncated native field header')
  require(re.fullmatch(rb'[A-Z0-9_]{1,6}\x00*',p[at:at+6]) is not None,'Invalid native field tag')
  size=struct.unpack_from('<H',p,at+6)[0];header=8
  if size>=0xff00:
   require(len(p)-at>=10,'Truncated extended native field header');size=((size&255)<<16)|struct.unpack_from('<H',p,at+8)[0];header=10
  require(size<=len(p)-at-header,'Native field crosses parent')
  result.append((p[at:at+6].rstrip(b'\0').decode('ascii'),p[at+header:at+header+size],at));at+=header+size
 return result
def one(items,tag):
 found=[value for name,value,at in items if name==tag];require(len(found)==1,'Expected one field '+tag);return found[0]
def inspect(data,difficulty,money,fleet,observed=False):
 require(difficulty in ('easy','medium','hard'),'Unsupported selected difficulty')
 require(money in (10000,30000,50000,80000,100000),'Unsupported selected starting money')
 require(fleet in ('single','war','merchant'),'Unsupported selected fleet')
 require(type(observed) is bool,'Observed inspection mode must be a boolean')
 root,trailer=read_container(data);require(root.tag=='ANNOADDON1' and not trailer,'Expected one fully consumed native full-save container')
 parts=list(chunks(data,16,root.end));require(not any(c.tag=='SCENE' for c in parts),'This is a source scene, not a native full save')
 saved_islands=[]
 if observed:
  require(not any(c.tag in ('INSELLNK','INSELDUMMY') for c in parts),'Observed water check cannot use external/unloaded island references')
  for c in parts:
   if c.tag!='INSEL5':continue
   require(len(c.payload)>=12,'Saved island geometry is truncated')
   x,y,w,h,ident=struct.unpack_from('<HHHHI',c.payload)
   require(w>0 and h>0 and x+w<=1024 and y+h<=1024,'Saved island geometry leaves the supported world')
   saved_islands.append(dict(id=ident,x=x,y=y,width=w,height=h))
  require(1<=len(saved_islands)<=128 and len({i['id'] for i in saved_islands})==len(saved_islands),'Observed water check requires a nonempty saved island-rectangle list with unique IDs')
 basics=[];states=[];all_ids=[]
 for c in parts:
  if c.tag!='SPIELER':continue
  require(len(c.payload)>=8,'Truncated player prefix');version,ident=struct.unpack_from('<II',c.payload);require(version==0 and ident<32,'Unsupported saved player prefix')
  fs=fields(c.payload,8)
  for tag,p,at in fs:
   if tag in ('SCHIFF','SCHI64'):
    require(len(p)>=(16 if tag=='SCHIFF' else 20),'Truncated saved ship prefix')
    sid=struct.unpack_from('<H' if tag=='SCHIFF' else '<I',p)[0];require(sid!=0xffffffff,'Saved ship retains an unassigned ID');all_ids.append(sid)
  if ident==0:
   if fs and fs[0][0]=='HEAD':basics.append(fs)
   else:states.append(fs)
 require(len(basics)==len(states)==1,'Missing or duplicated paired human basic/state records')
 require(len(all_ids)==len(set(all_ids)),'Saved ship IDs are duplicated')
 basic=one(basics[0],'HEAD');require(len(basic)==108 and struct.unpack_from('<I',basic)[0]==11,'Saved human basic HEAD differs')
 actual_money=struct.unpack_from('<i',basic,4)[0]
 if observed:require(0<=actual_money<=money,f'Observed saved cash is outside the selected starting-money bound: chosen {money}, actual {actual_money}.')
 else:require(actual_money==money,f'Saved money differs: expected {money}, actual {actual_money}. A progressed save may have paid upkeep; --observed reports that snapshot without verifying the initial amount.')
 candidates=[(tag,p) for tag,p,at in states[0] if tag in ('SCHIFF','SCHI64')]
 require(len(candidates)==(1 if fleet=='single' else 3),'Saved human ship count differs')
 base=(450.5,422.5) if difficulty=='medium' else (566.5,435.5)
 expected=[(1502 if fleet=='single' else 1503,*base)]
 if fleet!='single':expected += [(1504 if fleet=='war' else 1502,base[0]-6,base[1]+6),(1504 if fleet=='war' else 1502,base[0]+6,base[1]+6)]
 seen=set();ships=[]
 for tag,p in candidates:
  if tag=='SCHIFF':ident,definition=struct.unpack_from('<HH',p);owner=p[4];x,y=struct.unpack_from('<ff',p,8);prefix=16
  else:ident=struct.unpack_from('<I',p)[0];definition=struct.unpack_from('<H',p,4)[0];owner=p[6];x,y=struct.unpack_from('<ff',p,12);prefix=20
  require(owner==0,'Saved human ship prefix belongs to another owner')
  require(math.isfinite(x) and math.isfinite(y) and 0<=x<1024 and 0<=y<1024,'Saved ship coordinates are nonfinite or outside the supported world')
  if observed:
   matches=[i for i,row in enumerate(expected) if row[0]==definition and i not in seen]
   require(matches,'Observed fleet composition differs from the chosen ship classes')
   index=min(matches,key=lambda i:(expected[i][1]-x)**2+(expected[i][2]-y)**2)
   require(not any(i['x']<=x<i['x']+i['width'] and i['y']<=y<i['y']+i['height'] for i in saved_islands),'Observed ship overlaps a saved island rectangle; ocean position is not established')
  else:
   matches=[i for i,row in enumerate(expected) if row==(definition,x,y)];require(len(matches)==1 and matches[0] not in seen,'Saved fleet definition, initial coordinates or uniqueness differs');index=matches[0]
  seen.add(index)
  fs=fields(p,prefix);head=one(fs,'HEAD');cargo=one(fs,'WAREN')
  require(len(head)==16 and head[8]==(6 if fleet=='war' else 0),'Saved equipped cannon count differs from the fleet maximum')
  require(head[9]==128,'Saved starting ship is not at full health')
  holds={1502:4,1503:8,1504:2}[definition];require(len(cargo)==holds*8,'Saved cargo hold count differs from its exact ship class')
  expected_cargo=[(0,0)]*holds
  if fleet=='merchant':expected_cargo[:2]=[(41,40),(42,40)]
  elif not index:expected_cargo[:4]=[(42,50),(26,10),(41,50),(41,50 if difficulty=='easy' else 30)]
  cargos=[]
  for i in range(holds):
   good,quantity,flags=struct.unpack_from('<HHI',cargo,i*8)
   require((good,quantity)==expected_cargo[i],f'Saved cargo differs in hold {i}: expected {expected_cargo[i]}, actual {(good,quantity)}')
   require(quantity<=50,'Saved cargo exceeds the verified50t per-hold capacity')
   cargos.append(dict(slot=i,good_id=good,good_name={0:'empty',41:'tools',42:'wood',26:'food'}.get(good),tons=quantity,unmapped_flags=flags))
  ships.append(dict(native_tag=tag,assigned_id=ident,definition=definition,type={1502:'small trade',1503:'large trade',1504:'small war'}[definition],x=x,y=y,nearest_selected_spawn_x=expected[index][1],nearest_selected_spawn_y=expected[index][2],matches_selected_spawn_coordinates=(x,y)==expected[index][1:],outside_saved_island_rectangles=True if observed else None,unmapped_prefix_bytes_hex=p[5:8].hex() if prefix==16 else p[7:12].hex(),equipped_cannons=head[8],health_ratio_out_of128=head[9],cargo=cargos))
 require(seen==set(range(len(expected))),'Saved fleet is incomplete')
 return dict(scope=__doc__,inspection_mode='observed_cash_positions_exact_fleet' if observed else 'strict_initial_state',selected=dict(difficulty=difficulty,starting_money=money,starting_fleet=fleet),actual_money=actual_money,money_difference_from_selected_start=actual_money-money,exact_initial_cash_match=actual_money==money,initial_money_verified_by_this_save=not observed,initial_money_scope='Observed cash snapshot only; initial amount requires the prior runtime certificate and its game-run evidence.' if observed else 'The serialized human balance equals the chosen initial amount.',initial_positions_verified_by_this_save=not observed,all_saved_positions_equal_selected_spawns=all(s['matches_selected_spawn_coordinates'] for s in ships),position_scope='Observed positions are reported and outside every saved island rectangle; initial coordinate equality is neither required nor claimed.' if observed else 'Every ship equals its selected initial spawn coordinates.',saved_island_rectangles_checked=len(saved_islands),fleet_check='Exact chosen ship count, definitions, full health, equipped cannons and per-boat cargo.',human_ship_count=len(ships),ships=ships,save_sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),automated_serialized_state_check=True,behavior_verified=False)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('save',type=Path);p.add_argument('--difficulty',choices=['easy','medium','hard'],required=True);p.add_argument('--money',type=int,choices=[10000,30000,50000,80000,100000],required=True);p.add_argument('--fleet',choices=['single','war','merchant'],required=True);p.add_argument('--observed',action='store_true',help='Report later cash and ocean positions without claiming initial cash/coordinates. Keep count/classes/health/guns/cargo exact.');p.add_argument('--output',type=Path)
 a=p.parse_args();report=inspect(a.save.read_bytes(),a.difficulty,a.money,a.fleet,a.observed);report['save_path']=str(a.save.resolve());text=json.dumps(report,indent=2)
 if a.output:a.output.write_text(text+'\n')
 print(text)
if __name__=='__main__':main()
