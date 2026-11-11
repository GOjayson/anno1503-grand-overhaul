/* Per-controller native COMP policies. Fresh settings are consumed exactly
 * once after the existing special-controller certificate. Loads only validate
 * their own saved tags; no remembered menu choice is applied to a checkpoint.
 * No draw, visibility, ship-damage, owner, route or native clock field changes. */
#define WS_FACTION_PIRATE_TAG UINT32_C(0x57540000)
#define WS_FACTION_MERCHANT_TAG UINT32_C(0x57550000)
typedef struct WSFactionActivityTarget {unsigned char*controller;uint32_t before,after;} WSFactionActivityTarget;
static int wsFactionActivityExpected;
static uint32_t wsFactionActivityFactions;
static int32_t wsFactionActivityFrequency=1,wsFactionActivityStrength=1,wsFactionActivityMerchant=1;

static int wsFactionActivityDecode(uint32_t flags,uint32_t type,uint32_t*frequency,uint32_t*strength){
 uint32_t f=1,s=1;if(type!=15u&&type!=16u)return 0;
 if(flags&UINT32_C(0xffffff00)){
  uint32_t tag=type==15u?WS_FACTION_PIRATE_TAG:WS_FACTION_MERCHANT_TAG;
  uint32_t reserved=type==15u?UINT32_C(0x0000f000):UINT32_C(0x0000fc00);
  if((flags&UINT32_C(0xffff0000))!=tag||(flags&reserved))return 0;
  f=(flags>>8)&3u;if(type==15u)s=(flags>>10)&3u;
  if(f>2u||s>2u)return 0;
 }
 if(frequency)*frequency=f;if(strength)*strength=s;return 1;
}
static int wsFactionActivityFind(void*world,void*approved,uint32_t type,uint32_t enabled,
 WSFactionActivityTarget*out,char*error,uint32_t cap){
 WSFactionActivityTarget target={0};uint32_t found=0;
 unsigned char*w=(unsigned char*)WS_AI_WORLD_MODULE(),*a=(unsigned char*)approved;
 if(!out||!w||(type!=15u&&type!=16u)||enabled>2u)
  return wsAIError(error,cap,"Faction activity has no supported native identity.");
 void*worldVT=wsAIPointer(world,0),*table=wsAIPointer(world,0x210);
 if((worldVT!=w+0xff1d8u&&worldVT!=w+0xff650u)||wsAIPointer(worldVT,0xf0)!=w+0xd1910u||
    wsAIPointer(table,0)!=w+0xfdbc0u||wsAIPointer(w+0xfdbc0u,0x10)!=w+0xc6d80u||
    wsAIPointer(w+0xfdbc0u,0x18)!=w+0x95990u)
  return wsAIError(error,cap,"Faction activity world or player table is not the verified native type.");
 for(uint32_t id=0;id<32u;id++){
  void*player=wsAIPointer(table,8u+id*8u);if(!player)continue;
  uint32_t actualId=UINT32_MAX;uint16_t actualType=0,culture=0;unsigned char alias[10]={0};
  if(wsAIPointer(player,0)!=w+0xfabe0u||!wsAIRead((unsigned char*)player+8,&actualId,4)||actualId!=id||
     wsAIPointer(player,0x10)!=world||!wsAIRead((unsigned char*)player+0x9c,&actualType,2)||
     !wsAIRead((unsigned char*)player+0x9e,&culture,2)||!wsAIRead((unsigned char*)player+0x68,alias,sizeof alias))
   return wsAIError(error,cap,"Faction activity found an unsupported player identity.");
  int pirate=actualType==15u||culture==11u||!memcmp(alias,"PIRAT01",8);
  int merchant=actualType==16u||culture==12u||!memcmp(alias,"VENEZIA01",10);
  if((type==15u&&!pirate)||(type==16u&&!merchant))continue;
  if((pirate&&merchant)||actualType!=type||culture!=(type==15u?11u:12u)||
     memcmp(alias,type==15u?"PIRAT01":"VENEZIA01",type==15u?8u:10u)||!a||++found>1u)
   return wsAIError(error,cap,"Faction activity found a missing, duplicated or conflicting special faction.");
  unsigned char*c=(unsigned char*)wsAIPointer(player,0x18);void*vt=wsAIPointer(c,0);
  uint32_t normal=type==15u?0x88ba8u:0x883c0u,classic=type==15u?0x85aa0u:0x85258u;
  int isClassic=vt==a+classic;uint32_t cpu=0;uint16_t owner=UINT16_MAX;MEMORY_BASIC_INFORMATION allocation;
  if((vt!=a+normal&&vt!=a+classic)||!VirtualQuery(vt,&allocation,sizeof allocation)||allocation.AllocationBase!=a||
     wsAIPointer(vt,0)!=a+(isClassic?0x6480u:0x80e0u)||wsAIPointer(vt,8)!=a+(isClassic?0x4260u:0x6090u)||
     wsAIPointer(vt,0x10)!=a+(isClassic?0x4a10u:0x6640u)||wsAIPointer(c,8)!=world||
     !wsAIRead(c+0xa4c,&cpu,4)||cpu!=type||!wsAIRead(c+0xa64,&owner,2)||owner!=id||
     !wsAIRead(c+0xab8,&target.before,4))
   return wsAIError(error,cap,"Faction activity controller is outside the approved private AI module.");
  target.controller=c;target.after=target.before;
 }
 if(enabled<2u&&found!=enabled)return wsAIError(error,cap,"Faction activity presence differs from the selected factions.");
 *out=target;return 1;
}
#include "merchant_activity.inc"

void WorldSettingsResetFactionActivity(void){wsFactionActivityExpected=0;wsFactionActivityFactions=0;wsFactionActivityFrequency=wsFactionActivityStrength=wsFactionActivityMerchant=1;}
void WorldSettingsExpectFactionActivity(uint32_t factions,int32_t frequency,int32_t strength,int32_t merchant){
 WorldSettingsResetFactionActivity();wsFactionActivityExpected=1;wsFactionActivityFactions=factions;
 wsFactionActivityFrequency=frequency;wsFactionActivityStrength=strength;wsFactionActivityMerchant=merchant;
}
int WorldSettingsBindFactionActivity(void*world,void*approved,char*error,uint32_t cap){
 WSFactionActivityTarget targets[2]={{0}};uint32_t factions=wsFactionActivityFactions;
 int frequency=wsFactionActivityFrequency,strength=wsFactionActivityStrength,merchant=wsFactionActivityMerchant;
 int expected=wsFactionActivityExpected;WorldSettingsResetFactionActivity();
 if(!expected||(factions&~3u)||frequency<0||frequency>2||strength<0||strength>2||merchant<0||merchant>2)
  return wsAIError(error,cap,"Fresh faction activity settings have no unique valid start scope.");
 if(!wsFactionActivityFind(world,approved,15u,!!(factions&1u),targets,error,cap))return 0;
 if(targets[0].controller){
  if(targets[0].before&UINT32_C(0xffffff00))return wsAIError(error,cap,"Pirate policy storage already contains unsupported flags. No policy was changed.");
  targets[0].after=WS_FACTION_PIRATE_TAG|((uint32_t)frequency<<8)|((uint32_t)strength<<10)|(targets[0].before&255u);
 }
 if(!wsFactionActivityMerchantTarget(world,approved,factions,merchant,targets+1,error,cap))return 0;
 for(uint32_t i=0;i<2u;i++)if(targets[i].controller&&!wsAIWritable(targets[i].controller+0xab8,4))
  return wsAIError(error,cap,"Faction policy storage is not writable. No policy was changed.");
 for(uint32_t i=0;i<2u;i++)if(targets[i].controller)memcpy(targets[i].controller+0xab8,&targets[i].after,4);
 for(uint32_t i=0;i<2u;i++)if(targets[i].controller){uint32_t observed=0;
  if(!wsAIRead(targets[i].controller+0xab8,&observed,4)||observed!=targets[i].after){
   for(uint32_t j=0;j<2u;j++)if(targets[j].controller&&wsAIWritable(targets[j].controller+0xab8,4))memcpy(targets[j].controller+0xab8,&targets[j].before,4);
   return wsAIError(error,cap,"Faction policy commit failed verification and was restored.");
  }
 }
 if(error&&cap)error[0]=0;return 1;
}
int WorldSettingsValidateFactionActivityWorld(void*world,char*error,uint32_t cap){
#ifdef WS_FACTION_ACTIVITY_APPROVED_MODULE
 void*approved=WS_FACTION_ACTIVITY_APPROVED_MODULE();
#elif defined(WS_AI_FIXTURE)
 void*approved=NULL;
#else
 void*approved=WorldSettingsLoadedAIModule();
#endif
 for(uint32_t type=15u;type<=16u;type++){
  WSFactionActivityTarget target={0};if(!wsFactionActivityFind(world,approved,type,2u,&target,error,cap))return 0;
  if(target.controller&&!wsFactionActivityDecode(target.before,type,NULL,NULL))
   return wsAIError(error,cap,"The checkpoint contains an unsupported faction activity policy.");
 }
 if(error&&cap)error[0]=0;return 1;
}
