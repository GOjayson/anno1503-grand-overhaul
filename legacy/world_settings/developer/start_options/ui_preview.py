"""Standalone screen preview. Cannot start a game or apply world options."""
from pathlib import Path
import ctypes
import argparse
ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--runtime',type=Path,default=ROOT/'native/AnnoWorldSettings.dll')
args=parser.parse_args()
runtime=ctypes.CDLL(str(args.runtime.resolve(strict=True)))
runtime.WorldSettingsSettingsSize.restype=ctypes.c_uint32
assert runtime.WorldSettingsSettingsSize()==52
runtime.WorldSettingsShowDevelopmentDialog.argtypes=[ctypes.c_void_p]
runtime.WorldSettingsShowDevelopmentDialog.restype=ctypes.c_int
print(__doc__,flush=True)
assert runtime.WorldSettingsShowDevelopmentDialog(None)==0
print('Preview closed; no game started.',flush=True)
