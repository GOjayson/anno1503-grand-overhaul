"""Adversarial/synthetic native-save fixtures for the read-only fertility inspector."""
from pathlib import Path
import copy,hashlib,importlib.util,json,struct
HERE=Path(__file__).resolve().parent
GAME=next(p for p in HERE.parents if (p/'Anno1503.exe').is_file() and (p/'WorldSettings_Work/_tools').is_dir())
PACKAGE=next((p for p in HERE.parents if (p/'world_patch.json').is_file()),GAME/'WorldSettings_Work/anno1503_food_world_dev5')
SOURCE=PACKAGE/'developer/fertility/inspect_fertility_save.py'
spec=importlib.util.spec_from_file_location('fertility_save',SOURCE);mod=importlib.util.module_from_spec(spec)
import sys;sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
def chunk(tag,payload):return tag.encode().ljust(12,b'\0')+struct.pack('<I',len(payload))+payload
def occurrence(ident,x,y,quantity=0):
    body=struct.pack('<IfffHHI',ident<<14,x,y,0,quantity,0,0)
    if ident==1559:body=body[:16]+b'WHALE'
    return b'ENTRY2'+struct.pack('<H',len(body))+body
ids={1:1661,2:1561,4:1562,8:1563,32:1564}
def definition(mineral_level='very'):
    rows=[]
    low={2:37,4:2,5:8}
    for climate in range(6):
        mask=(mod.CROP_MASKS[climate]|0xf009)&0x1fff
        ore_mask=mod.ORE_MASKS[climate] if mineral_level=='very' else low.get(climate,0)
        deposits=[]
        for j,bit in enumerate(b for b in [1,2,4,8,32] if ore_mask&b):deposits.append([ids[bit],20+j*10,20,400 if bit==1 else 2000])
        if climate:
            while len(deposits)<3:deposits.append([1661,20+len(deposits)*10,20,0])
        rows.append(dict(climate=climate,x=16+climate*80,y=16,mask=mask,deposits=deposits))
    return rows
def save(rows):
    islands=[]
    for ident,row in enumerate(rows):
        climate=row['climate'];crop_names=[n for i,n in enumerate(mod.CROPS) if row['mask']&(1<<i)]
        names=b''.join(n.encode('cp1252')+b'\0' for n in crop_names)
        height=chunk('HEIGHT',struct.pack('<HHBB',0,0,64,64)+bytes([48])*(64*64))
        info=bytes([climate])+bytes(11)
        raw=struct.pack('<HHHHI',row['x'],row['y'],64,64,ident)
        raw+=chunk('INFO',info)+height+chunk('FRUCHTBAR',bytes([15 if climate else 0])*(64*64))+chunk('ANBAU',names)
        occurrences=b''.join(occurrence(*d) for d in row['deposits'])
        if climate==0:occurrences+=occurrence(1559,20,20)
        raw+=chunk('OCCUR',occurrences);islands.append(chunk('INSEL5',raw))
    return chunk('ANNOADDON1',b''.join(islands))
checks=[]
def accepted(label,rows,plant='very',minerals='very',baseline=None):
    result=mod.inspect(save(rows),plant,minerals,baseline);assert result['passed'];checks.append(dict(case=label,passed=True));return result
def rejected(label,mutate,rows=None,plant='very',minerals='very',baseline=None):
    rows=copy.deepcopy(rows if rows is not None else definition());mutate(rows)
    try:mod.inspect(save(rows),plant,minerals,baseline)
    except ValueError as e:checks.append(dict(case=label,rejected=True,message=str(e)));return
    raise AssertionError('Accepted invalid state: '+label)
very=accepted('valid Very/Very synthetic native save',definition())
lowrows=definition('low');low=accepted('valid Low/Low essentials and persistent ore-free islands',lowrows,'low','low')
assert low['positive_saved_quantity_total']==5 and low['ore_free_island_count']==3
accepted('identical Low reload availability',lowrows,'low','low',low)
rows=copy.deepcopy(lowrows);rows[2]['deposits'][0][3]-=1
accepted('positive mine quantity may change on reload',rows,'low','low',low)
for mode in ['medium','mixed']:accepted('valid '+mode+' bounds with essential anchors',definition(),mode,mode)
rejected('zero unassigned deep iron revives on reload',lambda r:r[1]['deposits'].__setitem__(0,[1560,20,20,0]),lowrows,'low','low')
rejected('zero unassigned gold revives on reload',lambda r:r[1]['deposits'].__setitem__(0,[1561,20,20,0]),lowrows,'low','low')
rejected('positive old deep iron does not match new policy',lambda r:r[2]['deposits'][0].__setitem__(0,1560))
rejected('Low extra positive deposit',lambda r:r[1]['deposits'][0].__setitem__(3,400),lowrows,'low','low')
rejected('Very unused eligible slot',lambda r:r[1]['deposits'][1].__setitem__(0,1661) or r[1]['deposits'][1].__setitem__(3,0))
rejected('missing essential salt',lambda r:r[2]['deposits'][1].__setitem__(0,1661) or r[2]['deposits'][1].__setitem__(3,0),lowrows,'low','low')
rejected('duplicate distinct good on one island',lambda r:r[2]['deposits'][1].__setitem__(0,1661))
rejected('ore climate mismatch',lambda r:r[1]['deposits'][0].__setitem__(0,1561))
rejected('ore outside island',lambda r:r[2]['deposits'][0].__setitem__(1,1000))
rejected('duplicate ore coordinate',lambda r:r[2]['deposits'][1].__setitem__(1,20))
rejected('missing native forced grain flag',lambda r:r[0].__setitem__('mask',r[0]['mask']&~1))
rejected('unsupported tropical favorable crop in North',lambda r:r[2].__setitem__('mask',r[2]['mask']|(1<<7)))
rejected('Very lacks supported favorable wine',lambda r:r[2].__setitem__('mask',r[2]['mask']&~(1<<6)))
rejected('missing sole herbs coverage',lambda r:r[2].__setitem__('mask',r[2]['mask']&~(1<<11)),plant='mixed',minerals='mixed')
rejected('island rectangles overlap',lambda r:r[1].__setitem__('x',r[0]['x']))
mixed=accepted('Mixed baseline uses serialized masks',definition(),'mixed','mixed')
rejected('baseline detects changed per-island crop flags',lambda r:r[2].__setitem__('mask',r[2]['mask']&~(1<<6)),plant='mixed',minerals='mixed',baseline=mixed)
rejected('baseline detects changed zero occurrence position',lambda r:r[1]['deposits'][2].__setitem__(1,51),plant='mixed',minerals='mixed',baseline=mixed)
data=save(definition())
for bad,label in [(data[:-1],'truncated parent'),(data+b'X','trailing bytes'),(data.replace(b'GETREIDE',b'UNKNOWNX',1),'unknown native crop name')]:
    try:mod.inspect(bad,'very','very')
    except ValueError as e:checks.append(dict(case=label,rejected=True,message=str(e)))
    else:raise AssertionError('Accepted malformed '+label)
report=dict(scope=__doc__,passed=True,cases=len(checks),results=checks,inspector_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            game_executed=False,source_or_actual_saves_modified=False)
(HERE/'fertility_save_inspector_tests.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(passed=True,cases=len(checks),inspector_sha256=report['inspector_sha256']),indent=2))
