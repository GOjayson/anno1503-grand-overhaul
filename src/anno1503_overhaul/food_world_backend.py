"""Independent Food06 + World host validator, packaged as world_mod.py.

The shared installer owns the transaction. This helper prepares the exact Food
edits and introduced World files together; it never installs legacy overlays.
"""
from pathlib import Path
import hashlib
import importlib
import json
import os
import struct
import sys

PACKAGE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(PACKAGE))
import food_mod as food
if Path(food.__file__).resolve() != PACKAGE / 'food_mod.py':
    raise RuntimeError('Unexpected combined Food preparation helper.')
sys.path.insert(0, str(PACKAGE / 'support'))
import world_transactions as tx
import stock_baseline as stock
import package_alias_assets as aliases
import package_world_assets as islands
import food_world_policy as policy

FINAL_STATE = policy.PROFILE
MARKER = '.anno1503-worldsettings-test-copy.json'
MANAGED = '.anno1503-grand-overhaul-copy.json'
INSTALL_RECORD = '.anno1503-grand-overhaul-install.json'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def _json(path):
    if path.stat().st_size > 5 * 1024 * 1024:
        raise ValueError('Combined metadata is too large.')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate combined metadata field.')
            result[key] = value
        return result
    value = json.loads(path.read_bytes(), object_pairs_hook=pairs)
    if not isinstance(value, dict):
        raise ValueError('Expected combined metadata.')
    return value


def resolve_copy(spec, root=None, package=None):
    if (spec.get('profile') != FINAL_STATE or spec.get('food_enabled') is not True
            or spec.get('food_files') != policy.food_files()
            or spec.get('new_world_required') is not True
            or spec.get('old_save_migration_supported') is not False):
        raise ValueError('This is not the exact Food06 + World profile.')
    bound = Path(spec['host_root']).resolve(strict=True)
    requested = bound if root is None else Path(root).resolve(strict=True)
    if bound != requested or str(bound) != spec['host_root']:
        raise ValueError('Combined World Settings belongs to another managed copy.')
    stock._root(bound)
    managed = _json(tx._path(bound, MANAGED, target=False))
    original = Path(managed.get('source_root', '')).resolve()
    if (type(managed.get('schema')) is not int or managed.get('schema') != 1
            or managed.get('managed_copy') is not True
            or Path(managed.get('copy_root', '')).resolve() != bound
            or original == bound or original in bound.parents or bound in original.parents
            or str(original) != spec['input_source_root']
            or managed.get('source_exe_sha256') != spec['exe_sha256']):
        raise ValueError('Combined World Settings requires its independent managed copy.')
    expected = dict(schema=1, development_copy=True, source_root=str(original),
                    copy_root=str(bound), source_exe_sha256=spec['exe_sha256'])
    if _json(tx._path(bound, MARKER, target=False)) != expected:
        raise ValueError('The combined World Settings marker differs.')
    return bound


def _amd64(data, name):
    try:
        pe, = struct.unpack_from('<I', data, 60)
        valid = (data[:2] == b'MZ' and data[pe:pe+4] == b'PE\0\0'
                 and struct.unpack_from('<H', data, pe+4)[0] == 0x8664
                 and struct.unpack_from('<H', data, pe+24)[0] == 0x20b)
    except (struct.error, IndexError):
        valid = False
    if not valid:
        raise ValueError('Expected the inspected AMD64 module: ' + name)


def _payloads(spec):
    data = {**aliases.data_payload_hashes(), **islands.data_payload_hashes()}
    expected = {'AnnoWorldSettings.dll': 'native/AnnoWorldSettings.dll',
                'WorldSettingsAI/CompLogic.dll': 'native/CompLogic.food06.dll',
                'WorldSettingsAI/CompLogicClassic.dll': 'native/CompLogicClassic.food06.dll',
                **aliases.introduced_files(), **islands.introduced_files()}
    if spec.get('introduced_files') != expected or set(spec['payloads']) != set(expected.values()):
        raise ValueError('The combined introduced-file policy differs.')
    outputs = {}
    for name, payload in expected.items():
        value = tx._path(PACKAGE, payload).read_bytes()
        if sha(value) != spec['payloads'][payload]:
            raise ValueError('A combined World payload changed: ' + name)
        if payload in data:
            if sha(value) != data[payload]:
                raise ValueError('A combined island payload differs.')
            (aliases if payload in aliases.data_payload_hashes() else islands).validate_data_payload(payload, value)
        else:
            _amd64(value, name)
        outputs[name] = value
    return outputs


def _file_state(root, name):
    path = tx._path(root, name)
    if not path.is_file():
        raise ValueError('A combined host file is missing: ' + name)
    return path.stat().st_size, tx.file_sha(path)


def _edited_state(root, edit):
    if edit.offset is None:
        return len(edit.after), sha(edit.after)
    path = tx._path(root, edit.name)
    if (type(edit.offset) is not int or edit.offset < 0
            or len(edit.before) != len(edit.after)
            or edit.offset + len(edit.before) > path.stat().st_size):
        raise ValueError('Invalid combined archive edit.')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        remaining = edit.offset
        while remaining:
            block = stream.read(min(1024 * 1024, remaining))
            if not block:
                raise ValueError('Incomplete combined archive.')
            digest.update(block)
            remaining -= len(block)
        if stream.read(len(edit.before)) != edit.before:
            raise ValueError('Combined archive region changed.')
        digest.update(edit.after)
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return path.stat().st_size, digest.hexdigest()


def _bug_fix_files(root, spec, *, installed):
    """Allow only the explicitly selected, freshly derived asset-only recipe."""
    expected = spec.get('bug_fixes')
    record_path = tx._path(root, INSTALL_RECORD, target=False)
    installation = _json(record_path) if installed and record_path.is_file() else None
    profile = installation.get('profile') if isinstance(installation, dict) else None
    features = profile.get('features', {}) if isinstance(profile, dict) else {}
    if expected is None:
        if isinstance(features, dict) and features.get('bug_fixes') is True:
            raise ValueError('This combined package has no selected Bug Fixes recipe.')
        return {}
    if not isinstance(expected, dict):
        raise ValueError('The combined Bug Fixes recipe differs.')
    support = (PACKAGE / 'support').resolve(strict=True)
    modules = ('_combined_filesystem', '_combined_ambient_sound_baselines', '_combined_bug_fixes',
               '_combined_ambient_sound', '_combined_bugfix_recipe')
    for name in modules:
        module = importlib.import_module(name)
        if Path(module.__file__).resolve(strict=True) != support / (name + '.py'):
            raise ValueError('Unexpected combined Bug Fixes helper: ' + name)
    actual = sys.modules[modules[-1]].recipe(Path(spec['input_source_root']))
    if expected != actual or actual.get('version') != '1.2':
        raise ValueError('The combined Bug Fixes recipe differs from the reviewed originals.')
    files = {entry['path']: {key: value for key, value in entry.items() if key != 'path'}
             for entry in actual['files']}
    if (len(files) != len(actual['files'])
            or len({name.casefold() for name in files}) != len(files)):
        raise ValueError('The combined Bug Fixes inventory contains duplicate paths.')
    for quest in actual['quests']:
        if _file_state(root, quest['scene_path'])[1] != quest['scene_sha256']:
            raise ValueError('The combined King of Ore scenario changed: ' + quest['locale'])
    if installed:
        if (not isinstance(installation, dict) or installation.get('schema') != 1
                or installation.get('status') != 'installed'
                or installation.get('copy_root') != str(root)
                or installation.get('source_root') != spec['input_source_root']
                or not isinstance(features, dict)
                or features.get('food_overhaul') is not True
                or features.get('world_settings') is not True
                or features.get('bug_fixes') is not True
                or installation.get('bug_fixes_version') != actual['version']
                or installation.get('bug_fix_quests') != actual['quests']
                or installation.get('bug_fix_sounds') != actual['sounds']):
            raise ValueError('The combined Bug Fixes installation binding differs.')
    return files


def build_edits(root, spec, progress=print):
    root = resolve_copy(spec, root)
    if _file_state(root, 'Anno1503.exe')[1] != spec['exe_sha256']:
        raise ValueError('The combined executable differs.')
    islands.validate_required_copy(root)
    outputs = _payloads(spec)
    food_policy = policy.food_files()
    record = tx.read_manifest(root)
    installed = record is not None and record['status'] == 'installed'
    bug_fixes = _bug_fix_files(root, spec, installed=installed)
    if ({name.casefold() for name in bug_fixes}
            & {name.casefold() for name in set(food_policy) | set(outputs)}):
        raise ValueError('Combined Bug Fixes overlaps another selected feature.')
    if installed:
        entries = {entry['name']: entry for entry in record['edits']}
        if (record['source_state'] != 'vanilla'
                or len(entries) != len(record['edits'])
                or set(entries) != set(food_policy) | set(outputs) | set(bug_fixes)):
            raise ValueError('The combined restoration journal differs.')
        backup = tx._path(root, tx.BACKUP, target=False)
        for name, expected in {**food_policy, **bug_fixes}.items():
            entry = entries[name]
            if (entry.get('existed') is not True
                    or any(entry.get(key) != value for key, value in expected.items())):
                raise ValueError('A combined selected-feature restoration record differs: ' + name)
            tx._require(root, entry, [tx._after(entry)])
            original = tx._path(backup, 'before/' + name, target=False)
            if tx._state(original) != tx._before(entry):
                raise ValueError('A combined restoration backup is missing or changed: ' + name)
        for name, value in outputs.items():
            entry = entries[name]
            if entry['existed'] or tx._after(entry) != (len(value), sha(value)):
                raise ValueError('A combined World restoration record differs: ' + name)
            tx._require(root, entry, [tx._after(entry)])
        for name, digest in spec['native_sha256'].items():
            value = tx._path(root, name).read_bytes()
            _amd64(value, name)
            if sha(value) != digest:
                raise ValueError('A combined native host module changed: ' + name)
        progress('Verified Food 0.6 with its separately pinned World Settings host.')
        return FINAL_STATE, []
    if record and record['status'] not in {'restored', 'rolled_back'}:
        raise ValueError('Restore the interrupted combined installation first.')
    for name, expected in bug_fixes.items():
        if _file_state(root, name) != (expected['before_size'], expected['before_sha256']):
            raise ValueError('The combined Bug Fixes requires its exact original file: ' + name)
    for name, expected in food_policy.items():
        if _file_state(root, name) != (expected['before_size'], expected['before_sha256']):
            raise ValueError('The combined profile requires its exact original file: ' + name)
    for name, digest in spec['native_sha256'].items():
        if name not in food_policy:
            value = tx._path(root, name).read_bytes()
            _amd64(value, name)
            if sha(value) != digest:
                raise ValueError('An unchanged combined native host module differs: ' + name)
    food_spec = _json(PACKAGE / 'food_patch.json')
    state, edits = food.build_edits(root, food_spec, progress)
    if state != 'vanilla' or len({edit.name for edit in edits}) != len(edits) or {edit.name for edit in edits} != set(food_policy):
        raise ValueError('The composed Food06 edit inventory differs.')
    for edit in edits:
        expected = food_policy[edit.name]
        if (edit.offset != expected['offset']
                or _edited_state(root, edit) != (expected['after_size'], expected['after_sha256'])):
            raise ValueError('A composed Food06 output differs: ' + edit.name)
    for name, value in outputs.items():
        if name in food_policy or os.path.lexists(tx._path(root, name)):
            raise ValueError('An introduced combined file already exists: ' + name)
        edits.append(tx.Edit(name, None, value))
    progress('Preparing Food 0.6 and World Settings together; start a NEW world.')
    return 'vanilla', edits


def verify_activation(copy_root=None):
    spec = _json(PACKAGE / 'world_patch.json')
    root = resolve_copy(spec, copy_root)
    state, edits = build_edits(root, spec, progress=lambda _: None)
    if state != FINAL_STATE or edits:
        raise ValueError('Install the exact combined Food06 package before activation.')
    for name in ['Anno1503.exe', *spec['native_sha256']]:
        if (root / name).stat().st_nlink != 1:
            raise ValueError('The combined host must not share writable native files.')
    return dict(source=root, copy=root, exe_sha256=spec['exe_sha256'],
                native_sha256=spec['native_sha256'],
                runtime_sha256=spec['payloads']['native/AnnoWorldSettings.dll'],
                private_native_sha256={name: spec['payloads'][payload]
                                      for name, payload in spec['introduced_files'].items()
                                      if name.startswith('WorldSettingsAI/')},
                spec_sha256=sha((PACKAGE / 'world_patch.json').read_bytes()))
