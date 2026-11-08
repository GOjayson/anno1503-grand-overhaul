#ifndef WS_NATIVE_DISASTER_OPTIONS_H
#define WS_NATIVE_DISASTER_OPTIONS_H
#include <stdint.h>
/* Exact History Edition Frame callbacks0x47c00/0x47c80 bind these native
 * Pirates/disasters option bytes. Native55330 translates them to World
 * property6 masks0x20/0x86. The enclosing hook validates the complete module
 * fingerprint before this helper is reachable. No executable bytes change.
 */
static int wsBindNativeFactionOptions(uint8_t*frame,uint32_t factions,int32_t disasters){
 if(!frame||(factions&~3u)||disasters<0||disasters>1)return 0;
 frame[0xc7a78]=(uint8_t)disasters;
 frame[0xc7a79]=(uint8_t)((factions&1u)!=0);
 return 1;
}
#endif
