# Grand Overhaul 0.10.0-beta.1 validation

This release packages World Settings 0.9.0-beta.1, Food 0.6.0-dev.1 and Bug
Fixes 1.2 as independent installer choices. Food 0.6 needs new endless worlds.
The supported Food/World input set remains the inspected AMD64 History Edition
build with Dutch scene/UI data. Standalone Bug Fixes supports six verified
Ubisoft Connect language packs.

## Public preparation

The public combined recipe reconstructs the Food host, both AI modules and 16
island assets from the player's supported game, verified original backups and
tracked mod construction code. It does not read a private development baseline
or prebuilt runtime profile. Native exception tables are rebuilt from owned
DLLs locally; original game bytes are not included in the release.

A fresh public-source construction produced the existing reviewed combined
runtime `6bf858328c35610dc81135094e56258bd8e5b505d16af34cd04c171a4513f6e5`
and engine plan `e2375529553996e6e02c74814a97be1dddd45c9be6649ea048087e12299bb07c`.
Both reconstructed AI precursors and final Food AI outputs match their exact
prior fingerprints. All 43 imported compiled inputs remain unchanged.

The packaged worker accepts the exact public combined or Food-only package
kind, its version-owned recipe and retained launcher identity. Arbitrary
private development packages are not accepted by the Windows release worker.
Food 0.5 and its historical source recipes remain preserved separately.

## Evidence scope

The preceding all-mods source check passed fresh 1024-world creation, a saved
24-island preview comparison, and in-game loading of a compatible Huge save
with three active AI opponents. The house Food bar, original summary icon and
matching market icons were observed. Its 159-file installation/restoration
round trip passed. That run is documented separately in
[Food + World validation](FOOD_WORLD_VALIDATION.md).

The full regression run completed 904 tests: 899 passed and five Windows
symbolic-link privilege checks were skipped. The Windows nested-folder repair
also passed all 12 focused public-preparation checks and a real rebuild with
an audit hook refusing access to private baseline/runtime stores. It recorded
zero attempts to access those stores and reproduced the exact reviewed output.

A Windows candidate installed Food + Bug Fixes with World Settings disabled,
retained its sealed launcher, reached the managed game's normal main menu and
closed normally. Exact restoration of its 140 changed files passed. This is
startup and file evidence; it does not establish a new Food-only playthrough.

The frozen runtime's production import preflight passed, including pefile,
Capstone, Tk and the standard-library modules used by Food and Bug Fixes. The
archive includes the reviewed compiler and six sets of third-party notices.
Archive-specific installation, restoration, startup and all-three game-check
results, together with the ZIP SHA256, are published in the
[0.10.0-beta.1 release notes](https://github.com/GOjayson/anno1503-grand-overhaul/releases/tag/v0.10.0-beta.1).
Candidate artifacts and machine-specific logs stay in ignored local storage.

## Limits

Full population progression, long-session food balance, every setting
combination and perceived sound mixing are not established by bounded startup
and reload checks. Huge 2048 worlds remain experimental. Vanilla and Food 0.5
saves are not migrated to Food 0.6. Eight ordinary AI, new LAN multiplayer and
the Knowledge overhaul remain unimplemented research goals.

The original game, existing managed copies, saves, historical backups and the
0.9.0-beta.1 release archive are preserved. Game-derived DLLs, islands, archives,
sound files, saves and private launch context are excluded from the public ZIP.
