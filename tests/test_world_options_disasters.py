"""HE scheduler gates and independently authenticated disaster checkpoints.

Native instruction emulation and Windows file/unwind fixtures do not establish
actual presentation, long-session disaster rates or live economic outcomes.
"""
import sys
sys.dont_write_bytecode=True
import ctypes as C
import hashlib
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'.local/toolchain/world-options-validation')]
from anno1503_overhaul import world_options_disasters as d
from anno1503_overhaul.world_options import PRIVATE,authored
from anno1503_overhaul.world_runtime_build import STOCK_SHA256,RuntimeBuildError

NATIVE=ROOT/'src/anno1503_overhaul/native/world_options'


class DisasterPreimages(unittest.TestCase):
 def test_exact_native_sites_and_unknown_image_refusals(self):
  name='AnnoWelt.dll';path=ROOT/'.local/game-copies/World Settings'/name
  if not path.is_file():raise unittest.SkipTest('Exact private HE module unavailable.')
  raw=path.read_bytes();proof=d.verify_disaster_preimages({name:raw},STOCK_SHA256)
  self.assertEqual(proof['hook_count'],8)
  self.assertEqual(len({row['callback']for row in proof['hooks']}),7)
  for value,pin in ((raw[:-1]+bytes([raw[-1]^1]),STOCK_SHA256),(raw,{name:'0'*64})):
   with self.assertRaises(RuntimeBuildError):d.verify_disaster_preimages({name:value},pin)
  with self.assertRaises(RuntimeBuildError):d.disaster_bridge(0)


@unittest.skipUnless(os.name=='nt','Windows native fixtures require the Win64 ABI.')
class DisasterMath(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  zig=ROOT/'.local/toolchain/ziglang/zig.exe'
  if not zig.is_file():raise unittest.SkipTest('Pinned native compiler unavailable.')
  cls.tmp=tempfile.TemporaryDirectory(prefix='anno-disaster-math-');folder=Path(cls.tmp.name)
  source=r'''
#include <stdint.h>
#include "disaster_policy.h"
__declspec(dllexport) uint32_t valid(uint32_t a,uint32_t b,uint32_t c,uint32_t d){return wsDisasterOptionsValid(a,b,c,d);}
__declspec(dllexport) uint32_t nativeFlags(uint32_t a,uint32_t b){return wsDisasterDisabledNative(a,b);}
__declspec(dllexport) uint32_t chance(uint32_t a,uint32_t b,uint32_t c){return wsDisasterChance(a,b,c);}
__declspec(dllexport) uint32_t interval(uint32_t a,uint32_t b){return wsDisasterInterval(a,b);}
'''
  (folder/'fixture.c').write_text(source,encoding='utf-8')
  result=subprocess.run([str(zig),'cc','-target','x86_64-windows-gnu','-shared','-O2','-Wall','-Wextra','-Werror','-I',str(NATIVE),str(folder/'fixture.c'),'-o',str(folder/'fixture.dll')],capture_output=True,text=True)
  if result.returncode:raise AssertionError(result.stdout+result.stderr)
  cls.lib=C.CDLL(str(folder/'fixture.dll'))
  cls.lib.valid.argtypes=[C.c_uint32]*4
  cls.lib.nativeFlags.argtypes=[C.c_uint32]*2
  cls.lib.chance.argtypes=[C.c_uint32]*3
  cls.lib.interval.argtypes=[C.c_uint32]*2
  for name in ('valid','nativeFlags','chance','interval'):getattr(cls.lib,name).restype=C.c_uint32
 @classmethod
 def tearDownClass(cls):
  import _ctypes
  _ctypes.FreeLibrary(cls.lib._handle);cls.tmp.cleanup()
 def test_all_masks_have_independent_native_enablement_and_bounded_schema(self):
  for master in range(2):
   for mask in range(32):
    self.assertEqual(self.lib.valid(master,mask,341,341),1)
    active=mask if master else 0
    expected=(0 if active&3 else 8)|(0 if active&4 else 2)|(0 if active&8 else 128)|(0 if active&16 else 4)
    self.assertEqual(self.lib.nativeFlags(master,mask),expected)
  for values in ((2,31,341,341),(1,32,341,341),(1,31,1024,341),(1,31,341,1024),
                 (1,31,3,341),(1,31,341,340),(1,31,341,337)):
   with self.subTest(values=values):self.assertEqual(self.lib.valid(*values),0)
  for i in range(5):
   for mode in range(3):
    value=(341&~(3<<(i*2)))|(mode<<(i*2))
    self.assertEqual(self.lib.valid(1,31,value,341),1)
    self.assertEqual(self.lib.valid(1,31,341,value),int(i>=2 or mode==1))
 def test_normal_random_is_exact_and_frequency_changes_native_chance_monotonically(self):
  for denominator in (31,63,95,127,159,191,223):
   counts=[0,0,0]
   for random in range(65536):
    normal=self.lib.chance(random,denominator,1);self.assertEqual(normal,random)
    for mode in range(3):counts[mode]+=self.lib.chance(random,denominator,mode)%denominator<=3
   self.assertLess(counts[0],counts[1]);self.assertLess(counts[1],counts[2])
  for normal in (300,450000,9900000,9965535):
   self.assertEqual([self.lib.interval(normal,m)for m in range(3)],[normal*2,normal,normal//2])


@unittest.skipUnless(os.name=='nt','Actual Windows RtlVirtualUnwind is required.')
class DisasterBridges(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  try:
   import capstone
   import unicorn as U
   from unicorn import x86_const as X
  except ImportError as exc:raise unittest.SkipTest('Native instruction tools unavailable.')from exc
  cls.cs=capstone;cls.U=U;cls.X=X
  class Function(C.Structure):_fields_=[('begin',C.c_uint32),('end',C.c_uint32),('unwind',C.c_uint32)]
  cls.Function=Function;cls.virtual=C.WinDLL('ntdll').RtlVirtualUnwind
  cls.virtual.argtypes=[C.c_uint32,C.c_uint64,C.c_uint64,C.POINTER(Function),C.c_void_p,C.POINTER(C.c_void_p),C.POINTER(C.c_uint64),C.c_void_p]
 def test_every_bridge_instruction_unwinds_actual_stack_and_preserves_native_arguments(self):
  X,U,cs=self.X,self.U,self.cs;decoder=cs.Cs(cs.CS_ARCH_X86,cs.CS_MODE_64)
  register_names=('RAX','RCX','RDX','RBX','RSP','RBP','RSI','RDI','R8','R9','R10','R11','R12','R13','R14','R15')
  context_offsets=dict(zip(register_names,range(120,248,8)))
  # Keep both separately allocated image buffers alive for distinct ASLR bases.
  image_buffers=[C.create_string_buffer(8192),C.create_string_buffer(8192)]
  self.assertNotEqual(C.addressof(image_buffers[0]),C.addressof(image_buffers[1]))
  checked=0
  for image in image_buffers:
   image_base=C.addressof(image)
   for module,prefix,rva,before,callback in d.DISASTER_CALLS:
    bridge,cell,end,unwind=d.disaster_bridge(rva);code=bytearray(bridge)
    external,stop,objects,native_base=0x41000000,0x42000000,0x43000000,0x180000000
    struct.pack_into('<Q',code,cell,external)
    C.memset(image_base,0,8192);C.memmove(image_base,bytes(code),len(code));C.memmove(image_base+0x1000,unwind,len(unwind))
    u=U.Uc(U.UC_ARCH_X86,U.UC_MODE_64);page=image_base&~4095;span=((image_base-page+8192+4095)//4096)*4096
    u.mem_map(page,span);u.mem_write(image_base,bytes(C.string_at(image_base,8192)))
    for at,size in ((external,0x1000),(stop,0x1000),(objects,0x10000),(native_base,0x110000)):u.mem_map(at,size)
    stack=C.create_string_buffer(8192);stack_base=C.addressof(stack);stack_page=stack_base&~4095
    stack_span=((stack_base-stack_page+8192+4095)//4096)*4096
    for at in range(stack_page,stack_page+stack_span,4096):
     if not page<=at<page+span:u.mem_map(at,4096)
    entry_rsp=((stack_base+0x1000)&~15)-8
    u.mem_write(entry_rsp,struct.pack('<Q',stop))
    initial={name:0x22330000+i*0x100 for i,name in enumerate(register_names)}
    world,island,city,table,position=objects,objects+0x8000,objects+0x9000,objects+0xa000,objects+0xb000
    initial.update(RSP=entry_rsp,RAX=3,RBX=world,RCX=world,RDX=400,R8=100,R9=position,RDI=island,RSI=city,R12=native_base,R14=native_base)
    expected_callback=[];returned=123
    if rva in (0xb1c56,0xb1d4a):
     initial['RBX']=31;u.mem_write(native_base+0xfe1d0+6,struct.pack('<H',12345));expected_callback=[12345,31,city]
    elif rva==0xe0b52:
     u.mem_write(world+0x6f04,struct.pack('<I',500000));returned=225000;expected_callback=[world]
    elif rva==0x587f3:
     initial.update(RBX=island,RAX=200);returned=600;expected_callback=[island]
    elif rva==0x75977:
     initial.update(RCX=1,R8=100);returned=19800200;expected_callback=[9900100,world]
    elif rva==0x58870:
     initial['RCX']=island;expected_callback=[island]
    elif rva==0x75a5e:
     initial.update(RAX=table,RCX=0x123,RDX=29,R8=0,RSI=0xffffffff);expected_callback=[table,29,0,position]
    elif rva==0xe0d26:
     initial.update(RCX=table,RDX=346,R8=0);expected_callback=[table,346,0,position]
     u.mem_write(entry_rsp+0x28,struct.pack('<I',0xffffffff))
    for name,value in initial.items():u.reg_write(getattr(X,'UC_X86_REG_'+name),value)
    u.mem_write(external,b'\x48\xb8'+struct.pack('<Q',returned)+b'\xc3')
    instruction_addresses={image_base+i.address for i in decoder.disasm(bytes(code[:end]),0)}
    expected_nonvolatile={name:initial[name]for name in ('RBX','RBP','RSI','RDI','R12','R13','R14','R15')}
    seen=set();call_count=[]
    def hook(machine,address,size,data):
     nonlocal checked
     if address==external:
      actual=[machine.reg_read(getattr(X,'UC_X86_REG_'+n))for n in ('RCX','RDX','R8','R9')]
      self.assertEqual(actual[:len(expected_callback)],expected_callback,(hex(rva),actual))
      if rva in (0x75a5e,0xe0d26):self.assertEqual(struct.unpack('<I',machine.mem_read(machine.reg_read(X.UC_X86_REG_RSP)+0x28,4))[0],0xffffffff)
      call_count.append(1);return
     if address not in instruction_addresses:return
     seen.add(address);C.memmove(stack_base,bytes(machine.mem_read(stack_base,8192)),8192)
     storage=C.create_string_buffer(1280);ctx=(C.addressof(storage)+15)&~15
     C.c_uint32.from_address(ctx+48).value=0x10000b
     for name,offset in context_offsets.items():C.c_uint64.from_address(ctx+offset).value=machine.reg_read(getattr(X,'UC_X86_REG_'+name))
     C.c_uint64.from_address(ctx+248).value=address
     handler=C.c_void_p();frame=C.c_uint64()
     self.virtual(0,image_base,address,C.byref(self.Function(0,end,0x1000)),ctx,C.byref(handler),C.byref(frame),None)
     self.assertEqual(C.c_uint64.from_address(ctx+152).value,entry_rsp+8,(hex(rva),hex(address-image_base),'RSP'))
     self.assertEqual(C.c_uint64.from_address(ctx+248).value,stop,(hex(rva),hex(address-image_base),'RIP'))
     for name,value in expected_nonvolatile.items():self.assertEqual(C.c_uint64.from_address(ctx+context_offsets[name]).value,value,(hex(rva),hex(address-image_base),name))
     checked+=1
    u.hook_add(U.UC_HOOK_CODE,hook);u.emu_start(image_base,stop,count=1000)
    self.assertEqual(len(call_count),1);self.assertEqual(seen,instruction_addresses)
    self.assertEqual(u.reg_read(X.UC_X86_REG_RSP),entry_rsp+8)
    for name,value in expected_nonvolatile.items():self.assertEqual(u.reg_read(getattr(X,'UC_X86_REG_'+name)),value)
    if rva==0x587f3:self.assertEqual((u.reg_read(X.UC_X86_REG_RAX),u.reg_read(X.UC_X86_REG_RCX)),(200,600))
    if rva==0xe0b52:self.assertEqual(u.reg_read(X.UC_X86_REG_EFLAGS)&1,0)
    if rva==0x75977:self.assertEqual(u.reg_read(X.UC_X86_REG_RDX),returned)
  expected=sum(len(list(decoder.disasm(d.disaster_bridge(row[2])[0][:d.disaster_bridge(row[2])[2]],0)))for row in d.DISASTER_CALLS)*len(image_buffers)
  self.assertEqual(checked,expected)


class NativeDisasterSchedulers(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  try:
   import pefile
   import unicorn as U
   from unicorn import x86_const as X
  except ImportError as exc:raise unittest.SkipTest('Native instruction tools unavailable.')from exc
  path=ROOT/'.local/game-copies/World Settings/AnnoWelt.dll'
  if not path.is_file():raise unittest.SkipTest('Exact native HE module unavailable.')
  raw=path.read_bytes()
  if hashlib.sha256(raw).hexdigest()!=STOCK_SHA256['AnnoWelt.dll']:raise AssertionError('Exact native World module differs.')
  cls.pe=pefile.PE(data=raw);cls.image=cls.pe.get_memory_mapped_image();cls.U,cls.X=U,X
 def machine(self,base):
  U=self.U;image=bytearray(self.image);delta=base-self.pe.OPTIONAL_HEADER.ImageBase
  if delta:
   for block in self.pe.DIRECTORY_ENTRY_BASERELOC:
    for entry in block.entries:
     if entry.type==10:struct.pack_into('<Q',image,entry.rva,struct.unpack_from('<Q',image,entry.rva)[0]+delta)
  u=U.Uc(U.UC_ARCH_X86,U.UC_MODE_64);u.mem_map(base,(len(image)+4095)&~4095);u.mem_write(base,bytes(image))
  for at,size in ((0x31000000,0x100000),(0x32000000,0x40000),(0x33000000,0x10000),(base+0x200000,0x10000)):u.mem_map(at,size)
  return u
 def put(self,u,address,fmt,*values):u.mem_write(address,struct.pack(fmt,*values))
 def callback(self,u,fn):
  X=self.X;stack=u.reg_read(X.UC_X86_REG_RSP);ret=struct.unpack('<Q',u.mem_read(stack,8))[0]
  value=fn(u);u.reg_write(X.UC_X86_REG_RAX,value or 0);u.reg_write(X.UC_X86_REG_RSP,stack+8);u.reg_write(X.UC_X86_REG_RIP,ret)
 def call(self,u,base,entry,rcx,rdx=0):
  X=self.X;stack=0x32020008;stop=0x3300f000;self.put(u,stack,'<Q',stop)
  for r,v in ((X.UC_X86_REG_RSP,stack),(X.UC_X86_REG_RCX,rcx),(X.UC_X86_REG_RDX,rdx)):u.reg_write(r,v)
  u.emu_start(base+entry,stop,count=200000);self.assertEqual(u.reg_read(X.UC_X86_REG_RIP),stop)
 def install(self,u,base,rva,fn):
  before=next(row[3]for row in d.DISASTER_CALLS if row[2]==rva);bridge,cell,end,unwind=d.disaster_bridge(rva)
  gate=base+0x200000;callback=0x33000100;code=bytearray(bridge);struct.pack_into('<Q',code,cell,callback);u.mem_write(gate,bytes(code))
  u.mem_write(base+rva,b'\xe8'+struct.pack('<i',gate-(base+rva)-5)+b'\x90'*(len(before)-5))
  def hook(machine,address,size,data):
   if address==callback:self.callback(machine,fn)
  u.hook_add(self.U.UC_HOOK_CODE,hook,begin=callback,end=callback)
 def test_actual_native_earthquake_and_drought_threshold_branches_all_modes(self):
  X,U=self.X,self.U;world=0x31000000
  for base in (0x180000000,0x280000000):
   for kind,entry,site,normal,pass_rva,fail_rva in (
      ('earthquake',0xe0b40,0xe0b52,450000,0xe0b62,0xe0d43),
      ('drought',0x587d0,0x587f3,300,0x587fd,0x5887c)):
    for mode in range(3):
     threshold=normal*2 if mode==0 else normal//2 if mode==2 else normal
     for elapsed in (threshold-1,threshold,threshold+1):
      u=self.machine(base);self.install(u,base,site,lambda machine,value=threshold:value)
      if kind=='earthquake':self.put(u,world+0x6f04,'<I',elapsed-1);delta=1;expected=elapsed>=threshold
      else:self.put(u,world+0x12c,'<H',1000);delta=(1000+elapsed)*500;expected=elapsed>=threshold
      stopped=[]
      def stop(machine,address,size,data):
       if address in (base+pass_rva,base+fail_rva):stopped.append(address==base+pass_rva);machine.emu_stop()
      u.hook_add(U.UC_HOOK_CODE,stop);self.put(u,0x32020008,'<Q',0x3300f000)
      for reg,value in ((X.UC_X86_REG_RSP,0x32020008),(X.UC_X86_REG_RCX,world),(X.UC_X86_REG_RDX,delta)):u.reg_write(reg,value)
      u.emu_start(base+entry,0x3300f000,count=2000)
      self.assertEqual(stopped,[expected],(kind,hex(base),mode,elapsed,threshold))
 def test_actual_native_volcano_delay_reset_all_modes_without_rng_advance(self):
  X=self.X;world,island=0x31000000,0x31008000
  for base in (0x180000000,0x280000000):
   for mode in range(3):
    for random in (0,1,32767,65535):
     u=self.machine(base);self.install(u,base,0x75977,lambda machine,m=mode:(machine.reg_read(X.UC_X86_REG_RCX)*2 if m==0 else machine.reg_read(X.UC_X86_REG_RCX)//2 if m==2 else machine.reg_read(X.UC_X86_REG_RCX)))
     self.put(u,world+0x1e8,'<HH',123,1000)
     for reg,value in ((X.UC_X86_REG_RSP,0x32020000),(X.UC_X86_REG_RBX,world),(X.UC_X86_REG_RDI,island),(X.UC_X86_REG_R8,random)):u.reg_write(reg,value)
     u.emu_start(base+0x75965,base+0x75983,count=1000)
     normal=9900000+random;expected=normal*2 if mode==0 else normal//2 if mode==2 else normal
     self.assertEqual(struct.unpack('<I',u.mem_read(island+0x58,4))[0],expected)
     self.assertEqual(bytes(u.mem_read(world+0x1e8,4)),struct.pack('<HH',123,1000))
 def test_actual_native_event_duration_changes_damage_attempts_and_projectile_bursts(self):
  X,U=self.X,self.U
  for base in (0x180000000,0x280000000):
   for kind,entry,normal in (('earthquake',0x33f40,7500),('volcano',0x34850,10000)):
    effects=[]
    for severity in range(3):
     u=self.machine(base);event,world,island,game=0x31000000,0x31008000,0x31010000,0x31018000
     option,table,resident,figure,projectile=0x31020000,0x31021000,0x31022000,0x31023000,0x31024000
     world_vt,island_vt,game_vt,option_vt,table_vt,resident_vt,projectile_vt=(0x31030000+i*0x1000 for i in range(7))
     for obj,vt in ((world,world_vt),(island,island_vt),(game,game_vt),(option,option_vt),(table,table_vt),(resident,resident_vt),(projectile,projectile_vt)):self.put(u,obj,'<Q',vt)
     handlers={};counter=[0]
     def target(vt,slot,fn):
      address=0x33000100+len(handlers)*0x20;self.put(u,vt+slot,'<Q',address);handlers[address]=fn
     target(world_vt,0x48,lambda machine:option);target(world_vt,0x170,lambda machine:0)
     target(world_vt,0x148,lambda machine:resident);target(world_vt,0x38,lambda machine:game)
     target(island_vt,0x248,lambda machine:table);target(island_vt,0x150,lambda machine:0)
     target(option_vt,0x100,lambda machine:0);target(table_vt,8,lambda machine:0);target(game_vt,0xe0,lambda machine:figure)
     def create_projectile(machine):
      pointer=struct.unpack('<Q',machine.mem_read(machine.reg_read(X.UC_X86_REG_RSP)+0x30,8))[0]
      self.put(machine,pointer,'<Q',projectile);counter[0]+=1;return 0
     target(resident_vt,0,create_projectile)
     target(projectile_vt,0x130,lambda machine:0);target(projectile_vt,0x1c8,lambda machine:0);target(projectile_vt,0x1e0,lambda machine:1)
     def hook(machine,address,size,data):
      if address==base+0x34130:
       counter[0]+=1;self.callback(machine,lambda other:0)
      elif address in handlers:self.callback(machine,handlers[address])
     u.hook_add(U.UC_HOOK_CODE,hook)
     self.put(u,event,'<Q',base+(0xf2130 if kind=='earthquake'else 0xf2230));self.put(u,event+8,'<QQQ',island,world,game)
     self.put(u,event+0x28,'<II',0,346 if kind=='earthquake'else 29)
     duration=normal//2 if severity==0 else normal*2 if severity==2 else normal
     self.put(u,event+0x48,'<I',duration);self.put(u,event+0x58,'<I',500 if kind=='earthquake'else 0)
     self.put(u,event+0x60,'<Q',0)
     for clock in range(100,duration+201,100):
      self.call(u,base,entry,event,clock)
      if struct.unpack('<I',u.mem_read(event+0x28,4))[0]!=0 or (kind=='volcano'and struct.unpack('<I',u.mem_read(event+0x48,4))[0]==normal and clock>duration):break
     effects.append(counter[0])
    self.assertGreater(effects[0],0,(kind,hex(base),effects));self.assertLess(effects[0],effects[1],(kind,hex(base),effects));self.assertLess(effects[1],effects[2],(kind,hex(base),effects))


if __name__=='__main__':unittest.main()
