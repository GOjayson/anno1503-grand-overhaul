"""Headless entry used exclusively by the running native multiplayer menu."""
from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
from struct import Struct
import sys

from .filesystem import checked_path, file_sha, read_copy_marker, safe_child
from .lan_identity import load_player, set_player_name
from .lan_preflight import game_fingerprint
from .lan_room import LanRoomError
from .multiplayer_menu_worker import LAN_PLAYER_LIMIT, NATIVE_PLAN_SIZE, MenuAction, MenuRequest, pair_menu_request
from .multiplayer_menu_world import WORLD_MARKER, make_world, receive_world, require_runtime, select_world, start_resolver
from .world_options_snapshot import SNAPSHOT_SIZE, decode
from .world_settings_multiplayer_scene import multiplayer_disaster_guid
from .world_settings_multiplayer_faction_activity import MULTIPLAYER_FREQUENCY_AI_SHA256
from .world_settings_multiplayer_native import (
    supports_faction_frequency, supports_peaceful_ai, supports_populated_cultures, supports_populated_factions,
)
from .world_settings_multiplayer import FEATURE
from .world_runtime_build import STOCK_SHA256


_REQUEST = Struct(f"<IIQQQ32s16s16sIIII{SNAPSHOT_SIZE}s")
_REPLY = Struct(f"<II{NATIVE_PLAN_SIZE}sQ32sII256s{SNAPSHOT_SIZE}s32s")
_DISASTER_SETTINGS = Struct("<4I16s")
_STOCK_DISPLAY = "3cfc150fde93b572dd06ff375454792b844f1d7aab62a65c034230df64356eb2"


def _text(raw: bytes) -> str:
    word, end, padding = raw.partition(b"\0")
    if not end or any(padding) or any(not 32 <= char <= 126 for char in word):
        raise ValueError("Invalid multiplayer menu text.")
    return word.decode("ascii")


def _owner(pid: int, creation: int, window: int, dialog: int, executable: Path) -> None:
    """Use Windows-owned process identity and the exact modal owner each time."""
    import ctypes as c
    from ctypes import wintypes as w

    kernel = c.WinDLL("kernel32", use_last_error=True)
    user = c.WinDLL("user32", use_last_error=True)
    user.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
    user.GetWindowThreadProcessId.restype = w.DWORD
    user.IsWindowEnabled.argtypes = [w.HWND]
    user.IsWindowEnabled.restype = w.BOOL
    user.GetWindow.argtypes = [w.HWND, w.UINT]
    user.GetWindow.restype = w.HWND
    user.GetClassNameW.argtypes = [w.HWND, w.LPWSTR, c.c_int]
    user.GetClassNameW.restype = c.c_int
    kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    kernel.OpenProcess.restype = w.HANDLE
    kernel.GetProcessTimes.argtypes = [w.HANDLE, *([c.POINTER(w.FILETIME)] * 4)]
    kernel.GetProcessTimes.restype = w.BOOL
    kernel.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, c.POINTER(w.DWORD)]
    kernel.QueryFullProcessImageNameW.restype = w.BOOL
    kernel.CloseHandle.argtypes = [w.HANDLE]
    kernel.CloseHandle.restype = w.BOOL

    def owns_modal():
        owner_pid = w.DWORD()
        dialog_pid = w.DWORD()
        window_thread = user.GetWindowThreadProcessId(window, c.byref(owner_pid))
        dialog_thread = user.GetWindowThreadProcessId(dialog, c.byref(dialog_pid))
        dialog_class = c.create_unicode_buffer(32)
        return (window_thread and window_thread == dialog_thread
                and owner_pid.value == dialog_pid.value == pid
                and user.GetWindow(dialog, 4) == window
                and user.GetClassNameW(dialog, dialog_class, len(dialog_class))
                and dialog_class.value == "#32770" and not user.IsWindowEnabled(window))

    error = "The multiplayer menu is no longer awaiting this request."
    if not pid or not creation or not window or not dialog or not owns_modal():
        raise LanRoomError(error)
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        raise LanRoomError(error)
    try:
        started, exited, elapsed_kernel, elapsed_user = (w.FILETIME() for _ in range(4))
        name = c.create_unicode_buffer(32768)
        length = w.DWORD(len(name))
        if not (kernel.GetProcessTimes(handle, *(c.byref(item) for item in (
                started, exited, elapsed_kernel, elapsed_user)))
                and (started.dwHighDateTime << 32 | started.dwLowDateTime) == creation
                and kernel.QueryFullProcessImageNameW(handle, 0, name, c.byref(length))
                and checked_path(Path(name.value)) == executable
                and owns_modal()):
            raise LanRoomError(error)
    finally:
        kernel.CloseHandle(handle)


def _handle(raw: bytes, game: Path, pins: Mapping[str, str], world_pin: str | None = None,
            *, visibility: bool = False, huge: bool = False, stock_ai: bool = False, disasters: bool = False,
            factions: bool = False, cultures: bool = False, faction_ai_pins: Mapping[str, str] | None = None) -> bytes:
    if len(raw) != _REQUEST.size:
        raise ValueError("Open multiplayer from the running Anno game.")
    (action, pid, creation, window, dialog, name, address, bind,
     preview_only, use_world, preview_length, session_mode, snapshot) = _REQUEST.unpack(raw)
    action = MenuAction(action)
    if session_mode not in (0, 1) and not 3 <= session_mode <= LAN_PLAYER_LIMIT:
        raise ValueError("Invalid multiplayer session mode.")
    co_op = session_mode == 1
    count = max(2, session_mode)
    request = MenuRequest(action, _text(address), _text(bind), co_op, count)
    name = _text(name)
    hosting = request.action in (MenuAction.LAN_HOST, MenuAction.INTERNET_HOST)
    if (preview_only not in (0, 1) or use_world not in (0, 1)
            or session_mode and preview_only
            or preview_length not in (0, SNAPSHOT_SIZE) or any(snapshot[preview_length:])
            or bool(preview_length) != bool(hosting and use_world and not preview_only)
            or preview_only and not (hosting and use_world)):
        raise ValueError("Invalid World Settings menu request.")
    if count > 4 and not use_world:
        raise ValueError("Five to eight players require a generated World Settings map.")
    if faction_ai_pins is not None and (not factions or faction_ai_pins != MULTIPLAYER_FREQUENCY_AI_SHA256):
        raise ValueError("This multiplayer build has unexpected faction frequency modules.")
    executable = safe_child(game, "Anno1503.exe", exists=True)

    def verify() -> None:
        _owner(pid, creation, window, dialog, executable)

    def verified_game() -> None:
        marker = read_copy_marker(game)
        if marker["phase"] != "vanilla" or file_sha(executable) != marker.get("source_exe_sha256"):
            raise LanRoomError("Use the verified isolated Anno multiplayer copy.")
        for relative, expected in pins.items():
            if file_sha(safe_child(game, relative, exists=True)) != expected:
                raise LanRoomError("The isolated multiplayer build has changed.")
        if faction_ai_pins is not None:
            world_selected = marker.get(WORLD_MARKER) is True
            if use_world and not world_selected:
                raise LanRoomError("Enable the verified World Settings multiplayer companion first.")
            expected_pins = faction_ai_pins if world_selected else STOCK_SHA256
            for name in faction_ai_pins:
                if file_sha(safe_child(game, name, exists=True)) != expected_pins[name]:
                    raise LanRoomError("The multiplayer faction frequency modules differ from this install.")

    def verify_frequency_runtime() -> None:
        if faction_ai_pins is not None and not supports_faction_frequency(require_runtime(game, world_pin), world_pin):
            raise ValueError("This World Settings companion cannot apply faction frequency.")

    def fingerprint() -> str:
        verified_game()
        native = {name: (pins[name], STOCK_SHA256[name])
                  for name in ("AnnoFrame.dll", "AnnoScene.dll", "AnnoWelt.dll") if name in pins}
        native["AnnoDisplay.dll"] = pins["AnnoDisplay.dll"], _STOCK_DISPLAY
        if faction_ai_pins is not None:
            native.update({name: (digest, STOCK_SHA256[name]) for name, digest in faction_ai_pins.items()})
        stock = game_fingerprint(game, native_baselines=native)
        parts = [stock, *(pins[name] for name in sorted(pins))]
        if use_world:
            require_runtime(game, world_pin)
            parts.append(world_pin)
            if faction_ai_pins is not None:
                parts.extend(faction_ai_pins[name] for name in sorted(faction_ai_pins))
        payload = b"".join(map(bytes.fromhex, parts))
        if co_op:
            payload += b"ANNOCOOP" if action in (MenuAction.LAN_HOST, MenuAction.LAN_JOIN) else b"ANNOCNET"
        elif count > 2:
            mode = b"ANNOROOM" if action in (MenuAction.LAN_HOST, MenuAction.LAN_JOIN) else b"ANNONETR"
            payload += mode + bytes((count,))
        return sha256(payload).hexdigest()

    verify()
    if preview_only:
        verified_game()
        verify_frequency_runtime()
        selection = select_world(game, world_pin, dialog)
        verify()
        return _REPLY.pack(0 if selection else 2, len(selection or b""), b"", 0, b"", 0, 0, b"", selection or b"", b"")

    generated = None
    pair_options = {}
    if use_world:
        verified_game()
        verify_frequency_runtime()
        world_options = dict(allow_unexplored=visibility, resolve_starts=start_resolver(game, world_pin, allow_huge=huge))
        if visibility:
            world_options["allow_reveal_activity"] = True
        if huge:
            world_options["allow_huge"] = True
        if stock_ai:
            world_options["allow_ai"] = True
            if visibility and supports_peaceful_ai(require_runtime(game, world_pin), world_pin):
                world_options["allow_peaceful_ai"] = True
        if disasters:
            world_options["allow_disasters"] = True
        if factions:
            if not supports_populated_factions(require_runtime(game, world_pin), world_pin):
                raise ValueError("This World Settings companion cannot load populated faction islands.")
            world_options["allow_factions"] = True
            if faction_ai_pins is not None:
                world_options["allow_faction_activity"] = True
        if cultures:
            if not supports_populated_cultures(require_runtime(game, world_pin), world_pin):
                raise ValueError("This World Settings companion cannot load native culture towns.")
            world_options["allow_cultures"] = True
        if count > 4:
            world_options["human_slots"] = 8
        if hosting:
            generated = make_world(game, snapshot, **world_options)
            pair_options["addon_offer"] = generated.offer
        else:
            def prepare(received):
                nonlocal generated
                verify()
                generated = receive_world(game, received, **world_options)
                verify()
                return generated.offer["artifact_sha256"]

            pair_options.update(addon_id=FEATURE, prepare_addon=prepare)
    verify()
    player = set_player_name(name) if name else load_player() or set_player_name("LAN Player")
    timeout = 180 if count > 2 else 75 if hosting else 20
    paired = pair_menu_request(request, player, verify_request=verify, game_fingerprint=fingerprint,
                               timeout=timeout, **pair_options)
    plan = paired.native_plan(verify_request=verify, game_fingerprint=fingerprint)
    if generated is None:
        if use_world:
            raise LanRoomError("The agreed World Settings map is missing.")
        return _REPLY.pack(0, 0, plan, 0, b"", 0, 0, b"", b"", b"")
    disaster_policy = b""
    if disasters:
        selected = generated.offer["payload"]
        settings = decode(selected)["settings"]
        peaceful_ai = bool(settings["aiCount"] and settings["aiDifficulty"] == 0)
        disaster_policy = _DISASTER_SETTINGS.pack(
            settings["disasters"], settings["disasterMask"], settings["disasterFrequency"],
            settings["disasterSeverity"], multiplayer_disaster_guid(selected, peaceful_ai=peaceful_ai),
        )
    return _REPLY.pack(0, 0, plan, generated.scene_size, generated.digest,
                       generated.map_visibility, generated.enemy_visibility, b"", b"", disaster_policy)


def run(pins: Mapping[str, str], world_pin: str | None = None, *, visibility: bool = False,
        huge: bool = False, stock_ai: bool = False, disasters: bool = False, factions: bool = False,
        cultures: bool = False, faction_ai_pins: Mapping[str, str] | None = None) -> None:
    """Read one owned request and return one bounded binary result."""
    try:
        game = checked_path(Path(sys.executable)).parent
        reply = _handle(sys.stdin.buffer.read(_REQUEST.size + 1), game, pins, world_pin,
                        visibility=visibility, huge=huge, stock_ai=stock_ai, disasters=disasters,
                        factions=factions, cultures=cultures, faction_ai_pins=faction_ai_pins)
    except (OSError, ValueError, RuntimeError) as error:
        message = str(error).encode("utf-8")[:255].decode("utf-8", errors="ignore").encode("utf-8")
        reply = _REPLY.pack(1, 0, b"", 0, b"", 0, 0, message, b"", b"")
    sys.stdout.buffer.write(reply)
    sys.stdout.buffer.flush()
