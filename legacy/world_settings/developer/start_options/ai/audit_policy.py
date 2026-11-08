"""Fingerprint-bound static inventory and preserved Food AI byte verification."""
from pathlib import Path
import hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'WorldSettings_Work/engine_audit'))
from audit import Module
from inspect_ai import inventory
SPEC={
 'CompLogic.dll':dict(sha='7f2c7e818d8c25a0b6c48cda2d21bfa0c4096c5dcd8be91c2ab93d877c22afee',helper=0x40770,callers=[0x12c2,0x4eea,0x7f8b,0x8086,0xb08b,0xb137,0x6236e],mutations=[(0x40651,0,3),(0x407f7,2,3),(0x408a4,2,0),(0x408d5,0,3),(0x40983,2,0),(0x40a35,1,3),(0x62231,1,0),(0x62323,0,0),(0x62423,2,1)],reads=[0x6a33,0x6a4d,0x5f5d4,0x8064d],writes=[0x6542,0x6587,0x65a2],island_ctor=0x1bbfd),
 'CompLogicClassic.dll':dict(sha='0a7692879e15e8cbaed73ec3b59eaa6419165faaea6d8696cddfd68c92000f22',helper=0x3dd80,callers=[0x634d,0x6431,0x94cf,0x9563,0x5f57e,0x7bb56],mutations=[(0x3dc61,0,3),(0x3de07,2,3),(0x3deb4,2,0),(0x3dee5,0,3),(0x3df93,2,0),(0x3e045,1,3),(0x5f441,1,0),(0x5f533,0,0),(0x5f633,2,1)],reads=[0x4e03,0x4e1d,0x5c864],writes=[0x48c2,0x4925,0x4960],island_ctor=0x1a55d),
}
# Original-module hash is independently recorded; candidate input is the exact
# approved Food payload and is verified against its own manifest separately.
manifest=json.loads((HERE/'candidate_manifest.json').read_text('utf-8'));results=[]
for name,s in SPEC.items():
 m=Module(str(ROOT/name));assert hashlib.sha256(m.data).hexdigest()==s['sha']
 d=inventory(name);allins=[i for f in d['functions'] for i in f['instructions']]
 callers=[i for i in allins if i['mnemonic'] in ['call','jmp'] and s['helper'] in i['target']]
 assert [i['rva'] for i in callers]==s['callers']
 assert m.image.find(struct.pack('<Q',m.base+s['helper']))==-1 # not address-taken/vtable-dispatched
 calls=[i for i in allins if i['mnemonic'] in ['call','jmp'] and '+ 0x210]' in i['op']]
 assert [i['rva'] for i in calls]==[r for r,_,_ in s['mutations']]
 # No vtable+0x210 is loaded into a register for a separately indirect call.
 assert not [i for i in allins if 0x210 in i['fields'] and i['mnemonic'] in ['mov','lea'] and i['op'].split(', ',1)[0] in ['rax','rbx','rcx','rdx','rsi','rdi','r8','r9','r10','r11','r12','r13','r14','r15'] and 'qword ptr' in i['op'] and not any(v in i['op'] for v in ['[rsp +','[rbp +'])]
 field=[i for i in allins if any(0xab8<=n<=0xabb for n in i['fields'])]
 known=set(s['reads']+s['writes']+[s['island_ctor']])
 other=[i for i in field if i['rva'] not in known]
 assert len(other)==2 and all('[rbp + 0xab8]' in i['op'] and i['mnemonic']=='mov' for i in other) # two large stack-local parser records
 assert next(i for i in allins if i['rva']==s['writes'][0])['mnemonic']=='mov'
 assert all(next(i for i in allins if i['rva']==r)['mnemonic']=='or' for r in s['writes'][1:])
 p=next(p for p in manifest['payloads'] if p['module']==name);source=Module(str(ROOT/p['source']));candidate=Module(str(HERE/p['output']))
 assert hashlib.sha256(source.data).hexdigest()==p['source_sha256'] and hashlib.sha256(candidate.data).hexdigest()==p['sha256']
 changes=[]
 for section in source.pe.sections:
  start=section.VirtualAddress;length=max(section.Misc_VirtualSize,section.SizeOfRawData)
  changes.extend(start+j for j in range(length) if source.image[start+j:start+j+1]!=candidate.image[start+j:start+j+1])
 allowed={r for edit in p['edits'] for r in range(edit['rva'],edit['rva']+len(bytes.fromhex(edit['preimage'])))}
 assert set(changes)<=allowed and len(changes)<=13
 for edit in p['edits']:
  r=edit['rva'];assert source.image[r:r+len(bytes.fromhex(edit['preimage']))]==bytes.fromhex(edit['preimage'])
 results.append(dict(module=name,original_sha256=s['sha'],machine='AMD64 PE32+',food_input_sha256=p['source_sha256'],candidate_sha256=p['sha256'],direct_declaration_callers=[dict(rva=hex(i['rva']),bytes=i['bytes']) for i in callers],address_taken_helper_pointers=0,native_relation_mutations=[dict(rva=hex(r),relation_type=t,state=v,meaning='initiating war' if (t,v)==(2,3) else 'existing native diplomacy retained') for r,t,v in s['mutations']],controller_spezflag_reads=[hex(r) for r in s['reads']],controller_spezflag_writes=[hex(r) for r in s['writes']],other_same_displacement_objects='one CCompInsel constructor and two RBP stack-local parser records; not controller fields',changed_existing_mapped_bytes=[hex(r) for r in changes],preserved_food_code=True))
out=dict(scope=__doc__,results=results,passed=True,actual_game_runs=0)
(HERE/'static_audit_results.json').write_text(json.dumps(out,indent=2)+'\n','utf-8')
print(json.dumps(dict(passed=True,modules=len(results),preserved_food_code=True),indent=2))
