"""Unmarked/native worlds keep native calls without per-sprite OS queries.

Uses the real display adapter in a synthetic Windows memory graph, not Anno.
"""
import ctypes as C
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_world_visibility_native import FIXTURE, NATIVE, ROOT

EXTRA = r'''
static void nativePrepare(uint32_t policy){
 wsChartCoreFree(&wsChartActive);wsChartWorldBinding=0;
 nativeMonitor=nativeRefreshSeen=nativeRefreshLeaked=nativeClippedCalls=0;
 prepare(policy,1);ptr(rendererBytes,moduleBytes+0xf63740u);
 for(size_t i=0;i<sizeof wsVisibilityActorLayouts/sizeof wsVisibilityActorLayouts[0];i++){
  const WSVisibilityActorLayout*a=wsVisibilityActorLayouts+i;unsigned char*v=moduleBytes+a->vtable;
  ptr(v+0x38,moduleBytes+a->worldGetter);ptr(v+0x40,moduleBytes+a->ownerGetter);
  ptr(v+0xb0,moduleBytes+a->xGetter);ptr(v+0xc0,moduleBytes+a->zGetter);
 }
 ptr(actorBytes,moduleBytes+0xeb5f0u);ptr(actorBytes+0x28,worldBytes);
 nativeExpectedRenderer=rendererBytes;
}
static uintptr_t nativeWork(void*renderer){
 if(!wsVisibilityNativeTLS||wsVisibilityNativeTLS->renderer!=renderer)return 1;
 float point[3]={21.5f,0,21.5f};spyStaticPosition=point;visibilityReadChecks=0;
 for(uint32_t i=0;i<10000;i++){
  if(WorldSettingsVisibilityDrawStatic180(renderer,quadBytes,7,11,0xc0,point)!=0x4455u||
     WorldSettingsVisibilityRenderStatic188(renderer,quadBytes,7,11,0xc0,point)!=0x4455u||
     WorldSettingsVisibilityDispatchResident100(actorBytes,71,renderer)!=0x3344u||
     WorldSettingsVisibilityDispatchResident108(actorBytes,71,renderer)!=0x3344u||
     WorldSettingsVisibilityDispatchOccurrence100(actorBytes,71,renderer,0x1234u)!=0x3345u)return 2;
 }
 return 0x1234u;
}
static DWORD WINAPI otherThread(void*p){(void)p;return wsVisibilityNativeTLS?1u:0u;}
__declspec(dllexport) int nativePassthrough(uint32_t which,uint32_t*out){
 nativePrepare(which==1?wsVisibilityEncode(0,0):0);WSVisibilityNativeScope scope;
 if(which==6){
  nativeExpectedRenderer=drawRendererBytes;nativeBenchmark=1;
  uintptr_t value=WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes);nativeBenchmark=0;
  out[0]=visibilityReadChecks;out[1]=spyStaticCalls;out[2]=spyResidentCalls;out[3]=spyOccurrenceFlags;
  return value==0x1234u&&!spyFailure&&!wsVisibilityNativeTLS&&!wsVisibilityDrawContext&&!wsVisibilityRenderBusy&&!wsChartActive.cells?0:1;
 }
 if(which==9){
  nativeExpectedRenderer=drawRendererBytes;nativeBenchmark=1;
  uintptr_t value=WorldSettingsVisibilityDrawTerrainClipped(worldBytes,listBytes,17,(const int32_t*)tableBytes,29,drawRendererBytes);nativeBenchmark=0;
  out[0]=visibilityReadChecks;out[1]=spyStaticCalls;out[2]=spyResidentCalls;out[3]=spyOccurrenceFlags;
  return value==0x1235u&&nativeClippedCalls==1&&!spyFailure&&!wsVisibilityNativeTLS&&!wsVisibilityDrawContext&&!wsVisibilityRenderBusy&&!wsChartActive.cells?0:1;
 }
 wsVisibilityNativeEnter(&scope,worldBytes,which>=7?drawRendererBytes:rendererBytes,0);
 if(which==1){int present=wsVisibilityNativeTLS!=0;wsVisibilityNativeLeave(&scope);return present;}
 if(!wsVisibilityNativeTLS)return 90;
 int result=0;
 if(which==0){
  float point[3]={21.5f,0,21.5f};spyStaticPosition=point;
  visibilityReadChecks=0;
  for(uint32_t i=0;i<10000;i++){
   if(WorldSettingsVisibilityDrawStatic180(rendererBytes,quadBytes,7,11,0xc0,point)!=0x4455u||
      WorldSettingsVisibilityRenderStatic188(rendererBytes,quadBytes,7,11,0xc0,point)!=0x4455u||
      WorldSettingsVisibilityDispatchResident100(actorBytes,71,rendererBytes)!=0x3344u||
      WorldSettingsVisibilityDispatchResident108(actorBytes,71,rendererBytes)!=0x3344u||
      WorldSettingsVisibilityDispatchOccurrence100(actorBytes,71,rendererBytes,0x1234u)!=0x3345u){result=1;break;}
  }
  out[0]=visibilityReadChecks;out[1]=spyStaticCalls;out[2]=spyResidentCalls;out[3]=spyOccurrenceFlags;
  if(spyFailure||wsVisibilityDrawContext||wsVisibilityRenderBusy||wsChartActive.cells)result=2;
 }else if(which==2){
  if(!wsVisibilityNativeActor(actorBytes,rendererBytes))result=1;
  ptr(actorBytes+0x28,worldBytes+8);if(wsVisibilityNativeActor(actorBytes,rendererBytes))result=2;
  ptr(actorBytes+0x28,worldBytes);if(wsVisibilityNativeActor(actorBytes,tableBytes))result=3;
 }else if(which==3){
  WSVisibilityNativeScope nested;wsVisibilityNativeEnter(&nested,worldBytes,rendererBytes,1);
  if(wsVisibilityNativeTLS)result=1;wsVisibilityNativeLeave(&nested);
  if(wsVisibilityNativeTLS!=&scope)result=2;
 }else if(which==4){
  HANDLE thread=CreateThread(0,0,otherThread,0,0,0);DWORD code=2;
  if(!thread)result=1;else{if(WaitForSingleObject(thread,10000)!=WAIT_OBJECT_0||!GetExitCodeThread(thread,&code)||code)result=2;CloseHandle(thread);}
 }else if(which==5){
  wsVisibilityNativeLeave(&scope);ptr(moduleBytes+0xeb5f0u+0x38,moduleBytes+0x1234u);
  wsVisibilityNativeEnter(&scope,worldBytes,rendererBytes,0);
  if(!wsVisibilityNativeTLS||wsVisibilityNativeActor(actorBytes,rendererBytes))result=1;
 }else if(which==7){
  wsPut32(worldBytes+0x6eec,wsVisibilityEncode(1,0)|0x86u);nativeMonitor=1;
  uintptr_t value=WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes);nativeMonitor=0;
  if(value!=0x1234u||!nativeRefreshSeen||nativeRefreshLeaked||spyFailure||wsVisibilityNativeTLS!=&scope)result=1;
 }else if(which==8){
  wsPut32(worldBytes+0x6eec,wsVisibilityEncode(1,0)|0x86u);InterlockedExchange(&wsVisibilityRenderBusy,1);
  if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes)||wsVisibilityNativeTLS!=&scope)result=1;
  InterlockedExchange(&wsVisibilityRenderBusy,0);
 }else result=99;
 wsVisibilityNativeLeave(&scope);if(wsVisibilityNativeTLS)return 91;return result;
}
'''


@unittest.skipUnless(os.name == 'nt', 'Requires Windows native memory and TLS.')
class NativePassthrough(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='anno-native-passthrough-')
        folder = Path(cls.temp.name)
        zig = ROOT / '.local/toolchain/ziglang/zig.exe'
        if not zig.is_file():
            cls.temp.cleanup()
            raise unittest.SkipTest('Reviewed native compiler unavailable.')
        # Typed renderer/CRT boundaries are supplied by the existing fixture.
        # Only executable protection of its synthetic module is substituted.
        source = FIXTURE.replace('#define WS_VISIBILITY_STATIC_TARGET_OK(target) 1',
            '#define WS_VISIBILITY_NATIVE_SCOPE_TARGET_OK(module,target) 1\n'
            '#define WS_VISIBILITY_STATIC_TARGET_OK(target) 1')
        source = source.replace('renderer!=tableBytes)spyFailure=12',
                                'renderer!=nativeExpectedRenderer)spyFailure=12')
        source = source.replace('renderer!=rendererBytes||frame!=quadBytes',
                                'renderer!=nativeExpectedRenderer||frame!=quadBytes')
        source = source.replace('static uintptr_t spy5(void*,void*,uint32_t,uint32_t,void*);',
            'static void*nativeExpectedRenderer;static uint32_t nativeBenchmark,nativeMonitor,nativeRefreshSeen,nativeRefreshLeaked,nativeClippedCalls;\n'
            'static uintptr_t nativeWork(void*);\n'
            'static uintptr_t spy5(void*,void*,uint32_t,uint32_t,void*);')
        source = source.replace(' spyCalls++;\n', ' spyCalls++;if(nativeBenchmark)return nativeWork(renderer);\n', 1)
        source = source.replace('static void spyDirtyViewport(void*renderer,const int32_t*rect){',
            'static void spyDirtyViewport(void*renderer,const int32_t*rect){if(nativeMonitor){nativeRefreshSeen++;if(wsVisibilityNativeTLS)nativeRefreshLeaked++;}')
        clipped_check = ' if(rect!=(int32_t*)tableBytes)spyFailure=4;'
        if source.count(clipped_check) != 1:
            raise AssertionError('The native clipped argument-check boundary changed.')
        source = source.replace(clipped_check,
            ' if(nativeBenchmark){nativeClippedCalls++;if(world!=worldBytes||list!=listBytes||flags!=17||property!=29||renderer!=drawRendererBytes)spyFailure=17;}\n'
            + clipped_check)
        (folder / 'fixture.c').write_text(source + EXTRA, encoding='utf-8')
        output = folder / 'fixture.dll'
        result = subprocess.run([str(zig), 'cc', '-target', 'x86_64-windows-gnu',
            '-std=c11', '-shared', '-O2', '-Wall', '-Wextra', '-Werror', '-I',
            str(NATIVE), str(folder / 'fixture.c'), '-o', str(output)],
            capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.lib = C.CDLL(str(output))
        cls.lib.nativePassthrough.argtypes = [C.c_uint32, C.POINTER(C.c_uint32)]

    @classmethod
    def tearDownClass(cls):
        import _ctypes
        _ctypes.FreeLibrary(cls.lib._handle)
        cls.temp.cleanup()

    def run_case(self, which):
        output = (C.c_uint32 * 4)()
        self.assertEqual(self.lib.nativePassthrough(which, output), 0)
        return list(output)

    def test_fifty_thousand_native_calls_keep_arguments_without_os_queries(self):
        self.assertEqual(self.run_case(0), [0, 20000, 30000, 0x1234])

    def test_marked_world_never_acquires_native_scope(self):
        self.run_case(1)

    def test_foreign_world_and_renderer_cannot_use_scope(self):
        self.run_case(2)

    def test_nested_custom_draw_suspends_then_restores_scope(self):
        self.run_case(3)

    def test_scope_is_private_to_its_drawing_thread(self):
        self.run_case(4)

    def test_changed_native_interface_does_not_acquire_actor_exemption(self):
        self.run_case(5)

    def test_actual_native_world_draw_scopes_fifty_thousand_calls_then_cleans_up(self):
        self.assertEqual(self.run_case(6), [0, 20000, 30000, 0x1234])

    def test_actual_nested_marked_preflight_suspends_native_scope_before_callbacks(self):
        self.run_case(7)

    def test_actual_failed_nested_marked_draw_restores_its_callers_native_scope(self):
        self.run_case(8)

    def test_actual_clipped_draw_keeps_arguments_and_scopes_fifty_thousand_calls(self):
        self.assertEqual(self.run_case(9), [0, 20000, 30000, 0x1234])


if __name__ == '__main__':
    unittest.main()
