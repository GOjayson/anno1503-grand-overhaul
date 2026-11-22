"""The reviewed direct discovery send call in the History Edition Frame."""

from hashlib import sha256
from struct import unpack

from .world_runtime_build import PE, STOCK_SHA256


INTERNET_ROOM_CALLS = ((0x715F1, bytes.fromhex("ff1599d00200"), "AnnoMenuSendRoomDiscovery"),)


def verified_internet_room_calls(original: bytes):
    if sha256(original).hexdigest() != STOCK_SHA256["AnnoFrame.dll"]:
        raise ValueError("Expected the reviewed History Edition Frame for Internet rooms.")
    image = PE(original)
    (address, before, _), = INTERNET_ROOM_CALLS
    end = address + len(before)
    if (not image.executable(address, len(before)) or image.read(address, len(before)) != before
            or end + unpack("<i", before[2:])[0] != 0x9E690
            or not any(start == 0x710F0 and end <= stop for start, stop, _ in image.function_table())):
        raise ValueError("The reviewed native discovery send instruction changed.")
    return INTERNET_ROOM_CALLS
