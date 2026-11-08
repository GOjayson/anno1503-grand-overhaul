"""Bounded read-only debugger inspection of the exact active test's scene selection."""
from pathlib import Path
import json
import sys
HERE=Path(__file__).resolve().parent
PACKAGE=HERE.parent/'anno1503_food_world_dev3'
sys.path.insert(0,str(PACKAGE/'activation'))
import activate_world_settings as api
def main():
    inputs=api.verify()
    saved=json.loads(api.SESSION.read_bytes())
    ids=api.all_processes()
    assert ids==[saved['pid']]
    session=api.Session(ids[0])
    try:
        assert api.creation_time(session.handle)==saved['process_creation_time']
        mods=api.modules(ids[0]);api.verify_modules(mods,inputs,api.same,api.sha)
        frame=mods['annoframe.dll']['base']
        selection=session.read(frame+0xc7430,260).split(b'\0')[0]
        digest=session.read(frame+0xc7534,16)
        result=dict(scope=__doc__,pid=ids[0],selection_ansi=selection.decode('cp1252'),
                    selection_hex=selection.hex(),selected_digest_hex=digest.hex(),
                    bytes_read=276,process_memory_modified=False)
        (HERE/'live_selection.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2))
    finally:api.close(session.handle)
if __name__=='__main__':main()
