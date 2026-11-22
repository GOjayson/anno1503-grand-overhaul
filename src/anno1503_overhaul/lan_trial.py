"""Prepare explicit IPv4 settings for the isolated native LAN trial."""
from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Interface, IPv4Network
from struct import Struct

from .lan_identity import PlayerIdentity
from .lan_room import host_preflight, join_preflight


_FORMAT = Struct("<8sI4s4sI")
_SIGNATURE = b"ANNOLAN1"
_ROLES = {"host": 1, "guest": 2}
_LAN_NETWORKS = tuple(IPv4Network(block) for block in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))


@dataclass(frozen=True)
class DirectLanTrial:
    role: str
    interface: str
    peer: str

    def settings(self) -> bytes:
        """Use two distinct, unicast addresses on the selected private subnet."""
        if (not isinstance(self.role, str) or self.role not in _ROLES
                or not isinstance(self.interface, str) or "/" not in self.interface
                or not isinstance(self.peer, str)):
            raise ValueError("Select host or guest and specify the local IPv4 interface with its prefix.")
        local = IPv4Interface(self.interface)
        peer = IPv4Address(self.peer)
        network = local.network
        if not any(network.subnet_of(block) for block in _LAN_NETWORKS):
            raise ValueError("Select a subnet in the private IPv4 ranges.")
        if (peer not in network or peer == local.ip or network.prefixlen > 30
                or {local.ip, peer} & {network.network_address, network.broadcast_address}):
            raise ValueError("The host and the guest must have distinct unicast addresses on the same subnet.")
        return _FORMAT.pack(_SIGNATURE, _ROLES[self.role], local.ip.packed, peer.packed, network.prefixlen)

    def preflight(self, fingerprint: str, player: PlayerIdentity, port: int, *, on_listening=None, timeout=None):
        """Return native settings only after the intended stock-game peer passes."""
        settings = self.settings()
        _, _, local_ip, peer_ip, _ = _FORMAT.unpack(settings)
        local = str(IPv4Address(local_ip))
        peer = str(IPv4Address(peer_ip))
        timing = {"timeout": timeout} if timeout is not None else {}
        if self.role == "host":
            other = host_preflight(
                player, fingerprint, local, port, on_listening=on_listening, expected_peer=peer, **timing,
            )
        else:
            other = join_preflight(player, fingerprint, peer, port, bind_address=local, **timing)
        return settings, other
