"""Prepare private-only special-controller activity certificate candidates."""
from pathlib import Path
import hashlib
import json
import shutil

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[1]/"ai_food/experiment_runtime"
OUT = HERE/"special_activity"
OUT.mkdir(exist_ok=True)
sha = lambda data: hashlib.sha256(data).hexdigest()
original = (SOURCE/"world_ai.c").read_bytes()
header = (SOURCE/"world_ai.h").read_bytes()
if sha(original) != "02c6e2565d8c5bf980cd5a9ee9847afe3d1ebdbf890c52bf2522eb2ad145310c":
    raise ValueError("Reviewed lifetime source changed")
if sha(header) != "744608796177629c264747f0e443c7fe317b1a11f76eb5941c2b9f44f596d1b3":
    raise ValueError("Reviewed lifetime header changed")
text = original.decode().replace("\r\n","\n")
changes = {
    "static int wsNativeExpected,wsNativeChecked;": "static int wsNativeExpected,wsNativeChecked;\nstatic uint32_t wsFactionsExpected,wsNativeFactions;",
    "wsNativeActive=wsNativeSequence;wsNativeExpected=wsProfilesExpected>=0;": "wsNativeActive=wsNativeSequence;wsNativeExpected=wsProfilesExpected>=0;wsNativeFactions=wsFactionsExpected;",
    "wsProfilesExpected=-1;wsNativeActive=0;wsNativeExpected=0;wsNativeChecked=0;wsNativeWorld=NULL;": "wsProfilesExpected=-1;wsFactionsExpected=0;wsNativeFactions=0;wsNativeActive=0;wsNativeExpected=0;wsNativeChecked=0;wsNativeWorld=NULL;",
    "void WorldSettingsExpectAIProfiles(int32_t count){InterlockedExchange(&wsProfileStatus,0);wsProfilesExpected=count;wsProfileError[0]=0;}": "void WorldSettingsExpectAIProfiles(int32_t count,uint32_t factions){InterlockedExchange(&wsProfileStatus,0);wsProfilesExpected=count;wsFactionsExpected=factions;wsProfileError[0]=0;}",
    "void WorldSettingsAIProfileAttemptFinished(int success){if(!success){InterlockedExchange(&wsProfileStatus,0);wsProfilesExpected=-1;wsNativeChecked=0;wsNativeWorld=NULL;}}": "void WorldSettingsAIProfileAttemptFinished(int success){if(!success){InterlockedExchange(&wsProfileStatus,0);wsProfilesExpected=-1;wsFactionsExpected=0;wsNativeFactions=0;wsNativeChecked=0;wsNativeWorld=NULL;}}",
    "int valid=WorldSettingsCheckAIControllers(world,expected,approved,wsProfileError,sizeof wsProfileError);": "int valid=WorldSettingsCheckAIControllers(world,expected,approved,wsProfileError,sizeof wsProfileError);\n if(valid==1)valid=WorldSettingsCheckSpecialControllers(world,wsNativeFactions,approved,wsProfileError,sizeof wsProfileError);",
    "#define WS_AI_WORLD_MODULE() GetModuleHandleA(\"AnnoWelt.dll\")\n#endif": "#define WS_AI_WORLD_MODULE() GetModuleHandleA(\"AnnoWelt.dll\")\n#endif\n#include \"special_activity.inc\"",
}
for before, after in changes.items():
    if text.count(before) != 1:
        raise ValueError("Source patch preimage changed: "+before)
    text = text.replace(before,after)
h = header.decode().replace("\r\n","\n")
before = "void WorldSettingsExpectAIProfiles(int32_t);"
if h.count(before) != 1:
    raise ValueError("Expectation declaration changed")
h = h.replace(before,"void WorldSettingsExpectAIProfiles(int32_t,uint32_t);\n__declspec(dllexport) int WorldSettingsCheckSpecialControllers(void*,uint32_t,void*,char*,uint32_t);")
(OUT/"world_ai.c").write_text(text)
(OUT/"world_ai.h").write_text(h)
shutil.copyfile(HERE/"special_activity.inc.candidate",OUT/"special_activity.inc")
shutil.copyfile(SOURCE/"stock_ai_profiles.h",OUT/"stock_ai_profiles.h")
report = dict(scope=__doc__,base_source_sha256=sha(original),base_header_sha256=sha(header),
              candidates={name:sha((OUT/name).read_bytes()) for name in ["world_ai.c","world_ai.h","special_activity.inc","stock_ai_profiles.h"]},
              production_source_changed=False,actual_game_runs=0)
(OUT/"candidate_sources.json").write_text(json.dumps(report,indent=2)+"\n")
if (SOURCE/"world_ai.c").read_bytes() != original or (SOURCE/"world_ai.h").read_bytes() != header:
    raise ValueError("Production source changed during private preparation")
print(json.dumps(report,indent=2))
