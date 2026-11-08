/* In-game preview of the exact cached plan. No scene is staged by this UI
 * until Start. Coast masks are generated from fingerprinted native HEIGHT
 * cells; only their visual coastline is simplified, never island placement. */
#include "world_preview_coasts.h"
#include "world_factions.h"

static const char *previewClassName="Anno1503WorldMapPreview";
static const char *previewClimateNames[6]={"Polar","Tundra","North","Prairie","Jungle","Steppe"};
static const COLORREF previewClimateColors[6]={
 RGB(219,230,235),RGB(148,166,132),RGB(92,151,88),
 RGB(178,184,104),RGB(52,123,76),RGB(202,171,103)};

static uint32_t freshPreviewSeed(uint32_t previous){
 uint32_t value=0;static LONG sequence;
 if(BCryptGenRandom(NULL,(PUCHAR)&value,sizeof value,BCRYPT_USE_SYSTEM_PREFERRED_RNG)<0)
  value=GetTickCount()^(uint32_t)GetCurrentProcessId()^((uint32_t)InterlockedIncrement(&sequence)*0x9e3779b9u);
 if(!value||value==previous)value=previous+0x9e3779b9u;
 if(!value)value=1;return value;
}

static void paintPreview(DialogState*d,HDC dc,const RECT*client){
 HBRUSH sea=CreateSolidBrush(RGB(34,75,103));FillRect(dc,client,sea);DeleteObject(sea);
 int width=client->right-client->left,height=client->bottom-client->top;
 int size=width<height?width:height;RECT map={client->left+(width-size)/2,client->top+(height-size)/2,0,0};map.right=map.left+size;map.bottom=map.top+size;
 HPEN grid=CreatePen(PS_SOLID,1,RGB(46,87,115));HGDIOBJ oldPen=SelectObject(dc,grid);
 for(int i=1;i<4;i++){int at=MulDiv(size,i,4);MoveToEx(dc,map.left+at,map.top,NULL);LineTo(dc,map.left+at,map.bottom);MoveToEx(dc,map.left,map.top+at,NULL);LineTo(dc,map.right,map.top+at);}
 SelectObject(dc,oldPen);DeleteObject(grid);
 if(d->previewValid){
  uint32_t world=(uint32_t)d->previewSettings.worldSize;
  if(world!=256u&&world!=512u&&world!=1024u&&world!=2048u)return;
  HBRUSH land[6];for(int i=0;i<6;i++)land[i]=CreateSolidBrush(previewClimateColors[i]);
  for(uint32_t i=0;i<d->previewCount;i++){
   const WSPlanIsland*p=&d->previewIslands[i];
   if(p->templateIndex>=WS_PREVIEW_COAST_COUNT||p->climate>=6)continue;
   int left=map.left+(int)((uint64_t)p->x*size/world),top=map.top+(int)((uint64_t)p->y*size/world);
   int right=map.left+(int)((uint64_t)(p->x+p->width)*size/world),bottom=map.top+(int)((uint64_t)(p->y+p->height)*size/world);
   int iw=right-left,ih=bottom-top;if(iw<=0||ih<=0)continue;
   const unsigned char*coast=wsPreviewCoasts[p->templateIndex];
   for(int y=0;y<ih;y++){
    uint32_t row=(uint32_t)y*WS_PREVIEW_COAST_SIZE/(uint32_t)ih;int first=-1;
    for(int x=0;x<=iw;x++){
     uint32_t bit=x<iw?row*WS_PREVIEW_COAST_SIZE+(uint32_t)x*WS_PREVIEW_COAST_SIZE/(uint32_t)iw:0;
     int solid=x<iw&&(coast[bit>>3]&(1u<<(bit&7u)));
     if(solid&&first<0)first=x;
     if(!solid&&first>=0){RECT run={left+first,top+y,left+x,top+y+1};FillRect(dc,&run,land[p->climate]);first=-1;}
    }
   }
  }
  for(int i=0;i<6;i++)DeleteObject(land[i]);
  HGDIOBJ previousFont=SelectObject(dc,d->font);int oldMode=SetBkMode(dc,TRANSPARENT);COLORREF oldColor=GetTextColor(dc);
  for(uint32_t i=0;i<d->previewCount;i++){
   const WSPlanIsland*p=&d->previewIslands[i];
   if(p->templateIndex>=sizeof(wsTemplateFactions)/sizeof(wsTemplateFactions[0]))continue;
   uint32_t faction=wsTemplateFactions[p->templateIndex];if(faction!=1u&&faction!=2u)continue;
   char symbol[2]={faction==1u?'P':'V',0};SIZE extent={0};GetTextExtentPoint32A(dc,symbol,1,&extent);
   int pad=scaled(d,3),mw=extent.cx+pad*2,mh=extent.cy+pad*2;
   int cx=map.left+(int)(((uint64_t)p->x*2+p->width)*size/(world*2u)),cy=map.top+(int)(((uint64_t)p->y*2+p->height)*size/(world*2u));
   RECT badge={cx-mw/2,cy-mh/2,cx-mw/2+mw,cy-mh/2+mh};
   if(badge.left<map.left)OffsetRect(&badge,map.left-badge.left,0);if(badge.right>map.right)OffsetRect(&badge,map.right-badge.right,0);
   if(badge.top<map.top)OffsetRect(&badge,0,map.top-badge.top);if(badge.bottom>map.bottom)OffsetRect(&badge,0,map.bottom-badge.bottom);
   HBRUSH marker=CreateSolidBrush(faction==1u?RGB(156,38,38):RGB(242,202,83));FillRect(dc,&badge,marker);DeleteObject(marker);FrameRect(dc,&badge,(HBRUSH)GetStockObject(BLACK_BRUSH));
   SetTextColor(dc,faction==1u?RGB(255,255,255):RGB(20,20,20));DrawTextA(dc,symbol,1,&badge,DT_CENTER|DT_VCENTER|DT_SINGLELINE);
  }
  SetTextColor(dc,oldColor);SetBkMode(dc,oldMode);SelectObject(dc,previousFont);
 }else{
  SetBkMode(dc,TRANSPARENT);SetTextColor(dc,RGB(233,239,242));HGDIOBJ font=SelectObject(dc,d->font);
  RECT text=map;text.left+=16;text.right-=16;text.top+=size/2-24;text.bottom=text.top+64;
  DrawTextA(dc,d->previewBusy?"Preparing map preview...":"No valid map preview.\r\nCheck your settings, then regenerate.",-1,&text,DT_CENTER|DT_WORDBREAK);
  SelectObject(dc,font);
 }
}

static LRESULT CALLBACK previewWindowProc(HWND w,UINT msg,WPARAM wp,LPARAM lp){
 DialogState*d=(DialogState*)GetWindowLongPtrA(w,GWLP_USERDATA);
 if(msg==WM_NCCREATE){CREATESTRUCTA*c=(CREATESTRUCTA*)lp;d=(DialogState*)c->lpCreateParams;SetWindowLongPtrA(w,GWLP_USERDATA,(LONG_PTR)d);}
 if(!d)return DefWindowProcA(w,msg,wp,lp);
 if(msg==WM_ERASEBKGND)return 1;
 if(msg==WM_PAINT){
  PAINTSTRUCT ps;HDC dc=BeginPaint(w,&ps);RECT rc;GetClientRect(w,&rc);
  HDC buffer=CreateCompatibleDC(dc);HBITMAP bitmap=buffer?CreateCompatibleBitmap(dc,rc.right-rc.left,rc.bottom-rc.top):NULL;
  if(buffer&&bitmap){HGDIOBJ previous=SelectObject(buffer,bitmap);paintPreview(d,buffer,&rc);BitBlt(dc,0,0,rc.right,rc.bottom,buffer,0,0,SRCCOPY);SelectObject(buffer,previous);DeleteObject(bitmap);DeleteDC(buffer);}
  else{if(bitmap)DeleteObject(bitmap);if(buffer)DeleteDC(buffer);paintPreview(d,dc,&rc);}
  EndPaint(w,&ps);return 0;
 }
 return DefWindowProcA(w,msg,wp,lp);
}

static int registerPreviewClass(void){
 WNDCLASSEXA c={0};c.cbSize=sizeof c;c.lpfnWndProc=previewWindowProc;c.hInstance=dllInstance;c.hCursor=LoadCursorA(NULL,IDC_ARROW);c.lpszClassName=previewClassName;
 return RegisterClassExA(&c)||GetLastError()==ERROR_CLASS_ALREADY_EXISTS;
}

static int settingsNotification(int id,int notification){
 if(id==ID_COUNT||id==ID_SPACING)return notification==EN_CHANGE;
 if((id>=ID_CULTURE&&id<ID_CULTURE+8)||(id>=ID_FACTION&&id<ID_FACTION+2))return notification==BN_CLICKED;
 return id>=ID_DIFFICULTY&&id<=ID_WORLD_SIZE&&notification==CBN_SELCHANGE;
}

static void invalidatePreview(DialogState*d){
 WorldSettingsFinishAttempt(0);
 d->previewValid=0;d->previewCount=0;EnableWindow(GetDlgItem(d->window,ID_START),FALSE);
 if(d->preview)InvalidateRect(d->preview,NULL,FALSE);
 status(d,"Settings changed. Updating the map preview...");
}

static int generatePreview(DialogState*d,int regenerate){
 if(d->previewBusy||d->creating||d->done)return 0;
 invalidatePreview(d);d->previewBusy=1;
 EnableWindow(GetDlgItem(d->window,ID_REGENERATE),FALSE);
 if(d->preview)UpdateWindow(d->preview);
 char error[512]={0};int valid=collect(d);
 if(valid){
  if(regenerate||!d->previewSeed)d->previewSeed=freshPreviewSeed(d->previewSeed);
  valid=WorldSettingsBuildPlan(&d->settings,d->previewSeed,error,sizeof error);
  int count=valid?WorldSettingsPlanCount():0;
  if(valid&&(count<1||count>128)){valid=0;message(error,sizeof error,"The map preview has an invalid island count.");}
  for(int i=0;valid&&i<count;i++){
   WSPlanIsland*p=&d->previewIslands[i];
   uint32_t world=(uint32_t)d->settings.worldSize;
   if(!WorldSettingsPlanIsland((uint32_t)i,p)||p->id!=(uint32_t)i||p->templateIndex>=WS_PREVIEW_COAST_COUNT||p->climate>=6||p->x>world||p->y>world||!p->width||!p->height||p->width>world-p->x||p->height>world-p->y){valid=0;message(error,sizeof error,"The map preview could not read every validated island.");}
  }
  if(valid){d->previewSettings=d->settings;d->previewCount=(uint32_t)count;d->previewValid=1;status(d,"Map ready. Start uses this preview; Regenerate makes another world.");}
  else status(d,error[0]?error:"This map could not be prepared. Change settings or regenerate.");
 }
 d->previewBusy=0;EnableWindow(GetDlgItem(d->window,ID_REGENERATE),TRUE);
 EnableWindow(GetDlgItem(d->window,ID_START),valid&&prepareBackend&&d->frame&&d->setup);
 if(d->preview){InvalidateRect(d->preview,NULL,FALSE);UpdateWindow(d->preview);}
 return valid;
}
