# Modular installer

## Windows beta

Extract the complete beta ZIP outside the game folder, close Anno, then open
**Anno1503OverhaulSetup.exe**. Check the detected original game folder and choose
a separate modded-copy folder. Leave Food unchecked for the World Settings beta.
Click **Check installation**, review the destination and copy size, then click
**Install selected features**. Use **Start with World Settings** after setup.

The bundle includes its Python runtime and compiler. Preparation reconstructs
the World-only files from your own supported game and verifies the result; no
private development baseline store is required. Game-derived data stays local.
Prepared packages and version-matched launch support live in the user's local
application-data cache, separate from the extracted download and original game.

This beta supports the inspected AMD64 History Edition build and Dutch scene/UI
data. Other localizations are refused until their exact files are verified.
Normal Ubisoft Connect authentication is still required. The original client
session is hidden only after its fresh menu is verified, before the modded
copy starts; the original session closes normally after the copy is ready.

The setup never changes the original Ubisoft installation. **Restore original
game** returns its managed copy to the checked originals and keeps saves and
backups. Huge/custom saves may still require the mod after restoration.

Food is optional and off by default. Its preserved combined development build
still needs matching development files and its existing native startup inputs;
the beta does not silently prepare or enable that combination. Food-only
preparation remains a separate experimental choice.

## Source and preserved development installations

`INSTALLER.cmd` opens the Windows installer. `FEATURE_SELECTOR.cmd` and
`python -m anno1503_overhaul gui` open the same interface. Python 3.10 or newer
and Tk support are required when running from source. World Settings preparation
also needs the reviewed Zig 0.16.0 compiler. The beta bundle supplies these
tools. World Settings activation requires 64-bit Python and the inspected AMD64
History Edition game build.

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

**Advanced: existing development files** is only for historical builds. It
points to a local baseline store with complete `food_overhaul`,
`world_settings` and `launcher` packages. The initial migration preserved that
store under `.local/baselines/`. Food-only preparation uses reviewed public
source and authored artwork and does not require the private World payloads.
The expanded menu requires its separately built, pinned runtime profile under
ignored `.local/runtime-profiles/options-world-only-<fingerprint>/` or
`options-food-world-<fingerprint>/`, matching the Food selection. Historical
runtime profiles remain preserved. Native build and local input requirements
are described below.

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
- **Food and World:** the expanded combined runtime keeps the existing exact
  Food 0.5 source-installation and combined-copy compatibility contract. Its
  working Food changes remain intact, and the historical runtime is preserved
  separately.

**Start with World Settings** uses normal Ubisoft authentication and the
explicitly selected profile. For World-only, a verified fresh normal client
launch supplies the existing startup context. The handoff rechecks that exact
owned main menu and starts the identical managed-copy executable once while
the normal source menu remains alive but hidden for client SDK initialization. After both
exact menus are verified, it requests the source menu's normal close and checks
that the copied host survives alone before native activation. Existing running games and worlds
are not adopted or closed. Startup arguments/environment remain in memory and
are not logged or saved; no authentication data are synthesized. Ubisoft
registration, installation paths and security settings are not edited.

The selected host must then pass the fresh-process, main-menu, exact-module,
complete-engine-profile and one-attempt activation guards. World size,
fertility, islands, starting fleet and other world choices remain in the
in-game menu. Consult [World options validation](WORLD_OPTIONS_VALIDATION.md)
for the expanded profile's actual startup, preset and native-save reload
acceptance. The earlier stock-host observations remain in
[decoupling validation](DECOUPLING_VALIDATION.md).

The Windows beta can create a desktop shortcut for World Settings. The
**Create a desktop shortcut for World Settings** checkbox is selected by
default. The shortcut uses the installed copy and its selected feature profile.
If you leave it unchecked, or shortcut creation fails, use **Start with World
Settings** in the setup window.

## Configure a world inside Anno

Starting a supported endless game first offers **Original game**, **Custom
world** or **Back**. Original game uses Anno's normal setup and generation and
ignores World Settings choices. Custom world opens the mod's setup screen.
Tutorials, campaigns and other scenarios keep their native start route.

The setup tabs are **Map**, **Players**, **Start**, **Presets**, **Details**,
**Explore**, **Islands** and **Disasters**. The map preview, seed, regeneration
and Start controls remain beside them. A preview with revealed geography lets
you inspect islands and choose an eligible preferred starting island. Terra
incognita conceals the preview and island details instead.

A seed and the same world options reproduce the preview when used with the
matching generator version. Regenerate chooses another seed. Start uses that
validated preview plan; impossible geometry or missing required resources
block creation with an explanation. A played world's later AI decisions and
events can differ even when its starting map is the same.

On **Explore**, choose **Unexplored (terra incognita)**, **Geography revealed**
or **Fully explored**. Unexplored covers uncharted land and sea; your ships,
settlements and eligible deployed scouts/military units chart nearby terrain.
Strict line of sight hides live enemy ships and units outside current sight,
while buildings retain their last-seen appearance until you return. **Reveal
all activity** shows live activity in charted areas; unexplored areas stay
covered. Exploration and remembered buildings are stored with each native save.
Use the compatible World Settings launcher when reopening those saves.

On **Presets**, save a named combination or load an existing one. Version-5
presets store all 43 choices and the map seed in the managed copy's
`WorldSettingsPresets/` folder. Supported exact predecessor versions can load
without rewriting their files; unknown generator identities are refused.
Presets remain when restoring original game files. Installer feature profiles
select Food and World Settings only; they do not configure individual worlds.

The [environment options guide](WORLD_ENVIRONMENT_OPTIONS.md) describes island
variety, rotation, climate counts and disasters, with their validation scope.
Earlier shortcut reports, visibility instructions and acceptance statements
are preserved separately in [historical installer guidance](INSTALLER_HISTORY.md).
Those older results do not establish current beta gameplay or long-session
stability.

## Historical package implementation

The technical package descriptions and fingerprints below belong to preserved
development installers. They are not the public beta preparation instructions
or a validation record for this beta. Use the Windows beta steps above for a
new installation; those steps reconstruct the World-only package locally from
your verified game files.

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

| Preserved World-only artifact | SHA-256 |
| --- | --- |
| Canonical runtime | `4ede7aefddeb78319328f9de7e4597e49d6d1652739539c29afe5439024a86e9` |
| Stock-bound engine plan | `71940166c7131f78d1b5efd68c1e6dff0299ea8d3334ed811420da4a53fa1f4e` |

The installer prepares the separate expanded-menu package kind for both
profiles. It retains and verifies the frozen corpus and binds the exact
runtime, generator identity and snapshot schema. Experimental 0.6 uses
120-byte settings, a 5256-byte preview and 29-choice version-3 presets.
Its current r8 build fingerprints, automated checks and bounded World-only
acceptance evidence belong in the
[visibility validation record](WORLD_VISIBILITY_VALIDATION.md), not in the
historical tables below.

The preserved 0.5 schema used 112-byte settings and a 5248-byte preview; its
build and acceptance state remains recorded in
[fairness validation](WORLD_FAIRNESS_VALIDATION.md).

| Historical 0.5 expanded-menu native profile | SHA-256 |
| --- | --- |
| World only | `3ae9e17383ff7aa4405fe0a39274f81e443d545f10582c395cc97c138554f371` |
| Food and World | `f2eab1d1a9dcb7aaa35f2e28b277101e94d0b538a9b77583f59d031cad1d381b` |

The historical 0.5 generator fingerprint is
`ws5-9763e325b88da3c2e60d75368626888fe5effa444071076c45bb3683dada1808`.
Both profiles compiled three times to their identical reviewed output, with
exact native preimage checks. Those earlier builds do not validate the 0.6
visibility runtime. Compilation remains separate from actual game acceptance.

The preserved 0.4 schema was 96-byte settings and a 5232-byte preview. Its
historical reviewed canonical runtimes are:

| Historical 0.4 expanded-menu native profile | SHA-256 |
| --- | --- |
| World only | `f7a070e6825a9269e61d2f504e0e855f38002be13ad5befedcf87bd5081f8b14` |
| Food and World | `23b2b69956d70e900cb0fa0aa079fdc5b7f00215b74c853c276ac90633fb837f` |

The historical 0.4 generator fingerprint is
`ws4-443c04febaf41fe2328c0084ad379232a6e7d6a6b049c70707f587d768cccf1a`.
Changing authored native generator source requires another reviewed build and
matching package/preset identity. Historical validators and pins remain intact.

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
python tools/build_world_options_runtime.py --profile world-only --game "PATH_TO_VERIFIED_STOCK_COPY" --publish
python tools/build_world_options_runtime.py --profile food-world --game "PATH_TO_SUPPORTED_FOOD_SOURCE" --publish
python tools/prepare_installer_package.py --world-only --baselines .local/baselines --source-game "PATH_TO_GAME" --copy-game "PATH_TO_COPY" --output .local/installer-packages/world-only
python tools/prepare_installer_package.py --baselines .local/baselines --source-game "PATH_TO_FOOD_SOURCE" --copy-game "PATH_TO_COPY" --output .local/installer-packages/combined
```

These commands prepare mod inputs; they do not install or launch the game.
They refuse an existing output folder. The expanded native builder uses Zig
0.16.0 and the exact native inputs for the selected profile, checks the original
43 compiled-source fingerprints and native hook/engine/unwind preimages, then
publishes only its reviewed canonical output when requested. It preserves the
488 imported legacy source files, all 43 original compiled-source inputs,
previous builds and historical runtimes, while existing restoration backup
generations remain retained. A public clone contains the Food
reconstruction source, but no licensed World payloads, complete game islands,
private test corpus or compiler installation.

## Historical validation scope

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
The seven expanded settings have separate source, fixture, compilation and
actual-game evidence in [World options validation](WORLD_OPTIONS_VALIDATION.md).
The 0.6 [visibility record](WORLD_VISIBILITY_VALIDATION.md) separately records
r8's World-only automatic startup, certified-save reload and the user's
smooth camera/visibility sample. Food + World builds, scene APIs and
production installation/restoration were checked; its actual visibility
gameplay run was omitted at the user's request. Those automated checks do not
stand in for a Food live run or establish long-session gameplay performance.
