"""Guard all tagged ordinary-CPU declarations at the actual native world endpoint.

Transforms only an exact reviewed World Settings overlay copy; never originals.
The leaf gate runs before the native prologue or any relation side effect.
"""
from pathlib import Path
import hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'WorldSettings_Work/engine_audit'));sys.path.insert(0,str(ROOT/'WorldSettings_Work/engine_resume/ai_food'))
from audit import Module
from code_support import Code,Extension,align
HOOK=0xdf460;RESUME=0xdf466
BEFORE=bytes.fromhex('488bc4895010')
LEAF_UNWIND=bytes.fromhex('01000000')
SOURCE=ROOT/'WorldSettings_Work/anno1503_food_world_dev3_cityfix1/native/AnnoWelt.world.dll'
SOURCE_SHA256='7b607854ab6689d16952b075651372aa794274699f3e014c55858b117bafe93b'

from world_policy_bridge import gate,build_world_policy_code

def transform_bytes(data):
 import pefile
 m=Module.__new__(Module);m.name='<reviewed world bytes>';m.data=bytes(data);m.pe=pefile.PE(data=m.data);m.base=m.pe.OPTIONAL_HEADER.ImageBase;m.image=m.pe.get_memory_mapped_image();baseline=SOURCE_SHA256
 assert hashlib.sha256(m.data).hexdigest()==baseline,'World overlay is not the reviewed cityfix1 input'
 assert m.pe.FILE_HEADER.Machine==0x8664 and m.image[HOOK:RESUME]==bytes.fromhex('488bc4895010')
 last=max(m.pe.sections,key=lambda s:s.VirtualAddress);assert last.Name.rstrip(bytes(1))==b'.wsaildr'
 ext=Extension.__new__(Extension);ext.m=m;ext.last=last;ext.rva=align(last.VirtualAddress+max(last.Misc_VirtualSize,last.SizeOfRawData),16);ext.raw=last.PointerToRawData+ext.rva-last.VirtualAddress;ext.payload=bytearray();ext.functions=[];ext.edits=[]
 start=ext.function('central_tagged_cpu_declaration_gate',HOOK,gate);ext.jump(HOOK,RESUME,start)
 raw=bytearray(ext.finish(lambda data:__import__('pefile').PE(data=bytes(data)).generate_checksum()))
 # Entry occurs before the original prologue: standalone leaf unwind info,
 # not the parent chain which would assume its pushes already happened.
 f=ext.functions[0];uw=m.pe.get_offset_from_rva(last.VirtualAddress)+(f['unwind']-last.VirtualAddress)
 raw[uw:uw+16]=bytes.fromhex('01000000')+bytes(12)
 pe=pefile.PE(data=bytes(raw));struct.pack_into('<I',raw,pe.DOS_HEADER.e_lfanew+24+64,pe.generate_checksum())
 manifest=dict(scope=__doc__,source='WorldSettings_Work/anno1503_food_world_dev3_cityfix1/native/AnnoWelt.world.dll',source_sha256=baseline,output='AnnoWelt.world-policy.dll',sha256=hashlib.sha256(raw).hexdigest(),hook_rva=HOOK,resume_rva=RESUME,gate_rva=start,gate_end=f['end'],unwind_rva=f['unwind'],unwind_kind='standalone leaf before original prologue',edits=[dict(rva=r,preimage=b.hex(),patch=a.hex()) for r,b,a in ext.edits],tag='0x57530000',policy='0 none; 1 every fourth; 2 every second; 3 all; new central type2/state3 only; existing war passes uncounted')
 return bytes(raw),manifest

def transform(source=SOURCE,output=None):
 raw,manifest=transform_bytes(Path(source).read_bytes())
 output=HERE/'AnnoWelt.world-policy.dll' if output is None else Path(output);output.write_bytes(raw)
 manifest['output']=output.name
 (HERE/'welt_policy_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n','utf-8')
 return manifest
if __name__=='__main__':print(json.dumps(transform(),indent=2))
