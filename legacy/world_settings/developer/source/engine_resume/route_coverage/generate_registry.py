"""Generate private exact-selection registry from the existing installed data."""
from pathlib import Path
import hashlib
import json
import sys
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'WorldSettings_Work/world_data'))
from scene_catalogue import chunks


def main():
    cache = (ROOT / 'Scenes/Scenes.cach').read_bytes()
    records = []
    for entry in chunks(cache, 0, len(cache)):
        p = entry.payload
        assert entry.tag == 'ENTRY' and len(p) == 384
        folder = p[24:72].split(b'\0')[0].decode('ascii')
        filename = p[72:120].split(b'\0')[0].decode('ascii')
        if '\\0010SingleEndlos\\' not in folder and '\\0011SingleEndlosAddon\\' not in folder:
            continue
        assert p[0] == 2
        source = ROOT / folder / filename
        data = source.read_bytes()
        assert data[128:144] == p[8:24]
        records.append(dict(filename=filename, path=str(source.relative_to(ROOT)),
                            sha256=hashlib.sha256(data).hexdigest(),
                            md5=hashlib.md5(data).hexdigest(),
                            scene_guid=p[8:24].hex(),
                            title=p[120:376].split(b'\0')[0].decode('cp1252')))
    assert len(records) == 12 and len({r['filename'].lower() for r in records}) == 12
    lines = ['/* Generated exact current stock single-endless selections. */',
             'typedef struct WSStockEndless { const char *filename; unsigned char md5[16]; } WSStockEndless;',
             'static const WSStockEndless wsStockEndless[] = {']
    for row in records:
        digest = ','.join('0x'+row['md5'][i:i+2] for i in range(0, 32, 2))
        lines.append('{'+json.dumps(row['filename'])+',{'+digest+'}},')
    lines.append('};')
    (HERE / 'stock_endless.h').write_text('\n'.join(lines)+'\n', encoding='ascii')
    (HERE / 'stock_endless.json').write_text(json.dumps(dict(
        scope='Original installed single-endless scene identities; not game execution',
        cache_sha256=hashlib.sha256(cache).hexdigest(), records=records), indent=2)+'\n', encoding='utf-8')
    print('Registered', len(records), 'original single-endless selections')


if __name__ == '__main__': main()
