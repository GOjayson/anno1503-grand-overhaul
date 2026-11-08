# Anno 1503 Grand Overhaul

A modular overhaul project for **Anno 1503 History Edition**. Development lives
outside the installed game, with optional features chosen before installation
or launch and world-specific settings configured inside Anno.

The starting point is the existing experimental World Settings, Food overhaul
and automatic-launch work. Food and World Settings have independent checkboxes:
choose either feature or both on a separate managed game copy. The installer
also restores the files it manages to their verified original-game baseline.

| Feature | Priority | Status |
| --- | --- | --- |
| World Settings | Priority | Preserved combined baseline plus a separate experimental World-only stock-game profile; see its validation scope |
| Food overhaul | Priority | Imported experimental 0.5.0; economy and AI work remain unfinished |
| Local-host multiplayer | Priority | Research; host/join, synchronization and capacity need verification |
| Smarter / better AI | Planned | Behaviour improvements and a target of eight ordinary AI opponents |
| Knowledge overhaul | Planned | Expanded schools, universities and knowledge progression |

**Eight AI opponents and eight human multiplayer slots are separate research
targets.** Flag colours do not establish either engine limit. Current World
Settings supports zero to three ordinary AI opponents from inspected stock
placeholders; that is not a verified universal engine maximum.

## Install or restore

On Windows, open `INSTALLER.cmd`. The installer needs Python 3.10 or newer
with Tk support; World Settings startup needs 64-bit Python. Choose your
installed History Edition folder and a separate destination for the modded
copy, then select the feature checkboxes:

1. **Food overhaul:** enable the Food 0.5 gameplay changes, or leave it unchecked
   to retain the stock food economy.
2. **World Settings:** enable world configuration independently of Food. This
   choice needs the complete preserved local mod inputs; World-only also needs
   its separately pinned native runtime profile.
3. Click **Check installation**, review the destination and copy size, then
   click **Install selected features**.

**Restore original game** affects this installer's managed copy. It restores
the checked vanilla files, removes introduced mod payloads, and retains saves
and restoration backups. Restore before changing installed features. Close
Anno before installation or restoration; unknown or independently changed
files are refused.

The original installed game and its existing backups are read-only inputs.
If the source already has Food changes, the installer needs verified original
bytes from its existing backups to prepare a vanilla baseline in the copy.
A clean supported source needs no such recovery.

World-only keeps the inspected stock food definitions, markets, archives, UI
and native host DLLs. Its copied executable is the actual game host and world
data root; Food changes in the input installation are not carried into that
world. The preserved combined profile keeps its existing Food implementation
and exact startup contract.

**Start with World Settings** uses normal Ubisoft authentication and the
selected profile's guarded launch path. World-only relays the verified normal
client startup context to the identical managed copy in memory; it does not
change installation registration or persist startup values. The new profile's
live startup/gameplay validation is tracked separately in
[decoupling validation](docs/DECOUPLING_VALIDATION.md). World options remain
inside Anno; Huge saves still need the compatible runtime after restoration.

A public clone can prepare Food-only installation inputs. World Settings also
requires a local payload provider containing the complete preserved
`food_overhaul`, `world_settings` and `launcher` packages; this machine's
provider is ignored under `.local/baselines/`. Full game DLLs, complete islands
and private evidence are not downloaded or included in Git.

See [installer usage and limitations](docs/INSTALLER.md) for the local package
contract and restoration behavior.

## Feature profiles

The profile and installer framework has no third-party Python runtime
dependencies. It can also be opened through:

```console
python -m pip install -e .
python -m anno1503_overhaul gui
```

`FEATURE_SELECTOR.cmd` remains an alias for the installer. Profiles save feature
choices separately from installation. Research features remain unavailable.
Food and World Settings selections stay independent when saved and reloaded.
Restore the managed copy before changing an installed feature set, then use a
fresh launch. This is an installation choice, not a switch inside a running
world.

```console
python -m anno1503_overhaul features
python -m anno1503_overhaul new-profile profiles/default.json
python -m anno1503_overhaul validate profiles/default.json
```

Profiles contain feature flags only. Map size, islands, fertility, starting
fleet and other world options remain in the game's World Settings screen.

## Source and local builds

| Path | Contents |
| --- | --- |
| `src/anno1503_overhaul/` | Feature catalogue, profiles, installer, verified local packages, copy creation and restoration |
| `legacy/world_settings/` | Imported World Settings source with its internal build layout preserved |
| `legacy/food_overhaul/` | Imported Food source, patch descriptions and authored artwork |
| `legacy/launcher/` | Imported automatic startup source and readiness checks |
| `docs/` | Architecture, roadmap, feature status and migration details |
| `provenance/` | Relative source provenance and original/imported fingerprints |
| `.local/` | Ignored local baselines, game inputs, compiler tools and build candidates |

Original/patched game DLLs, executable files, complete game islands, saves and
compiler caches are kept out of Git. The initial local migration preserves the
complete tested packages and release ZIPs separately under `.local/baselines/`.
The existing installed mod, game copy, desktop shortcut and backups remain in
place.

The imported public World Settings specification remains explicitly a source
snapshot and refuses direct legacy installation or activation. The modular
installer instead prepares a local package from exact, pinned preserved inputs,
binds its game paths explicitly and records the relocation as new integration.
Historical live-test evidence stays bound to the frozen runtime; package
preparation does not count as a new game run.

The preserved combined World Settings runtime can be compiled into a new local candidate
outside the game folder on Windows with the matching Zig 0.16.0 toolchain:

```console
python tools/build_world_runtime.py --tools PATH_TO_LOCAL_COMPILER_TOOLS
```

The tools directory must contain `ziglang/zig.exe` and its libraries. An ignored
`.local/toolchain/` installation is discovered automatically. The builder writes
only beneath `.local/builds/` and does not install, launch or patch Anno. Full
payload reconstruction from arbitrary new native builds and save compatibility
need their own integration work. The combined installer accepts the reviewed
frozen runtime rather than automatically accepting a rebuilt DLL.

The independent stock-game runtime has a separate controlled builder:

```console
python tools/build_world_only_runtime.py --vanilla-game PATH_TO_VERIFIED_STOCK_COPY
```

It verifies the imported source fingerprints and all stock hook/engine
preimages, stages reviewed changes, and accepts only the pinned canonical
World-only output. It writes beneath ignored `.local/builds/` and
`.local/runtime-profiles/`; it does not install or start the game. The old
combined runtime and imported source remain intact.

## Checks and contributions

```console
python -B -m unittest discover -s tests -v
python -B tools/check_repository.py
```

Portable checks run in GitHub Actions on Windows and Linux. Native instruction
fixtures, actual game runs, save comparisons and long-session gameplay are
separate evidence. Keep that distinction in changes and reports.

See [the roadmap](docs/ROADMAP.md), [feature status](docs/FEATURES.md),
[architecture](docs/ARCHITECTURE.md), [import scope](docs/IMPORT_SCOPE.md) and
[contribution guide](CONTRIBUTING.md).

This is an independent community project. No project-wide license has been
selected yet; existing component notices are retained.
