"""Execute exact native Frame camera-coordinate bounds and World getters.

This is a bounded native instruction test with fixture objects, not a game
rendering test. It proves this identified coordinate clamp is dynamic through
the native World interface; minimap transforms and all camera callers remain
separate live/reverse-engineering scope.
"""
from pathlib import Path
import hashlib,json,struct,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;GAME=HERE.parents[2]
sys.path.insert(0,str(GAME/'WorldSettings_Work/_tools'))
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64
from unicorn.x86_const import UC_X86_REG_RCX,UC_X86_REG_RSP,UC_X86_REG_RBX,UC_X86_REG_XMM6


def sha(blob):return hashlib.sha256(blob).hexdigest()


def main():
    fb=(GAME/'AnnoFrame.dll').read_bytes();wb=(GAME/'AnnoWelt.dll').read_bytes()
    assert sha(fb)=='046b5ad6f351dfe867ed38ce29fb50a594485b43a32ee90adadc48e850466baf'
    assert sha(wb)=='ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9'
    fm=pefile.PE(data=fb).get_memory_mapped_image();wm=pefile.PE(data=wb).get_memory_mapped_image()
    cases=[];bounds=[1.0,0.0,-1.0,-255.0,-511.0,-1023.0,-1024.0,-1025.0,-2047.0,-2048.0,-2049.0,-3000.0]
    for frame_base,world_base in [(0x180000000,0x280000000),(0x380000000,0x480000000)]:
        u=Uc(UC_ARCH_X86,UC_MODE_64)
        for base,image in [(frame_base,fm),(world_base,wm)]:u.mem_map(base,(len(image)+4095)&~4095);u.mem_write(base,image)
        obj,world,stack,stop=0x4000000,0x5000000,0x6000000,0x7000000
        u.mem_map(obj,0xc2000);u.mem_map(world,0x20000);u.mem_map(stack,0x10000);u.mem_map(stop,0x1000)
        vt=world_base+0xff650;u.mem_write(world,struct.pack('<Q',vt));u.mem_write(vt+0xb0,struct.pack('<QQ',world_base+0xc7c90,world_base+0xc7ca0))
        for size in [256,512,1024,2048]:
            u.mem_write(world+0x1d8,struct.pack('<II',size,size))
            for i,x in enumerate(bounds):
                y=bounds[(i*5)%len(bounds)];initial=bytearray([0xa5])*0xc2000
                struct.pack_into('<Q',initial,0x18,world);struct.pack_into('<fff',initial,0xc0320,x,77.5,y)
                u.mem_write(obj,bytes(initial));sp=stack+0x8008;u.mem_write(sp,struct.pack('<Q',stop))
                u.reg_write(UC_X86_REG_RCX,obj);u.reg_write(UC_X86_REG_RSP,sp);u.reg_write(UC_X86_REG_RBX,0x12345678);u.reg_write(UC_X86_REG_XMM6,0x12345678123456781234567812345678)
                u.emu_start(frame_base+0x1d640,stop,count=200)
                result=bytes(u.mem_read(obj,len(initial)));actual_x,actual_z,actual_y=struct.unpack_from('<fff',result,0xc0320)
                expected_x=max(-size,min(0,x));expected_y=max(-size,min(0,y))
                assert (actual_x,actual_z,actual_y)==(expected_x,77.5,expected_y)
                allowed=set(range(0xc0320,0xc0324))|set(range(0xc0328,0xc032c))
                assert all(a==b or at in allowed for at,(a,b)in enumerate(zip(initial,result)))
                assert u.reg_read(UC_X86_REG_RBX)==0x12345678 and u.reg_read(UC_X86_REG_XMM6)==0x12345678123456781234567812345678
                cases.append(dict(frame_base=hex(frame_base),world_base=hex(world_base),world_size=size,input=[x,y],output=[actual_x,actual_y],expected=[expected_x,expected_y]))
    report=dict(scope=__doc__,passed=True,frame_sha256=sha(fb),world_sha256=sha(wb),native_frame_bounds_function_rva='0x1d640',native_world_dimension_getters=['0xc7c90','0xc7ca0'],
        coordinate_members=['0xc0320','0xc0328'],native_world_object_member='Frame+0x18',cases=cases,case_count=len(cases),
        sizes_tested=[256,512,1024,2048],two_relocated_image_base_pairs=True,nonvolatile_registers_and_unrelated_object_memory_preserved=True,
        this_bounds_function_contains_no_fixed1024_world_clamp=True,minimap_or_actual_camera_UI_proven=False,game_executed=False,game_or_copy_mutated=False,
        test_source_sha256=sha(Path(__file__).read_bytes()))
    (HERE/'camera_bounds_results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(passed=True,cases=len(cases),sizes=report['sizes_tested'],actual_game_run=False),indent=2))


if __name__=='__main__':main()
