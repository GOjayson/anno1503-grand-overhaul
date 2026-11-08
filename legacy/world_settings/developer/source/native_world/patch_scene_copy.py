"""Fingerprint-bound AMD64 native dummy application hooks, on output copies only.

Appends two imports from AnnoWorldSettings.dll and chained x64 unwind records.
The original Scene resource/crop/village pipeline remains the implementation.
"""
from pathlib import Path
import struct,hashlib,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine_audit'))
from patch_frame_copy import align,pe_info,checksum

EXPECTED_SHA256='f7d0685cf6156ff25c518f2f558863b351d7738280467e48dd585a1fefa9537a'
PREPARE_RVA=0xe3d0
PREPARE_BEFORE=bytes.fromhex('498bcde878deffff')
GUARD_RVA=0xc71d
GUARD_BEFORE=bytes.fromhex('4c8b6c2430')

def build_code(rva):
 code=bytearray();symbols={};fix=[]
 def mark(n):symbols[n]=rva+len(code)
 def emit(b):code.extend(bytes.fromhex(b) if isinstance(b,str) else b)
 def rel(prefix,to):
  emit(prefix);at=len(code);emit(bytes(4));fix.append((at,to))
 mark('prepare');emit('498bcd');rel('488d15',0);rel('ff15','prepare_iat')
 emit('85c0');rel('0f8e','prepare_failed')
 emit('498bcd');rel('e8',0xc250);rel('e9',0xe3d8)
 mark('prepare_failed');emit('b805400080');rel('e9',0xe3d8);mark('prepare_end')
 while len(code)%16:emit('cc')
 mark('resource_guard');rel('ff15','active_iat');emit('85c0');rel('0f84','resource_ok')
 for i in range(7):
  emit('6683bd');emit(struct.pack('<I',0xda+2*i));emit('00');rel('0f85',0xcdd7)
 mark('resource_ok');emit(GUARD_BEFORE);rel('e9',0xc722);mark('resource_guard_end')
 while len(code)%8:emit('00')
 mark('prepare_iat');emit(bytes(8));mark('active_iat');emit(bytes(16))
 mark('new_ilt');emit(bytes(24))
 mark('dll_name');emit(b'AnnoWorldSettings.dll\0')
 while len(code)%2:emit('00')
 mark('prepare_name');emit(b'\0\0WorldSettingsPrepareScene\0')
 while len(code)%2:emit('00')
 mark('active_name');emit(b'\0\0WorldSettingsIsActive\0')
 for at,to in fix:
  dest=symbols[to] if isinstance(to,str) else to
  struct.pack_into('<i',code,at,dest-(rva+at+4))
 for target in ['prepare_iat','new_ilt']:
  struct.pack_into('<QQQ',code,symbols[target]-rva,symbols['prepare_name'],symbols['active_name'],0)
 hooks=[(PREPARE_RVA,PREPARE_BEFORE,b'\xe9'+struct.pack('<i',symbols['prepare']-(PREPARE_RVA+5))+b'\x90'*3),
        (GUARD_RVA,GUARD_BEFORE,b'\xe9'+struct.pack('<i',symbols['resource_guard']-(GUARD_RVA+5)))]
 return bytes(code),symbols,hooks

def transform_scene(original):
 if hashlib.sha256(original).hexdigest()!=EXPECTED_SHA256:raise ValueError('Unrecognized AMD64 History Scene fingerprint; no patch')
 pe,opt,table,sections,off=pe_info(original);sa,fa=struct.unpack_from('<II',original,opt+32)
 if original[table+len(sections)*40:table+(len(sections)+1)*40]!=bytes(40):raise ValueError('No free section header')
 if table+(len(sections)+1)*40>min(s[4] for s in sections):raise ValueError('New section header overlaps data')
 rva=align(max(s[2]+max(s[1],s[3]) for s in sections),sa);raw=align(len(original),fa)
 code,names,hooks=build_code(rva);payload=bytearray(code)
 oldimp,oldimpsize=struct.unpack_from('<II',original,opt+112+8)
 descriptors=[];pos=off(oldimp)
 while original[pos:pos+20]!=bytes(20):
  descriptors.append(original[pos:pos+20]);pos+=20
  if len(descriptors)>128:raise ValueError('Import descriptor count exceeds guard')
 payload+=bytes(align(len(payload),4)-len(payload));newimp=rva+len(payload)
 payload+=b''.join(descriptors)+struct.pack('<IIIII',names['new_ilt'],0,0,names['dll_name'],names['prepare_iat'])+bytes(20)
 oldpdata,oldpdatasize=struct.unpack_from('<II',original,opt+112+3*8)
 if oldpdatasize%12:raise ValueError('Invalid original exception directory')
 entries=[struct.unpack_from('<III',original,off(oldpdata)+i) for i in range(0,oldpdatasize,12)]
 original_entries=entries.copy()
 # The prepare hook is in the already-restored d800 suffix. Chain to the same
 # parent entry as that suffix; the c250 guard chains to its complete frame.
 prepare_parent=struct.unpack_from('<III',original,off(0x4a180)+4)
 application_parent=next(e for e in original_entries if e[0]==0xc250)
 new_entries=[]
 for start,end,parent in [('prepare','prepare_end',prepare_parent),('resource_guard','resource_guard_end',application_parent)]:
  payload+=bytes(align(len(payload),4)-len(payload));unwind=rva+len(payload)
  payload+=bytes.fromhex('21000000')+struct.pack('<III',*parent)
  entry=(names[start],names[end],unwind);entries.append(entry);new_entries.append(entry)
 entries.sort()
 if any(a[1]>b[0] for a,b in zip(entries,entries[1:])):raise ValueError('Overlapping exception records')
 payload+=bytes(align(len(payload),4)-len(payload));pdata=rva+len(payload)
 payload+=b''.join(struct.pack('<III',*e) for e in entries)
 result=bytearray(original)
 for at,before,after in hooks:
  pos=off(at)
  if result[pos:pos+len(before)]!=before:raise ValueError('Hook preimage mismatch')
  result[pos:pos+len(after)]=after
 struct.pack_into('<H',result,pe+6,len(sections)+1)
 struct.pack_into('<I',result,opt+4,struct.unpack_from('<I',original,opt+4)[0]+align(len(payload),fa))
 struct.pack_into('<I',result,opt+56,align(rva+len(payload),sa))
 struct.pack_into('<II',result,opt+112+8,newimp,(len(descriptors)+2)*20)
 struct.pack_into('<II',result,opt+112+3*8,pdata,len(entries)*12)
 result[table+len(sections)*40:table+(len(sections)+1)*40]=struct.pack('<8sIIIIIIHHI',b'.wset\0\0\0',len(payload),rva,align(len(payload),fa),raw,0,0,0,0,0x60000020)
 result+=bytes(raw-len(result))+payload+bytes(align(len(payload),fa)-len(payload))
 struct.pack_into('<I',result,opt+64,checksum(result))
 return bytes(result),dict(input_sha256=EXPECTED_SHA256,output_sha256=hashlib.sha256(result).hexdigest(),symbols=names,section=dict(rva=rva,raw=raw,size=len(payload)),added_imports=['WorldSettingsPrepareScene','WorldSettingsIsActive'],added_runtime_functions=new_entries,original_runtime_function_count=len(original_entries),original_import_descriptor_count=len(descriptors))

if __name__=='__main__':
 if len(sys.argv)!=3:raise SystemExit('Usage: patch_scene_copy.py INPUT_SCENE OUTPUT_COPY')
 src=Path(sys.argv[1]).resolve();dst=Path(sys.argv[2]).resolve();root=Path(__file__).resolve().parents[2]
 if dst==src or dst==root/'AnnoScene.dll':raise SystemExit('Refusing to replace the live/input module; choose output copy')
 result,meta=transform_scene(src.read_bytes());dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(result)
 dst.with_suffix('.bridge.json').write_text(json.dumps(meta,indent=2));print(json.dumps(meta,indent=2))
