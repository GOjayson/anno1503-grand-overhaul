"""Exact stock call sites used to refresh the direct lobby's visible roster."""

from hashlib import sha256

from .world_runtime_build import PE, STOCK_SHA256


LOBBY_ROSTER_CALLS = (
    # The following backdrop hook now uses RCX and no longer consumes the
    # virtual table load included in this preimage at 0x4C6DF.
    (0x4C6DA, bytes.fromhex("e8b11a0000488b07"), "AnnoMenuRefreshLobbyPlayers"),
    # The replacement retains the stock global dirty-flag reset after refresh.
    (0x4E7B7, bytes.fromhex("e8d4f9ffff44883d52940700"), "AnnoMenuUpdateLobbyPlayers"),
)

_WIDGET_PREIMAGES = (
    (0x4E1D2, "488b7868"),  # stock lobby list control
    (0x4E447, "ff90a0000000"),  # name and flag row insertion
    (0x924D0, "4d8bd083fa177430448bca4181e9b80100007417"),  # tGadListeEx capability 0x1B8
)


def verify_lobby_roster(original: bytes) -> None:
    if sha256(original).hexdigest() != STOCK_SHA256["AnnoFrame.dll"]:
        raise ValueError("The reviewed native lobby roster image changed.")
    image = PE(original)
    for address, signature in _WIDGET_PREIMAGES:
        before = bytes.fromhex(signature)
        if image.read(address, len(before)) != before:
            raise ValueError("The reviewed native lobby list instructions changed.")
