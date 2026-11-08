#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
__declspec(dllexport) void WSUnwindFixture(uintptr_t base,uint32_t begin,uint32_t end,uint32_t unwind,const uint64_t *input,uint64_t *output){
 CONTEXT c={0};RUNTIME_FUNCTION f={begin,end,unwind};void *handler=NULL;DWORD64 frame=0;
 c.ContextFlags=CONTEXT_ALL;c.Rbx=input[0];c.Rbp=input[1];c.Rsi=input[2];c.Rdi=input[3];
 c.R12=input[4];c.R13=input[5];c.R14=input[6];c.R15=input[7];c.Rsp=input[8];c.Rip=input[9];
 c.Xmm6.Low=input[10];c.Xmm6.High=(LONGLONG)input[11];
 RtlVirtualUnwind(UNW_FLAG_NHANDLER,(DWORD64)base,c.Rip,&f,&c,&handler,&frame,NULL);
 output[0]=c.Rbx;output[1]=c.Rbp;output[2]=c.Rsi;output[3]=c.Rdi;output[4]=c.R12;output[5]=c.R13;output[6]=c.R14;output[7]=c.R15;
 output[8]=c.Rsp;output[9]=c.Rip;output[10]=c.Xmm6.Low;output[11]=(uint64_t)c.Xmm6.High;
}
