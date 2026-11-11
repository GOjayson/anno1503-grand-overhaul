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
| World Settings | Priority | Experimental 0.6.0-dev.7 performance candidate; prior build improved camera movement but lag remained; new live acceptance pending |
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
   choice needs the complete preserved local mod inputs and the separately
   pinned runtime for the selected Food/World combination.
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
world. The Food + World profile keeps the existing Food implementation and
exact source-installation startup contract. The expanded menu uses separately
reviewed new runtimes for both selections; historical runtime profiles remain
available unchanged.

**Start with World Settings** uses normal Ubisoft authentication and the
selected profile's guarded launch path. World-only relays the verified normal
client startup context to the identical managed copy in memory; it does not
change installation registration or persist startup values. Earlier stock-host
startup and gameplay observations are recorded separately in
[decoupling validation](docs/DECOUPLING_VALIDATION.md). World options remain
inside Anno; Huge saves still need the compatible runtime after restoration.
The seven earlier menu additions are recorded in
[World options validation](docs/WORLD_OPTIONS_VALIDATION.md). The new island,
starting-position and resource controls have a separate
[fairness validation record](docs/WORLD_FAIRNESS_VALIDATION.md). Experimental
0.6 visibility work has a separate [development validation record](docs/WORLD_VISIBILITY_VALIDATION.md).
Development **0.6.0-dev.7** reduces further duplicate graphics and island memory
checks within individual calls, retaining fresh fields and original fallbacks.
All 169 visibility tests, six matching builds and World-only installation/
restoration passed. Saves, presets and all preceding backups were retained.
The updated automatic shortcut is installed; fresh game acceptance is pending.

The preceding **0.6.0-dev.6** reduces repeated memory-protection queries while
keeping fresh object, ownership and asset checks. All 160 visibility tests,
six matching builds, and World-only installation/restoration passed. The updated
shortcut's automatic startup, `wc5` loading and read-only world checks passed.
The user confirmed correct remembered buildings/fog and improved camera movement,
but lag remains.
Observation timestamps and recorded building state are unchanged.

The preceding **0.6.0-dev.5** adds an island lookup index for each draw and exact
uniform fog spans, plus passive coarse-stage timings for the actual game.
Independent source/fixture checks, all six matching profile builds and the full
suite passed: 371 tests passed and five Windows link-privilege tests were skipped.
Installation/restoration checks passed, ending with World Settings on and Food
off; the desktop shortcut was updated. Fresh automatic startup and `wc5` loading
passed. The user confirmed correct remembered towns/fog, but camera movement
remains unchanged or worse. Live elapsed timings identify chart observation as
the larger remaining cost; the performance repair is incomplete. Food gameplay
is not being repeated. See the development validation record for bounded evidence.

The preceding **0.6.0-dev.4** grouped remembered
sprites within each draw, preserving exact recorded appearance and animation
time. All six builds passed independent review, with three identical runtimes per
Food selection. Targeted tests, native instruction checks and 72 isolated
compiled-DLL scene stages passed. The full suite completed 358 tests: 353
passed and five Windows link-privilege tests were skipped. Closed-game data
preservation and the production installation/restoration cycle passed. The
new World-only build is installed and its shortcut was updated; automatic
startup and loading `wc4` passed. The user confirmed correct remembered towns
and saved `wc5`; independent file checks retained exploration history and world
geometry. Camera movement still feels laggy while the stationary view is smooth,
so the performance repair remains incomplete. CPU benchmarks show a reduction
in this specific work; they do not establish game FPS.

The preceding dev.3 V4 installation/restoration cycle and fresh `wc3` load
passed. The user confirmed foreign controls blocked, own controls working and
scout exploration, then saved `wc4`. Its exploration-history file certificate
and an eligible native scout observer check passed. Lag improved but remained
noticeable. Those bounded ownership/scout results remain valid evidence for V4;
they are not acceptance of the new batching candidate. Food + World gameplay
is not being repeated at the user's request.

The preceding 0.6.0-dev.2 V3 candidate passed automated and installer checks.
Its stock profile loaded `wv63`, displayed fog over unknown land and sea, and
produced independently checked `wc1`, `wc2` and `wc3` checkpoints. The user
confirmed that known buildings remain visible while away and update on return,
then reported lag, foreign shipyard/production controls and missing exploration
by land units. Those failures prevent release acceptance of V3. The earlier
0.6.0-dev.1 r8 smoothness and visibility sample remains historical evidence;
it does not validate the new charted-world behavior.

The original `wv63` checkpoint was verified byte-for-byte in its automatic
backup. The current named `wv63` checkpoint contains newer exploration history.

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

## In-game world options

The menu has **World**, **Players**, **Starting**, **Presets**, **Islands** and
**Visibility** pages. The Starting page heading remains **Starting options**.
The preview area and seed stay visible; terra incognita covers the preview.
In addition to the existing world, island, fertility, fleet and opponent
choices, it provides:

- **Map seed:** enter a number from 0 to 4294967295, copy it, or regenerate to
  choose another seed. The same seed and the same settings reproduce the map
  preview with the same generator version.
- **Saved presets:** save and load every world setting, including the seed and
  preferred starting island, from inside the game.
- **Map visibility:** choose Unexplored (terra incognita), Geography revealed
  (the default), or Fully explored. Unexplored covers uncharted land and sea
  with an opaque layer in the main view. Your ships and settlements chart nearby
  areas in eight-tile cells, which stay remembered. Deployed scouts and military
  units also provide sight. Scout exploration passed a bounded game check;
  other unit classes still need wider coverage. The minimap covers unknown areas uniformly,
  without island outlines. Geography revealed shows the terrain layout;
  Fully explored also unlocks island fertility information. Native island
  contact still controls native fertility and gameplay knowledge; it does not
  chart a whole island. Terra incognita also covers the setup preview, island details,
  start assignments and resource summaries; a preferred climate still works.
- **Enemy activity:** separately choose Strict line of sight (the default) or
  Reveal all activity. Strict vision uses 48 tiles around controllable human
  ships and owned settlements' building-anchor rectangles. Enemy ships and
  units disappear outside that range. Buildings remain as last seen until
  you revisit them. Reveal all activity shows live activity in charted areas.
  Both choices keep uncharted areas covered when Unexplored is selected.
- **Exploration in saves:** saving or using Save As stores the charted areas
  and remembered buildings in that checkpoint. Loading an older save without
  exploration history begins around your current ships and settlements; it
  does not invent previously seen buildings. Compatible World Settings is
  required to restore this history in-game.
- **Island details:** with a revealed preview, click any island to inspect its climate, dimensions,
  estimated fertile land, planned crops and minerals, occupants and nearby
  resources. Inspection is separate from selecting a starting position;
  fertile land is not a guarantee of usable building space.
- **Starting position:** choose a climate, or inspect an ordinary island and
  choose **Use inspected island as preferred starting position**. Starting
  ships move to checked nearby water; no settlement is built automatically.
  Terra incognita uses an automatic island and prevents preview selection,
  while retaining the preferred-climate choice.
- **Balanced starts:** optionally choose comparable ordinary starting islands
  for the human and selected AI opponents, with close, balanced or distant
  separation. A revealed preview marks assigned starts and displays a summary;
  terra incognita withholds those details.
- **Resource distribution:** keep original assignments, favour spreading
  resources, or favour specialised regions. Redistribution preserves each
  resource's world count from the selected fertility level while respecting
  climate compatibility and actual ore occurrences. Individual islands can differ;
  saturated fertility or native/climate constraints can leave assignments unchanged.
- **Nearby basic resources:** optionally ensure grain, flax, potatoes, iron
  and salt near each player's start. This can add resources above fertility
  abundance. It does not guarantee every production chain in the Food overhaul.
- **Starting cargo:** customise tools, wood and food on each trade ship, with
  validation of separate 50-ton holds and the selected fleet's capacity.
- **Climate balance:** favour temperate, tropical or polar islands while
  retaining all six climates, enabled cultures and essential resources.
- **Layout style:** evenly spread islands, grouped archipelagos or a central
  ocean. Invalid combinations are blocked instead of overlapping islands.
- **Disasters:** enable or disable the inspected native endless-game option.

Presets belong to the managed game copy and remain when restoring original
game files. They require the matching generator fingerprint. Seed reuse is a
map-generation feature, not a promise that AI events or a played game will
unfold identically. Earlier presets remain on disk when a new generator
refuses their fingerprint; they are not silently converted. Compilation,
native fixtures and actual game acceptance are distinguished in the
[visibility validation record](docs/WORLD_VISIBILITY_VALIDATION.md). The new
batching candidate passed eight batch methods, 19 existing native methods,
independent source review, and 480 original-native cases comparing 20,352
exact output tuples. Its 72 isolated compiled-DLL scene stages cover both Food
selections, all six policies, 512/1024/2048 worlds and two seeds with AI zero;
these stages do not run Anno. All six builds passed independent review with
three identical runtimes per Food selection. The full suite completed 358
tests in 195.016 seconds: 353 passed and five Windows link-privilege tests were
skipped. Closed-game preservation retained all saves, presets and backups,
with the current autosave archived separately. The production installation/
restoration cycle passed and finished with World Settings enabled and Food
disabled. The updated shortcut's fresh automatic startup and `wc4` load passed.
The user's `wc5` display/save check and independent history certificate passed,
but camera-motion lag remains unresolved.

The preceding V4 suite completed 350 tests: 345 passed and five Windows
link-privilege tests were skipped. Its installer cycle, fresh `wc3` load,
`wc4` file checks and user-confirmed ownership/scout sample passed. Its
remaining lag is the reason for the new candidate. Broader gameplay and
long-session performance remain unverified.

The preceding V3 suite ran 322 tests: 317 passed and five Windows link-privilege
tests were skipped. Its 72 isolated compiled-DLL scene stages and three identical
builds per Food selection remain evidence for that build only. Its bounded
building-memory observations do not resolve the reported lag, foreign controls
or missing land-unit exploration. Fresh-world generation, restart/reload
persistence, broader interactions and long-session stability need separate
acceptance. Earlier fairness acceptance remains bound to
[its original build](docs/WORLD_FAIRNESS_VALIDATION.md).

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
place. The 488 imported legacy source files and 43 original compiled-source
inputs remain preserved; new native changes are staged separately.

The imported public World Settings specification remains explicitly a source
snapshot and refuses direct legacy installation or activation. The modular
installer instead prepares a local package from exact, pinned preserved inputs,
binds its game paths explicitly and records the relocation as new integration.
Historical live-test evidence stays bound to the frozen runtime; package
preparation does not count as a new game run.

The expanded menu has a controlled builder for each native profile:

```console
python tools/build_world_options_runtime.py --profile world-only --game PATH_TO_VERIFIED_STOCK_COPY
python tools/build_world_options_runtime.py --profile food-world --game PATH_TO_SUPPORTED_FOOD_SOURCE
```

It verifies the immutable imported inputs and exact History Edition native
preimages before compiling in ignored local staging. Publishing a local
runtime profile additionally requires `--publish` and the exact reviewed
canonical runtime and generator fingerprints. Building or publishing a
profile does not install it or launch Anno.

The preserved combined World Settings runtime can still be compiled into a local candidate
outside the game folder on Windows with the matching Zig 0.16.0 toolchain:

```console
python tools/build_world_runtime.py --tools PATH_TO_LOCAL_COMPILER_TOOLS
```

The tools directory must contain `ziglang/zig.exe` and its libraries. An ignored
`.local/toolchain/` installation is discovered automatically. The builder writes
only beneath `.local/builds/` and does not install, launch or patch Anno. Full
payload reconstruction from arbitrary new native builds and save compatibility
need their own integration work. Historical package validators accept their
reviewed frozen runtimes rather than automatically accepting rebuilt DLLs.
The current installer prepares the separate expanded-menu package and its
exact selected-profile runtime.

The preserved 0.3 independent stock-game runtime also retains its original
controlled builder:

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
