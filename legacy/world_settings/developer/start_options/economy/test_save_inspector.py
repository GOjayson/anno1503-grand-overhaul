"""Self-contained saved-state inspector tests from production API scene records.

Recorded, validated StageScene player records are normalized into synthetic
full-save-shaped containers. Assigned escort IDs and merged player state are
fixture operations; one artificial island rectangle is added for ocean checks.
They are not evidence that the game saved or loaded this content.
No developer fixture DLL or external Python package is needed.
"""
from pathlib import Path
import hashlib,itertools,json,struct,sys
sys.dont_write_bytecode=True
from inspect_start_save import inspect,fields,chunks,require
HERE=Path(__file__).resolve().parent
def make_chunk(tag,payload):return tag.encode('ascii').ljust(12,b'\0')+struct.pack('<I',len(payload))+payload
fixture_path=HERE/'production_stage_fixtures.json';fixture=json.loads(fixture_path.read_text());production=json.loads((HERE/'production_stage_results.json').read_text())
require(fixture['runtime_sha256']==production['runtime_sha256'] and fixture['actual_game_runs']==0,'Production scene-fixture fingerprint differs')
cases=fixture['cases'];require({(x['difficulty'],x['money'],x['fleet']) for x in cases}==set(itertools.product(range(3),[10000,30000,50000,80000,100000],range(3))) and len(cases)==45,'Production fixture matrix is incomplete or duplicated')
positives=0;negatives=0;observed_positives=0;observed_rejections=0;prefix_flags_accepted=0;wrong_owners_rejected=0;observed_moves_accepted=0;bad_positions_rejected=0
for row in cases:
 difficulty,money,fleet=row['difficulty'],row['money'],row['fleet'];human=[bytes.fromhex(v) for v in row['human_player_payloads_hex']]
 require(len(human)==(3 if fleet else 2),'Unexpected production human player shape')
 state=bytearray(human[1]);state.extend(human[2][8:] if fleet else b'')
 # Native player saving merges incremental fields into its one state record;
 # fake assigned IDs are strictly confined to these synthetic input fixtures.
 assigned=0
 for tag,ship,at in fields(state,8):
  if tag=='SCHI64':struct.pack_into('<I',state,at+8,100+assigned);assigned+=1
 save=make_chunk('ANNOADDON1',make_chunk('INSEL5',struct.pack('<HHHHI',16,16,64,64,0))+make_chunk('SPIELER',human[0])+make_chunk('SPIELER',bytes(state)))
 level=['easy','medium','hard'][difficulty];fleet_name=['single','war','merchant'][fleet]
 report=inspect(save,level,money,fleet_name);require(report['human_ship_count']==(1 if not fleet else 3),'Synthetic normalized ship count differs');positives+=1
 def reject(data,why):
  global negatives,observed_rejections
  try:inspect(data,level,money,fleet_name)
  except ValueError:negatives+=1
  else:raise AssertionError('Malformed saved '+why+' was accepted')
  if why!='money':
   try:inspect(data,level,money,fleet_name,observed=True)
   except ValueError:observed_rejections+=1
   else:raise AssertionError('Observed mode weakened saved '+why+' validation')
 for c in chunks(save,16,len(save)):
  if c.tag!='SPIELER':continue
  for tag,p,at in fields(c.payload,8):
   if tag=='HEAD':
    money_at=c.offset+16+at+8+4
    bad=bytearray(save);struct.pack_into('<i',bad,money_at,money-1);reject(bytes(bad),'money')
    observed=bytearray(save);struct.pack_into('<i',observed,money_at,money-16)
    try:inspect(bytes(observed),level,money,fleet_name)
    except ValueError:pass
    else:raise AssertionError('Strict initial-money check accepted a progressed cash snapshot')
    snapshot=inspect(bytes(observed),level,money,fleet_name,observed=True)
    require(snapshot['actual_money']==money-16 and snapshot['initial_money_verified_by_this_save'] is False and snapshot['exact_initial_cash_match'] is False,'Observed mode claimed initial-cash equality');observed_positives+=1
    for illegal in (-1,money+1):
     invalid=bytearray(save);struct.pack_into('<i',invalid,money_at,illegal)
     try:inspect(bytes(invalid),level,money,fleet_name,observed=True)
     except ValueError:observed_rejections+=1
     else:raise AssertionError('Observed mode accepted invalid cash bounds')
   if tag in ('SCHIFF','SCHI64'):
    prefix=16 if tag=='SCHIFF' else 20
    if tag=='SCHIFF':
     changed_flags=bytearray(save);changed_flags[c.offset+16+at+8+5]=8
     require(inspect(bytes(changed_flags),level,money,fleet_name)['human_ship_count']==report['human_ship_count'],'Legacy prefix flags were misread as owner bits');prefix_flags_accepted+=1
     wrong_owner=bytearray(save);wrong_owner[c.offset+16+at+8+4]=1
     for observed_mode in (False,True):
      try:inspect(bytes(wrong_owner),level,money,fleet_name,observed_mode)
      except ValueError:wrong_owners_rejected+=1
      else:raise AssertionError('Actual owner-byte mismatch was accepted')
     start=c.offset+16+at+8
     current_x,current_y=struct.unpack_from('<ff',save,start+8)
     changed_position=bytearray(save);struct.pack_into('<ff',changed_position,start+8,current_x+1.25,current_y-.75)
     try:inspect(bytes(changed_position),level,money,fleet_name)
     except ValueError:pass
     else:raise AssertionError('Strict initial position check accepted a moved ship')
     moved=inspect(bytes(changed_position),level,money,fleet_name,observed=True)
     require(moved['initial_positions_verified_by_this_save'] is False and moved['all_saved_positions_equal_selected_spawns'] is False,'Observed movement claimed initial coordinate equality');observed_moves_accepted+=1
     for illegal_position in ((32.5,32.5),(-1,500)):
      invalid=bytearray(save);struct.pack_into('<ff',invalid,start+8,*illegal_position)
      try:inspect(bytes(invalid),level,money,fleet_name,observed=True)
      except ValueError:bad_positions_rejected+=1
      else:raise AssertionError('Observed ship island collision/world bounds check was bypassed')
    for field,body,offset in fields(p,prefix):
     start=c.offset+16+at+8+offset+8
     if field=='HEAD':
      bad=bytearray(save);bad[start+8]=5 if fleet else 1;reject(bytes(bad),'cannons')
      bad=bytearray(save);bad[start+9]=127;reject(bytes(bad),'health')
     if field=='WAREN':bad=bytearray(save);struct.pack_into('<H',bad,start+2,39);reject(bytes(bad),'cargo')
 reject(save[:-1],'container boundary')
report=dict(scope=__doc__,fixture_sha256=hashlib.sha256(fixture_path.read_bytes()).hexdigest(),production_runtime_sha256=fixture['runtime_sha256'],positive_save_shapes=positives,malformed_rejections=negatives,observed_cash_snapshots_accepted_without_initial_money_claim=observed_positives,observed_invalid_cash_or_fleet_rejections=observed_rejections,legacy_prefix_flag_cases_accepted=prefix_flags_accepted,actual_owner_byte_mismatches_rejected=wrong_owners_rejected,observed_moves_accepted_without_initial_position_claim=observed_moves_accepted,observed_island_collisions_or_world_bounds_rejected=bad_positions_rejected,strict_money_and_position_checks_preserved=True,actual_game_runs=0)
(HERE/'save_inspector_results.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
