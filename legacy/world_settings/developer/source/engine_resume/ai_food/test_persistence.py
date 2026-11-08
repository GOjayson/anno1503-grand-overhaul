"""Fingerprint-bound original controller COMP save/load instruction fixtures.

Native control flow, attribute getters/setters and serialization execute in
Unicorn private memory. File I/O, snprintf, memset, strchr, strncmp, atoi and
stack probing are test primitives. No game is started or DLL patched/loaded.
"""
from pathlib import Path
import hashlib,json,re,struct,sys
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[1];ROOT=WORK.parent
sys.path.insert(0,str(WORK/'engine_audit'))
from audit import Module
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE,UC_HOOK_MEM_READ
from unicorn.x86_const import *
SPEC={
 'CompLogic.dll':dict(sha='7f2c7e818d8c25a0b6c48cda2d21bfa0c4096c5dcd8be91c2ab93d877c22afee',vtable=0x88128,save=0x5ec70,load=0x5e630,memset=0x85a42,printf=0x2f00,stack=0x85ab0,getter=0x6640,nop=0x1020),
 'CompLogicClassic.dll':dict(sha='0a7692879e15e8cbaed73ec3b59eaa6419165faaea6d8696cddfd68c92000f22',vtable=0x84fc8,save=0x5bf00,load=0x5b8c0,memset=0x82532,printf=0x1010,stack=0x825a0,getter=0x4a10,nop=0x1020)}
cases=[]
for name,s in SPEC.items():
 m=Module(str(ROOT/name));assert hashlib.sha256(m.data).hexdigest()==s['sha'] and m.pe.FILE_HEADER.Machine==0x8664
 assert struct.unpack_from('<Q',m.image,s['vtable']+0x28)[0]==m.base+s['save']
 assert struct.unpack_from('<Q',m.image,s['vtable']+0x30)[0]==m.base+s['load']
 # Getters and inert virtual callback vary between these AMD64 modules.
 s['getter']=struct.unpack_from('<Q',m.image,s['vtable']+0x10)[0]-m.base
 s['nop']=struct.unpack_from('<Q',m.image,s['vtable']+0x40)[0]-m.base
 for base in [0x180000000,0x280000000]:
  for suspend in [0,1]:
   u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,(len(m.image)+4095)&~4095);u.mem_write(base,m.image)
   u.mem_map(0x31000000,0x10000);u.mem_map(0x32000000,0x40000);u.mem_map(0x33000000,0x2000)
   controller=0x32002000;world=0x32008000;cvtable=0x32005000;wvtable=0x32009000
   table=0x3200a000;tvtable=0x3200b000;io=0x3200c000;iovtable=0x3200d000;out=0x3200e000
   city=0x32010000
   u.mem_write(controller,struct.pack('<QQ',cvtable,world));u.mem_write(controller+0xa4c,struct.pack('<I',12))
   u.mem_write(controller+0x9e0,struct.pack('<Q',city));u.mem_write(city+0x13c,struct.pack('<H',0x123))
   poison=0x66660000+suspend*0x10000;u.mem_write(city+0x2350,struct.pack('<Q',poison))
   u.mem_write(cvtable+0x10,struct.pack('<Q',base+s['getter']))
   # The load-SUSPEND callback is external to the parser semantics being
   # checked. Keep it inert for both modules and document it explicitly.
   u.mem_write(cvtable+0x40,struct.pack('<Q',0x33000380));u.mem_write(0x33000380,b'\xc3')
   u.mem_write(world,struct.pack('<QQ',wvtable,table));u.mem_write(table,struct.pack('<Q',tvtable))
   u.mem_write(wvtable+0x98,struct.pack('<Q',0x33000300));u.mem_write(wvtable+0x150,struct.pack('<Q',0x33000320))
   u.mem_write(tvtable+0x18,struct.pack('<Q',0x33000340));u.mem_write(tvtable+0x10,struct.pack('<Q',0x33000340))
   u.mem_write(0x33000300,bytes.fromhex('41c7400800000000b801000000c3'))
   u.mem_write(0x33000320,bytes.fromhex('488b4108c3'));u.mem_write(0x33000340,bytes.fromhex('31c0c3'))
   u.mem_write(io,struct.pack('<Q',iovtable));u.mem_write(iovtable,struct.pack('<QQ',0x33000400,0x33000420))
   input_text=('SUSPEND='+str(suspend)+'\0').encode('ascii');output=[];observed_queue_reads=[]
   def cstring(address,maximum=8192):
    data=bytearray()
    for n in range(maximum):
     value=bytes(u.mem_read(address+n,1))[0]
     if not value:return bytes(data)
     data.append(value)
    raise AssertionError('unterminated fixture string')
   def return_value(machine,value=0):
    stack=machine.reg_read(UC_X86_REG_RSP);target=struct.unpack('<Q',machine.mem_read(stack,8))[0]
    machine.reg_write(UC_X86_REG_RAX,value&0xffffffffffffffff);machine.reg_write(UC_X86_REG_RSP,stack+8);machine.reg_write(UC_X86_REG_RIP,target)
   import_stubs={};stub=0x33000500
   for imp in m.pe.DIRECTORY_ENTRY_IMPORT:
    for item in imp.imports:
     if item.name not in [b'strchr',b'strrchr',b'strncmp',b'atoi',b'atol']:continue
     u.mem_write(base+item.address-m.base,struct.pack('<Q',stub));import_stubs[stub]=item.name.decode('ascii');stub+=16
   def native_primitive(machine,address,size,user):
    rcx=machine.reg_read(UC_X86_REG_RCX);rdx=machine.reg_read(UC_X86_REG_RDX);r8=machine.reg_read(UC_X86_REG_R8);r9=machine.reg_read(UC_X86_REG_R9)
    if address==base+s['stack']:return_value(machine,machine.reg_read(UC_X86_REG_RAX));return
    if address==base+s['memset']:
     machine.mem_write(rcx,bytes([rdx&255])*r8);return_value(machine,rcx);return
    if address==base+s['printf']:
     fmt=cstring(r8).decode('ascii');types=re.findall(r'%[dius]',fmt);args=[]
     for index,typ in enumerate(types):
      value=r9 if index==0 else struct.unpack('<Q',machine.mem_read(machine.reg_read(UC_X86_REG_RSP)+0x28+(index-1)*8,8))[0]
      if typ=='%s':args.append(cstring(value).decode('ascii'))
      else:args.append(struct.unpack('<i',struct.pack('<I',value&0xffffffff))[0])
     text=(fmt%tuple(args)).encode('ascii');assert len(text)<rdx
     machine.mem_write(rcx,text+b'\0');return_value(machine,len(text));return
    if address==0x33000400:
     output.append(bytes(machine.mem_read(rdx,r8)));machine.mem_write(r9,struct.pack('<I',r8));return_value(machine,1);return
    if address==0x33000420:
     assert r8==len(input_text);machine.mem_write(rdx,input_text);machine.mem_write(r9,struct.pack('<I',r8));return_value(machine,1);return
    kind=import_stubs[address]
    if kind in ['strchr','strrchr']:
     data=cstring(rcx);at=(data.find if kind=='strchr' else data.rfind)(bytes([rdx&255]));return_value(machine,rcx+at if at>=0 else 0)
    elif kind=='strncmp':
     a=bytes(machine.mem_read(rcx,r8)).split(b'\0')[0];b=bytes(machine.mem_read(rdx,r8)).split(b'\0')[0]
     return_value(machine,(a>b)-(a<b))
    else:
     match=re.match(rb'\s*([+-]?\d+)',cstring(rcx));return_value(machine,int(match[1]) if match else 0)
   targets=[base+s['stack'],base+s['memset'],base+s['printf'],0x33000400,0x33000420,*import_stubs]
   for target in targets:u.hook_add(UC_HOOK_CODE,native_primitive,begin=target,end=target)
   def watch_queue(machine,access,address,size,value,user):
    if address<city+0x2358 and address+size>city+0x2350:observed_queue_reads.append((address,size))
   u.hook_add(UC_HOOK_MEM_READ,watch_queue)
   def call(rva,**regs):
    u.mem_write(0x31008008,struct.pack('<Q',0x33000000));u.reg_write(UC_X86_REG_RSP,0x31008008)
    for key,value in regs.items():u.reg_write(globals()['UC_X86_REG_'+key],value)
    try:u.emu_start(base+rva,0x33000000,count=100000)
    except Exception as exc:raise AssertionError((name,hex(rva),hex(u.reg_read(UC_X86_REG_RIP)),hex(u.reg_read(UC_X86_REG_RSP)))) from exc
    assert u.reg_read(UC_X86_REG_RIP)==0x33000000
    return u.reg_read(UC_X86_REG_RAX)
   assert call(s['load'],RCX=controller,RDX=io,R8=len(input_text),R9=out)==1
   flag=bytes(u.mem_read(controller+0x1e9d,1))[0]
   assert flag==1-suspend and struct.unpack('<I',u.mem_read(controller+0xab4,4))[0]==suspend
   assert call(s['save'],RCX=controller,RDX=io,R8=out)==1
   serialized=b''.join(output);assert ('SUSPEND='+str(suspend)).encode()+b'\0' in serialized
   assert not observed_queue_reads and u.mem_read(city+0x2350,8)==struct.pack('<Q',poison)
   cases.append(dict(module=name,image_base=hex(base),saved_suspend=suspend,loaded_scheduler_flag=flag,
    serialized_bytes=len(serialized),serialized_sha256=hashlib.sha256(serialized).hexdigest(),
    pending_head_reads=len(observed_queue_reads),city_id_record_present=b'STADTOFF=291\0' in serialized,
    text=serialized.decode('ascii').replace('\0','\n')))
result=dict(cases=cases,native_controller_roundtrips=len(cases),actual_game_runs=0,
 input_sha256={name:s['sha'] for name,s in SPEC.items()},
 scope=__doc__,conclusion='Native COMP persistence serializes controller attributes and city identities in these fixtures; it does not access pending queue heads. Appended pending records still require constructor/allocation/delete hooks and world reconstruction verification.')
(HERE/'persistence_results.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2))
