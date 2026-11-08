"""Pin one existing, unmodified activation invocation to the observed process."""
from pathlib import Path
import argparse
import hashlib
import json
import sys

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))


def require_observation(row,pid,creation,hwnd,frame):
    expected=dict(state='menu',menu_proof_verified=True,pid=pid,
                  process_creation_time=creation,hwnd=hwnd,frame_pointer=frame)
    if any(type(row.get(k)) is not type(v) or row.get(k)!=v for k,v in expected.items()):
        raise RuntimeError('The observed main menu changed. No activation was attempted.')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('pid','creation','hwnd','frame'):ap.add_argument('--'+name,type=int,required=True)
    args=ap.parse_args()
    config=json.loads((HERE/'launcher_config.json').read_bytes())
    package=(HERE/config['package_relative']).resolve(strict=True)
    if hashlib.sha256((package/'world_patch.json').read_bytes()).hexdigest()!=config['package_spec_sha256']:
        raise RuntimeError('The packaged World Settings specification changed.')
    from native_ready import _activation,NativeReadiness
    a=_activation(package)
    inputs=a.verify()
    probe=NativeReadiness(package,inputs)
    try:
        if probe.processes()!=[args.pid]:raise RuntimeError('The Anno process changed before activation.')
        require_observation(probe.inspect(args.pid),args.pid,args.creation,args.hwnd,args.frame)
    finally:probe.close()
    original_session=a.Session
    original_processes=a.all_processes
    class PinnedSession(original_session):
        def __init__(self,pid,mutate=False):
            if pid!=args.pid:raise RuntimeError('Unexpected Anno process; no changes made.')
            super().__init__(pid,mutate)
            if a.creation_time(self.handle)!=args.creation:
                a.close(self.handle)
                raise RuntimeError('Anno restarted; no changes made.')
    def pinned_processes():
        ids=original_processes()
        if ids!=[args.pid]:raise RuntimeError('The Anno process changed; no changes made.')
        return ids
    a.Session=PinnedSession
    a.all_processes=pinned_processes
    sys.argv=[str(package/'activation/activate_world_settings.py'),'--install','--game-dir',str(inputs['copy'])]
    a.main()


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('ERROR: '+str(exc),file=sys.stderr)
        raise SystemExit(1)
