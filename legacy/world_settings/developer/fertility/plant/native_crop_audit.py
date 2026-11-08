"""Inspect exact local AMD64 crop fields; writes only new research artifacts.

This is native-code/data inspection, not a running game or harvest test.
"""
from pathlib import Path
import hashlib, json, struct, sys

HERE=Path(__file__).resolve().parent
GAME=next(p for p in HERE.parents if (p/'Anno1503.exe').is_file())
PACKAGE=next((p for p in HERE.parents if (p/'developer/source/engine_audit/audit.py').is_file()),GAME/'WorldSettings_Work/anno1503_food_world_dev5')
sys.path.insert(0,str(GAME/'WorldSettings_Work/_tools'))
sys.path.insert(0,str(PACKAGE/'developer/source/engine_audit'))
from audit import Module
from capstone.x86_const import X86_OP_MEM, X86_REG_RIP

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    game=Module(str(GAME/'AnnoGame.dll'));welt=Module(str(GAME/'AnnoWelt.dll'));scene=Module(str(GAME/'AnnoScene.dll'))
    expected={
      'AnnoGame.dll':'e6f01d19e8e16e6716c0a6c7d3ba00273c9df493e051b8ba62865ee4b53dfdea',
      'AnnoWelt.dll':'ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9',
      'AnnoScene.dll':'f7d0685cf6156ff25c518f2f558863b351d7738280467e48dd585a1fefa9537a'}
    for m in [game,welt,scene]:
        assert sha(Path(m.name))==expected[Path(m.name).name]
        assert m.pe.FILE_HEADER.Machine==0x8664 and m.pe.OPTIONAL_HEADER.Magic==0x20b
    names=[]
    for i in range(17):
        at=struct.unpack_from('<Q',game.image,0x23400+8*i)[0]-game.base
        names.append(game.image[at:at+64].split(b'\0')[0].decode('cp1252'))
    refs=[]
    for a,b in welt.funcs:
        for ins in welt.cs.disasm(welt.image[a:b],welt.base+a):
            if any(o.type==X86_OP_MEM and o.mem.base!=X86_REG_RIP and o.mem.disp==0x134 for o in ins.operands):
                refs.append(dict(rva=hex(ins.address-welt.base),function=hex(a),instruction=ins.mnemonic+' '+ins.op_str))
    masks=[0x18000,0xf009,0xf949,0xf06b,0xf6b9,0xf04d]
    out=dict(scope=__doc__,fingerprints=expected,crop_names=names,
             native_baseline_mask=hex(0xf009),optional_harvest_mask=hex(0xff6),
             climate_masks=[hex(v) for v in masks],
             optional_crops_by_climate=[[names[i] for i in range(13) if m&(1<<i)&0xff6] for m in masks],
             island_mask_field_references=refs)
    (HERE/'native_crop_audit.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    functions={int(r['function'],16) for r in refs}
    (HERE/'native_crop_fields.asm').write_text('\n\n'.join(welt.dis(a) for a in sorted(functions))+'\n',encoding='utf-8')
    (HERE/'scene_crop_application.asm').write_text(scene.dis(0xc250)+'\n',encoding='utf-8')
    setter=struct.unpack_from('<Q',welt.image,0xf33e8+0x180)[0]-welt.base
    (HERE/'island_crop_property.asm').write_text(welt.dis(setter)+'\n\n'+welt.dis(0x49500)+'\n',encoding='utf-8')
    print('setter',hex(setter))
    print(json.dumps(dict(passed=True,names=names,field_references=refs),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
