"""Execute resource geography against the real catalogue, without Anno.

These fixtures exercise native policy code, not the game's mineral loader or
an actual harvest/mine. Full DLL and save comparisons have separate evidence.
"""
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
         'world_factions.h', 'world_ship_reserves.h', 'plant_fertility.inc', 'mineral_fertility.inc')
FIELDS = ('size', 'difficulty', 'islandSize', 'islandCount', 'spacing', 'aiCount',
          'cultures', 'factions', 'startingMoney', 'startingFleet', 'aiDifficulty',
          'plantFertility', 'mineralFertility', 'worldSize', 'mapSeed', 'startClimate',
          'startIsland', 'cargoMode', 'cargoTools', 'cargoWood', 'cargoFood',
          'climateBalance', 'layoutStyle', 'disasters', 'fairStarts',
          'startSeparation', 'resourceDistribution', 'guaranteeBasics', 'mapVisibility', 'enemyVisibility')


class Settings(C.Structure):
    _fields_ = [(n, C.c_uint32 if n in {'size', 'cultures', 'factions', 'mapSeed'} else C.c_int32) for n in FIELDS]


class Island(C.Structure):
    _fields_ = [(n, C.c_uint32) for n in ('id', 'x', 'y', 'width', 'height', 'templateIndex',
                                        'cropMask', 'mineralMask', 'cultures', 'climate')]


def options(**values):
    result = Settings(size=C.sizeof(Settings), difficulty=1, islandSize=3,
                      islandCount=24, spacing=16, cultures=255, factions=3,
                      startingMoney=30000, aiDifficulty=1, plantFertility=1,
                      mineralFertility=1, worldSize=1024, mapSeed=3719,
                      startClimate=-1, startIsland=-1, disasters=1, startSeparation=1, mapVisibility=1)
    for key, value in values.items():
        setattr(result, key, value)
    return result


def census(rows, field, bits):
    return [sum(bool(getattr(p, field) & (1 << b)) for p in rows) for b in range(bits)]


def centres_distance(a, b):
    return ((2*a.x+a.width)-(2*b.x+b.width))**2 + ((2*a.y+a.height)-(2*b.y+b.height))**2


def spread_measure(rows):
    score = 0
    for field, bits in (('cropMask', 0xff6), ('mineralMask', 0x2f)):
        for b in range(13):
            if not bits & (1 << b):
                continue
            matching = [p for p in rows if getattr(p, field) & (1 << b)]
            score += sum(centres_distance(a, z) for i, a in enumerate(matching) for z in matching[:i])
    return score


class NativeResourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='anno-resource-geography-')
        folder = Path(cls.temp.name)
        if os.name == 'nt':
            zig = ROOT / '.local/toolchain/ziglang/zig.exe'
            if not zig.is_file():
                cls.temp.cleanup()
                raise unittest.SkipTest('Native resource fixtures need the reviewed local Zig toolchain.')
            compiler, output = [str(zig), 'cc', '-target', 'x86_64-windows-gnu'], folder / 'resources.dll'
        else:
            cc = shutil.which('cc') or shutil.which('clang') or shutil.which('gcc')
            if not cc:
                cls.temp.cleanup()
                raise unittest.SkipTest('Native resource fixtures need a C compiler.')
            compiler, output = [cc], folder / 'resources.so'
        files = {PRIVATE + n: (SOURCE / PRIVATE / n).read_bytes() for n in NAMES}
        before = {n: hashlib.sha256(v).hexdigest() for n, v in files.items()}
        apply_common(files)
        apply_planner(files)
        for name, digest in before.items():
            if hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() != digest:
                raise AssertionError('A frozen native input changed.')
        for name, value in files.items():
            if name.endswith(('.h', '.inc')):
                (folder / Path(name).name).write_bytes(value)
        fixture = (SOURCE / 'developer/world_sizes/layout/layout_fixture.c').read_text()
        fixture = fixture.replace('#include "../../source/engine_resume/ai_food/experiment_runtime/', '#include "')
        fixture = fixture.replace('wsPack(count,', 'wsPack(s,count,').replace('wsPack(n,', 'wsPack(s,n,')
        fixture = '#ifndef _WIN32\n#define __declspec(x)\n#define __stdcall\n#endif\n' + fixture
        fixture += '''
static uint32_t planCount,resourceFixtureAnchors[4];
static void wsMessage(char*out,uint32_t cap,const char*text){if(out&&cap)snprintf(out,cap,"%s",text);}
#include "plant_fertility.inc"
#include "mineral_fertility.inc"
#include "resource_distribution.inc"
static int wsStartResourceAnchor(const WSWorldSettings*s,uint32_t owner,uint32_t*island){
 if(!s||owner>(uint32_t)s->aiCount||owner>=4||resourceFixtureAnchors[owner]>=planCount||!wsResourceOrdinary(resourceFixtureAnchors[owner]))return 0;
 *island=resourceFixtureAnchors[owner];return 1;
}
__declspec(dllexport) int ResourceBuild(const WSWorldSettings*s,uint32_t seed,WSPlanIsland*out,char*error){
 uint32_t attempt;int n=SelectPlan(s,seed,out,&attempt);if(n<=0)return 0;planCount=(uint32_t)n;
 if(!wsApplyPlantFertility(s,seed,error,512)||!wsApplyMineralFertility(s,seed,error,512)||!wsApplyResourceDistribution(s,seed,error,512))return 0;
 if(!wsValidateStartResources(s,error,512))return 0;
 memcpy(out,planned,planCount*sizeof(*out));return n;
}
__declspec(dllexport) int ResourceApply(const WSWorldSettings*s,const WSPlanIsland*input,uint32_t count,const uint32_t*anchors,WSPlanIsland*out,char*error){
 if(!s||!input||!out||!count||count>WS_LIMIT||!wsConfigureWorldSize(s))return 0;
 memcpy(planned,input,count*sizeof(*input));planCount=count;
 for(uint32_t i=0;i<4;i++)resourceFixtureAnchors[i]=anchors?anchors[i]:0;
 int result=wsApplyResourceDistribution(s,s->mapSeed,error,512)&&wsGuaranteeStartResources(s,s->mapSeed,error,512)&&wsValidateStartResources(s,error,512);
 memcpy(out,planned,planCount*sizeof(*out));return result;
}
__declspec(dllexport) int ResourceTemplate(uint32_t climate,uint32_t slots,uint32_t culture,uint32_t faction){
 for(uint32_t i=0;i<WS_COUNT;i++)if(wsTemplates[i].climate==climate&&wsTemplates[i].oreSlots==slots&&(!culture?!wsTemplates[i].cultures:wsTemplates[i].cultures!=0)&&wsTemplateFaction(&wsTemplates[i])==faction)return (int)i;
 return -1;
}
__declspec(dllexport) int ResourceIsland(uint32_t index,uint32_t id,uint32_t x,uint32_t y,uint32_t crops,uint32_t minerals,WSPlanIsland*out){
 if(index>=WS_COUNT||!out)return 0;const WSTemplate*t=&wsTemplates[index];
 *out=(WSPlanIsland){id,x,y,t->width,t->height,index,crops,minerals,t->cultures,t->climate};return 1;
}
__declspec(dllexport) int ResourceOrdinary(uint32_t index){return wsResourceOrdinary(index);}
__declspec(dllexport) int ResourceValid(const WSWorldSettings*s,char*error){return wsValidateStartResources(s,error,512);}
__declspec(dllexport) void ResourceCorrupt(uint32_t index,uint32_t bit){if(index<planCount)planned[index].mineralMask^=bit;}
__declspec(dllexport) void ResourceNearby(uint32_t index,uint32_t*crops,uint32_t*minerals){wsResourceNearby(index,crops,minerals);}
'''
        (folder / 'fixture.c').write_text(fixture)
        command = compiler + ['-std=c11', '-shared', '-O2', '-Wall', '-Wextra', '-Werror',
                              '-Wno-misleading-indentation', '-Wno-unused-function', '-Wno-unused-const-variable']
        if os.name != 'nt':
            command += ['-fPIC']
        command += ['-o', str(output), str(folder / 'fixture.c')]
        environment = os.environ.copy()
        if os.name == 'nt':
            for key in ('ZIG_GLOBAL_CACHE_DIR', 'ZIG_LOCAL_CACHE_DIR', 'TEMP', 'TMP'):
                path = folder / key
                path.mkdir()
                environment[key] = str(path)
        result = subprocess.run(command, capture_output=True, text=True, env=environment, timeout=120)
        if result.returncode:
            raise AssertionError('Resource policy fixture did not compile:\n' + result.stderr)
        cls.lib = C.CDLL(str(output))
        cls.lib.ResourceBuild.argtypes = [C.POINTER(Settings), C.c_uint32, C.POINTER(Island), C.c_char_p]
        cls.lib.ResourceApply.argtypes = [C.POINTER(Settings), C.POINTER(Island), C.c_uint32, C.POINTER(C.c_uint32), C.POINTER(Island), C.c_char_p]
        cls.lib.ResourceTemplate.argtypes = [C.c_uint32]*4
        cls.lib.ResourceTemplate.restype = C.c_int
        cls.lib.ResourceIsland.argtypes = [C.c_uint32]*6 + [C.POINTER(Island)]
        cls.lib.ResourceOrdinary.argtypes = [C.c_uint32]
        cls.lib.ResourceValid.argtypes = [C.POINTER(Settings), C.c_char_p]
        cls.lib.ResourceCorrupt.argtypes = [C.c_uint32, C.c_uint32]
        cls.lib.ResourceNearby.argtypes = [C.c_uint32, C.POINTER(C.c_uint32), C.POINTER(C.c_uint32)]

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'lib') and os.name == 'nt':
            import _ctypes
            _ctypes.FreeLibrary(cls.lib._handle)
        cls.temp.cleanup()

    def build(self, settings):
        output, error = (Island*128)(), C.create_string_buffer(512)
        count = self.lib.ResourceBuild(C.byref(settings), settings.mapSeed, output, error)
        self.assertEqual(count, settings.islandCount, error.value.decode())
        ordinary = [bool(self.lib.ResourceOrdinary(i)) for i in range(count)]
        return list(output[:count]), ordinary

    def island(self, climate, slots, index, x, y=0, crops=None, minerals=0, culture=0, faction=0):
        template = self.lib.ResourceTemplate(climate, slots, culture, faction)
        self.assertGreaterEqual(template, 0)
        out = Island()
        defaults = [0x18000, 0xf009, 0xf949, 0xf06b, 0xf6b9, 0xf04d]
        self.assertEqual(self.lib.ResourceIsland(template,index,x,y,defaults[climate] if crops is None else crops,minerals,C.byref(out)),1)
        return out

    def apply(self, settings, rows, anchors=(0,0,0,0)):
        source, out, error = (Island*len(rows))(*rows), (Island*len(rows))(), C.create_string_buffer(512)
        result = self.lib.ResourceApply(C.byref(settings),source,len(rows),(C.c_uint32*4)(*anchors),out,error)
        return result, list(out), error.value.decode()

    def test_real_catalogue_modes_preserve_census_geometry_and_special_islands(self):
        self.assertEqual(C.sizeof(Settings),120)
        improved = 0
        for seed in (0,3719,123456789,0xffffffff):
            for fertility in range(4):
                original, ordinary = self.build(options(mapSeed=seed,plantFertility=fertility,mineralFertility=fertility))
                for mode in (1,2):
                    with self.subTest(seed=seed,fertility=fertility,mode=mode):
                        changed, changed_ordinary = self.build(options(mapSeed=seed,plantFertility=fertility,mineralFertility=fertility,resourceDistribution=mode))
                        self.assertEqual(ordinary,changed_ordinary)
                        self.assertEqual(census(original,'cropMask',13),census(changed,'cropMask',13))
                        self.assertEqual(census(original,'mineralMask',6),census(changed,'mineralMask',6))
                        for a,b,moveable in zip(original,changed,ordinary):
                            self.assertEqual((a.id,a.x,a.y,a.width,a.height,a.templateIndex,a.cultures,a.climate),
                                             (b.id,b.x,b.y,b.width,b.height,b.templateIndex,b.cultures,b.climate))
                            if not moveable:
                                self.assertEqual(bytes(a),bytes(b))
                        if mode==1:
                            initial=spread_measure([p for p,eligible in zip(original,ordinary) if eligible])
                            after=spread_measure([p for p,eligible in zip(changed,ordinary) if eligible])
                            self.assertGreaterEqual(after,initial)
                            improved+=after>initial
        self.assertGreater(improved,0)

    def test_modes_repeat_exactly_and_do_not_depend_on_money_food_or_fleet(self):
        for mode in range(3):
            settings=options(resourceDistribution=mode)
            first,_=self.build(settings)
            again,_=self.build(settings)
            self.assertEqual([bytes(p) for p in first],[bytes(p) for p in again])
            settings.startingMoney=100000;settings.startingFleet=2;settings.cargoMode=1
            settings.cargoTools=25;settings.cargoWood=75;settings.cargoFood=40
            changed,_=self.build(settings)
            self.assertEqual([bytes(p) for p in first],[bytes(p) for p in changed])

    def test_specialised_regions_cluster_resources_on_compatible_islands(self):
        rows=[self.island(2,2,i,x,crops=0xf009,minerals=1 if i%2 else 4)
              for i,x in enumerate((0,80,160,240,700,780,860,940))]
        original=spread_measure(rows)
        results=[]
        for seed in (1,79,123456789):
            result,changed,error=self.apply(options(resourceDistribution=2,mapSeed=seed,worldSize=2048),rows)
            self.assertEqual(result,1,error)
            self.assertEqual(census(rows,'mineralMask',6),census(changed,'mineralMask',6))
            results.append(spread_measure(changed))
        self.assertTrue(all(value<original for value in results),results)

    def test_nearby_basics_covers_each_selected_player_and_can_override_density(self):
        rows=[self.island(2,0,0,0,crops=0xf009),self.island(2,2,1,80,crops=0xf009),
              self.island(2,2,2,400,crops=0xf009,minerals=5),self.island(2,0,3,800,crops=0xf009),
              self.island(2,2,4,880,crops=0xf009)]
        settings=options(guaranteeBasics=1,aiCount=1)
        result,changed,error=self.apply(settings,rows,anchors=(0,3,0,0))
        self.assertEqual(result,1,error)
        self.assertGreater(sum(p.mineralMask.bit_count() for p in changed),sum(p.mineralMask.bit_count() for p in rows))
        for anchor in (0,3):
            crops,minerals=C.c_uint32(),C.c_uint32()
            self.lib.ResourceNearby(anchor,C.byref(crops),C.byref(minerals))
            self.assertEqual(crops.value&0x1009,0x1009)
            self.assertEqual(minerals.value&5,5)
        error_buffer=C.create_string_buffer(512)
        self.lib.ResourceCorrupt(1,4)
        self.assertEqual(self.lib.ResourceValid(C.byref(settings),error_buffer),0)

    def test_full_native_slots_can_swap_without_losing_an_existing_basic(self):
        rows=[self.island(2,0,0,0,crops=0xf009),
              self.island(2,1,1,80,crops=0xf009,minerals=4),
              self.island(2,1,2,180,crops=0xf009,minerals=32),
              self.island(2,1,3,700,crops=0xf009,minerals=1)]
        result,changed,error=self.apply(options(guaranteeBasics=1),rows)
        self.assertEqual(result,1,error)
        self.assertEqual(census(rows,'mineralMask',6),census(changed,'mineralMask',6))
        self.assertEqual(changed[1].mineralMask,4)
        self.assertEqual(changed[2].mineralMask,1)
        self.assertEqual(changed[3].mineralMask,32)
        crops,minerals=C.c_uint32(),C.c_uint32()
        self.lib.ResourceNearby(0,C.byref(crops),C.byref(minerals))
        self.assertEqual(minerals.value&5,5)

    def test_impossible_guarantee_preserves_plan_and_does_not_use_occupied_islands(self):
        rows=[self.island(4,0,0,0,crops=0xf009),self.island(2,2,1,800,crops=0xf009,minerals=5)]
        settings=options(guaranteeBasics=1)
        result,changed,error=self.apply(settings,rows)
        self.assertEqual(result,0)
        self.assertIn('iron or salt',error)
        self.assertEqual([bytes(p) for p in rows],[bytes(p) for p in changed])
        # A query on an occupied island is allowed; only nearby ordinary land
        # contributes to its accessible-resource union.
        occupied=self.island(2,2,0,0,crops=0xf009,minerals=5,culture=1)
        result,changed,error=self.apply(options(),[occupied])
        self.assertEqual(result,1,error)
        crops,minerals=C.c_uint32(),C.c_uint32()
        self.lib.ResourceNearby(0,C.byref(crops),C.byref(minerals))
        self.assertEqual((crops.value,minerals.value),(0,0))

    def test_polar_nonplant_flags_do_not_count_as_growing_basic_crops(self):
        row=self.island(0,2,0,0)
        result,_,error=self.apply(options(),[row])
        self.assertEqual(result,1,error)
        crops,minerals=C.c_uint32(),C.c_uint32()
        self.lib.ResourceNearby(0,C.byref(crops),C.byref(minerals))
        self.assertEqual((crops.value,minerals.value),(0,0))
        result,changed,error=self.apply(options(guaranteeBasics=1),[row])
        self.assertEqual(result,0)
        self.assertIn('grain, flax and potatoes',error)
        self.assertEqual(bytes(changed[0]),bytes(row))

    def test_invalid_capacity_and_distribution_are_rejected(self):
        row=self.island(2,0,0,0,crops=0xf009,minerals=5)
        result,_,error=self.apply(options(),[row])
        self.assertEqual(result,0)
        self.assertIn('capacity',error)
        valid=self.island(2,2,0,0,crops=0xf009)
        result,_,error=self.apply(options(resourceDistribution=3),[valid])
        self.assertEqual(result,0)
        self.assertIn('Invalid resource distribution',error)


if __name__=='__main__':
    unittest.main()
