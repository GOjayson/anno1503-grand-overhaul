"""Read-only contextual lookup-layout survey outside AnnoWelt.

Instruction equality is candidate evidence only. Linear executable-section
disassembly covers leaf code as well as pdata functions but can decode data.
No instruction or game file is changed by this survey.
"""
from pathlib import Path
import bisect,collections,hashlib,json,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
GAME=HERE.parents[2]
sys.path.insert(0,str(GAME/'WorldSettings_Work/_tools'))
import pefile
from capstone import Cs,CS_ARCH_X86,CS_MODE_64
from capstone.x86 import X86_OP_MEM,X86_OP_IMM

NAMES=['Anno1503.exe','AnnoFrame.dll','AnnoGame.dll','AnnoScene.dll','View.dll',
       'FileGame.dll','AnnoDisplay.dll','CompLogic.dll','CompLogicClassic.dll',
       'AnnoFrameAddOn.dll','AnnoGameAddOn.dll','AnnoSceneAddOn.dll','AnnoWeltAddOn.dll',
       'WorldSettings_Work/anno1503_food_world_dev7/native/CompLogic.food-ai.dll',
       'WorldSettings_Work/anno1503_food_world_dev7/native/CompLogicClassic.food-ai.dll']

def main():
 out={}
 for name in NAMES:
  blob=(GAME/name).read_bytes();p=pefile.PE(data=blob)
  base=dict(sha256=hashlib.sha256(blob).hexdigest(),machine=hex(p.FILE_HEADER.Machine),pe_magic=hex(p.OPTIONAL_HEADER.Magic))
  if p.FILE_HEADER.Machine!=0x8664 or p.OPTIONAL_HEADER.Magic!=0x20b:
   out[name]=dict(**base,skipped='Not the inspected AMD64 HE architecture');continue
  image=p.get_memory_mapped_image();funcs=sorted((e.struct.BeginAddress,e.struct.EndAddress)for e in getattr(p,'DIRECTORY_ENTRY_EXCEPTION',[]));starts=[a for a,b in funcs]
  cs=Cs(CS_ARCH_X86,CS_MODE_64);cs.detail=True;cs.skipdata=True
  def summary(i):
   k=bisect.bisect_right(starts,i.address)-1
   return dict(rva=hex(i.address),bytes=i.bytes.hex(),assembly=i.mnemonic+' '+i.op_str,
     function=hex(funcs[k][0])if k>=0 and i.address<funcs[k][1]else None)
  previous=collections.deque(maxlen=6);pending=[];byte240=[];table=[];bases=[];count=0
  for section in p.sections:
   if not section.Characteristics&0x20000000:continue
   previous.clear()
   for i in cs.disasm(image[section.VirtualAddress:section.VirtualAddress+section.Misc_VirtualSize],section.VirtualAddress):
    count+=1;s=summary(i)
    is_table=bool(i.id and any(o.type==X86_OP_MEM and o.mem.disp==0x6640 for o in i.operands))
    for row,remaining in list(pending):
     row['following'].append(s)
     if is_table:row['nearby_pointer_table'].append(hex(i.address))
     pending.remove((row,remaining))
     if remaining>1:pending.append((row,remaining-1))
    if i.id:
     if any(o.type==X86_OP_MEM and o.mem.disp==0x240 and o.size==1 for o in i.operands):
      row=dict(**s,previous=list(previous),following=[],nearby_pointer_table=[]);byte240.append(row);pending.append((row,8))
     if is_table:table.append(dict(**s,previous=list(previous)))
     if any(o.type==X86_OP_IMM and o.imm in {0x6400,0x7068,0x6f00} for o in i.operands):bases.append(dict(**s,previous=list(previous)))
    previous.append(s)
  out[name]=dict(**base,decoded_instructions=count,pdata_functions=len(funcs),
    byte240_candidates=byte240,pointer_table_6640_candidates=table,world_size_immediate_candidates=bases,
    byte240_followed_by6640=[r for r in byte240 if r['nearby_pointer_table']])
  print(json.dumps(dict(module=name,instructions=count,byte240=len(byte240),table6640=len(table),strong_pairs=len(out[name]['byte240_followed_by6640']))),flush=True)
 result=dict(scope=__doc__,modules=out,game_executed=False,game_or_copy_or_release_modified=False,
   limitation='Absence of this direct pattern does not exclude indirect aliases, other fields, packed coordinates or module-local caches.')
 (HERE/'crossmodule_scan_results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
