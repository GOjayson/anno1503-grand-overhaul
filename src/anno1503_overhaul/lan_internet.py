"""Explicit IPv4 Internet preflight for one player-hosted session."""
from __future__ import annotations

from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass, field
from ipaddress import IPv4Address, IPv4Network
import re
from secrets import token_hex
import socket
from time import monotonic

from .lan_identity import PlayerIdentity
from .lan_room import (
    LanRoomError,
    _ADDON_PEER_TIMEOUT,
    _PEER_TIMEOUT,
    _Reject,
    _check_addon_preparer,
    _checked_addon_offer,
    _deadline,
    _exchange_guest,
    _exchange_host,
    _hello,
    _network_errors,
    _notify_rejection,
    _receive,
    _send,
    _set_timeout,
)


_PRIVATE_INTERFACES = tuple(IPv4Network(cidr) for cidr in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
))


_IETF_PROTOCOL_ASSIGNMENTS = IPv4Network("192.0.0.0/24")
_RETIRED_6TO4_RELAY = IPv4Network("192.88.99.0/24")
_PUBLIC_IETF_ASSIGNMENTS = {IPv4Address("192.0.0.9"), IPv4Address("192.0.0.10")}
_GROUP_REQUEST = "internet-group-request"
_GROUP_ACCEPTED = "internet-group-accepted"
_TICKET_BYTES = 12
_TICKET = re.compile(r"[0-9a-f]{24}")


@dataclass(frozen=True)
class InternetPreflight:
    peer: PlayerIdentity
    local_address: str
    remote_address: str
    advertised_address: str
    ticket: str | None = field(default=None, repr=False)
    player_count: int = 2


def _ipv4(value: str, *, interface: bool = False, allow_local: bool = False) -> str:
    expected = "a local unicast IPv4 interface address" if interface else "a public unicast IPv4 address"
    try:
        if not isinstance(value, str):
            raise ValueError
        ip = IPv4Address(value)
    except ValueError as exc:
        raise LanRoomError(f"Enter {expected}.") from exc
    if not ip.is_multicast and not ip.is_reserved and not ip.is_unspecified:
        publicly_routable = (ip.is_global and ip not in _RETIRED_6TO4_RELAY
                             and (ip not in _IETF_PROTOCOL_ASSIGNMENTS or ip in _PUBLIC_IETF_ASSIGNMENTS))
        if publicly_routable or (allow_local and ip.is_loopback):
            return str(ip)
        if (interface or allow_local) and any(ip in network for network in _PRIVATE_INTERFACES):
            return str(ip)
    raise LanRoomError(f"Enter {expected}.")


def _port(value: int, *, ephemeral: bool = False) -> int:
    if type(value) is not int or not (0 if ephemeral else 1) <= value <= 65535:
        raise LanRoomError("Enter a valid TCP port.")
    return value


def _hairpin_source(value: str, local: str) -> str:
    try:
        address = IPv4Address(value) if isinstance(value, str) else None
    except ValueError:
        address = None
    if (address is None or str(address) == local
            or not any(address in network for network in _PRIVATE_INTERFACES)):
        raise LanRoomError("Enter a distinct RFC1918 IPv4 address for the router's hairpin source.")
    return str(address)


def host_internet_preflight(
    player: PlayerIdentity,
    fingerprint: str,
    bind_address: str,
    advertised_address: str,
    port: int,
    *,
    on_listening=None,
    timeout: float = 60.0,
    allow_local: bool = False,
    hairpin_peer: str | None = None,
    addon_offer: dict | None = None,
) -> InternetPreflight:
    """Bind one interface and report the validated guest's observed TCP source.

    A hairpin test accepts TCP from the configured router source or the
    advertised public address. Skipping other connections preserves the overall
    listening deadline.
    """
    allow_local = allow_local and hairpin_peer is None
    local = _ipv4(bind_address, interface=True, allow_local=allow_local)
    advertised = _ipv4(advertised_address, allow_local=allow_local)
    expected_peers = (
        {_hairpin_source(hairpin_peer, local), advertised} if hairpin_peer is not None else None
    )
    endpoint = local, _port(port, ephemeral=allow_local)
    hello = _hello(player, fingerprint)
    addon_offer = _checked_addon_offer(addon_offer) if addon_offer is not None else None
    deadline = _deadline(timeout)
    peer_timeout = _ADDON_PEER_TIMEOUT if addon_offer is not None else _PEER_TIMEOUT
    with _network_errors(), socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(endpoint)
        listener.listen(1)
        if on_listening is not None:
            on_listening(*listener.getsockname())
        while True:
            _set_timeout(listener, deadline)
            connection, peer_endpoint = listener.accept()
            with connection:
                if expected_peers is not None:
                    if peer_endpoint[0] not in expected_peers:
                        continue
                    peer_address = peer_endpoint[0]
                else:
                    try:
                        peer_address = _ipv4(peer_endpoint[0], allow_local=allow_local)
                    except LanRoomError:
                        continue
                    if peer_address == local and not allow_local:
                        continue
                try:
                    peer = _exchange_host(connection, hello, min(deadline, monotonic() + peer_timeout),
                                          addon_offer=addon_offer)
                except _Reject as rejection:
                    if rejection.code != "protocol":
                        raise
                    # Malformed connections do not consume the game seat.
                    continue
                except (TimeoutError, ConnectionError):
                    continue
                return InternetPreflight(peer, local, peer_address, advertised)


def _valid_group_count(value: object) -> bool:
    return type(value) is int and 3 <= value <= 8


def _group_address(value: str, *, interface: bool = False, allow_local: bool = False) -> str:
    address = _ipv4(value, interface=interface, allow_local=allow_local)
    if allow_local and not IPv4Address(address).is_loopback:
        raise LanRoomError("Internet group loopback testing requires a loopback IPv4 address.")
    return address


def host_internet_group_preflight(
    player: PlayerIdentity,
    fingerprint: str,
    bind_address: str,
    advertised_address: str,
    port: int,
    *,
    player_count: int,
    on_listening: Callable[[str, int], None] | None = None,
    timeout: float = 180.0,
    allow_local: bool = False,
    addon_offer: dict | None = None,
) -> tuple[str, tuple[tuple[str, PlayerIdentity, str], ...]]:
    """Verify identities and issue a ticket for each Internet guest's native connection."""
    if not _valid_group_count(player_count):
        raise LanRoomError("An Internet group supports three to eight players including the host.")
    local = _group_address(bind_address, interface=True, allow_local=allow_local)
    _group_address(advertised_address, allow_local=allow_local)
    endpoint = local, _port(port, ephemeral=allow_local)
    hello = _hello(player, fingerprint)
    addon_offer = _checked_addon_offer(addon_offer) if addon_offer is not None else None
    deadline = _deadline(timeout)
    peer_timeout = _ADDON_PEER_TIMEOUT if addon_offer is not None else _PEER_TIMEOUT
    wanted = player_count - 1
    known_ids = {player.player_id}
    verified: list[tuple[str, PlayerIdentity, socket.socket]] = []
    with _network_errors(), ExitStack() as admitted, socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(endpoint)
        listener.listen(wanted)
        if on_listening is not None:
            on_listening(*listener.getsockname())
        while len(verified) < wanted:
            _set_timeout(listener, deadline)
            connection, peer_endpoint = listener.accept()
            with ExitStack() as candidate:
                candidate.enter_context(connection)
                try:
                    remote = _group_address(peer_endpoint[0], allow_local=allow_local)
                    if remote == local and not allow_local:
                        continue
                    exchange_deadline = min(deadline, monotonic() + peer_timeout)
                    with _notify_rejection(connection, exchange_deadline):
                        request = _receive(connection, _GROUP_REQUEST, {"player_count"}, exchange_deadline)
                        requested = request["player_count"]
                        if requested is not None and not _valid_group_count(requested):
                            raise _Reject("protocol")
                        if requested is not None and requested != player_count:
                            raise _Reject("fingerprint")
                        _send(connection, dict(kind=_GROUP_ACCEPTED, player_count=player_count), exchange_deadline)
                    peer = _exchange_host(connection, hello, exchange_deadline,
                                          addon_offer=addon_offer, known_ids=known_ids)
                except (LanRoomError, OSError):
                    continue
                known_ids.add(peer.player_id)
                verified.append((remote, peer, connection))
                admitted.enter_context(candidate.pop_all())

        listener.close()
        tickets = tuple(token_hex(_TICKET_BYTES) for _ in verified)
        if len(set(tickets)) != wanted:
            raise LanRoomError("Could not allocate distinct Internet room tickets.")
        for (_, _, connection), ticket in zip(verified, tickets, strict=True):
            _send(connection, dict(kind="room-ready", player_count=player_count, ticket=ticket), deadline)
        return local, tuple((address, peer, ticket) for (address, peer, _), ticket
                            in zip(verified, tickets, strict=True))


def join_internet_preflight(
    player: PlayerIdentity,
    fingerprint: str,
    address: str,
    port: int,
    *,
    bind_address: str | None = None,
    timeout: float = 10.0,
    allow_local: bool = False,
    addon_id: tuple[str, int] | None = None,
    prepare_addon: Callable[[dict], str] | None = None,
    wait_for_group: bool = False,
    player_count: int | None = None,
) -> InternetPreflight:
    """Connect directly to a known host and report the IPv4 route selected locally."""
    if type(wait_for_group) is not bool or (player_count is not None and
            (not wait_for_group or not _valid_group_count(player_count))):
        raise LanRoomError("Select three to eight players for an Internet group.")
    route_address = _group_address if wait_for_group else _ipv4
    advertised = route_address(address, allow_local=allow_local)
    endpoint = advertised, _port(port)
    local = route_address(bind_address, interface=True, allow_local=allow_local) if bind_address is not None else None
    hello = _hello(player, fingerprint)
    _check_addon_preparer(addon_id, prepare_addon)
    deadline = _deadline(timeout)
    with _network_errors(), socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        if local is not None:
            connection.bind((local, 0))
        _set_timeout(connection, deadline)
        connection.connect(endpoint)
        local_address = route_address(connection.getsockname()[0], interface=True, allow_local=allow_local)
        if wait_for_group:
            _send(connection, dict(kind=_GROUP_REQUEST, player_count=player_count), deadline)
            accepted = _receive(connection, _GROUP_ACCEPTED, {"player_count"}, deadline)
            count = accepted["player_count"]
            if not _valid_group_count(count) or (player_count is not None and count != player_count):
                raise LanRoomError("The host returned invalid Internet room settings.")
        peer = _exchange_guest(connection, hello, deadline, addon_id=addon_id, prepare_addon=prepare_addon)
        if not wait_for_group:
            return InternetPreflight(peer, local_address, advertised, advertised)
        ready = _receive(connection, "room-ready", {"player_count", "ticket"}, deadline)
        ticket = ready["ticket"]
        if (type(ready["player_count"]) is not int or ready["player_count"] != count
                or not isinstance(ticket, str) or _TICKET.fullmatch(ticket) is None):
            raise LanRoomError("The host returned invalid Internet room settings.")
        return InternetPreflight(peer, local_address, advertised, advertised, ticket=ticket, player_count=count)
