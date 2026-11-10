"""Portable pointer-free exploration/checkpoint codec refusal and shape tests."""
from pathlib import Path
import ctypes as C
import os
import shutil
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'src/anno1503_overhaul/native/world_options'
FIXTURE = r'''
#include "start_visibility_chart.h"
#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif
EXPORT unsigned char*make_blob(uint32_t width,uint32_t occupied,uint32_t*size){
 unsigned char guid[16]={1,2,3};WSChartCore c={0};unsigned char*out=0;
 if(!wsChartCoreNew(&c,width,width,0,0x1000,guid))return 0;
 if(occupied){WSChartCell r={{123,0,0,0x40,0,0xc0,5,0},1,6,7,0,500,124,0};if(!wsChartCellSet(&c,3,4,&r)||!wsChartCoreMark(&c,128,128,128,128)){wsChartCoreFree(&c);return 0;}}
 if(occupied>1){if(!wsChartMapShape(&c,64,64)||!wsChartMapPut(&c,3,0x8b)||!wsChartMapPut(&c,6,0x8b)||!wsChartMapPut(&c,6,0x9b)){wsChartCoreFree(&c);return 0;}}
 if(!wsChartCoreEncode(&c,&out,size,0,0))out=0;wsChartCoreFree(&c);return out;
}
EXPORT void release_blob(void*p){free(p);}
EXPORT int decode_blob(const void*p,uint32_t size,uint32_t*values){
 WSChartCore c={0},prior;memset(&c,0xa5,sizeof c);prior=c;
 int result=wsChartCoreDecode(p,size,&c,0,0);
 if(!result){values[0]=!memcmp(&c,&prior,sizeof c);return 0;}
 values[0]=c.width;values[1]=c.height;values[2]=c.count;values[3]=c.bitBytes;
 values[4]=wsChartCorePoint(&c,128,128);values[5]=c.cells[4*c.width+3].flags;values[6]=c.cells[4*c.width+3].time;values[7]=c.cells[4*c.width+3].logical;
 unsigned char pixel=0;values[8]=c.mapWidth;values[9]=c.mapHeight;values[10]=wsChartMapGet(&c,3,&pixel)?pixel:0xffffffffu;values[11]=wsChartMapGet(&c,6,&pixel)?pixel:0xffffffffu;
 wsChartCoreFree(&c);return 1;
}
EXPORT int core_case(uint32_t which){
 unsigned char guid[16]={1};WSChartCore c={0};if(!wsChartCoreNew(&c,256,256,0,0x1000,guid))return 1;
 int result=0;
 if(which==0){
  if(!wsChartCoreMark(&c,0,0,0,0)||!wsChartCorePoint(&c,0,0)||!wsChartCorePoint(&c,47,0)||wsChartCorePoint(&c,64,0)||wsChartCorePoint(&c,-1,0)||wsChartCorePoint(&c,256,0))result=2;
  uint32_t generation=c.generation;if(!wsChartCoreMark(&c,0,0,0,0)||generation!=c.generation)result=3;
 }else if(which==1){
  uint32_t bad=0x7fc00000u;float n;memcpy(&n,&bad,4);uint32_t generation=c.generation;
  if(wsChartCoreMark(&c,n,0,0,0)||wsChartCoreMark(&c,10,10,1,1)||wsChartCoreMark(&c,256,0,256,0)||generation!=c.generation)result=4;
 }else if(which==2){
  WSChartCell empty={{0},0,0,1,0,0,0,0},bad=empty;if(!wsChartCellSet(&c,1,1,&empty))result=5;
  uint32_t generation=c.generation;bad.flags=2;if(wsChartCellSet(&c,1,1,&bad)||memcmp(c.cells+257,&empty,sizeof empty)||generation!=c.generation)result=6;
  bad=empty;bad.time=1;if(wsChartCellSet(&c,1,1,&bad)||wsChartCellSet(&c,256,0,&empty))result=7;
 }else if(which==3){
  unsigned char pixel=0;if(!wsChartMapShape(&c,64,64)||!wsChartMapPut(&c,3,0x8b)||!wsChartMapGet(&c,3,&pixel)||pixel!=0x8b)result=8;
  if(wsChartMapPut(&c,3,160)||!wsChartMapGet(&c,3,&pixel)||pixel!=0x8b)result=11;
  unsigned char*prior=c.mapPixels;if(wsChartMapShape(&c,2049,1)||prior!=c.mapPixels)result=9;
  if(!wsChartMapShape(&c,32,32)||wsChartMapGet(&c,3,&pixel)||!wsChartMapValid(&c))result=10;
 }else result=99;
 wsChartCoreFree(&c);return result;
}
EXPORT int maximum_case(uint32_t*out){
 unsigned char guid[16]={1};WSChartCore active={0},staged={0};unsigned char*blob=0;uint32_t size=0;int result=0;
 if(!wsChartCoreNew(&active,2048,2048,0,0x1000,guid)||!wsChartMapShape(&active,2048,2048)){result=1;goto done;}
 memset(active.bits,255,active.bitBytes);for(uint32_t n=0;n<active.count;n++)active.cells[n].flags=WS_CHART_OBSERVED;
 memset(active.mapKnown,255,active.mapKnownBytes);memset(active.mapPixels,0x9b,active.mapCount);
 if(!wsChartCoreEncode(&active,&blob,&size,0,0)||size>WS_CHART_BLOB_LIMIT||!wsChartCoreDecode(blob,size,&staged,0,0)){result=2;goto done;}
 if(staged.cells[staged.count-1u].flags!=WS_CHART_OBSERVED||staged.mapPixels[staged.mapCount-1u]!=0x9b||memcmp(staged.bits,active.bits,active.bitBytes)){result=3;goto done;}
 out[0]=size;out[1]=active.count*(uint32_t)sizeof(WSChartCell);out[2]=active.mapCount+active.mapKnownBytes;out[3]=active.bitBytes;
 done:free(blob);wsChartCoreFree(&active);wsChartCoreFree(&staged);return result;
}
'''


def hash64(data):
    value = 14695981039346656037
    for byte in data:
        value = ((value ^ byte) * 1099511628211) & ((1 << 64) - 1)
    return value


def seal(data):
    data = bytearray(data)
    struct.pack_into('<Q', data, 72, hash64(data[128:]))
    struct.pack_into('<Q', data, 80, 0)
    struct.pack_into('<Q', data, 80, hash64(data[:128]))
    return bytes(data)


class ChartCodecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='anno-chart-codec-')
        folder = Path(cls.temp.name)
        source = folder / 'chart.c'
        source.write_text(FIXTURE)
        binary = folder / ('chart.dll' if os.name == 'nt' else 'chart.so')
        if os.name == 'nt':
            compiler = ROOT / '.local/toolchain/ziglang/zig.exe'
            if not compiler.exists():
                raise unittest.SkipTest('Reviewed local native compiler is unavailable.')
            command = [str(compiler), 'cc', '-target', 'x86_64-windows-gnu']
        else:
            compiler = shutil.which('cc')
            if not compiler:
                raise unittest.SkipTest('Native compiler is unavailable.')
            command = [compiler, '-fPIC']
        run = subprocess.run(command + ['-std=c11', '-shared', '-O2', '-Wall', '-Wextra', '-Werror', '-I', str(NATIVE), str(source), '-o', str(binary)], capture_output=True, text=True)
        if run.returncode:
            raise AssertionError(run.stdout + run.stderr)
        cls.lib = C.CDLL(str(binary))
        cls.lib.make_blob.argtypes = [C.c_uint32, C.c_uint32, C.POINTER(C.c_uint32)]
        cls.lib.make_blob.restype = C.c_void_p
        cls.lib.release_blob.argtypes = [C.c_void_p]
        cls.lib.decode_blob.argtypes = [C.c_void_p, C.c_uint32, C.POINTER(C.c_uint32)]
        cls.lib.core_case.argtypes = [C.c_uint32]
        cls.lib.maximum_case.argtypes = [C.POINTER(C.c_uint32)]

    @classmethod
    def tearDownClass(cls):
        if os.name == 'nt':
            import _ctypes
            _ctypes.FreeLibrary(cls.lib._handle)
        del cls.lib
        cls.temp.cleanup()

    def blob(self, width=256, occupied=1):
        size = C.c_uint32()
        address = self.lib.make_blob(width, occupied, C.byref(size))
        self.assertTrue(address)
        try:
            return C.string_at(address, size.value)
        finally:
            self.lib.release_blob(address)

    def decode(self, data, expected=True):
        buffer = C.create_string_buffer(data)
        out = (C.c_uint32 * 12)()
        self.assertEqual(self.lib.decode_blob(buffer, len(data), out), int(expected))
        if not expected:
            self.assertEqual(out[0], 1, 'Refused input changed the caller snapshot.')
        return list(out)

    def test_all_world_sizes_roundtrip_and_zero_ocean_is_one_small_run(self):
        for width in (256, 512, 1024, 2048):
            with self.subTest(width=width):
                blob = self.blob(width, 0)
                self.assertEqual(len(blob), 128 + (width // 8) ** 2 // 8 + 8)
                self.assertEqual(self.decode(blob)[:4], [width, width, width * width, (width // 8) ** 2 // 8])
        self.assertLess(len(self.blob(2048, 0)), 9000)

    def test_scalar_records_and_chart_survive_canonical_roundtrip(self):
        self.assertEqual(self.decode(self.blob())[4:8], [1, 7, 500, 124])
        self.assertEqual(self.blob(), self.blob())

    def test_chart_edges_observation_empty_and_invalid_values(self):
        for case in range(4):
            self.assertEqual(self.lib.core_case(case), 0)

    def test_truncated_oversize_checksum_and_reserved_headers_refuse_atomically(self):
        blob = self.blob()
        for cut in (0, 1, 127, 128, len(blob) - 1):
            self.decode(blob[:cut], False)
        for offset, value in ((8, 99), (16, 4096), (24, 16), (28, 0x7000), (48, 0xffffffff), (56, 0xffffffff), (64, 8), (68, 0), (92, 1)):
            bad = bytearray(blob)
            struct.pack_into('<I', bad, offset, value)
            self.decode(seal(bad), False)
        bad = bytearray(blob)
        bad[-1] ^= 1
        self.decode(bytes(bad), False)

    def test_run_overflow_noncanonical_zero_data_and_duplicate_coverage_refuse(self):
        blob = self.blob()
        run = 128 + 128
        for zero, records in ((0xffffffff, 1), (0, 0), (0, 0xffffffff), (65536, 1)):
            bad = bytearray(blob)
            struct.pack_into('<II', bad, run, zero, records)
            self.decode(seal(bad), False)
        bad = bytearray(blob)
        bad[run + 8:run + 28] = bytes(20)
        self.decode(seal(bad), False)
        bad = bytearray(blob)
        struct.pack_into('<I', bad, run + 28, 0)
        self.decode(seal(bad), False)

    def test_invalid_record_flags_owner_and_definition_refuse_before_publish(self):
        blob = self.blob()
        record = 128 + 128 + 8
        for offset, value in ((16, 0), (5, 0x12), (7, 1), (8, 2), (9, 32), (10, 2), (10, 0x83), (18, 1), (11, 1)):
            bad = bytearray(blob)
            bad[record + offset] = value
            self.decode(seal(bad), False)
        bad = bytearray(blob)
        struct.pack_into('<H', bad, record, 4000)
        self.decode(seal(bad), False)

    def test_bitmap_history_keeps_exact_owner_and_observed_empty_bytes(self):
        blob = self.blob(256, 2)
        self.assertEqual(self.decode(blob)[8:], [64, 64, 0x8b, 0x9b])
        known = 128 + 128
        pixels = known + 512
        bad = bytearray(blob)
        bad[pixels + 4] = 0x8b
        self.decode(seal(bad), False)
        for value in (160, 255):
            bad = bytearray(blob)
            bad[pixels + 3] = value
            self.decode(seal(bad), False)
        last_valid = bytearray(blob)
        last_valid[pixels + 3] = 159
        self.assertEqual(self.decode(seal(last_valid))[10], 159)
        for offset, value in ((92, 2049), (96, 0), (100, 0xffffffff), (104, 0xffffffff), (108, 1)):
            bad = bytearray(blob)
            struct.pack_into('<I', bad, offset, value)
            self.decode(seal(bad), False)

    def test_huge_dense_checkpoint_and_maximum_bitmap_stay_below_hard_cap(self):
        out = (C.c_uint32 * 4)()
        self.assertEqual(self.lib.maximum_case(out), 0)
        self.assertEqual(out[1:], [80 * 1024 * 1024, 4608 * 1024, 8192])
        self.assertEqual(out[0], 128 + sum(out[1:]) + 8)
        self.assertLess(out[0], 96 * 1024 * 1024)


if __name__ == '__main__':
    unittest.main()
