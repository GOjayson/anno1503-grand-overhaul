"""Independent PE and native-hook metadata review of the private dev3 copy.

Only files in this review directory are written. No game or DLL is loaded.
"""
from pathlib import Path
import hashlib,json,re,struct,sys
HERE=Path(__file__).resolve().parent;DEV=HERE.parent;WORK=DEV.parent;ROOT=WORK.parent
sys.path[:0]=[str(DEV),str(WORK/'_tools'),str(WORK/'engine_audit')]
import pefile
from frame_payload import transform_full_frame3
from audit import Module
from capstone import Cs,CS_ARCH_X86,CS_MODE_64
from capstone.x86_const import X86_OP_MEM,X86_OP_IMM,X86_REG_RIP
source=(ROOT/'AnnoFrame.dll').read_bytes();sourceSha=hashlib.sha256(source).hexdigest();assert sourceSha=='046b5ad6f351dfe867ed38ce29fb50a594485b43a32ee90adadc48e850466baf'
output,metadata=transform_full_frame3(source);old=pefile.PE(data=source);new=pefile.PE(data=output)
assert new.FILE_HEADER.Machine==0x8664 and new.OPTIONAL_HEADER.Magic==0x20b and new.verify_checksum()
assert old.OPTIONAL_HEADER.AddressOfEntryPoint==new.OPTIONAL_HEADER.AddressOfEntryPoint
retained=[]
for index in [0,2,4,5,6,7,8,9,10,11,12,13,14,15]:
 a,b=old.OPTIONAL_HEADER.DATA_DIRECTORY[index],new.OPTIONAL_HEADER.DATA_DIRECTORY[index]
 assert (a.VirtualAddress,a.Size)==(b.VirtualAddress,b.Size),index
 retained.append(index)
oldImage=old.get_memory_mapped_image();newImage=new.get_memory_mapped_image()
hooks=[(0x44bb0,9),(0x55c54,6),(0x43e44,6),(0x55f2e,5),(0x5746b,5)]
assert len(new.sections)==len(old.sections)+3
sectionChecks=[]
for before,after in zip(old.sections,new.sections):
 assert before.__pack__()==after.__pack__(),before.Name
 a=before.VirtualAddress;n=max(before.Misc_VirtualSize,before.SizeOfRawData);expected=bytearray(oldImage[a:a+n])
 changes=[]
 for rva,length in hooks:
  if a<=rva<a+n:
   assert rva+length<=a+n;expected[rva-a:rva-a+length]=newImage[rva:rva+length];changes.append(dict(rva=hex(rva),length=length))
 assert newImage[a:a+n]==expected,(before.Name,'unexpected source section modification')
 sectionChecks.append(dict(name=before.Name.rstrip(b'\0').decode(),source_bytes=n,allowed_hook_changes=changes))
assert sum(len(x['allowed_hook_changes']) for x in sectionChecks)==5
def imports(pe):
 return [(entry.dll.decode(),[(x.name.decode() if x.name else None,x.ordinal,x.address-pe.OPTIONAL_HEADER.ImageBase) for x in entry.imports]) for entry in pe.DIRECTORY_ENTRY_IMPORT]
originalImports=imports(old);newImports=imports(new);assert newImports[:len(originalImports)]==originalImports
extraImports=newImports[len(originalImports):];assert len(extraImports)==2
assert [(x[0],x[1][0][0]) for x in extraImports]==[('AnnoWorldSettings.dll','WorldSettingsCreateScene'),('AnnoWorldSettings.dll','WorldSettingsAfterProfiles')]
assert [x[0] for x in extraImports[1][1]]==['WorldSettingsAfterProfiles','WorldSettingsBeginNativeWorldStart','WorldSettingsEndNativeWorldStart']
for descriptor in new.DIRECTORY_ENTRY_IMPORT:
 for attr in ['OriginalFirstThunk','FirstThunk']:
  rva=getattr(descriptor.struct,attr);assert rva
  for index in range(4096):
   assert rva+index*8+8<=len(newImage)
   entry=struct.unpack_from('<Q',newImage,rva+index*8)[0]
   if not entry:break
   assert entry&0x8000000000000000 or entry+2<len(newImage)
  else:raise AssertionError('unterminated import thunk array')
oldEntries={(x.struct.BeginAddress,x.struct.EndAddress,x.struct.UnwindData) for x in old.DIRECTORY_ENTRY_EXCEPTION}
newEntries=[(x.struct.BeginAddress,x.struct.EndAddress,x.struct.UnwindData) for x in new.DIRECTORY_ENTRY_EXCEPTION]
assert oldEntries.issubset(newEntries);assert all(a[1]<=b[0] for a,b in zip(newEntries,newEntries[1:]))
added=[]
for begin,end,unwind in newEntries:
 if (begin,end,unwind) in oldEntries:continue
 assert 0<begin<end<=len(newImage) and unwind+4<=len(newImage)
 section=next(s for s in new.sections if s.VirtualAddress<=begin and end<=s.VirtualAddress+s.Misc_VirtualSize);assert section.Characteristics&0x20000000
 versionFlags,prolog,count,frame=newImage[unwind:unwind+4];assert versionFlags&7==1 and versionFlags>>3 in [0,4] and prolog<=end-begin
 n=(4+count*2+3)&~3;assert unwind+n<=len(newImage)
 parent=None
 if versionFlags>>3==4:
  parent=struct.unpack_from('<III',newImage,unwind+n);assert parent in oldEntries,'child must chain to an original native function'
 added.append(dict(begin=hex(begin),end=hex(end),unwind=hex(unwind),parent=[hex(x) for x in parent] if parent else None))
assert len(added)==6
# Compare the full PE wrapper instructions against the transient C metadata.
# PE import slots and transient resolved import cells may live at different
# addresses; they must resolve to the same export. Native/local targets must
# retain the same meaning after native-relative relocation.
header=(DEV/'runtime_test_blobs.h').read_text();md=Cs(CS_ARCH_X86,CS_MODE_64);md.detail=True
arrays={name:bytes(int(x,0) for x in re.findall(r'0x[0-9a-fA-F]+|\d+',body)) for name,body in re.findall(r'static const unsigned char (\w+)\[\] = \{(.*?)\};',header)}
iatNames={item.address-new.OPTIONAL_HEADER.ImageBase:item.name.decode() for d in new.DIRECTORY_ENTRY_IMPORT for item in d.imports if item.name}
peBases={'flag':int(added[0]['begin'],16),'factory':int(added[2]['begin'],16),'direct':int(added[3]['begin'],16),'postprofile':int(added[4]['begin'],16),'native_attempt':int(added[5]['begin'],16)}
semanticInstructions=0
for label,base in peBases.items():
 code=arrays[label+'_code'];relocBody=re.search(r'static const WSRelocation '+label+r'_relocs\[\] = \{(.*?)\};',header).group(1);relocs={int(x) for x in re.findall(r'\{(\d+)\}',relocBody)}
 functions=[(int(a),int(b)) for a,b in re.findall(r'\{(\d+),(\d+),\w+,\d+\}',re.search(r'static const WSFunctionMeta '+label+r'_functions\[\] = \{(.*?)\};',header).group(1))]
 imp=re.search(r'static const WSImportCell '+label+r'_imports\[\] = \{(.*?)\};',header);runtimeImports={int(a):b for a,b in re.findall(r'\{(\d+),"([^"]+)"\}',imp.group(1))} if imp else {}
 for start,end in functions:
  transient=list(md.disasm(code[start:end],start));peInstructions=list(md.disasm(newImage[base+start:base+end],base+start));assert len(transient)==len(peInstructions)
  for a,b in zip(transient,peInstructions):
   assert a.mnemonic==b.mnemonic and a.size==b.size and len(a.operands)==len(b.operands)
   aa,bb=bytearray(a.bytes),bytearray(b.bytes)
   for oa,ob in zip(a.operands,b.operands):
    if oa.type==X86_OP_MEM and oa.mem.base==X86_REG_RIP:
     field=a.address+a.disp_offset;ta=a.address+a.size+oa.mem.disp;tb=b.address+b.size+ob.mem.disp;offset=a.disp_offset;n=a.disp_size
    elif oa.type==X86_OP_IMM and a.imm_size==4 and (a.group(1) or a.group(2)):
     field=a.address+a.imm_offset;ta=oa.imm;tb=ob.imm;offset=a.imm_offset;n=a.imm_size
    else:continue
    if ta in runtimeImports:assert iatNames.get(tb)==runtimeImports[ta],(label,hex(a.address),'different import export')
    elif field in relocs:assert tb==ta,(label,hex(a.address),'different native target')
    else:assert tb==base+ta,(label,hex(a.address),'different local target')
    aa[offset:offset+n]=bb[offset:offset+n]=bytes(n)
   assert aa==bb,(label,hex(a.address),'nonrelative wrapper instruction differs')
   semanticInstructions+=1
# Food Mod's guard must survive all private AI code extensions.
guardChecks=[]
for name,rva,sha in [('CompLogic.dll',0x86540,'e247ef8b755354cb5c9b2ff21bf81a5dd25646ee2012ac8204162a54daa72d9d'),('CompLogicClassic.dll',0x83010,'c2e101508bfb5aee0da3d4abd13f3281baccbf4762a26ff3f90f9e1fbc354556')]:
 original=Module(str(ROOT/name));path=WORK/'engine_resume/ai_food/_build/preload'/name;candidate=pefile.PE(str(path));assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
 guard=bytes.fromhex('83e81a83f80e770789bc83f0000000c3');assert original.image[rva:rva+len(guard)]==guard==candidate.get_memory_mapped_image()[rva:rva+len(guard)]
 guardChecks.append(dict(module=name,rva=hex(rva),bytes=guard.hex(),candidate_sha256=sha))
(HERE/'AnnoFrame.dev3.review-copy.dll').write_bytes(output)
result=dict(scope=__doc__,source_sha256=sourceSha,output_sha256=hashlib.sha256(output).hexdigest(),retained_directories=retained,original_sections=sectionChecks,added_imports=extraImports,sorted_runtime_functions=len(newEntries),added_unwind_functions=added,pe_transient_semantic_instructions=semanticInstructions,retained_food_guards=guardChecks,actual_game_runs=0,source_files={str(p.relative_to(WORK)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [DEV/'frame_payload.py',DEV/'runtime_test_blobs.h',WORK/'engine_resume/ai_food/experiment_runtime/postprofile_bridge.py',WORK/'engine_resume/ai_food/experiment_runtime/attempt_bridge.py']})
(HERE/'frame_review_results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['scope','original_sections','retained_food_guards','source_files']},indent=2))
