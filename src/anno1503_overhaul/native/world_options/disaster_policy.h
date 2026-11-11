#ifndef WS_DISASTER_POLICY_H
#define WS_DISASTER_POLICY_H
#include <stdint.h>
#define WS_DISASTER_COUNT 5u
#define WS_DISASTER_MASK 31u
#define WS_DISASTER_NORMAL_MODES 341u
/* Fire, plague, volcano, earthquake, drought. Fire/plague damage remains
 * native: only the three independently proved duration/extent controls vary. */
#define WS_DISASTER_SEVERITY_TYPES 28u
static int wsDisasterOptionsValid(uint32_t master,uint32_t mask,uint32_t frequency,uint32_t severity){
 if(master>1u||(mask&~WS_DISASTER_MASK)||(frequency&~1023u)||(severity&~1023u))return 0;
 for(uint32_t i=0;i<WS_DISASTER_COUNT;i++){
  uint32_t f=(frequency>>(i*2u))&3u,s=(severity>>(i*2u))&3u;
  if(f>2u||s>2u||(!(WS_DISASTER_SEVERITY_TYPES&(1u<<i))&&s!=1u))return 0;
 }return 1;
}
static uint32_t wsDisasterDisabledNative(uint32_t master,uint32_t mask){
 uint32_t active=master?mask:0u,result=0u;
 if(!(active&3u))result|=8u;
 if(!(active&4u))result|=2u;
 if(!(active&8u))result|=128u;
 if(!(active&16u))result|=4u;
 return result;
}
static uint32_t wsDisasterChance(uint32_t random,uint32_t denominator,uint32_t mode){
 if(mode==1u||denominator<5u||denominator>254u)return random;
 if(mode==0u){uint32_t r=random%(denominator*2u);return r<denominator?r:4u;}
 return random%((denominator+1u)/2u);
}
static uint32_t wsDisasterInterval(uint32_t normal,uint32_t mode){
 if(mode==0u)return normal>UINT32_MAX/2u?UINT32_MAX:normal*2u;
 if(mode==2u)return normal>1u?normal/2u:1u;
 return normal;
}
#endif
