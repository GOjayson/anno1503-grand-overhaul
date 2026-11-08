"""Build two private AMD64 war-policy candidates on the approved Food AI payloads.

Only the six-byte native SPEZFLAG store is redirected in each AI DLL. All war
requests remain native and are filtered once at the central AnnoWelt endpoint.
No original game file or existing payload is modified.
"""
from pathlib import Path
import hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'WorldSettings_Work/engine_audit'))
sys.path.insert(0,str(ROOT/'WorldSettings_Work/engine_resume/ai_food'))
from audit import Module
from code_support import Extension

SPEC={
 'CompLogic.dll':dict(source='CompLogic.food-ai.dll',sha='e247ef8b755354cb5c9b2ff21bf81a5dd25646ee2012ac8204162a54daa72d9d',hook=0x407f7,resume=0x407fe,deny=0x40802,helper=0x40770,vtable=0x88128,setter_store=0x6542),
 'CompLogicClassic.dll':dict(source='CompLogicClassic.food-ai.dll',sha='c2e101508bfb5aee0da3d4abd13f3281baccbf4762a26ff3f90f9e1fbc354556',hook=0x3de07,resume=0x3de0e,deny=0x3de12,helper=0x3dd80,vtable=0x84fc8,setter_store=0x48c2),
}

def build_preserver(c,s):
    # Native scripts can later replace SPEZFLAG through public setter 29.
    # Preserve an existing mod tag on those native low-flag updates, while an
    # incoming correctly tagged COMP record can restore its saved full value.
    c.add('83 be 4c 0a 00 00 0c');c.branch('0f85','store')
    c.add('44 8b 9e b8 0a 00 00 45 89 da 41 81 e2 00 00 ff ff')
    c.add('41 81 fa 00 00 53 57');c.branch('0f85','store')
    c.add('41 89 c2 41 81 e2 00 00 ff ff 41 81 fa 00 00 53 57')
    c.branch('0f84','store')
    c.add('41 81 e3 00 ff ff ff 25 ff 00 00 00 44 09 d8')
    c.mark('store');c.add('89 86 b8 0a 00 00');c.branch('e9',s['setter_store']+6)

def main():
    manifest=dict(scope=__doc__,tag='0x57530000',native_flags_mask='0x000000ff',mode_mask='0x00000300',counter_mask='0x0000fc00',cadence=[0,4,2,1],payloads=[])
    source=ROOT/'WorldSettings_Work/anno1503_food_world_dev3_cityfix1/native'
    for name,s in SPEC.items():
        p=source/s['source'];m=Module(str(p));assert hashlib.sha256(m.data).hexdigest()==s['sha']
        assert m.pe.FILE_HEADER.Machine==0x8664 and m.pe.OPTIONAL_HEADER.Magic==0x20b
        assert m.image[s['hook']:s['hook']+7]==bytes.fromhex('41ff9210020000')
        assert m.image[s['deny']:s['deny']+2]==bytes.fromhex('32c0')
        ext=Extension(m)
        assert m.image[s['setter_store']:s['setter_store']+6]==bytes.fromhex('8986b80a0000')
        preserver=ext.function('preserve_policy_on_native_flag_updates',s['setter_store'],lambda c:build_preserver(c,s))
        ext.jump(s['setter_store'],s['setter_store']+6,preserver)
        raw=ext.finish(lambda data: __import__('pefile').PE(data=bytes(data)).generate_checksum())
        out=HERE/(name.replace('.dll','.food-world-policy.dll'));out.write_bytes(raw)
        manifest['payloads'].append(dict(module=name,source=str(p.relative_to(ROOT)),source_sha256=s['sha'],output=out.name,sha256=hashlib.sha256(raw).hexdigest(),native_declaration_helper_rva=s['helper'],native_declaration_call_rva=s['hook'],vtable_rva=s['vtable'],setter_store_rva=s['setter_store'],preserver_rva=preserver,edits=[dict(rva=at,preimage=before.hex(),patch=after.hex()) for at,before,after in ext.edits],unwind=ext.functions))
    (HERE/'candidate_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n','utf-8')
    print(json.dumps({p['module']:p['sha256'] for p in manifest['payloads']},indent=2))
if __name__=='__main__':main()
