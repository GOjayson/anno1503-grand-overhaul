"""Verify the optional visibility transform and native adapter in synthetic memory."""

import ctypes
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from anno1503_overhaul.world_options import PRIVATE
from anno1503_overhaul.world_options_visibility_hooks import INSTALLER
from anno1503_overhaul.world_settings_multiplayer_visibility import apply_multiplayer_visibility
from test_world_visibility_native import FIXTURE, NATIVE, ROOT


def staged_visibility_sources():
    files = {PRIVATE + path.name: path.read_bytes() for path in NATIVE.glob("start_visibility*.inc")}
    files[PRIVATE + "WorldSettings.c"] = b"/* Existing native chooser. */\n"
    files[INSTALLER] = b"/* Existing reviewed installer. */\n"
    return files


def add_visibility(files, *, peaceful_ai=False):
    apply_multiplayer_visibility(files, frame_sha256="ab" * 32,
                                 display_sha256="cd" * 32, scene_sha256="fe" * 32,
                                 peaceful_ai=peaceful_ai)


class MultiplayerVisibilityStagingTests(unittest.TestCase):
    def test_changes_only_opt_in_stage(self):
        original = staged_visibility_sources()
        companion = dict(original)
        add_visibility(companion)
        self.assertEqual(original, staged_visibility_sources())
        self.assertTrue(companion[PRIVATE + "WorldSettings.c"].startswith(b"#define WS_MULTIPLAYER_VISIBILITY 1\n"))
        install_name = INSTALLER.rsplit("/", 1)[0] + "/visibility_multiplayer_install.inc"
        self.assertIn(b"wsMpSceneSha[32]={0xfe,0xfe,", companion[install_name])
        self.assertNotIn(b"#define WS_MP_HAS_WORLD_PIN", companion[install_name])
        self.assertNotIn(PRIVATE + "peaceful_ai.inc", companion)

    def test_adds_derived_world_pin_only_to_multiplayer_loader(self):
        companion = staged_visibility_sources()
        native_pins = INSTALLER.rsplit("/", 1)[0] + "/visibility_native_pins.h"
        companion[native_pins] = b"/* Reviewed single-player pins. */\n"
        apply_multiplayer_visibility(companion, frame_sha256="ab" * 32,
                                     display_sha256="cd" * 32, world_sha256="ef" * 32)
        install_name = INSTALLER.rsplit("/", 1)[0] + "/visibility_multiplayer_install.inc"
        self.assertIn(b"wsMpWorldSha[32]={0xef,0xef,", companion[install_name])
        self.assertIn(b"#define WS_MP_HAS_WORLD_PIN 1", companion[install_name])
        self.assertEqual(companion[native_pins], b"/* Reviewed single-player pins. */\n")

    def test_rejects_unreviewable_pins_before_staging(self):
        original = staged_visibility_sources()
        companion = dict(original)
        for module in ("Scene", "World"):
            with self.subTest(module=module), self.assertRaisesRegex(ValueError, f"{module} pin"):
                apply_multiplayer_visibility(companion, frame_sha256="ab" * 32, display_sha256="cd" * 32,
                                             **{f"{module.lower()}_sha256": "malformed"})
        self.assertEqual(original, companion)


NATIVE_CASES = r'''
#include "start_visibility_exploration.inc"
static unsigned char matchFrame[0x60], lockstep[0x28], differentWorld[sizeof worldBytes];

static uint32_t projectedActivity;
static void spyActivityTiles(void *world, const void *row, uint32_t quadrant, uint32_t flags, void *result)
{
    (void)world;
    (void)row;
    (void)quadrant;
    (void)result;
    projectedActivity = flags;
}

static uint32_t spyActivityProperty(void *world, uint32_t property)
{
    (void)world;
    return property;
}

static uint8_t peacefulController[0xab8];
static uint32_t peacefulCalls;
static uintptr_t spyDiplomacy(void *world, uint32_t relation, uint32_t state, void *source, void *target)
{
    (void)world;
    (void)relation;
    (void)state;
    (void)source;
    (void)target;
    peacefulCalls++;
    return 0x7254u;
}

__declspec(dllexport) int multiplayerPeacefulAI(void)
{
    prepare(0, 0);
    ptr(worldBytes, moduleBytes + 0xff650);
    ptr(worldBytes + 0x210, players);
    ptr(players, moduleBytes + 0xfdbc0);
    ptr(players + 8, humanBytes);
    ptr(players + 16, enemyBytes);
    ptr(humanBytes, moduleBytes + 0xfabe0);
    ptr(enemyBytes, moduleBytes + 0xfabe0);
    ptr(humanBytes + 0x10, worldBytes);
    ptr(enemyBytes + 0x10, worldBytes);
    wsPut32(humanBytes + 8, 0);
    wsPut32(enemyBytes + 8, 1);
    wsPut16(humanBytes + 0x9c, 8);
    wsPut16(enemyBytes + 0x9c, 12);
    memset(peacefulController, 0, sizeof peacefulController);
    ptr(peacefulController, moduleBytes + 0x88128);
    ptr(peacefulController + 8, worldBytes);
    wsPut32(peacefulController + 0xa4c, 12);
    wsPut16(peacefulController + 0xa64, 1);
    ptr(enemyBytes + 0x18, peacefulController);
    memcpy(worldBytes + 0x6e4c, "WSMPAI0!", 8);
    peacefulCalls = 0;

    WorldSettingsSetMultiplayerVisibility(wsVisibilityEncode(1, 0));
    unsigned char before[sizeof enemyBytes];
    memcpy(before, enemyBytes, sizeof before);
    int result = 0;
    for (uint32_t i = 0; i < 64; ++i) {
        if (WorldSettingsMultiplayerPeacefulDiplomacy(worldBytes, 2, 3, enemyBytes, humanBytes) || peacefulCalls) {
            result = 1;
            goto done;
        }
    }
    if (memcmp(before, enemyBytes, sizeof before)) {result = 2;goto done;}
    uintptr_t accepted = 0x7254u;
    if (WorldSettingsMultiplayerPeacefulDiplomacy(worldBytes, 2, 3, humanBytes, enemyBytes) != accepted ||
        WorldSettingsMultiplayerPeacefulDiplomacy(worldBytes, 2, 1, enemyBytes, humanBytes) != accepted ||
        WorldSettingsMultiplayerPeacefulDiplomacy(worldBytes, 1, 3, enemyBytes, humanBytes) != accepted) {
        result = 3;
        goto done;
    }
    enemyBytes[0x1da] = 3;
    if (WorldSettingsMultiplayerPeacefulDiplomacy(worldBytes, 2, 3, enemyBytes, humanBytes) != accepted) {
        result = 4;
        goto done;
    }
    enemyBytes[0x1da] = 0;
    for (uint16_t kind = 13; kind <= 16; ++kind) {
        wsPut16(enemyBytes + 0x9c, kind);
        if (WorldSettingsMultiplayerPeacefulDiplomacy(worldBytes, 2, 3, enemyBytes, humanBytes) != accepted) {
            result = 5;
            goto done;
        }
    }
    wsPut16(enemyBytes + 0x9c, 12);
    ptr(worldBytes, moduleBytes + 0xff1d8);
    if (wsMpDenyNewWar(worldBytes, 2, 3, enemyBytes, humanBytes)) {result = 6;goto done;}
    ptr(worldBytes, moduleBytes + 0xff650);
    worldBytes[0x6e4c] = 0;
    if (wsMpDenyNewWar(worldBytes, 2, 3, enemyBytes, humanBytes)) {result = 7;goto done;}
    worldBytes[0x6e4c] = 'W';
    WorldSettingsDisableMultiplayerVisibility();
    if (wsMpDenyNewWar(worldBytes, 2, 3, enemyBytes, humanBytes) || peacefulCalls != 8u)
        result = 8;
done:
    WorldSettingsDisableMultiplayerVisibility();
    return result;
}

static HWND multiplayerFrame(uint32_t seat)
{
    memset(matchFrame, 0, sizeof matchFrame);
    memset(lockstep, 0, sizeof lockstep);
    wsPut32(worldBytes + 0x1e4, seat);
    wsPut32(humanBytes + 8, seat);
    ptr(players + 8, NULL);
    ptr(players + 8 + seat * 8, humanBytes);
    ptr(matchFrame, moduleBytes + 0xa1788);
    ptr(matchFrame + 0x28, worldBytes);
    ptr(matchFrame + 0x40, lockstep);
    ptr(matchFrame + 0x48, humanBytes);
    ptr(lockstep, moduleBytes + 0xa7418);
    ptr(lockstep + 0x10, worldBytes);
    ptr(lockstep + 0x18, matchFrame);
    HWND window = CreateWindowExW(0, L"STATIC", L"", WS_OVERLAPPED,
        0, 0, 16, 16, NULL, NULL, GetModuleHandleW(NULL), NULL);
    if (window) SetWindowLongPtrW(window, GWLP_USERDATA, (LONG_PTR)matchFrame);
    return window;
}

__declspec(dllexport) int multiplayerDraw(uint32_t seat, uint16_t discovery, uint32_t map, uint32_t activity)
{
    unsigned char beforeWorld[sizeof worldBytes], beforeIsland[sizeof islandBytes];
    prepare(0, discovery);
    HWND window = multiplayerFrame(seat);
    if (!window) return 1;
    int result = 0;
    if (!WorldSettingsSetMultiplayerVisibility(wsVisibilityEncode(map, activity))) {result = 2;goto done;}
    memcpy(beforeWorld, worldBytes, sizeof worldBytes);
    memcpy(beforeIsland, islandBytes, sizeof islandBytes);
    spyMasked = !map && !(discovery & (1u << seat));
    if (WorldSettingsVisibilityDrawTerrain(worldBytes, listBytes, 17, 29, drawRendererBytes) != 0x1234u ||
        spyFailure || spyRefreshCalls || listBytes[8 + 0x4d] != 1u || listBytes[8 + 0x50] != 0xa5u) {
        result = 3;
        goto done;
    }
    if (memcmp(beforeWorld, worldBytes, sizeof worldBytes) || memcmp(beforeIsland, islandBytes, sizeof islandBytes) ||
        !wsChartActive.bits || wsChartActive.viewer != seat || spyChartProducerCalls) {
        result = 4;
        goto done;
    }
    unsigned char *bytes = NULL;
    uint32_t size = 0;
    if (wsVisibilityChartSaveBlob(&bytes, &size, NULL, 0) || bytes || size) {
        free(bytes);
        result = 5;
    }
    uint64_t drawn = WorldSettingsMultiplayerVisibilityView();
    uint32_t expected = (activity << 24) | ((discovery >> seat & 1u) << 16) | (map << 8) | (seat + 1u);
    if (!result && ((uint32_t)drawn != expected || !(drawn >> 32))) result = 6;
done:
    WorldSettingsDisableMultiplayerVisibility();
    if (!result && WorldSettingsMultiplayerVisibilityView()) result = 7;
    DestroyWindow(window);
    return result;
}

__declspec(dllexport) int multiplayerRevealActivity(void)
{
    prepare(0, 0);
    HWND window = multiplayerFrame(7);
    if (!window) return 1;
    ptr(moduleBytes + 0xff1d8u + 0xf0u, spyActivityProperty);
    ptr(moduleBytes + 0xff650u + 0xf0u, spyActivityProperty);
    memcpy(differentWorld, worldBytes, sizeof differentWorld);
    unsigned char originalWorld[sizeof worldBytes], originalTiles[sizeof physicalTiles];
    memcpy(originalWorld, worldBytes, sizeof originalWorld);
    memcpy(originalTiles, physicalTiles, sizeof originalTiles);

    int result = 0;
    WorldSettingsSetMultiplayerVisibility(wsVisibilityEncode(1, 0));
    WorldSettingsVisibilityProjectActivityTiles(worldBytes, listBytes, 0, 1, quadBytes);
    if (projectedActivity != 1u || WorldSettingsVisibilityActivityMinimapProperty(worldBytes, 5) != 5u) {
        result = 2;
        goto done;
    }
    WorldSettingsSetMultiplayerVisibility(wsVisibilityEncode(1, 1));
    WorldSettingsVisibilityProjectActivityTiles(worldBytes, listBytes, 0, 0, quadBytes);
    if (projectedActivity != WS_MP_REVEAL_ACTIVITY || WorldSettingsVisibilityActivityMinimapProperty(worldBytes, 5) ||
        WorldSettingsVisibilityActivityMinimapProperty(worldBytes, 6) != 6u) {
        result = 3;
        goto done;
    }
    WorldSettingsVisibilityProjectActivityTiles(worldBytes, listBytes, 0, 1, quadBytes);
    if (projectedActivity != (WS_MP_REVEAL_ACTIVITY | 1u)) {
        result = 6;
        goto done;
    }
    WorldSettingsVisibilityProjectActivityTiles(differentWorld, listBytes, 0, 0, quadBytes);
    if (projectedActivity || WorldSettingsVisibilityActivityMinimapProperty(differentWorld, 5) != 5u) {
        result = 4;
        goto done;
    }
    WorldSettingsDisableMultiplayerVisibility();
    WorldSettingsVisibilityProjectActivityTiles(worldBytes, listBytes, 0, 0, quadBytes);
    if (projectedActivity || memcmp(originalWorld, worldBytes, sizeof originalWorld) ||
        memcmp(originalTiles, physicalTiles, sizeof originalTiles))
        result = 5;
done:
    WorldSettingsDisableMultiplayerVisibility();
    DestroyWindow(window);
    return result;
}

__declspec(dllexport) int multiplayerIdentity(void)
{
    prepare(0, 1u);
    HWND window = multiplayerFrame(7);
    if (!window) return 1;
    int result = 0;
    WSVisibilityWorld view;
    WorldSettingsSetMultiplayerVisibility(wsVisibilityEncode(0, 0));
    wsPut32(worldBytes + 0x1e4, 0u);
    if (!wsVisibilityWorldRead(worldBytes, &view) || !view.multiplayerWithheld) {result = 2;goto done;}
    wsPut32(worldBytes + 0x1e4, 7u);
    ptr(players + 8 + 7 * 8, enemyBytes);
    if (!wsVisibilityWorldRead(worldBytes, &view) || !view.multiplayerWithheld) {result = 3;goto done;}
    ptr(players + 8 + 7 * 8, humanBytes);
    if (!wsVisibilityWorldRead(worldBytes, &view) || !view.marked || view.multiplayerPlayer != humanBytes) {
        result = 4;
        goto done;
    }
    uint32_t generation = view.multiplayerGeneration;
    wsPut32(worldBytes + 0x1e4, 31u);
    if (wsVisibilityWorldRead(worldBytes, &view) || !wsMultiplayerWorldWithheld(worldBytes)) {
        result = 14;goto done;
    }
    wsPut32(worldBytes + 0x1e4, 7u);
    if (!wsVisibilityWorldRead(worldBytes, &view) || view.marked != 1 || view.multiplayerGeneration != generation) {
        result = 15;goto done;
    }
    worldBytes[0x6e4c] = 1;
    if (!wsVisibilityWorldRead(worldBytes, &view) || !view.multiplayerWithheld) {result = 5;goto done;}
    worldBytes[0x6e4c] = 0;
    if (!wsVisibilityWorldRead(worldBytes, &view) || view.marked != 1 || view.multiplayerGeneration != generation) {
        result = 6;
        goto done;
    }
    WorldSettingsSetMultiplayerVisibility(wsVisibilityEncode(0, 0));
    if (!wsVisibilityWorldRead(worldBytes, &view) || !view.marked || view.multiplayerGeneration == generation) {
        result = 7;
        goto done;
    }
    memcpy(differentWorld, worldBytes, sizeof differentWorld);
    if (!wsVisibilityWorldRead(differentWorld, &view) || view.marked ||
        !wsVisibilityWorldRead(worldBytes, &view) || !view.marked) {result = 8;goto done;}
    ptr(humanBytes + 0x10, differentWorld);
    if (!wsVisibilityWorldRead(differentWorld, &view) || view.marked) {result = 9;goto done;}
    if (!wsVisibilityWorldRead(worldBytes, &view) || !view.multiplayerWithheld) {result = 10;goto done;}
    ptr(humanBytes + 0x10, worldBytes);
    if (!wsVisibilityWorldRead(worldBytes, &view) || view.marked != 1) {result = 11;goto done;}
    ptr(lockstep + 0x18, NULL);
    if (!wsVisibilityWorldRead(differentWorld, &view) || view.marked || wsMultiplayerWorldWithheld(worldBytes)) {
        result = 12;
        goto done;
    }
    WorldSettingsDisableMultiplayerVisibility();
    if (!wsVisibilityWorldRead(worldBytes, &view) || view.marked) result = 13;
done:
    WorldSettingsDisableMultiplayerVisibility();
    DestroyWindow(window);
    return result;
}

static DWORD WINAPI multiplayerOffThread(void *ignored)
{
    (void)ignored;
    WSVisibilityWorld view;
    return !wsVisibilityWorldRead(worldBytes, &view) || !view.multiplayerWithheld ||
        WorldSettingsVisibilityDrawTerrain(worldBytes, listBytes, 17, 29, drawRendererBytes) != 0;
}

__declspec(dllexport) int multiplayerReload(uint32_t seat, uint32_t reuseWorld)
{
    prepare(0, 1u);
    HWND window = multiplayerFrame(seat);
    if (!window) return 1;
    int result = 0;
    WSVisibilityWorld view;
    WorldSettingsSetMultiplayerVisibility(wsVisibilityEncode(0, 1));
    spyMasked = seat != 0;
    if (WorldSettingsVisibilityDrawTerrain(worldBytes, listBytes, 17, 29, drawRendererBytes) != 0x1234u ||
        !wsVisibilityWorldRead(worldBytes, &view) || !view.multiplayerPlayer ||
        !wsChartCoreMark(&wsChartActive, 225, 225, 225, 225) || !wsChartCorePoint(&wsChartActive, 225, 225)) {
        result = 2;
        goto done;
    }
    uint32_t generation = view.multiplayerGeneration;
    uint64_t drawn = WorldSettingsMultiplayerVisibilityView();
    unsigned char *world = reuseWorld ? worldBytes : differentWorld;
    if (!reuseWorld) memcpy(world, worldBytes, sizeof differentWorld);
    memset(enemyBytes, 0, sizeof enemyBytes);
    ptr(enemyBytes, moduleBytes + 0xfabe0);
    wsPut32(enemyBytes + 8, seat);
    ptr(enemyBytes + 0x10, world);
    ptr(lockstep + 0x10, world);
    ptr(matchFrame + 0x48, enemyBytes);
    ptr(players + 8 + seat * 8, enemyBytes);
    if (WorldSettingsMultiplayerFinishReload(world) != 1 || WorldSettingsMultiplayerVisibilityView() != drawn ||
        !wsVisibilityWorldRead(world, &view) || view.multiplayerPlayer || !wsMultiplayerUsesRenderer(drawRendererBytes)) {
        result = 3;
        goto done;
    }

    world[0x6e4c] = 1;
    if (WorldSettingsMultiplayerFinishReload(lockstep) != 1 || WorldSettingsMultiplayerVisibilityView() ||
        !wsVisibilityWorldRead(world, &view) || !view.multiplayerWithheld || view.multiplayerPlayer) {
        result = 4;
        goto done;
    }
    if (wsMultiplayerRevealActivity(world)) {result = 11;goto done;}
    world[0x6e4c] = 0;
    wsPut32(world + 0x1e4, seat ^ 7u);
    if (!wsVisibilityWorldRead(world, &view) || !view.multiplayerWithheld || view.multiplayerPlayer) {
        result = 5;
        goto done;
    }
    wsPut32(world + 0x1e4, seat);
    ptr(players + 8 + seat * 8, humanBytes);
    if (!wsVisibilityWorldRead(world, &view) || !view.multiplayerWithheld || view.multiplayerPlayer) {
        result = 6;
        goto done;
    }
    ptr(players + 8 + seat * 8, enemyBytes);
    ptr(islandBytes + 0x38, world);
    if (!reuseWorld && (!wsVisibilityWorldRead(world, &view) || !view.multiplayerWithheld)) {
        result = 10;
        goto done;
    }
    ptr(matchFrame + 0x28, world);
    if (!wsVisibilityWorldRead(world, &view) || view.multiplayerWithheld || view.multiplayerPlayer != enemyBytes ||
        view.multiplayerGeneration == generation || view.viewer != seat || view.map != 0 || view.enemy != 1 ||
        !wsVisibilityChartEnsure(&view) || wsChartCorePoint(&wsChartActive, 225, 225)) {
        result = 7;
        goto done;
    }
    if (!(wsMultiplayerWorldWithheld(world) && (reuseWorld || !wsMultiplayerWorldWithheld(worldBytes))) ||
        wsU16(islandBytes + 0x12e) != 1u || wsU32(world + 0x6eec) != 0x86u)
        result = 8;
    WSVisibilityDrawContext context;
    if (!result && wsVisibilityContextRead(&view, &context)) {
        wsMultiplayerVisibilityDrawn(&context);
        const uint64_t expected = ((uint64_t)view.multiplayerGeneration << 32) |
            (1u << 24) | ((seat == 0) << 16) | (seat + 1u);
        if (WorldSettingsMultiplayerVisibilityView() != expected) result = 9;
    } else if (!result) {
        result = 9;
    }
done:
    WorldSettingsDisableMultiplayerVisibility();
    DestroyWindow(window);
    return result;
}

static void multiplayerSurface(void *world, unsigned char *frame, unsigned char *surface,
    unsigned char *parent, uint32_t *pixels)
{
    ptr(frame + 8, drawRendererBytes);
    ptr(frame + 0x18, world);
    wsPut32(drawRendererBytes + 0x460, 4);
    wsPut32(drawRendererBytes + 0x464, 4);
    wsPut32(drawRendererBytes + 0x498, 2);
    ptr(drawRendererBytes + 0x4b0, surface);
    ptr(moduleBytes + 0xf63740 + 0x118, moduleBytes + 0x483e0);
    ptr(surface, moduleBytes + 0xf653a0);
    ptr(moduleBytes + 0xf653a0 + 0xa8, moduleBytes + 0x5e550);
    ptr(moduleBytes + 0xf653a0 + 0xb0, moduleBytes + 0x5e560);
    ptr(moduleBytes + 0xf653a0 + 0xb8, moduleBytes + 0x5e570);
    ptr(moduleBytes + 0xf653a0 + 0x108, moduleBytes + 0x5ea70);
    ptr(surface + 8, parent);
    ptr(surface + 0x10, pixels);
    wsPut16(surface + 0x18, 4);
    wsPut16(surface + 0x1a, 4);
    wsPut32(surface + 0x1c, 5);
    wsPut32(surface + 0x20, 0x20080808);
    wsPut32(parent + 0x28, 4);
    wsPut32(parent + 0x2c, 4);
    wsPut32(parent + 0x44, 20);
    ptr(parent + 0x48, pixels);
}

__declspec(dllexport) int multiplayerWithhold(uint32_t wrongWorld)
{
    prepare(0, 1u);
    HWND window = NULL;
    int result = 0;
    unsigned char frame[0x20] = {0}, surface[0x80] = {0}, parent[0x50] = {0};
    uint32_t pixels[20];
    for (size_t i = 0; i < sizeof pixels / sizeof pixels[0]; ++i) pixels[i] = 0xffabcdefu;
    WorldSettingsSetMultiplayerVisibility(wsVisibilityEncode(1, 0));
    if (wrongWorld) {
        window = multiplayerFrame(7);
        if (!window || WorldSettingsVisibilityDrawTerrain(worldBytes, listBytes, 17, 29, drawRendererBytes) != 0x1234u) {
            result = 1;
            goto done;
        }
        memcpy(differentWorld, worldBytes, sizeof differentWorld);
    } else {
        DWORD resultCode = 1;
        HANDLE thread = CreateThread(NULL, 0, multiplayerOffThread, NULL, 0, NULL);
        if (!thread) {result = 2;goto done;}
        WaitForSingleObject(thread, INFINITE);
        GetExitCodeThread(thread, &resultCode);
        CloseHandle(thread);
        if (resultCode) {result = 2;goto done;}
        if (WorldSettingsVisibilityCreateMap(mapBytes, 0, tableBytes) || spyCalls) {result = 3;goto done;}
        for (size_t i = 0; i < sizeof pixelBytes; ++i)
            if (pixelBytes[i] != 0x90u) {result = 4;goto done;}
    }
    unsigned char *world = wrongWorld ? differentWorld : worldBytes;
    uint32_t calls = spyCalls;
    if (WorldSettingsVisibilityDrawTerrain(world, listBytes, 17, 29, drawRendererBytes) || spyCalls != calls) {
        result = 5;
        goto done;
    }
    multiplayerSurface(world, frame, surface, parent, pixels);
    if (!wsVisibilityExplorationPreflight(drawRendererBytes, frame) ||
        !wsVisibilityApplyExploredSea(drawRendererBytes, frame)) {result = 6;goto done;}
    for (size_t i = 0; i < sizeof pixels / sizeof pixels[0]; ++i)
        if (pixels[i] != (i % 5 == 4 ? 0xffabcdefu : 0xff000000u)) {result = 7;goto done;}
    if (wrongWorld) ptr(lockstep + 0x18, NULL);
    else WorldSettingsDisableMultiplayerVisibility();
    pixels[0] = 0xffabcdefu;
    if (!wsVisibilityApplyExploredSea(drawRendererBytes, frame) || pixels[0] != 0xffabcdefu)
        result = 8;
done:
    WorldSettingsDisableMultiplayerVisibility();
    if (window) DestroyWindow(window);
    return result;
}

__declspec(dllexport) int multiplayerIncompleteDiscovery(void)
{
    prepare(0, 0x0081u);
    HWND window = multiplayerFrame(7);
    if (!window) return 1;
    WSVisibilityWorld view;
    WorldSettingsSetMultiplayerVisibility(wsVisibilityEncode(2, 0));
    int result = !wsVisibilityWorldRead(worldBytes, &view) || !view.multiplayerWithheld ||
        WorldSettingsVisibilityDrawTerrain(worldBytes, listBytes, 17, 29, drawRendererBytes) ||
        WorldSettingsMultiplayerVisibilityView();
    uint16_t known;
    memcpy(&known, islandBytes + 0x12e, sizeof known);
    WorldSettingsDisableMultiplayerVisibility();
    DestroyWindow(window);
    return result || known != 0x0081u;
}

__declspec(dllexport) int multiplayerRevealedMinimap(uint32_t seat, uint32_t mode, uint32_t nativeUpdate)
{
    const uint16_t discovery = mode == 2 ? 0x381u : 0;
    prepare(0, discovery);
    ptr(worldBytes + 0x220, mapBytes);
    WorldSettingsSetMultiplayerVisibility(wsVisibilityEncode(mode, 1));
    int result = 0;
    HWND window = NULL;
    if (WorldSettingsVisibilityCreateMap(mapBytes, 0, tableBytes) || spyCalls || pixelBytes[300] != 0x90u) {
        result = 1;
        goto done;
    }
    window = multiplayerFrame(seat);
    if (!window) {result = 2;goto done;}
    unsigned char before[sizeof worldBytes];
    memcpy(before, worldBytes, sizeof before);
    spyMapPartial = 1;
    spyMapOwnerColor = 5;
    if (nativeUpdate) {
        if (WorldSettingsVisibilityCreateMap(mapBytes, 0, tableBytes) != 0x1236u) {result = 3;goto done;}
    } else if (WorldSettingsVisibilityDrawTerrain(worldBytes, listBytes, 17, 29, drawRendererBytes) != 0x1234u) {
        result = 3;
        goto done;
    }
    const uint32_t firstCalls = nativeUpdate ? 1u : 2u;
    if (spyCalls != firstCalls || spyMapFlags != 3 || spyMapHeightPixels != sizeof pixelBytes || pixelBytes[300] != 0x5bu ||
        spyMapRect[0] || spyMapRect[1] || spyMapRect[2] != 256 || spyMapRect[3] != 256 || spyFailure) {
        result = 4;
        goto done;
    }
    if (WorldSettingsVisibilityDrawTerrain(worldBytes, listBytes, 17, 29, drawRendererBytes) != 0x1234u ||
        spyCalls != firstCalls + 1u || spyMapHeightPixels != sizeof pixelBytes) {
        result = 5;
        goto done;
    }
    (void)WorldSettingsMultiplayerFinishReload(lockstep);
    if (WorldSettingsVisibilityDrawTerrain(worldBytes, listBytes, 17, 29, drawRendererBytes) != 0x1234u ||
        spyCalls != firstCalls + 3u || spyMapFlags != 3 || spyMapHeightPixels != 2u * sizeof pixelBytes) {
        result = 6;
        goto done;
    }
    if (memcmp(worldBytes, before, sizeof before) || wsU16(islandBytes + 0x12e) != discovery || spyRefreshCalls)
        result = 7;
done:
    WorldSettingsDisableMultiplayerVisibility();
    if (window) DestroyWindow(window);
    return result;
}

__declspec(dllexport) int multiplayerSight(uint32_t map)
{
    prepare(0, map == 2 ? 0x0381u : 1u);
    HWND window = multiplayerFrame(7);
    if (!window) return 1;
    int result = 0;
    WSVisibilityWorld view;
    WSVisibilityDrawContext *context = calloc(1, sizeof *context);
    const WSVisibilityActorLayout *ship = wsVisibilityActorLayout(humanShip, moduleBytes);
    WorldSettingsSetMultiplayerVisibility(wsVisibilityEncode(map, 0));
    if (!context || !ship || !wsVisibilityWorldRead(worldBytes, &view) ||
        !wsVisibilityContextRead(&view, context) || context->human != humanBytes || context->visionCount != 1) {
        result = 2;
        goto done;
    }
    if (wsVisibilityActorValuesInContext(context, ship, 220.0f, 220.0f, enemyBytes) ||
        !wsVisibilityActorValuesInContext(context, ship, 132.0f, 128.0f, enemyBytes) ||
        !wsVisibilityActorValuesInContext(context, ship, 220.0f, 220.0f, humanBytes))
        result = 3;
done:
    free(context);
    WorldSettingsDisableMultiplayerVisibility();
    DestroyWindow(window);
    return result;
}
'''


@unittest.skipUnless(os.name == "nt", "Requires a synthetic native Windows rendering fixture.")
class MultiplayerVisibilityNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configured = os.environ.get("ANNO_VISIBILITY_TEST_ZIG")
        zig = Path(configured) if configured else ROOT / ".local/toolchain/ziglang/zig.exe"
        if not zig.is_file():
            raise unittest.SkipTest("Reviewed native compiler unavailable.")
        temporary = TemporaryDirectory(prefix="anno-multiplayer-visibility-")
        cls.addClassCleanup(temporary.cleanup)
        folder = Path(temporary.name)
        files = staged_visibility_sources()
        add_visibility(files, peaceful_ai=True)
        for path, source in files.items():
            if path.startswith(PRIVATE) and path.endswith(".inc"):
                (folder / Path(path).name).write_bytes(source)
        source = folder / "fixture.c"
        fixture = FIXTURE.replace('#include "start_visibility_runtime.inc"', r'''
static void spyActivityTiles(void *, const void *, uint32_t, uint32_t, void *);
static uintptr_t spyDiplomacy(void *, uint32_t, uint32_t, void *, void *);
#define WS_MP_NATIVE_ACTIVITY_TILES(module) spyActivityTiles
#define WS_MP_NATIVE_ACTIVITY_PROPERTY(target) ((WSVisibilityNativeActivityProperty)(target))
#define WS_MP_NATIVE_DIPLOMACY(module) spyDiplomacy
#include "start_visibility_runtime.inc"
''')
        source.write_text(fixture + NATIVE_CASES, encoding="utf-8")
        runtime = folder / "fixture.dll"
        result = subprocess.run([str(zig), "cc", "-std=c11", "-target", "x86_64-windows-gnu",
                                 "-shared", "-O2", "-Wall", "-Wextra", "-Werror", "-I", str(NATIVE),
                                 str(source), "-luser32", "-o", str(runtime)], capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.native = ctypes.CDLL(str(runtime))
        import _ctypes
        cls.addClassCleanup(_ctypes.FreeLibrary, cls.native._handle)
        cls.native.multiplayerDraw.argtypes = [ctypes.c_uint32, ctypes.c_uint16, ctypes.c_uint32, ctypes.c_uint32]
        cls.native.multiplayerRevealActivity.argtypes = []
        cls.native.multiplayerPeacefulAI.argtypes = []
        cls.native.multiplayerIdentity.argtypes = []
        cls.native.multiplayerReload.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
        cls.native.multiplayerIncompleteDiscovery.argtypes = []
        cls.native.multiplayerRevealedMinimap.argtypes = [ctypes.c_uint32] * 3
        cls.native.multiplayerSight.argtypes = [ctypes.c_uint32]
        cls.native.multiplayerWithhold.argtypes = [ctypes.c_uint32]

    def test_same_discovery_bits_produce_different_local_draws(self):
        for seat, discovery, map_mode in ((0, 1, 0), (7, 1, 0), (0, 128, 0), (7, 128, 0), (7, 0, 1)):
            with self.subTest(seat=seat, discovery=discovery, map_mode=map_mode):
                self.assertEqual(self.native.multiplayerDraw(seat, discovery, map_mode, 0), 0)

    def test_reveal_activity_uses_only_the_bound_world_and_keeps_unexplored_terrain_hidden(self):
        self.assertEqual(self.native.multiplayerRevealActivity(), 0)
        for seat, discovery in ((0, 1), (7, 1), (0, 128), (7, 128)):
            with self.subTest(seat=seat, discovery=discovery):
                self.assertEqual(self.native.multiplayerDraw(seat, discovery, 0, 1), 0)

    def test_peaceful_authority_leaves_existing_relations_and_other_owners_on_stock_path(self):
        self.assertEqual(self.native.multiplayerPeacefulAI(), 0)

    def test_requires_matching_viewer_and_world_membership_and_retires_ended_match(self):
        self.assertEqual(self.native.multiplayerIdentity(), 0)

    def test_native_reload_rebinds_only_the_verified_seat_and_resets_the_old_chart(self):
        for seat in (0, 7):
            for reuse_world in (0, 1):
                with self.subTest(seat=seat, reuse_world=reuse_world):
                    self.assertEqual(self.native.multiplayerReload(seat, reuse_world), 0)

    def test_fully_explored_requires_all_human_discovery_and_keeps_world_read_only(self):
        for seat in (0, 7):
            with self.subTest(seat=seat):
                for activity in (0, 1):
                    self.assertEqual(self.native.multiplayerDraw(seat, 0x0381, 2, activity), 0)
        self.assertEqual(self.native.multiplayerIncompleteDiscovery(), 0)

    def test_revealed_minimap_recovers_once_after_withholding_and_reload(self):
        for seat, mode in ((0, 1), (7, 1), (7, 2)):
            for native_update in (0, 1):
                with self.subTest(seat=seat, mode=mode, native_update=native_update):
                    self.assertEqual(self.native.multiplayerRevealedMinimap(seat, mode, native_update), 0)

    def test_uses_guest_observers_for_foreign_ship_visibility(self):
        for map_mode in (1, 2):
            with self.subTest(map_mode=map_mode):
                self.assertEqual(self.native.multiplayerSight(map_mode), 0)

    def test_pending_and_wrong_world_draws_never_publish_stale_pixels(self):
        for wrong_world in (0, 1):
            with self.subTest(wrong_world=wrong_world):
                self.assertEqual(self.native.multiplayerWithhold(wrong_world), 0)
