"""Opt-in native World Settings selector for the multiplayer companion."""

from pathlib import Path
import os
from struct import error as StructError
from struct import pack

from .filesystem import checked_path, file_sha, read_copy_marker
from .world_options import PRIVATE, PREVIEW_SIZE, SETTINGS_SIZE, replace
from .world_options_snapshot import SETTINGS_FIELDS, SETTINGS_FORMAT, decode
from .world_settings_multiplayer_scene import HUGE_WORLD_SIZE, SHIP_RESERVE, WORLD_SHIP_TILES
from .world_settings_multiplayer_visibility import PEACEFUL_AI_EXPORT


PREVIEW_EXPORT = "WorldSettingsChooseMultiplayerPreview"
BUILD_EXPORT = "WorldSettingsBuildMultiplayerPreview"
PREVIEW_STARTS_EXPORT = "WorldSettingsChooseMultiplayerPreviewWithStarts"
BUILD_STARTS_EXPORT = "WorldSettingsBuildMultiplayerStartPlan"
PREVIEW_PRESETS_EXPORT = "WorldSettingsChooseMultiplayerPreviewWithPresets"
STOCK_AI_CAPACITY_EXPORT = "WorldSettingsMultiplayerStockAICapacity"
FACTION_MASK_EXPORT = "WorldSettingsMultiplayerFactionMask"
FACTION_FREQUENCY_EXPORT = "WorldSettingsMultiplayerFactionFrequency"
CULTURE_CAPACITY_EXPORT = "WorldSettingsMultiplayerCultureCapacity"
_NATIVE = Path(__file__).with_name("native") / "world_settings_multiplayer"


def _load_preview_runtime(runtime, expected_sha256):
    if os.name != "nt":
        raise RuntimeError("The native World Settings dialog requires Windows.")
    import ctypes as c

    library = checked_path(Path(runtime))
    if library.name != "AnnoWorldSettings.dll" or file_sha(library) != expected_sha256:
        raise ValueError("The World Settings companion runtime differs from its reviewed build.")
    native = c.WinDLL(str(library))
    native.WorldSettingsSettingsSize.restype = c.c_uint32
    native.WorldSettingsPreviewSnapshotSize.restype = c.c_uint32
    if native.WorldSettingsSettingsSize() != SETTINGS_SIZE or native.WorldSettingsPreviewSnapshotSize() != PREVIEW_SIZE:
        raise RuntimeError("The World Settings companion has different preview or settings fields.")
    return native


def _validated_preview(buffer, size):
    if size != PREVIEW_SIZE:
        raise RuntimeError("The World Settings companion returned an incomplete map preview.")
    value = buffer.raw
    snapshot = decode(value)
    if snapshot["state_name"] != "ready":
        raise RuntimeError("The World Settings companion preview was not ready.")
    return value


def choose_preview(runtime, expected_sha256, owner=0, *, allow_start_layout=False, preset_root=None):
    """Return the reviewed companion's exact selected preview bytes or None."""
    import ctypes as c

    native = _load_preview_runtime(runtime, expected_sha256)
    buffer = c.create_string_buffer(PREVIEW_SIZE)
    if preset_root is not None and hasattr(native, PREVIEW_PRESETS_EXPORT):
        root = checked_path(Path(preset_root))
        library = checked_path(Path(runtime))
        if (not owner or read_copy_marker(root)["phase"] != "vanilla"
                or library.parent != root / "AnnoGrandWorldSettings"):
            raise ValueError("Multiplayer presets require the running, verified game copy.")
        choose = getattr(native, PREVIEW_PRESETS_EXPORT)
        choose.argtypes = [c.c_void_p, c.c_wchar_p, c.c_int, c.c_void_p, c.c_uint32]
        choose.restype = c.c_uint32
        size = choose(owner, str(root), allow_start_layout, buffer, PREVIEW_SIZE)
        if size == 0xFFFFFFFF:
            raise ValueError("The owned game-copy folder cannot be opened for multiplayer presets.")
    else:
        choose = getattr(native, PREVIEW_STARTS_EXPORT if allow_start_layout else PREVIEW_EXPORT)
        choose.argtypes = [c.c_void_p, c.c_void_p, c.c_uint32]
        choose.restype = c.c_uint32
        size = choose(owner, buffer, PREVIEW_SIZE)
    if size == 0:
        return None
    return _validated_preview(buffer, size)


def supports_start_layout(runtime, expected_sha256) -> bool:
    """Check the exact candidate for both new planner entry points."""
    native = _load_preview_runtime(runtime, expected_sha256)
    return hasattr(native, PREVIEW_STARTS_EXPORT) and hasattr(native, BUILD_STARTS_EXPORT)


def _optional_capacity(runtime, expected_sha256, export: str) -> int:
    import ctypes as c

    native = _load_preview_runtime(runtime, expected_sha256)
    capacity = getattr(native, export, None)
    if capacity is None:
        return 0
    capacity.argtypes = []
    capacity.restype = c.c_uint32
    return capacity()


def supports_populated_factions(runtime, expected_sha256) -> bool:
    """Require both populated faction types in the reviewed optional native build."""
    return _optional_capacity(runtime, expected_sha256, FACTION_MASK_EXPORT) == 3


def supports_faction_frequency(runtime, expected_sha256) -> bool:
    """Check that the exact optional chooser includes both faction frequency controls."""
    return _optional_capacity(runtime, expected_sha256, FACTION_FREQUENCY_EXPORT) == 1


def supports_populated_cultures(runtime, expected_sha256) -> bool:
    """Require the reviewed native culture-town capacity."""
    return _optional_capacity(runtime, expected_sha256, CULTURE_CAPACITY_EXPORT) == 21


def supports_peaceful_ai(runtime, expected_sha256) -> bool:
    return hasattr(_load_preview_runtime(runtime, expected_sha256), PEACEFUL_AI_EXPORT)


def _build_preview(runtime, expected_sha256, settings, resolve_starts, *, allow_huge=False):
    import ctypes as c

    if (not isinstance(settings, dict) or settings.keys() != set(SETTINGS_FIELDS)
            or any(type(value) is not int for value in settings.values())):
        raise ValueError("The multiplayer world has unexpected native settings.")
    if settings["worldSize"] == HUGE_WORLD_SIZE and allow_huge is not True:
        raise ValueError("Huge multiplayer worlds require an explicit offline planning opt-in.")
    native = _load_preview_runtime(runtime, expected_sha256)
    build = getattr(native, BUILD_STARTS_EXPORT if resolve_starts else BUILD_EXPORT)
    shared_types = [c.c_char_p, c.c_uint32, c.c_void_p, c.c_uint32]
    start_types = [c.POINTER(c.c_uint32), c.c_uint32] if resolve_starts else []
    build.argtypes = shared_types + start_types + [c.c_void_p, c.c_uint32]
    build.restype = c.c_uint32
    try:
        encoded = pack(SETTINGS_FORMAT, *(settings[name] for name in SETTINGS_FIELDS))
    except (StructError, OverflowError) as exc:
        raise ValueError("The multiplayer world has out-of-range native settings.") from exc
    buffer = c.create_string_buffer(PREVIEW_SIZE)
    error = c.create_string_buffer(512)
    tiles = (c.c_uint32 * 12)()
    starts = (tiles, len(tiles)) if resolve_starts else ()
    size = build(encoded, len(encoded), buffer, PREVIEW_SIZE, *starts, error, len(error))
    if size == 0:
        raise ValueError(error.value.decode("ascii", errors="replace") or "The multiplayer map preview could not be built.")
    result = _validated_preview(buffer, size)
    if not resolve_starts:
        return result
    return result, tuple(zip(tiles[::3], tiles[1::3], tiles[2::3], strict=True))


def build_preview(runtime, expected_sha256, settings):
    """Rebuild the same native preview without showing the dialog."""
    return _build_preview(runtime, expected_sha256, settings, False)


def build_start_plan(runtime, expected_sha256, settings, *, allow_huge=False):
    """Rebuild the native preview and four human (x, y, island ID) tuples."""
    return _build_preview(runtime, expected_sha256, settings, True, allow_huge=allow_huge)


def apply_multiplayer_preview(files, *, allow_huge_planning=False, allow_huge_matches=False, allow_stock_ai=False,
                              allow_disasters=False, allow_populated_factions=False, allow_populated_cultures=False,
                              allow_peaceful_ai=False, allow_faction_activity=False):
    """Add the companion mode to staged, already transformed World Settings sources."""
    name = PRIVATE + "WorldSettings.c"
    menu = files[name]
    if allow_faction_activity:
        if not allow_populated_factions:
            raise ValueError("Multiplayer faction frequency requires populated native faction islands.")
        menu = b"#define WS_MP_FACTION_ACTIVITY 1\n" + menu
    if allow_peaceful_ai:
        menu = b"#define WS_MP_PEACEFUL_AI 1\n" + menu
    if allow_populated_cultures:
        menu = b"#define WS_MP_POPULATED_CULTURES 1\n" + menu
    if allow_populated_factions:
        menu = b"#define WS_MP_POPULATED_FACTIONS 1\n" + menu
    if allow_disasters:
        menu = b"#define WS_MP_INDIVIDUAL_DISASTERS 1\n" + menu
    if allow_huge_matches:
        menu = b"#define WS_MP_HUGE_MATCHES 1\n" + menu
    if allow_huge_planning or allow_huge_matches:
        menu = b"#define WS_MP_HUGE_PLANNING 1\n" + menu
    if allow_stock_ai:
        menu = b"#define WS_MP_STOCK_AI 1\n" + menu
        menu = replace(menu, b'__declspec(dllexport) int __cdecl WorldSettingsValidateSettings(',
                       b'int WorldSettingsMultiplayerPreviewActive(void);\n'
                       b'__declspec(dllexport) int __cdecl WorldSettingsValidateSettings(',
                       'declare the thread-scoped multiplayer preview guard')
        menu = replace(menu, b'if(s->aiCount&&!WorldSettingsAIExperimentConfigured()){',
                       b'if(s->aiCount&&!WorldSettingsMultiplayerPreviewActive()&&!WorldSettingsAIExperimentConfigured()){',
                       'validate stock CPU count in a game-free preview without activating single-player AI')
    menu = replace(menu, b' HWND pageControls[320];int controlPages[320];',
                   b' HWND pageControls[320];int controlPages[320];\n'
                   b' WSPreviewSnapshot *multiplayerPreview;', 'companion dialog output')
    menu = replace(menu, b'#include "menu_values.inc"',
                   b'#include "menu_multiplayer_export.inc"\n#include "menu_values.inc"',
                   'companion controls and preview capture')
    menu = replace(menu, b' if(!wsMenuCollectAdvanced(d,&s))return 0;',
                   b' if(!wsMenuCollectAdvanced(d,&s))return 0;\n'
                   b' if(d->multiplayerPreview&&!wsMultiplayerOptionsSupported(&s,0)){\n'
                   b'  status(d,"Use the available settings for this multiplayer world.");return 0;\n'
                   b' }', 'guard fixed companion options')
    menu = replace(menu, b' WorldSettingsAIProfileAttemptFinished(0); /* a new Start cannot inherit prior verification */',
                   b' if(!d->multiplayerPreview)WorldSettingsAIProfileAttemptFinished(0);',
                   'companion selection avoids native start')
    menu = replace(menu, b' if(!prepareBackend || !d->frame || !d->setup){status(d,noBackend);return;}',
                   b' if(d->multiplayerPreview){\n'
                   b'  if(!wsCaptureMultiplayerPreview(d)){\n'
                   b'   invalidatePreview(d);status(d,"The preview changed. Wait for the refreshed map.");\n'
                   b'   SetTimer(d->window,WS_PREVIEW_TIMER,200,NULL);return;\n'
                   b'  }\n'
                   b'  d->result=1;d->done=1;DestroyWindow(d->window);return;\n'
                   b' }\n'
                   b' if(!prepareBackend || !d->frame || !d->setup){status(d,noBackend);return;}',
                   'accept exact companion preview without staging')
    menu = replace(menu, b'static int dialog(HWND owner,void*setup,uint8_t*frame){',
                   b'static int dialogWithPreview(HWND owner,void*setup,uint8_t*frame,WSPreviewSnapshot*selection){',
                   'one native dialog for both modes')
    menu = replace(menu, b'd.frame=frame;d.creating=1;d.scale=1000;',
                   b'd.frame=frame;d.creating=1;d.scale=1000;d.multiplayerPreview=selection;',
                   'bind optional caller-owned preview')
    menu = replace(menu, b'#include "menu_generation.inc"',
                   b'static int dialog(HWND owner,void*setup,uint8_t*frame){\n'
                   b' return dialogWithPreview(owner,setup,frame,NULL);\n'
                   b'}\n'
                   b'static uint32_t wsChooseMultiplayerWorld(HWND owner,void*out,uint32_t capacity,int startLayout,const wchar_t*presetRoot){\n'
                   b' if(!out||capacity!=sizeof(WSPreviewSnapshot)||!wsEnterMultiplayerPreview(startLayout))return 0;\n'
                   b' if(presetRoot&&!wsSetMultiplayerPresetRoot(owner,presetRoot)){wsLeaveMultiplayerPreview();return UINT32_MAX;}\n'
                   b' WSPreviewSnapshot selected={0};\n'
                   b' int accepted=dialogWithPreview(owner,NULL,NULL,&selected);\n'
                   b' if(accepted)memcpy(out,&selected,sizeof selected);\n'
                   b' wsLeaveMultiplayerPreview();\n'
                   b' return accepted?sizeof selected:0;\n'
                   b'}\n'
                   b'__declspec(dllexport) uint32_t WINAPI WorldSettingsChooseMultiplayerPreview(HWND owner,void*out,uint32_t capacity){\n'
                   b' return wsChooseMultiplayerWorld(owner,out,capacity,0,NULL);\n'
                   b'}\n'
                   b'__declspec(dllexport) uint32_t WINAPI WorldSettingsChooseMultiplayerPreviewWithStarts(HWND owner,void*out,uint32_t capacity){\n'
                   b' return wsChooseMultiplayerWorld(owner,out,capacity,1,NULL);\n'
                   b'}\n'
                   b'__declspec(dllexport) uint32_t WINAPI WorldSettingsChooseMultiplayerPreviewWithPresets(\n'
                   b' HWND owner,const wchar_t*root,int startLayout,void*out,uint32_t capacity){\n'
                   b' if(!root||(startLayout!=0&&startLayout!=1))return UINT32_MAX;\n'
                   b' return wsChooseMultiplayerWorld(owner,out,capacity,startLayout,root);\n'
                   b'}\n'
                   b'#include "menu_generation.inc"', 'standalone companion export')
    files[name] = menu

    name = PRIVATE + "world_menu_preview.inc"
    preview = replace(files[name], b' EnableWindow(GetDlgItem(d->window,ID_START),valid&&prepareBackend&&d->frame&&d->setup);',
                      b' wsMultiplayerPreviewControls(d);\n'
                      b' if(valid&&d->multiplayerPreview&&!wsMultiplayerCultureCapacity(d->previewIslands,d->previewCount)){\n'
                      b'  valid=0;d->previewValid=0;status(d,wsMultiplayerCultureCapacityMessage);\n'
                      b' }\n'
                      b' if(valid&&d->multiplayerPreview)status(d,"Map ready. Use this world selects the current preview.");\n'
                      b' EnableWindow(GetDlgItem(d->window,ID_START),valid&&(d->multiplayerPreview||(prepareBackend&&d->frame&&d->setup)));',
                      'enable selection for the validated companion preview')
    preview = replace(preview, b'   uint32_t faction=wsTemplateFactions[p->templateIndex];int owner=WorldSettingsStartOwner(i);',
                      b'   if(d->multiplayerPreview&&!wsMultiplayerStartLayout)continue;\n'
                      b'   uint32_t faction=wsTemplateFactions[p->templateIndex];int owner=WorldSettingsStartOwner(i);',
                      'omit single-player ownership badges in companion preview')
    preview = replace(preview, b'   int chosen=(int)i==WorldSettingsStartingIslandChosen();',
                      b'   int chosen=(int)i==WorldSettingsStartingIslandChosen();\n'
                      b'   if(d->multiplayerPreview&&!d->previewSettings.fairStarts&&!chosen)continue;\n   ',
                      'show companion start badges only for relocated fleets')
    files[name] = preview

    name = PRIVATE + "menu_create.inc"
    menu_create = replace(files[name], b'"Choose options below. The map updates automatically."',
                          b'd->multiplayerPreview?"Unavailable settings use the stock multiplayer rules.":"Choose options below. The map updates automatically."',
                          'explain disabled companion controls')
    menu_create = replace(menu_create, b'"Start custom world",BS_DEFPUSHBUTTON',
                          b'd->multiplayerPreview?"Use this world":"Start custom world",BS_DEFPUSHBUTTON',
                          'label companion selection without game start')
    menu_create = replace(menu_create, b'label(d,"Game difficulty preset",',
                          b'label(d,d->multiplayerPreview?"Starting difficulty preset":"Game difficulty preset",',
                          'label the companion cargo and stock profile presets')
    if allow_stock_ai:
        menu_create = replace(menu_create, b'label(d,"AI opponents",',
                              b'label(d,d->multiplayerPreview?"AI opponents (stock behavior)":"AI opponents",',
                              'identify the native multiplayer computer-player behavior')
    menu_create = replace(menu_create, b'developmentConfigured&&prepareBackend?configuredStatus:noBackend',
                          b'(d->multiplayerPreview||(developmentConfigured&&prepareBackend))?configuredStatus:noBackend',
                          'show companion preview initialization status')
    world_choices = b'(d->multiplayerPreview&&!wsMultiplayerStartLayout)?3:4' if allow_huge_matches else b'd->multiplayerPreview?3:4'
    menu_create = replace(menu_create, b'ID_WORLD_SIZE),worlds,4,2);',
                          b'ID_WORLD_SIZE),worlds,' + world_choices + b',2);',
                          'select only native multiplayer map sizes')
    menu_create = replace(menu_create, b'"Balance starting islands for human and AI players"',
                          b'd->multiplayerPreview?"Balance starting islands for all human players":'
                          b'"Balance starting islands for human and AI players"',
                          'describe the four multiplayer starts')
    menu_create = replace(menu_create, b'"P: Pirates   V: Venetians   S: You   1-3: AI"',
                          b'd->multiplayerPreview?"S: Host start   1-3: Other player starts":'
                          b'"P: Pirates   V: Venetians   S: You   1-3: AI"',
                          'identify human start slots in the multiplayer legend')
    menu_create = replace(menu_create, b'ID_MAP_VISIBILITY),visibility,3,1);',
                          b'ID_MAP_VISIBILITY),visibility,d->multiplayerPreview?WS_MULTIPLAYER_VISIBILITY_CHOICES:3,1);',
                          'show only map visibility modes supplied by the companion')
    menu_create = replace(menu_create, b' label(d,"Disaster",24,194,230,22);',
                          b' if(d->multiplayerPreview&&!WS_MP_INDIVIDUAL_DISASTERS){\n'
                          b'  HWND firePlague=control(d,"BUTTON","Fire and plague",BS_AUTOCHECKBOX|WS_TABSTOP,24,208,620,28,ID_DISASTER_ENABLE);\n'
                          b'  HWND weather=control(d,"BUTTON","Volcanic eruptions, earthquakes and drought",BS_AUTOCHECKBOX|WS_TABSTOP,24,250,620,28,ID_DISASTER_ENABLE+2);\n'
                          b'  if(!firePlague||!weather)return 0;\n'
                          b'  SendMessageA(firePlague,BM_SETCHECK,BST_CHECKED,0);\n'
                          b'  SendMessageA(weather,BM_SETCHECK,BST_CHECKED,0);\n'
                          b'  label(d,"Both groups follow the standard multiplayer frequency and severity.",24,306,620,56);\n'
                          b' }else{\n'
                          b' label(d,"Disaster",24,194,230,22);',
                          'show two native multiplayer disaster groups')
    menu_create = replace(menu_create, b'Eruptions need a volcano.",24,546,620,108);',
                          b'Eruptions need a volcano.",24,546,620,108);\n }',
                          'retain single-player disaster controls only in single-player')
    files[name] = replace(menu_create, b' wsMenuShowSizeLimits(d);wsMenuLegacyLimits(d);wsMenuPutSeed(d,freshPreviewSeed(0));',
                          b' if(d->multiplayerPreview){\n'
                          b'  for(int i=0;i<8;i++)SendDlgItemMessageA(w,ID_CULTURE+i,BM_SETCHECK,BST_UNCHECKED,0);\n'
                          b'  for(int i=0;i<2;i++)SendDlgItemMessageA(w,ID_FACTION+i,BM_SETCHECK,BST_UNCHECKED,0);\n'
                          b' }\n'
                          b' wsMenuShowSizeLimits(d);wsMenuLegacyLimits(d);wsMenuPutSeed(d,freshPreviewSeed(0));', 'stock scenario supplies multiplayer occupants')
    files[name] = replace(files[name], b' EnableWindow(GetDlgItem(w,ID_START),FALSE);',
                          b' wsMultiplayerPreviewControls(d);\n EnableWindow(GetDlgItem(w,ID_START),FALSE);',
                          'disable unsupported companion controls on open')

    name = PRIVATE + "menu_values.inc"
    values = replace(files[name], b' SetDlgItemTextA(d->window,ID_ISLAND_DETAILS,text);',
                     b' if(d->multiplayerPreview&&!wsMultiplayerStartLayout){\n'
                     b'  if(known){char*start=strstr(text,"\\r\\n\\r\\nStarting assignment:");if(start)*start=0;}\n'
                     b'  else if(d->previewValid)snprintf(text,sizeof text,"Click an island to inspect its climate and planned resources.");\n'
                     b'  SetDlgItemTextA(d->window,ID_ISLAND_DETAILS,text);\n'
                     b'  SetDlgItemTextA(d->window,ID_FAIR_SUMMARY,"Starting locations use the multiplayer scenario.");\n'
                     b'  EnableWindow(GetDlgItem(d->window,ID_USE_ISLAND),FALSE);return;\n'
                     b' }\n'
                     b' SetDlgItemTextA(d->window,ID_ISLAND_DETAILS,text);',
                     'show exact companion fertility and geography')
    values = replace(values, b'"Terra incognita keeps land, sea, resources and occupants hidden.',
                     b'd->multiplayerPreview?"Terra incognita keeps the map and resources hidden until you explore.":'
                     b'"Terra incognita keeps land, sea, resources and occupants hidden.',
                     'describe concealed multiplayer preview')
    values = replace(values, b'"Click any island to inspect it. S: human start; 1-3: AI starts."',
                     b'd->multiplayerPreview?"Click an island to inspect it. S: host; 1-3: other player start slots.":'
                     b'"Click any island to inspect it. S: human start; 1-3: AI starts."',
                     'describe the multiplayer start badges in the hint')
    values = replace(values, b' for(int i=0;i<5;i++){\n  int enabled=SendDlgItemMessageA',
                     b' if(d->multiplayerPreview&&!WS_MP_INDIVIDUAL_DISASTERS){\n'
                     b'  EnableWindow(GetDlgItem(d->window,ID_DISASTER_ENABLE),active);\n'
                     b'  EnableWindow(GetDlgItem(d->window,ID_DISASTER_ENABLE+2),active);\n'
                     b'  return;\n'
                     b' }\n'
                     b' for(int i=0;i<5;i++){\n  int enabled=SendDlgItemMessageA',
                     'master checkbox enables just the two multiplayer disaster groups')
    values = replace(values, b' s->disasterMask=s->disasterFrequency=s->disasterSeverity=0;',
                     b' if(d->multiplayerPreview&&!WS_MP_INDIVIDUAL_DISASTERS){\n'
                     b'  s->disasterMask=0;\n'
                     b'  if(SendDlgItemMessageA(d->window,ID_DISASTER_ENABLE,BM_GETCHECK,0,0)==BST_CHECKED)\n'
                     b'   s->disasterMask|=WS_MP_FIRE_PLAGUE_MASK;\n'
                     b'  if(SendDlgItemMessageA(d->window,ID_DISASTER_ENABLE+2,BM_GETCHECK,0,0)==BST_CHECKED)\n'
                     b'   s->disasterMask|=WS_MP_WEATHER_DISASTER_MASK;\n'
                     b'  s->disasterFrequency=s->disasterSeverity=341u;\n'
                     b'  return 1;\n'
                     b' }\n'
                     b' s->disasterMask=s->disasterFrequency=s->disasterSeverity=0;',
                     'keep grouped multiplayer preset masks in the existing snapshot field')
    values = replace(values, b'static int wsPresetFolder(char path[MAX_PATH],int create){\n'
                     b' if(!developmentConfigured||!developmentRoot[0]||strlen(developmentRoot)+sizeof("\\\\WorldSettingsPresets")>MAX_PATH)return 0;\n'
                     b' snprintf(path,MAX_PATH,"%s\\\\WorldSettingsPresets",developmentRoot);',
                     b'static int wsPresetFolder(char path[MAX_PATH],int create){\n'
                     b' int multiplayer=WorldSettingsMultiplayerPreviewActive();\n'
                     b' if(multiplayer){\n'
                     b'  if(!wsMultiplayerPresetRoot[0])return 0;\n'
                     b'  snprintf(path,MAX_PATH,"%s\\\\AnnoGrandMultiplayerPresets",wsMultiplayerPresetRoot);\n'
                     b' }else{\n'
                     b'  if(!developmentConfigured||!developmentRoot[0]||strlen(developmentRoot)+sizeof("\\\\WorldSettingsPresets")>MAX_PATH)return 0;\n'
                     b'  snprintf(path,MAX_PATH,"%s\\\\WorldSettingsPresets",developmentRoot);\n'
                     b' }',
                     'keep multiplayer presets in their owned copy')
    values = replace(values,
                     b' return attrs!=INVALID_FILE_ATTRIBUTES&&(attrs&FILE_ATTRIBUTE_DIRECTORY)&&!(attrs&FILE_ATTRIBUTE_REPARSE_POINT);',
                     b' return attrs!=INVALID_FILE_ATTRIBUTES&&(attrs&FILE_ATTRIBUTE_DIRECTORY)&&!(attrs&FILE_ATTRIBUTE_REPARSE_POINT)\n'
                     b'     &&(!multiplayer||wsLockMultiplayerPresetFolder(path));',
                     'hold the checked multiplayer preset folder throughout the dialog')
    values = replace(values,
                     b' if(!WorldSettingsValidateSettings(&value,error,sizeof error)){status(d,error);return;}',
                     b' if(!WorldSettingsValidateSettings(&value,error,sizeof error)){status(d,error);return;}\n'
                     b' if(d->multiplayerPreview&&!wsMultiplayerOptionsSupported(&value,0)){\n'
                     b'  status(d,"This preset uses settings unavailable in this multiplayer build.");return;\n'
                     b' }',
                     'reject unsupported multiplayer preset choices before changing the menu')
    values = replace(values, b'wsMenuApplySettings(d,&value);SetDlgItemTextA',
                     b'wsMenuApplySettings(d,&value);wsMultiplayerPreviewControls(d);SetDlgItemTextA',
                     'keep unsupported controls disabled immediately after a preset is loaded')
    files[name] = replace(values, b' if(id==ID_MAP_VISIBILITY&&d->preview)InvalidateRect(d->preview,NULL,FALSE);',
                          b' if(id==ID_MAP_VISIBILITY&&d->preview)InvalidateRect(d->preview,NULL,FALSE);\n'
                          b' wsMultiplayerPreviewControls(d);', 'keep companion-only controls fixed')
    name = PRIVATE + "menu_island_text.inc"
    files[name] = replace(files[name], b'"AI opponent %d",d->startOwner',
                          b'WorldSettingsMultiplayerPreviewActive()?"Player %d":"AI opponent %d",'
                          b'd->startOwner+(WorldSettingsMultiplayerPreviewActive()!=0)',
                          'name human multiplayer start assignments')
    name = PRIVATE + "world_ship_reserves.h"
    reserve_definitions = b""
    reserve_cases = b""
    for world_size, tiles in WORLD_SHIP_TILES.items():
        if world_size == HUGE_WORLD_SIZE and not (allow_huge_planning or allow_huge_matches):
            continue
        symbol = f"wsMultiplayerShipReserves{world_size}"
        side = 2 * SHIP_RESERVE + 1
        rows = ",\n".join(f" {{0,{x - SHIP_RESERVE},{y - SHIP_RESERVE},{side},{side},0,0,0,0,0,0}}"
                          for x, y in tiles)
        reserve_definitions += f"static const WSPlanIsland {symbol}[]={{\n{rows}\n}};\n".encode("ascii")
        reserve_cases += f" case {world_size}:return {symbol};\n".encode("ascii")
    reserves = replace(files[name], b'static void wsWorldShipPosition(uint32_t owner,float*x,float*y){',
                       b'extern int WorldSettingsMultiplayerPreviewActive(void);\n' + reserve_definitions +
                       b'#define WS_MULTIPLAYER_SHIP_COUNT 5u\n'
                       b'static const WSPlanIsland *wsMultiplayerShipReserves(void){\n'
                       b' switch(wsWorld){\n' + reserve_cases +
                       b' default:return NULL;}\n'
                       b'}\n'
                       b'static uint32_t wsLastStartingParticipant(const WSWorldSettings*s){\n'
                       b' return WorldSettingsMultiplayerPreviewActive() ? 3u : (uint32_t)s->aiCount;\n'
                       b'}\n'
                       b'static void wsWorldShipPosition(uint32_t owner,float*x,float*y){',
                       'reserve each New Earth starting fleet')
    reserves = replace(reserves, b' if(wsWorld==1024u){*x=wsStockShipXY',
                       b' if(WorldSettingsMultiplayerPreviewActive()){\n'
                       b'  const WSPlanIsland* reserve=wsMultiplayerShipReserves();\n'
                       b'  if(reserve&&owner<WS_MULTIPLAYER_SHIP_COUNT){\n'
                       b'   *x=(float)(reserve[owner].x+reserve[owner].width/2u)+0.5f;\n'
                       b'   *y=(float)(reserve[owner].y+reserve[owner].height/2u)+0.5f;return;\n'
                       b'  }\n'
                       b' }\n'
                       b' if(wsWorld==1024u){*x=wsStockShipXY',
                       'use the reviewed multiplayer anchors in nearby resources')
    files[name] = replace(reserves, b' if(wsWorld==1024u){memcpy(wsActiveShipReserves,wsStockShipReserves,',
                          b' if(WorldSettingsMultiplayerPreviewActive()){\n'
                          b'  const WSPlanIsland* reserve=wsMultiplayerShipReserves();\n'
                          b'  if(!reserve)return 0;\n'
                          b'  wsActiveShipReserveCount=WS_MULTIPLAYER_SHIP_COUNT;\n'
                          b'  memcpy(wsActiveShipReserves,reserve,WS_MULTIPLAYER_SHIP_COUNT*sizeof *reserve);\n'
                          b' }else if(wsWorld==1024u){memcpy(wsActiveShipReserves,wsStockShipReserves,',
                          'apply the ship reservations only in companion mode')
    name = PRIVATE + "resource_distribution.inc"
    files[name] = replace(files[name], b'(uint32_t)s->aiCount', b'wsLastStartingParticipant(s)',
                          'guarantee resources around all four possible human seats', count=4)
    name = PRIVATE + "fair_starts.inc"
    files[name] = replace(files[name], b'(uint32_t)s->aiCount', b'wsLastStartingParticipant(s)',
                          'balance four human starts through the existing native planner', count=4)
    name = PRIVATE + "start_position.inc"
    files[name] = replace(files[name], b'(uint32_t)s->aiCount+1u', b'wsLastStartingParticipant(s)+1u',
                          'view all four start assignments in the native preview')
    name = PRIVATE + "world_backend.c"
    if allow_stock_ai:
        files[name] = replace(files[name], b'(s->aiCount&&!WorldSettingsAIExperimentConfigured())',
                              b'(s->aiCount&&!WorldSettingsMultiplayerPreviewActive()&&!WorldSettingsAIExperimentConfigured())',
                              'plan the four human starts while preserving the single-player activation check')
    files[name] += b'''
int WorldSettingsCopyMultiplayerStartTiles(uint32_t *out,uint32_t words){
 if(!WorldSettingsMultiplayerPreviewActive()||wsPreviewCache.state!=1u||!out||words!=12u)return 0;
 uint32_t tiles[12];
 for(uint32_t owner=0;owner<4u;owner++){
  float x=0,y=0;wsWorldShipPosition(owner,&x,&y);
  if(!(x>=24.0f&&y>=24.0f&&x<(float)wsWorld-24.0f&&y<(float)wsWorld-24.0f)
     ||x!=(float)(uint32_t)x+0.5f||y!=(float)(uint32_t)y+0.5f)return 0;
  tiles[owner*3u]=(uint32_t)x;tiles[owner*3u+1u]=(uint32_t)y;
  tiles[owner*3u+2u]=(uint32_t)wsAssignedStartIsland[owner];
 }
 memcpy(out,tiles,sizeof tiles);return 1;
}
'''
    files[PRIVATE + "menu_multiplayer_export.inc"] = checked_path(_NATIVE / "menu_multiplayer_export.inc").read_bytes()
