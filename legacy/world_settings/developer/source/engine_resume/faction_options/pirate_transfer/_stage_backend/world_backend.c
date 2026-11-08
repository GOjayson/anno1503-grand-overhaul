#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <bcrypt.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../../runtime/world_backend.h"
#include "../alias_runtime/world_catalogue.h"
#include "../../runtime/world_ship_reserves.h"
#include "../../runtime/world_factions.h"

#define WS_LIMIT 128
#define WS_WORLD 1024
#define WS_COUNT (sizeof(wsTemplates)/sizeof(wsTemplates[0]))
static const uint32_t cropMasks[6]={0x18000,0xf009,0xf949,0xf06b,0xf6b9,0xf04d};
static const uint32_t mineralMasks[6]={0,0x45,0x65,0x41,0x43,0x4b};
static const char *climateNames[6]={"polar","tundra","northern","prairie","jungle","steppe"};
static const char *cultureNames[8]={"Moors","Mongols","Bedouins","Aztecs","Africans","Native Americans","Inuit","Polynesians"};
static WSPlanIsland planned[WS_LIMIT];
static uint32_t planCount,planSpacing,rngState,sceneSequence,planFactions;
static int pending,prepared;
static char pendingPath[MAX_PATH],gameDirectory[MAX_PATH],prepareError[512];
static void *preparedScene;
static void wsMessage(char *out,uint32_t cap,const char *msg){if(out&&cap){snprintf(out,cap,"%s",msg);out[cap-1]=0;}}
static uint32_t wsRandom(void){uint32_t n=rngState;n^=n<<13;n^=n>>17;n^=n<<5;return rngState=n;}
static int wsSize(const WSTemplate*t,int size){return size==3||(size>=0&&size<=2&&(t->sizeChoices&(1u<<size)));}
static uint32_t wsTemplateFaction(const WSTemplate*t){return wsTemplateFactions[t-wsTemplates];}
static int wsEligible(const WSTemplate*t,const WSWorldSettings*s){uint32_t f=wsTemplateFaction(t);int size=f?(s->islandSize==3||(wsTemplateFactionSizes[t-wsTemplates]&(1u<<s->islandSize))):wsSize(t,s->islandSize);return (!t->excludedNative||f)&&!(f&~s->factions)&&size&&!(t->cultures&~s->cultures)&&(t->fertileLand>0||t->climate==0);}
static int wsChoose(const WSWorldSettings*s,uint32_t requiredCulture,int climate,int ore,int whale,int empty,int faction){
 uint32_t choice=0,count=0;
 for(uint32_t i=0;i<WS_COUNT;i++){const WSTemplate*t=&wsTemplates[i];if(!wsEligible(t,s)||wsTemplateFaction(t)!=(uint32_t)faction)continue;
  if(requiredCulture&&!(t->cultures&requiredCulture))continue;if(climate>=0&&t->climate!=climate)continue;
  if(ore&&(!t->oreSlots||!(mineralMasks[t->climate]&ore)))continue;if(whale&&!t->whales)continue;
  if(empty&&t->cultures)continue;if(++count==1||wsRandom()%count==0)choice=i;
 }return count?(int)choice:-1;
}
static int wsAdd(uint32_t index,uint32_t*count){if(*count>=WS_LIMIT)return 0;const WSTemplate*t=&wsTemplates[index];WSPlanIsland*p=&planned[(*count)++];memset(p,0,sizeof(*p));p->templateIndex=index;p->width=t->width;p->height=t->height;p->cultures=t->cultures;p->climate=t->climate;p->cropMask=cropMasks[t->climate];return 1;}
static int wsPop(uint32_t n){int count=0;while(n){count++;n&=n-1;}return count;}
static int wsSeparated(const WSPlanIsland*a,const WSPlanIsland*b,uint32_t gap){return a->x+a->width+gap<=b->x||b->x+b->width+gap<=a->x||a->y+a->height+gap<=b->y||b->y+b->height+gap<=a->y;}
static int wsPack(uint32_t count,uint32_t spacing){
 /* Largest first, then deterministic bottom-left contact candidates. */
 uint32_t order[WS_LIMIT];for(uint32_t i=0;i<count;i++)order[i]=i;
 for(uint32_t i=1;i<count;i++){uint32_t key=order[i],j=i;while(j&&planned[order[j-1]].width<planned[key].width){order[j]=order[j-1];j--;}order[j]=key;}
 for(uint32_t i=0;i<count;i++){
  WSPlanIsland*p=&planned[order[i]];int found=0;uint32_t bestX=0,bestY=0;
  uint32_t reserveCount=sizeof(wsShipReserves)/sizeof(wsShipReserves[0]);
  for(uint32_t yi=0;yi<=i+reserveCount;yi++){for(uint32_t xi=0;xi<=i+reserveCount;xi++){
   WSPlanIsland q=*p;
   q.x=xi==0?spacing:(xi<=i?planned[order[xi-1]].x+planned[order[xi-1]].width+spacing:wsShipReserves[xi-i-1].x+wsShipReserves[xi-i-1].width+spacing);
   q.y=yi==0?spacing:(yi<=i?planned[order[yi-1]].y+planned[order[yi-1]].height+spacing:wsShipReserves[yi-i-1].y+wsShipReserves[yi-i-1].height+spacing);
   /* Welt cfea0/cff3a..cff6f snaps both positive coordinates down to an
    * eight-tile grid. Round upward before packing so native loading cannot
    * move a validated island toward another island or a starting ship. */
   q.x=(q.x+7u)&~7u;q.y=(q.y+7u)&~7u;
   if(q.x+q.width+spacing>WS_WORLD||q.y+q.height+spacing>WS_WORLD)continue;int fits=1;
   for(uint32_t j=0;j<i;j++)if(!wsSeparated(&q,&planned[order[j]],spacing)){fits=0;break;}
   for(uint32_t j=0;j<reserveCount&&fits;j++)if(!wsSeparated(&q,&wsShipReserves[j],spacing))fits=0;
   if(fits&&(!found||q.y<bestY||(q.y==bestY&&q.x<bestX))){found=1;bestX=q.x;bestY=q.y;}
  }}
  if(!found)return 0;
  p->x=bestX;p->y=bestY;p->id=order[i];
 }return 1;
}
static int wsValidatePlan(const WSWorldSettings*s,char*error,uint32_t cap){
 uint32_t climates=0,cultures=0,crops=0,minerals=0,whales=0,pirates=0;
 for(uint32_t i=0;i<planCount;i++){const WSPlanIsland*p=&planned[i];const WSTemplate*t=&wsTemplates[p->templateIndex];
  if(p->id!=i||(p->x&7u)||(p->y&7u)||p->x+p->width+planSpacing>WS_WORLD||p->y+p->height+planSpacing>WS_WORLD||p->x<planSpacing||p->y<planSpacing){wsMessage(error,cap,"Island placement is outside the supported native grid or world.");return 0;}
  for(uint32_t j=0;j<i;j++)if(!wsSeparated(p,&planned[j],planSpacing)){wsMessage(error,cap,"Island placement overlaps or violates spacing.");return 0;}
  for(uint32_t j=0;j<sizeof(wsShipReserves)/sizeof(wsShipReserves[0]);j++)if(!wsSeparated(p,&wsShipReserves[j],planSpacing)){wsMessage(error,cap,"Island placement intersects a starting ship reserve.");return 0;}
  if(!wsEligible(t,s)||(p->mineralMask&~mineralMasks[p->climate])||wsPop(p->mineralMask)>t->oreSlots){wsMessage(error,cap,"Template cannot satisfy assigned resources.");return 0;}
  pirates+=wsTemplateFaction(t)==1;climates|=1u<<p->climate;cultures|=p->cultures;crops|=p->cropMask;minerals|=p->mineralMask;whales+=t->whales;
 }
 if(pirates!=((s->factions&1u)!=0)||climates!=63||cultures!=s->cultures||crops!=0x1ffff||(minerals&0x2f)!=0x2f||!whales){wsMessage(error,cap,"World lacks a required climate, culture, crop, mineral or whale template.");return 0;}
 return 1;
}
__declspec(dllexport) int WorldSettingsBuildPlan(const WSWorldSettings*s,uint32_t seed,char*error,uint32_t cap){
 char message[512];
 if(pending){wsMessage(error,cap,"A generated world is already pending.");return 0;}
 planCount=0;
 if(!s||s->size!=sizeof(*s)||s->difficulty<0||s->difficulty>2||s->islandSize<0||s->islandSize>3||s->islandCount<1||s->islandCount>WS_LIMIT||s->spacing<0||s->spacing>256||s->aiCount||s->cultures&~255u||s->factions&~3u){wsMessage(error,cap,"Invalid world settings or unsupported Food Mod AI count.");return 0;}
 rngState=seed?seed:0x15032026;planSpacing=(uint32_t)s->spacing;planFactions=s->factions;
 for(int attempt=0;attempt<32;attempt++){
  uint32_t n=0,seen=0,climates=0;int failed=0;
  for(int c=0;c<8;c++)if((s->cultures&(1u<<c))&&!(seen&(1u<<c))){int pick=wsChoose(s,1u<<c,-1,0,0,0,0);if(pick<0){snprintf(message,sizeof message,"No island in this size contains %s. Choose mixed or another size.",cultureNames[c]);wsMessage(error,cap,message);return 0;}wsAdd((uint32_t)pick,&n);seen|=wsTemplates[pick].cultures;}
  if(s->factions&1u){int pick=wsChoose(s,0,-1,0,0,0,1);if(pick<0||!wsAdd((uint32_t)pick,&n)){wsMessage(error,cap,"No pirate island matches this size.");return 0;}}
  for(uint32_t i=0;i<n;i++)climates|=1u<<planned[i].climate;
  for(int c=0;c<6;c++)if(!(climates&(1u<<c))){int pick=wsChoose(s,0,c,0,0,1,0);if(pick<0){snprintf(message,sizeof message,"This island size has no uninhabited %s template. Choose mixed or another size.",climateNames[c]);wsMessage(error,cap,message);return 0;}wsAdd((uint32_t)pick,&n);}
  /* Rare deposits first; each requires an actual ERZSYMBOL occurrence. */
  const uint32_t need[]={0x20,8,4,2,1};
  for(uint32_t r=0;r<sizeof(need)/sizeof(need[0]);r++){int placed=0;for(uint32_t i=0;i<n;i++){WSPlanIsland*p=&planned[i];const WSTemplate*t=&wsTemplates[p->templateIndex];if((mineralMasks[p->climate]&need[r])&&wsPop(p->mineralMask)<t->oreSlots){p->mineralMask|=need[r];placed=1;break;}}
   if(!placed){int pick=wsChoose(s,0,-1,(int)need[r],0,1,0);if(pick<0){wsMessage(error,cap,"No eligible ore occurrence matches the requested size and cultures.");return 0;}if(!wsAdd((uint32_t)pick,&n)){failed=1;break;}planned[n-1].mineralMask=need[r];}
  }if(failed)continue;
  uint32_t whales=0;for(uint32_t i=0;i<n;i++)whales+=wsTemplates[planned[i].templateIndex].whales;
  if(!whales){int pick=wsChoose(s,0,-1,0,1,1,0);if(pick<0){wsMessage(error,cap,"No whale occurrence matches these settings.");return 0;}wsAdd((uint32_t)pick,&n);}
  if(n>(uint32_t)s->islandCount){snprintf(message,sizeof message,"At least %u islands are required for these cultures and essential resources.",n);wsMessage(error,cap,message);continue;}
  while(n<(uint32_t)s->islandCount){int pick=wsChoose(s,0,-1,0,0,1,0);if(pick<0||!wsAdd((uint32_t)pick,&n)){failed=1;break;}}
  if(failed||!wsPack(n,(uint32_t)s->spacing)){wsMessage(error,cap,"Island size, count and spacing do not fit in the supported 1024 by 1024 world.");continue;}
  planCount=n;if(wsValidatePlan(s,error,cap)){wsMessage(error,cap,"");return 1;}planCount=0;
 }return 0;
}
__declspec(dllexport) int WorldSettingsPlanCount(void){return(int)planCount;}
__declspec(dllexport) int WorldSettingsPlanIsland(uint32_t i,WSPlanIsland*out){if(i>=planCount||!out)return 0;*out=planned[i];return 1;}

static uint32_t wsU32(const unsigned char*p){uint32_t n;memcpy(&n,p,4);return n;}
static uint16_t wsU16(const unsigned char*p){uint16_t n;memcpy(&n,p,2);return n;}
static void wsPut32(unsigned char*p,uint32_t n){memcpy(p,&n,4);}
static void wsPut16(unsigned char*p,uint16_t n){memcpy(p,&n,2);}
static int wsTag(const unsigned char*p,const char*tag){size_t n=strlen(tag);return n<=12&&!memcmp(p,tag,n)&&(n==12||p[n]==0);}
static int wsHashFile(const char*path,const unsigned char expected[32]){
 BCRYPT_ALG_HANDLE alg=NULL;BCRYPT_HASH_HANDLE hash=NULL;HANDLE file=INVALID_HANDLE_VALUE;unsigned char data[32768],digest[32];DWORD got;int ok=0;
 if(BCryptOpenAlgorithmProvider(&alg,BCRYPT_SHA256_ALGORITHM,NULL,0)<0)goto done;
 if(BCryptCreateHash(alg,&hash,NULL,0,NULL,0,0)<0)goto done;
 file=CreateFileA(path,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);if(file==INVALID_HANDLE_VALUE)goto done;
 do{if(!ReadFile(file,data,sizeof data,&got,NULL))goto done;if(got&&BCryptHashData(hash,data,got,0)<0)goto done;}while(got);
 if(BCryptFinishHash(hash,digest,sizeof digest,0)<0)goto done;ok=!memcmp(digest,expected,32);
 done:if(file!=INVALID_HANDLE_VALUE)CloseHandle(file);if(hash)BCryptDestroyHash(hash);if(alg)BCryptCloseAlgorithmProvider(alg,0);return ok;
}
static int wsFullPath(const char*root,const char*relative,char out[MAX_PATH]){int n=snprintf(out,MAX_PATH,"%s\\%s",root,relative);return n>0&&n<MAX_PATH;}
static const char*wsDummy(const WSTemplate*t,char path[100]){
 const char*folder[]={"polar","tundra","nord","praerie","dschungel","steppe"};const char*prefix[]={"Po","T","N","Pr","D","S"};
 snprintf(path,100,"islands\\%s\\%s_%03ux%03u_dummy.scp",folder[t->climate],prefix[t->climate],t->width,t->height);return path;
}
typedef struct WSBuffer{unsigned char*data;uint32_t size,capacity;}WSBuffer;
static int wsAppend(WSBuffer*b,const void*data,uint32_t size){if(size>b->capacity-b->size)return 0;memcpy(b->data+b->size,data,size);b->size+=size;return 1;}
static int wsChunk(WSBuffer*b,const char*tag,const void*payload,uint32_t size){unsigned char h[16]={0};memcpy(h,tag,strlen(tag));wsPut32(h+12,size);return wsAppend(b,h,16)&&wsAppend(b,payload,size);}
static int wsLinks(WSBuffer*b){
 for(uint32_t i=0;i<planCount;i++){WSPlanIsland*p=&planned[i];unsigned char link[128]={0};char dummy[100];wsDummy(&wsTemplates[p->templateIndex],dummy);
  wsPut16(link,(uint16_t)p->x);wsPut16(link+2,(uint16_t)p->y);wsPut16(link+4,(uint16_t)p->width);wsPut16(link+6,(uint16_t)p->height);wsPut32(link+8,p->id);memcpy(link+12,dummy,strlen(dummy)+1);
  if(!wsChunk(b,"INSELLNK",link,(uint32_t)strlen(dummy)+13))return 0;
 }return 1;
}
#include "../../runtime/special_scene.inc"
static int wsBuildSZE(const WSWorldSettings*s,WSBuffer*b,char*error,uint32_t cap){
 const unsigned char*src=s->difficulty==0?wsSceneEasy:(s->difficulty==1?wsSceneMedium:wsSceneHard);
 uint32_t size=s->difficulty==0?sizeof(wsSceneEasy):(s->difficulty==1?sizeof(wsSceneMedium):sizeof(wsSceneHard));
 if(size<32||(!wsTag(src,"ANNO")&&!wsTag(src,"ANNOADDON1"))||wsU32(src+12)!=size-16||!wsTag(src+16,"SCENE")||wsU32(src+28)!=size-32){wsMessage(error,cap,"Embedded scene envelope is not recognized.");return 0;}
 unsigned char special[32]={0};if(!wsSpecialPlayers(src,size,special,error,cap))return 0;
 if(!wsAppend(b,src,32))return 0;int links=0,head=0,ores=0,crops=0,treasure=0;
 for(uint32_t at=32;at<size;){if(size-at<16){wsMessage(error,cap,"Truncated embedded scene chunk.");return 0;}uint32_t n=wsU32(src+at+12);if(n>size-at-16){wsMessage(error,cap,"Embedded scene chunk crosses its parent.");return 0;}
  if(wsTag(src+at,"SPIELER")&&n>=8&&wsU32(src+at+20)<32&&special[wsU32(src+at+20)]&&!(s->factions&special[wsU32(src+at+20)])){}
  else if(wsTag(src+at,"BIGBROTHER")){if(!wsSpecialScript(b,src+at+16,n,s->factions,special,error,cap))return 0;}
  else if(wsTag(src+at,"INSELLNK")||wsTag(src+at,"INSEL5")){if(!links&&!wsLinks(b))return 0;links=1;}
  else if(wsTag(src+at,"HEAD")){if(n!=32||wsU32(src+at+16)!=WS_WORLD||wsU32(src+at+20)!=WS_WORLD){wsMessage(error,cap,"Only verified 1024 by 1024 scene headers are supported.");return 0;}head++;if(!wsAppend(b,src+at,n+16))return 0;}
  else if(wsTag(src+at,"ROHSTOFF")||wsTag(src+at,"ERZE")||wsTag(src+at,"SCHATZ")){unsigned char zeros[32]={0};if(n>sizeof zeros){wsMessage(error,cap,"Unsupported resource request chunk.");return 0;}if(wsTag(src+at,"ROHSTOFF"))crops++;if(wsTag(src+at,"ERZE"))ores++;if(wsTag(src+at,"SCHATZ"))treasure++;char tag[13]={0};memcpy(tag,src+at,12);if(!wsChunk(b,tag,zeros,n))return 0;}
  else if(!wsAppend(b,src+at,n+16))return 0;at+=n+16;
 }
 if(!links||head!=1||ores!=1||crops!=1||treasure!=1){wsMessage(error,cap,"Required scene chunks are absent or duplicated.");return 0;}
 wsPut32(b->data+12,b->size-16);wsPut32(b->data+28,b->size-32);return 1;
}
__declspec(dllexport) int WorldSettingsStageScene(const WSWorldSettings*s,const char*root,uint32_t seed,char*out,uint32_t outCap,char*error,uint32_t cap){
 if(!root||strlen(root)<3||strlen(root)>=MAX_PATH||!((root[1]==':'&&(root[2]=='\\'||root[2]=='/'))||(root[0]=='\\'&&root[1]=='\\'))){wsMessage(error,cap,"An absolute game folder path is required.");return 0;}
 if(!WorldSettingsBuildPlan(s,seed,error,cap))return 0;
 char path[MAX_PATH],dummy[100];unsigned char checked[WS_COUNT];memset(checked,0,sizeof checked);
 for(uint32_t i=0;i<planCount;i++){const WSTemplate*t=&wsTemplates[planned[i].templateIndex];uint32_t index=planned[i].templateIndex;
  if(!checked[index]){if(!wsFullPath(root,t->path,path)||!wsHashFile(path,t->sha256)){wsMessage(error,cap,"A selected island differs from the inspected History Edition catalogue.");return 0;}checked[index]=1;}
  char relative[128];snprintf(relative,sizeof relative,"Scenes\\%s",wsDummy(t,dummy));DWORD attributes;
  if(!wsFullPath(root,relative,path)||(attributes=GetFileAttributesA(path))==INVALID_FILE_ATTRIBUTES||(attributes&FILE_ATTRIBUTE_DIRECTORY)){wsMessage(error,cap,"A native dummy island alias is missing.");return 0;}
 }
 WSBuffer b={0};b.capacity=262144;b.data=(unsigned char*)malloc(b.capacity);if(!b.data){wsMessage(error,cap,"Cannot allocate generated scene buffer.");return 0;}
 if(!wsBuildSZE(s,&b,error,cap)){free(b.data);return 0;}
 char relative[120];snprintf(relative,sizeof relative,"Scenes\\WorldSettings_%lu_%u.sze",(unsigned long)GetCurrentProcessId(),++sceneSequence);
 if(!wsFullPath(root,relative,path)||!out||outCap<=strlen(path)){free(b.data);wsMessage(error,cap,"Generated scene path is too long.");return 0;}
 HANDLE f=CreateFileA(path,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);DWORD written=0;int created=f!=INVALID_HANDLE_VALUE;int ok=created;
 if(ok){ok=WriteFile(f,b.data,b.size,&written,NULL)&&written==b.size&&FlushFileBuffers(f);CloseHandle(f);}free(b.data);
 if(!ok){if(created)DeleteFileA(path);wsMessage(error,cap,"Cannot write the generated scene.");return 0;}
 snprintf(gameDirectory,sizeof gameDirectory,"%s",root);snprintf(pendingPath,sizeof pendingPath,"%s",path);snprintf(out,outCap,"%s",path);pending=1;prepared=0;preparedScene=NULL;prepareError[0]=0;wsMessage(error,cap,"");return 1;
}
__declspec(dllexport) const char*WorldSettingsPendingPath(void){return pending?pendingPath:NULL;}
__declspec(dllexport) int WorldSettingsIsActive(void){return pending;}
static int wsMemory(const void*ptr,SIZE_T size,int write){MEMORY_BASIC_INFORMATION m;if(!ptr||!VirtualQuery(ptr,&m,sizeof m)||m.State!=MEM_COMMIT||m.Protect&(PAGE_GUARD|PAGE_NOACCESS))return 0;uintptr_t at=(uintptr_t)ptr,end=(uintptr_t)m.BaseAddress+m.RegionSize;if(at>end||size>end-at)return 0;if(write&&!(m.Protect&(PAGE_READWRITE|PAGE_WRITECOPY|PAGE_EXECUTE_READWRITE|PAGE_EXECUTE_WRITECOPY)))return 0;return 1;}
__declspec(dllexport) int WorldSettingsPrepareScene(void*scene,void*sceneBase){
 (void)sceneBase;if(!pending)return 1;prepared=0;preparedScene=NULL;
 if(!wsMemory(scene,0x53f8,0)){wsMessage(prepareError,sizeof prepareError,"Invalid native scene object.");return 0;}
 unsigned char*node;memcpy(&node,(unsigned char*)scene+0x53f0,8);unsigned char*nodes[WS_LIMIT];unsigned char seen[WS_LIMIT]={0};uint32_t count=0;
 while(node){if(count>=planCount||!wsMemory(node,0x15e,1)){wsMessage(prepareError,sizeof prepareError,"Native dummy list is invalid or exceeds the plan.");return 0;}
  uint32_t id=wsU32(node+0x18);if(id>=planCount||seen[id]){wsMessage(prepareError,sizeof prepareError,"Native dummy list has an invalid or repeated island ID.");return 0;}WSPlanIsland*p=&planned[id];
  if(wsU16(node+0x10)!=p->x||wsU16(node+0x12)!=p->y||wsU16(node+0x14)!=p->width||wsU16(node+0x16)!=p->height||wsU16(node+0x1c)!=p->climate){wsMessage(prepareError,sizeof prepareError,"Native island geometry or climate differs from the validated plan.");return 0;}
  char full[MAX_PATH];if(!wsFullPath(gameDirectory,wsTemplates[p->templateIndex].path,full)){wsMessage(prepareError,sizeof prepareError,"Selected island path is too long.");return 0;}
  nodes[count++]=node;seen[id]=1;memcpy(&node,node+8,8);
 }
 if(count!=planCount){wsMessage(prepareError,sizeof prepareError,"Native dummy list does not contain every planned island.");return 0;}
 /* Commit only after the entire native list has passed bounds and identity checks. */
 for(uint32_t i=0;i<count;i++){node=nodes[i];WSPlanIsland*p=&planned[wsU32(node+0x18)];char full[MAX_PATH];wsFullPath(gameDirectory,wsTemplates[p->templateIndex].path,full);memset(node+0x1e,0,260);memcpy(node+0x1e,full,strlen(full));
  for(uint32_t c=0;c<20;c++)wsPut16(node+0x122+c*2,(uint16_t)((p->cropMask>>c)&1));for(uint32_t m=0;m<9;m++)wsPut16(node+0x14a+m*2,(uint16_t)((p->mineralMask>>m)&1));node[0x15c]=(unsigned char)(p->cultures!=0||wsTemplateFaction(&wsTemplates[p->templateIndex])!=0);node[0x15d]=0;
 }prepared=1;preparedScene=scene;return 1;
}
#include "../../runtime/validated_world.inc"
__declspec(dllexport) int WorldSettingsValidateScene(void*scene,char*error,uint32_t cap){
 if(!pending)return 1;
 if(!prepared||preparedScene!=scene){wsMessage(error,cap,prepareError[0]?prepareError:"Native world preparation did not complete.");return 0;}
 return wsLoadedCertificate(scene,error,cap);
}
__declspec(dllexport) void WorldSettingsFinishAttempt(int success){(void)success;if(pendingPath[0])DeleteFileA(pendingPath);pending=0;prepared=0;preparedScene=NULL;pendingPath[0]=0;gameDirectory[0]=0;prepareError[0]=0;}
