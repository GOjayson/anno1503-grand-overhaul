"""Check public repository boundaries without opening any game or credential."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess

ROOT=Path(__file__).resolve().parents[1]
BLOCKED={'.dll','.exe','.scp','.sze','.dat','.sav','.dmp','.zip','.7z','.lnk',
         '.obj','.o','.a','.lib','.pdb','.exp','.pyc','.pyo','.asm','.pem','.pfx','.key'}
SECRET=re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
USER_PATH=re.compile(r'(?i)[a-z]:[/\\]+users[/\\]+[^/\\\r\n"\']+')


def check(root=ROOT,private_identifiers=()):
    output=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=root)
    names=sorted(set(x.decode('utf-8')for x in output.split(b'\0')if x))
    problems=[]
    for name in names:
        p=root/name
        if (name.startswith(('.local/','.git/','profiles/')) or p.suffix.lower()in BLOCKED
                or p.name in ('activation_session.json','SHORTCUT_INSTALLATION.json')):
            problems.append('Forbidden public path: '+name);continue
        if p.is_symlink()or not p.resolve().is_relative_to(root.resolve()):
            problems.append('Public file leaves repository: '+name);continue
        if not p.is_file():
            problems.append('Tracked file is missing: '+name);continue
        data=p.read_bytes()
        if data[:2]==b'MZ':problems.append('Executable payload: '+name)
        if SECRET.search(data):problems.append('Possible credential material: '+name)
        if p.suffix.lower()=='.png':continue
        try:text=data.decode('utf-8-sig')
        except UnicodeDecodeError:
            problems.append('Unreviewed binary data: '+name);continue
        if USER_PATH.search(text):problems.append('Absolute personal directory: '+name)
        if any(item.lower()in text.lower()for item in private_identifiers if item):
            problems.append('Private identifier: '+name)
    specification=root/'legacy/world_settings/world_patch.json'
    if specification.exists():
        spec=json.loads(specification.read_bytes())
        if (spec.get('repository_source_snapshot',{}).get('source_only')is not True
                or spec.get('original_game_root')!='${ANNO1503_GAME_DIR}'
                or spec.get('game_evidence') or spec.get('game_evidence_sha256')
                or spec.get('actual_game_run')is not False):
            problems.append('Legacy source snapshot must remain uninstalled and sanitized.')
    manifest=root/'provenance/legacy_import.json'
    if manifest.exists():
        if not specification.is_file():
            problems.append('The imported World Settings source specification is missing.')
        imported=json.loads(manifest.read_bytes())
        for name,expected in imported['compiled_source_sha256'].items():
            if hashlib.sha256((root/name).read_bytes()).hexdigest()!=expected:
                problems.append('Imported compiled source changed: '+name)
    if problems:raise ValueError('\n'.join(problems))
    return dict(passed=True,public_files_checked=len(names),game_executed=False,
                original_game_files_uploaded=False)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--private-identifiers-file',type=Path)
    args=ap.parse_args();private=[]
    if args.private_identifiers_file:
        path=args.private_identifiers_file.resolve(strict=True)
        if not path.is_relative_to((ROOT/'.local').resolve()):raise ValueError('Private scan inputs must stay in ignored .local/.')
        private=json.loads(path.read_bytes())
    print(json.dumps(check(private_identifiers=private),indent=2))


if __name__=='__main__':main()
