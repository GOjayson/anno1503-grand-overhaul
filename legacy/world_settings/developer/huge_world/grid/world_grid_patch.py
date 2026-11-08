"""Exact AMD64 History Edition World lookup relocation.

This module never writes a game file or process. The caller owns installation
and must apply all edits before a World object can be created.
"""
from pathlib import Path
import hashlib
import json
import struct
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
for parent in (HERE, *HERE.parents):
    for candidate in (parent / '_tools', parent / 'WorldSettings_Work' / '_tools'):
        if (candidate / 'pefile.py').exists():
            sys.path.insert(0, str(candidate))
            break
import pefile

ORIGINAL_SHA256 = 'ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9'
DEV7_SHA256 = '059ecd1dcb2139b350f50a2805d811eff89e61cead2733ca9aedb6da83058319'
PLAN_SHA256 = 'e5f1506096f3cc88093e27fcade2c903d1622b0cff1781e63eb3bc10f063e81b'
GRID_OFFSET = 0x10000
GRID_BYTES = 0x10000
ALLOCATION_BYTES = 0x20000
SOURCE_HASHES = frozenset((ORIGINAL_SHA256, DEV7_SHA256))
# Filled after deterministic generation; these identify exact, complete output.
PATCHED_HASHES = {
    '8c3fef5ffc23303ccbb90eface8977899a03e4bbffd314e8ef9f4b92b238a48d': ORIGINAL_SHA256,
    '3d05583144039da2b477509b60fbfc3e70f75cad23a2a666cb8a3ecf07c94c6f': DEV7_SHA256,
}


def sha256(blob):
    return hashlib.sha256(blob).hexdigest()


def _source_plan():
    blob = (HERE / 'grid_plan_source.json').read_bytes()
    if sha256(blob) != PLAN_SHA256:
        raise ValueError('World grid source plan fingerprint mismatch')
    source = json.loads(blob)
    entries = [(item, GRID_OFFSET) for item in source['grid_relocation_candidates']]
    entries += [(item, GRID_BYTES) for item in source['clear_lengths']]
    entries += [(source['allocation'], ALLOCATION_BYTES)]
    entries += [(item, ALLOCATION_BYTES) for item in source['sized_delete_metadata']]
    if len(entries) != 104:
        raise ValueError('Expected exactly 104 World grid instruction sites')
    return entries


def instruction_edits():
    """Machine-readable instruction guards and four-byte operand edits.

    RVA is the instruction start, operand_rva is the actual write address.
    For an in-memory transaction check all complete before_instruction values
    before writing any after bytes, and roll all writes back on any failure.
    """
    output = []
    for item, target in _source_plan():
        rva = int(item['rva'], 0)
        operand = item['encoded_operand_offset']
        before = bytes.fromhex(item['native_instruction'])
        expected = struct.pack('<I', int(item['expected_operand'], 0))
        if item['encoded_operand_bytes'] != 4 or before[operand:operand + 4] != expected:
            raise ValueError('Source plan operand preimage mismatch')
        after = bytearray(before)
        after[operand:operand + 4] = struct.pack('<I', target)
        output.append(dict(rva=rva, operand_rva=rva + operand,
                           operand_offset=operand, size=4,
                           before=expected.hex(), after=struct.pack('<I', target).hex(),
                           before_instruction=before.hex(), after_instruction=after.hex(),
                           role=item['role'], assembly=item['assembly']))
    output.sort(key=lambda item: item['rva'])
    for left, right in zip(output, output[1:]):
        if left['rva'] + len(bytes.fromhex(left['before_instruction'])) > right['rva']:
            raise ValueError('Overlapping World grid instruction edits')
    for item in output:
        for hook, length in ((0xc714d, 6), (0xdf460, 6)):
            if max(item['rva'], hook) < min(item['rva'] + len(bytes.fromhex(item['before_instruction'])), hook + length):
                raise ValueError('World grid edit overlaps an existing Food/World hook')
    return output


def _validate_pe(blob):
    try:
        pe = pefile.PE(data=blob, fast_load=True)
    except Exception as exc:
        raise ValueError('Invalid World PE image') from exc
    if pe.FILE_HEADER.Machine != 0x8664 or pe.OPTIONAL_HEADER.Magic != 0x20b:
        raise ValueError('Only the exact AMD64 PE32+ History Edition is supported')
    return pe


def transform_welt_grid(blob):
    """Return (patched bytes, manifest); reject unknown or partially edited input."""
    if not isinstance(blob, bytes):
        raise TypeError('World image must be immutable bytes')
    digest = sha256(blob)
    known_patched = digest in PATCHED_HASHES
    if digest not in SOURCE_HASHES and not known_patched:
        raise ValueError('Unsupported World DLL fingerprint: ' + digest)
    pe = _validate_pe(blob)
    edits = instruction_edits()
    patched = bytearray(blob)
    changed_offsets = set()
    for item in edits:
        expected = bytes.fromhex(item['after_instruction'] if known_patched else item['before_instruction'])
        offset = pe.get_offset_from_rva(item['rva'])
        if blob[offset:offset + len(expected)] != expected:
            raise ValueError('World instruction guard mismatch at RVA ' + hex(item['rva']))
        section = pe.get_section_by_rva(item['rva'])
        if section is None or not section.Characteristics & 0x20000000:
            raise ValueError('World patch site is not executable')
        operand_offset = offset + item['operand_offset']
        patched[operand_offset:operand_offset + 4] = bytes.fromhex(item['after'])
        changed_offsets.update(range(operand_offset, operand_offset + 4))
        item['file_offset'] = offset
        item['operand_file_offset'] = operand_offset
    output = bytes(patched)
    if len(output) != len(blob) or any(a != b and pos not in changed_offsets for pos, (a, b) in enumerate(zip(blob, output))):
        raise ValueError('Unexpected bytes changed outside World grid operands')
    manifest = dict(schema=1, component='World island lookup grid',
        architecture='AMD64 PE32+', source_sha256=digest, output_sha256=sha256(output),
        idempotent=known_patched, source_plan_sha256=PLAN_SHA256,
        grid_offset=GRID_OFFSET, grid_bytes=GRID_BYTES, cell_tiles=8,
        allocation_bytes=ALLOCATION_BYTES, original_allocation_bytes=0x7068,
        pointer_table_offset=0x6640, island_id_sentinel=255,
        native_members_preserved=True, existing_welt_hooks_preserved=True,
        instruction_count=len(edits), operand_bytes=4 * len(edits), edits=edits,
        activation_requirement='Apply transaction before any World object exists',
        game_executed=False)
    return output, manifest


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    output, manifest = transform_welt_grid(args.input.read_bytes())
    args.output.write_bytes(output)
    args.output.with_suffix(args.output.suffix + '.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: manifest[key] for key in ('output_sha256', 'instruction_count', 'idempotent')}))


if __name__ == '__main__':
    main()
