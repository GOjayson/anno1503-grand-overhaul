"""Original AMD64 ore constructor/setter/consume/save/load instruction proof.

Native code executes in Unicorn at two independent module bases. Objects and
Figure buffers are constructed; stream I/O and world flags are explicit boundary
doubles. This is not an Anno process, complete world load or mining test.
"""
from pathlib import Path
import hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent
GAME=next(p for p in HERE.parents if (p/'Anno1503.exe').is_file() and (p/'WorldSettings_Work/_tools').is_dir())
PACKAGE=next((p for p in HERE.parents if (p/'world_patch.json').is_file()),GAME/'WorldSettings_Work/anno1503_food_world_dev5')
sys.path.insert(0,str(GAME/'WorldSettings_Work/_tools'))
sys.path.insert(0,str(PACKAGE/'developer/source/engine_audit'))
from audit import Module
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *
W=Module(str(GAME/'AnnoWelt.dll'));G=Module(str(GAME/'AnnoGame.dll'))
EXPECTED={'AnnoWelt.dll':'ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9','AnnoGame.dll':'e6f01d19e8e16e6716c0a6c7d3ba00273c9df493e051b8ba62865ee4b53dfdea'}
for m in [W,G]:
    assert hashlib.sha256(m.data).hexdigest()==EXPECTED[Path(m.name).name]
    assert m.pe.FILE_HEADER.Machine==0x8664 and m.pe.OPTIONAL_HEADER.Magic==0x20b
Q=lambda x:struct.pack('<Q',x)
I=lambda x:struct.pack('<I',x)
class NativeOre:
    def __init__(self,wbase,gbase):
        self.u=Uc(UC_ARCH_X86,UC_MODE_64);self.wbase=wbase;self.gbase=gbase
        for m,base in [(W,wbase),(G,gbase)]:
            pe=pefile.PE(data=m.data);pe.relocate_image(base);image=bytes(pe.get_memory_mapped_image())
            self.u.mem_map(base,(len(image)+4095)&~4095);self.u.mem_write(base,image)
        self.u.mem_map(0x40000000,0x20000);self.u.mem_map(0x50000000,0x20000);self.u.mem_map(0x60000000,0x10000)
        self.obj=0x40000000;self.other=0x40001000;self.io=0x40002000;self.count=0x40003000
        self.parent=0x40004000;self.world=0x40005000
        self.stop=0x60000000;self.stub_getworld=0x60000010;self.stub_flags=0x60000020
        self.stub_read=0x60000030;self.stub_write=0x60000040
        for a in [self.stop,self.stub_getworld,self.stub_flags,self.stub_read,self.stub_write]:self.u.mem_write(a,b'\xc3')
        self.u.mem_write(self.parent,Q(self.parent+0x800));self.u.mem_write(self.parent+0x800+0x38,Q(self.stub_getworld))
        self.u.mem_write(self.world,Q(self.world+0x800));self.u.mem_write(self.world+0x800+0xf0,Q(self.stub_flags))
        self.u.mem_write(self.io,Q(self.io+0x800));self.u.mem_write(self.io+0x800,Q(self.stub_write));self.u.mem_write(self.io+0x808,Q(self.stub_read))
        self.flags=2;self.payload=b'';self.bytes_read=0;self.bytes_written=0
        self.u.hook_add(UC_HOOK_CODE,self.hook)
    def hook(self,u,a,n,data):
        if a==self.stop:u.emu_stop();return
        if a==self.stub_getworld:u.reg_write(UC_X86_REG_RAX,self.world)
        elif a==self.stub_flags:u.reg_write(UC_X86_REG_RAX,self.flags)
        elif a==self.stub_read:
            count=u.reg_read(UC_X86_REG_R8);assert count==len(self.payload)==8
            u.mem_write(u.reg_read(UC_X86_REG_RDX),self.payload);u.mem_write(u.reg_read(UC_X86_REG_R9),I(count));self.bytes_read+=count
            u.reg_write(UC_X86_REG_RAX,1)
        elif a==self.stub_write:
            count=u.reg_read(UC_X86_REG_R8);assert count==8
            self.payload=bytes(u.mem_read(u.reg_read(UC_X86_REG_RDX),count));u.mem_write(u.reg_read(UC_X86_REG_R9),I(count));self.bytes_written+=count
            u.reg_write(UC_X86_REG_RAX,1)
    def run(self,rva,*args):
        sp=0x5001e008;self.u.mem_write(sp,Q(self.stop));self.u.reg_write(UC_X86_REG_RSP,sp)
        for reg,v in zip([UC_X86_REG_RCX,UC_X86_REG_RDX,UC_X86_REG_R8,UC_X86_REG_R9],args[:4]):self.u.reg_write(reg,v)
        if len(args)>4:self.u.mem_write(sp+0x28,Q(args[4]))
        self.u.emu_start(self.wbase+rva,self.stop+1,count=10000)
        assert self.u.reg_read(UC_X86_REG_RIP)==self.stop and self.u.reg_read(UC_X86_REG_RSP)==sp+8
        return self.u.reg_read(UC_X86_REG_RAX)&0xffffffff
    def definition(self,ident,kind=1):
        at=0x40010000+(ident-1550)*0x200
        self.u.mem_write(at,Q(self.gbase+0x21038));self.u.mem_write(at+8,I(ident));self.u.mem_write(at+0x108,bytes([kind]))
        return at
    def construct(self,obj,ident,kind=1):
        self.u.mem_write(obj,bytes(0x48));assert self.run(0x71960,obj)==obj
        assert self.run(0x718f0,obj,self.definition(ident,kind))==0
        self.u.mem_write(obj+0x10,Q(self.parent))
    def fields(self,obj):
        q,discovery,reserve,disabled=struct.unpack('<IIBB',bytes(self.u.mem_read(obj+0x38,10)))
        return dict(quantity_fixed=q,discovery=discovery,reserve=reserve,disabled=disabled)
    def exhaust(self,obj):
        self.run(0x718b0,obj,1,0)
        q=self.run(0x717e0,obj,1)
        assert self.run(0x71800,obj,q,1)==q
        assert self.fields(obj)['quantity_fixed']==0
    def save(self,obj):
        self.run(0x71730,obj,self.io,0,self.count)
        assert struct.unpack('<I',bytes(self.u.mem_read(self.count,4)))[0]==8
        return self.payload
    def load(self,obj,ident,payload,kind=1):
        self.construct(obj,ident,kind);self.payload=payload
        assert self.run(0x71600,obj,self.io,0,8,self.count)==1
        assert struct.unpack('<I',bytes(self.u.mem_read(self.count,4)))[0]==8
        return self.fields(obj)
results=[]
for delta in [0,0x100000000]:
    wb,gb=0x180000000+delta,0x190000000+delta
    for ident in [1560,1561,1562,1563,1564,1661]:
        e=NativeOre(wb,gb);e.construct(e.obj,ident)
        initial=e.fields(e.obj);e.exhaust(e.obj);depleted=e.fields(e.obj)
        payload=e.save(e.obj);raw_reload=e.load(e.other,ident,payload)
        assert raw_reload['quantity_fixed']==(0 if ident==1661 else 0x7d000)
        # Normalize only already-exhausted objects to the engine's persisted
        # non-reserve shallow-iron representation, then exhaust the setter's
        # temporary400t entirely through the original consume method.
        assert e.run(0x718f0,e.obj,e.definition(1661))==0
        temporary=e.fields(e.obj);assert temporary['quantity_fixed']==0x19000 and temporary['reserve']==0
        assert e.run(0x71800,e.obj,0x19000,1)==0x19000
        normalized=e.fields(e.obj);assert normalized['quantity_fixed']==0 and normalized['reserve']==0
        fixed_payload=e.save(e.obj);fixed_reload=e.load(e.other,1661,fixed_payload)
        assert fixed_reload['quantity_fixed']==0 and fixed_reload['reserve']==0 and fixed_reload['disabled']==0
        assert e.run(0x717e0,e.other,0)==e.run(0x717e0,e.other,1)==0
        results.append(dict(welt_base=hex(wb),game_base=hex(gb),original_definition=ident,
            initial=initial,depleted_by_original_native_sequence=depleted,
            native_saved_payload_hex=payload.hex(),native_unfixed_reload=raw_reload,
            normalized=normalized,normalized_payload_hex=fixed_payload.hex(),native_normalized_reload=fixed_reload,
            read_write_bytes=[e.bytes_read,e.bytes_written]))
    for quantity in [1,400,1600,2000,32767,65535]:
        e=NativeOre(wb,gb);e.construct(e.obj,1661);e.u.mem_write(e.obj+0x38,I(quantity<<8))
        payload=e.save(e.obj);loaded=e.load(e.other,1661,payload)
        assert loaded['quantity_fixed']==quantity<<8 and loaded['reserve']==0
        results.append(dict(welt_base=hex(wb),case='shallow positive quantity unchanged',tons=quantity,loaded=loaded))
    # Extraction refusal is observable: no claim that a native method always
    # succeeds. The integrated normalizer must reject if postconditions fail.
    e=NativeOre(wb,gb);e.construct(e.obj,1661);e.flags=0
    refused_result=e.run(0x71800,e.obj,0x19000,1)
    assert refused_result==0x19000 and e.fields(e.obj)['quantity_fixed']==0x19000
    results.append(dict(welt_base=hex(wb),case='world flag denies extraction but reports requested amount; caller must check actual quantity',returned=refused_result,passed=True))
report=dict(scope=__doc__,fingerprints=EXPECTED,original_instruction_cases=len(results),
    bases=2,results=results,passed=True,game_executed=False,
    boundary_doubles=['8byte stream read/write','world property flags=2 or0'],
    original_native_functions=['Welt71960 constructor','Welt718f0 definition setter','Welt718b0 flag setter','Welt717e0 quantity getter','Welt71800 extraction','Welt71730 save','Welt71600 load','Game159d0 class','Game159e0 definition ID','Game14a30 category'])
(HERE/'native_mineral_persistence_results.json').write_text(json.dumps(report,indent=2)+'\n')
(HERE/'native_mineral_persistence.asm').write_text('\n\n'.join(m.name+' '+hex(a)+'\n'+m.dis(a,b) for m,a,b in [(W,0x71960,0x719d5),(W,0x718f0,0x71955),(W,0x71730,0x717a9),(W,0x71600,0x7172f),(W,0x717e0,0x717f8),(W,0x718b0,0x718ef),(W,0x71800,0x718a0),(W,0x5c3f0,0x5c7f7),(W,0x5be00,0x5c342)]))
print(json.dumps(dict(passed=True,original_instruction_cases=len(results),bases=2,zero_absence_fixed=True,game_executed=False),indent=2))
