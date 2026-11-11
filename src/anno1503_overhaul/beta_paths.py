"""User-owned beta cache and bundled compiler locations, outside the game."""
import os
from pathlib import Path

from .filesystem import checked_path


def application_data() -> Path:
    base = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local')
    return checked_path(base / 'Anno1503GrandOverhaul', exists=False)


def default_game_copy() -> Path:
    return application_data() / 'Game'


def package_workspace() -> Path:
    directory = application_data() / 'Packages'
    directory.mkdir(parents=True, exist_ok=True)
    return checked_path(directory)


def compiler_path() -> Path:
    root = Path(__file__).resolve().parents[2]
    for candidate in (root / 'tools/compiler/zig.exe', root / '.local/toolchain/ziglang/zig.exe'):
        if candidate.is_file():
            return checked_path(candidate)
    raise RuntimeError('The compiler included with the beta is missing. Extract the complete beta ZIP and run Setup again. Source contributors can place Zig 0.16.0 in tools/compiler/.')
