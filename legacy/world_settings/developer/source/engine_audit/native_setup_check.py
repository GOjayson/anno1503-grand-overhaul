"""Run installed x64 native endless setup commit code under Unicorn.
This is an automated instruction check, not a Windows game run.
"""
import sys,struct,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'_tools'))
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE,UC_PROT_ALL
from unicorn.x86_const import *
ROOT=Path(__file__).resolve().parents[2]
BASE=0x180000000; STACK=0x40000000; OBJ=0x50000000; STOP=0x60000000
pe=pefile.PE(str(ROOT/'AnnoFrame.dll')); blob=pe.get_memory_mapped_image(); rows=[]
for disabled in [(),(0,),(6,),tuple(range(7)),(1,3,5)]:
 uc=Uc(UC_ARCH_X86,UC_MODE_64);uc.mem_map(BASE,(len(blob)+4095)&~4095,UC_PROT_ALL);uc.mem_write(BASE,blob)
 uc.mem_map(STACK,0x20000,UC_PROT_ALL);uc.mem_map(OBJ,0x10000,UC_PROT_ALL);uc.mem_map(STOP,0x1000,UC_PROT_ALL)
 uc.mem_write(STOP,b'\xc3');uc.reg_write(UC_X86_REG_RSP,STACK+0x10008);uc.mem_write(STACK+0x10008,struct.pack('<Q',STOP))
 vt=OBJ+0x8000;uc.mem_write(OBJ,struct.pack('<Q',vt));uc.mem_write(vt+0x188,struct.pack('<Q',STOP))
 source=bytes((x*31+9)&255 for x in range(0x498));uc.mem_write(OBJ+0x2288,source)
 flags=bytes(0 if i in disabled else 1 for i in range(7));uc.mem_write(OBJ+0x2280,flags)
 guard=b'GUARD-UNCHANGED!';uc.mem_write(OBJ+0x2288+0x498,guard);uc.mem_write(BASE+0xc75e0-16,guard);uc.mem_write(BASE+0xc75e0+0x498,guard)
 uc.reg_write(UC_X86_REG_RCX,OBJ)
 visits=[]
 def hook(uc,addr,size,_):
  if addr==STOP:uc.emu_stop()
  if addr==BASE+0x476f0:visits.append(uc.reg_read(UC_X86_REG_R9))
 uc.hook_add(UC_HOOK_CODE,hook)
 uc.emu_start(BASE+0x47d00,STOP+1,count=10000)
 expected=bytearray(source)
 for i in disabled:expected[i*0xa8+0x4c:i*0xa8+0x5c]=bytes(16)
 result=bytes(uc.mem_read(BASE+0xc75e0,0x498));assert result==expected,(disabled,[(i,a,b) for i,(a,b) in enumerate(zip(result,expected)) if a!=b][:5])
 assert visits==[0],visits # compiler unrolls all seven slots in one iteration
 assert bytes(uc.mem_read(OBJ+0x2288+0x498,16))==guard
 assert bytes(uc.mem_read(BASE+0xc75e0-16,16))==guard
 assert bytes(uc.mem_read(BASE+0xc75e0+0x498,16))==guard
 rows.append({'disabled_slots':disabled,'bytes_copied':len(result),'slot_count':len(flags),'guid_size':16,'passed':True})
print(json.dumps({'scope':'Native x64 instruction execution under Unicorn with final UI transition stub; not an actual game run','checks':rows},indent=2))

