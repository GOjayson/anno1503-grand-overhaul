"""Explicit temporary activation for the UNFINISHED Food + World Settings build.

Launch the game normally through Ubisoft Connect and leave it in the idle menu.
Default invocation is read-only. --install loads only this package's copied DLL,
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
from preflight import verify
from pe_exports import exports
from module_checks import verify_modules,profile_status
from preview_snapshot import SNAPSHOT_SIZE,decode as decode_preview_snapshot

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
PACKAGE = HERE.parent
DLL = PACKAGE / 'native/AnnoWorldSettings.dll'
ENGINE_PLAN = PACKAGE / 'developer/huge_world/runtime_engine_edits.json'
SESSION = PACKAGE / 'activation_session.json'
REQUIRED = {'WorldSettingsEnginePatchStatus','WorldSettingsConfigureDevelopmentRoot','WorldSettingsCopyConfigurationError',
            'WorldSettingsInstallTestHooks','WorldSettingsCopyTestHooksError','WorldSettingsCopyFactoryError',
            'WorldSettingsCopyAILoaderError','WorldSettingsCopyAIProfileError','WorldSettingsAIProfileStatus',
            'WorldSettingsBeginNativeWorldStart','WorldSettingsEndNativeWorldStart','WorldSettingsBindAIProfileWorld',
            'WorldSettingsBindAIDiplomacy','WorldSettingsStagePreviewScene',
            'WorldSettingsPreviewSnapshotSize','WorldSettingsCopyPreviewSnapshot'}
HOOK_SITES = {'AnnoFrame.dll':[(0x43e44,6),(0x44bb0,9),(0x55c54,6),(0x55f2e,5),(0x5746b,5)],
              'AnnoScene.dll':[(0xe3d0,8),(0xc71d,5)],
              'AnnoWelt.dll':[(0xc714d,6),(0xdf460,6)]}
CENTRAL_WAR_PREIMAGE = bytes.fromhex('488bc4895010')


def central_hook_state(data):
    """Classify the exact six-byte central site; jump shape is not a code audit."""
    if data == CENTRAL_WAR_PREIMAGE:
        return 'original'
    if len(data) == 6 and data[0] == 0xe9 and data[5] == 0x90:
        return 'guard-jump'
    return 'changed'

def engine_state(session,mods,plan):
    """Read every World and Frame instruction in the atomic engine profile."""
    original=patched=True
    for edit in plan['edits']:
        before,after=bytes.fromhex(edit['before']),bytes.fromhex(edit['after'])
        declared=edit.get('module',plan.get('module',''))
        if not isinstance(declared,str):
            raise RuntimeError('Invalid bounded engine edit module.')
        name=declared.lower()
        module=mods.get(name)
        rva=edit['rva']
        if (name not in ('annowelt.dll','annoframe.dll') or not module
                or type(rva)is not int or rva<0 or rva+len(before)>module['size']
                or not before or len(before)!=len(after) or len(before)>32):
            raise RuntimeError('Invalid bounded engine edit plan.')
        value=session.read(module['base']+rva,len(before))
        original=original and value==before;patched=patched and value==after
    return 'original' if original else ('expanded' if patched else 'changed')


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
        m=Module();m.size=C.sizeof(m);ok=module_first(h,C.byref(m));items={};all_items=[]
        while ok:
            item={'name':m.name,'path':m.path,'base':m.base,'size':m.imageSize}
            items[m.name.lower()]=item;all_items.append(item)
            ok=module_next(h,C.byref(m))
        if C.get_last_error()!=18:raise OSError(C.get_last_error(),'Incomplete module snapshot')
        items['__all__']=all_items
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
        # Retain caller buffers for every interruption/error until a completed
        # thread is proven; even Ctrl+C must not free an active thread argument.
        self.incomplete_thread=True
        t=check(thread(self.handle,None,0,address,arg,0,None),'Start bounded test export')
        try:
            status=wait(t,60000)
            if status!=0:
                self.incomplete_thread=True
                raise RuntimeError('Test export did not finish in 60 seconds. Keep its buffers and DLL resident; close the test game before retrying.')
            self.incomplete_thread=False
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
    return exports(DLL.read_bytes(), REQUIRED)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--install',action='store_true')
    ap.add_argument('--diagnostics',action='store_true')
    ap.add_argument('--game-dir',type=Path,help='Explicit marked copy when more than one matching copy exists')
    args=ap.parse_args()
    if C.sizeof(PTR)!=8:raise RuntimeError('Use 64-bit Python.')
    inputs=verify(args.game_dir)
    plan=json.loads(ENGINE_PLAN.read_bytes())
    specification=json.loads((PACKAGE/'world_patch.json').read_bytes())
    if (sha(ENGINE_PLAN)!=specification.get('expanded_engine_plan_sha256')
            or plan.get('engine_instruction_count')!=len(plan.get('edits',[]))
            or plan['engine_instruction_count']!=specification.get('expanded_engine_patch_count')):
        raise RuntimeError('Expanded engine activation plan differs from the package specification.')
    ROOT=inputs['source'];COPY=inputs['copy'];EXE_SHA=inputs['exe_sha256']
    ids=all_processes()
    if len(ids)!=1:raise RuntimeError(f'Exactly one normally launched Anno process is required; found {len(ids)}.')
    s=Session(ids[0],args.install or args.diagnostics)
    try:
        b=C.create_unicode_buffer(260);n=W.DWORD(len(b))
        check(query_path(s.handle,0,b,C.byref(n)),'Verify executable path')
        if not same(b.value,ROOT/'Anno1503.exe') or sha(b.value)!=EXE_SHA:raise RuntimeError('Unexpected game executable; no changes made.')
        if sha(DLL)!=inputs['runtime_sha256']:raise RuntimeError('DLL differs from the package fingerprint.')
        mods=modules(s.pid)
        verify_modules(mods,inputs,same,sha)
        rvas=exported_rvas()
        result={'pid':s.pid,'process_creation_time':creation_time(s.handle),'executable_sha256':EXE_SHA,
                'runtime_sha256':inputs['runtime_sha256'],'world_spec_sha256':inputs['spec_sha256'],
                'copy_root':str(COPY),'installed_files_modified':False,'engine_plan_sha256':sha(ENGINE_PLAN)}
        already=mods.get(DLL.name.lower())
        if len([m for m in mods['__all__'] if m['name'].lower()==DLL.name.lower()])>1:
            raise RuntimeError('Multiple World Settings DLLs are loaded; restart the game.')
        if already and not same(already['path'],DLL):raise RuntimeError('Another World Settings DLL is already loaded; restart the game.')
        if args.install:
            if already:raise RuntimeError('A World Settings test DLL is already loaded. Close and relaunch the game before installing another test build.')
            if central_hook_state(s.read(mods['annowelt.dll']['base']+0xdf460,6))!='original':
                raise RuntimeError('The central native war-declaration preimage differs; no activation was attempted.')
            if engine_state(s,mods,plan)!='original':
                raise RuntimeError('An inspected engine preimage differs; no activation was attempted.')
            if not already:
                p=s.buffer((str(DLL)+'\0').encode('utf-16-le'))
                try:s.remote(local_system_export('LoadLibraryW',mods),p)
                finally:s.release(p)
                mods=modules(s.pid);already=mods.get(DLL.name.lower())
                if not already or not same(already['path'],DLL):raise RuntimeError('Windows did not load the copied test DLL.')
            base=already['base']
            result['runtime_base']=base
            SESSION.write_text(json.dumps(result,indent=2))
            p=s.buffer((str(COPY)+'\0').encode('utf-16-le'))
            try:configured=s.remote(base+rvas['WorldSettingsConfigureDevelopmentRoot'],p)
            finally:s.release(p)
            if configured!=1:raise RuntimeError(s.text(base+rvas['WorldSettingsCopyConfigurationError']))
            installed=s.remote(base+rvas['WorldSettingsInstallTestHooks'])
            if installed!=1:raise RuntimeError(s.text(base+rvas['WorldSettingsCopyTestHooksError']))
            result.update(hooks_installed=True,copy_root=str(COPY),removal='Close the test game process.')
            SESSION.write_text(json.dumps(result,indent=2))
        elif args.diagnostics:
            if not already:raise RuntimeError('No test DLL is loaded.')
            base=already['base']
            saved=json.loads(SESSION.read_text())
            if any(saved.get(k)!=v for k,v in [('pid',s.pid),('process_creation_time',result['process_creation_time']),
                    ('runtime_sha256',inputs['runtime_sha256']),('runtime_base',base),
                    ('world_spec_sha256',inputs['spec_sha256']),('copy_root',str(COPY)),
                    ('engine_plan_sha256',sha(ENGINE_PLAN))]):
                raise RuntimeError('Loaded runtime does not match the saved test session. No export was called; restart the game.')
            result['factory_error']=s.text(base+rvas['WorldSettingsCopyFactoryError'])
            result['hook_error']=s.text(base+rvas['WorldSettingsCopyTestHooksError'])
            result['ai_loader_error']=s.text(base+rvas['WorldSettingsCopyAILoaderError'])
            result['ai_profile_error']=s.text(base+rvas['WorldSettingsCopyAIProfileError'])
            result.update(profile_status(s.remote(base+rvas['WorldSettingsAIProfileStatus'])))
            if s.remote(base+rvas['WorldSettingsPreviewSnapshotSize'])!=SNAPSHOT_SIZE:
                raise RuntimeError('The loaded preview snapshot ABI differs from this package.')
            p=s.buffer(bytes(SNAPSHOT_SIZE))
            try:
                if s.remote(base+rvas['WorldSettingsCopyPreviewSnapshot'],p)!=SNAPSHOT_SIZE:
                    raise RuntimeError('The preview is changing. Leave World Settings idle and retry diagnostics.')
                result['preview']=decode_preview_snapshot(s.read(p,SNAPSHOT_SIZE))
            finally:s.release(p)
        else:result['read_only_preflight']=True
        result['hook_bytes']={name:{hex(rva):s.read(mods[name.lower()]['base']+rva,n).hex() for rva,n in sites}
                              for name,sites in HOOK_SITES.items()}
        result['hook_site_count']=sum(len(sites) for sites in HOOK_SITES.values())
        result['central_war_site_state']=central_hook_state(bytes.fromhex(result['hook_bytes']['AnnoWelt.dll']['0xdf460']))
        result['engine_state']=engine_state(s,mods,plan)
        result['engine_patch_count']=plan['engine_instruction_count']
        if args.install or args.diagnostics:
            result['engine_patch_status']=s.remote(base+rvas['WorldSettingsEnginePatchStatus'])
            if result['engine_state']!='expanded' or result['engine_patch_status']!=plan['engine_instruction_count']:
                raise RuntimeError('The complete expanded engine transaction is not active. Close the test game before retrying.')
            result['all_engine_instruction_bytes_verified']=True
        if args.install and result['central_war_site_state']!='guard-jump':
            raise RuntimeError('Activation returned success without the central war-declaration hook; close the test game before retrying.')
        print(json.dumps(result,indent=2))
    finally:close(s.handle)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('ERROR: '+str(exc),file=sys.stderr)
        raise SystemExit(1)
