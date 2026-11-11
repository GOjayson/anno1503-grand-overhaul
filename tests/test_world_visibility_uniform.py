"""Uniform chart spans match an independent per-pixel projection oracle.

These isolated surfaces use real Windows page guards and synthetic native
bindings. They do not measure Anno FPS or replace an actual game check.
"""
import ctypes as C
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_world_visibility_exploration import NATIVE, ROOT, SOURCE

EXTRA = r'''
static void uniformPattern(uint32_t pattern,uint32_t cells){
 for(uint32_t z=0;z<cells;z++)for(uint32_t x=0;x<cells;x++){
  int known=pattern==1u||(pattern==2u&&((x+z)&1u))||
   (pattern==3u&&((x>cells/8u&&x<cells/2u&&z>cells/3u&&z<cells*2u/3u)||
                   (x>cells*3u/4u&&z<cells/4u)))||
   (pattern==4u&&x!=cells/2u&&z!=cells/2u&&!(x%8u==7u&&z%8u==0u));
  if(known){uint32_t index=z*cells+x;bits[index>>3]|=(unsigned char)(1u<<(index&7u));}
 }
}
/* Per-pixel expected values use the native projection equation directly,
 * without the production run, summary or endpoint helpers. */
static int uniformPixels(void){
 float a,b,c,d,t0,t1,t2,t3;memcpy(&a,drawBytes+0xd8,4);memcpy(&b,drawBytes+0xdc,4);memcpy(&c,drawBytes+0xf8,4);memcpy(&d,drawBytes+0xfc,4);
 memcpy(&t0,drawBytes+0x108,4);memcpy(&t1,drawBytes+0x10c,4);memcpy(&t2,drawBytes+0x118,4);memcpy(&t3,drawBytes+0x11c,4);
 double determinant=(double)a*d-(double)c*b;
 for(uint32_t y=0;y<height;y++)for(uint32_t x=0;x<rowPixels;x++){
  uint32_t expected=originalPixel(x,y);
  if(x<viewWidth&&y<viewHeight){
   double u=7.0+x+0.5-(double)t0-t2,v=(double)t3-(11.0+y+0.5)-t1;
   double wx=(u*d-c*v)/determinant,wz=(a*v-u*b)/determinant;
   if(!bitAt((int32_t)floor(wx/8.0),(int32_t)floor(wz/8.0)))expected=0xff000000u;
  }
  if(wsU32(pixels+((size_t)y*rowPixels+x)*4u)!=expected)return 0;
 }
 return canaries();
}
__declspec(dllexport) int uniform_case(uint32_t which){
 uint32_t quarter=which%4u,zoom=(which/4u)%8u,phase=(which/32u)%8u,pattern=(which/256u)%5u,worldSize=256u<<(which/1280u);
 const float scales[8]={0.3f,0.7f,1.1f,2.3f,3.7f,8,16,32};
 const double offsets[8]={-8,-0.125,0,7.99999,8,8.125,worldSize-8.0,worldSize+0.125};
 prepare(111,75,128,103,67,worldSize,quarter,scales[zoom],offsets[phase],offsets[(phase+3u)%8u]);
 uniformPattern(pattern,worldSize>>3);uniformRuns=0;
 int result=!wsVisibilityApplyExploredSea(drawBytes,contextBytes)?1:!uniformPixels()?2:
  beginCalls!=1u||endCalls!=1u||pointCalls!=(worldSize>>3)*(worldSize>>3)?3:0;
 dispose();return result;
}
__declspec(dllexport) int uniform_large_case(uint32_t quarter,uint32_t pattern,uint32_t zoom){
 const uint32_t worldSize=2048u;float scale=zoom?32.0f:16.0f;
 float ax[4]={scale,scale,-scale,-scale},az[4]={-scale,scale,scale,-scale};
 float bx[4]={scale/2,-scale/2,-scale/2,scale/2},bz[4]={scale/2,scale/2,-scale/2,-scale/2};
 double determinant=(double)ax[quarter]*bz[quarter]-(double)az[quarter]*bx[quarter];
 double firstX=1024.125-1920.0*bz[quarter]/determinant-1025.0*az[quarter]/determinant;
 double firstZ=1023.875+1920.0*bx[quarter]/determinant+1025.0*ax[quarter]/determinant;
 prepare(3840,2050,3856,3840,2050,worldSize,quarter,scale,firstX,firstZ);
 uniformPattern(pattern,worldSize>>3);uniformRuns=0;
 int result=!wsVisibilityApplyExploredSea(drawBytes,contextBytes)?1:!uniformPixels()?2:
  beginCalls!=1u||endCalls!=1u||pointCalls!=65536u?3:0;
 /* The entire viewport is inside a single uniform World-sized block. This
  * checks eliminated projection work, without a machine-speed assertion. */
 if(!result&&pattern<2u&&uniformRuns>2050u)result=4;
 dispose();return result;
}
'''


def uniform_fixture():
    source = (NATIVE / 'start_visibility_exploration.inc').read_text(encoding='utf-8')
    marker = 'for(uint32_t x=0;x<width;){'
    if source.count(marker) != 1:
        raise AssertionError('The production pixel-run loop changed; review its work counter.')
    source = source.replace(marker, marker + 'uniformRuns++;')
    fixture = SOURCE.replace('#include "start_visibility_exploration.inc"',
                             'static uint64_t uniformRuns;\n' + source)
    return fixture + EXTRA


@unittest.skipUnless(os.name == 'nt', 'Uniform exploration surfaces use Windows memory guards.')
class UniformExplorationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = ROOT / '.local/toolchain/ziglang/zig.exe'
        if not compiler.is_file():
            raise unittest.SkipTest('The reviewed local native toolchain is unavailable.')
        cls.temp = tempfile.TemporaryDirectory(prefix='anno1503-uniform-sea-')
        directory = Path(cls.temp.name)
        source, dll = directory / 'uniform.c', directory / 'uniform.dll'
        source.write_text(uniform_fixture(), encoding='utf-8')
        result = subprocess.run([str(compiler), 'cc', '-target', 'x86_64-windows-gnu',
                                 '-shared', '-O2', '-std=c11', '-I', str(NATIVE),
                                 str(source), '-o', str(dll)], capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.lib = C.CDLL(str(dll))
        cls.lib.uniform_case.argtypes = [C.c_uint32]
        cls.lib.uniform_large_case.argtypes = [C.c_uint32, C.c_uint32, C.c_uint32]
        cls.lib.sea_guard_case.argtypes = [C.c_uint32]

    @classmethod
    def tearDownClass(cls):
        import _ctypes
        _ctypes.FreeLibrary(cls.lib._handle)
        del cls.lib
        cls.temp.cleanup()

    def check_pattern(self, pattern):
        for world in range(4):
            for phase in range(8):
                for zoom in range(8):
                    for rotation in range(4):
                        case = rotation + zoom * 4 + phase * 32 + pattern * 256 + world * 1280
                        with self.subTest(world=256 << world, phase=phase, zoom=zoom, rotation=rotation):
                            self.assertEqual(self.lib.uniform_case(case), 0)

    def test_unknown_and_known_blocks_match_pixel_oracle_at_negative_and_world_edges(self):
        self.check_pattern(0)
        self.check_pattern(1)

    def test_checkerboard_mixed_leaves_match_pixel_oracle_at_all_fractional_rotations(self):
        self.check_pattern(2)

    def test_clustered_chart_history_and_thin_unknown_channels_do_not_leak_pixels(self):
        self.check_pattern(3)
        self.check_pattern(4)

    def test_full_size_uniform_viewports_eliminate_repeated_cell_projections(self):
        for rotation in range(4):
            for pattern in (0, 1):
                for zoom in range(2):
                    with self.subTest(rotation=rotation, pattern=pattern, zoom=zoom):
                        self.assertEqual(self.lib.uniform_large_case(rotation, pattern, zoom), 0)

    def test_full_size_mixed_and_clustered_viewports_preserve_all_pixels_and_row_padding(self):
        for rotation in range(4):
            for pattern in (2, 3, 4):
                for zoom in range(2):
                    with self.subTest(rotation=rotation, pattern=pattern, zoom=zoom):
                        self.assertEqual(self.lib.uniform_large_case(rotation, pattern, zoom), 0)

    def test_ownership_page_protection_and_failure_black_contracts_still_hold(self):
        for case in range(18):
            with self.subTest(case=case):
                self.assertEqual(self.lib.sea_guard_case(case), 0)


if __name__ == '__main__':
    unittest.main()
