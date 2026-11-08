"""Execute the complete native ca2f0 view-list producer on bounded fixtures.

Fixtures provide visibility cells, all-ocean World geometry, a clipping result,
CRT allocation/deletion/memset and stack probing. The producer's native loops,
stack arrays, neighbour pointers, old-record lookup and recycling all execute.
This does not draw a frame or establish an actual Anno game run.
"""
from pathlib import Path
import argparse,hashlib,importlib.util,json,struct,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;GAME=HERE.parents[3]
sys.path.insert(0,str(GAME/'WorldSettings_Work/_tools'))
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *


def sha(data):return hashlib.sha256(data).hexdigest()


def require(ok,message):
    if not ok:raise ValueError(message)


class Producer:
    def __init__(self,blob,base,patched):
        self.base=base;self.patched=patched;self.u=u=Uc(UC_ARCH_X86,UC_MODE_64)
        p=pefile.PE(data=blob);p.relocate_image(base);image=p.get_memory_mapped_image()
        u.mem_map(base,(len(image)+4095)&~4095);u.mem_write(base,bytes(image))
        self.stack=0x4000000;self.world=0x5000000;self.data=0x6000000;self.output=0x7000000;self.heap=0x8000000;self.stop=0x9000000
        for at,n in[(self.stack,0x200000),(self.world,0x30000),(self.data,0x10000),(self.output,0xc1000),(self.heap,0x400000),(self.stop,0x1000)]:u.mem_map(at,n)
        self.created=[];self.deleted=[];self.alloc_at=self.heap;self.visible=set();self.native_helper=False
        for rva in[0xe5960,0xe58ea,0xe46bc,0xe46f8,0xe43f0,0xc9eb0]:u.hook_add(UC_HOOK_CODE,self.callback,begin=base+rva,end=base+rva)
    def returns(self,value=None):
        u=self.u;sp=u.reg_read(UC_X86_REG_RSP);ret=struct.unpack('<Q',u.mem_read(sp,8))[0]
        if value is not None:u.reg_write(UC_X86_REG_RAX,value&0xffffffffffffffff)
        u.reg_write(UC_X86_REG_RSP,sp+8);u.reg_write(UC_X86_REG_RIP,ret)
    def callback(self,u,address,size,unused):
        rva=address-self.base
        if rva==0xe5960:self.returns()
        elif rva==0xe58ea:
            at=u.reg_read(UC_X86_REG_RCX);value=u.reg_read(UC_X86_REG_RDX)&255;n=u.reg_read(UC_X86_REG_R8)
            require(n<=0x10420,'Unexpected memset size');u.mem_write(at,bytes([value])*n);self.returns(at)
        elif rva==0xe46bc:
            n=u.reg_read(UC_X86_REG_RCX);require(n==0x390,'Unexpected native allocation size');at=self.alloc_at;self.alloc_at+=(n+15)&~15
            u.mem_write(at,bytes(n));self.created.append(at);self.returns(at)
        elif rva==0xe46f8:
            at=u.reg_read(UC_X86_REG_RCX);n=u.reg_read(UC_X86_REG_RDX);require(n==0x390,'Unexpected delete size');self.deleted.append(at);self.returns()
        elif rva==0xe43f0:self.returns(1)
        elif rva==0xc9eb0 and not self.native_helper:
            at=u.reg_read(UC_X86_REG_R9);stride=4 if self.patched else 2;mask=bytearray(2048 if self.patched else 512)
            for x,y in self.visible:
                offset=(y*stride+x//32)*4;value=struct.unpack_from('<I',mask,offset)[0]
                struct.pack_into('<I',mask,offset,value|(1<<(x%32)))
            u.mem_write(at,bytes(mask));self.returns()
    def run(self,size,visible,previous=None,native_helper=False):
        u=self.u;self.visible=set(visible);self.native_helper=native_helper;self.deleted=[]
        u.mem_write(self.world,bytes(0x20000));u.mem_write(self.world,struct.pack('<Q',self.base+0xff650))
        u.mem_write(self.world+0x1d8,struct.pack('<II',size,size));u.mem_write(self.world+0x10000,b'\xff'*65536)
        auxiliary=self.data+0x2000;vt=self.data+0x3000
        u.mem_write(self.world+0x208,struct.pack('<Q',auxiliary));u.mem_write(auxiliary,struct.pack('<Q',vt));u.mem_write(vt+0x88,struct.pack('<Q',self.base+0xc1600))
        u.mem_write(self.output,bytes(0xc1000))
        if previous:
            u.mem_write(self.output,struct.pack('<I',len(previous)))
            for i,row in enumerate(previous):u.mem_write(self.output+8+i*88,row)
        sp=self.stack+0x1f0008;u.mem_write(sp,struct.pack('<Q',self.stop));u.reg_write(UC_X86_REG_RSP,sp)
        u.reg_write(UC_X86_REG_RCX,self.world);u.reg_write(UC_X86_REG_RDX,self.data);u.reg_write(UC_X86_REG_R8,self.data+0x100);u.reg_write(UC_X86_REG_R9,self.output)
        saved={r:0x1111000000000000+i for i,r in enumerate([UC_X86_REG_RBX,UC_X86_REG_RBP,UC_X86_REG_RSI,UC_X86_REG_RDI,UC_X86_REG_R12,UC_X86_REG_R13,UC_X86_REG_R14,UC_X86_REG_R15])}
        for reg,value in saved.items():u.reg_write(reg,value)
        u.emu_start(self.base+0xca2f0,self.stop,count=30000000)
        require(u.reg_read(UC_X86_REG_RIP)==self.stop,'Native producer did not return')
        require(u.reg_read(UC_X86_REG_RSP)==sp+8 and all(u.reg_read(r)==v for r,v in saved.items()),'Native producer damaged caller stack/registers')
        count=struct.unpack('<I',u.mem_read(self.output,4))[0];require(count<=8192,'Native producer exceeded record capacity')
        records=[bytes(u.mem_read(self.output+8+88*i,88))for i in range(count)]
        coords=[struct.unpack_from('<HH',row)for row in records]
        expected=[(x*16,y*16)for x,y in sorted(self.visible,key=lambda p:(p[1],p[0]))][:8192]
        require(coords==expected,'Native producer coordinates differ from exact visible cells')
        if self.patched:
            rbp=sp-64-(0xe0ce8-0x100);matrix=struct.unpack('<16384I',u.mem_read(rbp+0xbe0,65536))
            require(set(matrix).issubset(set(range(count+1)))and sum(v!=0 for v in matrix)==count,'Native matrix contains an unassigned/nonreachable encoded index')
            require(all(matrix[(y//16)*128+x//16]==i+1 for i,(x,y)in enumerate(coords)),'Native matrix row stride/index encoding differs from produced geometry')
        for row in records:
            x,y=struct.unpack_from('<HH',row)
            for at in[0x28,0x30]:
                ptr=struct.unpack_from('<Q',row,at)[0]
                require(not ptr or self.output+8<=ptr<self.output+8+88*count,'Native neighbour pointer leaves the produced list')
        return dict(count=count,coordinates=coords,records=records,deleted=list(self.deleted),all_nonvolatile_registers_preserved=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--candidate',type=Path,default=HERE/'AnnoWelt.visibility_candidate2.dll');parser.add_argument('--baseline',type=Path,default=GAME/'WorldSettings_Work/anno1503_food_world_dev8/native/AnnoWelt.world.dll');a=parser.parse_args()
    baseline=a.baseline.read_bytes();candidate=a.candidate.read_bytes()
    require(sha(baseline)=='bc4de21e6c92ab5a94d9fc50d25f0609d9e1cdb2ff119c29238d3354f978fb29','Use the preserved119-site baseline as --baseline')
    cases=[]
    for base in[0x180000000,0x280000000]:
        old=Producer(baseline,base,False);new=Producer(candidate,base,True)
        for size in[256,512,1024]:
            limit=size//16
            selections=[{(x,y)for y in range(limit)for x in range(limit)},
                {(x,y)for y in range(max(0,limit-5),limit)for x in range(max(0,limit-7),limit)},
                {(x,y)for y in range(limit)for x in range(limit)if(x+3*y)%7==0}]
            for selected in selections:
                left=old.run(size,selected);right=new.run(size,selected)
                require(left['records']==right['records'],'Supported size native output differs')
                cases.append(dict(image_base=hex(base),world_size=size,visible_cells=len(selected),native_records=right['count'],exact_old_record_bytes_equal=True))
            before_old=old.run(size,selections[0]);before_new=new.run(size,selections[0])
            after_old=old.run(size,selections[2],previous=before_old['records']);after_new=new.run(size,selections[2],previous=before_new['records'])
            require(after_old['records']==after_new['records'],'Supported-size previous-record cache transition differs')
            cases.append(dict(image_base=hex(base),world_size=size,case='native_previous_cache_transition',before=before_old['count'],after=after_new['count'],exact_old_record_bytes_equal=True))
        for selected in[{(0,0),(64,0),(0,1),(80,0),(0,80),(127,127)},
            {(x,y)for y in range(120,128)for x in range(112,128)},
            {(x,y)for y in range(128)for x in range(128)}]:
            result=new.run(2048,selected)
            cases.append(dict(image_base=hex(base),world_size=2048,visible_cells=len(selected),native_records=result['count'],all_coordinates_and_neighbour_pointers_valid=True,capacity_truncation=len(selected)>8192))
        far={(x,y)for y in range(120,128)for x in range(112,128)}
        previous=new.run(2048,far)['records'];owned=[];seeded=[]
        for i,row in enumerate(previous):
            handle=new.heap+0x200000+i*0x390;owned.append(handle);data=bytearray(row);struct.pack_into('<Q',data,8,handle);seeded.append(bytes(data))
        kept=new.run(2048,far,previous=seeded)
        require([struct.unpack_from('<Q',row,8)[0]for row in kept['records']]==owned,'Native mapped cells did not retain their exact cached corner ownership')
        require(not kept['deleted'],'Native mapped cells deleted retained cache handles')
        dropped=new.run(2048,{(x,y)for y in range(128)for x in range(128)},previous=seeded)
        retained=struct.unpack('<Q',new.u.mem_read(new.output+0xc0010,8))[0]
        require(retained in owned and set(dropped['deleted'])==set(owned)-{retained}and len(dropped['deleted'])==len(owned)-1,'Capped unassigned cells did not recycle every cached handle exactly once')
        cases.append(dict(image_base=hex(base),world_size=2048,case='mapped_and_capped_unassigned_cache_ownership',owned_handles=len(owned),mapped_handles_retained=True,unassigned_handles_reused_for_common_water_node=1,unassigned_handles_deleted=len(dropped['deleted']),all_handles_accounted_for=True))
        for size in[1024,2048]:
            visible={(x,y)for y in range(size//16)for x in range(size//16)}
            result=new.run(size,visible,native_helper=True)
            cases.append(dict(image_base=hex(base),world_size=size,case='complete_native_helper_and_producer',visible_cells=len(visible),native_records=result['count'],native_visibility_helper_executed=True))
    report=dict(scope=__doc__,passed=True,baseline_sha256=sha(baseline),candidate_sha256=sha(candidate),cases=cases,
        complete_native_producer_executed=True,actual_game_run=False,actual_rendering_verified=False,game_or_copy_or_source_modified=False,
        source_sha256=sha(Path(__file__).read_bytes()))
    output=HERE/'visibility_producer_results.json';output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(passed=True,cases=len(cases),candidate_sha256=sha(candidate),actual_game_run=False),indent=2))


if __name__=='__main__':main()
