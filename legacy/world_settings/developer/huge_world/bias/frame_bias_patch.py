"""EXPERIMENTAL canonical-Frame Huge depth recentering; no file/process writes.

Preserve original1/2600 slopes/height precision. The actual state4 fixed-depth
bias is centered on the2048 World only: .5-1024*(depthX+depthY). Other sizes and
null World retain the exact original.5 load. State6 is deliberately unchanged
pending independent native local-bias invariance/pixel-path verification.
"""
import hashlib,struct

ACCEPTED={
 '046b5ad6f351dfe867ed38ce29fb50a594485b43a32ee90adadc48e850466baf':'food_original',
 'dfe71e26feb210bb1c400c338d338a71b1b3026c1e9b2e1ddf06a6378a1d5f86':'world_overlay166',
}
CAVE=0x9d450;CENTER=0x9d4c0;SIGN=0x9d4d0;END=0x9d4e0
SITES={0x1c3f6:bytes.fromhex('f30f10055aff0800'),0x1c7d0:bytes.fromhex('f30f100580fb0800')};HALF=0xac358


def sha(b):return hashlib.sha256(b).hexdigest()
def require(ok,m):
 if not ok:raise ValueError(m)


def layout(blob):
 nt=struct.unpack_from('<I',blob,0x3c)[0];require(blob[:2]==b'MZ'and blob[nt:nt+4]==b'PE\0\0'and struct.unpack_from('<H',blob,nt+4)[0]==0x8664 and struct.unpack_from('<H',blob,nt+24)[0]==0x20b,'ExactAMD64PE32+required')
 n=struct.unpack_from('<H',blob,nt+6)[0];opt=struct.unpack_from('<H',blob,nt+20)[0];sections=[]
 for i in range(n):
  at=nt+24+opt+i*40;vs,va,raw,offset=struct.unpack_from('<IIII',blob,at+8);sections.append(dict(name=blob[at:at+8].rstrip(b'\0').decode(),rva=va,virtual_size=vs,raw_size=raw,file_offset=offset,header_offset=at,flags=struct.unpack_from('<I',blob,at+36)[0]))
 def offset(rva):
  for s in sections:
   if s['rva']<=rva<s['rva']+s['raw_size']:return s['file_offset']+rva-s['rva']
  raise ValueError('RVA outside source raw image')
 return sections,offset


def runtime_bias_edits():
 b=bytearray(b'\x90'*(END-CAVE));code=[]
 def emit(p,data):b[p-CAVE:p-CAVE+len(data)]=data;code.append((p,data));return p+len(data)
 def mem(p,op,target):return emit(p,bytes.fromhex(op)+struct.pack('<i',target-(p+len(bytes.fromhex(op))+4)))
 p=CAVE;p=emit(p,bytes.fromhex('66490f6ec3'));p=emit(p,bytes.fromhex('4c8b5f18'));p=emit(p,bytes.fromhex('4d85db'));null=p;p=emit(p,b'\x74\0')
 p=emit(p,bytes.fromhex('4181bbd801000000080000'));width=p;p=emit(p,b'\x75\0');p=emit(p,bytes.fromhex('4181bbdc01000000080000'));height=p;p=emit(p,b'\x75\0')
 p=emit(p,bytes.fromhex('66490f7ec3'));p=emit(p,bytes.fromhex('f30f1087a8010c00'));p=emit(p,bytes.fromhex('f30f5887c8010c00'))
 p=mem(p,'f30f5905',CENTER);p=mem(p,'0f5705',SIGN);p=mem(p,'f30f5805',HALF);p=emit(p,b'\xc3')
 fallback=p;p=emit(p,bytes.fromhex('66490f7ec3'));p=mem(p,'f30f1005',HALF);p=emit(p,b'\xc3');require(p<=CENTER,'Code overlaps bounded scalar')
 for at,op in[(null,0x74),(width,0x75),(height,0x75)]:
  replacement=bytes([op])+struct.pack('<b',fallback-at-2);b[at-CAVE:at-CAVE+2]=replacement;code=[(a,replacement if a==at else c)for a,c in code]
 covered={x for at,c in code for x in range(at,at+len(c))};pieces=[dict(rva=at,before=bytes(len(c)).hex(),after=c.hex(),category='huge_centered_depth_leaf_instruction')for at,c in code]
 for at in range(CAVE,CENTER):
  if at not in covered:pieces.append(dict(rva=at,before='00',after='90',category='huge_centered_depth_leaf_padding'))
 pieces.sort(key=lambda e:e['rva']);out=[]
 for e in pieces:
  if out and out[-1]['rva']+len(bytes.fromhex(out[-1]['after']))==e['rva']and len(bytes.fromhex(out[-1]['after']))+len(bytes.fromhex(e['after']))<=32:
   out[-1]['before']+=e['before'];out[-1]['after']+=e['after'];out[-1]['category']='huge_centered_depth_leaf_code'
  else:out.append(dict(e))
 # Keep all padding and both constants explicitly bounded/guarded.
 data=struct.pack('<f',1024.)+bytes(12)+struct.pack('<4I',0x80000000,0,0,0)
 out.append(dict(rva=CENTER,before=bytes(len(data)).hex(),after=data.hex(),category='huge_centered_depth_constants'))
 for site,before in SITES.items():
  out.append(dict(rva=site,before=before.hex(),after=(b'\xe8'+struct.pack('<i',CAVE-site-5)+b'\x90'*3).hex(),category='huge_centered_depth_bias_load'))
 return out


def transform_frame_bias(blob):
 source=sha(blob);require(source in ACCEPTED,'Unsupported full canonical Food Frame source;173/partial/unknown images are rejected')
 sections,offset=layout(blob);text=next(s for s in sections if s['name']=='.text')
 require((text['rva'],text['virtual_size'],text['raw_size'],text['flags'])==(0x1000,0x9c44c,0x9c600,0x60000020),'Unexpected executable padding layout')
 require(CAVE//4096==(text['rva']+text['virtual_size']-1)//4096 and END<=text['rva']+text['raw_size'],'Helper leaves original mapped executable finalpage')
 require(blob[offset(CAVE):offset(CAVE)+END-CAVE]==bytes(END-CAVE),'Canonical code cave is not zero')
 edits=runtime_bias_edits();out=bytearray(blob)
 for e in edits:
  at=offset(e['rva']);old=bytes.fromhex(e['before']);new=bytes.fromhex(e['after']);require(out[at:at+len(old)]==old,'Exact centered-bias preimage differs');out[at:at+len(new)]=new
 h=text['header_offset']+8;old=struct.pack('<I',text['virtual_size']);new=struct.pack('<I',END-text['rva']);require(out[h:h+4]==old,'VirtualSize differs');out[h:h+4]=new
 result=bytes(out);require(len(result)==len(blob),'Image length changed')
 return result,dict(schema=2,status='EXPERIMENTAL_NOT_APPROVED',module='AnnoFrame.dll',profile='history-amd64-world-centered-depth-bias-v1',source_profile=ACCEPTED[source],source_sha256=source,output_sha256=sha(result),
  runtime_edits=edits,runtime_edit_count=len(edits),disk_only_metadata_edits=[dict(rva=h,file_offset=h,before=old.hex(),after=new.hex(),category='declare_existing_page_bias_helper')],helper_range=[CAVE,END],
  original_normalization_and_both_scalar_consumers_unchanged=True,both_state4_bias_loads_redirected=True,state6_native_fixed_bias_unchanged=True,
  Huge_bias_formula='0.5f - 1024.0f*(camera_main_depthX+camera_main_depthY)',legacy_or_null_world_bias='exact native0.5f',
  helper_no_stack_adjustment_or_nonvolatile_changes=True,original_unwind_exception_tables_unchanged=True,actual_repaired_game_verified=False)
