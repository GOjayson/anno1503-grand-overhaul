"""Independently validate the emitted C metadata and relocated native operands.

No DLL/game is loaded and no root source or generated header is written.
"""
from pathlib import Path
import hashlib,json,re,struct,sys,os
HERE=Path(__file__).resolve().parent;DEV=HERE.parent;WORK=DEV.parent;ROOT=WORK.parent
ROOT=Path(os.environ.get('ANNO1503_SOURCE_GAME',ROOT))
sys.path[:0]=[str(DEV),str(WORK),str(WORK/'_tools'),str(WORK/'engine_audit'),str(WORK/'native_world'),str(WORK/'engine_resume/ai_loader'),str(WORK/'engine_resume/route_coverage'),str(WORK/'engine_resume/ai_food/experiment_runtime')]
from capstone import Cs,CS_ARCH_X86,CS_MODE_64
from capstone.x86_const import X86_OP_MEM,X86_OP_IMM,X86_REG_RIP
from audit import Module
from bridge_codegen import build_bridge
from frame_factory_bridge import build_factory_code
from patch_scene_copy import build_code
from direct_bridge import build_direct_bridge
from postprofile_bridge import build_postprofile_code
from attempt_bridge import build_attempt_code
from loader_bridge import build_loader_bridge
from world_policy_bridge import build_world_policy_code
header=(DEV/'runtime_test_blobs.h').read_text();md=Cs(CS_ARCH_X86,CS_MODE_64);md.detail=True
arrays={name:bytes(int(x,0) for x in re.findall(r'0x[0-9a-fA-F]+|\d+',body)) for name,body in re.findall(r'static const unsigned char (\w+)\[\] = \{(.*?)\};',header)}
def body(kind,name):
 m=re.search(r'static const '+kind+' '+name+r'\[\] = \{(.*?)\};',header);assert m,name;return m.group(1)
expected={'flag':build_bridge(0)[0],'factory':build_factory_code(0)[0],'scene':build_code(0)[0],'direct':build_direct_bridge(0)[0],'postprofile':build_postprofile_code(0)[0],'native_attempt':build_attempt_code(0)[0],'ai_loader':build_loader_bridge(0)[0]}
expected['world_policy']=build_world_policy_code(0)[0]
moduleNames={'flag':'AnnoFrame.dll','factory':'AnnoFrame.dll','scene':'AnnoScene.dll','direct':'AnnoFrame.dll','postprofile':'AnnoFrame.dll','native_attempt':'AnnoFrame.dll','ai_loader':'AnnoWelt.dll'}
moduleNames['world_policy']='AnnoWelt.dll'
modules={name:Module(str(ROOT/name)) for name in set(moduleNames.values())};report=[];totalHooks=0;operandCases=0
for label,code in expected.items():
 assert arrays[label+'_code']==code,(label,'generated C code is stale relative to reviewed builder')
 m=modules[moduleNames[label]]
 relocs=[int(x) for x in re.findall(r'\{(\d+)\}',body('WSRelocation',label+'_relocs'))];assert len(set(relocs))==len(relocs)
 imports=[(int(a),name) for a,name in re.findall(r'\{(\d+),"([^"]+)"\}',body('WSImportCell',label+'_imports'))] if label in ['factory','scene','postprofile','native_attempt','ai_loader'] else []
 functions=[]
 for a,b,unwind,n in re.findall(r'\{(\d+),(\d+),(\w+),(\d+)\}',body('WSFunctionMeta',label+'_functions')):
  a,b,n=int(a),int(b),int(n);u=arrays[unwind];assert len(u)==n and a<b<=len(code);assert u[0]&7==1 and u[0]>>3 in [0,4]
  ordinary=(4+u[2]*2+3)&~3;assert len(u)==ordinary+(12 if u[0]>>3==4 else 0)
  if u[0]>>3==4:assert struct.unpack_from('<III',u,ordinary) in [(e.struct.BeginAddress,e.struct.EndAddress,e.struct.UnwindData) for e in m.pe.DIRECTORY_ENTRY_EXCEPTION]
  functions.append((a,b))
 assert functions and all(a[1]<=b[0] for a,b in zip(functions,functions[1:]))
 hookRanges=[]
 for at,n,before,target,call in re.findall(r'\{(\d+),(\d+),(\w+),(\d+),(\d+)\}',body('WSHook',label+'_hooks')):
  at,n,target,call=int(at),int(n),int(target),int(call);pre=arrays[before];assert len(pre)==n and m.image[at:at+n]==pre and 5<=n<=32 and target<len(code) and call in [0,1]
  assert at//4096==(at+n-1)//4096
  hookRanges.append(dict(rva=hex(at),length=n,call=bool(call),target=target));totalHooks+=1
 instructions=[i for a,b in functions for i in md.disasm(code[a:b],a)]
 instructionFields={i.address+i.disp_offset for i in instructions if i.disp_size==4}|{i.address+i.imm_offset for i in instructions if i.imm_size==4}
 assert all(at in instructionFields and at+4<=len(code) for at in relocs)
 for at,name in imports:assert at+8<=len(code) and name and all(not(a<=at<b) for a,b in functions)
 for base in [0x180000000,0x7ff600000000]:
  for delta in [0x180000,0x1000000,0x12345000,0x6ffff000]:
   fixed=bytearray(code)
   for at in relocs:
    old=struct.unpack_from('<i',code,at)[0];value=old-delta;assert -2**31<=value<2**31;struct.pack_into('<i',fixed,at,value)
   moved=[i for a,b in functions for i in md.disasm(fixed[a:b],base+delta+a)]
   assert len(moved)==len(instructions)
   for old,new in zip(instructions,moved):
    assert old.mnemonic==new.mnemonic and old.size==new.size
    for oldOp,newOp in zip(old.operands,new.operands):
     if oldOp.type==X86_OP_MEM and oldOp.mem.base==X86_REG_RIP:
      field=old.address+old.disp_offset;oldTarget=old.address+old.size+oldOp.mem.disp;newTarget=new.address+new.size+newOp.mem.disp
     elif oldOp.type==X86_OP_IMM and old.imm_size==4 and (old.group(1) or old.group(2)):
      field=old.address+old.imm_offset;oldTarget=oldOp.imm;newTarget=newOp.imm
     else:continue
     if field in relocs:assert 0<=oldTarget<len(m.image) and newTarget==base+oldTarget,(label,hex(old.address),'native target changed')
     else:assert 0<=oldTarget<len(code) and newTarget==base+delta+oldTarget,(label,hex(old.address),'internal target changed')
     operandCases+=1
 report.append(dict(label=label,module=moduleNames[label],code_sha256=hashlib.sha256(code).hexdigest(),code_bytes=len(code),functions=len(functions),native_relocations=relocs,imports=imports,hooks=hookRanges))
assert totalHooks==9
result=dict(scope=__doc__,header_sha256=hashlib.sha256((DEV/'runtime_test_blobs.h').read_bytes()).hexdigest(),hook_count=totalHooks,positive_allocation_cases_per_blob=8,verified_relative_operand_cases=operandCases,blobs=report,actual_game_runs=0)
(HERE/'blob_review_results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['scope','blobs']},indent=2))
