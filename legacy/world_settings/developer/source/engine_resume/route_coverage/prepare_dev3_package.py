"""Create a new filtered dev3 scaffold; never change an existing package/copy."""
from pathlib import Path
import json
import shutil
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[1]
SOURCE=WORK/'anno1503_food_world_dev2';DEST=WORK/'anno1503_food_world_dev3'
SKIP_DIRS={'__pycache__','tmp','_build','.zig-cache','global-cache','local-cache','zig_global_cache','zig_local_cache'}
SKIP_FILES={'activation_session.json','SOURCE_BASELINES.json','PACKAGE_SHA256.json','world_patch.json',
            'installer_test_results.json','FOOD_PRESERVATION.json'}


def main():
    DEST.mkdir(exist_ok=False)
    count=0
    for path in sorted(SOURCE.rglob('*')):
        relative=path.relative_to(SOURCE)
        if (not path.is_file() or any(x in SKIP_DIRS for x in relative.parts)
                or path.name in SKIP_FILES or path.suffix.lower() in {'.pyc','.obj','.o','.a','.lib','.pdb'}
                or relative.parts[0]=='native'
                or relative.parts[:2] in [('developer','source'),('developer','world')]):
            continue
        target=DEST/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target);count+=1
    (DEST/'BUILD_PENDING.json').write_text(json.dumps(dict(status='UNFINISHED',version='0.6.0-dev.3',
        payload_ready=False,reason='Fresh runtime, native bridges and matching tests must be snapshotted before installation.'),indent=2)+'\n')
    print('Created',DEST,'with',count,'filtered scaffold files')


if __name__=='__main__':main()
