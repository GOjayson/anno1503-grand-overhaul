"""Exercise Windows unwinding for the new leaf guard. No Anno process is attached."""
from pathlib import Path
import ctypes as C,hashlib,json,struct,sys
PACKAGE=Path(__file__).resolve().parents[2]
SOURCE=PACKAGE/'developer/source'
PRIVATE=SOURCE/'engine_resume/ai_food/experiment_runtime'
sys.path.insert(0,str(PRIVATE))
from world_policy_bridge import build_world_policy_code,LEAF_UNWIND
from capstone import Cs,CS_ARCH_X86,CS_MODE_64
code,names=build_world_policy_code(0)
assert LEAF_UNWIND==bytes.fromhex('01000000') and names['entry']==0 and names['end']==len(code)
memory=C.create_string_buffer(len(code)+64);base=C.addressof(memory)
C.memmove(base,code,len(code));unwind=(len(code)+3)&~3
C.memmove(base+unwind,LEAF_UNWIND,len(LEAF_UNWIND))
class Function(C.Structure):
    _fields_=[('begin',C.c_uint32),('end',C.c_uint32),('unwind',C.c_uint32)]
entry=Function(0,len(code),unwind)
virtual=C.WinDLL('ntdll').RtlVirtualUnwind
virtual.argtypes=[C.c_uint32,C.c_uint64,C.c_uint64,C.POINTER(Function),C.c_void_p,C.POINTER(C.c_void_p),C.POINTER(C.c_uint64),C.c_void_p]
virtual.restype=C.c_void_p
cases=[]
for ins in Cs(CS_ARCH_X86,CS_MODE_64).disasm(code,0):
    context=C.create_string_buffer(1248);ctx=(C.addressof(context)+15)&~15
    struct.pack_into('<I',context,ctx-C.addressof(context)+48,0x10000b)
    stack=(C.c_uint64*8)(0x123456789abcdef0,*([0]*7))
    C.c_uint64.from_address(ctx+152).value=C.addressof(stack)
    C.c_uint64.from_address(ctx+248).value=base+ins.address
    offsets=[144,160,168,176,216,224,232,240]
    for i,off in enumerate(offsets):C.c_uint64.from_address(ctx+off).value=0x11110000+i
    handler=C.c_void_p();frame=C.c_uint64()
    assert not virtual(0,base,base+ins.address,C.byref(entry),ctx,C.byref(handler),C.byref(frame),None)
    assert C.c_uint64.from_address(ctx+248).value==stack[0]
    assert C.c_uint64.from_address(ctx+152).value==C.addressof(stack)+8
    assert all(C.c_uint64.from_address(ctx+off).value==0x11110000+i for i,off in enumerate(offsets))
    cases.append(ins.address)
result=dict(scope=__doc__,bridge_sha256=hashlib.sha256((PRIVATE/'world_policy_bridge.py').read_bytes()).hexdigest(),
            code_sha256=hashlib.sha256(code).hexdigest(),unwind_bytes=LEAF_UNWIND.hex(),
            windows_RtlVirtualUnwind=True,instruction_offsets_checked=cases,nonvolatile_registers_preserved=True,
            actual_game_run=False,limitation='Tests leaf frame metadata and return recovery; not a game exception-delivery test.')
(Path(__file__).parent/'guard_unwind_results.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(instruction_offsets_checked=len(cases),windows_unwind=True,actual_game_run=False)))
