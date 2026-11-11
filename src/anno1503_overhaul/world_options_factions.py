"""Exact private-AI derivatives for persisted, independent faction activity.

Only newly packaged AI copies change. Normal and untagged native controllers
retain their original behavior; no installed module or legacy input is edited.
"""
from __future__ import annotations

import hashlib
import re
import struct

from .world_options import PRIVATE, authored, replace
from .world_runtime_build import RuntimeBuildError
from .world_native import _pe, _offset, _align, checksum, _policy_code


PROFILE_INPUT_SHA256 = {
    'world-only': {
        'CompLogic.dll': 'bbf15a8aa0a06f2fb484cb38df741ff8f8d63f479de9d05afbf0c453b2c96fd9',
        'CompLogicClassic.dll': '7592ca081ac7fe8d3011b64c5ea868b125a8b5e358c0c4a9e365b1329d0a1dcd',
    },
    'food-world': {
        'CompLogic.dll': '0612873c32c95252144f4b4fd2bed45dddddc177303981833b673ddc4ed51453',
        'CompLogicClassic.dll': '29d1759bd3beb39f9a5a3364946a24b36f8bb4fa546c6a999b6ca994aeeaab34',
    },
}
PIRATE_TAG = 0x57540000
MERCHANT_TAG = 0x57550000
SPEC = {
    'CompLogic.dll': dict(pirate_vtable=0x88ba8, merchant_vtable=0x883c0,
        threshold=0x7f61f, spawn=0x7f69b, create=0x53e90,
        merchant=0x72cd0, setter=0x6542),
    'CompLogicClassic.dll': dict(pirate_vtable=0x85aa0, merchant_vtable=0x85258,
        threshold=0x7cadf, spawn=0x7cb5b, create=0x513f0,
        merchant=0x6fc60, setter=0x48c2),
}
for _pins in PROFILE_INPUT_SHA256.values():
    for _digest in _pins.values():
        if re.fullmatch(r'[0-9a-f]{64}', _digest) is None:
            raise RuntimeBuildError('Faction activity input pin is not a complete SHA256.')


class _Code:
    def __init__(self, rva):
        self.rva, self.data, self.labels, self.fixups = rva, bytearray(), {}, []

    def add(self, raw):
        self.data.extend(bytes.fromhex(raw) if isinstance(raw, str) else raw)

    def label(self, name):
        self.labels[name] = self.rva + len(self.data)

    def jump(self, opcode, target):
        self.add(opcode)
        self.fixups.append((len(self.data), target))
        self.add(bytes(4))

    def lea(self, opcode, target):
        self.jump(opcode, target)  # RIP-relative disp32 has the same fixup.

    def continuation(self, target):
        # Register-indirect ModRM11 is deliberately not a Win64 tail epilogue.
        # An E9 out of a chained continuation is interpreted as an epilogue
        # and would skip its native parent's active stack frame on unwind.
        self.lea('4c8d1d', target)
        self.add('41ffe3')

    def finish(self):
        for at, target in self.fixups:
            dest = self.labels[target] if isinstance(target, str) else target
            struct.pack_into('<i', self.data, at, dest-self.rva-at-4)
        return bytes(self.data)


def _threshold_code(rva, family):
    """R10/R11 are dead native volatile values; EAX is original output."""
    c = _Code(rva)
    c.lea('4c8d15', family['pirate_vtable'])
    c.add('4c3917');c.jump('0f85', 'normal')
    c.add('83bf4c0a00000f');c.jump('0f85', 'normal')
    c.add('8b87b80a00004189c24181e20000ffff4181fa00005457');c.jump('0f85', 'normal')
    c.add('a900f00000');c.jump('0f85', 'deny')
    c.add('4189c241c1ea0a4183e2034183fa03');c.jump('0f84', 'deny')
    c.add('c1e80883e00383f803');c.jump('0f84', 'deny')
    c.add('83f801');c.jump('0f84', 'normal')
    c.add('85c0');c.jump('0f84', 'rare')
    c.add('4169c0983a0000');c.jump('e9', 'done')  # 15000
    c.label('rare');c.add('4169c060ea0000');c.jump('e9', 'done')  # 60000
    c.label('normal');c.add('4169c030750000');c.jump('e9', 'done')
    c.label('deny');c.add('b8ffffffff')  # unsigned elapsed cannot exceed this
    c.label('done');c.continuation(family['threshold']+7)
    return c.finish()


def _spawn_code(rva, family):
    """Six-argument leaf tail adapter; only new pirate armament can change."""
    c = _Code(rva)
    c.add('4c8d51f8');c.lea('4c8d1d', family['pirate_vtable'])
    c.add('4d391a');c.jump('0f85', 'native')
    c.add('4183ba4c0a00000f');c.jump('0f85', 'native')
    c.add('6645398a640a0000');c.jump('0f85', 'native')
    c.add('817c2428e4050000');c.jump('0f85', 'native')
    c.add('4183f920');c.jump('0f83', 'native')
    c.add('4d8b5a084d85db');c.jump('0f84', 'native')
    c.add('4d8b9b100200004d85db');c.jump('0f84', 'native')
    c.add('4f8b5ccb084d85db');c.jump('0f84', 'native')
    c.add('4d395318');c.jump('0f85', 'native')
    c.add('45394b08');c.jump('0f85', 'native')
    c.add('664181bb9c0000000f00');c.jump('0f85', 'native')
    c.add('664181bb9e0000000b00');c.jump('0f85', 'native')
    c.add('48b8504952415430310049394368');c.jump('0f85', 'native')
    c.add('418b82b80a00004189c34181e30000ffff4181fb00005457');c.jump('0f85', 'native')
    c.add('a900f00000');c.jump('0f85', 'deny')
    c.add('4189c341c1eb084183e3034183fb03');c.jump('0f84', 'deny')
    c.add('c1e80a83e00383f803');c.jump('0f84', 'deny')
    c.add('83f801');c.jump('0f84', 'native')
    c.add('4189c38b44243083f804');c.jump('0f82', 'deny')
    c.add('83f812');c.jump('0f87', 'deny')
    c.add('4585db');c.jump('0f84', 'weak')
    c.add('4189c383c001d1e84401d883f812');c.jump('0f86', 'store')
    c.add('b812000000');c.jump('e9', 'store')
    c.label('weak');c.add('d1e883f804');c.jump('0f83', 'store')
    c.add('b804000000')
    c.label('store');c.add('89442430')
    c.label('native');c.jump('e9', family['create'])
    c.label('deny');c.add('b8ffffffffc3')
    return c.finish()


def _merchant_code(rva, family):
    """Preserve native R14 target; R10/R11 are dead on both successors."""
    c = _Code(rva)
    c.lea('4c8d15', family['merchant_vtable'])
    c.add('4c3916');c.jump('0f85', 'normal')
    c.add('83be4c0a000010');c.jump('0f85', 'normal')
    c.add('448b96b80a00004589d34181e30000ffff4181fb00005557');c.jump('0f85', 'normal')
    c.add('41f7c200fc0000');c.jump('0f85', 'deny')
    c.add('41c1ea084183e2034183fa03');c.jump('0f84', 'deny')
    c.add('4183fa01');c.jump('0f84', 'normal')
    c.add('4183fe01');c.jump('0f8c', 'normal')
    c.add('4183fe05');c.jump('0f8f', 'normal')
    c.add('4585d2');c.jump('0f84', 'rare')
    c.add('478d1436');c.jump('e9', 'scaled')  # R10d=R14d*2
    c.label('rare');c.add('458d560141d1ea')  # ceil(original/2)
    c.label('scaled');c.add('443996880c0000');c.continuation(family['merchant']+7)
    c.label('deny');c.add('4539f6');c.continuation(family['merchant']+7)  # force JGE
    c.label('normal');c.add('4439b6880c0000');c.continuation(family['merchant']+7)
    return c.finish()


def _setter_code(rva, family, original_target):
    """Keep old CPU12 preserver exact; special low-flag updates retain tags.

    Full incoming saved words, including malformed words, are transported
    unchanged so the load validator can reject them instead of silently
    converting a corrupt policy into an untagged Normal world.
    """
    c = _Code(rva)
    c.add('83be4c0a00000f');c.jump('0f84', 'pirate')
    c.add('83be4c0a000010');c.jump('0f85', 'original')
    c.lea('4c8d15', family['merchant_vtable'])
    c.add('41bb00005557');c.jump('e9', 'identity')
    c.label('pirate');c.lea('4c8d15', family['pirate_vtable']);c.add('41bb00005457')
    c.label('identity');c.add('4c3916');c.jump('0f85', 'original')
    c.add('a900ffffff');c.jump('0f85', 'store')
    c.add('448b96b80a00004181e20000ffff4539da');c.jump('0f85', 'store')
    c.add('448b96b80a00004181e200ffffff4409d0')
    c.label('store');c.add('8986b80a0000');c.continuation(family['setter']+6)
    c.label('original');c.continuation(original_target)
    return c.finish()


def apply_factions(files: dict[str, bytes]) -> None:
    """Stage fresh-only policy binding; checkpoints restore their own tags."""
    declarations = (b'void WorldSettingsExpectFactionActivity(uint32_t,int32_t,int32_t,int32_t);\n'
                    b'void WorldSettingsResetFactionActivity(void);\n'
                    b'int WorldSettingsBindFactionActivity(void*,void*,char*,uint32_t);\n'
                    b'int WorldSettingsValidateFactionActivityWorld(void*,char*,uint32_t);\n')
    header = PRIVATE + 'world_ai.h'
    files[header] = replace(files[header],
        b'__declspec(dllexport) int WorldSettingsBindAIProfileWorld(void*,char*,uint32_t);\n#endif',
        b'__declspec(dllexport) int WorldSettingsBindAIProfileWorld(void*,char*,uint32_t);\n'+declarations+b'#endif',
        'fresh faction policy declarations')
    ai = PRIVATE + 'world_ai.c'
    files[ai] = replace(files[ai], b'#include "special_activity.inc"',
        b'#include "special_activity.inc"\n#include "faction_activity.inc"', 'faction policy binder')
    files[ai] = replace(files[ai],
        b' if(valid==1)valid=WorldSettingsValidateChosenDisasters(world,wsProfileError,sizeof wsProfileError);',
        b' if(valid==1)valid=WorldSettingsValidateChosenDisasters(world,wsProfileError,sizeof wsProfileError);\n'
        b' if(valid==1)valid=WorldSettingsBindFactionActivity(world,approved,wsProfileError,sizeof wsProfileError);',
        'bind fresh faction policy after original opponent and special certificates')
    files[ai] = replace(files[ai],
        b'void WorldSettingsAIProfileAttemptFinished(int success){if(!success){',
        b'void WorldSettingsAIProfileAttemptFinished(int success){if(!success){WorldSettingsResetFactionActivity();',
        'cancel pending faction policy without modifying a loaded controller')
    files[ai] = replace(files[ai],
        b' wsProfilesExpected=-1;wsFactionsExpected=0;wsNativeFactions=0;wsNativeActive=0;',
        b' WorldSettingsResetFactionActivity();\n wsProfilesExpected=-1;wsFactionsExpected=0;wsNativeFactions=0;wsNativeActive=0;',
        'end unique native start faction scope')
    menu = PRIVATE + 'WorldSettings.c'
    files[menu] = replace(files[menu],
        b' WorldSettingsExpectAIProfiles(d->settings.aiCount,d->settings.factions,d->settings.aiDifficulty);',
        b' WorldSettingsExpectFactionActivity(d->settings.factions,d->settings.pirateFrequency,d->settings.pirateStrength,d->settings.merchantFrequency);\n'
        b' WorldSettingsExpectAIProfiles(d->settings.aiCount,d->settings.factions,d->settings.aiDifficulty);',
        'fresh menu faction options')
    for name in ('faction_activity.inc', 'merchant_activity.inc'):
        files[PRIVATE + name] = authored(name)


def apply_faction_load_validation(files: dict[str, bytes]) -> None:
    """Certify only this mod's authenticated checkpoint before publication.

    Original scenes and unmarked saves deliberately stage no exploration
    checkpoint. Their native faction identities need not satisfy a generated
    custom world's Pirate/Venetian certificate.
    """
    name = PRIVATE + 'start_visibility_memory_io.inc'
    files[name] = replace(files[name],
        b'__declspec(dllexport) int WorldSettingsVisibilityAfterLoad(void*scene,char*error,uint32_t cap){\n',
        b'extern int WorldSettingsValidateFactionActivityWorld(void*,char*,uint32_t);\n'
        b'__declspec(dllexport) int WorldSettingsVisibilityAfterLoad(void*scene,char*error,uint32_t cap){\n',
        'declare saved faction validation at the native Scene load boundary')
    files[name] = replace(files[name],
        b' else if(!v.marked)ok=1;',
        b' else if(v.marked&&!WorldSettingsValidateFactionActivityWorld(v.world,error,cap))ok=0;\n'
        b' else if(!v.marked)ok=1;',
        'validate saved faction tags only after the owned marked checkpoint identity')


def _parent(raw, info, entries, hook):
    parent = next((e for e in entries if e[0] <= hook < e[1]), None)
    if parent is None:
        raise RuntimeBuildError('Faction native hook has no exception function.')
    immediate = parent
    seen = set()
    while True:
        if parent in seen:
            raise RuntimeBuildError('Faction native unwind chain is cyclic.')
        seen.add(parent)
        at = _offset(info, parent[2], 4)
        version, prologue, count, frame = raw[at:at+4]
        if version & 7 != 1:
            raise RuntimeBuildError('Faction native unwind version differs.')
        if not version >> 3 & 4:
            # Retain the immediate entry. Its intermediate chained records can
            # restore additional nonvolatile registers (pirate RBP/R12).
            return immediate
        parent = struct.unpack_from('<III', raw, _offset(info, parent[2]+_align(4+count*2, 4), 12))
        if parent not in entries:
            raise RuntimeBuildError('Faction native unwind parent is unregistered.')


def derive_faction_ai(name: str, original: bytes, expected_sha256: str):
    """Return a deterministic new private payload and its complete proof."""
    profiles = [p for p, pins in PROFILE_INPUT_SHA256.items() if pins.get(name) == expected_sha256]
    if name not in SPEC or len(profiles) != 1 or not isinstance(original, bytes) or hashlib.sha256(original).hexdigest() != expected_sha256:
        raise RuntimeBuildError('Faction AI input is not its exact reviewed private profile.')
    family = SPEC[name]
    try:
        info = _pe(original)
        def read(at, size):
            offset = _offset(info, at, size)
            return original[offset:offset+size]
        threshold = bytes.fromhex('4169c030750000')
        merchant = bytes.fromhex('4439b6880c0000')
        spawn = b'\xe8'+struct.pack('<i', family['create']-family['spawn']-5)
        old_hook = read(family['setter'], 6)
        if read(family['threshold'], 7) != threshold or read(family['merchant'], 7) != merchant or read(family['spawn'], 5) != spawn or old_hook[:1] != b'\xe9' or old_hook[-1:] != b'\x90':
            raise RuntimeBuildError('Faction AI native instruction preimage differs.')
        old_target = family['setter']+5+struct.unpack_from('<i', old_hook, 1)[0]
        old_code = _policy_code(old_target, family['setter'])
        if read(old_target, len(old_code)) != old_code:
            raise RuntimeBuildError('Existing ordinary CPU policy preserver differs.')
        pdata, pdata_size = struct.unpack_from('<II', original, info['opt']+112+3*8)
        if not pdata_size or pdata_size % 12 or pdata_size > 4*1024*1024:
            raise RuntimeBuildError('Faction AI exception directory is unbounded.')
        entries = [struct.unpack_from('<III', original, _offset(info, pdata+i, 12)) for i in range(0, pdata_size, 12)]
        if any(a[1] > b[0] for a, b in zip(entries, entries[1:])):
            raise RuntimeBuildError('Existing faction exception functions overlap.')
        section_align, file_align = struct.unpack_from('<II', original, info['opt']+32)
        rva = _align(max(s['rva']+max(s['virtual_size'], s['size']) for s in info['sections']), section_align)
        raw_at = _align(len(original), file_align)
        payload, functions, edits = bytearray(), [], []
        def function(label, hook, emit, standalone=False):
            payload.extend(b'\xcc'*(_align(len(payload), 16)-len(payload)))
            start = rva+len(payload)
            code = emit(start, family)
            payload.extend(code)
            functions.append(dict(name=label, start=start, end=start+len(code),
                                  parent=None if standalone else _parent(original, info, entries, hook),
                                  code_sha256=hashlib.sha256(code).hexdigest(), stack_adjustment=0))
            return start
        frequency_gate = function('pirate_interval', family['threshold'], _threshold_code)
        spawn_gate = function('new_pirate_armament', family['spawn'], _spawn_code, True)
        merchant_gate = function('merchant_native_fleet_target', family['merchant'], _merchant_code)
        setter_gate = function('special_native_flag_preserver', family['setter'],
                               lambda at, spec: _setter_code(at, spec, old_target))
        def patch(at, before, opcode, target):
            after = opcode+struct.pack('<i', target-at-5)+b'\x90'*(len(before)-5)
            if read(at, len(before)) != before:
                raise RuntimeBuildError('Faction patch preimage changed.')
            edits.append(dict(rva=at, preimage=before.hex(), patch=after.hex()))
        patch(family['threshold'], threshold, b'\xe9', frequency_gate)
        patch(family['spawn'], spawn, b'\xe8', spawn_gate)
        patch(family['merchant'], merchant, b'\xe9', merchant_gate)
        patch(family['setter'], old_hook, b'\xe9', setter_gate)
        new_entries = list(entries)
        for row in functions:
            payload.extend(bytes(_align(len(payload), 4)-len(payload)))
            row['unwind'] = rva+len(payload)
            unwind = bytes.fromhex('01000000') if row['parent'] is None else bytes.fromhex('21000000')+struct.pack('<III', *row['parent'])
            payload.extend(unwind)
            row['unwind_bytes'] = unwind.hex()
            new_entries.append((row['start'], row['end'], row['unwind']))
        new_entries.sort()
        if any(a[1] > b[0] for a, b in zip(new_entries, new_entries[1:])):
            raise RuntimeBuildError('New faction exception functions overlap.')
        payload.extend(bytes(_align(len(payload), 4)-len(payload)))
        new_pdata = rva+len(payload)
        payload.extend(b''.join(struct.pack('<III', *entry) for entry in new_entries))
        result = bytearray(original)
        header = info['table']+40*len(info['sections'])
        if header+40 > info['header_size'] or result[header:header+40] != bytes(40):
            raise RuntimeBuildError('Faction derivative has no unused section header.')
        for edit in edits:
            before, after = bytes.fromhex(edit['preimage']), bytes.fromhex(edit['patch'])
            at = _offset(info, edit['rva'], len(before));result[at:at+len(before)] = after
        size = _align(len(payload), file_align)
        struct.pack_into('<H', result, info['pe']+6, len(info['sections'])+1)
        struct.pack_into('<I', result, info['opt']+4, struct.unpack_from('<I', original, info['opt']+4)[0]+size)
        struct.pack_into('<I', result, info['opt']+56, _align(rva+len(payload), section_align))
        struct.pack_into('<II', result, info['opt']+112+3*8, new_pdata, len(new_entries)*12)
        result[header:header+40] = struct.pack('<8sIIIIIIHHI', b'.wsfacts', len(payload), rva, size, raw_at, 0, 0, 0, 0, 0x60000020)
        result.extend(bytes(raw_at-len(result))+payload+bytes(size-len(payload)))
        struct.pack_into('<I', result, info['opt']+64, checksum(bytes(result)))
        output = bytes(result);_pe(output)
        # All old mapped section bytes, including previous appended helpers,
        # remain byte-exact except these four independently proved sites.
        for section in info['sections']:
            expected = bytearray(original[section['raw']:section['raw']+section['size']])
            for edit in edits:
                offset = _offset(info, edit['rva'], len(bytes.fromhex(edit['patch'])))-section['raw']
                if 0 <= offset < len(expected):
                    value = bytes.fromhex(edit['patch']);expected[offset:offset+len(value)] = value
            if output[section['raw']:section['raw']+section['size']] != expected:
                raise RuntimeBuildError('Faction derivative changed an unrelated original section byte.')
        proof = dict(schema_version=1, profile=profiles[0], module=name,
            input_sha256=expected_sha256, output_sha256=hashlib.sha256(output).hexdigest(),
            section='.wsfacts', section_rva=rva, section_raw=raw_at,
            edits=edits, functions=functions, old_setter_target=old_target,
            old_exception_entries=len(entries), exception_entries=len(new_entries),
            original_sections_preserved_except_counted_sites=True,
            native_low_flags_mask=255, pirate_tag=PIRATE_TAG, merchant_tag=MERCHANT_TAG,
            original_files_modified=False, game_executed=False)
        return output, proof
    except (ValueError, KeyError, IndexError, struct.error) as exc:
        raise RuntimeBuildError('Faction private-AI derivative failed its bounded PE proof.') from exc
