"""Build exact native producer layout edits for the2048 visibility repair.

This creates an additive JSON plan only. It changes no DLL, game, copy, release
or process. The caller must compose the helper and producer edits atomically.
"""
from pathlib import Path
import hashlib,json,struct,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;GAME=HERE.parents[3]
sys.path.insert(0,str(GAME/'WorldSettings_Work/_tools'))
import pefile
from capstone import Cs,CS_ARCH_X86,CS_MODE_64
from capstone.x86 import X86_OP_MEM
OLD_FRAME=0xd6968;DELTA=0xa380;NEW_FRAME=OLD_FRAME+DELTA


def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    blob=(GAME/'AnnoWelt.dll').read_bytes();assert sha(blob)=='ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9'
    p=pefile.PE(data=blob);image=p.get_memory_mapped_image();cs=Cs(CS_ARCH_X86,CS_MODE_64);cs.detail=True
    edits=[];inventory=[]
    def raw(rva,before,after,role):
        assert isinstance(before,bytes)and isinstance(after,bytes)and len(before)==len(after)and image[rva:rva+len(before)]==before
        edits.append(dict(rva=rva,before=before.hex(),after=after.hex(),length=len(before),role=role))
    def instruction(rva,new_value,kind,role):
        i=next(cs.disasm(image[rva:rva+20],rva));after=bytearray(i.bytes)
        offset,width=(i.disp_offset,i.disp_size)if kind=='disp'else(i.imm_offset,i.imm_size)
        assert width in(1,4)
        after[offset:offset+width]=int(new_value).to_bytes(width,'little',signed=new_value<0)
        raw(rva,bytes(i.bytes),bytes(after),role)
    for i in cs.disasm(image[0xca2f0:0xcafbb],0xca2f0):
        for op in i.operands:
            if op.type!=X86_OP_MEM or i.reg_name(op.mem.base)!='rbp':continue
            old=op.mem.disp;new=old
            if 0x1c0<=old<0x460:new=old+0x600
            elif 0x460<=old<0x6860:new=old+0x780
            elif old>=0x6860:new=old+DELTA
            inventory.append(dict(rva=hex(i.address),assembly=i.mnemonic+' '+i.op_str,old_displacement=hex(old),new_displacement=hex(new),encoded_bytes=i.disp_size))
            if new!=old:
                assert i.disp_size==4
                instruction(i.address,new,'disp','Move native stack array/parameter reference for enlarged mask and128-column matrix')
                break
    instruction(0xca310,-(NEW_FRAME-0x100),'disp','Keep native RBP at new RSP+0x100')
    instruction(0xca318,NEW_FRAME,'imm','Native chkstk requested stack allocation')
    instruction(0xcaf37,NEW_FRAME,'imm','Matching native frame epilogue deallocation')
    instruction(0xca3dd,0x800,'imm','Clear128x128 one-bit visibility mask (2048 bytes)')
    instruction(0xca45b,0x10420,'imm','Zero128 column pointers plus four margins and the full128x128 index matrix')
    instruction(0xca4d9,4,'imm','Check all four DWORDs in a128-block visibility row')
    instruction(0xca90b,4,'imm','Advance four DWORDs per visibility row')
    raw(0xca8ae,bytes.fromhex('8d0450'),bytes.fromhex('8d0490'),'Visibility clear index x/32+y*4')
    raw(0xca970,bytes.fromhex('428d0440'),bytes.fromhex('428d0480'),'Previous-record visibility index x/32+y*4')
    raw(0xca914,bytes.fromhex('8344246850'),bytes.fromhex('836c246880'),'Matrix row stride128, encoded as subtract signed -128')
    raw(0xca989,bytes.fromhex('438d0480c1e004'),bytes.fromhex('4489c0c1e00790'),'Previous-record matrix row index y*128')
    instruction(0xca505,1,'imm','Encode matrix index as record index plus one; zero is an unassigned slot')
    raw(0xca99a,bytes.fromhex('81f900200000'),bytes.fromhex('ffc980fd2090'),'Decode matrix index, reject zero/unassigned; reachable raw values are0 or1..8192')
    raw(0xca9a0,bytes.fromhex('0f837a010000'),bytes.fromhex('0f839a000000'),'Unassigned capped cell uses existing not-visible cache recycling path, then continues other records')
    instruction(0xe8bde,0xd69b0+DELTA,'disp','C++ second cleanup funclet reaches unchanged caller-home pointer from new establisher RSP')
    raw(0x11f336,struct.pack('<I',OLD_FRAME),struct.pack('<I',NEW_FRAME),'Matching native ALLOC_LARGE unwind metadata; code/handler addresses unchanged')
    helper_path=GAME/'WorldSettings_Work/huge_engine_work/grid/border/visibility_helper_edits.json';helper_data=helper_path.read_bytes();helper=json.loads(helper_data)
    assert len(helper['edits'])==3 and helper.get('requires_matching_caller_layout_repair')is True
    for row in helper['edits']:raw(row['rva'],bytes.fromhex(row['before']),bytes.fromhex(row['after']),'Visibility helper: '+row['role'])
    edits.sort(key=lambda row:row['rva'])
    for left,right in zip(edits,edits[1:]):assert left['rva']+left['length']<=right['rva']
    result=dict(schema=1,module='AnnoWelt.dll',architecture='AMD64 PE32+',source_original_sha256=sha(blob),
        component='Visibility helper plus native ca2f0 producer stack/caches and cleanup/unwind closure',
        old_stack_frame=OLD_FRAME,new_stack_frame=NEW_FRAME,stack_growth_bytes=DELTA,rbp_offset_from_rsp=0x100,
        old_visibility_mask_bytes=512,new_visibility_mask_bytes=2048,visibility_mask_rbp_displacement=-0x40,
        old_pointer_cache_slots=84,new_pointer_cache_slots=132,old_matrix_columns=80,new_matrix_columns=128,
        old_pointer_cache_rbp=0x1c0,new_pointer_cache_rbp=0x7c0,old_matrix_rbp=0x460,new_matrix_rbp=0xbe0,
        old_cached_pointers_rbp=0x6860,new_cached_pointers_rbp=0x10be0,
        old_previous_records_rbp=0x46860,new_previous_records_rbp=0x50be0,
        visible_record_capacity=8192,record_bytes=88,previous_record_bytes=72,
        matrix_zero_is_unassigned=True,matrix_store_index_bias=1,reachable_matrix_values=[0,8192],
        native_unwind_info_rva=0x11f330,native_frame_alloc_unwind_rva=0x11f336,
        native_cpp_funcinfo_rva=0x102e50,native_cpp_unwind_help_offset=0xb0,
        native_cpp_cleanup_funclets=[0xe8bb0,0xe8bd0],native_cpp_shifted_cleanup_instruction=0xe8bde,
        instruction_or_metadata_region_count=len(edits),edits=edits,stack_reference_inventory=inventory,
        helper_plan_sha256=sha(helper_data),generator_sha256=sha(Path(__file__).read_bytes()),
        game_executed=False,game_or_copy_or_release_or_process_modified=False,
        activation_requirement='Compose all helper, producer, cleanup and unwind changes before restarting a test game. Never apply a partial repair or hot-patch an existing World.')
    target=HERE/'visibility_repair_plan.json';target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(regions=len(edits),frame=hex(NEW_FRAME),growth=DELTA,plan_sha256=sha(target.read_bytes()),output=str(target)),indent=2))


if __name__=='__main__':main()
