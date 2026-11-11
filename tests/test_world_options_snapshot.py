"""Independent binary-boundary checks for expanded preview diagnostics."""
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from anno1503_overhaul import world_options_snapshot as snapshot


def fixture(**changes):
    settings = dict(zip(snapshot.SETTINGS_FIELDS, [132, 1, 3, 2, 0, 0, 255, 3,
        30000, 0, 1, 1, 1, 1024, 4294967295, -1, -1, 0, 40, 40, 10, 0, 0, 1, 0, 1, 0, 0, 1, 0, 1, 1, 1]))
    settings.update(changes)
    data = bytearray(snapshot.SNAPSHOT_SIZE)
    struct.pack_into('<4I', data, 0, len(data), 1, settings['mapSeed'], 2)
    struct.pack_into('<I5i2I6iI18i', data, 16, *settings.values())
    for index, x in enumerate((0, 128)):
        struct.pack_into('<10I', data, snapshot.ROWS_OFFSET + index * 40, index, x, 0, 64, 64, index, 1, 0, 0, 2)
    return data


class OptionsSnapshotTests(unittest.TestCase):
    def test_uint32_seed_and_negative_auto_preferences_round_trip(self):
        value = snapshot.decode(fixture())
        self.assertEqual(value['seed'], 4294967295)
        self.assertEqual(value['settings']['startIsland'], -1)
        self.assertEqual(value['settings']['startClimate'], -1)
        self.assertEqual(value['islands'][1]['x'], 128)

    def test_zero_seed_is_a_reusable_value(self):
        self.assertEqual(snapshot.decode(fixture(mapSeed=0))['seed'], 0)

    def test_overlapping_islands_refused(self):
        data = fixture()
        struct.pack_into('<I', data, snapshot.ROWS_OFFSET + 40 + 4, 32)
        with self.assertRaisesRegex(ValueError, 'overlap'):
            snapshot.decode(data)

    def test_slot_rounding_refuses_cargo_below_total_tonnage_capacity(self):
        with self.assertRaisesRegex(ValueError, 'holds'):
            snapshot.decode(fixture(cargoMode=1, cargoTools=51, cargoWood=51, cargoFood=1))
        snapshot.decode(fixture(startingFleet=1, cargoMode=1, cargoTools=51, cargoWood=51, cargoFood=1))

    def test_invalid_selection_fields_and_seed_mismatch_refused(self):
        for key, value in [('startIsland', 2), ('startClimate', 6), ('disasters', 2),
                           ('layoutStyle', 3), ('climateBalance', 4), ('cargoFood', -1),
                           ('fairStarts', 2), ('startSeparation', -1), ('resourceDistribution', 3), ('guaranteeBasics', 2),
                           ('mapVisibility', -1), ('mapVisibility', 3), ('enemyVisibility', -1), ('enemyVisibility', 2),
                           ('pirateFrequency', -1), ('pirateFrequency', 3), ('pirateStrength', -1), ('pirateStrength', 3),
                           ('merchantFrequency', -1), ('merchantFrequency', 3)]:
            with self.subTest(field=key), self.assertRaises(ValueError):
                snapshot.decode(fixture(**{key: value}))
        data = fixture()
        struct.pack_into('<I', data, 8, 12)
        with self.assertRaises(ValueError):
            snapshot.decode(data)

    def test_exploration_and_enemy_visibility_are_independent(self):
        for geography in range(3):
            for activity in range(2):
                with self.subTest(geography=geography, activity=activity):
                    result = snapshot.decode(fixture(mapVisibility=geography, enemyVisibility=activity))
                    self.assertEqual(result['settings']['mapVisibility'], geography)
                    self.assertEqual(result['settings']['enemyVisibility'], activity)
        with self.assertRaises(ValueError):
            snapshot.decode(fixture(mapVisibility=0, startIsland=1))

    def test_absent_and_truncated_snapshots(self):
        data = bytearray(snapshot.SNAPSHOT_SIZE)
        struct.pack_into('<I', data, 0, len(data))
        self.assertEqual(snapshot.decode(data)['state_name'], 'absent')
        data[-1] = 1
        with self.assertRaises(ValueError):
            snapshot.decode(data)
        with self.assertRaises(ValueError):
            snapshot.decode(fixture()[:-1])

    def test_activity_choices_preserve_plan_and_work_with_disabled_factions(self):
        original = snapshot.decode(fixture())
        self.assertEqual(snapshot.SETTINGS_SIZE, 132)
        self.assertEqual(snapshot.ROWS_OFFSET, 148)
        self.assertEqual(snapshot.SNAPSHOT_SIZE, 5268)
        for frequency in range(3):
            for strength in range(3):
                for merchant in range(3):
                    with self.subTest(frequency=frequency, strength=strength, merchant=merchant):
                        result = snapshot.decode(fixture(factions=0, pirateFrequency=frequency,
                            pirateStrength=strength, merchantFrequency=merchant))
                        self.assertEqual(result['settings']['pirateFrequency'], frequency)
                        self.assertEqual(result['settings']['pirateStrength'], strength)
                        self.assertEqual(result['settings']['merchantFrequency'], merchant)
                        self.assertEqual(result['plan_sha256'], original['plan_sha256'])

    def test_legacy_binary_size_is_not_mistaken_for_migratable_text_preset(self):
        data = fixture(size=120)
        with self.assertRaises(ValueError):
            snapshot.decode(data)
        legacy = data[:136] + data[148:]
        struct.pack_into('<I', legacy, 0, len(legacy))
        with self.assertRaises(ValueError):
            snapshot.decode(legacy)


if __name__ == '__main__':
    unittest.main()
