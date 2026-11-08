"""Independent adversarial test of native ShipRM backtracking stack capacity.

Executes the actual full native prologue and loop. A small deterministic coarse
node callback supplies valid-direction chains or cycles. This is a stack-bound
and failure-epilogue proof, not an end-to-end route finder or game run.
"""
from pathlib import Path
import hashlib,json,struct,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;GAME=HERE.parents[2]
PACKAGE=GAME/'WorldSettings_Work/anno1503_food_world_dev8';PLAN=PACKAGE/'developer/huge_world/runtime_engine_edits.json'
sys.path.insert(0,str(GAME/'WorldSettings_Work/_tools'))
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.x86_const import *


def sha(data):return hashlib.sha256(data).hexdigest()


def require(ok,message):
    if not ok:raise ValueError(message)


def native_run(image,base,append_count):
    u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,(len(image)+4095)&~4095);u.mem_write(base,image)
    obj,cell,stack,stop=0x2000000,0x3000000,0x4000000,0x5000000
    u.mem_map(obj,0x20000);u.mem_map(cell,0x1000);u.mem_map(stack,0x20000);u.mem_map(stop,0x1000)
    sp=stack+0x8008;frame_sp=sp-56-0x1050
    u.mem_write(sp,struct.pack('<Q',stop));u.mem_write(cell+2,bytes([0x80 if append_count!=0 else 0]))
    registers=[UC_X86_REG_RBX,UC_X86_REG_RBP,UC_X86_REG_RSI,UC_X86_REG_RDI,UC_X86_REG_R12,UC_X86_REG_R13,UC_X86_REG_R14,UC_X86_REG_R15]
    before_regs={reg:0x1111111100000000+i for i,reg in enumerate(registers)}
    for reg,value in before_regs.items():u.reg_write(reg,value)
    xmm6,xmm7=0x123456789abcdef0123456789abcdef0,0xfedcba9876543210fedcba9876543210
    u.reg_write(UC_X86_REG_XMM6,xmm6);u.reg_write(UC_X86_REG_XMM7,xmm7)
    u.reg_write(UC_X86_REG_RCX,obj);u.reg_write(UC_X86_REG_RSP,sp);u.reg_write(UC_X86_REG_XMM1,0);u.reg_write(UC_X86_REG_XMM2,0)
    state=dict(steps=0,pair_writes=0,overflow_writes=[],complete=False)
    def returns():
        current=u.reg_read(UC_X86_REG_RSP);ret=struct.unpack('<Q',u.mem_read(current,8))[0]
        u.reg_write(UC_X86_REG_RSP,current+8);u.reg_write(UC_X86_REG_RIP,ret)
    def code(uc,address,size,unused):
        rva=address-base
        if rva==0xe5960:returns() # Native chkstk: retain requested RAX allocation.
        elif rva==0x70550:
            u.reg_write(UC_X86_REG_RAX,cell);returns()
        elif rva==0x6f0b0:
            state['steps']+=1
            if append_count is not None and state['steps']>=append_count:u.mem_write(cell+2,b'\0')
            returns()
        elif rva==0x6aba5:
            state['complete']=True;u.emu_stop() # Stop before unrelated fine-search work.
    def writes(uc,access,address,size,value,unused):
        if frame_sp+0x30<=address<frame_sp+0x1030:state['pair_writes']+=1
        if frame_sp+0x1030<=address<frame_sp+0x1030+0x5000 and 0x6ab50<=u.reg_read(UC_X86_REG_RIP)-base<0x6aba5:
            state['overflow_writes'].append(dict(rva=hex(u.reg_read(UC_X86_REG_RIP)-base),relative_to_frame=hex(address-frame_sp),bytes=size))
    u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,writes)
    u.emu_start(base+0x6aa70,stop,count=500000)
    returned=not state['complete']
    result=dict(requested_appends=append_count,coarse_step_callback_calls=state['steps'],native_pair_write_instructions=state['pair_writes'],
        backtrack_completed=state['complete'],returned_early=returned,overflow_write_count=len(state['overflow_writes']),overflow_write_examples=state['overflow_writes'][:3])
    if returned:
        value=u.reg_read(UC_X86_REG_RAX)&0xffffffff;value=value-(1<<32)if value&(1<<31)else value
        result.update(return_value=value,all_nonvolatile_registers_preserved=all(u.reg_read(reg)==v for reg,v in before_regs.items()),
            xmm6_xmm7_preserved=u.reg_read(UC_X86_REG_XMM6)==xmm6 and u.reg_read(UC_X86_REG_XMM7)==xmm7,
            original_caller_stack_restored=u.reg_read(UC_X86_REG_RSP)==sp+8)
    return result


def main():
    original=(GAME/'AnnoWelt.dll').read_bytes();p=pefile.PE(data=original);plan_data=PLAN.read_bytes();plan=json.loads(plan_data)
    require(plan['engine_instruction_count']>115,'A reviewed backtracking guard must be present before this test')
    changed=bytearray(original)
    for row in plan['edits']:
        if row.get('module','AnnoWelt.dll')!='AnnoWelt.dll':continue
        before,after=bytes.fromhex(row['before']),bytes.fromhex(row['after']);offset=p.get_offset_from_rva(row['rva'])
        require(changed[offset:offset+len(before)]==before,'Original native transaction preimage differs')
        changed[offset:offset+len(after)]=after
    old_image=p.get_memory_mapped_image();new_image=pefile.PE(data=bytes(changed)).get_memory_mapped_image();cases=[]
    for base in [0x180000000,0x280000000]:
        for count in [0,1,1022,1023,1024,1025,4096,None]:
            patched=native_run(new_image,base,count)
            if count is not None and count<=1023:
                require(patched['backtrack_completed']and not patched['overflow_write_count'],'Guard changed an in-capacity backtrack')
                require(patched['coarse_step_callback_calls']==count,'In-capacity backtrack step count changed')
            else:
                require(patched['returned_early']and patched['return_value']==-1,'Oversized/cyclic backtrack did not return native failure')
                require(not patched['overflow_write_count'],'Guard wrote into saved registers/caller stack')
                require(patched['all_nonvolatile_registers_preserved']and patched['xmm6_xmm7_preserved']and patched['original_caller_stack_restored'],'Guard failure damaged the native call frame')
            row=dict(image_base=hex(base),patched=patched)
            if count in [1023,1024,1025]:
                old=native_run(old_image,base,count);row['unpatched']=old
                require(old['backtrack_completed'],'Original finite fixture did not terminate')
                require(bool(old['overflow_write_count'])==(count>=1024),'Original stack-bound counterexample differs')
            cases.append(row)
    report=dict(scope=__doc__,passed=True,original_welt_sha256=sha(original),runtime_plan_sha256=sha(plan_data),engine_patch_count=plan['engine_instruction_count'],
        native_function_rva='0x6aa70',native_frame_bytes=0x1050,coordinate_array_offset=0x30,first_saved_vector_offset=0x1030,
        coordinate_pairs_capacity=1024,first_pair_is_initial_position=True,maximum_additional_pairs=1023,
        original1025th_total_pair_overwrites_saved_vector=True,guard_rejects_oversized_and_cyclic_paths_before_overflow=True,
        cases=cases,actual_game_run=False,complete_native_route_search_tested=False,game_or_copy_or_source_modified=False,
        inspector_sha256=sha(Path(__file__).read_bytes()))
    (HERE/'backtracking_guard_independent_results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(passed=True,cases=len(cases),capacity_pairs=1024,engine_patch_count=plan['engine_instruction_count'],actual_game_run=False),indent=2))


if __name__=='__main__':main()
