"""Review exact History/Food Mod vtables and execute unmodified native getters.
No game process is started. Unicorn objects are synthetic buffers, not game data.
"""
from pathlib import Path
import sys,struct,json,hashlib
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE.parent/'engine_audit'))
from audit import Module
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64
from unicorn.x86_const import *
W=Module(str(ROOT/'AnnoWelt.dll'));G=Module(str(ROOT/'AnnoGame.dll'))
EXPECTED={'AnnoWelt.dll':'ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9','AnnoGame.dll':'e6f01d19e8e16e6716c0a6c7d3ba00273c9df493e051b8ba62865ee4b53dfdea'}
for module in [W,G]:
 assert hashlib.sha256(module.data).hexdigest()==EXPECTED[Path(module.name).name], 'Unreviewed binary fingerprint'
 assert module.pe.FILE_HEADER.Machine==0x8664 and module.pe.OPTIONAL_HEADER.Magic==0x20b
roles={
 'world_getters':([0xff1d8,0xff650],{0x148:0xd1a40,0x180:0xd1a80}),
 'island':([0xf2da8,0xf33e8,0xf37a0],{0x190:0x49500,0x238:0x1fa50,0x1f8:0x47980}),
 'occurrence_table':([0xf42f8],{0x28:0x5b340,0x20:0x5b6c0}),
 'occurrence':([0xf4098,0xf41c8,0xf58e8,0xf5a18,0xf5b48,0xf5c78,0xf60a8,0xf6468,0xf65a0,0xf66d0,0xf6808],{0xe8:0x35210,0xb0:0x72430,0xc0:0x19320}),
 'ore':([0xf58e8],{0x118:0x717e0,0xf8:0x718d0}),
 'player':([0xfabe0],{0x98:0xa28e0,0x88:0x8d00}),
 'city':([0xfc678],{0x40:0x8ca0}),
 'player_ship':([0xee000],{0xb0:0x19320,0xc0:0x19340,0x40:0x198d0,0xf8:0x19370}),
 'figure':([0x21038,0x211b0,0x21328],{0x88:0x159e0})}
def invoke(m,base,rva,obj,a=0,b=0,buffer=b''):
 u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,(len(m.image)+4095)&~4095);u.mem_write(base,m.image)
 for at,size in [(0x40000000,0x10000),(0x41000000,0x10000),(0x50000000,0x10000),(0x60000000,0x1000)]:u.mem_map(at,size)
 u.mem_write(0x40000000,bytes(obj));u.mem_write(0x41000000,bytes(buffer) if buffer else b'\0'*256)
 rsp=0x5000f008;u.mem_write(rsp,struct.pack('<Q',0x60000000));u.reg_write(UC_X86_REG_RSP,rsp)
 for reg,val in [(UC_X86_REG_RCX,0x40000000),(UC_X86_REG_RDX,a),(UC_X86_REG_R8,b)]:u.reg_write(reg,val)
 u.emu_start(base+rva,0x60000000,count=10000)
 assert u.reg_read(UC_X86_REG_RIP)==0x60000000
 return u.reg_read(UC_X86_REG_RAX),struct.unpack('<f',int(u.reg_read(UC_X86_REG_XMM0)).to_bytes(16,'little')[:4])[0],bytes(u.mem_read(0x41000000,256))
def main():
 evidence={'scope':__doc__,'fingerprints':{Path(m.name).name:hashlib.sha256(m.data).hexdigest() for m in [W,G]},'vtables':[],'native_cases':[]}
 for role,(tables,methods) in roles.items():
  m=G if role=='figure' else W
  for vt in tables:
   for slot,method in methods.items():
    actual=struct.unpack_from('<Q',m.image,vt+slot)[0]-m.base
    assert actual==method,(role,hex(vt),hex(slot),hex(actual),hex(method))
    evidence['vtables'].append(dict(role=role,module=Path(m.name).name,vt=hex(vt),slot=hex(slot),method=hex(method)))
 names=[]
 for i in range(20):
  ptr=struct.unpack_from('<Q',G.image,0x23c90+i*8)[0]-G.base
  names.append(G.image[ptr:ptr+100].split(b'\0')[0].decode('ascii') if 0<=ptr<len(G.image) else None)
 evidence['native_culture_names']=names
 assert [names[i] for i in [2,4,3,6,5,8,7,9]]==['MAUREN','MONGOLEN','BEDUINEN','AZTEKEN','AFRIKANER','INDIANER','ESKIMOS','SUEDSEE']
 for base in [0x180000000,0x280000000]:
  def case(label,module,rva,obj,a=0,b=0,expected=None,floating=None,payload=None,buffer=b''):
   result=invoke(module,base,rva,obj,a,b,buffer)
   if expected is not None:assert result[0]==expected,(label,result,expected)
   if floating is not None:assert result[1]==floating,(label,result,floating)
   if payload is not None:assert struct.unpack_from('<I',result[2],8)[0]==payload,(label,result,payload)
   evidence['native_cases'].append(dict(base=hex(base),case=label,rva=hex(rva)))
  obj=bytearray(0x800)
  struct.pack_into('<I',obj,0x134,0x1ffff);case('crop getter property11',W,0x49500,obj,11,expected=0x1ffff)
  for climate in range(6):
   obj[0x148]=climate;case('climate getter property7 '+str(climate),W,0x49500,obj,7,expected=climate)
  for enum in range(20):
   struct.pack_into('<H',obj,0x9e,enum);case('player property1c enum'+str(enum),W,0xa28e0,obj,0x1c,0x41000000,expected=1,payload=enum)
  for kind in [0xb,14,0xffff]:
   struct.pack_into('<H',obj,0x9c,kind);case('player property9 type'+str(kind),W,0xa28e0,obj,9,0x41000000,expected=1,payload=kind)
  for number in [0,1,400000,0x7fffffff]:
   struct.pack_into('<I',obj,0x38,number);obj[0x40]=1
   case('remaining quantity includes reserves '+str(number),W,0x717e0,obj,1,expected=number)
  for value in [0,1,255]:
   obj[0x41]=value;case('occurrence disabled flag4 '+str(value),W,0x718d0,obj,4,expected=value)
  struct.pack_into('<f',obj,0x20,50.5);case('occurrence X',W,0x72430,obj,floating=50.5)
  struct.pack_into('<f',obj,0x28,60.5);case('occurrence Y',W,0x19320,obj,floating=60.5)
  struct.pack_into('<f',obj,0x28,566.5);case('ship X',W,0x19320,obj,floating=566.5)
  struct.pack_into('<f',obj,0x30,435.5);case('ship Y',W,0x19340,obj,floating=435.5)
  struct.pack_into('<Q',obj,0x270,0x40000abc);case('ship owner',W,0x198d0,obj,expected=0x40000abc)
  struct.pack_into('<I',obj,8,1502);case('figure1502 identifier',G,0x159e0,obj,expected=1502)
  struct.pack_into('<I',obj,8,0);case('human owner0 identifier',W,0x8d00,obj,expected=0)
  struct.pack_into('<Q',obj,0x208,0x40000abc);struct.pack_into('<Q',obj,0x220,0x40000def)
  case('actual resident table getter+148 reads world+208',W,0xd1a40,obj,expected=0x40000abc)
  case('map getter+180 reads distinct world+220',W,0xd1a80,obj,expected=0x40000def)
  struct.pack_into('<Q',obj,0x28,0x40000def);case('city owner',W,0x8ca0,obj,expected=0x40000def)
  struct.pack_into('<QQ',obj,0x18,0x41000000,0x41000060);case('resident vector size stride32',W,0xc13c0,obj,expected=3)
  vector=bytearray(256)
  for i in range(3):struct.pack_into('<Q',vector,i*32+24,0x40001000+i*256)
  for i in range(3):case('resident vector pointer'+str(i),W,0xc1390,obj,i,expected=0x40001000+i*256,buffer=vector)
 (HERE/'native_evidence.json').write_text(json.dumps(evidence,indent=2))
 (HERE/'native_getters.asm').write_text('\n\n'.join(Path(m.name).name+' '+hex(rva)+'\n'+m.dis(rva) for m,rva in [(W,0x49500),(W,0xa28e0),(W,0x717e0),(W,0x718d0),(W,0xc1390),(W,0xc13c0),(W,0x72430),(W,0x19320),(W,0x19340),(W,0x198d0),(W,0x8ca0),(G,0x159e0)]))
 print(json.dumps({'vtable_method_assertions':len(evidence['vtables']),'original_native_getter_cases':len(evidence['native_cases']),'bases':2,'status':'passed'}))
if __name__=='__main__':main()
