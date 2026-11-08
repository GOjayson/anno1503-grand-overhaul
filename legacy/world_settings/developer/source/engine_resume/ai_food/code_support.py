"""Small AMD64/PE copy builder for the isolated AI experiment candidates."""
import struct
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
def parent_entry(m,rva):
 entries=[(x.struct.BeginAddress,x.struct.EndAddress,x.struct.UnwindData) for x in m.pe.DIRECTORY_ENTRY_EXCEPTION]
 entry=next(x for x in entries if x[0]<=rva<x[1]);seen=set()
 while True:
  assert entry not in seen;seen.add(entry);at=entry[2]
  version_flags,prolog,count,frame=m.image[at:at+4];assert version_flags&7==1
  if not (version_flags>>3)&4:return entry
  entry=struct.unpack_from('<III',m.image,at+align(4+count*2,4))
class Extension:
 def __init__(self,module):
  self.m=module;self.last=max(module.pe.sections,key=lambda s:s.VirtualAddress)
  assert self.last.Name.rstrip(b'\0')==b'.aifneed'
  self.rva=align(self.last.VirtualAddress+max(self.last.Misc_VirtualSize,self.last.SizeOfRawData),16)
  self.raw=self.last.PointerToRawData+self.rva-self.last.VirtualAddress
  assert self.raw>=len(module.data)
  self.payload=bytearray();self.functions=[];self.edits=[]
 def function(self,name,hook,builder):
  self.payload+=b'\xcc'*(align(len(self.payload),16)-len(self.payload))
  start=self.rva+len(self.payload);c=Code(start);builder(c);code=c.finish();self.payload+=code
  self.functions.append(dict(name=name,start=start,end=start+len(code),parent=parent_entry(self.m,hook)))
  return start
 def patch(self,at,before,after):
  assert len(before)==len(after) and self.m.image[at:at+len(before)]==before,(hex(at),'preimage')
  self.edits.append((at,before,after))
 def jump(self,at,end,target):
  length=end-at;assert length>=5
  self.patch(at,self.m.image[at:end],b'\xe9'+struct.pack('<i',target-at-5)+b'\x90'*(length-5))
 def finish(self,checksum):
  m=self.m;entries=[(x.struct.BeginAddress,x.struct.EndAddress,x.struct.UnwindData) for x in m.pe.DIRECTORY_ENTRY_EXCEPTION]
  for f in self.functions:
   self.payload+=bytes(align(len(self.payload),4)-len(self.payload));f['unwind']=self.rva+len(self.payload)
   self.payload+=bytes.fromhex('21000000')+struct.pack('<III',*f['parent'])
   entries.append((f['start'],f['end'],f['unwind']))
  entries.sort();assert all(a[1]<=b[0] for a,b in zip(entries,entries[1:]))
  self.payload+=bytes(align(len(self.payload),4)-len(self.payload));pdata=self.rva+len(self.payload)
  self.payload+=b''.join(struct.pack('<III',*entry) for entry in entries)
  data=bytearray(m.data)
  for at,before,after in self.edits:
   offset=m.pe.get_offset_from_rva(at);assert data[offset:offset+len(before)]==before;data[offset:offset+len(after)]=after
  pe=m.pe.DOS_HEADER.e_lfanew;opt=pe+24;section_at=self.last.get_file_offset()
  virtual_size=self.rva+len(self.payload)-self.last.VirtualAddress
  raw_size=align(virtual_size,m.pe.OPTIONAL_HEADER.FileAlignment)
  struct.pack_into('<I',data,section_at+8,virtual_size);struct.pack_into('<I',data,section_at+16,raw_size)
  struct.pack_into('<I',data,opt+4,m.pe.OPTIONAL_HEADER.SizeOfCode+raw_size-self.last.SizeOfRawData)
  struct.pack_into('<I',data,opt+56,align(self.last.VirtualAddress+virtual_size,m.pe.OPTIONAL_HEADER.SectionAlignment))
  struct.pack_into('<II',data,opt+112+3*8,pdata,len(entries)*12)
  data+=bytes(self.raw-len(data))+self.payload
  data+=bytes(self.last.PointerToRawData+raw_size-len(data));struct.pack_into('<I',data,opt+64,checksum(data))
  return bytes(data)
