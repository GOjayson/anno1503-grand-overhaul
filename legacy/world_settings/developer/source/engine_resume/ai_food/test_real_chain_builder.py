"""Execute native recursive recipe builders with Food-Mod chain inputs.

Anlagen recipe names are read from the installed Food0.5 resource copies.
The original Game property44d dispatcher reads bounded definition fixtures.
Definition lookup/identity/unlock-mask getters are documented fixture boundaries;
this is not a resource-parser run or evidence that an AI builds in the game.
"""
from pathlib import Path
import hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[1];ROOT=WORK.parent
sys.path.insert(0,str(WORK/'engine_audit'))
from audit import Module
from inspect_food_chains import entries
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *
prior=json.loads((HERE/'scoring_candidate_manifest.json').read_text());game=Module(str(ROOT/'AnnoGame.dll'))
assert hashlib.sha256(game.data).hexdigest()=='e6f01d19e8e16e6716c0a6c7d3ba00273c9df493e051b8ba62865ee4b53dfdea'
#The translation offsets are audited separately from these recipe fixtures.
#These are the native raw/growth/animal enum values, not array ordinal guesses.
translation_path=HERE.parent/'ai_audit2/enum_translation_results.json'
translation=json.loads(translation_path.read_text());assert translation['original_native_chunk_decode_cases']==72
good_ids=translation['resolved_names']
producer={24:805,25:1004,45:1018,14:1002,13:811,12:820}
expected={24:[(1,805,24)],25:[(1,1004,25),(2,1002,14),(2,811,13)],45:[(1,1018,45),(2,820,12)]}
cases=[];provider_cases=0
for filename in ['Anlagen.dat','Anlagen.addon']:
 source=ROOT/filename;definitions=entries(source)
 source_proof=next(s for s in translation['sources'] if s['path']==filename)
 assert hashlib.sha256(source.read_bytes()).hexdigest()==source_proof['sha256']
 inputs={ident:[good_ids[part.decode('ascii')] for part in definitions[ident]['ROHSTOFF'].split(b'\0') if part and part!=b'UNUSED'] for ident in producer.values()}
 assert inputs=={805:[137],1004:[14],1018:[12],1002:[13],811:[56],820:[69]},inputs
 for item in prior['modules']:
  path=HERE/item['output'];assert hashlib.sha256(path.read_bytes()).hexdigest()==item['output_sha256'];m=Module(str(path))
  builder=0x3a910 if item['module']=='CompLogic.dll' else 0x39090
  for base in [0x180000000,0x280000000]:
   for good in [24,25,45]:
    u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,(len(m.image)+4095)&~4095);u.mem_write(base,m.image)
    gb=base+0x200000000;u.mem_map(gb,(len(game.image)+4095)&~4095);u.mem_write(gb,game.image)
    u.mem_map(0x31000000,0x10000);u.mem_map(0x32000000,0x20000);u.mem_map(0x33000000,0x1000)
    provider=0x32002000;lookup=0x32004000;lookupvt=0x32005000;defvt=0x32006000;plan=0x32007000;sp=0x31008008
    u.mem_write(provider+8,struct.pack('<Q',lookup));u.mem_write(lookup,struct.pack('<Q',lookupvt));u.mem_write(lookupvt+0xe8,struct.pack('<Q',0x33000100))
    addresses={ident:0x32008000+i*0x400 for i,ident in enumerate(producer.values())};inverse={v:k for k,v in addresses.items()}
    for output,ident in producer.items():u.mem_write(provider+0x194+output*32,struct.pack('<I',ident))
    for ident,address in addresses.items():
     u.mem_write(address,struct.pack('<Q',defvt));u.mem_write(address+0x203,bytes([len(inputs[ident])]))
     u.mem_write(address+0x208,bytes(inputs[ident]+[0]*(2-len(inputs[ident]))))
    for offset,func in [(0x88,0x33000120),(0xd0,0x33000140),(0x1b0,0x33000160),(0x98,gb+0x45f0)]:u.mem_write(defvt+offset,struct.pack('<Q',func))
    seen=[]
    def boundary(machine,address,size,user):
     if address==0x33000100:
      ident=machine.reg_read(UC_X86_REG_RDX)&0xffffffff;value=addresses[ident];seen.append(ident)
     elif address==0x33000120:value=inverse[machine.reg_read(UC_X86_REG_RCX)]
     elif address==0x33000140:value=0
     else:value=8
     stack=machine.reg_read(UC_X86_REG_RSP);ret=struct.unpack('<Q',machine.mem_read(stack,8))[0]
     machine.reg_write(UC_X86_REG_RAX,value);machine.reg_write(UC_X86_REG_RSP,stack+8);machine.reg_write(UC_X86_REG_RIP,ret)
    for target in [0x33000100,0x33000120,0x33000140,0x33000160]:u.hook_add(UC_HOOK_CODE,boundary,begin=target,end=target)
    u.mem_write(plan-16,bytes([0xa5])*16+bytes(0x7c)+bytes([0xa5])*16)
    u.reg_write(UC_X86_REG_RSP,sp);u.mem_write(sp,struct.pack('<Q',0x33000000));u.mem_write(sp+0x28,struct.pack('<I',0));u.mem_write(sp+0x30,struct.pack('<Q',plan))
    for reg,value in [(UC_X86_REG_RCX,provider),(UC_X86_REG_RDX,0x100),(UC_X86_REG_R8,good),(UC_X86_REG_R9,0)]:u.reg_write(reg,value)
    u.emu_start(base+builder,0x33000000,count=30000)
    assert u.reg_read(UC_X86_REG_RIP)==0x33000000 and u.reg_read(UC_X86_REG_RAX)&255==1
    raw=bytes(u.mem_read(plan,0x7c));length=raw[0x60]
    actual=[(struct.unpack_from('<I',raw,p)[0],struct.unpack_from('<I',raw,p+4)[0],struct.unpack_from('<H',raw,p+8)[0]) for p in range(0,length*12,12)]
    assert actual==expected[good],(filename,item['module'],good,actual)
    assert struct.unpack_from('<I',raw,0x6c)[0]==8
    assert u.mem_read(plan-16,16)==bytes([0xa5])*16 and u.mem_read(plan+0x7c,16)==bytes([0xa5])*16
    cases.append(dict(source=filename,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),module=item['module'],base=hex(base),good=good,recipe_steps=actual,definition_lookups=seen))
   #The generic provider registration branch calls the original Game450/44d
   #getters and updates its existing eight-slot rows. Classification of the
   #building into this branch is the explicit entry boundary of this fixture.
   for good in [24,25,45]:
    ident=producer[good];record=next(r for r in source_proof['records'] if r['id']==ident)
    assert bytes.fromhex(record['WARE']['source_payload_hex'])==definitions[ident]['WARE']
    for used in [0,7,8]:
     u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,(len(m.image)+4095)&~4095);u.mem_write(base,m.image)
     gb=base+0x200000000;u.mem_map(gb,(len(game.image)+4095)&~4095);u.mem_write(gb,game.image)
     u.mem_map(0x31000000,0x10000);u.mem_map(0x32000000,0x10000)
     provider=0x32002000;definition=0x32006000;vt=0x32007000;sp=0x31008008
     raw=bytearray([0xa5])*0x1000
     outputs=[value for value in record['WARE']['ids'] if 1<=value<=56]
     for output in outputs:
      p=0x194+output*32;raw[p:p+32]=struct.pack('<8I',*([1000+i for i in range(used)]+[0]*(8-used)))
     u.mem_write(provider,bytes(raw));u.mem_write(definition,struct.pack('<Q',vt));u.mem_write(vt+0x98,struct.pack('<Q',gb+0x45f0))
     values=record['WARE']['ids'];u.mem_write(definition+0x20e,bytes(values+[0]*(2-len(values))))
     values=record['ROHSTOFF']['ids'];u.mem_write(definition+0x208,bytes(values+[0]*(2-len(values))))
     u.mem_write(definition+0x203,bytes([sum(v!=0 for v in values)]))
     for reg,value in [(UC_X86_REG_RSP,sp),(UC_X86_REG_RBX,provider),(UC_X86_REG_RSI,definition),(UC_X86_REG_RDI,ident),(UC_X86_REG_R8,0)]:u.reg_write(reg,value)
     delta=0 if item['module']=='CompLogic.dll' else -0x2a00
     #The two module-specific branch addresses are verified independently.
     start,end=(0x3cc03,0x3cb1d) if item['module']=='CompLogic.dll' else (0x3a213,0x3a12d)
     assert m.image[start:start+5]==bytes.fromhex('4489442420')
     u.emu_start(base+start,base+end,count=10000)
     expected_raw=bytearray(raw)
     if used<8:
      for output in outputs:struct.pack_into('<I',expected_raw,0x194+output*32+used*4,ident)
     #The branch also remembers the proven Hunt stand for animal input137.
     if good==24:struct.pack_into('<I',expected_raw,0x50,ident)
     assert u.mem_read(provider,len(raw))==expected_raw,(filename,item['module'],good,used,'provider rows')
     provider_cases+=1
result=dict(scope=__doc__,cases=cases,passed=len(cases),native_generic_producer_registration_cases=provider_cases,actual_game_runs=0,source_enum_translation_proof=dict(path=str(translation_path.relative_to(WORK)),sha256=hashlib.sha256(translation_path.read_bytes()).hexdigest()),
 fixture_boundaries=['Anlagen ROHSTOFF names translated to audited native IDs in bounded Game definition fixtures','Definition lookup/identity getters return source building IDs','Definition population getter returns0 and unlock-mask getter returns8 for every chain step'])
(HERE/'real_chain_builder_results.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')
print(f'PASS: {len(cases)} complete native recursive builders; original Game property44d getter; three real Food chains; no game run')
