"""Promote tested status copies after the prior game process is closed."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent
manifest=json.loads((HERE/'status_next_sources.json').read_text())
promoted={}
for name,expected in manifest['mapped_source_sha256'].items():
 target=HERE/name;data=target.read_bytes();assert hashlib.sha256(data).hexdigest()==expected
 backup=HERE/(name+'.before_status.'+expected[:12])
 if backup.exists():assert backup.read_bytes()==data
 else:backup.write_bytes(data)
 nextfile=HERE/(name+'.next');nextdata=nextfile.read_bytes()
 assert hashlib.sha256(nextdata).hexdigest()==manifest['next_sha256'][nextfile.name]
 target.write_bytes(nextdata);promoted[name]=hashlib.sha256(nextdata).hexdigest()
ui=HERE/'WorldSettings.c';text=ui.read_text('utf-8');old='static void start(DialogState*d){\n if(!collect(d))return;'
assert text.count(old)==1
digest=hashlib.sha256(ui.read_bytes()).hexdigest();backup=HERE/(ui.name+'.before_status.'+digest[:12])
if backup.exists():assert backup.read_bytes()==ui.read_bytes()
else:backup.write_bytes(ui.read_bytes())
text=text.replace(old,'static void start(DialogState*d){\n WorldSettingsAIProfileAttemptFinished(0); /* a new Start cannot inherit prior verification */\n if(!collect(d))return;')
ui.write_text(text,'utf-8');promoted[ui.name]=hashlib.sha256(ui.read_bytes()).hexdigest()
(HERE/'status_promoted_sources.json').write_text(json.dumps(dict(scope=__doc__,source_sha256=promoted),indent=2)+'\n','utf-8')
print(json.dumps(promoted,indent=2))
