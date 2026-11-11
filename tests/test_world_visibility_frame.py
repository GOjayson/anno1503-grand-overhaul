"""Final-flush ordering against owned C spies; never opens Anno or game data."""
import ctypes as C
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]


class VisibilityFrameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='anno-chart-flush-', ignore_cleanup_errors=True)
        folder = Path(cls.temp.name)
        zig = ROOT / '.local/toolchain/ziglang/zig.exe'
        compiler = [str(zig), 'cc'] if os.name == 'nt' and zig.is_file() else []
        if not compiler:
            found = shutil.which('cc') or shutil.which('gcc') or shutil.which('clang')
            if not found:
                cls.temp.cleanup()
                raise unittest.SkipTest('Final-flush ordering checks need a C compiler.')
            compiler = [found]
        header = ROOT / 'src/anno1503_overhaul/native/world_options/start_visibility_frame.inc'
        source = r'''
#include <stdint.h>
#include <stddef.h>
#ifndef _WIN32
#define __declspec(x)
#define __cdecl
#endif
typedef int32_t LONG;
static unsigned char display[0xf64000],renderer[8],context[32];
static LONG wsVisibilityLastError;
static int fault,events[8],count,prepared,applied;
enum {WS_PERF_OVERLAY_PREFLIGHT=7,WS_PERF_NATIVE_FLUSH=8,WS_PERF_OVERLAY_APPLY=9,WS_PERF_CLEANUP=10};
static int timingStages[4],timingCount;
static uint64_t wsVisibilityPerformanceBegin(void){return 1u;}
static void wsVisibilityPerformanceEnd(uint32_t stage,uint64_t begin){if(begin==1u&&timingCount<4)timingStages[timingCount++]=(int)stage;}
static int InterlockedExchange(LONG*p,int value){int old=*p;*p=value;return old;}
static void*module(const char*name){(void)name;return fault==1?NULL:display;}
#define WS_CERT_MODULE(name) module(name)
static void*wsCertPointer(void*p,size_t offset){
 if(p==renderer&&offset==0)return display+(fault==2?0xf63748:0xf63740);
 if(p==display+0xf63740&&offset==0x118)return display+(fault==3?0x483e1:0x483e0);
 return NULL;
}
static int wsVisibilityWithinModule(unsigned char*m,void*p,size_t size){
 return fault!=4&&m==display&&p==display+0x483e0&&size==1;
}
static int wsCertMemory(void*p,size_t size,int execute){
 return fault!=5&&p==display+0x483e0&&size==1&&execute==1;
}
static int wsVisibilityExplorationPreflight(void*r,void*c){
 if(r!=renderer||c!=context)return 0;events[count++]=1;return prepared;
}
static uintptr_t original_flush(void*r){
 if(r!=renderer)return 0;events[count++]=2;return UINT64_C(0xfedcba9876543210);
}
#define WS_VISIBILITY_NATIVE_FLUSH(target) original_flush
static void wsVisibilityChartRetire(void*r){if(r==renderer)events[count++]=3;}
static int wsVisibilityApplyExploredSea(void*r,void*c){
 if(r!=renderer||c!=context)return 0;events[count++]=4;return applied;
}
'''
        source += header.read_text() + r'''
__declspec(dllexport) uintptr_t fixture_run(int bad,int before,int after){
 fault=bad;prepared=before;applied=after;count=0;timingCount=0;wsVisibilityLastError=0;
 return WorldSettingsVisibilityFinishFrame(renderer,context);
}
__declspec(dllexport) int fixture_event(int index){return index<count?events[index]:-1;}
__declspec(dllexport) int fixture_count(void){return count;}
__declspec(dllexport) int fixture_error(void){return wsVisibilityLastError;}
__declspec(dllexport) int fixture_timing_count(void){return timingCount;}
__declspec(dllexport) int fixture_timing_stage(int index){return index<timingCount?timingStages[index]:-1;}
'''
        path = folder / 'fixture.c'
        path.write_text(source, encoding='utf-8')
        output = folder / ('fixture.dll' if os.name == 'nt' else 'fixture.so')
        command = [*compiler, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                   '-Wno-misleading-indentation', '-shared', str(path), '-o', str(output)]
        if os.name != 'nt':
            command.insert(len(compiler), '-fPIC')
        compiled = subprocess.run(command, capture_output=True, text=True)
        if compiled.returncode:
            cls.temp.cleanup()
            raise AssertionError(compiled.stdout + compiled.stderr)
        cls.lib = C.CDLL(str(output))
        cls.lib.fixture_run.argtypes = [C.c_int, C.c_int, C.c_int]
        cls.lib.fixture_run.restype = C.c_uint64
        cls.lib.fixture_event.argtypes = [C.c_int]

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_native_workers_drain_once_before_copy_retirement_and_pixel_mask(self):
        self.assertEqual(self.lib.fixture_run(0, 1, 1), 0xfedcba9876543210)
        self.assertEqual(self.lib.fixture_count(), 4)
        self.assertEqual([self.lib.fixture_event(i) for i in range(4)], [1, 2, 3, 4])
        self.assertEqual(self.lib.fixture_error(), 0)
        self.assertEqual(self.lib.fixture_timing_count(), 4)
        self.assertEqual([self.lib.fixture_timing_stage(i) for i in range(4)], [7, 8, 10, 9])

    def test_preflight_failure_does_not_skip_native_drain_or_use_a_stale_surface(self):
        for applied in (0, 1):
            with self.subTest(postflush_valid=applied):
                self.assertEqual(self.lib.fixture_run(0, 0, applied), 0xfedcba9876543210)
                self.assertEqual([self.lib.fixture_event(i) for i in range(4)], [1, 2, 3, 4])
                self.assertEqual(self.lib.fixture_error(), 0 if applied else 16)

    def test_postflush_failure_preserves_native_return_and_reports_failure(self):
        self.assertEqual(self.lib.fixture_run(0, 1, 0), 0xfedcba9876543210)
        self.assertEqual(self.lib.fixture_error(), 16)
        self.assertEqual([self.lib.fixture_event(i) for i in range(4)], [1, 2, 3, 4])

    def test_unknown_renderer_or_wrong_executable_method_is_never_called(self):
        for fault in range(1, 6):
            with self.subTest(fault=fault):
                self.assertEqual(self.lib.fixture_run(fault, 1, 1), 0)
                self.assertEqual(self.lib.fixture_count(), 0)
                self.assertEqual(self.lib.fixture_error(), 16)
                self.assertEqual(self.lib.fixture_timing_count(), 0)


if __name__ == '__main__':
    unittest.main()
