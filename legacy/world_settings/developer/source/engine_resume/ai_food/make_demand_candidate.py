"""Wire the original AI demand evaluator to18 explicit consumers, on copies.

Builds on make_pending_candidate.py outputs. This is still an incomplete AI
candidate: no game installation, process loading or opponent enabling occurs.
The new tail retains the native demand arithmetic and shared Food Mod data.
"""
from pathlib import Path
import ctypes as C,hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[1];ROOT=WORK.parent
sys.path.insert(0,str(WORK/'engine_audit'));sys.path.insert(0,str(ROOT/'anno1503_food_mod/developer'))
from audit import Module
from pe_builder import checksum
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64
from unicorn.x86_const import *
def align(n,a):return (n+a-1)&-a
class Code:
 def __init__(self,rva):self.rva=rva;self.bytes=bytearray();self.labels={};self.fixups=[]
 def add(self,value):self.bytes.extend(bytes.fromhex(value) if isinstance(value,str) else value)
 def mark(self,name):self.labels[name]=self.rva+len(self.bytes)
 def branch(self,opcode,target):
  self.add(opcode);at=len(self.bytes);self.add(bytes(4));self.fixups.append((at,target))
 def finish(self):
  for at,target in self.fixups:
   dest=self.labels[target] if isinstance(target,str) else target
   struct.pack_into('<i',self.bytes,at,dest-self.rva-at-4)
  return bytes(self.bytes)
def demand_tail(rva,start,end):
 c=Code(rva)
 c.add('4183fc28');c.branch('0f84','to24')
 c.add('4183fc19');c.branch('0f84','to45')
 c.add('4183fc2d');c.branch('0f84','exit')
 c.add('41ffc449ffc74883c55c');c.branch('e9',start)
 c.mark('to24');c.add('41bc1800000041bf1b0000004881edc0050000');c.branch('e9',start)
 c.mark('to45');c.add('41bc2d00000041bf300000004881c530070000');c.branch('e9',start)
 c.mark('exit');c.branch('e9',end)
 return c.finish()
def primary_unwind_parent(m,rva):
 entries=[(x.struct.BeginAddress,x.struct.EndAddress,x.struct.UnwindData) for x in m.pe.DIRECTORY_ENTRY_EXCEPTION]
 entry=next(x for x in entries if x[0]<=rva<x[1]);seen=set()
 while True:
  assert entry not in seen;seen.add(entry);at=entry[2]
  version_flags,prolog,count,frame=m.image[at:at+4]
  assert version_flags&7==1
  if not (version_flags>>3)&4:return entry,entries
  entry=struct.unpack_from('<III',m.image,at+align(4+count*2,4))

pending=json.loads((HERE/'pending_candidate_manifest.json').read_text())
ctest=json.loads((HERE/'test_results.json').read_text());helper=HERE/'_build/AnnoAIFoodCandidate.dll'
assert hashlib.sha256(helper.read_bytes()).hexdigest()==ctest['candidate_dll_sha256']
dll=C.CDLL(str(helper))
class Demand(C.Structure):_fields_=[('demand',C.c_float),('negative',C.c_float),('stock',C.c_float)]
evaluate=dll.AIFEvaluateDemand;evaluate.argtypes=[C.c_void_p,C.POINTER(C.c_int32),C.c_uint32,C.c_uint32,C.c_int32,C.POINTER(Demand)];evaluate.restype=C.c_int32
reports=[];cases=0;comparisons=0
for item in pending['modules']:
 source=HERE/item['output'];assert hashlib.sha256(source.read_bytes()).hexdigest()==item['output_sha256']
 m=Module(str(source));name=item['module']
 evaluator,loop,hook,exit=(0x582e5,0x58322,0x583ed,0x58401) if name=='CompLogic.dll' else (0x55845,0x55882,0x5594d,0x55961)
 expected=bytes.fromhex('41ffc449ffc74883c55c4183fc280f8e21ffffff');assert m.image[hook:exit]==expected
 parent,entries=primary_unwind_parent(m,hook)
 data=bytearray(m.data);pe=m.pe.DOS_HEADER.e_lfanew;opt=pe+24;count=m.pe.FILE_HEADER.NumberOfSections
 table=opt+m.pe.FILE_HEADER.SizeOfOptionalHeader;header_at=table+count*40
 assert header_at+40<=min(s.PointerToRawData for s in m.pe.sections) and data[header_at:header_at+40]==bytes(40)
 rva=align(max(s.VirtualAddress+max(s.Misc_VirtualSize,s.SizeOfRawData) for s in m.pe.sections),m.pe.OPTIONAL_HEADER.SectionAlignment)
 raw=align(len(data),m.pe.OPTIONAL_HEADER.FileAlignment);code=demand_tail(rva,loop,exit);payload=bytearray(code)
 payload+=bytes(align(len(payload),4)-len(payload));unwind=rva+len(payload)
 payload+=bytes.fromhex('21000000')+struct.pack('<III',*parent)
 payload+=bytes(align(len(payload),4)-len(payload));pdata=rva+len(payload)
 newentries=sorted(entries+[(rva,rva+len(code),unwind)])
 assert all(a[1]<=b[0] for a,b in zip(newentries,newentries[1:]))
 payload+=b''.join(struct.pack('<III',*entry) for entry in newentries)
 at=m.pe.get_offset_from_rva(hook);patch=b'\xe9'+struct.pack('<i',rva-hook-5)+b'\x90'*(exit-hook-5)
 data[at:at+len(patch)]=patch
 rawsize=align(len(payload),m.pe.OPTIONAL_HEADER.FileAlignment)
 data[header_at:header_at+40]=struct.pack('<8sIIIIIIHHI',b'.aifneed',len(payload),rva,rawsize,raw,0,0,0,0,0x60000020)
 struct.pack_into('<H',data,pe+6,count+1);struct.pack_into('<I',data,opt+4,m.pe.OPTIONAL_HEADER.SizeOfCode+rawsize)
 struct.pack_into('<I',data,opt+56,align(rva+len(payload),m.pe.OPTIONAL_HEADER.SectionAlignment))
 struct.pack_into('<II',data,opt+112+3*8,pdata,len(newentries)*12)
 data+=bytes(raw-len(data))+payload+bytes(rawsize-len(payload));struct.pack_into('<I',data,opt+64,checksum(data))
 path=HERE/'_build'/(Path(name).stem+'.demand_candidate.dll');path.write_bytes(data);candidate=Module(str(path))
 goods=list(range(26,41))+[24,25,45];profiles=bytearray(5*0x120);counts=[0,23,65,131,400]
 for level in range(5):
  for index,good in enumerate(goods,1):
   profiles[level*0x120+good+3]=index;struct.pack_into('<H',profiles,level*0x120+0x66+index*4,(index*7+level*3)%137)
 for base in [0x180000000,0x280000000]:
  for highest in range(5):
   u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,(len(candidate.image)+4095)&~4095);u.mem_write(base,candidate.image)
   u.mem_map(0x31000000,0x10000);u.mem_map(0x32000000,0x20000);u.mem_map(0x33000000,0x1000)
   state=bytearray([0xa5])*(56*0x5c)
   for good in range(56):state[good*0x5c+0x34]=8 if good in goods else 0
   statebase=0x32002000;u.mem_write(statebase,bytes(state));u.mem_write(0x32004000,bytes(profiles))
   city=bytearray(0x400);struct.pack_into('<QQ',city,0,0x32009000,0x3200a000)
   for good in goods:struct.pack_into('<i',city,0x200+good*4,good*257)
   u.mem_write(0x32008000,bytes(city));vt=bytearray(0x108)
   struct.pack_into('<Q',vt,0xc0,0x33000100);struct.pack_into('<Q',vt,0x100,0x33000120)
   u.mem_write(0x32009000,bytes(vt));u.mem_write(0x3200a000,struct.pack('<Q5i',0x3200b000,*counts));u.mem_write(0x3200b000,struct.pack('<Q',0x33000140))
   u.mem_write(0x33000100,bytes.fromhex('488b4108c3'));u.mem_write(0x33000120,bytes.fromhex('8b849100020000c3'));u.mem_write(0x33000140,bytes.fromhex('8b449108c3'))
   for reg,value in [(UC_X86_REG_RSP,0x31008008),(UC_X86_REG_RAX,0x32004000),(UC_X86_REG_RBP,statebase+26*0x5c-0x97c),(UC_X86_REG_R13,0x32008000),(UC_X86_REG_RSI,highest)]:u.reg_write(reg,value)
   u.emu_start(base+evaluator,base+exit,count=20000)
   assert u.reg_read(UC_X86_REG_RIP)==base+exit
   pbuf=C.create_string_buffer(bytes(profiles),len(profiles));cbuf=(C.c_int32*5)(*counts)
   expected_state=bytearray(state)
   for good in goods:
    result=Demand();assert evaluate(pbuf,cbuf,highest,good,good*257,C.byref(result))==1
    rawresult=bytes(result);start=good*0x5c
    expected_state[start:start+4]=rawresult[:4];expected_state[start+8:start+16]=rawresult[4:12];comparisons+=1
   assert u.mem_read(statebase,len(state))==expected_state,(name,highest,'unexpected native state write')
   cases+=1
 reports.append(dict(module=name,input_sha256=item['input_sha256'],pending_input_sha256=item['output_sha256'],
  output=str(path.relative_to(HERE)),output_sha256=hashlib.sha256(data).hexdigest(),
  demand_hook_rva=hex(hook),before=expected.hex(),after=patch.hex(),tail_rva=hex(rva),tail_bytes=code.hex(),
  chained_unwind_parent=[hex(x) for x in parent],consumer_order=goods))
 assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==item['input_sha256']
result=dict(scope=__doc__,modules=reports,native_patched_loop_cases=cases,good_metric_comparisons=comparisons,
 all_unselected_state_bytes_preserved=True,actual_game_runs=0,installed_hooks=0,
 status='WIRED DEMAND + NODE LIFECYCLE CANDIDATE; market and producer scheduling integration remains incomplete')
(HERE/'demand_candidate_manifest.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['modules','scope']},indent=2))
