/* Transaction around ONLY the fields written by the reviewed stock AI binder
 * and start_disasters.h. Original seven flags at2280 (seven bytes), seven
 * 168-byte records at2288, and Frame option bytesc7a78/c7a79 are preserved.
 * The gap byte2287 and every other native field are deliberately untouched.
 */
#ifndef WS_MENU_FRAME_MODULE
#define WS_MENU_FRAME_MODULE() GetModuleHandleA("AnnoFrame.dll")
#endif
typedef struct WSMenuNativeSetup {
 unsigned char*setup,*frame;void*allocation,*vtable;
 unsigned char flags[7],records[7*168],options[2];int active,poisoned;
} WSMenuNativeSetup;
static WSMenuNativeSetup wsMenuNativeSetup;
static SRWLOCK wsMenuNativeSetupLock=SRWLOCK_INIT;
static int wsMenuSetupSpan(const void*pointer,SIZE_T size,void*allocation){
 uintptr_t at=(uintptr_t)pointer,end;
 if(!at||size>UINTPTR_MAX-at)return 0;end=at+size;
 while(at<end){MEMORY_BASIC_INFORMATION m;
  if(VirtualQuery((void*)at,&m,sizeof m)!=sizeof m||m.State!=MEM_COMMIT||m.AllocationBase!=allocation||
     m.Protect&(PAGE_GUARD|PAGE_NOACCESS))return 0;
  DWORD p=m.Protect&255u;if(p!=PAGE_READWRITE&&p!=PAGE_WRITECOPY&&p!=PAGE_EXECUTE_READWRITE&&p!=PAGE_EXECUTE_WRITECOPY)return 0;
  uintptr_t base=(uintptr_t)m.BaseAddress;if(m.RegionSize>UINTPTR_MAX-base||base+m.RegionSize<=at)return 0;
  at=base+m.RegionSize<end?base+m.RegionSize:end;
 }return 1;
}
static int wsMenuSetupIdentity(const WSMenuNativeSetup*s){
 MEMORY_BASIC_INFORMATION m;void*vt=NULL;
 if(!s||!s->setup||!s->frame||s->frame!=(unsigned char*)WS_MENU_FRAME_MODULE()||
    !wsMenuSetupSpan(s->setup,8,s->allocation)||
    !wsMenuSetupSpan(s->setup+0x2280,0x4a0,s->allocation)||
    !wsMenuSetupSpan(s->frame+0xc7a78,2,s->frame))return 0;
 memcpy(&vt,s->setup,8);
 if(!vt||vt!=s->vtable||VirtualQuery(vt,&m,sizeof m)!=sizeof m||m.State!=MEM_COMMIT||m.AllocationBase!=s->frame||m.Protect&(PAGE_GUARD|PAGE_NOACCESS))return 0;
 return 1;
}
static int wsMenuSetupRestoreLocked(void){
 WSMenuNativeSetup*s=&wsMenuNativeSetup;
 if(s->poisoned)return 0;if(!s->active)return 1;
 if(!wsMenuSetupIdentity(s)){s->poisoned=1;return 0;}
 /* All destinations have been checked before the first restoring write. */
 memcpy(s->setup+0x2280,s->flags,sizeof s->flags);
 memcpy(s->setup+0x2288,s->records,sizeof s->records);
 memcpy(s->frame+0xc7a78,s->options,sizeof s->options);
 if(memcmp(s->setup+0x2280,s->flags,sizeof s->flags)||memcmp(s->setup+0x2288,s->records,sizeof s->records)||
    memcmp(s->frame+0xc7a78,s->options,sizeof s->options)){s->poisoned=1;return 0;}
 memset(s,0,sizeof(*s));return 1;
}
int WorldSettingsRestoreNativeSetup(void){
 AcquireSRWLockExclusive(&wsMenuNativeSetupLock);int result=wsMenuSetupRestoreLocked();ReleaseSRWLockExclusive(&wsMenuNativeSetupLock);return result;
}
int WorldSettingsFinishNativeSetup(int success){
 AcquireSRWLockExclusive(&wsMenuNativeSetupLock);int result;
 if(success&&!wsMenuNativeSetup.poisoned){memset(&wsMenuNativeSetup,0,sizeof wsMenuNativeSetup);result=1;}
 else result=wsMenuSetupRestoreLocked();
 ReleaseSRWLockExclusive(&wsMenuNativeSetupLock);return result;
}
static int wsMenuSnapshotNativeSetup(void*setup,void*frame){
 AcquireSRWLockExclusive(&wsMenuNativeSetupLock);int result=0;WSMenuNativeSetup s={0};MEMORY_BASIC_INFORMATION m;
 if(!wsMenuSetupRestoreLocked()||!setup||!frame||(uintptr_t)setup>UINTPTR_MAX-0x2720u||
    (uintptr_t)frame>UINTPTR_MAX-0xc7a7au||VirtualQuery(setup,&m,sizeof m)!=sizeof m)goto done;
 s.setup=setup;s.frame=frame;s.allocation=m.AllocationBase;
 if(!wsMenuSetupSpan(setup,8,s.allocation))goto done;memcpy(&s.vtable,setup,8);
 if(!wsMenuSetupIdentity(&s))goto done;
 memcpy(s.flags,s.setup+0x2280,sizeof s.flags);memcpy(s.records,s.setup+0x2288,sizeof s.records);memcpy(s.options,s.frame+0xc7a78,sizeof s.options);
 s.active=1;wsMenuNativeSetup=s;result=1;
 done:ReleaseSRWLockExclusive(&wsMenuNativeSetupLock);return result;
}
static const char*wsMenuSetupResetMessage="The original game setup could not be restored safely. Close Anno and start it again before creating another world.";
static void wsMenuSetupFailed(DialogState*d,const char*failure){
 int restored=WorldSettingsRestoreNativeSetup();WorldSettingsFinishAttempt(0);invalidatePreview(d);status(d,restored?failure:wsMenuSetupResetMessage);
}
