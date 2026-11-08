"""Read all actual stock single-endless language/root files; emit exact paths."""
from pathlib import Path
import hashlib
import json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]


def main():
    folders=[ROOT/'Scenes']
    folders += [p/'Scenes' for p in sorted((ROOT/'Languages').iterdir()) if p.is_dir()]
    records=[]
    for folder in folders:
        for category in ['0010SingleEndlos','0011SingleEndlosAddon']:
            for source in sorted((folder/category).glob('*.sze')):
                data=source.read_bytes();relative=source.relative_to(ROOT).as_posix().replace('/','\\')
                assert relative.isascii()
                records.append(dict(path=relative,filename=source.name,sha256=hashlib.sha256(data).hexdigest()))
    assert records and len({r['path'].lower() for r in records})==len(records)
    lines=['/* Exact actual installed single-endless source paths and SHA256. */',
           'typedef struct WSStockEndlessPath { const char *path; unsigned char sha256[32]; } WSStockEndlessPath;',
           'static const WSStockEndlessPath wsStockEndlessPaths[] = {']
    for row in records:
        digest=','.join('0x'+row['sha256'][i:i+2] for i in range(0,64,2))
        lines.append('{'+json.dumps(row['path'])+',{'+digest+'}},')
    lines.append('};')
    (HERE/'stock_endless_paths.h').write_text('\n'.join(lines)+'\n',encoding='ascii')
    (HERE/'stock_endless_paths.json').write_text(json.dumps(dict(scope='Actual source paths, not native MD5 globals or a game run',records=records),indent=2)+'\n')
    print(json.dumps(dict(records=len(records),languages=sorted({r['path'].split('\\')[1] for r in records if r['path'].startswith('Languages\\')}))))


if __name__=='__main__':main()
