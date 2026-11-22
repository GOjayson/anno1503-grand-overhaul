"""Review the native direct lobby's entry-only paint hook."""

from hashlib import sha256
from pathlib import Path

from .filesystem import file_sha, safe_child
from .world_runtime_build import PE, STOCK_SHA256


# RCX already carries the lobby at the stock virtual initialization call.
LOBBY_BACKGROUND_CALLS = (
    (0x4C6E5, bytes.fromhex("ff90b0010000"), "AnnoMenuPrepareLobbyPaint"),
)

_FRAME_PREIMAGES = (
    (0x4C6DF, "488b07488bcfff90b0010000488bcf"),  # lobby initialization
    (0x3CD02, "ff15f0130600"),  # startup surface clear
    (0x4C84D, "0f1005ec780500488b0d8da707004c8d442420f20f100de8780500ba0a000000"
     "0f11442428f20f114c2438488b01ff9098000000"),  # stock lobby resource lookup
    (0x4FAC8, "488b8ba82100004c8d0df26007004c8d05c3600700c74424200000000033d2"
     "e804a10400488b0df5740700488bd88b542438488b384c8b0141ff90a8000000488bd0488bcbff17"),
    (0x99BF0, "ff25ea490000"),  # stock dynamic cast
    (0xA4140, b"FARBAUSWAHLMULTISPIELER\0".hex()),
)

_DISPLAY_PREIMAGES = (
    (0x61C40, "4883ec084d8bd883fa0a"),  # map resource name to ID
    (0x61580, "85d278214c8b81880000"),  # look up native texture by ID
    (0x3B210, "483b5118740d488951184883c1c0e90d000000c3"),  # set texture and invalidate
    (0x3C32E, "488d058b5df200488903488d05915df20048894340488b430848634804488d05a65df2004889441908"),
)

_STARTUP_ART = {
    "ToolGfx/Startup.inc": "951daf0e2768d8e9a45079b0e9497782427f1fd9aa5d8263dae2c0b40c81bfc8",
    "ToolGfx/Startup.tex": "139b55a920e7090be9afa652de87dafadb98734dfe041873622d1334f3f4c606",
}


def _verify_preimages(original, expected, preimages):
    if sha256(original).hexdigest() != expected:
        raise ValueError("The reviewed native lobby paint image changed.")
    image = PE(original)
    for address, signature in preimages:
        before = bytes.fromhex(signature)
        if image.read(address, len(before)) != before:
            raise ValueError("A reviewed native lobby backdrop instruction changed.")


def verify_lobby_background(original: bytes) -> None:
    _verify_preimages(original, STOCK_SHA256["AnnoFrame.dll"], _FRAME_PREIMAGES)


def verify_lobby_backdrop_inputs(source: Path, display: bytes, display_sha256: str) -> None:
    _verify_preimages(display, display_sha256, _DISPLAY_PREIMAGES)
    for path, pin in _STARTUP_ART.items():
        if file_sha(safe_child(source, path, exists=True)) != pin:
            raise ValueError("The reviewed stock lobby artwork differs in " + path)
