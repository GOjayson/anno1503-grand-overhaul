"""Create private combined source copies; never edits canonical or game files."""
from pathlib import Path
import hashlib,json,shutil
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[2]
factions=WORK/'engine_resume/faction_options/runtime'
inputs={}
def source(path):
 inputs[str(path.relative_to(WORK))]=hashlib.sha256(path.read_bytes()).hexdigest()
 return path.read_text('utf-8')
def replace(text,old,new):
 assert text.count(old)==1,(old,text.count(old))
 return text.replace(old,new)
for path in factions.iterdir():
 if path.is_file():
  inputs[str(path.relative_to(WORK))]=hashlib.sha256(path.read_bytes()).hexdigest()
  shutil.copyfile(path,HERE/path.name)
text=source(WORK/'runtime_integrated/WorldSettings.c')
text=replace(text,'#include "../engine_resume/runtime/world_backend.h"','#include "world_backend.h"\n#include "world_ai.h"\n#include "../../ai_loader/ai_loader.h"')
text=replace(text,'int32_t aiCount;          /* food AI planning has not been implemented */','int32_t aiCount;          /* 0..3 existing stock placeholders; private test */')
text=replace(text,'uint32_t cultures;        /* bits in cultureNames order below */','uint32_t cultures;        /* bits in cultureNames order below */\n    uint32_t factions;        /* bit0 Pirates; bit1 Venetians */')
text=replace(text,'if (s->aiCount!=0) {message(err,cap,"Combined Food Mod supports zero AI opponents; extra-food AI planning is unimplemented.");return 0;}',
 'if(s->aiCount<0||s->aiCount>3){message(err,cap,"Choose zero to three AI opponents.");return 0;}\n    if(s->aiCount&&!WorldSettingsAIExperimentConfigured()){message(err,cap,"The copied Food AI support has not completed activation. Start is blocked.");return 0;}')
text=replace(text,'if (s->cultures&~255u) {message(err,cap,"Unknown culture bit.");return 0;}',
 'if (s->cultures&~255u) {message(err,cap,"Unknown culture bit.");return 0;}\n    if(s->factions&~3u){message(err,cap,"Unknown Pirates or Venetians option.");return 0;}')
text=replace(text,'prepareBackend=NULL;backendContext=NULL;developmentConfigured=0;developmentRoot[0]=0;configurationError[0]=0;',
 'prepareBackend=NULL;backendContext=NULL;developmentConfigured=0;developmentRoot[0]=0;configurationError[0]=0;\n    WorldSettingsConfigureAIExperiment(NULL,NULL);')
text=replace(text,'memcpy(developmentRoot,ansi,(size_t)bytes);developmentConfigured=1;prepareBackend=developmentStage;backendContext=NULL;',
 'memcpy(developmentRoot,ansi,(size_t)bytes);developmentConfigured=1;prepareBackend=developmentStage;backendContext=NULL;\n    char sourceRoot[MAX_PATH];defaultUsed=FALSE;\n    int sourceBytes=WideCharToMultiByte(codePage,flags,exe,-1,sourceRoot,MAX_PATH,NULL,codePage==CP_UTF8?NULL:&defaultUsed);\n    if(sourceBytes&&!defaultUsed&&MultiByteToWideChar(codePage,MB_ERR_INVALID_CHARS,sourceRoot,-1,roundTrip,MAX_PATH)&&!wcscmp(exe,roundTrip))WorldSettingsConfigureAIExperiment(developmentRoot,sourceRoot);')
text=replace(text,'ID_CULTURE=120,ID_STATUS=140','ID_CULTURE=120,ID_FACTION=130,ID_STATUS=140')
text=replace(text,'s.aiCount=0;for(int i=0;i<8;i++)',
 's.aiCount=(int)SendDlgItemMessageA(d->window,ID_AI,CB_GETCURSEL,0,0);\n for(int i=0;i<2;i++)if(SendDlgItemMessageA(d->window,ID_FACTION+i,BM_GETCHECK,0,0)==BST_CHECKED)s.factions|=1u<<i;\n for(int i=0;i<8;i++)')
text=replace(text,'memset((uint8_t*)d->setup+0x2280,0,7); /* preserve supported zero-AI food gameplay */',
 'if(!WorldSettingsBindStockAIProfiles(d->setup,d->settings.difficulty,d->settings.aiCount,error,sizeof error)){WorldSettingsFinishAttempt(0);status(d,error);return;}\n WorldSettingsExpectAIProfiles(d->settings.aiCount);')
text=replace(text,'const char*ai[]={"0 (Combined Food Mod)"};','const char*ai[]={"0","1","2","3"};')
text=replace(text,'ID_AI),ai,1,0);','ID_AI),ai,4,0);')
text=replace(text,'label(d,"AI opponents require additional Food Mod support.",24,288,556,40);','label(d,"AI food compatibility is being tested in this development build.",24,288,556,40);')
text=replace(text,'label(d,"Status",24,514,550,20);control(d,"STATIC",developmentConfigured&&prepareBackend?configuredStatus:noBackend,SS_LEFT,24,540,556,68,ID_STATUS);',
 'label(d,"Pirates and Venetians",24,514,550,20);\n  const char*special[]={"Pirates","Venetians"};for(int i=0;i<2;i++){HWND c=control(d,"BUTTON",special[i],BS_AUTOCHECKBOX|WS_TABSTOP,24+i*296,540,260,26,ID_FACTION+i);SendMessageA(c,BM_SETCHECK,BST_CHECKED,0);}\n  label(d,"Status",24,582,550,20);control(d,"STATIC",developmentConfigured&&prepareBackend?configuredStatus:noBackend,SS_LEFT,24,608,556,68,ID_STATUS);')
text=replace(text,'320,624,120,32,ID_BACK','320,692,120,32,ID_BACK')
text=replace(text,'460,624,120,32,ID_START','460,692,120,32,ID_START')
text=replace(text,'RECT rc={0,0,608,680};','RECT rc={0,0,608,748};')
route=source(WORK/'engine_resume/route_coverage/runtime_integration.inc')
text=replace(text,'BOOL WINAPI DllMain(',route+'\nBOOL WINAPI DllMain(')
(HERE/'WorldSettings.c').write_text(text,'utf-8')
backend=(HERE/'world_backend.c').read_text('utf-8')
backend=replace(backend,'#include "world_factions.h"','#include "world_factions.h"\n#include "world_ai.h"\n#include "../../ai_loader/ai_loader.h"')
backend=replace(backend,'#include "special_scene.inc"','#include "special_scene.inc"\n#include "ai_scene.inc"')
backend=replace(backend,'unsigned char special[32]={0};if(!wsSpecialPlayers(src,size,special,error,cap))return 0;',
 'unsigned char special[32]={0};if(!wsSpecialPlayers(src,size,special,error,cap))return 0;\n uint32_t cpuSuspensions[32]={0};if(!wsAISuspensionOffsets(src,size,s->difficulty,cpuSuspensions,error,cap))return 0;')
backend=replace(backend,'else if(!wsAppend(b,src+at,n+16))return 0;at+=n+16;',
 'else if(!wsAIAppendSourceChunk(b,src,at,n+16,cpuSuspensions))return 0;at+=n+16;')
backend=replace(backend,'||s->aiCount||','||s->aiCount<0||s->aiCount>3||(s->aiCount&&!WorldSettingsAIExperimentConfigured())||')
backend=replace(backend,'void WorldSettingsFinishAttempt(int success){(void)success;',
 'void WorldSettingsFinishAttempt(int success){WorldSettingsAIProfileAttemptFinished(success);')
(HERE/'world_backend.c').write_text(backend,'utf-8')
(HERE/'source_inputs.json').write_text(json.dumps(dict(scope=__doc__,inputs=inputs),indent=2)+'\n','utf-8')
print('Prepared private ABI32 UI/backend with 8 culture toggles, Pirates, Venetians and gated AI0..3.')
