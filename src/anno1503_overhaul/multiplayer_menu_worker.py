"""Pair an explicit native multiplayer menu request and prepare its in-memory plan."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum
from ipaddress import IPv4Address
from struct import Struct

from .lan_identity import PlayerIdentity, validate_display_name
from .lan_internet import _ipv4, host_internet_group_preflight, host_internet_preflight, join_internet_preflight
from .lan_preflight import DEFAULT_PORT
from .lan_room import LanRoomError, _address, _valid_fingerprint, host_group_preflight, host_preflight, join_preflight


class MenuAction(IntEnum):
    LAN_HOST = 1
    LAN_JOIN = 2
    INTERNET_HOST = 3
    INTERNET_JOIN = 4


_HOST_ACTIONS = (MenuAction.LAN_HOST, MenuAction.INTERNET_HOST)
_LAN_ACTIONS = (MenuAction.LAN_HOST, MenuAction.LAN_JOIN)
LAN_PLAYER_LIMIT = 8
_INTERNET_TICKET_LENGTH = 24
_EXTRA_GUEST = Struct("<4s32s")
_EXTRA_GUEST_BYTES = _EXTRA_GUEST.size * (LAN_PLAYER_LIMIT - 2)
_INTERNET_TICKET_BYTES = _INTERNET_TICKET_LENGTH * (LAN_PLAYER_LIMIT - 1)
_NATIVE_PLAN = Struct(f"<8sI4s4sI32s32sII{_EXTRA_GUEST_BYTES}s{_INTERNET_TICKET_BYTES}s")
NATIVE_PLAN_SIZE = _NATIVE_PLAN.size


@dataclass(frozen=True)
class MenuRequest:
    action: MenuAction
    address: str = ""
    bind_address: str | None = None
    co_op: bool = False
    player_count: int = 2


@dataclass(frozen=True)
class PairedMenuRequest:
    request: MenuRequest
    fingerprint: str
    player: PlayerIdentity
    peer: PlayerIdentity
    local_address: str
    remote_address: str
    extra_guests: tuple[tuple[str, PlayerIdentity], ...] = ()
    internet_tickets: tuple[str, ...] = ()

    def native_plan(self, *, verify_request: Callable[[], None], game_fingerprint: Callable[[], str]) -> bytes:
        """Recheck the same menu action and copy immediately before handing the plan back."""
        _verify_pairing(self.fingerprint, verify_request, game_fingerprint)
        host = self.request.action in _HOST_ACTIONS
        host_player, guest_player = (self.player, self.peer) if host else (self.peer, self.player)
        signature = b"ANNOLAB1" if self.request.action in _LAN_ACTIONS else b"ANNOINET"
        if self.request.co_op:
            signature = b"ANNOCOOP" if self.request.action in _LAN_ACTIONS else b"ANNOCNET"
        elif self.request.player_count > 2:
            signature = b"ANNOROOM" if self.request.action in _LAN_ACTIONS else b"ANNONETR"
        extra = b"".join(_EXTRA_GUEST.pack(IPv4Address(address).packed, _native_name(guest, b"LAN Guest"))
                         for address, guest in self.extra_guests)
        expected_tickets = (self.request.player_count - 1 if host else 1) if signature == b"ANNONETR" else 0
        if len(self.internet_tickets) != expected_tickets or any(
            len(ticket) != _INTERNET_TICKET_LENGTH or any(char not in "0123456789abcdef" for char in ticket)
            for ticket in self.internet_tickets
        ):
            raise LanRoomError("The Internet room admission ticket is invalid.")
        return _NATIVE_PLAN.pack(
            signature,
            1 if host else 2,
            IPv4Address(self.local_address).packed,
            IPv4Address(self.remote_address).packed,
            0,
            _native_name(host_player, b"LAN Host"),
            _native_name(guest_player, b"LAN Guest"),
            self.request.player_count,
            len(self.extra_guests),
            extra,
            "".join(self.internet_tickets).encode("ascii"),
        )


def _native_name(player: PlayerIdentity, fallback: bytes) -> bytes:
    name = validate_display_name(player.display_name)
    return name.encode("ascii") if name.isascii() else fallback


def _menu_fingerprint(verify_request: Callable[[], None], game_fingerprint: Callable[[], str]) -> str:
    verify_request()
    fingerprint = game_fingerprint()
    verify_request()
    if not _valid_fingerprint(fingerprint):
        raise LanRoomError("The selected multiplayer game fingerprint is invalid.")
    return fingerprint


def _verify_pairing(fingerprint: str, verify_request: Callable[[], None], game_fingerprint: Callable[[], str]) -> None:
    if _menu_fingerprint(verify_request, game_fingerprint) != fingerprint:
        raise LanRoomError("The selected multiplayer game files changed during pairing.")


def _lan_address(value: str) -> str:
    address = _address(value)
    if IPv4Address(address).is_loopback:
        raise LanRoomError("Select a private IPv4 address on a LAN interface.")
    return address


def _require_distinct(local: str, remote: str) -> None:
    if local == remote:
        raise LanRoomError("Host and guest require different IPv4 interface addresses.")


def pair_menu_request(
    request: MenuRequest,
    player: PlayerIdentity,
    *,
    verify_request: Callable[[], None],
    game_fingerprint: Callable[[], str],
    on_listening: Callable[[str, int], None] | None = None,
    timeout: float | None = None,
    addon_offer: dict | None = None,
    addon_id: tuple[str, int] | None = None,
    prepare_addon: Callable[[dict], str] | None = None,
) -> PairedMenuRequest:
    """Pair one menu action while its caller verifies the owned process and outstanding request."""
    if not isinstance(request, MenuRequest) or not isinstance(request.action, MenuAction):
        raise LanRoomError("Select a multiplayer host or join action.")
    action = request.action
    if type(request.co_op) is not bool:
        raise LanRoomError("Select a valid co-op mode.")
    count = request.player_count
    if type(count) is not int or not 2 <= count <= LAN_PLAYER_LIMIT:
        raise LanRoomError("Select a player count from two to eight.")
    if count > 2 and request.co_op:
        raise LanRoomError("Shared-flag co-op supports two players.")
    if (action in _HOST_ACTIONS and (addon_id is not None or prepare_addon is not None)
            or action not in _HOST_ACTIONS and addon_offer is not None):
        raise LanRoomError("The host chooses the multiplayer map.")
    hosting_addon = {"addon_offer": addon_offer} if addon_offer is not None else {}
    joining_addon = {"addon_id": addon_id, "prepare_addon": prepare_addon} if addon_id is not None else {}
    fingerprint = _menu_fingerprint(verify_request, game_fingerprint)

    def listening(address: str, port: int) -> None:
        verify_request()
        if on_listening is not None:
            on_listening(address, port)

    bind = request.bind_address if request.bind_address != "" else None
    extras = ()
    tickets = ()
    if action in _LAN_ACTIONS:
        route: tuple[str, str] | None = None

        def record_route(local_address: str, remote_address: str) -> None:
            nonlocal route
            verify_request()
            local, remote = _lan_address(local_address), _lan_address(remote_address)
            _require_distinct(local, remote)
            route = local, remote

        if action == MenuAction.LAN_HOST:
            if request.address != "" or bind is None:
                raise LanRoomError("Choose the local LAN IPv4 interface to host on.")
            local = _lan_address(bind)
            if count > 2:
                guests = host_group_preflight(
                    player, fingerprint, local, DEFAULT_PORT, player_count=count,
                    on_listening=listening, on_route=record_route, timeout=180.0 if timeout is None else timeout,
                    **hosting_addon,
                )
                (remote, peer), *remainder = guests
                extras = tuple(remainder)
                route = local, remote
            else:
                peer = host_preflight(
                    player, fingerprint, local, DEFAULT_PORT, on_listening=listening, on_route=record_route,
                    timeout=60.0 if timeout is None else timeout, **hosting_addon,
                )
        else:
            host = _lan_address(request.address)
            bind = _lan_address(bind) if bind is not None else None
            if bind is not None:
                _require_distinct(bind, host)
            if count > 2:
                joining_addon["wait_for_group"] = True
            peer = join_preflight(
                player, fingerprint, host, DEFAULT_PORT, bind_address=bind,
                on_route=record_route, timeout=(180.0 if count > 2 else 10.0) if timeout is None else timeout,
                **joining_addon,
            )
        if route is None:
            raise LanRoomError("The active LAN route could not be verified.")
        local, remote = route
    elif count > 2 and action == MenuAction.INTERNET_HOST:
        if bind is None:
            raise LanRoomError("Choose the local IPv4 interface and the public IPv4 address.")
        local, guests = host_internet_group_preflight(
            player, fingerprint, bind, request.address, DEFAULT_PORT, player_count=count,
            on_listening=listening, timeout=180.0 if timeout is None else timeout, **hosting_addon,
        )
        (remote, peer, _), *remainder = guests
        extras = tuple((address, identity) for address, identity, _ in remainder)
        tickets = tuple(ticket for _, _, ticket in guests)
    else:
        if action == MenuAction.INTERNET_HOST:
            if bind is None:
                raise LanRoomError("Choose the local IPv4 interface and the public IPv4 address.")
            internet = host_internet_preflight(
                player, fingerprint, bind, request.address, DEFAULT_PORT,
                on_listening=listening, timeout=300.0 if timeout is None else timeout, **hosting_addon,
            )
        else:
            if count > 2:
                joining_addon.update(wait_for_group=True, player_count=count)
            internet = join_internet_preflight(
                player, fingerprint, request.address, DEFAULT_PORT, bind_address=bind,
                timeout=(180.0 if count > 2 else 10.0) if timeout is None else timeout, **joining_addon,
            )
            if count > 2:
                tickets = (internet.ticket or "",)
        local = _ipv4(internet.local_address, interface=True)
        remote = _ipv4(internet.remote_address)
        _require_distinct(local, remote)
        peer = internet.peer

    _verify_pairing(fingerprint, verify_request, game_fingerprint)
    return PairedMenuRequest(request, fingerprint, player, peer, local, remote, extras, tickets)
