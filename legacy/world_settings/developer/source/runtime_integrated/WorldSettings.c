#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <wchar.h>
#include "../engine_resume/runtime/world_backend.h"

/* Candidate ABI: configuration validation is NOT generated-world validation.
 * A backend is accepted only after independently validating island geometry,
 * essential resources and native settlement construction.
 */
typedef struct WSSettings {
    uint32_t size;
    int32_t difficulty;       /* 0 easy, 1 medium, 2 hard */
    int32_t islandSize;       /* 0 small, 1 medium, 2 large, 3 mixed */
    int32_t islandCount;      /* application input bound, NOT an engine limit */
    int32_t spacing;          /* minimum tile clearance requested */
    int32_t aiCount;          /* food AI planning has not been implemented */
    uint32_t cultures;        /* bits in cultureNames order below */
} WSSettings;
typedef int (__cdecl *WSBackend)(const WSSettings *, const char *, char *, uint32_t, char *, uint32_t, void *);
static HINSTANCE dllInstance;
static WSBackend prepareBackend;
static void *backendContext;
static char developmentRoot[MAX_PATH];
static char configurationError[512];
static int developmentConfigured;
static const char *cultureNames[8] = {"Moors", "Mongols", "Bedouins", "Aztecs", "Africans", "Native Americans", "Inuit", "Polynesians"};
static const char *className = "Anno1503WorldSettingsCandidate";
static const char *noBackend = "Development candidate: world generation has not been verified. Start is blocked.";
static const char *configuredStatus = "Development copy configured. Start prepares the selected world; loaded islands, resources and native cultures must pass validation before play.";
static void message(char *out, uint32_t cap, const char *text) {
    if (out && cap) { snprintf(out,cap,"%s",text); out[cap-1]=0; }
}
__declspec(dllexport) int __cdecl WorldSettingsValidateSettings(const WSSettings *s, char *err, uint32_t cap) {
    if (!s || s->size != sizeof(*s)) {message(err,cap,"Invalid settings structure.");return 0;}
    if (s->difficulty<0 || s->difficulty>2) {message(err,cap,"Choose a difficulty.");return 0;}
    if (s->islandSize<0 || s->islandSize>3) {message(err,cap,"Choose small, medium, large or mixed islands.");return 0;}
    if (s->islandCount<1 || s->islandCount>128) {message(err,cap,"Enter 1 to 128 islands (development input range; engine limit unverified).");return 0;}
    if (s->spacing<0 || s->spacing>256) {message(err,cap,"Enter 0 to 256 tiles of spacing (development input range).");return 0;}
    if (s->aiCount!=0) {message(err,cap,"Combined Food Mod supports zero AI opponents; extra-food AI planning is unimplemented.");return 0;}
    if (s->cultures&~255u) {message(err,cap,"Unknown culture bit.");return 0;}
    message(err,cap,"");return 1;
}
static int configurationFailure(const char *text) {message(configurationError,sizeof configurationError,text);return 0;}
extern void WorldSettingsSetFailureReporter(void (*reporter)(const char *));
static void reportGenerationFailure(const char *text) {
    MessageBoxA(GetActiveWindow(),text,"Anno 1503 - World Settings",MB_OK|MB_ICONERROR);
}
static int __cdecl developmentStage(const WSSettings *settings,const char *selected,char *path,uint32_t pathCap,char *error,uint32_t errorCap,void *context) {
    (void)selected;(void)context;
    if(!developmentConfigured||!developmentRoot[0]){message(error,errorCap,noBackend);return 0;}
    WSWorldSettings nativeSettings;
    _Static_assert(sizeof(WSSettings)==sizeof(WSWorldSettings),"World Settings backend ABI differs");
    memcpy(&nativeSettings,settings,sizeof nativeSettings);
    return WorldSettingsStageScene(&nativeSettings,developmentRoot,GetTickCount(),path,pathCap,error,errorCap);
}
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

enum {ID_DIFFICULTY=101,ID_SIZE,ID_COUNT,ID_SPACING,ID_AI,ID_CULTURE=120,ID_STATUS=140,ID_START=151,ID_BACK=152};
typedef struct DialogState {HWND owner,window;HFONT font;int result;int done;void *setup;uint8_t *frame;WSSettings settings;} DialogState;
static HWND control(DialogState *d, const char *cls, const char *text, DWORD style, int x,int y,int w,int h,int id) {
 HWND c=CreateWindowExA(0,cls,text,WS_CHILD|WS_VISIBLE|style,x,y,w,h,d->window,(HMENU)(INT_PTR)id,dllInstance,NULL);
 if(c)SendMessageA(c,WM_SETFONT,(WPARAM)d->font,TRUE);return c;
}
static void label(DialogState*d,const char*t,int x,int y,int w,int h){control(d,"STATIC",t,0,x,y,w,h,0);}
static void fillCombo(HWND h,const char **values,int count,int selected){for(int i=0;i<count;i++)SendMessageA(h,CB_ADDSTRING,0,(LPARAM)values[i]);SendMessageA(h,CB_SETCURSEL,selected,0);}
static int integer(HWND w,int id,int *out){char b[64],*end;GetDlgItemTextA(w,id,b,sizeof b);long v=strtol(b,&end,10);if(!b[0]||*end||v<0||v>2147483647)return 0;*out=(int)v;return 1;}
static void status(DialogState*d,const char*t){SetDlgItemTextA(d->window,ID_STATUS,t);}
static int collect(DialogState*d){
 WSSettings s={0};s.size=sizeof s;char err[512];s.difficulty=(int)SendDlgItemMessageA(d->window,ID_DIFFICULTY,CB_GETCURSEL,0,0);s.islandSize=(int)SendDlgItemMessageA(d->window,ID_SIZE,CB_GETCURSEL,0,0);
 if(!integer(d->window,ID_COUNT,&s.islandCount)||!integer(d->window,ID_SPACING,&s.spacing)){status(d,"Enter whole numbers for island count and spacing.");return 0;}
 s.aiCount=0;for(int i=0;i<8;i++)if(SendDlgItemMessageA(d->window,ID_CULTURE+i,BM_GETCHECK,0,0)==BST_CHECKED)s.cultures|=1u<<i;
 if(!WorldSettingsValidateSettings(&s,err,sizeof err)){status(d,err);return 0;}d->settings=s;return 1;
}
static void start(DialogState*d){
 if(!collect(d))return;
 if(!prepareBackend || !d->frame || !d->setup){status(d,noBackend);return;}
 char path[260]={0},error[512]={0};
 int valid=prepareBackend(&d->settings,NULL,path,sizeof path,error,sizeof error,backendContext);
 path[259]=0;error[511]=0;
 if(valid!=1 || !path[0]){status(d,error[0]?error:"World validation did not succeed. Start is blocked.");return;}
 /* Staging permits the native factory attempt. Its separate loaded-world
  * validator must pass before the scene can reach simulation. The factory
  * bridge substitutes the absolute pending path without altering Frame data. */
 DWORD attrs=GetFileAttributesA(path);
 if(attrs==INVALID_FILE_ATTRIBUTES || attrs&FILE_ATTRIBUTE_DIRECTORY){WorldSettingsFinishAttempt(0);status(d,"Prepared world file is missing. Start is blocked.");return;}
 memset((uint8_t*)d->setup+0x2280,0,7); /* preserve supported zero-AI food gameplay */
 d->result=1;d->done=1;DestroyWindow(d->window);
}
static LRESULT CALLBACK windowProc(HWND w,UINT msg,WPARAM wp,LPARAM lp){
 DialogState*d=(DialogState*)GetWindowLongPtrA(w,GWLP_USERDATA);
 if(msg==WM_NCCREATE){CREATESTRUCTA*c=(CREATESTRUCTA*)lp;d=(DialogState*)c->lpCreateParams;d->window=w;SetWindowLongPtrA(w,GWLP_USERDATA,(LONG_PTR)d);}
 if(!d)return DefWindowProcA(w,msg,wp,lp);
 switch(msg){
 case WM_CREATE:{
  const char*diff[]={"Easy","Medium","Hard"};const char*size[]={"Small (smallest available)","Medium (128 tiles)","Large (largest available)","Mixed"};const char*ai[]={"0 (Combined Food Mod)"};
  label(d,"World Settings",24,18,550,28);label(d,"Difficulty",24,60,245,20);
  fillCombo(control(d,"COMBOBOX","",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,24,84,260,180,ID_DIFFICULTY),diff,3,1);
  label(d,"Island size",320,60,245,20);
  fillCombo(control(d,"COMBOBOX","",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,320,84,260,180,ID_SIZE),size,4,3);
  label(d,"Island count",24,126,245,20);
  control(d,"EDIT","24",WS_BORDER|ES_NUMBER|WS_TABSTOP,24,150,260,27,ID_COUNT);
  label(d,"Minimum spacing (tiles)",320,126,260,20);
  control(d,"EDIT","16",WS_BORDER|ES_NUMBER|WS_TABSTOP,320,150,260,27,ID_SPACING);
  label(d,"Small/Large: smallest/largest available per climate and culture.\r\nSmall:64/80/128; Medium:128; Large:128/256; Mixed:any. Difficulty is separate.",24,190,556,30);
  label(d,"AI opponents",24,224,245,20);fillCombo(control(d,"COMBOBOX","",CBS_DROPDOWNLIST|WS_TABSTOP,24,248,556,100,ID_AI),ai,1,0);
  label(d,"AI opponents require additional Food Mod support.",24,288,556,40);
  label(d,"Native cultures",24,338,550,22);
  for(int i=0;i<8;i++){HWND c=control(d,"BUTTON",cultureNames[i],BS_AUTOCHECKBOX|WS_TABSTOP,24+(i%2)*296,368+(i/2)*34,260,26,ID_CULTURE+i);SendMessageA(c,BM_SETCHECK,BST_CHECKED,0);}
  label(d,"Status",24,514,550,20);control(d,"STATIC",developmentConfigured&&prepareBackend?configuredStatus:noBackend,SS_LEFT,24,540,556,68,ID_STATUS);
  control(d,"BUTTON","Back",BS_PUSHBUTTON|WS_TABSTOP,320,624,120,32,ID_BACK);control(d,"BUTTON","Start",BS_DEFPUSHBUTTON|WS_TABSTOP,460,624,120,32,ID_START);
  SetFocus(GetDlgItem(w,ID_DIFFICULTY));return 0;}
 case WM_COMMAND:if(LOWORD(wp)==ID_BACK){d->done=1;DestroyWindow(w);return 0;}if(LOWORD(wp)==ID_START){start(d);return 0;}break;
 case WM_CLOSE:d->done=1;DestroyWindow(w);return 0;
 case WM_DESTROY:d->done=1;return 0;
 }
 return DefWindowProcA(w,msg,wp,lp);
}
static int dialog(HWND owner,void*setup,uint8_t*frame){
 DialogState d;memset(&d,0,sizeof d);d.owner=owner;d.setup=setup;d.frame=frame;
 d.font=(HFONT)GetStockObject(DEFAULT_GUI_FONT);
 WNDCLASSEXA c={0};c.cbSize=sizeof c;c.lpfnWndProc=windowProc;c.hInstance=dllInstance;c.hCursor=LoadCursorA(NULL,IDC_ARROW);c.hbrBackground=(HBRUSH)(COLOR_BTNFACE+1);c.lpszClassName=className;
 if(!RegisterClassExA(&c) && GetLastError()!=ERROR_CLASS_ALREADY_EXISTS)return 0;
 RECT rc={0,0,608,680};AdjustWindowRectEx(&rc,WS_CAPTION|WS_SYSMENU,FALSE,WS_EX_DLGMODALFRAME|WS_EX_CONTROLPARENT);
 int width=rc.right-rc.left,height=rc.bottom-rc.top;RECT area;SystemParametersInfoA(SPI_GETWORKAREA,0,&area,0);
 int x=area.left+((area.right-area.left)-width)/2,y=area.top+((area.bottom-area.top)-height)/2;if(y<area.top)y=area.top;
 BOOL wasEnabled=owner?IsWindowEnabled(owner):FALSE;
 HWND w=CreateWindowExA(WS_EX_DLGMODALFRAME|WS_EX_CONTROLPARENT,className,"Anno 1503 - World Settings (Development)",WS_CAPTION|WS_SYSMENU,x,y,width,height,owner,NULL,dllInstance,&d);
 if(!w)return 0;
 if(owner&&wasEnabled)EnableWindow(owner,FALSE);ShowWindow(w,SW_SHOW);UpdateWindow(w);
 MSG m;int r=1;while(!d.done&&(r=GetMessageA(&m,NULL,0,0))>0){if(!IsDialogMessageA(w,&m)){TranslateMessage(&m);DispatchMessageA(&m);}}
 if(r==0)PostQuitMessage((int)m.wParam);if(IsWindow(w))DestroyWindow(w);if(owner&&wasEnabled){EnableWindow(owner,TRUE);SetActiveWindow(owner);}return d.result;
}
__declspec(dllexport) int __cdecl WorldSettingsBeforeStart(void*setup,void*frame){return dialog(GetActiveWindow(),setup,(uint8_t*)frame);}
__declspec(dllexport) int __cdecl WorldSettingsShowDevelopmentDialog(HWND owner){return dialog(owner,NULL,NULL);}
BOOL WINAPI DllMain(HINSTANCE h,DWORD why,LPVOID reserved){(void)reserved;if(why==DLL_PROCESS_ATTACH)dllInstance=h;return TRUE;}


