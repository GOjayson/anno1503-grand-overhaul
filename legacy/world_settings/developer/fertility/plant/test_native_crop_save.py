"""Execute original ANBAU writer/loader loops with explicit IO boundaries.

The crop enumeration, mask tests, name matching, climate baseline and ORs are
unaltered AMD64 instructions. File reading, dictionary name requests and bounded
string copy are synthetic boundaries. No actual game save or game process runs.
"""
from pathlib import Path
import hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent;GAME=next(p for p in HERE.parents if (p/'Anno1503.exe').is_file())
PACKAGE=next((p for p in HERE.parents if (p/'developer/source/engine_audit/audit.py').is_file()),GAME/'WorldSettings_Work/anno1503_food_world_dev5')
sys.path.insert(0,str(GAME/'WorldSettings_Work/_tools'))
sys.path.insert(0,str(PACKAGE/'developer/source/engine_audit'))
from audit import Module
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *
W=Module(str(GAME/'AnnoWelt.dll'));G=Module(str(GAME/'AnnoGame.dll'))
Q=lambda n:struct.pack('<Q',n)
I=lambda n:struct.pack('<I',n)
NAMES=[]
for i in range(13):
    at=struct.unpack_from('<Q',G.image,0x23400+8*i)[0]-G.base
    NAMES.append(G.image[at:at+64].split(b'\0')[0])

def engine(base):
    u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,(len(W.image)+4095)&~4095);u.mem_write(base,W.image)
    for at,size in [(0x40000000,0x10000),(0x50000000,0x20000),(0x60000000,0x1000)]:u.mem_map(at,size)
    u.mem_write(0x60000010,b'\xc3');u.mem_write(0x60000020,b'\xc3');u.mem_write(0x60000030,b'\xc3')
    u.mem_write(0x40001000,Q(0x40002000));u.mem_write(0x40002098,Q(0x60000010))
    u.mem_write(0x40000030,Q(0x40001000))
    return u

def cstr(u,p):
    out=bytearray()
    while len(out)<256:
        value=bytes(u.mem_read(p+len(out),1))
        if value==b'\0':return bytes(out)
        out+=value
    raise AssertionError('Unterminated synthetic name')

def writer(base,mask):
    u=engine(base);u.mem_write(0x40000134,I(mask))
    u.mem_write(base+0xea288,Q(0x60000020))
    u.reg_write(UC_X86_REG_RDI,0x40000000);u.reg_write(UC_X86_REG_RSI,0x40004000)
    u.reg_write(UC_X86_REG_RBP,0x50010000);u.reg_write(UC_X86_REG_RSP,0x5000f000)
    u.reg_write(UC_X86_REG_R14,1);u.reg_write(UC_X86_REG_R15,0);u.reg_write(UC_X86_REG_R13,0xffffffffffffffff)
    calls=[]
    def hook(uc,at,size,data):
        if at==0x60000010:
            p=uc.reg_read(UC_X86_REG_R8);enum=struct.unpack('<I',uc.mem_read(p,4))[0];assert 0x38<=enum<=0x44
            uc.mem_write(p+8,NAMES[enum-0x38]+b'\0');uc.reg_write(UC_X86_REG_RAX,1);calls.append(enum-0x38)
        elif at==0x60000020:
            dst=uc.reg_read(UC_X86_REG_RCX);cap=uc.reg_read(UC_X86_REG_RDX);src=uc.reg_read(UC_X86_REG_R8)
            value=cstr(uc,src)+b'\0';assert len(value)<=cap;uc.mem_write(dst,value);uc.reg_write(UC_X86_REG_RAX,0)
    u.hook_add(UC_HOOK_CODE,hook)
    u.emu_start(base+0x4cfb3,base+0x4d012,count=100000)
    assert u.reg_read(UC_X86_REG_RIP)==base+0x4d012
    payload=bytes(u.mem_read(0x40004000,u.reg_read(UC_X86_REG_RSI)-0x40004000))
    return payload,calls

def loader(base,climate,payload):
    u=engine(base);u.mem_write(0x40000148,bytes([climate]));u.mem_write(0x40000134,I(0xdeadbeef))
    u.mem_write(0x40005000,Q(base+0xffb58)+Q(0x1234));u.mem_write(0x4000600c,I(len(payload)))
    u.mem_write(base+0xea028,Q(0x60000030));u.mem_write(0x40007000,I(0))
    u.reg_write(UC_X86_REG_RSI,0x40000000);u.reg_write(UC_X86_REG_RDI,0x40005000);u.reg_write(UC_X86_REG_RBX,0x40006000)
    u.reg_write(UC_X86_REG_R15,0x40007000);u.reg_write(UC_X86_REG_R14,0)
    u.reg_write(UC_X86_REG_RBP,0x50010000);u.reg_write(UC_X86_REG_RSP,0x5000f000)
    def hook(uc,at,size,data):
        if at==0x60000010:
            p=uc.reg_read(UC_X86_REG_R8);enum=struct.unpack('<I',uc.mem_read(p,4))[0];assert 0x38<=enum<=0x44
            uc.mem_write(p+8,NAMES[enum-0x38]+b'\0');uc.reg_write(UC_X86_REG_RAX,1)
        elif at==0x60000030:
            assert uc.reg_read(UC_X86_REG_R8)==len(payload)
            uc.mem_write(uc.reg_read(UC_X86_REG_RDX),payload)
            uc.mem_write(uc.reg_read(UC_X86_REG_R9),I(len(payload)));uc.reg_write(UC_X86_REG_RAX,1)
    u.hook_add(UC_HOOK_CODE,hook)
    u.emu_start(base+0x4bdbc,base+0x4c258,count=100000)
    assert u.reg_read(UC_X86_REG_RIP)==base+0x4c258
    return struct.unpack('<I',u.mem_read(0x40000134,4))[0]

def main():
    cases=[]
    assert hashlib.sha256(W.data).hexdigest()=='ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9'
    for base in [0x180000000,0x280000000]:
        for climate in range(6):
            for mask in [0xf009,0xf04d,0xf6b9,0xf049,0x1ffff]+[0xf009|(1<<i) for i in range(13)]:
                payload,calls=writer(base,mask)
                expected=[i for i in range(13) if mask&(1<<i)]
                assert calls==expected and payload==b''.join(NAMES[i]+b'\0' for i in expected)
                after=loader(base,climate,payload)
                assert after&0x1fff==mask&0x1fff
                assert after==((mask&0x1fff)|(0xf009 if climate else 0))
                cases.append(dict(base=hex(base),climate=climate,before=hex(mask),after=hex(after),saved_indices=calls))
    result=dict(scope=__doc__,native_welt_sha256=hashlib.sha256(W.data).hexdigest(),native_game_sha256=hashlib.sha256(G.data).hexdigest(),
                cases=cases,roundtrips=len(cases),harvest_crop_mask='0x1fff',nonplant_flags_not_serialized_in_ANBAU=True,
                conclusions=['Native writer emits names only for set harvest crop bits0..12.','Native ANBAU loader preserves every enabled/disabled optional harvest crop bit; nonpolar baseline remains0xf009.','Fishing/nonplant bits outside0x1fff are not serialized by this field; polar loader baseline is0.'],passed=True,game_executed=False)
    (HERE/'native_crop_save_results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(passed=True,roundtrips=len(cases),harvest_crop_bits_exact=True),indent=2))
if __name__=='__main__':main()
