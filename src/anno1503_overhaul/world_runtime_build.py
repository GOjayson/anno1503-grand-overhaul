"""Build a reviewed World-only runtime derivative in ignored local staging.

The imported compiled-source closure and known Food runtime are never changed.
This builder proves stock instruction and unwind preimages before compiling;
neither compilation nor those checks constitute a running-game observation.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import uuid

from .filesystem import checked_path


ROOT = Path(__file__).resolve().parents[2]
SOURCE_PREFIX = 'legacy/world_settings/'
BLOBS = 'developer/source/runtime_dev3/runtime_test_blobs.h'
AI_LOADER = 'developer/source/engine_resume/ai_loader/ai_loader.c'
WORLD_SETTINGS = 'developer/source/engine_resume/ai_food/experiment_runtime/WorldSettings.c'
ENGINE_PLAN = 'developer/huge_world/runtime_engine_edits.json'
ENGINE_HEADER = 'developer/source/engine_resume/ai_loader/engine_patch_plan.h'
ENGINE_PLAN_SHA256 = 'c17f70c5f8d2cd9326e3cdf7bdbb5c8ecf27964441257814de742bd4fc1c94cf'
WORLD_ONLY_RUNTIME_SHA256 = '4ede7aefddeb78319328f9de7e4597e49d6d1652739539c29afe5439024a86e9'
WORLD_ONLY_ENGINE_PLAN_SHA256 = '71940166c7131f78d1b5efd68c1e6dff0299ea8d3334ed811420da4a53fa1f4e'
KNOWN_FOOD_RUNTIME = '2f9d1156f3ac53d92a900e41c38a169138c2b4ac7145f2dc92b93c48736cf089'
STOCK_SHA256 = {
    'Anno1503.exe': '1a4bebe7c676a5904834b9e67e936187729dc67c013a4fb4fd64986a3cb8e95a',
    'AnnoFrame.dll': 'dfd7c76dfc0b017fa5142c46a2bb084c01fc750a049d85ca70b56dca2f555ccd',
    'AnnoWelt.dll': '95951b5712848cd005f009115fafddb10e2c79ae5cf79501753a9938503ae4dc',
    'AnnoScene.dll': 'f7d0685cf6156ff25c518f2f558863b351d7738280467e48dd585a1fefa9537a',
    'AnnoGame.dll': '06af5111316276c73efe9dde355b06c479fa36d617478722a9700c36225b15bf',
    'View.dll': 'ed1c13167d6fc9fd220f074da52bb63d396b6a11b722c48a44a2babd8c6f4aef',
    'CompLogic.dll': 'a8218ef1a1ba9cbe929f2c32430ebd5647e750e2df2af6733808d7314a80c483',
    'CompLogicClassic.dll': 'd005f6505b41a4648d9cc75573cdebf74174f89c2091fcf32a8e019c20246b2e',
}
FOOD_SHA256 = {
    'AnnoFrame.dll': '046b5ad6f351dfe867ed38ce29fb50a594485b43a32ee90adadc48e850466baf',
    'AnnoWelt.dll': 'ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9',
    'CompLogic.dll': '7f2c7e818d8c25a0b6c48cda2d21bfa0c4096c5dcd8be91c2ab93d877c22afee',
    'CompLogicClassic.dll': '0a7692879e15e8cbaed73ec3b59eaa6419165faaea6d8696cddfd68c92000f22',
}
FOOD_AI_CANDIDATES = {
    'CompLogic.dll': '0612873c32c95252144f4b4fd2bed45dddddc177303981833b673ddc4ed51453',
    'CompLogicClassic.dll': '29d1759bd3beb39f9a5a3364946a24b36f8bb4fa546c6a999b6ca994aeeaab34',
}
REQUIRED_EXPORTS = {
    'WorldSettingsEnginePatchStatus', 'WorldSettingsConfigureDevelopmentRoot',
    'WorldSettingsCopyConfigurationError', 'WorldSettingsInstallTestHooks',
    'WorldSettingsCopyTestHooksError', 'WorldSettingsCopyFactoryError',
    'WorldSettingsCopyAILoaderError', 'WorldSettingsCopyAIProfileError',
    'WorldSettingsAIProfileStatus', 'WorldSettingsBeginNativeWorldStart',
    'WorldSettingsEndNativeWorldStart', 'WorldSettingsBindAIProfileWorld',
    'WorldSettingsBindAIDiplomacy', 'WorldSettingsStagePreviewScene',
    'WorldSettingsPreviewSnapshotSize', 'WorldSettingsCopyPreviewSnapshot',
}


class RuntimeBuildError(RuntimeError):
    pass


def _sha(data):
    return hashlib.sha256(data).hexdigest()


class PE:
    """Bounded raw-file RVA reads, exception-table membership and architecture."""
    def __init__(self, data):
        self.data = data
        if data[:2] != b'MZ':
            raise RuntimeBuildError('Missing native DOS signature.')
        self.pe, = self.unpack('<I', 60)
        if data[self.pe:self.pe + 4] != b'PE\0\0':
            raise RuntimeBuildError('Missing native PE signature.')
        machine, count = self.unpack('<HH', self.pe + 4)
        optional_size, = self.unpack('<H', self.pe + 20)
        self.optional = self.pe + 24
        magic, = self.unpack('<H', self.optional)
        if machine != 0x8664 or magic != 0x20b or not 1 <= count <= 96 or optional_size < 240:
            raise RuntimeBuildError('Expected the inspected AMD64 PE32+ architecture.')
        self.image_size, self.header_size = self.unpack('<II', self.optional + 56)
        directories, = self.unpack('<I', self.optional + 108)
        if not 7 <= directories <= 16 or not self.image_size or self.header_size > len(data):
            raise RuntimeBuildError('Invalid bounded native header.')
        self.sections = []
        for index in range(count):
            at = self.optional + optional_size + index * 40
            name = self.bytes(at, 8).split(b'\0')[0].decode('ascii')
            virtual_size, rva, raw_size, raw = self.unpack('<IIII', at + 8)
            flags, = self.unpack('<I', at + 36)
            extent = max(virtual_size, raw_size)
            if raw + raw_size > len(data) or rva + extent > self.image_size:
                raise RuntimeBuildError('Native section leaves its file or mapped image.')
            self.sections.append(dict(name=name, rva=rva, virtual=virtual_size,
                                      raw_size=raw_size, raw=raw, flags=flags))
        for index, first in enumerate(self.sections):
            for second in self.sections[index + 1:]:
                for start, size in (('rva', 'virtual'), ('raw', 'raw_size')):
                    if first[size] and second[size] and max(first[start], second[start]) < min(
                            first[start] + first[size], second[start] + second[size]):
                        raise RuntimeBuildError('Native sections overlap.')

    def bytes(self, at, size):
        if type(at) is not int or type(size) is not int or at < 0 or size < 0 or at + size > len(self.data):
            raise RuntimeBuildError('Native structure leaves its file.')
        return self.data[at:at + size]

    def unpack(self, fmt, at):
        return struct.unpack(fmt, self.bytes(at, struct.calcsize(fmt)))

    def offset(self, rva, size):
        if type(rva) is not int or type(size) is not int or rva < 0 or size < 0 or rva + size > self.image_size:
            raise RuntimeBuildError('Native mapped span leaves its image.')
        if rva + size <= self.header_size:
            return rva
        matches = [section['raw'] + rva - section['rva'] for section in self.sections
                   if 0 <= rva - section['rva'] and rva - section['rva'] + size <= section['raw_size']]
        if len(matches) != 1:
            raise RuntimeBuildError('Native mapped span is absent or ambiguous.')
        return matches[0]

    def read(self, rva, size):
        return self.bytes(self.offset(rva, size), size)

    def executable(self, rva, size):
        return any(section['flags'] & 0x20000000 and section['rva'] <= rva
                   and rva + size <= section['rva'] + min(section['virtual'], section['raw_size'])
                   for section in self.sections)

    def directory(self, index):
        return self.unpack('<II', self.optional + 112 + index * 8)

    def function_table(self):
        rva, size = self.directory(3)
        if not rva or not size or size % 12 or size // 12 > 131072:
            raise RuntimeBuildError('Missing or unbounded native exception-function table.')
        data = self.read(rva, size)
        return set(struct.iter_unpack('<III', data))


def _hex_bytes(value):
    tokens = [token.strip() for token in value.split(',') if token.strip()]
    if not tokens or any(not re.fullmatch(r'0x[0-9a-fA-F]{2}', token) for token in tokens):
        raise RuntimeBuildError('Generated native metadata has invalid byte literals.')
    return bytes(int(token, 16) for token in tokens)


def blob_metadata(header):
    text = header.decode('ascii')
    arrays = {name: _hex_bytes(value) for name, value in re.findall(
        r'static const unsigned char (\w+)\[\] = \{([^}]*)\};', text)}
    blobs = []
    declaration = text.split('static const WSBlob wsBlobs[] = ', 1)
    if len(declaration) != 2:
        raise RuntimeBuildError('The reviewed native blob table is missing.')
    for module, digest, fields in re.findall(r'\{L"([^"]+)",\{([^}]*)\},([^{}]+)\}', declaration[1]):
        fields = fields.split(',')
        if len(fields) != 10 or not fields[0].endswith('_code'):
            raise RuntimeBuildError('The reviewed native blob table changed shape.')
        prefix = fields[0][:-5]
        if fields[8] != prefix + '_hooks' or int(fields[1]) != len(arrays[prefix + '_code']):
            raise RuntimeBuildError('Generated native blob sizes or hook names differ.')
        hooks_match = re.search(r'static const WSHook ' + prefix + r'_hooks\[\] = \{(.*?)\};', text)
        functions_match = re.search(r'static const WSFunctionMeta ' + prefix + r'_functions\[\] = \{(.*?)\};', text)
        if not hooks_match or not functions_match:
            raise RuntimeBuildError('Generated native hook/function metadata is missing.')
        hooks = []
        for rva, size, before, target, call in re.findall(r'\{(\d+),(\d+),(\w+),(\d+),([01])\}', hooks_match[1]):
            value = arrays[before]
            if len(value) != int(size) or not 5 <= len(value) <= 32 or int(target) >= int(fields[1]):
                raise RuntimeBuildError('Generated native hook metadata is invalid.')
            hooks.append(dict(rva=int(rva), before=value, target=int(target), call=int(call)))
        if len(hooks) != int(fields[9]):
            raise RuntimeBuildError('Generated native hook count differs.')
        functions = []
        for begin, end, unwind, size in re.findall(r'\{(\d+),(\d+),(\w+),(\d+)\}', functions_match[1]):
            value = arrays[unwind]
            if not 0 <= int(begin) < int(end) <= int(fields[1]) or len(value) != int(size):
                raise RuntimeBuildError('Generated native unwind metadata is invalid.')
            functions.append(dict(begin=int(begin), end=int(end), unwind=value))
        if len(functions) != int(fields[7]):
            raise RuntimeBuildError('Generated native function count differs.')
        blobs.append(dict(module=module, sha256=_hex_bytes(digest).hex(), prefix=prefix,
                          hooks=hooks, functions=functions))
    if len(blobs) != 8 or sum(len(blob['hooks']) for blob in blobs) != 9:
        raise RuntimeBuildError('Expected exactly eight native blobs and nine hook sites.')
    return blobs


def verify_native_preimages(game, header, plan_raw, *, expected_hashes=None):
    """Prove exact stock native hashes, all 182 sites and chained unwind parents."""
    game = checked_path(game)
    hashes = STOCK_SHA256 if expected_hashes is None else expected_hashes
    modules = {}
    for name, expected in hashes.items():
        path = checked_path(game / name)
        data = path.read_bytes()
        if _sha(data) != expected:
            raise RuntimeBuildError('World-only input is not the inspected stock module: ' + name)
        modules[name] = PE(data)
    plan = json.loads(plan_raw)
    if (plan.get('engine_instruction_count') != 173 or len(plan.get('edits', [])) != 173):
        raise RuntimeBuildError('Expected the complete 173-edit engine plan.')
    spans = []
    for edit in plan['edits']:
        name = edit.get('module', plan.get('module'))
        rva = edit.get('rva')
        before, after = bytes.fromhex(edit['before']), bytes.fromhex(edit['after'])
        if name not in {'AnnoFrame.dll', 'AnnoWelt.dll'} or type(rva) is not int or not 1 <= len(before) <= 32 or len(before) != len(after):
            raise RuntimeBuildError('Invalid bounded native engine edit.')
        if modules[name].read(rva, len(before)) != before:
            raise RuntimeBuildError(f'Stock engine preimage differs: {name}+0x{rva:x}')
        spans.append((name, rva, rva + len(before)))
    unwind_parents = []
    for blob in blob_metadata(header):
        name = blob['module']
        if name not in modules or blob['sha256'] != hashes[name]:
            raise RuntimeBuildError('Derived native blob is not bound to the inspected stock input.')
        pe = modules[name]
        for hook in blob['hooks']:
            rva, before = hook['rva'], hook['before']
            if not pe.executable(rva, len(before)) or pe.read(rva, len(before)) != before:
                raise RuntimeBuildError(f'Stock hook preimage differs: {name}+0x{rva:x}')
            spans.append((name, rva, rva + len(before)))
        for function in blob['functions']:
            unwind = function['unwind']
            if len(unwind) < 4 or unwind[0] & 7 != 1:
                raise RuntimeBuildError('Generated unwind version is unsupported.')
            flags = unwind[0] >> 3
            ordinary = (4 + 2 * unwind[2] + 3) & ~3
            if flags not in (0, 4) or len(unwind) != ordinary + (12 if flags == 4 else 0):
                raise RuntimeBuildError('Generated unwind layout is unsupported.')
            if flags == 4:
                parent = struct.unpack_from('<III', unwind, ordinary)
                if (parent not in pe.function_table() or not pe.executable(parent[0], parent[1] - parent[0])
                        or pe.read(parent[2], 4)[0] & 7 != 1):
                    raise RuntimeBuildError('A chained unwind parent is absent from the exact stock native table.')
                unwind_parents.append(dict(module=name, begin=parent[0], end=parent[1], unwind=parent[2]))
    for index, first in enumerate(spans):
        for second in spans[index + 1:]:
            if first[0] == second[0] and max(first[1], second[1]) < min(first[2], second[2]):
                raise RuntimeBuildError('Native hook and engine edit spans overlap.')
    return dict(stock_module_sha256=dict(hashes), hook_sites_verified=9, engine_sites_verified=173,
                unwind_parents_verified=unwind_parents, game_executed=False)


def _replace(data, before, after, count, label):
    if data.count(before) != count:
        raise RuntimeBuildError('Reviewed source transformation does not match: ' + label)
    return data.replace(before, after)


def _c_digest(digest):
    return ','.join('0x' + digest[index:index + 2] for index in range(0, 64, 2)).encode()


def derive_engine_plan(stock_welt_bytes, frozen_plan_raw):
    """Rebind the two Food-relocated .pdata edits to unique stock function tuples."""
    if _sha(stock_welt_bytes) != STOCK_SHA256['AnnoWelt.dll'] or _sha(frozen_plan_raw) != ENGINE_PLAN_SHA256:
        raise RuntimeBuildError('The stock Welt or frozen engine plan differs from the reviewed build.')
    pe = PE(stock_welt_bytes)
    table_rva, table_size = pe.directory(3)
    table = pe.read(table_rva, table_size)
    plan = json.loads(frozen_plan_raw)
    relocations = []
    for old_rva, triplet, field, before, after, expected_rva in (
        (0x14be8c, (0x68024, 0x6804d, 0x115800), 4, '4d800600', '59800600', 0x1389d8),
        (0x14be94, (0x6804d, 0x68053, 0x115814), 0, '4d80060053800600', '598006005f800600', 0x1389e0),
    ):
        needle = struct.pack('<III', *triplet)
        matches = [index for index in range(0, len(table), 12) if table[index:index + 12] == needle]
        if len(matches) != 1:
            raise RuntimeBuildError('The stock exception-function parent tuple is absent or ambiguous.')
        new_rva = table_rva + matches[0] + field
        if new_rva != expected_rva or pe.read(new_rva, len(bytes.fromhex(before))).hex() != before:
            raise RuntimeBuildError('The stock exception-function edit preimage differs.')
        edits = [edit for edit in plan['edits'] if edit.get('module', plan.get('module')) == 'AnnoWelt.dll'
                 and edit.get('rva') == old_rva]
        if len(edits) != 1 or edits[0].get('category') != 'unwind' or edits[0]['before'] != before or edits[0]['after'] != after:
            raise RuntimeBuildError('The frozen exception-function edit differs.')
        edits[0]['rva'] = new_rva
        relocations.append(dict(module='AnnoWelt.dll', frozen_rva=old_rva, stock_rva=new_rva,
                                parent_triplet=list(triplet), before=before, after=after))
    plan['profile'] += '-world-only-v1'
    plan['world_only_derivative'] = dict(
        frozen_engine_plan_sha256=ENGINE_PLAN_SHA256, stock_welt_sha256=STOCK_SHA256['AnnoWelt.dll'],
        native_disk_hash_metadata='Inherited source/output artifact hashes describe the frozen combined disk payload, not a World-only disk module.',
        unwind_table_relocations=relocations,
    )
    return (json.dumps(plan, indent=2) + '\n').encode('utf-8')


def derive_engine_header(header):
    for before, after in ((b'0x14be8cu', b'0x1389d8u'), (b'0x14be94u', b'0x1389e0u')):
        header = _replace(header, before, after, 1, 'stock exception-function table RVA')
    return header


def transform_sources(header, ai_loader, world_settings, candidate_hashes):
    """Only reviewed metadata pins and managed same-root guards are changed."""
    if set(candidate_hashes) != set(FOOD_AI_CANDIDATES) or any(not re.fullmatch(r'[0-9a-f]{64}', value) for value in candidate_hashes.values()):
        raise RuntimeBuildError('World-only AI fingerprints are missing or invalid.')
    for name, count in (('AnnoFrame.dll', 5), ('AnnoWelt.dll', 2)):
        header = _replace(header, _c_digest(FOOD_SHA256[name]), _c_digest(STOCK_SHA256[name]), count, name + ' blob source')
    for name in FOOD_AI_CANDIDATES:
        ai_loader = _replace(ai_loader, FOOD_SHA256[name].encode(), STOCK_SHA256[name].encode(), 1, name + ' AI source')
        ai_loader = _replace(ai_loader, FOOD_AI_CANDIDATES[name].encode(), candidate_hashes[name].encode(), 1, name + ' AI candidate')
    ai_loader = _replace(ai_loader, b'!absolute(copyRoot)||!absolute(sourceRoot)||!_stricmp(copyRoot,sourceRoot)',
                         b'!absolute(copyRoot)||!absolute(sourceRoot)', 1, 'managed same-root AI configuration')
    ai_loader = _replace(ai_loader, b'AI modules require distinct absolute source and copy folders.',
                         b'AI modules require verified absolute source and copy folders.', 1, 'AI diagnostic')
    world_settings = _replace(world_settings, b'.anno1503-worldsettings-test-copy.json',
                              b'.anno1503-grand-overhaul-copy.json', 2, 'managed-copy marker')
    world_settings = _replace(world_settings, b'attributes==INVALID_FILE_ATTRIBUTES||(attributes&FILE_ATTRIBUTE_DIRECTORY)',
                              b'attributes==INVALID_FILE_ATTRIBUTES||(attributes&(FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT))',
                              1, 'regular managed-copy marker')
    newline = b'\r\n' if b'\r\n' in world_settings else b'\n'
    old = b'        configurationFailure("Development-copy root must differ from the actual game executable folder, including directory aliases.");goto done;'
    new = (b'        /* This derivative permits only its Python-verified managed host as the data root. */' + newline
           + b'        if(_wcsicmp(full,exe)){configurationFailure("Managed host root must match the actual executable folder without aliases.");goto done;}' + newline
           + b'        attributes=GetFileAttributesW(marker);' + newline
           + b'        if(attributes==INVALID_FILE_ATTRIBUTES||(attributes&(FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT))){configurationFailure("A regular Grand Overhaul managed-copy marker is required for the host root.");goto done;}')
    world_settings = _replace(world_settings, old, new, 1, 'managed same-root native host')
    world_settings = _replace(world_settings, b'The copied Food AI support has not completed activation.',
                              b'The copied World Settings AI support has not completed activation.', 1, 'World-only AI diagnostic')
    return {BLOBS: header, AI_LOADER: ai_loader, WORLD_SETTINGS: world_settings}


def _verified_sources(repo):
    provenance = json.loads((repo / 'provenance/legacy_import.json').read_bytes())
    compiled = provenance['compiled_source_sha256']
    if len(compiled) != 43 or any(not name.startswith(SOURCE_PREFIX) for name in compiled):
        raise RuntimeBuildError('The reviewed 43-source native closure is missing.')
    for name, expected in compiled.items():
        if _sha(checked_path(repo / name).read_bytes()) != expected:
            raise RuntimeBuildError('Imported native source changed: ' + name)
    records = {entry['path']: entry['imported_sha256'] for entry in provenance['source_files']}
    for name in (SOURCE_PREFIX + ENGINE_PLAN, SOURCE_PREFIX + 'developer/source/runtime_dev3/build_runtime.py',
                 SOURCE_PREFIX + 'developer/source/runtime_dev3/REVIEWED_HOOKS_SHA256.txt'):
        if name not in records or _sha(checked_path(repo / name).read_bytes()) != records[name]:
            raise RuntimeBuildError('Reviewed build metadata changed: ' + name)
    return compiled


def normalize_pe_metadata(data):
    """Canonicalize compiler timestamp/CodeView IDs; leave executable sections exact."""
    pe = PE(data)
    if pe.directory(4) != (0, 0):
        raise RuntimeBuildError('A signed native image cannot be normalized.')
    output = bytearray(data)
    edits = []
    def zero(at, size, label):
        before = bytes(output[at:at + size])
        output[at:at + size] = bytes(size)
        edits.append(dict(offset=at, before=before.hex(), after=bytes(size).hex(), field=label))
    zero(pe.pe + 8, 4, 'COFF timestamp')
    rva, size = pe.directory(6)
    if not rva or size != 56:
        raise RuntimeBuildError('Unexpected runtime build-identification directory.')
    directory = pe.offset(rva, size)
    sections = [section for section in pe.sections if section['name'] == '.buildid']
    if len(sections) != 1 or not sections[0]['rva'] <= rva < sections[0]['rva'] + sections[0]['virtual']:
        raise RuntimeBuildError('Runtime build metadata is outside the expected section.')
    codeview = 0
    for index in range(size // 28):
        at = directory + index * 28
        fields = pe.unpack('<IIHHIIII', at)
        kind, length, address, pointer = fields[4:]
        if kind not in (2, 16):
            raise RuntimeBuildError('Unexpected runtime debug metadata type.')
        zero(at + 4, 4, 'debug timestamp')
        if kind == 2:
            if length < 25 or pe.offset(address, length) != pointer or pe.bytes(pointer, 4) != b'RSDS':
                raise RuntimeBuildError('Invalid runtime CodeView metadata.')
            zero(pointer + 4, 16, 'CodeView build ID')
            codeview += 1
        elif length or address or pointer:
            raise RuntimeBuildError('Unexpected reproducible-build debug payload.')
    if codeview != 1:
        raise RuntimeBuildError('Expected exactly one runtime CodeView build ID.')
    return bytes(output), edits


def build_world_only_runtime(vanilla_game, tools=None, output=None, *, frozen_world_package=None,
                             profile_output=None, progress=lambda _: None):
    """Stage, prove and compile a World-only candidate; never install or launch."""
    if os.name != 'nt':
        raise RuntimeBuildError('Native World-only compilation currently requires Windows.')
    repo = checked_path(ROOT)
    vanilla_game = checked_path(vanilla_game)
    compiled = _verified_sources(repo)
    source = repo / SOURCE_PREFIX
    tools = checked_path(tools if tools is not None else repo / '.local/toolchain')
    zig = checked_path(tools / 'ziglang/zig.exe')
    version = subprocess.check_output([str(zig), 'version'], text=True).strip()
    if version != '0.16.0':
        raise RuntimeBuildError('World-only compilation requires the reviewed Zig 0.16.0 toolchain.')
    builds = checked_path(repo / '.local/builds', exists=False)
    builds.mkdir(parents=True, exist_ok=True)
    output = checked_path(output if output is not None else builds / ('world-only-' + uuid.uuid4().hex), exists=False)
    if not output.is_relative_to(builds) or output == builds or output.exists() or output.is_relative_to(vanilla_game):
        raise RuntimeBuildError('Choose a new native build folder beneath ignored .local/builds.')
    # These candidate bytes are derived and checked by the World-only native recipe.
    from .world_native import derive_ai_candidate, WORLD_ONLY_AI_SHA256
    frozen = checked_path(frozen_world_package if frozen_world_package is not None
                          else repo / '.local/baselines/world_settings')
    candidates = {name: derive_ai_candidate(name, checked_path(vanilla_game / name).read_bytes(),
                                           checked_path(frozen / 'native' / payload).read_bytes())
                  for name, payload in (('CompLogic.dll', 'CompLogic.food-ai.dll'),
                                        ('CompLogicClassic.dll', 'CompLogicClassic.food-ai.dll'))}
    candidate_hashes = {name: _sha(data) for name, data in candidates.items()}
    if candidate_hashes != WORLD_ONLY_AI_SHA256:
        raise RuntimeBuildError('World-only AI recipe does not match its reviewed output fingerprints.')
    derivatives = transform_sources((source / BLOBS).read_bytes(), (source / AI_LOADER).read_bytes(),
                                    (source / WORLD_SETTINGS).read_bytes(), candidate_hashes)
    frozen_plan = (source / ENGINE_PLAN).read_bytes()
    if _sha(frozen_plan) != ENGINE_PLAN_SHA256:
        raise RuntimeBuildError('The exact reviewed engine plan changed.')
    plan_raw = derive_engine_plan(checked_path(vanilla_game / 'AnnoWelt.dll').read_bytes(), frozen_plan)
    if _sha(plan_raw) != WORLD_ONLY_ENGINE_PLAN_SHA256:
        raise RuntimeBuildError('The derived engine plan differs from the reviewed World-only profile.')
    derivatives[ENGINE_HEADER] = derive_engine_header((source / ENGINE_HEADER).read_bytes())
    proof = verify_native_preimages(vanilla_game, derivatives[BLOBS], plan_raw)
    progress('All stock hook, engine and unwind preimages passed. Preparing native build…')
    stage = output / 'package'
    shutil.copytree(source, stage, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '_build', '*.dll', '*.exe'))
    for name, expected in compiled.items():
        if _sha((stage / name.removeprefix(SOURCE_PREFIX)).read_bytes()) != expected:
            raise RuntimeBuildError('Staged imported native input differs: ' + name)
    transformations = []
    for name, data in derivatives.items():
        before = (stage / name).read_bytes()
        (stage / name).write_bytes(data)
        transformations.append(dict(path=name, before_sha256=_sha(before), after_sha256=_sha(data)))
    (stage / ENGINE_PLAN).write_bytes(plan_raw)
    reviewed = stage / 'developer/source/runtime_dev3/REVIEWED_HOOKS_SHA256.txt'
    reviewed.write_text(_sha(derivatives[BLOBS]) + '\n', encoding='ascii')
    report = dict(schema_version=1, profile='world-settings-without-food-v1', created_at=datetime.now(timezone.utc).isoformat(),
                  known_food_runtime_sha256=KNOWN_FOOD_RUNTIME, imported_compiled_source_sha256=compiled,
                  transformations=transformations, engine_plan_sha256=_sha(plan_raw),
                  ai_candidate_sha256=candidate_hashes, native_preimage_proof=proof,
                  toolchain_version=version, game_executed=False, installed=False, game_files_modified=False)
    (output / 'SOURCE_PROOF.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    command = [sys.executable, '-B', str(stage / 'developer/source/runtime_dev3/build_runtime.py'), '--tools', str(tools)]
    progress('Compiling the separate World Settings runtime…')
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf-8', errors='replace')
    (output / 'build.log').write_text(result.stdout, encoding='utf-8')
    if result.returncode:
        raise RuntimeBuildError('World-only native compilation failed. The staged build and log were preserved.')
    candidate = stage / 'developer/source/runtime_dev3/AnnoWorldSettings.dll'
    raw = candidate.read_bytes()
    normalized, metadata = normalize_pe_metadata(raw)
    candidate.write_bytes(normalized)
    if _sha(normalized) != WORLD_ONLY_RUNTIME_SHA256:
        raise RuntimeBuildError('The compiled candidate differs from the reviewed World-only runtime. Build output was preserved and no runtime profile was published.')
    spec = importlib.util.spec_from_file_location('_anno_world_only_exports', repo / 'legacy/world_settings/activation/pe_exports.py')
    parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser)
    exports = parser.exports(normalized, REQUIRED_EXPORTS)
    derived_hashes = {name: _sha((stage / name.removeprefix(SOURCE_PREFIX)).read_bytes()) for name in compiled}
    allowed = {SOURCE_PREFIX + name for name in derivatives}
    if {name for name in compiled if derived_hashes[name] != compiled[name]} != allowed:
        raise RuntimeBuildError('An unreviewed compiled source changed during the derivative build.')
    if _verified_sources(repo) != compiled:
        raise RuntimeBuildError('Imported source closure changed during native compilation.')
    report.update(built=True, runtime_path=str(candidate), runtime_sha256=_sha(normalized),
                  compiler_output_sha256=_sha(raw), normalized_metadata=metadata,
                  derivative_compiled_source_sha256=derived_hashes, export_rvas=exports, output_root=str(output))
    (output / 'BUILD_RESULT.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    profiles = checked_path(repo / '.local/runtime-profiles', exists=False)
    profiles.mkdir(parents=True, exist_ok=True)
    profile = checked_path(profile_output if profile_output is not None else profiles / 'world-only-v1', exists=False)
    if profile == profiles or not profile.is_relative_to(profiles) or profile.exists():
        raise RuntimeBuildError('Runtime profile output already exists or leaves ignored .local/runtime-profiles. Build output was preserved.')
    profile.mkdir(parents=True)
    with (profile / 'AnnoWorldSettings.dll').open('xb') as stream:
        stream.write(normalized)
    with (profile / 'runtime_engine_edits.json').open('xb') as stream:
        stream.write(plan_raw)
    for name, data in candidates.items():
        target = profile / 'WorldSettingsAI' / name
        target.parent.mkdir(exist_ok=True)
        with target.open('xb') as stream:
            stream.write(data)
    report['profile_root'] = str(profile)
    (profile / 'runtime-profile.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report
