Anno 1503 - World Settings automatic launcher 1.0.0

Double-click "Anno 1503 - World Settings" on your desktop. The launcher checks
the installed test copy, starts Anno through Ubisoft Connect, waits through
startup and enables World Settings at the verified main menu. The startup
window closes after success. Choose a new endless game or load your save.
You do not need to run ACTIVATE_WORLD_SETTINGS.cmd separately.

Close an existing Anno session before using the shortcut. Startup may take
time while the intro plays. Leave Anno at its menu until World Settings is
enabled. If Ubisoft needs login or another startup choice, complete that
yourself. The launcher does not handle account or security prompts.

This launcher is for the tested Food + World Settings 0.11.0-dev.1 package
in the neighbouring anno1503_food_world_dev8 folder and its marked game copy.
It keeps that package, its engine payloads, installer, backups and existing
ZIP intact. The original tested activator still performs the guarded engine
transaction. A changed package, existing game, unsupported process or partial
activation is refused. Activation is attempted only once per launch.

The normal Ubisoft bootstrap may replace itself before the first main menu.
Only a unique, matching process created after this launcher started may be
activated. Once a menu is certified, process changes are refused. The final
worker checks the menu again and pins both process ID and creation time.

To recreate the desktop shortcut, run CREATE_SHORTCUT.cmd. It requires the
same 64-bit Python 3.10+ installation with window support. Existing unrelated
shortcuts are preserved. A second shortcut is kept in this launcher folder.

To remove automatic launching, delete the desktop shortcut. To restore the
World Settings game-copy files, close Anno and use the existing package's
RESTORE.cmd. The automatic launcher never installs or restores game files.
Closing Anno removes its temporary engine changes as before.

Launch logs remain locally in logs. On failure, use Open launch log. Close
Anno before retrying; a failed/uncertain activation is never repeated in that
game process. Automated tests and actual shortcut-run evidence are recorded
separately in AUTOMATED_TEST_RESULTS.json and LIVE_STARTUP_RESULTS.json.
