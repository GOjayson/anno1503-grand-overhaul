"""Exact private-AI demand bounds for the separate Food 0.6 + World profile.

Food 0.6 omits zero-share needs. HE maps an absent good to the need count,
whereas the inherited AI demand loop indexes that sentinel without checking.
This derivative skips absent/invalid mappings before reading a demand rate.
Valid rates, native arithmetic and all existing faction policies remain.
Neither the host AI modules nor the preserved Food 0.5 profile are changed.
"""
from __future__ import annotations

import hashlib
import struct

from .world_native import _align, _offset, _pe, checksum
from .world_options_factions import _parent
from .world_runtime_build import PE, RuntimeBuildError


INPUT_SHA256 = {
    "CompLogic.dll": "fca39112873f10003abf617b2804ec8dc82cb5264655d59a65535b2b370c99fc",
    "CompLogicClassic.dll": "d49b4c360cbc02963d403108fb2c2205ee8a818f4b0ad15747614a3598b36888",
}
OUTPUT_SHA256 = {
    "CompLogic.dll": "73b49582fa39923fd8a70802b7845eab7547ae0a0e1bb32dc8c48831e7159f41",
    "CompLogicClassic.dll": "70af14ff63d90f1ad2588cc07c2f4f859619f1af69adb8b859caaf7a3071009c",
}
SPEC = {
    "CompLogic.dll": dict(begin=0x582E5, end=0x58401, patch=0x58377,
                          resume=0x58381, skip=0x5838F,
                          body_sha256="f18d69dbe521ed5b1d5a6ec550ca029c76f20925c9f2c4d3fee88b981a0c8fd1"),
    "CompLogicClassic.dll": dict(begin=0x55845, end=0x55961, patch=0x558D7,
                                 resume=0x558E1, skip=0x558EF,
                                 body_sha256="08b87ddad664748d46ac10eed7f9563b1069e9ab7c2bdc41281a1fab39921f77"),
}
PREIMAGE = bytes.fromhex("410fb6043f0fb74c8766")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def guard_code(rva: int, *, resume: int, skip: int) -> tuple[bytes, list[dict]]:
    """A no-frame continuation; R11 is dead before the next native call.

    Register-indirect continuations deliberately are not Win64 tail epilogues.
    This allows the chained unwind to restore the active native caller frame
    throughout the guard. No nonvolatile register or stack slot is changed.
    """
    if any(type(n) is not int or not 0 < n < 0x80000000 for n in (rva, resume, skip)):
        raise RuntimeBuildError("Invalid Food 0.6 AI guard coordinates.")
    code, fixups, labels = bytearray(), [], {}

    def emit(value):
        code.extend(bytes.fromhex(value))

    def branch(opcode, target):
        emit(opcode)
        fixups.append((len(code), target))
        code.extend(bytes(4))

    def continuation(target):
        branch("4c8d1d", target)  # LEA R11,[RIP+disp32]
        emit("41ffe3")           # JMP R11 (ModRM11, not a tail epilogue)

    emit("410fb6043f")            # Original MOVZX EAX,BYTE [R15+RDI]
    emit("0fb64f02")              # MOVZX ECX,BYTE [RDI+2] (native need count)
    emit("83f912")                # CMP ECX,18 (reviewed native record capacity)
    branch("0f87", "skip")       # JA skip
    emit("39c8")                  # CMP EAX,ECX
    branch("0f83", "skip")       # JAE skip, including count zero/sentinel
    emit("0fb74c8766")            # Original MOVZX ECX,WORD [RDI+RAX*4+66]
    continuation(resume)
    labels["skip"] = rva + len(code)
    continuation(skip)
    proof = []
    for offset, target in fixups:
        target = labels[target] if isinstance(target, str) else target
        displacement = target - (rva + offset + 4)
        if not -(1 << 31) <= displacement < (1 << 31):
            raise RuntimeBuildError("Food 0.6 AI guard leaves REL32 range.")
        struct.pack_into("<i", code, offset, displacement)
        proof.append(dict(displacement_offset=offset, target_rva=target))
    return bytes(code), proof


def _construct(name: str, activity_bytes: bytes) -> tuple[bytes, dict]:
    if (name not in INPUT_SHA256 or not isinstance(activity_bytes, bytes)
            or _sha(activity_bytes) != INPUT_SHA256[name]):
        raise RuntimeBuildError("Food 0.6 AI needs its exact preserved faction-activity input.")
    pe, info, spec = PE(activity_bytes), _pe(activity_bytes), SPEC[name]
    if (_sha(pe.read(spec["begin"], spec["end"] - spec["begin"])) != spec["body_sha256"]
            or pe.read(spec["patch"], len(PREIMAGE)) != PREIMAGE):
        raise RuntimeBuildError("The reviewed native AI demand mapping differs.")
    entries = sorted(pe.function_table())
    parent = _parent(activity_bytes, info, entries, spec["patch"])
    section_align, file_align = pe.unpack("<II", pe.optional + 32)
    rva = _align(pe.image_size, section_align)
    code, branches = guard_code(rva, resume=spec["resume"], skip=spec["skip"])
    payload = bytearray(code)
    payload.extend(bytes(_align(len(payload), 4) - len(payload)))
    unwind = rva + len(payload)
    payload.extend(bytes.fromhex("21000000") + struct.pack("<III", *parent))
    entries.append((rva, rva + len(code), unwind))
    entries.sort()
    if any(a[1] > b[0] for a, b in zip(entries, entries[1:])):
        raise RuntimeBuildError("Food 0.6 AI unwind ranges overlap.")
    payload.extend(bytes(_align(len(payload), 4) - len(payload)))
    pdata = (rva + len(payload), len(entries) * 12)
    payload.extend(b"".join(struct.pack("<III", *entry) for entry in entries))
    table = info["table"] + len(info["sections"]) * 40
    if (table + 40 > min(s["raw"] for s in info["sections"] if s["size"])
            or activity_bytes[table:table + 40] != bytes(40)):
        raise RuntimeBuildError("The Food 0.6 AI input has no unused section header.")
    output = bytearray(activity_bytes)
    # The original mapping is ten bytes, enough for a non-epilogue entry
    # continuation. This avoids relying on an E9 target lookup to recognize
    # the appended code's chained native parent during virtual unwind.
    patch = bytes.fromhex("4c8d1d") + struct.pack("<i", rva - spec["patch"] - 7) + bytes.fromhex("41ffe3")
    at = _offset(info, spec["patch"], len(PREIMAGE))
    output[at:at + len(patch)] = patch
    raw, raw_size = _align(len(output), file_align), _align(len(payload), file_align)
    output[table:table + 40] = struct.pack("<8sIIIIIIHHI", b".f06need", len(payload),
                                        rva, raw_size, raw, 0, 0, 0, 0, 0x60000020)
    struct.pack_into("<H", output, info["pe"] + 6, len(info["sections"]) + 1)
    struct.pack_into("<I", output, pe.optional + 4, pe.unpack("<I", pe.optional + 4)[0] + raw_size)
    struct.pack_into("<I", output, pe.optional + 56, _align(rva + len(payload), section_align))
    struct.pack_into("<II", output, pe.optional + 112 + 3 * 8, *pdata)
    output.extend(bytes(raw - len(output)) + payload + bytes(raw_size - len(payload)))
    struct.pack_into("<I", output, pe.optional + 64, checksum(bytes(output)))
    result, checked = bytes(output), PE(bytes(output))
    if (any(checked.directory(i) != pe.directory(i) for i in range(16) if i != 3)
            or checked.function_table() != set(entries)):
        raise RuntimeBuildError("Food 0.6 AI changed an unrelated native directory.")
    for section in info["sections"]:
        before = bytearray(activity_bytes[section["raw"]:section["raw"] + section["size"]])
        if section["rva"] <= spec["patch"] < section["rva"] + section["virtual_size"]:
            relative = at - section["raw"]
            before[relative:relative + len(patch)] = patch
        if result[section["raw"]:section["raw"] + section["size"]] != before:
            raise RuntimeBuildError("Food 0.6 AI changed an unrelated mapped section byte.")
    return result, dict(schema_version=1, profile="food06-world", module=name,
                        input_sha256=INPUT_SHA256[name], output_sha256=_sha(result),
                        native_body_sha256=spec["body_sha256"],
                        patch_rva=spec["patch"], preimage=PREIMAGE.hex(), patch=patch.hex(),
                        guard_rva=rva, code_size=len(code), code_sha256=_sha(code), branches=branches,
                        unwind_rva=unwind, unwind_parent=list(parent),
                        old_exception_entries=len(entries) - 1, new_exception_entries=1,
                        original_sections_preserved_except_mapping=True,
                        imports_exports_relocations_unchanged=True, stack_adjustment=0,
                        changed_nonvolatile_registers=[], absent_needs_skipped=True,
                        maximum_need_count=18, zero_rates_follow_native_arithmetic=True,
                        actual_game_test_performed=False)


def derive_food06_ai(name: str, activity_bytes: bytes) -> tuple[bytes, dict]:
    """Build the separately pinned combined-profile input; unknown bytes refuse."""
    output, proof = _construct(name, activity_bytes)
    if _sha(output) != OUTPUT_SHA256[name]:
        raise RuntimeBuildError("Food 0.6 private AI differs from its reviewed output pin.")
    return output, proof
