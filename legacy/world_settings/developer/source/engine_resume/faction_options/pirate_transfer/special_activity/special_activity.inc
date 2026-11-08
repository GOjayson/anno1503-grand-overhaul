/* Private candidate: read-only post-profile native special-faction check.
 * Both approved AMD64 controller factories and shared init/getters were read
 * from original History binaries; no ordinary CPU disabled flag is assumed.
 * World flags bit20 is the native inverse Pirates option, not a culture bit.
 */
static uint32_t wsU32Special(const unsigned char *p){uint32_t value;memcpy(&value,p,sizeof value);return value;}
__declspec(dllexport) int WorldSettingsCheckSpecialControllers(void *world,uint32_t factions,void *approvedAI,char *error,uint32_t cap){
 if((factions&~3u)||!approvedAI)return wsAIError(error,cap,"Special-faction selection or approved AI payload is missing.");
 unsigned char *w=(unsigned char*)WS_AI_WORLD_MODULE(),*a=(unsigned char*)approvedAI;
 void *vt=wsAIPointer(world,0),*table=wsAIPointer(world,0x210);uint32_t flags=0;unsigned char mode=255;
 if(!w||(vt!=w+0xff1d8&&vt!=w+0xff650)||wsAIPointer(vt,0xf0)!=w+0xd1910||
    wsAIPointer(table,0)!=w+0xfdbc0||!wsAIRead((unsigned char*)world+0x6e48,&mode,1)||
    !wsAIRead((unsigned char*)world+0x6eec,&flags,4))return wsAIError(error,cap,"Loaded special factions have no verified native world settings.");
 typedef uint32_t (__cdecl *WSWorldProperty)(void*,uint32_t);
 WSWorldProperty getWorld=(WSWorldProperty)wsAIPointer(vt,0xf0);
 if(getWorld(world,0)!=mode||getWorld(world,6)!=flags||mode!=0)return wsAIError(error,cap,"Loaded special-faction world mode or native flags differ.");
 if((flags&0x20u)!=((factions&1u)?0u:0x20u))return wsAIError(error,cap,"The native Pirates option differs from World Settings.");
 uint32_t found[2]={0,0};
 for(uint32_t id=0;id<32;id++){
  void *player=wsAIPointer(table,8+id*8);if(!player)continue;
  uint16_t type=0,culture=0;uint32_t actualId=UINT32_MAX;unsigned char alias[10]={0};
  if(wsAIPointer(player,0)!=w+0xfabe0||!wsAIRead((unsigned char*)player+0x9c,&type,2)||
     !wsAIRead((unsigned char*)player+0x9e,&culture,2)||!wsAIRead((unsigned char*)player+8,&actualId,4)||actualId!=id||
     wsAIPointer(player,0x10)!=world||!wsAIRead((unsigned char*)player+0x68,alias,sizeof alias))return wsAIError(error,cap,"A loaded special-faction player has an unsupported native identity.");
  int pirate=type==15||culture==11||!memcmp(alias,"PIRAT01",8);
  int venetian=type==16||culture==12||!memcmp(alias,"VENEZIA01",10);
  if(!pirate&&!venetian)continue;
  if(pirate&&venetian)return wsAIError(error,cap,"Loaded Pirates and Venetians have conflicting identities.");
  uint32_t bit=pirate?1u:2u,index=pirate?0u:1u;
  if(!(factions&bit)||type!=(pirate?15:16)||culture!=(pirate?11:12)||
     memcmp(alias,pirate?"PIRAT01":"VENEZIA01",pirate?8:10)||++found[index]!=1)return wsAIError(error,cap,"Loaded Pirates or Venetians differ from the selected identity.");
  void *controller=wsAIPointer(player,0x18),*cv=wsAIPointer(controller,0);uint32_t controllerType=0,suspend=UINT32_MAX;uint16_t owner=UINT16_MAX;unsigned char thinking=255;
  uint32_t normalVtable=pirate?0x88ba8u:0x883c0u,classicVtable=pirate?0x85aa0u:0x85258u;
  int classic=cv==a+classicVtable;uint32_t classVtable=classic?classicVtable:normalVtable;
  uint32_t setter=classic?0x4260u:0x6090u,getter=classic?0x4a10u:0x6640u,initializer=classic?0x6480u:0x80e0u;
  MEMORY_BASIC_INFORMATION allocation;
  if(cv!=a+classVtable||!VirtualQuery(cv,&allocation,sizeof allocation)||allocation.AllocationBase!=a||
     wsAIPointer(cv,0)!=a+initializer||wsAIPointer(cv,8)!=a+setter||wsAIPointer(cv,0x10)!=a+getter||
     !wsAIRead((unsigned char*)controller+0xa4c,&controllerType,4)||controllerType!=type||
     !wsAIRead((unsigned char*)controller+0xa64,&owner,2)||owner!=id||
     !wsAIRead((unsigned char*)controller+0xab4,&suspend,4)||!wsAIRead((unsigned char*)controller+0x1e9d,&thinking,1))return wsAIError(error,cap,"A special faction is not using its verified Food AI controller.");
  unsigned char property[32]={0};
  typedef int (__cdecl *WSSpecialGetter)(void*,uint32_t,void*);
  if(((WSSpecialGetter)(a+getter))(controller,0x1a,property)!=1||wsU32Special(property+0x18)!=suspend||suspend!=0||thinking!=1)return wsAIError(error,cap,pirate?"The selected Pirates controller is suspended or not thinking.":"The selected Venetians controller is suspended or not thinking.");
 }
 if(found[0]!=((factions&1u)!=0)||found[1]!=((factions&2u)!=0))return wsAIError(error,cap,"Loaded Pirates or Venetians are missing after native profile application.");
 if(error&&cap)error[0]=0;return 1;
}
