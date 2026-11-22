"""Exact native multiplayer cleanup boundaries for the private menu candidate."""

from hashlib import sha256

from .world_runtime_build import PE, STOCK_SHA256


# The first two branches are reached after releasing both native network
# objects. Each has the startup Frame in RBX and only its epilogue follows.
# At the last call the completed-match path has cleared both objects and the
# stock diagnostic takes one const char* in RCX before rebuilding the menu.
MENU_LIFECYCLE_CALLS = (
    (0x38F58, bytes.fromhex("c6831822000000c7831022000001000000"), "AnnoMenuFinishQuit"),
    (0x38FD7, bytes.fromhex("c7831022000000000000c6059adc080000c6831822000000"), "AnnoMenuFinishBack"),
    (0x5789F, bytes.fromhex("ff15d3670400"), "AnnoMenuFinishMatch"),
)


def lifecycle_arguments(address: int) -> bytes:
    """Pass the native RBX startup object to the two original state setters."""
    return b"\x48\x8b\xcb" if address in (0x38F58, 0x38FD7) else b""


def verified_menu_lifecycle_calls(original: bytes):
    if sha256(original).hexdigest() != STOCK_SHA256["AnnoFrame.dll"]:
        raise ValueError("The reviewed native multiplayer cleanup image changed.")
    image = PE(original)
    functions = image.function_table()
    for address, before, _ in MENU_LIFECYCLE_CALLS:
        end = address + len(before)
        if (not image.executable(address, len(before)) or image.read(address, len(before)) != before
                or not any(start <= address < end <= stop for start, stop, _ in functions)):
            raise ValueError("A reviewed native multiplayer cleanup boundary changed.")
    return MENU_LIFECYCLE_CALLS
