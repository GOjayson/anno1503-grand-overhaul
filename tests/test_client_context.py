"""Normal-client relay guards; synthetic context values never leave a process."""
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from anno1503_overhaul import client_context as context
from anno1503_overhaul.filesystem import COPY_MARKER


class ClientContextTests(unittest.TestCase):
    def test_environment_parser_preserves_values_and_windows_drive_keys(self):
        raw = '=C:=C:\\game\0Path=normal-path\0UPLAY_ARGUMENTS=private-value\0\0'.encode('utf-16-le')
        parsed = context.parse_environment_block(raw)
        self.assertEqual(parsed, {'=C:': 'C:\\game', 'Path': 'normal-path', 'UPLAY_ARGUMENTS': 'private-value'})

    def test_environment_parser_refuses_missing_termination_duplicates_and_invalid_entries(self):
        for value in ('Path=a\0PATH=b\0\0', 'BAD\0\0', 'Path=no-terminator'):
            with self.subTest(case=value), self.assertRaises(context.ContextError):
                context.parse_environment_block(value.encode('utf-16-le'))
        with self.assertRaises(context.ContextError):
            context.parse_environment_block(b'x')
        with self.assertRaises(context.ContextError):
            context.parse_environment_block(b'x' * (context.MAX_ENVIRONMENT_BYTES+2))

    def test_context_representation_and_summary_never_contain_values(self):
        value = context.ClientContext(7, 123, Path('/source'), {'UPLAY_ARGUMENTS': 'private-value'},
                                      ['--session=private-argument'], ['UPLAY_ARGUMENTS'])
        summary = json.dumps(value.safe_summary()) + repr(value)
        self.assertNotIn('private-value', summary)
        self.assertNotIn('private-argument', summary)
        self.assertNotIn('--session', summary)
        self.assertEqual(value.safe_summary()['argument_count'], 1)
        self.assertIn('UPLAY_ARGUMENTS', summary)
        with self.assertRaises(TypeError):
            json.dumps(value)

    def _fixture(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name).resolve()
        source, target = root/'source', root/'copy'
        source.mkdir(); target.mkdir()
        data = b'unmodified signed-game fixture'
        (source/'Anno1503.exe').write_bytes(data)
        (target/'Anno1503.exe').write_bytes(data)
        marker = dict(schema=1, managed_copy=True, source_root=str(source), copy_root=str(target), phase='vanilla')
        (target/COPY_MARKER).write_text(json.dumps(marker), encoding='utf-8')
        pin = patch.object(context, 'EXE_SHA256', hashlib.sha256(data).hexdigest())
        pin.start(); self.addCleanup(pin.stop)
        return source, target

    def test_capture_checks_creation_time_and_does_not_expose_normal_values(self):
        source, _ = self._fixture()
        fake = Mock()
        fake.identity.return_value = (source/'Anno1503.exe', 123)
        fake.capture.return_value = (str(source/'Anno1503.exe'), [str(source/'Anno1503.exe'), '--ticket=private-argument'],
                                     {'UPLAY_ARGUMENTS': 'private-value'})
        opener = Mock()
        opener.return_value.__enter__ = Mock(return_value=fake)
        opener.return_value.__exit__ = Mock(return_value=False)
        with patch.object(context, '_WindowsContext', opener):
            captured = context.capture_client_context(source, 7, 123)
            self.assertNotIn('private-value', repr(captured))
            with self.assertRaises(context.ContextError):
                context.capture_client_context(source, 7, 124)
        self.assertEqual(fake.capture.call_count, 1)

    def test_relay_forwards_unchanged_normal_environment_once_without_persisting_it(self):
        source, target = self._fixture()
        environment = {'UPLAY_ARGUMENTS': 'private-value', 'Path': 'normal-path'}
        captured = context.ClientContext(7, 123, source, environment, ['--session=private-argument'], ['UPLAY_ARGUMENTS'])
        process = Mock(pid=8)
        with patch.object(context, 'require_game_closed'), patch.object(context.subprocess, 'Popen', return_value=process) as start:
            self.assertIs(context.launch_copy(captured, target), process)
            args, keywords = start.call_args
            self.assertEqual(args[0], [str(target/'Anno1503.exe'), '--session=private-argument'])
            self.assertEqual(keywords['env'], environment)
            self.assertEqual(keywords['cwd'], target)
            with self.assertRaises(context.ContextError):
                context.launch_copy(captured, target)
        self.assertEqual(captured._environment, {})
        self.assertEqual(captured._arguments, ())
        self.assertEqual(environment['UPLAY_ARGUMENTS'], 'private-value')
        self.assertFalse(any(p.name.endswith('.json') and p.name != COPY_MARKER for p in target.iterdir()))

    def test_altered_executable_foreign_marker_and_running_game_refuse_before_spawn(self):
        source, target = self._fixture()
        for mode in ('altered', 'foreign', 'running'):
            captured = context.ClientContext(7, 123, source, {'A': 'private-value'}, [], [])
            with self.subTest(mode=mode), patch.object(context.subprocess, 'Popen') as start:
                if mode == 'altered':
                    (target/'Anno1503.exe').write_bytes(b'changed')
                    with self.assertRaises(context.ContextError): context.launch_copy(captured, target)
                    (target/'Anno1503.exe').write_bytes((source/'Anno1503.exe').read_bytes())
                elif mode == 'foreign':
                    marker = json.loads((target/COPY_MARKER).read_bytes())
                    marker['source_root'] = str(source.parent/'another-game')
                    (target/COPY_MARKER).write_text(json.dumps(marker), encoding='utf-8')
                    with self.assertRaises(context.ContextError): context.launch_copy(captured, target)
                    marker['source_root'] = str(source)
                    (target/COPY_MARKER).write_text(json.dumps(marker), encoding='utf-8')
                else:
                    with patch.object(context, 'require_game_closed', side_effect=RuntimeError('game is running')):
                        with self.assertRaises(RuntimeError): context.launch_copy(captured, target)
                start.assert_not_called()

    def test_uncertain_spawn_failure_clears_context_and_never_echoes_private_values(self):
        source, target = self._fixture()
        captured = context.ClientContext(7, 123, source, {'A': 'private-value'}, ['--session=private-argument'], [])
        with patch.object(context, 'require_game_closed'), patch.object(context.subprocess, 'Popen', side_effect=RuntimeError('private-value')):
            with self.assertRaises(context.ContextError) as raised:
                context.launch_copy(captured, target)
        self.assertNotIn('private-value', str(raised.exception))
        self.assertTrue(captured._used)
        self.assertFalse(captured._environment)

    def _bridge_fixture(self, *, state='menu', existing=False, close=True, copy_state='menu'):
        source, target = self._fixture()
        class Clock:
            value = 0
            def monotonic(self): return self.value
            def sleep(self, seconds): self.value += seconds
            def time_ns(self): return 100000
        class Probe:
            started = False
            closed = False
            child_started = False
            copy_menu_observed = False
            extra_pid = False
            hidden = False
            visibility_requests = None
            mode = state
            inputs = dict(source=source, exe_sha256=context.EXE_SHA256)
            def processes(self):
                return ([7] if existing or (self.started and not self.closed) else []) + ([8] if self.child_started else []) + ([9] if self.extra_pid else [])
            def inspect(self, pid):
                return dict(state='waiting' if self.hidden else self.mode, pid=pid, process_creation_time=116444736000001100,
                            hwnd=12, frame_pointer=16, menu_proof_verified=True)
            def inspect_owned_bootstrap(self, pid, identity):
                if identity != (7,116444736000001100,12,16) or pid != 7:
                    raise AssertionError('Wrong owned bootstrap identity')
                return dict(state=self.mode, pid=pid, process_creation_time=116444736000001100,
                            hwnd=12, frame_pointer=16, menu_proof_verified=True)
        clock, probe = Clock(), Probe()
        probe.visibility_requests=[]
        class CopyProbe:
            inputs = dict(source=target, exe_sha256=context.EXE_SHA256)
            mode = copy_state
            def inspect(self, pid):
                if self.mode == 'menu': probe.copy_menu_observed = True
                return dict(state=self.mode, pid=pid, process_creation_time=116444736000001200,
                            hwnd=24, frame_pointer=32, menu_proof_verified=True)
        probe.copy_probe = CopyProbe()
        captured = context.ClientContext(7, 116444736000001100, source,
                                         {'UPLAY_ARGUMENTS': 'private-value'}, ['--session=private-argument'], [])
        stack = __import__('contextlib').ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(context, 'time', clock))
        route = stack.enter_context(patch.object(context.os, 'startfile',
                                                side_effect=lambda _: setattr(probe, 'started', True), create=True))
        capture = stack.enter_context(patch.object(context, 'capture_client_context', return_value=captured))
        def normal_close(*_):
            if not probe.copy_menu_observed: raise AssertionError('The source SDK session closed before the copy initialized.')
            probe.closed = close
        def initialize(*_, **__):
            if probe.closed: raise AssertionError('The normal source session must remain alive during copied SDK initialization.')
            if not probe.hidden: raise AssertionError('The normal source menu must be hidden before a copy can open.')
            probe.child_started = True
            captured.clear()
            return Mock(pid=8)
        close_menu = stack.enter_context(patch.object(context, '_request_menu_close', side_effect=normal_close))
        def visibility(root, identity, visible):
            if root != source or identity != (7,116444736000001100,12,16):
                raise AssertionError('Only the exact owned source window may change visibility')
            probe.visibility_requests.append(visible)
            probe.hidden=not visible
        probe.visibility = stack.enter_context(patch.object(context, '_set_bootstrap_visible', side_effect=visibility))
        launch = stack.enter_context(patch.object(context, 'launch_copy', side_effect=initialize))
        return source, target, probe, captured, route, capture, close_menu, launch

    def test_bridge_uses_normal_client_then_only_closes_its_verified_fresh_menu(self):
        source, target, probe, captured, route, capture, close_menu, launch = self._bridge_fixture()
        events = []
        result = context.start_game('uplay://launch/123/0', source, target, probe,
                                    copy_probe=probe.copy_probe,
                                    event=lambda kind, value: events.append((kind, value)), timeout=10)
        self.assertEqual(result.pid, 8)
        route.assert_called_once_with('uplay://launch/123/0')
        capture.assert_called_once_with(source, 7, 116444736000001100)
        close_menu.assert_called_once_with(7, 12)
        launch.assert_called_once()
        args,kwargs=launch.call_args
        self.assertEqual(args,(captured,target))
        self.assertEqual(kwargs['source_identity'],(7,116444736000001100,12,16))
        self.assertIsInstance(kwargs['source_probe'],context._HiddenBootstrapProbe)
        self.assertEqual(probe.visibility_requests,[False])
        self.assertNotIn('private-value', json.dumps(events))
        self.assertNotIn('private-argument', json.dumps(events))
        self.assertTrue(captured._used)

    def test_bridge_never_adopts_an_existing_game(self):
        source, target, probe, _, route, capture, close_menu, launch = self._bridge_fixture(existing=True)
        with self.assertRaises(context.ContextError):
            context.start_game('uplay://launch/123/0', source, target, probe, copy_probe=probe.copy_probe, timeout=10)
        for action in (route, capture, close_menu, launch): action.assert_not_called()

    def test_bridge_refuses_unsafe_process_without_close_or_copy(self):
        source, target, probe, _, _, capture, close_menu, launch = self._bridge_fixture(state='unsafe')
        with self.assertRaises(context.ContextError):
            context.start_game('uplay://launch/123/0', source, target, probe, copy_probe=probe.copy_probe, timeout=10)
        for action in (capture, close_menu, launch): action.assert_not_called()

    def test_bridge_never_closes_a_source_that_left_its_menu_during_capture(self):
        source, target, probe, captured, _, capture, close_menu, launch = self._bridge_fixture()
        capture.side_effect = lambda *_: (setattr(probe, 'mode', 'world'), captured)[1]
        with self.assertRaises(context.ContextError):
            context.start_game('uplay://launch/123/0', source, target, probe, copy_probe=probe.copy_probe, timeout=10)
        close_menu.assert_not_called()
        launch.assert_not_called()
        self.assertTrue(captured._used)
        self.assertFalse(captured._environment)

    def test_bridge_timeout_does_not_close_or_copy_an_unverified_game(self):
        source, target, probe, _, _, capture, close_menu, launch = self._bridge_fixture(state='waiting')
        with self.assertRaises(context.ContextError):
            context.start_game('uplay://launch/123/0', source, target, probe, copy_probe=probe.copy_probe, timeout=5)
        for action in (capture, close_menu, launch): action.assert_not_called()

    def test_bridge_never_force_closes_a_source_that_ignores_its_normal_close(self):
        source, target, probe, captured, _, _, close_menu, launch = self._bridge_fixture(close=False)
        with self.assertRaises(context.ContextError):
            context.start_game('uplay://launch/123/0', source, target, probe, copy_probe=probe.copy_probe, timeout=8)
        close_menu.assert_called_once()
        launch.assert_called_once()
        self.assertTrue(captured._used)

    def test_copied_sdk_not_ready_or_unsafe_leaves_original_menu_alive(self):
        for state in ('waiting','unsafe'):
            source,target,probe,captured,_,_,close_menu,launch=self._bridge_fixture(copy_state=state)
            with self.subTest(state=state),self.assertRaises(context.ContextError):
                context.start_game('uplay://launch/123/0',source,target,probe,copy_probe=probe.copy_probe,timeout=8)
            launch.assert_called_once()
            close_menu.assert_not_called()
            self.assertFalse(probe.closed)
            self.assertFalse(probe.hidden)
            self.assertEqual(probe.visibility_requests,[False,True])

    def test_extra_game_process_is_never_adopted_or_closed(self):
        source,target,probe,_,_,_,close_menu,launch=self._bridge_fixture()
        original=launch.side_effect
        def extra(*args,**kwargs):
            child=original(*args,**kwargs);probe.extra_pid=True;return child
        launch.side_effect=extra
        with self.assertRaises(context.ContextError):
            context.start_game('uplay://launch/123/0',source,target,probe,copy_probe=probe.copy_probe,timeout=8)
        close_menu.assert_not_called()

    def test_wrong_copy_observer_is_refused_before_any_normal_launch(self):
        source,target,probe,_,route,capture,close_menu,launch=self._bridge_fixture()
        probe.copy_probe.inputs['source']=source
        with self.assertRaises(context.ContextError):
            context.start_game('uplay://launch/123/0',source,target,probe,copy_probe=probe.copy_probe,timeout=8)
        for action in (route,capture,close_menu,launch):action.assert_not_called()

    def test_missing_hidden_observer_capability_refuses_before_hiding_or_copy(self):
        source,target,probe,_,_,_,close_menu,launch=self._bridge_fixture()
        probe.inspect_owned_bootstrap=None
        with self.assertRaises(context.ContextError):
            context.start_game('uplay://launch/123/0',source,target,probe,copy_probe=probe.copy_probe,timeout=8)
        probe.visibility.assert_not_called()
        launch.assert_not_called()
        close_menu.assert_not_called()

    def test_hidden_menu_change_restores_only_its_owned_source_and_never_starts_copy(self):
        source,target,probe,_,_,_,close_menu,launch=self._bridge_fixture()
        original=probe.visibility.side_effect
        def changed(*args):
            original(*args)
            if args[2] is False:probe.mode='world'
        probe.visibility.side_effect=changed
        with self.assertRaises(context.ContextError):
            context.start_game('uplay://launch/123/0',source,target,probe,copy_probe=probe.copy_probe,timeout=8)
        self.assertEqual(probe.visibility_requests,[False,True])
        self.assertFalse(probe.hidden)
        launch.assert_not_called();close_menu.assert_not_called()

    def test_failed_or_uncertain_hiding_restores_visibility_without_starting_copy(self):
        source,target,probe,_,_,_,close_menu,launch=self._bridge_fixture()
        original=probe.visibility.side_effect
        def changed(*args):
            original(*args)
            if args[2] is False:raise context.ContextError('window changed')
        probe.visibility.side_effect=changed
        with self.assertRaisesRegex(context.ContextError,'window changed'):
            context.start_game('uplay://launch/123/0',source,target,probe,copy_probe=probe.copy_probe,timeout=8)
        self.assertEqual(probe.visibility_requests,[False,True])
        launch.assert_not_called();close_menu.assert_not_called()

    def test_visibility_restore_failure_does_not_mask_original_safe_error(self):
        source,target,probe,_,_,_,close_menu,launch=self._bridge_fixture(copy_state='unsafe')
        original=probe.visibility.side_effect
        def changed(*args):
            if args[2] is True:raise context.ContextError('replacement window refused')
            original(*args)
        probe.visibility.side_effect=changed
        events=[]
        with self.assertRaisesRegex(context.ContextError,'copied game startup could not be verified'):
            context.start_game('uplay://launch/123/0',source,target,probe,copy_probe=probe.copy_probe,
                               event=lambda k,v:events.append((k,v)),timeout=8)
        self.assertIn(('normal_source_menu_restore_visibility',dict(restored=False)),events)
        self.assertNotIn('private-value',json.dumps(events))
        close_menu.assert_not_called()

    def _window_fixture(self):
        source,_=self._fixture();process=Mock();process.identity.return_value=(source/'Anno1503.exe',123)
        factory=Mock();factory.return_value.__enter__=Mock(return_value=process)
        factory.return_value.__exit__=Mock(return_value=False)
        state=dict(visible=True);user=Mock()
        user.IsWindow.return_value=True
        def owner(hwnd,target):target._obj.value=7;return 10
        user.GetWindowThreadProcessId.side_effect=owner
        user.GetWindowLongPtrW.return_value=16
        user.IsWindowVisible.side_effect=lambda _:state['visible']
        def show(hwnd,mode):
            previous=state['visible'];state['visible']=mode!=0;return previous
        user.ShowWindow.side_effect=show
        stack=__import__('contextlib').ExitStack();self.addCleanup(stack.close)
        stack.enter_context(patch.object(context,'os',SimpleNamespace(name='nt')))
        stack.enter_context(patch.object(context,'_WindowsContext',factory))
        stack.enter_context(patch.object(context.C,'WinDLL',return_value=user,create=True))
        return source,process,user,state

    def test_window_api_hides_and_restores_only_exact_owned_identity_without_activation(self):
        source,process,user,state=self._window_fixture()
        context._set_bootstrap_visible(source,(7,123,12,16),False)
        self.assertFalse(state['visible']);user.ShowWindow.assert_called_once_with(12,0)
        context._set_bootstrap_visible(source,(7,123,12,16),True)
        self.assertTrue(state['visible']);self.assertEqual(user.ShowWindow.call_args.args,(12,4))
        user.SetForegroundWindow.assert_not_called();user.PostMessageW.assert_not_called()

    def test_window_api_refuses_recycled_pid_wrong_path_hwnd_owner_and_changed_frame(self):
        for mutation in ('creation','path','hwnd','owner','frame'):
            source,process,user,state=self._window_fixture()
            if mutation=='creation':process.identity.return_value=(source/'Anno1503.exe',124)
            elif mutation=='path':process.identity.return_value=(source/'another.exe',123)
            elif mutation=='hwnd':user.IsWindow.return_value=False
            elif mutation=='owner':user.GetWindowThreadProcessId.side_effect=lambda h,p:(setattr(p._obj,'value',8),10)[1]
            elif mutation=='frame':user.GetWindowLongPtrW.return_value=17
            with self.subTest(mutation=mutation),self.assertRaises(context.ContextError):
                context._set_bootstrap_visible(source,(7,123,12,16),False)
            user.ShowWindow.assert_not_called()

    def test_window_api_checks_identity_again_after_showwindow(self):
        source,process,user,state=self._window_fixture()
        process.identity.side_effect=[(source/'Anno1503.exe',123),(source/'Anno1503.exe',123),(source/'Anno1503.exe',124)]
        with self.assertRaisesRegex(context.ContextError,'visibility could not be verified'):
            context._set_bootstrap_visible(source,(7,123,12,16),False)
        user.ShowWindow.assert_called_once_with(12,0)

    def test_hidden_adapter_rejects_a_different_pid_before_observation(self):
        probe=Mock();probe.inputs={}
        wrapper=context._HiddenBootstrapProbe(probe,(7,123,12,16))
        with self.assertRaises(context.ContextError):wrapper.inspect(8)
        probe.inspect_owned_bootstrap.assert_not_called()

    def test_explicit_bootstrap_allowance_is_bound_to_context_and_exact_menu(self):
        source,target=self._fixture()
        captured=context.ClientContext(7,123,source,{'A':'private-value'},[],[])
        probe=Mock()
        probe.inputs=dict(source=source,exe_sha256=context.EXE_SHA256)
        probe.processes.return_value=[7]
        probe.inspect.return_value=dict(state='menu',pid=7,process_creation_time=123,hwnd=12,
                                        frame_pointer=16,menu_proof_verified=True)
        with (patch.object(context,'require_game_closed',side_effect=AssertionError('explicit proof replaces only this check')),
              patch.object(context.subprocess,'Popen',return_value=Mock(pid=8)) as start):
            context.launch_copy(captured,target,source_identity=(7,123,12,16),source_probe=probe)
        start.assert_called_once()
        for identity,ids,state in (((9,123,12,16),[7],'menu'),((7,123,12,16),[7,9],'menu'),((7,123,12,16),[7],'world')):
            value=context.ClientContext(7,123,source,{'A':'private-value'},[],[])
            probe.processes.return_value=ids;probe.inspect.return_value['state']=state
            with (self.subTest(identity=identity,ids=ids,state=state),
                  patch.object(context.subprocess,'Popen') as start, self.assertRaises(context.ContextError)):
                context.launch_copy(value,target,source_identity=identity,source_probe=probe)
            start.assert_not_called()


if __name__ == '__main__':
    unittest.main()
