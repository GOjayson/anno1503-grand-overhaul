"""Native visibility policy/scene and isolated display-memory adapter fixtures.

The memory graph is synthetic. These tests neither run Anno nor establish GPU
presentation, enemy AI behavior or native exploration/save events.
"""
import ctypes as C
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'src/anno1503_overhaul/native/world_options'

FIXTURE = r'''
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#ifndef _WIN32
#define __declspec(x) __attribute__((visibility("default")))
#endif
#include "start_visibility_policy.h"
typedef struct WSWorldSettings {int32_t mapVisibility,enemyVisibility;} WSWorldSettings;
typedef struct WSBuffer {unsigned char*data;uint32_t size,capacity;} WSBuffer;
static uint16_t wsU16(const void*p){uint16_t n;memcpy(&n,p,2);return n;}
static uint32_t wsU32(const void*p){uint32_t n;memcpy(&n,p,4);return n;}
static void wsPut16(void*p,uint16_t n){memcpy(p,&n,2);}
static void wsPut32(void*p,uint32_t n){memcpy(p,&n,4);}
static int wsTag(const unsigned char*p,const char*tag){size_t n=strlen(tag);return n<=12&&!memcmp(p,tag,n)&&(n==12||!p[n]);}
static void wsMessage(char*out,uint32_t cap,const char*msg){if(out&&cap){snprintf(out,cap,"%s",msg);out[cap-1]=0;}}
#include "start_visibility_scene.inc"
__declspec(dllexport) uint32_t policy(int32_t map,int32_t enemy){return wsVisibilityEncode(map,enemy);}
__declspec(dllexport) int decode(uint32_t flags,int32_t*out){return wsVisibilityDecode(flags,out,out+1);}
__declspec(dllexport) int scene(int32_t map,int32_t enemy,uint32_t before,uint32_t malformed,uint32_t*out){
 unsigned char raw[128]={0};WSBuffer b={raw,80,sizeof raw};WSWorldSettings s={map,enemy};char error[128];
 memcpy(raw+32,"HEAD",4);wsPut32(raw+44,32);wsPut32(raw+64,before);
 if(malformed==1)wsPut32(raw+44,31);
 if(malformed==2)b.size=79;
 if(malformed==3){memcpy(raw+80,"HEAD",4);wsPut32(raw+92,32);b.size=128;}
 unsigned char prior[128];memcpy(prior,raw,sizeof raw);
 int result=wsVisibilityScene(&b,&s,error,sizeof error);
 out[0]=wsU32(raw+64);out[1]=wsExpectedVisibilityCode;out[2]=!memcmp(prior,raw,sizeof raw);
 return result;
}
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
static unsigned char moduleBytes[0x1300000],worldBytes[0x8000],islandBytes[0x200],actorBytes[0x400],humanBytes[0x600],enemyBytes[0x600],humanShip[0x400],shipNode[24],players[264],listBytes[96],quadBytes[0x390],tableBytes[32],drawRendererBytes[0x4d0],mapBytes[48],pixelBytes[4096],replacementPixels[4096],renderBlocks[0x681000];
static unsigned char cityBytes[0x800],cityNode[24],buildingBytes[2][0x100],catalogueBytes[0x9000],definitionBytes[0x80],neighbourDefinition[0x80],physicalTiles[16*16*8],rendererBytes[8],rendererVtable[0x190];static void*buildingVector[2];
static uint32_t spyCalls,spyFailure,spyMasked,spyMapFlags,spyAnimalCalls,spyAnimalMode,islandReads,spyRefreshCalls,spyRefreshReenter,spyMapReplace;
static uint32_t spyResidentCalls,spyNativeRva,spyExcludeReturn,spyOccurrenceFlags;
static uint32_t spyStaticCalls;static const float*spyStaticPosition;
static uint32_t spyViewportCalls,spyViewportReset,spyDrawObservedViewport;static int32_t spyViewport[4];
static uint32_t visibilityReadChecks,stackQueryFault;
static uint32_t spyMapPartial,spyMapHeightPixels,spyMapRectOriginal,spyMapReset,spyMapOwnerColor=10;static int32_t spyMapRect[4];
static uintptr_t spy5(void*,void*,uint32_t,uint32_t,void*);
static uintptr_t spy6(void*,void*,uint32_t,const int32_t*,uint32_t,void*);
static uintptr_t spyMap(void*,uint32_t,void*);
static uintptr_t spyAnimalLegacy(void*,uint32_t,void*);
static uintptr_t spyAnimalNew(void*,uint32_t,void*);
static uintptr_t spyAnimalClipped(void*,uint32_t,void*);
static void spyRefresh(void*,void*,uint32_t);
static uintptr_t spyResident(void*,uint32_t,void*);
static uintptr_t spyOccurrence(void*,uint32_t,void*,uint32_t);
static int spyExclude(void*,uint32_t);
static uintptr_t spyStatic(void*,void*,uint32_t,uint32_t,uint32_t,const float*);
static void spyDirtyViewport(void*,const int32_t*);
#define WS_VISIBILITY_NATIVE_DRAW5(module) spy5
#define WS_VISIBILITY_NATIVE_DRAW6(module) spy6
#define WS_VISIBILITY_NATIVE_MAP(module) spyMap
#define WS_VISIBILITY_NATIVE_WILDLIFE(module,legacy) ((legacy)?spyAnimalLegacy:spyAnimalNew)
#define WS_VISIBILITY_NATIVE_WILDLIFE_CLIPPED(module) spyAnimalClipped
#define WS_VISIBILITY_NATIVE_ACTIVITY_REFRESH(module) spyRefresh
#define WS_VISIBILITY_NATIVE_RESIDENT(module,rva) (spyNativeRva=(rva),spyResident)
#define WS_VISIBILITY_NATIVE_OCCURRENCE(module,rva) (spyNativeRva=(rva),spyOccurrence)
#define WS_VISIBILITY_NATIVE_EXCLUDE(module,rva) (spyNativeRva=(rva),spyExclude)
#define WS_VISIBILITY_NATIVE_STATIC(target) spyStatic
#define WS_VISIBILITY_NATIVE_DIRTY_VIEWPORT(module) spyDirtyViewport
#define WS_VISIBILITY_STATIC_TARGET_OK(target) 1
#define WS_VISIBILITY_LEGACY_STATIC_TARGET_OK(target) 1
#define WS_VISIBILITY_UNKNOWN_RESIDENT(target) spyResident
#define WS_VISIBILITY_UNKNOWN_OCCURRENCE(target) spyOccurrence
#define WS_VISIBILITY_UNKNOWN_TARGET_OK(module,target) 1
#define WS_CERT_MODULE(name) moduleBytes
static int wsCertMemory(const void*p,size_t n,int executable){
 visibilityReadChecks++;
 uintptr_t at=(uintptr_t)p,end;if(!at||!n||n>UINTPTR_MAX-at)return 0;end=at+n;
 while(at<end){MEMORY_BASIC_INFORMATION m;if(!VirtualQuery((void*)at,&m,sizeof m)||m.State!=MEM_COMMIT||m.Protect&(PAGE_GUARD|PAGE_NOACCESS))return 0;
  DWORD prot=m.Protect&255;if(executable&&!(prot==PAGE_EXECUTE||prot==PAGE_EXECUTE_READ||prot==PAGE_EXECUTE_READWRITE||prot==PAGE_EXECUTE_WRITECOPY))return 0;
  uintptr_t base=(uintptr_t)m.BaseAddress;if(m.RegionSize>UINTPTR_MAX-base||base+m.RegionSize<=at)return 0;
  at=base+m.RegionSize<end?base+m.RegionSize:end;
 }return 1;
}
static int wsCertRead(const void*p,void*out,size_t n){if(!out||!wsCertMemory(p,n,0))return 0;if((uintptr_t)p>=(uintptr_t)islandBytes&&(uintptr_t)p<(uintptr_t)islandBytes+sizeof islandBytes)islandReads++;memcpy(out,p,n);return 1;}
static void*wsCertPointer(const void*p,size_t off){void*r=0;uintptr_t a=(uintptr_t)p;if(!a||off>UINTPTR_MAX-a||!wsCertRead((void*)(a+off),&r,sizeof r))return 0;return r;}
static int wsMineralPersistenceWritable(void*p,size_t n){
 uintptr_t at=(uintptr_t)p,end;if(!at||!n||n>UINTPTR_MAX-at)return 0;end=at+n;
 while(at<end){MEMORY_BASIC_INFORMATION m;if(!VirtualQuery((void*)at,&m,sizeof m)||m.State!=MEM_COMMIT||m.Protect&(PAGE_GUARD|PAGE_NOACCESS))return 0;
  DWORD prot=m.Protect&255;if(!(prot==PAGE_READWRITE||prot==PAGE_WRITECOPY||prot==PAGE_EXECUTE_READWRITE||prot==PAGE_EXECUTE_WRITECOPY))return 0;
  uintptr_t base=(uintptr_t)m.BaseAddress;if(m.RegionSize>UINTPTR_MAX-base||base+m.RegionSize<=at)return 0;
  at=base+m.RegionSize<end?base+m.RegionSize:end;
 }return 1;
}
static SIZE_T fixtureStackQuery(const void*at,MEMORY_BASIC_INFORMATION*memory,SIZE_T size){
 SIZE_T result=VirtualQuery(at,memory,size);if(!stackQueryFault)return result;
 if(stackQueryFault==1)return 0;
 if(stackQueryFault==2)memory->Type=MEM_IMAGE;
 if(stackQueryFault==3)memory->Protect|=PAGE_GUARD;
 if(stackQueryFault==4)memory->State=MEM_RESERVE;
 if(stackQueryFault==5)memory->BaseAddress=(void*)((uintptr_t)at+1u);
 if(stackQueryFault==6){memory->BaseAddress=(void*)(UINTPTR_MAX-3u);memory->RegionSize=8;}
 if(stackQueryFault==7)return size-1u;
 return result;
}
#define WS_VISIBILITY_QUERY_STACK(address,memory,size) fixtureStackQuery((address),(memory),(size))
#include "start_visibility_runtime.inc"
static void fixtureMaskMap(void*map){
 WSVisibilityWorld view;WSVisibilityMapView bitmap;WSVisibilityDrawContext context;
 if(wsVisibilityWorldRead(wsCertPointer(map,0x18),&view)&&view.marked>0&&view.map==0&&
    wsVisibilityMapRead(map,&view,&bitmap)&&wsVisibilityContextRead(&view,&context))wsVisibilityMaskMapView(&bitmap,&context);
}
static uintptr_t spy5(void*world,void*list,uint32_t flags,uint32_t property,void*renderer){
 spyCalls++;
 spyDrawObservedViewport=spyViewportCalls;
 if(world!=worldBytes||list!=listBytes||flags!=17||property!=29||renderer!=drawRendererBytes)spyFailure=1;
 if(listBytes[8+0x4d]!=(unsigned char)(spyMasked?0:1))spyFailure=2;
 for(size_t i=8;i<sizeof quadBytes;i++)if(quadBytes[i]!=0xa5)spyFailure=3;
 if(spyAnimalMode){
  uint32_t before=islandReads;
  if(!wsVisibilityDrawContext||wsVisibilityDrawContext->view.world!=worldBytes)spyFailure=6;
  for(uint32_t i=0;i<20;i++)if(WorldSettingsVisibilityDrawWildlife(actorBytes,71,tableBytes))spyFailure=7;
  if(islandReads!=before||spyAnimalCalls)spyFailure=8;
 }
 return 0x1234;
}
static uintptr_t spy6(void*world,void*list,uint32_t flags,const int32_t*rect,uint32_t property,void*renderer){
 if(rect!=(int32_t*)tableBytes)spyFailure=4;
 return spy5(world,list,flags,property,renderer)+1;
}
static uintptr_t spyMap(void*map,uint32_t flags,void*rect){
 spyCalls++;spyMapFlags=flags;spyMapRectOriginal=rect==tableBytes;if(map!=mapBytes||!rect)spyFailure=5;
 if(rect)memcpy(spyMapRect,rect,16);
 if(!spyMapPartial)memset(pixelBytes,(int)((spyMapOwnerColor<<4)|11u),sizeof pixelBytes);
 else if(rect){
  uint32_t left=(uint32_t)spyMapRect[0]/4,top=(uint32_t)spyMapRect[1]/4,right=((uint32_t)spyMapRect[2]+3)/4,bottom=((uint32_t)spyMapRect[3]+3)/4;
  if(right>64||bottom>64)spyFailure=15;
  else for(uint32_t y=top;y<bottom;y++)for(uint32_t x=left;x<right;x++){
   unsigned char*p=pixelBytes+y*64+x;if(flags&2u){*p=(unsigned char)((*p&0xf0u)|11u);spyMapHeightPixels++;}
   if(flags&1u)*p=(unsigned char)((*p&15u)|(spyMapOwnerColor<<4));
  }
 }
 if(spyMapReplace){void*p=replacementPixels;memcpy(mapBytes+0x20,&p,8);memset(replacementPixels,0xcd,sizeof replacementPixels);}
 if(spyMapReset){spyMapReset=0;WorldSettingsVisibilityReset();}
 return 0x1236;
}
static uintptr_t spyAnimalLegacy(void*actor,uint32_t time,void*renderer){
 spyAnimalCalls++;if(actor!=actorBytes||time!=71||renderer!=tableBytes)spyFailure=9;return 0x2231;
}
static uintptr_t spyAnimalNew(void*actor,uint32_t time,void*renderer){
 spyAnimalCalls++;if(actor!=actorBytes||time!=71||renderer!=tableBytes)spyFailure=9;return 0x2232;
}
static uintptr_t spyAnimalClipped(void*actor,uint32_t time,void*renderer){
 spyAnimalCalls++;if(actor!=actorBytes||time!=71||renderer!=tableBytes)spyFailure=9;return 0x2233;
}
static void spyRefresh(void*world,void*city,uint32_t viewer){
 spyRefreshCalls++;
 if(world!=worldBytes||city||viewer||worldBytes[0x6ee9]>1)spyFailure=10;
 if(spyRefreshReenter){spyRefreshReenter=0;if(!WorldSettingsVisibilityWorldLoaded(world,0,0))spyFailure=11;}
}
static uintptr_t spyResident(void*actor,uint32_t time,void*renderer){spyResidentCalls++;if(actor!=actorBytes||time!=71||renderer!=tableBytes)spyFailure=12;return 0x3344;}
static uintptr_t spyOccurrence(void*actor,uint32_t time,void*renderer,uint32_t flags){spyOccurrenceFlags=flags;return spyResident(actor,time,renderer)+1;}
static int spyExclude(void*actor,uint32_t reason){if(actor!=actorBytes||reason!=4)spyFailure=13;return (int)spyExcludeReturn;}
static uintptr_t spyStatic(void*renderer,void*frame,uint32_t orientation,uint32_t phase,uint32_t flags,const float*position){spyStaticCalls++;if(renderer!=rendererBytes||frame!=quadBytes||orientation!=7||phase!=11||flags!=0xc0||position!=spyStaticPosition)spyFailure=14;return 0x4455;}
static void spyDirtyViewport(void*renderer,const int32_t*rect){spyViewportCalls++;if(renderer!=drawRendererBytes||!rect)spyFailure=16;memcpy(spyViewport,rect,sizeof spyViewport);if(spyViewportReset){spyViewportReset=0;InterlockedIncrement(&wsVisibilityMapGeneration);}}
static void ptr(void*to,void*value){memcpy(to,&value,8);}
static void prepare(uint32_t policyCode,uint16_t discovery){
 WorldSettingsVisibilityReset();memset(worldBytes,0,sizeof worldBytes);memset(islandBytes,0,sizeof islandBytes);memset(actorBytes,0,sizeof actorBytes);memset(listBytes,0,sizeof listBytes);memset(quadBytes,0xa5,sizeof quadBytes);memset(mapBytes,0,sizeof mapBytes);memset(pixelBytes,0xab,sizeof pixelBytes);
 ptr(worldBytes,moduleBytes+0xff650);wsPut32(worldBytes+0x1d8,256);wsPut32(worldBytes+0x1dc,256);wsPut32(worldBytes+0x6eec,policyCode|0x86);worldBytes[0x6ee9]=0x7c;
 ptr(worldBytes+0x200,tableBytes);ptr(worldBytes+0x6640,islandBytes);ptr(islandBytes,moduleBytes+0xf33e8);ptr(islandBytes+0x38,worldBytes);
 memset(tableBytes,0,sizeof tableBytes);memset(drawRendererBytes,0,sizeof drawRendererBytes);ptr(drawRendererBytes,moduleBytes+0xf63740);ptr(moduleBytes+0xf63740+0x108,moduleBytes+0x43390);ptr(moduleBytes+0xf63740+0x138,moduleBytes+0x487b0);ptr(moduleBytes+0xf63740+0x170,moduleBytes+0x48a20);wsPut32(drawRendererBytes+0x460,256);wsPut32(drawRendererBytes+0x464,256);ptr(drawRendererBytes+0x4c0,renderBlocks);
 memset(humanBytes,0,sizeof humanBytes);memset(humanShip,0,sizeof humanShip);memset(shipNode,0,sizeof shipNode);memset(players,0,sizeof players);
 memset(enemyBytes,0,sizeof enemyBytes);ptr(enemyBytes,moduleBytes+0xfabe0);wsPut32(enemyBytes+8,1);ptr(enemyBytes+0x10,worldBytes);
 ptr(worldBytes+0x210,players);ptr(players,moduleBytes+0xfdbc0);ptr(players+8,humanBytes);ptr(humanBytes,moduleBytes+0xfabe0);ptr(humanBytes+0x10,worldBytes);
 ptr(humanBytes+0x2e8,shipNode);ptr(humanBytes+0x2f0,shipNode);ptr(shipNode+0x10,humanShip);ptr(humanShip,moduleBytes+0xee000);ptr(humanShip+0x270,humanBytes);ptr(humanShip+0x20,worldBytes);float observer=128.0f;memcpy(humanShip+0x28,&observer,4);memcpy(humanShip+0x30,&observer,4);
 for(size_t i=0;i<sizeof wsVisibilityActorLayouts/sizeof wsVisibilityActorLayouts[0];i++){
  const WSVisibilityActorLayout*a=&wsVisibilityActorLayouts[i];ptr(moduleBytes+a->vtable+0x38,moduleBytes+a->worldGetter);ptr(moduleBytes+a->vtable+0x40,moduleBytes+a->ownerGetter);ptr(moduleBytes+a->vtable+0xb0,moduleBytes+a->xGetter);ptr(moduleBytes+a->vtable+0xc0,moduleBytes+a->zGetter);
 }
 ptr(moduleBytes+0xee000+0x120,moduleBytes+0x1a170);
 memcpy(moduleBytes,"MZ",2);wsPut32(moduleBytes+0x3c,0x80);memcpy(moduleBytes+0x80,"PE\0\0",4);wsPut16(moduleBytes+0x84,0x8664);wsPut16(moduleBytes+0x98,0x20b);wsPut32(moduleBytes+0xd0,sizeof moduleBytes);
 wsPut16(islandBytes+8,16);wsPut16(islandBytes+10,16);wsPut16(islandBytes+12,16);wsPut16(islandBytes+14,16);wsPut16(islandBytes+0x12e,discovery);
 wsPut32(listBytes,1);wsPut16(listBytes+8,16);wsPut16(listBytes+10,16);memset(listBytes+8+0x38,255,4);listBytes[8+0x38]=0;listBytes[8+0x4d]=1;listBytes[8+0x50]=0xa5;ptr(listBytes+8+8,quadBytes);ptr(quadBytes,tableBytes);
 ptr(mapBytes,moduleBytes+0xff5e0);wsPut32(mapBytes+8,64);wsPut32(mapBytes+12,64);ptr(mapBytes+0x18,worldBytes);ptr(mapBytes+0x20,pixelBytes);
 float pos=20.0f;ptr(actorBytes,moduleBytes+0xf0ed0);ptr(actorBytes+0x28,worldBytes);memcpy(actorBytes+0x40,&pos,4);memcpy(actorBytes+0x48,&pos,4);
 InterlockedExchange(&wsVisibilityLastError,0);
 spyCalls=spyFailure=spyMasked=spyMapFlags=spyAnimalCalls=spyAnimalMode=islandReads=spyRefreshCalls=spyRefreshReenter=spyMapReplace=spyResidentCalls=spyNativeRva=spyExcludeReturn=spyOccurrenceFlags=spyStaticCalls=spyMapPartial=spyMapHeightPixels=spyMapRectOriginal=spyMapReset=0;spyStaticPosition=0;memset(spyMapRect,0,sizeof spyMapRect);
 spyMapOwnerColor=10;
 spyViewportCalls=spyViewportReset=spyDrawObservedViewport=0;memset(spyViewport,0,sizeof spyViewport);
 visibilityReadChecks=stackQueryFault=0;
}
/* These are fresh-construction boundary checks, separate from render fixtures.
 * The native contact instructions themselves are audited in a private exact
 * binary fixture; the OR below represents their already-proven write effect. */
static int fresh_begin(int32_t map,int32_t enemy){uint32_t out[3];return scene(map,enemy,0x86,0,out);}
static void fresh_second(unsigned char*other){
 memcpy(other,islandBytes,sizeof islandBytes);wsPut16(other+8,64);wsPut16(other+10,64);
 wsPut16(other+0x12e,0xa503);wsPut16(other+0x130,0x5aa5);ptr(worldBytes+0x6648,other);
}
__declspec(dllexport) int fresh_case(uint32_t which){
 char error[128];unsigned char other[sizeof islandBytes];
 if(which==0){
  for(int enemy=0;enemy<2;enemy++){
   prepare(wsVisibilityEncode(0,enemy),0x41);fresh_second(other);wsPut16(islandBytes+0x130,0xa55a);
   if(!fresh_begin(0,enemy))return 1;LONG generation=wsVisibilityMapGeneration;
   if(!WorldSettingsValidateChosenVisibility(worldBytes,error,sizeof error)||wsFreshVisibilityCode)return 2;
   if(wsU16(islandBytes+0x12e)!=0x40||wsU16(other+0x12e)!=0xa502||
      wsU16(islandBytes+0x130)!=0xa55a||wsU16(other+0x130)!=0x5aa5||wsVisibilityMapGeneration==generation)return 3;
   wsPut16(islandBytes+0x12e,0x41); /* A legitimate later contact is remembered. */
   if(!WorldSettingsValidateChosenVisibility(worldBytes,error,sizeof error)||
      !WorldSettingsVisibilityWorldLoaded(worldBytes,error,sizeof error)||wsU16(islandBytes+0x12e)!=0x41)return 4;
  }return 0;
 }
 if(which==1||which==2){
  for(int enemy=0;enemy<2;enemy++){
   prepare(wsVisibilityEncode((int32_t)which,enemy),0x40);fresh_second(other);
   if(!fresh_begin((int32_t)which,enemy)||!WorldSettingsValidateChosenVisibility(worldBytes,error,sizeof error)||wsFreshVisibilityCode)return 1;
   if(wsU16(islandBytes+0x12e)!=(which==2?0x41:0x40)||wsU16(other+0x12e)!=0xa503||wsU16(other+0x130)!=0x5aa5)return 2;
  }return 0;
 }
 if(which==3){
  prepare(wsVisibilityEncode(0,0),0x41);fresh_second(other);ptr(other+0x38,0);
  if(!fresh_begin(0,0)||WorldSettingsValidateChosenVisibility(worldBytes,error,sizeof error)||
     wsU16(islandBytes+0x12e)!=0x41||wsU16(other+0x12e)!=0xa503||!wsFreshVisibilityCode)return 1;
  ptr(other+0x38,worldBytes);
  if(!WorldSettingsValidateChosenVisibility(worldBytes,error,sizeof error)||wsFreshVisibilityCode||
     wsU16(islandBytes+0x12e)!=0x40||wsU16(other+0x12e)!=0xa502)return 2;
  return 0;
 }
 if(which==4){
  prepare(wsVisibilityEncode(0,0),0x41);
  unsigned char*locked=(unsigned char*)VirtualAlloc(0,4096,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);if(!locked)return 1;
  fresh_second(locked);DWORD prior=0;int result=0;
  if(!fresh_begin(0,0)||!VirtualProtect(locked,4096,PAGE_READONLY,&prior))result=2;
  else if(WorldSettingsValidateChosenVisibility(worldBytes,error,sizeof error)||wsU16(islandBytes+0x12e)!=0x41||
          wsU16(locked+0x12e)!=0xa503||!wsFreshVisibilityCode)result=3;
  DWORD ignored=0;if(!VirtualProtect(locked,4096,PAGE_READWRITE,&ignored))result=4;
  if(!result&&(!WorldSettingsValidateChosenVisibility(worldBytes,error,sizeof error)||wsFreshVisibilityCode||
              wsU16(islandBytes+0x12e)!=0x40||wsU16(locked+0x12e)!=0xa502))result=5;
  VirtualFree(locked,0,MEM_RELEASE);return result;
 }
 if(which==5){
  prepare(wsVisibilityEncode(0,0),0x41);if(!fresh_begin(0,0))return 1;
  wsPut32(worldBytes+0x6eec,wsVisibilityEncode(1,0)|0x86);
  if(WorldSettingsValidateChosenVisibility(worldBytes,error,sizeof error)||wsU16(islandBytes+0x12e)!=0x41||!wsFreshVisibilityCode)return 2;
  wsPut32(worldBytes+0x6eec,wsVisibilityEncode(0,0)|0x86);
  if(!WorldSettingsValidateChosenVisibility(worldBytes,error,sizeof error)||wsU16(islandBytes+0x12e)!=0x40)return 3;
  return 0;
 }
 if(which==6){
  prepare(wsVisibilityEncode(0,0),0x41);if(!fresh_begin(0,0))return 1;
  /* Reload and ordinary drawing call WorldLoaded, not the fresh certificate. */
  if(!WorldSettingsVisibilityWorldLoaded(worldBytes,error,sizeof error)||wsU16(islandBytes+0x12e)!=0x41||!wsFreshVisibilityCode)return 2;
  uint32_t out[3];if(scene(0,0,0,1,out)||wsFreshVisibilityCode||wsExpectedVisibilityCode)return 3;
  if(!WorldSettingsVisibilityWorldLoaded(worldBytes,error,sizeof error)||wsU16(islandBytes+0x12e)!=0x41)return 4;
  return 0;
 }
 if(which==7){
  prepare(wsVisibilityEncode(0,0),0x41);ptr(worldBytes+0x6640,0);
  if(!fresh_begin(0,0)||WorldSettingsValidateChosenVisibility(worldBytes,error,sizeof error)||!wsFreshVisibilityCode)return 1;
  ptr(worldBytes+0x6640,islandBytes);
  if(!WorldSettingsValidateChosenVisibility(worldBytes,error,sizeof error)||wsU16(islandBytes+0x12e)!=0x40||wsFreshVisibilityCode)return 2;
  return 0;
 }
 return 99;
}
__declspec(dllexport) int scoped_reads_case(uint32_t which){
 prepare(wsVisibilityEncode(1,0),1);ptr(islandBytes+0x10,physicalTiles);
 WSVisibilityWorld view;WSVisibilityDrawContext context;
 if(!wsVisibilityWorldRead(worldBytes,&view)||!wsVisibilityContextRead(&view,&context)||!wsVisibilityFastPrepare(&context,drawRendererBytes))return 90;
 wsVisibilityDrawContext=&context;int result=0;
 if(which==0){
  for(size_t i=0;i<sizeof wsVisibilityActorLayouts/sizeof wsVisibilityActorLayouts[0];i++){
   const WSVisibilityActorLayout*a=&wsVisibilityActorLayouts[i];
   for(uint32_t owner=0;owner<3;owner++)for(uint32_t position=0;position<3;position++){
    memset(actorBytes,0,sizeof actorBytes);ptr(actorBytes,moduleBytes+a->vtable);ptr(actorBytes+a->worldOffset,worldBytes);
    if(a->ownerOffset)ptr(actorBytes+a->ownerOffset,owner==1?humanBytes:(owner==2?enemyBytes:0));
    float coordinate=position==0?128.0f:(position==1?20.0f:255.0f);memcpy(actorBytes+a->xOffset,&coordinate,4);memcpy(actorBytes+a->zOffset,&coordinate,4);
    const WSVisibilityActorLayout*actual=0;int visible=-1;
    if(!wsVisibilityFastActorDecision(actorBytes,moduleBytes,&actual,&visible)||actual!=a||visible!=wsVisibilityActorInContext(&context,actorBytes,a)){result=1;goto done;}
   }
  }
 }else if(which==1){
  ptr(actorBytes,moduleBytes+0xfd7b0);ptr(actorBytes+0x28,worldBytes);float at=128.0f;memcpy(actorBytes+0x40,&at,4);memcpy(actorBytes+0x48,&at,4);
  const WSVisibilityActorLayout*a=0;int visible=0;uint32_t offsets[4]={0x38,0x40,0xb0,0xc0};
  for(uint32_t n=0;n<4;n++){
   void*prior=wsCertPointer(moduleBytes+0xfd7b0,offsets[n]);ptr(moduleBytes+0xfd7b0+offsets[n],0);
   if(!wsVisibilityFastActorDecision(actorBytes,moduleBytes,&a,&visible)||visible||wsVisibilityLastError!=9){result=2;goto done;}
   ptr(moduleBytes+0xfd7b0+offsets[n],prior);
   if(!wsVisibilityFastActorDecision(actorBytes,moduleBytes,&a,&visible)||!visible){result=3;goto done;}
  }
  ptr(actorBytes,moduleBytes+0x1100000);if(WorldSettingsVisibilityDispatchResident100(actorBytes,71,tableBytes)||spyResidentCalls){result=4;goto done;}
 }else if(which==2){
  ptr(actorBytes,moduleBytes+0xee000);ptr(actorBytes+0x20,worldBytes);ptr(actorBytes+0x270,enemyBytes);float at=128.0f;memcpy(actorBytes+0x28,&at,4);memcpy(actorBytes+0x30,&at,4);
  const WSVisibilityActorLayout*a=0;int visible=0;
  if(!wsVisibilityFastActorDecision(actorBytes,moduleBytes,&a,&visible)||!visible){result=1;goto done;}
  at=20.0f;memcpy(actorBytes+0x28,&at,4);memcpy(actorBytes+0x30,&at,4);
  if(!wsVisibilityFastActorDecision(actorBytes,moduleBytes,&a,&visible)||visible){result=2;goto done;}
  ptr(actorBytes+0x270,humanBytes);if(!wsVisibilityFastActorDecision(actorBytes,moduleBytes,&a,&visible)||!visible){result=3;goto done;}
  ptr(humanBytes+0x10,0);if(!wsVisibilityFastActorDecision(actorBytes,moduleBytes,&a,&visible)||visible){result=4;goto done;}ptr(humanBytes+0x10,worldBytes);
  ptr(actorBytes+0x20,0);if(!wsVisibilityFastActorDecision(actorBytes,moduleBytes,&a,&visible)||visible||wsVisibilityActorDecision(actorBytes,a,moduleBytes)){result=5;goto done;}ptr(actorBytes+0x20,worldBytes);
  uint32_t invalid[4]={0x7fc00000u,0x7f800000u,0xbf800000u,0x43800000u};
  for(uint32_t n=0;n<4;n++){wsPut32(actorBytes+0x28,invalid[n]);if(!wsVisibilityFastActorDecision(actorBytes,moduleBytes,&a,&visible)||visible){result=6;goto done;}}
 }else if(which==3){
  unsigned char*memory=(unsigned char*)VirtualAlloc(0,8192,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);if(!memory){result=1;goto done;}
  unsigned char*small=memory+4096-0x40;ptr(small,moduleBytes+0xead10);ptr(small+0x30,worldBytes);float at=128.0f;memcpy(small+0x14,&at,4);memcpy(small+0x1c,&at,4);DWORD old;
  if(!VirtualProtect(memory+4096,4096,PAGE_NOACCESS,&old)){VirtualFree(memory,0,MEM_RELEASE);result=2;goto done;}
  const WSVisibilityActorLayout*a=0;int visible=0;
  if(wsVisibilityFastActorDecision(small,moduleBytes,&a,&visible)||!(a=wsVisibilityActorLayout(small,moduleBytes))||!wsVisibilityActorDecision(small,a,moduleBytes))result=3;
  VirtualFree(memory,0,MEM_RELEASE);
 }else if(which==4){
  float point[3]={128.0f,0,128.0f};uintptr_t savedEnd=context.fast->stackEnd;
  if(!context.fast->stackBegin||(uintptr_t)point<context.fast->stackBegin||(uintptr_t)point+sizeof point>savedEnd){result=1;goto done;}
  visibilityReadChecks=0;if(!wsVisibilitySpritePoint(&context,point)||visibilityReadChecks){result=2;goto done;}
  wsPut32((unsigned char*)point,0x7fc00000u);if(wsVisibilitySpritePoint(&context,point)||visibilityReadChecks){result=3;goto done;}point[0]=128.0f;
  context.fast->stackEnd=(uintptr_t)point+8u;visibilityReadChecks=0;if(!wsVisibilitySpritePoint(&context,point)||visibilityReadChecks!=1){result=4;goto done;}context.fast->stackEnd=savedEnd;
  float*heap=(float*)VirtualAlloc(0,4096,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);if(!heap){result=5;goto done;}memcpy(heap,point,sizeof point);
  visibilityReadChecks=0;if(!wsVisibilitySpritePoint(&context,heap)||visibilityReadChecks!=1){VirtualFree(heap,0,MEM_RELEASE);result=6;goto done;}
  heap[0]=256.0f;if(wsVisibilitySpritePoint(&context,heap)){VirtualFree(heap,0,MEM_RELEASE);result=7;goto done;}
  DWORD old;VirtualProtect(heap,4096,PAGE_NOACCESS,&old);if(wsVisibilitySpritePoint(&context,heap)){VirtualFree(heap,0,MEM_RELEASE);result=8;goto done;}VirtualFree(heap,0,MEM_RELEASE);
 }else if(which==5){
  wsVisibilityFastRelease(&context);
  for(uint32_t fault=1;fault<=7;fault++){
   stackQueryFault=fault;if(!wsVisibilityFastPrepare(&context,drawRendererBytes)||context.fast->stackBegin||context.fast->stackEnd){result=1;goto done;}
   float point[3]={128.0f,0,128.0f};visibilityReadChecks=0;if(!wsVisibilitySpritePoint(&context,point)||visibilityReadChecks!=1){result=2;goto done;}
   wsVisibilityFastRelease(&context);
  }
  stackQueryFault=0;if(!wsVisibilityFastPrepare(&context,drawRendererBytes)||!context.fast->stackBegin){result=3;goto done;}
 }else if(which==6){
  ptr(actorBytes,moduleBytes+0xf0ed0);ptr(actorBytes+0x28,worldBytes);ptr(actorBytes+0x30,0);float at=128.0f;memcpy(actorBytes+0x40,&at,4);memcpy(actorBytes+0x48,&at,4);
  visibilityReadChecks=0;if(WorldSettingsVisibilityDispatchResident100(actorBytes,71,tableBytes)!=0x3344||visibilityReadChecks!=1||spyResidentCalls!=1||spyFailure){result=1;goto done;}
  wsVisibilityFastRelease(&context);if(context.fast){result=2;goto done;}
  visibilityReadChecks=0;if(WorldSettingsVisibilityDispatchResident108(actorBytes,71,tableBytes)!=0x3344||visibilityReadChecks<=1||spyResidentCalls!=2||spyFailure){result=3;goto done;}
 }else result=99;
 done:wsVisibilityFastRelease(&context);wsVisibilityDrawContext=0;stackQueryFault=0;return result;
}
__declspec(dllexport) int memory_case(uint32_t which){
 char error[128];unsigned char worldBefore[sizeof worldBytes],islandBefore[sizeof islandBytes],listBefore[sizeof listBytes];
 if(which==0){
  prepare(wsVisibilityEncode(0,0),0);memcpy(worldBefore,worldBytes,sizeof worldBytes);memcpy(islandBefore,islandBytes,sizeof islandBytes);memcpy(listBefore,listBytes,sizeof listBytes);
  wsVisibilityMaskList(worldBytes,listBytes);
  if(wsVisibilityBackupCount!=1||listBytes[8+0x4d]||listBytes[8+0x50]!=0xa4)return 1;
  listBefore[8+0x4d]=0;listBefore[8+0x50]=0xa4;
  if(memcmp(worldBefore,worldBytes,sizeof worldBytes)||memcmp(islandBefore,islandBytes,sizeof islandBytes)||memcmp(listBefore,listBytes,sizeof listBytes)||wsCertPointer(quadBytes,0)!=tableBytes)return 2;
  wsPut16(islandBytes+0x12e,1);if(!wsVisibilityRestore())return 3;
  for(size_t i=8;i<sizeof quadBytes;i++)if(quadBytes[i]!=0xa5)return 4;
  wsVisibilityMaskList(worldBytes,listBytes);return wsVisibilityBackupCount?5:0;
 }
 if(which==1){
  prepare(0,0);memcpy(worldBefore,worldBytes,sizeof worldBytes);memcpy(islandBefore,islandBytes,sizeof islandBytes);memcpy(listBefore,listBytes,sizeof listBytes);
  if(!WorldSettingsVisibilityWorldLoaded(worldBytes,error,sizeof error))return 1;
  wsVisibilityMaskList(worldBytes,listBytes);fixtureMaskMap(mapBytes);
  if(memcmp(worldBefore,worldBytes,sizeof worldBytes)||memcmp(islandBefore,islandBytes,sizeof islandBytes)||memcmp(listBefore,listBytes,sizeof listBytes))return 2;
  for(size_t i=8;i<sizeof quadBytes;i++)if(quadBytes[i]!=0xa5)return 3;
  for(size_t i=0;i<sizeof pixelBytes;i++)if(pixelBytes[i]!=0xab)return 4;
  return 0;
 }
 if(which==2){
  for(int enemy=0;enemy<2;enemy++){
   prepare(wsVisibilityEncode(2,enemy),0x40);if(!WorldSettingsVisibilityWorldLoaded(worldBytes,error,sizeof error))return 1;
   if(worldBytes[0x6ee9]!=1||wsU16(islandBytes+0x12e)!=0x41||wsU32(worldBytes+0x6eec)!=(wsVisibilityEncode(2,enemy)|0x86))return 2;
   wsVisibilityMaskList(worldBytes,listBytes);if(wsVisibilityBackupCount)return 3;
  }return 0;
 }
 if(which==3){
  prepare(wsVisibilityEncode(0,1),0);fixtureMaskMap(mapBytes);
  for(uint32_t y=0;y<64;y++)for(uint32_t x=0;x<64;x++)if(pixelBytes[y*64+x]!=(unsigned char)(x>=4&&x<8&&y>=4&&y<8?0xa0:0xab))return 1;
  wsPut16(islandBytes+0x12e,1);memset(pixelBytes,0xab,sizeof pixelBytes);fixtureMaskMap(mapBytes);
  for(size_t i=0;i<sizeof pixelBytes;i++)if(pixelBytes[i]!=0xab)return 2;return 0;
 }
 if(which==4){
  prepare(wsVisibilityEncode(0,0),0);wsVisibilityMaskList(worldBytes,listBytes);if(wsVisibilityBackupCount!=1)return 1;
  wsPut16(listBytes+8,32);if(wsVisibilityRestore())return 2;
  for(size_t i=8;i<sizeof quadBytes;i++)if(quadBytes[i]!=0xa5)return 3;
  return wsVisibilityLastError==1?0:4;
 }
 if(which==5){
  prepare(wsVisibilityEncode(2,1),0x40);ptr(islandBytes,moduleBytes+0x123);memcpy(worldBefore,worldBytes,sizeof worldBytes);memcpy(islandBefore,islandBytes,sizeof islandBytes);
  if(WorldSettingsVisibilityWorldLoaded(worldBytes,error,sizeof error))return 1;
  if(memcmp(worldBefore,worldBytes,sizeof worldBytes)||memcmp(islandBefore,islandBytes,sizeof islandBytes))return 2;
  return 0;
 }
 if(which==6){
  prepare(wsVisibilityEncode(0,0),0);wsPut32(listBytes,8193);wsVisibilityMaskList(worldBytes,listBytes);
  for(size_t i=8;i<sizeof quadBytes;i++)if(quadBytes[i]!=0xa5)return 1;
  return wsVisibilityLastError==3?0:2;
 }
 if(which==7){
  prepare(wsVisibilityEncode(0,0),0);memcpy(listBefore,listBytes,sizeof listBytes);spyMasked=1;
  if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes)!=0x1234||spyFailure||spyCalls!=1)return 1;
  if(wsVisibilityBackupCount||wsVisibilityRenderBusy||memcmp(listBefore,listBytes,sizeof listBytes))return 2;
  wsPut16(islandBytes+0x12e,1);spyMasked=0;
  if(WorldSettingsVisibilityDrawTerrainClipped(worldBytes,listBytes,17,(int32_t*)tableBytes,29,drawRendererBytes)!=0x1235||spyFailure||spyCalls!=2)return 3;
  if(wsVisibilityBackupCount||wsVisibilityRenderBusy||memcmp(listBefore,listBytes,sizeof listBytes))return 4;
  return 0;
 }
 if(which==8){
  prepare(wsVisibilityEncode(0,0),0);wsPut32(listBytes,8193);
  if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes)||spyCalls||wsVisibilityRenderBusy)return 1;
  if(wsVisibilityLastError!=3)return 2;
  prepare(wsVisibilityEncode(0,0),0);InterlockedExchange(&wsVisibilityRenderBusy,1);
  if(WorldSettingsVisibilityDrawTerrainClipped(worldBytes,listBytes,17,(int32_t*)tableBytes,29,drawRendererBytes)||spyCalls)return 3;
  InterlockedExchange(&wsVisibilityRenderBusy,0);return wsVisibilityLastError==6?0:4;
 }
 if(which==9){
  prepare(0,0);memcpy(worldBefore,worldBytes,sizeof worldBytes);memcpy(listBefore,listBytes,sizeof listBytes);
  if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes)!=0x1234||spyFailure||spyCalls!=1)return 1;
  if(memcmp(worldBefore,worldBytes,sizeof worldBytes)||memcmp(listBefore,listBytes,sizeof listBytes))return 2;
  if(WorldSettingsVisibilityCreateMap(mapBytes,1,tableBytes)!=0x1236||spyMapFlags!=1||spyFailure)return 3;
  return 0;
 }
 if(which==10){
  prepare(wsVisibilityEncode(0,1),0);
  if(WorldSettingsVisibilityCreateMap(mapBytes,1,tableBytes)!=0x1236||spyFailure||spyMapFlags!=1)return 1;
  if(pixelBytes[4*64+4]!=0xa0||pixelBytes[0]!=0xab||worldBytes[0x6ee9]!=1)return 2;
  uint32_t diagnostics[7]={0};if(WorldSettingsCopyVisibilityDiagnostics(diagnostics)!=28||diagnostics[0]!=1||diagnostics[1]!=0x7000||diagnostics[6])return 3;
  return WorldSettingsCopyVisibilityDiagnostics(0)?4:0;
 }
 if(which==11){
  prepare(wsVisibilityEncode(0,0),0);unsigned char actorBefore[sizeof actorBytes];memcpy(actorBefore,actorBytes,sizeof actorBytes);
  if(WorldSettingsVisibilityDrawWildlife(actorBytes,71,tableBytes)||WorldSettingsVisibilityDrawWildlifeClipped(actorBytes,71,tableBytes)||spyAnimalCalls)return 1;
  if(memcmp(actorBefore,actorBytes,sizeof actorBytes))return 2;
  wsPut16(islandBytes+0x12e,1);
  const uint32_t classes[3]={0xf0ed0,0xf13d0,0xf1738};
  for(uint32_t i=0;i<3;i++){
   ptr(actorBytes,moduleBytes+classes[i]);
   if(WorldSettingsVisibilityDrawWildlife(actorBytes,71,tableBytes)!=(i?0x2232u:0x2231u)||WorldSettingsVisibilityDrawWildlifeClipped(actorBytes,71,tableBytes)!=0x2233u||spyFailure)return 3;
  }
  return spyAnimalCalls==6?0:4;
 }
 if(which==12){
  prepare(wsVisibilityEncode(0,0),0);spyAnimalMode=spyMasked=1;
  if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes)!=0x1234||spyFailure||spyAnimalCalls)return 1;
  if(wsVisibilityDrawContext||wsVisibilityBackupCount||wsVisibilityRenderBusy)return 2;
  return 0;
 }
 if(which==13){
  for(uint32_t mode=0;mode<3;mode++){
   prepare(mode?wsVisibilityEncode((int32_t)mode,0):0,0);
   if(WorldSettingsVisibilityDrawWildlife(actorBytes,71,tableBytes)!=0x2231||WorldSettingsVisibilityDrawWildlifeClipped(actorBytes,71,tableBytes)!=0x2233||spyFailure||spyAnimalCalls!=2)return 1;
  }
  prepare(wsVisibilityEncode(0,0),0);wsPut32(actorBytes+0x40,0x7fc00000u);
  if(WorldSettingsVisibilityDrawWildlife(actorBytes,71,tableBytes)||spyAnimalCalls||wsVisibilityLastError!=7)return 2;
  prepare(wsVisibilityEncode(0,0),0);float at=200.0f;memcpy(actorBytes+0x40,&at,4);
  if(WorldSettingsVisibilityDrawWildlifeClipped(actorBytes,71,tableBytes)||spyAnimalCalls||wsVisibilityLastError!=7)return 3;
  return 0;
 }
 if(which==14){
  for(int enemy=0;enemy<2;enemy++){
   prepare(wsVisibilityEncode(1,enemy),0);spyRefreshReenter=1;
   if(!WorldSettingsVisibilityWorldLoaded(worldBytes,error,sizeof error)||spyFailure||spyRefreshCalls!=1||spyRefreshReenter)return 1;
   if(!WorldSettingsVisibilityWorldLoaded(worldBytes,error,sizeof error)||spyRefreshCalls!=1||worldBytes[0x6ee9]!=1)return 2;
  }
  prepare(0,0);if(!WorldSettingsVisibilityWorldLoaded(worldBytes,error,sizeof error)||spyRefreshCalls||worldBytes[0x6ee9]!=0x7c)return 3;
  return 0;
 }
 if(which==15){
  prepare(wsVisibilityEncode(0,0),0);ptr(islandBytes,moduleBytes+0x123);
  if(WorldSettingsVisibilityCreateMap(mapBytes,1,tableBytes)||spyCalls||wsVisibilityLastError!=4)return 1;
  for(size_t i=0;i<sizeof pixelBytes;i++)if(pixelBytes[i]!=0x90)return 2;
  prepare(wsVisibilityEncode(0,0),0);wsPut32(mapBytes+8,2049);
  if(WorldSettingsVisibilityCreateMap(mapBytes,1,tableBytes)||spyCalls||wsVisibilityLastError!=4)return 3;
  for(size_t i=0;i<sizeof pixelBytes;i++)if(pixelBytes[i]!=0xab)return 4;
  prepare(wsVisibilityEncode(0,0),0);spyMapReplace=1;
  if(WorldSettingsVisibilityCreateMap(mapBytes,1,tableBytes)||spyCalls!=1||wsVisibilityLastError!=4)return 5;
  for(size_t i=0;i<sizeof pixelBytes;i++)if(pixelBytes[i]!=0xab||replacementPixels[i]!=0x90)return 6;
  return 0;
 }
 if(which==16){
  prepare(0x7000,0);
  if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes)||spyCalls)return 1;
  if(WorldSettingsVisibilityCreateMap(mapBytes,1,tableBytes)||spyCalls)return 2;
  if(WorldSettingsVisibilityDrawWildlife(actorBytes,71,tableBytes)||spyAnimalCalls)return 3;
  if(WorldSettingsVisibilityWorldLoaded(worldBytes,error,sizeof error)||worldBytes[0x6ee9]!=0x7c)return 4;
  prepare(wsVisibilityEncode(0,0),0);wsPut32(worldBytes+0x1d8,4096);
  if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes)||WorldSettingsVisibilityCreateMap(mapBytes,1,tableBytes)||spyCalls)return 5;
  if(WorldSettingsVisibilityDrawWildlife(actorBytes,71,tableBytes)||spyAnimalCalls)return 6;
  return 0;
 }
 if(which==17){
  prepare(wsVisibilityEncode(1,0),0);ptr(actorBytes,moduleBytes+0xee000);ptr(actorBytes+0x20,worldBytes);ptr(actorBytes+0x270,enemyBytes);
  float x=200.0f,z=200.0f;memcpy(actorBytes+0x28,&x,4);memcpy(actorBytes+0x30,&z,4);
  if(WorldSettingsVisibilityDispatchResident100(actorBytes,71,tableBytes)||spyResidentCalls)return 1;
  if(!WorldSettingsVisibilityMinimapExclude(actorBytes,4)||spyNativeRva!=0x1a170||spyFailure)return 2;
  x=160.0f;z=128.0f;memcpy(actorBytes+0x28,&x,4);memcpy(actorBytes+0x30,&z,4);
  if(WorldSettingsVisibilityDispatchResident100(actorBytes,71,tableBytes)!=0x3344||spyResidentCalls!=1||spyFailure)return 3;
  if(WorldSettingsVisibilityMinimapExclude(actorBytes,4))return 4;
  spyExcludeReturn=7;if(WorldSettingsVisibilityMinimapExclude(actorBytes,4)!=7)return 5;
  x=200.0f;z=200.0f;memcpy(actorBytes+0x28,&x,4);memcpy(actorBytes+0x30,&z,4);ptr(actorBytes+0x270,humanBytes);
  if(WorldSettingsVisibilityDispatchResident108(actorBytes,71,tableBytes)!=0x3344||spyResidentCalls!=2||spyFailure)return 6;
  return 0;
 }
 if(which==18){
  prepare(wsVisibilityEncode(1,1),0);ptr(actorBytes,moduleBytes+0xee000);ptr(actorBytes+0x20,worldBytes);ptr(actorBytes+0x270,enemyBytes);float x=240.0f,z=240.0f;memcpy(actorBytes+0x28,&x,4);memcpy(actorBytes+0x30,&z,4);
  if(WorldSettingsVisibilityDispatchResident100(actorBytes,71,tableBytes)!=0x3344||spyFailure)return 1;
  if(WorldSettingsVisibilityMinimapExclude(actorBytes,4))return 2;
  prepare(wsVisibilityEncode(1,0),0);if(WorldSettingsVisibilityCreateMap(mapBytes,1,tableBytes)!=0x1236||spyMapFlags!=3)return 3;
  if(pixelBytes[0]!=0x9b||pixelBytes[32*64+32]!=0xab)return 4;
  return 0;
 }
 if(which==19){
  prepare(wsVisibilityEncode(0,0),0);ptr(actorBytes,moduleBytes+0xf58e8);ptr(actorBytes+0x10,worldBytes);float x=20.0f,z=20.0f;memcpy(actorBytes+0x20,&x,4);memcpy(actorBytes+0x28,&z,4);
  if(WorldSettingsVisibilityDispatchOccurrence100(actorBytes,71,tableBytes,0x12345678)||spyResidentCalls)return 1;
  wsPut16(islandBytes+0x12e,1);
  if(WorldSettingsVisibilityDispatchOccurrence100(actorBytes,71,tableBytes,0x12345678)!=0x3345||spyOccurrenceFlags!=0x12345678||spyFailure)return 2;
  prepare(0,0);ptr(actorBytes,moduleBytes+0xee000);ptr(actorBytes+0x20,worldBytes);ptr(actorBytes+0x270,enemyBytes);x=z=200.0f;memcpy(actorBytes+0x28,&x,4);memcpy(actorBytes+0x30,&z,4);
  if(WorldSettingsVisibilityDispatchResident100(actorBytes,71,tableBytes)!=0x3344||spyFailure)return 3;
  return 0;
 }
 if(which==20){
  prepare(wsVisibilityEncode(1,0),1);memset(cityBytes,0,sizeof cityBytes);memset(cityNode,0,sizeof cityNode);memset(buildingBytes,0,sizeof buildingBytes);
  ptr(cityBytes,moduleBytes+0xfc678);ptr(cityBytes+0x20,islandBytes);ptr(cityBytes+0x28,humanBytes);ptr(cityBytes+0x1b0,moduleBytes+0xfc228);
  ptr(humanBytes+0x318,cityNode);ptr(humanBytes+0x320,cityNode);ptr(cityNode+0x10,cityBytes);buildingVector[0]=buildingBytes[0];buildingVector[1]=buildingBytes[1];ptr(cityBytes+0x310,buildingVector);ptr(cityBytes+0x318,buildingVector+2);
  for(int i=0;i<2;i++){ptr(buildingBytes[i],moduleBytes+0xf6938);ptr(buildingBytes[i]+0x18,cityBytes);wsPut16(buildingBytes[i]+0xa,(uint16_t)(20+i*10));wsPut16(buildingBytes[i]+0xc,(uint16_t)(20+i*8));}
  ptr(moduleBytes+0xf6938+0xf8,moduleBytes+0x832a0);ptr(moduleBytes+0xf6938+0x38,moduleBytes+0x84fe0);
  WSVisibilityWorld view;WSVisibilityDrawContext context;if(!wsVisibilityWorldRead(worldBytes,&view)||!wsVisibilityContextRead(&view,&context))return 1;
  if(context.visionCount!=2||!wsVisibilityInSight(&context,78.0f,28.0f)||wsVisibilityInSight(&context,79.0f,28.0f))return 2;
  wsPut16(buildingBytes[1]+0xa,40);if(wsVisibilityContextRead(&view,&context))return 3;
  return 0;
 }
 if(which==21){
  prepare(wsVisibilityEncode(1,0),1);memset(cityBytes,0,sizeof cityBytes);memset(catalogueBytes,0,sizeof catalogueBytes);memset(definitionBytes,0,sizeof definitionBytes);memset(physicalTiles,0,sizeof physicalTiles);memset(rendererVtable,0,sizeof rendererVtable);
  ptr(cityBytes,moduleBytes+0xfc678);ptr(cityBytes+0x20,islandBytes);ptr(cityBytes+0x28,enemyBytes);ptr(islandBytes+0x68,cityBytes);ptr(islandBytes+0x10,physicalTiles);
  ptr(worldBytes+0x200,catalogueBytes);ptr(catalogueBytes,moduleBytes+0x20300);ptr(moduleBytes+0x20300+0xe8,moduleBytes+0xb4d0);ptr(catalogueBytes+0x218+123*8,definitionBytes);ptr(definitionBytes,moduleBytes+0xf612e0);ptr(moduleBytes+0xf612e0+0xc0,moduleBytes+0x27790);wsPut16(definitionBytes+0x38,0x41);
  wsPut32(physicalTiles+(4*16+4)*8,0x80000000u|123u);ptr(rendererBytes,rendererVtable);ptr(rendererVtable+0x180,moduleBytes+0x11100);ptr(rendererVtable+0x188,moduleBytes+0x11110);
  WSVisibilityWorld view;WSVisibilityDrawContext context;if(!wsVisibilityWorldRead(worldBytes,&view)||!wsVisibilityContextRead(&view,&context))return 1;
  float xyz[3]={20.5f,0,20.5f};spyStaticPosition=xyz;wsVisibilityDrawContext=&context;unsigned char before[8];memcpy(before,physicalTiles+(4*16+4)*8,8);
  if(WorldSettingsVisibilityDrawStatic180(rendererBytes,quadBytes,7,11,0xc0,xyz)||spyStaticCalls)return 2;
  float observerAt=40.0f;memcpy(humanShip+0x28,&observerAt,4);memcpy(humanShip+0x30,&observerAt,4);if(!wsVisibilityContextRead(&view,&context))return 3;
  if(WorldSettingsVisibilityDrawStatic188(rendererBytes,quadBytes,7,11,0xc0,xyz)!=0x4455||spyStaticCalls!=1||spyFailure)return 4;
  if(memcmp(before,physicalTiles+(4*16+4)*8,8)||wsU32(cityBytes+0x760)||wsU16(islandBytes+0x12e)!=1)return 5;
  observerAt=128.0f;memcpy(humanShip+0x28,&observerAt,4);memcpy(humanShip+0x30,&observerAt,4);if(!wsVisibilityContextRead(&view,&context))return 6;
  ptr(definitionBytes,moduleBytes+0xf60e60); /* A native tree in claimed territory is neutral decor. */
  if(WorldSettingsVisibilityDrawStatic180(rendererBytes,quadBytes,7,11,0xc0,xyz)!=0x4455||spyStaticCalls!=2||spyFailure)return 7;
  ptr(definitionBytes,moduleBytes+0xf61400);ptr(moduleBytes+0xf61400+0xc0,moduleBytes+0x27790);
  if(WorldSettingsVisibilityDrawStatic180(rendererBytes,quadBytes,7,11,0xc0,xyz)||spyStaticCalls!=2)return 10;
  wsPut16(definitionBytes+0x38,0xe2);ptr(catalogueBytes+0x218+124*8,neighbourDefinition);ptr(neighbourDefinition,moduleBytes+0x1101000);
  if(WorldSettingsVisibilityDrawStatic180(rendererBytes,quadBytes,7,11,0xc0,xyz)!=0x4455||spyStaticCalls!=3)return 11;
  ptr(neighbourDefinition,moduleBytes+0xf612e0);ptr(moduleBytes+0xf612e0+0x160,moduleBytes+0x17540);
  if(WorldSettingsVisibilityDrawStatic180(rendererBytes,quadBytes,7,11,0xc0,xyz)||spyStaticCalls!=3)return 12;
  ptr(neighbourDefinition,moduleBytes+0xf60af0);ptr(moduleBytes+0xf60af0+0x160,moduleBytes+0x62770);
  if(WorldSettingsVisibilityDrawStatic180(rendererBytes,quadBytes,7,11,0xc0,xyz)||spyStaticCalls!=3)return 13;
  wsPut16(definitionBytes+0x38,0x41);
  ptr(definitionBytes,moduleBytes+0xf612e0);ptr(actorBytes,moduleBytes+0xf5b48);ptr(actorBytes+0x10,worldBytes);memcpy(actorBytes+0x20,xyz,4);memcpy(actorBytes+0x28,xyz+2,4);
  if(WorldSettingsVisibilityDispatchOccurrence100(actorBytes,71,tableBytes,2)||spyResidentCalls)return 8;
  ptr(cityBytes+0x28,humanBytes);
  if(WorldSettingsVisibilityDispatchOccurrence100(actorBytes,71,tableBytes,2)!=0x3345||spyFailure)return 9;
  wsVisibilityDrawContext=0;return 0;
 }
 if(which==22){
  prepare(wsVisibilityEncode(0,0),0);
  if(WorldSettingsVisibilityCreateMap(mapBytes,1,tableBytes)!=0x1236||pixelBytes[4*64+4]!=0x90)return 1;
  prepare(wsVisibilityEncode(1,0),0);ptr(shipNode+8,shipNode);WSVisibilityWorld view;WSVisibilityDrawContext context;
  if(!wsVisibilityWorldRead(worldBytes,&view)||wsVisibilityContextRead(&view,&context))return 2;
  return 0;
 }
 if(which==23){
  prepare(0,0);ptr(actorBytes,moduleBytes+0x1100000);ptr(moduleBytes+0x1100000+0x100,moduleBytes+0x11100);ptr(moduleBytes+0x1100000+0x108,moduleBytes+0x11110);
  if(WorldSettingsVisibilityDispatchResident100(actorBytes,71,tableBytes)!=0x3344||spyFailure||spyResidentCalls!=1)return 1;
  if(WorldSettingsVisibilityDispatchOccurrence100(actorBytes,71,tableBytes,0x87654321)!=0x3345||spyOccurrenceFlags!=0x87654321||spyResidentCalls!=2)return 2;
  prepare(wsVisibilityEncode(1,0),1);ptr(actorBytes,moduleBytes+0x1100000);WSVisibilityWorld view;WSVisibilityDrawContext context;
  if(!wsVisibilityWorldRead(worldBytes,&view)||!wsVisibilityContextRead(&view,&context))return 3;wsVisibilityDrawContext=&context;
  if(WorldSettingsVisibilityDispatchResident108(actorBytes,71,tableBytes)||spyResidentCalls||wsVisibilityLastError!=9)return 4;
  wsVisibilityDrawContext=0;return 0;
 }
 if(which==24){
  prepare(wsVisibilityEncode(1,0),0);memset(cityBytes,0,sizeof cityBytes);memset(buildingBytes,0,sizeof buildingBytes);
  ptr(cityBytes,moduleBytes+0xfc678);ptr(cityBytes+0x28,enemyBytes);ptr(buildingBytes[0],moduleBytes+0xf6938);ptr(buildingBytes[0]+0x18,cityBytes);
  ptr(actorBytes,moduleBytes+0xf1ab0);ptr(actorBytes+0x28,worldBytes);ptr(actorBytes+0xf0,buildingBytes[0]);float x=200.0f,z=200.0f;memcpy(actorBytes+0x40,&x,4);memcpy(actorBytes+0x48,&z,4);
  if(WorldSettingsVisibilityDispatchResident100(actorBytes,71,tableBytes)||spyResidentCalls)return 1;
  ptr(cityBytes+0x28,humanBytes);
  if(WorldSettingsVisibilityDispatchResident108(actorBytes,71,tableBytes)!=0x3344||spyResidentCalls!=1||spyFailure)return 2;
  return 0;
 }
 if(which==25){
  prepare(wsVisibilityEncode(0,1),0);spyMapPartial=1;int32_t partial[4]={0,0,4,4};
  if(WorldSettingsVisibilityCreateMap(mapBytes,2,partial)!=0x1236||spyFailure||spyMapHeightPixels!=1||pixelBytes[4*64+4]!=0xa0)return 1;
  wsPut16(islandBytes+0x12e,1);spyMapHeightPixels=0;
  if(WorldSettingsVisibilityCreateMap(mapBytes,1,partial)!=0x1236||spyMapFlags!=3||spyMapHeightPixels!=64||spyMapRect[2]!=32||spyMapRect[3]!=32)return 2;
  for(uint32_t y=4;y<8;y++)for(uint32_t x=4;x<8;x++)if((pixelBytes[y*64+x]&15u)!=11u)return 3;
  spyMapHeightPixels=0;
  if(WorldSettingsVisibilityCreateMap(mapBytes,1,partial)!=0x1236||spyMapFlags!=1||spyMapHeightPixels||memcmp(spyMapRect,partial,16))return 4;
  if(WorldSettingsVisibilityCreateMap(mapBytes,0,0)!=0x1236||spyMapFlags||spyMapHeightPixels||spyMapRect[0]||spyMapRect[1]||spyMapRect[2]||spyMapRect[3])return 5;
  WorldSettingsVisibilityReset();spyMapHeightPixels=0;
  if(WorldSettingsVisibilityCreateMap(mapBytes,1,0)!=0x1236||spyMapFlags!=3||spyMapHeightPixels!=4096||spyMapRect[2]!=256||spyMapRect[3]!=256)return 6;
  return 0;
 }
 if(which==26){
  prepare(wsVisibilityEncode(1,0),1);spyMapPartial=1;int32_t partial[4]={0,0,4,4};
  if(WorldSettingsVisibilityCreateMap(mapBytes,0,partial)!=0x1236||spyMapFlags!=3||spyMapHeightPixels!=4096||pixelBytes[5*64+5]!=0x9b||pixelBytes[32*64+32]!=0xab)return 1;
  spyMapHeightPixels=0;
  float observerAt=20.0f;memcpy(humanShip+0x28,&observerAt,4);memcpy(humanShip+0x30,&observerAt,4);
  if(WorldSettingsVisibilityCreateMap(mapBytes,0,partial)!=0x1236||spyMapFlags!=1||spyMapHeightPixels||pixelBytes[5*64+5]!=0xab||pixelBytes[32*64+32]!=0x9b)return 2;
  return 0;
 }
 if(which==27){
  prepare(wsVisibilityEncode(0,1),1);spyMapPartial=1;int32_t partial[4]={0,0,4,4};
  if(WorldSettingsVisibilityCreateMap(mapBytes,1,partial)!=0x1236)return 1;
  WSVisibilityMapMemo memoBefore=wsVisibilityMapMemo;spyMapReplace=1;
  if(WorldSettingsVisibilityCreateMap(mapBytes,1,partial)||memcmp(&memoBefore,&wsVisibilityMapMemo,sizeof memoBefore)||wsVisibilityMapRefreshBusy)return 2;
  prepare(wsVisibilityEncode(0,1),0);uint32_t beforeCalls=spyCalls;InterlockedExchange(&wsVisibilityMapRefreshBusy,1);
  if(WorldSettingsVisibilityCreateMap(mapBytes,1,partial)||spyCalls!=beforeCalls||wsVisibilityLastError!=10)return 3;
  InterlockedExchange(&wsVisibilityMapRefreshBusy,0);return 0;
 }
 if(which==28){
  prepare(0,0);ptr(rendererBytes,rendererVtable);ptr(rendererVtable+0x180,(void*)spyStatic);ptr(rendererVtable+0x188,(void*)spyStatic);float xyz[3]={1,0,1};spyStaticPosition=xyz;
  if(WorldSettingsVisibilityDrawStatic180(rendererBytes,quadBytes,7,11,0xc0,xyz)!=0x4455||WorldSettingsVisibilityDrawStatic188(rendererBytes,quadBytes,7,11,0xc0,xyz)!=0x4455||spyFailure)return 1;
  uint64_t targets[2]={0};if(WorldSettingsCopyVisibilityRenderTargets(targets)!=16||targets[0]!=(uintptr_t)spyStatic||targets[1]!=(uintptr_t)spyStatic||WorldSettingsCopyVisibilityRenderTargets(0))return 2;
  return 0;
 }
 if(which==29){
  prepare(wsVisibilityEncode(1,0),1);ptr(worldBytes+0x220,mapBytes);spyMapPartial=1;
  if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes)!=0x1234||spyFailure||spyCalls!=2||spyMapFlags!=3||spyMapHeightPixels!=4096)return 1;
  spyMapHeightPixels=0;
  if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes)!=0x1234||spyFailure||spyCalls!=3)return 2;
  float observerAt=20.0f;memcpy(humanShip+0x28,&observerAt,4);memcpy(humanShip+0x30,&observerAt,4);
  if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes)!=0x1234||spyFailure||spyCalls!=5||spyMapHeightPixels||pixelBytes[5*64+5]!=0xab||pixelBytes[32*64+32]!=0x9b)return 3;
  return 0;
 }
 if(which==30){
  prepare(wsVisibilityEncode(0,0),1);spyMapPartial=1;int32_t partial[4]={0,0,4,4};
  if(WorldSettingsVisibilityCreateMap(mapBytes,0,partial)!=0x1236||!(pixelBytes[5*64+5]&15u))return 1;
  ptr(humanShip+0x20,0);LONG generation=wsVisibilityMapGeneration;
  if(WorldSettingsVisibilityCreateMap(mapBytes,0,partial)||wsVisibilityMapGeneration==generation||pixelBytes[5*64+5]!=0x90)return 2;
  ptr(humanShip+0x20,worldBytes);spyMapHeightPixels=0;
  if(WorldSettingsVisibilityCreateMap(mapBytes,0,partial)!=0x1236||!(spyMapFlags&2u)||!spyMapHeightPixels||(pixelBytes[5*64+5]&15u)!=11u)return 3;
  return 0;
 }
 if(which==31){
  prepare(wsVisibilityEncode(0,1),1);spyMapPartial=1;spyMapReset=1;int32_t partial[4]={0,0,4,4};
  if(WorldSettingsVisibilityCreateMap(mapBytes,1,partial)!=0x1236||wsVisibilityMapMemo.generation==wsVisibilityMapGeneration)return 1;
  spyMapHeightPixels=0;
  if(WorldSettingsVisibilityCreateMap(mapBytes,1,partial)!=0x1236||spyMapFlags!=3||spyMapHeightPixels!=64||wsVisibilityMapMemo.generation!=wsVisibilityMapGeneration)return 2;
  return 0;
 }
 if(which==32){
  prepare(wsVisibilityEncode(1,0),1);spyMapPartial=1;int32_t partial[4]={0,0,4,4};
  if(WorldSettingsVisibilityCreateMap(mapBytes,0,partial)!=0x1236||spyMapFlags!=3||spyMapHeightPixels!=4096)return 1;
  ptr(humanShip+0x20,0);
  if(WorldSettingsVisibilityCreateMap(mapBytes,0,partial)||pixelBytes[5*64+5]!=0x90)return 2;
  ptr(humanShip+0x20,worldBytes);spyMapHeightPixels=0;
  if(WorldSettingsVisibilityCreateMap(mapBytes,0,partial)!=0x1236||spyMapFlags!=3||spyMapHeightPixels!=4096||(pixelBytes[5*64+5]&15u)!=11u)return 3;
  spyMapHeightPixels=0;
  if(WorldSettingsVisibilityCreateMap(mapBytes,0,partial)!=0x1236||spyMapFlags||spyMapHeightPixels)return 4;
  return 0;
 }
 if(which==33){
  prepare(wsVisibilityEncode(0,0),0);spyMapPartial=1;int32_t partial[4]={0,0,4,4};float observerAt=20.0f;memcpy(humanShip+0x28,&observerAt,4);memcpy(humanShip+0x30,&observerAt,4);
  if(WorldSettingsVisibilityCreateMap(mapBytes,0,partial)!=0x1236||pixelBytes[5*64+5]!=0x90)return 1;
  WSVisibilityVisionSource unchanged=wsVisibilityMapMemo.vision[0];wsPut16(islandBytes+0x12e,1);spyMapHeightPixels=0;
  if(WorldSettingsVisibilityCreateMap(mapBytes,0,partial)!=0x1236||spyMapFlags!=3||spyMapHeightPixels!=64||pixelBytes[5*64+5]!=0xab||memcmp(&unchanged,wsVisibilityMapMemo.vision,sizeof unchanged))return 2;
  return 0;
 }
 if(which==34){
  prepare(wsVisibilityEncode(1,0),1);spyMapPartial=1;spyMapOwnerColor=0;int32_t partial[4]={0,0,4,4};
  if(humanBytes[0xcc]!=enemyBytes[0xcc]||WorldSettingsVisibilityCreateMap(mapBytes,0,partial)!=0x1236||pixelBytes[5*64+5]!=0x9b||pixelBytes[32*64+32]!=0x0b)return 1;
  float observerAt=20.0f;memcpy(humanShip+0x28,&observerAt,4);memcpy(humanShip+0x30,&observerAt,4);
  if(WorldSettingsVisibilityCreateMap(mapBytes,0,partial)!=0x1236||pixelBytes[5*64+5]!=0x0b||pixelBytes[32*64+32]!=0x9b)return 2;
  return 0;
 }
 if(which==35){
  prepare(wsVisibilityEncode(1,0),1);memset(cityBytes,0,sizeof cityBytes);memset(catalogueBytes,0,sizeof catalogueBytes);memset(definitionBytes,0,sizeof definitionBytes);memset(physicalTiles,0,sizeof physicalTiles);
  ptr(cityBytes,moduleBytes+0xfc678);ptr(cityBytes+0x20,islandBytes);ptr(cityBytes+0x28,enemyBytes);ptr(islandBytes+0x68,cityBytes);ptr(islandBytes+0x10,physicalTiles);
  ptr(worldBytes+0x200,catalogueBytes);ptr(catalogueBytes,moduleBytes+0x20300);ptr(moduleBytes+0x20300+0xe8,moduleBytes+0xb4d0);ptr(catalogueBytes+0x218+123*8,definitionBytes);ptr(definitionBytes,moduleBytes+0x1fac8);ptr(moduleBytes+0x1fac8+0xc0,moduleBytes+0x1090);ptr(moduleBytes+0x1fac8+0x160,moduleBytes+0x41e0);wsPut16(definitionBytes+0x18,0x22);
  wsPut32(physicalTiles+(4*16+4)*8,0x80000000u|123u);ptr(rendererBytes,moduleBytes+0xf63740);ptr(moduleBytes+0xf63740+0x180,(void*)WorldSettingsVisibilityRenderStatic180);ptr(moduleBytes+0xf63740+0x188,(void*)WorldSettingsVisibilityRenderStatic188);
  WSVisibilityWorld view;WSVisibilityDrawContext context;if(!wsVisibilityWorldRead(worldBytes,&view)||!wsVisibilityContextRead(&view,&context))return 1;wsVisibilityDrawContext=&context;float xyz[3]={20.5f,0,20.5f};spyStaticPosition=xyz;
  if(WorldSettingsVisibilityRenderStatic180(rendererBytes,quadBytes,7,11,0xc0,xyz)||WorldSettingsVisibilityRenderStatic188(rendererBytes,quadBytes,7,11,0xc0,xyz)||WorldSettingsVisibilityDrawStatic180(rendererBytes,quadBytes,7,11,0xc0,xyz)||spyStaticCalls)return 2;
  float observer=40.0f;memcpy(humanShip+0x28,&observer,4);memcpy(humanShip+0x30,&observer,4);if(!wsVisibilityContextRead(&view,&context))return 3;
  if(WorldSettingsVisibilityRenderStatic180(rendererBytes,quadBytes,7,11,0xc0,xyz)!=0x4455||WorldSettingsVisibilityRenderStatic188(rendererBytes,quadBytes,7,11,0xc0,xyz)!=0x4455||WorldSettingsVisibilityDrawStatic180(rendererBytes,quadBytes,7,11,0xc0,xyz)!=0x4455||WorldSettingsVisibilityDrawStatic188(rendererBytes,quadBytes,7,11,0xc0,xyz)!=0x4455||spyStaticCalls!=4||spyFailure)return 4;
  uint64_t targets[2]={0};if(WorldSettingsCopyVisibilityRenderTargets(targets)!=16||targets[0]!=(uintptr_t)(moduleBytes+0x49410)||targets[1]!=(uintptr_t)(moduleBytes+0x49bd0))return 5;
  wsVisibilityDrawContext=0;if(WorldSettingsVisibilityRenderStatic180(rendererBytes,quadBytes,7,11,0xc0,xyz)!=0x4455||WorldSettingsVisibilityDrawStatic188(rendererBytes,quadBytes,7,11,0xc0,xyz)!=0x4455||spyStaticCalls!=6||spyFailure)return 6;return 0;
 }
 if(which==36){
  prepare(wsVisibilityEncode(1,0),1);memset(cityBytes,0,sizeof cityBytes);memset(catalogueBytes,0,sizeof catalogueBytes);memset(definitionBytes,0,sizeof definitionBytes);memset(physicalTiles,0,sizeof physicalTiles);
  ptr(cityBytes,moduleBytes+0xfc678);ptr(cityBytes+0x20,islandBytes);ptr(cityBytes+0x28,enemyBytes);ptr(islandBytes+0x68,cityBytes);ptr(islandBytes+0x10,physicalTiles);ptr(worldBytes+0x200,catalogueBytes);ptr(catalogueBytes,moduleBytes+0x20300);ptr(moduleBytes+0x20300+0xe8,moduleBytes+0xb4d0);ptr(catalogueBytes+0x218+123*8,definitionBytes);ptr(definitionBytes,moduleBytes+0x1fac8);ptr(moduleBytes+0x1fac8+0xc0,moduleBytes+0x1090);ptr(moduleBytes+0x1fac8+0x160,moduleBytes+0x41e0);wsPut16(definitionBytes+0x18,0x22);
  uint32_t*anchor=(uint32_t*)(physicalTiles+(4*16+4)*8),*part=(uint32_t*)(physicalTiles+(5*16+5)*8);anchor[0]=0x80000000u|123u;part[0]=0x00090000u|123u;
  WSVisibilityWorld view;WSVisibilityDrawContext context;if(!wsVisibilityWorldRead(worldBytes,&view)||!wsVisibilityContextRead(&view,&context))return 1;void*owner=0;float xyz[3]={21.5f,0,21.5f};unsigned char before[sizeof physicalTiles];memcpy(before,physicalTiles,sizeof before);
  if(wsVisibilityOwnedBuilding(&context,&context.islands[0],xyz[0],xyz[2],&owner)!=1||owner!=enemyBytes||memcmp(before,physicalTiles,sizeof before))return 2;
  part[0]|=0x80000000u;if(wsVisibilityOwnedBuilding(&context,&context.islands[0],xyz[0],xyz[2],&owner)!=1)return 3;
  part[0]^=0x00400000u;if(wsVisibilityOwnedBuilding(&context,&context.islands[0],xyz[0],xyz[2],&owner))return 4;part[0]^=0x00400000u;
  part[1]=1u<<25;if(wsVisibilityOwnedBuilding(&context,&context.islands[0],xyz[0],xyz[2],&owner))return 5;part[1]=0;
  part[0]++;if(wsVisibilityOwnedBuilding(&context,&context.islands[0],xyz[0],xyz[2],&owner))return 6;part[0]--;
  anchor[0]&=~0x80000000u;if(wsVisibilityOwnedBuilding(&context,&context.islands[0],xyz[0],xyz[2],&owner))return 7;anchor[0]|=0x80010000u;if(wsVisibilityOwnedBuilding(&context,&context.islands[0],xyz[0],xyz[2],&owner))return 8;
  wsPut32(physicalTiles,0x00070000u|123u);if(wsVisibilityOwnedBuilding(&context,&context.islands[0],16.5f,16.5f,&owner))return 9;return 0;
 }
 if(which==37){
  prepare(wsVisibilityEncode(1,0),1);
  if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes)!=0x1234||spyViewportCalls!=1||spyDrawObservedViewport!=1||spyFailure||spyViewport[2]!=256)return 1;
  if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes)!=0x1234||spyViewportCalls!=1)return 2;
  float at=130.0f;memcpy(humanShip+0x28,&at,4);if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes)!=0x1234||spyViewportCalls!=2||spyDrawObservedViewport!=2)return 3;
  wsPut16(islandBytes+0x12e,3);if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes)!=0x1234||spyViewportCalls!=2)return 4;
  wsPut16(islandBytes+0x12e,2);if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes)!=0x1234||spyViewportCalls!=3)return 5;return 0;
 }
 if(which==38){
  prepare(wsVisibilityEncode(1,0),1);wsPut32(drawRendererBytes+0x460,0);
  if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes)!=0x1234||spyViewportCalls||wsVisibilityRenderMemo.valid||wsVisibilityRenderBusy||wsVisibilityDrawContext||wsVisibilityLastError)return 1;
  wsPut32(drawRendererBytes+0x460,256);if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes)!=0x1234||spyViewportCalls!=1)return 2;
  wsPut32(drawRendererBytes+0x460,320);if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes)!=0x1234||spyViewportCalls!=2||spyViewport[2]!=320)return 3;
  wsPut32(drawRendererBytes+0x458,0xffffffffu);if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes)||spyViewportCalls!=2)return 4;
  wsPut32(drawRendererBytes+0x458,0);ptr(drawRendererBytes+0x4c0,renderBlocks+0x1000);if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes)!=0x1234||spyViewportCalls!=3)return 5;
  ptr(drawRendererBytes+0x4c0,0);if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes)||spyViewportCalls!=3)return 6;return 0;
 }
 if(which==39){
  prepare(wsVisibilityEncode(1,0),1);spyViewportReset=1;
  if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes)||spyViewportCalls!=1||wsVisibilityRenderMemo.valid||wsVisibilityRenderBusy||wsVisibilityDrawContext)return 1;
  if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes)!=0x1234||spyViewportCalls!=2)return 2;
  WorldSettingsVisibilityReset();if(wsVisibilityRenderMemo.valid)return 3;
  if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes)!=0x1234||spyViewportCalls!=3)return 4;
  wsPut32(worldBytes+0x6eec,wsVisibilityEncode(1,1)|0x86);if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes)!=0x1234||spyViewportCalls!=4)return 5;
  if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes)!=0x1234||spyViewportCalls!=4)return 6;return 0;
 }
 if(which==40){
  prepare(0,0);ptr(drawRendererBytes,0);if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes)!=0x1234||spyViewportCalls)return 1;
  prepare(wsVisibilityEncode(1,0),1);InterlockedExchange(&wsVisibilityRenderBusy,1);if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes)||spyViewportCalls)return 2;InterlockedExchange(&wsVisibilityRenderBusy,0);
  ptr(moduleBytes+0xf63740+0x170,moduleBytes+0x48a21);if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes)||spyViewportCalls||wsVisibilityRenderBusy)return 3;return 0;
 }
 if(which==41){
  prepare(wsVisibilityEncode(0,0),0);wsPut32(listBytes,8193);
  if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes)||spyViewportCalls!=1||wsVisibilityRenderMemo.valid||wsVisibilityRenderBusy||wsVisibilityDrawContext)return 1;
  wsPut32(listBytes,1);spyMasked=1;if(WorldSettingsVisibilityDrawTerrain(worldBytes,listBytes,17,29,drawRendererBytes)!=0x1234||spyViewportCalls!=2||!wsVisibilityRenderMemo.valid||spyFailure)return 2;return 0;
 }
 if(which==42){
  prepare(wsVisibilityEncode(0,0),0);unsigned char*list=(unsigned char*)VirtualAlloc(0,8192,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);if(!list)return 1;
  wsPut32(list,47);for(uint32_t i=0;i<47;i++){unsigned char*r=list+8u+(size_t)i*88u;wsPut16(r,16);wsPut16(r+2,16);memset(r+0x38,255,4);r[0x38]=0;r[0x4d]=1;}
  unsigned char before[4144];memcpy(before,list,sizeof before);DWORD old;
  if(!VirtualProtect(list+4096,4096,PAGE_READONLY,&old)){VirtualFree(list,0,MEM_RELEASE);return 2;}
  if(wsVisibilityMaskList(worldBytes,list)||wsVisibilityBackupCount||memcmp(before,list,sizeof before)){VirtualFree(list,0,MEM_RELEASE);return 3;}
  if(!VirtualProtect(list+4096,4096,old,&old)){VirtualFree(list,0,MEM_RELEASE);return 4;}
  if(!wsVisibilityMaskList(worldBytes,list)||wsVisibilityBackupCount!=47||!wsVisibilityRestore()||memcmp(before,list,sizeof before)){VirtualFree(list,0,MEM_RELEASE);return 5;}
  VirtualFree(list,0,MEM_RELEASE);return 0;
 }
 return 99;
}
#endif
'''


class NativeVisibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='anno-visibility-')
        folder = Path(cls.temp.name)
        if os.name == 'nt':
            zig = ROOT / '.local/toolchain/ziglang/zig.exe'
            if not zig.is_file():
                cls.temp.cleanup()
                raise unittest.SkipTest('Visibility fixtures need the reviewed local Zig toolchain.')
            command, output = [str(zig), 'cc', '-target', 'x86_64-windows-gnu'], folder / 'visibility.dll'
        else:
            cc = shutil.which('cc') or shutil.which('clang') or shutil.which('gcc')
            if not cc:
                cls.temp.cleanup()
                raise unittest.SkipTest('Visibility fixtures need a native C compiler.')
            command, output = [cc], folder / 'visibility.so'
        source = folder / 'visibility.c'
        source.write_text(FIXTURE, encoding='utf-8')
        result = subprocess.run(command + ['-std=c11', '-shared', '-O2', '-Wall', '-Wextra',
            '-Werror', '-I', str(NATIVE), str(source), '-o', str(output)] + ([] if os.name == 'nt' else ['-fPIC']),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf-8', errors='replace')
        if result.returncode:
            cls.temp.cleanup()
            raise AssertionError(result.stdout)
        cls.lib = C.CDLL(str(output))
        cls.lib.policy.argtypes = [C.c_int32, C.c_int32]
        cls.lib.policy.restype = C.c_uint32
        cls.lib.decode.argtypes = [C.c_uint32, C.POINTER(C.c_int32)]
        cls.lib.scene.argtypes = [C.c_int32, C.c_int32, C.c_uint32, C.c_uint32, C.POINTER(C.c_uint32)]
        if os.name == 'nt':
            cls.lib.memory_case.argtypes = [C.c_uint32]
            cls.lib.fresh_case.argtypes = [C.c_uint32]
            cls.lib.scoped_reads_case.argtypes = [C.c_uint32]

    @classmethod
    def tearDownClass(cls):
        if os.name == 'nt':
            import _ctypes
            _ctypes.FreeLibrary(cls.lib._handle)
        del cls.lib
        cls.temp.cleanup()

    def test_policy_roundtrip_preserves_unrelated_native_flags(self):
        for map_mode in range(3):
            for enemy in range(2):
                code = self.lib.policy(map_mode, enemy)
                self.assertEqual(code, (1 + map_mode + 3 * enemy) << 12)
                for flags in (0, 0x86, 0x8fff, 0xffff8fff):
                    decoded = (C.c_int32 * 2)(-9, -9)
                    self.assertEqual(self.lib.decode(code | flags, decoded), 1)
                    self.assertEqual(list(decoded), [map_mode, enemy])

    def test_old_or_reserved_policy_is_not_reinterpreted(self):
        for flags, expected in ((0, 0), (0x86, 0), (0x8000, 0), (0x7000, -1), (0xffff, -1)):
            decoded = (C.c_int32 * 2)(-9, -9)
            self.assertEqual(self.lib.decode(flags, decoded), expected)
            self.assertEqual(list(decoded), [-9, -9])
        for map_mode, enemy in ((-1, 0), (3, 0), (0, -1), (0, 2)):
            self.assertEqual(self.lib.policy(map_mode, enemy), 0)

    def test_scene_policy_changes_only_reserved_transport_bits(self):
        for map_mode in range(3):
            for enemy in range(2):
                out = (C.c_uint32 * 3)()
                self.assertEqual(self.lib.scene(map_mode, enemy, 0x86, 0, out), 1)
                self.assertEqual(out[0], 0x86 | self.lib.policy(map_mode, enemy))
                self.assertEqual(out[1], self.lib.policy(map_mode, enemy))

    def test_malformed_or_pre_marked_scene_refused_atomically(self):
        for malformed, flags in ((1, 0), (2, 0), (3, 0), (0, 0x1000)):
            out = (C.c_uint32 * 3)()
            self.assertEqual(self.lib.scene(0, 0, flags, malformed, out), 0)
            self.assertEqual(out[1], 0)
            self.assertEqual(out[2], 1)

    @unittest.skipUnless(os.name == 'nt', 'Display-memory adapter uses Windows VirtualQuery; portable policy tests run everywhere.')
    def test_display_masks_restore_on_discovery_and_preserve_world_state(self):
        for case in range(43):
            with self.subTest(case=case):
                self.assertEqual(self.lib.memory_case(case), 0)

    @unittest.skipUnless(os.name == 'nt', 'Scoped actor/stack reads use real Windows VirtualQuery.')
    def test_scoped_actor_reads_match_all_native_layouts_and_refuse_mutations(self):
        for case in (0, 1, 2, 3, 6):
            with self.subTest(case=case):
                self.assertEqual(self.lib.scoped_reads_case(case), 0)

    @unittest.skipUnless(os.name == 'nt', 'Scoped position reads use real Windows VirtualQuery.')
    def test_scoped_stack_reads_keep_fresh_values_and_checked_fallback(self):
        for case in (4, 5):
            with self.subTest(case=case):
                self.assertEqual(self.lib.scoped_reads_case(case), 0)

    @unittest.skipUnless(os.name == 'nt', 'Fresh-world memory preflight uses Windows VirtualQuery.')
    def test_fresh_terra_clears_only_human_discovery_once(self):
        self.assertEqual(self.lib.fresh_case(0), 0)

    @unittest.skipUnless(os.name == 'nt', 'Fresh-world memory preflight uses Windows VirtualQuery.')
    def test_fresh_revealed_modes_preserve_native_discovery(self):
        for case in (1, 2):
            with self.subTest(case=case):
                self.assertEqual(self.lib.fresh_case(case), 0)

    @unittest.skipUnless(os.name == 'nt', 'Fresh-world memory preflight uses Windows VirtualQuery.')
    def test_fresh_normalization_preflights_every_target_before_writing(self):
        for case in (3, 4, 7):
            with self.subTest(case=case):
                self.assertEqual(self.lib.fresh_case(case), 0)

    @unittest.skipUnless(os.name == 'nt', 'Fresh-world memory preflight uses Windows VirtualQuery.')
    def test_reload_and_wrong_policy_do_not_clear_discovery(self):
        for case in (5, 6):
            with self.subTest(case=case):
                self.assertEqual(self.lib.fresh_case(case), 0)


if __name__ == '__main__':
    unittest.main()
