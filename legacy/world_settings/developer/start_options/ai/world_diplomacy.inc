/* Include at the end of world_ai.c, after its checked native-memory helpers.
 * Policy is stored only on ordinary CPU controllers, in COMP.SPEZFLAG. The
 * exact-byte candidate gates only their existing native initiating requests.
 * Native bits 0..7 survive; mode occupies 8..9, cadence 10..15, tag 16..31.
 * Call once after both controller validators pass, before reporting success.
 */
#define WS_DIPLOMACY_TAG UINT32_C(0x57530000)
__declspec(dllexport) int WorldSettingsBindAIDiplomacy(void *world,int32_t expected,int32_t mode,void *approvedAI,char *error,uint32_t cap){
 if(mode<0||mode>3||expected<0||expected>3)return wsAIError(error,cap,"AI diplomacy selection is outside the supported range.");
 if(!WorldSettingsCheckAIControllers(world,expected,approvedAI,error,cap))return 0;
 unsigned char *a=(unsigned char*)approvedAI;
 void *table=wsAIPointer(world,0x210);
 unsigned char *targets[3]={0};uint32_t before[3]={0},after[3]={0};uint32_t found=0;
 for(uint32_t id=0;id<32;id++){
  void *player=wsAIPointer(table,8+id*8);uint16_t type=0;
  if(!player)continue;
  if(!wsAIRead((unsigned char*)player+0x9c,&type,2))return wsAIError(error,cap,"AI diplomacy player identity could not be read.");
  if(type!=12)continue; /* Human, Pirates, Venice and all cultures retain stock diplomacy. */
  unsigned char *controller=(unsigned char*)wsAIPointer(player,0x18);
  void *cv=wsAIPointer(controller,0);uint32_t cpu=0,suspend=0,disabled=0,flags=0;
  if((cv!=a+0x88128&&cv!=a+0x84fc8)||!wsAIRead(controller+0xa4c,&cpu,4)||cpu!=12||
   !wsAIRead(controller+0xab4,&suspend,4)||!wsAIRead(controller+0xab0,&disabled,4)||!wsAIRead(controller+0xab8,&flags,4))return wsAIError(error,cap,"AI diplomacy controller is not the verified native type.");
  if(suspend||disabled)continue;
  if(found>=3||!wsAIWritable(controller+0xab8,4))return wsAIError(error,cap,"AI diplomacy storage is outside the verified writable range.");
  if(flags&UINT32_C(0xffffff00))return wsAIError(error,cap,"AI diplomacy storage already contains unsupported flags. No policy was changed.");
  targets[found]=controller+0xab8;before[found]=flags;after[found]=WS_DIPLOMACY_TAG|((uint32_t)mode<<8)|(flags&255);found++;
 }
 if(found!=(uint32_t)expected)return wsAIError(error,cap,"AI diplomacy controller count differs from the selected opponents. No policy was changed.");
 /* No writes until all identities, flags and destinations have passed. */
 for(uint32_t i=0;i<found;i++)memcpy(targets[i],after+i,4);
 for(uint32_t i=0;i<found;i++){
  uint32_t observed=0;
  if(!wsAIRead(targets[i],&observed,4)||observed!=after[i]){
   for(uint32_t j=0;j<found;j++)if(wsAIWritable(targets[j],4))memcpy(targets[j],before+j,4);
   return wsAIError(error,cap,"AI diplomacy policy did not verify and was restored. Start is blocked.");
  }
 }
 if(error&&cap)error[0]=0;return 1;
}
