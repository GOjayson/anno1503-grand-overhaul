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
from anno1503_overhaul.world_options import PRIVATE, apply_common, authored
from anno1503_overhaul.world_options_planner import apply_planner, stage_selection_fixture


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

    def test_mandatory_prelude_and_counter_preimages_are_strict(self):
        for before, after in ((b'const uint32_t need[]={0x20,8,4,2,1};',
                               b'const uint32_t need[]={8,0x20,4,2,1};'),
                              (b'p->cropMask=cropMasks[t->climate];return 1;}',
                               b'p->cropMask=0;return 1;}')):
            files = staged_sources()
            apply_common(files)
            files[PRIVATE + 'world_backend.c'] = files[PRIVATE + 'world_backend.c'].replace(before, after, 1)
            with self.subTest(anchor=before), self.assertRaises((ValueError, RuntimeError)):
                apply_planner(files)


class Settings(C.Structure):
    _fields_ = [(name, C.c_uint32 if name in {'size', 'cultures', 'factions', 'mapSeed', 'disasterMask', 'disasterFrequency', 'disasterSeverity'} else C.c_int32)
                for name in ('size', 'difficulty', 'islandSize', 'islandCount', 'spacing',
                             'aiCount', 'cultures', 'factions', 'startingMoney',
                             'startingFleet', 'aiDifficulty', 'plantFertility',
                             'mineralFertility', 'worldSize', 'mapSeed', 'startClimate',
                             'startIsland', 'cargoMode', 'cargoTools', 'cargoWood',
                             'cargoFood', 'climateBalance', 'layoutStyle', 'disasters',
                             'fairStarts', 'startSeparation', 'resourceDistribution', 'guaranteeBasics',
                             'mapVisibility', 'enemyVisibility', 'pirateFrequency',
                             'pirateStrength', 'merchantFrequency', 'islandVariety',
                             'minPolar', 'maxPolar', 'minTemperate', 'maxTemperate',
                             'minTropical', 'maxTropical', 'disasterMask',
                             'disasterFrequency', 'disasterSeverity', 'islandRotation')]


class Island(C.Structure):
    _fields_ = [(name, C.c_uint32) for name in ('id', 'x', 'y', 'width', 'height',
                  'templateIndex', 'cropMask', 'mineralMask', 'cultures', 'climate', 'rotation')]


def settings(**overrides):
    result = Settings(size=C.sizeof(Settings), difficulty=1, islandSize=3,
                      islandCount=24, spacing=16, aiCount=0, cultures=255,
                      factions=3, startingMoney=30000, startingFleet=0,
                      aiDifficulty=1, plantFertility=1, mineralFertility=1,
                      worldSize=1024, mapSeed=3719, startClimate=-1,
                      startIsland=-1, cargoTools=40, cargoWood=40, cargoFood=10,
                      disasters=1, startSeparation=1, mapVisibility=1,
                      pirateFrequency=1, pirateStrength=1, merchantFrequency=1,
                      maxPolar=128, maxTemperate=128, maxTropical=128,
                      disasterMask=31, disasterFrequency=341, disasterSeverity=341)
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
        files[PRIVATE + 'island_rotation_plan.h'] = authored('island_rotation_plan.h')
        for name, value in files.items():
            if name.endswith(('.h', '.inc')):
                (folder / Path(name).name).write_bytes(value)
        original = (SOURCE / 'developer/world_sizes/layout/layout_fixture.c').read_text()
        fixture = original.replace('#include "../../source/engine_resume/ai_food/experiment_runtime/', '#include "')
        if fixture.count('wsPack(count,') != 1 or fixture.count('wsPack(n,') != 1:
            raise AssertionError('The isolated native fixture changed.')
        fixture = fixture.replace('wsPack(count,', 'wsPack(s,count,').replace('wsPack(n,', 'wsPack(s,n,')
        fixture = stage_selection_fixture(fixture.encode()).decode()
        fixture = fixture.replace('#include "island_selection.inc"',
            '#include "island_selection.inc"\n#include "island_rotation_plan.h"')
        rotation_output = '  memcpy(out,planned,n*sizeof(*out));*usedAttempt=(uint32_t)attempt;return (int)n;'
        if fixture.count(rotation_output) != 1:
            raise AssertionError('The isolated rotation assignment boundary changed.')
        fixture = fixture.replace(rotation_output,
            '  if(!wsAssignIslandRotations(s,seed,planned,n,selectionError,sizeof selectionError)||!wsIslandRotationsValid(s,planned,n))continue;\n' + rotation_output)
        # Reuse the complete staged selector with a fixture-only packer that
        # refuses the preference pass, proving its real bounded fallback path.
        select_marker = '__declspec(dllexport) int SelectPlan('
        if fixture.count(select_marker) != 1:
            raise AssertionError('The isolated native selector boundary changed.')
        selector = fixture.split(select_marker, 1)[1]
        if selector.count('!wsPack(s,n,') != 1:
            raise AssertionError('The isolated native packer boundary changed.')
        forced = '__declspec(dllexport) int FixtureForceVarietyFallback(' + selector.replace('!wsPack(s,n,', '!wsFixtureFallbackPack(s,n,')
        fixture += '''
static int wsFixtureFallbackPack(const WSWorldSettings*s,uint32_t count,uint32_t spacing){
 if(s->islandVariety&&!wsVarietyRelaxed)return 0;return wsPack(s,count,spacing);
}
''' + forced
        fixture = '#ifndef _WIN32\n#define __declspec(x)\n#define __stdcall\n#endif\n' + fixture
        fixture += '''
__declspec(dllexport) int FixtureLayoutMatches(const WSWorldSettings*s,const WSPlanIsland*input,uint32_t count){
 if(!s||!input||count>WS_LIMIT||!wsConfigureWorldSize(s))return 0;
 memcpy(planned,input,count*sizeof(*input));return wsAdvancedLayoutMatches(s,count);
}
__declspec(dllexport) uint32_t FixtureTemplateInfo(uint32_t index,uint32_t*out){
 if(index>=WS_COUNT||!out)return 0;const WSTemplate*t=&wsTemplates[index];
 out[0]=t->climate;out[1]=t->cultures;out[2]=wsTemplateFaction(t);out[3]=wsTemplateShapeIds[index];return 1;
}
__declspec(dllexport) int FixtureQuotaCertificate(const WSWorldSettings*s,const WSPlanIsland*input,uint32_t count){return wsClimateQuotaCertificate(s,input,count);}
__declspec(dllexport) int FixtureRotationEligible(uint32_t index){return wsIslandRotationEligible(index);}
__declspec(dllexport) int FixtureRotationValidate(const WSWorldSettings*s,const WSPlanIsland*rows,uint32_t count){return wsIslandRotationsValid(s,rows,count);}
__declspec(dllexport) int FixtureRotationAssign(const WSWorldSettings*s,uint32_t seed,WSPlanIsland*rows,uint32_t count){
 uint32_t before=rngState;char error[256];int result=wsAssignIslandRotations(s,seed,rows,count,error,sizeof error);return rngState!=before?-1:result;
}
__declspec(dllexport) int FixtureRotationSource(uint32_t r,uint32_t width,uint32_t height,uint32_t x,uint32_t y,uint32_t*out){return wsRotationCoastSource(r,width,height,x,y,out,out+1);}
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
        cls.lib.FixtureCatalogue.restype = C.c_uint32
        cls.lib.FixtureEligible.argtypes = [C.POINTER(Settings), C.c_uint32]
        cls.lib.FixtureEligible.restype = C.c_int
        cls.lib.FixtureTemplateInfo.argtypes = [C.c_uint32, C.POINTER(C.c_uint32)]
        cls.lib.FixtureTemplateInfo.restype = C.c_uint32
        cls.lib.FixtureQuotaCertificate.argtypes = [C.POINTER(Settings), C.POINTER(Island), C.c_uint32]
        cls.lib.FixtureQuotaCertificate.restype = C.c_int
        cls.lib.FixtureRotationEligible.argtypes = [C.c_uint32]
        cls.lib.FixtureRotationEligible.restype = C.c_int
        cls.lib.FixtureRotationValidate.argtypes = [C.POINTER(Settings), C.POINTER(Island), C.c_uint32]
        cls.lib.FixtureRotationValidate.restype = C.c_int
        cls.lib.FixtureRotationAssign.argtypes = [C.POINTER(Settings), C.c_uint32, C.POINTER(Island), C.c_uint32]
        cls.lib.FixtureRotationAssign.restype = C.c_int
        cls.lib.FixtureFills.argtypes = [C.POINTER(Settings), C.c_uint32, C.POINTER(Island)]
        cls.lib.FixtureFills.restype = C.c_int
        cls.lib.FixtureReserves.argtypes = [C.POINTER(Settings), C.POINTER(Island)]
        cls.lib.FixtureReserves.restype = C.c_int
        cls.lib.LayoutPack.argtypes = [C.POINTER(Settings), C.POINTER(Island), C.c_uint32,
                                      C.c_uint32, C.POINTER(Island)]
        cls.lib.LayoutPack.restype = C.c_int
        cls.lib.SelectPlan.argtypes = [C.POINTER(Settings), C.c_uint32, C.POINTER(Island), C.POINTER(C.c_uint32)]
        cls.lib.SelectPlan.restype = C.c_int
        cls.lib.FixtureForceVarietyFallback.argtypes = cls.lib.SelectPlan.argtypes
        cls.lib.FixtureForceVarietyFallback.restype = C.c_int
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
        self.assertEqual(self.lib.FixtureABI(), 176)
        self.assertEqual(Settings.pirateFrequency.offset, 120)
        self.assertEqual(Settings.pirateStrength.offset, 124)
        self.assertEqual(Settings.merchantFrequency.offset, 128)
        self.assertEqual(Settings.islandVariety.offset, 132)
        self.assertEqual(Settings.maxTropical.offset, 156)
        self.assertEqual(Settings.islandRotation.offset, 172)
        self.assertEqual(C.sizeof(Island), 44)
        self.assertEqual(Island.rotation.offset, 40)
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
            options.mapVisibility = 0
            options.enemyVisibility = 1
            changed = self.native_plan(options)
            self.assertEqual([bytes(p) for p in first], [bytes(p) for p in changed])

    def test_activity_choices_preserve_same_seed_islands_for_every_layout_style(self):
        for style in range(3):
            options = settings(worldSize=2048, layoutStyle=style, mapSeed=123456789)
            expected = [bytes(p) for p in self.native_plan(options)]
            for frequency in range(3):
                for strength in range(3):
                    for merchant in range(3):
                        with self.subTest(style=style, frequency=frequency, strength=strength, merchant=merchant):
                            options.pirateFrequency = frequency
                            options.pirateStrength = strength
                            options.merchantFrequency = merchant
                            self.assertEqual([bytes(p) for p in self.native_plan(options)], expected)

    def test_default_selection_matches_preserved_07_native_plans(self):
        # Captured from the immutable 0.7.0-dev.1 staged native includes before
        # these policies, not computed from this implementation's output.
        cases = (
            (0,0,0,'24cb8443c2c9e966e8d63b0747fe69cf654a54c1acf5b71a26cdd7de02c7759a'),
            (3719,0,0,'be9590b502cf174b7468594cf6646f7383efc1ab4282131ec3b2c4c74cae84db'),
            (123456789,0,0,'c2f52c45b9ab5751573edc30ad9d3cccd62a5a715c8084e7434becfb87cdc761'),
            (0xffffffff,0,0,'325c7d7221de28232254d8365a2398618e123ee139bdd37ee0cc8a8feb668f68'),
            (3719,1,1,'d4f8ab86f7611b2af9f0e13763ae684dbd728b5195dc70b6fd8d5dea69693da3'),
            (123456789,1,2,'1febb9a1d8b2138aa7f88f20e9fd6e61edd4d92899498efd71b6baf91255b02f'),
            (3719,2,3,'340b8fab274869b37f56b6c0862c64ac025091ec6691d06ccf073e9a913b2699'),
            (123456789,2,0,'b9e7d018e01ef789dd6fec4139e42fe722be0865d161c4e7775eb0f760406349'),
        )
        for seed, style, balance, digest in cases:
            with self.subTest(seed=seed, style=style, balance=balance):
                islands = self.native_plan(settings(mapSeed=seed, layoutStyle=style, climateBalance=balance))
                self.assertTrue(all(p.rotation == 0 for p in islands))
                self.assertEqual(hashlib.sha256(b''.join(bytes(p)[:40] for p in islands)).hexdigest(), digest)

    def test_variety_prefers_unused_templates_or_actual_coastline_groups(self):
        for mode in (1, 2):
            value = settings(islandCount=128, worldSize=2048, islandVariety=mode, cultures=0, factions=0)
            pools = [[] for _ in range(6)]
            shapes = {}
            for index in range(self.lib.FixtureCatalogue()):
                info = (C.c_uint32 * 4)()
                self.assertEqual(self.lib.FixtureTemplateInfo(index, info), 1)
                shapes[index] = info[3]
                if self.lib.FixtureEligible(C.byref(value), index) and info[1] == info[2] == 0:
                    pools[info[0]].append(index)
            out = (Island * 128)()
            self.assertEqual(self.lib.FixtureFills(C.byref(value), 123456789, out), 128)
            template_use, shape_use = Counter(), Counter()
            for island in out:
                def score(index):
                    return (shape_use[shapes[index]] * 129 if mode == 2 else 0) + template_use[index]
                self.assertEqual(score(island.templateIndex), min(score(i) for i in pools[island.climate]))
                template_use[island.templateIndex] += 1
                shape_use[shapes[island.templateIndex]] += 1
            # Restricted climate pools are reused instead of dropping islands
            # or falsely promising every template/shape can stay unique.
            self.assertGreater(max(template_use.values()), 1)
            repeated = (Island * 128)()
            self.assertEqual(self.lib.FixtureFills(C.byref(value), 123456789, repeated), 128)
            self.assertEqual(bytes(out), bytes(repeated))

    def test_climate_minima_and_maxima_include_cultures_and_special_islands(self):
        for mode in range(3):
            for style in range(3):
                value = settings(islandVariety=mode, layoutStyle=style, worldSize=2048,
                                 minPolar=6, maxPolar=6, minTemperate=8, maxTemperate=8,
                                 minTropical=10, maxTropical=10, mapSeed=123456789)
                with self.subTest(mode=mode, style=style):
                    islands = self.native_plan(value)
                    self.assertEqual(Counter(p.climate // 2 for p in islands), {0:6, 1:8, 2:10})
                    self.assert_geometry(value, islands)
                    cultures = crops = minerals = climates = special = 0
                    for p in islands:
                        cultures |= p.cultures; crops |= p.cropMask; minerals |= p.mineralMask; climates |= 1 << p.climate
                        info = (C.c_uint32 * 4)()
                        self.assertEqual(self.lib.FixtureTemplateInfo(p.templateIndex, info), 1)
                        special |= info[2]
                    self.assertEqual((cultures,crops,minerals & 0x2f,climates,special), (255,0x1ffff,0x2f,63,3))
                    source = (Island * 24)(*islands)
                    self.assertEqual(self.lib.FixtureQuotaCertificate(C.byref(value), source, 24), 1)
                    first_polar = next(p for p in source if p.climate // 2 == 0)
                    first_polar.climate = 4
                    self.assertEqual(self.lib.FixtureQuotaCertificate(C.byref(value), source, 24), 0)

    def test_bad_or_unsatisfiable_quotas_do_not_publish_a_plan(self):
        for changes in ({'minPolar':-1}, {'maxTropical':129}, {'minTemperate':8,'maxTemperate':7},
                        {'maxPolar':1}, {'minPolar':20,'minTemperate':20},
                        {'maxPolar':4,'maxTemperate':4,'maxTropical':4},
                        {'islandVariety':3}, {'maxTropical':2}):
            with self.subTest(changes=changes):
                value = settings(worldSize=2048, **changes)
                out, attempt = (Island * 128)(), C.c_uint32(0xcccccccc)
                C.memset(C.byref(out), 0xa5, C.sizeof(out));before = bytes(out)
                self.assertEqual(self.lib.SelectPlan(C.byref(value), value.mapSeed, out, C.byref(attempt)), 0)
                self.assertEqual((bytes(out), attempt.value), (before, 0xcccccccc))

    def test_world_fit_fallback_keeps_hard_quotas_and_replays_allow_repeats_search(self):
        for size in (3,4):
            for seed in (3719,123456789):
                value = settings(islandSize=size, worldSize=2048, mapSeed=seed,
                    minPolar=6,maxPolar=6,minTemperate=8,maxTemperate=8,minTropical=10,maxTropical=10)
                expected = [bytes(p) for p in self.native_plan(value)]
                for mode in (1,2):
                    with self.subTest(size=size,seed=seed,mode=mode):
                        value.islandVariety=mode
                        out,attempt=(Island*128)(),C.c_uint32()
                        self.assertEqual(self.lib.FixtureForceVarietyFallback(C.byref(value), seed, out, C.byref(attempt)),24)
                        self.assertGreaterEqual(attempt.value,32)
                        self.assertLess(attempt.value,64)
                        self.assertEqual([bytes(p) for p in out[:24]],expected)

    def test_random_rotations_are_seeded_and_preserve_all_existing_geometry_and_quota_fields(self):
        orientations=set()
        for mode in range(3):
            for style in range(3):
                value=settings(islandVariety=mode,layoutStyle=style,worldSize=2048,mapSeed=123456789,
                    minPolar=6,maxPolar=6,minTemperate=8,maxTemperate=8,minTropical=10,maxTropical=10)
                original=self.native_plan(value);value.islandRotation=1;rotated=self.native_plan(value)
                self.assertEqual([bytes(p)[:40]for p in rotated],[bytes(p)[:40]for p in original])
                self.assertEqual([bytes(p)for p in self.native_plan(value)],[bytes(p)for p in rotated])
                for p in rotated:
                    self.assertIn(p.rotation,range(4));orientations.add(p.rotation)
                    if not self.lib.FixtureRotationEligible(p.templateIndex):self.assertEqual(p.rotation,0)
                    if p.rotation:
                        info=(C.c_uint32*4)();self.lib.FixtureTemplateInfo(p.templateIndex,info)
                        self.assertEqual((p.cultures,info[2]),(0,0))
        self.assertEqual(orientations,{0,1,2,3})

    def test_rotation_assignment_rejects_malformed_plans_atomically_without_rng_use(self):
        value=settings(worldSize=2048,islandRotation=1)
        rows=self.native_plan(value);source=(Island*24)(*rows)
        self.assertEqual(sum(self.lib.FixtureRotationEligible(i)for i in range(self.lib.FixtureCatalogue())),256)
        self.assertEqual(self.lib.FixtureRotationAssign(C.byref(value),3719,source,24),1)
        self.assertEqual(self.lib.FixtureRotationValidate(C.byref(value),source,24),1)
        for mutation in ('identity','template','geometry','setting'):
            malformed=(Island*24)(*rows);options=settings(worldSize=2048,islandRotation=1)
            if mutation=='identity':malformed[23].id=0
            elif mutation=='template':malformed[23].templateIndex=0xffffffff
            elif mutation=='geometry':malformed[23].width+=8
            else:options.islandRotation=2
            before=bytes(malformed)
            self.assertEqual(self.lib.FixtureRotationAssign(C.byref(options),3719,malformed,24),0)
            self.assertEqual(bytes(malformed),before)
        original=(Island*24)(*rows);original[0].rotation=4
        self.assertEqual(self.lib.FixtureRotationValidate(C.byref(value),original,24),0)
        original=(Island*24)(*rows)
        fixed=next(p for p in original if not self.lib.FixtureRotationEligible(p.templateIndex));fixed.rotation=1
        self.assertEqual(self.lib.FixtureRotationValidate(C.byref(value),original,24),0)

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
