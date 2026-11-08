# Working on Anno 1503 Grand Overhaul

Develop in this repository, outside the installed game. Preserve the installed
game, existing working copies, native saves, backups and released archives.
Use copies and explicit local paths for any integration or live game test.

## Evidence and compatibility

- Target Anno 1503 History Edition AMD64. Verify the exact executable/module
  hashes, preimages and structure layouts. Do not reuse classic-version patch
  addresses without proving that they apply.
- World Settings 0.11.0-dev.1, Food overhaul 0.5.0 and automatic launcher 1.0.0
  are experimental imported baselines. Preserve their source and test scope.
- Current World Settings activation requires Food 0.5 in the source game and
  the exact combined build on a marked independent copy. Keep that dependency
  explicit until decoupling has been implemented and tested.
- Eight ordinary AI players and eight LAN players are research targets, not
  established limits or implemented features. Flags, colors, owner IDs and
  special factions do not establish playable-player capacity.
- Separate automated checks, instruction/native fixtures, observed game runs,
  save comparisons and untested long-session behavior in all reports.

## Repository boundaries

- Track mod source, small patch descriptions, tests and contributor docs.
- Keep original/patched game DLLs, EXEs, complete native islands, game archives,
  saves, crash dumps, developer tools/caches and local machine paths untracked.
- `.local/` is the ignored local input, build and baseline store. It must never
  be staged or uploaded. Do not commit credentials, launch sessions or logs.
- `legacy/` holds imported source with its existing relative layout; new
  modular platform code belongs in `src/anno1503_overhaul/`.
- Do not silently claim that legacy build/install scripts are portable or
  that feature combinations work merely because a profile validates.

## Changes and tests

Keep optional feature dependencies explicit. Unavailable research features
cannot be enabled in an installation profile. Preserve restoration behavior
and refuse unknown versions or conflicting files rather than overwriting them.
Run relevant portable tests and repository-content checks before publishing.
Live engine activation requires a fresh, verified game process and its existing
guarded transaction; no retry after uncertain/partial activation.
