"""Pinned History Edition co-op flag selection and native lobby refresh sites."""

from hashlib import sha256
from struct import unpack

from .world_runtime_build import PE, STOCK_SHA256


COOP_LOBBY_FLAG_CALLS = (
    (0x4D19F, bytes.fromhex("488d05ba040000"), "AnnoMenuCoopChooseFlag"),
    (0x4D602, bytes.fromhex("4c8d0557000000"), "AnnoMenuCoopChooseFlag"),
    (0x4DCED, bytes.fromhex("e89e0d0000b801000000"), "AnnoMenuCoopSendFlags"),
    (0x4DDB4, bytes.fromhex("ff90a8010000"), "AnnoMenuCoopGuestFlagUi"),
)

_WIDGET_PREIMAGES = (
    (0x4D00B, "c744244808000000"),  # eight stock flag controls
    (0x4E09E, "41ff5148"),  # look up the flag child by index
    (0x4E0BA, "41ff91a0000000"),  # stock flag enable capability
    (0x946DF, "488d05ba6c0100488903"),  # looked-up flag button vtable
)


def verify_coop_lobby_flags(original: bytes) -> None:
    if sha256(original).hexdigest() != STOCK_SHA256["AnnoFrame.dll"]:
        raise ValueError("The reviewed native co-op lobby image changed.")
    image = PE(original)
    for address, signature in _WIDGET_PREIMAGES:
        before = bytes.fromhex(signature)
        if image.read(address, len(before)) != before:
            raise ValueError("The reviewed co-op lobby flag widget changed.")
    for address, before, _ in COOP_LOBBY_FLAG_CALLS[:2]:
        if address + len(before) + unpack("<i", before[3:])[0] != 0x4D660:
            raise ValueError("The reviewed stock co-op flag selection target changed.")
