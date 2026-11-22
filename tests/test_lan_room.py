from concurrent.futures import ThreadPoolExecutor
from queue import Queue
import socket
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from anno1503_overhaul import lan_room
from anno1503_overhaul.lan_identity import PlayerIdentity
from anno1503_overhaul.lan_room import LanRoomError, host_preflight, join_preflight


HOST = PlayerIdentity(str(uuid4()), "Host")
GUEST = PlayerIdentity(str(uuid4()), "Éléonore")
FINGERPRINT = "a" * 64
ADDON_ID = ("world-settings", 1)
ADDON = {"feature": ADDON_ID[0], "schema": ADDON_ID[1], "payload": b"native preview", "artifact_sha256": "b" * 64}


class LanRoomTests(unittest.TestCase):
    def start_host(self, worker, **kwargs):
        listening = Queue()
        result = worker.submit(
            host_preflight, HOST, FINGERPRINT, "127.0.0.1", 0, timeout=3,
            on_listening=lambda address, port: listening.put((address, port)), **kwargs,
        )
        return result, listening.get(timeout=3)

    def test_two_peers_exchange_identities(self):
        with ThreadPoolExecutor(max_workers=1) as worker:
            result, (address, port) = self.start_host(worker)
            self.assertEqual(address, "127.0.0.1")
            self.assertGreater(port, 0)
            self.assertEqual(join_preflight(GUEST, FINGERPRINT, address, port, timeout=3), HOST)
            self.assertEqual(result.result(timeout=3), GUEST)

    def test_group_pairs_seven_guests_and_releases_only_after_all_prepare(self):
        guests = {f"127.0.0.{index}": PlayerIdentity(str(uuid4()), f"Guest {index}") for index in range(2, 9)}
        listening, prepared = Queue(), Queue()
        with ThreadPoolExecutor(max_workers=8) as worker:
            host = worker.submit(lan_room.host_group_preflight, HOST, FINGERPRINT, "127.0.0.1", 0,
                                 player_count=8, timeout=5, addon_offer=ADDON,
                                 on_listening=lambda *endpoint: listening.put(endpoint))
            endpoint = listening.get(timeout=5)

            def prepare(offer):
                self.assertEqual(offer, ADDON)
                prepared.put(True)
                return offer["artifact_sha256"]

            def submit(address, guest):
                return worker.submit(join_preflight, guest, FINGERPRINT, *endpoint, timeout=5,
                                     bind_address=address, addon_id=ADDON_ID, prepare_addon=prepare, wait_for_group=True)

            pending = [submit(address, guests[address]) for address in tuple(guests)[:-1]]
            for _ in pending:
                prepared.get(timeout=5)
            self.assertFalse(host.done())
            self.assertTrue(all(not guest.done() for guest in pending))
            pending.append(submit("127.0.0.8", guests["127.0.0.8"]))
            self.assertEqual(dict(host.result(timeout=5)), guests)
            self.assertTrue(all(guest.result(timeout=5) == HOST for guest in pending))

    def test_selected_guest_connects_from_its_bound_address(self):
        with ThreadPoolExecutor(max_workers=1) as worker:
            host_route, guest_route = Mock(), Mock()
            result, (address, port) = self.start_host(worker, expected_peer="127.0.0.2", on_route=host_route)
            self.assertEqual(join_preflight(
                GUEST, FINGERPRINT, address, port, timeout=3, bind_address="127.0.0.2", on_route=guest_route,
            ), HOST)
            self.assertEqual(result.result(timeout=3), GUEST)
            host_route.assert_called_once_with("127.0.0.1", "127.0.0.2")
            guest_route.assert_called_once_with("127.0.0.2", "127.0.0.1")

    def test_host_rejects_a_connection_from_a_different_address(self):
        with ThreadPoolExecutor(max_workers=1) as worker:
            result, endpoint = self.start_host(worker, expected_peer="127.0.0.2")
            with socket.create_connection(endpoint, timeout=3):
                with self.assertRaisesRegex(LanRoomError, "different IPv4 address"):
                    result.result(timeout=3)

    def test_both_peers_reject_a_fingerprint_mismatch(self):
        with ThreadPoolExecutor(max_workers=1) as worker:
            result, (address, port) = self.start_host(worker)
            with self.assertRaisesRegex(LanRoomError, "game files differ"):
                join_preflight(GUEST, "f" * 64, address, port, timeout=3)
            with self.assertRaisesRegex(LanRoomError, "game files differ"):
                result.result(timeout=3)

    def test_both_peers_reject_reusing_the_host_identity(self):
        guest = PlayerIdentity(HOST.player_id, "Different name")
        with ThreadPoolExecutor(max_workers=1) as worker:
            result, (address, port) = self.start_host(worker)
            with self.assertRaisesRegex(LanRoomError, "different local player identities"):
                join_preflight(guest, FINGERPRINT, address, port, timeout=3)
            with self.assertRaisesRegex(LanRoomError, "different local player identities"):
                result.result(timeout=3)

    def test_host_rejects_oversized_frame_before_reading_its_body(self):
        with ThreadPoolExecutor(max_workers=1) as worker:
            result, endpoint = self.start_host(worker)
            with socket.create_connection(endpoint, timeout=3) as connection:
                connection.sendall((1025).to_bytes(2, "big"))
                with self.assertRaisesRegex(LanRoomError, "invalid preflight data"):
                    result.result(timeout=3)

    def test_addon_offer_accepts_full_binary_payload_and_requires_guest_preparation(self):
        offer = dict(ADDON, payload=bytes(range(256)) * 64)
        with ThreadPoolExecutor(max_workers=1) as worker:
            result, endpoint = self.start_host(worker, addon_offer=offer)

            def prepare(received):
                self.assertEqual(received, offer)
                self.assertFalse(result.done())
                return offer["artifact_sha256"]

            self.assertEqual(join_preflight(GUEST, FINGERPRINT, *endpoint, timeout=3,
                                            addon_id=ADDON_ID, prepare_addon=prepare), HOST)
            self.assertEqual(result.result(timeout=3), GUEST)

    def test_artifact_mismatch_reaches_both_peers(self):
        with ThreadPoolExecutor(max_workers=1) as worker:
            result, endpoint = self.start_host(worker, addon_offer=ADDON)
            with self.assertRaisesRegex(LanRoomError, "prepared multiplayer artifact differs"):
                join_preflight(GUEST, FINGERPRINT, *endpoint, timeout=3, addon_id=ADDON_ID,
                               prepare_addon=lambda _: "f" * 64)
            with self.assertRaisesRegex(LanRoomError, "prepared multiplayer artifact differs"):
                result.result(timeout=3)

    def test_addon_prepare_failure_does_not_send_exception_details(self):
        with ThreadPoolExecutor(max_workers=1) as worker:
            result, endpoint = self.start_host(worker, addon_offer=ADDON)
            prepare = Mock(side_effect=OSError("private game path"))
            with self.assertRaisesRegex(LanRoomError, "guest could not prepare"):
                join_preflight(GUEST, FINGERPRINT, *endpoint, timeout=3, addon_id=ADDON_ID, prepare_addon=prepare)
            with self.assertRaisesRegex(LanRoomError, "guest could not prepare") as outcome:
                result.result(timeout=3)
            self.assertNotIn("private game path", str(outcome.exception))

    def test_matching_base_inputs_are_required_before_addon_preparation(self):
        with ThreadPoolExecutor(max_workers=1) as worker:
            result, endpoint = self.start_host(worker, addon_offer=ADDON)
            prepare = Mock()
            with self.assertRaisesRegex(LanRoomError, "game files differ"):
                join_preflight(GUEST, "f" * 64, *endpoint, timeout=3, addon_id=ADDON_ID, prepare_addon=prepare)
            with self.assertRaisesRegex(LanRoomError, "game files differ"):
                result.result(timeout=3)
            prepare.assert_not_called()

    def test_stock_and_addon_modes_cannot_pair(self):
        for host_addon, guest_addon in ((ADDON, None), (None, Mock())):
            with self.subTest(host_addon=host_addon is not None), ThreadPoolExecutor(max_workers=1) as worker:
                result, endpoint = self.start_host(worker, addon_offer=host_addon)
                addon_id = ADDON_ID if guest_addon is not None else None
                with self.assertRaisesRegex(LanRoomError, "World Settings selection match the host"):
                    join_preflight(GUEST, FINGERPRINT, *endpoint, timeout=3, addon_id=addon_id, prepare_addon=guest_addon)
                with self.assertRaisesRegex(LanRoomError, "World Settings selection match the host"):
                    result.result(timeout=3)
                if guest_addon is not None:
                    guest_addon.assert_not_called()

    def test_wrong_feature_or_schema_is_rejected_before_preparation(self):
        for addon_id in (("different-feature", 1), ("world-settings", 2)):
            with self.subTest(addon_id=addon_id), ThreadPoolExecutor(max_workers=1) as worker:
                result, endpoint = self.start_host(worker, addon_offer=ADDON)
                prepare = Mock()
                with self.assertRaisesRegex(LanRoomError, "different multiplayer add-ons or schemas"):
                    join_preflight(GUEST, FINGERPRINT, *endpoint, timeout=3, addon_id=addon_id, prepare_addon=prepare)
                with self.assertRaisesRegex(LanRoomError, "different multiplayer add-ons or schemas"):
                    result.result(timeout=3)
                prepare.assert_not_called()

    def test_rejects_unbounded_or_malformed_addon_offers_before_networking(self):
        invalid = [
            dict(ADDON, artifact_sha256="wrong"),
            dict(ADDON, extra=True),
            dict(ADDON, schema=False),
            dict(ADDON, schema=65536),
            dict(ADDON, feature="../world-settings"),
            dict(ADDON, payload="bmF0aXZl"),
            dict(ADDON, payload=bytes(16 * 1024 + 1)),
        ]
        with patch("anno1503_overhaul.lan_room.socket.socket") as network:
            for offer in invalid:
                with self.assertRaisesRegex(LanRoomError, "add-on offer is invalid"):
                    host_preflight(HOST, FINGERPRINT, "127.0.0.1", 0, addon_offer=offer)
            with self.assertRaisesRegex(LanRoomError, "callback to prepare"):
                join_preflight(GUEST, FINGERPRINT, "127.0.0.1", 51503, addon_id=ADDON_ID, prepare_addon=42)
            with self.assertRaisesRegex(LanRoomError, "add-on and schema"):
                join_preflight(GUEST, FINGERPRINT, "127.0.0.1", 51503, prepare_addon=Mock())
            network.assert_not_called()

    def test_guest_checks_the_final_accepted_digest(self):
        send = lan_room._send

        def incorrect_ack(connection, message, deadline, **options):
            if message["kind"] == "accepted":
                message = dict(message, artifact_sha256="e" * 64)
            return send(connection, message, deadline, **options)

        with patch.object(lan_room, "_send", side_effect=incorrect_ack), ThreadPoolExecutor(max_workers=1) as worker:
            result, endpoint = self.start_host(worker, addon_offer=ADDON)
            with self.assertRaisesRegex(LanRoomError, "prepared multiplayer artifact differs"):
                join_preflight(GUEST, FINGERPRINT, *endpoint, timeout=3, addon_id=ADDON_ID,
                               prepare_addon=lambda message: message["artifact_sha256"])
            with self.assertRaisesRegex(LanRoomError, "prepared multiplayer artifact differs"):
                result.result(timeout=3)

    def test_rejects_noncanonical_or_oversized_addon_payload_from_peer(self):
        for encoded in ("YR==", "!?==", "é", "A" * 22000):
            with self.assertRaisesRegex(LanRoomError, "add-on offer is invalid"):
                lan_room._decode_addon_payload(encoded)

    def test_invalid_configuration_is_rejected_before_networking(self):
        with self.assertRaisesRegex(LanRoomError, "private LAN or loopback"):
            host_preflight(HOST, FINGERPRINT, "0.0.0.0", 0)
        with self.assertRaisesRegex(LanRoomError, "private LAN or loopback"):
            join_preflight(GUEST, FINGERPRINT, "203.0.113.2", 51503)
        with self.assertRaisesRegex(LanRoomError, "valid TCP port"):
            join_preflight(GUEST, FINGERPRINT, "127.0.0.1", 0)
        with self.assertRaisesRegex(LanRoomError, "SHA-256"):
            host_preflight(HOST, FINGERPRINT.upper(), "127.0.0.1", 0)
        with self.assertRaisesRegex(LanRoomError, "greater than zero"):
            host_preflight(HOST, FINGERPRINT, "127.0.0.1", 0, timeout=0)


if __name__ == "__main__":
    unittest.main()
