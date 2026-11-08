"""Read-only instruction inventory for the local AMD64 History Edition DLLs."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'WorldSettings_Work/_tools'))
import pefile,capstone
from capstone.x86_const import *

def inventory(name):
    raw=(ROOT/name).read_bytes(); pe=pefile.PE(data=raw)
    assert pe.FILE_HEADER.Machine==0x8664 and pe.OPTIONAL_HEADER.Magic==0x20b
    base=pe.OPTIONAL_HEADER.ImageBase; image=pe.get_memory_mapped_image()
    cs=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64);cs.detail=True
    funcs=[]
    for e in pe.DIRECTORY_ENTRY_EXCEPTION:
        a,b=e.struct.BeginAddress,e.struct.EndAddress
        instructions=[]
        for i in cs.disasm(image[a:b],base+a):
            instructions.append(dict(rva=i.address-base,bytes=i.bytes.hex(),mnemonic=i.mnemonic,op=i.op_str,
                fields=[o.mem.disp for o in i.operands if o.type==X86_OP_MEM and o.mem.base!=X86_REG_RIP],
                target=[o.imm-base for o in i.operands if o.type==X86_OP_IMM and base<=o.imm<base+len(image)]))
        funcs.append(dict(start=a,end=b,instructions=instructions))
    return dict(name=name,sha256=hashlib.sha256(raw).hexdigest(),machine='AMD64',magic='PE32+',functions=funcs)

if __name__=='__main__':
    for name in ['CompLogic.dll','CompLogicClassic.dll','AnnoWelt.dll','AnnoScene.dll']:
        p=Path(__file__).with_name(name+'.instructions.json')
        if not p.exists():p.write_text(json.dumps(inventory(name),indent=1)+'\n','utf-8')
        data=json.loads(p.read_text('utf-8'));print(name,data['sha256'])
        fields=[int(a,0) for a in sys.argv[1:]] or [0xa6c,0xa9c]
        for f in data['functions']:
            selected=[i for i in f['instructions'] if any(n in fields for n in i['fields'])]
            if selected:print(hex(f['start']),hex(f['end']),[(hex(i['rva']),i['mnemonic']+' '+i['op']) for i in selected])
