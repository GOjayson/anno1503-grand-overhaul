/* The native reveal property also relaxes the mouse selection ownership gate.
 * Keep that gate in its ordinary state at the two audited interaction calls,
 * and authorize the shared building/shipyard command interfaces independently
 * of visibility. No World, building, city, or player field is changed here. */
typedef uintptr_t (*WSVisibilityBuildingCommand)(void*,uint32_t,int32_t,void*);
typedef uintptr_t (*WSVisibilityInteractionGetter)(void*,uint32_t,uintptr_t,uintptr_t);
#ifndef WS_VISIBILITY_NATIVE_BUILDING_COMMAND
#define WS_VISIBILITY_NATIVE_BUILDING_COMMAND(module,rva) ((WSVisibilityBuildingCommand)((module)+(rva)))
#endif
#ifndef WS_VISIBILITY_NATIVE_INTERACTION_GETTER
#define WS_VISIBILITY_NATIVE_INTERACTION_GETTER(module) ((WSVisibilityInteractionGetter)((module)+0xd1910u))
#endif

/* Read the transport marker without imposing modded square-map dimensions on
 * ordinary native worlds. An invalid/reserved marked context never delegates. */
static int wsVisibilityControlPolicy(void*world,unsigned char*module,uint32_t*flags){
 void*vt=wsCertPointer(world,0);
 return module&&(vt==module+0xff1d8u||vt==module+0xff650u)&&
  wsCertRead((unsigned char*)world+0x6eecu,flags,4);
}
static int wsVisibilityControlTarget(unsigned char*module,uint32_t rva){
 return module&&wsVisibilityWithinModule(module,module+rva,1)&&wsCertMemory(module+rva,1,1);
}
static int wsVisibilityControlOwnHouse(const WSVisibilityWorld*v,void*house){
 void*vt=wsCertPointer(house,0);int known=0;
 for(size_t i=0;i<sizeof wsVisibilityProductionVtables/sizeof wsVisibilityProductionVtables[0];i++)
  if(vt==v->module+wsVisibilityProductionVtables[i]){known=1;break;}
 if(!known||!wsCertMemory(house,0x20u,0)||
    wsCertPointer(vt,0x30u)!=v->module+0x84fc0u||
    wsCertPointer(vt,0x38u)!=v->module+0x84fe0u||
    wsCertPointer(vt,0x40u)!=v->module+0x84ff0u)return 0;
 void*city=wsCertPointer(house,0x18u);void*island=wsCertPointer(city,0x20u);
 void*owner=wsCertPointer(city,0x28u);void*islandVT=wsCertPointer(island,0);
 if(wsCertPointer(city,0)!=v->module+0xfc678u||
    (islandVT!=v->module+0xf2da8u&&islandVT!=v->module+0xf33e8u&&islandVT!=v->module+0xf37a0u)||
    wsCertPointer(island,0x38u)!=v->world||wsCertPointer(owner,0)!=v->module+0xfabe0u||
    wsCertPointer(owner,0x10u)!=v->world)return 0;
 void*registered[WS_VISIBILITY_ISLAND_LIMIT],*cities[15];uint16_t xy[2],box[4];uint32_t ownerID;
 if(!wsCertRead(v->world+0x6640u,registered,sizeof registered)||
    !wsCertRead((unsigned char*)island+0x68u,cities,sizeof cities)||
    !wsCertRead((unsigned char*)island+8u,box,sizeof box)||
    !wsCertRead((unsigned char*)house+0xau,xy,sizeof xy)||
    !wsCertRead((unsigned char*)owner+8u,&ownerID,4))return 0;
 known=0;for(size_t i=0;i<WS_VISIBILITY_ISLAND_LIMIT;i++)if(registered[i]==island){known=1;break;}if(!known)return 0;
 known=0;for(size_t i=0;i<15u;i++)if(cities[i]==city){known=1;break;}if(!known)return 0;
 if(!box[2]||!box[3]||(uint32_t)box[0]+box[2]>v->width||(uint32_t)box[1]+box[3]>v->height||
    xy[0]<box[0]||xy[1]<box[1]||(uint32_t)xy[0]>=(uint32_t)box[0]+box[2]||
    (uint32_t)xy[1]>=(uint32_t)box[1]+box[3])return 0;
 void*table=wsCertPointer(v->world,0x210u);
 /* HE's in-game World Settings player is player zero. A changed spectator or
  * player binding cannot turn visibility permission into command authority. */
 return v->viewer==0u&&ownerID==0u&&wsCertPointer(table,0)==v->module+0xfdbc0u&&
  wsCertPointer(table,8u)==owner;
}
static uintptr_t wsVisibilityControlCommand(void*client,uint32_t selector,int32_t value,void*house,int queue){
 unsigned char*frame=(unsigned char*)WS_CERT_MODULE("AnnoFrame.dll");
 unsigned char*worldModule=(unsigned char*)WS_CERT_MODULE("AnnoWelt.dll");
 void*vt=wsCertPointer(client,0);uint32_t rva=0,flags=0;
 if(!frame||!worldModule||!wsCertMemory(client,0x20u,0))return 0;
 if(vt==frame+0xa7170u)rva=queue?0x785d0u:0x78630u;
 else if(vt==frame+0xa7418u)rva=queue?0x7d230u:0x7d340u;
 else return 0;
 if(!wsVisibilityControlTarget(frame,rva))return 0;
 void*world=wsCertPointer(client,0x10u);
 if(!wsVisibilityControlPolicy(world,worldModule,&flags))return 0;
 if(!(flags&WS_VISIBILITY_POLICY_MASK))return WS_VISIBILITY_NATIVE_BUILDING_COMMAND(frame,rva)(client,selector,value,house);
 WSVisibilityWorld view;
 if(!wsVisibilityWorldRead(world,&view)||view.marked!=1)return 0;
 void*game=wsCertPointer(client,0x18u);void*gameVT=wsCertPointer(game,0);
 if((gameVT!=frame+0xa0ce8u&&gameVT!=frame+0xa1788u)||
    wsCertPointer(game,0x28u)!=world||wsCertPointer(game,0x40u)!=client||
    !wsVisibilityControlOwnHouse(&view,house))return 0;
 return WS_VISIBILITY_NATIVE_BUILDING_COMMAND(frame,rva)(client,selector,value,house);
}
__declspec(dllexport) uintptr_t WorldSettingsVisibilityBuildingCommand(void*client,uint32_t selector,int32_t value,void*house){
 return wsVisibilityControlCommand(client,selector,value,house,0);
}
__declspec(dllexport) uintptr_t WorldSettingsVisibilityShipQueue(void*client,uint32_t selector,int32_t value,void*house){
 return wsVisibilityControlCommand(client,selector,value,house,1);
}
__declspec(dllexport) uintptr_t WorldSettingsVisibilityInteractionProperty(void*world,uint32_t property,uintptr_t third,uintptr_t fourth){
 unsigned char*module=(unsigned char*)WS_CERT_MODULE("AnnoWelt.dll");uint32_t flags=0;
 if(!wsVisibilityControlPolicy(world,module,&flags))return property==5u?1u:0u;
 if(flags&WS_VISIBILITY_POLICY_MASK){
  if(property==5u)return 1u; /* Native ordinary foreign-selection check. */
  WSVisibilityWorld view;if(!wsVisibilityWorldRead(world,&view)||view.marked!=1)return 0;
 }
 if(!wsVisibilityControlTarget(module,0xd1910u)||
    wsCertPointer(wsCertPointer(world,0),0xf0u)!=module+0xd1910u)return property==5u?1u:0u;
 return WS_VISIBILITY_NATIVE_INTERACTION_GETTER(module)(world,property,third,fourth);
}
