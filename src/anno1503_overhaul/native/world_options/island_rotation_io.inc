/* Only selected, fingerprinted templates are copied. Temporary assets use
 * CREATE_NEW and are removed through an identity-checked DELETE handle. */
#include "island_rotation_codec.inc"
typedef struct WSRotationFile {char path[MAX_PATH];DWORD volume,high,low;uint32_t size,index,rotation;unsigned char digest[32];} WSRotationFile;
static WSRotationFile wsRotationFiles[WS_LIMIT];
static uint32_t wsRotationSequence;
static int wsRotationDigest(const unsigned char*data,uint32_t size,unsigned char digest[32]){
 BCRYPT_ALG_HANDLE algorithm=NULL;BCRYPT_HASH_HANDLE hash=NULL;int ok=0;
 if(BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,NULL,0)<0)goto done;
 if(BCryptCreateHash(algorithm,&hash,NULL,0,NULL,0,0)<0)goto done;
 if(BCryptHashData(hash,(PUCHAR)data,size,0)<0||BCryptFinishHash(hash,digest,32,0)<0)goto done;ok=1;
done:if(hash)BCryptDestroyHash(hash);if(algorithm)BCryptCloseAlgorithmProvider(algorithm,0);return ok;
}
static int wsRotationRead(HANDLE file,unsigned char**out,uint32_t*size,BY_HANDLE_FILE_INFORMATION*identity){
 LARGE_INTEGER length;BY_HANDLE_FILE_INFORMATION info;unsigned char*data=NULL;DWORD read=0;
 if(!out||!size||!GetFileInformationByHandle(file,&info)||info.nNumberOfLinks!=1u||
    (info.dwFileAttributes&(FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT))||
    !GetFileSizeEx(file,&length)||length.QuadPart<32||length.QuadPart>64*1024*1024)return 0;
 data=(unsigned char*)malloc((size_t)length.QuadPart);if(!data)return 0;
 if(!ReadFile(file,data,(DWORD)length.QuadPart,&read,NULL)||read!=(DWORD)length.QuadPart){free(data);return 0;}
 *out=data;*size=read;if(identity)*identity=info;return 1;
}
static int wsRotationSame(const WSRotationFile*expected,const BY_HANDLE_FILE_INFORMATION*actual,uint32_t size,const unsigned char*digest){
 return expected->path[0]&&expected->volume==actual->dwVolumeSerialNumber&&expected->high==actual->nFileIndexHigh&&
  expected->low==actual->nFileIndexLow&&expected->size==size&&!memcmp(expected->digest,digest,32);
}
static int wsRotationCheck(const WSRotationFile*expected,int remove){
 if(!expected||!expected->path[0])return 0;
 HANDLE file=CreateFileA(expected->path,GENERIC_READ|(remove?DELETE:0),FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,NULL);
 if(file==INVALID_HANDLE_VALUE)return 0;unsigned char*data=NULL,digest[32];uint32_t size=0;BY_HANDLE_FILE_INFORMATION actual;int ok=0;
 if(wsRotationRead(file,&data,&size,&actual)&&wsRotationDigest(data,size,digest)&&wsRotationSame(expected,&actual,size,digest)){
  if(remove){FILE_DISPOSITION_INFO disposition;disposition.DeleteFile=TRUE;ok=SetFileInformationByHandle(file,FileDispositionInfo,&disposition,sizeof disposition)!=0;}
  else ok=1;
 }free(data);CloseHandle(file);return ok;
}
static void wsRotationCleanup(void){
 for(uint32_t i=0;i<WS_LIMIT;i++)if(wsRotationFiles[i].path[0]){wsRotationCheck(&wsRotationFiles[i],1);memset(&wsRotationFiles[i],0,sizeof wsRotationFiles[i]);}
}
static int wsRotationRoot(const char*root){
 if(!root||strlen(root)<3u||strlen(root)>=MAX_PATH||!((root[1]==':'&&(root[2]=='\\'||root[2]=='/'))||(root[0]=='\\'&&root[1]=='\\')))return 0;
 char scenes[MAX_PATH];if(!wsFullPath(root,"Scenes",scenes))return 0;
 DWORD attrs=GetFileAttributesA(scenes);return attrs!=INVALID_FILE_ATTRIBUTES&&(attrs&FILE_ATTRIBUTE_DIRECTORY)&&!(attrs&FILE_ATTRIBUTE_REPARSE_POINT);
}
static int wsRotationStage(const WSWorldSettings*s,const char*root,char*error,uint32_t cap){
 if(!wsRotationRoot(root)||!wsIslandRotationsValid(s,planned,planCount))return wsRotationMessage(error,cap,"The copied island folder or rotation plan cannot be certified.");
 uint32_t sequence=++wsRotationSequence;
 for(uint32_t i=0;i<planCount;i++){
  const WSPlanIsland*p=&planned[i];if(!p->rotation)continue;const WSTemplate*t=&wsTemplates[p->templateIndex];
  char source[MAX_PATH],relative[128],path[MAX_PATH];unsigned char *data=NULL,digest[32];uint32_t size=0;WSBuffer output={0};
  if(!wsFullPath(root,t->path,source))return wsRotationMessage(error,cap,"A source island path exceeds the supported length.");
  HANDLE input=CreateFileA(source,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,NULL);
  int valid=input!=INVALID_HANDLE_VALUE&&wsRotationRead(input,&data,&size,NULL)&&wsRotationDigest(data,size,digest)&&!memcmp(digest,t->sha256,32);
  if(input!=INVALID_HANDLE_VALUE)CloseHandle(input);
  if(!valid){free(data);return wsRotationMessage(error,cap,"A source island differs from its verified rotation input.");}
  output.capacity=64u*1024u*1024u;output.data=(unsigned char*)malloc(output.capacity);
  valid=output.data&&wsRotationBake(data,size,p->width,p->rotation,&output,error,cap);free(data);
  if(!valid){free(output.data);return 0;}
  int length=snprintf(relative,sizeof relative,"Scenes\\WorldSettingsIsland_%lu_%u_%u.scp",(unsigned long)GetCurrentProcessId(),sequence,i);
  if(length<0||(uint32_t)length>=sizeof relative||!wsFullPath(root,relative,path)){free(output.data);return wsRotationMessage(error,cap,"The rotated island path is too long.");}
  HANDLE file=CreateFileA(path,GENERIC_READ|GENERIC_WRITE|DELETE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL|FILE_FLAG_OPEN_REPARSE_POINT,NULL);
  if(file==INVALID_HANDLE_VALUE){free(output.data);return wsRotationMessage(error,cap,"Cannot create an exclusive rotated island. Existing files were kept.");}
  BY_HANDLE_FILE_INFORMATION info;DWORD written=0;
  valid=GetFileInformationByHandle(file,&info)&&info.nNumberOfLinks==1u&&!(info.dwFileAttributes&(FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT))&&
   WriteFile(file,output.data,output.size,&written,NULL)&&written==output.size&&FlushFileBuffers(file)&&wsRotationDigest(output.data,output.size,digest);
  if(!valid){FILE_DISPOSITION_INFO disposition;disposition.DeleteFile=TRUE;SetFileInformationByHandle(file,FileDispositionInfo,&disposition,sizeof disposition);CloseHandle(file);free(output.data);return wsRotationMessage(error,cap,"The rotated island could not be written completely.");}
  WSRotationFile row={0};memcpy(row.path,path,strlen(path)+1u);row.volume=info.dwVolumeSerialNumber;row.high=info.nFileIndexHigh;row.low=info.nFileIndexLow;
  row.size=output.size;row.index=p->templateIndex;row.rotation=p->rotation;memcpy(row.digest,digest,32);wsRotationFiles[i]=row;
  CloseHandle(file);free(output.data);
  if(!wsRotationCheck(&wsRotationFiles[i],0))return wsRotationMessage(error,cap,"The exclusive rotated island failed its identity and checksum check.");
 }return 1;
}
static int wsRotationSelectedPath(const char*root,const WSPlanIsland*p,char path[MAX_PATH]){
 if(!p||p<planned||p>=planned+planCount||p->templateIndex>=WS_COUNT)return 0;
 if(!p->rotation)return wsFullPath(root,wsTemplates[p->templateIndex].path,path);
 uint32_t i=(uint32_t)(p-planned);const WSRotationFile*t=&wsRotationFiles[i];
 if(t->index!=p->templateIndex||t->rotation!=p->rotation||!wsRotationCheck(t,0))return 0;
 memcpy(path,t->path,strlen(t->path)+1u);return 1;
}
