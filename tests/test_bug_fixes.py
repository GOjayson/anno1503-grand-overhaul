"""Verify the asset transforms with synthetic markup and samples."""
from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from anno1503_overhaul import bug_fixes


class KingOfOreTests(unittest.TestCase):
    def test_both_objective_rows_are_corrected_and_other_bytes_are_kept(self):
        before = bug_fixes._ORE_OBJECTIVE_BEFORE
        after = (
            b'Zorg dat je binnen de tijdslimiet in elk van je zes startsteden\r\n'
            b'  minstens 170 ton ijzererts op voorraad hebt.'
        )
        head = b'<html>\r\n<a name="single14_300170"></a><p>'
        middle = b'</p>\r\n<a name="single14_300171"></a><p>***HIDE***</p><p>'
        tail = b'</p>\r\n<p>Stad met caf\xe9</p>\r\n</html>\r\n'
        original = head + before + middle + before + tail
        with patch.object(bug_fixes, 'KING_OF_ORE_SHA256', hashlib.sha256(original).hexdigest()):
            self.assertEqual(bug_fixes.fix_king_of_ore(original), head + after + middle + after + tail)
            with self.assertRaises(bug_fixes.BugFixError):
                bug_fixes.fix_king_of_ore(original + b' ')

    def test_correct_fingerprint_without_two_objective_rows_is_refused(self):
        original = bug_fixes._ORE_OBJECTIVE_BEFORE
        with patch.object(bug_fixes, 'KING_OF_ORE_SHA256', hashlib.sha256(original).hexdigest()):
            with self.assertRaises(bug_fixes.BugFixError):
                bug_fixes.fix_king_of_ore(original)


class LocalizedKingOfOreTests(unittest.TestCase):
    fixture_objectives = {
        'Eng': 'Mine 170 tons of ore in each city.',
        'Fra': 'Extrayez 170 tonnes de fer dans chaque ville.',
        'Ger': 'Fördere 170 Tonnen Erz in jeder Stadt.',
        'Ita': 'Estrai 170 tonnellate di ferro in ogni città.',
        'Spa': 'Extrae 170 toneladas de mena en cada ciudad.',
    }
    kernel = b'IF OBJECT "O_CITY1" WARECOUNT "EISENERZ" > 169 THEN { WON("HUMAN"); }'
    scene = (
        b'ANNO\0\0\0\0\0\0\0\0'
        b'QUEST\0\x14\0\x12Singleplayer14.htm\0'
        b'[SCRIPT_KERNEL]\n$ Fixture comment\r\r\n'
        + kernel.replace(b' THEN ', b' THEN\r\r\n')
        + b'\n[SIGNALS]\n'
    )

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.baselines = dict(bug_fixes._KING_OF_ORE_BASELINES)
        for patcher in (
            patch.object(bug_fixes, '_KING_OF_ORE_BASELINES', self.baselines),
            patch.object(bug_fixes, '_ORE_KERNEL_SHA256', hashlib.sha256(self.kernel).hexdigest()),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def write_fixture(self, locale, quest, scene=None):
        scene = self.scene if scene is None else scene
        directory = self.root / 'Languages' / locale / 'Scenes' / '0200Single'
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'Single_14.sze').write_bytes(scene)
        (directory / 'Singleplayer14.htm').write_bytes(quest)
        self.baselines[locale] = replace(
            self.baselines[locale],
            quest_size=len(quest), quest_sha1=hashlib.sha1(quest, usedforsecurity=False).hexdigest(),
            scene_size=len(scene), scene_sha1=hashlib.sha1(scene, usedforsecurity=False).hexdigest(),
        )

    def fixture_quest(self, locale, *, encoding='cp1252'):
        original = self.fixture_objectives[locale].encode(encoding)
        return (
            b'<html><meta charset="' + encoding.encode() + b'"><table>\r\n'
            b'<tr><td><p><a name="single14_300170">#300170*</a></p></td>\r\n'
            b'<td><p><![if !vml]><img src="image001.gif"><![endif]>' + original
            + b'</p></td></tr>\r\n'
            b'<tr><td><p><a name="SINGLE14_300171">#300171*</a></p>'
            b'<p>***HIDE***</p></td><td><p><span>' + original
            + b'</span></p></td></tr>\r\n'
            b'<tr><td>Non-objective text</td><td><p>' + original
            + b'</p></td></tr>\r\n</table></html>\r\n'
        )

    def test_all_installed_locales_are_patched_in_order_and_only_two_spans_change(self):
        for locale in reversed(tuple(self.fixture_objectives)):
            self.write_fixture(locale, self.fixture_quest(locale))
        assets = bug_fixes.king_of_ore_assets(self.root)
        self.assertEqual(tuple(asset.locale for asset in assets), ('Eng', 'Fra', 'Ger', 'Ita', 'Spa'))
        for asset in assets:
            with self.subTest(locale=asset.locale):
                objective = self.fixture_objectives[asset.locale].encode('cp1252')
                replacement = self.baselines[asset.locale].objective.encode('cp1252')
                self.assertEqual(asset.after, asset.before.replace(objective, replacement, 2))
                self.assertEqual(asset.before, (self.root / asset.quest_path).read_bytes())
                self.assertEqual(asset.scene_sha256, hashlib.sha256(self.scene).hexdigest())

    def test_exact_locale_selection_ignores_unrelated_partial_locale(self):
        self.write_fixture('Ger', self.fixture_quest('Ger', encoding='utf-8'))
        self.write_fixture('Eng', self.fixture_quest('Eng'))
        (self.root / 'Languages/Eng/Scenes/0200Single/Single_14.sze').unlink()
        asset, = bug_fixes.king_of_ore_assets(self.root, locales=('Ger',))
        self.assertIn('Startstädte'.encode(), asset.after)
        with self.assertRaisesRegex(bug_fixes.BugFixError, 'required for Eng'):
            bug_fixes.king_of_ore_assets(self.root)

    def test_translated_line_wrap_preserves_existing_crlf_and_indent(self):
        quest = self.fixture_quest('Fra').replace(b'dans chaque ville.', b'\r\n  dans chaque ville.', 2)
        self.write_fixture('Fra', quest)
        asset, = bug_fixes.king_of_ore_assets(self.root)
        self.assertEqual(asset.after.count(b'\r\n'), asset.before.count(b'\r\n'))
        self.assertEqual(asset.after.count(b'\r\n  '), 2)

    def test_refuses_modified_quest_and_even_a_pinned_wrong_scene_rule(self):
        quest = self.fixture_quest('Eng')
        self.write_fixture('Eng', quest)
        (self.root / 'Languages/Eng/Scenes/0200Single/Singleplayer14.htm').write_bytes(
            quest.replace(b'Mine', b'Sell', 1),
        )
        with self.assertRaisesRegex(bug_fixes.BugFixError, 'reviewed Ubisoft installation'):
            bug_fixes.king_of_ore_assets(self.root)
        self.write_fixture('Eng', quest, scene=self.scene.replace(b'169', b'170'))
        with self.assertRaisesRegex(bug_fixes.BugFixError, 'reviewed stockpile rule'):
            bug_fixes.king_of_ore_assets(self.root)

    def test_refuses_even_a_pinned_quest_missing_one_objective(self):
        quest = self.fixture_quest('Eng').replace(b'SINGLE14_300171', b'SINGLE14_300172')
        self.write_fixture('Eng', quest)
        with self.assertRaisesRegex(bug_fixes.BugFixError, 'both King of Ore objectives'):
            bug_fixes.king_of_ore_assets(self.root)


class LivestockSampleTests(unittest.TestCase):
    def test_gain_preserves_sample_layout_and_header(self):
        sample = bug_fixes.LIVESTOCK_SAMPLE_PATHS[0]
        header = b'H' * 4096
        original = header + struct.pack('<5h', -32768, -1000, 0, 1000, 32767)
        digest = hashlib.sha256(original).hexdigest()
        with patch.dict(bug_fixes._LIVESTOCK_SAMPLE_SHA256, {sample: digest}, clear=True):
            result = bug_fixes.quieter_livestock_sample(sample, original)
            self.assertEqual(result[:4096], header)
            self.assertEqual(struct.unpack('<5h', result[4096:]), (-10362, -316, 0, 316, 10362))
            with self.assertRaises(bug_fixes.BugFixError):
                bug_fixes.quieter_livestock_sample(sample, result)
            with self.assertRaises(bug_fixes.BugFixError):
                bug_fixes.quieter_livestock_sample(sample.replace('/Nl/', '/Eng/'), original)
