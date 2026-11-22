from concurrent.futures import ThreadPoolExecutor
from queue import Queue
import socket
from time import monotonic
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from anno1503_overhaul.lan_identity import PlayerIdentity
from anno1503_overhaul.lan_internet import (
    InternetPreflight,
    host_internet_group_preflight,
    host_internet_preflight,
    join_internet_preflight,
)
from anno1503_overhaul.lan_room import LanRoomError, _exchange_guest, _hello, _receive, _send


HOST = PlayerIdentity(str(uuid4()), "Harbor Master")
GUEST = PlayerIdentity(str(uuid4()), "Navigator")
FINGERPRINT = "a" * 64


class InternetPreflightTests(unittest.TestCase):
    def start_loopback(self, worker, **kwargs):
        listening = Queue()
        host = worker.submit(
            host_internet_preflight, HOST, FINGERPRINT, "127.0.0.1", "127.0.0.1", 0,
            timeout=3, allow_local=True, on_listening=lambda *endpoint: listening.put(endpoint), **kwargs,
        )
        return host, listening.get(timeout=3)

    def test_reports_bound_guest_address_learned_from_tcp(self):
        with ThreadPoolExecutor(max_workers=1) as worker:
            host, (address, port) = self.start_loopback(worker)
            guest = join_internet_preflight(
                GUEST, FINGERPRINT, address, port, bind_address="127.0.0.2", timeout=3, allow_local=True,
            )
            self.assertEqual(guest, InternetPreflight(HOST, "127.0.0.2", "127.0.0.1", "127.0.0.1"))
            self.assertEqual(host.result(timeout=3), InternetPreflight(GUEST, "127.0.0.1", "127.0.0.2", "127.0.0.1"))

    def test_reports_automatic_local_route(self):
        with ThreadPoolExecutor(max_workers=1) as worker:
            host, endpoint = self.start_loopback(worker)
            guest = join_internet_preflight(GUEST, FINGERPRINT, *endpoint, timeout=3, allow_local=True)
            self.assertEqual(guest.local_address, "127.0.0.1")
            self.assertEqual(host.result(timeout=3).remote_address, guest.local_address)

    def test_two_player_host_skips_group_client_and_accepts_ordinary_guest(self):
        with ThreadPoolExecutor(max_workers=1) as worker:
            host, endpoint = self.start_loopback(worker)
            with self.assertRaisesRegex(LanRoomError, "invalid preflight"):
                join_internet_preflight(
                    GUEST, FINGERPRINT, *endpoint, wait_for_group=True, player_count=3,
                    timeout=3, allow_local=True,
                )
            guest = join_internet_preflight(GUEST, FINGERPRINT, *endpoint, timeout=3, allow_local=True)
            self.assertEqual(guest.player_count, 2)
            self.assertIsNone(guest.ticket)
            self.assertEqual(host.result(timeout=3).peer, GUEST)

    def test_fingerprint_mismatch_reaches_both_sides(self):
        with ThreadPoolExecutor(max_workers=1) as worker:
            host, endpoint = self.start_loopback(worker)
            with self.assertRaisesRegex(LanRoomError, "game files differ"):
                join_internet_preflight(GUEST, "b" * 64, *endpoint, timeout=3, allow_local=True)
            with self.assertRaisesRegex(LanRoomError, "game files differ"):
                host.result(timeout=3)

    def test_addon_offer_uses_the_accepted_ipv4_route(self):
        addon = {"feature": "world-settings", "schema": 1, "payload": b"native preview", "artifact_sha256": "b" * 64}
        with ThreadPoolExecutor(max_workers=1) as worker:
            host, (address, port) = self.start_loopback(worker, addon_offer=addon)

            def prepare(offer):
                self.assertEqual(offer, addon)
                return addon["artifact_sha256"]

            guest = join_internet_preflight(
                GUEST, FINGERPRINT, address, port, bind_address="127.0.0.2", timeout=3,
                allow_local=True, addon_id=("world-settings", 1), prepare_addon=prepare,
            )
            self.assertEqual(guest, InternetPreflight(HOST, "127.0.0.2", "127.0.0.1", "127.0.0.1"))
            self.assertEqual(host.result(timeout=3), InternetPreflight(GUEST, "127.0.0.1", "127.0.0.2", "127.0.0.1"))

    def test_public_host_advertisement_is_separate_from_interface(self):
        with (
            patch("anno1503_overhaul.lan_internet.socket.socket") as factory,
            patch("anno1503_overhaul.lan_internet._exchange_host", return_value=GUEST) as exchange,
        ):
            listener = factory.return_value.__enter__.return_value
            private = MagicMock()
            public = MagicMock()
            listener.accept.side_effect = [(private, ("192.168.1.1", 60000)), (public, ("1.1.1.1", 60001))]
            result = host_internet_preflight(HOST, FINGERPRINT, "192.168.1.9", "8.8.8.8", 51503)
            listener.bind.assert_called_once_with(("192.168.1.9", 51503))
            exchange.assert_called_once()
            self.assertIs(exchange.call_args.args[0], public)
            self.assertEqual(result, InternetPreflight(GUEST, "192.168.1.9", "1.1.1.1", "8.8.8.8"))

    def test_hairpin_accepts_only_the_configured_tcp_source(self):
        with (
            patch("anno1503_overhaul.lan_internet.socket.socket") as factory,
            patch("anno1503_overhaul.lan_internet._exchange_host", return_value=GUEST) as exchange,
        ):
            listener = factory.return_value.__enter__.return_value
            unexpected = MagicMock()
            router = MagicMock()
            listener.accept.side_effect = [
                (unexpected, ("192.168.1.2", 60000)),
                (unexpected, ("1.1.1.1", 60001)),
                (router, ("192.168.1.1", 60002)),
            ]
            result = host_internet_preflight(
                HOST, FINGERPRINT, "192.168.1.9", "8.8.8.8", 51503, hairpin_peer="192.168.1.1",
            )
            listener.bind.assert_called_once_with(("192.168.1.9", 51503))
            self.assertEqual(unexpected.__exit__.call_count, 2)
            exchange.assert_called_once()
            self.assertIs(exchange.call_args.args[0], router)
            self.assertEqual(result, InternetPreflight(GUEST, "192.168.1.9", "192.168.1.1", "8.8.8.8"))

    def test_hairpin_rejects_invalid_source_and_private_advertisement_before_networking(self):
        with patch("anno1503_overhaul.lan_internet.socket.socket") as factory:
            for source in ("192.168.1.9", "192.168.1.0/24", "8.8.8.8", "127.0.0.1", "100.64.0.1"):
                with self.subTest(source=source), self.assertRaisesRegex(LanRoomError, "distinct RFC1918 IPv4"):
                    host_internet_preflight(
                        HOST, FINGERPRINT, "192.168.1.9", "8.8.8.8", 51503, hairpin_peer=source,
                    )
            with self.assertRaisesRegex(LanRoomError, "public unicast IPv4"):
                host_internet_preflight(
                    HOST, FINGERPRINT, "192.168.1.9", "192.168.1.9", 51503,
                    allow_local=True, hairpin_peer="192.168.1.1",
                )
            factory.assert_not_called()

    def test_nonpublic_targets_and_ambiguous_binds_are_rejected_before_networking(self):
        with patch("anno1503_overhaul.lan_internet.socket.socket") as factory:
            for target in ("localhost", "::1", "127.0.0.1", "192.168.1.9", "100.64.0.1", "239.1.2.3"):
                with self.subTest(target=target), self.assertRaisesRegex(LanRoomError, "public unicast IPv4"):
                    join_internet_preflight(GUEST, FINGERPRINT, target, 51503)
            with self.assertRaisesRegex(LanRoomError, "IPv4 interface"):
                host_internet_preflight(HOST, FINGERPRINT, "0.0.0.0", "8.8.8.8", 51503)
            factory.assert_not_called()


class InternetGroupTests(unittest.TestCase):
    def start_group(self, worker, count, **kwargs):
        listening = Queue()
        host = worker.submit(
            host_internet_group_preflight, HOST, FINGERPRINT, "127.0.0.1", "127.0.0.1", 0,
            player_count=count, timeout=5, allow_local=True,
            on_listening=lambda *endpoint: listening.put(endpoint), **kwargs,
        )
        return host, listening.get(timeout=3)

    def join_group(self, player, endpoint, *, count=None, **kwargs):
        return join_internet_preflight(
            player, FINGERPRINT, *endpoint, wait_for_group=True, player_count=count,
            timeout=5, allow_local=True, **kwargs,
        )

    def test_eight_players_share_one_source_address_and_receive_distinct_tickets(self):
        guests = [PlayerIdentity(str(uuid4()), GUEST.display_name) for _ in range(7)]
        with ThreadPoolExecutor(max_workers=8) as worker:
            host, endpoint = self.start_group(worker, 8)
            joins = [worker.submit(self.join_group, guest, endpoint, count=8 if index else None)
                     for index, guest in enumerate(guests)]
            local, admissions = host.result(timeout=5)
            self.assertEqual(local, endpoint[0])
            self.assertEqual({source for source, _, _ in admissions}, {local})
            tickets = {guest: ticket for _, guest, ticket in admissions}
            self.assertEqual(set(tickets), set(guests))
            self.assertEqual(len(set(tickets.values())), 7)
            for player, pending in zip(guests, joins, strict=True):
                guest = pending.result(timeout=5)
                self.assertEqual(guest.peer, HOST)
                self.assertEqual(guest.player_count, 8)
                self.assertRegex(guest.ticket, r"\A[0-9a-f]{24}\Z")
                self.assertEqual(guest.ticket, tickets[player])
                self.assertNotIn(guest.ticket, repr(guest))

    def test_invalid_arrivals_and_duplicate_identity_leave_room_open(self):
        second = PlayerIdentity(str(uuid4()), "Trader")
        duplicate = PlayerIdentity(GUEST.player_id, "Different name")
        with ThreadPoolExecutor(max_workers=2) as worker:
            host, endpoint = self.start_group(worker, 3)
            with socket.create_connection(endpoint, timeout=3) as broken:
                broken.sendall(b"\0\0")
            with self.assertRaisesRegex(LanRoomError, "invalid preflight"):
                join_internet_preflight(GUEST, FINGERPRINT, *endpoint, timeout=3, allow_local=True)
            with self.assertRaisesRegex(LanRoomError, "multiplayer options differ"):
                self.join_group(GUEST, endpoint, count=4)
            with self.assertRaisesRegex(LanRoomError, "game files differ"):
                join_internet_preflight(
                    GUEST, "b" * 64, *endpoint, wait_for_group=True, player_count=3,
                    timeout=3, allow_local=True,
                )

            with socket.create_connection(endpoint, timeout=3) as first:
                deadline = monotonic() + 5
                _send(first, dict(kind="internet-group-request", player_count=3), deadline)
                self.assertEqual(_receive(first, "internet-group-accepted", {"player_count"}, deadline)["player_count"], 3)
                self.assertEqual(_exchange_guest(first, _hello(GUEST, FINGERPRINT), deadline), HOST)
                with self.assertRaisesRegex(LanRoomError, "different local player identities"):
                    self.join_group(duplicate, endpoint, count=3)
                self.assertFalse(host.done())
                other = self.join_group(second, endpoint, count=3)
                ready = _receive(first, "room-ready", {"ticket", "player_count"}, deadline)
                self.assertEqual(ready["player_count"], 3)
                self.assertEqual(host.result(timeout=5), (endpoint[0], (
                    (endpoint[0], GUEST, ready["ticket"]),
                    (endpoint[0], second, other.ticket),
                )))

    def test_group_waits_until_each_guest_prepares_the_same_addon(self):
        addon = {"feature": "world-settings", "schema": 1, "payload": b"room preview", "artifact_sha256": "b" * 64}
        second = PlayerIdentity(str(uuid4()), "Trader")
        with ThreadPoolExecutor(max_workers=3) as worker:
            host, endpoint = self.start_group(worker, 3, addon_offer=addon)
            prepared = Queue()

            def prepare(offer):
                prepared.put(offer)
                return addon["artifact_sha256"]

            opts = dict(count=3, addon_id=("world-settings", 1), prepare_addon=prepare)
            first = worker.submit(self.join_group, GUEST, endpoint, **opts)
            self.assertEqual(prepared.get(timeout=3), addon)
            self.assertFalse(first.done())
            self.assertFalse(host.done())
            finish = worker.submit(self.join_group, second, endpoint, **opts)
            self.assertEqual(prepared.get(timeout=3), addon)
            self.assertEqual(first.result(timeout=5).player_count, 3)
            self.assertEqual(finish.result(timeout=5).player_count, 3)
            self.assertEqual(len(host.result(timeout=5)[1]), 2)

    def test_guest_rejects_invalid_ticket_or_count(self):
        target = "127.0.0.1", 51503
        with (
            patch("anno1503_overhaul.lan_internet.socket.socket") as factory,
            patch("anno1503_overhaul.lan_internet._exchange_guest", return_value=HOST),
            patch("anno1503_overhaul.lan_internet._receive") as receive,
        ):
            factory.return_value.__enter__.return_value.getsockname.return_value = target
            for count, ticket in ((4, "a" * 24), (True, "a" * 24), (3, "g" * 24), (3, "a" * 23), (3, None)):
                with self.subTest(count=count, ticket=ticket):
                    receive.side_effect = [dict(player_count=3), dict(player_count=count, ticket=ticket)]
                    with self.assertRaisesRegex(LanRoomError, "invalid Internet room settings"):
                        self.join_group(GUEST, target, count=3)

    def test_group_rejects_invalid_count_and_non_loopback_lab_address_before_networking(self):
        with patch("anno1503_overhaul.lan_internet.socket.socket") as factory:
            with self.assertRaisesRegex(LanRoomError, "three to eight"):
                host_internet_group_preflight(HOST, FINGERPRINT, "127.0.0.1", "127.0.0.1", 0,
                                              player_count=True, allow_local=True)
            with self.assertRaisesRegex(LanRoomError, "loopback testing"):
                self.join_group(GUEST, ("192.168.1.9", 51503), count=3)
            with self.assertRaisesRegex(LanRoomError, "three to eight"):
                join_internet_preflight(GUEST, FINGERPRINT, "127.0.0.1", 51503, player_count=3, allow_local=True)
            factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
