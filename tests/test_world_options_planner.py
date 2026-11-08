"""Planner source guards and isolated native policies; never opens Anno."""
from collections import Counter
import ctypes as C
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from anno1503_overhaul.world_options import PRIVATE, apply_common
from anno1503_overhaul.world_options_planner import apply_planner


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'legacy/world_settings'
NAMES = ('world_backend.h', 'world_backend.c', 'WorldSettings.c', 'preview_state.inc',
         'selection_policy.inc', 'balanced_layout.inc', 'world_catalogue.h',
         'world_factions.h', 'world_ship_reserves.h')


def staged_sources():
    return {PRIVATE + name: (SOURCE / PRIVATE / name).read_bytes() for name in NAMES}


class SourceGuardTests(unittest.TestCase):
    def test_transforms_do_not_change_imported_bytes(self):
        files = staged_sources()
        before = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
        apply_common(files)
        apply_planner(files)
        self.assertIn(PRIVATE + 'advanced_climate.inc', files)
        self.assertIn(PRIVATE + 'advanced_layout.inc', files)
        for name, digest in before.items():
            self.assertEqual(hashlib.sha256((SOURCE / name).read_bytes()).hexdigest(), digest)

    def test_altered_filler_or_layout_anchor_is_rejected(self):
        for name, before, after in (
            ('selection_policy.inc', b'wsChooseBalancedFill(', b'otherFiller('),
            ('balanced_layout.inc', b'static int wsPack(', b'static int otherPack('),
            ('world_backend.c', b'wsPack(n,', b'otherPack(n,'),
        ):
            files = staged_sources()
            apply_common(files)
            files[PRIVATE + name] = files[PRIVATE + name].replace(before, after, 1)
            with self.subTest(name=name), self.assertRaises((ValueError, RuntimeError)):
                apply_planner(files)

    def test_original_inputs_are_not_accepted_twice(self):
        files = staged_sources()
        apply_common(files)
        apply_planner(files)
        with self.assertRaises((ValueError, RuntimeError)):
            apply_planner(files)


class Settings(C.Structure):
    _fields_ = [(name, C.c_uint32 if name in {'size', 'cultures', 'factions', 'mapSeed'} else C.c_int32)
                for name in ('size', 'difficulty', 'islandSize', 'islandCount', 'spacing',
                             'aiCount', 'cultures', 'factions', 'startingMoney',
                             'startingFleet', 'aiDifficulty', 'plantFertility',
                             'mineralFertility', 'worldSize', 'mapSeed', 'startClimate',
                             'startIsland', 'cargoMode', 'cargoTools', 'cargoWood',
                             'cargoFood', 'climateBalance', 'layoutStyle', 'disasters')]


class Island(C.Structure):
    _fields_ = [(name, C.c_uint32) for name in ('id', 'x', 'y', 'width', 'height',
                  'templateIndex', 'cropMask', 'mineralMask', 'cultures', 'climate')]


def settings(**overrides):
    result = Settings(size=C.sizeof(Settings), difficulty=1, islandSize=3,
                      islandCount=24, spacing=16, aiCount=0, cultures=255,
                      factions=3, startingMoney=30000, startingFleet=0,
                      aiDifficulty=1, plantFertility=1, mineralFertility=1,
                      worldSize=1024, mapSeed=3719, startClimate=-1,
                      startIsland=-1, cargoTools=40, cargoWood=40, cargoFood=10,
                      disasters=1)
    for key, value in overrides.items():
        setattr(result, key, value)
    return result


def separated(a, b, gap=0):
    return (a.x + a.width + gap <= b.x or b.x + b.width + gap <= a.x or
            a.y + a.height + gap <= b.y or b.y + b.height + gap <= a.y)


class NativePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='anno-world-options-planner-')
        folder = Path(cls.temp.name)
        if os.name == 'nt':
            zig = ROOT / '.local/toolchain/ziglang/zig.exe'
            if not zig.is_file():
                cls.temp.cleanup()
                raise unittest.SkipTest('An isolated Windows native fixture needs the local reviewed Zig toolchain.')
            compiler = [str(zig), 'cc', '-target', 'x86_64-windows-gnu']
            output = folder / 'planner.dll'
        else:
            cc = shutil.which('cc') or shutil.which('clang') or shutil.which('gcc')
            if not cc:
                cls.temp.cleanup()
                raise unittest.SkipTest('An isolated native fixture needs a C compiler.')
            compiler = [cc]
            output = folder / 'planner.so'
        files = staged_sources()
        apply_common(files)
        apply_planner(files)
        for name, value in files.items():
            if name.endswith(('.h', '.inc')):
                (folder / Path(name).name).write_bytes(value)
        original = (SOURCE / 'developer/world_sizes/layout/layout_fixture.c').read_text()
        fixture = original.replace('#include "../../source/engine_resume/ai_food/experiment_runtime/', '#include "')
        if fixture.count('wsPack(count,') != 1 or fixture.count('wsPack(n,') != 1:
            raise AssertionError('The isolated native fixture changed.')
        fixture = fixture.replace('wsPack(count,', 'wsPack(s,count,').replace('wsPack(n,', 'wsPack(s,n,')
        fixture = '#ifndef _WIN32\n#define __declspec(x)\n#define __stdcall\n#endif\n' + fixture
        fixture += '''
__declspec(dllexport) int FixtureLayoutMatches(const WSWorldSettings*s,const WSPlanIsland*input,uint32_t count){
 if(!s||!input||count>WS_LIMIT||!wsConfigureWorldSize(s))return 0;
 memcpy(planned,input,count*sizeof(*input));return wsAdvancedLayoutMatches(s,count);
}
'''
        (folder / 'fixture.c').write_text(fixture)
        command = compiler + ['-std=c11', '-shared', '-O2', '-Wall', '-Wextra', '-Werror']
        if os.name != 'nt':
            command += ['-fPIC', '-Wno-unused-function', '-Wno-unused-const-variable', '-Wno-misleading-indentation']
        command += ['-o', str(output), str(folder / 'fixture.c')]
        env = os.environ.copy()
        if os.name == 'nt':
            for key in ('ZIG_GLOBAL_CACHE_DIR', 'ZIG_LOCAL_CACHE_DIR', 'TEMP', 'TMP'):
                path = folder / key
                path.mkdir()
                env[key] = str(path)
        completed = subprocess.run(command, capture_output=True, text=True, env=env, timeout=120)
        if completed.returncode:
            raise AssertionError('Isolated planner fixture did not compile:\n' + completed.stderr)
        cls.lib = C.CDLL(str(output))
        cls.lib.FixtureABI.restype = C.c_uint32
        cls.lib.FixtureFills.argtypes = [C.POINTER(Settings), C.c_uint32, C.POINTER(Island)]
        cls.lib.FixtureFills.restype = C.c_int
        cls.lib.FixtureReserves.argtypes = [C.POINTER(Settings), C.POINTER(Island)]
        cls.lib.FixtureReserves.restype = C.c_int
        cls.lib.LayoutPack.argtypes = [C.POINTER(Settings), C.POINTER(Island), C.c_uint32,
                                      C.c_uint32, C.POINTER(Island)]
        cls.lib.LayoutPack.restype = C.c_int
        cls.lib.SelectPlan.argtypes = [C.POINTER(Settings), C.c_uint32, C.POINTER(Island), C.POINTER(C.c_uint32)]
        cls.lib.SelectPlan.restype = C.c_int
        cls.lib.FixtureLayoutMatches.argtypes = [C.POINTER(Settings), C.POINTER(Island), C.c_uint32]
        cls.lib.FixtureLayoutMatches.restype = C.c_int

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'lib') and os.name == 'nt':
            import _ctypes
            _ctypes.FreeLibrary(cls.lib._handle)
        cls.temp.cleanup()

    def assert_geometry(self, options, islands):
        reserves = (Island * 32)()
        count = self.lib.FixtureReserves(C.byref(options), reserves)
        self.assertGreater(count, 0)
        for i, island in enumerate(islands):
            self.assertEqual(island.id, i)
            self.assertEqual((island.x % 8, island.y % 8), (0, 0))
            self.assertGreaterEqual(island.x, options.spacing)
            self.assertGreaterEqual(island.y, options.spacing)
            self.assertLessEqual(island.x + island.width + options.spacing, options.worldSize)
            self.assertLessEqual(island.y + island.height + options.spacing, options.worldSize)
            for other in islands[:i]:
                self.assertTrue(separated(island, other, options.spacing))
            for reserve in reserves[:count]:
                self.assertTrue(separated(island, reserve, options.spacing))

    def native_plan(self, options):
        out, attempt = (Island * 128)(), C.c_uint32()
        count = self.lib.SelectPlan(C.byref(options), options.mapSeed, out, C.byref(attempt))
        self.assertEqual(count, options.islandCount)
        return list(out[:count])

    def test_native_abi_and_weighted_climate_targets(self):
        self.assertEqual(self.lib.FixtureABI(), 96)
        self.assertEqual(C.sizeof(Island), 40)
        for balance, favored in ((0, ()), (1, (2, 3)), (2, (4, 5)), (3, (0, 1))):
            options = settings(islandCount=60, climateBalance=balance)
            out = (Island * 128)()
            self.assertEqual(self.lib.FixtureFills(C.byref(options), 931, out), 60)
            counts = Counter(p.climate for p in out[:60])
            self.assertEqual(set(counts), set(range(6)))
            self.assertEqual([counts[c] for c in range(6)],
                             [10 if not favored else (20 if c in favored else 5) for c in range(6)])

    def test_full_selection_preserves_cultures_resources_and_geometry(self):
        for balance in range(4):
            for style in range(3):
                with self.subTest(balance=balance, style=style):
                    options = settings(climateBalance=balance, layoutStyle=style)
                    islands = self.native_plan(options)
                    self.assert_geometry(options, islands)
                    cultures = crops = minerals = climates = 0
                    for p in islands:
                        cultures |= p.cultures
                        crops |= p.cropMask
                        minerals |= p.mineralMask
                        climates |= 1 << p.climate
                    self.assertEqual((cultures, crops, minerals & 0x2f, climates),
                                     (255, 0x1ffff, 0x2f, 63))
                    if style == 2:
                        edge = ((options.worldSize // 3 + 7) // 8) * 8
                        ocean = Island(x=edge, y=edge, width=options.worldSize-edge*2,
                                       height=options.worldSize-edge*2)
                        self.assertTrue(all(separated(p, ocean) for p in islands))

    def test_seed_reuse_and_non_map_settings_do_not_change_layout(self):
        for style in range(3):
            options = settings(worldSize=2048, layoutStyle=style, mapSeed=0xffffffff)
            first = self.native_plan(options)
            again = self.native_plan(options)
            self.assertEqual([bytes(p) for p in first], [bytes(p) for p in again])
            options.difficulty = 2
            options.startingMoney = 100000
            options.startingFleet = 2
            options.cargoMode = 1
            options.cargoTools = 50
            options.cargoWood = 100
            options.disasters = 0
            changed = self.native_plan(options)
            self.assertEqual([bytes(p) for p in first], [bytes(p) for p in changed])

    def test_archipelagos_have_tighter_groups_than_even_layout(self):
        options = settings(islandCount=24)
        source = (Island * 24)(*(Island(id=i, width=64, height=64) for i in range(24)))
        results = []
        for style in range(3):
            options.layoutStyle = style
            output = (Island * 24)()
            self.assertEqual(self.lib.LayoutPack(C.byref(options), source, 24, 1883, output), 1)
            islands = list(output)
            self.assert_geometry(options, islands)
            results.append(islands)
        def nearest_total(islands):
            return sum(min((max(0, b.x-a.x-a.width, a.x-b.x-b.width)**2 +
                            max(0, b.y-a.y-a.height, a.y-b.y-b.height)**2)
                           for j, b in enumerate(islands) if i != j)
                       for i, a in enumerate(islands))
        self.assertLess(nearest_total(results[1]), nearest_total(results[0]) * 0.7)
        self.assertNotEqual([bytes(p) for p in results[0]], [bytes(p) for p in results[2]])

    def test_central_ocean_is_rechecked_and_does_not_fall_back(self):
        options = settings(layoutStyle=2)
        bad = (Island * 1)(Island(id=0, x=400, y=400, width=64, height=64))
        self.assertEqual(self.lib.FixtureLayoutMatches(C.byref(options), bad, 1), 0)
        edge = (Island * 1)(Island(id=0, x=0, y=0, width=64, height=64))
        self.assertEqual(self.lib.FixtureLayoutMatches(C.byref(options), edge, 1), 1)
        giant = (Island * 1)(Island(id=0, width=1024, height=1024))
        output = (Island * 1)()
        self.assertEqual(self.lib.LayoutPack(C.byref(options), giant, 1, 939, output), 0)


if __name__ == '__main__':
    unittest.main()
