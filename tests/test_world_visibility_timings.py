"""Isolated coarse-stage timing snapshots; no Anno process or game timing claim."""
import ctypes as C
from pathlib import Path
import subprocess
import os
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'src/anno1503_overhaul/native/world_options'
SOURCE = r'''
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>
static LONG probeMode,probeCount,qpcFail,freqFail;static uint64_t nowTicks=100u;
static BOOL qpc(LARGE_INTEGER*out){out->QuadPart=(LONGLONG)nowTicks;return !qpcFail;}
static BOOL mockFrequency(LARGE_INTEGER*out){out->QuadPart=10000000;return !freqFail;}
static int writable(void*p,size_t size){
 uintptr_t at=(uintptr_t)p,end;if(!at||size>UINTPTR_MAX-at)return 0;end=at+size;
 while(at<end){MEMORY_BASIC_INFORMATION m;if(VirtualQuery((void*)at,&m,sizeof(m))!=sizeof(m)||m.State!=MEM_COMMIT||m.Protect&(PAGE_GUARD|PAGE_NOACCESS))return 0;
  DWORD protection=m.Protect&255u;if(protection!=PAGE_READWRITE&&protection!=PAGE_WRITECOPY&&protection!=PAGE_EXECUTE_READWRITE&&protection!=PAGE_EXECUTE_WRITECOPY)return 0;
  uintptr_t base=(uintptr_t)m.BaseAddress;if(m.RegionSize>UINTPTR_MAX-base||base+m.RegionSize<=at)return 0;at=base+m.RegionSize;
 }return 1;
}
static void probe(void);
static void stageProbe(uint32_t);
static LONG snapshotWriters(void);
#define WS_VISIBILITY_PERF_QPC(out) qpc(out)
#define WS_VISIBILITY_PERF_FREQUENCY(out) mockFrequency(out)
#define WS_VISIBILITY_PERF_WRITABLE(out,size) writable(out,size)
#define WS_VISIBILITY_PERF_SNAPSHOT_PROBE() probe()
#define WS_VISIBILITY_PERF_SNAPSHOT_STAGE_PROBE(stage) stageProbe(stage)
#define WS_VISIBILITY_PERF_SNAPSHOT_WRITERS() snapshotWriters()
#include "start_visibility_performance.inc"
static void probe(void){if(probeMode==2||(probeMode==1&&!probeCount)){probeCount++;wsVisibilityPerformanceRecord(WS_PERF_NATIVE_DRAW,7u);}}
/* Deterministic scheduling: start a writer after count has been copied, leave
 * its total/max published, then finish it at the final writers load. Reading
 * revision before writers would accept count0/total7; the correct order retries. */
static void stageProbe(uint32_t stage){
 if(probeMode==3&&stage==WS_PERF_NATIVE_DRAW&&!probeCount){
  probeCount=1;InterlockedIncrement(&wsVisibilityPerformanceWriters);
  InterlockedExchangeAdd64(&wsVisibilityPerformanceStages[stage].totalTicks,7);
  InterlockedExchange64(&wsVisibilityPerformanceStages[stage].maxTicks,7);
 }
}
static LONG snapshotWriters(void){
 if(probeMode==3&&probeCount==1){
  InterlockedIncrement64(&wsVisibilityPerformanceStages[WS_PERF_NATIVE_DRAW].count);
  InterlockedIncrement64(&wsVisibilityPerformanceRevision);
  InterlockedDecrement(&wsVisibilityPerformanceWriters);probeCount=2;
 }return InterlockedCompareExchange(&wsVisibilityPerformanceWriters,0,0);
}
__declspec(dllexport) void reset(void){memset(wsVisibilityPerformanceStages,0,sizeof(wsVisibilityPerformanceStages));wsVisibilityPerformanceWriters=0;wsVisibilityPerformanceRevision=wsVisibilityPerformanceFailures=0;probeMode=probeCount=qpcFail=freqFail=0;nowTicks=100;}
__declspec(dllexport) void recordStage(uint32_t stage,uint64_t ticks){wsVisibilityPerformanceRecord(stage,ticks);}
__declspec(dllexport) uint64_t beginAt(uint64_t ticks,int fail){nowTicks=ticks;qpcFail=fail;return wsVisibilityPerformanceBegin();}
__declspec(dllexport) void endAt(uint32_t stage,uint64_t begin,uint64_t ticks,int fail){nowTicks=ticks;qpcFail=fail;wsVisibilityPerformanceEnd(stage,begin);qpcFail=0;}
__declspec(dllexport) void blockSnapshot(int value){InterlockedExchange(&wsVisibilityPerformanceWriters,value);}
__declspec(dllexport) void probeSnapshot(int value){probeMode=value;probeCount=0;}
__declspec(dllexport) void failFrequency(int value){freqFail=value;}
static DWORD WINAPI worker(void*arg){uint32_t count=(uint32_t)(uintptr_t)arg;for(uint32_t n=0;n<count;n++)wsVisibilityPerformanceRecord(WS_PERF_NATIVE_DRAW,7u);return 0;}
__declspec(dllexport) int threaded(uint32_t iterations,uint32_t*out){
 HANDLE workers[4]={0};uint32_t started=0;for(;started<4;started++){workers[started]=CreateThread(NULL,0,worker,(void*)(uintptr_t)iterations,0,NULL);if(!workers[started])break;}
 if(started!=4u){for(uint32_t n=0;n<started;n++){WaitForSingleObject(workers[n],INFINITE);CloseHandle(workers[n]);}return 1;}
 uint32_t good=0,busy=0;int mismatch=0;for(uint32_t n=0;n<iterations;n++){
  WSVisibilityPerformanceSnapshot s;if(WorldSettingsCopyVisibilityPerformance(&s)){WSVisibilityPerformanceValues*v=s.stages+WS_PERF_NATIVE_DRAW;if(v->totalTicks!=7u*v->count||(v->count&&v->maxTicks!=7u)||s.activeWriters||s.recordFailures)mismatch=1;good++;}else busy++;
 }
 if(WaitForMultipleObjects(4,workers,TRUE,10000u)!=WAIT_OBJECT_0)mismatch=1;for(uint32_t n=0;n<4;n++)CloseHandle(workers[n]);
 out[0]=good;out[1]=busy;return mismatch?2:0;
}
__declspec(dllexport) int destinations(void){
 unsigned char*region=(unsigned char*)VirtualAlloc(NULL,8192u,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);if(!region)return 1;
 memset(region,0xa5,8192);DWORD old=0;int result=0;if(!VirtualProtect(region+4096u,4096u,PAGE_READONLY,&old))result=2;
 if(!result&&(WorldSettingsCopyVisibilityPerformance(NULL)||WorldSettingsCopyVisibilityPerformance(region+4096u)||WorldSettingsCopyVisibilityPerformance(region+4096u-100u)))result=3;
 for(uint32_t n=0;!result&&n<8192u;n++)if(region[n]!=0xa5)result=4;
 if(!VirtualFree(region,0,MEM_RELEASE))return 5;return result;
}
'''


class Values(C.Structure):
    _fields_ = [('count', C.c_uint64), ('totalTicks', C.c_uint64), ('maxTicks', C.c_uint64)]


class Snapshot(C.Structure):
    _fields_ = [('size', C.c_uint32), ('version', C.c_uint32), ('stageCount', C.c_uint32),
                ('flags', C.c_uint32), ('frequency', C.c_uint64), ('revision', C.c_uint64),
                ('activeWriters', C.c_uint64), ('recordFailures', C.c_uint64), ('stages', Values * 13)]


@unittest.skipUnless(os.name == 'nt', 'Native timing guards use Windows memory APIs.')
class VisibilityTimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='anno-visibility-timings-')
        directory = Path(cls.temp.name)
        source = directory / 'fixture.c'
        source.write_text(SOURCE, encoding='utf-8', newline='\n')
        output = directory / 'fixture.dll'
        compiler = ROOT / '.local/toolchain/ziglang/zig.exe'
        if not compiler.exists():
            raise unittest.SkipTest('Reviewed native compiler is unavailable.')
        result = subprocess.run([str(compiler), 'cc', '-target',
                                 'x86_64-windows-gnu', '-std=c11', '-shared', '-O2', '-Wall', '-Wextra',
                                 '-Werror', '-I', str(NATIVE), str(source), '-o', str(output)],
                                capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        cls.lib = C.CDLL(str(output))
        cls.lib.WorldSettingsCopyVisibilityPerformance.argtypes = [C.c_void_p]
        cls.lib.WorldSettingsCopyVisibilityPerformance.restype = C.c_uint32
        cls.lib.recordStage.argtypes = [C.c_uint32, C.c_uint64]
        cls.lib.beginAt.argtypes = [C.c_uint64, C.c_int]
        cls.lib.beginAt.restype = C.c_uint64
        cls.lib.endAt.argtypes = [C.c_uint32, C.c_uint64, C.c_uint64, C.c_int]
        cls.lib.threaded.argtypes = [C.c_uint32, C.POINTER(C.c_uint32)]

    @classmethod
    def tearDownClass(cls):
        import _ctypes
        _ctypes.FreeLibrary(cls.lib._handle)
        cls.temp.cleanup()

    def setUp(self):
        self.lib.reset()

    def snapshot(self):
        value = Snapshot()
        self.assertEqual(self.lib.WorldSettingsCopyVisibilityPerformance(C.byref(value)), C.sizeof(value))
        return value

    def test_empty_fixed_abi(self):
        s = self.snapshot()
        self.assertEqual((C.sizeof(s), s.size, s.version, s.stageCount, s.flags), (360, 360, 1, 13, 0))
        self.assertEqual((s.frequency, s.revision, s.activeWriters, s.recordFailures), (10000000, 0, 0, 0))
        self.assertTrue(all((v.count, v.totalTicks, v.maxTicks) == (0, 0, 0) for v in s.stages))

    def test_monotonic_stage_totals_max_and_no_reset(self):
        for stage in range(13):
            for ticks in (11, 2, 40, 0):
                self.lib.recordStage(stage, ticks)
        s = self.snapshot()
        self.assertEqual(s.revision, 52)
        self.assertTrue(all((v.count, v.totalTicks, v.maxTicks) == (4, 53, 40) for v in s.stages))
        self.assertEqual(bytes(s), bytes(self.snapshot()))

    def test_paired_timer_zero_delta_and_invalid_samples(self):
        begin = self.lib.beginAt(100, 0)
        self.lib.endAt(2, begin, 130, 0)
        self.lib.endAt(2, begin, 100, 0)
        self.lib.endAt(2, begin, 99, 0)
        self.lib.endAt(2, begin, 200, 1)
        self.lib.recordStage(13, 10)
        self.lib.recordStage(3, 1 << 63)
        self.assertEqual(self.lib.beginAt(0, 0), 0)
        self.assertEqual(self.lib.beginAt(100, 1), 0)
        s = self.snapshot()
        self.assertEqual((s.stages[2].count, s.stages[2].totalTicks, s.stages[2].maxTicks), (2, 30, 30))
        self.assertEqual(s.recordFailures, 6)

    def test_invalid_readonly_and_cross_boundary_destinations_untouched(self):
        self.assertEqual(self.lib.destinations(), 0)

    def test_busy_and_frequency_failure_leave_destination_untouched(self):
        output = (C.c_ubyte * 360)(*([0xA5] * 360))
        self.lib.blockSnapshot(1)
        self.assertEqual(self.lib.WorldSettingsCopyVisibilityPerformance(output), 0)
        self.lib.blockSnapshot(0)
        self.lib.failFrequency(1)
        self.assertEqual(self.lib.WorldSettingsCopyVisibilityPerformance(output), 0)
        self.assertEqual(bytes(output), bytes([0xA5]) * 360)

    def test_retries_changed_revision_and_bounded_exhaustion(self):
        self.lib.probeSnapshot(1)
        s = self.snapshot()
        self.assertEqual((s.stages[4].count, s.stages[4].totalTicks, s.revision), (1, 7, 1))
        self.lib.probeSnapshot(2)
        output = (C.c_ubyte * 360)(*([0xA5] * 360))
        self.assertEqual(self.lib.WorldSettingsCopyVisibilityPerformance(output), 0)
        self.assertEqual(bytes(output), bytes([0xA5]) * 360)
        self.lib.probeSnapshot(0)
        self.assertEqual(self.snapshot().stages[4].count, 5)

    def test_concurrent_writers_preserve_exact_counts_and_coherent_successes(self):
        results = (C.c_uint32 * 2)()
        self.assertEqual(self.lib.threaded(10000, results), 0)
        self.assertEqual(sum(results), 10000)
        s = self.snapshot()
        self.assertEqual((s.stages[4].count, s.stages[4].totalTicks, s.stages[4].maxTicks), (40000, 280000, 7))
        self.assertEqual((s.revision, s.recordFailures), (40000, 0))

    def test_writer_finishing_during_final_checks_cannot_publish_partial_totals(self):
        self.lib.probeSnapshot(3)
        s = self.snapshot()
        self.assertEqual((s.stages[4].count, s.stages[4].totalTicks, s.stages[4].maxTicks), (1, 7, 7))
        self.assertEqual((s.revision, s.activeWriters, s.recordFailures), (1, 0, 0))


if __name__ == '__main__':
    unittest.main(verbosity=2)
