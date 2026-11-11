/* Synchronous native-checkpoint chart storage. No timer, watcher, sidecar or
 * native simulation field is used as storage. Included after chart/runtime. */
#include "start_visibility_chart.h"
#define WS_MEMORY_NATIVE_LIMIT (128u*1024u*1024u)
#define WS_MEMORY_FILE_LIMIT (WS_MEMORY_NATIVE_LIMIT+WS_CHART_BLOB_LIMIT+256u)
#define WS_MEMORY_HEADER 128u
typedef struct WSMemoryFile {
 uint32_t chartAt,chartSpan,nativeSize,blobSize,width,height,policy,viewer;int full;
 const unsigned char*blob;unsigned char guid[16];
} WSMemoryFile;
static char wsMemoryIOError[512];
static volatile LONG wsMemorySaveBusy,wsMemoryFileSequence;
static int wsMemoryError(char*out,uint32_t cap,const char*message){wsMessage(out,cap,message);return 0;}
static int wsMemoryExactTag(const unsigned char*p,const char*name){size_t n=strlen(name);if(n>12u||memcmp(p,name,n))return 0;for(size_t i=n;i<12u;i++)if(p[i])return 0;return 1;}
static int wsMemoryTagValid(const unsigned char*p){int end=0,any=0;for(unsigned i=0;i<12;i++){unsigned c=p[i];if(!c){end=1;continue;}if(end||!((c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'))return 0;any=1;}return any;}
static int wsMemoryZero(const unsigned char*p,uint32_t size){for(uint32_t i=0;i<size;i++)if(p[i])return 0;return 1;}
static int wsMemoryHash(const unsigned char*data,uint32_t size,unsigned char out[32]){
 BCRYPT_ALG_HANDLE alg=NULL;BCRYPT_HASH_HANDLE hash=NULL;int ok=0;
 if(BCryptOpenAlgorithmProvider(&alg,BCRYPT_SHA256_ALGORITHM,NULL,0)<0||BCryptCreateHash(alg,&hash,NULL,0,NULL,0,0)<0)goto done;
 if(BCryptHashData(hash,(PUCHAR)data,size,0)<0||BCryptFinishHash(hash,out,32,0)<0)goto done;ok=1;
 done:if(hash)BCryptDestroyHash(hash);if(alg)BCryptCloseAlgorithmProvider(alg,0);return ok;
}
/* Hash the exact native file after excluding WSCHART and normalizing ONLY
 * the root payload length. This avoids a self-referential whole-file hash. */
static int wsMemoryNativeHash(const unsigned char*data,uint32_t size,const WSMemoryFile*f,unsigned char out[32]){
 BCRYPT_ALG_HANDLE alg=NULL;BCRYPT_HASH_HANDLE hash=NULL;unsigned char head[16];int ok=0;
 if(!f||size<16u||f->nativeSize<16u)return 0;memcpy(head,data,16);wsPut32(head+12,f->nativeSize-16u);
 if(BCryptOpenAlgorithmProvider(&alg,BCRYPT_SHA256_ALGORITHM,NULL,0)<0||BCryptCreateHash(alg,&hash,NULL,0,NULL,0,0)<0)goto done;
 if(BCryptHashData(hash,head,16,0)<0)goto done;
 if(f->chartSpan){
  if(f->chartAt<16u||f->chartAt>size||f->chartSpan>size-f->chartAt)goto done;
  if(BCryptHashData(hash,(PUCHAR)data+16,f->chartAt-16u,0)<0||BCryptHashData(hash,(PUCHAR)data+f->chartAt+f->chartSpan,size-f->chartAt-f->chartSpan,0)<0)goto done;
 }else if(BCryptHashData(hash,(PUCHAR)data+16,size-16u,0)<0)goto done;
 if(BCryptFinishHash(hash,out,32,0)<0)goto done;ok=1;
 done:if(hash)BCryptDestroyHash(hash);if(alg)BCryptCloseAlgorithmProvider(alg,0);return ok;
}
static int wsMemoryBlobIdentity(const unsigned char*p,uint32_t size,const WSMemoryFile*f){
 return p&&f&&size>=128u&&size<=WS_CHART_BLOB_LIMIT&&!memcmp(p,"WSCHRT01",8)&&wsU32(p+8)==1u&&wsU32(p+12)==128u&&
  wsU32(p+16)==f->width&&wsU32(p+20)==f->height&&wsU32(p+24)==f->viewer&&wsU32(p+28)==f->policy&&!memcmp(p+32,f->guid,16);
}
static int wsMemoryParse(const unsigned char*data,uint32_t size,WSMemoryFile*out,char*error,uint32_t cap){
 WSMemoryFile f={0};uint32_t at=16,welt=0,guid=0,alias=0;int invalidKnown=0;const unsigned char*head=NULL;
 if(!data||!out||size<16u||size>WS_MEMORY_FILE_LIMIT||!wsMemoryExactTag(data,"ANNOADDON1")||wsU32(data+12)!=size-16u)return wsMemoryError(error,cap,"The native save has an invalid root or size.");
 while(at<size){
  if(size-at<16u||!wsMemoryTagValid(data+at))return wsMemoryError(error,cap,"The native save has a truncated or invalid chunk.");
  uint32_t n=wsU32(data+at+12);if(n>size-at-16u)return wsMemoryError(error,cap,"A native save chunk crosses its parent.");
  const unsigned char*p=data+at+16u;
  if(wsMemoryExactTag(data+at,"WSCHART")){
   if(f.chartSpan||n<WS_MEMORY_HEADER||n-WS_MEMORY_HEADER>WS_CHART_BLOB_LIMIT)return wsMemoryError(error,cap,"The save has duplicate or oversized exploration memory.");
   f.chartAt=at;f.chartSpan=16u+n;head=p;f.blob=p+WS_MEMORY_HEADER;f.blobSize=n-WS_MEMORY_HEADER;
  }else if(wsMemoryExactTag(data+at,"WELT")){
   welt++;if(n!=32u)invalidKnown=1;if(n>=8u){f.width=wsU32(p);f.height=wsU32(p+4);}if(n>=18u)f.policy|=wsU16(p+16)&WS_VISIBILITY_POLICY_MASK;
  }else if(wsMemoryExactTag(data+at,"GUID")){
   guid++;if(n!=16u)invalidKnown=1;else memcpy(f.guid,p,16);
  }else if(wsMemoryExactTag(data+at,"ALIASNAME")){
   alias++;if(n!=128u)invalidKnown=1;
  }
  at+=16u+n;
 }
 f.nativeSize=size-f.chartSpan;f.full=welt==1u&&guid==1u&&alias==1u&&!invalidKnown;
 if(f.nativeSize>WS_MEMORY_NATIVE_LIMIT)return wsMemoryError(error,cap,"The native checkpoint exceeds the supported file bound.");
 /* Unmarked native saves keep their own metadata/dimension rules. Only this
  * mod's policy or extension requires the exact exploration-world schema. */
 if((f.policy||head)&&!f.full)return wsMemoryError(error,cap,"The exploration checkpoint has ambiguous or missing native world metadata.");
 if((f.policy||head)&&(f.width!=f.height||(f.width!=256u&&f.width!=512u&&f.width!=1024u&&f.width!=2048u)))return wsMemoryError(error,cap,"The native world dimensions are unsupported.");
 if(head){
  unsigned char digest[32];f.viewer=wsU32(head+116);
  if(!f.full||memcmp(head,"WSCHART1",8)||wsU32(head+8)!=1u||wsU32(head+12)!=128u||
     wsU32(head+96)!=f.width||wsU32(head+100)!=f.height||wsU32(head+104)!=f.policy||wsU32(head+108)!=f.nativeSize||wsU32(head+112)!=f.blobSize||
     f.viewer>=16u||!f.policy||!wsMemoryZero(head+120,8)||memcmp(head+80,f.guid,16)||!wsMemoryBlobIdentity(f.blob,f.blobSize,&f))return wsMemoryError(error,cap,"Exploration memory belongs to a different checkpoint or schema.");
  if(!wsMemoryNativeHash(data,size,&f,digest)||memcmp(digest,head+16,32)||!wsMemoryHash(f.blob,f.blobSize,digest)||memcmp(digest,head+48,32))return wsMemoryError(error,cap,"The checkpoint or exploration checksum differs.");
 }
 *out=f;return 1;
}
static int wsMemoryAssemble(const unsigned char*native,uint32_t size,const WSMemoryFile*base,const unsigned char*blob,uint32_t blobSize,unsigned char**out,uint32_t*outSize,char*error,uint32_t cap){
 if(!native||!base||!base->full||base->chartSpan||!blob||!out||!outSize||blobSize<128u||blobSize>WS_CHART_BLOB_LIMIT)return wsMemoryError(error,cap,"Cannot attach exploration memory to this native output.");
 WSMemoryFile f=*base;f.viewer=wsU32(blob+24);
 if(!wsMemoryBlobIdentity(blob,blobSize,&f)||size>WS_MEMORY_FILE_LIMIT-16u-WS_MEMORY_HEADER-blobSize)return wsMemoryError(error,cap,"The exploration snapshot does not match the saved world.");
 uint32_t total=size+16u+WS_MEMORY_HEADER+blobSize;unsigned char*data=(unsigned char*)malloc(total);if(!data)return wsMemoryError(error,cap,"Cannot allocate the complete exploration checkpoint.");
 memcpy(data,native,size);wsPut32(data+12,total-16u);memset(data+size,0,16u+WS_MEMORY_HEADER);memcpy(data+size,"WSCHART",7);wsPut32(data+size+12,WS_MEMORY_HEADER+blobSize);
 unsigned char*h=data+size+16u;memcpy(h,"WSCHART1",8);wsPut32(h+8,1);wsPut32(h+12,128);memcpy(h+80,f.guid,16);
 wsPut32(h+96,f.width);wsPut32(h+100,f.height);wsPut32(h+104,f.policy);wsPut32(h+108,size);wsPut32(h+112,blobSize);wsPut32(h+116,f.viewer);memcpy(h+128,blob,blobSize);
 if(!wsMemoryNativeHash(native,size,&f,h+16)||!wsMemoryHash(blob,blobSize,h+48)){free(data);return wsMemoryError(error,cap,"Cannot certify the exploration checkpoint checksums.");}
 WSMemoryFile checked;if(!wsMemoryParse(data,total,&checked,error,cap)||checked.nativeSize!=size||memcmp(data+16,native+16,size-16u)){free(data);return 0;}
 *out=data;*outSize=total;return 1;
}
static int wsMemoryRegular(HANDLE file,BY_HANDLE_FILE_INFORMATION*info){
 return file!=INVALID_HANDLE_VALUE&&GetFileType(file)==FILE_TYPE_DISK&&GetFileInformationByHandle(file,info)&&info->nNumberOfLinks==1u&&!(info->dwFileAttributes&(FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT));
}
static int wsMemorySameFile(const BY_HANDLE_FILE_INFORMATION*a,const BY_HANDLE_FILE_INFORMATION*b){
 return a->dwVolumeSerialNumber==b->dwVolumeSerialNumber&&a->nFileIndexHigh==b->nFileIndexHigh&&a->nFileIndexLow==b->nFileIndexLow&&a->nFileSizeHigh==b->nFileSizeHigh&&a->nFileSizeLow==b->nFileSizeLow&&a->ftLastWriteTime.dwHighDateTime==b->ftLastWriteTime.dwHighDateTime&&a->ftLastWriteTime.dwLowDateTime==b->ftLastWriteTime.dwLowDateTime;
}
static int wsMemorySafeParents(const char*path){
 char full[MAX_PATH];DWORD n=GetFullPathNameA(path,MAX_PATH,full,NULL);if(!n||n>=MAX_PATH||n<4u||full[1]!=':'||full[2]!='\\')return 0;
 for(DWORD i=3;i<n;i++)if(full[i]=='\\'){char old=full[i];full[i]=0;DWORD a=GetFileAttributesA(full);full[i]=old;if(a==INVALID_FILE_ATTRIBUTES||!(a&FILE_ATTRIBUTE_DIRECTORY)||(a&FILE_ATTRIBUTE_REPARSE_POINT))return 0;}return 1;
}
static HANDLE wsMemoryReadFile(const char*path,unsigned char**out,uint32_t*size,BY_HANDLE_FILE_INFORMATION*info,char*error,uint32_t cap){
 HANDLE file=INVALID_HANDLE_VALUE;unsigned char*data=NULL;LARGE_INTEGER n;DWORD got=0;BY_HANDLE_FILE_INFORMATION after;
 if(!path||!out||!size||!info||!wsMemorySafeParents(path))goto failed;
 file=CreateFileA(path,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,NULL);
 if(!wsMemoryRegular(file,info)||!GetFileSizeEx(file,&n)||n.QuadPart<16||n.QuadPart>WS_MEMORY_FILE_LIMIT)goto failed;
 data=(unsigned char*)malloc((size_t)n.QuadPart);if(!data||!ReadFile(file,data,(DWORD)n.QuadPart,&got,NULL)||got!=(DWORD)n.QuadPart||!wsMemoryRegular(file,&after)||!wsMemorySameFile(info,&after))goto failed;
 *out=data;*size=got;return file;
 failed:free(data);if(file!=INVALID_HANDLE_VALUE)CloseHandle(file);wsMemoryError(error,cap,"Cannot read one stable, regular native checkpoint.");return INVALID_HANDLE_VALUE;
}
static int wsMemoryString(const char*source,char out[MAX_PATH]){if(!source)return 0;for(uint32_t i=0;i<MAX_PATH;i++){if(!wsCertRead(source+i,out+i,1))return 0;if(!out[i])return i>0u;}return 0;}
static int wsMemorySavePath(void*owner,const char*filename,char out[MAX_PATH]){
 char root[MAX_PATH],name[MAX_PATH],combined[MAX_PATH],fullRoot[MAX_PATH];
 if(!wsMemoryString((const char*)owner+0x30,root)||!wsMemoryString(filename,name)||name[0]=='\\'||name[0]=='/'||strchr(name,':'))return 0;
 for(const char*p=name;*p;p++)if(*p=='/'||(*p=='.'&&p[1]=='.'))return 0;
 int n=snprintf(combined,sizeof combined,"%s\\%s",root,name);DWORD k=GetFullPathNameA(root,MAX_PATH,fullRoot,NULL),m=GetFullPathNameA(combined,MAX_PATH,out,NULL);
 if(n<0||n>=MAX_PATH||!k||k>=MAX_PATH||!m||m>=MAX_PATH)return 0;while(k&&fullRoot[k-1]=='\\')fullRoot[--k]=0;
 return m>k+1u&&!_strnicmp(out,fullRoot,k)&&out[k]=='\\'&&wsMemorySafeParents(out);
}
#ifndef WS_MEMORY_NATIVE_SAVE
#define WS_MEMORY_NATIVE_SAVE(module) ((uintptr_t(*)(void*,const char*,const char*,unsigned char))((unsigned char*)(module)+0x75b90))
#endif
#ifndef WS_MEMORY_REPLACE_FILE
#define WS_MEMORY_REPLACE_FILE(path,temp) ReplaceFileA((path),(temp),NULL,REPLACEFILE_WRITE_THROUGH,NULL,NULL)
#endif
#ifndef WS_MEMORY_WRITE_FILE
#define WS_MEMORY_WRITE_FILE WriteFile
#endif
#ifndef WS_MEMORY_COPY_FILE
#define WS_MEMORY_COPY_FILE CopyFileA
#endif
#ifndef WS_MEMORY_REPORT_FAILURE
#define WS_MEMORY_REPORT_FAILURE(message) MessageBoxA(GetActiveWindow(),(message),"Anno 1503 - Exploration memory",MB_OK|MB_ICONERROR)
#endif
static int wsMemoryUniqueName(const char*path,const char*kind,char out[MAX_PATH]){
 unsigned char random[8];if(BCryptGenRandom(NULL,random,sizeof random,BCRYPT_USE_SYSTEM_PREFERRED_RNG)<0)return 0;unsigned long long nonce=0;memcpy(&nonce,random,8);
 int n=snprintf(out,MAX_PATH,"%s.wschart-%s-%lu-%lu-%016llx",path,kind,(unsigned long)GetCurrentProcessId(),(unsigned long)InterlockedIncrement(&wsMemoryFileSequence),nonce);return n>0&&n<MAX_PATH;
}
/* Native Save uses CREATE_ALWAYS. Preserve the complete PREVIOUS checkpoint,
 * including its chart, before that call can truncate it. Keep this separate
 * from the native-output backup made during the later atomic attachment. */
static int wsMemoryPreservePrevious(const char*path,BY_HANDLE_FILE_INFORMATION*before,int*hadBefore,char*error,uint32_t cap){
 unsigned char*previous=NULL,*copy=NULL;uint32_t previousSize=0;DWORD copied=0;BY_HANDLE_FILE_INFORMATION expected,proof,backupBefore;unsigned char originalHash[32],copyHash[32];
 char backup[MAX_PATH];HANDLE source=INVALID_HANDLE_VALUE,durable=INVALID_HANDLE_VALUE;int ok=0;
 *hadBefore=0;
 DWORD attributes=GetFileAttributesA(path),reason=GetLastError();
 if(attributes==INVALID_FILE_ATTRIBUTES&&(reason==ERROR_FILE_NOT_FOUND||reason==ERROR_PATH_NOT_FOUND))return 1;
 source=wsMemoryReadFile(path,&previous,&previousSize,&expected,error,cap);if(source==INVALID_HANDLE_VALUE)goto done;
 *before=expected;*hadBefore=1;
 if(!wsMemoryHash(previous,previousSize,originalHash)||!wsMemoryUniqueName(path,"checkpoint-backup",backup)||!WS_MEMORY_COPY_FILE(path,backup,TRUE))goto done;
 durable=CreateFileA(backup,GENERIC_READ|GENERIC_WRITE,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,NULL);
 if(!wsMemoryRegular(durable,&backupBefore)||backupBefore.nFileSizeHigh||backupBefore.nFileSizeLow!=previousSize)goto done;
 copy=(unsigned char*)malloc(previousSize);
 if(!copy||!ReadFile(durable,copy,previousSize,&copied,NULL)||copied!=previousSize||memcmp(previous,copy,previousSize)||!wsMemoryHash(copy,previousSize,copyHash)||memcmp(originalHash,copyHash,32)||!FlushFileBuffers(durable)||!wsMemoryRegular(durable,&proof)||!wsMemorySameFile(&backupBefore,&proof)||!wsMemoryRegular(source,&proof)||!wsMemorySameFile(&expected,&proof))goto done;
 ok=1;
 done:if(durable!=INVALID_HANDLE_VALUE)CloseHandle(durable);if(source!=INVALID_HANDLE_VALUE)CloseHandle(source);free(previous);free(copy);
 if(!ok)return wsMemoryError(error,cap,"The previous complete checkpoint could not be backed up before the native save. The native save still ran; the previous exploration history may lack a backup.");
 return 1;
}
static int wsMemoryCommit(const char*path,HANDLE nativeHandle,const BY_HANDLE_FILE_INFORMATION*expected,const unsigned char*native,uint32_t nativeSize,const unsigned char*augmented,uint32_t augmentedSize,char*error,uint32_t cap){
 char temporary[MAX_PATH],backup[MAX_PATH];HANDLE temp=INVALID_HANDLE_VALUE;DWORD written=0;BY_HANDLE_FILE_INFORMATION current;int ready=0;
 if(!wsMemoryUniqueName(path,"temp",temporary)||!wsMemoryUniqueName(path,"native-backup",backup))goto failed;
 temp=CreateFileA(temporary,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL|FILE_FLAG_OPEN_REPARSE_POINT,NULL);
 if(!wsMemoryRegular(temp,&current)||!WS_MEMORY_WRITE_FILE(temp,augmented,augmentedSize,&written,NULL)||written!=augmentedSize||!FlushFileBuffers(temp))goto failed;
 CloseHandle(temp);temp=INVALID_HANDLE_VALUE;
 if(!wsMemoryRegular(nativeHandle,&current)||!wsMemorySameFile(expected,&current)||!wsMemorySafeParents(path))goto failed;
 /* CopyFile(TRUE) creates an EXCLUSIVE immutable native backup. Passing NULL
  * to ReplaceFile's backup parameter prevents it ever clobbering an old backup. */
 if(!CopyFileA(path,backup,TRUE))goto failed;
 unsigned char*copy=NULL;uint32_t count=0;BY_HANDLE_FILE_INFORMATION proof;HANDLE check=wsMemoryReadFile(backup,&copy,&count,&proof,error,cap);
 ready=check!=INVALID_HANDLE_VALUE&&count==nativeSize&&!memcmp(copy,native,nativeSize);free(copy);if(check!=INVALID_HANDLE_VALUE)CloseHandle(check);
 if(!ready)goto failed;
 HANDLE durable=CreateFileA(backup,GENERIC_WRITE,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,NULL);
 ready=wsMemoryRegular(durable,&proof)&&FlushFileBuffers(durable);if(durable!=INVALID_HANDLE_VALUE)CloseHandle(durable);if(!ready)goto failed;
 CloseHandle(nativeHandle);nativeHandle=INVALID_HANDLE_VALUE;
 /* Recheck the exact source immediately before the synchronous replacement.
  * ReplaceFile is atomic by NAME, not a FileID compare-and-swap: these handles
  * must close first, leaving a bounded external-writer race before replacement.
  * This does not serialize unrelated programs; the certified backup retains
  * the guarded native bytes even if another writer changes the target name. */
 HANDLE verify=CreateFileA(path,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,NULL);
 ready=wsMemoryRegular(verify,&current)&&wsMemorySameFile(expected,&current);if(verify!=INVALID_HANDLE_VALUE)CloseHandle(verify);
 if(!ready||!wsMemorySafeParents(path)||!WS_MEMORY_REPLACE_FILE(path,temporary)){
  /* A rare partial Win32 replacement failure may leave the target absent.
   * Restore only into a missing name; never overwrite an unknown file. */
  DWORD attrs=GetFileAttributesA(path),reason=GetLastError();
  if(attrs==INVALID_FILE_ATTRIBUTES&&(reason==ERROR_FILE_NOT_FOUND||reason==ERROR_PATH_NOT_FOUND))CopyFileA(backup,path,TRUE);
  goto failed;
 }
 unsigned char*committed=NULL;uint32_t committedSize=0;HANDLE committedFile=wsMemoryReadFile(path,&committed,&committedSize,&proof,error,cap);
 ready=committedFile!=INVALID_HANDLE_VALUE&&committedSize==augmentedSize&&!memcmp(committed,augmented,augmentedSize);free(committed);if(committedFile!=INVALID_HANDLE_VALUE)CloseHandle(committedFile);if(!ready)goto failed;
 return 1;
 failed:if(temp!=INVALID_HANDLE_VALUE)CloseHandle(temp);if(nativeHandle!=INVALID_HANDLE_VALUE)CloseHandle(nativeHandle);
 return wsMemoryError(error,cap,"The native game save was kept, but exploration memory could not be committed. Existing backups were retained.");
}
__declspec(dllexport) uintptr_t WorldSettingsVisibilitySave(void*owner,const char*alias,const char*filename,unsigned char desync){
 unsigned char*frame=(unsigned char*)WS_CERT_MODULE("AnnoFrame.dll");uintptr_t result=0;
 if(!frame){wsMemoryError(wsMemoryIOError,sizeof wsMemoryIOError,"The native save module is unavailable.");return 0;}
 if(InterlockedCompareExchange(&wsMemorySaveBusy,1,0))return WS_MEMORY_NATIVE_SAVE(frame)(owner,alias,filename,desync);
 unsigned char*blob=NULL,*native=NULL,*augmented=NULL;uint32_t blobSize=0,nativeSize=0,augmentedSize=0;char path[MAX_PATH],error[512]={0},previousError[256]={0};
 BY_HANDLE_FILE_INFORMATION before={0},after={0};int hadBefore=0,want=0,snapshot=0;HANDLE file=INVALID_HANDLE_VALUE;WSVisibilityWorld world;unsigned char guid[16];
 void*worldObject=wsCertPointer(owner,0x10);wsMemoryIOError[0]=0;
 if(wsVisibilityWorldRead(worldObject,&world)&&world.marked>0){
  want=1;
  if(!wsMemorySavePath(owner,filename,path))wsMemoryError(error,sizeof error,"The native save path cannot be safely certified.");
  else{
   int certifiedPrevious=wsMemoryPreservePrevious(path,&before,&hadBefore,previousError,sizeof previousError);
   if(!certifiedPrevious&&!hadBefore)wsMemoryError(error,sizeof error,"The previous checkpoint's presence or identity could not be certified; exploration memory was not attached.");
   else if(!wsCertRead(world.world+0x6e4c,guid,16))wsMemoryError(error,sizeof error,"The current native world identifier is unavailable.");
   else{
    snapshot=WorldSettingsVisibilitySaveBlob(&blob,&blobSize,error,sizeof error);
    WSMemoryFile identity={0};identity.width=world.width;identity.height=world.height;identity.policy=world.flags&WS_VISIBILITY_POLICY_MASK;identity.viewer=world.viewer;memcpy(identity.guid,guid,16);
    if(snapshot&&!wsMemoryBlobIdentity(blob,blobSize,&identity)){snapshot=0;wsMemoryError(error,sizeof error,"The exploration snapshot belongs to a different native world.");}
   }
  }
 }
 result=WS_MEMORY_NATIVE_SAVE(frame)(owner,alias,filename,desync);
 if(want&&snapshot){
  file=wsMemoryReadFile(path,&native,&nativeSize,&after,error,sizeof error);
  if(file!=INVALID_HANDLE_VALUE){
   WSMemoryFile parsed;
   if(hadBefore&&wsMemorySameFile(&before,&after))wsMemoryError(error,sizeof error,"No newly completed native checkpoint was detected; exploration memory was not attached to the older save.");
   else if(wsMemoryParse(native,nativeSize,&parsed,error,sizeof error)&&parsed.full&&!parsed.chartSpan&&parsed.width==world.width&&parsed.height==world.height&&parsed.policy==(world.flags&WS_VISIBILITY_POLICY_MASK)&&!memcmp(parsed.guid,guid,16)&&wsMemoryAssemble(native,nativeSize,&parsed,blob,blobSize,&augmented,&augmentedSize,error,sizeof error)){
    HANDLE owned=file;file=INVALID_HANDLE_VALUE;if(wsMemoryCommit(path,owned,&after,native,nativeSize,augmented,augmentedSize,error,sizeof error))error[0]=0;
   }else if(!error[0])wsMemoryError(error,sizeof error,"The native save output does not match the captured exploration checkpoint.");
  }
 }
 if(file!=INVALID_HANDLE_VALUE)CloseHandle(file);free(blob);free(native);free(augmented);
 if(want&&(previousError[0]||!snapshot||error[0])){
  if(!snapshot&&!error[0])wsMemoryError(error,sizeof error,"The game save has no certified exploration snapshot.");
  snprintf(wsMemoryIOError,sizeof wsMemoryIOError,"%s%s%s",previousError,previousError[0]&&error[0]?"\r\n\r\n":"",error);WS_MEMORY_REPORT_FAILURE(wsMemoryIOError);
 }
 InterlockedExchange(&wsMemorySaveBusy,0);return result;
}
typedef struct WSMemoryPendingLoad {HANDLE file;unsigned char*data;uint32_t size;BY_HANDLE_FILE_INFORMATION info;WSMemoryFile parsed;} WSMemoryPendingLoad;
static _Thread_local WSMemoryPendingLoad wsMemoryLoad;
__declspec(dllexport) void WorldSettingsVisibilityCancelLoad(void){
 if(wsMemoryLoad.file&&wsMemoryLoad.file!=INVALID_HANDLE_VALUE)CloseHandle(wsMemoryLoad.file);free(wsMemoryLoad.data);memset(&wsMemoryLoad,0,sizeof wsMemoryLoad);WorldSettingsVisibilityCancelBlob();
}
__declspec(dllexport) int WorldSettingsVisibilityBeforeLoad(const char*path,char*error,uint32_t cap){
 WorldSettingsVisibilityCancelLoad();if(!path||!path[0])return 1;
 WSMemoryPendingLoad pending={0};pending.file=wsMemoryReadFile(path,&pending.data,&pending.size,&pending.info,error,cap);if(pending.file==INVALID_HANDLE_VALUE)return 0;
 if(!wsMemoryExactTag(pending.data,"ANNOADDON1")){CloseHandle(pending.file);free(pending.data);return 1;}
 if(!wsMemoryParse(pending.data,pending.size,&pending.parsed,error,cap))goto failed;
 if(!pending.parsed.full||(!pending.parsed.policy&&!pending.parsed.chartSpan)){CloseHandle(pending.file);free(pending.data);return 1;}
 if(!WorldSettingsVisibilityStageBlob(pending.parsed.chartSpan?pending.parsed.blob:NULL,pending.parsed.chartSpan?pending.parsed.blobSize:0u,error,cap))goto failed;
 wsMemoryLoad=pending;return 1;
 failed:CloseHandle(pending.file);free(pending.data);WorldSettingsVisibilityCancelBlob();return 0;
}
__declspec(dllexport) int WorldSettingsVisibilityAfterLoad(void*scene,char*error,uint32_t cap){
 if(!wsMemoryLoad.data)return 1;int ok=0;BY_HANDLE_FILE_INFORMATION after;WSVisibilityWorld v;unsigned char guid[16];WSMemoryFile*f=&wsMemoryLoad.parsed;
 if(!wsMemoryRegular(wsMemoryLoad.file,&after)||!wsMemorySameFile(&wsMemoryLoad.info,&after)||!wsVisibilityWorldRead(wsCertPointer(scene,0x160),&v)||!wsCertRead(v.world+0x6e4c,guid,16)||v.width!=f->width||v.height!=f->height||(v.flags&WS_VISIBILITY_POLICY_MASK)!=f->policy||memcmp(guid,f->guid,16))wsMemoryError(error,cap,"The loaded native world does not match its certified exploration checkpoint.");
 else if(!v.marked)ok=1;
 else ok=WorldSettingsVisibilityApplyBlob(v.world,error,cap);
 WorldSettingsVisibilityCancelLoad();return ok;
}
__declspec(dllexport) int WorldSettingsVisibilityReleaseUnpublishedScene(void*scene){
 unsigned char*module=(unsigned char*)WS_CERT_MODULE("AnnoScene.dll");void*vt=wsCertPointer(scene,0);
 if(!module||!scene||!wsCertMemory(scene,0x168,0)||!vt)return 0;
 uintptr_t destructor=vt==module+0x35498?0x1080u:vt==module+0x36108?0xa480u:vt==module+0x3f648?0xb560u:0u;
 if(!destructor||wsCertPointer(vt,0)!=(void*)(module+destructor)||wsCertPointer(vt,0x18)!=(void*)(module+0x1b60))return 0;
 ((void(*)(void*))(module+0x1b60))(scene);return 1;
}
__declspec(dllexport) uint32_t WorldSettingsCopyMemoryError(void*buffer){
 if(!buffer)return 0;uint32_t n=0;while(n<sizeof wsMemoryIOError-1u&&wsMemoryIOError[n])n++;memcpy(buffer,wsMemoryIOError,n);((char*)buffer)[n]=0;return n+1u;
}

/* Exact HE Frame 76B50 file-load boundary only.
 * Scene+A8 is signed-32-bit HRESULT: Frame tests EAX then JS at 76B56/76B58.
 * All three certified Scene vtables use native A8 target 3AC0. That adapter
 * writes arg5 to Scene+178 and arg4 to Scene+160, then tail-dispatches B0.
 * The separate Scene+B8 stream-loading branch is deliberately untouched. */
typedef int32_t (*WSMemoryNativeLoadA8)(void*,const char*,uint32_t,void*,unsigned char);
static _Thread_local int wsMemoryInGameLoadBusy;
__declspec(dllexport) int32_t WorldSettingsVisibilityLoadFileA8(
 void*scene,const char*filename,uint32_t index,void*world,unsigned char flag){
 const int32_t failure=(int32_t)0x80004005u;
 char error[512]={0},captured[MAX_PATH];
 unsigned char*module=(unsigned char*)WS_CERT_MODULE("AnnoScene.dll");
 void*vt=wsCertPointer(scene,0),*target=NULL;
 /* An outer certified factory/file load owns its staged checkpoint. Never
  * cancel that owner or stage another checkpoint on recursive entry. */
 if(wsMemoryInGameLoadBusy||wsMemoryLoad.data||wsMemoryLoad.file){
  wsMemoryError(error,sizeof error,"A native exploration load is already pending.");goto refused;
 }
 if(!module||!scene||!wsCertMemory(scene,0x180,0)||
    (vt!=module+0x35498&&vt!=module+0x36108&&vt!=module+0x3f648)||
    (target=wsCertPointer(vt,0xa8))!=(void*)(module+0x3ac0)||
    !wsCertMemory(target,0x1c,1)){
  wsMemoryError(error,sizeof error,"The native in-game file-load boundary differs.");goto refused;
 }
 if(!wsMemoryString(filename,captured)){
  wsMemoryError(error,sizeof error,"The native load filename is invalid or too long.");goto refused;
 }
 wsMemoryInGameLoadBusy=1;
 if(!WorldSettingsVisibilityBeforeLoad(captured,error,sizeof error))goto failed;
 int32_t loaded=((WSMemoryNativeLoadA8)target)(scene,captured,index,world,flag);
 if(loaded<0){WorldSettingsVisibilityCancelLoad();wsMemoryInGameLoadBusy=0;return loaded;}
 if(!WorldSettingsVisibilityAfterLoad(scene,error,sizeof error))goto failed;
 wsMemoryInGameLoadBusy=0;return loaded;
 failed:WorldSettingsVisibilityCancelLoad();wsMemoryInGameLoadBusy=0;
 refused:
 snprintf(wsMemoryIOError,sizeof wsMemoryIOError,"%s",error[0]?error:"The exploration checkpoint could not be loaded.");
 WS_MEMORY_REPORT_FAILURE(wsMemoryIOError);return failure;
}
