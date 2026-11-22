from struct import unpack
import unittest
from unittest.mock import patch
from uuid import uuid4

from anno1503_overhaul.lan_identity import PlayerIdentity
from anno1503_overhaul.lan_room import LanRoomError
from anno1503_overhaul.lan_trial import DirectLanTrial


class DirectLanTrialTests(unittest.TestCase):
    def test_settings_keep_local_and_peer_in_network_byte_order(self):
        host = DirectLanTrial("host", "192.168.77.21/24", "192.168.77.22")
        guest = DirectLanTrial("guest", "192.168.77.22/24", "192.168.77.21")
        self.assertEqual(unpack("<8sI4s4sI", host.settings()),
                         (b"ANNOLAN1", 1, bytes([192, 168, 77, 21]), bytes([192, 168, 77, 22]), 24))
        self.assertEqual(unpack("<8sI4s4sI", guest.settings()),
                         (b"ANNOLAN1", 2, bytes([192, 168, 77, 22]), bytes([192, 168, 77, 21]), 24))

    def test_only_distinct_unicast_peers_on_a_private_subnet(self):
        for interface, peer in (
            ("192.168.77.21", "192.168.77.22"),
            ("192.168.77.21/24", "192.168.77.21"),
            ("192.168.77.21/24", "192.168.78.22"),
            ("192.168.77.21/24", "192.168.77.255"),
            ("192.168.77.0/24", "192.168.77.22"),
            ("192.168.77.21/16", "192.168.0.0"),
            ("192.168.77.21/15", "192.169.77.22"),
            ("127.0.0.1/24", "127.0.0.2"),
            ("203.0.113.21/24", "203.0.113.22"),
        ):
            with self.subTest(interface=interface, peer=peer), self.assertRaises(ValueError):
                DirectLanTrial("host", interface, peer).settings()

    def test_preflight_binds_the_guest_to_the_planned_interface(self):
        guest = DirectLanTrial("guest", "10.10.0.22/24", "10.10.0.21")
        player = PlayerIdentity(str(uuid4()), "Guest")
        peer = PlayerIdentity(str(uuid4()), "Host")
        with patch("anno1503_overhaul.lan_trial.join_preflight", return_value=peer) as connect:
            settings, other = guest.preflight("f" * 64, player, 51503)
        connect.assert_called_once_with(player, "f" * 64, "10.10.0.21", 51503, bind_address="10.10.0.22")
        self.assertEqual((settings, other), (guest.settings(), peer))

    def test_host_requires_preflight_from_the_selected_guest(self):
        host = DirectLanTrial("host", "10.10.0.21/24", "10.10.0.22")
        player = PlayerIdentity(str(uuid4()), "Host")
        with (
            patch("anno1503_overhaul.lan_trial.host_preflight",
                  side_effect=LanRoomError("rejected")) as listen,
            self.assertRaisesRegex(LanRoomError, "rejected"),
        ):
            host.preflight("f" * 64, player, 51503)
        listen.assert_called_once_with(player, "f" * 64, "10.10.0.21", 51503, on_listening=None,
                                       expected_peer="10.10.0.22")
