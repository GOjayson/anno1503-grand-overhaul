#include "ai_food.h"
#include <string.h>
#include <limits.h>

/* Preserve the old ascending order and its tie behavior, then add the three
 * goods outside26..40. This is a set, not a widened numeric interval. */
static const uint32_t consumers[AIF_CONSUMERS]={
    26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,24,25,45
};
static const uint32_t foodMarketWares[6]={26,28,24,40,25,45};
static uint16_t read16(const void *p){uint16_t x;memcpy(&x,p,sizeof x);return x;}
static uint32_t read32(const void *p){uint32_t x;memcpy(&x,p,sizeof x);return x;}
static int32_t readSigned32(const void *p){int32_t x;memcpy(&x,p,sizeof x);return x;}
static void write16(void *p,uint16_t x){memcpy(p,&x,sizeof x);}
static void writeSigned32(void *p,int32_t x){memcpy(p,&x,sizeof x);}

int AIFReadyForGame(void){return 0;}
uint32_t AIFConsumerAt(uint32_t ordinal){return ordinal<AIF_CONSUMERS?consumers[ordinal]:0;}
int AIFIsConsumer(uint32_t good){
    return (good>=26&&good<=40)||good==24||good==25||good==45;
}
size_t AIFPendingRecordOffset(uint32_t good){
    if(good==24)return 0x340;
    if(good==25)return 0x354;
    if(good>=26&&good<=55)return 0x48+(size_t)(good-26)*20;
    return SIZE_MAX;
}
int AIFPendingAfterConstructor(void *node,size_t allocationBytes){
    if(!node||allocationBytes!=AIF_NODE_BYTES)return 0;
    memset((unsigned char*)node+AIF_NATIVE_NODE_BYTES,0,AIF_NODE_BYTES-AIF_NATIVE_NODE_BYTES);
    return 1;
}
int AIFPendingAdd(void *node,uint32_t good,int32_t x,int32_t y){
    size_t offset=AIFPendingRecordOffset(good);
    unsigned char *record;uint16_t count;int64_t sx,sy;
    if(!node||!AIFIsConsumer(good)||offset==SIZE_MAX)return 0;
    record=(unsigned char*)node+offset;count=read16(record+12);
    sx=(int64_t)readSigned32(record)+x;sy=(int64_t)readSigned32(record+4)+y;
    if(count==UINT16_MAX||sx<INT32_MIN||sx>INT32_MAX||sy<INT32_MIN||sy>INT32_MAX)return 0;
    writeSigned32(record,(int32_t)sx);writeSigned32(record+4,(int32_t)sy);
    write16(record+12,(uint16_t)(count+1));return 1;
}
int AIFPendingClear(void *node,uint32_t good){
    size_t offset=AIFPendingRecordOffset(good);
    if(!node||!AIFIsConsumer(good)||offset==SIZE_MAX)return 0;
    /* Match native placement: count resets, coordinate sums remain. */
    write16((unsigned char*)node+offset+12,0);return 1;
}
int AIFPendingSelect(void *head,uint32_t nodeLimit,AIFPendingChoice *out){
    AIFPendingChoice choice={0};void *node=head;uint32_t visited=0;
    if(!out||!nodeLimit)return 0;
    while(node){
        uint32_t ordinal;void *next;
        if(visited++==nodeLimit)return 0;
        for(ordinal=0;ordinal<AIF_CONSUMERS;ordinal++){
            uint32_t good=consumers[ordinal];
            unsigned char *record=(unsigned char*)node+AIFPendingRecordOffset(good);
            uint16_t count=read16(record+12);
            if(count>choice.count){
                choice.node=node;choice.good=good;choice.count=count;
                choice.x=readSigned32(record)/(int32_t)count;
                choice.y=readSigned32(record+4)/(int32_t)count;
            }
        }
        memcpy(&next,node,sizeof next);node=next;
    }
    if(!choice.count)return 0;
    *out=choice;return 1;
}
uint32_t AIFMarketWareCount(void *definition,uint32_t buildingType,AIFWareGetter getter){
    uint32_t index;
    if(!definition||!getter)return 0;
    if(buildingType!=0xa1)return 2;
    for(index=0;index<6;index++)if(getter(definition,(uint8_t)index)!=foodMarketWares[index])return 2;
    return 6;
}
int AIFMarketCovers(void *definition,uint32_t buildingType,AIFWareGetter getter,uint32_t good){
    uint32_t index,count=AIFMarketWareCount(definition,buildingType,getter);
    if(!good)return 0;
    for(index=0;index<count;index++)if(getter(definition,(uint8_t)index)==good)return 1;
    return 0;
}
int AIFPendingClearMarket(void *node,void *definition,uint32_t buildingType,AIFWareGetter getter){
    uint32_t index,count=AIFMarketWareCount(definition,buildingType,getter);
    if(!node||!count)return 0;
    for(index=0;index<count;index++){
        uint32_t good=getter(definition,(uint8_t)index);
        if(AIFIsConsumer(good)&&!AIFPendingClear(node,good))return 0;
    }
    return 1;
}
uint32_t AIFConsumerStand(const void *provider,uint32_t good,uint32_t foodStand){
    if(!provider||!AIFIsConsumer(good))return 0;
    if(good==24||good==25||good==40||good==45)return foodStand;
    return read32((const unsigned char*)provider+0xf0+(size_t)(good-26)*4);
}
int AIFEvaluateDemand(const void *profiles,const int32_t counts[AIF_POPULATIONS],
    uint32_t highestPopulation,uint32_t good,int32_t stockFixed,AIFDemand *out){
    float sum=0.0f,demand;uint32_t level;
    AIFDemand result;
    if(!profiles||!counts||!out||highestPopulation>=AIF_POPULATIONS||!AIFIsConsumer(good)||stockFixed<0)return 0;
    for(level=0;level<=highestPopulation;level++){
        const unsigned char *profile=(const unsigned char*)profiles+level*0x120;
        uint32_t index=profile[good+3];int32_t population=counts[level];int64_t product;
        uint16_t amount;
        if(index>46||population<0)return 0;
        amount=read16(profile+0x66+index*4);
        if(level==highestPopulation&&population<60)population=60;
        if(!population)continue;
        if(highestPopulation==0)population+=50;
        product=(int64_t)population*amount;
        if(product>INT32_MAX)return 0;
        sum+=(float)(int32_t)product;
    }
    demand=sum*(1.0f/4096.0f);
    if(highestPopulation==0&&demand<0.7f)demand+=demand;
    result.demand=demand;result.negativeDemand=-demand;
    result.stock=(float)stockFixed*(1.0f/256.0f);
    *out=result;return 1;
}
int AIFRemoveAddedFoodPlans(void *city,size_t cityBytes,uint32_t buildingID){
    uint32_t pass,good,candidate,entry;
    unsigned char *bytes=(unsigned char*)city;
    if(!city||cityBytes<0xfd10||!buildingID)return 0;
    /* Validate the complete operation first so malformed plan data cannot
     * leave a partial update. Only IDs24/25 lack native removal accounting. */
    for(pass=0;pass<2;pass++)for(good=24;good<=25;good++){
        for(candidate=0;candidate<8;candidate++){
            unsigned char *plan=bytes+0x23a4+(size_t)good*0x3e0+candidate*0x7c;
            uint32_t count=plan[0x60];
            if(!count)break;
            if(count>8)return 0;
            for(entry=0;entry<count;entry++){
                unsigned char *step=plan+entry*12;
                if(read32(step+4)!=buildingID)continue;
                if(!step[10])return 0;
                if(pass)step[10]--;
            }
        }
    }
    return 1;
}
