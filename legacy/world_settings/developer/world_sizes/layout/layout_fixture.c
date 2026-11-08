/* Isolated Windows-native execution of the shipped selection/layout includes.
 * This has no Anno process, loader, hook, scene writer or engine object.
 * SelectPlan duplicates only the documented selection prelude; full-runtime
 * fertility/staging/native-engine validation is deliberately separate.
 */
#include <stdint.h>
#include <string.h>
#include "../../source/engine_resume/ai_food/experiment_runtime/world_backend.h"
#include "../../source/engine_resume/ai_food/experiment_runtime/world_catalogue.h"
#include "../../source/engine_resume/ai_food/experiment_runtime/world_factions.h"
#include "../../source/engine_resume/ai_food/experiment_runtime/world_ship_reserves.h"
#define WS_LIMIT 128
#define WS_COUNT (sizeof(wsTemplates)/sizeof(wsTemplates[0]))
static const uint32_t cropMasks[6]={0x18000,0xf009,0xf949,0xf06b,0xf6b9,0xf04d};
static const uint32_t mineralMasks[6]={0,0x45,0x65,0x41,0x43,0x4b};
static WSPlanIsland planned[WS_LIMIT];
static uint32_t rngState;
static uint32_t wsRandom(void){uint32_t n=rngState;n^=n<<13;n^=n>>17;n^=n<<5;return rngState=n;}
#include "../../source/engine_resume/ai_food/experiment_runtime/selection_policy.inc"
static int wsAdd(uint32_t index,uint32_t*count){if(*count>=WS_LIMIT)return 0;const WSTemplate*t=&wsTemplates[index];WSPlanIsland*p=&planned[(*count)++];memset(p,0,sizeof(*p));p->templateIndex=index;p->width=t->width;p->height=t->height;p->cultures=t->cultures;p->climate=t->climate;p->cropMask=cropMasks[t->climate];return 1;}
static int wsPop(uint32_t n){int count=0;while(n){count++;n&=n-1;}return count;}
static int wsSeparated(const WSPlanIsland*a,const WSPlanIsland*b,uint32_t gap){return a->x+a->width+gap<=b->x||b->x+b->width+gap<=a->x||a->y+a->height+gap<=b->y||b->y+b->height+gap<=a->y;}
#include "../../source/engine_resume/ai_food/experiment_runtime/balanced_layout.inc"
__declspec(dllexport) uint32_t FixtureABI(void){return (uint32_t)sizeof(WSWorldSettings);}
__declspec(dllexport) uint32_t FixtureCatalogue(void){return WS_COUNT+(uint32_t)(sizeof wsSceneEasy+sizeof wsSceneMedium+sizeof wsSceneHard)*0u;}
__declspec(dllexport) int FixtureReserves(const WSWorldSettings*s,WSPlanIsland*out){if(!out||!wsConfigureWorldSize(s))return -1;memcpy(out,wsActiveShipReserves,wsActiveShipReserveCount*sizeof(*out));return (int)wsActiveShipReserveCount;}
__declspec(dllexport) int FixtureEligible(const WSWorldSettings*s,uint32_t index){return index<WS_COUNT&&wsConfigureWorldSize(s)&&wsEligible(&wsTemplates[index],s);}
__declspec(dllexport) int FixtureChoose(const WSWorldSettings*s,uint32_t seed,uint32_t attempt,uint32_t culture,int climate,int ore,int whale,int empty,int faction){if(!wsConfigureWorldSize(s))return -1;rngState=seed?seed:0x15032026;wsSelectionBeginAttempt(s,(int)attempt);return wsChoose(s,culture,climate,ore,whale,empty,faction);}
__declspec(dllexport) int FixtureFills(const WSWorldSettings*s,uint32_t seed,WSPlanIsland*out){if(!s||!out||s->islandCount<1||s->islandCount>WS_LIMIT||!wsConfigureWorldSize(s))return 0;rngState=seed?seed:0x15032026;wsSelectionBeginAttempt(s,0);uint32_t n=0;while(n<(uint32_t)s->islandCount){int pick=wsChooseBalancedFill(s,n);if(pick<0||!wsAdd((uint32_t)pick,&n))return 0;}memcpy(out,planned,n*sizeof(*out));return (int)n;}
__declspec(dllexport) int LayoutPack(const WSWorldSettings*s,const WSPlanIsland*input,uint32_t count,uint32_t seed,WSPlanIsland*out){
 if(!input||!out||!count||count>WS_LIMIT||!wsConfigureWorldSize(s)||s->spacing<0)return 0;
 memcpy(planned,input,count*sizeof(*input));rngState=seed;
 if(!wsPack(count,(uint32_t)s->spacing)||rngState!=seed)return 0;
 memcpy(out,planned,count*sizeof(*out));return 1;
}
__declspec(dllexport) int LayoutCompact(const WSWorldSettings*s,const WSPlanIsland*input,uint32_t count,WSPlanIsland*out){
 if(!input||!out||!count||count>WS_LIMIT||!wsConfigureWorldSize(s)||s->spacing<0||(uint32_t)s->spacing>wsWorld/2)return 0;
 memcpy(planned,input,count*sizeof(*input));
 if(!wsCompactPack(count,(uint32_t)s->spacing))return 0;
 memcpy(out,planned,count*sizeof(*out));return 1;
}
__declspec(dllexport) int SelectPlan(const WSWorldSettings*s,uint32_t seed,WSPlanIsland*out,uint32_t*usedAttempt){
 if(!s||!out||!usedAttempt||s->islandCount<1||s->islandCount>WS_LIMIT||s->spacing<0||!wsConfigureWorldSize(s))return 0;
 rngState=seed?seed:0x15032026;
 for(int attempt=0;attempt<32;attempt++){
  wsSelectionBeginAttempt(s,attempt);uint32_t n=0,seen=0,climates=0;int failed=0;
  for(int c=0;c<8;c++)if((s->cultures&(1u<<c))&&!(seen&(1u<<c))){int pick=wsChoose(s,1u<<c,-1,0,0,0,0);if(pick<0)return 0;if(!wsAdd((uint32_t)pick,&n))return 0;seen|=wsTemplates[pick].cultures;}
  for(int f=1;f<=2;f++)if(s->factions&(uint32_t)f){int pick=wsChoose(s,0,-1,0,0,0,f);if(pick<0||!wsAdd((uint32_t)pick,&n))return 0;}
  for(uint32_t i=0;i<n;i++)climates|=1u<<planned[i].climate;
  for(int c=0;c<6;c++)if(!(climates&(1u<<c))){int pick=wsChoose(s,0,c,0,0,1,0);if(pick<0||!wsAdd((uint32_t)pick,&n))return 0;}
  const uint32_t need[]={0x20,8,4,2,1};
  for(uint32_t r=0;r<sizeof(need)/sizeof(need[0]);r++){int placed=0;for(uint32_t i=0;i<n;i++){WSPlanIsland*p=&planned[i];const WSTemplate*t=&wsTemplates[p->templateIndex];if((mineralMasks[p->climate]&need[r])&&wsPop(p->mineralMask)<t->oreSlots){p->mineralMask|=need[r];placed=1;break;}}
   if(!placed){int pick=wsChoose(s,0,-1,(int)need[r],0,1,0);if(pick<0)return 0;if(!wsAdd((uint32_t)pick,&n)){failed=1;break;}planned[n-1].mineralMask=need[r];}
  }if(failed)continue;
  uint32_t whales=0;for(uint32_t i=0;i<n;i++)whales+=wsTemplates[planned[i].templateIndex].whales;
  if(!whales){int pick=wsChoose(s,0,-1,0,1,1,0);if(pick<0||!wsAdd((uint32_t)pick,&n))return 0;}
  if(n>(uint32_t)s->islandCount)continue;
  while(n<(uint32_t)s->islandCount){int pick=wsChooseBalancedFill(s,n);if(pick<0||!wsAdd((uint32_t)pick,&n)){failed=1;break;}}
  if(failed||!wsPack(n,(uint32_t)s->spacing))continue;
  memcpy(out,planned,n*sizeof(*out));*usedAttempt=(uint32_t)attempt;return (int)n;
 }return 0;
}
