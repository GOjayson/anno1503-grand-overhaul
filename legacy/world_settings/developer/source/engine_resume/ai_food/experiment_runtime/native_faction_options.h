#ifndef WS_NATIVE_FACTION_OPTIONS_H
#define WS_NATIVE_FACTION_OPTIONS_H
#include <stdint.h>
/* The fingerprinted start bridges supply the actual AnnoFrame module base.
 * Its native Pirates AAN/UIT checkbox uses this byte, and native55330 copies
 * that choice to World property6 bit0x20 (one means pirates disabled).
 * The adjacent byte controls disasters; Venetians have no matching UI flag.
 */
static int wsBindNativeFactionOptions(uint8_t *frame,uint32_t factions){
 if(!frame||(factions&~3u))return 0;
 frame[0xc7a79]=(uint8_t)((factions&1u)!=0);
 return 1;
}
#endif
