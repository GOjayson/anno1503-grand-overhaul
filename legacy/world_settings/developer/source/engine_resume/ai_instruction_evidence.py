"""Fingerprint-bound AI storage/range evidence; no game/DLL loading or patching.

Source files are read only. Small original instruction sequences run in Unicorn
against private test buffers; this is not AI gameplay, advancement or save/load.
Only evidence reports beside this script are written.
"""
from pathlib import Path
import hashlib,json,struct,sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE.parent/'engine_audit'))
from audit import Module
from capstone.x86_const import X86_OP_MEM,X86_OP_IMM,X86_REG_RIP
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_RAX,UC_X86_REG_RBX,UC_X86_REG_RCX,UC_X86_REG_RDX,UC_X86_REG_R8,UC_X86_REG_R9,UC_X86_REG_RDI,UC_X86_REG_RSP,UC_X86_REG_RIP

EXPECTED={
 'CompLogic.dll':'7f2c7e818d8c25a0b6c48cda2d21bfa0c4096c5dcd8be91c2ab93d877c22afee',
 'CompLogicClassic.dll':'0a7692879e15e8cbaed73ec3b59eaa6419165faaea6d8696cddfd68c92000f22',
 'AnnoWelt.dll':'ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9',
 'AnnoFrame.dll':'046b5ad6f351dfe867ed38ce29fb50a594485b43a32ee90adadc48e850466baf',
 'AnnoGame.dll':'e6f01d19e8e16e6716c0a6c7d3ba00273c9df493e051b8ba62865ee4b53dfdea'}
modules={}
for name,sha in EXPECTED.items():
 m=Module(str(ROOT/name))
 assert hashlib.sha256(m.data).hexdigest()==sha,(name,'unrecognized source')
 assert m.pe.FILE_HEADER.Machine==0x8664 and m.pe.OPTIONAL_HEADER.Magic==0x20b
 modules[name]=m

SPEC={
 'CompLogic.dll':dict(guard=0x86540,guard_calls=[0x3c952,0x3c98e],indexed_reads=[0x1ac02,0x1ac79],fixed_food_read=0x354dd,
  definition_initialize=[0x3b390,0x3c1b0],definition_clear=[0x3b8e7,0x3c71d],factory=0x59560,computer_allocation=0x595de,computer_delete=0x5b620,
  pending_allocate=0x363a8,pending_ctor=0x847d0,pending_ctor_end=0x84af6,pending_delete=0x36932,pending_bulk_delete=0x2a043,
  pending_exception_delete=0x86169,computer_vtable=0x88128,computer_delete_slot=0x128,
  city_ctor=0x29ca0,city_allocate=0x79a0b,city_delete=0x29fb9,city_state_ctor=0x82f60,city_state_count=0x83252,city_memset=0x85a42,
  generic_producer_sites=[0x3a93c,0x3cc6c,0x3cd20],
  ranges=[(0x1ab90,0x1abd6),(0x3191b,0x31950),(0x320c2,0x32237),(0x32498,0x32587),(0x36c56,0x36cee),(0x36e21,0x37289),(0x57ac9,0x57cad),(0x582e5,0x58401),(0x60343,0x603f4),(0x7330b,0x73353),(0x840a8,0x8419c)]),
 'CompLogicClassic.dll':dict(guard=0x83010,guard_calls=[0x39f62,0x39f9e],indexed_reads=[0x19562,0x195d9],fixed_food_read=0x33c5d,
  definition_initialize=[0x397c0],definition_clear=[0x39d2d],factory=0x569b0,computer_allocation=0x56a2e,computer_delete=0x588d0,
  pending_allocate=0x34b28,pending_ctor=0x81340,pending_ctor_end=0x81666,pending_delete=0x350b2,pending_bulk_delete=0x289a3,
  pending_exception_delete=0x82c49,computer_vtable=0x84fc8,computer_delete_slot=0x120,
  city_ctor=0x28600,city_allocate=0x7688b,city_delete=0x28919,city_state_ctor=0x7fad0,city_state_count=0x7fdc2,city_memset=0x82532,
  generic_producer_sites=[0x390bc,0x3a27c,0x3a330],
  ranges=[(0x194f0,0x19536),(0x3027b,0x302b0),(0x30a22,0x30b97),(0x30df8,0x30ee7),(0x353d6,0x3546e),(0x355a1,0x35a09),(0x55029,0x5520d),(0x55845,0x55961),(0x5d5b3,0x5d664),(0x7029b,0x702e3),(0x80c18,0x80d0c)])}

def instruction(module,rva):
 return next(module.cs.disasm(module.image[rva:rva+16],module.base+rva))
def record(module,rva):
 i=instruction(module,rva)
 return dict(rva=hex(rva),bytes=i.bytes.hex(),instruction=i.mnemonic+' '+i.op_str)
def check_bytes(module,rva,value):
 assert module.image[rva:rva+len(bytes.fromhex(value))]==bytes.fromhex(value),(module.name,hex(rva),'instruction preimage')
def private_machine(module,base):
 uc=Uc(UC_ARCH_X86,UC_MODE_64)
 uc.mem_map(base,(len(module.image)+4095)&~4095);uc.mem_write(base,module.image)
 uc.mem_map(0x31000000,0x10000);uc.mem_map(0x32000000,0x20000);uc.mem_map(0x33000000,0x1000)
 return uc
def execute(uc,base,rva,**registers):
 uc.reg_write(UC_X86_REG_RSP,0x31008008);uc.mem_write(0x31008008,struct.pack('<Q',0x33000000))
 for name,value in registers.items():uc.reg_write(globals()['UC_X86_REG_'+name],value)
 uc.emu_start(base+rva,0x33000000,count=20000)
 assert uc.reg_read(UC_X86_REG_RIP)==0x33000000,'instruction budget reached'
 return uc.reg_read(UC_X86_REG_RAX)

result=dict(scope=__doc__,source_sha256=EXPECTED,ai_modules={},world_player_slots={},used_scene_placeholders=[])
assembly=[];guard_cases=0;node_cases=0;city_cases=0
for name,s in SPEC.items():
 m=modules[name]
 check_bytes(m,s['guard'],'83e81a83f80e770789bc83f0000000c3')
 for at in s['guard_calls']:
  i=instruction(m,at);assert i.mnemonic=='call' and i.operands[0].imm==m.base+s['guard']
 indexed=[]
 for a,b in m.funcs:
  for i in m.cs.disasm(m.image[a:b],m.base+a):
   if any(o.type==X86_OP_MEM and o.mem.disp==0xf0 and o.mem.index and o.mem.scale==4 for o in i.operands):indexed.append(i.address-m.base)
 assert indexed==s['indexed_reads'],(name,indexed)
 for at in indexed:assert instruction(m,at).mnemonic=='mov'
 assert '0xf0]' in instruction(m,s['fixed_food_read']).op_str
 check_bytes(m,s['computer_allocation'],'b9d0210000')
 assert bytes.fromhex('bad0210000') in m.image[s['computer_delete']:s['computer_delete']+256]
 assert struct.unpack_from('<Q',m.image,s['computer_vtable']+s['computer_delete_slot'])[0]==m.base+s['computer_delete']
 check_bytes(m,s['pending_allocate'],'b940030000')
 check_bytes(m,s['pending_delete'],'ba40030000')
 check_bytes(m,s['pending_bulk_delete'],'ba40030000')
 check_bytes(m,s['pending_exception_delete'],'ba40030000')
 check_bytes(m,s['city_allocate'],'b910fd0000');check_bytes(m,s['city_delete'],'ba10fd0000')
 check_bytes(m,s['city_state_count'],'418d4a38')
 assert m.image[s['pending_ctor_end']-1]==0xc3
 for base in [0x180000000,0x280000000]:
  uc=private_machine(m,base);pointer=0x32002000
  for good in range(56):
   before=bytes([0xa5])*0x1000;expected=bytearray(before);uc.mem_write(pointer,before)
   execute(uc,base,s['guard'],RAX=good,RBX=pointer,RDI=0x12345678)
   if 26<=good<=40:struct.pack_into('<I',expected,0xf0+(good-26)*4,0x12345678)
   assert uc.mem_read(pointer,len(before))==expected,(name,good)
   guard_cases+=1
  uc.mem_write(pointer-16,bytes([0xa5])*(0x340+32))
  execute(uc,base,s['pending_ctor'],RCX=pointer)
  raw=bytes(uc.mem_read(pointer,0x340))
  assert bytes(uc.mem_read(pointer-16,16))==bytes([0xa5])*16
  assert bytes(uc.mem_read(pointer+0x340,16))==bytes([0xa5])*16
  for index in range(30):
   start=0x48+index*20
   assert raw[start:start+16]==bytes(16) and raw[start+16]==0,(name,index)
  node_cases+=1
  # The native city constructor calls only local constructors and memset.
  # Substitute that one C-library primitive in private emulator memory.
  # This executes the original 56-state / 56*8-plan construction instructions.
  uc.mem_write(pointer-16,bytes([0xa5])*(0xfd10+32));memset_calls=[]
  def emulate_memset(machine,address,size,user):
   dest=machine.reg_read(UC_X86_REG_RCX);value=machine.reg_read(UC_X86_REG_RDX)&255;length=machine.reg_read(UC_X86_REG_R8)
   assert length==0x60 and pointer<=dest and dest+length<=pointer+0xfd10
   machine.mem_write(dest,bytes([value])*length);memset_calls.append((dest,length))
   stack=machine.reg_read(UC_X86_REG_RSP);target=struct.unpack('<Q',machine.mem_read(stack,8))[0]
   machine.reg_write(UC_X86_REG_RAX,dest);machine.reg_write(UC_X86_REG_RSP,stack+8);machine.reg_write(UC_X86_REG_RIP,target)
  hook=uc.hook_add(UC_HOOK_CODE,emulate_memset,begin=base+s['city_memset'],end=base+s['city_memset'])
  assert execute(uc,base,s['city_ctor'],RCX=pointer)==pointer
  uc.hook_del(hook)
  assert len(memset_calls)==448
  for index,(dest,length) in enumerate(memset_calls):assert dest==pointer+0x23a4+index*0x7c and length==0x60
  assert bytes(uc.mem_read(pointer-16,16))==bytes([0xa5])*16
  assert bytes(uc.mem_read(pointer+0xfd10,16))==bytes([0xa5])*16
  for good in range(56):
   start=pointer+0x5c4+good*0x5c
   assert uc.mem_read(start,0x58)==bytes(0x58),(name,good,'native initialized good state')
  city_cases+=1
 result['ai_modules'][name]=dict(guard=record(m,s['guard']),guard_callers=[record(m,x) for x in s['guard_calls']],
  indexed_consumer_stand_readers=[record(m,x) for x in indexed],fixed_fish_fallback=record(m,s['fixed_food_read']),
  native_consumer_stand_protocol_goods=list(range(26,41)),physical_consumer_stand_C_array_length='UNPROVEN; next proven generic production table begins at+0x194',
  generic_producer_sites=[record(m,x) for x in s['generic_producer_sites']],generic_producer_candidates_per_good=8,
  computer_controller_allocation_bytes=0x21d0,computer_allocator=record(m,s['computer_allocation']),computer_delete=hex(s['computer_delete']),
  computer_destructor_vtable_slot=hex(s['computer_delete_slot']),
  city_allocation_bytes=0xfd10,city_allocate=record(m,s['city_allocate']),city_delete=record(m,s['city_delete']),
  city_constructor=hex(s['city_ctor']),city_state_constructor=hex(s['city_state_ctor']),city_good_states=56,city_good_state_offset=0x5c4,city_good_state_stride=0x5c,
  city_plan_records=448,city_plan_offset=0x23a4,city_plan_stride=0x7c,city_plan_goods=56,city_plan_candidates_per_good=8,
  pending_node_allocation_bytes=0x340,pending_node_allocate=record(m,s['pending_allocate']),pending_node_constructor=hex(s['pending_ctor']),
  pending_node_delete=record(m,s['pending_delete']),pending_node_bulk_delete=record(m,s['pending_bulk_delete']),
  pending_node_exception_delete=record(m,s['pending_exception_delete']),
  pending_record_goods=list(range(26,56)),pending_record_offset=0x48,pending_record_stride=20,
  range_candidates=[dict(begin=hex(a),end=hex(b)) for a,b in s['ranges']])
 assembly.append('\n# '+name+' SHA256 '+EXPECTED[name])
 for a,b in s['ranges']:assembly.append(m.dis(a,b))
 for at in [s['guard'],s['computer_allocation'],s['pending_allocate'],s['pending_delete'],s['pending_bulk_delete'],s['pending_exception_delete'],s['city_allocate'],s['city_delete'],s['city_state_count']]:assembly.append(m.dis(at,at+16))

g=modules['AnnoGame.dll']
assert struct.unpack_from('<Q',g.image,0x1f888+0x160)[0]==g.base+0x41e0
assert g.image[0x41e0]==0xe9 and 0x41e5+struct.unpack_from('<i',g.image,0x41e1)[0]==0x2e000
assert struct.unpack_from('<I',g.image,0x5000+(0x450-0x44d)*4)[0]==0x4c84
market_name=struct.unpack_from('<Q',g.image,0x22268+0xa1*8)[0]-g.base
assert g.image[market_name:market_name+11]==b'MARKTSTAND\0'
ware_getter_cases=0;property_cases=0
for base in [0x180000000,0x280000000]:
 uc=private_machine(g,base);definition=0x32002000;payload=0x32003000
 for wares,expected in [(bytes([26,28]),[26,28,24,40,25,45,0,0]),(bytes([37,0]),[37,0,0,0,0,0,0,0])]:
  raw=bytearray(0x300);raw[0x20e:0x216]=wares+bytes([0xee])*6
  uc.mem_write(definition,bytes(raw))
  for index,value in enumerate(expected):
   assert execute(uc,base,0x41e0,RCX=definition,RDX=index)==value
   ware_getter_cases+=1
   uc.mem_write(payload,struct.pack('<III',index,0,0))
   assert execute(uc,base,0x45f0,RCX=definition,RDX=0x450,R8=payload)==1
   assert struct.unpack('<I',uc.mem_read(payload+8,4))[0]==raw[0x20e+index]
   property_cases+=1
result['market_ware_api']=dict(market_stand_enum=0xa1,market_enum_name_rva=hex(market_name),
 virtual_ware_getter_slot=0x160,virtual_ware_getter=hex(0x41e0),food_mod_ware_helper=hex(0x2e000),
 food_market_wares=[26,28,24,40,25,45],
 property_0x450_raw_read=record(g,0x4c87),property_0x450_does_not_use_extended_virtual_getter=True,
 virtual_getter_emulation_cases=ware_getter_cases,raw_property_emulation_cases=property_cases)
assembly.extend(['\n# AnnoGame.dll SHA256 '+EXPECTED['AnnoGame.dll'],g.dis(0x4c84,0x4c9e),g.dis(0x2e000,0x2e033)])

w=modules['AnnoWelt.dll']
assert struct.unpack_from('<Q',w.image,0xfdbc0+0x10)[0]==w.base+0xc6d80
assert struct.unpack_from('<Q',w.image,0xfdbc0+0x18)[0]==w.base+0x95990
assert struct.unpack_from('<Q',w.image,0xff650+0x168)[0]==w.base+0xd1a90
check_bytes(w,0xc6d80,'b820000000c3');check_bytes(w,0x95990,'4863c2488b44c108c3')
check_bytes(w,0xc6c6b,'4883f820');check_bytes(w,0xc6c82,'83fa20');check_bytes(w,0xc6c87,'b805400080')
capacity_cases=0
for base in [0x180000000,0x280000000]:
 uc=private_machine(w,base);table=0x32002000;out=0x32009000
 assert execute(uc,base,0xc6d80)==32;capacity_cases+=1
 raw=bytearray(0x110)
 for index in range(32):struct.pack_into('<Q',raw,8+index*8,0x40000000+index*0x10000)
 uc.mem_write(table,bytes(raw))
 for index in [0,31]:
  assert execute(uc,base,0x95990,RCX=table,RDX=index)==0x40000000+index*0x10000
  capacity_cases+=1
 uc.mem_write(out,struct.pack('<Q',0xfeedface))
 assert execute(uc,base,0xc6c20,RCX=table,R8=0xffffffff,R9=out)&0xffffffff==0x80004005
 assert uc.mem_read(out,8)==bytes(8) and uc.mem_read(table,len(raw))==raw
 capacity_cases+=1
result['world_player_slots']=dict(capacity=32,table_vtable=hex(0xfdbc0),capacity_getter=hex(0xc6d80),id_getter=hex(0x95990),full_allocator_failure=hex(0xc6c87),emulated_cases=capacity_cases,meaning='total player slots, not an AI opponent maximum')

saved=json.loads((HERE/'scene_player_evidence.json').read_text())
for name,expected_count in [('01_1024_easy_256.sze',3),('03_1024_med_256.sze',4),('06_1024_heavy_256.sze',4)]:
 entry=next(x for x in saved['scenes'] if Path(x['path']).name==name)
 assert hashlib.sha256((ROOT/entry['path']).read_bytes()).hexdigest()==entry['sha256']
 assert entry['native_computer_type_0c_count']==expected_count
 result['used_scene_placeholders'].append(entry)
result.update(guard_instruction_emulation_cases=guard_cases,pending_constructor_emulation_cases=node_cases,
 city_constructor_emulation_cases=city_cases,city_constructor_external_stub='memset only,448 calls per constructor',
 actual_game_runs=0,ai_compatibility_status='UNIMPLEMENTED; zero-AI gate remains required')
(HERE/'ai_instruction_evidence.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')
(HERE/'ai_instruction_evidence.asm').write_text('\n\n'.join(assembly)+'\n','utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['ai_modules','used_scene_placeholders']},indent=2))
