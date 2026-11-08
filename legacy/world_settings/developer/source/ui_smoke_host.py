"""Standalone developer UI host: no engine state and no game-start capability."""
import ctypes
from pathlib import Path

if __name__ == '__main__':
    here = Path(__file__).resolve().parent
    dll = ctypes.CDLL(str(here / 'engine_audit/runtime/WorldSettings.dll'))
    dll.WorldSettingsShowDevelopmentDialog.argtypes = [ctypes.c_void_p]
    dll.WorldSettingsShowDevelopmentDialog.restype = ctypes.c_int
    print('Opening standalone development dialog; not an in-game integration test.', flush=True)
    result = dll.WorldSettingsShowDevelopmentDialog(None)
    print('Dialog result:', result, flush=True)
    if result != 0:
        raise SystemExit('Unverified standalone host must not authorize a game start')
