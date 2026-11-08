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
- Food and World Settings are independent feature choices. Do not silently
  select Food when World Settings is selected, or treat a profile flag as proof
  that the native feature set matches it.
- The preserved combined profile still uses its exact Food 0.5 startup inputs
  and runtime. World-only uses a separate stock native/data host and separately
  pinned runtime, engine plan and private World-policy AI modules. Never relax
  one profile's fingerprints to accept the other.
- World-only must preserve the checked vanilla diet, markets, data, archives,
  UI and host DLLs. Its native hooks and engine transaction apply in memory to
  the independent managed host; they are not Food compatibility patches.
- Keep the original 43 imported compiled inputs byte-exact. The World-only
  builder applies reviewed transformations only to newly staged copies. Keep
  compilation, native preimage proofs, startup and gameplay evidence separate.
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
World-only startup may relay the already verified normal Ubisoft launch context
to an identical independent executable. Keep arguments/environment in memory
only, never log their values, never synthesize authentication data, and close
only the exact fresh owned source main menu. Do not edit Ubisoft registration,
installation paths, security settings or the executable to make a copy launch.
