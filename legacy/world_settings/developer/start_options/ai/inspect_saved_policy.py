"""Read-only strict native-save AI policy certificate; no process/game actions.

Checks paired ordinary CPU records, active count, mode and inactive untagged
controllers. Optional baseline comparison also verifies native low flags and
suspended controller words stayed identical. Serialized state does not prove
long-running war/defense behavior.
"""
from pathlib import Path
import argparse,hashlib,json,re,struct,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'WorldSettings_Work/world_data'))
sys.path.insert(0,str(HERE.parent/'economy'))
from scene_catalogue import read_container,chunks
from inspect_start_save import fields,require
MODES=['peaceful','easy','medium','hard'];TAG=0x57530000

def attributes(data):
 require(data.endswith(bytes(1)),'COMP attributes are not terminated')
 result={}
 for token in data.rstrip(bytes(1)).split(bytes(1)):
  key,sep,value=token.partition(b'=');require(bool(sep) and re.fullmatch(rb'[A-Z0-9_]+',key) is not None,'Invalid COMP attribute')
  result.setdefault(key.decode('ascii'),[]).append(value.decode('ascii'))
 return result

def number(attrs,key):
 values=attrs.get(key,[]);require(len(values)==1 and re.fullmatch(r'-?[0-9]+',values[0]) is not None,'Missing, duplicated or invalid COMP '+key)
 value=int(values[0]);require(-(1<<31)<=value<=(1<<32)-1,'COMP '+key+' exceeds native uint32 transport')
 return value&0xffffffff

def inspect(data,expected,mode,baseline=None):
 require(expected in range(4) and mode in MODES,'Unsupported selected opponent count or AI mode')
 root,trailer=read_container(data);require(root.tag=='ANNOADDON1' and not trailer,'Expected one fully consumed native full-save container')
 parts=list(chunks(data,16,root.end));require(not any(c.tag=='SCENE' for c in parts),'Source scene is not a native full save')
 basics={};states={};all_controllers=[]
 for c in parts:
  if c.tag!='SPIELER':continue
  require(len(c.payload)>=8,'Truncated player prefix');version,ident=struct.unpack_from('<II',c.payload);require(version==0 and ident<32,'Unsupported player prefix')
  fs=fields(c.payload,8)
  if fs and fs[0][0]=='HEAD':
   require(ident not in basics,'Duplicated basic player');head=fs[0][1];require(len(head)==108,'Unsupported basic HEAD size');basics[ident]=struct.unpack_from('<I',head)[0]
  else:
   require(ident not in states,'Duplicated state player');states[ident]=fs
   for tag,p,at in fs:
    if tag!='COMP':continue
    require(len(p)>=8,'Truncated COMP prefix');typ,pid=struct.unpack_from('<II',p);require(pid==ident,'COMP owner differs from state player')
    attrs=attributes(p[8:]);flags=number(attrs,'SPEZFLAG');suspend=number(attrs,'SUSPEND');require(suspend in (0,1),'Invalid saved suspension')
    all_controllers.append(dict(id=ident,type=typ,suspend=suspend,spezflag=flags,native_flags=flags&255,tagged=flags&0xffff0000==TAG,mode=MODES[(flags>>8)&3] if flags&0xffff0000==TAG else None,cadence=(flags>>10)&63 if flags&0xffff0000==TAG else None,offset=c.offset+16+8+at))
 cpus=[]
 for ident,typ in sorted(basics.items()):
  records=[c for c in all_controllers if c['id']==ident]
  require(len(records)<=1,'Duplicated saved COMP')
  if typ==12:
   require(len(records)==1 and records[0]['type']==12,'Missing or wrong ordinary CPU COMP');c=records[0]
   if not c['suspend']:require(c['tagged'] and c['mode']==mode,'Active CPU has no matching persisted AI policy')
   else:require(not c['tagged'] and c['spezflag']<=255,'Suspended CPU was assigned a policy or unsupported flags')
   cpus.append(c)
  else:
   require(not any(c['tagged'] for c in records),'A human/special/native controller contains an AI policy tag')
 require(3<=len(cpus)<=4,'Saved stock CPU placeholder count differs from verified range')
 require(sum(c['suspend']==0 for c in cpus)==expected,'Saved active AI count differs from selection')
 for c in all_controllers:require(c['id'] in basics,'COMP has no paired basic player')
 if baseline is not None:
  previous={c['id']:c for c in baseline['ordinary_cpu_controllers']}
  require(set(previous)=={c['id'] for c in cpus},'Baseline CPU identities differ')
  for c in cpus:
   old=previous[c['id']];require(c['suspend']==old['suspend'] and c['native_flags']==old['native_flags'],'Native flags or suspension changed from baseline')
   if c['suspend']:require(c['spezflag']==old['spezflag'],'Suspended CPU word changed from baseline')
 return dict(scope=__doc__,save_sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),selected=dict(ai_count=expected,ai_difficulty=mode),ordinary_cpu_controllers=cpus,special_controller_count=sum(c['type']!=12 for c in all_controllers),native_flags_compared_to_baseline=baseline is not None,automated_serialized_policy_check=True,actual_game_run_proven_by_this_inspector=False,passed=True)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('save',type=Path);p.add_argument('--ai-count',type=int,choices=range(4),required=True);p.add_argument('--mode',choices=MODES,required=True);p.add_argument('--baseline',type=Path);p.add_argument('--output',type=Path)
 a=p.parse_args();baseline=json.loads(a.baseline.read_text('utf-8')) if a.baseline else None
 result=inspect(a.save.read_bytes(),a.ai_count,a.mode,baseline);result['save_path']=str(a.save.resolve());text=json.dumps(result,indent=2)
 if a.output:a.output.write_text(text+'\n','utf-8')
 print(text)
if __name__=='__main__':main()
