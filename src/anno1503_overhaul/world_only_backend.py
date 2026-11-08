"""Packaged World-only validator. Game definitions and native host stay stock.

This file is copied as world_mod.py into a pinned local World-only package.
It prepares introduced World files only; the shared installer owns publication.
"""
from pathlib import Path
import hashlib
import json
import os
import struct
import sys

PACKAGE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(PACKAGE / 'support'))
import world_transactions as tx
import stock_baseline as stock
import package_alias_assets as aliases
import package_world_assets as islands

FINAL_STATE = 'world-only-0.3.0'
MARKER = '.anno1503-worldsettings-test-copy.json'
MANAGED = '.anno1503-grand-overhaul-copy.json'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def _json(path):
    if path.stat().st_size > 5 * 1024 * 1024:
        raise ValueError('World-only metadata is too large.')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate World-only metadata field.')
            result[key] = value
        return result
    value = json.loads(path.read_bytes(), object_pairs_hook=pairs)
    if not isinstance(value, dict):
        raise ValueError('Expected World-only metadata.')
    return value


def resolve_copy(spec, root=None, package=None):
    if spec.get('profile') != 'world-only-0.3.0' or spec.get('food_enabled') is not False:
        raise ValueError('This package is not the independent World Settings profile.')
    bound = Path(spec['host_root']).resolve(strict=True)
    requested = bound if root is None else Path(root).resolve(strict=True)
    if bound != requested or str(bound) != spec['host_root']:
        raise ValueError('World Settings belongs to another managed game copy.')
    stock._root(bound)  # Inspect requested ancestors for reparse points.
    managed = _json(tx._path(bound, MANAGED, target=False))
    original = Path(managed.get('source_root', '')).resolve()
    if (type(managed.get('schema')) is not int or managed.get('schema') != 1
            or managed.get('managed_copy') is not True
            or Path(managed.get('copy_root', '')).resolve() != bound
            or original == bound or original in bound.parents or bound in original.parents
            or str(original) != spec['input_source_root']
            or managed.get('source_exe_sha256') != spec['exe_sha256']):
        raise ValueError('World Settings requires its independently marked game copy.')
    expected = dict(schema=1, development_copy=True, source_root=str(original),
                    copy_root=str(bound), source_exe_sha256=spec['exe_sha256'])
    if _json(tx._path(bound, MARKER, target=False)) != expected:
        raise ValueError('The World Settings marker differs from this managed copy.')
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
        raise ValueError('Expected the inspected AMD64 World module: ' + name)


def _payloads(spec):
    data = {**aliases.data_payload_hashes(), **islands.data_payload_hashes()}
    expected = {'AnnoWorldSettings.dll': 'native/AnnoWorldSettings.dll',
                'WorldSettingsAI/CompLogic.dll': 'native/CompLogic.world-only.dll',
                'WorldSettingsAI/CompLogicClassic.dll': 'native/CompLogicClassic.world-only.dll',
                **aliases.introduced_files(), **islands.introduced_files()}
    if spec.get('introduced_files') != expected or set(spec['payloads']) != set(expected.values()):
        raise ValueError('The World-only file policy differs from the reviewed package.')
    outputs = {}
    for name, payload in expected.items():
        value = tx._path(PACKAGE, payload).read_bytes()
        if sha(value) != spec['payloads'][payload]:
            raise ValueError('A World-only payload fingerprint changed: ' + name)
        if payload in data:
            if sha(value) != data[payload]:
                raise ValueError('A World island payload differs.')
            (aliases if payload in aliases.data_payload_hashes() else islands).validate_data_payload(payload, value)
        else:
            _amd64(value, name)
        outputs[name] = value
    return outputs


def build_edits(root, spec, progress=print):
    root = resolve_copy(spec, root)
    baseline = stock.verify_vanilla(root, PACKAGE)
    for name, digest in spec['native_sha256'].items():
        path = tx._path(root, name)
        value = path.read_bytes()
        _amd64(value, name)
        if sha(value) != digest:
            raise ValueError('A stock host module changed: ' + name)
    islands.validate_required_copy(root)
    outputs = _payloads(spec)
    record = tx.read_manifest(root)
    if record and record['status'] == 'installed':
        entries = {entry['name']: entry for entry in record['edits']}
        if record['source_state'] != 'vanilla' or set(entries) != set(outputs):
            raise ValueError('World-only installation has an unexpected restoration journal.')
        backup = tx._path(root, tx.BACKUP, target=False)
        for name, value in outputs.items():
            entry = entries[name]
            if entry['existed'] or tx._after(entry) != (len(value), sha(value)):
                raise ValueError('A World-only restoration record differs: ' + name)
            tx._require(root, entry, [tx._after(entry)])
        progress('Verified World Settings with stock food, market, residents and native host modules.')
        return FINAL_STATE, []
    if record and record['status'] not in {'restored', 'rolled_back'}:
        raise ValueError('Restore the interrupted installation before installing World Settings.')
    edits = []
    for name, value in outputs.items():
        if os.path.lexists(tx._path(root, name)):
            raise ValueError('An introduced World Settings file already exists: ' + name)
        edits.append(tx.Edit(name, None, value))
    progress('Stock Food definitions and native modules are unchanged; preparing World Settings only.')
    return 'vanilla', edits


def verify_activation(copy_root=None):
    spec = _json(PACKAGE / 'world_patch.json')
    root = resolve_copy(spec, copy_root)
    state, edits = build_edits(root, spec, progress=lambda _: None)
    if state != FINAL_STATE or edits:
        raise ValueError('Install the exact World-only package before activation.')
    for name in ['Anno1503.exe', *spec['native_sha256']]:
        if (root / name).stat().st_nlink != 1:
            raise ValueError('The World-only host must not share writable native files.')
    return dict(source=root, copy=root, exe_sha256=spec['exe_sha256'],
                native_sha256=spec['native_sha256'],
                runtime_sha256=spec['payloads']['native/AnnoWorldSettings.dll'],
                private_native_sha256={name: spec['payloads'][payload]
                                      for name, payload in spec['introduced_files'].items()
                                      if name.startswith('WorldSettingsAI/')},
                spec_sha256=sha((PACKAGE / 'world_patch.json').read_bytes()))
