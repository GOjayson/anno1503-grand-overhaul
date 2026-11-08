"""Freeze reproducible, private Food-AI DLL copies for a scoped game experiment.

This only writes beneath ai_food/_build/preload. It never installs, loads or
enables AI. Public World Settings must stay at zero until gameplay is verified.
"""
from pathlib import Path
import hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[1];ROOT=WORK.parent
sys.path.insert(0,str(WORK/'engine_audit'));sys.path.insert(0,str(ROOT/'anno1503_food_mod/developer'))
from audit import Module
from pe_builder import checksum
prior=json.loads((HERE/'scoring_candidate_manifest.json').read_text());reports=[]
output=HERE/'_build/preload';output.mkdir(exist_ok=True)
for item in prior['modules']:
 source=ROOT/item['module'];candidate=HERE/item['output'];m=Module(str(candidate));original=Module(str(source))
 assert hashlib.sha256(source.read_bytes()).hexdigest()==item['input_sha256']
 assert hashlib.sha256(candidate.read_bytes()).hexdigest()==item['output_sha256']
 assert m.pe.FILE_HEADER.Machine==0x8664 and m.pe.OPTIONAL_HEADER.Magic==0x20b
 assert m.pe.OPTIONAL_HEADER.AddressOfEntryPoint==original.pe.OPTIONAL_HEADER.AddressOfEntryPoint
 assert m.pe.OPTIONAL_HEADER.DllCharacteristics==original.pe.OPTIONAL_HEADER.DllCharacteristics
 assert m.pe.OPTIONAL_HEADER.SizeOfImage%4096==0
 assert m.pe.OPTIONAL_HEADER.CheckSum==checksum(bytearray(m.data))
 def exports(mod):return [(x.name,x.ordinal,x.address,x.forwarder) for x in mod.pe.DIRECTORY_ENTRY_EXPORT.symbols]
 assert exports(m)==exports(original)
 #Loader-facing directories are retained byte-for-byte at their original RVAs.
 #Only the exception directory intentionally changes to cover appended code.
 for index in [0,1,5,9,10,12]:
  old=original.pe.OPTIONAL_HEADER.DATA_DIRECTORY[index];new=m.pe.OPTIONAL_HEADER.DATA_DIRECTORY[index]
  assert (old.VirtualAddress,old.Size)==(new.VirtualAddress,new.Size)
  assert m.image[old.VirtualAddress:old.VirtualAddress+old.Size]==original.image[old.VirtualAddress:old.VirtualAddress+old.Size]
 entries=[(x.struct.BeginAddress,x.struct.EndAddress,x.struct.UnwindData) for x in m.pe.DIRECTORY_ENTRY_EXCEPTION]
 assert entries==sorted(entries) and all(a[1]<=b[0] for a,b in zip(entries,entries[1:]))
 assert all(0<=a<b<=m.pe.OPTIONAL_HEADER.SizeOfImage and 0<=c<m.pe.OPTIONAL_HEADER.SizeOfImage for a,b,c in entries)
 #Retain the working Food Mod market guard and all human-data files untouched.
 guard=0x86540 if item['module']=='CompLogic.dll' else 0x83010
 guard_bytes=bytes.fromhex('83e81a83f80e770789bc83f0000000c3')
 assert m.image[guard:guard+len(guard_bytes)]==original.image[guard:guard+len(guard_bytes)]==guard_bytes
 dest=output/item['module'];dest.write_bytes(candidate.read_bytes())
 reports.append(dict(module=item['module'],source_sha256=item['input_sha256'],candidate_sha256=item['output_sha256'],
  path=str(dest.relative_to(HERE)),machine='AMD64 PE32+',entrypoint_rva=hex(m.pe.OPTIONAL_HEADER.AddressOfEntryPoint),
  export_count=len(exports(m)),exception_entry_count=len(entries),food_guard_retained=True))
evidence=[]
for filename in ['test_results.json','persistence_results.json','pending_candidate_manifest.json','demand_candidate_manifest.json','market_candidate_manifest.json','state_candidate_manifest.json','scoring_candidate_manifest.json','real_chain_builder_results.json']:
 p=HERE/filename;evidence.append(dict(path=filename,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
result=dict(scope=__doc__,status='PRIVATE EXPERIMENT ONLY; zero positive-AI game runs',modules=reports,evidence=evidence,
 public_ai_count_enabled=False,actual_game_runs=0,installed_original_files_changed=False,
 unchanged_secondary_behavior='Native foreign-inventory/diplomacy aid heuristic602d0/Classic5d540 keeps26..39; it does not schedule own-city production.',
 game_run_required=['Verify full-path preload is reused by actual native basename loader; inspect actual module path/hash','Verify one native CPU placeholder can run and save/reload','Observe AI markets cover all six Food wares without repeated market construction','Observe unlocked hunting/potato/bread/butcher chains and resident full-diet consumption across population unlocks','Verify human Food0.5 gameplay remains intact'])
(HERE/'candidate_manifest.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')
print(json.dumps(result,indent=2))
