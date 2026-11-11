/* The two existing AMD64 start bridges share this decision. Return values are
 * 0: cancel, 1: untouched native start, 2: accepted custom-world staging.
 * In particular, the direct bridge must not commit custom setup on result 1.
 */
extern int WorldSettingsClassifyDirectSelection(const char*,uint32_t,const unsigned char*);

#ifndef WS_MENU_GENERATION_CHOOSER
typedef struct WSGenerationChoice {HWND owner,window;HFONT font;int done,result;} WSGenerationChoice;
enum {WS_GENERATION_NATIVE=101,WS_GENERATION_CUSTOM=102,WS_GENERATION_BACK=103};
static LRESULT CALLBACK wsGenerationWindowProc(HWND w,UINT message,WPARAM wp,LPARAM lp){
 WSGenerationChoice*d=(WSGenerationChoice*)GetWindowLongPtrA(w,GWLP_USERDATA);
 if(message==WM_NCCREATE){d=(WSGenerationChoice*)((CREATESTRUCTA*)lp)->lpCreateParams;d->window=w;SetWindowLongPtrA(w,GWLP_USERDATA,(LONG_PTR)d);}
 if(!d)return DefWindowProcA(w,message,wp,lp);
 if(message==WM_CREATE){
  const struct {const char*kind,*text;DWORD style;int x,y,width,height,id;} items[]={
   {"STATIC","How would you like to create this endless game?",0,22,18,456,28,0},
   {"BUTTON","Original game",BS_PUSHBUTTON|WS_TABSTOP,22,62,218,38,WS_GENERATION_NATIVE},
   {"BUTTON","Custom world",BS_DEFPUSHBUTTON|WS_TABSTOP,258,62,218,38,WS_GENERATION_CUSTOM},
   {"STATIC","Use the game's own setup and generation. World Settings choices are ignored.",0,22,114,218,76,0},
   {"STATIC","Choose islands, resources, players and more, with an optional map preview.",0,258,114,218,76,0},
   {"BUTTON","Back",BS_PUSHBUTTON|WS_TABSTOP,358,204,118,32,WS_GENERATION_BACK}
  };
  for(size_t i=0;i<sizeof items/sizeof items[0];i++){
   HWND child=CreateWindowExA(0,items[i].kind,items[i].text,WS_CHILD|WS_VISIBLE|items[i].style,items[i].x,items[i].y,items[i].width,items[i].height,w,(HMENU)(INT_PTR)items[i].id,dllInstance,NULL);
   if(!child)return -1;SendMessageA(child,WM_SETFONT,(WPARAM)d->font,TRUE);
  }
  SetFocus(GetDlgItem(w,WS_GENERATION_CUSTOM));return 0;
 }
 if(message==WM_COMMAND){int id=LOWORD(wp);
  if(id==WS_GENERATION_NATIVE||id==WS_GENERATION_CUSTOM||id==WS_GENERATION_BACK||id==IDCANCEL){d->result=id==WS_GENERATION_NATIVE?1:id==WS_GENERATION_CUSTOM?2:0;d->done=1;DestroyWindow(w);return 0;}
 }
 if(message==WM_CLOSE){d->done=1;DestroyWindow(w);return 0;}
 if(message==WM_DESTROY){d->done=1;return 0;}
 return DefWindowProcA(w,message,wp,lp);
}
static int wsMenuChooseGeneration(HWND owner){
 WSGenerationChoice d={0};d.owner=owner;d.font=(HFONT)GetStockObject(DEFAULT_GUI_FONT);
 WNDCLASSEXA cls={0};cls.cbSize=sizeof cls;cls.lpfnWndProc=wsGenerationWindowProc;cls.hInstance=dllInstance;
 cls.hCursor=LoadCursorA(NULL,IDC_ARROW);cls.hbrBackground=(HBRUSH)(COLOR_BTNFACE+1);cls.lpszClassName="Anno1503WorldGenerationChoice";
 if(!RegisterClassExA(&cls)&&GetLastError()!=ERROR_CLASS_ALREADY_EXISTS)return 0;
 RECT work={0},box={0,0,498,258};
 if(!SystemParametersInfoA(SPI_GETWORKAREA,0,&work,0)||!AdjustWindowRectEx(&box,WS_CAPTION|WS_SYSMENU,FALSE,WS_EX_DLGMODALFRAME|WS_EX_CONTROLPARENT))return 0;
 int width=box.right-box.left,height=box.bottom-box.top;
 int x=work.left+((work.right-work.left)-width)/2,y=work.top+((work.bottom-work.top)-height)/2;
 BOOL enabled=owner?IsWindowEnabled(owner):FALSE;
 HWND w=CreateWindowExA(WS_EX_DLGMODALFRAME|WS_EX_CONTROLPARENT,cls.lpszClassName,"Anno 1503 - New endless game",WS_CAPTION|WS_SYSMENU,x,y,width,height,owner,NULL,dllInstance,&d);
 if(!w)return 0;if(owner&&enabled)EnableWindow(owner,FALSE);ShowWindow(w,SW_SHOW);UpdateWindow(w);
 MSG message;int result=1;
 while(!d.done&&(result=GetMessageA(&message,NULL,0,0))>0)if(!IsDialogMessageA(w,&message)){TranslateMessage(&message);DispatchMessageA(&message);}
 if(result==0)PostQuitMessage((int)message.wParam);
 if(IsWindow(w))DestroyWindow(w);if(owner&&enabled){EnableWindow(owner,TRUE);SetActiveWindow(owner);}
 return d.result;
}
#define WS_MENU_GENERATION_CHOOSER(owner) wsMenuChooseGeneration(owner)
#endif
#ifndef WS_MENU_OPEN_CUSTOM
#define WS_MENU_OPEN_CUSTOM(owner,setup,frame) dialog((owner),(setup),(uint8_t*)(frame))
#endif
static int wsMenuClassifySelection(void*frame){
 if(!frame)return -1;
 const unsigned char*base=(const unsigned char*)frame;
 return WorldSettingsClassifyDirectSelection((const char*)base+0xc7430,260,base+0xc7534);
}
static int wsMenuGenerationStart(void*setup,void*frame,int selection){
 /* No preview, preset or old pending attempt may affect a native start. This
  * cancels staged options only; it does not alter the game's setup or flags. */
 if(!WorldSettingsRestoreNativeSetup()){reportGenerationFailure(wsMenuSetupResetMessage);return 0;}
 WorldSettingsFinishAttempt(0);
 if(selection==0)return 1;
 if(selection!=1){reportGenerationFailure("This endless-game source is not supported. Return to the menu and choose an original endless game.");return 0;}
 if(!setup||!frame){reportGenerationFailure("The game setup is unavailable. Return to the menu and try again.");return 0;}
 HWND owner=GetActiveWindow();int choice=WS_MENU_GENERATION_CHOOSER(owner);
 if(choice!=2)return choice==1?1:0;
 return WS_MENU_OPEN_CUSTOM(owner,setup,frame)>0?2:0;
}
