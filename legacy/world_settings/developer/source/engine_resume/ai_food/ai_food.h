#ifndef ANNO_AI_FOOD_H
#define ANNO_AI_FOOD_H
#include <stddef.h>
#include <stdint.h>
#ifdef _WIN32
#define AIF_EXPORT __declspec(dllexport)
#else
#define AIF_EXPORT
#endif
#define AIF_NATIVE_NODE_BYTES 0x340u
#define AIF_NODE_BYTES 0x368u
#define AIF_CONSUMERS 18u
#define AIF_GOODS 56u
#define AIF_POPULATIONS 5u
typedef uint32_t (*AIFWareGetter)(void *definition,uint8_t index);
typedef struct {
    void *node;
    uint32_t good;
    uint32_t count;
    int32_t x,y;
} AIFPendingChoice;
typedef struct {
    float demand,negativeDemand,stock;
} AIFDemand;
/* Native constructor runs first, on an allocation of AIF_NODE_BYTES. */
AIF_EXPORT int AIFPendingAfterConstructor(void *node,size_t allocationBytes);
AIF_EXPORT size_t AIFPendingRecordOffset(uint32_t good);
AIF_EXPORT int AIFPendingAdd(void *node,uint32_t good,int32_t x,int32_t y);
AIF_EXPORT int AIFPendingClear(void *node,uint32_t good);
AIF_EXPORT int AIFPendingSelect(void *head,uint32_t nodeLimit,AIFPendingChoice *out);
AIF_EXPORT uint32_t AIFConsumerAt(uint32_t ordinal);
AIF_EXPORT int AIFIsConsumer(uint32_t good);
/* Six applies only to the exact extended Food stand; other stands keep two. */
AIF_EXPORT uint32_t AIFMarketWareCount(void *definition,uint32_t buildingType,AIFWareGetter getter);
AIF_EXPORT int AIFMarketCovers(void *definition,uint32_t buildingType,AIFWareGetter getter,uint32_t good);
AIF_EXPORT int AIFPendingClearMarket(void *node,void *definition,uint32_t buildingType,AIFWareGetter getter);
/* provider points at native controller+8. foodStand is a verified six-ware stand. */
AIF_EXPORT uint32_t AIFConsumerStand(const void *provider,uint32_t good,uint32_t foodStand);
/* profiles: five native population records, stride0x120. No shared data writes. */
AIF_EXPORT int AIFEvaluateDemand(const void *profiles,const int32_t counts[AIF_POPULATIONS],
    uint32_t highestPopulation,uint32_t good,int32_t stockFixed,AIFDemand *out);
/* Add after the untouched native removal accounting. ID45 is already handled
 * by its native41..45 branch; processing it again would double-decrement. */
AIF_EXPORT int AIFRemoveAddedFoodPlans(void *city,size_t cityBytes,uint32_t buildingID);
/* Deliberately false: these helpers alone are not a certified native integration. */
AIF_EXPORT int AIFReadyForGame(void);
#endif
