# Modular installer

`INSTALLER.cmd` opens the Windows installer. `FEATURE_SELECTOR.cmd` and
`python -m anno1503_overhaul gui` open the same interface. Python 3.10 or newer
and Tk support are required. World Settings activation also requires 64-bit
Python and the inspected AMD64 History Edition game build.

## Choose features and folders

The supported combinations are Food overhaul 0.5 alone and Food 0.5 with World
Settings 0.11.0-dev.1. Selecting World Settings selects and locks Food. Better
AI, LAN multiplayer and Knowledge overhaul remain research modules and cannot
be enabled by changing a saved profile.

Choose the installed game as **Original game folder**. Choose a new, separate
**Modded copy folder** outside that installation. Inside this repository, game
copies belong under ignored `.local/`; an unrelated existing directory is
never adopted or overwritten. The installer creates a managed copy marker and
copies game files without sharing writable files with the source. Existing mod
workspaces, historical backups and logs are excluded from the game copy.

**World Settings files** is needed for the combined World Settings selection. It
points to a local baseline store with complete `food_overhaul`,
`world_settings` and `launcher` packages. The initial migration preserved that
store under `.local/baselines/`. Food-only preparation uses reviewed public
source and authored artwork and does not require the private World payloads.

Click **Check installation** first. This validates feature dependencies, local
mod inputs, game fingerprints and original-file recovery inputs and prepares a
plan. It can create ignored package data but does not change the game. Review
the selected features, destination and required copy size before clicking
**Install selected features**. Installation rechecks its inputs before
publishing changes.

## Original files and recovery

The installer changes only its managed copy. It never installs Food in the
original game, runs historical restore scripts there or rewrites an existing
source backup.

For a clean supported source, the copied files already provide the vanilla
baseline. For a source containing Food changes, recovery reads known historical
backup layouts and accepts original bytes only when they match the reviewed
vanilla fingerprints. It checks whole native files, archives and supported UI
pairs. Backup journal claims alone do not establish that bytes are original.
If original bytes or supported fingerprints are unavailable, installation
stops instead of treating a preceding mod version as vanilla.

Installation uses one common restoration journal, `GrandOverhaul_Backup_v1`,
for the selected combination. It owns the composed Food and World changes
together; it does not stack unrelated patch installers onto the same native
file. Old restoration generations are retained when a restored copy is
installed again.

## Restore original game

Close Anno and select the managed modded-copy folder, then click **Restore
original game**. Restoration verifies the journal, backup originals and current
target fingerprints before publishing original bytes. Unknown changes are
refused rather than overwritten. Introduced runtime, AI and island payloads
are removed according to that same journal.

Restoration returns the files managed by this installer to the inspected
vanilla baseline. Saves and restoration backups are retained. It does not
delete the game copy, alter the installed Ubisoft game or remove arbitrary
files belonging to another mod. Restore before selecting another feature set.
Restoration uses retained backup bytes and reviewed source specifications; it
does not need the prepared package to remain available.

World Settings saves retain their feature requirements. In particular, a Huge
save is not made stock-game compatible by restoring the game files.

## World Settings startup dependency

The current World Settings implementation requires exact Food 0.5 in the
registered Ubisoft source installation as well as the exact combined build in
the marked independent copy. The installer checks this dependency without
changing the source. A clean vanilla source can install Food-only but cannot
currently launch the combined selection through this native path.

**Start with World Settings** uses the normal registered Ubisoft launch route
and the explicitly selected copy. It keeps the existing fresh-process,
main-menu, exact-module, complete-engine-profile and single-attempt activation
guards. It does not bypass Ubisoft authentication. World size, fertility,
islands, starting fleet and other world choices remain in the in-game menu.

## Prepared local packages

Prepared packages stay in ignored local storage. A combined package contains
`food/`, `world/`, `launcher/` and `manifest.json`. A Food-only package contains
`food/` and its manifest. Helper code comes from the reviewed public source,
not from arbitrary Python scripts supplied by a payload provider.

The combined provider must supply the exact frozen World specification with
SHA-256 `f43d4a136a0625836889a1379a70ecb60c589aa34d7acdc9a75db5206e2b5fec`
and all 25 named payloads with their reviewed hashes. The accepted runtime is
`2f9d1156f3ac53d92a900e41c38a169138c2b4ac7145f2dc92b93c48736cf089`.
The preserved raw specification remains in `world/frozen_world_patch.json`.
The relocated specification clears current-package gameplay claims and records
the explicit source/copy bindings and adapter version. Launcher specification
pins are regenerated for that exact local configuration.

Every use validates immutable helpers, specifications, native architecture and
payload fingerprints against the trusted recipe. Editing a package manifest
cannot authorize changed code or a different native DLL. Unexpected files and
reparse paths are rejected; only bounded diagnostic session/log locations are
mutable. The public source-only World specification and preserved baseline
packages remain unchanged.

Local preparation can also be invoked explicitly:

```console
python tools/prepare_installer_package.py --food-only --source-game "PATH_TO_GAME" --copy-game "PATH_TO_COPY" --output .local/installer-packages/food
python tools/prepare_installer_package.py --baselines .local/baselines --source-game "PATH_TO_FOOD_SOURCE" --copy-game "PATH_TO_COPY" --output .local/installer-packages/combined
```

These commands prepare mod inputs; they do not install or launch the game.
They refuse an existing output folder. A public clone contains the Food
reconstruction source, but no licensed World payloads, complete game islands,
private test corpus or compiler installation.

## Validation scope

Portable package tests use small synthetic native fixtures with explicit test
trust pins. They test rejection and storage behavior, not game compatibility.
Checking or preparing the real pinned inputs establishes package integrity.
Installation/restoration comparisons establish the files changed and restored
under those inputs. None of these checks is an actual game session, UI
acceptance test, Food economy test or new World save/reload observation.

Historical World Settings and launcher game evidence remains bounded to its
original build and observations. See [installer validation](INSTALLER_VALIDATION.md)
for the separately observed new installation, restoration, startup and in-game
menu checks. A new world/save comparison and gameplay session remain untested
for this installer integration.
