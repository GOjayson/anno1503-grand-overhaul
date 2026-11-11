"""Stage the bounded HE map-visibility adapters on fresh source copies only."""
from .world_options import PRIVATE, authored, replace


def apply_memory_factory(files: dict[str, bytes]) -> None:
    factory = 'developer/source/world_factory.c'
    files[factory] = replace(files[factory],
        b'extern int WorldSettingsBindAIProfileWorld(void*,char*,uint32_t);',
        b'extern int WorldSettingsBindAIProfileWorld(void*,char*,uint32_t);\n'
        b'extern int WorldSettingsVisibilityBeforeLoad(const char*,char*,uint32_t);\n'
        b'extern int WorldSettingsVisibilityAfterLoad(void*,char*,uint32_t);\n'
        b'extern void WorldSettingsVisibilityCancelLoad(void);\n'
        b'extern int WorldSettingsVisibilityCommitFresh(void*,char*,uint32_t);\n'
        b'extern void WorldSettingsVisibilityCancelFresh(void);\n'
        b'extern int WorldSettingsVisibilityReleaseUnpublishedScene(void*);',
        'synchronous native checkpoint load declarations')
    files[factory] = replace(files[factory],
        b'    WorldSettingsFinishAttempt(0);',
        b'    WorldSettingsVisibilityCancelFresh();\n    WorldSettingsFinishAttempt(0);',
        'discard only provisional fresh chart after unsuccessful creation')
    files[factory] = replace(files[factory],
        b'    lastFactoryError[0] = 0;\n    WorldSettingsFinishAttempt(1);',
        b'    if (!WorldSettingsVisibilityCommitFresh(*out,lastFactoryError,sizeof lastFactoryError)) {\n'
        b'        WorldSettingsVisibilityReleaseUnpublishedScene(*out);\n'
        b'        *out = NULL;\n'
        b'        if (!lastFactoryError[0]) snprintf(lastFactoryError,sizeof lastFactoryError,"%s","The fresh exploration checkpoint could not be committed.");\n'
        b'        return finishFailure(failure);\n'
        b'    }\n'
        b'    lastFactoryError[0] = 0;\n    WorldSettingsFinishAttempt(1);',
        'publish fresh chart only after scene and AI certificates succeed')
    files[factory] = replace(files[factory],
        b'    if (!active) {\n        return original(mode, path, saveList, out, metadata, index, flags);\n    }',
        b'    if (!active) {\n'
        b'        *out = NULL;\n'
        b'        if (!WorldSettingsVisibilityBeforeLoad(path,lastFactoryError,sizeof lastFactoryError)) {\n'
        b'            if (failureReporter) failureReporter(lastFactoryError);\n'
        b'            return failure;\n'
        b'        }\n'
        b'        int32_t loaded = original(mode,path,saveList,out,metadata,index,flags);\n'
        b'        if (loaded < 0) { WorldSettingsVisibilityCancelLoad(); *out = NULL; return loaded; }\n'
        b'        if (!*out || !WorldSettingsVisibilityAfterLoad(*out,lastFactoryError,sizeof lastFactoryError)) {\n'
        b'            WorldSettingsVisibilityCancelLoad();\n'
        b'            if (*out) WorldSettingsVisibilityReleaseUnpublishedScene(*out);\n'
        b'            *out = NULL;\n'
        b'            if (!lastFactoryError[0]) snprintf(lastFactoryError,sizeof lastFactoryError,"%s","The loaded exploration checkpoint failed validation.");\n'
        b'            if (failureReporter) failureReporter(lastFactoryError);\n'
        b'            return failure;\n'
        b'        }\n'
        b'        return loaded;\n'
        b'    }', 'restore exploration only before native factory publication')


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
        b'#include "mineral_persistence.inc"\n#include "start_visibility_runtime.inc"\n'
        b'#include "start_visibility_control.inc"\n'
        b'#include "start_visibility_exploration.inc"\n#include "start_visibility_frame.inc"\n'
        b'#include "start_visibility_memory_io.inc"',
        'bounded native display visibility adapters')
    files[backend] = replace(files[backend],
        b' if(!wsStabilizeMineralAbsence(scene,error,cap))return 0;\n return wsLoadedCertificate(scene,error,cap);',
        b' if(!wsStabilizeMineralAbsence(scene,error,cap))return 0;\n'
        b' if(!WorldSettingsValidateChosenVisibility(wsCertPointer(scene,0x160),error,cap))return 0;\n'
        b' return wsLoadedCertificate(scene,error,cap);',
        'new-world visibility certificate before gameplay')
    files[backend] = replace(files[backend],
        b'void WorldSettingsFinishAttempt(int success){WorldSettingsAIProfileAttemptFinished(success);',
        b'void WorldSettingsFinishAttempt(int success){if(!success)WorldSettingsVisibilityCancelFresh();WorldSettingsAIProfileAttemptFinished(success);',
        'cancel provisional chart on menu Back, Close and pre-factory setup failures')
    ai = PRIVATE + 'world_ai.c'
    files[ai] = replace(files[ai], b'extern int WorldSettingsIsActive(void);',
        b'extern int WorldSettingsIsActive(void);\n#ifndef WS_AI_FIXTURE\nextern void WorldSettingsVisibilityReset(void);\n#endif',
        'visibility scratch-buffer native lifetime reset')
    files[ai] = replace(files[ai],
        b' if(wsNativeActive)return 0; /* reject reentry without consuming its owner */',
        b' if(wsNativeActive)return 0; /* reject reentry without consuming its owner */\n'
        b' #ifndef WS_AI_FIXTURE\n WorldSettingsVisibilityReset();\n #endif',
        'discard idle scratch storage before native world replacement')
    apply_memory_factory(files)
    for name in ('start_visibility_policy.h', 'start_visibility_scene.inc', 'start_visibility_runtime.inc',
                 'start_visibility_vision.inc', 'start_visibility_actor_layouts.h',
                 'start_visibility_control.inc', 'start_visibility_performance.inc',
                 'start_visibility_map_refresh.inc', 'start_visibility_memory_io.inc',
                 'start_visibility_chart.h', 'start_visibility_chart.inc',
                 'start_visibility_exploration.inc', 'start_visibility_frame.inc', 'start_visibility_native.inc'):
        files[PRIVATE + name] = authored(name)
