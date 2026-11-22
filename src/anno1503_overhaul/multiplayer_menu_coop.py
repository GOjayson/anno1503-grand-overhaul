"""Stock History Edition scene-factory call for paired LAN co-op."""

from hashlib import sha256
from struct import unpack

from .world_runtime_build import PE, STOCK_SHA256


MENU_COOP_CALLS = ((0x55C54, bytes.fromhex("ff15a6860400"), "AnnoMenuCoopScene"),)
_FACTORY_SLOT = 0x9E300


def verified_menu_coop_calls(original: bytes):
    """Patch only the final native World creation call, before roster assignment."""
    if sha256(original).hexdigest() != STOCK_SHA256["AnnoFrame.dll"]:
        raise ValueError("Expected the reviewed stock History Edition Frame for co-op.")
    image = PE(original)
    (address, before, _), = MENU_COOP_CALLS
    end = address + len(before)
    if (not image.executable(address, len(before)) or image.read(address, len(before)) != before
            or end + unpack("<i", before[2:])[0] != _FACTORY_SLOT
            or not any(start <= address < end <= stop for start, stop, _ in image.function_table())):
        raise ValueError("The reviewed native co-op scene factory call changed.")
    return MENU_COOP_CALLS
