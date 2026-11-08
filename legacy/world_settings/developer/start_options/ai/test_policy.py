"""Actual AMD64 AI SPEZFLAG setter preservation; war gating is tested centrally.

Private instruction emulation only. See test_world_policy.py for the combined
all-caller war policy matrix; no game process is started.
"""
from pathlib import Path
import hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'WorldSettings_Work/engine_audit'));from audit import Module
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64
from unicorn.x86_const import *
manifest=json.loads((HERE/'candidate_manifest.json').read_text());cases=[]
for item in manifest['payloads']:
 m=Module(str(HERE/item['output']));assert hashlib.sha256(m.data).hexdigest()==item['sha256']
 for base in [0x180000000,0x280000000]:
  u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,(len(m.image)+4095)&~4095);u.mem_write(base,m.image)
  u.mem_map(0x31000000,0x10000);u.mem_map(0x32000000,0x10000);u.mem_map(0x33000000,0x1000)
  controller=0x32002000;record=0x32006000
  setter=0x6090 if item['module']=='CompLogic.dll' else 0x4260
  def put(p,n):u.mem_write(p,struct.pack('<I',n))
  def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
  def setword(value):
   put(record+0x18,value);sp=0x31008008;u.mem_write(sp,struct.pack('<Q',0x33000000))
   for r,v in [(UC_X86_REG_RSP,sp),(UC_X86_REG_RCX,controller),(UC_X86_REG_RDX,29),(UC_X86_REG_R8,record)]:u.reg_write(r,v)
   u.emu_start(base+setter,0x33000000,count=10000);assert u.reg_read(UC_X86_REG_RIP)==0x33000000 and u.reg_read(UC_X86_REG_RAX)==1
  put(controller+0xa4c,12)
  for mode in range(4):
   flags=0x5753fc0f|(mode<<8)
   for value in [0,4,8,255]:
    put(controller+0xab8,flags);setword(value);assert word(controller+0xab8)==(flags&0xffffff00)|value
    cases.append(dict(module=item['module'],image_base=hex(base),mode=mode,native_update=value,preserved=True))
   restored=0x57531c07|(mode<<8);setword(restored);assert word(controller+0xab8)==restored
  for actor,flags in [(12,0),(8,0x57530000),(11,0x57530000),(15,0x57530000),(16,0x57530000)]:
   put(controller+0xa4c,actor);put(controller+0xab8,flags);setword(0xabcdef01);assert word(controller+0xab8)==0xabcdef01
result=dict(scope=__doc__,matrix_cases=len(cases),cases=cases,actual_game_runs=0,passed=True)
(HERE/'policy_test_results.json').write_text(json.dumps(result,indent=2)+'\n','utf-8');print(json.dumps(dict(passed=True,matrix_cases=len(cases),actual_game_runs=0),indent=2))
