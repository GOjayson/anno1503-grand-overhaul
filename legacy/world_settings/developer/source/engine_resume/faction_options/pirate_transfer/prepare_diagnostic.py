"""Prepare, but do not install, a more specific loaded-owner diagnostic."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[2]
source=WORK/'engine_resume/ai_food/experiment_runtime/validated_world.inc'
before=source.read_bytes();text=before.decode()
old='if(type!=14)WS_CERT_FAIL("A template settlement was not transferred to an enabled native player.");'
new='''if(type!=14){
    if(error&&cap){snprintf(error,cap,"Loaded settlement owner rejected. island=%u slot=%u type=%u culture=%u expectedCultures=0x%x expectedFactions=0x%x.",id,slot,type,nativeCulture,p->cultures,wsTemplateFaction(&wsTemplates[p->templateIndex]));error[cap-1]=0;}
    return 0;
   }'''
assert text.count(old)==1
output=HERE/'validated_world.inc.next';output.write_text(text.replace(old,new))
assert source.read_bytes()==before
result=dict(scope=__doc__,source=str(source.relative_to(WORK)),source_sha256=hashlib.sha256(before).hexdigest(),next_include_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),installed=False,game_runs=0)
(HERE/'diagnostic_manifest.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
