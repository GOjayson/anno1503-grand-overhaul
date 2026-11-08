"""Copy/PE invariants and native prepare-hook CPU checks; no game launch."""
from pathlib import Path
import struct,json
from patch_scene_copy import *
from native_emulate import NativeScene,Q,I,UC_X86_REG_RSP,UC_X86_REG_RCX,UC_X86_REG_RDX,UC_X86_REG_R13,UC_X86_REG_RAX,UC_X86_REG_RIP
import pefile

def main():
 root=Path(__file__).resolve().parents[2];src=(root/'AnnoScene.dll').read_bytes();dst,meta=transform_scene(src)
 old=pefile.PE(data=src);new=pefile.PE(data=dst)
 assert new.OPTIONAL_HEADER.CheckSum==new.generate_checksum()
 assert new.FILE_HEADER.Machine==0x8664 and new.OPTIONAL_HEADER.Magic==0x20b
 assert len(new.DIRECTORY_ENTRY_EXCEPTION)==len(old.DIRECTORY_ENTRY_EXCEPTION)+2
 assert set((e.struct.BeginAddress,e.struct.EndAddress,e.struct.UnwindData) for e in old.DIRECTORY_ENTRY_EXCEPTION)<=set((e.struct.BeginAddress,e.struct.EndAddress,e.struct.UnwindData) for e in new.DIRECTORY_ENTRY_EXCEPTION)
 for a,b in zip(old.sections,new.sections):
  before=bytearray(a.get_data());after=bytearray(b.get_data())
  for at,pre,post in build_code(meta['section']['rva'])[2]:
   if a.VirtualAddress<=at<a.VirtualAddress+a.SizeOfRawData:
    loc=at-a.VirtualAddress;assert before[loc:loc+len(pre)]==pre;before[loc:loc+len(pre)]=post
  assert before==after,a.Name
 assert [(d.dll,[(i.name,i.ordinal,i.address-old.OPTIONAL_HEADER.ImageBase) for i in d.imports]) for d in old.DIRECTORY_ENTRY_IMPORT]==[(d.dll,[(i.name,i.ordinal,i.address-new.OPTIONAL_HEADER.ImageBase) for i in d.imports]) for d in new.DIRECTORY_ENTRY_IMPORT[:-1]]
 try:transform_scene(src[:-1]+bytes([src[-1]^1]));raise AssertionError('Unknown fingerprint accepted')
 except ValueError:pass
 checks=[]
 for base in [0x180000000,0x1a1000000]:
  for accepted in [1,0,-1]:
   e=NativeScene(base,True);events=[]
   def prepare():
    assert e.reg(UC_X86_REG_RCX)==e.obj and e.reg(UC_X86_REG_RDX)==base
    assert e.reg(UC_X86_REG_RSP)%16==8;events.append('prepare');return accepted&0xffffffff
   def native():events.append('c250');return 0x1234
   e.write(base+e.meta['symbols']['prepare_iat'],Q(e.stub(prepare,'prepare')))
   e.write(base+0xc250,b'\xc3');e.callbacks[base+0xc250]=(native,'original_c250_boundary')
   def stop_native():e.u.emu_stop()
   e.callbacks[base+0xe3d8]=(stop_native,'native_join')
   sp=0x40100000;e.u.reg_write(UC_X86_REG_RSP,sp);e.u.reg_write(UC_X86_REG_R13,e.obj)
   e.u.emu_start(base+PREPARE_RVA,base+0xe3d8+1,count=10000)
   assert e.reg(UC_X86_REG_RIP)==base+0xe3d8
   assert e.reg(UC_X86_REG_RSP)==sp and e.reg(UC_X86_REG_R13)==e.obj
   assert events==(['prepare','c250'] if accepted>0 else ['prepare'])
   assert e.reg(UC_X86_REG_RAX)&0xffffffff==(0x1234 if accepted>0 else 0x80004005)
   checks.append(dict(base=hex(base),accepted=accepted,events=events,passed=True))
 result=dict(scope='PE preservation/AMD64 prepare-hook checks; native c250 callback doubled only in prepare-hook branch cases; full c250 runs are native_emulate.py; no actual game run',pe_invariants=True,checks=checks)
 (Path(__file__).parent/'patch_results.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
