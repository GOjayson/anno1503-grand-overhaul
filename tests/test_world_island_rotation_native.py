"""Original HE terrain instructions at typed renderer boundaries; no game run."""
import hashlib
from pathlib import Path
import struct
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / '.local/toolchain/world-options-validation')]
try:
    import pefile
    import unicorn as U
    from unicorn import x86_const as X
except ImportError:
    U = None
from anno1503_overhaul.world_options_rotation import verify_rotation_native_image
from anno1503_overhaul.world_runtime_build import STOCK_SHA256, FOOD_SHA256, RuntimeBuildError
CODE=0x180000000;HEAP=0x31000000;STACK=0x32000000;API=0x33000000;STOP=API+0x1000

def run(image, gfxid, x=3, y=3):
    cpu=U.Uc(U.UC_ARCH_X86,U.UC_MODE_64)
    cpu.mem_map(CODE,(len(image)+4095)&~4095);cpu.mem_write(CODE,image)
    cpu.mem_map(HEAP,0x10000);cpu.mem_map(STACK,0x10000);cpu.mem_map(API,0x2000)
    quad=HEAP;context=HEAP+0x1000;texture=HEAP+0x2000;renderer=HEAP+0x3000
    mesh=HEAP+0x4000;vertices=HEAP+0x5000;indices=HEAP+0x6000;origin=HEAP+0x7000
    def put(at,fmt,*values):cpu.mem_write(at,struct.pack(fmt,*values))
    put(quad,'Q',context);put(quad+0x208+(y*9+x)*4,'H',gfxid)
    put(context,'Q',context+0x100);put(context+0x100+0x48,'Q',API)
    put(texture,'Q',texture+0x100);put(texture+0x100+0xa8,'Q',API+0x20)
    put(renderer,'Q',renderer+0x100);put(renderer+0x100+0x140,'Q',API+0x10);put(renderer+0x100+0x148,'Q',API+0x30)
    put(mesh+8,'QQ',vertices,indices)
    for at,value in ((API,texture),(API+0x10,mesh),(API+0x20,HEAP+0x8000)):
        cpu.mem_write(at,b'\x48\xb8'+struct.pack('<Q',value)+b'\xc3')
    cpu.mem_write(API+0x30,b'\xc3');cpu.mem_write(STOP,b'\x90')
    rsp=STACK+0x8008;put(rsp,'Q',STOP)
    cpu.reg_write(X.UC_X86_REG_RSP,rsp);cpu.reg_write(X.UC_X86_REG_RCX,quad);cpu.reg_write(X.UC_X86_REG_RDX,origin);cpu.reg_write(X.UC_X86_REG_R8,renderer)
    native_calls=[]
    def hook(u,at,size,data):
        if at not in(CODE+0xe58ea,CODE+0xe5960):return
        native_calls.append(hex(at-CODE));stack=u.reg_read(X.UC_X86_REG_RSP);target=struct.unpack('<Q',u.mem_read(stack,8))[0]
        if at==CODE+0xe58ea:
            dest=u.reg_read(X.UC_X86_REG_RCX);value=u.reg_read(X.UC_X86_REG_RDX)&255;n=u.reg_read(X.UC_X86_REG_R8)
            assert n<=0x10000;u.mem_write(dest,bytes([value])*n);u.reg_write(X.UC_X86_REG_RAX,dest)
        u.reg_write(X.UC_X86_REG_RSP,stack+8);u.reg_write(X.UC_X86_REG_RIP,target)
    cpu.hook_add(U.UC_HOOK_CODE,hook)
    cpu.emu_start(CODE+0xc5d30,STOP,count=100000)
    assert cpu.reg_read(X.UC_X86_REG_RIP)==STOP
    vertexcount,indexcount=struct.unpack('<HH',cpu.mem_read(mesh+0x18,4))
    rows=[struct.unpack('<3fI2f',cpu.mem_read(vertices+i*24,24))for i in range(vertexcount)]
    ids=list(struct.unpack('<'+'H'*indexcount,cpu.mem_read(indices,indexcount*2)))
    return dict(gfxid=gfxid,vertices=rows,indices=ids,native_crt_boundaries=native_calls,
                texture_pointer=hex(struct.unpack('<Q',cpu.mem_read(mesh,8))[0]),material_flags=struct.unpack('<I',cpu.mem_read(mesh+0x1c,4))[0])


@unittest.skipIf(U is None, 'Native instruction tools unavailable.')
class NativeRotationFormat(unittest.TestCase):
    def test_both_exact_profiles_and_clockwise_texture_orientation(self):
        paths = [(ROOT / '.local/game-copies/World Settings/AnnoWelt.dll', STOCK_SHA256),
                 (Path('C:/Program Files (x86)/Ubisoft/Ubisoft Game Launcher/games/Anno 1503 - History Edition/AnnoWelt.dll'), FOOD_SHA256)]
        for path, pins in paths:
            if not path.is_file(): raise unittest.SkipTest('Exact private HE inputs unavailable.')
            raw = path.read_bytes()
            proof = verify_rotation_native_image(raw, pins['AnnoWelt.dll'])
            self.assertEqual(len(proof['functions']), 3)
            with self.assertRaises(RuntimeBuildError):
                verify_rotation_native_image(raw[:-1]+bytes([raw[-1]^1]), pins['AnnoWelt.dll'])
            with self.assertRaises(RuntimeBuildError):
                verify_rotation_native_image(raw, '0'*64)
            image = pefile.PE(data=raw).get_memory_mapped_image()
            result = [run(image, (33<<8)|(2<<5)|(4<<2)|orientation) for orientation in range(4)]
            for old in range(4):
                uv = [v[-2:] for v in result[old]['vertices']]
                self.assertEqual(len(uv), 4)
                for turns in range(4):
                    self.assertEqual([v[-2:] for v in result[(old-turns)&3]['vertices']], uv)
                    uv = [uv[i] for i in (1,3,0,2)]
                self.assertEqual(result[old]['indices'], [0,1,2,2,1,3])
                self.assertEqual(result[old]['native_crt_boundaries'], ['0xe5960','0xe58ea'])
                self.assertEqual(result[old]['material_flags'], 0)
            self.assertEqual(run(image, 0)['vertices'], [])

if __name__ == '__main__':
    unittest.main()
