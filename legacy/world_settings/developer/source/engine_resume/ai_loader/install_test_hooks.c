/* Transient, explicitly invoked test hooks for the fingerprinted AMD64 game.
 * No DllMain work, remote process operations, disk writes or launcher changes.
 * Successful allocations/unwind tables live until this process exits.
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <tlhelp32.h>
#include <bcrypt.h>
#include <stdint.h>
#include <limits.h>
#include <string.h>
#ifndef WS_RUNTIME_BLOBS_HEADER
#define WS_RUNTIME_BLOBS_HEADER "../../runtime_test_blobs.h"
#endif
#include WS_RUNTIME_BLOBS_HEADER
#include "ai_loader.h"
#include "engine_patch_plan.h"

#define WS_BLOB_COUNT (sizeof(wsBlobs)/sizeof(wsBlobs[0]))
#define WS_MAX_HOOKS (16+WS_ENGINE_PATCH_COUNT)
#define WS_MAX_PATCH 32
#define WS_MAX_THREADS 512
#define WS_NEAR_LIMIT 0x70000000u
typedef struct {
 HMODULE module; uint32_t imageSize; unsigned char *allocation;
 SIZE_T allocationSize; PRUNTIME_FUNCTION functions; int registered;
} WSInstalledBlob;
typedef struct {
 unsigned char *address; uint32_t length; unsigned char before[WS_MAX_PATCH],after[WS_MAX_PATCH];
 uint32_t page; int written;
} WSPatch;
typedef struct {unsigned char *address;SIZE_T length;DWORD protection;int writable;} WSPage;
typedef struct {HANDLE handle;int suspended;} WSThread;
static WSInstalledBlob wsInstalled[WS_BLOB_COUNT];
static SRWLOCK wsInstallLock=SRWLOCK_INIT;
static int wsInstallState;
static HMODULE wsEngineModule;
static HMODULE wsEngineModules[WS_ENGINE_MODULE_COUNT];
static char wsInstallError[512];
__declspec(dllexport) int WorldSettingsInstallTestHooks(void);
/* This readiness proof is separate from the nine menu/factory/AI hooks. It
 * checks all committed engine bytes again before the menu can start a world. */
__declspec(dllexport) DWORD WorldSettingsEnginePatchStatus(void){
 DWORD result=0;AcquireSRWLockShared(&wsInstallLock);
 if(wsInstallState==1){
  if(wsEngineModules[WS_ENGINE_MODULE_WORLD]&&wsEngineModules[WS_ENGINE_MODULE_FRAME]){result=WS_ENGINE_PATCH_COUNT;
   for(uint32_t i=0;i<WS_ENGINE_PATCH_COUNT;i++){
    const WSEngineEdit *edit=&wsEngineEdits[i];
    if(edit->module>=WS_ENGINE_MODULE_COUNT){result=0;break;}
    unsigned char *base=(unsigned char*)wsEngineModules[edit->module];
    if(!base){result=0;break;}
    if(memcmp(base+edit->rva,edit->after,edit->length)){result=0;break;}
   }
  }
 }
 ReleaseSRWLockShared(&wsInstallLock);return result;
}
__declspec(dllexport) const char *WorldSettingsTestHooksError(void){return wsInstallError;}
/* The explicit test loader supplies a writable 512-byte buffer in this process.
 * The DWORD return is the byte count including NUL, never a truncated pointer. */
__declspec(dllexport) DWORD WorldSettingsCopyTestHooksError(void *buffer){
 if(!buffer)return 0;
 AcquireSRWLockShared(&wsInstallLock);
 unsigned char *out=(unsigned char*)buffer;DWORD n=0;
 do{out[n]=(unsigned char)wsInstallError[n];n++;}while(n<sizeof wsInstallError&&wsInstallError[n-1]);
 out[n-1]=0;
 ReleaseSRWLockShared(&wsInstallLock);return n;
}
/* Error recording also runs in the suspended-thread phase: no CRT formatting,
 * heap allocation or locale locks are used here. */
static int wsError(const char *message){SIZE_T i=0;for(;message[i]&&i+1<sizeof wsInstallError;i++)wsInstallError[i]=message[i];wsInstallError[i]=0;return 0;}
static int wsWinError(const char *message){
 DWORD error=GetLastError();char digits[11];SIZE_T n=0,at=0;
 wsError(message);while(wsInstallError[at])at++;
 const char *prefix=" (Windows error ";
 for(SIZE_T i=0;prefix[i]&&at+1<sizeof wsInstallError;i++)wsInstallError[at++]=prefix[i];
 do{digits[n++]=(char)('0'+error%10);error/=10;}while(error&&n<sizeof digits);
 while(n&&at+1<sizeof wsInstallError)wsInstallError[at++]=digits[--n];
 if(at+2<sizeof wsInstallError){wsInstallError[at++]=')';wsInstallError[at++]='.';}wsInstallError[at]=0;return 0;
}
static SIZE_T wsAlign(SIZE_T n,SIZE_T alignment){return (n+alignment-1)&~(alignment-1);}
static int wsSpan(uint32_t offset,uint32_t length,uint32_t size){return offset<=size&&length<=size-offset;}
static int wsReadable(const void *pointer,SIZE_T length){
 uintptr_t at=(uintptr_t)pointer;
 if(!at||length>UINTPTR_MAX-at)return 0;
 uintptr_t end=at+length;
 while(at<end){MEMORY_BASIC_INFORMATION m;
  if(!VirtualQuery((void*)at,&m,sizeof m)||m.State!=MEM_COMMIT||(m.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return 0;
  uintptr_t next=(uintptr_t)m.BaseAddress+m.RegionSize;if(next<=at)return 0;at=next<end?next:end;
 }return 1;
}
/* Exact HE World lifetime guard. Include after windows.h and stdint.h.
 * No allocation, CRT, heap walking or game function calls are used.
 * Call once during preparation and again with all other threads paused.
 * Return 0: no World observed; 1: existing World found; -1: incomplete scan.
 * Separately reject any paused RIP in Welt+[21c0,2690), [d1de0,d220b),
 * [d1c60,d1dd4), [e2b80,e2c61) to exclude construction/destruction races.
 * This must run before committing any allocation/grid edits.
 */
static int wsEngineExistingWorld(HMODULE welt, uintptr_t *foundWorld) {
    SYSTEM_INFO info;
    MEMORY_BASIC_INFORMATION region;
    HANDLE process = GetCurrentProcess();
    uintptr_t cursor, last;
    const uintptr_t serverVtable = (uintptr_t)welt + 0xff650u;
    const uintptr_t baseVtable = (uintptr_t)welt + 0xff1d8u;
    union { uint64_t align; unsigned char bytes[65536]; } scratch;
    if (foundWorld) *foundWorld = 0;
    if (!welt) return -1;
    GetSystemInfo(&info);
    cursor = (uintptr_t)info.lpMinimumApplicationAddress;
    last = (uintptr_t)info.lpMaximumApplicationAddress;
    while (cursor < last) {
        uintptr_t start, end, part;
        DWORD protection;
        if (!VirtualQuery((LPCVOID)cursor, &region, sizeof(region))) return -1;
        start = (uintptr_t)region.BaseAddress;
        if (region.RegionSize > last - start) end = last;
        else end = start + region.RegionSize;
        if (end <= cursor) return -1;
        protection = region.Protect & 0xffu;
        if (region.State == MEM_COMMIT && region.Type == MEM_PRIVATE &&
            !(region.Protect & (PAGE_GUARD | PAGE_NOACCESS)) &&
            (protection == PAGE_READWRITE || protection == PAGE_WRITECOPY ||
             protection == PAGE_EXECUTE_READWRITE || protection == PAGE_EXECUTE_WRITECOPY)) {
            for (part = start; part < end;) {
                SIZE_T amount = (SIZE_T)(end - part), got = 0, offset;
                if (amount > sizeof(scratch.bytes)) amount = sizeof(scratch.bytes);
                if (!ReadProcessMemory(process, (LPCVOID)part, scratch.bytes, amount, &got) || got != amount) return -1;
                for (offset = 0; offset + sizeof(uintptr_t) <= amount; offset += sizeof(uintptr_t)) {
                    uintptr_t candidate, vtable = *(const uintptr_t *)(scratch.bytes + offset);
                    struct { uintptr_t self; uint32_t unknown; uint32_t pad; uint32_t width; uint32_t height; } fields;
                    SIZE_T fieldBytes = 0;
                    if (vtable != serverVtable && vtable != baseVtable) continue;
                    candidate = part + offset;
                    if (candidate > last - 0x1e0u) continue;
                    /* +1c8 QWORD self; +1d0 DWORD state/padding; +1d8,+1dc sizes. */
                    if (!ReadProcessMemory(process, (LPCVOID)(candidate + 0x1c8u), &fields, sizeof(fields), &fieldBytes) || fieldBytes != sizeof(fields)) return -1;
                    if (fields.self != candidate) continue;
                    if ((fields.width == 0 && fields.height == 0) ||
                        (fields.width >= 8 && fields.height >= 8 &&
                         fields.width <= 65535u && fields.height <= 65535u &&
                         !(fields.width & 7u) && !(fields.height & 7u))) {
                        if (foundWorld) *foundWorld = candidate;
                        return 1;
                    }
                }
                part += amount;
            }
        }
        cursor = end;
    }
    return 0;
}

static int wsHashModule(HMODULE module,const unsigned char expected[32]){
 wchar_t path[32768];DWORD n=GetModuleFileNameW(module,path,32768);
 if(!n||n>=32768)return wsWinError("Cannot identify the loaded native module file");
 HANDLE file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
 if(file==INVALID_HANDLE_VALUE)return wsWinError("Cannot read the loaded native module file");
 BCRYPT_ALG_HANDLE algorithm=NULL;BCRYPT_HASH_HANDLE hash=NULL;
 unsigned char buffer[32768],digest[32];DWORD got=0;int ok=0;
 if(BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,NULL,0)<0||BCryptCreateHash(algorithm,&hash,NULL,0,NULL,0,0)<0){wsError("Cannot initialize native module SHA256 verification.");goto done;}
 do{if(!ReadFile(file,buffer,sizeof buffer,&got,NULL)){wsWinError("Cannot read the loaded native module file");goto done;}
  if(got&&BCryptHashData(hash,buffer,got,0)<0){wsError("Cannot hash the loaded native module file.");goto done;}
 }while(got);
 if(BCryptFinishHash(hash,digest,sizeof digest,0)<0){wsError("Cannot finish native module SHA256 verification.");goto done;}
 if(memcmp(digest,expected,32)){wsError("A loaded native file differs from its inspected History Edition fingerprint.");goto done;}
 ok=1;
 done:if(hash)BCryptDestroyHash(hash);if(algorithm)BCryptCloseAlgorithmProvider(algorithm,0);CloseHandle(file);return ok;
}
static int wsModuleImage(HMODULE module,uint32_t *size){
 unsigned char *base=(unsigned char*)module;
 if(!wsReadable(base,sizeof(IMAGE_DOS_HEADER)))return wsError("Loaded native module has no readable PE header.");
 const IMAGE_DOS_HEADER *dos=(const IMAGE_DOS_HEADER*)base;
 if(dos->e_magic!=IMAGE_DOS_SIGNATURE||dos->e_lfanew<0||(uint32_t)dos->e_lfanew>0x100000u||!wsReadable(base+dos->e_lfanew,sizeof(IMAGE_NT_HEADERS64)))return wsError("Loaded native module has an unsupported PE envelope.");
 const IMAGE_NT_HEADERS64 *nt=(const IMAGE_NT_HEADERS64*)(base+dos->e_lfanew);
 if(sizeof(void*)!=8||nt->Signature!=IMAGE_NT_SIGNATURE||nt->FileHeader.Machine!=IMAGE_FILE_MACHINE_AMD64||nt->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR64_MAGIC||nt->FileHeader.SizeOfOptionalHeader<sizeof(IMAGE_OPTIONAL_HEADER64)||nt->OptionalHeader.NumberOfRvaAndSizes<=IMAGE_DIRECTORY_ENTRY_EXCEPTION||nt->OptionalHeader.SizeOfImage<0x1000u)return wsError("Transient hooks require the inspected AMD64 PE32+ modules.");
 *size=nt->OptionalHeader.SizeOfImage;return 1;
}
static int wsOriginalFunction(WSInstalledBlob *installed,const unsigned char *bytes){
 unsigned char *base=(unsigned char*)installed->module;
 const IMAGE_DOS_HEADER *dos=(const IMAGE_DOS_HEADER*)base;
 const IMAGE_NT_HEADERS64 *nt=(const IMAGE_NT_HEADERS64*)(base+dos->e_lfanew);
 const IMAGE_DATA_DIRECTORY *directory=&nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_EXCEPTION];
 if(!directory->Size||directory->Size%sizeof(RUNTIME_FUNCTION)||!wsSpan(directory->VirtualAddress,directory->Size,installed->imageSize)||!wsReadable(base+directory->VirtualAddress,directory->Size))return 0;
 for(uint32_t at=0;at<directory->Size;at+=(uint32_t)sizeof(RUNTIME_FUNCTION))if(!memcmp(base+directory->VirtualAddress+at,bytes,sizeof(RUNTIME_FUNCTION)))return 1;
 return 0;
}
static int wsUnwind(WSInstalledBlob *installed,const WSFunctionMeta *function){
 if(!function->unwind||function->unwindSize<4||(function->unwind[0]&7)!=1)return wsError("Generated function unwind version is unsupported.");
 uint32_t flags=function->unwind[0]>>3;
 uint32_t ordinary=(uint32_t)wsAlign(4u+2u*function->unwind[2],4);
 if((flags!=0&&flags!=4)||function->unwindSize!=ordinary+(flags==4?12u:0u))return wsError("Generated function unwind layout is unsupported.");
 if(flags==4&&!wsOriginalFunction(installed,function->unwind+ordinary))return wsError("Chained unwind parent is absent from the original module function table.");
 return 1;
}
static void *wsAllocateNear(HMODULE module,uint32_t imageSize,SIZE_T size){
 SYSTEM_INFO system;GetSystemInfo(&system);uintptr_t base=(uintptr_t)module;
 SIZE_T granularity=system.dwAllocationGranularity;
 uintptr_t at=wsAlign(base+imageSize,granularity);
 if(base>UINTPTR_MAX-WS_NEAR_LIMIT)return NULL;
 uintptr_t limit=base+WS_NEAR_LIMIT;
 while(at<limit&&size<=limit-at){MEMORY_BASIC_INFORMATION m;
  if(!VirtualQuery((void*)at,&m,sizeof m))return NULL;
  uintptr_t next=(uintptr_t)m.BaseAddress+m.RegionSize;if(next<=at)return NULL;
  if(m.State==MEM_FREE){uintptr_t candidate=wsAlign(at,granularity);
   if(candidate<next&&size<=next-candidate&&size<=limit-candidate){void *memory=VirtualAlloc((void*)candidate,size,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);if(memory)return memory;}
  }
  at=wsAlign(next,granularity);
 }return NULL;
}
static int wsPrepareBlob(uint32_t index,HMODULE self,WSPatch *patches,uint32_t *patchCount){
 const WSBlob *blob=&wsBlobs[index];WSInstalledBlob *installed=&wsInstalled[index];
 installed->module=GetModuleHandleW(blob->module);
 if(!installed->module)return wsError("The inspected native modules must already be loaded by the normally launched game.");
 if(!wsModuleImage(installed->module,&installed->imageSize)||!wsHashModule(installed->module,blob->sha256))return 0;
 if(!blob->code||!blob->codeSize||blob->codeSize>0x100000u||!blob->functionCount||blob->functionCount>32||blob->hookCount>WS_MAX_HOOKS-*patchCount)return wsError("Generated native hook metadata exceeds its bounds.");
 SIZE_T total=wsAlign(blob->codeSize,4);
 for(uint32_t i=0;i<blob->functionCount;i++){
  const WSFunctionMeta *function=&blob->functions[i];
  if(function->begin>=function->end||function->end>blob->codeSize||(i&&blob->functions[i-1].end>function->begin)||!wsUnwind(installed,function))return wsError("Generated function range or exact unwind metadata is invalid.");
  if(function->unwindSize>256)return wsError("Generated unwind record is too large.");
  total+=wsAlign(function->unwindSize,4);
 }
 SIZE_T tableOffset=total;total+=blob->functionCount*sizeof(RUNTIME_FUNCTION);
 installed->allocationSize=total;
 installed->allocation=(unsigned char*)wsAllocateNear(installed->module,installed->imageSize,total);
 if(!installed->allocation)return wsWinError("No suitable positive native-relative executable allocation is available");
 uintptr_t allocationRva=(uintptr_t)installed->allocation-(uintptr_t)installed->module;
 if(!allocationRva||allocationRva>WS_NEAR_LIMIT||total>WS_NEAR_LIMIT-allocationRva)return wsError("Allocated hook code is outside its permitted native-relative range.");
 memcpy(installed->allocation,blob->code,blob->codeSize);
 for(uint32_t i=0;i<blob->relocCount;i++){
  uint32_t at=blob->relocs[i].offset;
  if(!wsSpan(at,4,blob->codeSize))return wsError("Generated native-relative relocation is outside its code blob.");
  int32_t old;memcpy(&old,blob->code+at,4);
  int64_t target=(int64_t)at+4+old;
  int64_t displacement=(int64_t)old-(int64_t)allocationRva;
  if(target<0||target>=installed->imageSize||displacement<INT32_MIN||displacement>INT32_MAX)return wsError("Generated native-relative relocation cannot reach its inspected native target.");
  int32_t value=(int32_t)displacement;memcpy(installed->allocation+at,&value,4);
 }
 for(uint32_t i=0;i<blob->importCount;i++){
  const WSImportCell *cell=&blob->imports[i];
  if(!wsSpan(cell->offset,8,blob->codeSize)||!cell->name||!cell->name[0])return wsError("Generated hook import cell is invalid.");
  FARPROC function=GetProcAddress(self,cell->name);
  if(!function)return wsError("The copied World Settings DLL lacks a required hook export.");
  uintptr_t value=(uintptr_t)function;memcpy(installed->allocation+cell->offset,&value,8);
 }
 SIZE_T cursor=wsAlign(blob->codeSize,4);
 installed->functions=(PRUNTIME_FUNCTION)(installed->allocation+tableOffset);
 for(uint32_t i=0;i<blob->functionCount;i++){
  const WSFunctionMeta *function=&blob->functions[i];
  memcpy(installed->allocation+cursor,function->unwind,function->unwindSize);
  installed->functions[i].BeginAddress=(DWORD)(allocationRva+function->begin);
  installed->functions[i].EndAddress=(DWORD)(allocationRva+function->end);
  installed->functions[i].UnwindData=(DWORD)(allocationRva+cursor);
  cursor+=wsAlign(function->unwindSize,4);
 }
 for(uint32_t i=0;i<blob->hookCount;i++){
  const WSHook *hook=&blob->hooks[i];
  if(hook->length<5||hook->length>WS_MAX_PATCH||!hook->before||!wsSpan(hook->rva,hook->length,installed->imageSize)||hook->target>=blob->codeSize||(hook->call!=0&&hook->call!=1))return wsError("Generated hook patch range is invalid.");
  WSPatch *patch=&patches[(*patchCount)++];patch->address=(unsigned char*)installed->module+hook->rva;patch->length=hook->length;
  if(!wsReadable(patch->address,patch->length)||memcmp(patch->address,hook->before,patch->length))return wsError("A loaded Frame/Scene hook preimage differs; no hooks were installed.");
  memcpy(patch->before,hook->before,patch->length);memset(patch->after,0x90,patch->length);patch->after[0]=(unsigned char)(hook->call?0xe8:0xe9);
  int64_t displacement=(int64_t)(uintptr_t)(installed->allocation+hook->target)-(int64_t)(uintptr_t)(patch->address+5);
  if(displacement<INT32_MIN||displacement>INT32_MAX)return wsError("Generated native call/jump cannot reach its copied hook code.");
  int32_t value=(int32_t)displacement;memcpy(patch->after+1,&value,4);
 }
 DWORD previous;
 if(!VirtualProtect(installed->allocation,total,PAGE_EXECUTE_READ,&previous)||!FlushInstructionCache(GetCurrentProcess(),installed->allocation,total))return wsWinError("Cannot finalize copied hook code protection/cache");
 if(!RtlAddFunctionTable(installed->functions,blob->functionCount,(DWORD64)(uintptr_t)installed->module))return wsError("Windows rejected the generated exact native unwind table.");
 installed->registered=1;return 1;
}
static int wsPrepareEngine(WSPatch *patches,uint32_t *patchCount){
 uint32_t imageSizes[WS_ENGINE_MODULE_COUNT];
 wsEngineModules[WS_ENGINE_MODULE_WORLD]=GetModuleHandleW(L"AnnoWelt.dll");
 wsEngineModules[WS_ENGINE_MODULE_FRAME]=GetModuleHandleW(L"AnnoFrame.dll");
 /* Both source modules have already passed wsPrepareBlob's exact file hash
  * and AMD64 checks. Engine edits join those hooks in the same transaction. */
 for(uint32_t i=0;i<WS_ENGINE_MODULE_COUNT;i++)
  if(!wsEngineModules[i]||!wsModuleImage(wsEngineModules[i],&imageSizes[i]))return wsError("An inspected world or drawing engine module is unavailable.");
 wsEngineModule=wsEngineModules[WS_ENGINE_MODULE_WORLD];
 if(WS_ENGINE_PATCH_COUNT>WS_MAX_HOOKS-*patchCount)return wsError("Expanded engine patch metadata exceeds transaction bounds.");
 for(uint32_t i=0;i<WS_ENGINE_PATCH_COUNT;i++){
  const WSEngineEdit *edit=&wsEngineEdits[i];
  if(edit->module>=WS_ENGINE_MODULE_COUNT||!edit->length||edit->length>WS_MAX_PATCH||!wsSpan(edit->rva,edit->length,imageSizes[edit->module]))return wsError("Expanded engine edit has an invalid inspected module or range.");
  WSPatch *patch=&patches[(*patchCount)++];
  patch->address=(unsigned char*)wsEngineModules[edit->module]+edit->rva;patch->length=edit->length;
  if(!wsReadable(patch->address,patch->length)||memcmp(patch->address,edit->before,patch->length))return wsError("An expanded engine instruction differs from its inspected preimage; no changes were committed.");
  memcpy(patch->before,edit->before,patch->length);memcpy(patch->after,edit->after,patch->length);
 }
 return 1;
}
/* A thread inside CRT/another module can still be constructing a World.
 * Conservatively reject return addresses in the complete native lifetime
 * ranges as well as RIP itself. Stale stack values may require a fresh launch;
 * they must never turn an uncertain construction into a smaller allocation. */
static int wsWorldLifetimeAddress(uintptr_t address){
 uintptr_t base=(uintptr_t)wsEngineModule;
 if(!base||address<base)return 0;
 uintptr_t rva=address-base;
 return (rva>=0x21c0u&&rva<0x2690u)||(rva>=0xd1de0u&&rva<0xd220bu)||
        (rva>=0xd1c60u&&rva<0xd1dd4u)||(rva>=0xe2b80u&&rva<0xe2c61u);
}
static int wsWorldLifetimeStack(const CONTEXT *context){
 MEMORY_BASIC_INFORMATION m;uintptr_t start=(uintptr_t)context->Rsp,end;
 if(wsWorldLifetimeAddress((uintptr_t)context->Rip))return 1;
 if(!start||!VirtualQuery((void*)start,&m,sizeof m)||m.State!=MEM_COMMIT||
    (m.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return -1;
 if(m.RegionSize>UINTPTR_MAX-(uintptr_t)m.BaseAddress)return -1;
 end=(uintptr_t)m.BaseAddress+m.RegionSize;
 if(end<start||end-start>0x1000000u||!wsReadable((void*)start,end-start))return -1;
 start=(start+7u)&~(uintptr_t)7u;
 for(;start<=end-sizeof(uintptr_t);start+=sizeof(uintptr_t))
  if(wsWorldLifetimeAddress(*(const uintptr_t*)start))return 1;
 return 0;
}
static int wsEngineWorldAbsent(void){
 uintptr_t found=0;int state=wsEngineExistingWorld(wsEngineModule,&found);
 if(state>0)return wsError("A native world already exists. Close and relaunch Anno, then activate from its first main menu before loading a world.");
 if(state<0)return wsError("The native world lifetime scan was incomplete; no engine edits were committed. Close and relaunch Anno before retrying.");
 return 1;
}
static void wsResumeThreads(WSThread *threads,uint32_t count){
 for(uint32_t i=count;i>0;i--){WSThread *thread=&threads[i-1];if(thread->suspended)ResumeThread(thread->handle);if(thread->handle)CloseHandle(thread->handle);}
}
static int wsSuspendThreads(WSThread *threads,uint32_t *count,WSPatch *patches,uint32_t patchCount){
 HANDLE snapshot=CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD,0);
 if(snapshot==INVALID_HANDLE_VALUE)return wsWinError("Cannot enumerate game threads for an atomic hook commit");
 THREADENTRY32 entry;memset(&entry,0,sizeof entry);entry.dwSize=sizeof entry;
 DWORD current=GetCurrentThreadId(),process=GetCurrentProcessId();int ok=1;
 if(!Thread32First(snapshot,&entry)){CloseHandle(snapshot);return wsWinError("Cannot inspect game threads for a hook commit");}
 do{if(entry.th32OwnerProcessID!=process||entry.th32ThreadID==current)continue;
  if(*count>=WS_MAX_THREADS){wsError("Too many game threads for the bounded hook transaction.");ok=0;break;}
  HANDLE thread=OpenThread(THREAD_SUSPEND_RESUME|THREAD_GET_CONTEXT|THREAD_QUERY_INFORMATION,FALSE,entry.th32ThreadID);
  if(!thread){if(GetLastError()==ERROR_INVALID_PARAMETER)continue;wsWinError("Cannot open a game thread for the hook transaction");ok=0;break;}
  threads[(*count)++].handle=thread;
 }while(Thread32Next(snapshot,&entry));
 /* A failed Next call is complete only for ERROR_NO_MORE_FILES. Capture its
  * error before CloseHandle can overwrite it; a partial snapshot must never
  * reach the suspension/patch phase with uncollected game threads running. */
 DWORD enumerationError=GetLastError();
 if(ok&&enumerationError!=ERROR_NO_MORE_FILES){
  SetLastError(enumerationError);wsWinError("Incomplete game thread snapshot; no hooks were installed");ok=0;
 }
 CloseHandle(snapshot);if(!ok)return 0;
 /* All handles and all code are prepared before any thread is suspended. */
 for(uint32_t i=0;i<*count;i++){
  WSThread *thread=&threads[i];DWORD previous=SuspendThread(thread->handle);
  if(previous==(DWORD)-1){DWORD status;if(GetExitCodeThread(thread->handle,&status)&&status!=STILL_ACTIVE)continue;return wsWinError("Cannot suspend a game thread for the hook transaction");}
  thread->suspended=1;CONTEXT context;memset(&context,0,sizeof context);context.ContextFlags=CONTEXT_CONTROL;
  if(!GetThreadContext(thread->handle,&context))return wsWinError("Cannot inspect a suspended game thread");
  if(wsWorldLifetimeStack(&context)!=0)return wsError("A game thread may be constructing or destroying a world. Retry only from a fresh idle main menu.");
  for(uint32_t p=0;p<patchCount;p++)if(context.Rip>=(uintptr_t)patches[p].address&&context.Rip<(uintptr_t)patches[p].address+patches[p].length)return wsError("A native thread is executing a hook site; retry from the idle game menu.");
 }return 1;
}
static int wsRestorePatches(WSPatch *patches,uint32_t count,WSPage *pages,uint32_t pageCount){
 int ok=1;
 /* Restore bytes while every affected protection page is writable, then
  * restore each original page protection exactly once. Multiple hooks may
  * occupy one page; no intermediate RX change may strand another rollback. */
 for(uint32_t i=0;i<pageCount;i++){
  WSPage *page=&pages[i];int needed=page->writable;
  for(uint32_t p=0;p<count&&!needed;p++)if(patches[p].page==i&&patches[p].written)needed=1;
  if(needed&&!page->writable){DWORD temporary;
   if(!VirtualProtect(page->address,page->length,PAGE_EXECUTE_READWRITE,&temporary))ok=0;
   else page->writable=1;
  }
 }
 for(uint32_t i=count;i>0;i--){WSPatch *patch=&patches[i-1];
  if(patch->written){
   if(!pages[patch->page].writable){ok=0;continue;}
   memcpy(patch->address,patch->before,patch->length);
   if(!FlushInstructionCache(GetCurrentProcess(),patch->address,patch->length))ok=0;
   patch->written=0;
  }
 }
 for(uint32_t i=0;i<pageCount;i++){WSPage *page=&pages[i];if(page->writable){DWORD temporary;
  if(!VirtualProtect(page->address,page->length,page->protection,&temporary))ok=0;else page->writable=0;
 }}
 return ok;
}
static int wsGroupPages(WSPatch *patches,uint32_t count,WSPage *pages,uint32_t *pageCount,SIZE_T pageSize){
 if(!pageSize)return wsError("The native protection-page size is invalid.");
 *pageCount=0;
 for(uint32_t i=0;i<count;i++){
  uintptr_t begin=(uintptr_t)patches[i].address;
  if(!patches[i].length||patches[i].length>UINTPTR_MAX-begin)return wsError("A native hook range is invalid.");
  uintptr_t page=begin/pageSize*pageSize;
  if(page!=(begin+patches[i].length-1)/pageSize*pageSize)return wsError("A native hook patch crosses a page boundary.");
  for(uint32_t j=0;j<i;j++){
   uintptr_t other=(uintptr_t)patches[j].address;
   if(begin<other+patches[j].length&&other<begin+patches[i].length)return wsError("Native hook patch ranges overlap.");
  }
  uint32_t p=0;while(p<*pageCount&&(uintptr_t)pages[p].address!=page)p++;
  if(p==*pageCount){pages[p].address=(unsigned char*)page;pages[p].length=pageSize;(*pageCount)++;}
  patches[i].page=p;
 }return 1;
}
static int wsDiscardBlobs(void){
 int ok=1;
 for(uint32_t i=0;i<WS_BLOB_COUNT;i++){
  WSInstalledBlob *installed=&wsInstalled[i];
  if(installed->registered){if(!RtlDeleteFunctionTable(installed->functions)){ok=0;continue;}installed->registered=0;}
  if(installed->allocation){if(!VirtualFree(installed->allocation,0,MEM_RELEASE)){ok=0;continue;}installed->allocation=NULL;}
 }return ok;
}
/* Return -1 only when rollback was incomplete and executable allocations must
 * remain resident. Runs with other known game threads already suspended. */
static int wsApplyPatches(WSPatch *patches,uint32_t patchCount,WSPage *pages,uint32_t pageCount){
 for(uint32_t i=0;i<patchCount;i++)if(memcmp(patches[i].address,patches[i].before,patches[i].length))return wsError("A native hook site changed before the memory transaction; nothing was committed.");
 for(uint32_t i=0;i<pageCount;i++){
  WSPage *page=&pages[i];
  if(!VirtualProtect(page->address,page->length,PAGE_EXECUTE_READWRITE,&page->protection)){wsWinError("Cannot temporarily unlock a native hook page");goto rollback;}
  page->writable=1;
 }
 for(uint32_t i=0;i<patchCount;i++){memcpy(patches[i].address,patches[i].after,patches[i].length);patches[i].written=1;}
 for(uint32_t i=0;i<patchCount;i++)if(!FlushInstructionCache(GetCurrentProcess(),patches[i].address,patches[i].length)){wsWinError("Cannot flush a native hook site instruction cache");goto rollback;}
 for(uint32_t i=0;i<pageCount;i++){
  DWORD temporary;WSPage *page=&pages[i];
  if(!VirtualProtect(page->address,page->length,page->protection,&temporary)){wsWinError("Cannot restore native hook page protection");goto rollback;}
  page->writable=0;
 }
 return 1;
 rollback:if(!wsRestorePatches(patches,patchCount,pages,pageCount))return -1;
 return 0;
}
__declspec(dllexport) int WorldSettingsInstallTestHooks(void){
 WSPatch patches[WS_MAX_HOOKS];WSPage pages[WS_MAX_HOOKS];WSThread threads[WS_MAX_THREADS];uint32_t patchCount=0,pageCount=0,threadCount=0;
 int result=0,safeToDiscard=1;HMODULE self=NULL;
 AcquireSRWLockExclusive(&wsInstallLock);
 if(wsInstallState==1){WorldSettingsSetAILoaderHookReady(1);ReleaseSRWLockExclusive(&wsInstallLock);return 1;}
 if(wsInstallState<0){wsError("A previous hook transaction could not be fully cleaned up; restart the game before testing.");ReleaseSRWLockExclusive(&wsInstallLock);return 0;}
 WorldSettingsSetAILoaderHookReady(0);
 wsInstallError[0]=0;memset(patches,0,sizeof patches);memset(pages,0,sizeof pages);memset(threads,0,sizeof threads);memset(wsInstalled,0,sizeof wsInstalled);
 if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,(LPCWSTR)(uintptr_t)&WorldSettingsInstallTestHooks,&self)){wsWinError("Cannot identify the copied World Settings test DLL");goto done;}
 for(uint32_t i=0;i<WS_BLOB_COUNT;i++)if(!wsPrepareBlob(i,self,patches,&patchCount))goto done;
 if(!wsPrepareEngine(patches,&patchCount))goto done;
 if(patchCount!=9u+WS_ENGINE_PATCH_COUNT){wsError("The complete nine-hook and expanded-engine transaction is incomplete.");goto done;}
 if(!wsEngineWorldAbsent())goto done;
 SYSTEM_INFO system;GetSystemInfo(&system);
 if(!wsGroupPages(patches,patchCount,pages,&pageCount,system.dwPageSize))goto done;
 if(!wsSuspendThreads(threads,&threadCount,patches,patchCount))goto done;
 if(!wsEngineWorldAbsent())goto done;
 /* No loader, heap, file, bcrypt or import resolution in the paused phase. */
 int applied=wsApplyPatches(patches,patchCount,pages,pageCount);
 if(applied==1){wsInstallState=1;result=1;}
 else if(applied<0){safeToDiscard=0;wsInstallState=-1;wsError("Windows refused complete in-memory hook rollback; hook allocations were retained. Restart the game before further testing.");}
 done:
 if(result)WorldSettingsSetAILoaderHookReady(1);
 wsResumeThreads(threads,threadCount);
 if(!result&&safeToDiscard&&!wsDiscardBlobs()){wsInstallState=-1;wsError("Native hooks were not committed, but Windows refused complete test allocation/unwind cleanup. Restart the game before retrying.");}
 ReleaseSRWLockExclusive(&wsInstallLock);return result;
}
