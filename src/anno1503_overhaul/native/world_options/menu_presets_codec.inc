/* Versioned, bounded text presets. No native pointers or opaque structs are
 * persisted. The caller validates the decoded settings before publication. */
#include <stddef.h>
#ifndef WS_WORLD_OPTIONS_GENERATOR
#error The preset codec requires the reviewed World options generator identity.
#endif
#define WS_PRESET_MAX_BYTES 4096u
#define WS_PRESET_NAME_MAX 32u
static const char wsPresetHeader[]="ANNO1503_WORLD_PRESET 5\nGENERATOR=" WS_WORLD_OPTIONS_GENERATOR "\n";
/* Exact predecessors migrate in memory only. New generation options retain
 * the preceding selection path; added disaster choices use native Normal. */
static const char wsPresetLegacyHeader4[]="ANNO1503_WORLD_PRESET 4\nGENERATOR=ws6-6113d0190fad378ad46a5a36c921b7d70b437f31359c6836ba3dd74c585f3327\n";
static const char wsPresetLegacyHeader3[]="ANNO1503_WORLD_PRESET 3\nGENERATOR=ws6-e980d1f2563739790004625336b4a6f243c94fb0e00bc59bb80662f4546693ae\n";
/* Exact dev.3 choices retain the identical layout and full 43-field ABI. */
static const char wsPresetLegacyHeader5[]="ANNO1503_WORLD_PRESET 5\nGENERATOR=ws6-601be2d158e48f8b09bea0b310e4e9ecd2cab3c5ece5647d035af668e7c67f02\n";
typedef struct WSMenuPresetField {const char *name;size_t offset;int unsignedValue;} WSMenuPresetField;
#define WS_PRESET_FIELD(name,isUnsigned) {#name,offsetof(WSWorldSettings,name),isUnsigned}
static const WSMenuPresetField wsPresetFields[]={
 WS_PRESET_FIELD(difficulty,0),WS_PRESET_FIELD(islandSize,0),
 WS_PRESET_FIELD(islandCount,0),WS_PRESET_FIELD(spacing,0),
 WS_PRESET_FIELD(aiCount,0),WS_PRESET_FIELD(cultures,1),WS_PRESET_FIELD(factions,1),
 WS_PRESET_FIELD(startingMoney,0),WS_PRESET_FIELD(startingFleet,0),
 WS_PRESET_FIELD(aiDifficulty,0),WS_PRESET_FIELD(plantFertility,0),
 WS_PRESET_FIELD(mineralFertility,0),WS_PRESET_FIELD(worldSize,0),
 WS_PRESET_FIELD(mapSeed,1),WS_PRESET_FIELD(startClimate,0),
 WS_PRESET_FIELD(startIsland,0),WS_PRESET_FIELD(cargoMode,0),
 WS_PRESET_FIELD(cargoTools,0),WS_PRESET_FIELD(cargoWood,0),
 WS_PRESET_FIELD(cargoFood,0),WS_PRESET_FIELD(climateBalance,0),
 WS_PRESET_FIELD(layoutStyle,0),WS_PRESET_FIELD(disasters,0),
 WS_PRESET_FIELD(fairStarts,0),WS_PRESET_FIELD(startSeparation,0),
 WS_PRESET_FIELD(resourceDistribution,0),WS_PRESET_FIELD(guaranteeBasics,0),
 WS_PRESET_FIELD(mapVisibility,0),WS_PRESET_FIELD(enemyVisibility,0),
 WS_PRESET_FIELD(pirateFrequency,0),WS_PRESET_FIELD(pirateStrength,0),
 WS_PRESET_FIELD(merchantFrequency,0),WS_PRESET_FIELD(islandVariety,0),
 WS_PRESET_FIELD(minPolar,0),WS_PRESET_FIELD(maxPolar,0),
 WS_PRESET_FIELD(minTemperate,0),WS_PRESET_FIELD(maxTemperate,0),
 WS_PRESET_FIELD(minTropical,0),WS_PRESET_FIELD(maxTropical,0),
 WS_PRESET_FIELD(disasterMask,1),WS_PRESET_FIELD(disasterFrequency,1),
 WS_PRESET_FIELD(disasterSeverity,1),WS_PRESET_FIELD(islandRotation,0)
};
#undef WS_PRESET_FIELD

static int wsMenuUnsigned(const char *text,size_t length,uint32_t *out){
 if(!text||!out||!length||length>10u)return 0;
 uint32_t value=0;
 for(size_t i=0;i<length;i++){
  unsigned char c=(unsigned char)text[i];if(c<'0'||c>'9')return 0;
  uint32_t digit=(uint32_t)(c-'0');if(value>(UINT32_MAX-digit)/10u)return 0;
  value=value*10u+digit;
 }
 *out=value;return 1;
}
static int wsMenuSigned(const char *text,size_t length,int32_t *out){
 if(!text||!out)return 0;
 int negative=length&&text[0]=='-';uint32_t value;
 if(!out||!wsMenuUnsigned(text+negative,length-(size_t)negative,&value))return 0;
 if(value>(negative?2147483648u:2147483647u))return 0;
 *out=(int32_t)(negative?-(int64_t)value:(int64_t)value);return 1;
}
static int wsPresetNameValid(const char *name){
 if(!name)return 0;size_t n=strlen(name);if(!n||n>WS_PRESET_NAME_MAX||name[0]==' '||name[n-1]==' ')return 0;
 char upper[WS_PRESET_NAME_MAX+1];
 for(size_t i=0;i<n;i++){
  unsigned char c=(unsigned char)name[i];
  if(!((c>='A'&&c<='Z')||(c>='a'&&c<='z')||(c>='0'&&c<='9')||c==' '||c=='_'||c=='-'))return 0;
  upper[i]=(char)(c>='a'&&c<='z'?c-'a'+'A':c);
 }
 upper[n]=0;
 if(!strcmp(upper,"CON")||!strcmp(upper,"PRN")||!strcmp(upper,"AUX")||!strcmp(upper,"NUL"))return 0;
 if(n==4&&(!memcmp(upper,"COM",3)||!memcmp(upper,"LPT",3))&&upper[3]>='0'&&upper[3]<='9')return 0;
 return 1;
}
static int wsPresetEncode(const WSWorldSettings *settings,char *out,uint32_t cap,uint32_t *written){
 if(!settings||settings->size!=sizeof(*settings)||!out||!written||cap>WS_PRESET_MAX_BYTES)return 0;
 size_t used=sizeof(wsPresetHeader)-1;if(used>=cap)return 0;memcpy(out,wsPresetHeader,used);
 for(size_t i=0;i<sizeof(wsPresetFields)/sizeof(wsPresetFields[0]);i++){
  const WSMenuPresetField *field=&wsPresetFields[i];uint32_t u;int32_t s;
  memcpy(&u,(const unsigned char*)settings+field->offset,sizeof u);memcpy(&s,&u,sizeof s);
  int size=field->unsignedValue?snprintf(out+used,cap-(uint32_t)used,"%s=%u\n",field->name,u):snprintf(out+used,cap-(uint32_t)used,"%s=%d\n",field->name,s);
  if(size<0||(size_t)size>=cap-used)return 0;used+=(size_t)size;
 }
 if(cap-used<=4u)return 0;memcpy(out+used,"END\n",4);used+=4;out[used]=0;*written=(uint32_t)used;return 1;
}
static int wsPresetDecode(const char *data,uint32_t length,WSWorldSettings *out){
 if(!data||!out||!length||length>WS_PRESET_MAX_BYTES)return 0;
 /* CRLF and LF are accepted, but every complete line and generator identity
  * must match; duplicate, missing, reordered or additional fields are refused. */
 char canonical[WS_PRESET_MAX_BYTES+1];uint32_t n=0;
 for(uint32_t i=0;i<length;i++){
  unsigned char c=(unsigned char)data[i];
  if(c=='\r'){if(i+1u>=length||data[i+1]!='\n')return 0;continue;}
  if(c!='\n'&&(c<32u||c>126u))return 0;
  canonical[n++]=(char)c;
 }
 canonical[n]=0;size_t at=sizeof(wsPresetHeader)-1;
 size_t fields=sizeof(wsPresetFields)/sizeof(wsPresetFields[0]);
 if(at>n||memcmp(canonical,wsPresetHeader,at)){
  at=sizeof(wsPresetLegacyHeader5)-1;
  if(at>n||memcmp(canonical,wsPresetLegacyHeader5,at)){
  at=sizeof(wsPresetLegacyHeader4)-1;fields=32u;
  if(at>n||memcmp(canonical,wsPresetLegacyHeader4,at)){
   at=sizeof(wsPresetLegacyHeader3)-1;fields=29u;
   if(at>n||memcmp(canonical,wsPresetLegacyHeader3,at))return 0;
  }
  }
 }
 WSWorldSettings result={0};result.size=sizeof result;
 result.pirateFrequency=result.pirateStrength=result.merchantFrequency=1;
 result.maxPolar=result.maxTemperate=result.maxTropical=128;
 result.disasterMask=31;result.disasterFrequency=result.disasterSeverity=341;
 for(size_t i=0;i<fields;i++){
  const WSMenuPresetField *field=&wsPresetFields[i];size_t key=strlen(field->name);
  if(at+key+2u>n||memcmp(canonical+at,field->name,key)||canonical[at+key]!='=')return 0;
  at+=key+1u;size_t end=at;while(end<n&&canonical[end]!='\n')end++;
  if(end==n)return 0;uint32_t raw=0;
  if(field->unsignedValue){if(!wsMenuUnsigned(canonical+at,end-at,&raw))return 0;}
  else{int32_t value;if(!wsMenuSigned(canonical+at,end-at,&value))return 0;memcpy(&raw,&value,sizeof raw);}
  memcpy((unsigned char*)&result+field->offset,&raw,sizeof raw);at=end+1u;
 }
 if(n-at!=4u||memcmp(canonical+at,"END\n",4))return 0;
 *out=result;return 1;
}
