/* Include in WorldSettings.c and link selection.c. Private, not installed.
 * The incoming Frame/page pointers are supplied only by the fingerprinted
 * native bridge in this process, under the same trust contract as BeforeStart.
 */
extern int WorldSettingsClassifyDirectSelection(const char *,uint32_t,const unsigned char *);
__declspec(dllexport) int __cdecl WorldSettingsBeforeDirectStart(void *page,void *frame) {
    if(!page||!frame)return 0;
    const unsigned char *base=(const unsigned char*)frame;
    int selected=WorldSettingsClassifyDirectSelection((const char*)base+0xc7430,260,base+0xc7534);
    if(selected==0)return 1; /* Original tutorial/mission path, no UI or commit. */
    if(selected!=1){
        reportGenerationFailure("The selected endless scene differs from the inspected development source. Start is blocked.");
        return 0;
    }
    void **children=*(void***)((unsigned char*)page+0x21b0);
    if(!children||!children[0]){
        reportGenerationFailure("The native endless setup object is unavailable. Start is blocked.");
        return 0;
    }
    return WorldSettingsBeforeStart(children[0],frame)>0?2:0;
}
