"""Create a beta desktop entry without replacing a user's existing shortcut."""
import base64
import json
import os
from pathlib import Path
import re
import subprocess


def _literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def create_desktop_shortcut(executable, arguments, working_directory):
    if os.name != 'nt':
        raise RuntimeError('Desktop shortcuts require Windows.')
    executable, working_directory = Path(executable), Path(working_directory)
    if not executable.is_file() or not working_directory.is_dir():
        raise RuntimeError('The installed launcher is missing; use Setup to check the installation.')
    command_line = subprocess.list2cmdline(list(arguments))
    script = """$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$taskDesktop=[Environment]::GetFolderPath('DesktopDirectory')
$taskShell=New-Object -ComObject WScript.Shell
$taskTarget=EXECUTABLE
$taskArguments=ARGUMENTS
$taskWorking=WORKING
$taskBase='Anno 1503 - World Settings Beta'
$taskSelected=$null
for($taskIndex=1;$taskIndex -le 100;$taskIndex++) {
    $taskName=if($taskIndex -eq 1){$taskBase+'.lnk'}else{$taskBase+' ('+$taskIndex+').lnk'}
    $taskPath=Join-Path $taskDesktop $taskName
    if(-not (Test-Path -LiteralPath $taskPath)){$taskSelected=$taskPath;break}
    $taskExisting=$taskShell.CreateShortcut($taskPath)
    if($taskExisting.TargetPath -ceq $taskTarget -and $taskExisting.Arguments -ceq $taskArguments -and $taskExisting.WorkingDirectory -ceq $taskWorking){
        [Console]::WriteLine((@{path=$taskPath;created=$false;existing_preserved=$true}|ConvertTo-Json -Compress));exit 0
    }
}
if(-not $taskSelected){throw 'No unused beta shortcut name is available.'}
if(Test-Path -LiteralPath $taskSelected){throw 'The chosen shortcut appeared independently; existing files were kept.'}
$taskLink=$taskShell.CreateShortcut($taskSelected)
$taskLink.TargetPath=$taskTarget
$taskLink.Arguments=$taskArguments
$taskLink.WorkingDirectory=$taskWorking
$taskLink.Description='Launch Anno 1503 with World Settings enabled automatically'
$taskLink.WindowStyle=1
$taskLink.Save()
$taskCheck=$taskShell.CreateShortcut($taskSelected)
if($taskCheck.TargetPath -cne $taskTarget -or $taskCheck.Arguments -cne $taskArguments -or $taskCheck.WorkingDirectory -cne $taskWorking){throw 'The new shortcut did not retain the installed launcher.'}
[Console]::WriteLine((@{path=$taskSelected;created=$true;existing_preserved=$true}|ConvertTo-Json -Compress))
"""
    literals = {'EXECUTABLE': _literal(executable), 'ARGUMENTS': _literal(command_line), 'WORKING': _literal(working_directory)}
    script = re.sub(r'\b(EXECUTABLE|ARGUMENTS|WORKING)\b', lambda match: literals[match.group()], script)
    encoded = base64.b64encode(script.encode('utf-16-le')).decode('ascii')
    result = subprocess.run(['powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
                            creationflags=subprocess.CREATE_NO_WINDOW, capture_output=True, text=True, encoding='utf-8', timeout=30)
    if result.returncode:
        raise RuntimeError('The game is installed, but Windows could not create its desktop shortcut. Use Start with World Settings in Setup.')
    value = json.loads(result.stdout)
    if not isinstance(value, dict) or value.get('existing_preserved') is not True or not isinstance(value.get('path'), str):
        raise RuntimeError('Windows did not confirm the desktop shortcut. The installed game was kept.')
    return value
