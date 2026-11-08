"""Independent read-only pirate candidate/source safety review.

The source templates remain unchanged. Native flag instructions run only in
Unicorn; there is no game attachment, adoption or initialization mutation.
"""
from pathlib import Path
import hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[3];ROOT=WORK.parent
sys.path[:0]=[str(WORK/'engine_audit'),str(WORK/'world_data')]
from audit import Module
from scene_catalogue import chunks,read_container
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *
catalogue=json.loads((WORK/'engine_resume/faction_options/candidate_sources.json').read_text())
profiles=[]
for item in catalogue['pirate_templates']:
 p=ROOT/item['path'];data=p.read_bytes();assert hashlib.sha256(data).hexdigest()==item['sha256']
 root,trailer=read_container(data)
 players=[c for c in chunks(data,16,root.end) if c.tag=='SPIELER'];assert len(players)==1
 payload=players[0].payload;at=8;fields=[]
 while at<len(payload):
  assert len(payload)-at>=8
  n=struct.unpack_from('<H',payload,at+6)[0];h=8
  if n>=0xff00:h=10;n=((n&255)<<16)|struct.unpack_from('<H',payload,at+8)[0]
  assert n<=len(payload)-at-h
  fields.append((payload[at:at+6].rstrip(b'\0').decode('ascii'),payload[at+h:at+h+n]));at+=h+n
 assert not any(tag=='HEAD' for tag,value in fields)
 assert [value for tag,value in fields if tag=='VOLK']==[b'PIRATEN\0']
 assert [value for tag,value in fields if tag=='ALIAS']==[b'\0']
 assert len(trailer)==60 and b'DUMMYPLAYER\0' in trailer
 profiles.append(dict(path=item['path'],source_sha256=item['sha256'],top_level_fields=[tag for tag,value in fields],top_level_player_HEAD_absent=True,alias_empty=True,trailer_bytes=len(trailer)))
assert len(profiles)==15
m=Module(str(ROOT/'AnnoWelt.dll'));assert hashlib.sha256(m.data).hexdigest()=='ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9'
assert m.pe.FILE_HEADER.Machine==0x8664 and m.pe.OPTIONAL_HEADER.Magic==0x20b
assert m.image[0xcede1:0xcedea]==bytes.fromhex('83f8080f8789000000')
flags=[]
for base in [0x180000000,0x280000000]:
 for loadflag in [0,1]:
  for initial_type in [11,15]:
   u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,0x160000);u.mem_write(base,m.image);u.mem_map(0x40000000,0x10000);u.mem_map(0x41000000,0x10000)
   rbp=0x40004000;player=0x41000000;u.mem_write(rbp+0x20,struct.pack('<H',2));u.mem_write(player+0x9c,struct.pack('<H',initial_type))
   for reg,value in [(UC_X86_REG_RBP,rbp),(UC_X86_REG_R13,player),(UC_X86_REG_R14,loadflag)]:u.reg_write(reg,value)
   def hook(machine,address,size,_):
    if address in [base+0x9bed3,base+0x9c15a]:machine.emu_stop()
   u.hook_add(UC_HOOK_CODE,hook);u.emu_start(base+0x9beb8,base+0x9c15b,count=100)
   actual=struct.unpack('<H',u.mem_read(player+0x9c,2))[0];assert actual==(initial_type if loadflag else 2)
   flags.append(dict(base=hex(base),load_flags=loadflag,initial_player_type=initial_type,synthetic_HEAD_type=2,result_type=actual,source_templates_contain_no_player_HEAD=True))
manual=WORK/'engine_resume/faction_options/pirate_transfer/pirate_finalize.inc.candidate'
report=dict(scope=__doc__,actual_game_runs=0,templates=profiles,native_synthetic_HEAD_flag_cases=flags,manual_candidate_sha256=hashlib.sha256(manual.read_bytes()).hexdigest(),
 manual_candidate_adoption='BLOCKED; prefer data-only alias repair under original factory initialization',
 manual_candidate_findings=[
  'Source owner membership list/table and temporary city references are explicitly checked, but a nonnull old-owner controller is not gated before native Remove virtual20 dispatch.',
  'Source city+470 is not verified equal to source owner before transfer; only the already-owned case checks it.',
  'Native Add120 allocates at a3d60/e46bc after source removal; e46bc has a throwing failure path. The C helper has no exception cleanup for its temporary city reference or exception-to-factory-failure translation.',
  'Existing successful fixture preallocates four empty destination membership vector slots and uses a nonfailing allocator; it does not exercise vector growth or allocation failure.',
  'All 15 source pirate profiles have no top-level player HEAD. Therefore named ALIAS loading does not encounter the HEAD overwrite branch; strict absence checks must remain part of alias preparation.'
 ])
(HERE/'results.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
(HERE/'native.asm').write_text('\n'.join(m.dis(a,b) for a,b in [(0xcedde,0xceeff),(0xcef55,0xcefe0),(0x9beb8,0x9bed3),(0xa3d87,0xa3dfc),(0xe46bc,0xe46f8)]),'utf-8')
print(json.dumps(dict(pirate_source_profiles=len(profiles),top_level_player_HEAD_absent=15,native_synthetic_flag_cases=len(flags),manual_candidate_adopted=False,actual_game_runs=0)))
