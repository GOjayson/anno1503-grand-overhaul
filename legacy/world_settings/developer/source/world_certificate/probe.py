from pathlib import Path
import sys, struct, json
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'engine_audit'))
from audit import Module

def main():
 m=Module(sys.argv[1]);mode=sys.argv[2]
 if mode=='dis':
  start=int(sys.argv[3],0);end=int(sys.argv[4],0) if len(sys.argv)>4 else None
  print(m.dis(start,end))
 elif mode=='pointers':
  target=m.base+int(sys.argv[3],0);needle=struct.pack('<Q',target);at=0
  while (at:=m.image.find(needle,at))>=0:print(hex(at));at+=1
 elif mode=='table':
  start=int(sys.argv[3],0);end=int(sys.argv[4],0)
  for i in range(start,end,8):
   val=struct.unpack_from('<Q',m.image,i)[0]-m.base
   ins=list(m.cs.disasm(m.image[val:val+32],m.base+val))[:3] if 0<=val<len(m.image) else []
   print(hex(i-start),hex(i),hex(val),'; '.join(x.mnemonic+' '+x.op_str for x in ins))
 elif mode=='memrefs':
  from capstone.x86_const import X86_OP_MEM
  target=int(sys.argv[3],0)
  for a,b in ([(s.VirtualAddress,s.VirtualAddress+s.Misc_VirtualSize) for s in m.pe.sections if s.Characteristics&0x20000000] if len(sys.argv)>5 else m.funcs):
   hits=[i for i in m.cs.disasm(m.image[a:b],m.base+a) if any(o.type==X86_OP_MEM and o.mem.disp==target for o in i.operands)]
   if hits:print(hex(a),'; '.join(f'{i.address-m.base:x} {i.mnemonic} {i.op_str}' for i in hits))
 elif mode=='string':
  needle=sys.argv[3].encode();at=0
  while (at:=m.image.find(needle,at))>=0:
   print(hex(at),m.refs(at));at+=1
 elif mode=='bytes':
  needle=bytes.fromhex(sys.argv[3]);at=0
  while (at:=m.image.find(needle,at))>=0:print(hex(at));at+=1
 elif mode=='refrange':
  from capstone.x86_const import X86_OP_MEM,X86_REG_RIP
  lo=int(sys.argv[3],0);hi=int(sys.argv[4],0)
  for a,b in ([(s.VirtualAddress,s.VirtualAddress+s.Misc_VirtualSize) for s in m.pe.sections if s.Characteristics&0x20000000] if len(sys.argv)>5 else m.funcs):
   for i in m.cs.disasm(m.image[a:b],m.base+a):
    for o in i.operands:
     if o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP and lo<=i.address+i.size+o.mem.disp-m.base<hi:print(hex(a),hex(i.address-m.base),i.mnemonic,i.op_str,'target',hex(i.address+i.size+o.mem.disp-m.base))
if __name__=='__main__':main()
