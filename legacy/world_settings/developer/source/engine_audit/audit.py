import sys,struct,re,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'_tools'))
import pefile,capstone
from capstone.x86_const import *
class Module:
 def __init__(self,name):
  self.name=name;self.data=Path(name).read_bytes();self.pe=pefile.PE(data=self.data);self.base=self.pe.OPTIONAL_HEADER.ImageBase;self.image=self.pe.get_memory_mapped_image();self.cs=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64);self.cs.detail=True;self.funcs=[(e.struct.BeginAddress,e.struct.EndAddress) for e in self.pe.DIRECTORY_ENTRY_EXCEPTION]
 def function(self,rva):
  return next(((a,b) for a,b in self.funcs if a<=rva<b),(rva,rva+0x100))
 def dis(self,a,b=None):
  a,b=self.function(a) if b is None else (a,b)
  return '\n'.join(f'{i.address-self.base:08x}  {i.bytes.hex():24} {i.mnemonic:7} {i.op_str}' for i in self.cs.disasm(self.image[a:b],self.base+a))
 def refs(self,target):
  out=[]
  for a,b in self.funcs:
   for i in self.cs.disasm(self.image[a:b],self.base+a):
    if any((o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP and i.address+i.size+o.mem.disp==self.base+target) or (o.type==X86_OP_IMM and o.imm==self.base+target) for o in i.operands):out.append((i.address-self.base,a,b,i.mnemonic+' '+i.op_str))
  return out
if __name__=='__main__':
 m=Module(sys.argv[1]);mode=sys.argv[2]
 if mode=='dis': print(m.dis(int(sys.argv[3],0),int(sys.argv[4],0) if len(sys.argv)>4 else None))
 elif mode=='refs':
  for t in sys.argv[3:]:print(hex(int(t,0)),m.refs(int(t,0)))
