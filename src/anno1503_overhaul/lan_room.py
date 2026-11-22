"""Private IPv4 preflight for a player-hosted session."""

from base64 import b64decode, b64encode
from collections.abc import Callable
from contextlib import ExitStack, contextmanager
from ipaddress import IPv4Address, IPv4Network
import json
import re
import socket
from struct import Struct
from time import monotonic

from .lan_identity import PlayerIdentity, validate_display_name, validate_player_id


class LanRoomError(RuntimeError):
    """The peer preflight could not be completed."""


_VERSION = 1
_HEADER = Struct("!H")
_MAX_FRAME_SIZE = 1024
_MAX_ADDON_PAYLOAD = 16 * 1024
_MAX_ADDON_BASE64 = ((_MAX_ADDON_PAYLOAD + 2) // 3) * 4
_MAX_ADDON_FRAME_SIZE = _MAX_ADDON_BASE64 + _MAX_FRAME_SIZE
_ADDON_FIELDS = {"feature", "schema", "payload", "artifact_sha256"}
_PEER_TIMEOUT = 10.0
_ADDON_PEER_TIMEOUT = 15.0
_PRIVATE_NETWORKS = tuple(IPv4Network(net) for net in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8",
))
_REJECTIONS = {
    "protocol": "The other player sent invalid preflight data or disconnected.",
    "fingerprint": "The selected game files differ, or the multiplayer options differ.",
    "identity": "Host and guest must use different local player identities.",
    "addon": "The multiplayer add-on offer is invalid or too large.",
    "addon-selection": "Make the guest's World Settings selection match the host's choice.",
    "addon-feature": "The players selected different multiplayer add-ons or schemas.",
    "addon-digest": "The prepared multiplayer artifact differs from the host's artifact.",
    "addon-prepare": "The guest could not prepare the multiplayer add-on.",
}


class _Reject(LanRoomError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(_REJECTIONS[code])


def _address(value: str) -> str:
    try:
        if not isinstance(value, str):
            raise ValueError
        ip = IPv4Address(value)
    except ValueError as exc:
        raise LanRoomError("Enter a private LAN or loopback IPv4 address.") from exc
    if not any(ip in network for network in _PRIVATE_NETWORKS):
        raise LanRoomError("Enter a private LAN or loopback IPv4 address.")
    return str(ip)


def _deadline(timeout: float) -> float:
    if type(timeout) not in (int, float) or not 0 < timeout <= 300:
        raise LanRoomError("The preflight timeout must be greater than zero and at most 300 seconds.")
    return monotonic() + timeout


def _valid_fingerprint(value: str) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _hello(player: PlayerIdentity, fingerprint: str) -> dict:
    if not isinstance(player, PlayerIdentity):
        raise LanRoomError("Set a local player identity before connecting.")
    try:
        player_id = validate_player_id(player.player_id)
        name = validate_display_name(player.display_name)
    except ValueError as exc:
        raise LanRoomError(str(exc)) from exc
    if not _valid_fingerprint(fingerprint):
        raise LanRoomError("The preflight fingerprint must be a lowercase SHA-256 digest.")
    return dict(kind="hello", player_id=player_id, display_name=name,
                fingerprint=fingerprint)


def _endpoint(address: str, port: int, *, allow_zero: bool = False) -> tuple[str, int]:
    if type(port) is not int or not (0 if allow_zero else 1) <= port <= 65535:
        raise LanRoomError("Enter a valid TCP port.")
    return _address(address), port


def _set_timeout(connection: socket.socket, deadline: float) -> None:
    remaining = deadline - monotonic()
    if remaining <= 0:
        raise TimeoutError
    connection.settimeout(remaining)


def _read_exact(connection: socket.socket, count: int, deadline: float) -> bytes:
    data = bytearray()
    while len(data) < count:
        _set_timeout(connection, deadline)
        received = connection.recv(count - len(data))
        if not received:
            raise _Reject("protocol")
        data.extend(received)
    return bytes(data)


def _json_object(pairs: list) -> dict:
    fields = {}
    for name, value in pairs:
        if name in fields:
            raise _Reject("protocol")
        fields[name] = value
    return fields


def _message_bytes(message: dict, *, limit: int) -> bytes:
    try:
        body = json.dumps(dict(version=_VERSION, **message), separators=(",", ":")).encode("utf-8")
    except (ValueError, RecursionError) as exc:
        raise _Reject("protocol") from exc
    if len(body) > limit:
        raise _Reject("protocol")
    return body


def _send(connection: socket.socket, message: dict, deadline: float, *, limit: int = _MAX_FRAME_SIZE) -> None:
    body = _message_bytes(message, limit=limit)
    _set_timeout(connection, deadline)
    connection.sendall(_HEADER.pack(len(body)) + body)


def _receive(connection: socket.socket, kind: str, fields: set[str], deadline: float, *,
             limit: int = _MAX_FRAME_SIZE, other_mode: tuple[str, set[str]] | None = None) -> dict:
    (size,) = _HEADER.unpack(_read_exact(connection, _HEADER.size, deadline))
    if not 1 <= size <= limit:
        raise _Reject("protocol")
    body = _read_exact(connection, size, deadline)
    try:
        message = json.loads(body.decode("utf-8"), object_pairs_hook=_json_object)
    except (ValueError, RecursionError) as exc:
        raise _Reject("protocol") from exc
    if not isinstance(message, dict) or type(message.get("version")) is not int or message["version"] != _VERSION:
        raise _Reject("protocol")
    if message.keys() == {"version", "kind", "code"} and message["kind"] == "reject":
        code = message["code"]
        if isinstance(code, str) and code in _REJECTIONS:
            raise LanRoomError(_REJECTIONS[code])
    if other_mode is not None:
        other_kind, other_fields = other_mode
        if message.get("kind") == other_kind and message.keys() == other_fields | {"version", "kind"}:
            raise _Reject("addon-selection")
    if message.keys() != fields | {"version", "kind"} or message["kind"] != kind:
        raise _Reject("protocol")
    return message


def _receive_player(connection: socket.socket, local: dict, deadline: float) -> PlayerIdentity:
    message = _receive(connection, "hello", {"player_id", "display_name", "fingerprint"}, deadline)
    try:
        player_id = validate_player_id(message["player_id"])
        name = validate_display_name(message["display_name"])
    except ValueError as exc:
        raise _Reject("protocol") from exc
    digest = message["fingerprint"]
    if name != message["display_name"] or not _valid_fingerprint(digest):
        raise _Reject("protocol")
    if player_id == local["player_id"]:
        raise _Reject("identity")
    if digest != local["fingerprint"]:
        raise _Reject("fingerprint")
    return PlayerIdentity(player_id, name)


def _checked_addon_id(addon_id: tuple[str, int]) -> tuple[str, int]:
    if type(addon_id) is not tuple or len(addon_id) != 2:
        raise _Reject("addon")
    feature, schema = addon_id
    if (not isinstance(feature, str) or not 1 <= len(feature) <= 64
            or re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", feature) is None
            or type(schema) is not int or not 1 <= schema <= 65535):
        raise _Reject("addon")
    return addon_id


def _checked_addon_offer(offer: dict) -> dict:
    if type(offer) is not dict or offer.keys() != _ADDON_FIELDS:
        raise _Reject("addon")
    checked = dict(offer)
    _checked_addon_id((checked["feature"], checked["schema"]))
    payload = checked["payload"]
    if (type(payload) is not bytes or len(payload) > _MAX_ADDON_PAYLOAD
            or not _valid_fingerprint(checked["artifact_sha256"])):
        raise _Reject("addon")
    return checked


def _decode_addon_payload(encoded: str) -> bytes:
    if not isinstance(encoded, str) or len(encoded) > _MAX_ADDON_BASE64:
        raise _Reject("addon")
    try:
        payload = b64decode(encoded, validate=True)
    except ValueError as exc:
        raise _Reject("addon") from exc
    if len(payload) > _MAX_ADDON_PAYLOAD or b64encode(payload).decode("ascii") != encoded:
        raise _Reject("addon")
    return payload


def _check_addon_preparer(addon_id: tuple[str, int] | None, prepare_addon: Callable[[dict], str] | None) -> None:
    if addon_id is not None or prepare_addon is not None:
        if addon_id is None:
            raise LanRoomError("Select the multiplayer add-on and schema to prepare.")
        _checked_addon_id(addon_id)
        if not callable(prepare_addon):
            raise LanRoomError("Set a callback to prepare the offered multiplayer add-on.")


@contextmanager
def _network_errors():
    try:
        yield
    except TimeoutError as exc:
        raise LanRoomError("The multiplayer preflight timed out.") from exc
    except OSError as exc:
        raise LanRoomError(f"The multiplayer preflight connection failed: {exc}") from exc


@contextmanager
def _notify_rejection(connection: socket.socket, deadline: float):
    try:
        yield
    except _Reject as rejection:
        try:
            _send(connection, dict(kind="reject", code=rejection.code), deadline)
        except OSError:
            pass
        raise


def _exchange_host(connection: socket.socket, hello: dict, deadline: float, *,
                   addon_offer: dict | None = None, known_ids: set[str] | None = None) -> PlayerIdentity:
    with _notify_rejection(connection, deadline):
        remote = _receive_player(connection, hello, deadline)
        if known_ids is not None and remote.player_id in known_ids:
            raise _Reject("identity")
        _send(connection, hello, deadline)
        accepted = dict(kind="accepted")
        addon_request = "addon-request", {"feature", "schema"}
        confirm = "confirm", set()
        if addon_offer is None:
            _receive(connection, *confirm, deadline, other_mode=addon_request)
        else:
            request = _receive(connection, *addon_request, deadline, other_mode=confirm)
            requested = _checked_addon_id((request["feature"], request["schema"]))
            if requested != (addon_offer["feature"], addon_offer["schema"]):
                raise _Reject("addon-feature")
            wire = dict(addon_offer, kind="addon", payload=b64encode(addon_offer["payload"]).decode("ascii"))
            _send(connection, wire, deadline, limit=_MAX_ADDON_FRAME_SIZE)
            ready = _receive(connection, "addon-ready", {"artifact_sha256"}, deadline)
            expected = addon_offer["artifact_sha256"]
            if ready["artifact_sha256"] != expected:
                raise _Reject("addon-digest")
            accepted["artifact_sha256"] = expected
        _send(connection, accepted, deadline)
        if addon_offer is not None:
            confirmation = _receive(connection, "addon-confirm", {"artifact_sha256"}, deadline)
            if confirmation["artifact_sha256"] != addon_offer["artifact_sha256"]:
                raise _Reject("addon-digest")
        return remote


def _exchange_guest(connection: socket.socket, hello: dict, deadline: float, *,
                    addon_id: tuple[str, int] | None = None,
                    prepare_addon: Callable[[dict], str] | None = None) -> PlayerIdentity:
    with _notify_rejection(connection, deadline):
        _send(connection, hello, deadline)
        remote = _receive_player(connection, hello, deadline)
        if addon_id is None:
            _send(connection, dict(kind="confirm"), deadline)
            _receive(connection, "accepted", set(), deadline)
        else:
            feature, schema = addon_id
            _send(connection, dict(kind="addon-request", feature=feature, schema=schema), deadline)
            message = _receive(connection, "addon", _ADDON_FIELDS, deadline, limit=_MAX_ADDON_FRAME_SIZE)
            offered = _checked_addon_id((message["feature"], message["schema"]))
            if offered != addon_id:
                raise _Reject("addon-feature")
            offer = _checked_addon_offer({"feature": feature, "schema": schema,
                                         "payload": _decode_addon_payload(message["payload"]),
                                         "artifact_sha256": message["artifact_sha256"]})
            expected = offer["artifact_sha256"]
            try:
                digest = prepare_addon(offer)
            except Exception as exc:
                raise _Reject("addon-prepare") from exc
            if not _valid_fingerprint(digest) or digest != expected:
                raise _Reject("addon-digest")
            _send(connection, dict(kind="addon-ready", artifact_sha256=digest), deadline)
            accepted = _receive(connection, "accepted", {"artifact_sha256"}, deadline)
            if accepted["artifact_sha256"] != expected:
                raise _Reject("addon-digest")
            _send(connection, dict(kind="addon-confirm", artifact_sha256=expected), deadline)
        return remote


def host_preflight(player: PlayerIdentity, fingerprint: str, address: str, port: int, *,
                   timeout: float = 60.0, on_listening=None,
                   expected_peer: str | None = None, addon_offer: dict | None = None,
                   on_route: Callable[[str, str], None] | None = None) -> PlayerIdentity:
    """Listen for one guest and return their validated identity.

    If supplied, on_route receives the local and remote IPv4 addresses before the identity exchange.
    """
    endpoint = _endpoint(address, port, allow_zero=True)
    expected = _address(expected_peer) if expected_peer is not None else None
    hello = _hello(player, fingerprint)
    addon_offer = _checked_addon_offer(addon_offer) if addon_offer is not None else None
    deadline = _deadline(timeout)
    with _network_errors(), socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(endpoint)
        listener.listen(1)
        if on_listening is not None:
            on_listening(*listener.getsockname())
        _set_timeout(listener, deadline)
        connection, peer = listener.accept()
        with connection:
            listener.close()
            remote_address = _address(peer[0])
            if expected is not None and remote_address != expected:
                raise LanRoomError("The preflight connection came from a different IPv4 address.")
            if on_route is not None:
                on_route(connection.getsockname()[0], remote_address)
            peer_timeout = _ADDON_PEER_TIMEOUT if addon_offer is not None else _PEER_TIMEOUT
            deadline = min(deadline, monotonic() + peer_timeout)
            return _exchange_host(connection, hello, deadline, addon_offer=addon_offer)


def join_preflight(player: PlayerIdentity, fingerprint: str, address: str, port: int, *,
                   timeout: float = 10.0, bind_address: str | None = None,
                   addon_id: tuple[str, int] | None = None,
                   prepare_addon: Callable[[dict], str] | None = None,
                   on_route: Callable[[str, str], None] | None = None,
                   wait_for_group: bool = False) -> PlayerIdentity:
    """Connect to the host and return their validated identity.

    If supplied, on_route receives the local and remote IPv4 addresses before the identity exchange.
    """
    endpoint = _endpoint(address, port)
    local = _address(bind_address) if bind_address is not None else None
    hello = _hello(player, fingerprint)
    _check_addon_preparer(addon_id, prepare_addon)
    deadline = _deadline(timeout)
    with _network_errors(), socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        if local is not None:
            connection.bind((local, 0))
        _set_timeout(connection, deadline)
        connection.connect(endpoint)
        if on_route is not None:
            on_route(connection.getsockname()[0], endpoint[0])
        peer = _exchange_guest(connection, hello, deadline, addon_id=addon_id, prepare_addon=prepare_addon)
        if wait_for_group:
            _receive(connection, "room-ready", set(), deadline)
        return peer


def host_group_preflight(player: PlayerIdentity, fingerprint: str, address: str, port: int, *,
                         player_count: int, timeout: float = 180.0, on_listening=None,
                         addon_offer: dict | None = None,
                         on_route: Callable[[str, str], None] | None = None
                         ) -> tuple[tuple[str, PlayerIdentity], ...]:
    """Verify each guest and release them to native discovery as a complete room."""
    if type(player_count) is not int or not 3 <= player_count <= 8:
        raise LanRoomError("A LAN group supports three to eight players including the host.")
    endpoint = _endpoint(address, port, allow_zero=True)
    hello = _hello(player, fingerprint)
    addon_offer = _checked_addon_offer(addon_offer) if addon_offer is not None else None
    deadline = _deadline(timeout)
    peer_timeout = _ADDON_PEER_TIMEOUT if addon_offer is not None else _PEER_TIMEOUT
    guests = {}
    identities = {player.player_id}
    connections = []
    with _network_errors(), ExitStack() as resources:
        listener = resources.enter_context(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
        listener.bind(endpoint)
        listener.listen(player_count - 1)
        if on_listening is not None:
            on_listening(*listener.getsockname())
        for _ in range(player_count - 1):
            _set_timeout(listener, deadline)
            connection, peer = listener.accept()
            resources.enter_context(connection)
            remote = _address(peer[0])
            if on_route is not None:
                on_route(connection.getsockname()[0], remote)
            exchange_deadline = min(deadline, monotonic() + peer_timeout)
            if remote in guests:
                with _notify_rejection(connection, exchange_deadline):
                    raise _Reject("identity")
            identity = _exchange_host(connection, hello, exchange_deadline,
                                      addon_offer=addon_offer, known_ids=identities)
            guests[remote] = identity
            identities.add(identity.player_id)
            connections.append(connection)
        listener.close()
        for connection in connections:
            _send(connection, dict(kind="room-ready"), deadline)
    return tuple(guests.items())
