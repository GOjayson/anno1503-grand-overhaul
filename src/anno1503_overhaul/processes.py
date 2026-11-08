"""Fail closed when a game is running or Windows cannot enumerate processes."""
import os


def require_game_closed():
    if os.name != 'nt':
        raise RuntimeError('Installing and restoring Anno requires Windows.')
    import ctypes as c
    from ctypes import wintypes as w

    class Entry(c.Structure):
        _fields_ = [('size', w.DWORD), ('usage', w.DWORD), ('pid', w.DWORD),
                    ('heap', c.c_size_t), ('module', w.DWORD), ('threads', w.DWORD),
                    ('parent', w.DWORD), ('priority', w.LONG), ('flags', w.DWORD),
                    ('exe', w.WCHAR * 260)]
    api = c.WinDLL('kernel32', use_last_error=True)
    api.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
    api.CreateToolhelp32Snapshot.restype = w.HANDLE
    for name in ('Process32FirstW', 'Process32NextW'):
        function = getattr(api, name)
        function.argtypes = [w.HANDLE, c.POINTER(Entry)]
        function.restype = w.BOOL
    api.CloseHandle.argtypes = [w.HANDLE]
    api.CloseHandle.restype = w.BOOL
    handle = api.CreateToolhelp32Snapshot(2, 0)
    if handle == c.c_void_p(-1).value:
        raise RuntimeError('Cannot check whether Anno is running. Close it and try again.')
    try:
        entry = Entry()
        entry.size = c.sizeof(entry)
        more = api.Process32FirstW(handle, c.byref(entry))
        while more:
            if entry.exe.casefold() == 'anno1503.exe':
                raise RuntimeError('Close Anno 1503 before installing or restoring game files.')
            more = api.Process32NextW(handle, c.byref(entry))
        if c.get_last_error() != 18:
            raise RuntimeError('The running-game check was incomplete. No game files were changed.')
    finally:
        api.CloseHandle(handle)
