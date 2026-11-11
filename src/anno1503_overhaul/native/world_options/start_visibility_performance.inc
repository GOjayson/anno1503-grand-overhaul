/* Passive coarse-stage CPU timing; no game pointers,
 * reset, persistent cache, native hook or settings/save ABI changes.
 * Include after the Windows/stdint declarations and writable-span helper.
 */
enum WSVisibilityPerformanceStage {
 WS_PERF_CONTEXT=0,WS_PERF_FAST_PREPARE,WS_PERF_CHART_OBSERVE,
 WS_PERF_PREPARE_COPIES,WS_PERF_NATIVE_DRAW,WS_PERF_MAP_REFRESH,
 WS_PERF_RENDER_REFRESH,WS_PERF_OVERLAY_PREFLIGHT,WS_PERF_NATIVE_FLUSH,
 WS_PERF_OVERLAY_APPLY,WS_PERF_CLEANUP,WS_PERF_CHART_READ,
 WS_PERF_DRAW_TOTAL,WS_PERF_STAGE_COUNT
};
typedef struct WSVisibilityPerformanceValues {uint64_t count,totalTicks,maxTicks;} WSVisibilityPerformanceValues;
typedef struct WSVisibilityPerformanceSnapshot {
 uint32_t size,version,stageCount,flags;
 uint64_t frequency,revision,activeWriters,recordFailures;
 WSVisibilityPerformanceValues stages[WS_PERF_STAGE_COUNT];
} WSVisibilityPerformanceSnapshot;
_Static_assert(sizeof(WSVisibilityPerformanceSnapshot)==360u,"visibility performance ABI");
typedef struct WSVisibilityPerformanceAtomic {
 volatile LONG64 count,totalTicks,maxTicks;
} WSVisibilityPerformanceAtomic;
static WSVisibilityPerformanceAtomic wsVisibilityPerformanceStages[WS_PERF_STAGE_COUNT];
static volatile LONG wsVisibilityPerformanceWriters;
static volatile LONG64 wsVisibilityPerformanceRevision,wsVisibilityPerformanceFailures;
#ifndef WS_VISIBILITY_PERF_QPC
#define WS_VISIBILITY_PERF_QPC(value) QueryPerformanceCounter(value)
#endif
#ifndef WS_VISIBILITY_PERF_FREQUENCY
#define WS_VISIBILITY_PERF_FREQUENCY(value) QueryPerformanceFrequency(value)
#endif
#ifndef WS_VISIBILITY_PERF_WRITABLE
#define WS_VISIBILITY_PERF_WRITABLE(out,size) wsMineralPersistenceWritable((out),(size))
#endif
#ifndef WS_VISIBILITY_PERF_SNAPSHOT_STAGE_PROBE
#define WS_VISIBILITY_PERF_SNAPSHOT_STAGE_PROBE(stage) ((void)(stage))
#endif
#ifndef WS_VISIBILITY_PERF_SNAPSHOT_WRITERS
#define WS_VISIBILITY_PERF_SNAPSHOT_WRITERS() InterlockedCompareExchange(&wsVisibilityPerformanceWriters,0,0)
#endif
#ifndef WS_VISIBILITY_PERF_SNAPSHOT_QUIET_PROBE
#define WS_VISIBILITY_PERF_SNAPSHOT_QUIET_PROBE() ((void)0)
#endif
#ifndef WS_VISIBILITY_PERF_SNAPSHOT_PROBE
#define WS_VISIBILITY_PERF_SNAPSHOT_PROBE() ((void)0)
#endif
static uint64_t wsVisibilityPerformanceLoad(volatile LONG64*value){return (uint64_t)InterlockedCompareExchange64(value,0,0);}
static void wsVisibilityPerformanceFailure(void){
 InterlockedIncrement(&wsVisibilityPerformanceWriters);
 InterlockedIncrement64(&wsVisibilityPerformanceFailures);
 InterlockedIncrement64(&wsVisibilityPerformanceRevision);
 InterlockedDecrement(&wsVisibilityPerformanceWriters);
}
static uint64_t wsVisibilityPerformanceBegin(void){
 LARGE_INTEGER now;if(!WS_VISIBILITY_PERF_QPC(&now)||now.QuadPart<=0){wsVisibilityPerformanceFailure();return 0;}
 return (uint64_t)now.QuadPart;
}
static void wsVisibilityPerformanceRecord(uint32_t stage,uint64_t ticks){
 if(stage>=WS_PERF_STAGE_COUNT||ticks>(uint64_t)INT64_MAX){wsVisibilityPerformanceFailure();return;}
 InterlockedIncrement(&wsVisibilityPerformanceWriters);
 WSVisibilityPerformanceAtomic*p=wsVisibilityPerformanceStages+stage;
 InterlockedExchangeAdd64(&p->totalTicks,(LONG64)ticks);
 uint64_t current=wsVisibilityPerformanceLoad(&p->maxTicks);
 while(current<ticks){uint64_t prior=(uint64_t)InterlockedCompareExchange64(&p->maxTicks,(LONG64)ticks,(LONG64)current);if(prior==current)break;current=prior;}
 InterlockedIncrement64(&p->count);
 InterlockedIncrement64(&wsVisibilityPerformanceRevision);
 InterlockedDecrement(&wsVisibilityPerformanceWriters);
}
static void wsVisibilityPerformanceEnd(uint32_t stage,uint64_t begin){
 LARGE_INTEGER now;if(!begin)return;
 if(!WS_VISIBILITY_PERF_QPC(&now)||now.QuadPart<0||(uint64_t)now.QuadPart<begin){wsVisibilityPerformanceFailure();return;}
 wsVisibilityPerformanceRecord(stage,(uint64_t)now.QuadPart-begin);
}
__declspec(dllexport) DWORD WINAPI WorldSettingsCopyVisibilityPerformance(void*out){
 if(!out||!WS_VISIBILITY_PERF_WRITABLE(out,sizeof(WSVisibilityPerformanceSnapshot)))return 0;
 LARGE_INTEGER frequency;if(!WS_VISIBILITY_PERF_FREQUENCY(&frequency)||frequency.QuadPart<=0)return 0;
 for(uint32_t attempt=0;attempt<4u;attempt++){
  if(WS_VISIBILITY_PERF_SNAPSHOT_WRITERS())continue;
  uint64_t revision=wsVisibilityPerformanceLoad(&wsVisibilityPerformanceRevision);
  WSVisibilityPerformanceSnapshot next={0};next.size=sizeof(next);next.version=1u;next.stageCount=WS_PERF_STAGE_COUNT;
  next.frequency=(uint64_t)frequency.QuadPart;next.revision=revision;
  next.recordFailures=wsVisibilityPerformanceLoad(&wsVisibilityPerformanceFailures);
  for(uint32_t stage=0;stage<WS_PERF_STAGE_COUNT;stage++){
   WSVisibilityPerformanceAtomic*p=wsVisibilityPerformanceStages+stage;
   next.stages[stage].count=wsVisibilityPerformanceLoad(&p->count);
   WS_VISIBILITY_PERF_SNAPSHOT_STAGE_PROBE(stage);
   next.stages[stage].totalTicks=wsVisibilityPerformanceLoad(&p->totalTicks);
   next.stages[stage].maxTicks=wsVisibilityPerformanceLoad(&p->maxTicks);
  }
  WS_VISIBILITY_PERF_SNAPSHOT_PROBE();
  /* Check writers BEFORE the final revision. An overlapping writer must
   * either still be active here, or have published a changed revision. A
   * writer beginning after this quiet check cannot have changed our earlier
   * copied values; a completed update is caught by the final revision read. */
  if(WS_VISIBILITY_PERF_SNAPSHOT_WRITERS())continue;
  WS_VISIBILITY_PERF_SNAPSHOT_QUIET_PROBE();
  if(wsVisibilityPerformanceLoad(&wsVisibilityPerformanceRevision)!=revision)continue;
  memcpy(out,&next,sizeof(next));return sizeof(next);
 }return 0;
}
