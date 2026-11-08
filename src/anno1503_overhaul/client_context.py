"""Relay a verified normal-client launch context to the identical game copy.

The Ubisoft client still performs authentication and ownership checks. This
module neither changes the executable/client nor creates authentication data.
Existing arguments/environment are retained in memory only, never logged or
written to a package. A context authorizes one copy-launch attempt.
"""
from __future__ import annotations

import ctypes as C
from ctypes import wintypes as W
import os
from pathlib import Path
import struct
import subprocess
import time

from .filesystem import checked_path, file_sha, read_copy_marker, validate_roots
from .processes import require_game_closed


EXE_SHA256 = '1a4bebe7c676a5904834b9e67e936187729dc67c013a4fb4fd64986a3cb8e95a'
MAX_ENVIRONMENT_BYTES = 8 * 1024 * 1024


class ContextError(RuntimeError):
    pass


class ClientContext:
    """Opaque, single-use startup context; its representation omits values."""
    __slots__ = ('pid', 'creation_time', 'source_root', '_environment', '_arguments', '_keys', '_used')

    def __init__(self, pid, creation_time, source_root, environment, arguments, keys):
        self.pid, self.creation_time, self.source_root = pid, creation_time, source_root
        self._environment, self._arguments = dict(environment), tuple(arguments)
        self._keys, self._used = tuple(keys), False

    def __repr__(self):
        return f'ClientContext(pid={self.pid}, consumed={self._used}, startup_values=<hidden>)'

    def safe_summary(self):
        return dict(source_pid=self.pid, source_creation_time=self.creation_time,
                    environment_entries=len(self._environment),
                    argument_count=len(self._arguments),
                    differing_game_environment_key_names=list(self._keys), consumed=self._used,
                    startup_values_persisted=False)

    def clear(self):
        # Discard references; Python strings do not promise a secure memory wipe.
        self._environment.clear()
        self._arguments = ()
        self._used = True


def parse_environment_block(data: bytes) -> dict[str, str]:
    """Strict bounded UTF-16 environment parser, including Windows drive keys."""
    if not isinstance(data, bytes) or len(data) > MAX_ENVIRONMENT_BYTES or len(data) % 2:
        raise ContextError('Unsupported normal-client environment storage.')
    end = next((i for i in range(0, len(data)-3, 2) if data[i:i+4] == b'\0\0\0\0'), None)
    if end is None:
        raise ContextError('Normal-client environment termination was not found.')
    try:
        text = data[:end].decode('utf-16-le', 'surrogatepass')
    except UnicodeError:
        raise ContextError('Unsupported normal-client environment encoding.') from None
    environment, keys = {}, set()
    for item in text.split('\0') if text else ():
        split = item.find('=', 1)
        if split < 1:
            raise ContextError('Unsupported normal-client environment entry.')
        key, value = item[:split], item[split+1:]
        if key.casefold() in keys:
            raise ContextError('Duplicate normal-client environment key.')
        keys.add(key.casefold())
        environment[key] = value
    return environment


class _WindowsContext:
    def __init__(self, pid):
        if os.name != 'nt' or C.sizeof(C.c_void_p) != 8:
            raise ContextError('The normal-client handoff requires 64-bit Windows Python.')

        class Basic(C.Structure):
            _fields_ = [('exit', W.LONG), ('peb', C.c_void_p), ('affinity', C.c_size_t),
                        ('priority', W.LONG), ('pid', C.c_size_t), ('parent', C.c_size_t)]

        class Memory(C.Structure):
            _fields_ = [('base', C.c_void_p), ('allocation', C.c_void_p), ('allocationprotect', W.DWORD),
                        ('partition', W.WORD), ('size', C.c_size_t), ('state', W.DWORD),
                        ('protect', W.DWORD), ('type', W.DWORD)]

        if C.sizeof(Basic) != 48 or C.sizeof(Memory) != 48:
            raise ContextError('The Windows process structures are unsupported.')
        self.Basic, self.Memory = Basic, Memory
        self.kernel, self.native = C.WinDLL('kernel32', use_last_error=True), C.WinDLL('ntdll')

        def bind(api, name, arguments, result):
            function = getattr(api, name)
            function.argtypes, function.restype = arguments, result
            return function

        self.open = bind(self.kernel, 'OpenProcess', [W.DWORD, W.BOOL, W.DWORD], W.HANDLE)
        self.close = bind(self.kernel, 'CloseHandle', [W.HANDLE], W.BOOL)
        self.read_memory = bind(self.kernel, 'ReadProcessMemory',
                                [W.HANDLE, C.c_void_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)], W.BOOL)
        self.query_memory = bind(self.kernel, 'VirtualQueryEx',
                                 [W.HANDLE, C.c_void_p, C.POINTER(Memory), C.c_size_t], C.c_size_t)
        self.image = bind(self.kernel, 'QueryFullProcessImageNameW',
                          [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)], W.BOOL)
        self.times = bind(self.kernel, 'GetProcessTimes',
                          [W.HANDLE, C.POINTER(W.FILETIME), C.POINTER(W.FILETIME),
                           C.POINTER(W.FILETIME), C.POINTER(W.FILETIME)], W.BOOL)
        self.query_basic = bind(self.native, 'NtQueryInformationProcess',
                                [W.HANDLE, W.ULONG, C.c_void_p, W.ULONG, C.POINTER(W.ULONG)], W.LONG)
        self.argv = bind(C.WinDLL('shell32'), 'CommandLineToArgvW',
                         [W.LPCWSTR, C.POINTER(C.c_int)], C.POINTER(W.LPWSTR))
        self.free = bind(self.kernel, 'LocalFree', [C.c_void_p], C.c_void_p)
        self.handle = self.open(0x1000 | 0x400 | 0x10 | 0x100000, False, pid)
        if not self.handle:
            raise ContextError('Cannot read the verified normal game process.')

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close(self.handle)

    def read(self, address, length):
        if (not address or address < 0x10000 or length < 0 or address+length >= 1 << 47
                or length > MAX_ENVIRONMENT_BYTES):
            raise ContextError('A normal-client context read exceeds its bounds.')
        value, received = C.create_string_buffer(length), C.c_size_t()
        if not self.read_memory(self.handle, address, value, length, C.byref(received)) or received.value != length:
            raise ContextError('The normal-client context could not be read completely.')
        return value.raw

    def identity(self):
        path, size = C.create_unicode_buffer(32768), W.DWORD(32768)
        if not self.image(self.handle, 0, path, C.byref(size)):
            raise ContextError('Cannot verify the normal game executable path.')
        created, exited, kernel, user = W.FILETIME(), W.FILETIME(), W.FILETIME(), W.FILETIME()
        if not self.times(self.handle, C.byref(created), C.byref(exited), C.byref(kernel), C.byref(user)):
            raise ContextError('Cannot verify the normal game creation time.')
        return checked_path(Path(path.value)), (created.dwHighDateTime << 32) | created.dwLowDateTime

    def string(self, header, offset):
        length, maximum, pointer = struct.unpack_from('<HH4xQ', header, offset)
        if length % 2 or length > maximum or maximum > 65534:
            raise ContextError('The normal-client process string is unsupported.')
        return self.read(pointer, length).decode('utf-16-le', 'surrogatepass') if length else ''

    def capture(self, pid):
        basic, needed = self.Basic(), W.ULONG()
        if (self.query_basic(self.handle, 0, C.byref(basic), C.sizeof(basic), C.byref(needed)) != 0
                or needed.value != C.sizeof(basic) or basic.pid != pid):
            raise ContextError('The Windows process identity structure is unsupported.')
        parameters = struct.unpack_from('<Q', self.read(basic.peb, 0x28), 0x20)[0]
        header = self.read(parameters, 0x90)
        if not 0x90 <= struct.unpack_from('<I', header, 4)[0] <= 65536:
            raise ContextError('The Windows process-parameter structure is unsupported.')
        image_path, command = self.string(header, 0x60), self.string(header, 0x70)
        pointer = struct.unpack_from('<Q', header, 0x80)[0]
        data = bytearray()
        terminated = False
        while len(data) < MAX_ENVIRONMENT_BYTES:
            region, address = self.Memory(), pointer+len(data)
            if (not self.query_memory(self.handle, address, C.byref(region), C.sizeof(region))
                    or region.state != 0x1000 or region.protect & 0x101):
                raise ContextError('The normal-client environment is not readable committed storage.')
            extent = region.base+region.size-address
            if extent <= 0:
                raise ContextError('The normal-client environment bounds do not advance.')
            start = max(0, len(data)-2)
            data.extend(self.read(address, min(65536, extent, MAX_ENVIRONMENT_BYTES-len(data))))
            if any(data[i:i+4] == b'\0\0\0\0' for i in range(start, len(data)-3, 2)):
                terminated = True
                break
        if not terminated:
            raise ContextError('The normal-client environment exceeds its bounded storage.')
        environment = parse_environment_block(bytes(data))
        count = C.c_int()
        arguments_pointer = self.argv(command, C.byref(count))
        if not arguments_pointer or not 1 <= count.value <= 1024:
            if arguments_pointer:
                self.free(arguments_pointer)
            raise ContextError('The normal-client arguments are unsupported.')
        try:
            arguments = [arguments_pointer[i] for i in range(count.value)]
        finally:
            self.free(arguments_pointer)
        return image_path, arguments, environment


def capture_client_context(source_game: Path, pid: int, creation_time: int) -> ClientContext:
    """Read only the exact fresh normal process already verified by the launcher."""
    if type(pid) is not int or not 0 < pid <= 0xffffffff or type(creation_time) is not int or creation_time <= 0:
        raise ContextError('A verified game PID and creation time are required.')
    source = checked_path(source_game)
    executable = checked_path(source / 'Anno1503.exe')
    if file_sha(executable) != EXE_SHA256:
        raise ContextError('The normal-client executable differs from the supported signed game.')
    with _WindowsContext(pid) as process:
        actual_path, actual_creation = process.identity()
        if actual_path != executable or actual_creation != creation_time:
            raise ContextError('The normal game process changed before its startup context was read.')
        image_path, arguments, environment = process.capture(pid)
        if (checked_path(Path(image_path)) != executable or not arguments
                or checked_path(Path(arguments[0])) != executable):
            raise ContextError('The normal-client context belongs to another executable.')
        if process.identity() != (actual_path, actual_creation):
            raise ContextError('The normal game process changed during context capture.')
    keys = sorted(key for key, value in environment.items() if os.environ.get(key) != value
                  and any(word in key.casefold() for word in ('uplay', 'ubi', 'launch', 'steam', 'game', 'overlay')))
    return ClientContext(pid, creation_time, source, environment, arguments[1:], keys)


def launch_copy(context: ClientContext, copy_game: Path, *, source_identity=None, source_probe=None):
    """One identical-copy start; the default still requires all games closed.

    The explicit bootstrap allowance keeps only this context's freshly verified
    normal source menu alive during the copied SDK's initialization. It cannot
    adopt an unrelated game or a source that has entered a world.
    """
    if not isinstance(context, ClientContext) or context._used:
        raise ContextError('This normal-client startup context has already been consumed.')
    source, target = validate_roots(context.source_root, copy_game)
    marker = read_copy_marker(target)
    if Path(marker['source_root']).resolve() != source or marker['phase'] not in {'vanilla', 'installed', 'restored'}:
        raise ContextError('The selected copy does not belong to this normal-client game source.')
    original, copied = checked_path(source / 'Anno1503.exe'), checked_path(target / 'Anno1503.exe')
    if (copied.stat().st_nlink != 1 or os.path.samefile(original, copied)
            or file_sha(original) != EXE_SHA256 or file_sha(copied) != EXE_SHA256):
        raise ContextError('Only an independent, identical copy of the supported executable can be launched.')
    if source_identity is None and source_probe is None:
        require_game_closed()
    else:
        if (not isinstance(source_identity, tuple) or len(source_identity) != 4 or source_probe is None
                or source_identity[:2] != (context.pid, context.creation_time)
                or any(type(value) is not int or value <= 0 for value in source_identity)):
            raise ContextError('The normal-client bootstrap identity does not match this context.')
        inputs = getattr(source_probe, 'inputs', {})
        if (Path(inputs.get('source', '')).resolve() != source
                or inputs.get('exe_sha256') != EXE_SHA256 or source_probe.processes() != [context.pid]
                or _menu_identity(source_probe.inspect(context.pid), context.pid, context.creation_time) != source_identity):
            raise ContextError('Only the exact verified normal-client source menu may remain during copy startup.')
    context._used = True
    try:
        return subprocess.Popen([str(copied), *context._arguments], cwd=target, env=context._environment.copy())
    except Exception:
        # Never include Popen argument/environment representations in an error.
        raise ContextError('The identical game copy could not start through the normal-client context.') from None
    finally:
        context.clear()


def _request_menu_close(pid: int, hwnd: int):
    """Request the normal close of one verified window, never terminate a PID."""
    if os.name != 'nt':
        raise ContextError('The normal-client handoff requires Windows.')
    user = C.WinDLL('user32', use_last_error=True)
    user.IsWindow.argtypes, user.IsWindow.restype = [W.HWND], W.BOOL
    user.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
    user.GetWindowThreadProcessId.restype = W.DWORD
    user.PostMessageW.argtypes, user.PostMessageW.restype = [W.HWND, W.UINT, W.WPARAM, W.LPARAM], W.BOOL
    owner = W.DWORD()
    if (not user.IsWindow(hwnd) or not user.GetWindowThreadProcessId(hwnd, C.byref(owner))
            or owner.value != pid or not user.PostMessageW(hwnd, 0x0010, 0, 0)):
        raise ContextError('The verified normal game menu could not close. No game was force-closed or activated.')


def _menu_identity(observation: dict, pid: int, not_before: int):
    if (not isinstance(observation, dict) or observation.get('state') != 'menu'
            or observation.get('menu_proof_verified') is not True
            or type(observation.get('pid')) is not int or observation['pid'] != pid
            or type(observation.get('process_creation_time')) is not int
            or observation['process_creation_time'] < not_before
            or type(observation.get('hwnd')) is not int or observation['hwnd'] <= 0
            or type(observation.get('frame_pointer')) is not int or observation['frame_pointer'] <= 0):
        return None
    return pid, observation['process_creation_time'], observation['hwnd'], observation['frame_pointer']


def start_game(uri: str, source_game: Path, copy_game: Path, source_probe, *, copy_probe,
               event=None, progress=None, timeout: float = 300):
    """Normal Ubisoft authentication, then one identical-copy context relay.

    ``source_probe`` must be the existing read-only NativeReadiness observer
    configured for the exact registered source profile. It must positively
    identify the visible ordinary main menu. A world, unknown process or
    unverified window is never closed. Existing games are never adopted.
    """
    import re
    if not isinstance(uri, str) or not re.fullmatch(r'uplay://launch/[0-9]+/0', uri):
        raise ContextError('An exact registered Ubisoft launch route is required.')
    if type(timeout) not in (int, float) or not 5 <= timeout <= 600:
        raise ContextError('The normal-client startup timeout is invalid.')
    source, target = validate_roots(source_game, copy_game)
    for probe, expected in ((source_probe, source), (copy_probe, target)):
        inputs = getattr(probe, 'inputs', {})
        if Path(inputs.get('source', '')).resolve() != expected or inputs.get('exe_sha256') != EXE_SHA256:
            raise ContextError('The read-only startup observer belongs to a different game profile.')
    if source_probe.processes():
        raise ContextError('Close the running Anno game before starting a selected-feature copy.')
    notify, message = event or (lambda *_: None), progress or (lambda _: None)
    not_before = time.time_ns() // 100 + 116444736000000000
    deadline = time.monotonic() + timeout
    message('Starting Anno through Ubisoft Connect…')
    os.startfile(uri)
    notify('normal_client_start_requested', dict(normal_client_authentication=True))
    identity, since, chosen = None, None, None
    while time.monotonic() < deadline:
        ids = source_probe.processes()
        observation = source_probe.inspect(ids[0]) if len(ids) == 1 else None
        if observation and observation.get('state') == 'unsafe':
            raise ContextError('The normal Anno startup process could not be verified. No copy was started.')
        token = _menu_identity(observation, ids[0], not_before) if len(ids) == 1 else None
        if token is None:
            identity = since = None
        elif token != identity:
            identity, since = token, time.monotonic()
        elif time.monotonic()-since >= 1.5:
            chosen = token
            break
        message('Waiting for the verified Anno main menu before starting the selected-feature copy…')
        time.sleep(0.2)
    if chosen is None:
        raise ContextError('Anno did not reach a verified normal main menu. No copy was started.')
    pid, created, hwnd, _ = chosen
    captured = capture_client_context(source, pid, created)
    try:
        notify('normal_client_context_captured', captured.safe_summary())
        # Reobserve before initializing a second SDK session; source input may
        # have moved to a world while the startup context was being captured.
        ids = source_probe.processes()
        final = source_probe.inspect(pid) if ids == [pid] else None
        if _menu_identity(final, pid, not_before) != chosen:
            raise ContextError('Anno left its verified main menu. No game was closed or copy started.')
        # The client must still have its normal source session alive when the
        # copied SDK initializes. Closing it first was observed to fail normal
        # platform initialization. The guarded allowance names only this menu.
        child = launch_copy(captured, target, source_identity=chosen, source_probe=source_probe)
        notify('feature_copy_initialization_requested', dict(pid=child.pid, normal_source_menu_still_alive=True))
        message('Waiting for your selected-feature copy to finish normal startup…')
        copied_identity, copied_since = None, None
        while time.monotonic() < deadline:
            ids = source_probe.processes()
            if len(ids) != 2 or set(ids) != {pid, child.pid}:
                raise ContextError('The two verified startup processes changed. No source menu was closed.')
            if _menu_identity(source_probe.inspect(pid), pid, not_before) != chosen:
                raise ContextError('The original game left its verified menu. It was not closed.')
            row = copy_probe.inspect(child.pid)
            if row and row.get('state') == 'unsafe':
                raise ContextError('The copied game startup could not be verified. The original menu was not closed.')
            token = _menu_identity(row, child.pid, not_before)
            if token is None:
                copied_identity = copied_since = None
            elif token != copied_identity:
                copied_identity, copied_since = token, time.monotonic()
            elif time.monotonic()-copied_since >= 1.5:
                break
            time.sleep(0.2)
        else:
            raise ContextError('The copied game did not reach its verified menu. The original menu was not closed.')
        # Both menus must still be their exact observed instances before closing
        # only the normal bootstrap source. No force-close or confirmation occurs.
        if (set(source_probe.processes()) != {pid, child.pid}
                or _menu_identity(source_probe.inspect(pid), pid, not_before) != chosen
                or _menu_identity(copy_probe.inspect(child.pid), child.pid, not_before) != copied_identity):
            raise ContextError('A verified startup menu changed. Neither game was closed by the handoff.')
        _request_menu_close(pid, hwnd)
        notify('normal_source_menu_close_requested', dict(pid=pid, process_creation_time=created))
        message('Finishing the normal-client handoff…')
        close_deadline = min(deadline, time.monotonic()+30)
        single_since = None
        while time.monotonic() < close_deadline:
            ids = source_probe.processes()
            if ids == [child.pid]:
                if _menu_identity(copy_probe.inspect(child.pid), child.pid, not_before) != copied_identity:
                    raise ContextError('The copied game left its verified menu during the client handoff.')
                if single_since is None:
                    single_since = time.monotonic()
                elif time.monotonic()-single_since >= 1.5:
                    notify('feature_copy_start_requested', dict(pid=child.pid, unchanged_normal_client_context=True,
                                                               normal_source_closed=True))
                    return child
                time.sleep(0.2)
                continue
            if len(ids) != 2 or set(ids) != {pid, child.pid}:
                raise ContextError('The verified startup process inventory changed during the client handoff.')
            single_since = None
            time.sleep(0.2)
        raise ContextError('The normal source menu did not close. No game was force-closed or activated.')
    finally:
        captured.clear()
