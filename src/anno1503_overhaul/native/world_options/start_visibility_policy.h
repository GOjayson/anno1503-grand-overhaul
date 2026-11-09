#ifndef WS_START_VISIBILITY_POLICY_H
#define WS_START_VISIBILITY_POLICY_H
#include <stdint.h>
/* Exact HE WELT/scene HEAD transport retains these three low-word bits.
 * Codes 1..6 identify this policy, zero leaves older/ordinary saves alone.
 * The original native property-6 consumers were audited separately from the
 * transport. This is not a claim about arbitrary scripts or other game builds.
 */
#define WS_VISIBILITY_POLICY_MASK 0x7000u
#define WS_VISIBILITY_RENDER_BYTES 0x390u
#define WS_VISIBILITY_PAYLOAD_BYTES (WS_VISIBILITY_RENDER_BYTES-8u)
#define WS_VISIBILITY_RECORD_BYTES 88u
#define WS_VISIBILITY_RECORD_LIMIT 8192u
#define WS_VISIBILITY_ISLAND_LIMIT 255u
static uint32_t wsVisibilityEncode(int32_t map,int32_t enemy){
 if(map<0||map>2||enemy<0||enemy>1)return 0;
 return (1u+(uint32_t)map+3u*(uint32_t)enemy)<<12;
}
static int wsVisibilityDecode(uint32_t flags,int32_t*map,int32_t*enemy){
 uint32_t code=(flags&WS_VISIBILITY_POLICY_MASK)>>12;
 if(!code)return 0;
 if(code>6u)return -1;
 if(map)*map=(int32_t)((code-1u)%3u);
 if(enemy)*enemy=(int32_t)((code-1u)/3u);
 return 1;
}
#endif
