/* Isolated Windows-native execution of the production layout helper.
 * No Anno process, hook, files, DLLs or engine objects are accessed.
 */
#include <stdint.h>
#include <string.h>
#include "../../source/engine_resume/ai_food/experiment_runtime/world_backend.h"
#define WS_LIMIT 128
#define WS_WORLD 1024
static WSPlanIsland planned[WS_LIMIT];
static uint32_t rngState;
#include "../../source/engine_resume/ai_food/experiment_runtime/world_ship_reserves.h"
static int wsSeparated(const WSPlanIsland*a,const WSPlanIsland*b,uint32_t gap){return a->x+a->width+gap<=b->x||b->x+b->width+gap<=a->x||a->y+a->height+gap<=b->y||b->y+b->height+gap<=a->y;}
#include "../../source/engine_resume/ai_food/experiment_runtime/balanced_layout.inc"
__declspec(dllexport) int LayoutPack(const WSPlanIsland*input,uint32_t count,uint32_t spacing,uint32_t seed,WSPlanIsland*out){
 if(!input||!out||!count||count>WS_LIMIT)return 0;
 memcpy(planned,input,count*sizeof(*input));rngState=seed;
 if(!wsPack(count,spacing)||rngState!=seed)return 0;
 memcpy(out,planned,count*sizeof(*out));return 1;
}
__declspec(dllexport) int LayoutCompact(const WSPlanIsland*input,uint32_t count,uint32_t spacing,WSPlanIsland*out){
 if(!input||!out||!count||count>WS_LIMIT||spacing>256)return 0;
 memcpy(planned,input,count*sizeof(*input));
 if(!wsCompactPack(count,spacing))return 0;
 memcpy(out,planned,count*sizeof(*out));return 1;
}
