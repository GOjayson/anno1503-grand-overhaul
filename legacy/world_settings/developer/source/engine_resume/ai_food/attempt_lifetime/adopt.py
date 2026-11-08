"""Preserve b497 inputs, then adopt the separately tested lifetime sources."""
from pathlib import Path
import hashlib,json,shutil
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[2];DEV=WORK/'runtime_dev3';PRIVATE=HERE.parent/'experiment_runtime'
manifest=json.loads((HERE/'candidate_sources.json').read_text());build=json.loads((DEV/'build_result.json').read_text())
assert build['sha256']=='b49757850043992ef7cc5209eedc0838fcfc0a465b54a04c4b67f9798b04ba0c'
assert hashlib.sha256((DEV/'AnnoWorldSettings.dll').read_bytes()).hexdigest()==build['sha256']
history=DEV/'history/b4975785_before_attempt';history.mkdir(parents=True,exist_ok=True)
files=[DEV/name for name in ['AnnoWorldSettings.dll','AnnoWorldSettings.pdb','WorldSettings.lib','build_result.json','runtime_verification.json','frame_payload.py','generate_blobs.py','runtime_test_blobs.h','build_runtime.py','verify_runtime.py']]
files += [WORK/name for name in manifest['compiled_sources_unchanged']]
files += [DEV/'review'/name for name in ['review_frame.py','review_blobs.py','frame_review_results.json','blob_review_results.json']]
files += [PRIVATE/name for name in ['test_profiles.py','test_status_next.py','test_combined_contract.py']]
saved={}
for source in files:
 relative=source.relative_to(WORK);data=source.read_bytes();target=history/'source'/relative
 target.parent.mkdir(parents=True,exist_ok=True)
 if target.exists():assert target.read_bytes()==data,(target,'existing history differs')
 else:target.write_bytes(data)
 saved[str(relative)]=hashlib.sha256(data).hexdigest()
archive=history/'archive.json';record=dict(runtime_sha256=build['sha256'],files=saved)
if archive.exists():assert json.loads(archive.read_text())==record
else:archive.write_text(json.dumps(record,indent=2)+'\n','utf-8')
for relative,expected in manifest['compiled_sources_unchanged'].items():assert hashlib.sha256((WORK/relative).read_bytes()).hexdigest()==expected
for source_name,target in [('world_ai.c.candidate',PRIVATE/'world_ai.c'),('world_ai.h.candidate',PRIVATE/'world_ai.h'),('world_factory.c.candidate',WORK/'world_factory.c')]:
 data=(HERE/source_name).read_bytes();assert hashlib.sha256(data).hexdigest()==manifest['candidate_sha256'][source_name];target.write_bytes(data)
shutil.copyfile(HERE/'attempt_bridge.py',PRIVATE/'attempt_bridge.py')
print(json.dumps(dict(history=str(history),adopted_source_files=3,bridge_builder_copied=True,runtime_rebuilt=False,package_or_game_copy_changed=False)))
