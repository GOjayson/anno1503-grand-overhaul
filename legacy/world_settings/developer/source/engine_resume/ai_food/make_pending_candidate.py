"""Build isolated, reversible pending-node lifecycle DLL candidates on copies.

These copies enlarge pending nodes and initialize appended records only. They
are NOT a complete food-AI patch and must not be installed or enabled. No live
module, game file, backup or save is written. Native constructors run only in
Unicorn private memory after exact fingerprint/preimage checks.
"""
from pathlib import Path
import hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[1];ROOT=WORK.parent
sys.path.insert(0,str(WORK/'engine_audit'))
sys.path.insert(0,str(ROOT/'anno1503_food_mod/developer'))
from audit import Module
from pe_builder import checksum
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64
from unicorn.x86_const import *
SPEC={
 'CompLogic.dll':dict(sha='7f2c7e818d8c25a0b6c48cda2d21bfa0c4096c5dcd8be91c2ab93d877c22afee',ctor=0x847d0,tail=0x84aef,allocation=0x363a8,deletes=[0x36932,0x2a043,0x86169]),
 'CompLogicClassic.dll':dict(sha='0a7692879e15e8cbaed73ec3b59eaa6419165faaea6d8696cddfd68c92000f22',ctor=0x81340,tail=0x8165f,allocation=0x34b28,deletes=[0x350b2,0x289a3,0x82c49])}
def align(value,boundary):return (value+boundary-1)&-boundary
reports=[];out=HERE/'_build';out.mkdir(exist_ok=True)
for name,s in SPEC.items():
 m=Module(str(ROOT/name));assert hashlib.sha256(m.data).hexdigest()==s['sha']
 assert m.pe.FILE_HEADER.Machine==0x8664 and m.pe.OPTIONAL_HEADER.Magic==0x20b
 data=bytearray(m.data);pe=m.pe.DOS_HEADER.e_lfanew;opt=pe+24
 section_table=opt+m.pe.FILE_HEADER.SizeOfOptionalHeader;nsections=m.pe.FILE_HEADER.NumberOfSections
 header_at=section_table+nsections*40
 assert header_at+40<=min(x.PointerToRawData for x in m.pe.sections)
 assert data[header_at:header_at+40]==bytes(40)
 rva=align(max(x.VirtualAddress+max(x.Misc_VirtualSize,x.SizeOfRawData) for x in m.pe.sections),m.pe.OPTIONAL_HEADER.SectionAlignment)
 raw=align(len(data),m.pe.OPTIONAL_HEADER.FileAlignment)
 # Leaf: replay overwritten store, then zero exactly the appended40 bytes.
 # No stack changes, no nonvolatile-register changes, no absolute addresses.
 code=bytes.fromhex('88414031d2')
 for disp in range(0x340,0x368,8):code+=bytes.fromhex('488991')+struct.pack('<I',disp)
 code+=bytes.fromhex('488bc1c3')
 edits=[]
 def edit(at,before,after):
  file_at=m.pe.get_offset_from_rva(at);assert data[file_at:file_at+len(before)]==before
  assert len(before)==len(after);data[file_at:file_at+len(before)]=after
  edits.append(dict(rva=hex(at),file_offset=file_at,before=before.hex(),after=after.hex()))
 edit(s['allocation'],bytes.fromhex('b940030000'),bytes.fromhex('b968030000'))
 for at in s['deletes']:edit(at,bytes.fromhex('ba40030000'),bytes.fromhex('ba68030000'))
 before=bytes.fromhex('884140488bc1c3')
 edit(s['tail'],before,b'\xe9'+struct.pack('<i',rva-s['tail']-5)+b'\x90\x90')
 raw_size=align(len(code),m.pe.OPTIONAL_HEADER.FileAlignment)
 data[header_at:header_at+40]=struct.pack('<8sIIIIIIHHI',b'.aifnode',len(code),rva,raw_size,raw,0,0,0,0,0x60000020)
 struct.pack_into('<H',data,pe+6,nsections+1)
 struct.pack_into('<I',data,opt+4,m.pe.OPTIONAL_HEADER.SizeOfCode+raw_size)
 struct.pack_into('<I',data,opt+56,align(rva+len(code),m.pe.OPTIONAL_HEADER.SectionAlignment))
 data+=bytes(raw-len(data))+code+bytes(raw_size-len(code))
 struct.pack_into('<I',data,opt+64,checksum(data))
 output=out/(Path(name).stem+'.pending_candidate.dll');output.write_bytes(data)
 candidate=Module(str(output));assert len(candidate.image)>rva+len(code)
 cases=[]
 for base in [0x180000000,0x280000000]:
  results=[]
  for module in [m,candidate]:
   u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,(len(module.image)+4095)&~4095);u.mem_write(base,module.image)
   u.mem_map(0x31000000,0x10000);u.mem_map(0x32000000,0x10000);u.mem_map(0x33000000,0x1000)
   node=0x32002000;u.mem_write(node-16,bytes([0xa5])*(0x368+32));u.mem_write(0x31008008,struct.pack('<Q',0x33000000))
   u.reg_write(UC_X86_REG_RSP,0x31008008);u.reg_write(UC_X86_REG_RCX,node)
   u.emu_start(base+s['ctor'],0x33000000,count=10000)
   assert u.reg_read(UC_X86_REG_RAX)==node
   assert u.mem_read(node-16,16)==bytes([0xa5])*16 and u.mem_read(node+0x368,16)==bytes([0xa5])*16
   results.append(bytes(u.mem_read(node,0x368)))
  assert results[0][:0x340]==results[1][:0x340]
  assert results[0][0x340:]==bytes([0xa5])*40 and results[1][0x340:]==bytes(40)
  cases.append(dict(image_base=hex(base),old_offsets_preserved=True,appended_zero_bytes=40,canaries_intact=True))
 # Restoring all edits and removing the added PE section is exactly the input;
 # the source itself is still the strongest restoration artifact and unchanged.
 assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==s['sha']
 reports.append(dict(module=name,input_sha256=s['sha'],output=str(output.relative_to(HERE)),
  output_sha256=hashlib.sha256(data).hexdigest(),edits=edits,leaf_rva=hex(rva),leaf_bytes=code.hex(),cases=cases))
result=dict(scope=__doc__,modules=reports,actual_game_runs=0,installed_hooks=0,
 status='LIFECYCLE CANDIDATE ONLY; incomplete food AI, do not install',
 unresolved=['consumer loop hooks','market coverage/selection hooks','demand/unlock/production scheduling hooks','loaded-world reconstruction verification','one-AI gameplay and save/reload test'])
(HERE/'pending_candidate_manifest.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')
print(json.dumps(dict(modules=len(reports),native_constructor_cases=sum(len(r['cases']) for r in reports),status=result['status']),indent=2))
