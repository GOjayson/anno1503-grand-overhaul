"""Development copy-only bridge around the actual HE scene factory call.

Preserves seven native Windows x64 arguments and passes the original factory
as an eighth argument to an in-process runtime export. This does not by itself
establish that a prepared world or its validation is correct.
"""
from pathlib import Path
import hashlib
import json
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'engine_audit'))
from patch_frame_copy import align, pe_info, checksum, transform_frame
from bridge_codegen import PROLOG, EPILOG, COMMON_UNWIND

EXPECTED_FLAG_FRAME_SHA = '1fec477921f9f2f74afcfd2eb6cd67dd82bb2fcf0a18b901ce743b413314fb8d'
FACTORY_CALL_RVA = 0x55c54
FACTORY_IAT_RVA = 0x9e300
FACTORY_CALL_BYTES = bytes.fromhex('ff15a6860400')


def build_factory_code(rva):
    code = bytearray(PROLOG)
    symbols = {'factory_bridge': rva}
    fixups = []

    def emit(value):
        code.extend(bytes.fromhex(value) if isinstance(value, str) else value)

    def relative(prefix, target):
        emit(prefix)
        at = len(code)
        emit(bytes(4))
        fixups.append((at, target))

    # At entry, native args 5..7 are at old RSP+28h/30h/38h. The reviewed
    # common prologue moves RSP down B8h and leaves it 16-byte aligned.
    emit('4989cc4989d54d89c64d89cf')  # r12=rcx,r13=rdx,r14=r8,r15=r9
    emit('488b9c24e0000000488bb424e8000000488bbc24f0000000')
    emit('4c89e14c89ea4d89f04d89f9')
    emit('48895c2420488974242848897c2430')
    relative('488b05', FACTORY_IAT_RVA)
    emit('4889442438')
    relative('ff15', 'factory_export_iat')
    emit(EPILOG)
    symbols['factory_bridge_end'] = rva + len(code)
    while len(code) % 8:
        emit('00')
    symbols['factory_export_iat'] = rva + len(code)
    emit(bytes(16))
    symbols['factory_export_ilt'] = rva + len(code)
    emit(bytes(16))
    symbols['dll_name'] = rva + len(code)
    emit(b'AnnoWorldSettings.dll\0')
    while len(code) % 2:
        emit('00')
    symbols['export_name'] = rva + len(code)
    emit(b'\0\0WorldSettingsCreateScene\0')
    for name in ['factory_export_iat', 'factory_export_ilt']:
        struct.pack_into('<QQ', code, symbols[name] - rva, symbols['export_name'], 0)
    for at, target in fixups:
        if isinstance(target, str):
            target = symbols[target]
        struct.pack_into('<i', code, at, target - (rva + at + 4))
    return bytes(code), symbols


def transform_flag_frame(original):
    if hashlib.sha256(original).hexdigest() != EXPECTED_FLAG_FRAME_SHA:
        raise ValueError('Unrecognized flag-hook Frame fingerprint')
    pe, opt, table, sections, off = pe_info(original)
    sa, fa = struct.unpack_from('<II', original, opt + 32)
    header_at = table + len(sections) * 40
    if original[header_at:header_at+40] != bytes(40) or header_at+40 > min(s[4] for s in sections):
        raise ValueError('No free PE section header')
    if original[off(FACTORY_CALL_RVA):off(FACTORY_CALL_RVA)+6] != FACTORY_CALL_BYTES:
        raise ValueError('Scene factory call preimage differs')
    rva = align(max(s[2]+max(s[1], s[3]) for s in sections), sa)
    raw = align(len(original), fa)
    code, symbols = build_factory_code(rva)
    payload = bytearray(code)
    old_import, _ = struct.unpack_from('<II', original, opt+112+8)
    descriptors = []
    at = off(old_import)
    while original[at:at+20] != bytes(20):
        descriptors.append(original[at:at+20])
        at += 20
        if len(descriptors) > 128:
            raise ValueError('Import descriptor guard exceeded')
    payload += bytes(align(len(payload), 4)-len(payload))
    new_import = rva + len(payload)
    payload += b''.join(descriptors)
    payload += struct.pack('<IIIII', symbols['factory_export_ilt'], 0, 0,
                           symbols['dll_name'], symbols['factory_export_iat']) + bytes(20)
    old_pdata, old_size = struct.unpack_from('<II', original, opt+112+3*8)
    if old_size % 12:
        raise ValueError('Malformed original runtime function table')
    entries = [struct.unpack_from('<III', original, off(old_pdata)+i)
               for i in range(0, old_size, 12)]
    payload += bytes(align(len(payload), 4)-len(payload))
    unwind = rva + len(payload)
    payload += COMMON_UNWIND
    entries.append((symbols['factory_bridge'], symbols['factory_bridge_end'], unwind))
    entries.sort()
    if any(a[1] > b[0] for a, b in zip(entries, entries[1:])):
        raise ValueError('Overlapping exception entries')
    payload += bytes(align(len(payload), 4)-len(payload))
    pdata = rva + len(payload)
    payload += b''.join(struct.pack('<III', *entry) for entry in entries)
    result = bytearray(original)
    hook = b'\xe8' + struct.pack('<i', symbols['factory_bridge']-FACTORY_CALL_RVA-5) + b'\x90'
    pos = off(FACTORY_CALL_RVA)
    result[pos:pos+6] = hook
    struct.pack_into('<H', result, pe+6, len(sections)+1)
    struct.pack_into('<I', result, opt+4,
                     struct.unpack_from('<I', original, opt+4)[0]+align(len(payload), fa))
    struct.pack_into('<I', result, opt+56, align(rva+len(payload), sa))
    struct.pack_into('<II', result, opt+112+8, new_import, (len(descriptors)+2)*20)
    struct.pack_into('<II', result, opt+112+3*8, pdata, len(entries)*12)
    result[header_at:header_at+40] = struct.pack(
        '<8sIIIIIIHHI', b'.wload\0\0', len(payload), rva, align(len(payload), fa),
        raw, 0, 0, 0, 0, 0x60000020)
    result += bytes(raw-len(result)) + payload + bytes(align(len(payload), fa)-len(payload))
    struct.pack_into('<I', result, opt+64, checksum(result))
    return bytes(result), dict(symbols=symbols, input_sha256=EXPECTED_FLAG_FRAME_SHA,
                              output_sha256=hashlib.sha256(result).hexdigest(),
                              section=dict(rva=rva, raw=raw, size=len(payload)))


def transform_full_frame(original):
    flag_frame, flag_metadata = transform_frame(original)
    result, factory_metadata = transform_flag_frame(flag_frame)
    return result, dict(flag_bridge=flag_metadata, factory_bridge=factory_metadata)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('Usage: frame_factory_bridge.py INPUT_FRAME OUTPUT_COPY')
    source, output = (Path(v).resolve() for v in sys.argv[1:])
    if source == output or output == HERE.parent / 'AnnoFrame.dll':
        raise SystemExit('Refusing to overwrite the source/live Frame')
    result, metadata = transform_full_frame(source.read_bytes())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(result)
    output.with_suffix('.factory.json').write_text(json.dumps(metadata, indent=2))
    print(json.dumps(metadata, indent=2))
