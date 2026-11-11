"""Reviewed HE visibility and save branches through bounded leaf bridges.

Only fresh staged blob metadata is extended. Existing code, native-relative
relocations, imports, hooks and chained unwind parents retain their original
bytes. Each bridge tail-jumps to an ordinary compiled DLL export without a
new native frame. Only the proved final-frame site copies live context RDI
to volatile argument RDX; all other register and stack arguments stay intact.
"""
import hashlib
import re

from .world_runtime_build import BLOBS, PE, RuntimeBuildError, blob_metadata, _hex_bytes


DISPLAY_SHA256 = '3cfc150fde93b572dd06ff375454792b844f1d7aab62a65c034230df64356eb2'
# module, existing guarded allocation, original call, complete instruction,
# native-compatible compiled callback. RVAs are for the pinned AMD64 images.
CALLS = (
    ('AnnoWelt.dll', 'world_policy', 0xcbf15, bytes.fromhex('ff9000010000'), 'WorldSettingsVisibilityDispatchResident100'),
    ('AnnoWelt.dll', 'world_policy', 0xcdb1c, bytes.fromhex('ff9008010000'), 'WorldSettingsVisibilityDispatchResident108'),
    ('AnnoWelt.dll', 'world_policy', 0xcbe60, bytes.fromhex('ff9000010000'), 'WorldSettingsVisibilityDispatchOccurrence100'),
    ('AnnoFrame.dll', 'native_attempt', 0x1bc1f, bytes.fromhex('ff9020010000'), 'WorldSettingsVisibilityMinimapExclude'),
    ('AnnoWelt.dll', 'world_policy', 0xcb91a, bytes.fromhex('41ff9288010000'), 'WorldSettingsVisibilityDrawStatic188'),
    ('AnnoWelt.dll', 'world_policy', 0xcb9cc, bytes.fromhex('41ff9280010000'), 'WorldSettingsVisibilityDrawStatic180'),
    ('AnnoWelt.dll', 'world_policy', 0xcbc89, bytes.fromhex('ff9080010000'), 'WorldSettingsVisibilityDrawStatic180'),
    ('AnnoWelt.dll', 'world_policy', 0xcde09, bytes.fromhex('ff9080010000'), 'WorldSettingsVisibilityDrawStatic180'),
    ('AnnoFrame.dll', 'native_attempt', 0x75b80, bytes.fromhex('e90b000000'), 'WorldSettingsVisibilitySave'),
    ('AnnoFrame.dll', 'native_attempt', 0x7666c, bytes.fromhex('e81ff5ffff'), 'WorldSettingsVisibilitySave'),
    ('AnnoFrame.dll', 'native_attempt', 0x7e713, bytes.fromhex('e87874ffff'), 'WorldSettingsVisibilitySave'),
    ('AnnoFrame.dll', 'native_attempt', 0x8040a, bytes.fromhex('e88157ffff'), 'WorldSettingsVisibilitySave'),
    ('AnnoFrame.dll', 'native_attempt', 0x1ca76, bytes.fromhex('ff9018010000'), 'WorldSettingsVisibilityFinishFrame'),
    ('AnnoFrame.dll', 'native_attempt', 0x169ac, bytes.fromhex('ff90f0000000'), 'WorldSettingsVisibilityInteractionProperty'),
    ('AnnoFrame.dll', 'native_attempt', 0x16a72, bytes.fromhex('ff90f0000000'), 'WorldSettingsVisibilityInteractionProperty'),
    ('AnnoFrame.dll', 'native_attempt', 0x76b50, bytes.fromhex('ff90a8000000'), 'WorldSettingsVisibilityLoadFileA8'),
)


def branch_is_call(module: str, rva: int) -> bool:
    """Retain the proved save wrapper's tail branch, not a synthetic call."""
    return (module, rva) != ('AnnoFrame.dll', 0x75b80)


def bridge_layout(module: str, rva: int):
    """Executable prefix, aligned import cell and leaf function extent."""
    if (module, rva) == ('AnnoFrame.dll', 0x1ca76):
        # MOV RDX,RDI; JMP [RIP+7]; seven NOPs; aligned import cell.
        return bytes.fromhex('4889faff2507000000') + b'\x90' * 7, 16, 9
    return bytes.fromhex('ff25020000009090'), 8, 6


def verify_visibility_call_preimages(images: dict[str, bytes], pins: dict[str, str]):
    rows = []
    for name in sorted({row[0] for row in CALLS}):
        if name not in images or name not in pins or hashlib.sha256(images[name]).hexdigest() != pins[name]:
            raise RuntimeBuildError('Strict visibility requires the exact native call-site image: ' + name)
        pe = PE(images[name])
        ranges = pe.function_table()
        for module, prefix, rva, before, callback in CALLS:
            if module != name:
                continue
            if not pe.executable(rva, len(before)) or pe.read(rva, len(before)) != before:
                raise RuntimeBuildError('A strict-visibility native dispatch instruction differs: ' + name)
            if not any(begin <= rva and rva + len(before) <= end for begin, end, unwind in ranges):
                raise RuntimeBuildError('A visibility dispatch crosses a native function boundary.')
            prefix_bytes, import_offset, function_end = bridge_layout(name, rva)
            rows.append(dict(module=name, rva=rva, before=before.hex(), callback=callback,
                             branch='call' if branch_is_call(name, rva) else 'tail-jump',
                             live_context_argument=(name, rva) == ('AnnoFrame.dll', 0x1ca76),
                             bridge_prefix=prefix_bytes.hex(), import_offset=import_offset,
                             leaf_function_bytes=function_end, native_sha256=pins[name]))
    return dict(call_count=len(rows), call_preimages=rows, stack_rewriting=False,
                stack_or_argument_rewriting=True,
                context_argument_copies=[dict(module='AnnoFrame.dll', rva=0x1ca76,
                                              source='RDI', destination='RDX')],
                allocation_and_unwind_in_existing_transaction=True)


def _one(text: str, pattern: str, label: str):
    matches = list(re.finditer(pattern, text, re.S))
    if len(matches) != 1:
        raise RuntimeBuildError('Visibility bridge metadata differs: ' + label)
    return matches[0]


def _array(data: bytes) -> str:
    return ','.join('0x%02x' % value for value in data)


def apply_visibility_calls(files: dict[str, bytes]) -> None:
    original = files[BLOBS]
    records = blob_metadata(original)  # Retains the strict original 8/9 contract.
    text = original.decode('ascii')
    for module, prefix in sorted({row[:2] for row in CALLS}):
        record = [row for row in records if row['module'] == module and row['prefix'] == prefix]
        if len(record) != 1:
            raise RuntimeBuildError('The reviewed visibility bridge allocation is absent.')
        selected = [row for row in CALLS if row[:2] == (module, prefix)]
        code_match = _one(text, r'static const unsigned char ' + prefix + r'_code\[\] = \{([^}]*)\};', prefix + ' code')
        old_code = _hex_bytes(code_match.group(1))
        code = bytearray(old_code)
        new_imports, new_functions, new_hooks, declarations = [], [], [], []
        for index, (_, _, rva, before, callback) in enumerate(selected):
            code.extend(b'\x90' * ((-len(code)) % 16))
            offset = len(code)
            executable, import_offset, function_end = bridge_layout(module, rva)
            code.extend(executable + bytes(8))
            new_imports.append('{%d,"%s"}' % (offset + import_offset, callback))
            new_functions.append('{%d,%d,%s_visibility_leaf,4}' % (offset, offset + function_end, prefix))
            name = prefix + '_visibility_before_' + str(index)
            declarations.append('static const unsigned char %s[] = {%s};\n' % (name, _array(before)))
            new_hooks.append('{%d,%d,%s,%d,%d}' % (rva, len(before), name, offset,
                                                 int(branch_is_call(module, rva))))
        if len(record[0]['functions']) + len(selected) > 32 or len(code) > 0x100000:
            raise RuntimeBuildError('Strict visibility bridge metadata exceeds native bounds.')
        replacement = 'static const unsigned char %s_code[] = {%s};' % (prefix, _array(code))
        text = text[:code_match.start()] + replacement + text[code_match.end():]
        for kind, additions in (('WSImportCell', new_imports), ('WSFunctionMeta', new_functions), ('WSHook', new_hooks)):
            suffix = {'WSImportCell': 'imports', 'WSFunctionMeta': 'functions', 'WSHook': 'hooks'}[kind]
            pattern = r'static const ' + kind + ' ' + prefix + '_' + suffix + r'\[\] = \{([^;]*)\};'
            match = list(re.finditer(pattern, text, re.S))
            if kind == 'WSImportCell' and not match:
                line = 'static const WSImportCell %s_imports[] = {%s};\n' % (prefix, ','.join(additions))
                at = text.index('static const WSBlob wsBlobs[]')
                text = text[:at] + line + text[at:]
            else:
                if len(match) != 1:
                    raise RuntimeBuildError('Visibility bridge metadata array differs: ' + prefix + '_' + suffix)
                match = match[0]
                before = match.group(0)
                body = match.group(1).rstrip()
                after = 'static const %s %s_%s[] = {%s%s%s};' % (
                    kind, prefix, suffix, body, ',' if body else '', ','.join(additions))
                if kind == 'WSFunctionMeta':
                    after = 'static const unsigned char %s_visibility_leaf[] = {0x01,0x00,0x00,0x00};\n' % prefix + after
                elif kind == 'WSHook':
                    after = ''.join(declarations) + after
                text = text[:match.start()] + after + text[match.end():]
        pattern = r'\{L"' + re.escape(module) + r'",\{([^}]*)\},(' + prefix + r'_code,[^{}]+)\}'
        entry = _one(text, pattern, prefix + ' blob entry')
        fields = entry.group(2).split(',')
        if len(fields) != 10 or fields[6] != prefix + '_functions' or fields[8] != prefix + '_hooks':
            raise RuntimeBuildError('Visibility bridge native blob fields changed.')
        fields[1] = str(len(code))
        fields[4] = prefix + '_imports'
        fields[5] = str(int(fields[5]) + len(selected))
        fields[7] = str(int(fields[7]) + len(selected))
        fields[9] = str(int(fields[9]) + len(selected))
        after = '{L"%s",{%s},%s}' % (module, entry.group(1), ','.join(fields))
        text = text[:entry.start()] + after + text[entry.end():]
        # Every old instruction/import cell remains byte-exact at its offset.
        check = _one(text, r'static const unsigned char ' + prefix + r'_code\[\] = \{([^}]*)\};', prefix + ' final code')
        if _hex_bytes(check.group(1))[:len(old_code)] != old_code:
            raise RuntimeBuildError('A strict bridge changed existing native blob code.')
    files[BLOBS] = text.encode('ascii')
