"""Explicit, temporary Anno 1503 test loader. No installed files are patched.

Launch the game normally through Ubisoft Connect and leave it in the idle menu.
Default invocation is read-only. --install loads only this build's copied DLL,
configures a marked independent game copy, then invokes its transactional hook
installer. Closing the game removes all hooks; never unload the DLL in-process.
No command-line/session/authentication data are read or altered.
"""
from pathlib import Path
import argparse
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import os
import sys
import pefile

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
ROOT = WORK.parent
COPY = WORK / 'game_copy'
DLL = HERE / 'AnnoWorldSettings.dll'
EXE_SHA = '1a4bebe7c676a5904834b9e67e936187729dc67c013a4fb4fd64986a3cb8e95a'
MODULE_SHA = {'AnnoFrame.dll': '046b5ad6f351dfe867ed38ce29fb50a594485b43a32ee90adadc48e850466baf',
              'AnnoScene.dll': 'f7d0685cf6156ff25c518f2f558863b351d7738280467e48dd585a1fefa9537a',
              'AnnoWelt.dll': 'ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9',
              'AnnoGame.dll': 'e6f01d19e8e16e6716c0a6c7d3ba00273c9df493e051b8ba62865ee4b53dfdea'}
K = C.WinDLL('kernel32', use_last_error=True)
SIZE = C.c_size_t
PTR = C.c_void_p
INVALID = PTR(-1).value

class Process(C.Structure):
    _fields_ = [('size',W.DWORD),('usage',W.DWORD),('pid',W.DWORD),('heap',SIZE),
                ('module',W.DWORD),('threads',W.DWORD),('parent',W.DWORD),
                ('priority',W.LONG),('flags',W.DWORD),('exe',W.WCHAR*260)]

class Module(C.Structure):
    _fields_ = [('size',W.DWORD),('id',W.DWORD),('pid',W.DWORD),('globalUsage',W.DWORD),
                ('processUsage',W.DWORD),('base',PTR),('imageSize',W.DWORD),('handle',PTR),
                ('name',W.WCHAR*256),('path',W.WCHAR*260)]

def bind(name, args, result):
    fn = getattr(K, name); fn.argtypes=args; fn.restype=result; return fn

snapshot=bind('CreateToolhelp32Snapshot',[W.DWORD,W.DWORD],W.HANDLE)
close=bind('CloseHandle',[W.HANDLE],W.BOOL)
process_first=bind('Process32FirstW',[W.HANDLE,C.POINTER(Process)],W.BOOL)
process_next=bind('Process32NextW',[W.HANDLE,C.POINTER(Process)],W.BOOL)
module_first=bind('Module32FirstW',[W.HANDLE,C.POINTER(Module)],W.BOOL)
module_next=bind('Module32NextW',[W.HANDLE,C.POINTER(Module)],W.BOOL)
open_process=bind('OpenProcess',[W.DWORD,W.BOOL,W.DWORD],W.HANDLE)
query_path=bind('QueryFullProcessImageNameW',[W.HANDLE,W.DWORD,W.LPWSTR,C.POINTER(W.DWORD)],W.BOOL)
allocate=bind('VirtualAllocEx',[W.HANDLE,PTR,SIZE,W.DWORD,W.DWORD],PTR)
free=bind('VirtualFreeEx',[W.HANDLE,PTR,SIZE,W.DWORD],W.BOOL)
write=bind('WriteProcessMemory',[W.HANDLE,PTR,PTR,SIZE,C.POINTER(SIZE)],W.BOOL)
read=bind('ReadProcessMemory',[W.HANDLE,PTR,PTR,SIZE,C.POINTER(SIZE)],W.BOOL)
thread=bind('CreateRemoteThread',[W.HANDLE,PTR,SIZE,PTR,PTR,W.DWORD,C.POINTER(W.DWORD)],W.HANDLE)
wait=bind('WaitForSingleObject',[W.HANDLE,W.DWORD],W.DWORD)
thread_code=bind('GetExitCodeThread',[W.HANDLE,C.POINTER(W.DWORD)],W.BOOL)
process_times=bind('GetProcessTimes',[W.HANDLE,C.POINTER(W.FILETIME),C.POINTER(W.FILETIME),C.POINTER(W.FILETIME),C.POINTER(W.FILETIME)],W.BOOL)
get_module=bind('GetModuleHandleW',[W.LPCWSTR],W.HMODULE)
get_proc=bind('GetProcAddress',[W.HMODULE,C.c_char_p],PTR)
module_at=bind('GetModuleHandleExW',[W.DWORD,PTR,C.POINTER(W.HMODULE)],W.BOOL)
module_path=bind('GetModuleFileNameW',[W.HMODULE,W.LPWSTR,W.DWORD],W.DWORD)

def check(value, label):
    if not value: raise OSError(C.get_last_error(),label)
    return value

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def same(a,b): return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))

def creation_time(handle):
    times=[W.FILETIME() for _ in range(4)]
    check(process_times(handle,*[C.byref(t) for t in times]),'Read process creation time')
    return times[0].dwLowDateTime+(times[0].dwHighDateTime<<32)

def all_processes():
    h=snapshot(2,0)
    if h==INVALID:raise OSError(C.get_last_error(),'Process snapshot')
    try:
        p=Process();p.size=C.sizeof(p);ok=process_first(h,C.byref(p));items=[]
        while ok:
            if p.exe.lower()=='anno1503.exe':items.append(p.pid)
            ok=process_next(h,C.byref(p))
        if C.get_last_error()!=18:raise OSError(C.get_last_error(),'Incomplete process snapshot')
        return items
    finally:close(h)

def modules(pid):
    h=snapshot(0x18,pid)
    if h==INVALID:raise OSError(C.get_last_error(),'Module snapshot')
    try:
        m=Module();m.size=C.sizeof(m);ok=module_first(h,C.byref(m));items={}
        while ok:
            items[m.name.lower()]={'name':m.name,'path':m.path,'base':m.base,'size':m.imageSize}
            ok=module_next(h,C.byref(m))
        if C.get_last_error()!=18:raise OSError(C.get_last_error(),'Incomplete module snapshot')
        return items
    finally:close(h)

class Session:
    def __init__(self,pid,mutate=False):
        self.pid=pid
        self.handle=check(open_process(0x1000|0x10|(0x2|0x8|0x20 if mutate else 0),False,pid),'Open Anno process')
        self.incomplete_thread=False
    def read(self,address,size):
        b=C.create_string_buffer(size);n=SIZE()
        check(read(self.handle,address,b,size,C.byref(n)) and n.value==size,'Read test memory')
        return b.raw
    def remote(self,address,arg=0):
        t=check(thread(self.handle,None,0,address,arg,0,None),'Start bounded test export')
        try:
            status=wait(t,60000)
            if status!=0:
                self.incomplete_thread=True
                raise RuntimeError('Test export did not finish in 60 seconds. Keep its buffers and DLL resident; close the test game before retrying.')
            code=W.DWORD();check(thread_code(t,C.byref(code)),'Read test export result')
            return code.value
        finally:close(t)
    def buffer(self,data):
        p=check(allocate(self.handle,None,len(data),0x3000,4),'Allocate test argument')
        b=C.create_string_buffer(data);n=SIZE()
        try:check(write(self.handle,p,b,len(data),C.byref(n)) and n.value==len(data),'Copy test argument')
        except BaseException:
            free(self.handle,p,0,0x8000)
            raise
        return p
    def release(self,p):
        if not self.incomplete_thread:check(free(self.handle,p,0,0x8000),'Release test argument')
    def text(self,address):
        p=self.buffer(bytes(512))
        try:self.remote(address,p);return self.read(p,512).split(b'\0')[0].decode('ascii','replace')
        finally:self.release(p)

def local_system_export(name,remote):
    fn=check(get_proc(get_module('kernel32.dll'),name.encode()),'Resolve LoadLibraryW')
    owner=W.HMODULE();check(module_at(6,fn,C.byref(owner)),'Locate Windows export owner')
    b=C.create_unicode_buffer(260);check(module_path(owner,b,len(b)),'Read Windows module path')
    item=remote.get(Path(b.value).name.lower())
    if not item or not same(item['path'],b.value):raise RuntimeError('Windows module paths differ; no remote call made.')
    return item['base']+fn-owner.value

def exported_rvas():
    p=pefile.PE(str(DLL))
    if p.FILE_HEADER.Machine!=0x8664 or p.OPTIONAL_HEADER.Magic!=0x20b:raise RuntimeError('Test DLL is not AMD64 PE32+.')
    values={e.name.decode():e.address for e in p.DIRECTORY_ENTRY_EXPORT.symbols if e.name and not e.forwarder}
    required={'WorldSettingsConfigureDevelopmentRoot','WorldSettingsCopyConfigurationError',
              'WorldSettingsInstallTestHooks','WorldSettingsCopyTestHooksError','WorldSettingsCopyFactoryError'}
    if not required<=values.keys():raise RuntimeError('The test DLL is missing required exports.')
    return values

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--install',action='store_true')
    ap.add_argument('--diagnostics',action='store_true')
    args=ap.parse_args()
    if C.sizeof(PTR)!=8:raise RuntimeError('Use 64-bit Python.')
    ids=all_processes()
    if len(ids)!=1:raise RuntimeError(f'Exactly one normally launched Anno process is required; found {len(ids)}.')
    s=Session(ids[0],args.install or args.diagnostics)
    try:
        b=C.create_unicode_buffer(260);n=W.DWORD(len(b))
        check(query_path(s.handle,0,b,C.byref(n)),'Verify executable path')
        if not same(b.value,ROOT/'Anno1503.exe') or sha(b.value)!=EXE_SHA:raise RuntimeError('Unexpected game executable; no changes made.')
        marker=json.loads((COPY/'.anno1503-worldsettings-test-copy.json').read_text())
        if not marker.get('development_copy') or not same(marker['copy_root'],COPY) or not same(marker['source_root'],ROOT) or marker['source_exe_sha256']!=EXE_SHA:raise RuntimeError('Independent copy marker is invalid.')
        built=json.loads((HERE/'build_result.json').read_text())
        if sha(DLL)!=built['sha256']:raise RuntimeError('DLL differs from the recorded build.')
        for path,digest in built['source_sha256'].items():
            if sha(WORK/path)!=digest and not args.diagnostics:raise RuntimeError(f'Source changed after build: {path}')
        mods=modules(s.pid)
        for name,digest in MODULE_SHA.items():
            m=mods.get(name.lower())
            if not m or not same(m['path'],ROOT/name) or sha(m['path'])!=digest:raise RuntimeError(f'Unexpected loaded {name}; no changes made.')
        rvas=exported_rvas()
        result={'pid':s.pid,'process_creation_time':creation_time(s.handle),'executable_sha256':EXE_SHA,'runtime_sha256':built['sha256'],'installed_files_modified':False}
        already=mods.get(DLL.name.lower())
        if already and not same(already['path'],DLL):raise RuntimeError('Another World Settings DLL is already loaded; restart the game.')
        if args.install:
            if already:raise RuntimeError('A World Settings test DLL is already loaded. Close and relaunch the game before installing another test build.')
            if not already:
                p=s.buffer((str(DLL)+'\0').encode('utf-16-le'))
                try:s.remote(local_system_export('LoadLibraryW',mods),p)
                finally:s.release(p)
                mods=modules(s.pid);already=mods.get(DLL.name.lower())
                if not already or not same(already['path'],DLL):raise RuntimeError('Windows did not load the copied test DLL.')
            base=already['base']
            result['runtime_base']=base
            (HERE/'runtime_test_session.json').write_text(json.dumps(result,indent=2))
            p=s.buffer((str(COPY)+'\0').encode('utf-16-le'))
            try:configured=s.remote(base+rvas['WorldSettingsConfigureDevelopmentRoot'],p)
            finally:s.release(p)
            if configured!=1:raise RuntimeError(s.text(base+rvas['WorldSettingsCopyConfigurationError']))
            installed=s.remote(base+rvas['WorldSettingsInstallTestHooks'])
            if installed!=1:raise RuntimeError(s.text(base+rvas['WorldSettingsCopyTestHooksError']))
            result.update(hooks_installed=True,copy_root=str(COPY),removal='Close the test game process.')
            (HERE/'runtime_test_session.json').write_text(json.dumps(result,indent=2))
        elif args.diagnostics:
            if not already:raise RuntimeError('No test DLL is loaded.')
            base=already['base']
            saved=json.loads((HERE/'runtime_test_session.json').read_text())
            if any(saved.get(k)!=v for k,v in [('pid',s.pid),('process_creation_time',result['process_creation_time']),('runtime_sha256',built['sha256']),('runtime_base',base)]):
                raise RuntimeError('Loaded runtime does not match the saved test session. No export was called; restart the game.')
            result['factory_error']=s.text(base+rvas['WorldSettingsCopyFactoryError'])
            result['hook_error']=s.text(base+rvas['WorldSettingsCopyTestHooksError'])
        else:result['read_only_preflight']=True
        result['hook_bytes']={name:{hex(rva):s.read(mods[name.lower()]['base']+rva,n).hex() for rva,n in sites}
                              for name,sites in {'AnnoFrame.dll':[(0x44bb0,9),(0x55c54,6)],'AnnoScene.dll':[(0xe3d0,8),(0xc71d,5)]}.items()}
        print(json.dumps(result,indent=2))
    finally:close(s.handle)

if __name__=='__main__':main()
