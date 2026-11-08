"""Execute exact crop application/property/cultivation instructions in Unicorn.

No game process, save or production chain is run. Synthetic island/definition
buffers and explicitly named external getter/collection/file boundaries are used.
"""
from pathlib import Path
import hashlib, json, struct, sys
HERE=Path(__file__).resolve().parent; GAME=next(p for p in HERE.parents if (p/'Anno1503.exe').is_file())
PACKAGE=next((p for p in HERE.parents if (p/'developer/source/engine_audit/audit.py').is_file()),GAME/'WorldSettings_Work/anno1503_food_world_dev5')
sys.path.insert(0,str(GAME/'WorldSettings_Work/_tools'))
sys.path.insert(0,str(PACKAGE/'developer/source/engine_audit'))
sys.path.insert(0,str(PACKAGE/'developer/source/native_world'))
from audit import Module
import native_emulate
native_emulate.ROOT=GAME
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *
W=Module(str(GAME/'AnnoWelt.dll'))
Q=lambda x:struct.pack('<Q',x)
I=lambda x:struct.pack('<I',x)

def query(base,crop,climate,fertility,mask):
    u=Uc(UC_ARCH_X86,UC_MODE_64)
    u.mem_map(base,(len(W.image)+4095)&~4095);u.mem_write(base,W.image)
    for at,size in [(0x40000000,0x20000),(0x50000000,0x10000),(0x60000000,0x1000)]:u.mem_map(at,size)
    island=0x40000000;definition=0x40001000;vt=0x40002000;cells=0x40003000;chunks=0x40004000
    obj=bytearray(0x200);struct.pack_into('<HHHH',obj,8,0,0,8,8)
    struct.pack_into('<Q',obj,0x28,cells)
    struct.pack_into('<IIQ',obj,0x110,1,1,chunks)
    struct.pack_into('<I',obj,0x134,mask);obj[0x148]=climate
    u.mem_write(island,bytes(obj));u.mem_write(cells,bytes([fertility])*64)
    u.mem_write(definition,Q(vt));u.mem_write(vt+0x160,Q(0x60000010));u.mem_write(vt+0x1b0,Q(0x60000020))
    u.mem_write(0x60000010,b'\xc3');u.mem_write(0x60000020,b'\xc3')
    captured=[]
    def hook(uc,at,size,userdata):
        if at==0x60000000:uc.emu_stop()
        elif at==0x60000010:uc.reg_write(UC_X86_REG_RAX,0x38+crop)
        elif at==0x60000020:uc.reg_write(UC_X86_REG_RAX,1<<climate)
        elif at==base+0x41a75:
            captured.append(uc.reg_read(UC_X86_REG_RCX)&255)
    u.hook_add(UC_HOOK_CODE,hook)
    results=[]
    for y in range(8):
        for x in range(8):
            sp=0x5000f008;u.mem_write(sp,Q(0x60000000));u.reg_write(UC_X86_REG_RSP,sp)
            for reg,value in [(UC_X86_REG_RCX,island),(UC_X86_REG_RDX,x),(UC_X86_REG_R8,y),(UC_X86_REG_R9,definition)]:u.reg_write(reg,value)
            u.emu_start(base+0x41860,0x60000000,count=10000)
            assert u.reg_read(UC_X86_REG_RIP)==0x60000000
            assert u.reg_read(UC_X86_REG_RSP)==sp+8
            results.append(u.reg_read(UC_X86_REG_RAX)&0xffffffff)
    assert len(captured)==64 and len(set(captured))==1
    return dict(mask=hex(mask),effective_fertility=captured[0],true_query_cells=sum(results),false_query_cells=64-sum(results))

def main():
    results=[];applications=[];property_cases=[]
    assert hashlib.sha256(W.data).hexdigest()=='ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9'
    for base in [0x180000000,0x280000000]:
        for climate in range(6):
            for planned in [0,0x1ffff]+[1<<i for i in range(17)]:
                e=native_emulate.NativeScene(base)
                original_nodes=e.nodes
                def nodes(climates,size=128):
                    ns=original_nodes([climate],size)
                    for bit in range(20):e.write(ns[0]+0x122+2*bit,struct.pack('<H',int(bool(planned&(1<<bit)))))
                    return ns
                e.nodes=nodes
                observed=e.apply([],0)['crop_masks']
                assert observed==[planned|0xf009],(climate,hex(planned),observed)
                applications.append(dict(base=hex(base),climate=climate,planned_mask=hex(planned),actual_mask=hex(observed[0])))
        # Execute original virtual setter+getter directly, no boundary doubles.
        u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,(len(W.image)+4095)&~4095);u.mem_write(base,W.image)
        u.mem_map(0x40000000,0x10000);u.mem_map(0x50000000,0x10000);u.mem_map(0x60000000,0x1000)
        for mask in [0,0xf009,0xf04d,0xf6b9,0x1ffff]:
            for rva in [0x49470,0x49500]:
                sp=0x5000f008;u.mem_write(sp,Q(0x60000000));u.reg_write(UC_X86_REG_RSP,sp)
                u.reg_write(UC_X86_REG_RCX,0x40000000);u.reg_write(UC_X86_REG_RDX,11);u.reg_write(UC_X86_REG_R8,mask)
                u.emu_start(base+rva,0x60000000,count=1000)
                assert u.reg_read(UC_X86_REG_RIP)==0x60000000
                if rva==0x49500:assert u.reg_read(UC_X86_REG_RAX)==mask
            property_cases.append(dict(base=hex(base),mask=hex(mask),setter_rva='0x49470',getter_rva='0x49500'))
        for crop,climate in [(1,3),(2,5),(4,4),(5,4),(6,2),(7,4),(8,2),(9,4),(10,4),(11,2)]:
            for fertility in [1,5,10,15]:
                absent=query(base,crop,climate,fertility,0xf009)
                present=query(base,crop,climate,fertility,0xf009|(1<<crop))
                assert absent['effective_fertility']==present['effective_fertility']//2
                results.append(dict(base=hex(base),crop=crop,climate=climate,land_fertility=fertility,absent=absent,present=present))
    report=dict(scope=__doc__,native_welt_sha256=hashlib.sha256(W.data).hexdigest(),native_scene_sha256=hashlib.sha256((GAME/'AnnoScene.dll').read_bytes()).hexdigest(),
                application_cases=applications,property_roundtrips=property_cases,cultivation_cases=results,
                boundary_doubles=['Scene world/island/occurrence/CRT methods as declared in NativeScene fixture','41860 definition growth-type getter+0x160 and climate-mask getter+0x1b0 only'],
                conclusion='Actual crop application sets planned mask OR0xf009 for every climate. Crop flag absence halves the effective fertility used by the native spatial cultivation query; this is not an absolute prohibition of harvesting.',game_executed=False,passed=True)
    (HERE/'native_crop_path_results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(passed=True,application_cases=len(applications),property_roundtrips=len(property_cases),cultivation_cases=len(results),cultivation_cell_queries=64*2*len(results),sample=results[1]),indent=2))

if __name__=='__main__':main()
