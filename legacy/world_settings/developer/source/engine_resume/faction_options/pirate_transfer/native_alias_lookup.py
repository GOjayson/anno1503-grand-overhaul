"""Run the complete original CEB00 SCP-profile owner selector on real fields.

Reads original and copied PIRATEN profile fields. Native sized-field parsing,
culture-name conversion, alias-property access and table selection execute
unchanged at two image bases. File methods, case-insensitive string compare
and the final player Load entry are explicit boundaries. No game is run.
"""
from pathlib import Path
import hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[2];ROOT=WORK.parent
sys.path[:0]=[str(HERE),str(WORK/'_tools'),str(WORK/'engine_audit'),str(WORK/'world_data')]
from alias_templates import fields
from scene_catalogue import chunks,read_container
from audit import Module
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE,UC_HOOK_MEM_INVALID
from unicorn.x86_const import *
W=Module(str(ROOT/'AnnoWelt.dll'));G=Module(str(ROOT/'AnnoGame.dll'))
assert hashlib.sha256(W.data).hexdigest()=='ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9'
assert hashlib.sha256(G.data).hexdigest()=='e6f01d19e8e16e6716c0a6c7d3ba00273c9df493e051b8ba62865ee4b53dfdea'
assert all(m.pe.FILE_HEADER.Machine==0x8664 and m.pe.OPTIONAL_HEADER.Magic==0x20b for m in [W,G])
def image(m,base):
 data=bytearray(m.image)
 for block in m.pe.DIRECTORY_ENTRY_BASERELOC:
  for entry in block.entries:
   if entry.type==10:struct.pack_into('<Q',data,entry.rva,struct.unpack_from('<Q',data,entry.rva)[0]+base-m.base)
   else:assert entry.type==0
 return bytes(data)
def profile(data):
 r,t=read_container(data);parts=[c.payload for c in chunks(data,16,r.end) if c.tag=='SPIELER' and [v for k,at,h,v in fields(c.payload) if k=='VOLK']==[b'PIRATEN\0']];assert len(parts)==1
 assert not any(k=='HEAD' for k,at,h,v in fields(parts[0]))
 return parts[0][8:]
manifest=json.loads((HERE/'alias_manifest.json').read_text());rows=[]
STACK=0x40000000;OBJ=0x41000000;EXT=0x42000000
WORLD=OBJ;TABLE=OBJ+0x8000;GAME=OBJ+0x9000;GAMEVT=OBJ+0xa000;FILE=OBJ+0xb000;FILEVT=OBJ+0xc000;RECT=OBJ+0xd000;COUNT=OBJ+0xe000
for base in [0x180000000,0x280000000]:
 for item in manifest['copies']:
  original=(ROOT/item['source']).read_bytes();copy=(HERE/'alias_payload'/item['copy_relative_path']).read_bytes()
  assert hashlib.sha256(original).hexdigest()==item['source_sha256'] and hashlib.sha256(copy).hexdigest()==item['copy_sha256']
  for label,serialized in [('empty-original-alias',profile(original)),('stock-pirate-alias',profile(copy))]:
   u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,0x160000);u.mem_write(base,image(W,base));gameBase=base+0x2000000;u.mem_map(gameBase,0x30000);u.mem_write(gameBase,image(G,gameBase));u.mem_map(STACK,0x30000);u.mem_map(OBJ,0x10000);u.mem_map(EXT,0x1000)
   def put(at,fmt,*v):u.mem_write(at,struct.pack('<'+fmt,*v))
   def get(at,fmt):return struct.unpack('<'+fmt,u.mem_read(at,struct.calcsize('<'+fmt)))[0]
   def cstring(at):
    data=bytearray()
    for i in range(512):
     b=u.mem_read(at+i,1)
     if b==b'\0':return bytes(data)
     data+=b
    raise AssertionError('unbounded native string')
   put(WORLD+0x210,'Q',TABLE);put(TABLE,'Q',base+0xfdbc0);put(WORLD+0x200,'Q',GAME);put(GAME,'Q',GAMEVT);put(GAMEVT+0x98,'Q',gameBase+0xe3d0)
   players={}
   for id,typ,culture,alias in [(0,11,1,b'HUMAN01\0'),(5,16,12,b'VENEZIA01\0'),(6,15,11,b'PIRAT01\0'),(31,2,1,b'DUMMYPLAYER\0')]:
    p=OBJ+0x1000+id*0x100;players[id]=p;put(p,'Q',base+0xfabe0);put(p+8,'I',id);put(p+0x9c,'HH',typ,culture);u.mem_write(p+0x68,alias);put(TABLE+8+id*8,'Q',p)
   put(FILE,'Q',FILEVT);put(FILEVT+8,'Q',EXT);put(FILEVT+0x10,'Q',EXT+0x10);u.mem_write(EXT,b'\xc3');u.mem_write(EXT+0x10,b'\xc3');u.mem_write(EXT+0x20,b'\xc3');u.mem_write(EXT+0x800,b'\xc3')
   compare=next(W.cs.disasm(W.image[0xceec6:0xceecd],W.base+0xceec6));assert compare.mnemonic=='call';put(base+compare.address+compare.size+compare.disp-W.base,'Q',EXT+0x20)
   pos=[0];loaded=[];last=[]
   def ret(cpu,value):
    rsp=cpu.reg_read(UC_X86_REG_RSP);target=struct.unpack('<Q',cpu.mem_read(rsp,8))[0];cpu.reg_write(UC_X86_REG_RAX,value);cpu.reg_write(UC_X86_REG_RSP,rsp+8);cpu.reg_write(UC_X86_REG_RIP,target)
   def hook(cpu,address,size,user):
    last.append(hex(address-base));last[:]=last[-8:]
    rcx=cpu.reg_read(UC_X86_REG_RCX);rdx=cpu.reg_read(UC_X86_REG_RDX);r8=cpu.reg_read(UC_X86_REG_R8);r9=cpu.reg_read(UC_X86_REG_R9)
    if address==base+0xe58ea:assert r8<=4096;cpu.mem_write(rcx,bytes([rdx&255])*r8);ret(cpu,rcx)
    elif address==EXT:
     assert rcx==FILE and r8<=65536;data=serialized[pos[0]:pos[0]+r8];cpu.mem_write(rdx,data);cpu.mem_write(r9,struct.pack('<I',len(data)));pos[0]+=len(data);ret(cpu,int(len(data)==r8))
    elif address==EXT+0x10:
     assert rcx==FILE and r8==1;delta=struct.unpack('<i',struct.pack('<I',rdx&0xffffffff))[0];pos[0]+=delta;assert 0<=pos[0]<=len(serialized);ret(cpu,pos[0])
    elif address==EXT+0x20:ret(cpu,0 if cstring(rcx).lower()==cstring(rdx).lower() else 1)
    elif address==base+0x9bd20:
     sp=cpu.reg_read(UC_X86_REG_RSP);flags=get(sp+0x28,'I');n=get(sp+0x30,'I');count=get(sp+0x38,'Q')
     id=next(i for i,p in players.items() if p==rcx);assert rdx==FILE and r8==RECT and pos[0]==0 and n==len(serialized)
     loaded.append(dict(id=id,flags=flags,bytes=n,top_level_head_absent=True));put(count,'I',n);pos[0]=n;ret(cpu,1)
   def invalid(cpu,access,address,size,value,user):print('INVALID',hex(address),'recent',last,'profile',label);return False
   u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_MEM_INVALID,invalid)
   rsp=STACK+0x20008;put(rsp,'Q',EXT+0x800);put(rsp+0x28,'I',len(serialized));put(rsp+0x30,'Q',COUNT)
   for reg,value in [(UC_X86_REG_RSP,rsp),(UC_X86_REG_RCX,WORLD),(UC_X86_REG_RDX,FILE),(UC_X86_REG_R8,RECT),(UC_X86_REG_R9,0)]:u.reg_write(reg,value)
   u.emu_start(base+0xceb00,EXT+0x800,count=200000)
   assert len(loaded)==1 and loaded[0]['id']==(0 if label=='empty-original-alias' else 6) and loaded[0]['flags']==(1 if label=='empty-original-alias' else 0),loaded
   assert get(players[6]+0x9c,'H')==15
   rows.append(dict(base=hex(base),source=item['source'],variant=label,selected_player=loaded[0]['id'],load_flags=loaded[0]['flags'],pirate_player_type_preserved=15))
result=dict(scope=__doc__,source_sha256={'AnnoWelt.dll':hashlib.sha256(W.data).hexdigest(),'AnnoGame.dll':hashlib.sha256(G.data).hexdigest()},native_owner_selection_cases=rows,actual_game_runs=0)
(HERE/'native_alias_results.json').write_text(json.dumps(result,indent=2)+'\n');(HERE/'native_alias_lookup.asm').write_text(W.dis(0xceb00,0xcf06d)+'\n\n'+W.dis(0xa29b6,0xa29d6))
print(json.dumps({'native_owner_selection_cases':len(rows),'original_fallback_player':0,'copied_alias_player':6,'top_level_player_head_absent_all_copies':True,'actual_game_runs':0}))
