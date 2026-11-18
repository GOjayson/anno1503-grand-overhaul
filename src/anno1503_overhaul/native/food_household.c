/* Read-only Food 0.6 house information. No inventory, orders or save fields. */
#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
typedef unsigned long long u64;
typedef __UINTPTR_TYPE__ uptr;
typedef __INTPTR_TYPE__ iptr;
typedef struct {u32 tag,pad;u64 value;u8 extra[112];} Value;
typedef struct {u32 state,percent,active,total_weight;u16 scores[5],rates[5];} FoodSnapshot;
#ifdef _WIN32
int _DllMainCRTStartup(void *module,u32 reason,void *reserved){(void)module;(void)reason;(void)reserved;return 1;}
#endif
typedef iptr (*Method)(void*,uptr,uptr,uptr);
static const u8 foods[5]={26,40,24,25,45};
static void *ptr(const void *p,u32 at){return *(void* const*)((const u8*)p+at);}
static u16 word(const void *p,u32 at){return *(const u16*)((const u8*)p+at);}
static Method method(void *p,u32 slot){return (Method)ptr(ptr(p,0),slot);}
static iptr call(void *p,u32 slot,uptr a,uptr b,uptr c){return method(p,slot)(p,a,b,c);}
static void clear(void *p,u32 n){u8 *q=(u8*)p;for(u32 i=0;i<n;i++)q[i]=0;}

EXPORT u32 food_measure(const void *house,u32 unlocked,FoodSnapshot *out){
 if(!out)return 0;
 clear(out,sizeof(*out));
 if(!house||!ptr(house,0)||!ptr(ptr(house,0),0x130))return 0;
 if(!word(house,0x52)){out->state=1;return 1;}
 const u8 *needs=(const u8*)ptr(house,0x48);
 if(!needs||!needs[2]||needs[2]>18)return 0;
 const u8 *records=(const u8*)ptr(needs,0x118);
 if(!records)return 0;
 u64 numerator=0;
 for(u32 j=0;j<5;j++){
  u32 good=foods[j],index=needs[good+3];
  if(index>=needs[2])continue;
  u16 rate=word(needs,0x66+index*4);
  u8 gate=records[good*26+2];
  if(!rate||gate>=32||!(unlocked&(1u<<gate)))continue;
  iptr raw=call((void*)house,0x130,good,0,0);
  u32 score=raw<0?0:(raw>128?128:(u32)raw);
  out->rates[j]=rate;out->scores[j]=(u16)score;
  out->active++;out->total_weight+=rate;numerator+=(u64)rate*score;
 }
 if(!out->total_weight){out->state=3;return 3;}
 out->percent=(u32)((numerator*100+(u64)out->total_weight*64)/((u64)out->total_weight*128));
 out->state=2;return 2;
}

static u8 *widget(void *view,u32 index){
 u8 **first=(u8**)ptr(view,0x750),**last=(u8**)ptr(view,0x758);
 if(!first||!last||last<first||(uptr)(last-first)<=(uptr)index)return (u8*)0;
 return first[index];
}
static void number(void *w,u32 property,u32 n){Value v;clear(&v,sizeof(v));v.value=n;call(w,0xa0,property,(uptr)&v,0);}
static void text(void *w,u32 property,const char *s){Value v;clear(&v,sizeof(v));v.value=(uptr)s;call(w,0xa0,property,(uptr)&v,0);}
static u32 resource(void *view,const char *name){
 Value v;clear(&v,sizeof(v));
 for(u32 i=0;i<110&&name[i];i++)((char*)&v.value)[i]=name[i];
 void *r=ptr(view,0x710);if(!r)return 0xffffffffu;
 /* tTextureset::GetProperty returns BOOL and writes only the ID DWORD. */
 if(!call(r,0x98,0xa,(uptr)&v,0)||(u32)v.value==0xffffffffu)return 0xffffffffu;
 return (u32)v.value;
}
static char *append(char *p,const char *s){while(*s)*p++=*s++;*p=0;return p;}
static char *decimal(char *p,u32 n){if(n>=100)*p++=(char)('0'+n/100);if(n>=10)*p++=(char)('0'+(n/10)%10);*p++=(char)('0'+n%10);*p=0;return p;}
static u32 unlocks(void *house){
 void *owner=(void*)call(house,0x38,0,0,0);if(!owner)return 0;
 void *profile=(void*)call(owner,0x40,0,0,0);if(!profile)return 0;
 Value v;clear(&v,sizeof(v));call(profile,0x98,0x21,(uptr)&v,0);return (u32)v.value;
}
static int origin(void *view,u32 at){return (int)*(const float*)((const u8*)view+at);}
EXPORT void food_position(void *view){
 const int x[3]={15,74,74},y[3]={354,358,384};
 for(u32 i=0;i<3;i++){void *w=widget(view,7+i);if(w)call(w,0xc0,(uptr)(iptr)(origin(view,0x6f8)+x[i]),(uptr)(iptr)(origin(view,0x6fc)+y[i]),0);}
}
static void hide(void *view){for(u32 i=7;i<10;i++){void *w=widget(view,i);if(w)call(w,0xc0,(uptr)(iptr)-10000,(uptr)(iptr)-10000,0);}}
EXPORT void food_refresh(void *view){
 void *icon=widget(view,7),*title=widget(view,8),*detail=widget(view,9);
 if(!icon||!title||!detail)return;
 void *house=ptr(view,0x808);
 if(!house||call(house,0x30,0,0,0)!=0x1a00){hide(view);return;}
 FoodSnapshot snapshot;food_measure(house,unlocks(house),&snapshot);
 char label[64];char *p=label;
 p=append(p,"Food: ");
 if(snapshot.state==1)p=append(p,"No residents");
 else if(snapshot.state==2){p=decimal(p,snapshot.percent);p=append(p,"%");}
 else p=append(p,"Not available");
 number(icon,0x1c0,snapshot.percent);
 /* Tooltip properties retain pointers; only module-lifetime literals are safe.
    Text property 1c4 uses the native string copy, as in the original house UI. */
 text(icon,0x1ca,"Food - combined household supply");
 text(icon,0x1c9,"Combined food supply (informative only)");
 text(title,0x1c4,label);text(title,0x1c9,"Weighted supply of this house's required foods. Locked foods are excluded.");
 text(detail,0x1c4,"Delivered food");text(detail,0x1c9,"Informative only. Individual food icons show each household need.");
 food_position(view);
}

#define HOUSE_VIEW_VTABLE 0xb1758u
static uptr viewbase(void *view){return (uptr)ptr(view,0)-HOUSE_VIEW_VTABLE;}
static iptr original(void *view,u32 rva,uptr a,uptr b,uptr c){return ((Method)(viewbase(view)+rva))(view,a,b,c);}
EXPORT iptr food_create(void *view,uptr a,uptr b,uptr c){
 iptr result=original(view,0x80ee0,a,b,c);if((int)result<0)return result;
 if(widget(view,7))return (iptr)(int)0x80004005u;
 u32 icon_id=resource(view,"OVERHAUL_FOOD_SUMMARY"),bar_id=resource(view,"BALKENWOHNHAUS");
 if(icon_id==0xffffffffu||bar_id==0xffffffffu)return (iptr)(int)0x80004005u;
 for(u32 i=7;i<10;i++){
  void *w=(void*)0;
  result=call(view,0x178,i==7?0xb18:0xb1c,(uptr)&w,(uptr)ptr(view,0x6c8));
  if((int)result<0||!w)return (iptr)(int)0x80004005u;
  if((u32)call(view,0x50,(uptr)w,i,0)==65535)return (iptr)(int)0x80004005u;
  call(w,0x80,i,0,0);call(w,0x58,(uptr)ptr(view,i==7?0x710:0x730),0,0);
  call(w,0xa8,i==7?50:166,i==7?50:20,0);
  Value owner;clear(&owner,sizeof(owner));owner.value=(uptr)view;call(w,0xa0,0x19d,(uptr)&owner,0);
  if(i==7){
   *(u32*)((u8*)w+0xc8)=bar_id;
   number(w,0x198,icon_id);
   number(w,0x1bc,100);number(w,0x194,1);number(w,0x190,1);number(w,0x1c2,0);
   number(w,0x1c0,0);
  }else number(w,0x1c6,0);
 }
 food_position(view);return 0;
}
EXPORT iptr food_layout(void *view,uptr a,uptr b,uptr c){iptr result=original(view,0x80be0,a,b,c);food_position(view);return result;}
EXPORT iptr food_set_house(void *view,uptr a,uptr b,uptr c){iptr result=original(view,0x804a0,a,b,c);if(a&&call((void*)a,0x30,0,0,0)==0x1a00)food_refresh(view);else hide(view);return result;}
EXPORT iptr food_tick(void *view,uptr a,uptr b,uptr c){iptr result=original(view,0x80460,a,b,c);if(a==1)food_refresh(view);return result;}
EXPORT iptr food_update(void *view,uptr a,uptr b,uptr c){iptr result=original(view,0x80490,a,b,c);food_refresh(view);return result;}
