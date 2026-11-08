/* Hit testing uses the same world-to-preview projection and coast mask as
 * painting. Water and inhabited/special islands cannot become start choices. */
static void wsMenuPreviewClick(DialogState*d,HWND window,LPARAM position){
 if(!d->previewValid||d->previewBusy)return;
 RECT client;GetClientRect(window,&client);int width=client.right-client.left,height=client.bottom-client.top;
 int size=width<height?width:height;if(size<=0)return;
 int x=(int)(short)LOWORD(position)-client.left-(width-size)/2;
 int y=(int)(short)HIWORD(position)-client.top-(height-size)/2;
 if(x<0||y<0||x>=size||y>=size)return;
 uint32_t world=(uint32_t)d->previewSettings.worldSize;
 for(uint32_t i=0;i<d->previewCount;i++){
  const WSPlanIsland*p=&d->previewIslands[i];if(p->templateIndex>=WS_PREVIEW_COAST_COUNT)continue;
  int left=(int)((uint64_t)p->x*(uint32_t)size/world),top=(int)((uint64_t)p->y*(uint32_t)size/world);
  int right=(int)((uint64_t)(p->x+p->width)*(uint32_t)size/world),bottom=(int)((uint64_t)(p->y+p->height)*(uint32_t)size/world);
  if(x<left||y<top||x>=right||y>=bottom||right<=left||bottom<=top)continue;
  uint32_t row=(uint32_t)(y-top)*WS_PREVIEW_COAST_SIZE/(uint32_t)(bottom-top);
  uint32_t column=(uint32_t)(x-left)*WS_PREVIEW_COAST_SIZE/(uint32_t)(right-left),bit=row*WS_PREVIEW_COAST_SIZE+column;
  if(!(wsPreviewCoasts[p->templateIndex][bit>>3]&(1u<<(bit&7u))))continue;
  if(!WorldSettingsStartingIslandEligible(i)){status(d,"Choose an ordinary island with safe nearby water. Native, pirate and Venetian islands cannot be selected.");return;}
  d->creating=1;d->preferredIsland=(int32_t)i;SendDlgItemMessageA(d->window,ID_START_CLIMATE,CB_SETCURSEL,0,0);d->creating=0;
  KillTimer(d->window,WS_PREVIEW_TIMER);generatePreview(d,0);return;
 }
 status(d,"Click the land on an ordinary island to choose a preferred starting position.");
}
