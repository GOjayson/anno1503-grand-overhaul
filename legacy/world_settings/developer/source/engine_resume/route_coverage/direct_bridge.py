"""Additional AMD64 gate for new single-player scenes with a fixed flag.

This is a private candidate. It neither patches disk nor installs a hook.
The runtime export must classify the stock single-endless selection before
opening World Settings. The native flag-selection bridge remains unchanged.
"""
from pathlib import Path
import hashlib
import os
import struct
import sys

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]
sys.path.insert(0, str(WORK / 'engine_audit'))
from audit import Module
from bridge_codegen import PROLOG,EPILOG,COMMON_UNWIND

EXPECTED_FRAME_SHA = '046b5ad6f351dfe867ed38ce29fb50a594485b43a32ee90adadc48e850466baf'
DIRECT_RVA = 0x43e44
DIRECT_BEFORE = bytes.fromhex('ff9078010000')
DIRECT_CONTINUE = 0x43e4a
DIRECT_CANCEL = 0x43d3c


def build_direct_bridge(rva, dll_path='AnnoWorldSettings.dll', export='WorldSettingsBeforeDirectStart'):
    # Source snapshots may live below developer/source rather than directly
    # below the game. An explicit source never falls back to another file;
    # the original exact History Edition hash and unwind preimages still gate it.
    source_game = Path(os.environ.get('ANNO1503_SOURCE_GAME', WORK.parent)).resolve(strict=True)
    frame = Module(str(source_game / 'AnnoFrame.dll'))
    if hashlib.sha256(frame.data).hexdigest() != EXPECTED_FRAME_SHA:
        raise ValueError('Unrecognized AMD64 Frame source')
    if frame.image[DIRECT_RVA:DIRECT_RVA + len(DIRECT_BEFORE)] != DIRECT_BEFORE:
        raise ValueError('Direct-start preimage differs')
    parent = next(e.struct for e in frame.pe.DIRECTORY_ENTRY_EXCEPTION
                  if e.struct.BeginAddress <= DIRECT_RVA < e.struct.EndAddress)
    parent_tuple = (parent.BeginAddress, parent.EndAddress, parent.UnwindData)
    if parent_tuple != (0x43dd0, 0x43ea4, 0xbaa30):
        raise ValueError('Direct-start native unwind parent differs')
    code = bytearray(); names = {}; fixups = []
    def mark(name): names[name] = rva + len(code)
    def emit(value): code.extend(bytes.fromhex(value) if isinstance(value, str) else value)
    def relative(prefix, target):
        emit(prefix); at = len(code); emit(bytes(4)); fixups.append((at, target))

    mark('direct_start'); emit(PROLOG)
    mark('prolog_end')
    # The original CALL supplies a real return address. Preserve its exact four
    # arguments and original virtual target before any loader/UI calls.
    emit('4989cc4989d54d89c64d89cf488b9878010000')
    relative('488d0d', 'dll_path'); relative('ff15', 0x9e408)
    emit('4885c0'); relative('0f84', 'cancel')
    emit('488bc8'); relative('488d15', 'export_name'); relative('ff15', 0x9e410)
    emit('4885c0'); relative('0f84', 'cancel')
    emit('4c89e1'); relative('488d15', 0); emit('ffd0')  # page, Frame base
    emit('83f801'); relative('0f84', 'proceed')  # nonendless, unchanged
    emit('83f802'); relative('0f85', 'cancel')  # only accepted endless is 2
    emit('498b8424b02100004885c0'); relative('0f84', 'cancel')
    emit('488b084885c9'); relative('0f84', 'cancel')
    relative('e8', 0x476e0)  # native setup commit only after accepted staging
    mark('proceed')
    emit('4c89e14c89ea4d89f04d89f9ffd3')
    emit(EPILOG)
    mark('proceed_end')
    mark('cancel')
    relative('488d05',DIRECT_CANCEL);emit('48898424b800000033c0')
    emit(EPILOG)
    mark('direct_start_end')
    while len(code) % 8: emit('cc')
    mark('dll_path'); emit(dll_path.encode('ascii') + b'\0')
    mark('export_name'); emit(export.encode('ascii') + b'\0')
    for at, target in fixups:
        destination = names[target] if isinstance(target, str) else target
        struct.pack_into('<i', code, at, destination - (rva + at + 4))
    hook = (DIRECT_RVA, DIRECT_BEFORE,
            b'\xe8' + struct.pack('<i', rva - DIRECT_RVA - 5)
            + b'\x90' * (len(DIRECT_BEFORE) - 5))
    return bytes(code), names, [hook], [(names['direct_start'], names['direct_start_end'], COMMON_UNWIND)]
