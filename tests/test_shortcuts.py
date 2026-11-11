"""Windows shortcut transport preserves literal paths and existing entries."""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from anno1503_overhaul import shortcuts


@unittest.skipUnless(os.name == 'nt', 'Windows shortcut transport.')
class Shortcuts(unittest.TestCase):
    def test_paths_and_arguments_are_literal_and_existing_entries_are_preserved(self):
        with tempfile.TemporaryDirectory(prefix='anno-shortcut-') as temporary:
            directory = Path(temporary) / "Héloise's $(literal) EXECUTABLE ARGUMENTS WORKING"
            directory.mkdir()
            executable = directory / 'Setup.exe'
            executable.write_bytes(b'fixture; never executed')
            arguments = ['-B', str(directory / 'launch world.pyw')]
            response = {'path': str(directory / 'existing.lnk'), 'created': False, 'existing_preserved': True}
            with mock.patch.object(shortcuts.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, json.dumps(response), '')) as run:
                self.assertEqual(shortcuts.create_desktop_shortcut(executable, arguments, directory), response)
            call = run.call_args
            self.assertEqual(call.kwargs['creationflags'], subprocess.CREATE_NO_WINDOW)
            self.assertEqual(call.kwargs['encoding'], 'utf-8')
            script = base64.b64decode(call.args[0][-1]).decode('utf-16-le')
            self.assertIn('$taskTarget=' + shortcuts._literal(executable), script)
            self.assertIn('$taskArguments=' + shortcuts._literal(subprocess.list2cmdline(arguments)), script)
            self.assertIn('$taskWorking=' + shortcuts._literal(directory), script)
            self.assertIn('The chosen shortcut appeared independently; existing files were kept.', script)

    def test_missing_installed_launcher_never_invokes_windows(self):
        with tempfile.TemporaryDirectory(prefix='anno-shortcut-') as temporary, mock.patch.object(shortcuts.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'launcher is missing'):
                shortcuts.create_desktop_shortcut(Path(temporary) / 'absent.exe', [], temporary)
            run.assert_not_called()
