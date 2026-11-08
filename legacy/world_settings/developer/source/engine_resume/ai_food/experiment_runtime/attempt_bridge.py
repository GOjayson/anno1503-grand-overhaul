"""Future ordinary CALL wrapper for the entire native world-start lifetime."""
import struct
SITE=0x5746b
BEFORE=bytes.fromhex('e8a0e5ffff')
PROLOG=bytes.fromhex('53565741544155415641574881ec80000000')
EPILOG=bytes.fromhex('4881c480000000415f415e415d415c5f5e5bc3')
UNWIND=bytes([1,18,8,0,18,0xf2,11,0xf0,9,0xe0,7,0xd0,5,0xc0,3,0x70,2,0x60,1,0x30])
PARENT=(0x57060,0x57a51,0xbc090)
def build_attempt_code(rva=0):
 code=bytearray();names={};fix=[]
 def mark(name):names[name]=rva+len(code)
 def add(value):code.extend(bytes.fromhex(value) if isinstance(value,str) else value)
 def rel(prefix,target):
  add(prefix);at=len(code);add(bytes(4));fix.append((at,target))
 mark('native_attempt');add(PROLOG)
 add('488bd9488bf2498bf84d8be9') # original RCX/RDX/R8/R9 in RBX/RSI/RDI/R13
 rel('ff15','begin_attempt_iat');add('85c0');rel('0f84','reject')
 add('448be0') # R12D=nonzero attempt token
 add('488bcb488bd64c8bc74d8bcd');rel('e8',0x55a10)
 add('0fb6d04489e1');rel('ff15','end_attempt_iat') # EDX=original AL, ECX=token
 rel('e9','return')
 mark('reject');add('33c0')
 mark('return');add(EPILOG);mark('native_attempt_end')
 while len(code)%8:add('cc')
 mark('begin_attempt_iat');add(bytes(8));mark('end_attempt_iat');add(bytes(8))
 for at,target in fix:
  target=names[target] if isinstance(target,str) else target
  struct.pack_into('<i',code,at,target-(rva+at+4))
 return bytes(code),names,[(names['native_attempt'],names['native_attempt_end'],UNWIND)]
