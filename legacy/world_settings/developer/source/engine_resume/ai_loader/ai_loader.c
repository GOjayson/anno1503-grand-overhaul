/* Private candidate: called only at the inspected Welt LoadLibraryA call site.
 * This is not DllMain code and does not patch a loader or installed file.
 * Root and source verification are additional to the UI's marked-copy guard.
 */
#include "ai_loader.h"
#include <bcrypt.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static char candidates[2][MAX_PATH], originals[2][MAX_PATH], loaderError[512];
static int configured;
static volatile LONG hookReady;
static HMODULE lastLoaded;
static const char *names[2]={"CompLogic.dll","CompLogicClassic.dll"};
static const char *sourceHashes[2]={
 "7f2c7e818d8c25a0b6c48cda2d21bfa0c4096c5dcd8be91c2ab93d877c22afee",
 "0a7692879e15e8cbaed73ec3b59eaa6419165faaea6d8696cddfd68c92000f22"};
static const char *candidateHashes[2]={
 "0612873c32c95252144f4b4fd2bed45dddddc177303981833b673ddc4ed51453",
 "29d1759bd3beb39f9a5a3364946a24b36f8bb4fa546c6a999b6ca994aeeaab34"};

#ifdef WS_AI_LOADER_TEST
static HMODULE (WINAPI *nativeLoader)(const char *)=LoadLibraryA;
__declspec(dllexport) void WorldSettingsTestSetLoader(HMODULE (WINAPI *fn)(const char *)){nativeLoader=fn?fn:LoadLibraryA;}
__declspec(dllexport) int WorldSettingsTestConfigure(const char *copyRoot,const char *sourceRoot){return WorldSettingsConfigureAIExperiment(copyRoot,sourceRoot);}
__declspec(dllexport) void WorldSettingsTestReady(int ready){WorldSettingsSetAILoaderHookReady(ready);}
__declspec(dllexport) int WorldSettingsTestConfigured(void){return WorldSettingsAIExperimentConfigured();}
#define WS_NATIVE_LOAD(p) nativeLoader(p)
#else
#define WS_NATIVE_LOAD(p) LoadLibraryA(p)
#endif

static int fail(const char *message){snprintf(loaderError,sizeof loaderError,"%s",message);SetLastError(ERROR_INVALID_DATA);return 0;}
static int path(char out[MAX_PATH],const char *root,const char *middle,const char *name){
 if(!root||!root[0])return 0;
 int n=snprintf(out,MAX_PATH,"%s\\%s%s",root,middle,name);
 return n>0&&n<MAX_PATH;
}
static int absolute(const char *s){return s&&strlen(s)<MAX_PATH&&strlen(s)>2&&((s[1]==':'&&(s[2]=='\\'||s[2]=='/'))||(s[0]=='\\'&&s[1]=='\\'));}
static int shaPE(const char *filename,const char *expected){
 HANDLE file=CreateFileA(filename,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
 if(file==INVALID_HANDLE_VALUE)return fail("An AI source or copied module cannot be read.");
 BCRYPT_ALG_HANDLE algorithm=NULL;BCRYPT_HASH_HANDLE hash=NULL;
 unsigned char bytes[32768],digest[32],header[4096];DWORD got=0;int ok=0;uint64_t total=0;DWORD headerLength=0;
 if(BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,NULL,0)<0||BCryptCreateHash(algorithm,&hash,NULL,0,NULL,0,0)<0){fail("AI module SHA256 initialization failed.");goto done;}
 do{
  if(!ReadFile(file,bytes,sizeof bytes,&got,NULL)){fail("AI module read failed.");goto done;}
  if(!total){headerLength=got<sizeof header?got:sizeof header;memcpy(header,bytes,headerLength);}
  total+=got;
  if(got&&BCryptHashData(hash,bytes,got,0)<0){fail("AI module hashing failed.");goto done;}
 }while(got);
 if(BCryptFinishHash(hash,digest,sizeof digest,0)<0){fail("AI module SHA256 completion failed.");goto done;}
 char actual[65];for(int i=0;i<32;i++)snprintf(actual+i*2,3,"%02x",digest[i]);
 if(strcmp(actual,expected)){fail("AI module differs from its inspected SHA256 fingerprint.");goto done;}
 uint32_t pe=0;uint16_t machine=0,magic=0;
 if(headerLength<64||memcmp(header,"MZ",2)){fail("AI module has no supported PE header.");goto done;}
 memcpy(&pe,header+0x3c,4);
 if(pe>headerLength||headerLength-pe<26||memcmp(header+pe,"PE\0\0",4)){fail("AI module PE header exceeds its bounded header.");goto done;}
 memcpy(&machine,header+pe+4,2);memcpy(&magic,header+pe+24,2);
 if(machine!=0x8664||magic!=0x20b){fail("AI integration requires the inspected AMD64 PE32+ modules.");goto done;}
 ok=1;
 done:if(hash)BCryptDestroyHash(hash);if(algorithm)BCryptCloseAlgorithmProvider(algorithm,0);CloseHandle(file);return ok;
}

int WorldSettingsConfigureAIExperiment(const char *copyRoot,const char *sourceRoot){
 configured=0;hookReady=0;lastLoaded=NULL;memset(candidates,0,sizeof candidates);memset(originals,0,sizeof originals);loaderError[0]=0;
 if(!copyRoot&&!sourceRoot)return 1;
 if(!absolute(copyRoot)||!absolute(sourceRoot)||!_stricmp(copyRoot,sourceRoot))return fail("AI modules require distinct absolute source and copy folders.");
 for(int i=0;i<2;i++){
  if(!path(candidates[i],copyRoot,"WorldSettingsAI\\",names[i])||!path(originals[i],sourceRoot,"",names[i]))return fail("AI module path exceeds MAX_PATH.");
  if(!shaPE(originals[i],sourceHashes[i])||!shaPE(candidates[i],candidateHashes[i]))return 0;
 }
 configured=1;return 1;
}
void WorldSettingsSetAILoaderHookReady(int ready){InterlockedExchange(&hookReady,ready==1);}
int WorldSettingsAIExperimentConfigured(void){return configured&&hookReady;}
HMODULE WorldSettingsLoadedAIModule(void){
 if(!configured||!hookReady||!lastLoaded)return NULL;
 char resolved[MAX_PATH];DWORD n=GetModuleFileNameA(lastLoaded,resolved,MAX_PATH);
 if(!n||n>=MAX_PATH||(_stricmp(resolved,candidates[0])&&_stricmp(resolved,candidates[1])))return NULL;
 return lastLoaded;
}

__declspec(dllexport) HMODULE WINAPI WorldSettingsLoadAiModule(const char *nativePath){
 if(!configured||!nativePath)return WS_NATIVE_LOAD(nativePath);
 int which=-1;
 for(int i=0;i<2;i++)if(!_stricmp(nativePath,originals[i])||!_stricmp(nativePath,names[i]))which=i;
 if(which<0)return WS_NATIVE_LOAD(nativePath);
 if(!hookReady){fail("The copied AI loader hook has not completed activation.");return NULL;}
 /* Recheck at use: unknown or replaced files must never become AI controllers. */
 if(!shaPE(candidates[which],candidateHashes[which]))return NULL;
 HMODULE loaded=WS_NATIVE_LOAD(candidates[which]);
#ifndef WS_AI_LOADER_TEST
 if(loaded){char resolved[MAX_PATH];DWORD n=GetModuleFileNameA(loaded,resolved,MAX_PATH);
  if(!n||n>=MAX_PATH||_stricmp(resolved,candidates[which])){
   FreeLibrary(loaded);fail("Windows returned an AI module outside the verified copy path.");return NULL;
  }
 }
#endif
 if(!loaded)fail("Windows could not load the verified copied AI module.");
 else lastLoaded=loaded;
 return loaded;
}
__declspec(dllexport) DWORD WINAPI WorldSettingsCopyAILoaderError(void *buffer){
 if(!buffer)return 0;char *out=(char*)buffer;DWORD n=0;
 do{out[n]=loaderError[n];n++;}while(n<sizeof loaderError&&loaderError[n-1]);out[n-1]=0;return n;
}
