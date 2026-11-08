/* Current native selection is a relative resource path.
 * The native MD5 global can remain all-FF offline, so verify the selected
 * original stock file with SHA256 under the actual executable directory.
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <bcrypt.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <wchar.h>
#include "stock_endless_paths.h"

static unsigned char lowerAscii(unsigned char c) {
    return c>='A'&&c<='Z'?(unsigned char)(c+'a'-'A'):c;
}

static int sameAscii(const char *a,const char *b) {
    for(size_t i=0;;i++){
        if(lowerAscii((unsigned char)a[i])!=lowerAscii((unsigned char)b[i]))return 0;
        if(!a[i])return 1;
    }
}

static int token(const char *at,size_t length,const char *wanted) {
    size_t n=strlen(wanted);
    if(length!=n)return 0;
    for(size_t i=0;i<n;i++)if(lowerAscii((unsigned char)at[i])!=lowerAscii((unsigned char)wanted[i]))return 0;
    return 1;
}

static int normalize(const char *filename,uint32_t capacity,char out[260]) {
    if(!filename||!capacity||capacity>260)return -1;
    uint32_t n=0;
    while(n<capacity&&filename[n]){
        unsigned char c=(unsigned char)filename[n];
        if(c<32||c==':'||c=='*'||c=='?'||c=='"'||c=='<'||c=='>'||c=='|')return -1;
        out[n]=c=='/'?'\\':(char)c;n++;
    }
    if(n==capacity)return -1;
    out[n]=0;
    if(!n)return 0;
    if(out[0]=='\\')return -1;
    size_t begin=0;
    for(size_t at=0;at<=n;at++)if(out[at]=='\\'||!out[at]){
        size_t length=at-begin;
        if(!length||token(out+begin,length,".")||token(out+begin,length,".."))return -1;
        if(out[at-1]==' '||out[at-1]=='.')return -1;
        begin=at+1;
    }
    return 1;
}

static int endlessPath(const char *filename) {
    const char *parts[6];size_t lengths[6],count=0,begin=0;
    for(size_t at=0;;at++)if(filename[at]=='\\'||!filename[at]){
        if(count>=6)return 0;
        parts[count]=filename+begin;lengths[count++]=at-begin;begin=at+1;
        if(!filename[at])break;
    }
    size_t category;
    if(count==3&&token(parts[0],lengths[0],"Scenes"))category=1;
    else if(count==5&&token(parts[0],lengths[0],"Languages")&&lengths[1]
            &&token(parts[2],lengths[2],"Scenes"))category=3;
    else return 0;
    return token(parts[category],lengths[category],"0010SingleEndlos")
        ||token(parts[category],lengths[category],"0011SingleEndlosAddon");
}

static int hashFile(const wchar_t *path,const unsigned char expected[32]) {
    HANDLE file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE)return 0;
    BCRYPT_ALG_HANDLE algorithm=NULL;BCRYPT_HASH_HANDLE hash=NULL;
    unsigned char bytes[32768],digest[32];DWORD got=0;int okay=0;
    if(BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,NULL,0)<0
        ||BCryptCreateHash(algorithm,&hash,NULL,0,NULL,0,0)<0)goto done;
    do{
        if(!ReadFile(file,bytes,sizeof bytes,&got,NULL))goto done;
        if(got&&BCryptHashData(hash,bytes,got,0)<0)goto done;
    }while(got);
    if(BCryptFinishHash(hash,digest,sizeof digest,0)<0)goto done;
    okay=memcmp(digest,expected,32)==0;
    done:if(hash)BCryptDestroyHash(hash);if(algorithm)BCryptCloseAlgorithmProvider(algorithm,0);CloseHandle(file);return okay;
}

static int classifyAtRoot(const char *filename,uint32_t capacity,const wchar_t *root) {
    char relative[260];int normalized=normalize(filename,capacity,relative);
    if(normalized<=0)return normalized;
    if(!endlessPath(relative))return 0;
    const WSStockEndlessPath *selected=NULL;
    for(size_t i=0;i<sizeof wsStockEndlessPaths/sizeof wsStockEndlessPaths[0];i++)
        if(sameAscii(relative,wsStockEndlessPaths[i].path)){selected=&wsStockEndlessPaths[i];break;}
    if(!selected||!root)return -1;
    size_t n=0;while(n<MAX_PATH&&root[n])n++;
    if(n<3||n>=MAX_PATH)return -1;
    int drive=((root[0]>=L'A'&&root[0]<=L'Z')||(root[0]>=L'a'&&root[0]<=L'z'))&&root[1]==L':'&&root[2]==L'\\';
    int unc=root[0]==L'\\'&&root[1]==L'\\'&&root[2]!=L'?'&&root[2]!=L'.';
    if(!drive&&!unc)return -1;
    while(n>3&&root[n-1]==L'\\')n--;
    size_t tail=strlen(selected->path);
    if(n+1+tail>=MAX_PATH)return -1;
    wchar_t path[MAX_PATH];memcpy(path,root,n*sizeof(wchar_t));path[n++]=L'\\';
    for(size_t i=0;i<=tail;i++)path[n+i]=(wchar_t)(unsigned char)selected->path[i];
    return hashFile(path,selected->sha256)?1:-1;
}

/* Preserve the existing internal ABI; nativeDigest is deliberately unused. */
__declspec(dllexport) int WorldSettingsClassifyDirectSelection(
        const char *filename,uint32_t capacity,const unsigned char *nativeDigest) {
    (void)nativeDigest;
    wchar_t exe[MAX_PATH];DWORD n=GetModuleFileNameW(NULL,exe,MAX_PATH);
    if(!n||n>=MAX_PATH)return -1;
    wchar_t *slash=wcsrchr(exe,L'\\');if(!slash)return -1;
    if(slash==exe+2&&exe[1]==L':')slash[1]=0;else *slash=0;
    return classifyAtRoot(filename,capacity,exe);
}

#ifdef WS_ROUTE_TESTING
/* Test-only boundary; no root override is exported by the game runtime. */
__declspec(dllexport) int WorldSettingsClassifyDirectSelectionAtRoot(
        const char *filename,uint32_t capacity,const wchar_t *root) {
    return classifyAtRoot(filename,capacity,root);
}
#endif
