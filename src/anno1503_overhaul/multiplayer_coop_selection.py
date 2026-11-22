"""Reviewed Frame and World hook sites for the separate co-op candidate."""

from hashlib import sha256
from struct import pack

from .world_runtime_build import PE, STOCK_SHA256


COOP_FRAME_SELECTION_CALLS = (
    (0x722E7, bytes.fromhex("e810790200440fb77312"), "AnnoMenuCoopCopyCommand"),
    (0x7F500, bytes.fromhex("410fb7384d8d70048d479c83f8340f87930f000048988b8c82440c08004803caffe1"),
     "AnnoMenuCoopBeginCommand"),
    (0x804A7, bytes.fromhex("450fb74002488d154dfbf7ff4d03c6"), "AnnoMenuCoopEndCommand"),
    (0x575F6, bytes.fromhex("ff90b0000000"), "AnnoMenuCoopCloseGame"),
)
COOP_WORLD_SELECTION_CALLS = (
    (0x993CB, bytes.fromhex("44897c2420488bc841ff5238"), "AnnoMenuCoopSeedGroup"),
    (0x98354, bytes.fromhex("41bd1e000000458bf5498be8488d7360418bf8660f1f840000000000"),
     "AnnoMenuCoopGroupLimit"),
)


def verified_coop_selection_calls(module: str, original: bytes):
    if module not in ("AnnoFrame.dll", "AnnoWelt.dll") or sha256(original).hexdigest() != STOCK_SHA256[module]:
        raise ValueError("Expected the reviewed stock History Edition selection module.")
    image = PE(original)
    calls = COOP_FRAME_SELECTION_CALLS if module == "AnnoFrame.dll" else COOP_WORLD_SELECTION_CALLS
    functions = image.function_table()
    for address, before, _ in calls:
        end = address + len(before)
        if (not image.executable(address, len(before)) or image.read(address, len(before)) != before
                or not any(first <= address < end <= last for first, last, _ in functions)):
            raise ValueError("A reviewed co-op selection boundary changed.")
    return calls


def coop_selection_edit(address: int, import_slot: int) -> bytes | None:
    """Retain the exact native arguments and continuation at each selected site."""
    before = after = b""
    if address == 0x722E7:
        after = bytes.fromhex("448bf0")  # Keep copied byte count in R14D.
    elif address == 0x7F500:
        # EDI is the low command byte. R14 holds the existing payload pointer.
        before = bytes.fromhex("410fb6384d8d7004498bcc498bd0")
        # Restore the record in R8 and frame base in RDX before the stock case.
        after = bytes.fromhex("4d8d46fc488d15") + pack("<i", -(address + len(before) + 6 + 11)) + b"\xff\xe0"
    elif address == 0x804A7:
        # Return the next record from native R14 without changing either entry.
        before = bytes.fromhex("498bcc498bd6")
        after = bytes.fromhex("4c8bc0")
    elif address == 0x993CB:
        # RAX still holds the exact type 3 ActiveInfo receiver. Its fifth
        # SetSelection argument is the zero supplied by the wrapper.
        before = bytes.fromhex("488bc8")
    elif address == 0x98354:
        # Save the stock loop's first index and vtable across the call.
        before = bytes.fromhex("418be84c8be9")
        after = bytes.fromhex("498bcd448be8448bf0488d73608bfd")
    elif address != 0x575F6:
        return None
    return before + b"\xff\x15" + pack("<i", import_slot - (address + len(before) + 6)) + after
