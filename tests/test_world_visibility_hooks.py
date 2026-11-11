"""Visibility dispatch preflight and guarded staging; no Anno execution.

Synthetic PE images and native API spies exercise the actual reviewed helper.
Neither the images nor the C buffers are game binaries or live game memory.
"""
import ctypes as C
import hashlib
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from anno1503_overhaul import world_options_visibility_hooks as visibility
from anno1503_overhaul import world_options_visibility_calls as call_visibility
from anno1503_overhaul.world_options import ROOT, authored
from anno1503_overhaul.world_runtime_build import PE, RuntimeBuildError


SOURCE = ROOT / 'legacy/world_settings' / visibility.INSTALLER
DISPATCH = tuple((slot, target) for slot, target, _ in visibility.HOOKS)
RENDER_DISPATCH = tuple((slot, target) for slot, target, _ in visibility.RENDER_HOOKS)
CONTROL_DISPATCH = tuple((slot, target) for slot, target, _ in visibility.CONTROL_HOOKS)
POINTERS = (tuple(('AnnoWelt.dll', slot, target) for slot, target in DISPATCH) +
            tuple(('AnnoDisplay.dll', slot, target) for slot, target in RENDER_DISPATCH) +
            tuple(('AnnoFrame.dll', slot, target) for slot, target in CONTROL_DISPATCH))
COMPONENTS = len(POINTERS) + len(call_visibility.CALLS)
TRANSACTION_CAPACITY = 36 + 173
PREPARED_COMPONENTS = 9 + len(call_visibility.CALLS) + 173


def fixture_pe(profile=0, image_base=0x180000000, renderer=False, control=False):
    """Fixture-only digests bind different synthetic profile envelopes."""
    sections = ((b'.text', 0x1000, 0x8f000 if control else 0xdf000, 0x400, 0x60000020),
                (b'.rdata', 0xf60000 if renderer else 0xa0000 if control else 0xf0000, 0x10000, 0xdf400, 0x40000040),
                (b'.pdata', 0x100000, 0x1000, 0xef400, 0x40000040))
    data = bytearray(0xf0400)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 60, 0x80)
    data[0x80:0x84] = b'PE\0\0'
    struct.pack_into('<HH', data, 0x84, 0x8664, len(sections))
    struct.pack_into('<H', data, 0x94, 240)
    optional = 0x98
    struct.pack_into('<H', data, optional, 0x20b)
    struct.pack_into('<Q', data, optional + 24, image_base)
    struct.pack_into('<II', data, optional + 56, 0xf70000 if renderer else 0x101000, 0x400)
    struct.pack_into('<I', data, optional + 108, 16)
    dispatch = RENDER_DISPATCH if renderer else CONTROL_DISPATCH if control else DISPATCH
    targets = sorted({target for _, target in dispatch})
    struct.pack_into('<II', data, optional + 112 + 3 * 8, 0x100000, len(targets) * 12)
    for index, (name, rva, size, raw, flags) in enumerate(sections):
        at = optional + 240 + index * 40
        data[at:at + len(name)] = name
        struct.pack_into('<IIII', data, at + 8, size, rva, size, raw)
        struct.pack_into('<I', data, at + 36, flags)
    data[0x300] = profile
    pe = PE(data)
    for slot, target in dispatch:
        struct.pack_into('<Q', data, pe.offset(slot, 8), image_base + target)
    for index, target in enumerate(targets):
        data[pe.offset(target, 16):pe.offset(target, 16) + 16] = b'\xc3' + b'\x90' * 15
        unwind = 0x100100 + index * 4
        struct.pack_into('<III', data, pe.offset(0x100000 + index * 12, 12),
                         target, target + 16, unwind)
        data[pe.offset(unwind, 4):pe.offset(unwind, 4) + 4] = b'\x01\0\0\0'
    return data


def verify_fixture(data):
    return visibility.verify_visibility_preimages(bytes(data), hashlib.sha256(data).hexdigest())


class VisibilityPreimageTests(unittest.TestCase):
    fixture = staticmethod(fixture_pe)
    dispatch = DISPATCH
    verifier = staticmethod(visibility.verify_visibility_preimages)

    def verify(self, data):
        return self.verifier(bytes(data), hashlib.sha256(data).hexdigest())

    def test_separate_profile_hashes_and_all_original_dispatch_targets(self):
        inputs = [bytes(self.fixture(0)), bytes(self.fixture(1, 0x280000000))]
        pins = [hashlib.sha256(data).hexdigest() for data in inputs]
        self.assertNotEqual(*pins)
        for index, (data, pin) in enumerate(zip(inputs, pins)):
            before = bytes(data)
            result = self.verifier(data, pin)
            self.assertEqual(result['machine'], 'AMD64')
            self.assertEqual(result['pointer_bytes'], 8)
            self.assertEqual(result['dispatch_count'], len(self.dispatch))
            self.assertEqual([(row['slot_rva'], row['original_target_rva'])
                              for row in result['dispatch_preimages']], list(self.dispatch))
            self.assertTrue(result['original_functions_not_patched'])
            self.assertEqual(data, before)
            with self.assertRaisesRegex(RuntimeBuildError, 'exact reviewed native'):
                self.verifier(data, pins[1 - index])

    def test_unrelated_image_mutation_is_rejected_before_interpreting_dispatch(self):
        data = self.fixture()
        expected = hashlib.sha256(data).hexdigest()
        data[-1] ^= 1
        with self.assertRaisesRegex(RuntimeBuildError, 'exact reviewed native'):
            self.verifier(bytes(data), expected)

    def test_wrong_dispatch_preimage_is_rejected_even_with_fixture_digest(self):
        for slot, target in self.dispatch:
            with self.subTest(slot=hex(slot)):
                data = self.fixture()
                struct.pack_into('<Q', data, PE(data).offset(slot, 8), 0x180000000 + target + 1)
                with self.assertRaisesRegex(RuntimeBuildError, 'dispatch preimage'):
                    self.verify(data)

    def test_non_amd64_or_non_pe32plus_is_rejected(self):
        for offset, value in ((0x84, 0x14c), (0x98, 0x10b)):
            with self.subTest(offset=offset):
                data = self.fixture()
                struct.pack_into('<H', data, offset, value)
                with self.assertRaisesRegex(RuntimeBuildError, 'AMD64'):
                    self.verify(data)

    def test_missing_function_and_middle_of_function_targets_are_rejected(self):
        for shift in (-1, 1):
            with self.subTest(shift=shift):
                data = self.fixture()
                pe = PE(data)
                at = pe.offset(0x100000, 12)
                begin, end, unwind = struct.unpack_from('<III', data, at)
                struct.pack_into('<III', data, at, begin + shift, end, unwind)
                with self.assertRaisesRegex(RuntimeBuildError, 'complete native function'):
                    self.verify(data)
        data = self.fixture()
        struct.pack_into('<II', data, PE(data).optional + 112 + 3 * 8, 0, 0)
        with self.assertRaisesRegex(RuntimeBuildError, 'exception-function table'):
            self.verify(data)

    def test_data_slots_must_be_nonexecutable_and_target_must_be_executable(self):
        for section, flags in ((0, 0x40000040), (1, 0x60000020)):
            with self.subTest(section=section):
                data = self.fixture()
                struct.pack_into('<I', data, PE(data).optional + 240 + section * 40 + 36, flags)
                with self.assertRaisesRegex(RuntimeBuildError, 'complete native function'):
                    self.verify(data)

    def test_invalid_function_end_duplicate_start_or_unmapped_unwind_is_rejected(self):
        for fault in ('empty', 'reversed', 'outside-code', 'duplicate', 'unwind'):
            with self.subTest(fault=fault):
                data = self.fixture()
                pe = PE(data)
                at = pe.offset(0x100000, 12)
                begin, end, unwind = struct.unpack_from('<III', data, at)
                if fault == 'empty':
                    end = begin
                elif fault == 'reversed':
                    end = begin - 1
                elif fault == 'outside-code':
                    end = 0xe0001
                elif fault == 'unwind':
                    unwind = 0x101000
                else:
                    struct.pack_into('<III', data, pe.offset(0x100000 + 12, 12), begin, end + 1, unwind)
                struct.pack_into('<III', data, at, begin, end, unwind)
                with self.assertRaises(RuntimeBuildError):
                    self.verify(data)


class RendererVisibilityPreimageTests(VisibilityPreimageTests):
    fixture = staticmethod(lambda profile=0, image_base=0x180000000:
                           fixture_pe(profile, image_base, renderer=True))
    dispatch = RENDER_DISPATCH
    verifier = staticmethod(visibility.verify_renderer_visibility_preimages)

    def test_reviewed_draw_slots_leave_native_dirty_notification_unhooked(self):
        self.assertEqual(visibility.RENDER_HOOKS, (
            (0xf638c0, 0x49410, 'WorldSettingsVisibilityRenderStatic180'),
            (0xf638c8, 0x49bd0, 'WorldSettingsVisibilityRenderStatic188'),
        ))
        # DD11+160 is a different five-argument dirty notification. Replacing
        # it with these six-argument sprite filters could leave cached pixels.
        include = authored('visibility_hooks.inc').decode()
        renderer_rows = [line for line in include.splitlines() if '{L"AnnoDisplay.dll",' in line]
        self.assertEqual(len(renderer_rows), 2)
        self.assertFalse(any('0xf638a0u' in line or '0x48df0u' in line for line in renderer_rows))

    def test_world_and_display_images_cannot_substitute_for_each_other(self):
        world, display = bytes(fixture_pe()), bytes(self.fixture())
        self.assertEqual(len(visibility.HOOKS), 5)
        self.assertEqual(len(visibility.RENDER_HOOKS), 2)
        for verifier, data in ((visibility.verify_visibility_preimages, display),
                               (self.verifier, world)):
            with self.subTest(verifier=verifier.__name__):
                with self.assertRaises(RuntimeBuildError):
                    verifier(data, hashlib.sha256(data).hexdigest())


class ControlVisibilityPreimageTests(VisibilityPreimageTests):
    fixture = staticmethod(lambda profile=0, image_base=0x180000000:
                           fixture_pe(profile, image_base, control=True))
    dispatch = CONTROL_DISPATCH
    verifier = staticmethod(visibility.verify_control_visibility_preimages)

    def test_both_native_clients_have_separate_queue_and_production_bindings(self):
        self.assertEqual(visibility.CONTROL_HOOKS, (
            (0xa7248, 0x78630, 'WorldSettingsVisibilityBuildingCommand'),
            (0xa7250, 0x785d0, 'WorldSettingsVisibilityShipQueue'),
            (0xa74f0, 0x7d340, 'WorldSettingsVisibilityBuildingCommand'),
            (0xa74f8, 0x7d230, 'WorldSettingsVisibilityShipQueue'),
        ))
        for data in (bytes(fixture_pe()), bytes(fixture_pe(renderer=True))):
            with self.assertRaises(RuntimeBuildError):
                self.verify(data)


class VisibilityStagingTests(unittest.TestCase):
    def test_staging_preserves_inputs_and_original_commit_rollback_thread_guards(self):
        original = SOURCE.read_bytes()
        files = {visibility.INSTALLER: original, 'unrelated-input': b'preserved'}
        visibility.apply_visibility_hooks(files)
        result = files[visibility.INSTALLER]
        self.assertEqual(SOURCE.read_bytes(), original)
        self.assertEqual(files['unrelated-input'], b'preserved')
        self.assertEqual(files['developer/source/engine_resume/ai_loader/visibility_hooks.inc'],
                         authored('visibility_hooks.inc'))
        # The suspension, world-lifetime recheck, apply, rollback and cleanup
        # implementations must stay byte-exact through this staging recipe.
        start = b'static void wsResumeThreads('
        end = b'__declspec(dllexport) int WorldSettingsInstallTestHooks(void){'
        self.assertEqual(result[result.index(start):result.index(end)],
                         original[original.index(start):original.index(end)])
        for token in (b'if(!wsPrepareVisibility(self,patches,&patchCount))goto done;',
                      b'9u+WS_ENGINE_PATCH_COUNT+WS_VISIBILITY_HOOK_COUNT',
                      b'wsVisibilityPatchStatusUnlocked()!=WS_VISIBILITY_HOOK_COUNT'):
            self.assertEqual(result.count(token), 1)
        for macro, count in ((b'POINTER', len(POINTERS)), (b'CALL', len(call_visibility.CALLS)), (b'HOOK', COMPONENTS)):
            self.assertIn(b'#define WS_VISIBILITY_' + macro + b'_COUNT ' + str(count).encode() + b'u', result)
        self.assertEqual(PREPARED_COMPONENTS + len(POINTERS), 209)
        self.assertLess(result.index(b'wsPrepareVisibility(self,patches,'),
                        result.index(b'if(!wsSuspendThreads('))
        pause = result.index(b'if(!wsSuspendThreads(')
        self.assertLess(pause, result.index(b'/* No loader, heap, file, bcrypt or import resolution', pause))
        self.assertLess(result.index(b'if(!wsEngineWorldAbsent())goto done;', pause),
                        result.index(b'int applied=wsApplyPatches(', pause))
        staged = dict(files)
        with self.assertRaises(RuntimeBuildError):
            visibility.apply_visibility_hooks(files)
        self.assertEqual(files, staged)

    def test_changed_or_duplicated_staging_anchor_is_refused_without_partial_output(self):
        original = SOURCE.read_bytes()
        anchors = (b'static char wsInstallError[512];',
                   b' ReleaseSRWLockShared(&wsInstallLock);return result;',
                   b'static int wsPrepareEngine(WSPatch *patches,uint32_t *patchCount){',
                   b' if(!wsPrepareEngine(patches,&patchCount))goto done;\n'
                   b' if(patchCount!=9u+WS_ENGINE_PATCH_COUNT){wsError("The complete nine-hook and expanded-engine transaction is incomplete.");goto done;}')
        for anchor in anchors:
            if b'\r\n' in original:
                anchor = anchor.replace(b'\n', b'\r\n')
            for changed in (original.replace(anchor, b'unsupported source anchor', 1), original + anchor):
                with self.subTest(anchor=anchor, duplicated=changed.endswith(anchor)):
                    files = {visibility.INSTALLER: changed}
                    with self.assertRaises(RuntimeBuildError):
                        visibility.apply_visibility_hooks(files)
                    self.assertEqual(files, {visibility.INSTALLER: changed})


def c_function(source, name):
    marker = source.index(name + '(')
    start = source.rfind('__declspec(dllexport)', 0, marker)
    brace = source.index('{', marker)
    at, depth = brace + 1, 1
    while depth:
        depth += (source[at] == '{') - (source[at] == '}')
        at += 1
    return source[start:at]


class VisibilityNativePreparationTests(unittest.TestCase):
    """Compile the actual include against isolated in-process C buffer spies."""
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='anno-visibility-hooks-', ignore_cleanup_errors=True)
        folder = Path(cls.temp.name)
        if os.name == 'nt' and (ROOT / '.local/toolchain/ziglang/zig.exe').is_file():
            compiler = [str(ROOT / '.local/toolchain/ziglang/zig.exe'), 'cc']
        else:
            found = shutil.which('cc') or shutil.which('gcc') or shutil.which('clang')
            if not found:
                cls.temp.cleanup()
                raise unittest.SkipTest('Native visibility preparation fixtures need a C compiler.')
            compiler = [found]
        files = {visibility.INSTALLER: SOURCE.read_bytes()}
        visibility.apply_visibility_hooks(files)
        status = c_function(files[visibility.INSTALLER].decode(), 'WorldSettingsEnginePatchStatus')
        include = authored('visibility_hooks.inc').decode()
        blob_files = {call_visibility.BLOBS: (ROOT / 'legacy/world_settings' / call_visibility.BLOBS).read_bytes()}
        call_visibility.apply_visibility_calls(blob_files)
        (folder / 'visibility_native_pins.h').write_text(
            'typedef struct {const wchar_t*name;unsigned char sha256[32];} WSVisibilityModulePin;\n'
            'static const WSVisibilityModulePin wsVisibilityModulePins[]={{L"AnnoDisplay.dll",{0}}};\n', encoding='ascii')
        source = r'''
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#ifndef _WIN32
#define __declspec(x)
#endif
typedef void* HMODULE; typedef void(*FARPROC)(void); typedef uint32_t DWORD;
typedef int SRWLOCK;
#define WS_VISIBILITY_POINTER_COUNT FIXTURE_POINTER_COUNT
#define WS_VISIBILITY_CALL_COUNT FIXTURE_CALL_COUNT
#define WS_VISIBILITY_HOOK_COUNT FIXTURE_COMPONENT_COUNT
#define WS_MAX_HOOKS FIXTURE_TRANSACTION_CAPACITY
#define WS_MAX_PATCH 32u
#define WS_ENGINE_MODULE_WORLD 0
#define WS_ENGINE_MODULE_FRAME 1
#define WS_ENGINE_MODULE_COUNT 2u
#define WS_ENGINE_PATCH_COUNT 173u
typedef struct {unsigned char*address;uint32_t length;unsigned char before[32],after[32];uint32_t page;int written;} WSPatch;
typedef struct {uint32_t module,rva,length;unsigned char after[1];} WSEngineEdit;
static unsigned char image[0x110000],frameImage[0x110000],sceneImage[0x110000],displayImage[0x1000000];
static HMODULE wsEngineModules[2]; static int wsInstallState; static SRWLOCK wsInstallLock;
static WSEngineEdit wsEngineEdits[WS_ENGINE_PATCH_COUNT];
static WSPatch prepared[WS_MAX_HOOKS];static uint32_t preparedCount,initialCount;
static int missingExport=-1,missingImage,unreadable=-1,badHash,displayFault;static char lastError[256];
static int wsError(const char*s){strncpy(lastError,s,sizeof lastError-1);return 0;}
static void AcquireSRWLockShared(SRWLOCK*p){(void)p;}
static void ReleaseSRWLockShared(SRWLOCK*p){(void)p;}
static int wsSpan(uint32_t o,uint32_t n,uint32_t size){return o<=size&&n<=size-o;}
static int wsModuleImage(HMODULE m,uint32_t*n){if(missingImage||(m==displayImage&&displayFault==1)||(m!=image&&m!=frameImage&&m!=sceneImage&&m!=displayImage))return 0;*n=m==displayImage?sizeof displayImage:sizeof image;return 1;}
static int wsHashModule(HMODULE m,const unsigned char*pin){(void)pin;return!badHash&&!(m==displayImage&&displayFault==2);}
'''
        source = source.replace('FIXTURE_POINTER_COUNT', str(len(POINTERS)) + 'u')
        source = source.replace('FIXTURE_CALL_COUNT', str(len(call_visibility.CALLS)) + 'u')
        source = source.replace('FIXTURE_COMPONENT_COUNT', str(COMPONENTS) + 'u')
        source = source.replace('FIXTURE_TRANSACTION_CAPACITY', str(TRANSACTION_CAPACITY) + 'u')
        source += blob_files[call_visibility.BLOBS].decode() + r'''
#define WS_BLOB_COUNT (sizeof(wsBlobs)/sizeof(wsBlobs[0]))
typedef struct {HMODULE module;unsigned char*allocation;int registered;} WSInstalledBlob;
static WSInstalledBlob wsInstalled[WS_BLOB_COUNT];
static unsigned char allocations[WS_BLOB_COUNT][0x10000];
static HMODULE GetModuleHandleW(const wchar_t*n){if(!wcscmp(n,L"AnnoFrame.dll"))return frameImage;if(!wcscmp(n,L"AnnoScene.dll"))return sceneImage;if(!wcscmp(n,L"AnnoDisplay.dll"))return displayFault==3?NULL:displayImage;return image;}
static int wsReadable(const void*p,size_t n){
 uintptr_t at=(uintptr_t)p,o=at-(uintptr_t)image;
 if(o<=sizeof image&&n<=sizeof image-o)return unreadable<0||o!=(uint32_t)unreadable;
 o=at-(uintptr_t)frameImage;if(o<=sizeof frameImage&&n<=sizeof frameImage-o)return 1;
 o=at-(uintptr_t)sceneImage;if(o<=sizeof sceneImage&&n<=sizeof sceneImage-o)return 1;
 o=at-(uintptr_t)displayImage;if(o<=sizeof displayImage&&n<=sizeof displayImage-o)return displayFault!=4;
 o=at-(uintptr_t)allocations;return o<=sizeof allocations&&n<=sizeof allocations-o;}
'''
        exports = list(dict.fromkeys([export for _, _, export in (*visibility.HOOKS, *visibility.RENDER_HOOKS, *visibility.CONTROL_HOOKS)]
                                    + [row[4] for row in call_visibility.CALLS]))
        for index in range(len(exports)):
            source += f'static void callback_{index}(void){{}}\n'
        source += 'static FARPROC GetProcAddress(HMODULE m,const char*n){(void)m;\n'
        for index, name in enumerate(exports):
            source += (f'if(!strcmp(n,"{name}"))'
                       f'return missingExport=={index}?NULL:callback_{index};\n')
        source += 'return NULL;}\n'
        source += include + '\n' + status + r'''
static WSPatch*fixture_call(uint32_t i){if(i>=WS_VISIBILITY_CALL_COUNT)return NULL;const WSVisibilityCall*c=&wsVisibilityCallPlan[i];unsigned char*owner=GetModuleHandleW(c->module);for(uint32_t j=0;j<WS_MAX_HOOKS;j++)if(prepared[j].address==owner+c->rva)return&prepared[j];return NULL;}
__declspec(dllexport) void fixture_reset(void){memset(image,0,sizeof image);memset(frameImage,0,sizeof frameImage);memset(sceneImage,0,sizeof sceneImage);memset(displayImage,0,sizeof displayImage);memset(prepared,0,sizeof prepared);memset(lastError,0,sizeof lastError);wsInstallState=0;missingExport=unreadable=-1;missingImage=badHash=displayFault=0;preparedCount=initialCount=0;
 memset(wsVisibilitySites,0,sizeof wsVisibilitySites);memset(wsVisibilityExpected,0,sizeof wsVisibilityExpected);memset(wsVisibilityLengths,0,sizeof wsVisibilityLengths);memset(wsVisibilityBridges,0,sizeof wsVisibilityBridges);memset(wsVisibilityCallbacks,0,sizeof wsVisibilityCallbacks);
 wsEngineModules[0]=image;wsEngineModules[1]=frameImage;
 for(uint32_t i=0;i<WS_VISIBILITY_POINTER_COUNT;i++){const WSVisibilityHook*h=&wsVisibilityHookPlan[i];unsigned char*owner=GetModuleHandleW(h->module);uintptr_t p=(uintptr_t)owner+h->target;memcpy(owner+h->slot,&p,8);}
 for(uint32_t j=0;j<WS_BLOB_COUNT;j++){
  const WSBlob*b=&wsBlobs[j];wsInstalled[j].module=GetModuleHandleW(b->module);wsInstalled[j].allocation=allocations[j];wsInstalled[j].registered=1;memcpy(allocations[j],b->code,b->codeSize);
  for(uint32_t k=0;k<b->importCount;k++){uintptr_t p=(uintptr_t)GetProcAddress(NULL,b->imports[k].name);memcpy(allocations[j]+b->imports[k].offset,&p,8);}
  for(uint32_t k=0;k<b->hookCount;k++){const WSHook*h=&b->hooks[k];WSPatch*p=&prepared[preparedCount++];p->address=(unsigned char*)wsInstalled[j].module+h->rva;p->length=h->length;memcpy(p->before,h->before,h->length);memcpy(p->address,h->before,h->length);memset(p->after,0x90,h->length);p->after[0]=h->call?0xe8:0xe9;int32_t d=(int32_t)((intptr_t)(allocations[j]+h->target)-(intptr_t)(p->address+5));memcpy(p->after+1,&d,4);}}
 for(uint32_t i=0;i<WS_ENGINE_PATCH_COUNT;i++){wsEngineEdits[i]=(WSEngineEdit){0,0x200+i,1,{0xa7}};WSPatch*p=&prepared[preparedCount++];p->address=image+0x200+i;p->length=1;p->after[0]=0xa7;}
 initialCount=preparedCount;}
__declspec(dllexport) uintptr_t fixture_base(void){return(uintptr_t)image;}
__declspec(dllexport) uint32_t fixture_image_bytes(void){return sizeof image;}
__declspec(dllexport) uintptr_t fixture_display_base(void){return(uintptr_t)displayImage;}
__declspec(dllexport) uintptr_t fixture_frame_base(void){return(uintptr_t)frameImage;}
__declspec(dllexport) uint32_t fixture_display_bytes(void){return sizeof displayImage;}
__declspec(dllexport) int fixture_prepare(uint32_t count){preparedCount=initialCount=count;return wsPrepareVisibility((HMODULE)1,prepared,&preparedCount);}
__declspec(dllexport) int fixture_null_argument(int which){uint32_t count=0;return wsPrepareVisibility((HMODULE)1,which==0?NULL:prepared,which==1?NULL:&count);}
__declspec(dllexport) uint32_t fixture_count(void){return preparedCount;}
__declspec(dllexport) uint32_t fixture_length(uint32_t i){return prepared[i].length;}
__declspec(dllexport) uintptr_t fixture_address(uint32_t i){return(uintptr_t)prepared[i].address;}
__declspec(dllexport) const void*fixture_before(uint32_t i){return prepared[i].before;}
__declspec(dllexport) const void*fixture_after(uint32_t i){return prepared[i].after;}
__declspec(dllexport) const char*fixture_error(void){return lastError;}
__declspec(dllexport) void fixture_fault(int kind,int value){if(kind==0)missingExport=value;if(kind==1)unreadable=value;if(kind==2)missingImage=value;if(kind==3)image[value]^=1;if(kind==4){prepared[0].address=image+value;prepared[0].length=8;}if(kind==5)wsInstallState=value;}
__declspec(dllexport) void fixture_display_fault(int kind,uint32_t value){if(kind==0)displayFault=(int)value;if(kind==1)displayImage[value]^=1;if(kind==2){prepared[0].address=displayImage+value;prepared[0].length=8;}}
__declspec(dllexport) void fixture_frame_fault(int kind,uint32_t value){if(kind==0)frameImage[value]^=1;if(kind==1){prepared[0].address=frameImage+value;prepared[0].length=8;}}
__declspec(dllexport) void fixture_call_fault(int kind,uint32_t i){WSPatch*p=fixture_call(i);if(!p)return;unsigned char*bridge=NULL;int32_t d;memcpy(&d,p->after+1,4);bridge=p->address+5+d;
 if(kind==0)p->after[0]^=1;if(kind==1)p->before[0]^=1;if(kind==2)bridge[0]^=1;if(kind==3)bridge[wsVisibilityCallPlan[i].contextArgument?16:8]^=1;
 if(kind==4)for(uint32_t j=0;j<WS_BLOB_COUNT;j++)wsInstalled[j].registered=0;
 if(kind==5)badHash=1;if(kind==6)p->address[0]^=1;if(kind==7)prepared[initialCount]=*p;}
__declspec(dllexport) void fixture_publish_only(void){for(uint32_t i=0;i<preparedCount;i++)if(prepared[i].length)memcpy(prepared[i].address,prepared[i].after,prepared[i].length);wsInstallState=1;}
__declspec(dllexport) void fixture_restore_only(void){for(uint32_t i=preparedCount;i>0;i--)if(prepared[i-1].length)memcpy(prepared[i-1].address,prepared[i-1].before,prepared[i-1].length);wsInstallState=0;}
'''
        (folder / 'fixture.c').write_text(source, encoding='utf-8')
        output = folder / ('fixture.dll' if os.name == 'nt' else 'fixture.so')
        command = [*compiler, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                   '-Wno-misleading-indentation', '-shared', str(folder / 'fixture.c'), '-o', str(output)]
        if os.name != 'nt':
            command.insert(len(compiler), '-fPIC')
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode:
            cls.temp.cleanup()
            raise AssertionError(result.stdout + result.stderr)
        cls.lib = C.CDLL(str(output))
        for name in ('fixture_base', 'fixture_display_base', 'fixture_frame_base', 'fixture_address', 'fixture_before', 'fixture_after'):
            getattr(cls.lib, name).restype = C.c_size_t
        for name in ('fixture_count', 'fixture_length', 'fixture_image_bytes', 'fixture_display_bytes', 'WorldSettingsVisibilityPatchStatus', 'WorldSettingsEnginePatchStatus'):
            getattr(cls.lib, name).restype = C.c_uint32
        cls.lib.fixture_prepare.argtypes = [C.c_uint32]
        cls.lib.fixture_fault.argtypes = [C.c_int, C.c_int]
        cls.lib.fixture_display_fault.argtypes = [C.c_int, C.c_uint32]
        cls.lib.fixture_frame_fault.argtypes = [C.c_int, C.c_uint32]
        cls.lib.fixture_call_fault.argtypes = [C.c_int, C.c_uint32]
        cls.lib.fixture_null_argument.argtypes = [C.c_int]
        cls.lib.fixture_error.restype = C.c_char_p

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.lib.fixture_reset()

    def image_hash(self):
        return tuple(hashlib.sha256(C.string_at(base, size)).digest() for base, size in
                     ((self.lib.fixture_base(), self.lib.fixture_image_bytes()),
                      (self.lib.fixture_display_base(), self.lib.fixture_display_bytes()),
                      (self.lib.fixture_frame_base(), self.lib.fixture_image_bytes())))

    def test_prepare_records_exact_reversible_pointer_edits_without_publishing(self):
        before = self.image_hash()
        self.assertEqual(self.lib.fixture_count(), PREPARED_COMPONENTS)
        self.assertEqual(self.lib.fixture_prepare(PREPARED_COMPONENTS), 1)
        self.assertEqual(self.lib.fixture_count(), 209)
        self.lib.fixture_reset()
        initial = TRANSACTION_CAPACITY - len(POINTERS)
        self.assertEqual(self.lib.fixture_prepare(initial), 1)
        self.assertEqual(self.lib.fixture_count(), TRANSACTION_CAPACITY)
        for index, (module, slot, target) in enumerate(POINTERS, initial):
            base = (self.lib.fixture_display_base() if module == 'AnnoDisplay.dll' else
                    self.lib.fixture_frame_base() if module == 'AnnoFrame.dll' else self.lib.fixture_base())
            self.assertEqual(self.lib.fixture_address(index), base + slot)
            self.assertEqual(self.lib.fixture_length(index), 8)
            self.assertEqual(C.string_at(self.lib.fixture_before(index), 8),
                             struct.pack('<Q', base + target))
            self.assertNotEqual(C.string_at(self.lib.fixture_before(index), 8),
                                C.string_at(self.lib.fixture_after(index), 8))
        self.assertEqual(self.image_hash(), before)
        self.assertEqual(self.lib.WorldSettingsVisibilityPatchStatus(), 0)
        self.assertEqual(self.lib.WorldSettingsEnginePatchStatus(), 0)
        self.lib.fixture_publish_only()
        self.assertEqual(self.lib.WorldSettingsVisibilityPatchStatus(), COMPONENTS)
        self.assertNotEqual(self.image_hash(), before)
        self.lib.fixture_restore_only()
        self.assertEqual(self.image_hash(), before)
        self.assertEqual(self.lib.WorldSettingsVisibilityPatchStatus(), 0)

    def test_preimage_export_readability_overlap_and_capacity_fail_closed(self):
        faults = ((0, 2), (1, DISPATCH[-1][0]), (2, 1),
                  (3, DISPATCH[-1][0]), (4, DISPATCH[0][0]))
        for kind, value in faults:
            with self.subTest(fault=kind):
                self.lib.fixture_reset()
                self.lib.fixture_fault(kind, value)
                before = self.image_hash()
                self.assertEqual(self.lib.fixture_prepare(PREPARED_COMPONENTS), 0)
                self.assertTrue(self.lib.fixture_error())
                self.assertEqual(self.image_hash(), before)
                self.assertEqual(self.lib.WorldSettingsVisibilityPatchStatus(), 0)
        for count in (TRANSACTION_CAPACITY - len(POINTERS) + 1,
                      TRANSACTION_CAPACITY, TRANSACTION_CAPACITY + 1, 0xffffffff):
            with self.subTest(count=count):
                self.lib.fixture_reset()
                self.assertEqual(self.lib.fixture_prepare(count), 0)
                self.assertEqual(self.lib.fixture_count(), count)

    def test_renderer_module_identity_preimages_exports_and_overlap_fail_closed(self):
        # Each fault belongs to Display; a valid World image must not mask it.
        for kind, value in ((0, 1), (0, 2), (0, 3), (0, 4),
                            (1, RENDER_DISPATCH[0][0]), (1, RENDER_DISPATCH[1][0]),
                            (2, RENDER_DISPATCH[0][0]), (2, RENDER_DISPATCH[1][0] + 7)):
            with self.subTest(kind=kind, value=value):
                self.lib.fixture_reset()
                self.lib.fixture_display_fault(kind, value)
                before = self.image_hash()
                self.assertEqual(self.lib.fixture_prepare(PREPARED_COMPONENTS), 0)
                self.assertTrue(self.lib.fixture_error())
                self.assertEqual(self.image_hash(), before)
                self.assertEqual(self.lib.WorldSettingsVisibilityPatchStatus(), 0)
        # World has three unique callbacks before the two new renderer exports.
        first = len(dict.fromkeys(row[2] for row in visibility.HOOKS))
        for missing in (first, first + 1):
            self.lib.fixture_reset()
            self.lib.fixture_fault(0, missing)
            before = self.image_hash()
            self.assertEqual(self.lib.fixture_prepare(PREPARED_COMPONENTS), 0)
            self.assertEqual(self.image_hash(), before)

    def test_complete_readiness_requires_all_committed_dispatches_and_engine_bytes(self):
        self.assertEqual(self.lib.fixture_prepare(PREPARED_COMPONENTS), 1)
        self.lib.fixture_publish_only()
        self.assertEqual(self.lib.WorldSettingsVisibilityPatchStatus(), COMPONENTS)
        self.assertEqual(self.lib.WorldSettingsEnginePatchStatus(), 173)
        for slot, _ in DISPATCH:
            with self.subTest(slot=slot):
                self.lib.fixture_fault(3, slot)
                self.assertEqual(self.lib.WorldSettingsVisibilityPatchStatus(), 0)
                self.assertEqual(self.lib.WorldSettingsEnginePatchStatus(), 0)
                self.lib.fixture_fault(3, slot)
        for slot, _ in RENDER_DISPATCH:
            with self.subTest(renderer_slot=slot):
                self.lib.fixture_display_fault(1, slot)
                self.assertEqual(self.lib.WorldSettingsVisibilityPatchStatus(), 0)
                self.assertEqual(self.lib.WorldSettingsEnginePatchStatus(), 0)
                self.lib.fixture_display_fault(1, slot)
        for slot, _ in CONTROL_DISPATCH:
            with self.subTest(control_slot=slot):
                self.lib.fixture_frame_fault(0, slot)
                self.assertEqual(self.lib.WorldSettingsVisibilityPatchStatus(), 0)
                self.assertEqual(self.lib.WorldSettingsEnginePatchStatus(), 0)
                self.lib.fixture_frame_fault(0, slot)
        self.lib.fixture_display_fault(0, 4)
        self.assertEqual(self.lib.WorldSettingsVisibilityPatchStatus(), 0)
        self.assertEqual(self.lib.WorldSettingsEnginePatchStatus(), 0)
        self.lib.fixture_display_fault(0, 0)
        self.lib.fixture_fault(1, DISPATCH[-1][0])
        self.assertEqual(self.lib.WorldSettingsVisibilityPatchStatus(), 0)
        self.assertEqual(self.lib.WorldSettingsEnginePatchStatus(), 0)
        self.lib.fixture_fault(1, -1)
        self.lib.fixture_fault(3, 0x200)
        self.assertEqual(self.lib.WorldSettingsEnginePatchStatus(), 0)
        self.assertEqual(self.lib.WorldSettingsVisibilityPatchStatus(), COMPONENTS)
        self.lib.fixture_fault(5, -1)
        self.assertEqual(self.lib.WorldSettingsVisibilityPatchStatus(), 0)

    def test_control_dispatch_preimages_exports_and_overlap_refuse_before_commit(self):
        for slot, _ in CONTROL_DISPATCH:
            for fault, at in ((0, slot), (1, slot), (1, slot + 7)):
                with self.subTest(slot=slot, fault=fault, address=at):
                    self.lib.fixture_reset()
                    self.lib.fixture_frame_fault(fault, at)
                    before = self.image_hash()
                    self.assertEqual(self.lib.fixture_prepare(PREPARED_COMPONENTS), 0)
                    self.assertEqual(self.image_hash(), before)
                    self.assertEqual(self.lib.WorldSettingsVisibilityPatchStatus(), 0)
        first = len(dict.fromkeys(row[2] for row in (*visibility.HOOKS, *visibility.RENDER_HOOKS)))
        for missing in (first, first + 1):
            self.lib.fixture_reset()
            self.lib.fixture_fault(0, missing)
            before = self.image_hash()
            self.assertEqual(self.lib.fixture_prepare(PREPARED_COMPONENTS), 0)
            self.assertEqual(self.image_hash(), before)

    def test_call_linkage_registered_leaf_import_and_profile_pin_fail_closed(self):
        for call in range(len(call_visibility.CALLS)):
            for fault in (0, 1, 2, 3, 4, 5):
                with self.subTest(call=call, fault=fault):
                    self.lib.fixture_reset()
                    self.lib.fixture_call_fault(fault, call)
                    before = self.image_hash()
                    self.assertEqual(self.lib.fixture_prepare(PREPARED_COMPONENTS), 0)
                    self.assertTrue(self.lib.fixture_error())
                    self.assertEqual(self.image_hash(), before)
                    self.assertEqual(self.lib.WorldSettingsVisibilityPatchStatus(), 0)
        self.lib.fixture_reset()
        self.lib.fixture_call_fault(7, 0)
        self.assertEqual(self.lib.fixture_prepare(PREPARED_COMPONENTS + 1), 0)

    def test_readiness_rechecks_every_call_instruction_leaf_and_import_cell(self):
        for call in range(len(call_visibility.CALLS)):
            for fault in (2, 3, 6):
                with self.subTest(call=call, fault=fault):
                    self.lib.fixture_reset()
                    self.assertEqual(self.lib.fixture_prepare(PREPARED_COMPONENTS), 1)
                    self.lib.fixture_publish_only()
                    self.assertEqual(self.lib.WorldSettingsVisibilityPatchStatus(), COMPONENTS)
                    self.lib.fixture_call_fault(fault, call)
                    self.assertEqual(self.lib.WorldSettingsVisibilityPatchStatus(), 0)
                    self.assertEqual(self.lib.WorldSettingsEnginePatchStatus(), 0)

    def test_null_preparation_arguments_do_not_touch_the_fixture_image(self):
        before = self.image_hash()
        for which in (0, 1):
            with self.subTest(null_argument=which):
                self.assertEqual(self.lib.fixture_null_argument(which), 0)
                self.assertEqual(self.image_hash(), before)
                self.assertEqual(self.lib.WorldSettingsVisibilityPatchStatus(), 0)


if __name__ == '__main__':
    unittest.main()
