"""Merchant-only staging and exact HE instruction fixtures.

Synthetic native graphs and optional instruction emulation do not establish
merchant navigation, visit timing, trade volume or game presentation.
"""
import sys
sys.dont_write_bytecode = True
import ctypes as C
import hashlib
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'.local/toolchain/world-options-validation')]
NATIVE=ROOT/'src/anno1503_overhaul/native/world_options'
FAMILIES={
 'CompLogic.dll':dict(sha='a8218ef1a1ba9cbe929f2c32430ebd5647e750e2df2af6733808d7314a80c483',
  vtable=0x883c0,setter=0x6090,getter=0x6640,load=0x72180,entry=0x72c91,compare=0x72cd0,
  spawn=0x72cfd,finish=0x72d07,table=0x730c8,ship=0x71540,allocation=0x7158c),
 'CompLogicClassic.dll':dict(sha='d005f6505b41a4648d9cc75573cdebf74174f89c2091fcf32a8e019c20246b2e',
  vtable=0x85258,setter=0x4260,getter=0x4a10,load=0x6f110,entry=0x6fc21,compare=0x6fc60,
  spawn=0x6fc8d,finish=0x6fc97,table=0x70058,ship=0x6e4d0,allocation=0x6e51c),
}

STAGING=r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef struct WSFactionActivityTarget {unsigned char*controller;uint32_t before,after;} WSFactionActivityTarget;
static unsigned char controller[32];static uint32_t flags,foundType,foundEnabled;static int failFind;
static int wsAIError(char*out,uint32_t cap,const char*message){if(out&&cap)snprintf(out,cap,"%s",message);return 0;}
static int wsFactionActivityFind(void*world,void*approved,uint32_t type,uint32_t enabled,WSFactionActivityTarget*out,char*error,uint32_t cap){
 (void)world;(void)approved;foundType=type;foundEnabled=enabled;if(failFind)return wsAIError(error,cap,"identity refused");
 out->controller=enabled?controller:NULL;out->before=enabled?flags:0;out->after=out->before;return 1;
}
#include "merchant_activity.inc"
#ifdef _WIN32
#define API __declspec(dllexport)
#else
#define API __attribute__((visibility("default")))
#endif
API int propose(uint32_t factions,int32_t mode,uint32_t before,int refuse,uint32_t*out){
 WSFactionActivityTarget target;memset(&target,0xa5,sizeof target);flags=before;failFind=refuse;foundType=foundEnabled=0;
 unsigned char old[32];memcpy(old,controller,sizeof old);int ok=wsFactionActivityMerchantTarget((void*)1,(void*)2,factions,mode,&target,NULL,0);
 if(memcmp(old,controller,sizeof old))return -1;
 out[0]=ok?target.before:0;out[1]=ok?target.after:0;out[2]=ok&&target.controller;out[3]=foundType;out[4]=foundEnabled;return ok;
}
'''

class MerchantStaging(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  if os.name=='nt':
   compiler=ROOT/'.local/toolchain/ziglang/zig.exe'
   if not compiler.is_file():raise unittest.SkipTest('Pinned Zig toolchain unavailable.')
   command=[str(compiler),'cc','-target','x86_64-windows-gnu'];suffix='.dll';extra=[]
  else:
   compiler=shutil.which('cc') or shutil.which('clang') or shutil.which('gcc')
   if not compiler:raise unittest.SkipTest('A native C compiler is unavailable.')
   command=[compiler];suffix='.so';extra=['-fPIC']
  cls.tmp=tempfile.TemporaryDirectory(prefix='anno-merchant-staging-');folder=Path(cls.tmp.name)
  source=folder/'fixture.c';source.write_text(STAGING,encoding='utf-8')
  result=subprocess.run(command+['-shared','-O2','-Wall','-Wextra','-Werror',*extra,'-I',str(NATIVE),str(source),'-o',str(folder/('fixture'+suffix))],capture_output=True,text=True)
  if result.returncode:raise AssertionError(result.stdout+result.stderr)
  cls.lib=C.CDLL(str(folder/('fixture'+suffix)));cls.lib.propose.argtypes=[C.c_uint32,C.c_int32,C.c_uint32,C.c_int,C.POINTER(C.c_uint32)];cls.lib.propose.restype=C.c_int

 @classmethod
 def tearDownClass(cls):
  if os.name=='nt':
   import _ctypes
   _ctypes.FreeLibrary(cls.lib._handle)
  cls.tmp.cleanup()

 def test_stages_all_modes_and_low_native_flags_without_writes(self):
  for mode in range(3):
   for flags in (0,4,8,0x7f,0xff):
    with self.subTest(mode=mode,flags=flags):
     out=(C.c_uint32*5)();self.assertEqual(self.lib.propose(2,mode,flags,0,out),1)
     self.assertEqual(list(out),[flags,0x57550000|(mode<<8)|flags,1,16,1])

 def test_disabled_faction_and_refusals_leave_no_policy_row(self):
  for factions in (0,1):
   out=(C.c_uint32*5)();self.assertEqual(self.lib.propose(factions,2,0xff,0,out),1)
   self.assertEqual(list(out),[0,0,0,16,0])
  for factions,mode,flags,refuse in ((4,1,0,0),(2,-1,0,0),(2,3,0,0),(2,1,0x100,0),
                                   (2,1,0x57550100,0),(2,1,0xffffffff,0),(2,1,0,1)):
   with self.subTest(factions=factions,mode=mode,flags=flags,refuse=refuse):
    out=(C.c_uint32*5)();self.assertEqual(self.lib.propose(factions,mode,flags,refuse,out),0)
    self.assertEqual(list(out)[:3],[0,0,0])


class NativeMerchantInstructions(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  try:
   import pefile
   import unicorn as U
   from unicorn import x86_const as X
  except ImportError:raise unittest.SkipTest('Native instruction fixtures require optional PE and Unicorn tooling.')
  cls.U,cls.X=U,X;cls.images={}
  for name,fields in FAMILIES.items():
   path=ROOT/'.local/game-copies/World Settings'/name
   if not path.is_file():raise unittest.SkipTest('Exact local HE AMD64 native input copies are unavailable.')
   raw=path.read_bytes()
   if hashlib.sha256(raw).hexdigest()!=fields['sha']:raise AssertionError('Exact native input differs: '+name)
   pe=pefile.PE(data=raw);cls.images[name]=(pe,pe.get_memory_mapped_image())

 def machine(self,name,base):
  U,X=self.U,self.X;pe,image=self.images[name];cpu=U.Uc(U.UC_ARCH_X86,U.UC_MODE_64)
  cpu.mem_map(base,(len(image)+4095)&~4095);cpu.mem_write(base,image)
  for address,size in ((0x31000000,0x20000),(0x32000000,0x40000),(0x33000000,0x10000)):cpu.mem_map(address,size)
  # Supply only the stack-limit field consumed by the real Win64 stack probe.
  cpu.reg_write(X.UC_X86_REG_GS_BASE,0x33008000);cpu.mem_write(0x33008010,struct.pack('<Q',0x31000000))
  return cpu

 def call(self,cpu,entry,rcx=0,rdx=0,r8=0,r9=0):
  X=self.X;rsp=0x31010008;stop=0x3300f000;cpu.mem_write(rsp,struct.pack('<Q',stop))
  for reg,value in ((X.UC_X86_REG_RSP,rsp),(X.UC_X86_REG_RCX,rcx),(X.UC_X86_REG_RDX,rdx),(X.UC_X86_REG_R8,r8),(X.UC_X86_REG_R9,r9)):cpu.reg_write(reg,value)
  cpu.emu_start(entry,stop,count=100000);self.assertEqual(cpu.reg_read(X.UC_X86_REG_RIP),stop)
  return cpu.reg_read(X.UC_X86_REG_RAX)&0xffffffff

 def test_native_population_target_mapping_and_definition1507_spawn(self):
  X=self.X
  for name,f in FAMILIES.items():
   pe,image=self.images[name]
   self.assertEqual(image[f['compare']:f['compare']+9],bytes.fromhex('4439b6880c00007d2e'))
   self.assertEqual(image[f['compare']-6:f['compare']],bytes.fromhex('41be05000000'))
   for base in (0x180000000,0x280000000):
    cpu=self.machine(name,base);events=[]
    def hook(machine,address,size,data):
     if address==base+f['spawn']:
      rsp=machine.reg_read(X.UC_X86_REG_RSP)
      events.append((machine.reg_read(X.UC_X86_REG_RCX),machine.reg_read(X.UC_X86_REG_RDX),machine.reg_read(X.UC_X86_REG_R8),machine.reg_read(X.UC_X86_REG_R9),struct.unpack('<II',machine.mem_read(rsp+0x20,4)+machine.mem_read(rsp+0x28,4))))
      machine.emu_stop()
    cpu.hook_add(self.U.UC_HOOK_CODE,hook)
    for census in range(13):
     target=0 if not census else 1 if census<=2 else 2 if census<=5 else 3 if census<=8 else 4 if census<=10 else 5
     for ships in range(12):
      with self.subTest(name=name,base=base,census=census,ships=ships):
       events.clear();cpu.mem_write(0x32000c88,struct.pack('<I',ships));cpu.mem_write(0x32000a64,struct.pack('<H',5))
       for reg,value in ((X.UC_X86_REG_RSP,0x31010000),(X.UC_X86_REG_RSI,0x32000000),(X.UC_X86_REG_RBX,census),(X.UC_X86_REG_R14,2)):cpu.reg_write(reg,value)
       cpu.emu_start(base+f['entry'],base+f['finish'],count=200)
       self.assertEqual(bool(events),bool(census and ships<target))
       if census:self.assertEqual(cpu.reg_read(X.UC_X86_REG_R14),target)
       if events:self.assertEqual(events,[(0x32000008,8,8,5,(1507,24))])

 def test_native_merchant_ship_adapter_refuses_a_forty_first_ship(self):
  X=self.X
  for name,f in FAMILIES.items():
   cpu=self.machine(name,0x180000000)
   cpu.mem_write(0x32000b40,b''.join(struct.pack('<Q',0x32010000+i*16) for i in range(40)))
   self.assertEqual(self.call(cpu,0x180000000+f['ship'],0x32000000,999),0)
   self.assertEqual(struct.unpack('<I',cpu.mem_read(0x32000c88,4))[0],0)

 def test_emitted_merchant_gate_preserves_live_state_and_exact_comparison(self):
  from anno1503_overhaul.world_options_factions import _merchant_code,SPEC
  X=self.X
  registers=(X.UC_X86_REG_RAX,X.UC_X86_REG_RBX,X.UC_X86_REG_RCX,X.UC_X86_REG_RDX,
             X.UC_X86_REG_RSI,X.UC_X86_REG_RDI,X.UC_X86_REG_RBP,X.UC_X86_REG_RSP,
             X.UC_X86_REG_R8,X.UC_X86_REG_R9,X.UC_X86_REG_R10,X.UC_X86_REG_R11,
             X.UC_X86_REG_R12,X.UC_X86_REG_R13,X.UC_X86_REG_R14,X.UC_X86_REG_R15)
  xmms=[getattr(X,'UC_X86_REG_XMM'+str(index)) for index in range(16)]
  for name,f in FAMILIES.items():
   for base in (0x180000000,0x280000000):
    cpu=self.machine(name,base);gate=base+0x200000;code=_merchant_code(0x200000,SPEC[name]);cpu.mem_map(gate,0x1000);cpu.mem_write(gate,code)
    writes=[];cpu.hook_add(self.U.UC_HOOK_MEM_WRITE,lambda m,a,address,size,value,data:writes.append((address,size)))
    for target in range(1,6):
     for mode in range(3):
      for count in (0,1,2,3,4,5,6,9,10,40):
       with self.subTest(name=name,base=base,target=target,mode=mode,count=count):
        values={reg:0x112233440000+index*0x100 for index,reg in enumerate(registers)}
        values.update({X.UC_X86_REG_RSI:0x32000000,X.UC_X86_REG_RSP:0x31010000,X.UC_X86_REG_R14:target})
        for reg,value in values.items():cpu.reg_write(reg,value)
        for index,reg in enumerate(xmms):cpu.reg_write(reg,0x102030405060708090a0b0c0d0e0f000+index)
        cpu.mem_write(0x32000000,struct.pack('<Q',base+f['vtable']));cpu.mem_write(0x32000a4c,struct.pack('<I',16))
        cpu.mem_write(0x32000ab8,struct.pack('<I',0x57550000|(mode<<8)|0xff));cpu.mem_write(0x32000c88,struct.pack('<I',count))
        cpu.mem_write(0x3100ff00,b'\xa5'*0x300);stack=bytes(cpu.mem_read(0x3100ff00,0x300));writes.clear()
        scaled=(target+1)//2 if mode==0 else target if mode==1 else target*2
        # The original instruction establishes the exact arithmetic flags oracle.
        cpu.reg_write(X.UC_X86_REG_R14,scaled);cpu.reg_write(X.UC_X86_REG_EFLAGS,0x202)
        cpu.emu_start(base+f['compare'],base+f['compare']+7,count=1);wanted=cpu.reg_read(X.UC_X86_REG_EFLAGS)
        cpu.reg_write(X.UC_X86_REG_R14,target);cpu.reg_write(X.UC_X86_REG_EFLAGS,0x202)
        cpu.emu_start(gate,base+f['compare']+7,count=100)
        self.assertEqual(cpu.reg_read(X.UC_X86_REG_EFLAGS),wanted)
        for reg,value in values.items():
         if reg not in (X.UC_X86_REG_R10,X.UC_X86_REG_R11):self.assertEqual(cpu.reg_read(reg),value)
        for index,reg in enumerate(xmms):self.assertEqual(cpu.reg_read(reg),0x102030405060708090a0b0c0d0e0f000+index)
        self.assertEqual(bytes(cpu.mem_read(0x3100ff00,0x300)),stack);self.assertEqual(writes,[])

 def test_merchant_gate_refuses_malformed_tags_and_preserves_native_fallbacks(self):
  from anno1503_overhaul.world_options_factions import _merchant_code,SPEC
  X=self.X
  for name,f in FAMILIES.items():
   base=0x180000000;cpu=self.machine(name,base);gate=base+0x200000;cpu.mem_map(gate,0x1000);cpu.mem_write(gate,_merchant_code(0x200000,SPEC[name]))
   for vt,cpu_type,flags,target,count,deny in (
       (f['vtable'],16,0x57550300,3,0,True),(f['vtable'],16,0x57550400,3,0xffffffff,True),
       (f['vtable'],16,0x5755fc00,3,0,True),(f['vtable'],16,0,3,2,False),
       (f['vtable'],16,0x57530200,3,2,False),(f['vtable'],12,0x57550200,3,2,False),
       (f['vtable']+8,16,0x57550200,3,2,False),(f['vtable'],16,0x57550200,0,0,False),
       (f['vtable'],16,0x57550200,6,5,False)):
    with self.subTest(name=name,vt=vt,cpu_type=cpu_type,flags=hex(flags),target=target,count=count):
     cpu.mem_write(0x32000000,struct.pack('<Q',base+vt));cpu.mem_write(0x32000a4c,struct.pack('<I',cpu_type));cpu.mem_write(0x32000ab8,struct.pack('<I',flags));cpu.mem_write(0x32000c88,struct.pack('<I',count))
     for reg,value in ((X.UC_X86_REG_RSI,0x32000000),(X.UC_X86_REG_R14,target),(X.UC_X86_REG_RSP,0x31010000),(X.UC_X86_REG_EFLAGS,0x202)):cpu.reg_write(reg,value)
     cpu.emu_start(base+f['compare'],base+f['compare']+7,count=1);native=cpu.reg_read(X.UC_X86_REG_EFLAGS);cpu.reg_write(X.UC_X86_REG_EFLAGS,0x202)
     cpu.emu_start(gate,base+f['compare']+7,count=100);actual=cpu.reg_read(X.UC_X86_REG_EFLAGS)
     if deny:self.assertEqual((actual>>7)&1,(actual>>11)&1) # original JGE must skip spawn, even for negative count
     else:self.assertEqual(actual,native)

 def test_gate_scratch_registers_are_dead_in_both_complete_native_suffixes(self):
  try:
   import capstone
   from capstone import x86_const as K
  except ImportError:self.skipTest('Native register liveness proof needs Capstone.')
  registers={K.X86_REG_R10,K.X86_REG_R10D,K.X86_REG_R10W,K.X86_REG_R10B,K.X86_REG_R11,K.X86_REG_R11D,K.X86_REG_R11W,K.X86_REG_R11B}
  decoder=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64);decoder.detail=True
  for name,f in FAMILIES.items():
   image=self.images[name][1];start=f['compare']+7;end=f['table']-1
   instructions=list(decoder.disasm(image[start:end],start));self.assertEqual(sum(x.size for x in instructions),1008)
   self.assertEqual(end-start,1008);self.assertEqual(instructions[-1].mnemonic,'ret')
   for instruction in instructions:
    read,written=instruction.regs_access();self.assertFalse(registers.intersection(read)|registers.intersection(written))

 def native_comp_roundtrip(self,cpu_type,policies):
  """Execute the actual class load override; mock only stream/CRT services.

  Corrupt high words must survive native transport for the separate read-only
  load validator to refuse. This is parser evidence, not a whole-game save.
  """
  U,X=self.U,self.X
  for name,f in FAMILIES.items():
   pe,image=self.images[name]
   vtable=f['vtable'] if cpu_type==16 else (0x88ba8 if name=='CompLogic.dll' else 0x85aa0)
   load=struct.unpack_from('<Q',image,vtable+0x30)[0]-pe.OPTIONAL_HEADER.ImageBase
   self.assertEqual(load,f['load'] if cpu_type==16 else (0x7a9f0 if name=='CompLogic.dll' else 0x77830))
   for base in (0x180000000,0x280000000):
    cpu=self.machine(name,base);imports={};payload=[b''];stream=0x32010000;buffer=0x32014000;ctrl=0x32000000
    cpu.mem_write(ctrl,struct.pack('<Q',base+vtable));cpu.mem_write(ctrl+0xa4c,struct.pack('<I',cpu_type))
    cpu.mem_write(base+vtable+8,struct.pack('<Q',base+f['setter']));cpu.mem_write(base+vtable+0x10,struct.pack('<Q',base+f['getter']))
    cpu.mem_write(stream,struct.pack('<Q',stream+0x100));cpu.mem_write(stream+0x108,struct.pack('<Q',0x33000000))
    def string(address,limit=4096):
     data=bytes(cpu.mem_read(address,limit));return data.split(b'\0',1)[0]
    wanted={'strchr','strrchr','strncmp','atoi'}
    for descriptor in pe.DIRECTORY_ENTRY_IMPORT:
     for entry in descriptor.imports:
      if entry.name and entry.name.decode() in wanted:
       address=0x33000010+len(imports)*16;imports[address]=entry.name.decode();cpu.mem_write(address,b'\xc3')
       cpu.mem_write(base+entry.address-pe.OPTIONAL_HEADER.ImageBase,struct.pack('<Q',address))
    self.assertEqual(set(imports.values()),wanted);cpu.mem_write(0x33000000,b'\xc3')
    def external(machine,address,size,data):
     if address!=0x33000000 and address not in imports:return
     rcx=machine.reg_read(X.UC_X86_REG_RCX);rdx=machine.reg_read(X.UC_X86_REG_RDX);r8=machine.reg_read(X.UC_X86_REG_R8)
     if address==0x33000000:
      self.assertEqual(rcx,stream);self.assertEqual(r8,len(payload[0]));machine.mem_write(rdx,payload[0]);result=1
     elif imports[address] in ('strchr','strrchr'):
      value=string(rcx);needle=bytes([rdx&255]);at=value.rfind(needle) if imports[address]=='strrchr' else value.find(needle)
      result=0 if at<0 else rcx+at
     elif imports[address]=='strncmp':
      left,right=bytes(machine.mem_read(rcx,r8)),bytes(machine.mem_read(rdx,r8));result=(left>right)-(left<right)
     else:result=int(string(rcx).decode('ascii'))
     machine.reg_write(X.UC_X86_REG_RAX,result&0xffffffffffffffff)
    cpu.hook_add(U.UC_HOOK_CODE,external)
    for flags in policies:
     with self.subTest(name=name,base=base,cpu_type=cpu_type,flags=hex(flags)):
      payload[0]=('SPEZFLAG='+str(flags)).encode()+b'\0'
      cpu.mem_write(ctrl+0xab8,bytes(4));self.assertEqual(self.call(cpu,base+load,ctrl,stream,len(payload[0])),1)
      self.assertEqual(struct.unpack('<I',cpu.mem_read(ctrl+0xab8,4))[0],flags)
      cpu.mem_write(buffer,bytes(32));self.assertEqual(self.call(cpu,base+f['getter'],ctrl,29,buffer),1)
      self.assertEqual(struct.unpack('<I',cpu.mem_read(buffer+0x18,4))[0],flags)

 def test_exact_native_merchant_comp_text_load_roundtrips_full_policy_flags(self):
  self.native_comp_roundtrip(16,[0x57550000|(mode<<8)|low for mode in range(3) for low in (0,4,8,0xff)]+
                            [0,0xff,0x57550300,0x57550400,0x5755fc00,0x57540200])

 def test_exact_native_pirate_comp_text_load_transports_policy_and_invalid_words(self):
  self.native_comp_roundtrip(15,[0x57540000|(mode<<8)|(strength<<10)|low
                             for mode in range(3) for strength in range(3) for low in (0,4,8,0xff)]+
                            [0,0xff,0x57540300,0x57540c00,0x57541000,0x57550200])


if __name__=='__main__':unittest.main()
