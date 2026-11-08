# Anno 1503 Grand Overhaul

A modular overhaul project for **Anno 1503 History Edition**. Development lives
outside the installed game, with optional features chosen before installation
or launch and world-specific settings configured inside Anno.

The starting point is the existing experimental World Settings, Food overhaul
and automatic-launch work. This repository preserves their source, introduces
a feature-profile foundation and records the work needed for the larger mod.

| Feature | Priority | Status |
| --- | --- | --- |
| World Settings | Priority | Imported experimental 0.11.0-dev.1; corrected Huge-world baseline preserved locally |
| Food overhaul | Priority | Imported experimental 0.5.0; economy and AI work remain unfinished |
| Local-host multiplayer | Priority | Research; host/join, synchronization and capacity need verification |
| Smarter / better AI | Planned | Behaviour improvements and a target of eight ordinary AI opponents |
| Knowledge overhaul | Planned | Expanded schools, universities and knowledge progression |

**Eight AI opponents and eight human multiplayer slots are separate research
targets.** Flag colours do not establish either engine limit. Current World
Settings supports zero to three ordinary AI opponents from inspected stock
placeholders; that is not a verified universal engine maximum.

## Feature profiles

Python 3.10 or newer is required. The profile framework has no third-party
runtime dependencies. The graphical selector uses Python's Tk support.

```console
python -m pip install -e .
python -m anno1503_overhaul gui
```

On Windows, `FEATURE_SELECTOR.cmd` also opens the selector from this checkout.
It saves selections; **a common modular installer is still under development**.
Research features are visible but unavailable for selection. World Settings
currently requires Food 0.5, so selecting it also selects Food. Decoupling that
dependency is a planned compatibility task.

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
| `src/anno1503_overhaul/` | New feature catalogue, profile validation, CLI and selector |
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

The imported public World Settings specification is explicitly a source
snapshot. It refuses installation and activation from this checkout. The
preserved local baseline retains its original metadata and bounded live-test
evidence. A migrated source tree is not itself a newly tested game release.

The native World Settings runtime can be compiled into a new local candidate
outside the game folder on Windows with the matching Zig 0.16.0 toolchain:

```console
python tools/build_world_runtime.py --tools PATH_TO_LOCAL_COMPILER_TOOLS
```

The tools directory must contain `ziglang/zig.exe` and its libraries. An ignored
`.local/toolchain/` installation is discovered automatically. The builder writes
only beneath `.local/builds/` and does not install, launch or patch Anno. Full
payload reconstruction, common installation and save compatibility need their
own integration work.

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
