"""Independent PE/caller/cave closure plus actual Windows image-page mapping.

Loads a byte-exact private source copy with DONT_RESOLVE_DLL_REFERENCES: no DLL
entry point, dependency initialization or game code runs. Only native page
metadata and original zero bytes are read; source/game files stay unchanged.
"""
from pathlib import Path
import ctypes as C,hashlib,importlib.util,json,re,struct,sys
from ctypes import wintypes as W
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;GAME=HERE.parents[3]
sys.path.insert(0,str(GAME/'WorldSettings_Work/_tools'))
import pefile
from capstone import Cs,CS_ARCH_X86,CS_MODE_64,CS_OP_IMM,CS_OP_MEM
from capstone.x86 import X86_REG_RIP
s=importlib.util.spec_from_file_location('frame_depth_audit_subject',HERE/'frame_depth_patch.py')
P=importlib.util.module_from_spec(s);sys.modules[s.name]=P;s.loader.exec_module(P)


def sha(b):return hashlib.sha256(b).hexdigest()
def require(ok,m):
 if not ok:raise ValueError(m)


def audit(blob):
 out,manifest=P.transform_frame_depth(blob);pe=pefile.PE(data=blob);image=pe.get_memory_mapped_image();new=pefile.PE(data=out)
 base=pe.OPTIONAL_HEADER.ImageBase;md=Cs(CS_ARCH_X86,CS_MODE_64);md.detail=True;md.skipdata=True
 calls=[];address_refs=[];cave_refs=[];scalar_refs=[];decoded=0
 for sec in pe.sections:
  if not sec.Characteristics&0x20000000:continue
  for ins in md.disasm(image[sec.VirtualAddress:sec.VirtualAddress+sec.Misc_VirtualSize],sec.VirtualAddress):
   if not ins.id:continue
   decoded+=1
   for op in ins.operands:
    if op.type==CS_OP_IMM and ins.mnemonic in['call','jmp']:
     if op.imm==0x8f020:calls.append(ins.address)
     if P.CAVE<=op.imm<P.CAVE_END:cave_refs.append(ins.address)
    elif op.type==CS_OP_MEM and op.mem.base==X86_REG_RIP:
     target=ins.address+ins.size+op.mem.disp
     if target==0x8f020:address_refs.append(ins.address)
     if P.CAVE<=target<P.CAVE_END:cave_refs.append(ins.address)
     if target==P.ORIGINAL_CONSTANT:scalar_refs.append(ins.address)
 require(calls==[0x1cc84,0x1d28d,0x1d76d,0x1d81b],'Unexpected generic camera projector call graph')
 require(not address_refs and not cave_refs,'Address-taking/cave source reference exists')
 ptr=struct.pack('<Q',base+0x8f020);require(blob.find(ptr)==-1,'Projector function pointer exists in source')
 exports=[e.address for e in getattr(getattr(pe,'DIRECTORY_ENTRY_EXPORT',None),'symbols',[])];require(0x8f020 not in exports,'Projector is exported')
 # Every exact direct caller supplies the same concrete camera+c0188 object.
 caller_bytes={0x1cc7a:'4881c188010c00',0x1d286:'488d8f88010c00',0x1d766:'488d8e88010c00',0x1d814:'4881c188010c00'}
 for at,raw in caller_bytes.items():require(image[at:at+len(bytes.fromhex(raw))]==bytes.fromhex(raw),'Camera ownership argument differs')
 require(scalar_refs==[0x1ccac,0x8f176],'The shared native depth scalar has another code consumer')
 ranges=[(e.struct.BeginAddress,e.struct.EndAddress,e.struct.UnwindData)for e in pe.DIRECTORY_ENTRY_EXCEPTION]
 require(not any(a<P.CAVE_END and P.CAVE<b for a,b,u in ranges),'Source helper cave overlaps RuntimeFunction')
 require([(e.struct.BeginAddress,e.struct.EndAddress,e.struct.UnwindData)for e in new.DIRECTORY_ENTRY_EXCEPTION]==ranges,'RuntimeFunction/unwind directory changed')
 allowed=set()
 _,offset=P.pe_layout(blob)
 for e in manifest['runtime_edits']:
  start=offset(e['rva']);allowed.update(range(start,start+len(bytes.fromhex(e['before']))))
 for e in manifest['disk_only_metadata_edits']:allowed.update(range(e['file_offset'],e['file_offset']+len(bytes.fromhex(e['before']))))
 actual={i for i,(a,b)in enumerate(zip(blob,out))if a!=b};require(actual<=allowed and len(blob)==len(out),'Unplanned output changes')
 leaf=out[offset(P.CAVE):offset(P.HUGE_CONSTANT)];insns=list(md.disasm(leaf,P.CAVE));valid=[i for i in insns if i.id]
 require(sum(i.size for i in valid)==len(leaf),'Helper code is not completely decoded')
 require(not any('rsp'in i.op_str or 'rbp'in i.op_str or i.mnemonic.startswith('call')or i.mnemonic in['push','pop','pushfq','popfq']for i in valid),'Leaf changes stack/nonvolatile frame or calls another routine')
 require(all(not i.mnemonic.startswith('j')or any(op.type==CS_OP_IMM and P.CAVE<=op.imm<P.HUGE_CONSTANT for op in i.operands)for i in valid),'Helper branch escapes bounded leaf')
 return dict(source_sha256=sha(blob),output_sha256=sha(out),decoded_source_instructions=decoded,projector_direct_calls=[hex(x)for x in calls],projector_RIP_address_taking_refs=0,projector_absolute_function_pointers=0,projector_exported=False,
             all_four_callers_supply_camera_plus_c0188=True,scalar_consumers=[hex(x)for x in scalar_refs],source_cave_refs=0,source_cave_overlapping_RuntimeFunctions=0,
             all_runtime_function_records_and_unwind_metadata_unchanged=True,complete_leaf_instruction_count=len(valid),leaf_has_no_stack_adjustment_nonvolatile_changes_or_calls=True,
             actual_changed_file_bytes=len(actual),all_changed_bytes_exactly_guarded=True,candidate_sha256=sha(out))


class MBI(C.Structure):
 _fields_=[('BaseAddress',C.c_void_p),('AllocationBase',C.c_void_p),('AllocationProtect',W.DWORD),('PartitionId',W.WORD),('RegionSize',C.c_size_t),('State',W.DWORD),('Protect',W.DWORD),('Type',W.DWORD)]


def loader_page(source):
 private=HERE/'Frame.loader_source_exact.dll'
 require(not private.exists()or private.read_bytes()==source,'Preserve private loader copy');private.write_bytes(source)
 dll=C.WinDLL('kernel32',use_last_error=True);load=dll.LoadLibraryExW;load.argtypes=[W.LPCWSTR,W.HANDLE,W.DWORD];load.restype=W.HMODULE
 free=dll.FreeLibrary;free.argtypes=[W.HMODULE];free.restype=W.BOOL
 query=dll.VirtualQuery;query.argtypes=[C.c_void_p,C.POINTER(MBI),C.c_size_t];query.restype=C.c_size_t
 handle=load(str(private.resolve()),None,1);require(bool(handle),'DONT_RESOLVE source image mapping failed: '+str(C.get_last_error()))
 try:
  mapped=int(handle);regions=[]
  for rva in[P.CAVE,P.MAIN_ENTRY,P.SECONDARY_ENTRY,P.COMMON,P.HUGE_CONSTANT,P.CAVE_END-1]:
   mbi=MBI();require(query(mapped+rva,C.byref(mbi),C.sizeof(mbi))==C.sizeof(mbi),'VirtualQuery failed')
   require(mbi.State==0x1000 and mbi.Type==0x1000000 and mbi.Protect&255 in[0x20,0x40,0x80]and not mbi.Protect&0x100,'Original source image does not map cave as committed executable memory')
   require(C.string_at(mapped+rva,1)==b'\0','Original mapped cave byte not zero')
   regions.append(dict(rva=hex(rva),page_offset=int(mbi.BaseAddress)-mapped,region_bytes=mbi.RegionSize,state='MEM_COMMIT',type='MEM_IMAGE',protection=hex(mbi.Protect),expected_original_zero_byte=True))
 finally:require(free(handle),'Private source image did not unload')
 return dict(private_copy_sha256=sha(private.read_bytes()),source_file_modified=False,load_mode='DONT_RESOLVE_DLL_REFERENCES (no DllMain/dependency initialization)',original_VirtualSize_used=True,all_new_RVAs_originally_committed_RX=True,queries=regions)


def main():
 source=(GAME/'AnnoFrame.dll').read_bytes();overlay=(GAME/'WorldSettings_Work/anno1503_food_world_dev8/native/AnnoFrame.world.dll').read_bytes();reports=[audit(b)for b in[source,overlay]]
 result=dict(passed=True,scope=__doc__,source_profiles=reports,original_Windows_image_mapping=loader_page(source),
             runtime_edit_count=len(P.runtime_depth_edits()),disk_only_header_edits=1,no_pdata_or_exception_directory_edits=True,
             patch_source_sha256=sha((HERE/'frame_depth_patch.py').read_bytes()),audit_source_sha256=sha(Path(__file__).read_bytes()),actual_game_runs=0,game_or_active_copy_or_package_modified=False)
 out=HERE/'frame_depth_closure_audit.json';require(not out.exists(),'Preserve prior audit');out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(dict(passed=True,profiles=len(reports),original_cave_RX=True)))


if __name__=='__main__':main()
