#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <bcrypt.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <wchar.h>
#include "world_backend.h"
#include "world_ai.h"
#include "native_faction_options.h"
#include "../../ai_loader/ai_loader.h"

/* Candidate ABI: configuration validation is NOT generated-world validation.
 * A backend is accepted only after independently validating island geometry,
 * essential resources and native settlement construction.
 */
typedef WSWorldSettings WSSettings;
typedef int (__cdecl *WSBackend)(const WSSettings *, const char *, char *, uint32_t, char *, uint32_t, void *);
static HINSTANCE dllInstance;
static WSBackend prepareBackend;
static void *backendContext;
static char developmentRoot[MAX_PATH];
static char configurationError[512];
static int developmentConfigured;
extern DWORD WorldSettingsEnginePatchStatus(void);
static const char *cultureNames[8] = {"Moors", "Mongols", "Bedouins", "Aztecs", "Africans", "Native Americans", "Inuit", "Polynesians"};
static const char *className = "Anno1503WorldSettingsCandidate";
static const char *noBackend = "Development candidate: world generation has not been verified. Start is blocked.";
static const char *configuredStatus = "Preparing your map preview...";
static void message(char *out, uint32_t cap, const char *text) {
    if (out && cap) { snprintf(out,cap,"%s",text); out[cap-1]=0; }
}
__declspec(dllexport) int __cdecl WorldSettingsValidateSettings(const WSSettings *s, char *err, uint32_t cap) {
    if (!s || s->size != sizeof(*s)) {message(err,cap,"Invalid settings structure.");return 0;}
    if (s->difficulty<0 || s->difficulty>2) {message(err,cap,"Choose a difficulty.");return 0;}
    if (s->worldSize!=256 && s->worldSize!=512 && s->worldSize!=1024 && s->worldSize!=2048) {message(err,cap,"Choose a supported world size.");return 0;}
    if (s->islandSize<0 || s->islandSize>4) {message(err,cap,"Choose small, medium, Big (strict), Mixed or Big (lenient) islands.");return 0;}
    if (s->islandCount<1 || s->islandCount>128) {message(err,cap,"Enter 1 to 128 islands (development input range; engine limit unverified).");return 0;}
    if (s->spacing<0 || s->spacing>256) {message(err,cap,"Enter 0 to 256 tiles of spacing (development input range).");return 0;}
    if(s->aiCount<0||s->aiCount>3){message(err,cap,"Choose zero to three AI opponents.");return 0;}
    if(s->aiCount&&!WorldSettingsAIExperimentConfigured()){message(err,cap,"The copied Food AI support has not completed activation. Start is blocked.");return 0;}
    if (s->cultures&~255u) {message(err,cap,"Unknown culture bit.");return 0;}
    if(s->factions&~3u){message(err,cap,"Unknown Pirates or Venetians option.");return 0;}
    if(s->startingMoney!=10000&&s->startingMoney!=30000&&s->startingMoney!=50000&&s->startingMoney!=80000&&s->startingMoney!=100000){message(err,cap,"Choose a starting money amount.");return 0;}
    if(s->startingFleet<0||s->startingFleet>2){message(err,cap,"Choose a starting fleet.");return 0;}
    if(s->aiDifficulty<0||s->aiDifficulty>3){message(err,cap,"Choose an AI difficulty.");return 0;}
    if(s->plantFertility<0||s->plantFertility>3){message(err,cap,"Choose plant fertility.");return 0;}
    if(s->mineralFertility<0||s->mineralFertility>3){message(err,cap,"Choose mineral fertility.");return 0;}
    message(err,cap,"");return 1;
}
static int configurationFailure(const char *text) {message(configurationError,sizeof configurationError,text);return 0;}
extern void WorldSettingsSetFailureReporter(void (*reporter)(const char *));
static void reportGenerationFailure(const char *text) {
    MessageBoxA(GetActiveWindow(),text,"Anno 1503 - World Settings",MB_OK|MB_ICONERROR);
}
static int __cdecl developmentStage(const WSSettings*,const char*,char*,uint32_t,char*,uint32_t,void*);
/* The sole registration path accepts a guarded development-copy root. No
 * world settings or seed can be supplied through this export. */
__declspec(dllexport) DWORD WINAPI WorldSettingsConfigureDevelopmentRoot(const wchar_t *root) {
    wchar_t full[MAX_PATH],exe[MAX_PATH],marker[MAX_PATH],roundTrip[MAX_PATH];char ansi[MAX_PATH];
    BY_HANDLE_FILE_INFORMATION copyInfo,exeInfo;
    HANDLE copyDirectory=INVALID_HANDLE_VALUE,exeDirectory=INVALID_HANDLE_VALUE;
    const wchar_t *markerName=L".anno1503-worldsettings-test-copy.json";
    DWORD result=0;
    if(WorldSettingsIsActive())return (DWORD)configurationFailure("A generated world is pending; finish that attempt before changing the development copy.");
    prepareBackend=NULL;backendContext=NULL;developmentConfigured=0;developmentRoot[0]=0;configurationError[0]=0;
    WorldSettingsConfigureAIExperiment(NULL,NULL);
    WorldSettingsSetFailureReporter(NULL);
    if(!root)return (DWORD)configurationFailure("An absolute development-copy folder is required.");
    size_t length=0;while(length<MAX_PATH&&root[length])length++;
    if(length<3||length>=MAX_PATH)return (DWORD)configurationFailure("Development-copy folder must fit the native MAX_PATH limit.");
    int drive=((root[0]>=L'A'&&root[0]<=L'Z')||(root[0]>=L'a'&&root[0]<=L'z'))&&root[1]==L':'&&(root[2]==L'\\'||root[2]==L'/');
    int unc=root[0]==L'\\'&&root[1]==L'\\'&&root[2]!=L'?'&&root[2]!=L'.';
    if(!drive&&!unc)return (DWORD)configurationFailure("Development-copy folder must be an absolute drive or UNC path.");
    DWORD n=GetFullPathNameW(root,MAX_PATH,full,NULL);
    if(!n||n>=MAX_PATH)return (DWORD)configurationFailure("Cannot resolve the development-copy folder within MAX_PATH.");
    for(DWORD i=0;i<n;i++)if(full[i]==L'/')full[i]=L'\\';
    while(n>3&&full[n-1]==L'\\')full[--n]=0;
    DWORD attributes=GetFileAttributesW(full);
    if(attributes==INVALID_FILE_ATTRIBUTES||!(attributes&FILE_ATTRIBUTE_DIRECTORY))return (DWORD)configurationFailure("Development-copy root is not an existing directory.");
    size_t markerLength=wcslen(markerName);
    if(n+1+markerLength>=MAX_PATH)return (DWORD)configurationFailure("Development-copy marker path exceeds MAX_PATH.");
    memcpy(marker,full,(n+1)*sizeof(wchar_t));marker[n]=L'\\';memcpy(marker+n+1,markerName,(markerLength+1)*sizeof(wchar_t));
    attributes=GetFileAttributesW(marker);
    if(attributes==INVALID_FILE_ATTRIBUTES||(attributes&FILE_ATTRIBUTE_DIRECTORY))return (DWORD)configurationFailure("The development-copy marker .anno1503-worldsettings-test-copy.json is missing.");
    n=GetModuleFileNameW(NULL,exe,MAX_PATH);
    if(!n||n>=MAX_PATH)return (DWORD)configurationFailure("Cannot identify the actual game executable folder.");
    wchar_t *slash=wcsrchr(exe,L'\\');
    if(!slash)return (DWORD)configurationFailure("Actual executable path has no absolute parent folder.");
    if(slash==exe+2&&exe[1]==L':')slash[1]=0;else *slash=0;
    copyDirectory=CreateFileW(full,0,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,NULL,OPEN_EXISTING,FILE_FLAG_BACKUP_SEMANTICS,NULL);
    exeDirectory=CreateFileW(exe,0,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,NULL,OPEN_EXISTING,FILE_FLAG_BACKUP_SEMANTICS,NULL);
    if(copyDirectory==INVALID_HANDLE_VALUE||exeDirectory==INVALID_HANDLE_VALUE||!GetFileInformationByHandle(copyDirectory,&copyInfo)||!GetFileInformationByHandle(exeDirectory,&exeInfo)){
        configurationFailure("Cannot verify development-copy and actual executable directory identities.");goto done;
    }
    if(copyInfo.dwVolumeSerialNumber==exeInfo.dwVolumeSerialNumber&&copyInfo.nFileIndexHigh==exeInfo.nFileIndexHigh&&copyInfo.nFileIndexLow==exeInfo.nFileIndexLow){
        configurationFailure("Development-copy root must differ from the actual game executable folder, including directory aliases.");goto done;
    }
    BOOL defaultUsed=FALSE;UINT codePage=GetACP();DWORD flags=codePage==CP_UTF8?WC_ERR_INVALID_CHARS:WC_NO_BEST_FIT_CHARS;
    int bytes=WideCharToMultiByte(codePage,flags,full,-1,ansi,MAX_PATH,NULL,codePage==CP_UTF8?NULL:&defaultUsed);
    if(!bytes||defaultUsed||!MultiByteToWideChar(codePage,MB_ERR_INVALID_CHARS,ansi,-1,roundTrip,MAX_PATH)||wcscmp(full,roundTrip)){
        configurationFailure("Development-copy folder cannot be represented losslessly by the native ANSI scene loader.");goto done;
    }
    memcpy(developmentRoot,ansi,(size_t)bytes);developmentConfigured=1;prepareBackend=developmentStage;backendContext=NULL;
    char sourceRoot[MAX_PATH];defaultUsed=FALSE;
    int sourceBytes=WideCharToMultiByte(codePage,flags,exe,-1,sourceRoot,MAX_PATH,NULL,codePage==CP_UTF8?NULL:&defaultUsed);
    if(sourceBytes&&!defaultUsed&&MultiByteToWideChar(codePage,MB_ERR_INVALID_CHARS,sourceRoot,-1,roundTrip,MAX_PATH)&&!wcscmp(exe,roundTrip))WorldSettingsConfigureAIExperiment(developmentRoot,sourceRoot);
    WorldSettingsSetFailureReporter(reportGenerationFailure);result=1;
    done:if(copyDirectory!=INVALID_HANDLE_VALUE)CloseHandle(copyDirectory);if(exeDirectory!=INVALID_HANDLE_VALUE)CloseHandle(exeDirectory);return result;
}
/* Remote-thread-compatible error delivery. Caller supplies a writable512-byte
 * buffer in this process; result includes the terminating NUL. */
__declspec(dllexport) DWORD WINAPI WorldSettingsCopyConfigurationError(void *buffer) {
    if(!buffer)return 0;char *out=(char*)buffer;DWORD n=0;
    do{out[n]=configurationError[n];n++;}while(n<sizeof configurationError&&configurationError[n-1]);
    out[n-1]=0;return n;
}
__declspec(dllexport) void __cdecl WorldSettingsSetBackend(WSBackend callback, void *context) {
    (void)context;
    if(callback){configurationFailure("Backend registration requires WorldSettingsConfigureDevelopmentRoot and a marked development copy.");return;}
    prepareBackend=NULL;backendContext=NULL;developmentConfigured=0;developmentRoot[0]=0;
    WorldSettingsSetFailureReporter(NULL);
}
__declspec(dllexport) uint32_t __cdecl WorldSettingsSettingsSize(void) { return sizeof(WSSettings); }

enum {ID_DIFFICULTY=101,ID_SIZE,ID_COUNT,ID_SPACING,ID_AI,ID_MONEY,ID_FLEET,ID_AI_DIFFICULTY,ID_PLANT_FERTILITY,ID_MINERAL_FERTILITY,ID_WORLD_SIZE,ID_CULTURE=120,ID_FACTION=130,ID_STATUS=140,ID_START=151,ID_BACK=152,ID_PREVIEW=153,ID_REGENERATE=154};
enum {WS_PREVIEW_TIMER=1,WS_PREVIEW_MESSAGE=WM_APP+17,WS_MENU_WIDTH=1120,WS_MENU_HEIGHT=810};
typedef struct DialogState {
 HWND owner,window,preview;HFONT font;int ownsFont,result,done,creating,previewValid,previewBusy;
 int scale;void *setup;uint8_t *frame;WSSettings settings,previewSettings;
 uint32_t previewSeed,previewCount;WSPlanIsland previewIslands[128];
} DialogState;
static int scaled(const DialogState*d,int value){return MulDiv(value,d->scale,1000);}
static HWND control(DialogState *d, const char *cls, const char *text, DWORD style, int x,int y,int w,int h,int id) {
 HWND c=CreateWindowExA(0,cls,text,WS_CHILD|WS_VISIBLE|style,scaled(d,x),scaled(d,y),scaled(d,w),scaled(d,h),d->window,(HMENU)(INT_PTR)id,dllInstance,NULL);
 if(c)SendMessageA(c,WM_SETFONT,(WPARAM)d->font,TRUE);return c;
}
static void label(DialogState*d,const char*t,int x,int y,int w,int h){control(d,"STATIC",t,0,x,y,w,h,0);}
static void fillCombo(HWND h,const char **values,int count,int selected){for(int i=0;i<count;i++)SendMessageA(h,CB_ADDSTRING,0,(LPARAM)values[i]);SendMessageA(h,CB_SETCURSEL,selected,0);}
static int integer(HWND w,int id,int *out){char b[64],*end;GetDlgItemTextA(w,id,b,sizeof b);long v=strtol(b,&end,10);if(!b[0]||*end||v<0||v>2147483647)return 0;*out=(int)v;return 1;}
static void status(DialogState*d,const char*t){SetDlgItemTextA(d->window,ID_STATUS,t);}
static int collect(DialogState*d){
 WSSettings s={0};s.size=sizeof s;char err[512];s.difficulty=(int)SendDlgItemMessageA(d->window,ID_DIFFICULTY,CB_GETCURSEL,0,0);s.islandSize=(int)SendDlgItemMessageA(d->window,ID_SIZE,CB_GETCURSEL,0,0);
 static const int worlds[]={256,512,1024,2048};int world=(int)SendDlgItemMessageA(d->window,ID_WORLD_SIZE,CB_GETCURSEL,0,0);s.worldSize=world>=0&&world<4?worlds[world]:0;
 if(!integer(d->window,ID_COUNT,&s.islandCount)||!integer(d->window,ID_SPACING,&s.spacing)){status(d,"Enter whole numbers for island count and spacing.");return 0;}
 s.aiCount=(int)SendDlgItemMessageA(d->window,ID_AI,CB_GETCURSEL,0,0);
 static const int amounts[]={10000,30000,50000,80000,100000};
 int money=(int)SendDlgItemMessageA(d->window,ID_MONEY,CB_GETCURSEL,0,0);
 s.startingMoney=money>=0&&money<5?amounts[money]:0;
 s.startingFleet=(int)SendDlgItemMessageA(d->window,ID_FLEET,CB_GETCURSEL,0,0);
 s.aiDifficulty=(int)SendDlgItemMessageA(d->window,ID_AI_DIFFICULTY,CB_GETCURSEL,0,0);
 s.plantFertility=(int)SendDlgItemMessageA(d->window,ID_PLANT_FERTILITY,CB_GETCURSEL,0,0);
 s.mineralFertility=(int)SendDlgItemMessageA(d->window,ID_MINERAL_FERTILITY,CB_GETCURSEL,0,0);
 for(int i=0;i<2;i++)if(SendDlgItemMessageA(d->window,ID_FACTION+i,BM_GETCHECK,0,0)==BST_CHECKED)s.factions|=1u<<i;
 for(int i=0;i<8;i++)if(SendDlgItemMessageA(d->window,ID_CULTURE+i,BM_GETCHECK,0,0)==BST_CHECKED)s.cultures|=1u<<i;
 if(!WorldSettingsValidateSettings(&s,err,sizeof err)){status(d,err);return 0;}d->settings=s;return 1;
}
#include "world_menu_preview.inc"
static int __cdecl developmentStage(const WSSettings *settings,const char *selected,char *path,uint32_t pathCap,char *error,uint32_t errorCap,void *context) {
    (void)selected;DialogState*d=(DialogState*)context;
    if(!developmentConfigured||!developmentRoot[0]){message(error,errorCap,noBackend);return 0;}
    if(!d||!d->previewValid||memcmp(settings,&d->previewSettings,sizeof(*settings))){message(error,errorCap,"The map preview is out of date. Generate a new preview before starting.");return 0;}
    _Static_assert(sizeof(WSSettings)==sizeof(WSWorldSettings),"World Settings backend ABI differs");
    return WorldSettingsStagePreviewScene(settings,developmentRoot,d->previewSeed,d->previewIslands,d->previewCount,path,pathCap,error,errorCap);
}
static void start(DialogState*d){
 WorldSettingsAIProfileAttemptFinished(0); /* a new Start cannot inherit prior verification */
 if(!collect(d))return;
 if(!d->previewValid||memcmp(&d->settings,&d->previewSettings,sizeof(d->settings))){invalidatePreview(d);status(d,"Settings changed. Wait for the updated preview before starting.");SetTimer(d->window,WS_PREVIEW_TIMER,200,NULL);return;}
 if(!prepareBackend || !d->frame || !d->setup){status(d,noBackend);return;}
 if(!WorldSettingsEnginePatchStatus()){status(d,"The expanded engine has not completed activation. Close and relaunch Anno, then activate this build before starting a world.");return;}
 char path[260]={0},error[512]={0};
 int valid=prepareBackend(&d->settings,NULL,path,sizeof path,error,sizeof error,d);
 path[259]=0;error[511]=0;
 if(valid!=1 || !path[0]){invalidatePreview(d);status(d,error[0]?error:"World validation did not succeed. Start is blocked.");return;}
 /* Staging permits the native factory attempt. Its separate loaded-world
  * validator must pass before the scene can reach simulation. The factory
  * bridge substitutes the absolute pending path without altering Frame data. */
 DWORD attrs=GetFileAttributesA(path);
 if(attrs==INVALID_FILE_ATTRIBUTES || attrs&FILE_ATTRIBUTE_DIRECTORY){WorldSettingsFinishAttempt(0);invalidatePreview(d);status(d,"Prepared world file is missing. Start is blocked.");return;}
 if(!WorldSettingsBindStockAIProfiles(d->setup,d->settings.difficulty,d->settings.aiCount,error,sizeof error)){WorldSettingsFinishAttempt(0);invalidatePreview(d);status(d,error);return;}
 if(!wsBindNativeFactionOptions(d->frame,d->settings.factions)){WorldSettingsFinishAttempt(0);invalidatePreview(d);status(d,"Native faction options are unavailable. Start is blocked.");return;}
 WorldSettingsExpectAIProfiles(d->settings.aiCount,d->settings.factions,d->settings.aiDifficulty);
 d->result=1;d->done=1;DestroyWindow(d->window);
}
static LRESULT CALLBACK windowProc(HWND w,UINT msg,WPARAM wp,LPARAM lp){
 DialogState*d=(DialogState*)GetWindowLongPtrA(w,GWLP_USERDATA);
 if(msg==WM_NCCREATE){CREATESTRUCTA*c=(CREATESTRUCTA*)lp;d=(DialogState*)c->lpCreateParams;d->window=w;SetWindowLongPtrA(w,GWLP_USERDATA,(LONG_PTR)d);}
 if(!d)return DefWindowProcA(w,msg,wp,lp);
 switch(msg){
 case WM_CREATE:{
  const char*diff[]={"Easy","Medium","Hard"};
  const char*size[]={"Small (smallest available)","Medium (128 tiles)","Big (strict)","Mixed","Big (lenient)"};
  const char*worlds[]={"Small (256 x 256)","Medium (512 x 512)","Big (1024 x 1024)","Huge (2048 x 2048) - experimental"};
  const char*ai[]={"0","1","2","3"};
  const char*money[]={"10,000","30,000","50,000","80,000","100,000"};
  const char*fleet[]={"Single ship (small trade ship)","War fleet (3 armed ships)","Merchant fleet (3 trade ships)"};
  const char*aggression[]={"Peaceful","Easy","Medium","Hard"};
  const char*fertility[]={"Very fertile","Medium fertility","Low fertility","Mixed"};
  label(d,"World Settings",24,18,632,28);
  label(d,"World size",24,58,296,20);
  fillCombo(control(d,"COMBOBOX","",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,24,80,296,180,ID_WORLD_SIZE),worlds,4,2);
  label(d,"Island count",348,58,296,20);
  control(d,"EDIT","24",WS_BORDER|ES_NUMBER|WS_TABSTOP,348,80,296,27,ID_COUNT);
  label(d,"Island size",24,116,296,20);
  fillCombo(control(d,"COMBOBOX","",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,24,138,296,180,ID_SIZE),size,5,3);
  label(d,"Minimum spacing (tiles)",348,116,296,20);
  control(d,"EDIT","16",WS_BORDER|ES_NUMBER|WS_TABSTOP,348,138,296,27,ID_SPACING);
  label(d,"Stock difficulty preset",24,174,296,20);
  fillCombo(control(d,"COMBOBOX","",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,24,196,296,180,ID_DIFFICULTY),diff,3,1);
  label(d,"AI opponents",348,174,296,20);
  fillCombo(control(d,"COMBOBOX","",CBS_DROPDOWNLIST|WS_TABSTOP,348,196,296,100,ID_AI),ai,4,0);
  label(d,"Starting money",24,232,296,20);
  fillCombo(control(d,"COMBOBOX","",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,24,254,296,180,ID_MONEY),money,5,1);
  label(d,"Starting fleet",348,232,296,20);
  fillCombo(control(d,"COMBOBOX","",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,348,254,296,180,ID_FLEET),fleet,3,0);
  label(d,"AI difficulty",24,290,296,20);
  fillCombo(control(d,"COMBOBOX","",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,24,312,296,180,ID_AI_DIFFICULTY),aggression,4,1);
  label(d,"Each world includes all six climates.",348,312,296,28);
  label(d,"Plant fertility",24,348,296,20);
  fillCombo(control(d,"COMBOBOX","",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,24,370,296,180,ID_PLANT_FERTILITY),fertility,4,1);
  label(d,"Mineral fertility",348,348,296,20);
  fillCombo(control(d,"COMBOBOX","",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,348,370,296,180,ID_MINERAL_FERTILITY),fertility,4,1);
  label(d,"Strict: largest available for each climate/culture. Lenient can use smaller islands.\r\nWar: 1 big trade + 2 small warships, all fully armed.\r\nMerchant: 1 big + 2 small trade ships; each has 40t tools and 40t wood.\r\nClimate still matters; essential resources remain worldwide.",24,408,632,64);
  label(d,"Native cultures",24,480,632,22);
  for(int i=0;i<8;i++){HWND c=control(d,"BUTTON",cultureNames[i],BS_AUTOCHECKBOX|WS_TABSTOP,24+(i%2)*324,508+(i/2)*30,296,24,ID_CULTURE+i);SendMessageA(c,BM_SETCHECK,BST_CHECKED,0);}
  label(d,"Pirates and Venetians",24,634,632,20);
  const char*special[]={"Pirates","Venetians"};for(int i=0;i<2;i++){HWND c=control(d,"BUTTON",special[i],BS_AUTOCHECKBOX|WS_TABSTOP,24+i*324,660,296,24,ID_FACTION+i);SendMessageA(c,BM_SETCHECK,BST_CHECKED,0);}
  label(d,"Status",24,700,632,20);control(d,"STATIC",developmentConfigured&&prepareBackend?configuredStatus:noBackend,SS_LEFT,24,724,632,42,ID_STATUS);
  label(d,"Map preview",688,58,408,22);
  d->preview=CreateWindowExA(0,previewClassName,"",WS_CHILD|WS_VISIBLE|WS_BORDER,scaled(d,688),scaled(d,90),scaled(d,408),scaled(d,408),w,(HMENU)(INT_PTR)ID_PREVIEW,dllInstance,d);
  if(!d->preview)return -1;
  label(d,"Simplified coastlines. Start uses this preview.",688,510,408,24);
  for(int i=0;i<6;i++)label(d,previewClimateNames[i],710+(i%2)*212,546+(i/2)*24,174,20);
  label(d,"P: Pirates     V: Venetians",688,632,408,24);
  control(d,"BUTTON","Regenerate map",BS_PUSHBUTTON|WS_TABSTOP,688,684,196,32,ID_REGENERATE);
  label(d,"Islands are spread automatically. Spacing sets the minimum gap between them.",688,730,408,40);
  control(d,"BUTTON","Back",BS_PUSHBUTTON|WS_TABSTOP,388,768,120,32,ID_BACK);control(d,"BUTTON","Start",BS_DEFPUSHBUTTON|WS_TABSTOP,528,768,120,32,ID_START);
  EnableWindow(GetDlgItem(w,ID_START),FALSE);d->creating=0;PostMessageA(w,WS_PREVIEW_MESSAGE,0,0);
  SetFocus(GetDlgItem(w,ID_DIFFICULTY));return 0;}
 case WM_COMMAND:{
  int id=LOWORD(wp),notice=HIWORD(wp);
  if(id==ID_BACK){WorldSettingsFinishAttempt(0);d->done=1;DestroyWindow(w);return 0;}
  if(id==ID_START){start(d);return 0;}
  if(id==ID_REGENERATE){KillTimer(w,WS_PREVIEW_TIMER);generatePreview(d,1);return 0;}
  if(!d->creating&&settingsNotification(id,notice)){invalidatePreview(d);SetTimer(w,WS_PREVIEW_TIMER,250,NULL);return 0;}
  break;}
 case WM_TIMER:if(wp==WS_PREVIEW_TIMER){KillTimer(w,WS_PREVIEW_TIMER);generatePreview(d,0);return 0;}break;
 case WS_PREVIEW_MESSAGE:if(!d->done)generatePreview(d,0);return 0;
 case WM_PAINT:{PAINTSTRUCT ps;HDC dc=BeginPaint(w,&ps);for(int i=0;i<6;i++){HBRUSH brush=CreateSolidBrush(previewClimateColors[i]);RECT r={scaled(d,688+(i%2)*212),scaled(d,550+(i/2)*24),scaled(d,702+(i%2)*212),scaled(d,564+(i/2)*24)};FillRect(dc,&r,brush);DeleteObject(brush);}EndPaint(w,&ps);return 0;}
 case WM_CLOSE:WorldSettingsFinishAttempt(0);d->done=1;DestroyWindow(w);return 0;
 case WM_DESTROY:KillTimer(w,WS_PREVIEW_TIMER);d->done=1;return 0;
 }
 return DefWindowProcA(w,msg,wp,lp);
}
static int dialog(HWND owner,void*setup,uint8_t*frame){
 DialogState d;memset(&d,0,sizeof d);d.owner=owner;d.setup=setup;d.frame=frame;d.creating=1;d.scale=1000;
 RECT area={0};if(!SystemParametersInfoA(SPI_GETWORKAREA,0,&area,0))return 0;RECT chrome={0,0,0,0};if(!AdjustWindowRectEx(&chrome,WS_CAPTION|WS_SYSMENU,FALSE,WS_EX_DLGMODALFRAME|WS_EX_CONTROLPARENT))return 0;
 int availableW=(area.right-area.left)-(chrome.right-chrome.left)-24,availableH=(area.bottom-area.top)-(chrome.bottom-chrome.top)-24;
 int sx=MulDiv(availableW,1000,WS_MENU_WIDTH),sy=MulDiv(availableH,1000,WS_MENU_HEIGHT);if(sx<d.scale)d.scale=sx;if(sy<d.scale)d.scale=sy;if(d.scale<500)return 0;
 d.font=(HFONT)GetStockObject(DEFAULT_GUI_FONT);LOGFONTA font;
 if(d.scale!=1000&&GetObjectA(d.font,sizeof font,&font)){font.lfHeight=MulDiv(font.lfHeight,d.scale,1000);HFONT resized=CreateFontIndirectA(&font);if(resized){d.font=resized;d.ownsFont=1;}}
 WNDCLASSEXA c={0};c.cbSize=sizeof c;c.lpfnWndProc=windowProc;c.hInstance=dllInstance;c.hCursor=LoadCursorA(NULL,IDC_ARROW);c.hbrBackground=(HBRUSH)(COLOR_BTNFACE+1);c.lpszClassName=className;
 if((!RegisterClassExA(&c)&&GetLastError()!=ERROR_CLASS_ALREADY_EXISTS)||!registerPreviewClass()){if(d.ownsFont)DeleteObject(d.font);return 0;}
 RECT rc={0,0,scaled(&d,WS_MENU_WIDTH),scaled(&d,WS_MENU_HEIGHT)};AdjustWindowRectEx(&rc,WS_CAPTION|WS_SYSMENU,FALSE,WS_EX_DLGMODALFRAME|WS_EX_CONTROLPARENT);
 int width=rc.right-rc.left,height=rc.bottom-rc.top;
 int x=area.left+((area.right-area.left)-width)/2,y=area.top+((area.bottom-area.top)-height)/2;if(y<area.top)y=area.top;
 BOOL wasEnabled=owner?IsWindowEnabled(owner):FALSE;
 HWND w=CreateWindowExA(WS_EX_DLGMODALFRAME|WS_EX_CONTROLPARENT,className,"Anno 1503 - World Settings (Development)",WS_CAPTION|WS_SYSMENU,x,y,width,height,owner,NULL,dllInstance,&d);
 if(!w){if(d.ownsFont)DeleteObject(d.font);return 0;}
 if(owner&&wasEnabled)EnableWindow(owner,FALSE);ShowWindow(w,SW_SHOW);UpdateWindow(w);
 MSG m;int r=1;while(!d.done&&(r=GetMessageA(&m,NULL,0,0))>0){if(!IsDialogMessageA(w,&m)){TranslateMessage(&m);DispatchMessageA(&m);}}
 if(r==0)PostQuitMessage((int)m.wParam);if(IsWindow(w))DestroyWindow(w);if(owner&&wasEnabled){EnableWindow(owner,TRUE);SetActiveWindow(owner);}if(d.ownsFont)DeleteObject(d.font);return d.result;
}
__declspec(dllexport) int __cdecl WorldSettingsBeforeStart(void*setup,void*frame){return dialog(GetActiveWindow(),setup,(uint8_t*)frame);}
__declspec(dllexport) int __cdecl WorldSettingsShowDevelopmentDialog(HWND owner){return dialog(owner,NULL,NULL);}
/* Include in WorldSettings.c and link selection.c. Private, not installed.
 * The incoming Frame/page pointers are supplied only by the fingerprinted
 * native bridge in this process, under the same trust contract as BeforeStart.
 */
extern int WorldSettingsClassifyDirectSelection(const char *,uint32_t,const unsigned char *);
__declspec(dllexport) int __cdecl WorldSettingsBeforeDirectStart(void *page,void *frame) {
    if(!page||!frame)return 0;
    const unsigned char *base=(const unsigned char*)frame;
    int selected=WorldSettingsClassifyDirectSelection((const char*)base+0xc7430,260,base+0xc7534);
    if(selected==0)return 1; /* Original tutorial/mission path, no UI or commit. */
    if(selected!=1){
        reportGenerationFailure("The selected endless scene differs from the inspected development source. Start is blocked.");
        return 0;
    }
    void **children=*(void***)((unsigned char*)page+0x21b0);
    if(!children||!children[0]){
        reportGenerationFailure("The native endless setup object is unavailable. Start is blocked.");
        return 0;
    }
    return WorldSettingsBeforeStart(children[0],frame)>0?2:0;
}

BOOL WINAPI DllMain(HINSTANCE h,DWORD why,LPVOID reserved){(void)reserved;if(why==DLL_PROCESS_ATTACH)dllInstance=h;return TRUE;}


