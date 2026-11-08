"""Exact-byte/PE/leaf closure and fail-closed source guards for bias2 copies.

Actual executable page mapping and Windows unwind behavior are independently
checked by the grid reviewer. No game process/file/package writes occur here.
"""
from pathlib import Path
import importlib.util,json,struct,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[1];GAME=WORK.parents[1]
sys.path.insert(0,str(GAME/'WorldSettings_Work/_tools'))
import pefile
from capstone import Cs,CS_ARCH_X86,CS_MODE_64,CS_OP_IMM,CS_OP_MEM
from capstone.x86 import X86_REG_RIP
s=importlib.util.spec_from_file_location('bias_closure_subject',HERE/'frame_bias_patch.py');P=importlib.util.module_from_spec(s);sys.modules[s.name]=P;s.loader.exec_module(P)


def audit(blob):
 out,manifest=P.transform_frame_bias(blob);p=pefile.PE(data=blob);n=pefile.PE(data=out);image=p.get_memory_mapped_image();base=p.OPTIONAL_HEADER.ImageBase
 _,offset=P.layout(blob);allowed=set()
 for e in manifest['runtime_edits']:
  at=offset(e['rva']);allowed.update(range(at,at+len(bytes.fromhex(e['before']))))
 for e in manifest['disk_only_metadata_edits']:allowed.update(range(e['file_offset'],e['file_offset']+len(bytes.fromhex(e['before']))))
 changes={i for i,(a,b)in enumerate(zip(blob,out))if a!=b};P.require(changes<=allowed and len(out)==len(blob),'Unplanned bytes changed')
 for a,b in[(0x8f020,0x8f3d4),(0x1cc20,0x1d003),(0xac30c,0xac310)]:P.require(p.get_data(a,b-a)==n.get_data(a,b-a),'Native scalar/camera/state6 construction changed')
 md=Cs(CS_ARCH_X86,CS_MODE_64);md.detail=True;md.skipdata=True;references=[];source_instructions=0
 for sec in p.sections:
  if not sec.Characteristics&0x20000000:continue
  for i in md.disasm(image[sec.VirtualAddress:sec.VirtualAddress+sec.Misc_VirtualSize],sec.VirtualAddress):
   if not i.id:continue
   source_instructions+=1
   for op in i.operands:
    target=op.imm if op.type==CS_OP_IMM and i.mnemonic in['call','jmp']else(i.address+i.size+op.mem.disp if op.type==CS_OP_MEM and op.mem.base==X86_REG_RIP else-1)
    if P.CAVE<=target<P.END:references.append(i.address)
 P.require(not references,'Existing source references new cave')
 P.require(not any(blob.find(struct.pack('<Q',base+rva))>=0 for rva in range(P.CAVE,P.END)),'Existing absolute source pointer references cave')
 old_functions=[(e.struct.BeginAddress,e.struct.EndAddress,e.struct.UnwindData)for e in p.DIRECTORY_ENTRY_EXCEPTION]
 new_functions=[(e.struct.BeginAddress,e.struct.EndAddress,e.struct.UnwindData)for e in n.DIRECTORY_ENTRY_EXCEPTION]
 P.require(old_functions==new_functions and not any(a<P.END and P.CAVE<b for a,b,u in old_functions),'Unwind tables changed/cave overlaps a native function')
 # Both sites are in concrete native camera methods whose prolog savesRCX inRDI.
 for at,raw in[(0x1c322,'488bf9'),(0x1c705,'488bf9')]:P.require(p.get_data(at,3)==bytes.fromhex(raw),'Camera owner register differs')
 leaf=n.get_data(P.CAVE,P.CENTER-P.CAVE);decoded=list(md.disasm(leaf,P.CAVE));P.require(all(i.id for i in decoded)and sum(i.size for i in decoded)==len(leaf),'Incomplete helper decode')
 P.require(not any('rsp'in i.op_str or 'rbp'in i.op_str or i.mnemonic in['call','push','pop','pushfq','popfq']for i in decoded),'Helper adjusts stack/calls/changesnonvolatileframe')
 P.require(all(not i.mnemonic.startswith('j')or any(op.type==CS_OP_IMM and P.CAVE<=op.imm<P.CENTER for op in i.operands)for i in decoded),'Helper branch leaves bounded code')
 P.require(P.SIGN%16==0 and n.get_data(P.SIGN,16)==struct.pack('<4I',0x80000000,0,0,0),'Aligned scalar-only sign mask differs')
 P.require(manifest['runtime_edits'][-2]['rva']==0x1c3f6 and manifest['runtime_edits'][-1]['rva']==0x1c7d0,'Install order must populate code/constants before both calls')
 # Full-image fingerprints reject unsupported, partly changed and old173 images.
 rejected=[];bad={'truncated':blob[:-1],'already_bias2':out}
 for name,at in[('changed_native_load',offset(0x1c3f6)),('changed_zero_padding',offset(P.CAVE)),('changed_source_scalar',offset(0xac30c))]:
  b=bytearray(blob);b[at]^=1;bad[name]=bytes(b)
 b=bytearray(blob);e=manifest['runtime_edits'][0];at=offset(e['rva']);b[at:at+len(bytes.fromhex(e['after']))]=bytes.fromhex(e['after']);bad['partial_helper_install']=bytes(b)
 for name,b in bad.items():
  try:P.transform_frame_bias(b)
  except ValueError:rejected.append(name)
  else:raise ValueError('Invalid source accepted: '+name)
 return dict(passed=True,source_sha256=P.sha(blob),output_sha256=P.sha(out),decoded_source_instructions=source_instructions,actual_changed_file_bytes=len(changes),all_changes_guarded_and_no_other_bytes_changed=True,
  original_depth_scalar_both_consumers_camera_and_state6_code_identical=True,both_camera_receiver_RDI_proven=True,source_cave_references=0,source_cave_absolute_pointers=0,
  native_exception_function_and_unwind_tables_unchanged=True,cave_does_not_overlap_native_RuntimeFunction=True,helper_full_decode_instructions=len(decoded),helper_no_stack_adjustment_or_calls=True,aligned_scalar_sign_mask=True,
  runtime_install_code_constants_before_both_calls=True,rejected_invalid_sources=rejected,source_guard_negative_cases=len(rejected))


def main():
 reports=[audit((GAME/'AnnoFrame.dll').read_bytes()),audit((WORK/'candidate166/native/AnnoFrame.world.dll').read_bytes())]
 old173=(HERE.parent/'frame_depth/AnnoFrame.food_original.depth.dll').read_bytes()
 try:P.transform_frame_bias(old173)
 except ValueError:pass
 else:raise ValueError('Old half-depth173 candidate accepted as canonical source')
 result=dict(passed=True,scope=__doc__,profiles=reports,old_half_depth173_source_rejected=True,runtime_edit_count=7,disk_only_metadata_edits=1,
             patch_source_sha256=P.sha((HERE/'frame_bias_patch.py').read_bytes()),audit_source_sha256=P.sha(Path(__file__).read_bytes()),actual_game_runs=0,game_or_copy_or_package_modified=False)
 out=HERE/'frame_bias_closure_audit.json';P.require(not out.exists(),'Preserve prior closure proof');out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(dict(passed=True,profiles=2,source_rejections=13)))


if __name__=='__main__':main()
