"""Generate an ordinary call wrapper for native profile application.

Runs after native55330 has applied profile/suspension choices. The original
55a10 boolean failure return and caller cleanup are retained on rejection.
"""
import struct
SITE=0x55f2e
BEFORE=bytes.fromhex('e8fdf3ffff')
PARENT=(0x55a10,0x56b70,0xbbfc0)
PROLOG=bytes.fromhex('53565741544155415641574881ec80000000')
RESTORE=bytes.fromhex('4881c480000000415f415e415d415c5f5e5bc3')
# A genuine CALL gives an ordinary frame. Do not use CHAININFO around an
# added stack frame: parent SAVE_NONVOL/XMM offsets use its own frame base.
UNWIND=bytes([1,18,8,0,18,0xf2,11,0xf0,9,0xe0,7,0xd0,5,0xc0,3,0x70,2,0x60,1,0x30])
def build_postprofile_code(rva=0):
 code=bytearray();names={};fix=[]
 def mark(name):names[name]=rva+len(code)
 def add(b):code.extend(bytes.fromhex(b) if isinstance(b,str) else b)
 def rel(prefix,target):
  add(prefix);at=len(code);add(bytes(4));fix.append((at,target))
 mark('postprofile');add(PROLOG);mark('prolog_end')
 add('488bda');rel('e8',0x55330) # retain original World RDX; same native args
 add('488bcb');rel('ff15','after_profiles_iat')
 add('83f801');rel('0f84','return')
 # Native55a10 ignores the profile-call result. On rejection use its exact
 # boolean failure exit as our return continuation, before restoring our
 # own ordinary stack. The native caller still owns normal cleanup.
 rel('488d05',0x56b30);add('48898424b8000000')
 mark('return');add(RESTORE)
 mark('postprofile_end')
 while len(code)%8:add('cc')
 mark('after_profiles_iat');add(bytes(8))
 for at,target in fix:
  dest=names[target] if isinstance(target,str) else target
  struct.pack_into('<i',code,at,dest-(rva+at+4))
 return bytes(code),names,[(names['postprofile'],names['postprofile_end'],UNWIND)]
