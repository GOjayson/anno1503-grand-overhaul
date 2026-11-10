/* Frame1CA76 is the final normal mode2 flush, after World and scene drawing.
 * Its registered leaf supplies live RDI context as the volatile RDX argument.
 * Drain the original native workers once before retiring our owned copies or
 * applying the opaque chart mask. No live context/surface pointer is retained.
 */
typedef uintptr_t (__cdecl*WSVisibilityNativeFlush)(void*);
#ifndef WS_VISIBILITY_NATIVE_FLUSH
#define WS_VISIBILITY_NATIVE_FLUSH(target) ((WSVisibilityNativeFlush)(target))
#endif
__declspec(dllexport) uintptr_t __cdecl WorldSettingsVisibilityFinishFrame(void*renderer,void*liveFrameContext){
 unsigned char*display=(unsigned char*)WS_CERT_MODULE("AnnoDisplay.dll");
 void*vt=wsCertPointer(renderer,0),*target=wsCertPointer(vt,0x118u);
 if(!display||vt!=display+0xf63740u||target!=display+0x483e0u||
    !wsVisibilityWithinModule(display,target,1)||!wsCertMemory(target,1,1)){
  InterlockedExchange(&wsVisibilityLastError,16);return 0;
 }
 int prepared=wsVisibilityExplorationPreflight(renderer,liveFrameContext);
 uintptr_t result=WS_VISIBILITY_NATIVE_FLUSH(target)(renderer);
 wsVisibilityChartRetire(renderer);
 /* A surface may be initialized by the native flush. The fresh postflush
  * checks, rather than a retained pixel pointer, decide whether it is safe. */
 int applied=wsVisibilityApplyExploredSea(renderer,liveFrameContext);
 if(!applied){InterlockedExchange(&wsVisibilityLastError,16);}
 (void)prepared;
 return result;
}
