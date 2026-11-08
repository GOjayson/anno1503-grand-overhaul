/* Menu state, clipboard and local named presets. All world options are
 * collected inside the game; no external settings file is required. */
#include "menu_presets_codec.inc"
#include "menu_island_text.inc"
static int collect(DialogState*d);
static void invalidatePreview(DialogState*d);
static int generatePreview(DialogState*d,int regenerate);
static uint32_t freshPreviewSeed(uint32_t previous);

static void wsMenuPage(DialogState*d,int page){
 if(page<0||page>4)return;d->page=page;
 for(uint32_t i=0;i<d->pageControlCount;i++)ShowWindow(d->pageControls[i],d->controlPages[i]==page?SW_SHOW:SW_HIDE);
 for(int i=0;i<5;i++)SendDlgItemMessageA(d->window,ID_TAB_WORLD+i,BM_SETSTATE,i==page,0);
}
static void wsMenuPutNumber(DialogState*d,int id,int32_t value){char text[32];snprintf(text,sizeof text,"%d",value);SetDlgItemTextA(d->window,id,text);}
static void wsMenuPutSeed(DialogState*d,uint32_t value){char text[16];snprintf(text,sizeof text,"%u",value);SetDlgItemTextA(d->window,ID_SEED,text);}
static int wsMenuReadSeed(DialogState*d,uint32_t*out){
 char text[16];int length=GetWindowTextLengthA(GetDlgItem(d->window,ID_SEED));
 if(length<1||length>10){status(d,"Enter a map seed from 0 to 4294967295.");return 0;}
 GetDlgItemTextA(d->window,ID_SEED,text,sizeof text);
 if(!wsMenuUnsigned(text,(size_t)length,out)){status(d,"Enter a map seed from 0 to 4294967295.");return 0;}return 1;
}
static void wsMenuCargoControls(DialogState*d){
 int custom=SendDlgItemMessageA(d->window,ID_CARGO_MODE,BM_GETCHECK,0,0)==BST_CHECKED;
 for(int id=ID_CARGO_TOOLS;id<=ID_CARGO_FOOD;id++)EnableWindow(GetDlgItem(d->window,id),custom);
}
static void wsMenuFairControls(DialogState*d){
 int balanced=SendDlgItemMessageA(d->window,ID_FAIR_STARTS,BM_GETCHECK,0,0)==BST_CHECKED;
 EnableWindow(GetDlgItem(d->window,ID_START_SEPARATION),balanced);
}
static void wsMenuIslandInfo(DialogState*d){
 char text[4096],summary[768];WSIslandDetails details={0};details.size=sizeof details;
 int selected=d->previewValid&&d->inspectedIsland>=0&&(uint32_t)d->inspectedIsland<d->previewCount;
 int known=selected&&WorldSettingsIslandDetails((uint32_t)d->inspectedIsland,&details);
 if(known){
  if(!wsMenuDescribeIsland(&d->previewIslands[d->inspectedIsland],&details,text,sizeof text))
   snprintf(text,sizeof text,"The island information could not be displayed.");
 }else snprintf(text,sizeof text,d->previewValid?"Click any island on the preview to inspect its resources, climate and occupants.\r\n\r\nInspection does not change your starting position. Use the button above to prefer an eligible island.":"Island information is available when the map preview is ready.");
 SetDlgItemTextA(d->window,ID_ISLAND_DETAILS,text);
 EnableWindow(GetDlgItem(d->window,ID_USE_ISLAND),known&&details.startEligible);
 if(!d->previewValid||!WorldSettingsDescribeStarts(summary,sizeof summary))snprintf(summary,sizeof summary,"Starting-position and resource checks appear here when the preview is ready.");
 SetDlgItemTextA(d->window,ID_FAIR_SUMMARY,summary);
}
static int wsMenuCollectAdvanced(DialogState*d,WSSettings*s){
 if(!wsMenuReadSeed(d,&s->mapSeed))return 0;
 s->startIsland=d->preferredIsland;
 s->startClimate=(int)SendDlgItemMessageA(d->window,ID_START_CLIMATE,CB_GETCURSEL,0,0)-1;
 s->cargoMode=SendDlgItemMessageA(d->window,ID_CARGO_MODE,BM_GETCHECK,0,0)==BST_CHECKED;
 if(!integer(d->window,ID_CARGO_TOOLS,&s->cargoTools)||!integer(d->window,ID_CARGO_WOOD,&s->cargoWood)||!integer(d->window,ID_CARGO_FOOD,&s->cargoFood)){
  status(d,"Enter whole tons for tools, wood and food.");return 0;
 }
 s->climateBalance=(int)SendDlgItemMessageA(d->window,ID_CLIMATE_BALANCE,CB_GETCURSEL,0,0);
 s->layoutStyle=(int)SendDlgItemMessageA(d->window,ID_LAYOUT_STYLE,CB_GETCURSEL,0,0);
 s->disasters=SendDlgItemMessageA(d->window,ID_DISASTERS,BM_GETCHECK,0,0)==BST_CHECKED;
 s->fairStarts=SendDlgItemMessageA(d->window,ID_FAIR_STARTS,BM_GETCHECK,0,0)==BST_CHECKED;
 s->startSeparation=(int)SendDlgItemMessageA(d->window,ID_START_SEPARATION,CB_GETCURSEL,0,0);
 s->resourceDistribution=(int)SendDlgItemMessageA(d->window,ID_RESOURCE_DISTRIBUTION,CB_GETCURSEL,0,0);
 s->guaranteeBasics=SendDlgItemMessageA(d->window,ID_GUARANTEE_BASICS,BM_GETCHECK,0,0)==BST_CHECKED;
 return 1;
}
static void wsMenuStartHint(DialogState*d){
 char text[160];int climate=(int)SendDlgItemMessageA(d->window,ID_START_CLIMATE,CB_GETCURSEL,0,0)-1;
 if(d->preferredIsland>=0)snprintf(text,sizeof text,"Preferred start: island %d. Inspect islands to change it.",d->preferredIsland+1);
 else if(climate>=0&&climate<6){static const char*names[]={"Polar","Tundra","North","Prairie","Jungle","Steppe"};snprintf(text,sizeof text,"Preferred start: %s climate. Inspect an island for details.",names[climate]);}
 else snprintf(text,sizeof text,"Click any island to inspect it. S: human start; 1-3: AI starts.");
 SetDlgItemTextA(d->window,ID_START_HINT,text);
}
static void wsMenuApplySettings(DialogState*d,const WSSettings*s){
 d->creating=1;static const int worlds[]={256,512,1024,2048},money[]={10000,30000,50000,80000,100000};
 int world=0,amount=0;while(world<3&&worlds[world]!=s->worldSize)world++;while(amount<4&&money[amount]!=s->startingMoney)amount++;
 SendDlgItemMessageA(d->window,ID_WORLD_SIZE,CB_SETCURSEL,world,0);
 SendDlgItemMessageA(d->window,ID_DIFFICULTY,CB_SETCURSEL,s->difficulty,0);
 SendDlgItemMessageA(d->window,ID_SIZE,CB_SETCURSEL,s->islandSize,0);
 SendDlgItemMessageA(d->window,ID_AI,CB_SETCURSEL,s->aiCount,0);
 SendDlgItemMessageA(d->window,ID_MONEY,CB_SETCURSEL,amount,0);
 SendDlgItemMessageA(d->window,ID_FLEET,CB_SETCURSEL,s->startingFleet,0);
 SendDlgItemMessageA(d->window,ID_AI_DIFFICULTY,CB_SETCURSEL,s->aiDifficulty,0);
 SendDlgItemMessageA(d->window,ID_PLANT_FERTILITY,CB_SETCURSEL,s->plantFertility,0);
 SendDlgItemMessageA(d->window,ID_MINERAL_FERTILITY,CB_SETCURSEL,s->mineralFertility,0);
 SendDlgItemMessageA(d->window,ID_START_CLIMATE,CB_SETCURSEL,s->startClimate+1,0);
 SendDlgItemMessageA(d->window,ID_CLIMATE_BALANCE,CB_SETCURSEL,s->climateBalance,0);
 SendDlgItemMessageA(d->window,ID_LAYOUT_STYLE,CB_SETCURSEL,s->layoutStyle,0);
 SendDlgItemMessageA(d->window,ID_START_SEPARATION,CB_SETCURSEL,s->startSeparation,0);
 SendDlgItemMessageA(d->window,ID_RESOURCE_DISTRIBUTION,CB_SETCURSEL,s->resourceDistribution,0);
 for(int i=0;i<8;i++)SendDlgItemMessageA(d->window,ID_CULTURE+i,BM_SETCHECK,s->cultures&(1u<<i)?BST_CHECKED:BST_UNCHECKED,0);
 for(int i=0;i<2;i++)SendDlgItemMessageA(d->window,ID_FACTION+i,BM_SETCHECK,s->factions&(1u<<i)?BST_CHECKED:BST_UNCHECKED,0);
 SendDlgItemMessageA(d->window,ID_CARGO_MODE,BM_SETCHECK,s->cargoMode?BST_CHECKED:BST_UNCHECKED,0);
 SendDlgItemMessageA(d->window,ID_DISASTERS,BM_SETCHECK,s->disasters?BST_CHECKED:BST_UNCHECKED,0);
 SendDlgItemMessageA(d->window,ID_FAIR_STARTS,BM_SETCHECK,s->fairStarts?BST_CHECKED:BST_UNCHECKED,0);
 SendDlgItemMessageA(d->window,ID_GUARANTEE_BASICS,BM_SETCHECK,s->guaranteeBasics?BST_CHECKED:BST_UNCHECKED,0);
 wsMenuPutNumber(d,ID_COUNT,s->islandCount);wsMenuPutNumber(d,ID_SPACING,s->spacing);
 wsMenuPutNumber(d,ID_CARGO_TOOLS,s->cargoTools);wsMenuPutNumber(d,ID_CARGO_WOOD,s->cargoWood);wsMenuPutNumber(d,ID_CARGO_FOOD,s->cargoFood);
 wsMenuPutSeed(d,s->mapSeed);d->previewSeed=s->mapSeed;d->preferredIsland=s->startIsland;d->settings=*s;
 d->inspectedIsland=-1;wsMenuCargoControls(d);wsMenuFairControls(d);wsMenuStartHint(d);d->creating=0;
}
static void wsMenuCopySeed(DialogState*d){
 uint32_t seed;if(!wsMenuReadSeed(d,&seed))return;wchar_t text[16];swprintf(text,16,L"%u",seed);
 SIZE_T bytes=(wcslen(text)+1u)*sizeof(wchar_t);HGLOBAL data=GlobalAlloc(GMEM_MOVEABLE,bytes);
 if(!data){status(d,"The map seed could not be copied.");return;}void*memory=GlobalLock(data);
 if(!memory){GlobalFree(data);status(d,"The map seed could not be copied.");return;}
 memcpy(memory,text,bytes);GlobalUnlock(data);
 if(!OpenClipboard(d->window)){GlobalFree(data);status(d,"The clipboard is busy. Try Copy seed again.");return;}
 int copied=EmptyClipboard()&&SetClipboardData(CF_UNICODETEXT,data)!=NULL;CloseClipboard();
 if(!copied)GlobalFree(data);status(d,copied?"Map seed copied. Reuse it with the same world options to reproduce the preview.":"The map seed could not be copied.");
}
static int wsPresetFolder(char path[MAX_PATH],int create){
 if(!developmentConfigured||!developmentRoot[0]||strlen(developmentRoot)+sizeof("\\WorldSettingsPresets")>MAX_PATH)return 0;
 snprintf(path,MAX_PATH,"%s\\WorldSettingsPresets",developmentRoot);
 DWORD attrs=GetFileAttributesA(path);
 if(attrs==INVALID_FILE_ATTRIBUTES&&create){if(!CreateDirectoryA(path,NULL)&&GetLastError()!=ERROR_ALREADY_EXISTS)return 0;attrs=GetFileAttributesA(path);}
 return attrs!=INVALID_FILE_ATTRIBUTES&&(attrs&FILE_ATTRIBUTE_DIRECTORY)&&!(attrs&FILE_ATTRIBUTE_REPARSE_POINT);
}
static int wsPresetPath(const char*name,char path[MAX_PATH],int create){
 char folder[MAX_PATH];if(!wsPresetNameValid(name)||!wsPresetFolder(folder,create)||strlen(folder)+strlen(name)+6u>=MAX_PATH)return 0;
 snprintf(path,MAX_PATH,"%s\\%s.awp",folder,name);return 1;
}
static int wsPresetRegularHandle(HANDLE file){
 BY_HANDLE_FILE_INFORMATION info;
 return file!=INVALID_HANDLE_VALUE&&GetFileInformationByHandle(file,&info)&&info.nNumberOfLinks==1u&&!(info.dwFileAttributes&(FILE_ATTRIBUTE_REPARSE_POINT|FILE_ATTRIBUTE_DIRECTORY));
}
static void wsPresetRefresh(DialogState*d,const char*selected){
 HWND list=GetDlgItem(d->window,ID_PRESET_PICK);SendMessageA(list,CB_RESETCONTENT,0,0);char folder[MAX_PATH],pattern[MAX_PATH];
 if(wsPresetFolder(folder,0)&&strlen(folder)+7u<MAX_PATH){
  snprintf(pattern,sizeof pattern,"%s\\*.awp",folder);WIN32_FIND_DATAA data;HANDLE find=FindFirstFileA(pattern,&data);uint32_t count=0;
  if(find!=INVALID_HANDLE_VALUE){do{
   size_t n=strlen(data.cFileName);if(n<5u||n>WS_PRESET_NAME_MAX+4u||data.dwFileAttributes&(FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT))continue;
   char name[WS_PRESET_NAME_MAX+1];memcpy(name,data.cFileName,n-4u);name[n-4u]=0;
   if(_stricmp(data.cFileName+n-4u,".awp")||!wsPresetNameValid(name))continue;
   if(count++>=128u)break;SendMessageA(list,CB_ADDSTRING,0,(LPARAM)name);
  }while(FindNextFileA(find,&data));FindClose(find);}
 }
 LRESULT index=selected&&selected[0]?SendMessageA(list,CB_FINDSTRINGEXACT,(WPARAM)-1,(LPARAM)selected):CB_ERR;
 if(index==CB_ERR&&SendMessageA(list,CB_GETCOUNT,0,0)>0)index=0;SendMessageA(list,CB_SETCURSEL,index,0);
}
static int wsPresetSelectedName(DialogState*d,char name[WS_PRESET_NAME_MAX+1]){
 HWND list=GetDlgItem(d->window,ID_PRESET_PICK);LRESULT index=SendMessageA(list,CB_GETCURSEL,0,0);
 if(index==CB_ERR)return 0;LRESULT length=SendMessageA(list,CB_GETLBTEXTLEN,index,0);
 if(length<1||length>WS_PRESET_NAME_MAX)return 0;SendMessageA(list,CB_GETLBTEXT,index,(LPARAM)name);return wsPresetNameValid(name);
}
static void wsMenuLoadPreset(DialogState*d){
 char name[WS_PRESET_NAME_MAX+1],path[MAX_PATH],error[512];
 if(!wsPresetSelectedName(d,name)){status(d,"Choose a saved preset first.");return;}
 if(!wsPresetPath(name,path,0)){status(d,"The saved preset folder is unavailable.");return;}
 HANDLE file=CreateFileA(path,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,NULL);
 if(!wsPresetRegularHandle(file)){if(file!=INVALID_HANDLE_VALUE)CloseHandle(file);status(d,"The saved preset is not a regular local file.");return;}
 LARGE_INTEGER size;char data[WS_PRESET_MAX_BYTES];DWORD received=0;WSSettings value;
 int valid=GetFileSizeEx(file,&size)&&size.QuadPart>0&&size.QuadPart<=WS_PRESET_MAX_BYTES&&ReadFile(file,data,(DWORD)size.QuadPart,&received,NULL)&&received==(DWORD)size.QuadPart;
 CloseHandle(file);
 if(!valid||!wsPresetDecode(data,received,&value)){status(d,"This preset is incomplete or belongs to a different World Settings generator.");return;}
 if(!WorldSettingsValidateSettings(&value,error,sizeof error)){status(d,error);return;}
 KillTimer(d->window,WS_PREVIEW_TIMER);wsMenuApplySettings(d,&value);SetDlgItemTextA(d->window,ID_PRESET_NAME,name);
 invalidatePreview(d);status(d,"Preset loaded. Recreating its map preview...");SetTimer(d->window,WS_PREVIEW_TIMER,50,NULL);
}
static void wsMenuSavePreset(DialogState*d){
 char name[WS_PRESET_NAME_MAX+2],path[MAX_PATH],temporary[MAX_PATH],data[WS_PRESET_MAX_BYTES];uint32_t size=0;
 int nameLength=GetWindowTextLengthA(GetDlgItem(d->window,ID_PRESET_NAME));GetDlgItemTextA(d->window,ID_PRESET_NAME,name,sizeof name);
 if(nameLength>(int)WS_PRESET_NAME_MAX||!wsPresetNameValid(name)){status(d,"Use a preset name of 1 to 32 letters, numbers, spaces, _ or -. Avoid reserved device names.");return;}
 if(!collect(d))return;
 if(!d->previewValid||memcmp(&d->settings,&d->previewSettings,sizeof d->settings)){status(d,"Wait for a valid, up-to-date map preview before saving this preset.");return;}
 if(!wsPresetEncode(&d->settings,data,sizeof data,&size)||!wsPresetPath(name,path,1)){status(d,"The preset could not be prepared in this game copy.");return;}
 DWORD attrs=GetFileAttributesA(path);
 if(attrs!=INVALID_FILE_ATTRIBUTES){
  HANDLE old=CreateFileA(path,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,NULL);int regular=wsPresetRegularHandle(old);if(old!=INVALID_HANDLE_VALUE)CloseHandle(old);
  if(!regular){status(d,"An existing preset is not a regular local file. Choose another name.");return;}
  if(MessageBoxA(d->window,"Replace the existing saved preset with these world settings?","Replace preset",MB_YESNO|MB_ICONQUESTION)!=IDYES){status(d,"The existing preset was kept.");return;}
 }
 static LONG sequence;char folder[MAX_PATH];if(!wsPresetFolder(folder,1)||strlen(folder)+64u>=MAX_PATH){status(d,"The preset folder path is too long.");return;}
 snprintf(temporary,sizeof temporary,"%s\\preset-%lu-%lu.tmp",folder,(unsigned long)GetCurrentProcessId(),(unsigned long)InterlockedIncrement(&sequence));
 HANDLE file=CreateFileA(temporary,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL|FILE_FLAG_OPEN_REPARSE_POINT,NULL);DWORD written=0;int created=file!=INVALID_HANDLE_VALUE;
 int valid=created&&wsPresetRegularHandle(file)&&WriteFile(file,data,size,&written,NULL)&&written==size&&FlushFileBuffers(file);
 if(created)CloseHandle(file);
 if(valid)valid=wsPresetFolder(folder,0)&&MoveFileExA(temporary,path,MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH);
 if(!valid){if(created)DeleteFileA(temporary);status(d,"The preset could not be saved. Existing presets were kept.");return;}
 wsPresetRefresh(d,name);status(d,"Preset saved, including the seed and every world setting.");
}
static int wsMenuCommand(DialogState*d,int id,int notice){
 if(id>=ID_TAB_WORLD&&id<ID_TAB_WORLD+5&&notice==BN_CLICKED){wsMenuPage(d,id-ID_TAB_WORLD);return 1;}
 if(id==ID_USE_ISLAND&&notice==BN_CLICKED){
  if(!d->previewValid||d->inspectedIsland<0||!WorldSettingsStartingIslandEligible((uint32_t)d->inspectedIsland)){status(d,"Inspect an ordinary island with safe nearby water first.");return 1;}
  d->creating=1;d->preferredIsland=d->inspectedIsland;SendDlgItemMessageA(d->window,ID_START_CLIMATE,CB_SETCURSEL,0,0);d->creating=0;
  KillTimer(d->window,WS_PREVIEW_TIMER);generatePreview(d,0);return 1;
 }
 if(id==ID_COPY_SEED&&notice==BN_CLICKED){wsMenuCopySeed(d);return 1;}
 if(id==ID_PRESET_SAVE&&notice==BN_CLICKED){wsMenuSavePreset(d);return 1;}
 if(id==ID_PRESET_LOAD&&notice==BN_CLICKED){wsMenuLoadPreset(d);return 1;}
 if(id==ID_PRESET_PICK&&notice==CBN_SELCHANGE){char name[WS_PRESET_NAME_MAX+1];if(wsPresetSelectedName(d,name))SetDlgItemTextA(d->window,ID_PRESET_NAME,name);return 1;}
 if(id==ID_CLEAR_START&&notice==BN_CLICKED){
  d->creating=1;d->preferredIsland=-1;SendDlgItemMessageA(d->window,ID_START_CLIMATE,CB_SETCURSEL,0,0);d->creating=0;wsMenuStartHint(d);invalidatePreview(d);SetTimer(d->window,WS_PREVIEW_TIMER,50,NULL);return 1;
 }
 return 0;
}
static void wsMenuOptionChanged(DialogState*d,int id){
 if(id!=ID_MONEY&&id!=ID_AI_DIFFICULTY&&id!=ID_CARGO_MODE&&id!=ID_CARGO_TOOLS&&id!=ID_CARGO_WOOD&&id!=ID_CARGO_FOOD&&id!=ID_DISASTERS&&id!=ID_FAIR_STARTS&&id!=ID_START_SEPARATION&&id!=ID_GUARANTEE_BASICS){d->preferredIsland=-1;d->inspectedIsland=-1;}
 if(id==ID_CARGO_MODE)wsMenuCargoControls(d);if(id==ID_FAIR_STARTS)wsMenuFairControls(d);wsMenuStartHint(d);
}
