"""Reconstruct the reviewed Food/World AI precursor from owned stock bytes.

Only construction expressions from the immutable imported generators execute.
Their file, process and emulator drivers are excluded. Native exception tables
are read from the player's DLL and rebuilt locally, never shipped as payloads.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path
import struct
import textwrap
from types import SimpleNamespace

from . import packages as common
from .food06_package import _food05_native
from .world_native import _STOCK_AI_SHA256, _FROZEN_AI_SHA256, _policy_code, checksum


ROOT = Path(__file__).resolve().parents[2]
PREFIX = 'legacy/world_settings/developer/source/engine_resume/ai_food/'
SOURCES = {
    'code_support.py': '6fcf8321f45c26eb0ba434399fbc6f5a5b1881160085c6448db7ac58e49f05b9',
    'make_pending_candidate.py': '8e0de49ae5273e520270a204249ff15184f76d266da8849f8a30e57c45441aa9',
    'make_demand_candidate.py': '21e40e51475eb26d2e15170ee56322b1b2f3543df12b6cc655dc63266d151287',
    'make_market_candidate.py': 'ac82e86fc229eaa279780d447e40612775730834b63fd6c7e1b6459c0fb14a34',
    'make_state_candidate.py': 'a3b73ce81e082a8145bceceee786a55ccd1512728525ce2bf1f734e0aad29aad',
    'make_scoring_candidate.py': '8931291a81f589af84774f54ef262b45067c4f9e9970a0fb1b9de1081eda87e5',
}
_PENDING = {
    'CompLogic.dll': dict(allocation=0x363a8, deletes=(0x36932, 0x2a043, 0x86169), tail=0x84aef),
    'CompLogicClassic.dll': dict(allocation=0x34b28, deletes=(0x350b2, 0x289a3, 0x82c49), tail=0x8165f),
}


def _source(name):
    if name not in SOURCES:
        raise common.PackageError('Unknown public Food AI construction stage.')
    raw = common._read(ROOT, PREFIX + name)
    common._require_sha(raw, SOURCES[name], 'immutable public Food AI generator: ' + name)
    return raw.decode('utf-8')


def _definitions(source, names, scope, label):
    nodes = [node for node in ast.parse(source).body
             if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
    if {node.name for node in nodes} != set(names) or len(nodes) != len(names):
        raise common.PackageError('Public Food AI helper definitions differ: ' + label)
    # optimize=0 preserves the imported generators' preimage assertions even
    # inside the optimized frozen executable. No imported driver is executed.
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<public Food AI ' + label + '>',
                 'exec', optimize=0), scope)


def _segment(source, begin, end, scope, label):
    if source.count(begin) != 1 or source.count(end) != 1:
        raise common.PackageError('Public Food AI construction boundaries differ: ' + label)
    start, stop = source.index(begin), source.index(end)
    if stop <= start:
        raise common.PackageError('Public Food AI construction order differs: ' + label)
    code = textwrap.dedent(source[start:stop])
    # These immutable ranges contain only in-memory PE construction. Reject
    # newly introduced imports/driver expressions before compiling them.
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise common.PackageError('A public Food AI construction range imports driver code.')
        if isinstance(node, ast.Name) and node.id in {'HERE', 'ROOT', 'WORK', 'Module', 'Uc', 'sys', 'Path', 'open'}:
            raise common.PackageError('A public Food AI construction range accesses a driver.')
    exec(compile(tree, '<public Food AI ' + label + '>', 'exec', optimize=0), scope)


def _image(value):
    import pefile
    pe = pefile.PE(data=value)
    if pe.FILE_HEADER.Machine != 0x8664 or pe.OPTIONAL_HEADER.Magic != 0x20b:
        raise common.PackageError('Public Food AI requires the exact AMD64 History Edition image.')
    return SimpleNamespace(data=value, pe=pe, image=pe.get_memory_mapped_image())


def derive_food05_ai(name: str, stock: bytes) -> bytes:
    """Return the exact preserved private-AI precursor without private inputs."""
    if name not in _STOCK_AI_SHA256 or not isinstance(stock, bytes):
        raise common.PackageError('Choose a supported immutable stock AI image.')
    common._require_sha(stock, _STOCK_AI_SHA256[name], 'owned stock AI: ' + name)
    raw = common._require_sha(common._read(common.ROOT, 'legacy/food_overhaul/food_patch.json'),
                              common.FOOD_SPEC_SHA256, 'preserved Food construction specification')
    spec = common._json(raw, 'preserved Food construction specification')
    current = _food05_native(stock, spec, name)
    native_checksum = lambda value: checksum(bytes(value))
    scope = dict(struct=struct, checksum=native_checksum)
    _definitions(_source('code_support.py'), {'align', 'Code', 'parent_entry', 'Extension'}, scope, 'PE helpers')
    demand = _source('make_demand_candidate.py')
    _definitions(demand, {'demand_tail', 'primary_unwind_parent'}, scope, 'demand helpers')
    try:
        scope.update(m=_image(current), name=name, s=_PENDING[name])
        _segment(_source('make_pending_candidate.py'), ' data=bytearray(m.data);pe=',
                 ' output=out/', scope, 'pending node')
        current = bytes(scope['data'])
        scope.update(m=_image(current), name=name)
        _segment(demand, ' evaluator,loop,hook,exit=', ' path=HERE/', scope, 'demand loop')
        current = bytes(scope['data'])
        for stage in ('market', 'state', 'scoring'):
            image = _image(current)
            scope.update(m=image, name=name, e=scope['Extension'](image))
            _segment(_source('make_' + stage + '_candidate.py'), ' sd=0 if name==',
                     ' data=e.finish(checksum);output=HERE/', scope, stage)
            current = scope['e'].finish(native_checksum)
        image = _image(current)
        extension = scope['Extension'](image)
        setter = {'CompLogic.dll': 0x6542, 'CompLogicClassic.dll': 0x48c2}[name]
        if image.image[setter:setter + 6] != bytes.fromhex('8986b80a0000'):
            raise common.PackageError('Public Food AI policy setter preimage differs.')
        target = extension.function('preserve_policy_on_native_flag_updates', setter,
                                    lambda code: code.add(_policy_code(code.rva, setter)))
        extension.jump(setter, setter + 6, target)
        result = extension.finish(native_checksum)
        common._require_sha(result, _FROZEN_AI_SHA256[name], 'reconstructed Food/World AI: ' + name)
        common._amd64(result, 'reconstructed Food/World AI: ' + name)
        return result
    except (AssertionError, KeyError, ValueError, struct.error) as exc:
        if isinstance(exc, common.PackageError):
            raise
        raise common.PackageError('Public Food AI construction failed at a reviewed preimage: ' + name) from exc
