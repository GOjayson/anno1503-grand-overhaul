"""Derive independent frequency-only native AI modules for multiplayer."""
from __future__ import annotations

from hashlib import sha256
from struct import error as StructError
from struct import pack, pack_into, unpack_from

from .world_native import _STOCK_AI_SHA256, _align, _offset, _pe, checksum
from .world_options_factions import (
    MERCHANT_TAG, PIRATE_TAG, SPEC, _Code, _merchant_code, _parent, _setter_code, _threshold_code,
)
from .world_runtime_build import RuntimeBuildError


MULTIPLAYER_FREQUENCY_AI_SHA256 = {
    "CompLogic.dll": "05d79b5896de866342e1e27906ad303d71d2c48cc1216ce9015f8c620ee6d4fa",
    "CompLogicClassic.dll": "56a5d7c3ae33b63e017ec59883f93ff85c373618153220d6f42f2da42a706734",
}
_NATIVE_STORE = bytes.fromhex("8986b80a0000")


def _frequency_setter(rva, family) -> bytes:
    # Reuse the special-faction preservation path. The stock ordinary setter
    # has no profile handling, so send its fallback straight to the native store.
    code = _setter_code(rva, family, original_target=rva)
    if (code.count(_NATIVE_STORE) != 1 or code[-10:-7] != bytes.fromhex("4c8d1d")
            or code[-3:] != bytes.fromhex("41ffe3")):
        raise RuntimeBuildError("The reviewed faction flag preservation template has changed.")
    ordinary = _Code(rva + len(code) - 10)
    ordinary.jump("e9", rva + code.index(_NATIVE_STORE))
    return code[:-10] + ordinary.finish()


def derive_multiplayer_faction_ai(name: str, original: bytes) -> tuple[bytes, dict]:
    """Build the reviewed local derivative from one exact stock multiplayer DLL."""
    expected = _STOCK_AI_SHA256.get(name)
    if expected is None or not isinstance(original, bytes) or sha256(original).hexdigest() != expected:
        raise RuntimeBuildError("Multiplayer faction AI input is not its exact reviewed stock module.")
    spec = SPEC[name]
    try:
        info = _pe(original)
        optional_header = info["opt"]
        section_align, file_align = unpack_from("<II", original, optional_header + 32)
        section_rva = _align(max(s["rva"] + max(s["virtual_size"], s["size"]) for s in info["sections"]), section_align)
        raw_start = _align(len(original), file_align)
        exception_dir = optional_header + 112 + 3 * 8
        pdata_rva, pdata_size = unpack_from("<II", original, exception_dir)
        if not pdata_size or pdata_size % 12 or pdata_size > 4 * 1024 * 1024:
            raise RuntimeBuildError("Multiplayer faction AI exception directory is unbounded.")
        pdata_offset = _offset(info, pdata_rva, pdata_size)
        entries = [unpack_from("<III", original, pdata_offset + row) for row in range(0, pdata_size, 12)]
        if any(first[1] > second[0] for first, second in zip(entries, entries[1:])):
            raise RuntimeBuildError("Multiplayer faction AI stock exception functions overlap.")

        result, section, functions, edits = bytearray(original), bytearray(), [], []
        sites = (
            ("pirate_interval", spec["threshold"], bytes.fromhex("4169c030750000"), _threshold_code),
            ("merchant_native_fleet_target", spec["merchant"], bytes.fromhex("4439b6880c0000"), _merchant_code),
            ("special_native_flag_preserver", spec["setter"], _NATIVE_STORE, _frequency_setter),
        )
        spawn = b"\xe8" + pack("<i", spec["create"] - spec["spawn"] - 5)
        spawn_offset = _offset(info, spec["spawn"], len(spawn))
        if original[spawn_offset:spawn_offset + len(spawn)] != spawn:
            raise RuntimeBuildError("Multiplayer faction AI native spawn preimage differs.")
        for label, hook, preimage, emit in sites:
            offset = _offset(info, hook, len(preimage))
            if original[offset:offset + len(preimage)] != preimage:
                raise RuntimeBuildError("Multiplayer faction AI instruction preimage differs.")
            section.extend(b"\xcc" * (_align(len(section), 16) - len(section)))
            start = section_rva + len(section)
            code = emit(start, spec)
            section.extend(code)
            patch = b"\xe9" + pack("<i", start - hook - 5) + b"\x90" * (len(preimage) - 5)
            result[offset:offset + len(patch)] = patch
            functions.append(dict(name=label, start=start, end=start + len(code),
                                  parent=_parent(original, info, entries, hook),
                                  code_sha256=sha256(code).hexdigest(), stack_adjustment=0))
            edits.append(dict(rva=hook, preimage=preimage.hex(), patch=patch.hex()))

        new_entries = list(entries)
        for row in functions:
            section.extend(bytes(_align(len(section), 4) - len(section)))
            unwind_rva = section_rva + len(section)
            unwind = bytes.fromhex("21000000") + pack("<III", *row["parent"])
            section.extend(unwind)
            new_entries.append((row["start"], row["end"], unwind_rva))
            row.update(unwind=unwind_rva, unwind_bytes=unwind.hex())
        new_entries.sort()
        if any(first[1] > second[0] for first, second in zip(new_entries, new_entries[1:])):
            raise RuntimeBuildError("Multiplayer faction AI derivative exception functions overlap.")
        section.extend(bytes(_align(len(section), 4) - len(section)))
        new_pdata = section_rva + len(section)
        section.extend(b"".join(pack("<III", *entry) for entry in new_entries))

        header = info["table"] + 40 * len(info["sections"])
        if header + 40 > info["header_size"] or result[header:header + 40] != bytes(40):
            raise RuntimeBuildError("Multiplayer faction AI has no unused section header.")
        size = _align(len(section), file_align)
        result[header:header + 40] = pack("<8sIIIIIIHHI", b".wsfacts", len(section), section_rva, size,
                                         raw_start, 0, 0, 0, 0, 0x60000020)
        pack_into("<H", result, info["pe"] + 6, len(info["sections"]) + 1)
        pack_into("<I", result, optional_header + 4, unpack_from("<I", original, optional_header + 4)[0] + size)
        pack_into("<I", result, optional_header + 56, _align(section_rva + len(section), section_align))
        pack_into("<II", result, exception_dir, new_pdata, len(new_entries) * 12)
        result.extend(bytes(raw_start - len(original)) + section + bytes(size - len(section)))
        pack_into("<I", result, optional_header + 64, checksum(bytes(result)))
        output = bytes(result)
        _pe(output)
    except (ValueError, KeyError, IndexError, StructError) as exc:
        raise RuntimeBuildError("Multiplayer faction AI derivative failed its bounded PE proof.") from exc
    digest = sha256(output).hexdigest()
    if digest != MULTIPLAYER_FREQUENCY_AI_SHA256[name]:
        raise RuntimeBuildError("The derived multiplayer faction AI differs from its reviewed result.")
    return output, dict(profile="multiplayer-stock", module=name, input_sha256=expected, output_sha256=digest,
                        section=".wsfacts", section_rva=section_rva, section_raw=raw_start,
                        edits=edits, functions=functions, old_exception_entries=len(entries),
                        exception_entries=len(new_entries), native_low_flags_mask=255,
                        pirate_tag=PIRATE_TAG, merchant_tag=MERCHANT_TAG)
