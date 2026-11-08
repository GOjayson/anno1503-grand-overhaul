"""Generate the reviewed native hook bytes for a transient process-only test.

Disk game files remain unchanged. The installer package uses the separate PE
copy transformations. This header contains only our added native code and tiny
fingerprinted hook preimages, not replacement original game functions.
"""
from pathlib import Path
import hashlib
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE / '_tools'), str(HERE / 'engine_audit'), str(HERE / 'native_world')]
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from bridge_codegen import build_bridge, COMMON_UNWIND, LEAF_UNWIND
from frame_factory_bridge import build_factory_code, FACTORY_CALL_RVA, FACTORY_CALL_BYTES
from patch_scene_copy import build_code, PREPARE_RVA, PREPARE_BEFORE, GUARD_RVA, GUARD_BEFORE
from patch_frame_copy import pe_info


def relocated_fields(a, b, functions, delta):
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    fields = []
    covered = set()
    for begin, end in functions:
        for ins in md.disasm(a[begin:end], begin):
            for off, size in [(ins.disp_offset, ins.disp_size), (ins.imm_offset, ins.imm_size)]:
                if not size:
                    continue
                at = ins.address + off
                covered.update(range(at, at+size))
                if a[at:at+size] == b[at:at+size]:
                    continue
                if size != 4:
                    raise ValueError('Unexpected non-rel32 native relocation')
                old, new = (struct.unpack_from('<I', data, at)[0] for data in (a, b))
                if (new-old) & 0xffffffff != (-delta) & 0xffffffff:
                    raise ValueError('Native relative relocation does not match its reviewed base shift')
                fields.append(at)
    # Data includes ILT/IAT RVAs that the transient loader replaces directly;
    # only executable instruction fields are reused as relative code.
    return sorted(set(fields))


def bytes_array(name, data):
    return 'static const unsigned char '+name+'[] = {'+','.join(f'0x{x:02x}' for x in data)+'};\n'


def main():
    frame = (HERE.parent / 'AnnoFrame.dll').read_bytes()
    scene = (HERE.parent / 'AnnoScene.dll').read_bytes()
    _, opt, _, _, off = pe_info(scene)
    pdata, size = struct.unpack_from('<II', scene, opt+112+3*8)
    entries = [struct.unpack_from('<III', scene, off(pdata)+i) for i in range(0, size, 12)]
    prepare_parent = struct.unpack_from('<III', scene, off(0x4a180)+4)
    application_parent = next(e for e in entries if e[0] == 0xc250)
    delta = 0x123456
    flag, names, hooks, functions = build_bridge(0)
    flag2, *_ = build_bridge(delta)
    factory, factory_names = build_factory_code(0)
    factory2, _ = build_factory_code(delta)
    native_scene, scene_names, _ = build_code(0)
    native_scene2, *_ = build_code(delta)
    blobs = [
        ('flag', 'AnnoFrame.dll', frame, flag, flag2, functions, [],
         [(hooks[0][0], hooks[0][1], names['worldsettings_start'], 0)]),
        ('factory', 'AnnoFrame.dll', frame, factory, factory2,
         [(factory_names['factory_bridge'], factory_names['factory_bridge_end'], COMMON_UNWIND)],
         [(factory_names['factory_export_iat'], 'WorldSettingsCreateScene')],
         [(FACTORY_CALL_RVA, FACTORY_CALL_BYTES, factory_names['factory_bridge'], 1)]),
        ('scene', 'AnnoScene.dll', scene, native_scene, native_scene2,
         [(scene_names['prepare'], scene_names['prepare_end'], bytes.fromhex('21000000')+struct.pack('<III', *prepare_parent)),
          (scene_names['resource_guard'], scene_names['resource_guard_end'], bytes.fromhex('21000000')+struct.pack('<III', *application_parent))],
         [(scene_names['prepare_iat'], 'WorldSettingsPrepareScene'), (scene_names['active_iat'], 'WorldSettingsIsActive')],
         [(PREPARE_RVA, PREPARE_BEFORE, scene_names['prepare'], 0), (GUARD_RVA, GUARD_BEFORE, scene_names['resource_guard'], 0)]),
    ]
    output = ['/* Generated from reviewed History Edition code generators. */\n#include <stdint.h>\n#include <wchar.h>\n',
              'typedef struct {uint32_t offset;} WSRelocation;\n',
              'typedef struct {uint32_t offset;const char *name;} WSImportCell;\n',
              'typedef struct {uint32_t begin,end;const unsigned char *unwind;uint32_t unwindSize;} WSFunctionMeta;\n',
              'typedef struct {uint32_t rva,length;const unsigned char *before;uint32_t target;int call;} WSHook;\n',
              'typedef struct {const wchar_t *module;unsigned char sha256[32];const unsigned char *code;uint32_t codeSize;const WSRelocation *relocs;uint32_t relocCount;const WSImportCell *imports;uint32_t importCount;const WSFunctionMeta *functions;uint32_t functionCount;const WSHook *hooks;uint32_t hookCount;} WSBlob;\n']
    descriptors = []
    for label, module, original, code, code2, functions, imports, hooks in blobs:
        fields = relocated_fields(code, code2, [(f[0], f[1]) for f in functions], delta)
        output.append(bytes_array(label+'_code', code))
        output.append('static const WSRelocation '+label+'_relocs[] = {'+','.join('{'+str(v)+'}' for v in fields)+'};\n')
        if imports:
            output.append('static const WSImportCell '+label+'_imports[] = {'+','.join('{'+str(at)+',"'+name+'"}' for at, name in imports)+'};\n')
        for index, f in enumerate(functions):
            output.append(bytes_array(label+'_unwind_'+str(index), f[2]))
        output.append('static const WSFunctionMeta '+label+'_functions[] = {'+
                      ','.join('{'+f'{begin},{end},{label}_unwind_{index},{len(unwind)}'+'}'
                               for index, (begin, end, unwind) in enumerate(functions))+'};\n')
        for index, (_, before, _, _) in enumerate(hooks):
            output.append(bytes_array(label+'_before_'+str(index), before))
        output.append('static const WSHook '+label+'_hooks[] = {'+
                      ','.join('{'+f'{rva},{len(before)},{label}_before_{index},{target},{call}'+'}'
                               for index, (rva, before, target, call) in enumerate(hooks))+'};\n')
        sha = ','.join(f'0x{x:02x}' for x in hashlib.sha256(original).digest())
        descriptors.append('{L"'+module+'",{'+sha+'},'+
                           f'{label}_code,{len(code)},{label}_relocs,{len(fields)},'+
                           (f'{label}_imports,{len(imports)},' if imports else '0,0,')+
                           f'{label}_functions,{len(functions)},{label}_hooks,{len(hooks)}'+'}')
        print(label, 'code bytes', len(code), 'rel32 fields', len(fields), 'hooks', len(hooks))
    output.append('static const WSBlob wsBlobs[] = {'+','.join(descriptors)+'};\n')
    (HERE / 'runtime_test_blobs.h').write_text(''.join(output))


if __name__ == '__main__':
    main()
