"""Optional combined asset recipe with real transforms and synthetic originals."""
from contextlib import ExitStack
import hashlib
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from anno1503_overhaul import ambient_sound, bug_fixes, food_world_bug_fixes


def sha(value):
    return hashlib.sha256(value).hexdigest()


def wav():
    samples = struct.pack('<8h', -30000, -1000, -1, 0, 1, 1000, 16000, 30000)
    fmt = struct.pack('<HHIIHH', 1, 1, 22050, 44100, 2, 16)
    chunks = b'fmt ' + struct.pack('<I', len(fmt)) + fmt + b'data' + struct.pack('<I', len(samples)) + samples
    return b'RIFF' + struct.pack('<I', len(chunks) + 4) + b'WAVE' + chunks


class CombinedBugFixRecipeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='anno-combined-bugfix-recipe-')
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name).resolve()
        self.quest_path = bug_fixes.KING_OF_ORE_PATH
        self.scene_path = bug_fixes.KING_OF_ORE_SCENE_PATH
        self.sound_name = 'fixture.wav'
        self.sound_path = 'Languages/Nl/Samples/' + self.sound_name
        self.quest = b'<p>' + bug_fixes._ORE_OBJECTIVE_BEFORE + b'</p>\r\n<p>' + bug_fixes._ORE_OBJECTIVE_BEFORE + b'</p>'
        self.scene = b'Synthetic scenario preimage'
        self.sound = wav()
        for name, value in ((self.quest_path, self.quest), (self.scene_path, self.scene), (self.sound_path, self.sound)):
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(bug_fixes, 'KING_OF_ORE_SHA256', sha(self.quest)))
        stack.enter_context(patch.object(bug_fixes, 'KING_OF_ORE_SCENE_SHA256', sha(self.scene)))
        stack.enter_context(patch.object(ambient_sound, 'localized_sample_baselines',
            return_value={self.sound_name: (len(self.sound), hashlib.sha1(self.sound, usedforsecurity=False).hexdigest())}))

    def test_real_transforms_define_exact_file_scope_sizes_and_fingerprints(self):
        recipe = food_world_bug_fixes.recipe(self.source)
        self.assertEqual(recipe['version'], '1.2')
        expected = {self.quest_path: (self.quest, bug_fixes.fix_king_of_ore(self.quest)),
                    self.sound_path: (self.sound, ambient_sound.attenuate_wav(self.sound, 10, name=self.sound_path))}
        self.assertEqual({item['path'] for item in recipe['files']}, set(expected))
        for entry in recipe['files']:
            before, after = expected[entry['path']]
            self.assertEqual(entry, dict(path=entry['path'], before_size=len(before), before_sha256=sha(before),
                after_size=len(after), after_sha256=sha(after), offset=None))
            self.assertEqual((self.source / entry['path']).read_bytes(), before)
        self.assertEqual(recipe['quests'][0]['scene_sha256'], sha(self.scene))
        self.assertEqual(recipe['sounds'][0]['path'], self.sound_path)
        self.assertEqual({item.relative_to(self.source).as_posix() for item in self.source.rglob('*') if item.is_file()},
                         {self.quest_path, self.scene_path, self.sound_path})

    def test_unknown_source_assets_cannot_define_an_accepted_recipe(self):
        for name, original in ((self.quest_path, self.quest), (self.scene_path, self.scene), (self.sound_path, self.sound)):
            with self.subTest(name=name):
                path = self.source / name
                path.write_bytes(original + b'changed')
                with self.assertRaises(bug_fixes.BugFixError):
                    food_world_bug_fixes.recipe(self.source)
                path.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
