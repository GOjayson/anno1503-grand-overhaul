"""Pinned combined Food/world engine extension; no installation side effects."""
from pathlib import Path
import hashlib,importlib.util,json
HERE=Path(__file__).resolve().parent
def _load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def transform_huge_welt(blob):
    plan=json.loads((HERE/'runtime_engine_edits.json').read_bytes())
    digest=hashlib.sha256(blob).hexdigest()
    if digest==plan['patched_welt_sha256']:return blob,dict(plan,idempotent=True)
    if digest!=plan['dev7_welt_sha256']:raise ValueError('Unsupported complete Food/world engine fingerprint')
    grid=_load('combined_huge_grid',HERE/'grid/world_grid_patch.py')
    navigation=_load('combined_huge_navigation',HERE/'navigation/navigation_patch.py')
    partial,_=grid.transform_welt_grid(blob)
    result=navigation.transform_welt_navigation(partial)
    visibility=_load('combined_huge_visibility',HERE/'visibility/world_visibility_patch.py')
    result,_=visibility.transform_welt_visibility(result)
    if hashlib.sha256(result).hexdigest()!=plan['patched_welt_sha256']:raise ValueError('Combined engine output differs from reviewed profile')
    return result,dict(plan,idempotent=False)

def transform_huge_frame(blob):
    plan=json.loads((HERE/'runtime_engine_edits.json').read_bytes())
    module=plan['modules']['AnnoFrame.dll'];digest=hashlib.sha256(blob).hexdigest()
    if digest==module['patched_sha256']:return blob,dict(plan['depth_layout'],idempotent=True)
    if digest!=module['copied_input_sha256']:raise ValueError('Unsupported complete Food/world Frame fingerprint')
    depth=_load('combined_huge_bias',HERE/'bias/frame_bias_patch.py')
    result,manifest=depth.transform_frame_bias(blob)
    if hashlib.sha256(result).hexdigest()!=module['patched_sha256']:raise ValueError('Combined depth output differs from reviewed profile')
    return result,dict(manifest,idempotent=False)
