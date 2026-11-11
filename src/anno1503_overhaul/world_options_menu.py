"""In-game World options pages, deterministic seeds and bounded local presets.

Only staged source dictionaries are transformed. Frozen imported source files
and the established engine hooks are never edited by this module.
"""
from .world_options import PRIVATE, authored, replace


def apply_menu(files: dict[str, bytes]) -> None:
    menu_name = PRIVATE + 'WorldSettings.c'
    menu = files[menu_name]
    anchor = b'enum {WS_PREVIEW_TIMER=1,WS_PREVIEW_MESSAGE=WM_APP+17,WS_MENU_WIDTH=1120,WS_MENU_HEIGHT=810};'
    menu = replace(menu, anchor, anchor + b'\n'
        b'enum {ID_SEED=201,ID_COPY_SEED,ID_START_CLIMATE,ID_CARGO_MODE,ID_CARGO_TOOLS,ID_CARGO_WOOD,ID_CARGO_FOOD,\n'
        b' ID_CLIMATE_BALANCE,ID_LAYOUT_STYLE,ID_DISASTERS,ID_PRESET_PICK,ID_PRESET_NAME,ID_PRESET_SAVE,ID_PRESET_LOAD,ID_CLEAR_START,ID_START_HINT,\n'
        b' ID_TAB_WORLD=220,ID_TAB_PLAYERS,ID_TAB_START,ID_TAB_PRESETS,ID_TAB_ISLANDS,ID_TAB_VISIBILITY,\n'
        b' ID_FAIR_STARTS=230,ID_START_SEPARATION,ID_RESOURCE_DISTRIBUTION,ID_GUARANTEE_BASICS,\n'
        b' ID_ISLAND_DETAILS,ID_USE_ISLAND,ID_FAIR_SUMMARY,ID_MAP_VISIBILITY,ID_ENEMY_VISIBILITY,\n'
        b' ID_PIRATE_FREQUENCY,ID_PIRATE_STRENGTH,ID_MERCHANT_FREQUENCY};', 'advanced menu control IDs')
    menu = replace(menu,
        b' uint32_t previewSeed,previewCount;WSPlanIsland previewIslands[128];',
        b' uint32_t previewSeed,previewCount;WSPlanIsland previewIslands[128];\n'
        b' int page,creatingPage;int32_t preferredIsland,inspectedIsland;uint32_t pageControlCount;\n'
        b' HWND pageControls[128];int controlPages[128];', 'paged menu state')
    menu = replace(menu,
        b' if(c)SendMessageA(c,WM_SETFONT,(WPARAM)d->font,TRUE);return c;',
        b' if(c)SendMessageA(c,WM_SETFONT,(WPARAM)d->font,TRUE);\n'
        b' if(c&&d->creatingPage>=0){if(d->pageControlCount>=128u){DestroyWindow(c);return NULL;}uint32_t at=d->pageControlCount++;d->pageControls[at]=c;d->controlPages[at]=d->creatingPage;}return c;',
        'track page visibility')
    menu = replace(menu, b'static int collect(DialogState*d){',
        b'#include "menu_values.inc"\nstatic int collect(DialogState*d){', 'menu values and presets include')
    menu = replace(menu,
        b' if(!WorldSettingsValidateSettings(&s,err,sizeof err)){status(d,err);return 0;}d->settings=s;return 1;',
        b' if(!wsMenuCollectAdvanced(d,&s))return 0;\n'
        b' if(!WorldSettingsValidateSettings(&s,err,sizeof err)){status(d,err);return 0;}d->settings=s;return 1;',
        'collect every advanced setting')
    menu = replace(menu, b'static LRESULT CALLBACK windowProc(HWND w,UINT msg,WPARAM wp,LPARAM lp){',
        b'#include "menu_create.inc"\nstatic LRESULT CALLBACK windowProc(HWND w,UINT msg,WPARAM wp,LPARAM lp){',
        'readable menu creation include')
    # Replace the single original WM_CREATE body, retaining the existing native
    # message loop and Start/Back/commit route around it.
    begin, end = b' case WM_CREATE:{', b' case WM_COMMAND:{'
    if menu.count(begin) != 1 or menu.count(end) != 1:
        from .world_runtime_build import RuntimeBuildError
        raise RuntimeBuildError('Advanced World Settings source differs: menu creation boundaries')
    at = menu.index(begin)
    stop = menu.index(end, at)
    menu = menu[:at] + b' case WM_CREATE:return wsCreateMenu(d,w)?0:-1;\n' + menu[stop:]
    menu = replace(menu, b'  int id=LOWORD(wp),notice=HIWORD(wp);',
        b'  int id=LOWORD(wp),notice=HIWORD(wp);\n  if(wsMenuCommand(d,id,notice))return 0;', 'new menu commands')
    menu = replace(menu,
        b'  if(id==ID_REGENERATE){KillTimer(w,WS_PREVIEW_TIMER);generatePreview(d,1);return 0;}',
        b'  if(id==ID_REGENERATE){KillTimer(w,WS_PREVIEW_TIMER);d->preferredIsland=d->inspectedIsland=-1;generatePreview(d,1);return 0;}',
        'clear stale island choice on regeneration')
    menu = replace(menu,
        b'  if(!d->creating&&settingsNotification(id,notice)){invalidatePreview(d);SetTimer(w,WS_PREVIEW_TIMER,250,NULL);return 0;}',
        b'  if(!d->creating&&settingsNotification(id,notice)){wsMenuOptionChanged(d,id);invalidatePreview(d);SetTimer(w,WS_PREVIEW_TIMER,250,NULL);return 0;}',
        'advanced input invalidates cached preview')
    menu = replace(menu, b'scaled(d,550+(i/2)*24)', b'scaled(d,614+(i/2)*24)', 'legend top')
    menu = replace(menu, b'scaled(d,564+(i/2)*24)', b'scaled(d,628+(i/2)*24)', 'legend bottom')
    files[menu_name] = menu

    preview_name = PRIVATE + 'world_menu_preview.inc'
    preview = files[preview_name]
    preview = replace(preview,
        b' HBRUSH sea=CreateSolidBrush(RGB(34,75,103));FillRect(dc,client,sea);DeleteObject(sea);',
        b' if(wsMenuMapConcealed(d)){wsMenuPaintConcealed(d,dc,client);return;}\n'
        b' HBRUSH sea=CreateSolidBrush(RGB(34,75,103));FillRect(dc,client,sea);DeleteObject(sea);',
        'terra incognita precedes every preview geometry and marker query')
    preview = replace(preview,
        b'   uint32_t faction=wsTemplateFactions[p->templateIndex];if(faction!=1u&&faction!=2u)continue;\n'
        b"   char symbol[2]={faction==1u?'P':'V',0};",
        b'   uint32_t faction=wsTemplateFactions[p->templateIndex];int owner=WorldSettingsStartOwner(i);\n'
        b'   int chosen=(int)i==WorldSettingsStartingIslandChosen();if(!chosen&&owner<0&&faction!=1u&&faction!=2u)continue;\n'
        b"   char symbol[2]={owner>0?(char)('0'+owner):(chosen||owner==0?'S':(faction==1u?'P':'V')),0};", 'mark the chosen starting island')
    preview = replace(preview,
        b'HBRUSH marker=CreateSolidBrush(faction==1u?RGB(156,38,38):RGB(242,202,83));',
        b'HBRUSH marker=CreateSolidBrush(chosen||owner>=0?RGB(93,218,235):(faction==1u?RGB(156,38,38):RGB(242,202,83)));',
        'starting island badge colour')
    preview = replace(preview,
        b'SetTextColor(dc,faction==1u?RGB(255,255,255):RGB(20,20,20));',
        b'SetTextColor(dc,!chosen&&owner<0&&faction==1u?RGB(255,255,255):RGB(20,20,20));', 'starting badge text')
    preview = replace(preview,
        b'  SetTextColor(dc,oldColor);SetBkMode(dc,oldMode);SelectObject(dc,previousFont);',
        b'  if(d->inspectedIsland>=0&&(uint32_t)d->inspectedIsland<d->previewCount){\n'
        b'   const WSPlanIsland*p=&d->previewIslands[d->inspectedIsland];\n'
        b'   RECT selection={map.left+(int)((uint64_t)p->x*size/world),map.top+(int)((uint64_t)p->y*size/world),\n'
        b'    map.left+(int)((uint64_t)(p->x+p->width)*size/world),map.top+(int)((uint64_t)(p->y+p->height)*size/world)};\n'
        b'   InflateRect(&selection,1,1);FrameRect(dc,&selection,(HBRUSH)GetStockObject(WHITE_BRUSH));\n'
        b'  }\n'
        b'  SetTextColor(dc,oldColor);SetBkMode(dc,oldMode);SelectObject(dc,previousFont);',
        'highlight the inspected island independently from starting badges')
    preview = replace(preview, b'static LRESULT CALLBACK previewWindowProc(HWND w,UINT msg,WPARAM wp,LPARAM lp){',
        b'#include "menu_preview.inc"\nstatic LRESULT CALLBACK previewWindowProc(HWND w,UINT msg,WPARAM wp,LPARAM lp){',
        'preview land hit testing include')
    preview = replace(preview, b' if(msg==WM_ERASEBKGND)return 1;',
        b' if(msg==WM_LBUTTONUP){wsMenuPreviewClick(d,w,lp);return 0;}\n if(msg==WM_ERASEBKGND)return 1;',
        'preview starting-island click')
    preview = replace(preview, b'static int settingsNotification(int id,int notification){',
        b'static int settingsNotification(int id,int notification){\n'
        b' if(id==ID_SEED||(id>=ID_CARGO_TOOLS&&id<=ID_CARGO_FOOD))return notification==EN_CHANGE;\n'
        b' if(id==ID_CARGO_MODE||id==ID_DISASTERS||id==ID_FAIR_STARTS||id==ID_GUARANTEE_BASICS)return notification==BN_CLICKED;\n'
        b' if(id==ID_START_CLIMATE||id==ID_CLIMATE_BALANCE||id==ID_LAYOUT_STYLE||id==ID_START_SEPARATION||id==ID_RESOURCE_DISTRIBUTION||id==ID_MAP_VISIBILITY||id==ID_ENEMY_VISIBILITY||id==ID_PIRATE_FREQUENCY||id==ID_PIRATE_STRENGTH||id==ID_MERCHANT_FREQUENCY)return notification==CBN_SELCHANGE;',
        'advanced control notifications')
    preview = replace(preview,
        b' d->previewValid=0;d->previewCount=0;EnableWindow(GetDlgItem(d->window,ID_START),FALSE);',
        b' d->previewValid=0;d->previewCount=0;EnableWindow(GetDlgItem(d->window,ID_START),FALSE);wsMenuStartHint(d);wsMenuIslandInfo(d);',
        'starting hint follows preview invalidation')
    preview = replace(preview,
        b' char error[512]={0};int valid=collect(d);\n if(valid){\n'
        b'  if(regenerate||!d->previewSeed)d->previewSeed=freshPreviewSeed(d->previewSeed);',
        b' if(regenerate){d->creating=1;wsMenuPutSeed(d,freshPreviewSeed(d->previewSeed));d->creating=0;}\n'
        b' char error[512]={0};int valid=collect(d);\n if(valid){\n'
        b'  d->previewSeed=d->settings.mapSeed;', 'displayed seed is the generation seed')
    preview = replace(preview,
        b'd->previewCount=(uint32_t)count;d->previewValid=1;status(d,"Map ready. Start uses this preview; Regenerate makes another world.");',
        b'd->previewCount=(uint32_t)count;d->previewValid=1;wsMenuStartHint(d);wsMenuIslandInfo(d);status(d,wsMenuMapConcealed(d)?"World ready. Terra incognita keeps the map hidden until you explore in the game.":"Map ready. Start uses this preview; click an island to inspect it.");',
        'updated preview preserves chosen start hint')
    files[preview_name] = preview
    for name in ('menu_presets_codec.inc', 'menu_values.inc', 'menu_create.inc', 'menu_preview.inc', 'menu_island_text.inc'):
        files[PRIVATE + name] = authored(name)
