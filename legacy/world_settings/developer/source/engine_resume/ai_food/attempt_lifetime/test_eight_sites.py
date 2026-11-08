"""Compiled grouped commit using all eight current hook descriptors.

Protection/cache calls are substituted. Descriptor-driven grouping, writes,
preimage refusal and rollback execute the real installer on private buffers.
No native module, game process or game-copy file is changed.
"""
from pathlib import Path
import ctypes as C,hashlib,json,os,subprocess
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[2];DEV=WORK/'runtime_dev3';LOADER=WORK/'engine_resume/ai_loader'
out=HERE/'_build';out.mkdir(exist_ok=True);(out/'tmp').mkdir(exist_ok=True)
source=(LOADER/'page_fixture.c').read_text('utf-8').replace('protections[2]','protections[8]').replace('delta>=8192','delta>=32768')
source='#define WS_RUNTIME_BLOBS_HEADER "'+(DEV/'runtime_test_blobs.h').as_posix()+'"\n'+source
source+='''
__declspec(dllexport) int WorldSettingsEightSites(int mode){
 int answer=0;WSPatch patches[WS_MAX_HOOKS]={0};WSPage pages[WS_MAX_HOOKS]={0};uint32_t pageCount=0,count=0,keyCount=0;
 uint64_t keys[WS_MAX_HOOKS]={0};int factory=-1,post=-1;
 fixtureMemory=VirtualAlloc(NULL,32768,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
 if(!fixtureMemory)return __LINE__;
 calls=0;failAt=0;failAlso=0;flushCalls=0;failFlush=0;
 for(int i=0;i<8;i++)protections[i]=PAGE_EXECUTE_READ;
 for(uint32_t i=0;i<WS_BLOB_COUNT;i++){
  const WSBlob*b=&wsBlobs[i];uint32_t module=!wcscmp(b->module,L"AnnoFrame.dll")?1:!wcscmp(b->module,L"AnnoScene.dll")?2:!wcscmp(b->module,L"AnnoWelt.dll")?3:0;
  REQUIRE(module);
  for(uint32_t j=0;j<b->hookCount;j++){
   const WSHook*h=&b->hooks[j];REQUIRE(count<WS_MAX_HOOKS&&h->length<=WS_MAX_PATCH);
   uint64_t key=((uint64_t)module<<32)|(h->rva>>12);uint32_t p=0;
   while(p<keyCount&&keys[p]!=key)p++;if(p==keyCount)keys[keyCount++]=key;
   patches[count].address=fixtureMemory+p*4096+(h->rva&4095);patches[count].length=h->length;
   memcpy(patches[count].before,h->before,h->length);memset(patches[count].after,0x90,h->length);patches[count].after[0]=(unsigned char)(h->call?0xe8:0xe9);
   memcpy(patches[count].address,h->before,h->length);
   if(module==1&&h->rva==0x55c54)factory=(int)count;if(module==1&&h->rva==0x55f2e)post=(int)count;
   count++;
  }
 }
 REQUIRE(count==8&&keyCount==7&&factory>=0&&post>=0);
 REQUIRE(wsGroupPages(patches,count,pages,&pageCount,4096)&&pageCount==7&&patches[factory].page==patches[post].page);
 if(mode>=1&&mode<=14)failAt=mode;
 if(mode>=15&&mode<=22)failFlush=mode-14;
 if(mode==23)patches[6].address[0]^=0xff;
 if(mode==24){failAt=8;failAlso=9;}
 if(mode==25){failFlush=1;failAt=8;}
 int result=wsApplyPatches(patches,count,pages,pageCount);
 if(mode==0){REQUIRE(result==1);for(uint32_t i=0;i<count;i++)REQUIRE(!memcmp(patches[i].address,patches[i].after,patches[i].length));}
 else if(mode==23){REQUIRE(result==0&&calls==0&&flushCalls==0);}
 else if(mode>=24)REQUIRE(result==-1);
 else{REQUIRE(result==0);for(uint32_t i=0;i<count;i++)REQUIRE(!memcmp(patches[i].address,patches[i].before,patches[i].length));}
 if(mode<24)for(uint32_t i=0;i<keyCount;i++)REQUIRE(protections[i]==PAGE_EXECUTE_READ);
 done:VirtualFree(fixtureMemory,0,MEM_RELEASE);fixtureMemory=NULL;return answer;
}
'''
(out/'eight_sites_fixture.c').write_text(source,'utf-8')
env=dict(os.environ,ZIG_GLOBAL_CACHE_DIR=str(out/'global-cache'),ZIG_LOCAL_CACHE_DIR=str(out/'local-cache'),TEMP=str(out/'tmp'),TMP=str(out/'tmp'))
paths=[DEV/'runtime_test_blobs.h',LOADER/'install_test_hooks.c'];hashes={str(p.relative_to(WORK)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
subprocess.run([str(WORK/'_tools/ziglang/zig.exe'),'cc','-shared','-O2','-Wall','-Wextra','-Werror','-I',str(LOADER),str(out/'eight_sites_fixture.c'),'-o',str(out/'EightSitesFixture.dll'),'-lbcrypt'],check=True,env=env)
lib=C.CDLL(str(out/'EightSitesFixture.dll'));test=lib.WorldSettingsEightSites;test.argtypes=[C.c_int];rows=[]
for mode in range(26):
 result=test(mode);assert result==0,(mode,'C assertion line',result);rows.append(dict(mode=mode,passed=True))
assert all(hashlib.sha256((WORK/p).read_bytes()).hexdigest()==h for p,h in hashes.items())
report=dict(scope=__doc__,actual_game_runs=0,hook_count=8,protection_pages=7,source_sha256=hashes,cases=rows,
 boundary='VirtualProtect and FlushInstructionCache success/failure substituted; actual installer grouping/transaction/rollback and current eight descriptors execute compiled')
(HERE/'eight_site_results.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
print(json.dumps(dict(hook_count=8,protection_pages=7,transaction_cases=len(rows),actual_game_runs=0)))
