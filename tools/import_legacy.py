"""Copy reviewed mod source into this repository without moving game files.

Original game modules, complete island files, saved worlds, caches, and machine
logs are never public import candidates. Optional private baselines retain the
current packages and archives byte for byte under the ignored .local folder.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import uuid

sys.dont_write_bytecode = True

CODE = {'.py', '.pyw', '.c', '.h', '.inc', '.s', '.cmd', '.ps1'}
GENERATED = {'.dll', '.exe', '.scp', '.sze', '.dat', '.obj', '.o', '.a', '.lib',
             '.pdb', '.exp', '.pyc', '.pyo', '.lnk', '.zip', '.dmp'}
CACHES = {'__pycache__', 'tmp', 'compiler_cache', '.zig-cache', 'global-cache',
          'local-cache', 'zig_global_cache', 'zig_local_cache'}
PUBLIC_EXCLUDED_DIRS = CACHES | {
    '_build', 'history', 'live', 'logs', 'copy_acceptance', 'review_evidence',
    'translated_evidence', 'alias_payload', 'native', 'worldsettingsislands',
}
DOCS = {'README.txt', 'VALIDATION.txt', 'FOOD_0_5_README.txt',
        'FOOD_0_5_VALIDATION.txt', 'ENGINE_NOTES.md', 'ARTWORK.txt', 'REBUILD.txt',
        'REVIEWED_HOOKS_SHA256.txt'}
JSON_DATA = {
    'food_patch.json', 'world_patch.json', 'launcher_config.json',
    'developer/compat-0.4.0.json', 'developer/compat-0.4.1.json',
    'developer/huge_world/runtime_engine_edits.json',
    'developer/huge_world/grid/grid_plan_source.json',
    'developer/huge_world/visibility/visibility_repair_plan.json',
    'developer/source/engine_resume/faction_options/pirate_transfer/FROZEN_ALIAS_MANIFEST.json',
    'developer/start_options/ai/candidate_manifest.json',
    'developer/start_options/ai/welt_policy_manifest.json',
}
SECRETS = re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
PINNED_RELEASES = {
    'anno1503_food_world_0_11_0_dev1.zip': 'a520aa612a1520c703af2e3265900a4df521da4593d4a048a1d405a5dfefe3b8',
    'anno1503_world_settings_launcher_1_0_0.zip': '0f8e20c542cdf793de5e0e56fc5b93380f0e85a900f44a8203211bd1756b9d5d',
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_stable(path: Path) -> bytes:
    before = path.stat()
    data = path.read_bytes()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Import input changed while being read: ' + path.name)
    return data


def regular_files(root: Path):
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('Source package contains a symlink: ' + str(path.relative_to(root)))
        if path.is_file():
            if not path.resolve(strict=True).is_relative_to(root):
                raise ValueError('Source file leaves its package.')
            yield path


def public_rule(relative: Path) -> tuple[bool, str]:
    parts = {part.lower() for part in relative.parts[:-1]}
    if parts & PUBLIC_EXCLUDED_DIRS:
        return False, 'private-history-cache-or-generated-directory'
    suffix = relative.suffix.lower()
    if suffix in GENERATED:
        return False, 'original-game-or-generated-artifact'
    name = relative.as_posix()
    if suffix in CODE:
        return True, 'authored-source'
    if name in JSON_DATA:
        return True, 'patch-or-build-description'
    if relative.parent.as_posix() == 'assets' and (
            suffix == '.png' or relative.name.endswith('_icon.json')):
        return True, 'authored-food-artwork'
    if relative.parent.as_posix() == 'assets/source' and suffix == '.png':
        return True, 'authored-food-artwork-source'
    if relative.name in DOCS:
        return True, 'baseline-documentation'
    return False, 'unreviewed-report-data-or-other-file'


def public_world_spec(data: bytes) -> bytes:
    spec = json.loads(data)
    original_hash = digest(data)
    historical_actual = bool(spec.get('actual_game_run'))
    spec['original_game_root'] = '${ANNO1503_GAME_DIR}'
    spec['game_evidence'] = {}
    spec['game_evidence_sha256'] = {}
    spec['runtime_gameplay_evidence'] = None
    spec['actual_game_run'] = False
    spec['packaged_runtime_gameplay_verified'] = False
    spec['complete_feature_verified'] = False
    spec['repository_source_snapshot'] = {
        'source_only': True,
        'original_world_spec_sha256': original_hash,
        'historical_baseline_actual_game_run': historical_actual,
        'historical_runtime_sha256': spec['payloads']['native/AnnoWorldSettings.dll'],
        'scope': 'Imported source and patch descriptions only. Original complete package and evidence are local, ignored baselines. No repository build or game run is certified by this snapshot.',
    }
    return (json.dumps(spec, indent=2) + '\n').encode('utf-8')


def guard_world_resolver(data: bytes) -> bytes:
    text = data.decode('utf-8')
    tree = ast.parse(text)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'resolve_copy')
    first = function.body[0]
    if not isinstance(first, ast.Expr) or not isinstance(first.value, ast.Constant) or not isinstance(first.value.value, str):
        raise ValueError('Expected documented legacy copy resolver.')
    lines = text.splitlines(keepends=True)
    newline = '\r\n' if b'\r\n' in data else '\n'
    addition = (
        '    if spec.get("repository_source_snapshot", {}).get("source_only") is True:' + newline
        + '        raise food.fm.ModError("Source-only repository snapshot cannot install or activate. Build a reviewed local package using the repository tools first.")' + newline
    )
    lines.insert(first.end_lineno, addition)
    result = ''.join(lines)
    compile(result, 'imported-world-mod.py', 'exec')
    return result.encode('utf-8')


def transform(family: str, relative: Path, data: bytes, game: Path) -> tuple[bytes, list[str]]:
    changes = []
    name = relative.as_posix()
    if family == 'world_settings' and name == 'world_patch.json':
        data = public_world_spec(data)
        changes.append('uncertified-source-specification-with-local-root-placeholder')
    elif family == 'world_settings' and name == 'world_mod.py':
        data = guard_world_resolver(data)
        changes.append('source-only-copy-resolution-guard')
    elif family == 'launcher' and name == 'launcher_config.json':
        config = json.loads(data)
        config['package_relative'] = '../world_settings'
        config['repository_source_snapshot'] = True
        data = (json.dumps(config, indent=2) + '\n').encode('utf-8')
        changes.append('repository-relative-source-package-location-still-fails-frozen-spec-pin')
    # Keep generic fixture/system path examples; remove only the exact installed
    # game path from documentation or noncompiled source if present.
    if relative.suffix.lower() in {'.txt', '.md', '.py', '.pyw', '.json', '.ps1', '.cmd'}:
        text = data.decode('utf-8-sig')
        for old in (str(game), str(game).replace('\\', '/'), str(game).replace('\\', '\\\\')):
            if old in text:
                text = text.replace(old, '${ANNO1503_GAME_DIR}')
                changes.append('exact-installed-game-path-redacted')
        data = text.encode('utf-8')
    return data, sorted(set(changes))


def private_baseline(source: Path, destination: Path) -> dict:
    destination.mkdir(parents=True, exist_ok=False)
    copied = {}
    omitted = Counter()
    for path in regular_files(source):
        relative = path.relative_to(source)
        if ({p.lower() for p in relative.parts} & CACHES or
                path.suffix.lower() in {'.obj', '.o', '.a', '.lib', '.pdb', '.exp', '.pyc', '.pyo'}):
            omitted['compiler-cache-or-intermediate'] += 1
            continue
        target = destination / relative
        if not target.resolve().is_relative_to(destination.resolve()):
            raise ValueError('Private baseline destination leaves its root.')
        target.parent.mkdir(parents=True, exist_ok=True)
        data = read_stable(path)
        with target.open('xb') as out:
            out.write(data)
        if digest(read_stable(target)) != digest(data) or digest(read_stable(path)) != digest(data):
            raise ValueError('Private baseline copy does not match: ' + relative.as_posix())
        copied[relative.as_posix()] = digest(data)
    return dict(source_path=str(source), files=copied, omitted=dict(omitted))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-dir', type=Path, required=True)
    parser.add_argument('--repo-dir', type=Path, required=True)
    parser.add_argument('--copy-baselines', action='store_true')
    parser.add_argument('--private-identifiers-file', type=Path,
                        help='Optional JSON list of private identifiers, stored only beneath ignored .local/')
    args = parser.parse_args(argv)
    game = args.game_dir.resolve(strict=True)
    repo = args.repo_dir.resolve(strict=True)
    if not (game/'Anno1503.exe').is_file() or not (repo/'AGENTS.md').is_file():
        raise ValueError('An explicit installed game and prepared repository are required.')
    if repo.is_relative_to(game) or game.is_relative_to(repo):
        raise ValueError('The repository and installed game must be independent directories.')
    local = repo/'.local'
    if local.exists() and (local.is_symlink() or local.resolve(strict=True) != local):
        raise ValueError('The local input directory must be a normal directory inside the repository.')
    if (repo/'legacy').exists() or (repo/'provenance/legacy_import.json').exists():
        raise ValueError('Preserving existing imported files; use a new repository or review the prior import.')
    personal = set()
    home_name = Path.home().name.casefold()
    if len(home_name) >= 3 and home_name not in {'root','user','administrator','runner'}:
        personal.add(home_name)
    if args.private_identifiers_file is not None:
        private_input = args.private_identifiers_file.resolve(strict=True)
        if not private_input.is_relative_to((repo/'.local').resolve()):
            raise ValueError('Private identifiers must stay beneath the ignored local input folder.')
        values = json.loads(private_input.read_bytes())
        if (not isinstance(values,list) or any(not isinstance(x,str) or len(x)<3 for x in values)):
            raise ValueError('Private identifiers must be a JSON list of strings with at least three characters.')
        personal.update(x.casefold() for x in values)
    work = game/'WorldSettings_Work'
    roots = {
        'food_overhaul': game/'anno1503_food_mod',
        'world_settings': work/'anno1503_food_world_dev8',
        'launcher': work/'world_settings_launcher',
    }
    for source in roots.values():
        source.resolve(strict=True)
    build = json.loads((roots['world_settings']/'developer/source/runtime_dev3/build_result.json').read_bytes())
    compiled = build['source_sha256']
    if len(compiled) != 43:
        raise ValueError('Expected the verified 43-input World Settings compiled closure.')
    local.mkdir(exist_ok=True)
    stage = local/('import-staging-'+uuid.uuid4().hex)
    stage.mkdir()
    provenance = []
    omitted = {family: Counter() for family in roots}
    for family, source in roots.items():
        for path in regular_files(source):
            relative = path.relative_to(source)
            include, reason = public_rule(relative)
            if not include:
                omitted[family][reason] += 1
                continue
            original = read_stable(path)
            if SECRETS.search(original):
                raise ValueError('Possible credential material in candidate source: '+family+'/'+relative.as_posix())
            data, changes = transform(family, relative, original, game)
            try:
                lower = data.decode('utf-8-sig').casefold() if path.suffix.lower() != '.png' else ''
            except UnicodeDecodeError:
                raise ValueError('Unexpected non-UTF8 source: '+family+'/'+relative.as_posix())
            if any(item in lower for item in personal):
                omitted[family]['personal-operator-source-or-document'] += 1
                continue
            destination = stage/family/relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open('xb') as out:
                out.write(data)
            provenance.append(dict(path='legacy/'+family+'/'+relative.as_posix(),
                source_family=family, source_relative=relative.as_posix(),
                original_sha256=digest(original), imported_sha256=digest(data),
                source_bytes=len(original), imported_bytes=len(data), changes=changes, category=reason))
    compiled_paths = {}
    for name, expected in compiled.items():
        source = roots['world_settings']/'developer/source'/name
        target = stage/'world_settings/developer/source'/name
        if not target.is_file() or digest(target.read_bytes()) != expected or digest(source.read_bytes()) != expected:
            raise ValueError('The complete compiled source must remain byte-exact: '+name)
        compiled_paths['legacy/world_settings/developer/source/'+name.replace('\\','/')] = expected
    private = None
    if args.copy_baselines:
        baselines = local/'baselines'
        if baselines.exists():
            raise ValueError('Preserving existing private baselines; no overwrite is allowed.')
        baselines.mkdir()
        private = {family: private_baseline(source, baselines/family) for family,source in roots.items()}
        release_dir = baselines/'releases'
        release_dir.mkdir()
        releases = {}
        for name, expected in PINNED_RELEASES.items():
            source = work/name
            data = read_stable(source)
            if digest(data) != expected:
                raise ValueError('The frozen release archive changed: '+name)
            target = release_dir/name
            with target.open('xb') as out:
                out.write(data)
            if digest(target.read_bytes()) != expected or digest(read_stable(source)) != expected:
                raise ValueError('Frozen archive preservation failed: '+name)
            releases[name] = dict(sha256=expected, bytes=len(data))
        private['releases'] = releases
        (baselines/'LOCAL_BASELINE_MANIFEST.json').write_text(json.dumps(private, indent=2)+'\n', encoding='utf-8')
    # Exclusive atomic publication: the destination must still be absent. No
    # installed package, release, backup, save, desktop shortcut or game is moved.
    if (repo/'legacy').exists():
        raise ValueError('Another import created legacy/; staged source was preserved locally.')
    source_endpoint = stage.resolve(strict=True)
    destination_endpoint = (repo/'legacy').resolve()
    if (not source_endpoint.is_relative_to((repo/'.local').resolve(strict=True))
            or destination_endpoint.parent != repo
            or destination_endpoint.exists()):
        raise ValueError('Import publication endpoints leave the intended repository or already exist.')
    source_endpoint.rename(destination_endpoint)
    report = dict(schema_version=1, imported_source_only=True,
        source_versions=dict(food_overhaul='0.5.0',world_settings='0.11.0-dev.1',launcher='1.0.0'),
        source_locations_are_relative_family_labels=True,
        source_files=provenance, excluded_counts={k:dict(v)for k,v in omitted.items()},
        compiled_input_count=43, compiled_source_sha256=compiled_paths,
        historical_runtime_sha256=build['sha256'],
        native_binaries_and_complete_islands_tracked=False,
        actual_repo_build_tested=False,actual_repo_game_run_tested=False,
        private_baselines_copied=private is not None,
        original_files_changed_or_removed=False)
    out = repo/'provenance/legacy_import.json'
    out.parent.mkdir(exist_ok=True)
    with out.open('x',encoding='utf-8') as stream:
        json.dump(report,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(passed=True,public_source_files=len(provenance),compiled_inputs_byte_exact=43,
        private_baselines_copied=private is not None,source_files_changed=False,
        excluded_counts=report['excluded_counts']),indent=2))


if __name__ == '__main__':
    main()
