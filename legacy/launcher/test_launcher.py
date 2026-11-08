"""Independent launcher checks. No game, registry, URI or remote-memory access.

Run with ``python -B -m unittest -v test_launcher`` from this folder. These are
policy/backend checks using stubs, not a successful native main-menu calibration
or an actual launch/activation test.
"""
from __future__ import annotations

import copy
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from launcher_core import LaunchError, LaunchPolicy

_loader = importlib.machinery.SourceFileLoader(
    "launcher_backend_under_test", str(HERE / "launch_world_settings.pyw"))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
backend_module = importlib.util.module_from_spec(_spec)
_loader.exec_module(backend_module)
Backend = backend_module.Backend
import activation_once


def menu(**changes):
    value = dict(state="menu", pid=101, process_creation_time=123456789,
                 hwnd=0x1234, frame_pointer=0x456780,
                 menu_proof_verified=True)
    value.update(changes)
    return value


class PolicyTests(unittest.TestCase):
    def policy(self, **kwargs):
        value = LaunchPolicy(**kwargs)
        value.start([], 10.0)
        return value

    def assert_not_attempted(self, policy):
        self.assertFalse(policy.activation_attempted)
        self.assertFalse(policy.finished)

    def test_existing_process_prevents_launch(self):
        for ids in ([101], [101, 102], [101, 101]):
            with self.subTest(ids=ids):
                p = LaunchPolicy()
                with self.assertRaisesRegex(LaunchError, "already running"):
                    p.start(ids, 10)
                self.assertIsNone(p.started)
                self.assert_not_attempted(p)

    def test_start_is_single_use(self):
        p = self.policy()
        with self.assertRaisesRegex(LaunchError, "already started"):
            p.start([], 11)
        self.assertEqual(p.started, 10)

    def test_observation_requires_start(self):
        p = LaunchPolicy()
        with self.assertRaises(LaunchError):
            p.observe([101], menu(), 10)
        self.assert_not_attempted(p)

    def test_stable_verified_menu_activates_once_at_threshold(self):
        p = self.policy(stable_seconds=1.5)
        self.assertEqual(p.observe([], None, 10.1), "waiting_for_game")
        self.assertEqual(p.observe([101], menu(), 11), "waiting_for_menu")
        self.assertEqual(p.observe([101], menu(), 12.499), "waiting_for_menu")
        self.assertEqual(p.observe([101], menu(), 12.5), "activate")
        self.assertTrue(p.activation_attempted)
        for ids, observation, now in (([101], menu(), 14), ([], None, 999),
                                      ([101, 102], menu(), 1000)):
            self.assertEqual(p.observe(ids, observation, now), "inactive")
        p.complete()
        self.assertTrue(p.finished)
        self.assertEqual(p.observe([101], menu(), 1001), "inactive")

    def test_multiple_or_duplicate_ids_stop_before_activation(self):
        for ids in ([101, 102], [101, 101]):
            with self.subTest(ids=ids):
                p = self.policy()
                p.observe([101], menu(), 10.5)
                with self.assertRaisesRegex(LaunchError, "More than one"):
                    p.observe(ids, None, 11)
                self.assert_not_attempted(p)

    def test_observed_ubisoft_bootstrap_handoff_before_menu_is_supported(self):
        # Exact identities from the first safe refusal. No native calls occur.
        launch = 134385630270000000
        bootstrap = dict(state="waiting", pid=39548,
                         process_creation_time=134385630275103540)
        game = menu(pid=18120, process_creation_time=134385630280873344)
        p = LaunchPolicy(stable_seconds=1.5)
        p.start([], 10, not_before_creation_time=launch)
        self.assertEqual(p.observe([39548], bootstrap, 10.2), "waiting_for_menu")
        self.assertIsNone(p.identity)
        self.assertEqual(p.observe([39548, 18120], None, 10.3), "waiting_for_game")
        self.assertEqual(p.observe([], None, 10.4), "waiting_for_game")
        self.assertEqual(p.observe([18120], dict(game, state="waiting"), 10.5), "waiting_for_menu")
        self.assertIsNone(p.identity)
        self.assertEqual(p.observe([18120], game, 11), "waiting_for_menu")
        self.assertEqual(p.identity, (18120, 134385630280873344))
        self.assertEqual(p.observe([18120], game, 12.499), "waiting_for_menu")
        self.assertEqual(p.observe([18120], game, 12.5), "activate")
        self.assertTrue(p.activation_attempted)

    def test_pre_menu_process_replacement_without_observation_does_not_pin(self):
        p = self.policy()
        self.assertEqual(p.observe([101], menu(state="waiting"), 11), "waiting_for_menu")
        self.assertIsNone(p.identity)
        self.assertEqual(p.observe([102], None, 12), "waiting_for_menu")
        self.assertIsNone(p.identity)
        self.assert_not_attempted(p)

    def test_startup_multiple_or_duplicate_processes_only_wait_without_inspection(self):
        for ids in ([101, 102], [101, 101]):
            with self.subTest(ids=ids):
                p = self.policy()
                self.assertEqual(p.observe(ids, None, 11), "waiting_for_game")
                self.assertIsNone(p.identity)
                self.assertIsNone(p.menu_token)
                self.assertIsNone(p.menu_since)
                self.assert_not_attempted(p)

    def test_startup_overlap_or_repeated_handoffs_cannot_extend_timeout(self):
        p = self.policy(timeout=3)
        self.assertEqual(p.observe([101, 102], None, 11), "waiting_for_game")
        self.assertEqual(p.observe([103], menu(pid=103, state="waiting"), 12), "waiting_for_menu")
        with self.assertRaisesRegex(LaunchError, "in time"):
            p.observe([104], menu(pid=104), 13.001)
        self.assert_not_attempted(p)

    def test_prelaunch_candidate_creation_is_rejected_even_while_waiting(self):
        lower = 134385630270000000
        for state in ("waiting", "video", "menu"):
            with self.subTest(state=state):
                p = LaunchPolicy()
                p.start([], 10, not_before_creation_time=lower)
                self.assertEqual(p.not_before_creation_time, lower)
                with self.assertRaisesRegex(LaunchError, "predates"):
                    p.observe([101], menu(state=state, process_creation_time=lower - 1), 11)
                self.assertIsNone(p.identity)
                self.assert_not_attempted(p)

    def test_creation_at_or_after_launch_bound_can_reach_verified_menu(self):
        lower = 134385630270000000
        for created in (lower, lower + 1, 134385630280873344):
            with self.subTest(created=created):
                p = LaunchPolicy()
                p.start([], 10, not_before_creation_time=lower)
                row = menu(process_creation_time=created)
                self.assertEqual(p.observe([101], row, 11), "waiting_for_menu")
                self.assertEqual(p.observe([101], row, 12.5), "activate")

    def test_first_certified_menu_permanently_closes_bootstrap_exception(self):
        for ids, row in (([102], None), ([102], menu(pid=102, state="waiting")),
                         ([102], menu(pid=102)), ([], None), ([101, 102], None),
                         ([101], menu(state="waiting", process_creation_time=987654321))):
            with self.subTest(ids=ids, row=row):
                p = self.policy()
                self.assertEqual(p.observe([101], menu(), 11), "waiting_for_menu")
                with self.assertRaises(LaunchError):
                    p.observe(ids, row, 11.1)
                self.assert_not_attempted(p)

    def test_observed_pid_must_match_current_candidate(self):
        p = self.policy()
        with self.assertRaisesRegex(LaunchError, "changed"):
            p.observe([102], menu(), 11)
        self.assert_not_attempted(p)

    def test_changed_creation_or_pid_is_not_a_new_launch_attempt(self):
        for changed in (menu(process_creation_time=987654321), menu(pid=102)):
            with self.subTest(changed=changed):
                p = self.policy()
                p.observe([101], menu(), 11)
                with self.assertRaisesRegex(LaunchError, "restarted|changed"):
                    p.observe([changed["pid"]], changed, 13)
                self.assert_not_attempted(p)

    def test_pinned_pid_change_is_rejected_even_without_observation(self):
        p = self.policy()
        p.observe([101], menu(), 11)
        with self.assertRaises(LaunchError):
            p.observe([102], None, 12)
        self.assert_not_attempted(p)

    def test_disappearing_pinned_process_is_not_relaunched(self):
        p = self.policy()
        p.observe([101], menu(), 11)
        with self.assertRaisesRegex(LaunchError, "closed"):
            p.observe([], None, 12)
        self.assert_not_attempted(p)

    def test_timeout_prevents_even_verified_menu_activation(self):
        p = self.policy(timeout=3)
        p.observe([101], menu(), 11)
        with self.assertRaisesRegex(LaunchError, "in time"):
            p.observe([101], menu(), 13.001)
        self.assert_not_attempted(p)

    def test_unsafe_foreign_or_already_loaded_process_never_activates(self):
        for reason in ("Foreign executable", "Native module differs", "Runtime already loaded"):
            with self.subTest(reason=reason):
                p = self.policy()
                with self.assertRaisesRegex(LaunchError, reason):
                    p.observe([101], dict(menu(), state="unsafe", reason=reason), 11)
                self.assert_not_attempted(p)

    def test_positive_proof_and_both_ownership_pointers_required(self):
        for changes in (dict(menu_proof_verified=False), dict(menu_proof_verified=None),
                        dict(menu_proof_verified=1), dict(menu_proof_verified="true"),
                        dict(hwnd=0), dict(hwnd=None), dict(frame_pointer=0),
                        dict(frame_pointer=None)):
            with self.subTest(changes=changes):
                p = self.policy()
                with self.assertRaises(LaunchError):
                    p.observe([101], menu(**changes), 11)
                self.assert_not_attempted(p)

    def test_creation_time_must_be_a_positive_integer_not_bool_or_text(self):
        for invalid in (None, 0, -1, True, "123456789", 123456789.0):
            with self.subTest(invalid=invalid):
                p = self.policy()
                with self.assertRaises(LaunchError):
                    p.observe([101], menu(process_creation_time=invalid), 11)
                self.assert_not_attempted(p)

    def test_menu_requires_its_own_creation_time_not_an_earlier_sample(self):
        for first in (None, menu(state="waiting"), menu()):
            with self.subTest(first=first):
                p = self.policy()
                if first is not None:
                    p.observe([101], first, 11)
                incomplete = menu()
                del incomplete["process_creation_time"]
                with self.assertRaises(LaunchError):
                    p.observe([101], incomplete, 14)
                self.assert_not_attempted(p)

    def test_waiting_or_incomplete_sample_breaks_continuous_menu_stability(self):
        for interrupted in (None, menu(state="waiting"), menu(state="video")):
            with self.subTest(interrupted=interrupted):
                p = self.policy(stable_seconds=1.5)
                p.observe([101], menu(), 11)
                self.assertEqual(p.observe([101], interrupted, 12.4), "waiting_for_menu")
                self.assertIsNone(p.menu_token)
                self.assertIsNone(p.menu_since)
                self.assertEqual(p.observe([101], menu(), 12.5), "waiting_for_menu")
                self.assertEqual(p.observe([101], menu(), 13.9), "waiting_for_menu")
                self.assertEqual(p.observe([101], menu(), 14), "activate")

    def test_changed_hwnd_or_frame_pointer_restarts_stability(self):
        for changed in (menu(hwnd=0x1235), menu(frame_pointer=0x456788)):
            with self.subTest(changed=changed):
                p = self.policy(stable_seconds=1.5)
                p.observe([101], menu(), 11)
                self.assertEqual(p.observe([101], changed, 12.5), "waiting_for_menu")
                self.assertEqual(p.observe([101], changed, 13.9), "waiting_for_menu")
                self.assertEqual(p.observe([101], changed, 14), "activate")

    def test_missing_process_before_any_identity_keeps_waiting(self):
        p = self.policy()
        self.assertEqual(p.observe([], None, 11), "waiting_for_game")
        self.assertEqual(p.observe([], None, 12), "waiting_for_game")
        self.assert_not_attempted(p)

    def test_completion_only_after_single_attempt(self):
        p = self.policy()
        with self.assertRaises(LaunchError):
            p.complete()
        p.observe([101], menu(), 11)
        p.observe([101], menu(), 13)
        p.complete()
        with self.assertRaises(LaunchError):
            p.complete()


class BackendTests(unittest.TestCase):
    def backend(self):
        value = Backend.__new__(Backend)
        value.event = Mock()
        value.package = HERE / "stub-package-never-opened"
        value.inputs = dict(copy=HERE / "stub-copy-never-opened", exe_sha256="executable-fingerprint")
        value.spec = dict(expanded_engine_plan_sha256="engine-plan-fingerprint")
        value.config = dict(runtime_sha256="runtime-fingerprint",
                            package_spec_sha256="spec-fingerprint")
        value.policy = LaunchPolicy(stable_seconds=1.5)
        value.uri = "uplay://launch/16234/0"
        return value

    def good_result(self):
        return dict(pid=101, process_creation_time=123456789,
                    hooks_installed=True, engine_state="expanded",
                    all_engine_instruction_bytes_verified=True,
                    engine_patch_count=173, engine_patch_status=173,
                    hook_site_count=9, central_war_site_state="guard-jump",
                    runtime_sha256="runtime-fingerprint",
                    world_spec_sha256="spec-fingerprint",
                    executable_sha256="executable-fingerprint",
                    copy_root=str(HERE / "stub-copy-never-opened"),
                    engine_plan_sha256="engine-plan-fingerprint")

    def result_process(self, data=None, code=0, stdout=None):
        return subprocess.CompletedProcess([], code,
            stdout=json.dumps(self.good_result() if data is None else data) if stdout is None else stdout,
            stderr="stub diagnostic")

    def test_existing_game_never_invokes_registered_uri(self):
        b = self.backend()
        b.native = types.SimpleNamespace(processes=Mock(return_value=[101]))
        with patch.object(backend_module.os, "startfile") as launch:
            with self.assertRaises(LaunchError):
                b.start()
        launch.assert_not_called()
        b.event.assert_not_called()

    def test_launch_uses_only_registered_uri_once(self):
        b = self.backend()
        b.native = types.SimpleNamespace(processes=Mock(return_value=[]))
        with patch.object(backend_module.os, "startfile") as launch, \
                patch.object(backend_module.time, "time_ns", return_value=1794088800123456700):
            b.start()
            with self.assertRaises(LaunchError):
                b.start()
        launch.assert_called_once_with(b.uri)
        self.assertEqual(b.policy.not_before_creation_time, 134385624001234567)

    def test_backend_sets_attempt_flag_before_activation_and_does_not_retry_error(self):
        b = self.backend()
        b.policy.start([], 0)
        b.native = types.SimpleNamespace(processes=Mock(return_value=[101]),
                                        inspect=Mock(side_effect=lambda _: menu()))
        calls = []
        def activation(_):
            self.assertTrue(b.policy.activation_attempted)
            calls.append("partial DLL mutation may already have happened")
            raise LaunchError("activation uncertain")
        b.activate = activation
        with patch.object(backend_module.time, "monotonic", side_effect=[1, 2.5]), \
                patch.object(backend_module.time, "sleep"):
            with self.assertRaisesRegex(LaunchError, "uncertain"):
                b.wait_and_activate(Mock())
        self.assertEqual(len(calls), 1)
        self.assertFalse(b.policy.finished)
        self.assertEqual(b.policy.observe([101], menu(), 999), "inactive")

    def test_backend_success_completes_once(self):
        b = self.backend()
        b.policy.start([], 0)
        b.native = types.SimpleNamespace(processes=Mock(return_value=[101]),
                                        inspect=Mock(side_effect=lambda _: menu()))
        b.activate = Mock(side_effect=lambda _: self.assertTrue(b.policy.activation_attempted))
        with patch.object(backend_module.time, "monotonic", side_effect=[1, 2.5]), \
                patch.object(backend_module.time, "sleep"):
            actual = b.wait_and_activate(Mock())
        self.assertEqual(actual, menu())
        b.activate.assert_called_once()
        self.assertTrue(b.policy.finished)
        self.assertEqual(sum(c.args[0] == "success" for c in b.event.call_args_list), 1)

    def test_last_menu_reprobe_must_match_every_identity_field(self):
        changes = (dict(state="waiting"), dict(menu_proof_verified=False),
                   dict(menu_proof_verified=1), dict(pid=102),
                   dict(process_creation_time=987654321), dict(hwnd=0x1235),
                   dict(frame_pointer=0x456788))
        for change in changes:
            with self.subTest(change=change):
                b = self.backend()
                b.policy.start([], 0)
                b.native = types.SimpleNamespace(processes=Mock(return_value=[101]),
                    inspect=Mock(side_effect=[menu(), menu(), menu(**change)]))
                b.activate = Mock()
                with patch.object(backend_module.time, "monotonic", side_effect=[1, 2.5]), \
                        patch.object(backend_module.time, "sleep"):
                    with self.assertRaisesRegex(LaunchError, "left its main menu"):
                        b.wait_and_activate(Mock())
                b.activate.assert_not_called()
                self.assertTrue(b.policy.activation_attempted)
                self.assertFalse(b.policy.finished)
                self.assertEqual(b.policy.observe([101], menu(), 999), "inactive")

    def test_reentering_backend_after_attempt_fails_without_wait_or_retry(self):
        b = self.backend()
        b.policy.start([], 0)
        b.policy.activation_attempted = True
        b.native = types.SimpleNamespace(processes=Mock(return_value=[101]),
                                        inspect=Mock(return_value=menu()))
        b.activate = Mock()
        with patch.object(backend_module.time, "sleep") as sleep:
            with self.assertRaisesRegex(LaunchError, "already attempted"):
                b.wait_and_activate(Mock())
        sleep.assert_not_called()
        b.activate.assert_not_called()

    def test_backend_does_not_inspect_multiple_processes(self):
        b = self.backend()
        b.policy.start([], 0)
        b.policy.observe([101], menu(), 0.5)
        b.native = types.SimpleNamespace(processes=Mock(return_value=[101, 102]), inspect=Mock())
        b.activate = Mock()
        with patch.object(backend_module.time, "monotonic", return_value=1):
            with self.assertRaises(LaunchError):
                b.wait_and_activate(Mock())
        b.native.inspect.assert_not_called()
        b.activate.assert_not_called()

    def test_backend_bootstrap_handoff_waits_until_one_certified_game_menu(self):
        b = self.backend()
        b.policy.start([], 0, not_before_creation_time=100)
        actual = menu(pid=102, process_creation_time=1000)
        b.native = types.SimpleNamespace(
            processes=Mock(side_effect=[[101], [101, 102], [], [102], [102], [102]]),
            inspect=Mock(side_effect=[menu(state="waiting", process_creation_time=999),
                                     dict(actual, state="waiting"), actual, actual, actual]))
        b.activate = Mock()
        with patch.object(backend_module.time, "monotonic", side_effect=[1, 1.4, 1.8, 2, 2.5, 4]), \
                patch.object(backend_module.time, "sleep"):
            result = b.wait_and_activate(Mock())
        self.assertEqual(result, actual)
        b.activate.assert_called_once_with(actual)
        self.assertEqual(b.native.inspect.call_count, 5)
        self.assertEqual(b.policy.identity, (102, 1000))
        self.assertTrue(b.policy.finished)

    def test_activation_command_and_complete_result_are_verified(self):
        b = self.backend()
        with patch.object(backend_module.subprocess, "run", return_value=self.result_process()) as run:
            b.activate(menu())
        run.assert_called_once()
        args, kwargs = run.call_args
        self.assertEqual(args[0], [sys.executable, "-B", "-u", str(HERE / "activation_once.py"),
                         "--pid", "101", "--creation", "123456789",
                         "--hwnd", str(0x1234), "--frame", str(0x456780)])
        self.assertEqual(kwargs["timeout"], 240)
        self.assertEqual(kwargs["creationflags"], subprocess.CREATE_NO_WINDOW)
        self.assertNotIn("shell", kwargs)

    def test_every_success_binding_is_required_no_retry(self):
        good = self.good_result()
        for key in good:
            for change in ("missing", "different"):
                with self.subTest(key=key, change=change):
                    altered = copy.deepcopy(good)
                    if change == "missing":
                        del altered[key]
                    else:
                        altered[key] = not good[key] if isinstance(good[key], bool) else "wrong"
                    b = self.backend()
                    with patch.object(backend_module.subprocess, "run",
                                      return_value=self.result_process(altered)) as run:
                        with self.assertRaises(LaunchError):
                            b.activate(menu())
                    run.assert_called_once()

    def test_failed_or_non_json_activation_is_never_retried(self):
        for result in (self.result_process(code=1), self.result_process(stdout="incomplete stdout")):
            with self.subTest(result=result):
                b = self.backend()
                with patch.object(backend_module.subprocess, "run", return_value=result) as run:
                    with self.assertRaises(LaunchError):
                        b.activate(menu())
                run.assert_called_once()

    def test_activation_timeout_is_uncertain_and_not_retried(self):
        b = self.backend()
        timeout = subprocess.TimeoutExpired("stub", 240, output=b"partial", stderr=b"unknown")
        with patch.object(backend_module.subprocess, "run", side_effect=timeout) as run:
            with self.assertRaisesRegex(LaunchError, "No retry"):
                b.activate(menu())
        run.assert_called_once()
        self.assertEqual(b.event.call_args_list[-1].args[0], "activation_timeout")


class ActivationWorkerTests(unittest.TestCase):
    """The worker delegates once to the immutable activator, using only stubs."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="anno-launcher-worker-")
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        package = self.folder / "package"
        package.mkdir()
        specification = b'{"stub_specification":true}'
        (package / "world_patch.json").write_bytes(specification)
        digest = activation_once.hashlib.sha256(specification).hexdigest()
        (self.folder / "launcher_config.json").write_text(json.dumps(dict(
            package_relative="package", package_spec_sha256=digest)), encoding="utf-8")
        self.copy = self.folder / "copy-never-opened"
        self.mutations = []
        outer = self
        class FakeSession:
            def __init__(self, pid, mutate=False):
                self.pid, self.handle = pid, "stub-handle"
                outer.session_opened.append((pid, mutate))
        self.session_opened = []
        self.a = types.SimpleNamespace(Session=FakeSession,
            all_processes=Mock(return_value=[101]), creation_time=Mock(return_value=123456789),
            close=Mock(), verify=Mock(return_value=dict(copy=self.copy)))
        def main():
            ids = self.a.all_processes()
            self.a.Session(ids[0], True)
            self.mutations.append("fake native writes reached after both guards")
        self.a.main = Mock(side_effect=main)
        self.probe = types.SimpleNamespace(processes=Mock(return_value=[101]),
                                          inspect=Mock(return_value=menu()), close=Mock())
        self.native = types.ModuleType("native_ready")
        self.native._activation = Mock(return_value=self.a)
        self.native.NativeReadiness = Mock(return_value=self.probe)

    def run_worker(self):
        argv = ["activation_once.py", "--pid", "101", "--creation", "123456789",
                "--hwnd", str(0x1234), "--frame", str(0x456780)]
        with patch.object(activation_once, "HERE", self.folder), \
                patch.object(sys, "argv", argv), patch.dict(sys.modules, {"native_ready": self.native}):
            activation_once.main()

    def test_require_observation_accepts_only_current_exact_typed_identity(self):
        activation_once.require_observation(menu(), 101, 123456789, 0x1234, 0x456780)
        for key in menu():
            for change in ("missing", "wrong", "wrong_type"):
                with self.subTest(key=key, change=change):
                    row = menu()
                    if change == "missing":
                        del row[key]
                    elif change == "wrong_type":
                        row[key] = 1 if key == "menu_proof_verified" else str(row[key])
                        if type(row[key]) is type(menu()[key]):
                            row[key] = None
                    else:
                        row[key] = False if key == "menu_proof_verified" else "wrong"
                    with self.assertRaises(RuntimeError):
                        activation_once.require_observation(row, 101, 123456789, 0x1234, 0x456780)

    def test_worker_delegates_one_unchanged_activation_with_original_cli(self):
        expected_original = self.a.main
        def original_main():
            self.assertEqual(sys.argv[1:], ["--install", "--game-dir", str(self.copy)])
            ids = self.a.all_processes()
            self.a.Session(ids[0], True)
            self.mutations.append("fake write")
        self.a.main.side_effect = original_main
        self.run_worker()
        self.assertIs(self.a.main, expected_original)
        self.a.main.assert_called_once_with()
        self.assertEqual(self.session_opened, [(101, True)])
        self.assertEqual(self.mutations, ["fake write"])
        self.probe.close.assert_called_once_with()

    def test_changed_package_prevents_even_readiness_or_activation(self):
        (self.folder / "package/world_patch.json").write_bytes(b"changed")
        with self.assertRaisesRegex(RuntimeError, "specification changed"):
            self.run_worker()
        self.native._activation.assert_not_called()
        self.a.main.assert_not_called()
        self.assertEqual(self.mutations, [])

    def test_probe_process_change_or_duplicate_stops_before_original_main(self):
        for ids in ([], [102], [101, 102], [101, 101]):
            with self.subTest(ids=ids):
                self.probe.processes.return_value = ids
                with self.assertRaisesRegex(RuntimeError, "process changed"):
                    self.run_worker()
                self.a.main.assert_not_called()
                self.assertEqual(self.mutations, [])
                self.probe.inspect.assert_not_called()

    def test_probe_menu_identity_change_stops_before_original_main(self):
        for key, value in (("state", "waiting"), ("menu_proof_verified", False),
                           ("pid", 102), ("process_creation_time", 987654321),
                           ("hwnd", 0x1235), ("frame_pointer", 0x456788)):
            with self.subTest(key=key):
                self.probe.inspect.return_value = menu(**{key: value})
                with self.assertRaisesRegex(RuntimeError, "main menu changed"):
                    self.run_worker()
                self.a.main.assert_not_called()
                self.assertEqual(self.mutations, [])
        self.assertEqual(self.probe.close.call_count, 6)

    def test_process_race_after_probe_fails_before_fake_mutation(self):
        for ids in ([], [102], [101, 102], [101, 101]):
            with self.subTest(ids=ids):
                # Each attempt is an independent fresh worker with a fresh stub.
                self.setUp()
                self.a.all_processes.return_value = ids
                with self.assertRaisesRegex(RuntimeError, "process changed"):
                    self.run_worker()
                self.a.main.assert_called_once_with()
                self.assertEqual(self.session_opened, [])
                self.assertEqual(self.mutations, [])

    def test_reused_pid_creation_race_fails_before_fake_mutation(self):
        self.a.creation_time.return_value = 987654321
        with self.assertRaisesRegex(RuntimeError, "restarted"):
            self.run_worker()
        self.a.main.assert_called_once_with()
        self.assertEqual(self.session_opened, [(101, True)])
        self.a.close.assert_called_once_with("stub-handle")
        self.assertEqual(self.mutations, [])

    def test_unexpected_session_pid_is_rejected_before_handle_open(self):
        self.a.main.side_effect = lambda: self.a.Session(102, True)
        with self.assertRaisesRegex(RuntimeError, "Unexpected Anno process"):
            self.run_worker()
        self.assertEqual(self.session_opened, [])
        self.assertEqual(self.mutations, [])

    def test_original_activation_exception_is_not_retried(self):
        self.a.main.side_effect = RuntimeError("uncertain after possible DLL mutation")
        with self.assertRaisesRegex(RuntimeError, "uncertain"):
            self.run_worker()
        self.a.main.assert_called_once_with()


class FakeKey:
    def __init__(self, name):
        self.name = name
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False


def registry_stub(installs, handler="UbisoftConnect.exe %1"):
    """Only the exact local game-registration keys used by find_uri."""
    reg = types.ModuleType("winreg")
    reg.HKEY_LOCAL_MACHINE, reg.HKEY_CLASSES_ROOT = "HKLM", "HKCR"
    reg.KEY_READ, reg.KEY_WOW64_32KEY = 1, 2
    opened = []
    def open_key(parent, name, *args):
        opened.append((getattr(parent, "name", parent), name, args))
        if parent == reg.HKEY_LOCAL_MACHINE:
            if name != r"SOFTWARE\Ubisoft\Launcher\Installs":
                raise AssertionError("Unexpected registry read")
            return FakeKey("installs")
        if parent == reg.HKEY_CLASSES_ROOT:
            if name != r"uplay\shell\open\command":
                raise AssertionError("Unexpected registry read")
            return FakeKey("handler")
        if parent.name != "installs" or name not in installs:
            raise FileNotFoundError(name)
        return FakeKey(name)
    def query(key, name):
        if key.name == "handler":
            return handler, 1
        if name != "InstallDir":
            raise AssertionError("Unexpected registry value")
        value = installs[key.name]
        if isinstance(value, Exception):
            raise value
        return value, 1
    reg.OpenKey = open_key
    reg.QueryInfoKey = lambda _: (len(installs), 0, 0)
    reg.EnumKey = lambda _, i: list(installs)[i]
    reg.QueryValueEx = query
    reg.opened = opened
    return reg


class RegisteredUriTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="anno-launcher-uri-")
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name)

    def find(self, installs, handler="UbisoftConnect.exe %1"):
        reg = registry_stub(installs, handler)
        with patch.dict(sys.modules, {"winreg": reg}):
            return Backend.find_uri(self.source)

    def test_only_matching_numeric_installation_supplies_uri(self):
        self.assertEqual(self.find({"other": str(self.source),
                                    "1": str(self.source / "different"),
                                    "16234": str(self.source)}), "uplay://launch/16234/0")

    def test_no_matching_or_ambiguous_installation_prevents_start(self):
        for installs in ({}, {"16234": str(self.source / "other")},
                         {"16234": str(self.source), "999": str(self.source)}):
            with self.subTest(installs=installs), self.assertRaises(LaunchError):
                self.find(installs)

    def test_invalid_install_entries_are_ignored(self):
        self.assertEqual(self.find({"1": FileNotFoundError("missing"), "2": None,
                                    "16234": str(self.source)}), "uplay://launch/16234/0")

    def test_missing_registered_handler_prevents_uri_use(self):
        with self.assertRaises(LaunchError):
            self.find({"16234": str(self.source)}, handler="")


if __name__ == "__main__":
    unittest.main(verbosity=2)
