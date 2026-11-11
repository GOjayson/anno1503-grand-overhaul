"""Disaster policies through actual Windows atomic checkpoint operations.

The native save/factory boundaries are controlled fixtures, not a game run.
Inherited cases also exercise the preceding chart protocol with no policy.
"""
import sys
sys.dont_write_bytecode=True
import ctypes as C
import hashlib
import os
from pathlib import Path
import struct
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
import test_world_visibility_memory_io as memory
from anno1503_overhaul.world_options import PRIVATE,authored
from anno1503_overhaul.world_options_disasters import apply_disaster_memory


POLICY_STRUCT=r'''
typedef struct WSWorldSettings {
 uint32_t size;int32_t difficulty,islandSize,islandCount,spacing,aiCount;
 uint32_t cultures,factions;
 int32_t startingMoney,startingFleet,aiDifficulty,plantFertility,mineralFertility,worldSize;
 uint32_t mapSeed;
 int32_t startClimate,startIsland,cargoMode,cargoTools,cargoWood,cargoFood,climateBalance,layoutStyle,disasters;
 int32_t fairStarts,startSeparation,resourceDistribution,guaranteeBasics,mapVisibility,enemyVisibility;
 int32_t pirateFrequency,pirateStrength,merchantFrequency,islandVariety,minPolar,maxPolar,minTemperate,maxTemperate,minTropical,maxTropical;
 uint32_t disasterMask,disasterFrequency,disasterSeverity;int32_t islandRotation;
} WSWorldSettings;
_Static_assert(sizeof(WSWorldSettings)==176,"Current settings fixture ABI differs");
_Static_assert(offsetof(WSWorldSettings,disasterMask)==160,"Disaster field offset differs");
#include "disaster_policy.inc"
'''

POLICY_EXPORTS=r'''
static unsigned char disasterIsland[0x200],disasterCity[0x40],disasterTable[0x50],disasterEvent[0x80],disasterDrought[24],disasterBefore[0x80];
static uint32_t disasterNativeCalls,disasterBad;static int32_t disasterOwner;
static void*disasterCreate(void*table,uint32_t type,uint32_t unused,const float*position,int32_t owner){
 (void)table;(void)unused;(void)position;disasterNativeCalls++;disasterOwner=owner;memset(disasterEvent,0x6d,sizeof disasterEvent);
 void*vt=moduleBytes+(type==29u?0xf2230u:0xf2130u);if(disasterBad)vt=moduleBytes+0xf2030u;memcpy(disasterEvent,&vt,8);
 void*p=disasterIsland;memcpy(disasterEvent+8,&p,8);p=worldBytes;memcpy(disasterEvent+0x10,&p,8);
 wsPut32(disasterEvent+0x28,0);wsPut32(disasterEvent+0x2c,type);wsPut32(disasterEvent+0x48,type==29u?10000u:7500u);memcpy(disasterBefore,disasterEvent,sizeof disasterEvent);return disasterEvent;
}
static void disasterBegin(void*island){
 disasterNativeCalls++;if(wsCertPointer(island,0x100))return;memset(disasterDrought,0,sizeof disasterDrought);wsPut32(disasterDrought+4,6);disasterDrought[0x12]=1;
 void*p=disasterDrought;memcpy((unsigned char*)island+0x100,&p,8);memcpy(disasterBefore,disasterDrought,sizeof disasterDrought);
}
static void disasterThunk(uint32_t at,void*fn){moduleBytes[at]=0x48;moduleBytes[at+1]=0xb8;memcpy(moduleBytes+at+2,&fn,8);moduleBytes[at+10]=0xff;moduleBytes[at+11]=0xe0;FlushInstructionCache(GetCurrentProcess(),moduleBytes+at,12);}
static void disasterGraph(void){
 memset(disasterIsland,0,sizeof disasterIsland);memset(disasterCity,0,sizeof disasterCity);memset(disasterTable,0,sizeof disasterTable);
 void*p=worldBytes;memcpy(disasterIsland+0x38,&p,8);p=disasterIsland;memcpy(disasterCity+0x20,&p,8);memcpy(disasterTable+0x38,&p,8);
 p=moduleBytes+0xf2588;memcpy(disasterTable,&p,8);p=moduleBytes+0x371c0;memcpy(moduleBytes+0xf2588,&p,8);
 disasterThunk(0x371c0,(void*)disasterCreate);disasterThunk(0x58890,(void*)disasterBegin);
}
__declspec(dllexport) int fixture_disaster_enable(uint32_t master,uint32_t mask,uint32_t frequency,uint32_t severity){
 WSWorldSettings s={0};s.size=sizeof s;s.disasters=(int32_t)master;s.disasterMask=mask;s.disasterFrequency=frequency;s.disasterSeverity=severity;
 wsPut32(worldBytes+0x6eec,0x1000u|(master?0u:0x86u));WorldSettingsExpectDisasterOptions(&s);char e[256];
 int result=WorldSettingsBindDisasterOptions(worldBytes,e,sizeof e);WorldSettingsFinishDisasterAttempt(result);
 uint16_t flags=(uint16_t)wsU32(worldBytes+0x6eec);if(nativeSize>=50u)memcpy(nativeOutput+48,&flags,2);return result;
}
__declspec(dllexport) int fixture_disaster_current(uint32_t*out){WSDisasterContext c={0};if(!out||!wsDisasterSnapshot(worldBytes,&c))return 0;out[0]=c.master;out[1]=c.mask;out[2]=c.frequency;out[3]=c.severity;return 1;}
__declspec(dllexport) uint32_t fixture_disaster_random(uint32_t kind,uint32_t random,uint32_t denominator){disasterGraph();return kind?WorldSettingsDisasterPlagueRandom(random,denominator,disasterCity):WorldSettingsDisasterFireRandom(random,denominator,disasterCity);}
__declspec(dllexport) int fixture_disaster_effect(uint32_t kind,uint32_t existing,uint32_t bad,uint32_t*out){
 if(!out||kind>2u)return 0;disasterGraph();disasterNativeCalls=0;disasterBad=bad;disasterOwner=0;memset(disasterEvent,0,sizeof disasterEvent);memset(disasterBefore,0,sizeof disasterBefore);
 if(kind==2u){
  if(existing){memset(disasterDrought,0,sizeof disasterDrought);wsPut32(disasterDrought+4,6);void*p=disasterDrought;memcpy(disasterIsland+0x100,&p,8);memcpy(disasterBefore,disasterDrought,sizeof disasterDrought);}
  WorldSettingsDisasterDroughtBegin(disasterIsland);void*p=wsCertPointer(disasterIsland,0x100);out[0]=!!p;out[1]=disasterNativeCalls;out[2]=p?wsU32((unsigned char*)p+4):0;out[3]=0;
  if(p)for(uint32_t i=0;i<24u;i++)if((i<4u||i>=8u)&&((unsigned char*)p)[i]!=disasterBefore[i])out[3]++;
 }else{
  float position[4]={8,0,8,0};void*p=WorldSettingsDisasterCreateEvent(disasterTable,kind?346u:29u,0,position,-13);
  out[0]=!!p;out[1]=disasterNativeCalls;out[2]=wsU32(disasterEvent+0x48);out[3]=0;out[4]=(uint32_t)disasterOwner;
  if(p)for(uint32_t i=0;i<sizeof disasterEvent;i++)if((i<0x48u||i>=0x4cu)&&disasterEvent[i]!=disasterBefore[i])out[3]++;
 }return 1;
}
'''


def chunks(raw):
 at=16;result=[]
 while at<len(raw):
  n=struct.unpack_from('<I',raw,at+12)[0];result.append((raw[at:at+12].rstrip(b'\0'),at,n));at+=16+n
 if at!=len(raw):raise ValueError('Truncated fixture chunks.')
 return result


def rebless_native(raw):
 result=bytearray(raw);chart=next((at,n)for tag,at,n in chunks(result)if tag==b'WSCHART')
 at,n=chart;core=result[:at]+result[at+16+n:];struct.pack_into('<I',core,12,len(core)-16)
 result[at+32:at+64]=hashlib.sha256(core).digest();return bytes(result)


@unittest.skipUnless(os.name=='nt','Actual checkpoint files use Windows BCrypt and ReplaceFile.')
class DisasterMemoryIOTests(memory.MemoryIOTests):
 @classmethod
 def setUpClass(cls):
  files={PRIVATE+'start_visibility_memory_io.inc':authored('start_visibility_memory_io.inc')}
  apply_disaster_memory(files)
  source=memory.FIXTURE.replace('#include "start_visibility_memory_io.inc"',POLICY_STRUCT+'\n'+files[PRIVATE+'start_visibility_memory_io.inc'].decode())
  source=source.replace('0x40000','0x130000')
  anchor='fault=saveCalls=stageCalls=applyCalls=releaseCalls=factoryCalls=reports=fixtureActive=0;'
  initialise='void*worldVT=moduleBytes+0xff650;memcpy(worldBytes,&worldVT,8);void*getter=moduleBytes+0xd1910;memcpy(moduleBytes+0xff650+0xf0,&getter,8);wsDisasterClearLoaded();'
  if source.count(anchor)!=1:raise AssertionError('Native-memory fixture initialisation differs.')
  source=source.replace(anchor,initialise+anchor)
  # The fixture factory models the saved native flag load independently of
  # policy publication; the real factory has separate World allocations.
  anchor='CloseHandle(h);return 0;}\n__declspec(dllexport) int fixture_init'
  load='unsigned char head[64];DWORD got=0;if(ReadFile(h,head,sizeof head,&got,NULL)&&got>=50u)wsPut32(worldBytes+0x6eec,wsU16(head+48));CloseHandle(h);return 0;}\n__declspec(dllexport) int fixture_init'
  if source.count(anchor)!=1:raise AssertionError('Native-memory fixture factory differs.')
  source=source.replace(anchor,load)+POLICY_EXPORTS
  original=memory.FIXTURE
  try:
   memory.FIXTURE=source;super().setUpClass()
  finally:memory.FIXTURE=original
  cls.lib.fixture_disaster_enable.argtypes=[C.c_uint32]*4
  cls.lib.fixture_disaster_current.argtypes=[C.POINTER(C.c_uint32)]
  cls.lib.fixture_disaster_random.argtypes=[C.c_uint32]*3;cls.lib.fixture_disaster_random.restype=C.c_uint32
  cls.lib.fixture_disaster_effect.argtypes=[C.c_uint32,C.c_uint32,C.c_uint32,C.POINTER(C.c_uint32)]
 def current(self):
  out=(C.c_uint32*4)();return list(out)if self.lib.fixture_disaster_current(out)else None
 def enable(self,master=1,mask=31,frequency=341,severity=341):
  self.assertEqual(self.lib.fixture_disaster_enable(master,mask,frequency,severity),1)
  self.assertEqual(self.current(),[master,mask,frequency,severity])
 def policy_chunk(self,raw):return next((at,n)for tag,at,n in chunks(raw)if tag==b'WSDISAST')
 def test_policy_save_is_separate_and_bound_to_unchanged_chart_hash(self):
  self.enable(mask=21,frequency=100,severity=549)
  path=self.save('policy.sav');raw=path.read_bytes();self.assertEqual(self.lib.fixture_parse(raw,len(raw)),1)
  tags=[tag for tag,at,n in chunks(raw)];self.assertEqual(tags[-2:],[b'WSDISAST',b'WSCHART'])
  at,n=self.policy_chunk(raw);self.assertEqual(n,64);p=raw[at+16:at+80]
  self.assertEqual(p[:16],b'WSDISR01'+struct.pack('<II',1,64))
  self.assertEqual(struct.unpack_from('<6I',p,32),(256,256,1,21,100,549))
  self.assertEqual(p[56:],bytes(8))
  self.assertEqual(self.lib.fixture_load(os.fsencode(path)),1)
  self.assertEqual(self.current(),[1,21,100,549])
  backup=list(self.folder.glob('*.wschart-native-backup-*'))
  self.assertEqual(len(backup),1)
  expected=bytearray(self.original);struct.pack_into('<H',expected,48,0x1080)
  self.assertEqual(backup[0].read_bytes(),bytes(expected))
 def test_malformed_policy_cannot_be_reblessed_by_chart_native_checksum(self):
  self.enable();raw=self.save('schema.sav').read_bytes();at,n=self.policy_chunk(raw);start=at+16
  changes=((8,2),(12,63),(32,512),(36,512),(40,2),(44,32),(48,3),(52,340),(56,1))
  for offset,value in changes:
   with self.subTest(offset=offset,value=value):
    changed=bytearray(raw);struct.pack_into('<I',changed,start+offset,value);changed=rebless_native(changed)
    self.assertEqual(self.lib.fixture_parse(changed,len(changed)),0)
  changed=bytearray(raw);changed[start+16]^=1;changed=rebless_native(changed)
  self.assertEqual(self.lib.fixture_parse(changed,len(changed)),0)
 def test_duplicate_or_unauthenticated_policy_is_refused(self):
  self.enable();raw=self.save('duplicates.sav').read_bytes();at,n=self.policy_chunk(raw)
  duplicate=bytearray(raw+raw[at:at+80]);struct.pack_into('<I',duplicate,12,len(duplicate)-16);duplicate=rebless_native(duplicate)
  self.assertEqual(self.lib.fixture_parse(duplicate,len(duplicate)),0)
  chart=next((a,n)for tag,a,n in chunks(raw)if tag==b'WSCHART');a,n=chart
  standalone=bytearray(raw[:a]+raw[a+16+n:]);struct.pack_into('<I',standalone,12,len(standalone)-16)
  self.assertEqual(self.lib.fixture_parse(bytes(standalone),len(standalone)),0)
  changed=bytearray(raw);changed[at+16+48]^=1
  self.assertEqual(self.lib.fixture_parse(bytes(changed),len(changed)),0)
 def test_loaded_policy_wins_over_current_and_older_save_clears_policy(self):
  self.enable(mask=21,frequency=100,severity=549);path=self.save('first.sav')
  self.enable(mask=31);self.assertEqual(self.lib.fixture_load(os.fsencode(path)),1)
  self.assertEqual(self.current(),[1,21,100,549])
  old=self.folder/'older.sav';old.write_bytes(self.original)
  self.assertEqual(self.lib.fixture_load(os.fsencode(old)),1);self.assertIsNone(self.current())
 def test_failed_chart_publication_does_not_publish_loaded_disaster_policy(self):
  self.enable(mask=21,frequency=100,severity=549);path=self.save('failed.sav');self.enable()
  self.lib.fixture_fault(4);self.assertEqual(self.lib.fixture_load(os.fsencode(path)),0)
  self.assertEqual(self.current(),[1,31,341,341]);self.assertEqual(self.lib.fixture_counts(3),1)
 def test_native_flag_mismatch_refuses_before_chart_publication(self):
  self.enable();path=self.save('flags.sav');raw=bytearray(path.read_bytes());at,n=self.policy_chunk(raw)
  struct.pack_into('<I',raw,at+16+44,0);raw=rebless_native(raw);path.write_bytes(raw)
  self.assertEqual(self.lib.fixture_parse(raw,len(raw)),1)
  self.assertEqual(self.lib.fixture_load(os.fsencode(path)),0)
  self.assertEqual(self.lib.fixture_counts(2),0);self.assertEqual(self.current(),[1,31,341,341])
 def test_compiled_callbacks_change_only_new_native_event_duration_or_drought_extent(self):
  for kind,index,normal in ((0,2,10000),(1,3,7500),(2,4,6)):
   for severity in range(3):
    packed=(341&~(3<<(index*2)))|(severity<<(index*2));self.enable(severity=packed)
    out=(C.c_uint32*5)();self.assertEqual(self.lib.fixture_disaster_effect(kind,0,0,out),1)
    expected=(normal//2 if severity==0 else normal*2 if severity==2 else normal)if kind!=2 else(3,6,9)[severity]
    self.assertEqual(list(out)[:4],[1,1,expected,0],(kind,severity,list(out)))
    if kind!=2:self.assertEqual(out[4],0xfffffff3)
   self.enable(mask=31&~(1<<index));out=(C.c_uint32*5)()
   self.assertEqual(self.lib.fixture_disaster_effect(kind,0,0,out),1);self.assertEqual(list(out)[:2],[0,0])
  self.enable(severity=(341&~(3<<8))|(2<<8));out=(C.c_uint32*5)()
  self.assertEqual(self.lib.fixture_disaster_effect(2,1,0,out),1);self.assertEqual(list(out)[:4],[1,1,6,0])
 def test_unknown_returned_event_identity_is_not_modified_and_guid_mismatch_uses_native_random(self):
  self.enable(severity=(341&~(3<<4))|(2<<4));out=(C.c_uint32*5)()
  self.assertEqual(self.lib.fixture_disaster_effect(0,0,1,out),1);self.assertEqual(list(out)[:4],[1,1,10000,0])
  for kind,bit in ((0,1),(1,2)):
   self.enable(mask=31&~bit)
   self.assertEqual(self.lib.fixture_disaster_random(kind,0,31),4)
   self.lib.fixture_world_change()
   self.assertEqual(self.lib.fixture_disaster_random(kind,12345,31),12345)
   self.lib.fixture_world_change()
   self.assertEqual(self.lib.fixture_disaster_random(kind,0,31),4)


if __name__=='__main__':unittest.main()
