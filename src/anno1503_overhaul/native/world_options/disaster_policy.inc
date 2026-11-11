/* Policies belong to one certified World identity. Native schedulers and RNG
 * remain authoritative; these callbacks are simulation hooks, never draw work. */
#include "disaster_policy.h"
typedef struct WSDisasterContext {void*world;unsigned char guid[16];uint32_t width,height,master,mask,frequency,severity,active,provisional;} WSDisasterContext;
static SRWLOCK wsDisasterLock=SRWLOCK_INIT;
static WSDisasterContext wsDisasterCurrent;
static uint32_t wsDisasterPending[5];
static int wsDisasterError(char*out,uint32_t cap,const char*message){wsMessage(out,cap,message);return 0;}
static int wsDisasterWorld(void*world,WSDisasterContext*out){
 unsigned char*w=(unsigned char*)WS_CERT_MODULE("AnnoWelt.dll");void*vt=wsCertPointer(world,0);WSDisasterContext c={0};
 if(!out||!w||(vt!=w+0xff1d8u&&vt!=w+0xff650u)||wsCertPointer(vt,0xf0)!=w+0xd1910u||
    !wsCertRead((unsigned char*)world+0x1d8,&c.width,4)||!wsCertRead((unsigned char*)world+0x1dc,&c.height,4)||
    !wsCertRead((unsigned char*)world+0x6e4c,c.guid,16)||c.width!=c.height||
    (c.width!=256u&&c.width!=512u&&c.width!=1024u&&c.width!=2048u))return 0;
 c.world=world;*out=c;return 1;
}
static int wsDisasterWritable(void*p,uint32_t size){
 MEMORY_BASIC_INFORMATION m;uintptr_t a=(uintptr_t)p;
 if(!p||!size||!VirtualQuery(p,&m,sizeof m)||m.State!=MEM_COMMIT||(m.Protect&(PAGE_GUARD|PAGE_NOACCESS))||
    !(m.Protect&(PAGE_READWRITE|PAGE_WRITECOPY|PAGE_EXECUTE_READWRITE|PAGE_EXECUTE_WRITECOPY)))return 0;
 return a>=(uintptr_t)m.BaseAddress&&size<=m.RegionSize&&a-(uintptr_t)m.BaseAddress<=m.RegionSize-size;
}
void WorldSettingsExpectDisasterOptions(const WSWorldSettings*s){
 memset(wsDisasterPending,0,sizeof wsDisasterPending);
 if(!s||!wsDisasterOptionsValid((uint32_t)s->disasters,s->disasterMask,s->disasterFrequency,s->disasterSeverity))return;
 wsDisasterPending[0]=1;wsDisasterPending[1]=(uint32_t)s->disasters;wsDisasterPending[2]=s->disasterMask;wsDisasterPending[3]=s->disasterFrequency;wsDisasterPending[4]=s->disasterSeverity;
}
void WorldSettingsFinishDisasterAttempt(int success){
 memset(wsDisasterPending,0,sizeof wsDisasterPending);AcquireSRWLockExclusive(&wsDisasterLock);
 if(wsDisasterCurrent.provisional){if(success)wsDisasterCurrent.provisional=0;else memset(&wsDisasterCurrent,0,sizeof wsDisasterCurrent);}
 ReleaseSRWLockExclusive(&wsDisasterLock);
}
static void wsDisasterPublish(const WSDisasterContext*c){AcquireSRWLockExclusive(&wsDisasterLock);wsDisasterCurrent=*c;ReleaseSRWLockExclusive(&wsDisasterLock);}
static void wsDisasterClearLoaded(void){WSDisasterContext c={0};wsDisasterPublish(&c);}
int WorldSettingsBindDisasterOptions(void*world,char*error,uint32_t cap){
 uint32_t p[5],before=0,after=0,observed=0;WSDisasterContext c;
 memcpy(p,wsDisasterPending,sizeof p);memset(wsDisasterPending,0,sizeof wsDisasterPending);
 if(p[0]!=1u||!wsDisasterOptionsValid(p[1],p[2],p[3],p[4])||!wsDisasterWorld(world,&c)||
    !wsCertRead((unsigned char*)world+0x6eec,&before,4)||(before&0x86u)!=(p[1]?0u:0x86u))return wsDisasterError(error,cap,"The fresh disaster policy has no unique certified native world.");
 after=(before&~0x8eu)|wsDisasterDisabledNative(p[1],p[2]);
 if(!wsDisasterWritable((unsigned char*)world+0x6eec,4))return wsDisasterError(error,cap,"The native disaster flags are not writable; no policy was changed.");
 memcpy((unsigned char*)world+0x6eec,&after,4);
 if(!wsCertRead((unsigned char*)world+0x6eec,&observed,4)||observed!=after){memcpy((unsigned char*)world+0x6eec,&before,4);return wsDisasterError(error,cap,"The disaster flags failed verification and were restored.");}
 c.master=p[1];c.mask=p[2];c.frequency=p[3];c.severity=p[4];c.active=c.provisional=1;wsDisasterPublish(&c);
 if(error&&cap)error[0]=0;return 1;
}
/* Exact native call sites supply live typed objects. The high-rate drought
 * threshold uses this bounded cached identity, with no VirtualQuery, catalogue
 * scan, chart lock, allocation or native random call on that path. */
static int wsDisasterFast(void*world,uint32_t type,uint32_t*frequency,uint32_t*severity){
 int found=0;AcquireSRWLockShared(&wsDisasterLock);
 if(type<WS_DISASTER_COUNT&&world&&wsDisasterCurrent.active&&wsDisasterCurrent.world==world&&
    !memcmp((unsigned char*)world+0x6e4c,wsDisasterCurrent.guid,16)){
  found=wsDisasterCurrent.master&&!!(wsDisasterCurrent.mask&(1u<<type))?1:-1;
  if(frequency)*frequency=(wsDisasterCurrent.frequency>>(type*2u))&3u;
  if(severity)*severity=(wsDisasterCurrent.severity>>(type*2u))&3u;
 }
 ReleaseSRWLockShared(&wsDisasterLock);return found;
}
static void*wsDisasterIslandWorld(void*island){void*w=NULL;if(island)memcpy(&w,(unsigned char*)island+0x38,sizeof w);return w;}
static uint32_t wsDisasterCityRandom(uint32_t random,uint32_t denominator,void*city,uint32_t type){
 void*island=wsCertPointer(city,0x20);uint32_t mode=1;int policy=wsDisasterFast(wsDisasterIslandWorld(island),type,&mode,NULL);
 if(policy<0)return denominator>=5u?4u:random;
 return policy?wsDisasterChance(random,denominator,mode):random;
}
__declspec(dllexport) uint32_t WorldSettingsDisasterFireRandom(uint32_t random,uint32_t denominator,void*city){return wsDisasterCityRandom(random,denominator,city,0);}
__declspec(dllexport) uint32_t WorldSettingsDisasterPlagueRandom(uint32_t random,uint32_t denominator,void*city){return wsDisasterCityRandom(random,denominator,city,1);}
__declspec(dllexport) uint32_t WorldSettingsDisasterEarthquakeThreshold(void*world){uint32_t mode=1;return wsDisasterFast(world,3,&mode,NULL)?wsDisasterInterval(450000u,mode):450000u;}
__declspec(dllexport) uint32_t WorldSettingsDisasterDroughtThreshold(void*island){uint32_t mode=1;return wsDisasterFast(wsDisasterIslandWorld(island),4,&mode,NULL)?wsDisasterInterval(300u,mode):300u;}
__declspec(dllexport) uint32_t WorldSettingsDisasterVolcanoInterval(uint32_t interval,void*world){uint32_t mode=1;return wsDisasterFast(world,2,&mode,NULL)?wsDisasterInterval(interval,mode):interval;}
__declspec(dllexport) void WorldSettingsDisasterDroughtBegin(void*island){
 unsigned char*w=(unsigned char*)WS_CERT_MODULE("AnnoWelt.dll");if(!w)return;
 uint32_t severity=1;int policy=wsDisasterFast(wsDisasterIslandWorld(island),4,NULL,&severity);
 void*prior=policy&&severity!=1u?wsCertPointer(island,0x100):NULL;
 if(policy<0)return;((void(*)(void*))(w+0x58890u))(island);
 if(policy&&severity!=1u&&!prior){unsigned char*state=(unsigned char*)wsCertPointer(island,0x100);uint32_t extent=0;
  if(state&&wsCertRead(state+4,&extent,4)&&extent==6u&&wsDisasterWritable(state+4,4)){extent=severity?9u:3u;memcpy(state+4,&extent,4);}
 }
}
__declspec(dllexport) void*WorldSettingsDisasterCreateEvent(void*table,uint32_t type,uint32_t unused,const float*position,int32_t owner){
 unsigned char*w=(unsigned char*)WS_CERT_MODULE("AnnoWelt.dll");void*island=wsCertPointer(table,0x38);
 if(!w||wsCertPointer(table,0)!=w+0xf2588u||wsCertPointer(w+0xf2588u,0)!=w+0x371c0u)return NULL;
 uint32_t index=type==0x1du?2u:type==0x15au?3u:WS_DISASTER_COUNT,severity=1;int policy=wsDisasterFast(wsDisasterIslandWorld(island),index,NULL,&severity);
 if(policy<0)return NULL;
 void*event=((void*(*)(void*,uint32_t,uint32_t,const float*,int32_t))(w+0x371c0u))(table,type,unused,position,owner);
 if(policy&&severity!=1u&&event){uint32_t duration=0,kind=0;void*vt=wsCertPointer(event,0);uint32_t normal=index==2u?10000u:7500u;
  if(vt==w+(index==2u?0xf2230u:0xf2130u)&&wsCertPointer(event,8)==island&&
     wsCertRead((unsigned char*)event+0x2c,&kind,4)&&kind==type&&wsCertRead((unsigned char*)event+0x48,&duration,4)&&
     duration==normal&&wsDisasterWritable((unsigned char*)event+0x48,4)){
   duration=severity?normal*2u:normal/2u;memcpy((unsigned char*)event+0x48,&duration,4);
  }
 }return event;
}
