"""Exact Food 0.6 household supply guards for the inspected AMD64 World DLL.

Food 0.6 omits zero-weight needs. Original house getters assume their requested
good/index exists and divide by its demand rate without checking. The new leaf
guards reject absent/zero demands, then tail-jump to the complete, unmodified
native getter. Empty households still use its original result of 128.

The two getter guards are leaves. The promotion thunk additionally skips only
Bread/Butcher's Meat absent from the current tier; other missing or zero-rate
requirements safely refuse promotion. It preserves the existing frame and has
an unwind chain to the exact native fragment. Existing DIR64 entries relocate
the changed vtable pointers; all code branches remain position-relative.
"""
from __future__ import annotations

import hashlib
import struct

from .world_native import _align, _offset, _pe, checksum
from .world_runtime_build import PE


FOOD05_WELT_SHA256 = "ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9"
FOOD06_WELT_SHA256 = "e3755d8d796dae276ee5d62f08e778cb4cbec5d6d27053c608e43d7440108d71"
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


def promotion_guard_code(rva: int) -> tuple[bytes, list[dict]]:
    """Guard the reviewed in-frame next-tier/current-tier requirement lookup.

    Live loop state R9/R10/R11 and accumulated RBX remain intact. Valid demands
    restore the displaced population load and resume native scoring. Absent
    next-tier Bread/Butcher's Meat skip only that future-food gate. Failure
    restores the four native saved registers before its existing zero epilogue.
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
    emit("83 f8 60")                       # CMP EAX,96
    branch("0f 83", "fail")
    emit("42 0f b6 4c 30 03")              # MOVZX ECX,BYTE [R14+RAX+3]
    emit("45 0f b6 46 02 45 85 c0")        # R8D=current count; TEST R8D,R8D
    branch("0f 84", "fail")
    emit("41 83 f8 12")                    # CMP R8D,18
    branch("0f 87", "fail")
    emit("44 39 c1")                       # CMP ECX,R8D
    branch("0f 83", "missing")
    emit("66 41 83 7c 8e 66 00")           # CMP WORD [R14+RCX*4+66],0
    branch("0f 84", "fail")
    emit("0f b7 45 52 85 c0")              # EAX=population; TEST EAX,EAX
    branch("0f 84", "fail")
    branch("e9", PROMOTION["resume"])
    labels["missing"] = rva + len(code)
    emit("83 f8 19")                       # Absent Bread (25) starts next tier
    branch("0f 84", PROMOTION["skip"])
    emit("83 f8 2d")                       # Absent Butcher's Meat (45), likewise
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


def _construct_welt(food05: bytes) -> tuple[bytes, dict]:
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
    promotion_code, promotion_branches = promotion_guard_code(promotion_start)
    payload.extend(promotion_code)
    payload.extend(bytes(_align(len(payload), 4) - len(payload)))
    unwind = rva + len(payload)
    payload.extend(b"\x21\x00\x00\x00" + struct.pack("<III", *PROMOTION["parent"]))
    entries = sorted(pe.function_table() | {(promotion_start, promotion_start + len(promotion_code), unwind)})
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
                        imports_exports_unchanged=True, new_relocations=0, new_unwind_entries=1,
                        promotion_guard=dict(patch_rva=PROMOTION["patch"], preimage=PROMOTION["preimage"].hex(),
                                             patch=detour.hex(), target_rva=promotion_start,
                                             code_size=len(promotion_code), code_sha256=_sha(promotion_code),
                                             branches=promotion_branches, unwind_rva=unwind,
                                             unwind_parent=list(PROMOTION["parent"]), stack_adjustment=0,
                                             failure_restores=["rbx", "rsi", "r12", "r15"],
                                             only_missing_future_foods_skipped=[25, 45]),
                        existing_dir64_entries_reused=[hook["vtable_rva"] for hook in hooks],
                        actual_game_test_performed=False)


def build_welt(food05_bytes: bytes) -> tuple[bytes, dict]:
    """Compose the fixed derivative in memory; unknown/repeated inputs refuse."""
    output, proof = _construct_welt(food05_bytes)
    if _sha(output) != FOOD06_WELT_SHA256:
        raise FoodSupplyError("The household supply derivative differs from its reviewed fingerprint.")
    return output, proof
