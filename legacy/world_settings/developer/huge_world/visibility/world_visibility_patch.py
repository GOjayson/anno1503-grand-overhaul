"""Pinned HE AMD64 visibility-layout repair; transforms bytes only.

This contains the visibility-mask helper, ca2f0 producer, expanded stack arrays,
matching epilogue/unwind metadata and C++ cleanup access. Never apply a subset.
No DLL or process is changed unless a caller explicitly writes returned bytes.
"""
from pathlib import Path
import hashlib,json,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
for parent in(HERE,*HERE.parents):
    candidate=parent/'WorldSettings_Work/_tools'
    if(candidate/'pefile.py').exists():sys.path.insert(0,str(candidate));break
import pefile

PLAN_SHA256='5e6e77be9d91e2aacf628d507aec059ee9b3170b0e319efe9b18f06ecad0835c'
SOURCE_HASHES=frozenset([
    'ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9',
    '059ecd1dcb2139b350f50a2805d811eff89e61cead2733ca9aedb6da83058319',
    '151fd9eab6e6d6c2733dac2678c57b8051720a1a4e7ea6c7436f5c6d991b75fd',
    'bc4de21e6c92ab5a94d9fc50d25f0609d9e1cdb2ff119c29238d3354f978fb29'])
PATCHED_HASHES={
    '6734eea9e5a93f6660d435033aad208094bd9db71a8f9699346c47e1e1d0cd99':'ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9',
    '505c4ae2e431dea52274f3c2b664407af547d8f8d6b6eecfbfd1c6a9145e50ee':'059ecd1dcb2139b350f50a2805d811eff89e61cead2733ca9aedb6da83058319',
    '70ac4f4a583b8353692c47d3315f1332b4ebefeca6dc5f54c13aa4c9d97bba42':'151fd9eab6e6d6c2733dac2678c57b8051720a1a4e7ea6c7436f5c6d991b75fd',
    '8a6f73e1f015e30685063dc3418305e6b3a0bf51f9fe49d6074c296fc1e33aa8':'bc4de21e6c92ab5a94d9fc50d25f0609d9e1cdb2ff119c29238d3354f978fb29'}


def sha(data):return hashlib.sha256(data).hexdigest()


def plan():
    data=(HERE/'visibility_repair_plan.json').read_bytes()
    if sha(data)!=PLAN_SHA256:raise ValueError('Visibility repair plan fingerprint differs')
    result=json.loads(data)
    if result['instruction_or_metadata_region_count']!=len(result['edits'])or len(result['edits'])!=47:
        raise ValueError('Visibility repair is incomplete')
    return result


def runtime_visibility_edits():
    return[dict(rva=row['rva'],before=row['before'],after=row['after'],category='visibility_layout')for row in plan()['edits']]


def transform_welt_visibility(blob):
    if not isinstance(blob,bytes):raise TypeError('Expected immutable DLL bytes')
    digest=sha(blob);known_patched=digest in PATCHED_HASHES
    if digest not in SOURCE_HASHES and not known_patched:raise ValueError('Unknown complete HE World fingerprint: '+digest)
    p=pefile.PE(data=blob,fast_load=True)
    if p.FILE_HEADER.Machine!=0x8664 or p.OPTIONAL_HEADER.Magic!=0x20b:raise ValueError('Only exact AMD64 PE32+ is supported')
    metadata=plan();edits=metadata['edits'];result=bytearray(blob);covered=set()
    for row in edits:
        before,after=bytes.fromhex(row['before']),bytes.fromhex(row['after']);offset=p.get_offset_from_rva(row['rva'])
        expected=after if known_patched else before
        if blob[offset:offset+len(expected)]!=expected:raise ValueError('Visibility repair preimage differs at '+hex(row['rva']))
        if covered.intersection(range(offset,offset+len(before))):raise ValueError('Overlapping visibility edits')
        covered.update(range(offset,offset+len(before)));result[offset:offset+len(after)]=after
    output=bytes(result)
    if len(output)!=len(blob)or any(a!=b and at not in covered for at,(a,b)in enumerate(zip(blob,output))):raise ValueError('Visibility repair changed undeclared bytes')
    return output,dict(component=metadata['component'],source_sha256=digest,output_sha256=sha(output),
        idempotent=known_patched,architecture='AMD64 PE32+',repair_plan_sha256=PLAN_SHA256,
        region_count=len(edits),new_stack_frame_bytes=metadata['new_stack_frame'],stack_growth_bytes=metadata['stack_growth_bytes'],
        new_visibility_mask_bytes=2048,new_matrix_columns=128,visible_record_capacity=8192,
        matrix_zero_is_unassigned=True,matching_cpp_cleanup_and_native_unwind=True,game_executed=False,
        activation_requirement=metadata['activation_requirement'])


if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('source',type=Path);ap.add_argument('output',type=Path)
    a=ap.parse_args();output=a.output.resolve()
    if not output.is_relative_to(HERE)or output.exists():raise ValueError('CLI output must be a new file under this experimental border folder')
    result,manifest=transform_welt_visibility(a.source.read_bytes());output.write_bytes(result)
    output.with_suffix(output.suffix+'.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,indent=2))
