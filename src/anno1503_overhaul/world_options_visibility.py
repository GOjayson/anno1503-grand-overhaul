"""Stage the bounded HE map-visibility adapters on fresh source copies only."""
from .world_options import PRIVATE, authored, replace


def apply_visibility(files: dict[str, bytes]) -> None:
    backend = PRIVATE + 'world_backend.c'
    files[backend] = replace(files[backend], b'#include "world_size.inc"',
        b'#include "world_size.inc"\n#include "start_visibility_scene.inc"',
        'saved native map visibility policy')
    files[backend] = replace(files[backend],
        b' if(!wsRewriteSceneShips(b,error,cap))return 0;',
        b' if(!wsRewriteSceneShips(b,error,cap)||!wsVisibilityScene(b,s,error,cap))return 0;',
        'serialize visibility only after native scene validation')
    files[backend] = replace(files[backend], b'#include "mineral_persistence.inc"',
        b'#include "mineral_persistence.inc"\n#include "start_visibility_runtime.inc"',
        'bounded native display visibility adapters')
    files[backend] = replace(files[backend],
        b' if(!wsStabilizeMineralAbsence(scene,error,cap))return 0;\n return wsLoadedCertificate(scene,error,cap);',
        b' if(!wsStabilizeMineralAbsence(scene,error,cap))return 0;\n'
        b' if(!WorldSettingsValidateChosenVisibility(wsCertPointer(scene,0x160),error,cap))return 0;\n'
        b' return wsLoadedCertificate(scene,error,cap);',
        'new-world visibility certificate before gameplay')
    ai = PRIVATE + 'world_ai.c'
    files[ai] = replace(files[ai], b'extern int WorldSettingsIsActive(void);',
        b'extern int WorldSettingsIsActive(void);\n#ifndef WS_AI_FIXTURE\nextern void WorldSettingsVisibilityReset(void);\n#endif',
        'visibility scratch-buffer native lifetime reset')
    files[ai] = replace(files[ai],
        b' if(wsNativeActive)return 0; /* reject reentry without consuming its owner */',
        b' if(wsNativeActive)return 0; /* reject reentry without consuming its owner */\n'
        b' #ifndef WS_AI_FIXTURE\n WorldSettingsVisibilityReset();\n #endif',
        'discard idle scratch storage before native world replacement')
    for name in ('start_visibility_policy.h', 'start_visibility_scene.inc', 'start_visibility_runtime.inc',
                 'start_visibility_vision.inc', 'start_visibility_actor_layouts.h',
                 'start_visibility_map_refresh.inc'):
        files[PRIVATE + name] = authored(name)
