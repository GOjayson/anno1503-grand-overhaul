EXPERIMENTAL DEVELOPMENT: Anno 1503 Food + World Settings 0.11.0-dev.1

This copy adds Huge (2048 x 2048) worlds to the in-game World Settings menu.
Small256, Medium512 and Big1024 remain available. Huge is an experimental
History Edition AMD64 engine extension. It has four times the map area of
Big; long-session performance and stability need separate gameplay testing.
See VALIDATION.txt and developer/huge_world for the exact test scope.

All world options are chosen inside Anno before a new endless game. The
menu retains the exact map preview and Regenerate map button, balanced island
spacing, strict/lenient big islands, eight individual native cultures, Pirates,
the complete Venetian town, money/fleet controls and independent plant/mineral
fertility. AI opponents remain0..3 within the supported stock placeholder
range; this does not claim a universal engine maximum.

The combined installer retains the working Food0.5 changes. Original game
files, previous releases and existing backup contents must remain preserved.
The new engine appends island and ship-navigation grids while retaining
existing native field offsets and the eight-tile island grid. The renderer
uses an expanded visibility mask and128-column cache with matching native
stack, unwind and cleanup changes. Huge rendering recenters the drawing depth
without reducing native precision; smaller worlds retain their native depth.
It also updates the copied DLL's active Windows exception table. Classic executable patch
addresses are never used.

INSTALLATION
Close Anno. Restore the older installed World Settings revision using THAT
preserved package's RESTORE.cmd. Run this package's INSTALL.cmd against the
existing independently marked WorldSettings_Work/game_copy. CHECK.cmd verifies
the package/copy. A missing or ambiguous marked copy is refused; the original
installation is never used as a fallback.64-bit Python3.10+ is required.

Launch Anno normally through Ubisoft Connect. From its FIRST idle main menu,
before starting or loading ANY world, run ACTIVATE_WORLD_SETTINGS.cmd. This
activates only the exact inspected Food0.5 process and copied assets. All nine
existing hooks and173 engine edits are committed as one guarded transaction.
An existing world, unexpected instructions, partial patch or unsupported
architecture refuses activation. Starting a world also checks engine readiness.
Close Anno to remove all in-memory edits. Activate again in every new process,
including before loading a Huge save. Do not load Huge saves without this
engine extension. Do not mix development revisions in one running process.

RESTORATION
Close Anno and run this package's RESTORE.cmd. It restores the copied overlays
and removes only matching files introduced by this revision, using its own
WorldFoodMod_Backup_0_11_Dev1. Existing backup contents remain intact. Closing
Anno removes transient engine edits; original root DLLs are never overwritten.
Conflicting changed files are refused instead of being silently overwritten.

SETTINGS
Stock difficulty selects the original Easy/Medium/Hard scene/controller
profiles. World size, island size, fertility, starting money/fleet and AI war
policy are separate. Big(strict) retains the largest templates; Big(lenient)
can admit smaller matching templates. Islands are never scaled or resampled.
The Venetian island remains its genuine stock80x80 town in every size mode.
Impossible geometry, overlaps, missing essential resources and blocked ship
starts are rejected. Spacing is the minimum rectangle clearance in tiles.

Starting money:10k,30k,50k,80k,100k. Single ship retains stock ship/cargo.
War fleet:one big trade ship plus two small warships, six cannons on each.
Merchant fleet:one big and two small trade ships, each carrying40 tons of
tools and40 tons of wood. Fleets and world difficulty do not change island
geometry for the same seed and world choices.

AI war policy:Peaceful blocks new ordinary-AI declarations; Easy admits every
fourth eligible request, Medium every second, Hard every eligible request.
These filter native requests, rather than setting measured random war odds.
Existing conflict, defense and special actors keep their native handling.

Plant/mineral choices:Very fertile, Medium fertility, Low fertility, Mixed.
They control actual compatible availability, retaining native climate rules,
essential resources somewhere in the complete world, and actual mineral
persistence. They do not multiply harvest/mining speed or deposit quantities.

Automated native instruction checks, Python-host generation tests and actual
Anno runs are separate evidence. Historical reports retain their old runtime
fingerprints and do not certify a new engine build. A generated preview alone
does not prove native loading, navigation, rendering, save/reload or stability.

CURRENT 2048 TEST RESULTS
The corrected Huge engine passed a fresh 24-island world generation and a
save/reload in a separate Anno process. The saved terrain, crops, minerals,
ship identities, ownership, equipment and cargo passed strict comparison.
All three ordinary AI controllers were active; their ships were observed
moving beyond the old1024 boundary. All eight cultures, Pirates and the
complete Venetian town were present in the inspected Huge save.

The user confirmed the repaired h12 views and that fresh h13 looked correct.
Actual256,512 and1024 saved worlds also loaded and rendered under this engine,
with their complete native island grids matching their original saves.
Restoration returned the marked copy to its exact Food0.5 native files,
removed only the19 matching introduced files, and preserved backup contents.

This remains an experimental development release. Extended settlement,
trade, combat, harvest/mining and Food production were not replayed for this
engine revision. Keep existing saves and use separate test save names.
