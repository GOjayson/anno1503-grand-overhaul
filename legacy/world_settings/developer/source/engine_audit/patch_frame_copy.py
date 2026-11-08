"""Append the reviewed Start bridge to a COPY of the installed food 0.5 Frame.
Pure stdlib implementation. All pre-existing sections are byte-preserved other
than the exact single-player flag callback hook, PE checksum and mandatory header metadata.
"""
from pathlib import Path
import struct,hashlib,json,sys
from bridge_codegen import build_bridge
EXPECTED_SHA256='046b5ad6f351dfe867ed38ce29fb50a594485b43a32ee90adadc48e850466baf'
def align(x,a):return (x+a-1)&-a
def pe_info(b):
 pe=struct.unpack_from('<I',b,60)[0]
 if b[pe:pe+4]!=b'PE\0\0' or struct.unpack_from('<H',b,pe+4)[0]!=0x8664:raise ValueError('Expected AMD64 PE')
 opt=pe+24
 if struct.unpack_from('<H',b,opt)[0]!=0x20b:raise ValueError('Expected PE32+')
 table=opt+struct.unpack_from('<H',b,pe+20)[0];n=struct.unpack_from('<H',b,pe+6)[0]
 sections=[struct.unpack_from('<8sIIIIIIHHI',b,table+i*40) for i in range(n)]
 def off(rva):return next(raw+rva-va for _,vs,va,rs,raw,*_ in sections if va<=rva<va+rs)
 return pe,opt,table,sections,off
def checksum(b):
 pe=struct.unpack_from('<I',b,60)[0];at=pe+24+64;total=0
 for i in range(0,len(b),2):
  total+=int.from_bytes(b[i:i+2],'little') if not at<=i<at+4 else 0
  total=(total&65535)+(total>>16)
 return ((total&65535)+(total>>16))+len(b)
def transform_frame(original,dll_path='AnnoWorldSettings.dll'):
 if hashlib.sha256(original).hexdigest()!=EXPECTED_SHA256:raise ValueError('Unrecognized Frame fingerprint; no writes')
 pe,opt,table,sections,off=pe_info(original);sa,fa=struct.unpack_from('<II',original,opt+32)
 if original[table+len(sections)*40:table+(len(sections)+1)*40]!=bytes(40):raise ValueError('No empty section header')
 if table+(len(sections)+1)*40>min(s[4] for s in sections):raise ValueError('Header overlaps first section')
 rva=align(max(s[2]+max(s[1],s[3]) for s in sections),sa);raw=align(len(original),fa)
 code,names,hooks,functions=build_bridge(rva,dll_path);payload=bytearray(code)
 oldrva,oldsize=struct.unpack_from('<II',original,opt+112+3*8)
 if oldsize%12:raise ValueError('Malformed runtime function table')
 entries=[struct.unpack_from('<III',original,off(oldrva)+i) for i in range(0,oldsize,12)]
 for start,end,unwind in functions:
  payload+=bytes(align(len(payload),4)-len(payload));urva=rva+len(payload);payload+=unwind;entries.append((start,end,urva))
 entries.sort()
 if any(a[1]>b[0] for a,b in zip(entries,entries[1:])):raise ValueError('Overlapping runtime functions')
 payload+=bytes(align(len(payload),4)-len(payload));pdata=(rva+len(payload),len(entries)*12);payload+=b''.join(struct.pack('<III',*x) for x in entries)
 result=bytearray(original)
 for at,before,after in hooks:
  pos=off(at)
  if result[pos:pos+len(before)]!=before:raise ValueError('Hook preimage mismatch')
  result[pos:pos+len(before)]=after
 struct.pack_into('<H',result,pe+6,len(sections)+1)
 struct.pack_into('<I',result,opt+4,struct.unpack_from('<I',original,opt+4)[0]+align(len(payload),fa))
 struct.pack_into('<I',result,opt+56,align(rva+len(payload),sa))
 struct.pack_into('<II',result,opt+112+3*8,*pdata)
 result[table+len(sections)*40:table+(len(sections)+1)*40]=struct.pack('<8sIIIIIIHHI',b'.wset\0\0\0',len(payload),rva,align(len(payload),fa),raw,0,0,0,0,0x60000020)
 result+=bytes(raw-len(result))+payload+bytes(align(len(payload),fa)-len(payload))
 struct.pack_into('<I',result,opt+64,checksum(result))
 return bytes(result),{'symbols':names,'section':{'rva':rva,'raw':raw,'size':len(payload)},'new_function_count':2,'input_sha256':EXPECTED_SHA256,'output_sha256':hashlib.sha256(result).hexdigest(),'dll_path':dll_path}
if __name__=='__main__':
 if len(sys.argv)!=3:raise SystemExit('Usage: patch_frame_copy.py INPUT_FRAME OUTPUT_COPY')
 src=Path(sys.argv[1]).resolve();dst=Path(sys.argv[2]).resolve();root=Path(__file__).resolve().parents[2]
 if dst==root/'AnnoFrame.dll' or dst==src:raise SystemExit('Refusing to replace live/input Frame; choose an output copy')
 result,info=transform_frame(src.read_bytes());dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(result);dst.with_suffix('.bridge.json').write_text(json.dumps(info,indent=2));print(json.dumps(info,indent=2))

