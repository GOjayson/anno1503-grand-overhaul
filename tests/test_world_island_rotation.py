"""Rotation codecs and native input comparisons; never launches Anno."""
import ctypes as C
import hashlib
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from anno1503_overhaul.world_island_catalogue import _chunks,catalogue_rows,template_resolver
from anno1503_overhaul.world_island_rotation import rotate_island,definition_dimensions,validate_rotation_metadata,IslandRotationError
NATIVE=ROOT/'src/anno1503_overhaul/native/world_options'


def chunk(tag,raw):return tag.encode().ljust(12,b'\0')+struct.pack('<I',len(raw))+raw


def fixture(extra=b''):
    n=64
    heights=bytearray(n*n)
    for y in range(7,24):heights[y*n+5:y*n+21]=bytes([64])*16
    heights[3*n]=5
    gfx=b''.join(struct.pack('<H',0x2150|(i&3))for i in range(n*n))
    cells=bytes(1 if h>=48 else 0 for h in heights)
    geometry=struct.pack('<4HI',0,0,n,n,0)
    body=chunk('INFO',bytes([2])+bytes(11))
    body+=chunk('HEIGHT',struct.pack('<HHBB',0,0,n,n)+heights)
    body+=chunk('GFXID',struct.pack('<HHBB',0,0,n,n)+gfx)
    body+=chunk('FRUCHTBAR',cells)+chunk('ANBAU',b'GETREIDE\0')
    body+=chunk('GELAENDE',struct.pack('<HHBBHBBbb',0,0,64,64,1585|(1<<14),0x23,48,20,21))
    body+=chunk('FLUESSE',struct.pack('<HHBBHBBbb',8,8,8,8,2708,0,0,2,1))
    body+=chunk('BERGWERK2',b'ENTRY\0'+struct.pack('<HI',4,17|(19<<12)))
    ore=struct.pack('<I3fHHI',1560<<14,15.5,17.5,4.0,400,0,0)
    whale=struct.pack('<I3f',1559<<14,5.5,2.5,0)+b'WHALE\0'+struct.pack('<H',18)
    whale+=b''.join(struct.pack('<HbbH',0,dx,dy,ident)for dx,dy,ident in ((-6,-10,17),(-11,-2,18),(5,-7,19)))
    body+=chunk('OCCUR',b'ENTRY2'+struct.pack('<H',len(ore))+ore+b'ENTRY2'+struct.pack('<H',len(whale))+whale)+extra
    return chunk('ANNO',chunk('WARETYPE',b'fixture\0')+chunk('INSEL5',geometry+body))


def parts(raw):
    end=16+struct.unpack_from('<I',raw,12)[0]
    island=next(p for tag,p in _chunks(raw,16,end)if tag==b'INSEL5')
    return list(_chunks(island,12,len(island)))


def vertices(raw,n=64):
    grid=bytearray((n+1)*(n+1));seen=bytearray(len(grid))
    for tag,p in parts(raw):
        if tag!=b'HEIGHT':continue
        x,y,w,h=struct.unpack_from('<HHBB',p)
        if x+w>n+1 or y+h>n+1:raise AssertionError('Invalid native vertex tile.')
        for yy in range(h):
            for xx in range(w):
                at=(y+yy)*(n+1)+x+xx
                if seen[at]:raise AssertionError('Overlapping native vertex tile.')
                seen[at]=1;grid[at]=p[6+yy*w+xx]
    return grid


PREFIX=r'''
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
typedef struct WSBuffer{unsigned char*data;uint32_t size,capacity;}WSBuffer;
static uint16_t wsU16(const void*p){uint16_t v;memcpy(&v,p,2);return v;}
static uint32_t wsU32(const void*p){uint32_t v;memcpy(&v,p,4);return v;}
static void wsPut16(void*p,uint16_t v){memcpy(p,&v,2);}
static void wsPut32(void*p,uint32_t v){memcpy(p,&v,4);}
static int wsTag(const unsigned char*p,const char*t){size_t n=strlen(t);return n<=12&&!memcmp(p,t,n)&&(n==12||!p[n]);}
static int wsAppend(WSBuffer*b,const void*p,uint32_t n){if(n>b->capacity-b->size)return 0;memcpy(b->data+b->size,p,n);b->size+=n;return 1;}
static int wsChunk(WSBuffer*b,const char*t,const void*p,uint32_t n){unsigned char h[16]={0};memcpy(h,t,strlen(t));wsPut32(h+12,n);return wsAppend(b,h,16)&&wsAppend(b,p,n);}
static void wsMessage(char*out,uint32_t cap,const char*t){if(out&&cap)snprintf(out,cap,"%s",t);}
#include "island_rotation_codec.inc"
#ifdef _WIN32
#define API __declspec(dllexport)
#else
#define API __attribute__((visibility("default")))
#endif
API uint32_t bake(const unsigned char*src,uint32_t size,uint32_t n,uint32_t q,unsigned char*out,uint32_t cap){
 WSBuffer b={out,0,cap};char error[512]={0};return wsRotationBake(src,size,n,q,&b,error,sizeof error)?b.size:0;
}
'''


class NativeRotationCodec(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler=ROOT/'.local/toolchain/ziglang/zig.exe'
        if os.name=='nt' and compiler.is_file():command=[str(compiler),'cc'];suffix='.dll';extra=[]
        else:
            found=shutil.which('cc')or shutil.which('clang')or shutil.which('gcc')
            if not found:raise unittest.SkipTest('A native C compiler is unavailable.')
            command=[found];suffix='.so';extra=['-fPIC']
        cls.tmp=tempfile.TemporaryDirectory(prefix='anno-rotation-codec-');folder=Path(cls.tmp.name)
        source=folder/'fixture.c';source.write_text(PREFIX,encoding='utf-8');dll=folder/('fixture'+suffix)
        result=subprocess.run(command+['-shared','-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',*extra,
            '-I',str(NATIVE),str(source),'-o',str(dll)],capture_output=True,text=True,timeout=90)
        if result.returncode:raise AssertionError(result.stdout+result.stderr)
        cls.lib=C.CDLL(str(dll));cls.lib.bake.argtypes=[C.c_void_p,C.c_uint32,C.c_uint32,C.c_uint32,C.c_void_p,C.c_uint32];cls.lib.bake.restype=C.c_uint32
    @classmethod
    def tearDownClass(cls):
        if os.name=='nt':
            import _ctypes
            _ctypes.FreeLibrary(cls.lib._handle)
        cls.tmp.cleanup()
    def native(self,raw,q,n=64,cap=None):
        cap=len(raw)*2+65536 if cap is None else cap
        src=C.create_string_buffer(raw,len(raw));out=(C.c_ubyte*(cap+16))();C.memset(out,0xa5,len(out))
        size=self.lib.bake(src,len(raw),n,q,out,cap)
        self.assertEqual(src.raw,raw);self.assertEqual(bytes(out)[cap:],bytes([0xa5])*16)
        return bytes(out)[:size]if size else None
    def test_full_codec_matches_reference_and_preserves_nonzero_end_vertices(self):
        raw=fixture();dims={1585:(3,4),2708:(4,4)}
        for q in (1,2,3):
            result=self.native(raw,q);self.assertIsNotNone(result)
            self.assertEqual(result,rotate_island(raw,q,dims))
            grid=vertices(result)
            nx,ny=((61,0),(64,61),(3,64))[q-1]
            self.assertEqual(grid[ny*65+nx],5)
            self.assertEqual(sum(v>=48 for v in grid),272)
    def test_unknown_scenario_chunks_partial_grids_and_invalid_inputs_refuse(self):
        for raw,q,n in ((fixture(chunk('PROD2',b'')),1,64),(fixture()[:-1],1,64),
                        (fixture(),0,64),(fixture(),4,64),(fixture(),1,80)):
            with self.subTest(q=q,n=n,length=len(raw)):self.assertIsNone(self.native(raw,q,n))
        self.assertIsNone(self.native(fixture(),1,cap=32))
        bad=fixture().replace(b'WHALE\0\x12\0',b'WHALE\0\x11\0')
        self.assertIsNone(self.native(bad,1))
    def test_malformed_landscape_definition_and_nonfinite_occurrence_refuse(self):
        raw=fixture();a=raw.index(struct.pack('<HBBbb',1585|(1<<14),0x23,48,20,21));bad=bytearray(raw);struct.pack_into('<H',bad,a,16383)
        self.assertIsNone(self.native(bytes(bad),1))
        at=raw.index(b'ENTRY2')+8+4;bad=bytearray(raw);struct.pack_into('<f',bad,at,float('nan'))
        self.assertIsNone(self.native(bytes(bad),1))
    def test_all_reviewed_native_templates_match_independent_reference(self):
        host=ROOT/'.local/game-copies/World Settings'
        if not (host/'Anlagen.dat').is_file():raise unittest.SkipTest('Exact private HE island/data inputs are unavailable.')
        read=template_resolver(host,ROOT/'.local/baselines/world_settings/assets')
        catalogue=(ROOT/'legacy/world_settings/developer/source/engine_resume/ai_food/experiment_runtime/world_catalogue.h').read_bytes()
        dims=definition_dimensions(host/'Anlagen.dat')
        header=(NATIVE/'island_rotation_plan.h').read_bytes();values=re.search(rb'wsTemplateCanRotate\[444\]\s*=\s*\{([^}]+)\}',header)
        enabled=[int(v)for v in re.findall(rb'\d+',values[1])]
        checked=0
        for row in catalogue_rows(catalogue):
            if not enabled[row['index']]:continue
            raw=read(row['path']);self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256'])
            for q in (1,2,3):
                with self.subTest(index=row['index'],q=q):
                    self.assertEqual(self.native(raw,q,row['fields'][0]),rotate_island(raw,q,dims))
                    checked+=1
        self.assertEqual(checked,256*3)


class RotationMetadata(unittest.TestCase):
    def test_projection_matches_selected_base_and_addon_definitions(self):
        host=ROOT/'.local/game-copies/World Settings'
        if not (host/'Anlagen.dat').is_file():raise unittest.SkipTest('Exact private HE island/data inputs are unavailable.')
        catalogue=(ROOT/'legacy/world_settings/developer/source/engine_resume/ai_food/experiment_runtime/world_catalogue.h').read_bytes()
        header=(NATIVE/'island_rotation_plan.h').read_bytes();dims_header=(NATIVE/'island_rotation_definitions.h').read_bytes()
        read=template_resolver(host,ROOT/'.local/baselines/world_settings/assets')
        variants=[definition_dimensions(host/name)for name in ('Anlagen.dat','Anlagen.addon')]
        proof=validate_rotation_metadata(catalogue,header,dims_header,read,variants)
        self.assertEqual((proof['ordinary_templates'],proof['rotatable_templates'],proof['landscape_definitions']),(269,256,281))
        self.assertEqual(proof['nonzero_boundary_templates_retained_unrotated'],13)
        for ph,dh in ((header.replace(b'1,1,1',b'0,1,1',1),dims_header),(header,dims_header+b'changed')):
            with self.assertRaises(IslandRotationError):validate_rotation_metadata(catalogue,ph,dh,read,variants)


if __name__=='__main__':unittest.main()
