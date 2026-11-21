"""Bound the native city supply-warning table before indexing it by ware ID."""
from __future__ import annotations

import hashlib
import struct

from .world_native import checksum
from .world_runtime_build import PE


FOOD06_GUARDED_WELT_SHA256 = "48afb7d4ef40b88afdbe111da342810ff78193b6fb5763d6ae8993f555c8c805"

_FUNCTION_RVA = 0xAE4F0
_FUNCTION_SIZE = 0x2FD
_FUNCTION_SHA256 = "bb7f4ebc9e95fd5d1e18cf3d371a655cb1c6a70c6110e749b98d5f4dac49e566"
_LOOP_RVA = 0xAE587
_ADVANCE_RVA = 0xAE7AF
_BACK_EDGE_RVA = 0xAE7C6
_LOOP_BEFORE = bytes.fromhex(
    "418d45148d48146690410fb62841be4600000083fd1abe55000000440f45f00f45f1"
    "486bcd1ac784afa408000000000000"
)
_BACK_EDGE_BEFORE = bytes.fromhex("0f8cc4fdffff")


def edited_spans() -> tuple[tuple[int, int], ...]:
    """The exact native ranges to check for overlap with the World runtime."""
    return ((_LOOP_RVA, len(_LOOP_BEFORE)), (_BACK_EDGE_RVA, len(_BACK_EDGE_BEFORE)))


def _branch(opcode: bytes, start: int, target: int) -> bytes:
    return opcode + struct.pack("<i", target - start - len(opcode) - 4)


def _bounded_loop() -> bytes:
    # Fifteen rows begin at city+0x7A2. Index 24 aliases the milestone.
    load_and_compare = bytes.fromhex(
        "410fb628"  # movzx ebp, byte ptr [r8]
        "8d55e6"    # lea edx, [rbp-26]
        "83fa0e"    # cmp edx, 14
    )
    skip = _branch(b"\x0f\x87", _LOOP_RVA + len(load_and_compare), _ADVANCE_RVA)
    original_calculation = bytes.fromhex(
        "85d2"            # test edx, edx
        "41be14000000"    # mov r14d, 20
        "be28000000"      # mov esi, 40
        "7506"            # jne normal need
        "41b646"          # mov r14b, 70 (fish)
        "40b655"          # mov sil, 85 (fish)
        "6bcd1a"          # imul ecx, ebp, 26
        "31d2"            # xor edx, edx
        "8994afa4080000"  # mov dword ptr [rdi+rbp*4+0x8A4], edx
    )
    return load_and_compare + skip + original_calculation


def bound_supply_statistics(image: bytes) -> bytes:
    """Patch the reviewed AMD64 city loop in place, without adding native code ranges."""
    pe = PE(image)
    before = pe.read(_FUNCTION_RVA, _FUNCTION_SIZE)
    if hashlib.sha256(before).hexdigest() != _FUNCTION_SHA256:
        raise ValueError("The native city supply statistics function differs from the reviewed build.")
    edits = (
        (_LOOP_RVA, _LOOP_BEFORE, _bounded_loop()),
        (_BACK_EDGE_RVA, _BACK_EDGE_BEFORE, _branch(b"\x0f\x8c", _BACK_EDGE_RVA, _LOOP_RVA)),
    )
    output = bytearray(image)
    for rva, original, replacement in edits:
        if len(original) != len(replacement) or pe.read(rva, len(original)) != original:
            raise ValueError("The native city supply statistics patch does not match its preimage.")
        offset = pe.offset(rva, len(original))
        output[offset:offset + len(original)] = replacement
    struct.pack_into("<I", output, pe.optional + 64, checksum(bytes(output)))
    return bytes(output)
