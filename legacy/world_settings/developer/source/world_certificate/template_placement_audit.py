"""Bounded source-only terrain/production metadata audit, never a live check.

The reviewed original loader decodes both six-byte GELAENDE and PROD2 records.
Anlagen HEAD bytes0/1 are native dimension getters; rotation parity swaps them.
No claim about pathfinding, production yield, collision masks or native trade.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE.parent / 'world_data'))
from scene_catalogue import SceneError, chunks, read_container, island_chunks


def definitions(path):
    """Read the small definitions chunk without reading texture payloads."""
    with path.open('rb') as stream:
        header = stream.read(16)
        if header[:12] != b'ANNO'.ljust(12, b'\0'):
            raise SceneError('Unsupported Anlagen container')
        end = 16 + struct.unpack_from('<I', header, 12)[0]
        if end != path.stat().st_size:
            raise SceneError('Anlagen root size mismatch')
        at = 16
        data = None
        while at < end:
            stream.seek(at)
            header = stream.read(16)
            if len(header) != 16:
                raise SceneError('Short Anlagen chunk')
            size = struct.unpack_from('<I', header, 12)[0]
            if size > end - at - 16:
                raise SceneError('Anlagen chunk crosses root')
            if header[:12] == b'ANLAGEN'.ljust(12, b'\0'):
                if data is not None or size > 8 * 1024 * 1024:
                    raise SceneError('Duplicate or excessive Anlagen definitions')
                data = stream.read(size)
            at += size + 16
    if data is None:
        raise SceneError('Missing Anlagen definitions')
    result = {}
    for entry in chunks(data, 0, len(data)):
        if entry.tag != 'ENTRY' or entry.length < 8:
            raise SceneError('Unsupported Anlagen entry')
        _, ident = struct.unpack_from('<II', entry.payload)
        if ident in result:
            raise SceneError('Duplicate Anlagen definition')
        fields = {}
        for field in chunks(entry.payload, 8, len(entry.payload)):
            if field.tag in fields:
                raise SceneError('Duplicate Anlagen field')
            fields[field.tag] = field.payload
        head = fields.get('HEAD', b'')
        if len(head) not in (36, 44, 48, 52, 56):
            raise SceneError('Unsupported Anlagen HEAD')
        result[ident] = dict(width=head[0], height=head[1],
                             production=fields.get('PRODTYPE', b'').rstrip(b'\0').decode('cp1252'),
                             goods=[v.decode('cp1252') for v in fields.get('WARE', b'').split(b'\0') if v])
    return result


def placements(payload):
    if len(payload) < 6 or (len(payload) - 6) % 6:
        raise SceneError('Terrain/production chunk has a partial record')
    if len(payload) > 6 + 65536 * 6:
        raise SceneError('Terrain/production traversal cap exceeded')
    origin_x, origin_y, width, height = struct.unpack_from('<HHBB', payload)
    if not width or not height:
        raise SceneError('Zero terrain/production tile extent')
    for at in range(6, len(payload), 6):
        packed, flags, stage, dx, dy = struct.unpack_from('<HBBbb', payload, at)
        yield dict(definition=packed & 0x3fff, rotation=packed >> 14,
                   flags=flags & 63, stage=stage,
                   x=(origin_x + dx) & 0xffff, y=(origin_y + dy) & 0xffff)


def inspect(data, defs):
    root, _ = read_container(data)
    island = [part for part in chunks(data, 16, root.end) if part.tag == 'INSEL5']
    if len(island) != 1:
        raise SceneError('Expected exactly one island')
    geometry, parts = island_chunks(island[0])
    origin_x, origin_y, width, height, _ = geometry
    count = Counter()
    for part in parts:
        if part.tag not in ('GELAENDE', 'PROD2'):
            continue
        for record in placements(part.payload):
            definition = defs.get(record['definition'])
            if definition is None:
                raise SceneError('Unknown placed definition')
            # All catalogued island origins are zero; use explicit local bounds.
            x, y = record['x'], record['y']
            if not (0 <= x < width and 0 <= y < height):
                raise SceneError('Placed anchor outside source island')
            count[part.tag] += 1
            if part.tag == 'GELAENDE':
                for good in ('BAUM', 'FISCH', 'EISFISCH'):
                    if good in definition['goods']:
                        count[good] += 1
            else:
                w, h = definition['width'], definition['height']
                if record['rotation'] & 1:
                    w, h = h, w
                if not w or not h or x + w > width or y + h > height:
                    raise SceneError('Rotated production bounds outside source island')
                count['production_goods_' + ','.join(definition['goods'])] += 1
    if origin_x or origin_y:
        raise SceneError('Unreviewed nonzero source island origin')
    return count


def sha_file(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    sources = [ROOT / 'Anlagen.dat', ROOT / 'Anlagen.addon']
    variants = [definitions(path) for path in sources]
    catalogue = json.loads((HERE.parent / 'world_data/catalogue.json').read_text())
    climates = [dict(climate=i, templates=0, terrain_records=0,
                     production_records=0, templates_with_trees=0,
                     tree_records=0, templates_with_stored_fish=0,
                     stored_fish_records=0, culture_production_records=0) for i in range(6)]
    totals = Counter()
    for template in catalogue['templates']:
        raw = (ROOT / template['path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == template['sha256'], template['path']
        observations = [inspect(raw, defs) for defs in variants]
        assert observations[0] == observations[1], template['path']
        counts = observations[0]
        if template['climate_index']:
            assert counts['BAUM'] > 0, template['path']
        summary = climates[template['climate_index']]
        summary['templates'] += 1
        summary['terrain_records'] += counts['GELAENDE']
        summary['production_records'] += counts['PROD2']
        summary['templates_with_trees'] += bool(counts['BAUM'])
        summary['tree_records'] += counts['BAUM']
        summary['templates_with_stored_fish'] += bool(counts['FISCH'])
        summary['stored_fish_records'] += counts['FISCH']
        if template['cultures']:
            summary['culture_production_records'] += counts['PROD2']
        totals.update(counts)
    report = dict(scope=__doc__, templates=443, variants=[dict(path=p.name, sha256=sha_file(p)) for p in sources],
                  terrain_anchor_records=totals['GELAENDE'], production_bounds_records=totals['PROD2'],
                  tree_records=totals['BAUM'], fish_records=totals['FISCH'], climates=climates,
                  note='Stored FISCH counts are observations, not a validity requirement. Most stock templates contain none.')
    (HERE / 'template_placement_audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f"PASS: 443 original templates x2 definition variants; {totals['GELAENDE']} terrain anchors; {totals['PROD2']} production bounds; all417 nonpolar templates have BAUM objects.")


if __name__ == '__main__':
    main()
