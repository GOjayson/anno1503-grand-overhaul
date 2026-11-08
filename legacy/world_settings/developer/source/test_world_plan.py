"""Geometry/culture tests using actual catalogue; no native gameplay claim."""
from dataclasses import replace
from pathlib import Path
import unittest

from world_plan import (CULTURES, Settings, PlanError, IntegrationUnverified,
                        plan_layout, load_catalogue, verify_template,
                        require_playable_world, size_class, geometry_errors)


class LayoutChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogue = load_catalogue()

    def test_actual_catalogue_hashes(self):
        root = Path(__file__).resolve().parent.parent
        for template in self.catalogue['templates']:
            verify_template(root, template)

    def test_seeds_count_spacing_and_all_cultures(self):
        settings = Settings(island_size='medium', island_count=24, spacing=16)
        for seed in range(50):
            p = plan_layout(settings, self.catalogue, seed)
            self.assertEqual(len(p['islands']), 24)
            self.assertFalse(geometry_errors(p['islands'], 1024, 1024, 16))
            self.assertEqual({c for i in p['islands'] for c in i['cultures']}, set(CULTURES))

    def test_difficulty_does_not_change_layout(self):
        base = Settings(island_size='medium', island_count=20)
        p = plan_layout(base, self.catalogue, 71)
        for difficulty in ('easy', 'hard'):
            other = plan_layout(replace(base, difficulty=difficulty), self.catalogue, 71)
            self.assertEqual(p['islands'], other['islands'])
            self.assertEqual(other['difficulty'], difficulty)

    def test_each_culture_can_be_disabled_individually(self):
        for culture in CULTURES:
            settings = Settings(island_size='medium', island_count=16,
                                cultures=frozenset(CULTURES) - {culture})
            p = plan_layout(settings, self.catalogue, 21)
            represented = {c for i in p['islands'] for c in i['cultures']}
            self.assertEqual(represented, settings.cultures)

    def test_sizes_and_no_cultures(self):
        for size, count in [('small', 30), ('medium', 24), ('large', 8), ('mixed', 14)]:
            p = plan_layout(Settings(island_size=size, island_count=count,
                                    cultures=frozenset()), self.catalogue, 9)
            self.assertFalse(any(i['cultures'] for i in p['islands']))
            if size != 'mixed':
                self.assertTrue(all(size_class(i) == size for i in p['islands']))

    def test_impossible_large_native_combination_rejected(self):
        # Inspected Inuit and Native American assets have no 256x256 template.
        with self.assertRaisesRegex(PlanError, 'No large template'):
            plan_layout(Settings(island_size='large'), self.catalogue)

    def test_impossible_spacing_rejected(self):
        with self.assertRaises(PlanError):
            plan_layout(Settings(island_size='large', island_count=24,
                                 spacing=256, cultures=frozenset()), self.catalogue)

    def test_intersection_and_exact_gap_boundary(self):
        a = dict(id=0, x=0, y=0, width=128, height=128)
        for x, errors in [(127, True), (128, True), (143, True), (144, False)]:
            b = dict(id=1, x=x, y=0, width=128, height=128)
            self.assertEqual(bool(geometry_errors([a, b], 1024, 1024, 16)), errors)

    def test_no_silent_ai_clamping(self):
        for value in [-1, 1, 3, 7, 8, True]:
            with self.assertRaises(PlanError):
                plan_layout(Settings(ai_count=value), self.catalogue)

    def test_no_silent_count_clamping_or_zero_dimensions(self):
        for value in [0, -1, 129, True, 2.5]:
            with self.assertRaises(PlanError):
                plan_layout(Settings(island_count=value), self.catalogue)
        for dimensions in [(0, 1024), (800, 800), (2048, 2048)]:
            with self.assertRaises(PlanError):
                plan_layout(Settings(), self.catalogue, width=dimensions[0], height=dimensions[1])

    def test_layout_cannot_claim_resources_or_start_game(self):
        p = plan_layout(Settings(island_size='medium'), self.catalogue)
        self.assertFalse(p['resources_validated'])
        self.assertFalse(p['playable'])
        # Even a caller forging flags cannot bypass the missing integration.
        p.update(resources_validated=True, playable=True)
        with self.assertRaises(IntegrationUnverified):
            require_playable_world(p)


if __name__ == '__main__':
    unittest.main(verbosity=2)
