"""Synthetic strict-container rejection checks; no game save is fabricated as evidence."""
import json,struct
from pathlib import Path
from inspect_saved_policy import inspect,MODES
from scene_catalogue import make_chunk
HERE=Path(__file__).resolve().parent
def field(tag,p):return tag.encode().ljust(6,bytes(1))+struct.pack('<H',len(p))+p
def save(mode=0,count=1,wrong=None):
 parts=[]
 for ident in range(1,4):
  head=struct.pack('<I',12)+bytes(104);parts.append(make_chunk('SPIELER',struct.pack('<II',0,ident)+field('HEAD',head)))
  active=ident<=count;flags=(0x57530000|(mode<<8)|0xfc00|15) if active else 4
  if wrong=='tag_inactive' and ident==3:flags=0x57530000
  if wrong=='untag_active' and ident==1:flags=0
  if wrong=='wrong_mode' and ident==1:flags=0x57530000|(((mode+1)%4)<<8)
  attrs=('SUSPEND='+str(int(not active))+'\0SPEZFLAG='+str(flags)+'\0').encode()
  if wrong=='duplicate_flag' and ident==1:attrs+=b'SPEZFLAG=0\0'
  comp=field('COMP',struct.pack('<II',12,ident)+attrs)
  if wrong=='missing_comp' and ident==1:comp=b''
  parts.append(make_chunk('SPIELER',struct.pack('<II',0,ident)+comp))
 if wrong=='duplicate_state':parts.append(parts[-1])
 return make_chunk('ANNOADDON1',b''.join(parts))
valid=0;rejected=[]
for mode in range(4):
 for count in range(4):
  data=save(mode,count);r=inspect(data,count,MODES[mode]);assert inspect(data,count,MODES[mode],r)['native_flags_compared_to_baseline'];valid+=1
for fault in ['tag_inactive','untag_active','wrong_mode','duplicate_flag','missing_comp','duplicate_state']:
 try:inspect(save(wrong=fault),1,'peaceful')
 except ValueError:rejected.append(fault)
 else:raise AssertionError(fault)
r=dict(scope=__doc__,valid_cases=valid,rejected=rejected,passed=True,actual_game_saves=0)
(HERE/'saved_policy_inspector_tests.json').write_text(json.dumps(r,indent=2)+'\n','utf-8');print(json.dumps(r,indent=2))
