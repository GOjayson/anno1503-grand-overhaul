#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
static DWORD protections[2];
static unsigned char *fixtureMemory;
static int calls,failAt,failAlso,flushCalls,failFlush;
static BOOL WINAPI fixtureProtect(LPVOID address,SIZE_T size,DWORD protection,PDWORD previous){
 calls++;if(calls==failAt||calls==failAlso){SetLastError(ERROR_ACCESS_DENIED);return FALSE;}
 uintptr_t delta=(uintptr_t)address-(uintptr_t)fixtureMemory;
 if(delta>=8192||size!=4096||delta%4096){SetLastError(ERROR_INVALID_PARAMETER);return FALSE;}
 unsigned int page=(unsigned int)(delta/4096);*previous=protections[page];protections[page]=protection;return TRUE;
}
static BOOL WINAPI fixtureFlush(HANDLE process,LPCVOID address,SIZE_T length){
 (void)process;(void)address;(void)length;flushCalls++;
 if(flushCalls==failFlush){SetLastError(ERROR_ACCESS_DENIED);return FALSE;}return TRUE;
}
#define VirtualProtect fixtureProtect
#define FlushInstructionCache fixtureFlush
#include "install_test_hooks.c"
void WorldSettingsSetAILoaderHookReady(int ready){(void)ready;}

#define REQUIRE(x) do{if(!(x)){answer=__LINE__;goto done;}}while(0)
/* Invoke the actual grouping/transaction functions. API calls are explicit
 * substitutes; the original bytes, page grouping and rollback execute here. */
__declspec(dllexport) int WorldSettingsPageFixture(int mode){
 int answer=0;WSPatch patches[3]={0};WSPage pages[3]={0};uint32_t count=0;
 fixtureMemory=VirtualAlloc(NULL,8192,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
 if(!fixtureMemory)return __LINE__;
 calls=0;failAt=0;failAlso=0;flushCalls=0;failFlush=0;
 protections[0]=PAGE_EXECUTE_READ;protections[1]=PAGE_READONLY;
 for(int i=0;i<3;i++){
  patches[i].address=fixtureMemory+(i<2?100+i*20:4200);patches[i].length=6;
  memset(patches[i].before,0x30+i,6);memset(patches[i].after,0x90+i,6);
  memcpy(patches[i].address,patches[i].before,6);
 }
 if(mode==20){patches[1].address=patches[0].address+3;REQUIRE(!wsGroupPages(patches,3,pages,&count,4096));goto done;}
 if(mode==21){patches[1].address=fixtureMemory+4094;REQUIRE(!wsGroupPages(patches,3,pages,&count,4096));goto done;}
 if(mode==22){REQUIRE(!wsGroupPages(patches,3,pages,&count,0));goto done;}
 REQUIRE(wsGroupPages(patches,3,pages,&count,4096));
 REQUIRE(count==2&&patches[0].page==patches[1].page&&patches[2].page!=patches[0].page);
 if(mode>=1&&mode<=4)failAt=mode;
 if(mode>=5&&mode<=7)failFlush=mode-4;
 if(mode==8)patches[1].address[0]=0xee;
 if(mode==9){failAt=4;failAlso=5;}
 if(mode==10){failFlush=1;failAt=3;}
 int result=wsApplyPatches(patches,3,pages,count);
 if(mode==0){
  REQUIRE(result==1);for(int i=0;i<3;i++)REQUIRE(!memcmp(patches[i].address,patches[i].after,6));
 }else if(mode==8){REQUIRE(result==0&&calls==0&&flushCalls==0&&patches[1].address[0]==0xee);}
 else if(mode==9||mode==10){REQUIRE(result==-1);}
 else{
  REQUIRE(result==0);for(int i=0;i<3;i++)REQUIRE(!memcmp(patches[i].address,patches[i].before,6));
 }
 if(mode!=9&&mode!=10)REQUIRE(protections[0]==PAGE_EXECUTE_READ&&protections[1]==PAGE_READONLY);
 done:VirtualFree(fixtureMemory,0,MEM_RELEASE);fixtureMemory=NULL;return answer;
}
