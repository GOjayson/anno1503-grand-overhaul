"""Derive a Food-free World native profile from exact, locally owned inputs.

World bridge sections retain their reviewed RVAs/imports/unwind tables. Food
changes in original mapped sections are restored only when the World overlay
has not changed those bytes. Unreachable historical Food section storage stays
in the PE layout; no original Food entry hook, data change or AI candidate is
retained. This byte-level derivation is not a gameplay certification.
"""
from __future__ import annotations

import base64
import hashlib
import json
import struct
from typing import Mapping


FOOD_SPEC_SHA256 = 'aa88900d4f55661720c5927ba7e66cb3dc3dfaa17a55ddedb89d4fb5a61bdae5'
WORLD_SPEC_SHA256 = 'f43d4a136a0625836889a1379a70ecb60c589aa34d7acdc9a75db5206e2b5fec'
PROFILE = 'world-only-vanilla-v1'
WORLD_ONLY_NATIVE_SHA256 = {
    'AnnoFrame.dll':'e56b45c7abc6895f05fecd9277f389a88c6c8c7bf3c54a66003bb8d9245a3589',
    'AnnoScene.dll':'b23a8cd2f2979e812c0dc1f573929bddeaa230f35d59512eb1ce8431c732a320',
    'AnnoWelt.dll':'d53297beb5e24e4fa304b60ce039ee7b3223bf893714ec3a9dc17fa0bdf29d19',
    'WorldSettingsAI/CompLogic.dll':'bbf15a8aa0a06f2fb484cb38df741ff8f8d63f479de9d05afbf0c453b2c96fd9',
    'WorldSettingsAI/CompLogicClassic.dll':'7592ca081ac7fe8d3011b64c5ea868b125a8b5e358c0c4a9e365b1329d0a1dcd',
}
WORLD_ONLY_AI_SHA256 = {name:WORLD_ONLY_NATIVE_SHA256['WorldSettingsAI/'+name]
                       for name in ('CompLogic.dll','CompLogicClassic.dll')}
_STOCK_AI_SHA256 = {
    'CompLogic.dll':'a8218ef1a1ba9cbe929f2c32430ebd5647e750e2df2af6733808d7314a80c483',
    'CompLogicClassic.dll':'d005f6505b41a4648d9cc75573cdebf74174f89c2091fcf32a8e019c20246b2e',
}
_FROZEN_AI_SHA256 = {
    'CompLogic.dll':'0612873c32c95252144f4b4fd2bed45dddddc177303981833b673ddc4ed51453',
    'CompLogicClassic.dll':'29d1759bd3beb39f9a5a3364946a24b36f8bb4fa546c6a999b6ca994aeeaab34',
}


class NativeProfileError(ValueError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _spec(raw: bytes, expected: str, name: str) -> dict:
    if not isinstance(raw, bytes) or sha(raw) != expected:
        raise NativeProfileError('Unreviewed ' + name + ' specification.')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise NativeProfileError('Duplicate specification field.')
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=pairs)
    if not isinstance(value, dict):
        raise NativeProfileError('Expected a specification object.')
    return value


def _pe(data: bytes) -> dict:
    try:
        if not isinstance(data, bytes) or len(data) < 64 or data[:2] != b'MZ':
            raise NativeProfileError('Expected an immutable AMD64 PE image.')
        pe, = struct.unpack_from('<I', data, 60)
        if data[pe:pe+4] != b'PE\0\0' or struct.unpack_from('<H', data, pe+4)[0] != 0x8664:
            raise NativeProfileError('Native input is not AMD64.')
        count, = struct.unpack_from('<H', data, pe+6)
        size, = struct.unpack_from('<H', data, pe+20)
        opt = pe + 24
        if size < 240 or struct.unpack_from('<H', data, opt)[0] != 0x20b:
            raise NativeProfileError('Native input is not PE32+.')
        header_size, = struct.unpack_from('<I', data, opt+60)
        table = opt + size
        if not 0 < count <= 64 or table + count*40 > header_size or header_size > len(data):
            raise NativeProfileError('Native section table is invalid.')
        sections = []
        for index in range(count):
            at = table + 40*index
            name = data[at:at+8].rstrip(b'\0').decode('ascii')
            virtual_size, rva, raw_size, raw = struct.unpack_from('<IIII', data, at+8)
            if raw_size and (raw < header_size or raw + raw_size > len(data)):
                raise NativeProfileError('Native section leaves its file.')
            sections.append(dict(name=name, virtual_size=virtual_size, rva=rva, size=raw_size, raw=raw))
        if len({s['name'] for s in sections}) != count:
            raise NativeProfileError('Native section names are ambiguous.')
        ranges = sorted((s['raw'], s['raw']+s['size']) for s in sections if s['size'])
        if any(a[1] > b[0] for a, b in zip(ranges, ranges[1:])):
            raise NativeProfileError('Native sections overlap.')
        return dict(pe=pe, opt=opt, table=table, header_size=header_size, sections=sections,
                    image_base=struct.unpack_from('<Q', data, opt+24)[0])
    except (struct.error, UnicodeError, IndexError) as exc:
        raise NativeProfileError('Native PE headers are truncated.') from exc


def checksum(data: bytes) -> int:
    """Windows PE checksum, excluding its own DWORD."""
    info = _pe(data)
    at = info['opt'] + 64
    value = bytearray(data)
    value[at:at+4] = bytes(4)
    if len(value) & 1:
        value.append(0)
    total = 0
    for index in range(0, len(value), 2):
        total += value[index] | (value[index+1] << 8)
        total = (total & 0xffff) + (total >> 16)
    total = (total & 0xffff) + (total >> 16)
    return (total & 0xffff) + len(data)


def _align(n: int, alignment: int) -> int:
    if alignment <= 0 or alignment & (alignment-1):
        raise NativeProfileError('Native alignment is unsupported.')
    return (n + alignment - 1) & -alignment


def _offset(info: dict, rva: int, length: int = 1) -> int:
    matches = [s for s in info['sections'] if s['rva'] <= rva and rva+length <= s['rva']+s['size']]
    if len(matches) != 1:
        raise NativeProfileError('Native RVA does not map to one section.')
    return matches[0]['raw'] + rva - matches[0]['rva']


def _policy_code(rva: int, setter: int) -> bytes:
    """Same tiny flag-preserver as the reviewed World policy candidate."""
    code, labels, fixups = bytearray(), {}, []
    def add(value): code.extend(bytes.fromhex(value))
    def branch(opcode, target):
        add(opcode)
        fixups.append((len(code), target))
        code.extend(bytes(4))
    add('83be4c0a00000c');branch('0f85','store')
    add('448b9eb80a00004589da4181e20000ffff')
    add('4181fa00005357');branch('0f85','store')
    add('4189c24181e20000ffff4181fa00005357');branch('0f84','store')
    add('4181e300ffffff25ff0000004409d8')
    labels['store'] = rva + len(code)
    add('8986b80a0000');branch('e9',setter+6)
    for at, target in fixups:
        target = labels[target] if isinstance(target, str) else target
        struct.pack_into('<i', code, at, target-rva-at-4)
    return bytes(code)


def _policy_ai(stock: bytes, frozen: bytes, name: str) -> tuple[bytes, dict]:
    """Stock AI plus only World difficulty-tag preservation, with full unwind."""
    info, prior = _pe(stock), _pe(frozen)
    setter = {'CompLogic.dll':0x6542, 'CompLogicClassic.dll':0x48c2}[name]
    original_store = bytes.fromhex('8986b80a0000')
    at = _offset(info, setter, 6)
    if stock[at:at+6] != original_store:
        raise NativeProfileError('Vanilla AI setter preimage differs.')
    old_at = _offset(prior, setter, 6)
    old_hook = frozen[old_at:old_at+6]
    if len(old_hook) != 6 or old_hook[0] != 0xe9 or old_hook[-1] != 0x90:
        raise NativeProfileError('Frozen World AI setter hook differs.')
    old_rva = setter+5+struct.unpack_from('<i',old_hook,1)[0]
    old_code = _policy_code(old_rva, setter)
    old_offset = _offset(prior, old_rva, len(old_code))
    if frozen[old_offset:old_offset+len(old_code)] != old_code:
        raise NativeProfileError('Frozen World AI preserver differs from its reviewed generator.')
    section_align, file_align = struct.unpack_from('<II', stock, info['opt']+32)
    rva = _align(max(s['rva']+max(s['virtual_size'],s['size']) for s in info['sections']), section_align)
    raw = _align(len(stock), file_align)
    code = _policy_code(rva, setter)
    pdata, pdata_size = struct.unpack_from('<II', stock, info['opt']+112+3*8)
    if not pdata_size or pdata_size % 12:
        raise NativeProfileError('Stock AI exception directory is invalid.')
    pdata_at = _offset(info, pdata, pdata_size)
    entries = [struct.unpack_from('<III',stock,pdata_at+i) for i in range(0,pdata_size,12)]
    parent = next((e for e in entries if e[0] <= setter < e[1]), None)
    if parent is None:
        raise NativeProfileError('Stock AI setter unwind parent is missing.')
    seen = set()
    while True:
        if parent in seen:
            raise NativeProfileError('Cyclic stock AI unwind chain.')
        seen.add(parent)
        uw = _offset(info, parent[2], 4)
        version_flags, prologue, count, frame = stock[uw:uw+4]
        if version_flags & 7 != 1:
            raise NativeProfileError('Stock AI unwind version differs.')
        if not version_flags >> 3 & 4:
            break
        chain = _align(4+count*2,4)
        parent = struct.unpack_from('<III',stock,_offset(info,parent[2]+chain,12))
        if parent not in entries:
            raise NativeProfileError('Stock AI unwind chain parent is not registered.')
    payload = bytearray(code)
    payload.extend(bytes(_align(len(payload),4)-len(payload)))
    unwind_rva = rva + len(payload)
    payload.extend(bytes.fromhex('21000000') + struct.pack('<III',*parent))
    entries.append((rva,rva+len(code),unwind_rva))
    entries.sort()
    if any(a[1] > b[0] for a,b in zip(entries,entries[1:])):
        raise NativeProfileError('AI exception functions overlap.')
    payload.extend(bytes(_align(len(payload),4)-len(payload)))
    new_pdata = rva + len(payload)
    payload.extend(b''.join(struct.pack('<III',*entry) for entry in entries))
    output = bytearray(stock)
    header = info['table'] + 40*len(info['sections'])
    if header+40 > info['header_size'] or output[header:header+40] != bytes(40):
        raise NativeProfileError('No spare section header for World AI policy.')
    output[at:at+6] = b'\xe9'+struct.pack('<i',rva-setter-5)+b'\x90'
    struct.pack_into('<H',output,info['pe']+6,len(info['sections'])+1)
    size = _align(len(payload),file_align)
    struct.pack_into('<I',output,info['opt']+4,struct.unpack_from('<I',stock,info['opt']+4)[0]+size)
    struct.pack_into('<I',output,info['opt']+56,_align(rva+len(payload),section_align))
    struct.pack_into('<II',output,info['opt']+112+3*8,new_pdata,len(entries)*12)
    output[header:header+40] = struct.pack('<8sIIIIIIHHI',b'.wspolcy',len(payload),rva,size,raw,0,0,0,0,0x60000020)
    output.extend(bytes(raw-len(output))+payload+bytes(size-len(payload)))
    struct.pack_into('<I',output,info['opt']+64,checksum(bytes(output)))
    result = bytes(output)
    _pe(result)
    # Every original mapped byte apart from the one World setter hook remains
    # exactly stock. No Food market/demand/production rewrite is copied.
    for section in info['sections']:
        begin, end = section['raw'], section['raw']+section['size']
        actual, expected = bytearray(result[begin:end]), bytearray(stock[begin:end])
        if begin <= at and at+6 <= end:
            actual[at-begin:at-begin+6] = original_store
        if actual != expected:
            raise NativeProfileError('World AI policy changed an unrelated original section byte.')
    return result, dict(setter_store_rva=setter, hook_bytes=result[at:at+6].hex(),
                        helper_rva=rva, helper_size=len(code),
                        frozen_helper_rva=old_rva, frozen_helper_exact=True,
                        chained_unwind_parent=list(parent),
                        preserved_original_section_bytes_except_hook=True,
                        food_market_demand_production_rewrites=False)


def derive_ai_candidate(name: str, stock: bytes, frozen: bytes) -> bytes:
    """Derive only the one reviewed World flag hook on an exact stock AI DLL."""
    if name not in _STOCK_AI_SHA256:
        raise NativeProfileError('Unknown World AI module.')
    if sha(stock) != _STOCK_AI_SHA256[name] or sha(frozen) != _FROZEN_AI_SHA256[name]:
        raise NativeProfileError('World AI input differs from its inspected fingerprint.')
    result, proof = _policy_ai(stock,frozen,name)
    if sha(result) != WORLD_ONLY_AI_SHA256[name]:
        raise NativeProfileError('Derived World AI output differs from its reviewed profile.')
    return result


def derive_public_ai_candidate(name: str, stock: bytes) -> bytes:
    """Construct the reviewed stock-only World AI without a Food payload.

    This additive beta path retains the historical constructor unchanged.
    Both native inputs and complete outputs remain exact fingerprint pins.
    """
    if name not in _STOCK_AI_SHA256 or not isinstance(stock, bytes) or sha(stock) != _STOCK_AI_SHA256[name]:
        raise NativeProfileError('Public World AI construction requires the exact supported stock module.')
    info = _pe(stock)
    setter = {'CompLogic.dll':0x6542, 'CompLogicClassic.dll':0x48c2}[name]
    original_store = bytes.fromhex('8986b80a0000')
    at = _offset(info, setter, 6)
    if stock[at:at+6] != original_store:
        raise NativeProfileError('Vanilla AI setter preimage differs.')
    section_align, file_align = struct.unpack_from('<II', stock, info['opt']+32)
    rva = _align(max(s['rva']+max(s['virtual_size'],s['size']) for s in info['sections']), section_align)
    raw = _align(len(stock), file_align)
    code = _policy_code(rva, setter)
    pdata, pdata_size = struct.unpack_from('<II', stock, info['opt']+112+3*8)
    if not pdata_size or pdata_size % 12:
        raise NativeProfileError('Stock AI exception directory is invalid.')
    pdata_at = _offset(info, pdata, pdata_size)
    entries = [struct.unpack_from('<III',stock,pdata_at+i) for i in range(0,pdata_size,12)]
    parent = next((e for e in entries if e[0] <= setter < e[1]), None)
    if parent is None:
        raise NativeProfileError('Stock AI setter unwind parent is missing.')
    seen = set()
    while True:
        if parent in seen:
            raise NativeProfileError('Cyclic stock AI unwind chain.')
        seen.add(parent)
        uw = _offset(info, parent[2], 4)
        version_flags, prologue, count, frame = stock[uw:uw+4]
        if version_flags & 7 != 1:
            raise NativeProfileError('Stock AI unwind version differs.')
        if not version_flags >> 3 & 4:
            break
        chain = _align(4+count*2,4)
        parent = struct.unpack_from('<III',stock,_offset(info,parent[2]+chain,12))
        if parent not in entries:
            raise NativeProfileError('Stock AI unwind chain parent is not registered.')
    payload = bytearray(code)
    payload.extend(bytes(_align(len(payload),4)-len(payload)))
    unwind_rva = rva + len(payload)
    payload.extend(bytes.fromhex('21000000') + struct.pack('<III',*parent))
    entries.append((rva,rva+len(code),unwind_rva))
    entries.sort()
    if any(a[1] > b[0] for a,b in zip(entries,entries[1:])):
        raise NativeProfileError('AI exception functions overlap.')
    payload.extend(bytes(_align(len(payload),4)-len(payload)))
    new_pdata = rva + len(payload)
    payload.extend(b''.join(struct.pack('<III',*entry) for entry in entries))
    output = bytearray(stock)
    header = info['table'] + 40*len(info['sections'])
    if header+40 > info['header_size'] or output[header:header+40] != bytes(40):
        raise NativeProfileError('No spare section header for World AI policy.')
    output[at:at+6] = b'\xe9'+struct.pack('<i',rva-setter-5)+b'\x90'
    struct.pack_into('<H',output,info['pe']+6,len(info['sections'])+1)
    size = _align(len(payload),file_align)
    struct.pack_into('<I',output,info['opt']+4,struct.unpack_from('<I',stock,info['opt']+4)[0]+size)
    struct.pack_into('<I',output,info['opt']+56,_align(rva+len(payload),section_align))
    struct.pack_into('<II',output,info['opt']+112+3*8,new_pdata,len(entries)*12)
    output[header:header+40] = struct.pack('<8sIIIIIIHHI',b'.wspolcy',len(payload),rva,size,raw,0,0,0,0,0x60000020)
    output.extend(bytes(raw-len(output))+payload+bytes(size-len(payload)))
    struct.pack_into('<I',output,info['opt']+64,checksum(bytes(output)))
    result = bytes(output)
    _pe(result)
    # Every original mapped byte apart from the one World setter hook remains
    # exactly stock. No Food market/demand/production rewrite is copied.
    for section in info['sections']:
        begin, end = section['raw'], section['raw']+section['size']
        actual, expected = bytearray(result[begin:end]), bytearray(stock[begin:end])
        if begin <= at and at+6 <= end:
            actual[at-begin:at-begin+6] = original_store
        if actual != expected:
            raise NativeProfileError('World AI policy changed an unrelated original section byte.')
    if sha(result) != WORLD_ONLY_AI_SHA256[name]:
        raise NativeProfileError('The public stock-only AI output differs from its reviewed fingerprint.')
    return result


def _food_forward(original: bytes, entry: dict) -> bytes:
    if sha(original) != entry['sources']['vanilla']:
        raise NativeProfileError('The original native fingerprint differs: ' + entry['name'])
    change = entry['changes'].get(sha(original))
    if not change:
        raise NativeProfileError('No exact vanilla Food recipe: ' + entry['name'])
    output = bytearray(original)
    occupied = set()
    for patch in change['patches']:
        offset, before, after = patch['offset'], bytes.fromhex(patch['before']), bytes.fromhex(patch['after'])
        if type(offset) is not int or offset < 0 or len(before) != len(after) or offset+len(before) > len(original):
            raise NativeProfileError('Invalid native Food patch.')
        locations = set(range(offset, offset+len(before)))
        if occupied & locations or original[offset:offset+len(before)] != before:
            raise NativeProfileError('Food preimage overlap or mismatch.')
        occupied.update(locations)
        output[offset:offset+len(before)] = after
    output += base64.b64decode(change['append_base64'], validate=True)
    output = bytes(output[:change['result_size']])
    if sha(output) != entry['after_sha256']:
        raise NativeProfileError('Reconstructed Food baseline differs: ' + entry['name'])
    _pe(output)
    return output


def _restore_food_body(original: bytes, food: bytes, world: bytes, entry: dict) -> tuple[bytes, dict]:
    """Keep World PE metadata while removing every original-section Food edit."""
    stock_info, food_info, world_info = (_pe(data) for data in (original, food, world))
    if len({info['image_base'] for info in (stock_info, food_info, world_info)}) != 1:
        raise NativeProfileError('Native image bases differ.')
    # World transformations append sections; the original sections keep their
    # loader mapping. Every original-section Food mutation can thus be restored
    # without relocating any World code or changing its imports/unwind entries.
    for stock in stock_info['sections']:
        candidates = [s for s in world_info['sections'] if s['name'] == stock['name']]
        if len(candidates) != 1 or any(candidates[0][key] != stock[key] for key in ('rva', 'raw', 'size')):
            raise NativeProfileError('World changed an original section mapping.')
    output = bytearray(world)
    body, header = [], []
    change = entry['changes'][entry['sources']['vanilla']]
    for patch in change['patches']:
        at = patch['offset']
        before, after = bytes.fromhex(patch['before']), bytes.fromhex(patch['after'])
        if at < stock_info['header_size']:
            if at+len(before) > stock_info['header_size']:
                raise NativeProfileError('Food patch crosses the header boundary.')
            header.append(dict(offset=at, length=len(before)))
            continue
        section = [s for s in stock_info['sections'] if s['raw'] <= at and at+len(before) <= s['raw']+s['size']]
        if len(section) != 1:
            raise NativeProfileError('Food body patch is not in one original mapped section.')
        if food[at:at+len(after)] != after or world[at:at+len(after)] != after:
            raise NativeProfileError('World and Food patches overlap: ' + entry['name'])
        output[at:at+len(before)] = before
        body.append(dict(offset=at, rva=section[0]['rva']+at-section[0]['raw'], length=len(before),
                         before_sha256=sha(after), after_sha256=sha(before)))
    # This is the only PE metadata recomputed here. The remaining header is
    # exactly the reviewed World header; removing its appended section layout
    # would invalidate World import cells, branches and exception metadata.
    struct.pack_into('<I', output, world_info['opt']+64, checksum(bytes(output)))
    result = bytes(output)
    expected = bytearray(world)
    for patch in change['patches']:
        if patch['offset'] >= stock_info['header_size']:
            raw = bytes.fromhex(patch['before'])
            expected[patch['offset']:patch['offset']+len(raw)] = raw
    struct.pack_into('<I', expected, world_info['opt']+64, checksum(bytes(expected)))
    if result != bytes(expected):
        raise NativeProfileError('World profile changed unrelated bytes.')
    return result, dict(restored_food_body_edits=body, retained_world_header=True,
                       retained_layout_food_header_fields=header,
                       inert_food_sections=[s['name'] for s in world_info['sections'] if s['name']=='.fmarket'],
                       original_sections_keep_mapping=True)


def derive_native_profile(vanilla_native: Mapping[str, bytes], frozen_payloads: Mapping[str, bytes], *,
                          food_spec: bytes, world_spec: bytes) -> tuple[dict[str, bytes], dict]:
    """Read-only, pinned derivation; no game module is loaded or modified.

    ``vanilla_native`` contains the six Food-affected original DLLs. The Scene
    source is supplied by the frozen pinned World payload. Return keys are
    installation target paths; Game and View remain byte-exact vanilla and
    are deliberately absent from the edit set.
    """
    food = _spec(food_spec, FOOD_SPEC_SHA256, 'Food')
    world = _spec(world_spec, WORLD_SPEC_SHA256, 'World')
    if world.get('version') != '0.11.0-dev.1' or world.get('status') != 'UNFINISHED':
        raise NativeProfileError('Unsupported World profile.')
    payload_map = world['payloads']
    if set(frozen_payloads) != set(payload_map):
        raise NativeProfileError('Frozen payload inventory differs.')
    for name, digest in payload_map.items():
        data = frozen_payloads[name]
        if not isinstance(data, bytes) or sha(data) != digest:
            raise NativeProfileError('Frozen payload fingerprint differs: ' + name)
        if name.startswith('native/'):
            _pe(data)
    entries = {entry['name']: entry for entry in food['native_modules']}
    if set(vanilla_native) != set(entries):
        raise NativeProfileError('All six original native modules are required.')
    baseline = {}
    for name, entry in entries.items():
        _pe(vanilla_native[name])
        baseline[name] = _food_forward(vanilla_native[name], entry)
    outputs, proofs = {}, {}
    for name, overlay in world['native_overlays'].items():
        source = frozen_payloads[overlay['baseline_payload']]
        result = frozen_payloads[overlay['output_payload']]
        if name in entries:
            if baseline[name] != source:
                raise NativeProfileError('World overlay is not based on exact Food output: ' + name)
            result, proofs[name] = _restore_food_body(vanilla_native[name], source, result, entries[name])
        else:
            if name != 'AnnoScene.dll':
                raise NativeProfileError('Unknown World-only native overlay.')
            if sha(source) != world['source_baselines'][name]:
                raise NativeProfileError('Scene source fingerprint differs.')
            proofs[name] = dict(food_edits=0, preserved_exact_world_overlay=True)
        outputs[name] = result
    if set(outputs) != {'AnnoFrame.dll', 'AnnoScene.dll', 'AnnoWelt.dll'}:
        raise NativeProfileError('World overlay set differs.')
    # The old private AI images contain Food-specific goods/market/production
    # rewrites. Rebuild from stock, retaining only the tiny World flag policy.
    for name in ('CompLogic.dll', 'CompLogicClassic.dll'):
        payload = 'native/' + name.replace('.dll','.food-ai.dll')
        outputs['WorldSettingsAI/' + name], proofs[name] = _policy_ai(vanilla_native[name],frozen_payloads[payload],name)
    source_hashes = {name: sha(data) for name, data in vanilla_native.items()}
    source_hashes['AnnoScene.dll'] = world['source_baselines']['AnnoScene.dll']
    report = dict(schema=1, profile=PROFILE, food_enabled=False,
                  source_native_sha256=source_hashes,
                  output_sha256={name:sha(data) for name,data in outputs.items()},
                  output_sizes={name:len(data) for name,data in outputs.items()},
                  native_proofs=proofs,
                  unchanged_vanilla_modules=['AnnoGame.dll','View.dll','CompLogic.dll','CompLogicClassic.dll'],
                  private_ai_are_vanilla_plus_world_policy=True, actual_game_test_performed=False)
    if report['output_sha256'] != WORLD_ONLY_NATIVE_SHA256:
        raise NativeProfileError('Derived World native output differs from its reviewed profile.')
    return outputs, report
