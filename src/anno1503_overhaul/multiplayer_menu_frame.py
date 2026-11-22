"""Verified callback loads for the in-game multiplayer dialog candidate."""

from .multiplayer_coop_lobby import COOP_LOBBY_FLAG_CALLS

# The stock selector and color lobby bind callbacks through either the fast
# widget path (RAX) or the native setter (R8).
MENU_CALLBACKS = (
    (0x50095, bytes.fromhex("488d05c4040000"), "AnnoTrialInternetMenu"),
    (0x50234, bytes.fromhex("4c8d0525030000"), "AnnoTrialInternetMenu"),
    (0x5017C, bytes.fromhex("488d05ad010000"), "AnnoMenuLanServer"),
    (0x5025E, bytes.fromhex("4c8d05cb000000"), "AnnoMenuLanServer"),
    (0x5010C, bytes.fromhex("488d057d030000"), "AnnoMenuLanClient"),
    (0x50249, bytes.fromhex("4c8d0540020000"), "AnnoMenuLanClient"),
    (0x4CD9F, bytes.fromhex("488d053a0a0000"), "AnnoMenuStartWorldLobby"),
    (0x4D5AE, bytes.fromhex("4c8d052b020000"), "AnnoMenuStartWorldLobby"),
)


def callback_load(before: bytes, displacement: bytes) -> bytes | None:
    """Replace only the reviewed RIP-relative callback load, retaining its register."""
    if len(before) != 7 or before not in {site[1] for site in (*MENU_CALLBACKS, *COOP_LOBBY_FLAG_CALLS)}:
        return None
    return before[:1] + b"\x8b" + before[2:3] + displacement
