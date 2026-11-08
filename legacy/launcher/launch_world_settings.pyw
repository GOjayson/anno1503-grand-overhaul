"""Start the installed Anno through Ubisoft and activate at its verified menu."""
from pathlib import Path
import ctypes as C
import datetime
import hashlib
import json
import os
import queue
import subprocess
import sys
import threading
import time
import uuid

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from launcher_core import LaunchPolicy, LaunchError


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


class Backend:
    def __init__(self, event):
        if os.name != 'nt' or C.sizeof(C.c_void_p) != 8:
            raise LaunchError('This launcher needs 64-bit Python on Windows.')
        self.event = event
        self.config = json.loads((HERE/'launcher_config.json').read_bytes())
        self.package = (HERE/self.config['package_relative']).resolve(strict=True)
        if sha(self.package/'world_patch.json') != self.config['package_spec_sha256']:
            raise LaunchError('This shortcut needs the tested 0.11.0-dev.1 package. Restore its files before trying again.')
        if sha(self.package/'native/AnnoWorldSettings.dll') != self.config['runtime_sha256']:
            raise LaunchError('The World Settings files do not match this shortcut.')
        self.spec = json.loads((self.package/'world_patch.json').read_bytes())
        sys.path.insert(0, str(self.package/'activation'))
        import preflight
        if Path(preflight.__file__).resolve() != self.package/'activation/preflight.py':
            raise LaunchError('Unexpected activation helper.')
        self.inputs = preflight.verify()
        from native_ready import NativeReadiness
        self.native = NativeReadiness(self.package, self.inputs)
        self.policy = LaunchPolicy(timeout=self.config['timeout_seconds'])
        self.uri = self.find_uri(self.inputs['source'])
        self.event('preflight_passed', dict(runtime_sha256=self.config['runtime_sha256'],
            world_spec_sha256=self.config['package_spec_sha256'], registered_game_uri=self.uri))

    @staticmethod
    def find_uri(source):
        import winreg
        ids = []
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Ubisoft\Launcher\Installs',
                            0, winreg.KEY_READ | winreg.KEY_WOW64_32KEY) as root:
            for i in range(winreg.QueryInfoKey(root)[0]):
                name = winreg.EnumKey(root, i)
                if not name.isdecimal():
                    continue
                with winreg.OpenKey(root, name) as item:
                    try:
                        folder = Path(winreg.QueryValueEx(item, 'InstallDir')[0]).resolve()
                    except (FileNotFoundError, TypeError, ValueError):
                        continue
                    if folder == source.resolve():
                        ids.append(name)
        if len(ids) != 1:
            raise LaunchError('Ubisoft Connect could not identify this Anno installation. No game was started.')
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r'uplay\shell\open\command') as handler:
            if not winreg.QueryValueEx(handler, None)[0]:
                raise LaunchError('The Ubisoft Connect game launcher is not registered.')
        return 'uplay://launch/' + ids[0] + '/0'

    def start(self):
        self.policy.start(self.native.processes(), time.monotonic(),
                          not_before_creation_time=time.time_ns()//100+116444736000000000)
        # The registered Ubisoft handler starts the normal, authenticated game;
        # no authentication arguments, launcher files or game EXE are modified.
        os.startfile(self.uri)
        self.event('launch_requested', dict(uri=self.uri,
            not_before_creation_time=self.policy.not_before_creation_time))

    def wait_and_activate(self, progress):
        previous = None
        while True:
            ids = self.native.processes()
            observation = self.native.inspect(ids[0]) if len(ids) == 1 else None
            state = self.policy.observe(ids, observation, time.monotonic())
            summary = None if observation is None else {
                k: observation.get(k) for k in ('state','pid','process_creation_time','reason','hwnd',
                    'frame_pointer','vtable_rva','menu_proof_verified','field8','field2210','field2218')}
            if summary != previous:
                self.event('startup_observation', summary)
                previous = summary
            if state == 'activate':
                final = self.native.inspect(ids[0])
                keys = ('pid','process_creation_time','hwnd','frame_pointer')
                if (final.get('state') != 'menu' or final.get('menu_proof_verified') is not True
                        or any(final.get(k) != observation.get(k) for k in keys)):
                    raise LaunchError('Anno left its main menu before activation. Close Anno and use this shortcut again.')
                progress('Enabling World Settings…\nPlease leave Anno at its main menu.')
                self.activate(final)
                self.policy.complete()
                self.event('success', dict(pid=observation['pid'], engine_patch_count=173))
                return observation
            if state == 'inactive':
                raise LaunchError('This launch has already attempted activation. Close Anno before trying again.')
            progress('Starting Anno through Ubisoft Connect…' if state == 'waiting_for_game'
                     else 'Waiting for Anno’s main menu…\nWorld Settings will enable automatically.')
            time.sleep(0.4)

    def activate(self, observation):
        command = [sys.executable, '-B', '-u', str(HERE/'activation_once.py'),
                   '--pid',str(observation['pid']),
                   '--creation',str(observation['process_creation_time']),
                   '--hwnd',str(observation['hwnd']),
                   '--frame',str(observation['frame_pointer'])]
        self.event('activation_attempt', dict(pid=observation['pid'], automatic_retries_allowed=False))
        try:
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                encoding='utf-8', errors='replace', creationflags=subprocess.CREATE_NO_WINDOW, timeout=240)
        except subprocess.TimeoutExpired as exc:
            self.event('activation_timeout', dict(stdout=str(exc.stdout or ''), stderr=str(exc.stderr or '')))
            raise LaunchError('Enabling World Settings timed out. Close Anno before using this shortcut again. No retry was attempted.') from exc
        self.event('activation_result', dict(exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr))
        if result.returncode:
            raise LaunchError('World Settings could not be enabled. Close Anno before trying again. Details are saved in the launch log.')
        try:
            data = json.loads(result.stdout)
        except ValueError as exc:
            raise LaunchError('Activation returned an unexpected result. Close Anno before trying again.') from exc
        expected = dict(pid=observation['pid'],process_creation_time=observation['process_creation_time'],
            hooks_installed=True,engine_state='expanded',all_engine_instruction_bytes_verified=True,
            engine_patch_count=173,engine_patch_status=173,hook_site_count=9,central_war_site_state='guard-jump',
            runtime_sha256=self.config['runtime_sha256'],world_spec_sha256=self.config['package_spec_sha256'],
            executable_sha256=self.inputs['exe_sha256'],copy_root=str(self.inputs['copy']),
            engine_plan_sha256=self.spec['expanded_engine_plan_sha256'])
        if any(data.get(k) != v for k,v in expected.items()):
            raise LaunchError('The complete World Settings activation could not be verified. Close Anno before trying again.')


def main():
    import tkinter as tk
    from tkinter import ttk
    root = tk.Tk()
    root.title('Anno 1503 — World Settings')
    root.geometry('470x175+%d+%d' % (max(0,(root.winfo_screenwidth()-470)//2),
                                   max(0,(root.winfo_screenheight()-175)//2)))
    root.resizable(False, False)
    root.attributes('-topmost', True)
    status = tk.StringVar(value='Checking World Settings…')
    ttk.Label(root, textvariable=status, wraplength=430, anchor='center', justify='center',
              font=('Segoe UI',11)).pack(padx=20,pady=(25,12))
    bar = ttk.Progressbar(root, mode='indeterminate', length=400)
    bar.pack(pady=5)
    bar.start(15)
    messages = queue.Queue()
    mutex_api = C.WinDLL('kernel32', use_last_error=True)
    mutex_api.CreateMutexW.argtypes = [C.c_void_p,C.c_int,C.c_wchar_p]
    mutex_api.CreateMutexW.restype = C.c_void_p
    mutex_api.CloseHandle.argtypes = [C.c_void_p]
    mutex = mutex_api.CreateMutexW(None, False, 'Local\\Anno1503WorldSettingsLauncher_0_11_Dev1')
    duplicate = C.get_last_error() == 183
    if not mutex:
        raise LaunchError('The launcher could not start.')
    log_dir = HERE/'logs'
    log_dir.mkdir(exist_ok=True)
    log = log_dir/(datetime.datetime.now().strftime('%Y%m%d_%H%M%S_')+uuid.uuid4().hex[:8]+'.jsonl')
    def event(kind, data):
        with log.open('a',encoding='utf-8') as out:
            out.write(json.dumps(dict(time_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                     event=kind,data=data),ensure_ascii=False)+'\n')
    active = [True]
    def close():
        # Closing a running activator must never cause a second activation or
        # end the game. The worker finishes independently; no DLL is unloaded.
        if active[0]:
            status.set('Please wait while startup finishes.\nTo cancel, close Anno first.')
        else:
            root.destroy()
    root.protocol('WM_DELETE_WINDOW',close)
    def worker():
        try:
            if duplicate:
                raise LaunchError('The World Settings launcher is already running. Please wait for it to finish.')
            backend=Backend(event)
            backend.start()
            observation=backend.wait_and_activate(lambda s:messages.put(('progress',s)))
            messages.put(('success',observation))
        except Exception as exc:
            event('error',dict(type=type(exc).__name__,message=str(exc)))
            messages.put(('error',str(exc)))
    def poll():
        try:
            while True:
                kind,data=messages.get_nowait()
                if kind=='progress':status.set(data)
                elif kind=='success':
                    active[0]=False;bar.stop()
                    status.set('World Settings enabled.\nChoose New endless game, or load your save.')
                    root.after(1800,root.destroy)
                else:
                    active[0]=False;bar.stop()
                    status.set(data)
                    root.geometry('470x255')
                    ttk.Button(root,text='Open launch log',command=lambda:os.startfile(log)).pack(pady=5)
                    ttk.Button(root,text='Close',command=root.destroy).pack(pady=5)
        except queue.Empty:
            pass
        if root.winfo_exists():root.after(100,poll)
    threading.Thread(target=worker,daemon=False).start()
    root.after(100,poll)
    try:root.mainloop()
    finally:mutex_api.CloseHandle(mutex)


if __name__=='__main__':
    main()
