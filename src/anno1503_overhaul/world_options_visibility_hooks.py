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
CONTROL_HOOKS = (
    (0xa7248, 0x78630, 'WorldSettingsVisibilityBuildingCommand'),
    (0xa7250, 0x785d0, 'WorldSettingsVisibilityShipQueue'),
    (0xa74f0, 0x7d340, 'WorldSettingsVisibilityBuildingCommand'),
    (0xa74f8, 0x7d230, 'WorldSettingsVisibilityShipQueue'),
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


def verify_control_visibility_preimages(data: bytes, expected_sha: str):
    """Prove both local and network client building-command dispatches."""
    return _verify_dispatch_preimages(data, expected_sha, CONTROL_HOOKS, 'Frame')


def apply_visibility_hooks(files: dict[str, bytes]) -> None:
    value = files[INSTALLER]
    value = replace(value, b'#define WS_MAX_HOOKS (16+WS_ENGINE_PATCH_COUNT)',
        b'#define WS_MAX_HOOKS (37+WS_ENGINE_PATCH_COUNT)', 'bounded visibility dispatch transaction capacity')
    value = replace(value, b'static char wsInstallError[512];',
        b'static char wsInstallError[512];\n'
        b'#define WS_VISIBILITY_NATIVE_POINTER_COUNT 11u\n'
        b'#define WS_VISIBILITY_IMPORT_COUNT 1u\n'
        b'#define WS_VISIBILITY_POINTER_COUNT 12u\n'
        b'#define WS_VISIBILITY_CALL_COUNT 16u\n'
        b'#define WS_VISIBILITY_HOOK_COUNT 28u\n'
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


IMPORT_HOOKS = (
    ('View.dll', 0xa1098, 'AnnoScene.dll', 'CreateAnnoSceneInstance',
     0x11a0, 'WorldSettingsVisibilityCreateSceneFromView'),
)

FACTORY_HEAD = bytes.fromhex('41564883ec3048c7442420feffffff')

def need(value, message):
    if not value:
        raise RuntimeBuildError(message)


def cstring(pe, rva, maximum=256):
    result = bytearray()
    for offset in range(maximum):
        value = pe.read(rva + offset, 1)[0]
        if not value:
            return result.decode('ascii')
        need(value < 128, 'Native import/export name is not bounded ASCII.')
        result.append(value)
    raise RuntimeBuildError('Native import/export name is unterminated.')


def import_binding(pe, slot):
    rva, size = pe.directory(1)
    need(rva and 40 <= size <= 20 * 4096 and size % 20 == 0,
         'Native import descriptor directory is absent or unbounded.')
    matches = []
    terminated = False
    for offset in range(0, size, 20):
        lookup, stamp, forwarder, name, first = struct.unpack('<5I', pe.read(rva + offset, 20))
        if not any((lookup, stamp, forwarder, name, first)):
            terminated = True
            break
        if not first or slot < first or (slot - first) % 8 or (slot - first) // 8 >= 8192:
            continue
        need(lookup, 'The reviewed import requires a separate original lookup table.')
        index = (slot - first) // 8
        stopped = False
        for at in range(index + 1):
            thunk, = struct.unpack('<Q', pe.read(lookup + at * 8, 8))
            if not thunk:
                stopped = True
                break
        if stopped:
            continue
        need(not thunk & (1 << 63) and thunk <= 0xffffffff,
             'The reviewed import must have one named lookup thunk.')
        matches.append(dict(module=cstring(pe, name), name=cstring(pe, thunk + 2),
                            lookup_rva=lookup + index * 8, hint_name_rva=thunk,
                            thunk=thunk, descriptor_rva=rva + offset))
    need(terminated and len(matches) == 1,
         'Native import slot lacks one terminated descriptor/lookup owner.')
    return matches[0]


def exported_function(pe, name):
    rva, size = pe.directory(0)
    need(rva and size >= 40, 'Native export directory is absent.')
    fields = struct.unpack('<IIHH7I', pe.read(rva, 40))
    _, _, _, _, _, ordinal_base, functions, names, address_table, name_table, ordinals = fields
    need(0 < functions <= 65536 and 0 < names <= 65536,
         'Native export tables are unbounded.')
    found = []
    for i in range(names):
        text_rva, = struct.unpack('<I', pe.read(name_table + i * 4, 4))
        if cstring(pe, text_rva) != name:
            continue
        ordinal, = struct.unpack('<H', pe.read(ordinals + i * 2, 2))
        need(ordinal < functions, 'Native export ordinal leaves its function table.')
        target, = struct.unpack('<I', pe.read(address_table + ordinal * 4, 4))
        need(not rva <= target < rva + size, 'Native factory export must not be forwarded.')
        found.append(target)
    need(len(found) == 1, 'Native factory export is absent or ambiguous.')
    return found[0]


def verify_import_visibility_preimages(images, expected_hashes):
    parsed = {}
    for name in {entry[i] for entry in IMPORT_HOOKS for i in (0, 2)}:
        need(name in images and hashlib.sha256(images[name]).hexdigest() == expected_hashes[name],
             'Visibility import requires the exact reviewed native ' + name + ' image.')
        parsed[name] = PE(images[name])
    rows = []
    for owner, slot, imported, symbol, target, wrapper in IMPORT_HOOKS:
        pe, dependency = parsed[owner], parsed[imported]
        binding = import_binding(pe, slot)
        need(binding['module'] == imported and binding['name'] == symbol,
             'The reviewed View import descriptor/name differs.')
        before = pe.read(slot, 8)
        need(struct.unpack('<Q', before)[0] == binding['thunk'] and not pe.executable(slot, 8),
             'The on-disk View thunk is not its exact nonexecutable named import.')
        need(exported_function(dependency, symbol) == target,
             'The imported Scene factory export RVA differs.')
        entries = [row for row in dependency.function_table() if row[0] == target]
        need(len(entries) == 1 and entries[0][1] > target and
             dependency.executable(target, entries[0][1] - target),
             'The imported Scene factory lacks complete executable function bounds.')
        dependency.read(entries[0][2], 4)
        need(dependency.read(target, len(FACTORY_HEAD)) == FACTORY_HEAD,
             'The imported Scene factory instruction preimage differs.')
        rows.append(dict(owner_module=owner, slot_rva=slot, imported_module=imported,
                         imported_export=symbol, original_target_rva=target,
                         wrapper_export=wrapper, disk_preimage=before.hex(),
                         import_descriptor_rva=binding['descriptor_rva'],
                         import_lookup_rva=binding['lookup_rva'], hint_name_rva=binding['hint_name_rva'],
                         original_function_end_rva=entries[0][1],
                         original_function_head=FACTORY_HEAD.hex(),
                         disk_thunk_is_absolute_function_address=False))
    return dict(machine='AMD64', pointer_bytes=8, dispatch_count=len(rows),
                native_sha256={name: expected_hashes[name] for name in sorted(parsed)},
                import_dispatch_preimages=rows, original_functions_not_patched=True,
                loaded_preimage_rule='View IAT slot equals loaded AnnoScene.dll base plus its exact named export RVA')

