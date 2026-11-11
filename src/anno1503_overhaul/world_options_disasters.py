"""Bounded HE disaster policies, native scheduler gates and save transport.

Only freshly staged sources and existing guarded in-memory hook allocations
change. Native module/data inputs and the WSCHART1 format stay unchanged.
"""
from __future__ import annotations

import hashlib
import re
import struct

from .world_options import PRIVATE, authored, replace
from .world_runtime_build import BLOBS, PE, RuntimeBuildError, _hex_bytes


DISASTER_CALLS = (
    ('AnnoWelt.dll', 'world_policy', 0xb1c56, bytes.fromhex('410fb78444d0e10f00'), 'WorldSettingsDisasterFireRandom'),
    ('AnnoWelt.dll', 'world_policy', 0xb1d4a, bytes.fromhex('410fb78446d0e10f00'), 'WorldSettingsDisasterPlagueRandom'),
    ('AnnoWelt.dll', 'world_policy', 0xe0b52, bytes.fromhex('81b9046f0000d0dd0600'), 'WorldSettingsDisasterEarthquakeThreshold'),
    ('AnnoWelt.dll', 'world_policy', 0x587f3, bytes.fromhex('b92c010000'), 'WorldSettingsDisasterDroughtThreshold'),
    ('AnnoWelt.dll', 'world_policy', 0x75977, bytes.fromhex('69d1e00f97004103d0'), 'WorldSettingsDisasterVolcanoInterval'),
    ('AnnoWelt.dll', 'world_policy', 0x58870, bytes.fromhex('e81b000000'), 'WorldSettingsDisasterDroughtBegin'),
    ('AnnoWelt.dll', 'world_policy', 0x75a5e, bytes.fromhex('488bc88974242041ff12'), 'WorldSettingsDisasterCreateEvent'),
    ('AnnoWelt.dll', 'world_policy', 0xe0d26, bytes.fromhex('488b06ff10'), 'WorldSettingsDisasterCreateEvent'),
)


def disaster_bridge(rva: int):
    """Return native-compatible code, import offset, code extent and unwind.

    Inserted calls have the native caller's aligned stack and ordinary Win64
    shadow space. The three non-leaf adapters allocate 40 bytes; their only
    live volatile output is the documented threshold/interval register.
    """
    callback = next((row[4] for row in DISASTER_CALLS if row[2] == rva), None)
    if callback is None:
        raise RuntimeBuildError('Unknown reviewed disaster native gate.')
    code = bytearray()
    fixups = []
    def call():
        code.extend(bytes.fromhex('ff15'))
        fixups.append(len(code));code.extend(bytes(4))
    def jump():
        code.extend(bytes.fromhex('ff25'))
        fixups.append(len(code));code.extend(bytes(4))
    framed = rva in (0xe0b52, 0x587f3, 0x75977)
    if rva == 0xe0b52:
        # A real RBP frame permits a recognised LEA/POP/RET epilogue while
        # retaining the native CMP flags. No CMP follows restored stack state.
        code.extend(bytes.fromhex('554883ec204889e5'))
    elif framed:
        code.extend(bytes.fromhex('4883ec28'))
    if rva in (0xb1c56, 0xb1d4a):
        code.extend(next(row[3] for row in DISASTER_CALLS if row[2] == rva))
        code.extend(bytes.fromhex('89c189da4989f0'));jump()
    elif rva == 0xe0b52:
        code.extend(bytes.fromhex('4889d9'));call()
        code.extend(bytes.fromhex('4889d93983046f0000488d65205dc3'))
    elif rva == 0x587f3:
        code.extend(bytes.fromhex('48894424204889d9'));call()
        # The original native CMP CX,AX remains after this five-byte MOV hook.
        code.extend(bytes.fromhex('89c1488b4424204883c428c3'))
    elif rva == 0x75977:
        code.extend(next(row[3] for row in DISASTER_CALLS if row[2] == rva))
        code.extend(bytes.fromhex('89d14889da'));call()
        code.extend(bytes.fromhex('89c24883c428c3'))
    elif rva == 0x75a5e:
        # The fifth stack argument moves by eight for the inserted CALL's
        # return address. This is the native owner argument, not stack storage.
        code.extend(bytes.fromhex('488bc889742428'));jump()
    else:
        jump()
    extent = len(code)
    code.extend(b'\x90' * ((-len(code)) % 8))
    cell = len(code);code.extend(bytes(8))
    for at in fixups:
        struct.pack_into('<i', code, at, cell-at-4)
    unwind = (bytes.fromhex('010803050803053201500000') if rva==0xe0b52 else
              bytes.fromhex('0104010004420000') if framed else bytes.fromhex('01000000'))
    return bytes(code), cell, extent, unwind


def verify_disaster_preimages(images: dict[str, bytes], pins: dict[str, str]):
    rows = []
    for module in sorted({row[0] for row in DISASTER_CALLS}):
        if module not in images or module not in pins or hashlib.sha256(images[module]).hexdigest() != pins[module]:
            raise RuntimeBuildError('Disasters require the exact reviewed HE native module: ' + module)
        pe = PE(images[module]);functions = pe.function_table()
        for name, prefix, rva, before, callback in DISASTER_CALLS:
            if name != module:
                continue
            if not pe.executable(rva, len(before)) or pe.read(rva, len(before)) != before or not any(
                    begin <= rva and rva+len(before) <= end for begin, end, unused in functions):
                raise RuntimeBuildError('A disaster scheduling instruction or function boundary differs.')
            code, cell, end, unwind = disaster_bridge(rva)
            rows.append(dict(module=name, rva=rva, before=before.hex(), callback=callback,
                bridge=code.hex(), import_offset=cell, function_bytes=end, unwind=unwind.hex(),
                stack_allocation=40 if len(unwind)>4 else 0, native_sha256=pins[module]))
        # These native data tables bound the fire/plague chance denominators.
        # 255 disables a native row before either hook; active rows are >=31.
        for at in (0xfcac0, 0xfc550):
            values = pe.read(at, 32)
            if any(v != 255 and not 31 <= v <= 223 for v in values):
                raise RuntimeBuildError('The native disaster probability table differs.')
    return dict(hook_count=len(rows), hooks=rows, new_native_scheduler=False,
                original_files_modified=False, game_executed=False,
                random_stream_advance_preserved=True, severity_types=['volcano', 'earthquake', 'drought'])


def apply_disaster_memory(files: dict[str, bytes]) -> None:
    name = PRIVATE + 'start_visibility_memory_io.inc'
    data = files[name]
    data = replace(data, b' const unsigned char*blob;unsigned char guid[16];',
        b' const unsigned char*blob,*disaster;unsigned char guid[16];', 'separate disaster checkpoint pointer')
    data = replace(data, b'  if(wsMemoryExactTag(data+at,"WSCHART")){',
        b'  if(wsMemoryExactTag(data+at,"WSDISAST")){\n'
        b'   if(f.disaster||n!=64u)return wsMemoryError(error,cap,"The save has duplicate or oversized disaster settings.");\n'
        b'   f.disaster=p;\n'
        b'  }else if(wsMemoryExactTag(data+at,"WSCHART")){', 'bounded separate disaster chunk')
    data = replace(data, b' *out=f;return 1;\n}',
        b' if(f.disaster){const unsigned char*p=f.disaster;\n'
        b'  if(!head||!f.full||memcmp(p,"WSDISR01",8)||wsU32(p+8)!=1u||wsU32(p+12)!=64u||memcmp(p+16,f.guid,16)||\n'
        b'     wsU32(p+32)!=f.width||wsU32(p+36)!=f.height||!wsDisasterOptionsValid(wsU32(p+40),wsU32(p+44),wsU32(p+48),wsU32(p+52))||\n'
        b'     !wsMemoryZero(p+56,8))return wsMemoryError(error,cap,"Disaster settings lack the matching certified exploration checkpoint or schema.");\n'
        b' }\n *out=f;return 1;\n}', 'authenticate full disaster chunk through unchanged chart native checksum')
    data = replace(data, b'static int wsMemoryRegular(HANDLE file,',
        b'#include "disaster_memory.inc"\nstatic int wsMemoryRegular(HANDLE file,', 'separate disaster checkpoint helpers')
    data = replace(data, b' void*worldObject=wsCertPointer(owner,0x10);wsMemoryIOError[0]=0;',
        b' void*worldObject=wsCertPointer(owner,0x10);wsMemoryIOError[0]=0;\n'
        b' WSDisasterContext disasterSnapshot={0};wsDisasterSnapshot(worldObject,&disasterSnapshot);', 'capture disaster policy before native save')
    data = replace(data, b'&&wsMemoryAssemble(native,nativeSize,&parsed,blob,blobSize,&augmented,&augmentedSize,error,sizeof error)',
        b'&&wsDisasterAssembleMemory(&disasterSnapshot,worldObject,native,nativeSize,&parsed,blob,blobSize,&augmented,&augmentedSize,error,sizeof error)',
        'attach disaster chunk before existing chart and atomic commit')
    data = replace(data, b' if(!wsMemoryLoad.data)return 1;int ok=0;',
        b' if(!wsMemoryLoad.data){wsDisasterClearLoaded();return 1;}int ok=0;WSDisasterContext disasterLoaded={0};',
        'older saves cannot inherit an unrelated active disaster policy')
    data = replace(data, b' else if(!v.marked)ok=1;',
        b' else if(!wsDisasterLoadContext(v.world,f,&disasterLoaded,error,cap))ok=0;\n else if(!v.marked)ok=1;',
        'validate disaster checkpoint before chart publication')
    data = replace(data, b' WorldSettingsVisibilityCancelLoad();return ok;',
        b' if(ok)wsDisasterPublish(&disasterLoaded);\n WorldSettingsVisibilityCancelLoad();return ok;',
        'publish disaster policy only after complete loaded chart succeeds')
    files[name] = data
    files[PRIVATE + 'disaster_memory.inc'] = authored('disaster_memory.inc')


def apply_disasters(files: dict[str, bytes]) -> None:
    backend = PRIVATE + 'world_backend.c'
    files[backend] = replace(files[backend], b'#include "start_visibility_memory_io.inc"',
        b'#include "disaster_policy.inc"\n#include "start_visibility_memory_io.inc"', 'bounded native disaster policy')
    files[backend] = replace(files[backend], b'void WorldSettingsFinishAttempt(int success){',
        b'void WorldSettingsFinishAttempt(int success){if(!success)WorldSettingsFinishDisasterAttempt(0);', 'factory failure cancels without consuming choices on scene success')
    header = PRIVATE + 'world_backend.h'
    files[header] = replace(files[header], b'#include "advanced_settings.h"',
        b'void WorldSettingsExpectDisasterOptions(const WSWorldSettings*);\n#include "advanced_settings.h"', 'fresh disaster declarations')
    menu = PRIVATE + 'WorldSettings.c'
    files[menu] = replace(files[menu], b' WorldSettingsExpectFactionActivity(d->settings.factions,',
        b' WorldSettingsExpectDisasterOptions(&d->settings);\n WorldSettingsExpectFactionActivity(d->settings.factions,', 'fresh menu disaster options')
    ai = PRIVATE + 'world_ai.c'
    files[ai] = replace(files[ai], b'extern int WorldSettingsValidateChosenDisasters(void*,char*,uint32_t);',
        b'extern int WorldSettingsValidateChosenDisasters(void*,char*,uint32_t);\nextern int WorldSettingsBindDisasterOptions(void*,char*,uint32_t);\nextern void WorldSettingsFinishDisasterAttempt(int);', 'certified disaster commit declaration')
    files[ai] = replace(files[ai],
        b' int missing=nativeSuccess&&wsNativeExpected&&!wsNativeChecked;\n WorldSettingsResetFactionActivity();',
        b' int missing=nativeSuccess&&wsNativeExpected&&!wsNativeChecked;\n WorldSettingsFinishDisasterAttempt(complete);\n WorldSettingsResetFactionActivity();',
        'commit disaster context after the complete native player-profile scope')
    files[ai] = replace(files[ai], b' if(valid==1)valid=WorldSettingsBindFactionActivity(world,approved,wsProfileError,sizeof wsProfileError);',
        b' if(valid==1)valid=WorldSettingsBindFactionActivity(world,approved,wsProfileError,sizeof wsProfileError);\n'
        b' if(valid==1)valid=WorldSettingsBindDisasterOptions(world,wsProfileError,sizeof wsProfileError);', 'fresh disaster policy after complete original certificates')
    for name in ('disaster_policy.h', 'disaster_policy.inc'):
        files[PRIVATE + name] = authored(name)
    apply_disaster_memory(files)


def _one(text: str, pattern: str, label: str):
    matches = list(re.finditer(pattern, text, re.S))
    if len(matches) != 1:
        raise RuntimeBuildError('Disaster bridge metadata differs: ' + label)
    return matches[0]


def _array(data):
    return ','.join('0x%02x' % value for value in data)


def apply_disaster_calls(files: dict[str, bytes]) -> None:
    """Append after strict visibility staging without weakening its parser."""
    text = files[BLOBS].decode('ascii');prefix = 'world_policy'
    entry = _one(text, r'\{L"AnnoWelt.dll",\{([^}]*)\},(' + prefix + r'_code,[^{}]+)\}', prefix + ' entry')
    fields = entry.group(2).split(',')
    if len(fields) != 10 or fields[6] != prefix+'_functions' or fields[8] != prefix+'_hooks':
        raise RuntimeBuildError('The existing world policy allocation metadata differs.')
    original_counts = tuple(int(fields[i]) for i in (5, 7, 9))
    if original_counts != (7, 8, 8):
        raise RuntimeBuildError('Disaster staging requires the exact preceding visibility allocation.')
    code_match = _one(text, r'static const unsigned char '+prefix+r'_code\[\] = \{([^}]*)\};', prefix+' code')
    original = _hex_bytes(code_match.group(1));code = bytearray(original)
    imports, functions, hooks, declarations = [], [], [], []
    for index, (module, allocation, rva, before, callback) in enumerate(DISASTER_CALLS):
        if (module, allocation) != ('AnnoWelt.dll', prefix):
            raise RuntimeBuildError('A disaster gate is outside its reviewed allocation.')
        code.extend(b'\x90' * ((-len(code)) % 16));at=len(code)
        bridge, cell, extent, unwind = disaster_bridge(rva);code.extend(bridge)
        imports.append('{%d,"%s"}' % (at+cell, callback))
        unwind_name = prefix+'_disaster_unwind_'+str(index)
        before_name = prefix+'_disaster_before_'+str(index)
        declarations.append('static const unsigned char %s[] = {%s};\n' % (unwind_name, _array(unwind)))
        declarations.append('static const unsigned char %s[] = {%s};\n' % (before_name, _array(before)))
        functions.append('{%d,%d,%s,%d}' % (at, at+extent, unwind_name, len(unwind)))
        hooks.append('{%d,%d,%s,%d,1}' % (rva, len(before), before_name, at))
    if original_counts[1]+len(DISASTER_CALLS)>32 or len(code)>0x100000:
        raise RuntimeBuildError('Disaster gate metadata exceeds existing bounded allocation limits.')
    text=text[:code_match.start()]+'static const unsigned char %s_code[] = {%s};' % (prefix,_array(code))+text[code_match.end():]
    for kind,suffix,items in (('WSImportCell','imports',imports),('WSFunctionMeta','functions',functions),('WSHook','hooks',hooks)):
        match=_one(text,r'static const '+kind+' '+prefix+'_'+suffix+r'\[\] = \{([^;]*)\};',prefix+' '+suffix)
        body=match.group(1).rstrip()
        replacement='static const %s %s_%s[] = {%s%s%s};' % (kind,prefix,suffix,body,',' if body else '',','.join(items))
        if suffix=='functions':replacement=''.join(declarations)+replacement
        text=text[:match.start()]+replacement+text[match.end():]
    entry=_one(text,r'\{L"AnnoWelt.dll",\{([^}]*)\},('+prefix+r'_code,[^{}]+)\}',prefix+' final entry')
    fields=entry.group(2).split(',');fields[1]=str(len(code))
    for at in (5,7,9):fields[at]=str(int(fields[at])+len(DISASTER_CALLS))
    text=text[:entry.start()]+'{L"AnnoWelt.dll",{%s},%s}' % (entry.group(1),','.join(fields))+text[entry.end():]
    final=_one(text,r'static const unsigned char '+prefix+r'_code\[\] = \{([^}]*)\};',prefix+' preserved code')
    if _hex_bytes(final.group(1))[:len(original)]!=original:
        raise RuntimeBuildError('Disaster staging modified existing visibility instructions.')
    files[BLOBS]=text.encode('ascii')


def apply_disaster_transaction(files: dict[str, bytes]) -> None:
    """Count the eight extra calls in the existing single atomic transaction."""
    name = 'developer/source/engine_resume/ai_loader/install_test_hooks.c'
    value = files[name]
    value = replace(value, b'#define WS_MAX_HOOKS (37+WS_ENGINE_PATCH_COUNT)',
        b'#define WS_MAX_HOOKS (45+WS_ENGINE_PATCH_COUNT)', 'exact eight-disaster transaction capacity')
    value = replace(value, b'static DWORD wsVisibilityPatchStatusUnlocked(void);',
        b'static DWORD wsVisibilityPatchStatusUnlocked(void);\nstatic DWORD wsDisasterPatchStatusUnlocked(void);',
        'independent disaster readiness declaration')
    value = replace(value, b' if(result&&wsVisibilityPatchStatusUnlocked()!=WS_VISIBILITY_HOOK_COUNT)result=0;',
        b' if(result&&wsVisibilityPatchStatusUnlocked()!=WS_VISIBILITY_HOOK_COUNT)result=0;\n'
        b' if(result&&wsDisasterPatchStatusUnlocked()!=8u)result=0;', 'complete disaster readiness')
    value = replace(value, b'#include "visibility_hooks.inc"',
        b'#include "visibility_hooks.inc"\n#include "disaster_hooks.inc"', 'registered disaster bridge certificate')
    value = replace(value,
        b' if(patchCount!=9u+WS_ENGINE_PATCH_COUNT+WS_VISIBILITY_HOOK_COUNT){',
        b' if(!wsPrepareDisasterHooks(self,patches,patchCount))goto done;\n'
        b' if(patchCount!=17u+WS_ENGINE_PATCH_COUNT+WS_VISIBILITY_HOOK_COUNT){', 'exact complete transaction membership')
    files[name] = value
    files['developer/source/engine_resume/ai_loader/disaster_hooks.inc'] = authored('disaster_hooks.inc')
