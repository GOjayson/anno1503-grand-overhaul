from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from anno1503_overhaul import food_world_public_ai as public
from anno1503_overhaul.packages import PackageError


class PublicFoodAI(unittest.TestCase):
    def test_unknown_mutable_and_changed_stock_images_refuse_before_generator_read(self):
        with mock.patch.object(public, '_source', side_effect=AssertionError('must not read recipes')):
            for name, value in [('other.dll', b'MZ'), ('CompLogic.dll', bytearray(b'MZ')),
                                ('CompLogicClassic.dll', b'MZ changed')]:
                with self.subTest(name=name, value=type(value).__name__), self.assertRaises(PackageError):
                    public.derive_food05_ai(name, value)

    def test_each_imported_construction_source_is_independently_hash_checked(self):
        for name in public.SOURCES:
            text = public._source(name)
            self.assertTrue(text)
            with mock.patch.object(public.common, '_read', return_value=text.encode() + b'\n# changed'):
                with self.subTest(name=name), self.assertRaises(PackageError):
                    public._source(name)

    def test_unknown_recipe_and_ambiguous_or_reversed_boundaries_refuse(self):
        with self.assertRaises(PackageError):
            public._source('external.py')
        for text in [' begin\n begin\n end', ' end\n begin', ' nothing']:
            with self.subTest(text=text), self.assertRaises(PackageError):
                public._segment(text, ' begin', ' end', {}, 'fixture')

    def test_only_selected_helper_definitions_execute_not_imports_or_driver(self):
        scope = {}
        public._definitions("raise RuntimeError('driver')\nimport unavailable\ndef kept(): return 17\n",
                            {'kept'}, scope, 'fixture')
        self.assertEqual(scope['kept'](), 17)
        with self.assertRaises(PackageError):
            public._definitions('def missing(): pass', {'kept'}, {}, 'fixture')

    def test_construction_segment_refuses_imports_and_file_process_or_emulator_drivers(self):
        for expression in ['import os', "open('target', 'w')", 'HERE', 'ROOT', 'WORK', 'Module', 'Uc', 'sys', 'Path']:
            text = ' begin = 1\n ' + expression + '\n end = 2'
            with self.subTest(expression=expression), self.assertRaises(PackageError):
                public._segment(text, ' begin', ' end', {}, 'fixture')

    def test_excluded_output_driver_is_not_executed_and_assertions_remain_active(self):
        scope = {}
        public._segment(" value = bytes([7])\n output=forbidden\n", ' value', ' output=', scope, 'fixture')
        self.assertEqual(scope['value'], b'\x07')
        with self.assertRaises(AssertionError):
            public._segment(' value = 1\n assert False\n output=forbidden\n', ' value', ' output=', {}, 'fixture')

    def test_preimage_assertions_survive_optimized_frozen_style_interpreter(self):
        script = (
            'import sys;sys.path.insert(0,sys.argv[1]);'
            'from anno1503_overhaul.food_world_public_ai import _segment\n'
            'try: _segment(" value=1\\n assert False\\n output=x\\n"," value"," output=",{},"fixture")\n'
            'except AssertionError: raise SystemExit(0)\n'
            'raise SystemExit(2)\n'
        )
        result = subprocess.run([sys.executable, '-B', '-O', '-c', script,
                                 str(Path(__file__).resolve().parents[1] / 'src')],
                                capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))


if __name__ == '__main__':
    unittest.main()
