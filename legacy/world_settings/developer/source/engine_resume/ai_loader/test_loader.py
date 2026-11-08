"""Compiled loader contract and original call-site emulation; no Anno process is run."""
from pathlib import Path
import ctypes as C
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
WORK=HERE.parents[1]
ROOT=WORK.parent
sys.path[:0]=[str(WORK/'_tools'),str(WORK/'engine_audit'),str(HERE)]
import pefile
from audit import Module
from loader_bridge import build_loader_bridge,transform_welt,WELT_SHA,LOADER_RVA,LOADER_BEFORE
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *

def main():
    out=HERE/'_build';out.mkdir(exist_ok=True)
    for name in ['tmp','global-cache','local-cache']:(out/name).mkdir(exist_ok=True)
    env=dict(os.environ,ZIG_GLOBAL_CACHE_DIR=str(out/'global-cache'),ZIG_LOCAL_CACHE_DIR=str(out/'local-cache'),TEMP=str(out/'tmp'),TMP=str(out/'tmp'))
    dllpath=out/'LoaderContract.dll'
    subprocess.run([str(WORK/'_tools/ziglang/zig.exe'),'cc','-shared','-O2','-Wall','-Wextra','-Werror','-DWS_AI_LOADER_TEST',str(HERE/'ai_loader.c'),'-lbcrypt','-o',str(dllpath)],check=True,env=env)
    dll=C.CDLL(str(dllpath))
    def bind(name,args,result=C.c_int):
        f=getattr(dll,name);f.argtypes=args;f.restype=result;return f
    configure=bind('WorldSettingsTestConfigure',[C.c_char_p,C.c_char_p])
    ready=bind('WorldSettingsTestReady',[C.c_int],None)
    configured=bind('WorldSettingsTestConfigured',[])
    load=bind('WorldSettingsLoadAiModule',[C.c_char_p],C.c_void_p)
    copyerr=bind('WorldSettingsCopyAILoaderError',[C.c_void_p],C.c_uint32)
    Callback=C.WINFUNCTYPE(C.c_void_p,C.c_char_p)
    calls=[]
    @Callback
    def native(name):calls.append(name);return 0x12345678
    bind('WorldSettingsTestSetLoader',[Callback],None)(native)
    cases=0
    assert configure(None,None)==1 and not configured();cases+=1
    assert load(b'CompLogic.dll')==0x12345678 and calls.pop()==b'CompLogic.dll';cases+=1
    with tempfile.TemporaryDirectory(prefix='fixture-',dir=out) as temp:
        copy=Path(temp)
        ai=copy/'WorldSettingsAI';ai.mkdir()
        for name in ['CompLogic.dll','CompLogicClassic.dll']:shutil.copyfile(WORK/'engine_resume/ai_food/_build/preload'/name,ai/name)
        assert configure(os.fsencode(copy),os.fsencode(ROOT))==1 and not configured();cases+=1
        assert load(b'CompLogic.dll') is None and not calls;cases+=1
        ready(1);assert configured();cases+=1
        for name in ['CompLogic.dll','CompLogicClassic.dll']:
            for nativepath in [name,name.upper(),str(ROOT/name)]:
                assert load(os.fsencode(nativepath))==0x12345678 and calls.pop()==os.fsencode(ai/name);cases+=1
        for name in [b'Other.dll',b'C:\\Other\\CompLogic.dll',b'CompLogic.dll.old',None]:
            assert load(name)==0x12345678 and calls.pop()==name;cases+=1
        target=ai/'CompLogic.dll';original=target.read_bytes();target.write_bytes(original+b'changed')
        assert load(b'CompLogic.dll') is None and not calls;cases+=1
        error=C.create_string_buffer(512);assert 1<=copyerr(error)<=512 and b'SHA256' in error.value;cases+=1
        target.write_bytes(original)
        assert configure(os.fsencode(copy),os.fsencode(copy))==0 and not configured();cases+=1
        assert configure(b'relative',os.fsencode(ROOT))==0 and not configured();cases+=1
        target.unlink()
        assert configure(os.fsencode(copy),os.fsencode(ROOT))==0 and not configured();cases+=1
    original=(ROOT/'AnnoWelt.dll').read_bytes()
    output,meta=transform_welt(original)
    pe=pefile.PE(data=output)
    assert pe.verify_checksum()
    originalpe=pefile.PE(data=original)
    for index in [0,5,9,10,12]:
        old=originalpe.OPTIONAL_HEADER.DATA_DIRECTORY[index]
        new=pe.OPTIONAL_HEADER.DATA_DIRECTORY[index]
        assert (old.VirtualAddress,old.Size)==(new.VirtualAddress,new.Size)
    assert any(d.dll==b'AnnoWorldSettings.dll' and d.imports[0].name==b'WorldSettingsLoadAiModule' for d in pe.DIRECTORY_ENTRY_IMPORT)
    entries=pe.DIRECTORY_ENTRY_EXCEPTION
    assert all(a.struct.EndAddress<=b.struct.BeginAddress for a,b in zip(entries,entries[1:]))
    oldimage=originalpe.get_memory_mapped_image();newimage=pe.get_memory_mapped_image()
    for section in originalpe.sections:
        a=section.VirtualAddress;b=a+section.Misc_VirtualSize
        expected=bytearray(oldimage[a:b])
        if a<=LOADER_RVA<b:expected[LOADER_RVA-a:LOADER_RVA-a+6]=newimage[LOADER_RVA:LOADER_RVA+6]
        assert newimage[a:b]==expected
    cases+=6
    # Run the actual six-byte original CALL redirected to our leaf bridge at two
    # ASLR bases and four near-allocation offsets. The exported loader is the
    # explicit boundary; arguments, stack, return and nonvolatiles execute here.
    m=Module(str(ROOT/'AnnoWelt.dll'));emulated=0
    for base in [0x180000000,0x7ff600000000]:
        for delta in [0x160000,0x1000000,0x12345600,0x6ffff000]:
            u=Uc(UC_ARCH_X86,UC_MODE_64)
            u.mem_map(base,alignpage(len(m.image)));u.mem_write(base,m.image)
            allocation=base+delta
            code,names=build_loader_bridge(delta)
            u.mem_map(allocation&~4095,alignpage((allocation&4095)+len(code)))
            u.mem_write(allocation,code)
            export=0x42000000;u.mem_map(export,4096);u.mem_write(export,b'\xc3')
            u.mem_write(allocation+8,struct.pack('<Q',export))
            u.mem_write(base+LOADER_RVA,b'\xe8'+struct.pack('<i',allocation-base-LOADER_RVA-5)+b'\x90')
            u.mem_map(0x31000000,0x10000);rsp=0x31008000
            u.reg_write(UC_X86_REG_RSP,rsp)
            for reg,value in [(UC_X86_REG_RCX,0x31001000),(UC_X86_REG_RDX,0x22),(UC_X86_REG_R8,0x33),(UC_X86_REG_R9,0x44),(UC_X86_REG_RBX,0x5511),(UC_X86_REG_R12,0x6622)]:u.reg_write(reg,value)
            def boundary(uc,address,size,user):
                if address==export:
                    assert uc.reg_read(UC_X86_REG_RCX)==0x31001000
                    assert uc.reg_read(UC_X86_REG_RSP)==rsp-8
                    assert struct.unpack('<Q',uc.mem_read(rsp-8,8))[0]==base+LOADER_RVA+5
                    uc.reg_write(UC_X86_REG_RAX,0x12345678)
            u.hook_add(UC_HOOK_CODE,boundary)
            u.emu_start(base+LOADER_RVA,base+LOADER_RVA+6,count=100)
            assert u.reg_read(UC_X86_REG_RAX)==0x12345678 and u.reg_read(UC_X86_REG_RSP)==rsp
            assert u.reg_read(UC_X86_REG_RBX)==0x5511 and u.reg_read(UC_X86_REG_R12)==0x6622
            emulated+=1
    assert hashlib.sha256((ROOT/'AnnoWelt.dll').read_bytes()).hexdigest()==WELT_SHA
    (out/'AnnoWelt.ai-loader.candidate.dll').write_bytes(output)
    result=dict(scope=__doc__,compiled_contract_cases=cases,native_call_bridge_cases=emulated,
                candidate_sha256=hashlib.sha256(output).hexdigest(),bridge=meta,
                source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [HERE/'ai_loader.c',HERE/'ai_loader.h',HERE/'loader_bridge.py']},
                boundary='LoadLibrary export is substituted; no game or candidate AI DLL is loaded',
                actual_game_tested=False)
    (HERE/'loader_results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

def alignpage(n):return (n+4095)&~4095

if __name__=='__main__':main()
