/* Test-only boundaries for world_factory.c; no game/file/UI operations. */
#include <stdint.h>
#include <string.h>
#include <stdio.h>
static int fixtureActive,fixturePrepared,fixtureHasObject,fixtureValidation,fixtureMessage;
static int32_t fixtureResult;
static uint64_t fixtureStats[64];
static void *fixtureNativeOut;
static char fixturePath[]="C:\\CopiedGame\\Scenes\\WorldSettings_123_1.sze";
static void fixtureEvent(uint64_t event){uint64_t n=fixtureStats[19]++;if(n<40)fixtureStats[20+n]=event;}
static void fixtureDelete(void*object,uint32_t flags){fixtureStats[4]++;fixtureStats[15]=(uintptr_t)object;fixtureStats[18]=flags;fixtureEvent(5);}
static void fixtureRelease(void*object){fixtureDelete(object,1);}
static void *fixtureVtable[4]={fixtureDelete,0,0,fixtureRelease};
static struct {void**vtable;uint64_t sentinel;} fixtureObject={fixtureVtable,0x1122334455667788};
#include "../world_factory.c"
int WorldSettingsIsActive(void){fixtureStats[0]++;fixtureEvent(1);return fixtureActive;}
const char *WorldSettingsPendingPath(void){fixtureStats[1]++;fixtureEvent(2);return fixturePrepared==0?NULL:fixturePrepared==1?"":fixturePath;}
int WorldSettingsValidateScene(void*object,char*message,uint32_t cap){
 fixtureStats[3]++;fixtureStats[14]=(uintptr_t)object;fixtureEvent(4);
 if(fixtureMessage==1)snprintf(message,cap,"Synthetic loaded-world failure.");
 else if(fixtureMessage==2)memset(message,'Q',cap);
 else if(fixtureMessage==3)snprintf(message,cap,"Stale diagnostic on success.");
 else if(cap)message[0]=0;
 return fixtureValidation;
}
void WorldSettingsFinishAttempt(int success){
 fixtureStats[5]++;fixtureStats[6]=(uint32_t)success;
 fixtureStats[17]=fixtureNativeOut?(uintptr_t)*(void**)fixtureNativeOut:0;fixtureEvent(6);
}
static void fixtureFailureReporter(const char*message){
 fixtureStats[60]++;fixtureStats[61]=fixtureStats[5];
 fixtureStats[62]=fixtureNativeOut?(uintptr_t)*(void**)fixtureNativeOut:0;
 fixtureStats[63]=message&&message[0]&&strcmp(message,WorldSettingsLastFactoryError())==0;
 fixtureEvent(7);
}
static int32_t fixtureOriginal(int32_t mode,const char*path,void*saveList,void**out,void*metadata,uint32_t index,uint32_t flags){
 fixtureStats[2]++;fixtureEvent(3);fixtureStats[7]=(uint32_t)mode;fixtureStats[8]=(uintptr_t)path;
 fixtureStats[9]=(uintptr_t)saveList;fixtureStats[10]=(uintptr_t)out;fixtureStats[11]=(uintptr_t)metadata;fixtureStats[12]=index;fixtureStats[13]=flags;
 fixtureStats[16]=(uintptr_t)*out;fixtureNativeOut=out;*out=fixtureHasObject?&fixtureObject:NULL;return fixtureResult;
}
__declspec(dllexport) void FactoryFixtureConfigure(int active,int prepared,int32_t result,int hasObject,int validation,int message){
 fixtureActive=active;fixturePrepared=prepared;fixtureResult=result;fixtureHasObject=hasObject;fixtureValidation=validation;fixtureMessage=message;
 memset(fixtureStats,0,sizeof fixtureStats);fixtureNativeOut=NULL;
 WorldSettingsSetFailureReporter(NULL);
}
__declspec(dllexport) void FactoryFixtureEnableReporter(void){WorldSettingsSetFailureReporter(fixtureFailureReporter);}
__declspec(dllexport) uint64_t FactoryFixtureStat(uint32_t index){return index<64?fixtureStats[index]:0;}
__declspec(dllexport) void*FactoryFixtureOriginal(void){return fixtureOriginal;}
__declspec(dllexport) void*FactoryFixtureObject(void){return &fixtureObject;}
__declspec(dllexport) const char*FactoryFixturePath(void){return fixturePath;}
