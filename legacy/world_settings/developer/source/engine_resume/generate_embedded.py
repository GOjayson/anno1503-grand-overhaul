"""Reproducibly embed only inspected installation metadata and scene templates."""
from pathlib import Path
import json,sys,hashlib,re,struct
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'runtime'
OUT.mkdir(exist_ok=True)
c=json.loads((ROOT/'WorldSettings_Work/world_data/catalogue.json').read_text('utf-8'))
assert len(c['templates'])==443 and not c['failures']
cultures=c['cultures']

def profile_names(raw):
    """Read the sized native VOLK fields; never infer ownership from filenames."""
    names=[]
    for m in re.finditer(b'VOLK\0\0',raw):
        at=m.start()+6
        assert at+2<=len(raw), 'Truncated native VOLK size'
        size=struct.unpack_from('<H',raw,at)[0]
        value=raw[at+2:at+2+size]
        assert size and len(value)==size and value.endswith(b'\0') and b'\0' not in value[:-1], 'Malformed native VOLK field'
        names.append(value[:-1].decode('ascii'))
    return names

# Small and Large are explicit smallest/largest AVAILABLE template choices,
# separately for each climate and exact native culture group. This preserves
# Inuit/Native American templates where their largest size differs from an
# uninhabited island in the same climate. Medium remains strictly 128 tiles.
rows=[]
for t in c['templates']:
    raw=(ROOT/t['path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==t['sha256']
    names=profile_names(raw)
    assert names.count('SPIELER')==1
    bits=sum(1<<cultures.index(x) for x in set(names) if x in cultures)
    assert bits==sum(1<<cultures.index(x) for x in t['cultures'])
    excluded=sorted(set(names)-set(cultures)-{'SPIELER'})
    fertile=sum(n for f,n in t['land_fertility_low_nibble_histogram'].items() if int(f)>0)
    rows.append(dict(template=t,bits=bits,excluded=excluded,fertile=fertile,profiles=names))
group_widths={}
for row in rows:
    t=row['template']
    if not row['excluded'] and (row['fertile'] or t['climate_index']==0):
        group_widths.setdefault((t['climate_index'],row['bits']),set()).add(t['width'])
lines=['/* Generated from the current History Edition installation. */',
       'typedef struct WSTemplate { const char *path; unsigned short width,height; unsigned char climate,cultures,oreSlots,whales,excludedNative,sizeChoices; unsigned int fertileLand; unsigned char sha256[32]; } WSTemplate;',
       'static const WSTemplate wsTemplates[] = {']
for entry in rows:
    t=entry['template']
    bits=entry['bits']
    ore=sum(t['verified_mineral_counts'].values())
    whales=sum(x['native_definition_id']==1559 for x in t['occurrences'])
    assert ore<256 and whales<256
    widths=group_widths.get((t['climate_index'],bits),set())
    size_choices=0
    if widths and not entry['excluded'] and (entry['fertile'] or t['climate_index']==0):
        size_choices=(int(t['width']==min(widths)) | (int(t['width']==128)<<1) | (int(t['width']==max(widths))<<2))
    row=[json.dumps(t['path'].replace('/','\\')),str(t['width']),str(t['height']),str(t['climate_index']),str(bits),str(ore),str(whales),str(int(bool(entry['excluded']))),str(size_choices),str(entry['fertile']),'{'+','.join(str(x) for x in bytes.fromhex(t['sha256']))+'}']
    lines.append('{'+','.join(row)+'},')
lines.append('};')
for name,path in [('Easy','01_1024_easy_256.sze'),('Medium','03_1024_med_256.sze'),('Hard','06_1024_heavy_256.sze')]:
    p=ROOT/'Languages/Nl/Scenes/0010SingleEndlos'/path
    data=p.read_bytes()
    lines.append(f'/* {p.relative_to(ROOT).as_posix()} SHA256 {hashlib.sha256(data).hexdigest()} */')
    lines.append(f'static const unsigned char wsScene{name}[] = {{')
    lines.extend(','.join(str(x) for x in data[i:i+32])+',' for i in range(0,len(data),32))
    lines.append('};')
(OUT/'world_catalogue.h').write_text('\n'.join(lines)+'\n','ascii')
spawns=json.loads((ROOT/'WorldSettings_Work/world_certificate/stock_ship_spawns.json').read_text('utf-8'))
positions=sorted({(int(s['x'])-16,int(s['y'])-16) for scene in spawns for s in scene['ships']})
reserve=['/* Stock starting ships, conservative 16 tile radius; union across difficulty. */',
         'static const WSPlanIsland wsShipReserves[] = {']
reserve.extend('{0,%d,%d,33,33,0,0,0,0,0},'%pos for pos in positions)
reserve.append('};')
(OUT/'world_ship_reserves.h').write_text('\n'.join(reserve)+'\n','ascii')
inventory={'scope':'Inspected original assets; size choices are per climate and exact native culture group.',
           'forbidden_profile_names':sorted({name for r in rows for name in r['excluded']}),
           'excluded_templates':[r['template']['path'] for r in rows if r['excluded']],
           'size_groups':[dict(climate=climate,cultures=[cultures[i] for i in range(8) if bits&(1<<i)],small=min(widths),medium=128 if 128 in widths else None,large=max(widths),available=sorted(widths)) for (climate,bits),widths in sorted(group_widths.items())]}
(HERE/'template_size_policy.json').write_text(json.dumps(inventory,indent=2)+'\n','utf-8')
print(json.dumps({'templates':len(c['templates']),'excluded_native_templates':len(inventory['excluded_templates']),'output':str(OUT/'world_catalogue.h')},indent=2))
