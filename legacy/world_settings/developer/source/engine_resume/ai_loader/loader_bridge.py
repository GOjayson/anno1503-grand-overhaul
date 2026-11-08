"""Fingerprint-bound Welt loader call bridge; this file never patches installed files."""
from pathlib import Path
import hashlib
import struct
import sys

WORK = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORK / 'engine_audit'))
from patch_frame_copy import align, pe_info, checksum

WELT_SHA = 'ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9'
LOADER_RVA = 0xc714d
LOADER_BEFORE = bytes.fromhex('ff15dd2e0200')
LEAF_UNWIND = bytes([1, 0, 0, 0])

def build_loader_bridge(rva=0):
    # The original CALL already provides the caller's shadow area and return
    # address. A leaf tail jump changes neither; the C export has LoadLibraryA's
    # exact x64 signature. No game registers or stack arguments are repurposed.
    names = {'entry': rva, 'end': rva + 6, 'iat': rva + 8}
    code = bytearray(bytes.fromhex('ff2502000000cccc'))
    code += bytes(16)
    names['ilt'] = rva + len(code)
    code += bytes(16)
    names['dll_name'] = rva + len(code)
    code += b'AnnoWorldSettings.dll\0'
    code += bytes(align(len(code), 2) - len(code))
    names['export_name'] = rva + len(code)
    code += b'\0\0WorldSettingsLoadAiModule\0'
    for key in ['iat', 'ilt']:
        struct.pack_into('<QQ', code, names[key]-rva, names['export_name'], 0)
    return bytes(code), names

def transform_welt(original):
    if hashlib.sha256(original).hexdigest() != WELT_SHA:
        raise ValueError('Welt differs from the inspected AMD64 History Edition')
    pe, opt, table, sections, off = pe_info(original)
    if struct.unpack_from('<H', original, pe+4)[0] != 0x8664 or struct.unpack_from('<H', original, opt)[0] != 0x20b:
        raise ValueError('Welt is not AMD64 PE32+')
    if original[off(LOADER_RVA):off(LOADER_RVA)+6] != LOADER_BEFORE:
        raise ValueError('Welt LoadLibraryA call differs')
    header_at = table + len(sections)*40
    if original[header_at:header_at+40] != bytes(40) or header_at+40 > min(s[4] for s in sections):
        raise ValueError('Welt has no free PE section header')
    sa, fa = struct.unpack_from('<II', original, opt+32)
    rva = align(max(s[2]+max(s[1],s[3]) for s in sections), sa)
    raw = align(len(original), fa)
    code, names = build_loader_bridge(rva)
    payload = bytearray(code)
    old_import, old_size = struct.unpack_from('<II', original, opt+112+8)
    descriptors = []
    for count in range(128):
        at = off(old_import)+count*20
        descriptor = original[at:at+20]
        if len(descriptor) != 20:
            raise ValueError('Truncated Welt import descriptor')
        if descriptor == bytes(20): break
        descriptors.append(descriptor)
    else: raise ValueError('Unbounded Welt import table')
    payload += bytes(align(len(payload),4)-len(payload))
    imports = rva+len(payload)
    payload += b''.join(descriptors)+struct.pack('<IIIII', names['ilt'],0,0,names['dll_name'],names['iat'])+bytes(20)
    pdata, pdata_size = struct.unpack_from('<II', original, opt+112+3*8)
    if pdata_size % 12: raise ValueError('Malformed Welt exception directory')
    entries = [struct.unpack_from('<III', original, off(pdata)+i) for i in range(0,pdata_size,12)]
    payload += bytes(align(len(payload),4)-len(payload))
    unwind = rva+len(payload)
    payload += LEAF_UNWIND
    entries.append((names['entry'],names['end'],unwind))
    entries.sort()
    if any(a[1]>b[0] for a,b in zip(entries,entries[1:])): raise ValueError('Overlapping Welt exception entries')
    payload += bytes(align(len(payload),4)-len(payload))
    new_pdata = rva+len(payload)
    payload += b''.join(struct.pack('<III',*e) for e in entries)
    result = bytearray(original)
    struct.pack_into('<H',result,pe+6,len(sections)+1)
    struct.pack_into('<I',result,opt+4,struct.unpack_from('<I',result,opt+4)[0]+align(len(payload),fa))
    struct.pack_into('<I',result,opt+56,align(rva+len(payload),sa))
    struct.pack_into('<II',result,opt+112+8,imports,(len(descriptors)+2)*20)
    struct.pack_into('<II',result,opt+112+3*8,new_pdata,len(entries)*12)
    result[header_at:header_at+40] = struct.pack('<8sIIIIIIHHI',b'.wsaildr',len(payload),rva,align(len(payload),fa),raw,0,0,0,0,0x60000020)
    at=off(LOADER_RVA)
    result[at:at+6]=b'\xe8'+struct.pack('<i',rva-LOADER_RVA-5)+b'\x90'
    result += bytes(raw-len(result))+payload+bytes(align(len(payload),fa)-len(payload))
    struct.pack_into('<I',result,opt+64,checksum(result))
    return bytes(result), dict(source_sha256=WELT_SHA, hook_rva=LOADER_RVA,
                               hook_preimage=LOADER_BEFORE.hex(), wrapper_rva=rva,
                               code_sha256=hashlib.sha256(code).hexdigest(),
                               original_native_callers_preserved=True,
                               scope='Private AI loader experiment; no actual-game execution')
