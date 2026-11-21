"""Household supply and progression hooks for the inspected AMD64 World DLL.

Food 0.6 omits zero-weight needs. Original house getters assume their requested
good/index exists and divide by its demand rate without checking. The new leaf
guards reject absent/zero demands, then tail-jump to the complete, unmodified
native getter. Empty households still use its original result of 128.

The preserved Food 0.6 derivative skips Bread/Butcher's Meat absent from the
current tier. The progression derivative scores split food once per house
and leaves the original non-food, services and transition logic in place.
Appended code preserves the native frames. Existing DIR64 entries relocate
the changed vtable pointers.
"""
from __future__ import annotations

import hashlib
import struct

from .food_diet import FOOD_IDS
from .world_native import _align, _offset, _pe, checksum
from .world_runtime_build import PE


FOOD05_WELT_SHA256 = "ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9"
FOOD06_WELT_SHA256 = "e3755d8d796dae276ee5d62f08e778cb4cbec5d6d27053c608e43d7440108d71"
FOOD_PROGRESSION_WELT_SHA256 = "0b7f0d096aeb00775d9eaf98bd2c4fc946f70ef86a7deadbcf7b29672615d715"
HOUSE_VTABLE = 0xF9EE8
PROMOTION = dict(begin=0x881B0, end=0x8837F,
                 body_sha256="dc457f24c654d641243e7377a283b2fff424ea1654a51efc69ad8b485f63e7c4",
                 patch=0x88217, preimage=bytes.fromhex("410fb601420fb64c30030fb74552"),
                 resume=0x88225, skip=0x8824C, epilogue=0x88372,
                 parent=(0x881D9, 0x88315, 0x118CDC))
GETTERS = {
    "good": dict(slot=0x130, original=0x88DF0, size=0x49,
                 sha256="0d97ca6dd00c08c1e928ca60d66400fc2950711f7e342c95a8f06b51ecd51c99"),
    "index": dict(slot=0x138, original=0x88E40, size=0x44,
                  sha256="65d900d073a48db435a40134306388795ada0ce97faa32487b674a4c1f31bfb7"),
}

# Exact AMD64 History Edition instruction spans. The appended in-frame
# sequences chain to the active native unwind fragment for their entry.
_GROWTH_SCORE_ENTRY = (0x883BF, bytes.fromhex("4c8b7948450fb6b7cc000000"))
_GROWTH_GOODS = (0x883E7, bytes.fromhex("410fb700410fb7cc"))
_GROWTH_USE_SCORE = (0x8849E, bytes.fromhex("410fb74f664c8b742438410fb7c4"))
_PROMOTION_SCORE_ENTRY = (0x881F6, bytes.fromhex("41bf80000000"))
_PROMOTION_USE_SCORE = (0x882C8, bytes.fromhex("0fb74552410fb74d664c8b642460488b742458"))
_GROWTH_TICK_CALL = (0x887CB, bytes.fromhex("e8b0fbffff"))
_PROMOTION_TICK_CALL = (0x888A3, bytes.fromhex("e808f9ffff"))
_GROWTH_UNWIND = (0x883B3, 0x8842D, 0x118D3C)
_GROWTH_BEGIN = 0x88380
_GROWTH_VTABLE_SLOT = HOUSE_VTABLE + 0x140


class FoodSupplyError(ValueError):
    pass


def _sha(data):
    if not isinstance(data, bytes):
        raise FoodSupplyError("The supply guard requires immutable native bytes.")
    return hashlib.sha256(data).hexdigest()


def guard_code(rva: int, original: int, *, indexed: bool) -> tuple[bytes, list[dict]]:
    """Author the two leaf sequences with explicit REL32 label fixups.

    Common: null house -> zero; population zero -> original; read non-null
    needs. By-good: require EDX<96, read mapped index into EAX. By-index: EAX
    receives EDX directly. Require count<=18, index<count and nonzero rate.
    The valid path JMPs to the original entry; zero is XOR EAX,EAX / RET.
    """
    if (type(rva) is not int or type(original) is not int or rva < 0 or original < 0
            or type(indexed) is not bool):
        raise FoodSupplyError("Invalid authored guard location or mode.")
    code, labels, fixups = bytearray(), {}, []

    def emit(value):
        code.extend(bytes.fromhex(value))

    def branch(opcode, target):
        emit(opcode)
        fixups.append((len(code), target))
        code.extend(bytes(4))

    emit("48 85 c9")                       # TEST RCX,RCX
    branch("0f 84", "zero")                # JZ zero
    emit("66 83 79 52 00")                 # CMP WORD [RCX+52],0
    branch("0f 84", original)              # JE original (preserve empty result)
    emit("4c 8b 41 48 4d 85 c0")           # MOV R8,[RCX+48] / TEST R8,R8
    branch("0f 84", "zero")
    if not indexed:
        emit("83 fa 60")                   # CMP EDX,96
        branch("0f 83", "zero")            # JAE zero
        emit("89 d0 41 0f b6 44 00 03")     # EAX=EDX; MOVZX EAX,[R8+RAX+3]
    else:
        emit("89 d0")                      # EAX=EDX (unsigned index guard)
    emit("45 0f b6 48 02")                 # MOVZX R9D,BYTE [R8+2]
    emit("41 83 f9 12")                    # CMP R9D,18
    branch("0f 87", "zero")                # JA zero
    emit("44 39 c8")                       # CMP EAX,R9D
    branch("0f 83", "zero")                # JAE zero (also rejects count zero)
    emit("66 41 83 7c 80 66 00")           # CMP WORD [R8+RAX*4+66],0
    branch("0f 84", "zero")
    branch("e9", original)                 # Tail JMP; original code stays whole
    labels["zero"] = rva + len(code)
    emit("31 c0 c3")                       # XOR EAX,EAX / RET
    proof = []
    for offset, destination in fixups:
        target = labels[destination] if isinstance(destination, str) else destination
        distance = target - (rva + offset + 4)
        if not -(1 << 31) <= distance < (1 << 31):
            raise FoodSupplyError("A supply guard branch is outside REL32 range.")
        struct.pack_into("<i", code, offset, distance)
        proof.append(dict(displacement_offset=offset, target_rva=target,
                          displacement=distance))
    return bytes(code), proof


def relocation_entries(pe: PE) -> set[int]:
    rva, size = pe.directory(5)
    data = pe.read(rva, size)
    result, offset = set(), 0
    while offset < len(data):
        if offset + 8 > len(data):
            raise FoodSupplyError("Truncated native relocation page.")
        page, length = struct.unpack_from("<II", data, offset)
        if length < 8 or length % 4 or offset + length > len(data):
            raise FoodSupplyError("Invalid native relocation page.")
        for at in range(offset + 8, offset + length, 2):
            entry = struct.unpack_from("<H", data, at)[0]
            if entry == 0:
                continue
            if entry >> 12 != 10:
                raise FoodSupplyError("The inspected AMD64 relocation kind differs.")
            address = page + (entry & 4095)
            if address in result:
                raise FoodSupplyError("Duplicate native relocation target.")
            pe.read(address, 8)
            result.add(address)
        offset += length
    return result


def promotion_guard_code(rva: int, *, combined=False) -> tuple[bytes, list[dict]]:
    """Guard the reviewed in-frame next-tier/current-tier requirement lookup.

    Live loop state R9/R10/R11 and accumulated RBX remain intact. Valid demands
    restore the displaced population load and resume native scoring. Absent
    next-tier Bread/Butcher's Meat skip only that future-food gate in the
    legacy derivative. The combined derivative excludes every split food
    from this goods average. Failure restores the four native saved
    registers before its existing zero epilogue.
    No push, pop, call or stack adjustment is introduced by the thunk itself.
    """
    if type(rva) is not int or rva < 0:
        raise FoodSupplyError("Invalid promotion guard location.")
    code, labels, fixups = bytearray(), {}, []

    def emit(value):
        code.extend(bytes.fromhex(value))

    def branch(opcode, target):
        emit(opcode)
        fixups.append((len(code), target))
        code.extend(bytes(4))

    emit("41 0f b6 01")                     # MOVZX EAX,BYTE [R9] (next good)
    if combined:
        for food in FOOD_IDS.values():
            emit(f"83 f8 {food:02x}")      # CMP EAX,food
            branch("0f 84", PROMOTION["skip"])
    emit("83 f8 60")                       # CMP EAX,96
    branch("0f 83", "fail")
    emit("42 0f b6 4c 30 03")              # MOVZX ECX,BYTE [R14+RAX+3]
    emit("45 0f b6 46 02 45 85 c0")        # R8D=current count; TEST R8D,R8D
    branch("0f 84", "fail")
    emit("41 83 f8 12")                    # CMP R8D,18
    branch("0f 87", "fail")
    emit("44 39 c1")                       # CMP ECX,R8D
    branch("0f 83", "fail" if combined else "missing")
    emit("66 41 83 7c 8e 66 00")           # CMP WORD [R14+RCX*4+66],0
    branch("0f 84", "fail")
    emit("0f b7 45 52 85 c0")              # EAX=population; TEST EAX,EAX
    branch("0f 84", "fail")
    branch("e9", PROMOTION["resume"])
    if not combined:
        labels["missing"] = rva + len(code)
        emit("83 f8 19")                   # Absent Bread (25) starts next tier
        branch("0f 84", PROMOTION["skip"])
        emit("83 f8 2d")                   # Absent Butcher's Meat (45), likewise
        branch("0f 84", PROMOTION["skip"])
    labels["fail"] = rva + len(code)
    emit("48 8b 5c 24 50 48 8b 74 24 58")  # Restore saved RBX,RSI
    emit("4c 8b 64 24 60 4c 8b 7c 24 20")  # Restore saved R12,R15
    branch("e9", PROMOTION["epilogue"])
    proof = []
    for offset, destination in fixups:
        target = labels[destination] if isinstance(destination, str) else destination
        distance = target - (rva + offset + 4)
        if not -(1 << 31) <= distance < (1 << 31):
            raise FoodSupplyError("A promotion branch is outside REL32 range.")
        struct.pack_into("<i", code, offset, distance)
        proof.append(dict(displacement_offset=offset, target_rva=target, displacement=distance))
    return bytes(code), proof


def progression_edited_spans() -> tuple[tuple[int, int], ...]:
    """Original-image ranges for compatibility and native preimage checks."""
    edits = (_GROWTH_SCORE_ENTRY, _GROWTH_GOODS, _GROWTH_USE_SCORE,
             _PROMOTION_SCORE_ENTRY, _PROMOTION_USE_SCORE, _GROWTH_TICK_CALL,
             _PROMOTION_TICK_CALL, (PROMOTION["patch"], PROMOTION["preimage"]))
    return tuple(sorted([(rva, len(before)) for rva, before in edits] + [(_GROWTH_VTABLE_SLOT, 8)]))


def _branch(rva: int, opcode: bytes, target: int) -> bytes:
    return opcode + struct.pack("<i", target - rva - len(opcode) - 4)


def _short_jump(rva: int, target: int) -> bytes:
    return b"\xeb" + struct.pack("<b", target - rva - 2)


def _continue_native(rva: int, target: int) -> bytes:
    # A direct JMP can mark a chained range as a tail epilogue. RDX is dead
    # at these resume points, so use register-indirect JMP within the frame.
    return _branch(rva, b"\x48\x8d\x15", target) + b"\xff\xe2"


def _chain(parent: tuple[int, int, int]) -> bytes:
    return b"\x21\x00\x00\x00" + struct.pack("<III", *parent)


def _growth_vtable_code(start: int) -> bytes:
    """Preserve the public one-argument growth virtual's stock calling ABI."""
    code = bytearray()
    branches = []

    def emit(hex_bytes):
        code.extend(bytes.fromhex(hex_bytes))

    def jump(opcode, label, *, near=False):
        code.extend((0x0F, opcode + 0x10) if near else (opcode,))
        branches.append((len(code), label, "<i" if near else "<b"))
        code.extend(bytes(4 if near else 1))

    emit("4881eca8000000")                 # Align stack, reserve shadow + Value + house
    emit("31c0 4885c9")                    # XOR EAX,EAX / TEST RCX,RCX
    jump(0x74, "return", near=True)
    emit("6683795200")                     # CMP WORD [house+52h],0
    jump(0x74, "return", near=True)
    emit("48898c24a0000000 488b4918")     # Save house; use its city, like the house tick
    emit("4885c9")
    jump(0x74, "unavailable")
    emit("488b01 4885c0")                # Validate city vtable
    jump(0x74, "unavailable")
    emit("ff5040 4885c0")                # Ask the city for its profile
    jump(0x74, "unavailable")
    emit("488bc8 488b01 4885c0")        # Profile receiver and vtable
    jump(0x74, "unavailable")
    emit("660fefc0")                     # Zero the 128-byte native Value
    for offset in range(0x20, 0x80, 16):
        code.extend((0x0F, 0x29, 0x44, 0x24, offset))  # MOVAPS [RSP+disp8], XMM0
    for offset in range(0x80, 0xA0, 16):
        emit("0f298424")                # MOVAPS [RSP+disp32], XMM0
        code.extend(struct.pack("<i", offset))
    emit("4c8d442420 ba21000000 4533c9")  # R8=Value, EDX=unlock property, R9=0
    emit("ff9098000000 8b542428")         # Read Value's unlock mask, as the native tick does
    jump(0xEB, "evaluate")
    labels = {"unavailable": len(code)}
    emit("31d2")                         # Failed retrieval contributes no unlocked foods
    labels["evaluate"] = len(code)
    emit("488b8c24a0000000")              # RCX=house
    code.extend(_branch(start + len(code), b"\xe8", _GROWTH_BEGIN))
    labels["return"] = len(code)
    emit("4881c4a8000000 c3")
    for offset, label, encoding in branches:
        struct.pack_into(encoding, code, offset, labels[label] - offset - struct.calcsize(encoding))
    return bytes(code)


def _progression_hooks(pe: PE, payload: bytearray, rva: int, base: int, relocations: set[int]):
    """Append the common score and narrow thunks, preserving the native frame.

    The house tick already retrieves the owner's unlock mask. Its two calls
    relay that mask in EDX. Each native evaluation computes the score once
    before its goods and services scans. The high half of a saved register
    carries the score while intervening native reads use its original low
    half. The score routine is stackless and leaves the shadow slots alone.
    """
    from .food_progression import combined_score_code

    hooks, unwind = [], []

    def align_code():
        payload.extend(b"\x90" * (_align(len(payload), 16) - len(payload)))
        return rva + len(payload)

    def add_hook(name, site, target=None, patch=None):
        address, before = site
        if pe.read(address, len(before)) != before:
            raise FoodSupplyError(f"The native {name} instructions differ.")
        if patch is None:
            patch = _branch(address, b"\xe9", target)
        if len(patch) > len(before):
            raise FoodSupplyError(f"The {name} patch exceeds its verified instructions.")
        patch += b"\x90" * (len(before) - len(patch))
        hook = dict(name=name, patch_rva=address, preimage=before.hex(),
                    patch=patch.hex(), target_rva=target)
        hooks.append(hook)
        return hook

    def append_sequence(name, site, start, code, parent):
        if parent not in pe.function_table():
            raise FoodSupplyError(f"The native {name} unwind parent differs.")
        payload.extend(code)
        hook = add_hook(name, site, target=start)
        hook.update(code_size=len(code), unwind_parent=list(parent))
        unwind.append((start, start + len(code), _chain(parent)))

    score = align_code()
    payload.extend(combined_score_code())

    for name, call_site, native in (
        ("growth unlock mask", _GROWTH_TICK_CALL, _GROWTH_BEGIN),
        ("promotion unlock mask", _PROMOTION_TICK_CALL, PROMOTION["begin"]),
    ):
        start = align_code()
        # CALL added an eight-byte return, putting the tick's mask at [rsp+40h].
        load_mask = bytes.fromhex("8b542440")
        payload.extend(load_mask + _branch(start + len(load_mask), b"\xe9", native))
        add_hook(name, call_site, target=start, patch=_branch(call_site[0], b"\xe8", start))

    if _GROWTH_VTABLE_SLOT not in relocations:
        raise FoodSupplyError("The native growth vtable DIR64 entry differs.")
    start = align_code()
    public_growth = _growth_vtable_code(start)
    payload.extend(public_growth)
    growth_virtual = (_GROWTH_VTABLE_SLOT, struct.pack("<Q", base + _GROWTH_BEGIN))
    hook = add_hook("growth vtable adapter", growth_virtual, target=start,
                    patch=struct.pack("<Q", base + start))
    hook.update(code_size=len(public_growth), unwind_parent=None, stack_allocation=0xA8)
    # Version 1, 7-byte prologue with UWOP_ALLOC_LARGE (0xa8 / 8 slots).
    unwind.append((start, start + len(public_growth), bytes.fromhex("0107020007011500")))

    start = align_code()
    prefix = bytes.fromhex("4533c0")          # XOR R8D,R8D (growth mode)
    growth_entry = prefix + _branch(start + len(prefix), b"\xe8", score)
    growth_entry += bytes.fromhex(
        "48c1e020 4c0be0 "                  # R12.high = score, R12.low = population
        "4533c9 41ba80000000 488bcd"        # Restore the native R9, R10 and house input
    ) + _GROWTH_SCORE_ENTRY[1]
    growth_entry += _continue_native(start + len(growth_entry),
                                     _GROWTH_SCORE_ENTRY[0] + len(_GROWTH_SCORE_ENTRY[1]))
    append_sequence("growth score entry", _GROWTH_SCORE_ENTRY, start, growth_entry, _GROWTH_UNWIND)

    start = align_code()
    prefix = bytes.fromhex("41b801000000")    # MOV R8D,1 (promotion mode)
    promotion_entry = prefix + _branch(start + len(prefix), b"\xe8", score)
    promotion_entry += bytes.fromhex(
        "448bf8 49c1e720 4981cf80000000 "   # R15.high = score, R15.low = 128
        "4533db"                           # Restore the native goods count
    )
    promotion_entry += _continue_native(start + len(promotion_entry),
                                        _PROMOTION_SCORE_ENTRY[0] + len(_PROMOTION_SCORE_ENTRY[1]))
    append_sequence("promotion score entry", _PROMOTION_SCORE_ENTRY, start,
                    promotion_entry, PROMOTION["parent"])

    start = align_code()
    goods_filter = bytearray.fromhex("410fb640fe")  # MOVZX EAX,BYTE [R8-2] (current good)
    skip_offsets = []
    for food in FOOD_IDS.values():
        goods_filter.extend((0x83, 0xF8, food, 0x74, 0))  # CMP EAX,food / JE skip
        skip_offsets.append(len(goods_filter) - 1)
    goods_filter += _GROWTH_GOODS[1]
    goods_filter += _continue_native(start + len(goods_filter),
                                     _GROWTH_GOODS[0] + len(_GROWTH_GOODS[1]))
    for offset in skip_offsets:
        struct.pack_into("<b", goods_filter, offset, len(goods_filter) - offset - 1)
    goods_filter += _continue_native(start + len(goods_filter), 0x8840D)
    append_sequence("growth goods filter", _GROWTH_GOODS, start, goods_filter, _GROWTH_UNWIND)

    # Recover the score and rejoin the original tier table and native rounding.
    growth_use = bytes.fromhex("4c8b742438 498bd4 48c1ea20")  # Restore R14, EDX=R12.high
    add_hook("growth food rating", _GROWTH_USE_SCORE,
             patch=growth_use + _short_jump(_GROWTH_USE_SCORE[0] + len(growth_use), 0x884CA))
    promotion_use = bytes.fromhex("4c8b642460 488b742458 49c1ef20 418bcf")  # Restore R12, RSI
    add_hook("promotion food rating", _PROMOTION_USE_SCORE,
             patch=promotion_use + _short_jump(_PROMOTION_USE_SCORE[0] + len(promotion_use), 0x882F9))
    return score, hooks, unwind


def _construct_welt(food05: bytes, *, progression=False) -> tuple[bytes, dict]:
    if _sha(food05) != FOOD05_WELT_SHA256:
        raise FoodSupplyError("The supply guards require exact preserved Food 0.5 AnnoWelt.dll.")
    pe, info = PE(food05), _pe(food05)
    base = info["image_base"]
    section_align, file_align = struct.unpack_from("<II", food05, pe.optional + 32)
    rva = _align(pe.image_size, section_align)
    relocations = relocation_entries(pe)
    payload, hooks = bytearray(), []
    for kind, getter in GETTERS.items():
        original = pe.read(getter["original"], getter["size"])
        if _sha(original) != getter["sha256"]:
            raise FoodSupplyError("An original household supply getter differs.")
        slot = HOUSE_VTABLE + getter["slot"]
        if struct.unpack("<Q", pe.read(slot, 8))[0] != base + getter["original"] or slot not in relocations:
            raise FoodSupplyError("A native house vtable pointer or its DIR64 entry differs.")
        payload.extend(b"\x90" * (_align(len(payload), 16) - len(payload)))
        start = rva + len(payload)
        code, branches = guard_code(start, getter["original"], indexed=kind == "index")
        payload.extend(code)
        hooks.append(dict(kind=kind, slot=getter["slot"], vtable_rva=slot,
                          original_rva=getter["original"], original_size=getter["size"],
                          original_sha256=getter["sha256"], target_rva=start,
                          code_size=len(code), code_sha256=_sha(code), branches=branches,
                          stack_adjustment=0, nonvolatile_registers_changed=[], tail_jump=True))
    if (_sha(pe.read(PROMOTION["begin"], PROMOTION["end"] - PROMOTION["begin"])) != PROMOTION["body_sha256"]
            or pe.read(PROMOTION["patch"], 14) != PROMOTION["preimage"]
            or PROMOTION["parent"] not in pe.function_table()):
        raise FoodSupplyError("The native promotion body, mapping preimage or unwind parent differs.")
    payload.extend(b"\x90" * (_align(len(payload), 16) - len(payload)))
    promotion_start = rva + len(payload)
    promotion_code, promotion_branches = promotion_guard_code(promotion_start, combined=progression)
    payload.extend(promotion_code)
    unwind_specs = [(promotion_start, promotion_start + len(promotion_code), _chain(PROMOTION["parent"]))]
    progression_proof = {}
    progression_hooks = []
    if progression:
        score, progression_hooks, additional_unwind = _progression_hooks(pe, payload, rva, base, relocations)
        unwind_specs.extend(additional_unwind)
        progression_proof = dict(food_progression_score_rva=score,
                                 food_progression_hooks=progression_hooks)
    new_entries = []
    unwind_by_target = {}
    for start, end, unwind_info in unwind_specs:
        payload.extend(bytes(_align(len(payload), 4) - len(payload)))
        unwind_rva = rva + len(payload)
        new_entries.append((start, end, unwind_rva))
        unwind_by_target[start] = unwind_rva
        payload.extend(unwind_info)
    for hook in progression_hooks:
        if "unwind_parent" in hook:
            hook["unwind_rva"] = unwind_by_target[hook["target_rva"]]
    unwind = new_entries[0][2]
    entries = sorted(pe.function_table() | set(new_entries))
    if any(first[1] > second[0] for first, second in zip(entries, entries[1:])):
        raise FoodSupplyError("The promotion unwind range overlaps a native function.")
    payload.extend(bytes(_align(len(payload), 4) - len(payload)))
    pdata = (rva + len(payload), len(entries) * 12)
    payload.extend(b"".join(struct.pack("<III", *entry) for entry in entries))
    table = info["table"] + 40 * len(info["sections"])
    if (table + 40 > min(section["raw"] for section in info["sections"] if section["size"])
            or food05[table:table + 40] != bytes(40)):
        raise FoodSupplyError("The preserved World DLL has no blank section-header slot.")
    result = bytearray(food05)
    for hook in hooks:
        struct.pack_into("<Q", result, _offset(info, hook["vtable_rva"], 8), base + hook["target_rva"])
    patch = _offset(info, PROMOTION["patch"], 14)
    detour = b"\xe9" + struct.pack("<i", promotion_start - PROMOTION["patch"] - 5) + b"\x90" * 9
    result[patch:patch + 14] = detour
    for hook in progression_hooks:
        after = bytes.fromhex(hook["patch"])
        offset = _offset(info, hook["patch_rva"], len(after))
        result[offset:offset + len(after)] = after
    raw = _align(len(result), file_align)
    raw_size = _align(len(payload), file_align)
    result[table:table + 40] = struct.pack("<8sIIIIIIHHI", b".food06", len(payload), rva,
                                        raw_size, raw, 0, 0, 0, 0, 0x60000020)
    struct.pack_into("<H", result, pe.pe + 6, len(info["sections"]) + 1)
    struct.pack_into("<I", result, pe.optional + 4,
                     struct.unpack_from("<I", result, pe.optional + 4)[0] + raw_size)
    struct.pack_into("<I", result, pe.optional + 56, _align(rva + len(payload), section_align))
    struct.pack_into("<II", result, pe.optional + 112 + 3 * 8, *pdata)
    result.extend(bytes(raw - len(result)) + payload + bytes(raw_size - len(payload)))
    struct.pack_into("<I", result, pe.optional + 64, checksum(bytes(result)))
    output = bytes(result)
    checked = PE(output)
    if (any(checked.directory(i) != pe.directory(i) for i in range(16) if i != 3)
            or relocation_entries(checked) != relocations
            or checked.function_table() != set(entries)):
        raise FoodSupplyError("The supply guard unexpectedly changed native directories or tables.")
    return output, dict(input_sha256=_sha(food05), output_sha256=_sha(output),
                        section_rva=rva, section_size=len(payload), section_flags=0x60000020,
                        hooks=hooks, original_getters_unchanged=True,
                        imports_exports_unchanged=True, new_relocations=0,
                        new_unwind_entries=len(new_entries),
                        promotion_guard=dict(patch_rva=PROMOTION["patch"], preimage=PROMOTION["preimage"].hex(),
                                             patch=detour.hex(), target_rva=promotion_start,
                                             code_size=len(promotion_code), code_sha256=_sha(promotion_code),
                                             branches=promotion_branches, unwind_rva=unwind,
                                             unwind_parent=list(PROMOTION["parent"]), stack_adjustment=0,
                                             failure_restores=["rbx", "rsi", "r12", "r15"],
                                             excluded_goods=(list(FOOD_IDS.values()) if progression else []),
                                             only_missing_future_foods_skipped=([] if progression else [25, 45])),
                        existing_dir64_entries_reused=(
                            [hook["vtable_rva"] for hook in hooks]
                            + ([_GROWTH_VTABLE_SLOT] if progression else [])
                        ),
                        actual_game_test_performed=False, **progression_proof)


def build_welt(food05_bytes: bytes) -> tuple[bytes, dict]:
    """Compose the fixed derivative in memory; unknown/repeated inputs refuse."""
    output, proof = _construct_welt(food05_bytes)
    if _sha(output) != FOOD06_WELT_SHA256:
        raise FoodSupplyError("The household supply derivative differs from its reviewed fingerprint.")
    return output, proof


def build_progression_welt(food05_bytes: bytes) -> tuple[bytes, dict]:
    """Compose the combined household progression and retained supply guards."""
    output, proof = _construct_welt(food05_bytes, progression=True)
    if _sha(output) != FOOD_PROGRESSION_WELT_SHA256:
        raise FoodSupplyError("The household progression derivative differs from its reviewed fingerprint.")
    return output, proof
