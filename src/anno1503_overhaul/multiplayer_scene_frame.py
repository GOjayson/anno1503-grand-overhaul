"""Exact History Edition opens for an optional verified multiplayer scene."""

from hashlib import sha256
from struct import unpack

from .world_runtime_build import PE, STOCK_SHA256


_OPEN = "AnnoTrialOpenScene"
FRAME_SHADOW_CALLS = (
    (0x400E3, bytes.fromhex("ff15f7e20500"), _OPEN),  # selected scenario checksum
    (0x3EAD5, bytes.fromhex("ff1505f90500"), _OPEN),  # host preparation checksum
    (0x3E679, bytes.fromhex("ff1561fd0500"), _OPEN),  # splash checksum
    (0x45163, bytes.fromhex("ff1577920500"), _OPEN),  # lobby scene header
    (0x4BE22, bytes.fromhex("ff15b8250500"), _OPEN),  # lobby checksum and seat data
)
SCENE_SHADOW_CALLS = (
    (0x356B, bytes.fromhex("ff15e71a0300"), _OPEN),  # common Scene filename loader
)


def verified_shadow_calls(module: str, original: bytes):
    """Bind callback RVAs, full instruction bytes and the native IAT slot to a stock image."""
    calls, slot = {
        "AnnoFrame.dll": (FRAME_SHADOW_CALLS, 0x9E3E0),
        "AnnoScene.dll": (SCENE_SHADOW_CALLS, 0x35058),
    }.get(module, (None, None))
    if calls is None or sha256(original).hexdigest() != STOCK_SHA256[module]:
        raise ValueError("Expected the reviewed History Edition scene or frame module.")
    image = PE(original)
    ranges = image.function_table()
    for address, before, _ in calls:
        end = address + len(before)
        if (not image.executable(address, len(before)) or image.read(address, len(before)) != before
                or before[:2] != b"\xff\x15" or end + unpack("<i", before[2:])[0] != slot
                or not any(start <= address < end <= stop for start, stop, _ in ranges)):
            raise ValueError("A reviewed native scene-open call changed.")
    return calls
