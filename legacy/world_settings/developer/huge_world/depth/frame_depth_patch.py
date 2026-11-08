"""Exact-HE size-aware depth normalization for the existing Food Frame overlay.

Two leaf helpers replace two8-byte scalar constant loads. Each camera-linked
2048-square World receives1/5200; every other size/null World gets the original
1/2600 scalar. Screen axes, fixed.5 cached-depth bias and all Food hooks stay.
All output files are caller-owned copies; this module does not write files.
"""
from pathlib import Path
import hashlib,json,struct

ACCEPTED={
 '046b5ad6f351dfe867ed38ce29fb50a594485b43a32ee90adadc48e850466baf':'food_original',
 'dfe71e26feb210bb1c400c338d338a71b1b3026c1e9b2e1ddf06a6378a1d5f86':'world_overlay166',
}
CAVE=0x9d450;MAIN_ENTRY=CAVE;SECONDARY_ENTRY=0x9d460;COMMON=0x9d470;HUGE_CONSTANT=0x9d4b0;CAVE_END=0x9d4b4
ORIGINAL_CONSTANT=0xac30c
SOURCE_LOADS={0x8f176:bytes.fromhex('f30f10058ed10100'),0x1ccac:bytes.fromhex('f30f100558f60800')}


def sha(b):return hashlib.sha256(b).hexdigest()
def require(ok,message):
 if not ok:raise ValueError(message)


def pe_layout(blob):
 nt=struct.unpack_from('<I',blob,0x3c)[0];require(blob[:2]==b'MZ'and blob[nt:nt+4]==b'PE\0\0','Invalid PE')
 require(struct.unpack_from('<H',blob,nt+4)[0]==0x8664 and struct.unpack_from('<H',blob,nt+24)[0]==0x20b,'AMD64 PE32+ required')
 count=struct.unpack_from('<H',blob,nt+6)[0];optional=struct.unpack_from('<H',blob,nt+20)[0];sections=[]
 for i in range(count):
  p=nt+24+optional+i*40;name=blob[p:p+8].rstrip(b'\0').decode();vs,va,raw,offset=struct.unpack_from('<IIII',blob,p+8)
  sections.append(dict(name=name,virtual_size=vs,rva=va,raw_size=raw,file_offset=offset,header_offset=p,flags=struct.unpack_from('<I',blob,p+36)[0]))
 def rva_offset(rva):
  for s in sections:
   if s['rva']<=rva<s['rva']+s['raw_size']:return s['file_offset']+rva-s['rva']
  raise ValueError('RVA outside raw sections')
 return sections,rva_offset


def code_and_edits():
 code=bytearray(b'\x90'*(CAVE_END-CAVE));instructions=[]
 def emit(at,b):
  require(CAVE<=at and at+len(b)<=CAVE_END,'Helper leaves bounded cave');code[at-CAVE:at-CAVE+len(b)]=b;instructions.append((at,b));return at+len(b)
 def jump8(at,target):return emit(at,b'\xeb'+struct.pack('<b',target-at-2))
 # XMM0 is the original replaced instruction's destination. Save volatileR11
 # there while inspecting World, then restoreR11 before loading the scalar.
 p=emit(MAIN_ENTRY,bytes.fromhex('66490f6ec3'));p=emit(p,bytes.fromhex('4c8b9b90fef3ff'));jump8(p,COMMON)
 p=emit(SECONDARY_ENTRY,bytes.fromhex('66490f6ec3'));p=emit(p,bytes.fromhex('4c8b5f18'));jump8(p,COMMON)
 p=emit(COMMON,bytes.fromhex('4d85db'));null_branch=p;p=emit(p,b'\x74\0')
 p=emit(p,bytes.fromhex('4181bbd801000000080000'));width_branch=p;p=emit(p,b'\x75\0')
 p=emit(p,bytes.fromhex('4181bbdc01000000080000'));height_branch=p;p=emit(p,b'\x75\0')
 p=emit(p,bytes.fromhex('66490f7ec3'))
 p=emit(p,bytes.fromhex('f30f1005')+struct.pack('<i',HUGE_CONSTANT-(p+8)));p=emit(p,b'\xc3')
 fallback=p;p=emit(p,bytes.fromhex('66490f7ec3'));p=emit(p,bytes.fromhex('f30f1005')+struct.pack('<i',ORIGINAL_CONSTANT-(p+8)));p=emit(p,b'\xc3')
 require(p<=HUGE_CONSTANT,'Code overlaps scalar')
 for at,opcode in[(null_branch,0x74),(width_branch,0x75),(height_branch,0x75)]:
  data=bytes([opcode])+struct.pack('<b',fallback-at-2);code[at-CAVE:at-CAVE+2]=data
  instructions=[(a,data if a==at else b)for a,b in instructions]
 constant=struct.pack('<f',1./5200.);code[HUGE_CONSTANT-CAVE:HUGE_CONSTANT-CAVE+4]=constant
 # Cover zero-to-NOP alignment bytes as explicit guarded regions too. Keeping
 # cave code before entry calls makes installation/rollback ordering safe.
 covered=set();regions=[]
 for at,b in sorted(instructions):covered.update(range(at,at+len(b)));regions.append(dict(rva=at,before=bytes(len(b)).hex(),after=b.hex(),category='huge_depth_leaf_instruction'))
 for at in range(CAVE,HUGE_CONSTANT):
  if at not in covered:regions.append(dict(rva=at,before='00',after='90',category='huge_depth_leaf_padding'))
 regions.append(dict(rva=HUGE_CONSTANT,before='00000000',after=constant.hex(),category='huge_depth_scalar'))
 regions.sort(key=lambda e:e['rva'])
 # Coalesce only complete instructions/padding, never cut a native instruction.
 combined=[]
 for e in regions:
  if combined and combined[-1]['rva']+len(bytes.fromhex(combined[-1]['after']))==e['rva']and len(bytes.fromhex(combined[-1]['after']))+len(bytes.fromhex(e['after']))<=32 and e['category']!='huge_depth_scalar':
   combined[-1]['before']+=e['before'];combined[-1]['after']+=e['after'];combined[-1]['category']='huge_depth_leaf_code'
  else:combined.append(dict(e))
 for site,entry in[(0x8f176,MAIN_ENTRY),(0x1ccac,SECONDARY_ENTRY)]:
  combined.append(dict(rva=site,before=SOURCE_LOADS[site].hex(),after=(b'\xe8'+struct.pack('<i',entry-site-5)+b'\x90'*3).hex(),category='huge_depth_guarded_load_call'))
 return bytes(code),combined


def runtime_depth_edits():
 """Common source/copy edits; leaf code first, entry calls last. NoPE headers."""
 return code_and_edits()[1]


def transform_frame_depth(blob):
 source_sha=sha(blob);require(source_sha in ACCEPTED,'Unsupported full Food Frame fingerprint; partial/unknown profiles are rejected')
 sections,offset=pe_layout(blob);text=next(s for s in sections if s['name']=='.text')
 require(text['rva']==0x1000 and text['virtual_size']==0x9c44c and text['raw_size']==0x9c600 and text['flags']==0x60000020,'Unexpected Frame text padding layout')
 require(CAVE//4096==(text['rva']+text['virtual_size']-1)//4096 and CAVE_END<=text['rva']+text['raw_size'],'Cave must stay in original final committed executable page')
 require(blob[offset(CAVE):offset(CAVE)+CAVE_END-CAVE]==bytes(CAVE_END-CAVE),'Cave is not original zero padding')
 require(blob[offset(ORIGINAL_CONSTANT):offset(ORIGINAL_CONSTANT)+4]==struct.pack('<f',1./2600.),'Native scalar differs')
 out=bytearray(blob);edits=runtime_depth_edits()
 for e in edits:
  at=offset(e['rva']);before=bytes.fromhex(e['before']);after=bytes.fromhex(e['after']);require(out[at:at+len(before)]==before,'Exact depth preimage differs');out[at:at+len(after)]=after
 # Declare code in the copied disk image. Original in-memory PE already maps
 # this same final page as RX; the header change is not a live runtime edit.
 header=text['header_offset']+8;old=struct.pack('<I',text['virtual_size']);new=struct.pack('<I',CAVE_END-text['rva'])
 require(out[header:header+4]==old,'Text header preimage differs');out[header:header+4]=new
 result=bytes(out);require(len(result)==len(blob),'Image length changed')
 manifest=dict(schema=1,module='AnnoFrame.dll',profile='history-amd64-size-aware-world-depth-v1',source_profile=ACCEPTED[source_sha],source_sha256=source_sha,output_sha256=sha(result),
  runtime_edits=edits,runtime_edit_count=len(edits),disk_only_metadata_edits=[dict(file_offset=header,rva=header,before=old.hex(),after=new.hex(),category='declare_existing_page_depth_code')],
  helper_range=[CAVE,CAVE_END],helper_entry_rvas=[MAIN_ENTRY,SECONDARY_ENTRY],original_text_virtual_end=text['rva']+text['virtual_size'],original_text_last_page=[CAVE&~4095,(CAVE&~4095)+4096],
  image_length_unchanged=True,original_scalar_preserved=True,null_or_non2048_world_uses_exact_original_scalar=True,huge_scalar=1./5200.,
  helper_stack_adjustment_bytes=0,helper_registers_preserved_except_original_xmm0_destination=True,flags_changed_only_at_two_dead_flag_sites=True,
  original_runtime_function_and_unwind_tables_unchanged=True,helper_windows_unwind_classification='leaf: no stack adjustment/nonvolatile changes/calls; return address remains at current RSP',
  runtime_edit_install_order='leaf code+scalar before callsites; rollback reverse removes calls first',game_or_process_modified=False)
 return result,manifest
