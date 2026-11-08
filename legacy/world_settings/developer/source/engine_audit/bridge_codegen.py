"""AMD64 single-player flag-selection bridge. No live game is modified.
The observed endless flag is page+2260, native Customize child [page+21b0][0].
Every native castle flag callback binds44bb0; other start routes unverified.
"""
import struct
PROLOG=bytes.fromhex('53565741544155415641574881ec80000000')
EPILOG=bytes.fromhex('4881c480000000415f415e415d415c5f5e5bc3')
COMMON_UNWIND=bytes([1,18,8,0,18,0xf2,11,0xf0,9,0xe0,7,0xd0,5,0xc0,3,0x70,2,0x60,1,0x30])
LEAF_UNWIND=bytes([1,0,0,0])
START_RVA=0x44bb0
ORIGINAL_START=bytes.fromhex('488b01881587040800')
LOADLIBRARY_IAT_RVA=0x9e408
GETPROCADDRESS_IAT_RVA=0x9e410

def build_bridge(rva,dll_path='AnnoWorldSettings.dll',export='WorldSettingsBeforeStart'):
 code=bytearray();names={};fix=[]
 def mark(n):names[n]=rva+len(code)
 def add(b):code.extend(bytes.fromhex(b) if isinstance(b,str) else b)
 def rel(prefix,target):
  add(prefix);at=len(code);add(bytes(4));fix.append((at,target))
 mark('worldsettings_start');add(PROLOG);mark('worldsettings_start_prolog_end')
 add('488bd9488bf2') # rbx=flag page, rsi=original flag argument
 add('80bb6022000000');rel('0f84','native_flag')
 add('488b83b02100004885c0');rel('0f84','cancel')
 add('488b384885ff');rel('0f84','cancel') # rdi=customization object
 rel('488d0d','dll_path');rel('ff15',LOADLIBRARY_IAT_RVA)
 add('4885c0');rel('0f84','cancel')
 add('488bc8');rel('488d15','export_name');rel('ff15',GETPROCADDRESS_IAT_RVA)
 add('4885c0');rel('0f84','cancel')
 add('488bcf');rel('488d15',0);add('ffd085c0');rel('0f8e','cancel')
 add('488bcf');rel('e8',0x476e0) # native commit, only after accepted world
 mark('native_flag');add('488bcb488bd6');rel('e8','original_flag_trampoline');rel('e9','done')
 mark('cancel');add('33c0');mark('done');add(EPILOG);mark('worldsettings_start_end')
 while len(code)%16:add('cc')
 mark('original_flag_trampoline');add('488b01');rel('8815',0xc5040);rel('e9',START_RVA+len(ORIGINAL_START));mark('original_flag_trampoline_end')
 mark('dll_path');add(dll_path.encode('ascii')+b'\0');mark('export_name');add(export.encode('ascii')+b'\0')
 for at,target in fix:
  dest=names[target] if isinstance(target,str) else target
  struct.pack_into('<i',code,at,dest-(rva+at+4))
 hooks=[(START_RVA,ORIGINAL_START,b'\xe9'+struct.pack('<i',names['worldsettings_start']-(START_RVA+5))+b'\x90'*4)]
 functions=[(names['worldsettings_start'],names['worldsettings_start_end'],COMMON_UNWIND),(names['original_flag_trampoline'],names['original_flag_trampoline_end'],LEAF_UNWIND)]
 return bytes(code),names,hooks,functions
