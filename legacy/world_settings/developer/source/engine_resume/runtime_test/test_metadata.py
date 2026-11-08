"""Static metadata/relocation checks only. No DLL or game process is loaded."""
from pathlib import Path
import hashlib,json,re,runpy,struct,sys

HERE=Path(__file__).resolve().parent
WORK=HERE.parents[1]
sys.path.insert(0,str(WORK))
ns=runpy.run_path(str(WORK/'generate_runtime_test_blobs.py'))
header=(WORK/'runtime_test_blobs.h').read_text()
def array(name):
    value=re.search(r'static const unsigned char '+re.escape(name)+r'\[\] = \{([^}]*)\};',header)
    assert value,name
    return bytes(int(n,16) for n in re.findall(r'0x([0-9a-f]+)',value[1]))
def relocs(name):
    value=re.search(r'static const WSRelocation '+name+r'_relocs\[\] = \{(.*?)\};',header)
    assert value,name
    return [int(n) for n in re.findall(r'\{(\d+)\}',value[1])]

flag,names,hooks,functions=ns['build_bridge'](0)
factory,factory_names=ns['build_factory_code'](0)
scene,scene_names,scene_hooks=ns['build_code'](0)
specs=[('flag',flag,functions,lambda r:ns['build_bridge'](r)[0],hooks),
       ('factory',factory,[(0,factory_names['factory_bridge_end'],ns['COMMON_UNWIND'])],lambda r:ns['build_factory_code'](r)[0],[(ns['FACTORY_CALL_RVA'],ns['FACTORY_CALL_BYTES'],b'')]),
       ('scene',scene,[(0,scene_names['prepare_end'],b''),(scene_names['resource_guard'],scene_names['resource_guard_end'],b'')],lambda r:ns['build_code'](r)[0],scene_hooks)]
cases=0;sites=[]
for label,code,functions,build,hook_list in specs:
    assert array(label+'_code')==code
    module='AnnoScene.dll' if label=='scene' else 'AnnoFrame.dll'
    original=(WORK.parent/module).read_bytes()
    pe,opt,table,sections,off=ns['pe_info'](original)
    assert struct.unpack_from('<H',original,pe+4)[0]==0x8664
    assert struct.unpack_from('<H',original,opt)[0]==0x20b
    for rva,before,_ in hook_list:
        assert original[off(rva):off(rva)+len(before)]==before
        assert rva//4096==(rva+len(before)-1)//4096
        sites.append((module,rva//4096))
    for allocation_rva in [0x10000,0x123456,0x10000000,0x70000000-0x1000]:
        relocated=bytearray(code)
        for at in relocs(label):
            old=struct.unpack_from('<i',code,at)[0]
            expected=old-allocation_rva
            assert -(1<<31)<=expected<(1<<31)
            struct.pack_into('<i',relocated,at,expected)
        expected=build(allocation_rva)
        for begin,end,_ in functions:assert relocated[begin:end]==expected[begin:end],(label,allocation_rva,begin,end)
        cases+=1
    for index,(begin,end,unwind) in enumerate(functions):
        if label!='scene':assert array(f'{label}_unwind_{index}')==unwind
        else:
            raw=array(f'{label}_unwind_{index}');assert raw[:4]==bytes.fromhex('21000000')
            pdata,n=struct.unpack_from('<II',original,opt+112+3*8)
            native_entries=[original[off(pdata)+i:off(pdata)+i+12] for i in range(0,n,12)]
            assert raw[4:] in native_entries
assert len(sites)==4 and len(set(sites))==4
result=dict(scope=__doc__,blob_count=3,positive_allocation_relocation_cases=cases,exact_native_hook_preimages=4,separate_protection_pages=True,scene_chained_unwind_parents_verified=2,header_sha256=hashlib.sha256((WORK/'runtime_test_blobs.h').read_bytes()).hexdigest())
(HERE/'metadata_results.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
