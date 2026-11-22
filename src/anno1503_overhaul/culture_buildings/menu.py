"""Reviewed History Edition construction-menu input fingerprints."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import struct
from .. import food_artwork as formats


MENU_SLOT_RVA = 0xCB130
EMPTY_SLOTS = struct.pack("<4I", 1, 0, 1, 0)
ADDON_ORNAMENTS = "THUMBNAILZIERDE_ADDON"

VIEW_HASHES = {
    "ed1c13167d6fc9fd220f074da52bb63d396b6a11b722c48a44a2babd8c6f4aef",
    "b5af6086d34a614a31f4c30a83c9fc9b213dee186a660394dbe664776ec160b2",
}

# These are the unmodified and Food 0.6 atlases from the two reviewed hosts.
ATLAS_HASHES = {
    Path("ToolGfx/fenster.tex"): {
        "8cc32a5e92594d0f915e72329349bb2b915eb5e4ba75afcc22a86da4ef4732b8",
        "5ffe4c898d00c38d1fed3e9beda4f3c0180f6a62ee87373e940e60ac4b3509c8",
    },
    Path("ToolGfx/fenster8.tex"): {
        "f0b97e0c83f5e4fd36c2d3f21555bcbfe1b04eaa05b1e372eb17c8e0597438ec",
        "fbffe486805a4e833a40bf028a3858552bdbbb496955910401713f2d0e134203",
    },
    Path("Languages/Nl/ToolGfx/fenster.tex"): {
        "2135e79aa74e906ef25d10cf79ac98fdbd70ab40f23c851685d1ef1a4c5ca777",
        "1449f7b247176bb643ade208f4572db41cabdaa8ddb9b0a98ad0de071f7bff96",
    },
}

INDEX_HASHES = {
    Path("ToolGfx/fenster.inc"): {
        "e223b51dce9c5f693d21a40cdb0a28a824a8cbf84b147de62ee2730ce469a4c0",
        "cc095d5906ef151763d425261b2a02f6386c83de553c6c8a0515a5af5acbcd64",
    },
    Path("ToolGfx/fenster8.inc"): {
        "634341be7c876af8b27d673ded2d5d57ca4511d1f11452b384b5a7b40499220a",
        "1614fa724a3e54644a0cc025dcf0d8b4f71480df149fa8fb2f0d38b73cead602",
    },
    Path("Languages/Nl/ToolGfx/fenster.inc"): {
        "634341be7c876af8b27d673ded2d5d57ca4511d1f11452b384b5a7b40499220a",
        "1614fa724a3e54644a0cc025dcf0d8b4f71480df149fa8fb2f0d38b73cead602",
    },
}


TOOLTIP_HASHES = {
    Path("Texte.dat"): "859734cd8a051b94103ac2e5a5d4634e7b949c3c4a77fee3cf956bfcb30cbe64",
    Path("Languages/Texte.dat"): "ca467e6bca423f1ac6d345db7fd314c68c599db868ad08877af2f2381b03ce3c",
    Path("Languages/Nl/Texte.dat"): "c6906aa2339d2dfb1147bf8af2879509561843854514c4ba73f429d463476fc0",
}



def _verified_source(root: Path, relative: Path, expected: set[str]) -> bytes:
    data = (root / relative).read_bytes()
    if sha256(data).hexdigest() not in expected:
        raise ValueError(f"Unrecognized prototype menu input {relative}")
    return data


def _section(data: bytes, header: bytes) -> tuple[int, int]:
    marker = header + b"\r\n"
    if data.count(marker) != 1:
        raise ValueError(f"Expected one text section {header.decode()}")
    start = data.index(marker)
    if start and data[start - 2:start] != b"\r\n":
        raise ValueError(f"Invalid text section boundary {header.decode()}")
    return start, data.index(b"\r\n[", start) + 2
