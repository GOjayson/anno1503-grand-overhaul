"""Build the exact Food-only house-panel derivative from preserved Food 0.5.

Five existing house-view virtual entries delegate to their native bodies and
append a read-only summary. No resident, goods or saved-object layout grows.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import struct
import subprocess
import tempfile

from .filesystem import checked_path
from .world_native import _pe, _offset, _align, checksum
from .world_runtime_build import PE, normalize_pe_metadata

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'src/anno1503_overhaul/native/food_household.c'
COMPILER_SHA256 = '086ce9d47ba42f33a514e1a6e04eb1d4a8fa1d75e0868e0213caad447c91e864'
FOOD05_VIEW_SHA256 = '9d03d19a8bc08af748bd23785a063736ad63b8302c1fdd0af392e534778e6ba2'
FOOD06_VIEW_SHA256 = 'b5af6086d34a614a31f4c30a83c9fc9b213dee186a660394dbe664776ec160b2'
HOUSE_VTABLE = 0xb1758
HOOKS = {0xe0: ('food_set_house', 0x804a0), 0xf0: ('food_layout', 0x80be0),
         0x128: ('food_create', 0x80ee0), 0x140: ('food_tick', 0x80460),
         0x148: ('food_update', 0x80490)}


class FoodHouseholdError(ValueError):
    pass


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _compiler(path):
    path = checked_path(Path(path))
    if not path.is_file() or _sha(path.read_bytes()) != COMPILER_SHA256:
        raise FoodHouseholdError('Select the reviewed offline Zig 0.16.0 Windows compiler.')
    options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    run = subprocess.run([str(path), 'version'], capture_output=True, text=True,
                         timeout=20, check=False, **options)
    if run.returncode or run.stdout.strip() != '0.16.0':
        raise FoodHouseholdError('The Food compiler version differs.')
    return path, options


def compile_payload(compiler_path):
    """Compile only authored C; this never reads or modifies a game process."""
    compiler, options = _compiler(compiler_path)
    with tempfile.TemporaryDirectory(prefix='anno-food-household-') as name:
        folder = Path(name)
        source = folder / 'food_household.c'
        source.write_bytes(SOURCE.read_bytes())
        output = folder / 'food_household.dll'
        command = [str(compiler), 'cc', '-target', 'x86_64-windows-gnu', '-std=c11',
                   '-shared', '-nostdlib', '-O2', '-g0', '-fno-builtin',
                   '-fno-stack-protector', '-Wall', '-Wextra', '-Werror',
                   str(source), '-o', str(output)]
        run = subprocess.run(command, capture_output=True, text=True,
                             timeout=120, check=False, **options)
        if run.returncode or not output.is_file():
            raise FoodHouseholdError('Food display compilation failed: ' + run.stderr[-8000:])
        raw, normalized = normalize_pe_metadata(output.read_bytes())
    pe = PE(raw)
    if pe.directory(1) != (0, 0) or pe.directory(13) != (0, 0):
        raise FoodHouseholdError('The display unexpectedly imports external functions.')
    return raw, dict(compiler_sha256=COMPILER_SHA256, compiler_version='0.16.0',
                     source_sha256=_sha(SOURCE.read_bytes()), payload_sha256=_sha(raw),
                     normalized_metadata=normalized)


def _exports(pe):
    rva, size = pe.directory(0)
    if not rva or size < 40:
        raise FoodHouseholdError('Missing authored display exports.')
    header = struct.unpack('<IIHHIIIIIII', pe.read(rva, 40))
    functions, count, table, names, ordinals = header[6:11]
    if not 1 <= functions <= 64 or not 1 <= count <= 64:
        raise FoodHouseholdError('Unexpected display export count.')
    result = {}
    for i in range(count):
        name_rva = struct.unpack('<I', pe.read(names + 4*i, 4))[0]
        value = bytearray()
        for j in range(96):
            byte = pe.read(name_rva+j, 1)[0]
            if not byte: break
            value.append(byte)
        else: raise FoodHouseholdError('Unbounded display export name.')
        ordinal = struct.unpack('<H', pe.read(ordinals + 2*i, 2))[0]
        if ordinal >= functions:
            raise FoodHouseholdError('Display export ordinal leaves its table.')
        target = struct.unpack('<I', pe.read(table + 4*ordinal, 4))[0]
        if not pe.executable(target, 1):
            raise FoodHouseholdError('A display export is not local executable code.')
        result[value.decode('ascii')] = target
    required = {'food_measure', 'food_position', 'food_refresh'} | {name for name, _ in HOOKS.values()}
    if set(result) != required:
        raise FoodHouseholdError('The display export closure differs.')
    return result


def _relocations(pe):
    rva, size = pe.directory(5)
    if not rva and not size: return set()
    raw = pe.read(rva, size)
    at, result = 0, set()
    while at < size:
        if at+8 > size: raise FoodHouseholdError('Truncated relocation page.')
        page, length = struct.unpack_from('<II', raw, at)
        if length < 8 or length % 4 or at+length > size:
            raise FoodHouseholdError('Invalid relocation page.')
        for n in range(at+8, at+length, 2):
            entry = struct.unpack_from('<H', raw, n)[0]
            if not entry: continue
            if entry >> 12 != 10:
                raise FoodHouseholdError('Only reviewed AMD64 DIR64 relocations are supported.')
            target = page+(entry & 4095)
            if target in result: raise FoodHouseholdError('Duplicate native relocation.')
            pe.read(target, 8)
            result.add(target)
        at += length
    return result


def _relocation_bytes(entries):
    result = bytearray()
    for page in sorted({rva & ~4095 for rva in entries}):
        values = [0xa000 | (rva & 4095) for rva in sorted(entries) if rva & ~4095 == page]
        if len(values) & 1: values.append(0)
        result += struct.pack('<II', page, 8+len(values)*2) + struct.pack('<'+'H'*len(values), *values)
    return bytes(result)


def _construct_view(food05, authored):
    if not isinstance(food05, bytes) or _sha(food05) != FOOD05_VIEW_SHA256:
        raise FoodHouseholdError('The house display requires its exact preserved Food 0.5 View.')
    old, extra = PE(food05), PE(authored)
    info = _pe(food05)
    base = struct.unpack_from('<Q', food05, old.optional+24)[0]
    if struct.unpack_from('<Q', authored, extra.optional+24)[0] != base:
        raise FoodHouseholdError('The display preferred image base differs.')
    if extra.directory(1) != (0, 0) or extra.directory(13) != (0, 0):
        raise FoodHouseholdError('Unexpected authored imports.')
    symbols = _exports(extra)
    occupied = [s for s in extra.sections if s['raw_size'] or s['virtual']]
    start = min(s['rva'] for s in occupied)
    end = max(s['rva']+max(s['raw_size'], s['virtual']) for s in occupied)
    if end-start > 1024*1024 or any(s['flags'] & 0x80000000 for s in occupied):
        raise FoodHouseholdError('Unexpected writable or oversized display data.')
    section_align, file_align = struct.unpack_from('<II', food05, old.optional+32)
    rva = _align(old.image_size, section_align)
    delta = rva-start
    payload = bytearray(end-start)
    for section in occupied:
        a = section['rva']-start
        payload[a:a+section['raw_size']] = authored[section['raw']:section['raw']+section['raw_size']]
    relocations = _relocations(old)
    extra_relocs = _relocations(extra)
    for at in extra_relocs:
        where = at-start
        if not 0 <= where <= len(payload)-8:
            raise FoodHouseholdError('A display relocation leaves the copied image.')
        value = struct.unpack_from('<Q', payload, where)[0]
        if not base+start <= value < base+end:
            raise FoodHouseholdError('A display absolute pointer leaves authored storage.')
        struct.pack_into('<Q', payload, where, value+delta)
        relocations.add(at+delta)
    entries = sorted(old.function_table())
    new_entries = []
    for begin, finish, unwind in sorted(extra.function_table()):
        if extra.read(unwind, 1)[0] != 1:
            raise FoodHouseholdError('Only ordinary version-one display unwind records are reviewed.')
        new_entries.append((begin+delta, finish+delta, unwind+delta))
    entries = sorted(entries+new_entries)
    if any(a[1] > b[0] for a, b in zip(entries, entries[1:])):
        raise FoodHouseholdError('Display unwind functions overlap.')
    payload += bytes(_align(len(payload), 4)-len(payload))
    pdata = (rva+len(payload), len(entries)*12)
    payload += b''.join(struct.pack('<III', *row) for row in entries)
    payload += bytes(_align(len(payload), 4)-len(payload))
    reloc_data = _relocation_bytes(relocations)
    reloc = (rva+len(payload), len(reloc_data))
    payload += reloc_data
    table_at = info['table']+len(info['sections'])*40
    if table_at+40 > min(s['raw'] for s in info['sections'] if s['size']) or food05[table_at:table_at+40] != bytes(40):
        raise FoodHouseholdError('No blank native section-header slot is available.')
    result = bytearray(food05)
    edits = []
    for slot, (name, before) in HOOKS.items():
        at = _offset(info, HOUSE_VTABLE+slot, 8)
        if struct.unpack_from('<Q', food05, at)[0] != base+before:
            raise FoodHouseholdError('A native house-view virtual preimage differs.')
        target = symbols[name]+delta
        struct.pack_into('<Q', result, at, base+target)
        edits.append(dict(slot=slot, original_rva=before, target_rva=target, symbol=name))
    raw = _align(len(result), file_align)
    raw_size = _align(len(payload), file_align)
    result[table_at:table_at+40] = struct.pack('<8sIIIIIIHHI', b'.food06', len(payload), rva,
        raw_size, raw, 0, 0, 0, 0, 0x60000060)
    struct.pack_into('<H', result, old.pe+6, len(info['sections'])+1)
    struct.pack_into('<I', result, old.optional+4, struct.unpack_from('<I', result, old.optional+4)[0]+raw_size)
    struct.pack_into('<I', result, old.optional+56, _align(rva+len(payload), section_align))
    struct.pack_into('<II', result, old.optional+112+3*8, *pdata)
    struct.pack_into('<II', result, old.optional+112+5*8, *reloc)
    result += bytes(raw-len(result))+payload+bytes(raw_size-len(payload))
    struct.pack_into('<I', result, old.optional+64, checksum(bytes(result)))
    output = bytes(result)
    checked = PE(output)
    if checked.function_table() != set(entries) or checked.directory(1) != old.directory(1):
        raise FoodHouseholdError('The composed native tables differ.')
    return output, dict(input_sha256=_sha(food05), output_sha256=_sha(output),
        payload_sha256=_sha(authored), section_rva=rva, section_size=len(payload),
        hooks=edits, functions_added=len(new_entries), relocated_absolute_pointers=len(extra_relocs),
        exports={name:at+delta for name,at in symbols.items()}, actual_game_test_performed=False)


def build_view(food05_bytes, compiler_path):
    if not isinstance(FOOD06_VIEW_SHA256, str) or len(FOOD06_VIEW_SHA256) != 64:
        raise FoodHouseholdError('The Food display candidate has not completed its build review.')
    payload, compiler = compile_payload(compiler_path)
    result, proof = _construct_view(food05_bytes, payload)
    if _sha(result) != FOOD06_VIEW_SHA256:
        raise FoodHouseholdError('The compiled Food display differs from its reviewed fingerprint.')
    return result, dict(proof, compiler=compiler)
