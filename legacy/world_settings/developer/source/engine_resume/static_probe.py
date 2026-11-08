"""Read-only current History Edition PE analysis; output only in engine_resume."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'WorldSettings_Work'/'engine_audit'))
from audit import Module

def annotated_dis(module,start,end=None):
    m=Module(str(ROOT/module))
    imports={i.address:i.name.decode() if i.name else str(i.ordinal)
             for d in m.pe.DIRECTORY_ENTRY_IMPORT for i in d.imports}
    text=m.dis(start,end)
    lines=[]
    for line in text.splitlines():
        rva=int(line.split()[0],16)
        ins=next(m.cs.disasm(m.image[rva:rva+16],m.base+rva,count=1))
        names=[]
        for op in ins.operands:
            if op.type==3 and op.mem.base==41:
                target=ins.address+ins.size+op.mem.disp
                if target in imports:names.append(imports[target])
        lines.append(line+('  ; '+', '.join(names) if names else ''))
    return '\n'.join(lines)

if __name__=='__main__':
    module=sys.argv[1];start=int(sys.argv[2],0);end=int(sys.argv[3],0) if len(sys.argv)>3 else None
    print(annotated_dis(module,start,end))
