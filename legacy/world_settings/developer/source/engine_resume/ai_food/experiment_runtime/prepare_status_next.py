"""Prepare explicit post-profile success status without editing mapped sources."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent
source=HERE/'world_ai.c';header=HERE/'world_ai.h'
text=source.read_text('utf-8')
def change(old,new):
 global text
 assert text.count(old)==1,(old,text.count(old));text=text.replace(old,new)
change('static char wsProfileError[512];','static char wsProfileError[512];\nstatic volatile LONG wsProfileStatus;\n/* Remote-thread-compatible result:0unverified,1..4verified AIcount+1. */\n__declspec(dllexport) DWORD WINAPI WorldSettingsAIProfileStatus(void *unused){(void)unused;return (DWORD)InterlockedCompareExchange(&wsProfileStatus,0,0);}')
change('void WorldSettingsExpectAIProfiles(int32_t count){wsProfilesExpected=count;wsProfileError[0]=0;}',
 'void WorldSettingsExpectAIProfiles(int32_t count){InterlockedExchange(&wsProfileStatus,0);wsProfilesExpected=count;wsProfileError[0]=0;}')
change('void WorldSettingsAIProfileAttemptFinished(int success){if(!success)wsProfilesExpected=-1;}',
 'void WorldSettingsAIProfileAttemptFinished(int success){if(!success){InterlockedExchange(&wsProfileStatus,0);wsProfilesExpected=-1;}}')
change('int valid=WorldSettingsCheckAIControllers(world,expected,approved,wsProfileError,sizeof wsProfileError);',
 'int valid=WorldSettingsCheckAIControllers(world,expected,approved,wsProfileError,sizeof wsProfileError);\n InterlockedExchange(&wsProfileStatus,valid==1?(LONG)expected+1:0);')
(HERE/'world_ai.c.next').write_text(text,'utf-8')
h=header.read_text('utf-8')
h=h.replace('#include <stdint.h>','#include <stdint.h>\n#ifndef WIN32_LEAN_AND_MEAN\n#define WIN32_LEAN_AND_MEAN\n#endif\n#include <windows.h>')
h=h.replace('__declspec(dllexport) unsigned long WorldSettingsCopyAIProfileError(void*);','__declspec(dllexport) unsigned long WorldSettingsCopyAIProfileError(void*);\n__declspec(dllexport) DWORD WINAPI WorldSettingsAIProfileStatus(void*);')
(HERE/'world_ai.h.next').write_text(h,'utf-8')
result=dict(scope=__doc__,mapped_source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [source,header]},next_sha256={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in ['world_ai.c.next','world_ai.h.next']})
(HERE/'status_next_sources.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')
print(json.dumps(result,indent=2))
