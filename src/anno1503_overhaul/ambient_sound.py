"""Attenuate the selected sound effects using each language's stock WAVs."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import hashlib
from pathlib import Path
import struct

from .ambient_sound_baselines import localized_sample_baselines
from .bug_fixes import BugFixError
from .filesystem import safe_child


@dataclass(frozen=True)
class AmbientSoundEdit:
    path: str
    before: bytes
    after: bytes


# Taludas's v1.0 reference reduces most clips by 10 dB and these by 20 dB.
_QUIETER_EFFECTS = frozenset({
    'Axt Hit Holz.wav', 'Pferd wiehert1.wav', 'Pferd wiehert2.wav', 'Pferd wiehert3.wav',
})


def attenuate_wav(wav: bytes, decibels: int, *, name: str) -> bytes:
    """Preserve the RIFF layout and scale only signed 16-bit PCM samples."""
    if len(wav) < 12 or wav[:4] != b'RIFF' or wav[8:12] != b'WAVE':
        raise BugFixError('Invalid sound effect WAV: ' + name)
    end = struct.unpack_from('<I', wav, 4)[0] + 8
    if not 12 <= end <= len(wav):
        raise BugFixError('Truncated sound effect WAV: ' + name)
    block_size = 0
    samples = None
    offset = 12
    while offset + 8 <= end:
        tag, size = struct.unpack_from('<4sI', wav, offset)
        start = offset + 8
        offset = start + size + (size & 1)
        if offset > end:
            raise BugFixError('Truncated sound effect WAV chunk: ' + name)
        if tag == b'fmt ':
            if size < 16 or block_size:
                raise BugFixError('Invalid sound effect WAV format: ' + name)
            encoding, channels, rate, _, block_size, bits = struct.unpack_from('<HHIIHH', wav, start)
            if encoding != 1 or not channels or not rate or bits != 16 or block_size != channels * 2:
                raise BugFixError('Expected 16-bit PCM sound effect WAV: ' + name)
        if tag == b'data':
            if samples is not None or not block_size or not size or size % block_size:
                raise BugFixError('Invalid sound effect WAV samples: ' + name)
            samples = (start, start + size)
    if offset != end or samples is None:
        raise BugFixError('Sound effect WAV has incomplete chunks: ' + name)

    first, last = samples
    gain = 10 ** (-decibels / 20)
    scaled = [round(sample * gain) for (sample,) in struct.iter_unpack('<h', wav[first:last])]
    return wav[:first] + struct.pack(f'<{len(scaled)}h', *scaled) + wav[last:]


def ambient_sound_assets(root: Path, locales: Iterable[str]) -> tuple[AmbientSoundEdit, ...]:
    """Build reversible edits from the selected language packs' own files."""
    edits = []
    for locale in locales:
        for filename, (size, sha1) in sorted(localized_sample_baselines(locale).items()):
            name = f'Languages/{locale}/Samples/{filename}'
            path = safe_child(root, name)
            if not path.is_file():
                raise BugFixError('Missing stock sound effect WAV: ' + name)
            with path.open('rb') as stream:
                before = stream.read(size + 1)
            if len(before) != size or hashlib.sha1(before, usedforsecurity=False).hexdigest() != sha1:
                raise BugFixError('Sound effect differs from the stock Ubisoft installation: ' + name)
            decibels = 20 if filename in _QUIETER_EFFECTS else 10
            edits.append(AmbientSoundEdit(name, before, attenuate_wav(before, decibels, name=name)))
    return tuple(edits)
