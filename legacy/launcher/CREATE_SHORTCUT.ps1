[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$taskLauncherRoot = $PSScriptRoot
$taskScript = Join-Path $taskLauncherRoot 'launch_world_settings.pyw'
if (-not (Test-Path -LiteralPath $taskScript -PathType Leaf)) { throw 'The World Settings launcher is missing.' }
$taskPythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
if ($null -ne $taskPythonCommand) {
    $taskPythonPath = & $taskPythonCommand.Source -B -c 'import sys,struct,tkinter; assert sys.version_info >= (3,10) and struct.calcsize("P")==8; print(sys.executable)'
} else {
    $taskPythonPath = & py -3-64 -B -c 'import sys,struct,tkinter; assert sys.version_info >= (3,10) and struct.calcsize("P")==8; print(sys.executable)'
}
if ($LASTEXITCODE -ne 0 -or -not $taskPythonPath) { throw '64-bit Python 3.10 or newer with window support is required.' }
$taskPythonwPath = Join-Path (Split-Path -Parent ([string]$taskPythonPath).Trim()) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $taskPythonwPath -PathType Leaf)) { throw 'The Python window launcher could not be found.' }
$taskSpecPath = Join-Path $taskLauncherRoot '../anno1503_food_world_dev8/world_patch.json'
$taskSpec = Get-Content -LiteralPath $taskSpecPath -Raw | ConvertFrom-Json
$taskConfig = Get-Content -LiteralPath (Join-Path $taskLauncherRoot 'launcher_config.json') -Raw | ConvertFrom-Json
if ((Get-FileHash -LiteralPath $taskSpecPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskConfig.package_spec_sha256) { throw 'The tested World Settings package does not match this shortcut.' }
$taskIcon = Join-Path $taskSpec.original_game_root 'Anno1503.exe'
$taskDesktop = [Environment]::GetFolderPath('DesktopDirectory')
$taskTargets = @(
    (Join-Path $taskLauncherRoot 'Anno 1503 - World Settings.lnk'),
    (Join-Path $taskDesktop 'Anno 1503 - World Settings.lnk')
)
$taskShell = New-Object -ComObject WScript.Shell
$taskArguments = '-B "' + $taskScript + '"'
# Validate all existing destinations before creating either shortcut. Preserve
# user changes or unrelated shortcuts instead of overwriting them.
foreach ($taskTarget in $taskTargets) {
    if (Test-Path -LiteralPath $taskTarget) {
        $taskExisting = $taskShell.CreateShortcut($taskTarget)
        if ($taskExisting.TargetPath -ne $taskPythonwPath -or $taskExisting.Arguments -ne $taskArguments -or $taskExisting.WorkingDirectory -ne $taskLauncherRoot) {
            throw ('An existing shortcut is different and was preserved: ' + $taskTarget)
        }
    }
}
$taskResults = @()
foreach ($taskTarget in $taskTargets) {
    $taskCreated = -not (Test-Path -LiteralPath $taskTarget)
    if ($taskCreated) {
        $taskShortcut = $taskShell.CreateShortcut($taskTarget)
        $taskShortcut.TargetPath = $taskPythonwPath
        $taskShortcut.Arguments = $taskArguments
        $taskShortcut.WorkingDirectory = $taskLauncherRoot
        $taskShortcut.IconLocation = $taskIcon + ',0'
        $taskShortcut.Description = 'Start Anno 1503 and automatically enable the tested World Settings build.'
        $taskShortcut.Save()
    }
    $taskVerified = $taskShell.CreateShortcut($taskTarget)
    if ($taskVerified.TargetPath -ne $taskPythonwPath -or $taskVerified.Arguments -ne $taskArguments -or $taskVerified.WorkingDirectory -ne $taskLauncherRoot) { throw 'Shortcut verification failed.' }
    $taskResults += [PSCustomObject]@{Path=$taskTarget;Created=$taskCreated;Target=$taskVerified.TargetPath;Arguments=$taskVerified.Arguments;WorkingDirectory=$taskVerified.WorkingDirectory}
}
$taskReport = [PSCustomObject]@{Passed=$true;Version='1.0.0';Shortcuts=$taskResults;GameFilesModified=$false}
$taskReport | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $taskLauncherRoot 'SHORTCUT_INSTALLATION.json') -Encoding utf8
$taskReport | ConvertTo-Json -Depth 5
