"""Cross-module View Scene import proof and isolated transaction fixtures.

No game process, UI, installation or Food gameplay is exercised.
"""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import ctypes as C
import hashlib
import importlib.util
import json
import struct
import subprocess
import unittest
import os

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from anno1503_overhaul import world_options_visibility_hooks as proposal
import test_world_visibility_hooks as old
from anno1503_overhaul.world_runtime_build import PE, RuntimeBuildError
VIEW_SHA='ed1c13167d6fc9fd220f074da52bb63d396b6a11b722c48a44a2babd8c6f4aef'
SCENE_SHA='f7d0685cf6156ff25c518f2f558863b351d7738280467e48dd585a1fefa9537a'
sha=lambda raw:hashlib.sha256(raw).hexdigest()

def fixture_images():
    view=old.fixture_pe(control=True)
    scene=old.fixture_pe(control=True,image_base=0x280000000)
    vp,sp=PE(view),PE(scene)
    def put(data,pe,rva,fmt,*args):struct.pack_into(fmt,data,pe.offset(rva,struct.calcsize(fmt)),*args)
    def data_at(data,pe,rva,raw):data[pe.offset(rva,len(raw)):pe.offset(rva,len(raw))+len(raw)]=raw
    put(view,vp,vp.optional+112+8,'II',0xa0300,40)
    put(view,vp,0xa0300,'5I',0xa0400,0,0,0xa0500,0xa1090)
    data_at(view,vp,0xa0500,b'AnnoScene.dll\0')
    put(view,vp,0xa0400,'3Q',0xa0640,0xa0600,0)
    data_at(view,vp,0xa0600,b'\0\0CreateAnnoSceneInstance\0')
    data_at(view,vp,0xa0640,b'\0\0CreateAnnoSaveGameInstance\0')
    put(view,vp,0xa1090,'3Q',0xa0640,0xa0600,0)
    put(scene,sp,sp.optional+112,'II',0xa0100,0x100)
    put(scene,sp,0xa0100,'IIHH7I',0,0,0,0,0xa0190,1,1,1,0xa0140,0xa0150,0xa0160)
    put(scene,sp,0xa0140,'I',0x11a0)
    put(scene,sp,0xa0150,'I',0xa0170)
    put(scene,sp,0xa0160,'H',0)
    data_at(scene,sp,0xa0170,b'CreateAnnoSceneInstance\0')
    data_at(scene,sp,0xa0190,b'AnnoScene.dll\0')
    put(scene,sp,sp.optional+112+24,'II',0x100000,12)
    put(scene,sp,0x100000,'3I',0x11a0,0x1362,0x100100)
    data_at(scene,sp,0x11a0,proposal.FACTORY_HEAD)
    return {'View.dll':bytes(view),'AnnoScene.dll':bytes(scene)}

class ImportPreimageTests(unittest.TestCase):
    def verify(self,images):return proposal.verify_import_visibility_preimages(images,{k:sha(v)for k,v in images.items()})
    def test_separate_native_owners_and_raw_thunk_not_absolute_address(self):
        images=fixture_images();before=dict(images);proof=self.verify(images);row=proof['import_dispatch_preimages'][0]
        self.assertEqual(images,before);self.assertEqual(proof['dispatch_count'],1)
        self.assertEqual((row['owner_module'],row['slot_rva'],row['imported_module'],row['original_target_rva']),('View.dll',0xa1098,'AnnoScene.dll',0x11a0))
        self.assertFalse(row['disk_thunk_is_absolute_function_address'])
        self.assertEqual(bytes.fromhex(row['disk_preimage']),struct.pack('<Q',0xa0600))
        self.assertNotEqual(PE(images['View.dll']).unpack('<Q',PE(images['View.dll']).optional+24),PE(images['AnnoScene.dll']).unpack('<Q',PE(images['AnnoScene.dll']).optional+24))
    def test_exact_local_native_images_when_available(self):
        folder=ROOT/'.local/game-copies/World Settings'
        if not all((folder/n).is_file() for n in ('View.dll','AnnoScene.dll')):
            self.skipTest('Exact local native HE copies are unavailable.')
        images={n:(folder/n).read_bytes()for n in ('View.dll','AnnoScene.dll')}
        result=proposal.verify_import_visibility_preimages(images,{'View.dll':VIEW_SHA,'AnnoScene.dll':SCENE_SHA})
        self.assertEqual(result['import_dispatch_preimages'][0]['hint_name_rva'],0xca354)
    def test_hashes_cannot_substitute_and_other_byte_changes_refuse(self):
        images=fixture_images();pins={k:sha(v)for k,v in images.items()}
        for name in images:
            changed=dict(images);data=bytearray(changed[name]);data[-1]^=1;changed[name]=bytes(data)
            with self.assertRaises(RuntimeBuildError):proposal.verify_import_visibility_preimages(changed,pins)
        with self.assertRaises(RuntimeBuildError):proposal.verify_import_visibility_preimages(images,{'View.dll':pins['AnnoScene.dll'],'AnnoScene.dll':pins['View.dll']})
    def test_named_import_and_thunk_faults_refuse_even_with_fixture_hash(self):
        faults=[(0xa0500,b'X'),(0xa0602,b'X'),(0xa0300,bytes(4)),(0xa0300+16,struct.pack('<I',0xa1098)),
                (0xa0408,struct.pack('<Q',1<<63)),(0xa1098,struct.pack('<Q',0x2800011a0)),
                (0xa0408,bytes(8)),(0xa0300+12,struct.pack('<I',0x101000))]
        for at,value in faults:
            with self.subTest(at=at,value=value):
                images=fixture_images();raw=bytearray(images['View.dll']);pe=PE(raw);raw[pe.offset(at,len(value)):pe.offset(at,len(value))+len(value)]=value;images['View.dll']=bytes(raw)
                with self.assertRaises(RuntimeBuildError):self.verify(images)
    def test_export_name_forwarder_middle_function_or_body_change_refuse(self):
        for at,value in [(0xa0170,b'X'),(0xa0140,struct.pack('<I',0xa0180)),(0xa0140,struct.pack('<I',0x11a1)),(0x100000,struct.pack('<I',0x11a1)),(0x11a0,b'\xe9')]:
            with self.subTest(at=at):
                images=fixture_images();raw=bytearray(images['AnnoScene.dll']);pe=PE(raw);raw[pe.offset(at,len(value)):pe.offset(at,len(value))+len(value)]=value;images['AnnoScene.dll']=bytes(raw)
                with self.assertRaises(RuntimeBuildError):self.verify(images)
    def test_old_native_dispatch_family_stays_separate_from_the_one_import(self):
        self.assertEqual(len(old.NATIVE_POINTERS),11)
        self.assertEqual(len(old.call_visibility.CALLS),16)
        self.assertEqual(proposal.IMPORT_HOOKS,(
            ('View.dll',0xa1098,'AnnoScene.dll','CreateAnnoSceneInstance',
             0x11a0,'WorldSettingsVisibilityCreateSceneFromView'),))
        include=(ROOT/'src/anno1503_overhaul/native/world_options/visibility_hooks.inc').read_text()
        native_rows=include.split('static const WSVisibilityHook wsVisibilityHookPlan[]={',1)[1].split('};',1)[0]
        self.assertEqual(native_rows.count('{L"'),11)
        self.assertNotIn('View.dll',native_rows)
        self.assertEqual(include.count('{L"View.dll",'),1)

class NativeImportTransactionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reuse the shared fixture without changing any imported module globals.
        old.VisibilityNativePreparationTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):
        import _ctypes
        if os.name=='nt':_ctypes.FreeLibrary(cls.lib._handle)
        else:_ctypes.dlclose(cls.lib._handle)
        cls.temp.cleanup()
    def setUp(self):self.lib.fixture_reset()
    def buffers(self):
        return tuple(sha(C.string_at(base,size))for base,size in [(self.lib.fixture_view_base(),0xe0000),(self.lib.fixture_scene_base(),0x110000),(self.lib.fixture_base(),0x110000),(self.lib.fixture_frame_base(),0x110000),(self.lib.fixture_display_base(),0x1000000)])
    def test_cross_module_pointer_is_prepared_committed_detected_and_restored(self):
        before=self.buffers();self.assertEqual(self.lib.fixture_prepare(198),1);self.assertEqual(self.buffers(),before);self.assertEqual(self.lib.fixture_count(),210)
        index=209;self.assertEqual(self.lib.fixture_address(index),self.lib.fixture_view_base()+0xa1098)
        self.assertEqual(C.string_at(self.lib.fixture_before(index),8),struct.pack('<Q',self.lib.fixture_scene_base()+0x11a0))
        self.assertNotEqual(C.string_at(self.lib.fixture_before(index),8),struct.pack('<Q',self.lib.fixture_view_base()+0x11a0))
        self.lib.fixture_publish_only();self.assertEqual(self.lib.WorldSettingsVisibilityPatchStatus(),28);self.assertEqual(self.lib.WorldSettingsEnginePatchStatus(),173)
        self.lib.fixture_view_mutate(0xa1098);self.assertEqual(self.lib.WorldSettingsVisibilityPatchStatus(),0);self.assertEqual(self.lib.WorldSettingsEnginePatchStatus(),0)
        self.lib.fixture_view_mutate(0xa1098);self.lib.fixture_restore_only();self.assertEqual(self.buffers(),before)
    def test_missing_module_hash_export_callback_and_readability_fail_closed(self):
        for fault in range(1,12):
            with self.subTest(fault=fault):
                self.lib.fixture_reset();self.lib.fixture_view_fault(fault);before=self.buffers()
                self.assertEqual(self.lib.fixture_prepare(198),0);self.assertEqual(self.buffers(),before);self.assertEqual(self.lib.WorldSettingsVisibilityPatchStatus(),0)
    def test_descriptor_name_lookup_and_resolved_target_fail_closed(self):
        for at in (0x80,0x84,0x98,0x110,0x114,0x200,0x20c,0x210,0x308,0x400,0x542,0xa1098):
            with self.subTest(at=at):
                self.lib.fixture_reset();self.lib.fixture_view_mutate(at);before=self.buffers()
                self.assertEqual(self.lib.fixture_prepare(198),0);self.assertEqual(self.buffers(),before)
        self.lib.fixture_reset();self.lib.fixture_scene_mutate(0x11a0);before=self.buffers();self.assertEqual(self.lib.fixture_prepare(198),0);self.assertEqual(self.buffers(),before)
    def test_import_overlap_and_capacity_refuse_before_publication(self):
        for offset in (0,7):
            self.lib.fixture_reset();self.lib.fixture_view_overlap(offset);before=self.buffers()
            self.assertEqual(self.lib.fixture_prepare(198),0);self.assertEqual(self.buffers(),before)
        for count in (199,210,211,0xffffffff):
            self.lib.fixture_reset();self.assertEqual(self.lib.fixture_prepare(count),0);self.assertEqual(self.lib.fixture_count(),count)

if __name__=='__main__':unittest.main()
