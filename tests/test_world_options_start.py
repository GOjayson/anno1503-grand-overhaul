import ctypes as C
import hashlib
import os
from pathlib import Path
import re
import struct
import subprocess
import unittest
import uuid

from anno1503_overhaul.world_options import PRIVATE, ROOT, apply_common
from anno1503_overhaul.world_options_start import apply_start
from anno1503_overhaul.world_runtime_build import PE, RuntimeBuildError


def staged():
    base = ROOT / 'legacy/world_settings'
    names = ('world_backend.h', 'world_backend.c', 'WorldSettings.c',
             'world_ship_reserves.h', 'start_options.inc', 'preview_state.inc',
             'starting_fleet_certificate.inc', 'native_faction_options.h', 'world_ai.c')
    files = {PRIVATE + name: (base / PRIVATE / name).read_bytes() for name in names}
    apply_common(files)
    apply_start(files)
    return files


class StartRecipeTests(unittest.TestCase):
    def test_stock_scenes_have_contiguous_ordinary_owner_ids_and_ships(self):
        catalogue = (ROOT / 'legacy/world_settings' / PRIVATE / 'world_catalogue.h').read_text()
        for difficulty, name in enumerate(('Easy', 'Medium', 'Hard')):
            scene = bytes(int(v) for v in re.findall(r'\d+',
                re.search(r'wsScene' + name + r'\[\]\s*=\s*\{(.*?)\};', catalogue, re.S)[1]))
            ordinary, boats = set(), {}
            at = 32
            while at < len(scene):
                tag = scene[at:at+12].rstrip(b'\0')
                size, = struct.unpack_from('<I', scene, at+12)
                payload = scene[at+16:at+16+size]
                self.assertEqual(len(payload), size)
                if tag == b'SPIELER':
                    scope, owner = struct.unpack_from('<II', payload)
                    self.assertEqual(scope, 0)
                    for field, data in NativeStartingOptionsTests.fields(payload, 8):
                        if field == 'HEAD' and len(data) == 108 and struct.unpack_from('<H', data)[0] == 12:
                            ordinary.add(owner)
                        if field in ('SCHIFF', 'SCHI64'):
                            definition, = struct.unpack_from('<H', data, 4 if field == 'SCHI64' else 2)
                            boats.setdefault(owner, []).append(definition)
                at += size+16
            expected = set(range(1, 4 if difficulty == 0 else 5))
            self.assertEqual(ordinary, expected)
            self.assertEqual({owner: boats[owner] for owner in expected}, {owner: [1502] for owner in expected})

    def test_imported_native_inputs_remain_immutable(self):
        base = ROOT / 'legacy/world_settings'
        names = ('world_ship_reserves.h', 'start_options.inc', 'native_faction_options.h')
        before = {name: (base / PRIVATE / name).read_bytes() for name in names}
        result = staged()
        self.assertIn(PRIVATE + 'start_position.inc', result)
        self.assertIn(PRIVATE + 'start_cargo.inc', result)
        for name, value in before.items():
            self.assertEqual((base / PRIVATE / name).read_bytes(), value)

    def test_unknown_native_option_binding_is_refused(self):
        base = ROOT / 'legacy/world_settings'
        names = ('world_backend.h', 'world_backend.c', 'WorldSettings.c',
                 'world_ship_reserves.h', 'start_options.inc', 'preview_state.inc',
                 'starting_fleet_certificate.inc', 'native_faction_options.h', 'world_ai.c')
        files = {PRIVATE + name: (base / PRIVATE / name).read_bytes() for name in names}
        apply_common(files)
        name = PRIVATE + 'WorldSettings.c'
        files[name] = files[name].replace(b'wsBindNativeFactionOptions(d->frame,d->settings.factions)',
                                        b'unsupported_native_binding(d->frame)', 1)
        with self.assertRaises(RuntimeBuildError):
            apply_start(files)


class Settings(C.Structure):
    _fields_ = [('size', C.c_uint32)] + [(name, C.c_int32) for name in (
        'difficulty', 'islandSize', 'islandCount', 'spacing', 'aiCount', 'cultures',
        'factions', 'startingMoney', 'startingFleet', 'aiDifficulty',
        'plantFertility', 'mineralFertility', 'worldSize', 'mapSeed',
        'startClimate', 'startIsland', 'cargoMode', 'cargoTools', 'cargoWood',
        'cargoFood', 'climateBalance', 'layoutStyle', 'disasters', 'fairStarts',
        'startSeparation', 'resourceDistribution', 'guaranteeBasics', 'mapVisibility', 'enemyVisibility')]


class Island(C.Structure):
    _fields_ = [(name, C.c_uint32) for name in (
        'id', 'x', 'y', 'width', 'height', 'templateIndex', 'cropMask',
        'mineralMask', 'cultures', 'climate')]


class SceneShip(C.Structure):
    _fields_ = [('owner', C.c_uint32), ('definition', C.c_uint32),
                ('x', C.c_float), ('y', C.c_float)]


def settings(**changes):
    value = Settings()
    value.size = C.sizeof(value)
    value.worldSize = 1024
    value.startClimate = value.startIsland = -1
    value.disasters = 1
    value.mapVisibility = 1
    for key, item in changes.items():
        setattr(value, key, item)
    return value


ZIG = ROOT / '.local/toolchain/ziglang/zig.exe'


@unittest.skipUnless(os.name == 'nt' and ZIG.is_file(), 'Optional local Windows native fixture toolchain is unavailable')
class NativeStartingOptionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        files = staged()
        output = ROOT / '.local/validation' / ('options-start-' + uuid.uuid4().hex)
        output.mkdir(parents=True)
        for name in ('advanced_settings.h', 'world_ship_reserves.h', 'start_position.inc',
                     'start_cargo.inc', 'start_options.inc', 'native_faction_options.h', 'fair_starts.inc'):
            (output / name).write_bytes(files[PRIVATE + name])
        header = files[PRIVATE + 'world_backend.h'].decode()
        declarations = '\n'.join(re.findall(r'typedef struct WS(?:WorldSettings|PlanIsland|IslandDetails)\s*\{.*?\}\s*WS\w+;', header, re.S))
        source = r'''
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
DECLARATIONS
#include "advanced_settings.h"
#include "world_ship_reserves.h"
#define WS_LIMIT 128u
typedef struct WSTemplate{uint32_t faction,fertileLand;} WSTemplate;
static WSTemplate wsTemplates[5]={{0,2000},{1,2000},{0,2500},{0,3000},{0,8000}};
#define WS_COUNT 5u
static WSPlanIsland planned[128];
static uint32_t planCount,planSpacing;
static struct{uint32_t state;}wsPreviewCache;
static uint32_t wsTemplateFaction(const WSTemplate*t){return t->faction;}
static int wsPop(uint32_t n){int count=0;while(n){count++;n&=n-1u;}return count;}
static void wsMessage(char*out,uint32_t cap,const char*text){if(out&&cap)snprintf(out,cap,"%s",text);}
static int wsSeparated(const WSPlanIsland*a,const WSPlanIsland*b,uint32_t gap){return a->x+a->width+gap<=b->x||b->x+b->width+gap<=a->x||a->y+a->height+gap<=b->y||b->y+b->height+gap<=a->y;}
#include "start_position.inc"
static uint32_t wsU32(const unsigned char*p){uint32_t n;memcpy(&n,p,4);return n;}
static uint16_t wsU16(const unsigned char*p){uint16_t n;memcpy(&n,p,2);return n;}
static void wsPut16(unsigned char*p,uint16_t value){memcpy(p,&value,2);}
static void wsPut32(unsigned char*p,uint32_t value){memcpy(p,&value,4);}
static int wsTag(const unsigned char*p,const char*tag){size_t n=strlen(tag);return n<=12&&!memcmp(p,tag,n)&&(n==12||p[n]==0);}
typedef struct WSBuffer{unsigned char*data;uint32_t size,capacity;}WSBuffer;
static int wsAppend(WSBuffer*b,const void*data,uint32_t size){if(size>b->capacity-b->size)return 0;memcpy(b->data+b->size,data,size);b->size+=size;return 1;}
static int wsChunk(WSBuffer*b,const char*tag,const void*payload,uint32_t size){unsigned char h[16]={0};memcpy(h,tag,strlen(tag));wsPut32(h+12,size);return wsAppend(b,h,16)&&wsAppend(b,payload,size);}
#include "start_options.inc"
static int wsCertRead(const void*p,void*out,SIZE_T size){memcpy(out,p,size);return 1;}
CARGO_CERTIFICATE
#include "native_faction_options.h"
__declspec(dllexport) int fixtureBind(unsigned char*frame,uint32_t factions,int32_t disasters){return wsBindNativeFactionOptions(frame,factions,disasters);}
__declspec(dllexport) int fixtureCargo(WSWorldSettings*s,uint32_t ship,unsigned short*goods,unsigned short*tons,unsigned char*serialized){
 if(s->startingFleet<0||s->startingFleet>2)return 0;
 wsExpectedStartShipCount=s->startingFleet?3u:1u;
 if(ship>=wsExpectedStartShipCount)return 0;
 wsExpectedStartShips[0].definition=s->startingFleet?1503u:1502u;
 wsExpectedStartShips[1].definition=wsExpectedStartShips[2].definition=s->startingFleet==1?1504u:1502u;
 if(!wsStartingCargoSelection(s))return 0;
 memcpy(goods,wsExpectedCargoGoods[ship],16);memcpy(tons,wsExpectedCargoTons[ship],16);
 uint32_t definition=wsExpectedStartShips[ship].definition,holds=definition==1503u?8u:(definition==1502u?4u:2u);
 wsStartingCargoBytes(serialized,ship,holds);return (int)holds;
}
__declspec(dllexport) int fixturePosition(WSWorldSettings*s,const WSPlanIsland*input,uint32_t count,float*xy,int32_t*chosen,uint32_t*unchanged,char*error,uint32_t cap){
 if(count>128||!wsAdvancedValidateSettings(s,error,cap))return 0;
 memcpy(planned,input,count*sizeof(*input));planCount=count;planSpacing=(uint32_t)s->spacing;wsPreviewCache.state=1;
 if(!wsConfigureWorldSize(s))return 0;
 int result=wsApplyPreferredStart(s,error,cap);wsWorldShipPosition(0,xy,xy+1);
 *chosen=wsPreferredIsland;*unchanged=!memcmp(planned,input,count*sizeof(*input));return result;
}
__declspec(dllexport) int fixtureFair(WSWorldSettings*s,const WSPlanIsland*input,uint32_t count,int replay,float*xy,int32_t*islands,uint32_t*owners,char*error,uint32_t cap){
 if(count>128||!wsAdvancedValidateSettings(s,error,cap))return 0;
 memcpy(planned,input,count*sizeof(*input));planCount=count;planSpacing=(uint32_t)s->spacing;wsPreviewCache.state=replay?1u:0u;
 if(!wsConfigureWorldSize(s)||!wsApplyPreferredStart(s,error,cap)||!wsValidateFairStarts(s,error,cap))return 0;
 if(memcmp(planned,input,count*sizeof(*input)))return 0;
 wsPreviewCache.state=1;
 for(uint32_t owner=0;owner<4u;owner++){
  wsWorldShipPosition(owner,xy+2u*owner,xy+2u*owner+1u);
  islands[owner]=wsAssignedStartIsland[owner];
 }
 *owners=WorldSettingsExpectedFairOwners();return 1;
}
__declspec(dllexport) int fixtureAnchor(WSWorldSettings*s,uint32_t owner,uint32_t*island){return wsStartResourceAnchor(s,owner,island);}
__declspec(dllexport) uint32_t fixtureShips(WSSceneShip*out){memcpy(out,wsExpectedSceneShips,wsExpectedSceneShipCount*sizeof(*out));return wsExpectedSceneShipCount;}
__declspec(dllexport) int fixtureSerialize(WSWorldSettings*s,const unsigned char*source,uint32_t size,unsigned char*out,uint32_t capacity,uint32_t*written,char*error,uint32_t cap){
 *written=0;if(!wsConfigureWorldSize(s)||!wsStartingInspect(source,size,s,error,cap))return 0;
 WSBuffer b={out,0,capacity};
 for(uint32_t at=32;at<size;){
  if(!wsStartingEmitExtraShips(&b,s,at,error,cap))return 0;
  if(size-at<16)return 0;uint32_t n=wsU32(source+at+12);if(n>size-at-16)return 0;
  if(wsTag(source+at,"SPIELER")&&n>=8&&wsU32(source+at+20)==0){if(!wsStartingScenePlayer(&b,source+at+16,n,s,error,cap))return 0;}
  at+=16+n;
 }
 *written=b.size;return 1;
}
__declspec(dllexport) int fixtureCargoCertificate(void*ship,void*figure,uint32_t definition,float x,float y,char*error,uint32_t cap){
 uint32_t seen=0;return wsStartingShipMatches(ship,figure,definition,x,y,&seen,error,cap);
}
'''.replace('DECLARATIONS', declarations).replace('CARGO_CERTIFICATE',
                files[PRIVATE + 'starting_fleet_certificate.inc'].decode().split('static int wsStartingMoneyCertificate', 1)[0])
        path = output / 'fixture.c'
        path.write_text(source, encoding='utf-8')
        dll = output / 'Fixture.dll'
        env = os.environ.copy()
        for key, child in (('ZIG_GLOBAL_CACHE_DIR', 'global-cache'), ('ZIG_LOCAL_CACHE_DIR', 'local-cache'),
                           ('TEMP', 'tmp'), ('TMP', 'tmp')):
            folder = output / child
            folder.mkdir(exist_ok=True)
            env[key] = str(folder)
        command = [str(ZIG), 'cc', '-shared', '-O2', '-Wall', '-Wextra', '-Werror', str(path), '-o', str(dll)]
        result = subprocess.run(command, capture_output=True, text=True, env=env)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        cls.dll = C.CDLL(str(dll))
        cls.cargo = cls.dll.fixtureCargo
        cls.cargo.argtypes = [C.POINTER(Settings), C.c_uint32, C.c_void_p, C.c_void_p, C.c_void_p]
        cls.cargo.restype = C.c_int
        cls.position = cls.dll.fixturePosition
        cls.position.argtypes = [C.POINTER(Settings), C.POINTER(Island), C.c_uint32, C.c_void_p,
                                C.c_void_p, C.c_void_p, C.c_void_p, C.c_uint32]
        cls.position.restype = C.c_int
        cls.fair = cls.dll.fixtureFair
        cls.fair.argtypes = [C.POINTER(Settings), C.POINTER(Island), C.c_uint32,
            C.c_int, C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p, C.c_uint32]
        cls.fair.restype = C.c_int
        cls.anchor = cls.dll.fixtureAnchor
        cls.anchor.argtypes = [C.POINTER(Settings), C.c_uint32, C.c_void_p]
        cls.anchor.restype = C.c_int
        cls.ships = cls.dll.fixtureShips
        cls.ships.argtypes = [C.POINTER(SceneShip)]
        cls.ships.restype = C.c_uint32
        cls.bind = cls.dll.fixtureBind
        cls.bind.argtypes = [C.c_void_p, C.c_uint32, C.c_int32]
        cls.bind.restype = C.c_int
        cls.eligible = cls.dll.WorldSettingsStartingIslandEligible
        cls.eligible.argtypes = [C.c_uint32]
        cls.eligible.restype = C.c_int
        cls.serialize = cls.dll.fixtureSerialize
        cls.serialize.argtypes = [C.POINTER(Settings), C.c_void_p, C.c_uint32, C.c_void_p,
                                 C.c_uint32, C.c_void_p, C.c_void_p, C.c_uint32]
        cls.serialize.restype = C.c_int
        cls.certificate = cls.dll.fixtureCargoCertificate
        cls.certificate.argtypes = [C.c_void_p, C.c_void_p, C.c_uint32, C.c_float,
                                   C.c_float, C.c_void_p, C.c_uint32]
        cls.certificate.restype = C.c_int
        catalogue = (ROOT / 'legacy/world_settings' / PRIVATE / 'world_catalogue.h').read_text()
        cls.scenes = [bytes(int(v) for v in re.findall(r'\d+',
                      re.search(r'wsScene' + name + r'\[\]\s*=\s*\{(.*?)\};', catalogue, re.S)[1]))
                      for name in ('Easy', 'Medium', 'Hard')]

    def read_cargo(self, value, ship=0):
        goods, tons, raw = (C.c_uint16 * 8)(), (C.c_uint16 * 8)(), C.create_string_buffer(64)
        count = self.cargo(C.byref(value), ship, goods, tons, raw)
        return count, list(goods), list(tons), raw.raw

    def test_capacity_counts_distinct_50_ton_stacks(self):
        for fleet in (0, 2):
            value = settings(startingFleet=fleet, cargoMode=1, cargoTools=51, cargoWood=51, cargoFood=51)
            self.assertEqual(self.read_cargo(value)[0], 0)  #153 tons still needs six holds.
        value = settings(startingFleet=1, cargoMode=1, cargoTools=200, cargoWood=100, cargoFood=100)
        count, goods, tons, raw = self.read_cargo(value)
        self.assertEqual((count, goods, tons), (8, [41]*4+[42]*2+[26]*2, [50]*8))
        self.assertEqual(len(raw), 64)
        value.cargoFood += 1
        self.assertEqual(self.read_cargo(value)[0], 0)

    def test_custom_cargo_is_per_trade_ship_and_warships_stay_empty(self):
        for fleet in range(3):
            value = settings(startingFleet=fleet, cargoMode=1, cargoTools=25, cargoWood=75, cargoFood=40)
            for ship in range(1 if not fleet else 3):
                count, goods, tons, raw = self.read_cargo(value, ship)
                if fleet == 1 and ship:
                    self.assertEqual(count, 2)
                    self.assertEqual((goods, tons), ([0]*8, [0]*8))
                else:
                    self.assertEqual(goods[:4], [41, 42, 42, 26])
                    self.assertEqual(tons[:4], [25, 50, 25, 40])
                for at in range(count):
                    self.assertEqual(int.from_bytes(raw[at*8:at*8+2], 'little'), goods[at])
                    self.assertEqual(int.from_bytes(raw[at*8+2:at*8+4], 'little'), tons[at])
                    self.assertEqual(raw[at*8+4:at*8+8], b'\0'*4)

    def test_stock_fleet_cargo_is_preserved(self):
        for difficulty in range(3):
            for fleet in range(3):
                value = settings(difficulty=difficulty, startingFleet=fleet)
                count, goods, tons, _ = self.read_cargo(value)
                if fleet == 2:
                    self.assertEqual((goods[:2], tons[:2]), ([41, 42], [40, 40]))
                else:
                    self.assertEqual((goods[:4], tons[:4]), ([42, 26, 41, 41], [50, 10, 50, 30 if difficulty else 50]))

    def preferred(self, value, islands):
        array = (Island * len(islands))(*islands)
        xy, chosen, unchanged, error = (C.c_float * 2)(), C.c_int32(), C.c_uint32(), C.create_string_buffer(512)
        result = self.position(C.byref(value), array, len(array), xy, C.byref(chosen),
                               C.byref(unchanged), error, len(error))
        return result, tuple(xy), chosen.value, unchanged.value, error.value

    def test_preferred_start_changes_only_human_spawn_not_island_geometry(self):
        islands = [Island(id=0, x=64, y=64, width=128, height=128, climate=2)]
        locations = set()
        for difficulty in range(3):
            for fleet in range(3):
                result, xy, chosen, unchanged, error = self.preferred(
                    settings(difficulty=difficulty, startingFleet=fleet, startIsland=0), islands)
                self.assertEqual((result, chosen, unchanged, error), (1, 0, 1, b''))
                locations.add(xy)
                self.assertEqual(self.eligible(0), 1)
        self.assertEqual(len(locations), 1)

    def test_native_and_faction_islands_are_refused_without_map_mutation(self):
        for island in (Island(id=0, x=64, y=64, width=128, height=128, cultures=1),
                       Island(id=0, x=64, y=64, width=128, height=128, templateIndex=1)):
            result, _, _, unchanged, error = self.preferred(settings(startIsland=0), [island])
            self.assertEqual((result, unchanged), (0, 1))
            self.assertIn(b'uninhabited', error)
            self.assertEqual(self.eligible(0), 0)

    def test_climate_preference_and_no_coastal_space(self):
        islands = [Island(id=0, x=64, y=64, width=128, height=128, climate=0),
                   Island(id=1, x=64, y=300, width=128, height=128, climate=4)]
        self.assertEqual(self.preferred(settings(startClimate=4), islands)[2], 1)
        blocked = [Island(id=0, x=0, y=0, width=256, height=256, climate=2)]
        result, _, _, unchanged, error = self.preferred(settings(worldSize=256, startIsland=0), blocked)
        self.assertEqual((result, unchanged), (0, 1))
        self.assertIn(b'clear coastal', error)

    def read_fair(self, value, islands, replay=False):
        array = (Island * len(islands))(*islands)
        xy, chosen, owners = (C.c_float * 8)(), (C.c_int32 * 4)(), C.c_uint32()
        error = C.create_string_buffer(512)
        result = self.fair(C.byref(value), array, len(array), replay, xy, chosen,
                           C.byref(owners), error, len(error))
        return result, tuple(xy), tuple(chosen), owners.value, error.value

    @staticmethod
    def fair_islands():
        return [Island(id=i, x=x, y=y, width=128, height=128, templateIndex=template,
                       cropMask=0xf949, mineralMask=5, climate=2)
                for i, (x, y, template) in enumerate(((128, 128, 0), (128, 1280, 2),
                                                     (1280, 128, 3), (1280, 1280, 0)))]

    def test_fair_starts_are_distinct_safe_and_deterministic_with_resource_repair(self):
        value = settings(difficulty=1, worldSize=2048, fairStarts=1, aiCount=3,
                         startSeparation=2, startingFleet=2)
        islands = self.fair_islands()
        islands[0].mineralMask = 0
        first = self.read_fair(value, islands)
        self.assertEqual((first[0], first[3], first[4]), (1, 14, b''))
        self.assertEqual(len(set(first[2])), 4)
        self.assertEqual(first, self.read_fair(value, islands))
        # Start-time replay must retain its exact assignment even after the
        # basic-resource repair has added compatible iron/salt on one island.
        islands[0].mineralMask = 5
        changed = self.read_fair(value, islands, replay=True)
        self.assertEqual(changed, first)
        for a in range(4):
            for b in range(a):
                dx, dy = first[1][2*a]-first[1][2*b], first[1][2*a+1]-first[1][2*b+1]
                self.assertGreaterEqual(dx*dx+dy*dy, 1024**2)
        for island, owner in zip(first[2], range(4)):
            self.assertEqual(self.dll.WorldSettingsStartOwner(island), owner)

    def test_fair_start_respects_preferred_island_and_preserves_inactive_owner(self):
        value = settings(difficulty=1, worldSize=2048, fairStarts=1, aiCount=2,
                         startSeparation=1, startIsland=0, startingFleet=1)
        result, xy, chosen, mask, error = self.read_fair(value, self.fair_islands())
        self.assertEqual((result, chosen[0], chosen[3], mask, error), (1, 0, -1, 6, b''))
        self.assertEqual(xy[6:8], (1536.5, 1536.5))  # inactive owner3 keeps its stock anchor
        ships = (SceneShip * 32)()
        count = self.ships(ships)
        actual = [(ship.owner, ship.definition, ship.x, ship.y) for ship in ships[:count]]
        self.assertEqual([row[1] for row in actual if row[0] == 0], [1503, 1504, 1504])
        self.assertIn((3, 1502, 1536.5, 1536.5), actual)
        self.assertIn((4, 1502, 512.5, 1536.5), actual)
        for owner in (1, 2):
            self.assertIn((owner, 1502, xy[owner*2], xy[owner*2+1]), actual)
        for participant in range(3):
            anchor = C.c_uint32()
            self.assertEqual(self.anchor(C.byref(value), participant, C.byref(anchor)), 1)
            self.assertEqual(anchor.value, chosen[participant])
        anchor = C.c_uint32()
        self.assertEqual(self.anchor(C.byref(value), 3, C.byref(anchor)), 0)

    def test_impossible_separation_and_unfair_land_are_rejected(self):
        islands = self.fair_islands()
        value = settings(difficulty=1, worldSize=2048, fairStarts=1, aiCount=3, startSeparation=0)
        self.assertEqual(self.read_fair(value, islands)[0], 0)
        value.startSeparation = 2
        islands[3].templateIndex = 4  # 8,000 fertile tiles versus 2,000-3,000
        result = self.read_fair(value, islands)
        self.assertEqual(result[0], 0)
        self.assertIn(b'No fair starts', result[4])
        islands[3].templateIndex = 0
        islands[3].cultures = 1
        self.assertEqual(self.read_fair(value, islands)[0], 0)

    def test_fair_start_summary_and_single_player_island_choice(self):
        value = settings(worldSize=2048, fairStarts=1, aiCount=0)
        result = self.read_fair(value, self.fair_islands())
        self.assertEqual((result[0], result[2][0], result[3]), (1, 2, 0))
        summary = C.create_string_buffer(512)
        self.assertEqual(self.dll.WorldSettingsDescribeStarts(summary, len(summary)), 1)
        self.assertIn(b'estimated fertile area 3000', summary.value)
        value.startClimate = 0  # no suitable polar growing island in the fixture
        result = self.read_fair(value, self.fair_islands())
        self.assertEqual(result[0], 0)
        self.assertIn(b'preferred island/climate', result[4])

    def test_native_disaster_binding_changes_only_two_proven_bytes(self):
        for factions in range(4):
            for disasters in range(2):
                data = C.create_string_buffer(b'\xa5'*0xd0000)
                self.assertEqual(self.bind(data, factions, disasters), 1)
                actual = data.raw[:0xd0000]
                self.assertEqual(actual[:0xc7a78], b'\xa5'*0xc7a78)
                self.assertEqual(actual[0xc7a78:0xc7a7a], bytes((disasters, bool(factions & 1))))
                self.assertEqual(actual[0xc7a7a:], b'\xa5'*(0xd0000-0xc7a7a))
        for factions, disasters in ((4, 0), (0, -1), (0, 2)):
            data = C.create_string_buffer(b'\xa5'*0xd0000)
            before = data.raw
            self.assertEqual(self.bind(data, factions, disasters), 0)
            self.assertEqual(data.raw, before)
        self.assertEqual(self.bind(None, 0, 1), 0)

    def test_trade_good_ids_match_pinned_history_edition_dictionary(self):
        module = ROOT / '.local/game-copies/World Settings/AnnoGame.dll'
        if not module.is_file():
            self.skipTest('Optional licensed native dictionary input is unavailable')
        data = module.read_bytes()
        self.assertIn(hashlib.sha256(data).hexdigest(), {
            '06af5111316276c73efe9dde355b06c479fa36d617478722a9700c36225b15bf',
            'e6f01d19e8e16e6716c0a6c7d3ba00273c9df493e051b8ba62865ee4b53dfdea'})
        pe = PE(data)
        image_base, = pe.unpack('<Q', pe.optional + 24)
        for rva, code in ((0x19a6f, '488b8cc190340200'), (0x19a98, '488b8cc1b02d0200')):
            self.assertEqual(pe.read(rva, len(bytes.fromhex(code))), bytes.fromhex(code))
        for ident, table, expected in ((26, 0x23490, b'NAHRUNG'),
                                        (41, 0x22db0, b'WERKZEUG'),
                                        (42, 0x22db0, b'HOLZ')):
            address, = struct.unpack('<Q', pe.read(table + 8*ident, 8))
            self.assertEqual(pe.read(address-image_base, 64).split(b'\0')[0], expected)

    @staticmethod
    def fields(data, at=0):
        result = []
        while at < len(data):
            if len(data)-at < 8:
                raise AssertionError('Truncated native field')
            name = data[at:at+6].rstrip(b'\0').decode('ascii')
            size = int.from_bytes(data[at+6:at+8], 'little')
            header = 8
            if size >= 0xff00:
                size = ((size & 255) << 16) | int.from_bytes(data[at+8:at+10], 'little')
                header = 10
            if at+header+size > len(data):
                raise AssertionError('Native field crosses its parent')
            result.append((name, data[at+header:at+header+size]))
            at += header+size
        return result

    def serialized(self, value):
        source = self.scenes[value.difficulty]
        output, written, error = C.create_string_buffer(262144), C.c_uint32(), C.create_string_buffer(512)
        result = self.serialize(C.byref(value), source, len(source), output, len(output),
                                C.byref(written), error, len(error))
        self.assertEqual((result, error.value), (1, b''))
        data = output.raw[:written.value]
        records, at = [], 0
        while at < len(data):
            self.assertEqual(data[at:at+12].rstrip(b'\0'), b'SPIELER')
            size, = struct.unpack_from('<I', data, at+12)
            payload = data[at+16:at+16+size]
            self.assertEqual(len(payload), size)
            self.assertEqual(payload[:8], b'\0'*8)
            records.append(self.fields(payload, 8))
            at += 16+size
        return records

    def test_exact_original_scene_serialization_and_loaded_cargo_certificate(self):
        for difficulty in range(3):
            for fleet in range(3):
                for custom in range(2):
                    with self.subTest(difficulty=difficulty, fleet=fleet, custom=custom):
                        value = settings(difficulty=difficulty, startingFleet=fleet, startingMoney=100000,
                                         cargoMode=custom, cargoTools=60, cargoWood=30, cargoFood=20)
                        records = self.serialized(value)
                        heads = [payload for record in records for tag, payload in record if tag == 'HEAD']
                        self.assertEqual(len(heads), 1)
                        self.assertEqual(int.from_bytes(heads[0][4:8], 'little'), 100000)
                        boats = [(tag, payload) for record in records for tag, payload in record if tag in ('SCHIFF', 'SCHI64')]
                        self.assertEqual(len(boats), 1 if fleet == 0 else 3)
                        for index, (tag, payload) in enumerate(boats):
                            wide = tag == 'SCHI64'
                            definition, = struct.unpack_from('<H', payload, 4 if wide else 2)
                            self.assertEqual(definition, (1503 if fleet else 1502) if not index else (1504 if fleet == 1 else 1502))
                            x, y = struct.unpack_from('<ff', payload, 12 if wide else 8)
                            fields = dict(self.fields(payload, 20 if wide else 16))
                            holds = 8 if definition == 1503 else (2 if definition == 1504 else 4)
                            guns = 6 if fleet == 1 else 0
                            self.assertEqual(fields['HEAD'][8], guns)
                            cargo = fields['WAREN']
                            self.assertEqual(len(cargo), holds*8)
                            expected = [(0, 0)]*holds
                            if custom and definition != 1504:
                                expected[:4] = [(41, 50), (41, 10), (42, 30), (26, 20)]
                            elif fleet == 2:
                                expected[:2] = [(41, 40), (42, 40)]
                            elif index == 0:
                                expected[:4] = [(42, 50), (26, 10), (41, 50), (41, 30 if difficulty else 50)]
                            actual = [struct.unpack_from('<HHI', cargo, slot*8) for slot in range(holds)]
                            self.assertEqual(actual, [(good, tons, 0) for good, tons in expected])
                            # Reconstruct only the inspected native figure/ship fields
                            # from the serializer output; execute the actual loaded
                            # certificate and then corrupt one populated cargo slot.
                            ship, figure = bytearray(0x300), bytearray(0x120)
                            struct.pack_into('<HH', figure, 0xf2, 1337, 0)
                            struct.pack_into('<H', figure, 0xfa, 50*256)
                            figure[0xfe], figure[0x100] = holds, (0 if definition == 1502 else 6)
                            struct.pack_into('<H', ship, 0xc0, 1337)
                            ship[0xce] = guns
                            for slot, (good, tons) in enumerate(expected):
                                ship[0x148+slot*24+8] = good
                                struct.pack_into('<H', ship, 0x148+slot*24+10, tons*256)
                            native_ship, native_figure = C.create_string_buffer(bytes(ship)), C.create_string_buffer(bytes(figure))
                            error = C.create_string_buffer(512)
                            self.assertEqual(self.certificate(native_ship, native_figure, definition, x, y, error, len(error)), 1, error.value)
                            native_ship[0x148+10] = bytes([1])
                            self.assertEqual(self.certificate(native_ship, native_figure, definition, x, y, error, len(error)), 0)
                            self.assertIn(b'cargo differs', error.value)


if __name__ == '__main__':
    unittest.main()
