"""Execute the complete original fixed-flag detector plus candidate gate.

File APIs, file parser, Windows loader, modal UI and final state callback are
doubled. Native HEAD decision, new bridge and setup commit execute as AMD64.
This is not an actual game run.
"""
from pathlib import Path
import hashlib
import itertools
import json
import struct
import sys
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'WorldSettings_Work/_tools'))
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE,UC_PROT_ALL
from unicorn.x86_const import *
from direct_bridge import build_direct_bridge,EXPECTED_FRAME_SHA,COMMON_UNWIND
import pefile


def main():
    original=(ROOT/'AnnoFrame.dll').read_bytes()
    assert hashlib.sha256(original).hexdigest()==EXPECTED_FRAME_SHA
    pe=pefile.PE(data=original); image=pe.get_memory_mapped_image(); results=[]
    for base,flag,outcome in itertools.product([0x180000000,0x1b3000000],range(1,9),
            ['accept','cancel','non_endless','error','unexpected_result','missing_dll',
             'missing_export','missing_array','missing_child']):
        STACK=0x40000000; PAGE=0x50000000; SETUP=PAGE+0x10000; EXT=0x60000000
        LOAD=EXT; GET=EXT+0x100; UI=EXT+0x200; STATE=EXT+0x300; STOP=EXT+0x400
        FILE=EXT+0x500; CLOSE=EXT+0x600
        uc=Uc(UC_ARCH_X86,UC_MODE_64);uc.mem_map(base,0x140000,UC_PROT_ALL);uc.mem_write(base,image)
        code,names,hooks,functions=build_direct_bridge(0x100000)
        uc.mem_write(base+0x100000,code)
        for rva,before,after in hooks:
            assert bytes(uc.mem_read(base+rva,len(before)))==before
            uc.mem_write(base+rva,after)
        assert functions[0][2]==COMMON_UNWIND
        for at,size in [(STACK,0x20000),(PAGE,0x30000),(EXT,0x1000)]:uc.mem_map(at,size,UC_PROT_ALL)
        for at in [LOAD,GET,UI,STATE,STOP,FILE,CLOSE,base+0x13a0,base+0x987ca,base+0x3cff0]:uc.mem_write(at,b'\xc3')
        for rva,at in [(0x9e408,LOAD),(0x9e410,GET),(0x9e3e0,FILE),(0x9e3e8,CLOSE)]:uc.mem_write(base+rva,struct.pack('<Q',at))
        rsp=STACK+0x10008;uc.reg_write(UC_X86_REG_RSP,rsp);uc.mem_write(rsp,struct.pack('<Q',STOP))
        vt=PAGE+0x8000;array=PAGE+0x9000
        uc.mem_write(PAGE,struct.pack('<Q',vt));uc.mem_write(vt+0x178,struct.pack('<Q',STATE))
        uc.mem_write(PAGE+0x21b0,struct.pack('<Q',0 if outcome=='missing_array' else array))
        uc.mem_write(array,struct.pack('<Q',0 if outcome=='missing_child' else SETUP))
        source=bytes((x*13+7)&255 for x in range(0x498))
        uc.mem_write(SETUP+0x2288,source);uc.mem_write(SETUP+0x2280,bytes([1]*7))
        guard=b'UNCHANGED-GUARD!'
        for at in [base+0xc75e0-16,base+0xc75e0+0x498,SETUP+0x2288+0x498]:uc.mem_write(at,guard)
        original_regs={UC_X86_REG_RBX:0x1111,UC_X86_REG_RSI:0x2222,UC_X86_REG_RDI:0x3333,
            UC_X86_REG_RBP:0x3456,UC_X86_REG_R12:0x4444,UC_X86_REG_R13:0x5555,
            UC_X86_REG_R14:0x6666,UC_X86_REG_R15:0x7777}
        for reg,value in original_regs.items():uc.reg_write(reg,value)
        uc.reg_write(UC_X86_REG_RCX,PAGE);calls=[]
        def cstring(at):
            out=bytearray()
            while len(out)<260:
                value=bytes(uc.mem_read(at+len(out),1))
                if value==b'\0':return out.decode('ascii')
                out+=value
            raise AssertionError('unterminated native test string')
        def clobber():
            for register in [UC_X86_REG_RCX,UC_X86_REG_RDX,UC_X86_REG_R8,UC_X86_REG_R9,UC_X86_REG_R10,UC_X86_REG_R11]:
                uc.reg_write(register,0xbadbadbad)
        def hook(uc,at,size,_):
            if at==STOP:uc.emu_stop();return
            if at in [LOAD,GET,UI,STATE,FILE,CLOSE,base+0x13a0,base+0x987ca,base+0x3cff0,base+0x476e0]:
                assert uc.reg_read(UC_X86_REG_RSP)%16==8,(hex(at),outcome)
            if at==base+0x987ca:
                target=uc.reg_read(UC_X86_REG_RCX);value=uc.reg_read(UC_X86_REG_RDX)&255;length=uc.reg_read(UC_X86_REG_R8)
                uc.mem_write(target,bytes([value])*length);uc.reg_write(UC_X86_REG_RAX,target)
            if at==FILE:uc.reg_write(UC_X86_REG_RAX,123)
            if at==base+0x3cff0:
                assert uc.reg_read(UC_X86_REG_RDX)==PAGE+0x2270
                for i in range(30):
                    uc.mem_write(PAGE+0x2270+i*0x6c,struct.pack('<I',0xffffffff))
                uc.mem_write(PAGE+0x2270,struct.pack('<I',11))
                uc.mem_write(PAGE+0x22bc,bytes([flag]))
                uc.reg_write(UC_X86_REG_RAX,0)
            if at==LOAD:
                assert cstring(uc.reg_read(UC_X86_REG_RCX))=='AnnoWorldSettings.dll';calls.append('load')
                clobber();uc.reg_write(UC_X86_REG_RAX,0 if outcome=='missing_dll' else 0x999)
            if at==GET:
                assert uc.reg_read(UC_X86_REG_RCX)==0x999
                assert cstring(uc.reg_read(UC_X86_REG_RDX))=='WorldSettingsBeforeDirectStart';calls.append('get')
                clobber();uc.reg_write(UC_X86_REG_RAX,0 if outcome=='missing_export' else UI)
            if at==UI:
                assert uc.reg_read(UC_X86_REG_RCX)==PAGE and uc.reg_read(UC_X86_REG_RDX)==base
                calls.append('route_export')
                if outcome=='accept':uc.mem_write(SETUP+0x2280,bytes(7))
                result={'accept':2,'non_endless':1,'missing_array':2,'missing_child':2,
                        'error':0xffffffff,'unexpected_result':3}.get(outcome,0)
                clobber();uc.reg_write(UC_X86_REG_RAX,result)
            if at==base+0x476e0:
                assert uc.reg_read(UC_X86_REG_RCX)==SETUP;calls.append('native_commit')
            if at==STATE:
                assert uc.reg_read(UC_X86_REG_RCX)==PAGE and uc.reg_read(UC_X86_REG_RDX)==0
                assert uc.reg_read(UC_X86_REG_R8)==1 and uc.reg_read(UC_X86_REG_R9)==8
                assert bytes(uc.mem_read(base+0xc5040,1))==bytes([flag]);calls.append('native_start')
                clobber();uc.reg_write(UC_X86_REG_RAX,0x1234)
        uc.hook_add(UC_HOOK_CODE,hook);uc.emu_start(base+0x43c70,STOP+1,count=20000)
        assert uc.reg_read(UC_X86_REG_RSP)==rsp+8
        for reg,value in original_regs.items():assert uc.reg_read(reg)==value,(outcome,reg)
        accepted=outcome=='accept';started=outcome in ['accept','non_endless']
        assert (uc.reg_read(UC_X86_REG_RAX)&255)==int(started)
        assert ('native_commit' in calls)==accepted
        assert ('native_start' in calls)==started
        if accepted:assert calls.index('route_export')<calls.index('native_commit')<calls.index('native_start')
        expected=bytearray(source)
        for i in range(7):expected[i*0xa8+0x4c:i*0xa8+0x5c]=bytes(16)
        assert bytes(uc.mem_read(base+0xc75e0,0x498))==(expected if accepted else bytes(0x498))
        for at in [base+0xc75e0-16,base+0xc75e0+0x498,SETUP+0x2288+0x498]:assert bytes(uc.mem_read(at,16))==guard
        results.append(dict(base=hex(base),fixed_flag=flag,outcome=outcome,calls=calls,passed=True))
    report=dict(scope=__doc__.strip(),source_sha256=EXPECTED_FRAME_SHA,game_executed=False,
                cases=len(results),results=results)
    (HERE/'direct_bridge_results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(cases=len(results),passed=True,game_executed=False)))


if __name__=='__main__':main()
