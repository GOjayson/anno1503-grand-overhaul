"""Tests for the localized, lossless-layout PCM attenuation."""
from __future__ import annotations

from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from anno1503_overhaul.ambient_sound import attenuate_wav, _QUIETER_EFFECTS
from anno1503_overhaul.ambient_sound_baselines import localized_sample_baselines
from anno1503_overhaul.bug_fixes import BugFixError, KING_OF_ORE_LOCALES


def _chunk(tag: bytes, body: bytes) -> bytes:
    padding = b'\0' if len(body) % 2 else b''
    return struct.pack('<4sI', tag, len(body)) + body + padding


def _pcm_fixture(samples: tuple[int, ...], *, encoding: int = 1) -> bytes:
    fmt = struct.pack('<HHIIHH', encoding, 1, 22050, 44100, 2, 16)
    riff = (b'WAVE' + _chunk(b'fmt ', fmt) + _chunk(b'JUNK', b'abc')
            + _chunk(b'data', struct.pack(f'<{len(samples)}h', *samples))
            + _chunk(b'LIST', b'metadata'))
    return b'RIFF' + struct.pack('<I', len(riff)) + riff


class AmbientSoundTests(unittest.TestCase):
    def test_only_the_samples_change_at_both_reference_gains(self):
        original = _pcm_fixture((-10000, -1, 0, 1, 10000))
        for gain, peak in ((10, 3162), (20, 1000)):
            with self.subTest(gain=gain):
                expected = _pcm_fixture((-peak, 0, 0, 0, peak))
                self.assertEqual(attenuate_wav(original, gain, name='sample'), expected)

    def test_refuses_truncated_and_non_pcm_wavs(self):
        for invalid in (_pcm_fixture((100,))[:-1], _pcm_fixture((100,), encoding=3), b''):
            with self.subTest(data=invalid):
                with self.assertRaises(BugFixError):
                    attenuate_wav(invalid, 10, name='sample')

    def test_every_locale_has_the_same_targets_and_its_own_voices(self):
        plans = [localized_sample_baselines(locale) for locale in KING_OF_ORE_LOCALES]
        expected = plans[0].keys()
        self.assertEqual(len(expected), 118)
        self.assertTrue(_QUIETER_EFFECTS <= expected)
        for plan in plans:
            self.assertEqual(plan.keys(), expected)
        for name in _QUIETER_EFFECTS:
            self.assertEqual(len({plan[name] for plan in plans}), 1)
        self.assertEqual(len({plan['m1.wav'] for plan in plans}), len(KING_OF_ORE_LOCALES))
