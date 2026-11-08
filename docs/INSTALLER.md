# Modular installer

`INSTALLER.cmd` opens the Windows installer. `FEATURE_SELECTOR.cmd` and
`python -m anno1503_overhaul gui` open the same interface. Python 3.10 or newer
and Tk support are required. World Settings activation also requires 64-bit
Python and the inspected AMD64 History Edition game build.

## Choose features and folders

Food and World Settings are independent checkboxes. Choose Food overhaul 0.5
alone, World Settings alone, or both. Leaving Food unchecked selects the
separate stock-game World-only profile; it does not silently keep Food's
native or economy changes. Better AI, LAN multiplayer and Knowledge overhaul
remain research modules and cannot be enabled by changing a saved profile.

Choose the installed game as **Original game folder**. Choose a new, separate
**Modded copy folder** outside that installation. Inside this repository, game
copies belong under ignored `.local/`; an unrelated existing directory is
never adopted or overwritten. The installer creates a managed copy marker and
copies game files without sharing writable files with the source. Existing mod
workspaces, historical backups and logs are excluded from the game copy.

**World Settings files** is needed whenever World Settings is selected. It
points to a local baseline store with complete `food_overhaul`,
`world_settings` and `launcher` packages. The initial migration preserved that
store under `.local/baselines/`. Food-only preparation uses reviewed public
source and authored artwork and does not require the private World payloads.
World-only also requires the separately built, pinned runtime profile under
ignored `.local/runtime-profiles/world-only-v1/`. Its native build and local
input requirements are described below.

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

## World Settings startup

The startup path depends on the selected native profile:

- **World only:** the independent copy's executable is the actual game host and
  world data root. Its checked diet, market definitions, archives, UI images
  and native host DLLs stay stock. Food is not required in that host. When the
  input installation has Food changes, the installer reads verified stock
  originals from its retained backups rather than carrying Food into the host.
- **Food and World:** the preserved combined runtime keeps its existing exact
  Food 0.5 source-installation and combined-copy compatibility contract. Its
  working Food changes and old runtime remain intact.

**Start with World Settings** uses normal Ubisoft authentication and the
explicitly selected profile. For World-only, a verified fresh normal client
launch supplies the existing startup context. The handoff rechecks that exact
owned main menu and starts the identical managed-copy executable once while
the normal source menu remains alive for client SDK initialization. After both
exact menus are verified, it requests the source menu's normal close and checks
that the copied host survives alone before native activation. Existing running games and worlds
are not adopted or closed. Startup arguments/environment remain in memory and
are not logged or saved; no authentication data are synthesized. Ubisoft
registration, installation paths and security settings are not edited.

The selected host must then pass the fresh-process, main-menu, exact-module,
complete-engine-profile and one-attempt activation guards. World size,
fertility, islands, starting fleet and other world choices remain in the
in-game menu. Consult [decoupling validation](DECOUPLING_VALIDATION.md) for the
new stock-host profile's actual startup and gameplay acceptance status.

## Prepared local packages

Prepared packages stay in ignored local storage. A combined package contains
`food/`, `world/`, `launcher/` and `manifest.json`. A Food-only package contains
`food/` and its manifest. Helper code comes from the reviewed public source,
not from arbitrary Python scripts supplied by a payload provider.

The World input provider must supply the exact frozen World specification with
SHA-256 `f43d4a136a0625836889a1379a70ecb60c589aa34d7acdc9a75db5206e2b5fec`
and all 25 named payloads with their reviewed hashes. The preserved combined runtime is
`2f9d1156f3ac53d92a900e41c38a169138c2b4ac7145f2dc92b93c48736cf089`.
The preserved raw specification remains in `world/frozen_world_patch.json`.
The relocated specification clears current-package gameplay claims and records
the explicit source/copy bindings and adapter version. Launcher specification
pins are regenerated for that exact local configuration.

The World-only recipe reuses that corpus as verified input, not as executable
provider code or as a Food installation. It additionally retains stock native
inputs for independent recipe verification and uses:

| World-only artifact | SHA-256 |
| --- | --- |
| Canonical runtime | `4ede7aefddeb78319328f9de7e4597e49d6d1652739539c29afe5439024a86e9` |
| Stock-bound engine plan | `71940166c7131f78d1b5efd68c1e6dff0299ea8d3334ed811420da4a53fa1f4e` |

World-only installs the runtime, private World-policy AI modules and island
assets. It leaves the inspected stock host DLLs, Food definitions, archives and
UI files unchanged. Two exception-table edit locations differ from the frozen
combined plan because the Food version had relocated that table. The derived
plan uses unique matched stock function records, while preserving all 173
before/after edits and validating every preimage.

Every use validates immutable helpers, specifications, native architecture and
payload fingerprints against the trusted recipe. Editing a package manifest
cannot authorize changed code or a different native DLL. Unexpected files and
reparse paths are rejected; only bounded diagnostic session/log locations are
mutable. The public source-only World specification and preserved baseline
packages remain unchanged.

Local preparation can also be invoked explicitly:

```console
python tools/prepare_installer_package.py --food-only --source-game "PATH_TO_GAME" --copy-game "PATH_TO_COPY" --output .local/installer-packages/food
python tools/build_world_only_runtime.py --vanilla-game "PATH_TO_VERIFIED_STOCK_COPY"
python tools/prepare_installer_package.py --world-only --baselines .local/baselines --source-game "PATH_TO_GAME" --copy-game "PATH_TO_COPY" --output .local/installer-packages/world-only
python tools/prepare_installer_package.py --baselines .local/baselines --source-game "PATH_TO_FOOD_SOURCE" --copy-game "PATH_TO_COPY" --output .local/installer-packages/combined
```

These commands prepare mod inputs; they do not install or launch the game.
They refuse an existing output folder. The World-only native builder uses Zig
0.16.0 and verified stock native inputs, checks the original 43 compiled-source
fingerprints and native hook/engine/unwind preimages, then accepts only its
reviewed canonical output. It preserves the imported source, previous builds
and combined runtime. A public clone contains the Food
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
menu checks on the preserved combined profile. The independent profile's
[decoupling validation](DECOUPLING_VALIDATION.md) separately records packaged
automatic startup, a new 1024 world, stock resident diets and native save reload
after a fresh process. Extended gameplay, active ordinary AI and a new Huge
World-only world were not exercised by that acceptance run.
