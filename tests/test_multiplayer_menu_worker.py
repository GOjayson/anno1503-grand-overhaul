from struct import unpack_from
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from anno1503_overhaul import multiplayer_menu_worker as worker
from anno1503_overhaul.lan_identity import PlayerIdentity
from anno1503_overhaul.lan_internet import InternetPreflight
from anno1503_overhaul.lan_room import LanRoomError
from anno1503_overhaul.multiplayer_menu_worker import MenuAction, MenuRequest, pair_menu_request


HOST = PlayerIdentity(str(uuid4()), "Host")
GUEST = PlayerIdentity(str(uuid4()), "Guest")
FINGERPRINT = "a" * 64
LAN_HOST = "192.168.247.1"
LAN_GUEST = "192.168.247.2"
INTERNET_HOST = "1.1.1.1"
INTERNET_GUEST = "8.8.8.8"


class NativeMenuWorkerTests(unittest.TestCase):
    def setUp(self):
        self.guard = Mock()
        self.fingerprint = Mock(return_value=FINGERPRINT)
        self.checks = dict(verify_request=self.guard, game_fingerprint=self.fingerprint)

    def plan(self, paired):
        signature, role, local, remote, prefix, host, guest = unpack_from(
            "<8sI4s4sI32s32s", paired.native_plan(**self.checks),
        )
        return signature, role, local, remote, prefix, host.rstrip(b"\0"), guest.rstrip(b"\0")

    def test_lan_host_learns_the_accepted_private_route(self):
        status = Mock()

        def host(player, fingerprint, bind, port, *, on_listening, on_route, timeout):
            self.assertEqual((player, fingerprint, bind, port, timeout), (HOST, FINGERPRINT, LAN_HOST, 51503, 60))
            on_listening(bind, port)
            on_route(bind, LAN_GUEST)
            return GUEST

        with patch.object(worker, "host_preflight", side_effect=host):
            request = MenuRequest(MenuAction.LAN_HOST, bind_address=LAN_HOST)
            paired = pair_menu_request(request, HOST, **self.checks, on_listening=status)
        status.assert_called_once_with(LAN_HOST, 51503)
        self.assertEqual((paired.local_address, paired.remote_address, paired.peer), (LAN_HOST, LAN_GUEST, GUEST))
        self.assertEqual(self.plan(paired), (
            b"ANNOLAB1", 1, b"\xc0\xa8\xf7\x01", b"\xc0\xa8\xf7\x02", 0, b"Host", b"Guest",
        ))

    def test_lan_join_uses_the_locally_selected_route_without_an_explicit_bind(self):
        def join(player, fingerprint, address, port, *, bind_address, on_route, timeout):
            self.assertEqual((player, fingerprint, address, port, bind_address, timeout),
                             (GUEST, FINGERPRINT, LAN_HOST, 51503, None, 10))
            on_route(LAN_GUEST, address)
            return HOST

        with patch.object(worker, "join_preflight", side_effect=join):
            paired = pair_menu_request(MenuRequest(MenuAction.LAN_JOIN, LAN_HOST, ""), GUEST, **self.checks)
        self.assertEqual(self.plan(paired), (
            b"ANNOLAB1", 2, b"\xc0\xa8\xf7\x02", b"\xc0\xa8\xf7\x01", 0, b"Host", b"Guest",
        ))

    def test_internet_host_and_guest_use_the_verified_public_route(self):
        host_route = InternetPreflight(GUEST, LAN_HOST, INTERNET_GUEST, INTERNET_HOST)
        guest_route = InternetPreflight(HOST, LAN_GUEST, INTERNET_HOST, INTERNET_HOST)
        with (
            patch.object(worker, "host_internet_preflight", return_value=host_route) as host,
            patch.object(worker, "join_internet_preflight", return_value=guest_route) as join,
        ):
            hosting = MenuRequest(MenuAction.INTERNET_HOST, INTERNET_HOST, LAN_HOST)
            joining = MenuRequest(MenuAction.INTERNET_JOIN, INTERNET_HOST, LAN_GUEST)
            host_result = pair_menu_request(hosting, HOST, **self.checks)
            guest_result = pair_menu_request(joining, GUEST, **self.checks)
        self.assertEqual(host.call_args.args, (HOST, FINGERPRINT, LAN_HOST, INTERNET_HOST, 51503))
        join.assert_called_once_with(GUEST, FINGERPRINT, INTERNET_HOST, 51503, bind_address=LAN_GUEST, timeout=10)
        self.assertEqual(self.plan(host_result), (
            b"ANNOINET", 1, b"\xc0\xa8\xf7\x01", b"\x08\x08\x08\x08", 0, b"Host", b"Guest",
        ))
        self.assertEqual(self.plan(guest_result), (
            b"ANNOINET", 2, b"\xc0\xa8\xf7\x02", b"\x01\x01\x01\x01", 0, b"Host", b"Guest",
        ))

    def test_lan_route_rejects_loopback_public_and_same_address_before_accepting_peer(self):
        for source in ("127.0.0.1", INTERNET_GUEST, LAN_HOST):
            def host(*_, on_route, **__):
                on_route(LAN_HOST, source)
                self.fail("The invalid LAN peer must fail the route callback.")

            with (
                self.subTest(source=source),
                patch.object(worker, "host_preflight", side_effect=host),
                self.assertRaises(LanRoomError),
            ):
                pair_menu_request(MenuRequest(MenuAction.LAN_HOST, bind_address=LAN_HOST), HOST, **self.checks)

    def test_shared_flag_plans_retain_separate_identities_and_transport(self):
        def host(*_, on_route, **__):
            on_route(LAN_HOST, LAN_GUEST)
            return GUEST

        with patch.object(worker, "host_preflight", side_effect=host):
            request = MenuRequest(MenuAction.LAN_HOST, bind_address=LAN_HOST, co_op=True)
            result = pair_menu_request(request, HOST, **self.checks)
        self.assertEqual(self.plan(result), (
            b"ANNOCOOP", 1, b"\xc0\xa8\xf7\x01", b"\xc0\xa8\xf7\x02", 0, b"Host", b"Guest",
        ))
        route = InternetPreflight(HOST, LAN_GUEST, INTERNET_HOST, INTERNET_HOST)
        with patch.object(worker, "join_internet_preflight", return_value=route):
            joined = pair_menu_request(MenuRequest(MenuAction.INTERNET_JOIN, INTERNET_HOST, co_op=True),
                                       GUEST, **self.checks)
        self.assertEqual(self.plan(joined), (
            b"ANNOCNET", 2, b"\xc0\xa8\xf7\x02", b"\x01\x01\x01\x01", 0, b"Host", b"Guest",
        ))
        with self.assertRaisesRegex(LanRoomError, "supports two players"):
            pair_menu_request(MenuRequest(MenuAction.INTERNET_JOIN, INTERNET_HOST, co_op=True, player_count=3),
                              GUEST, **self.checks)

    def test_eight_player_plan_includes_all_seven_tcp_admitted_addresses(self):
        guests = tuple((f"192.168.247.{index}", PlayerIdentity(str(uuid4()), f"Guest {index}")) for index in range(2, 9))

        def host(*args, player_count, on_route, **kwargs):
            self.assertEqual((args[2], player_count), (LAN_HOST, 8))
            for address, _ in guests:
                on_route(LAN_HOST, address)
            return guests

        with patch.object(worker, "host_group_preflight", side_effect=host):
            request = MenuRequest(MenuAction.LAN_HOST, bind_address=LAN_HOST, player_count=8)
            result = pair_menu_request(request, HOST, **self.checks)
        self.assertEqual(self.plan(result)[0:2], (b"ANNOROOM", 1))
        plan = result.native_plan(**self.checks)
        self.assertEqual(unpack_from("<II", plan, 88), (8, 6))
        self.assertEqual(result.extra_guests, guests[1:])
        self.assertEqual(unpack_from("<4s32s", plan, 96)[0], b"\xc0\xa8\xf7\x03")
        self.assertEqual(unpack_from("<4s32s", plan, 276)[0], b"\xc0\xa8\xf7\x08")

    def test_eight_player_internet_plan_preserves_individual_tickets_for_shared_ip(self):
        guests = tuple((INTERNET_GUEST, PlayerIdentity(str(uuid4()), "Guest"), str(index) * 24)
                       for index in range(7))
        route = InternetPreflight(HOST, LAN_GUEST, INTERNET_HOST, INTERNET_HOST,
                                  ticket=guests[-1][2], player_count=8)
        with (
            patch.object(worker, "host_internet_group_preflight", return_value=(LAN_HOST, guests)) as host,
            patch.object(worker, "join_internet_preflight", return_value=route) as join,
        ):
            hosting = MenuRequest(MenuAction.INTERNET_HOST, INTERNET_HOST, LAN_HOST, player_count=8)
            host_result = pair_menu_request(hosting, HOST, **self.checks, addon_offer={"world": "selected"})
            joining = MenuRequest(MenuAction.INTERNET_JOIN, INTERNET_HOST, LAN_GUEST, player_count=8)
            guest_result = pair_menu_request(joining, guests[-1][1], **self.checks)
        self.assertEqual(host.call_args.kwargs["player_count"], 8)
        self.assertEqual(host.call_args.kwargs["addon_offer"], {"world": "selected"})
        self.assertEqual(join.call_args.kwargs["player_count"], 8)
        self.assertTrue(join.call_args.kwargs["wait_for_group"])
        self.assertEqual(self.plan(host_result)[:2], (b"ANNONETR", 1))
        self.assertEqual(self.plan(guest_result)[:2], (b"ANNONETR", 2))
        self.assertEqual(host_result.native_plan(**self.checks)[312:],
                         b"".join(guest[2].encode("ascii") for guest in guests))
        self.assertEqual(guest_result.native_plan(**self.checks)[312:], b"6" * 24 + bytes(144))

    def test_requires_the_outstanding_action_before_connecting_and_to_emit_a_plan(self):
        route = InternetPreflight(HOST, LAN_GUEST, INTERNET_HOST, INTERNET_HOST)
        request = MenuRequest(MenuAction.INTERNET_JOIN, INTERNET_HOST)
        changed = RuntimeError("Menu request is no longer active.")
        with patch.object(worker, "join_internet_preflight", return_value=route) as join:
            self.guard.side_effect = changed
            with self.assertRaisesRegex(RuntimeError, "no longer active"):
                pair_menu_request(request, GUEST, **self.checks)
            join.assert_not_called()
            self.fingerprint.assert_not_called()

            self.guard.side_effect = None
            paired = pair_menu_request(request, GUEST, **self.checks)
        self.guard.side_effect = changed
        with self.assertRaisesRegex(RuntimeError, "no longer active"):
            paired.native_plan(**self.checks)

    def test_rejects_build_drift_during_pairing_or_before_handoff(self):
        route = InternetPreflight(HOST, LAN_GUEST, INTERNET_HOST, INTERNET_HOST)
        request = MenuRequest(MenuAction.INTERNET_JOIN, INTERNET_HOST)
        with patch.object(worker, "join_internet_preflight", return_value=route):
            self.fingerprint.side_effect = [FINGERPRINT, "b" * 64]
            with self.assertRaisesRegex(LanRoomError, "game files changed"):
                pair_menu_request(request, GUEST, **self.checks)

            self.fingerprint.side_effect = None
            paired = pair_menu_request(request, GUEST, **self.checks)
        self.fingerprint.return_value = "b" * 64
        with self.assertRaisesRegex(LanRoomError, "game files changed"):
            paired.native_plan(**self.checks)

    def test_native_name_keeps_existing_ascii_fallback(self):
        player = PlayerIdentity(GUEST.player_id, "Éléonore")
        route = InternetPreflight(HOST, LAN_GUEST, INTERNET_HOST, INTERNET_HOST)
        with patch.object(worker, "join_internet_preflight", return_value=route):
            paired = pair_menu_request(MenuRequest(MenuAction.INTERNET_JOIN, INTERNET_HOST), player, **self.checks)
        self.assertEqual(self.plan(paired)[-2:], (b"Host", b"LAN Guest"))


if __name__ == "__main__":
    unittest.main()
