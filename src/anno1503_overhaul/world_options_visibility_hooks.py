"""Exact HE visibility dispatch bindings in the existing guarded transaction.

The original nine code hooks and 173 engine edits are retained. Additional
dispatch-pointer replacements share their preflight, paused-thread commit and
rollback, and never alter the on-disk native modules or physical world data.
"""
import hashlib
import struct

from .world_options import PRIVATE, authored, replace
from .world_runtime_build import PE, RuntimeBuildError


HOOKS = (
    (0xff398, 0xcc5a0, 'WorldSettingsVisibilityDrawTerrain'),
    (0xff3a0, 0xcd470, 'WorldSettingsVisibilityDrawTerrainClipped'),
    (0xff810, 0xcc5a0, 'WorldSettingsVisibilityDrawTerrain'),
    (0xff818, 0xcd470, 'WorldSettingsVisibilityDrawTerrainClipped'),
    (0xff5f8, 0xd2620, 'WorldSettingsVisibilityCreateMap'),
)
RENDER_HOOKS = (
    (0xf638c0, 0x49410, 'WorldSettingsVisibilityRenderStatic180'),
    (0xf638c8, 0x49bd0, 'WorldSettingsVisibilityRenderStatic188'),
)
INSTALLER = 'developer/source/engine_resume/ai_loader/install_test_hooks.c'


def _verify_dispatch_preimages(data: bytes, expected_sha: str, hooks, module: str):
    if hashlib.sha256(data).hexdigest() != expected_sha:
        raise RuntimeBuildError(f'Visibility dispatch requires the exact reviewed native {module} image.')
    pe = PE(data)
    image_base, = pe.unpack('<Q', pe.optional + 24)
    functions = pe.function_table()
    result = []
    for slot, target, export in hooks:
        before = pe.read(slot, 8)
        if struct.unpack('<Q', before)[0] != image_base + target:
            raise RuntimeBuildError('A History Edition visibility dispatch preimage differs.')
        entries = [(begin, end, unwind) for begin, end, unwind in functions if begin == target]
        if (pe.executable(slot, 8) or len(entries) != 1 or
                entries[0][1] <= target or not pe.executable(target, entries[0][1] - target)):
            raise RuntimeBuildError('Visibility dispatch does not reference a complete native function.')
        pe.read(entries[0][2], 4)
        result.append(dict(slot_rva=slot, original_target_rva=target, wrapper_export=export,
                           disk_preimage=before.hex()))
    return dict(native_sha256=expected_sha, machine='AMD64', pointer_bytes=8,
                dispatch_count=len(result), dispatch_preimages=result,
                original_functions_not_patched=True)


def verify_visibility_preimages(data: bytes, expected_sha: str):
    """Establish the original five World bindings without changing their API."""
    return _verify_dispatch_preimages(data, expected_sha, HOOKS, 'World')


def verify_renderer_visibility_preimages(data: bytes, expected_sha: str):
    """Establish both DD11 bindings against the separately pinned Display image."""
    return _verify_dispatch_preimages(data, expected_sha, RENDER_HOOKS, 'Display')


def apply_visibility_hooks(files: dict[str, bytes]) -> None:
    value = files[INSTALLER]
    value = replace(value, b'#define WS_MAX_HOOKS (16+WS_ENGINE_PATCH_COUNT)',
        b'#define WS_MAX_HOOKS (29+WS_ENGINE_PATCH_COUNT)', 'bounded visibility dispatch transaction capacity')
    value = replace(value, b'static char wsInstallError[512];',
        b'static char wsInstallError[512];\n'
        b'#define WS_VISIBILITY_POINTER_COUNT 7u\n'
        b'#define WS_VISIBILITY_CALL_COUNT 13u\n'
        b'#define WS_VISIBILITY_HOOK_COUNT 20u\n'
        b'static DWORD wsVisibilityPatchStatusUnlocked(void);',
        'visibility readiness declarations')
    value = replace(value, b' ReleaseSRWLockShared(&wsInstallLock);return result;',
        b' if(result&&wsVisibilityPatchStatusUnlocked()!=WS_VISIBILITY_HOOK_COUNT)result=0;\n'
        b' ReleaseSRWLockShared(&wsInstallLock);return result;',
        'visibility dispatch is required for complete engine readiness')
    value = replace(value, b'static int wsPrepareEngine(WSPatch *patches,uint32_t *patchCount){',
        b'#include "visibility_hooks.inc"\n'
        b'static int wsPrepareEngine(WSPatch *patches,uint32_t *patchCount){',
        'visibility uses the existing transaction and native identity helpers')
    value = replace(value,
        b' if(!wsPrepareEngine(patches,&patchCount))goto done;\n'
        b' if(patchCount!=9u+WS_ENGINE_PATCH_COUNT){wsError("The complete nine-hook and expanded-engine transaction is incomplete.");goto done;}',
        b' if(!wsPrepareEngine(patches,&patchCount))goto done;\n'
        b' if(!wsPrepareVisibility(self,patches,&patchCount))goto done;\n'
        b' if(patchCount!=9u+WS_ENGINE_PATCH_COUNT+WS_VISIBILITY_HOOK_COUNT){wsError("The complete native hooks, engine edits and visibility dispatch transaction is incomplete.");goto done;}',
        'visibility joins the single guarded complete transaction')
    files[INSTALLER] = value
    files['developer/source/engine_resume/ai_loader/visibility_hooks.inc'] = authored('visibility_hooks.inc')
