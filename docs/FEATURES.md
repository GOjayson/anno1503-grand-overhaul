# Feature catalogue

The overhaul offers feature checkboxes before installation, with world-specific
choices remaining in the in-game World Settings menu. The modular installer
checks and installs Food alone, World Settings alone, or both on an independent
managed copy, and restores its managed files to the verified vanilla baseline.
It does not support arbitrary combinations of future native modifications.

## Current and planned modules

| Module | Priority | Current status | Selection constraints |
| --- | --- | --- | --- |
| World Settings | Priority | Experimental 0.8.0-dev.4 installed; new island/disaster controls passed automated checks, world creation, in-game reload and fresh-process reload | Food is optional; each selection needs its exact local payload/runtime profile and marked copy; automated and actual game evidence remain separate |
| Food overhaul | Priority | Experimental 0.5.0 with Food-only installation inputs prepared from public source | Keep its gameplay changes; supported stock/recovery fingerprints are checked; standalone and combined AI evidence have different scope |
| Automatic launch | Supporting platform | Preserved combined launcher plus a guarded normal-client handoff for the independent host | Exact fresh process, main menu, executable, module and selected-profile checks; no startup-value logging or permanent client-registration changes |
| Smarter AI | Planned | Existing combined AI adaptations are a starting point, not a completed overhaul | Unavailable as a new independent module until implemented and validated |
| Local-host multiplayer | Priority research | No new transport, lobby or capacity implementation provided by this migration | Unavailable; establish engine/network feasibility and session limits first |
| Knowledge overhaul | Planned | Design and native-state investigation pending | Unavailable; establish education/research behavior, persistence and interactions first |

The installer provides **Check installation**, **Install selected features**
and **Restore original game**. The restore action affects its independent copy
and retains saves and backup generations. The installed Ubisoft source and
its prior backups are preserved as read-only inputs. See [installer details](INSTALLER.md).

Unavailable modules must not be enabled merely by editing a profile file.
The UI should explain their status and the validator must enforce it too.

## Expanded in-game World Settings

Development **0.8.0-dev.4** adds template/shape variety, optional quarter-turn
rotation of verified ordinary islands, minimum/maximum climate-group counts,
and individual native disaster switches and frequencies. The new Islands and
Disasters pages keep configuration inside Anno. Three reproducible builds per
Food selection passed. The full dev.2 suite passed 423 methods; all 145 targeted
dev.4 methods passed after the save-safe rotation and disaster-handoff repairs. Another 77
portable installer methods passed. Four symbolic-link methods were skipped
for Windows privileges. Six
isolated compiled-runtime scene stages also passed. Those stages do not run
Anno. World-only installation/restoration preserved every save, preset and all 61
preceding backup generations, retaining two further restored generations
for a total of 63. The
shortcut points to the updated build. Environment1 loaded in Anno with 24
islands, ten rotations and climate totals 6/8/10. Its three checkpoints retain
exact height vertices, texture cells, resources and disaster policy through
in-game loading and a full restart. The user reported correct terrain, rivers
and mineral symbols in each check. Long-session event rates and persistence of
already active disaster durations remain unverified. No Food gameplay run was
performed. See
[environment options](WORLD_ENVIRONMENT_OPTIONS.md) for behavior and limitations.

The preceding **0.7.0-dev.1** adds independent pirate reinforcement frequency,
new-ship strength and neutral merchant traffic controls to the Players page.
All default to Normal, and the Pirates/Venetians on/off choices remain
authoritative. The World-only build and updated automatic shortcut are installed.
Startup, loading the older `wr2` world, and creating/saving the new `pa1` world
passed. Its native saved policies match Frequent / Strong / Frequent. In-game
loading, fresh-process loading and policy retention passed through `pa2r` and
`pa3`, which contains four merchant ships. The native prerequisite had only one
of three required qualifying towns, so pirates had not spawned. Pirate
armament/raids and merchant visit frequency/trade volume remain unverified in
gameplay. The renderer,
chart format, mineral visibility, ownership, scout and camera paths retain
the preceding implementation. Food was not installed or tested in gameplay.
See [Pirate activity and neutral trade](WORLD_FACTION_ACTIVITY.md) for semantics,
automated evidence, preservation and the current live-test scope.

**Known limitation:** strength changes newly created pirate ships; the native
save loader still caps their armament at **six cannons**, including native
Normal counts above six. The selected policy persists, but this build does not
preserve above-cap equipment across loading.

The preceding 0.6.0-dev.9 connected the running game's separate View loader to
checkpoint restoration. Its accepted main-menu, in-game and restart load checks
remain historical evidence, with the mineral repair retained. The new activity
policies have separate in-game and restart save checks recorded above.

The earlier 0.6.0-dev.8 candidate repairs mineral symbols whose native parent is an
island, including icons over remembered mine buildings, and adds checkpoint
handling for the inspected in-game filename path. Native mineral
quantity/discovery rules remain authoritative; this does not add remembered
depletion quantities. Uncharted terrain stays covered. All 187 visibility tests
and independent review of six matching builds passed. World-only installation/
restoration passed, preserving saves, presets and all 51 preceding backups;
two restored generations give 53. The updated shortcut preserves its preceding
version. Fresh automatic startup and main-menu `wr1` loading passed; the user
accepted mineral symbols. At that stage, normal in-game loading still produced
a black map and the load repair was unfinished. The chart format, camera
preparation, ownership and scout rules are unchanged. Food gameplay is not being
retested.
The later 2048-world/50-island `wr1` investigation does not extend the preceding
1024-world camera acceptance.

The preceding 0.6.0-dev.7 candidate reduces more duplicate graphics and island memory
checks inside individual calls, retaining fresh fields and original fallbacks.
All 169 visibility tests, six matching builds and World-only installation/
restoration passed. Automatic startup and `wc6` loading passed, with smooth
camera movement and correct remembered towns/fog confirmed by the user. The new
`wc7` save retained exploration and world data and passed a fresh-process reload
with read-only native checks. This is bounded 1024-world evidence. Ownership, scouts,
observation times and the save ABI are unchanged.

The preceding 0.6.0-dev.6 candidate removes repeated protection queries within immediately
verified spans, preserving fresh asset/ownership checks and every observation.
Its 160 visibility methods, six matching builds and World-only installation/
restoration passed. Fresh automatic startup, `wc5` loading and read-only world
checks passed. The user confirmed correct remembered buildings/fog and improved
camera movement, but lag remains. The settings/save ABI is unchanged.

The preceding 0.6.0-dev.5 candidate adds a scalar island lookup index for each draw, exact
uniform fog spans and passive coarse-stage timing diagnostics. It preserves
the settings/save ABI and existing ownership, visibility and scout rules.
Independent source/fixture checks, all six builds and the full suite passed
(371 passed, five Windows link-privilege skips). Installation/restoration passed,
ending with World Settings on and Food off. The updated shortcut's automatic
startup and `wc5` load passed, with correct remembered buildings/fog confirmed
by the user. Camera movement remains unchanged or worse; the repair is incomplete.

The preceding 0.6.0-dev.4 candidate groups remembered-sprite capture within each draw
to reduce CPU work. It keeps the chart format, save ABI, exact remembered
times, visibility rules and existing hooks. The preceding dev.3 repair added
deployed scouts/military observers and ownership checks separate from drawing;
the user confirmed own/foreign controls and scout exploration in a bounded
sample, but lag remained. Island inspection, balanced starts and resource
distribution remain available. The installer selects the feature
combination; it does not configure individual worlds. Eight pages keep the
choices beside the persistent preview area: World, Players, Starting,
Presets, Details, Visibility, Islands and Disasters. Terra incognita covers
that preview.

| Setting | Behavior and constraints |
| --- | --- |
| Map seed | Enter or copy an unsigned 32-bit seed, including zero. The same seed, generator fingerprint and settings reproduce the validated map preview. Regenerate chooses another displayed seed. |
| Saved presets | Save/load all 43 world choices, including seed and the new environment controls, using bounded version-5 named files. Exact preceding version-4 (0.7) and version-3 (0.6.0-dev.9) identities migrate in memory with new choices defaulted; their files are preserved. Other identities/formats are refused. |
| Pirate reinforcement frequency | Rare doubles the native waiting threshold; Normal retains it; Frequent halves it. Native fleet caps, targets and routes still limit raids. Disabling Pirates disables this control. |
| Pirate strength | Weak reduces newly created pirates' cannon count, Normal retains the native count, and Strong increases it within the native pirate 4Ã¢â‚¬â€œ18 range. **The unchanged native loader caps existing pirate armament at six cannons on reload.** The policy persists for future creations. Existing ships are not refilled or re-equipped; disabling Pirates disables this control. |
| Neutral merchant trade frequency | Rare halves the native trading-fleet target with rounding up, Normal retains it, and Frequent doubles it up to 10. Routes, travel, ports and demand still determine visits; Rare can equal Normal for a one-ship target. Disabling Venetians disables this control. |
| Island inspection | With a revealed preview, click any island, including native and special-faction islands, to inspect dimensions, climate, fertile-land estimate, planned crop/mineral masks, occupants, template ore/whale occurrences, nearby resources and starting eligibility. The estimate does not establish building or mine accessibility. |
| Starting position | Choose a climate or, with a revealed preview, inspect an ordinary uninhabited island and explicitly prefer it. Terra incognita disables manual island selection, clears a preceding preferred island and retains climate preferences. Starting ships move to checked nearby water; native/special islands and unsafe coastal starts are refused. Inspection alone does not move the starting fleet; no settlement is built automatically. |
| Balanced starts | Optionally allocate distinct ordinary islands to the human and selected ordinary AI opponents using fertile-land estimates and resource access. Close, balanced and distant separation choices apply to balanced starts. A preferred human island/climate remains a constraint. This does not improve AI strategy or increase the supported AI count. |
| Resource distribution | Original, Spread resources or Specialised regions. Spread favours geographic separation; Specialised regions favours grouping around a compatible seeded region. Both preserve each resource's world count from the selected fertility level, with native climate and occurrence limits. Per-island quantities can change; saturated fertility and native/climate constraints can leave modes with identical assignments. Native/special-faction resource assignments remain untouched. |
| Nearby basic resources | Optionally guarantee grain, flax, potatoes, iron and salt on ordinary islands within `max(128, worldSize / 4)` tiles of each actual participant's starting island. This can increase world abundance above fertility settings and is not a complete Food-overhaul diet guarantee. |
| Starting cargo | Custom tools, wood and food apply to each trade ship. Each distinct stack uses a 50-ton hold; small trade ships have four holds and big trade ships have eight. The choice must fit every trade ship in the fleet. Warship cannon equipment is retained. |
| Climate balance | Balanced, favour temperate (north/prairie), tropical (jungle/steppe) or polar (polar/tundra). Enabled cultures, all six climates and essential resources remain required. |
| Climate limits | Minimum/maximum numbers for Polar, Temperate and Tropical groups, including culture and special-faction islands. Each group must permit two islands; impossible ranges are refused. |
| Island variety | Allow repeats, prefer unique templates or prefer varied coastal shapes, within existing constraints. Soft preferences can fall back; hard quotas and resources remain required. |
| Island rotation | Optional seeded quarter turns for 256 save-safe ordinary templates. Native towns, Pirates and Venetians keep their orientation. Original island files are preserved. |
| Layout style | Evenly spread, grouped archipelagos or a central ocean. Geometry, native placement grid, ship reserves, border bounds and minimum spacing remain validated. An impossible choice fails rather than changing layout style silently. |
| Disasters | Master enable plus individual Fire, Plague, Eruption, Earthquake and Drought checkboxes and Rare/Normal/Frequent choices. Fire/Plague keep Normal severity; the other three offer Mild/Normal/Severe for newly created events. Native prerequisites remain authoritative. |
| Map visibility | Unexplored (terra incognita) covers uncharted land and sea with an opaque layer in the main view. Ships and settlements chart nearby eight-tile cells permanently; dev.3 also includes deployed scouts and military units. Scout exploration passed a bounded game check; other classes need wider coverage. Unknown minimap areas are uniform and show no island outlines. Geography revealed is the default and shows the terrain layout. Fully explored also unlocks island fertility information. Native island contact remains separate fertility/gameplay knowledge and does not reveal a whole island's terrain. Terra incognita covers setup geometry, details, start badges and resource summaries. |
| Enemy activity | Strict line of sight (default) or Reveal all activity. Strict uses a fixed 48-tile radius around controllable human ships, owned settlement building-anchor rectangles and, in the dev.3 repair, eligible deployed scouts/military units. Enemy ships and units hide outside current sight. Buildings keep their last-seen appearance until revisited. Reveal all activity shows live activity within charted areas; Unexplored keeps unknown areas covered in both activity modes. |
| Exploration history | Save and Save As include charted areas and remembered buildings in an automatic WSCHART extension inside the native checkpoint. History is checked against that exact checkpoint before loading. Older saves without the extension begin around current observers, with no invented historical buildings. Configuration stays in-game and requires no user-edited sidecar. |

Preset files are user data and are retained during restoration. Changing
generation choices clears a stale preferred-island selection; loading a preset
restores its seed, settings and selected index together. The preview remains
the exact cached plan used by Start, including when terra incognita conceals
its display. Visibility policy and the new exploration history need the
compatible World Settings runtime on reload. History belongs to each saved
checkpoint, so loading an earlier save does not import later exploration.
Food remains an independent feature selection.

The original seven expanded options have separately recorded compilation,
native fixtures and actual World-only acceptance in
[World options validation](WORLD_OPTIONS_VALIDATION.md). The 0.5 additions have
their own [fairness validation record](WORLD_FAIRNESS_VALIDATION.md); older
results must not be relabelled as testing the new generator.

The dev.3 repair has passed 40 targeted visibility/performance/land-unit
methods, 43 hook/branch checks and six command-ownership methods. The supported
land observer adapter covers six native classes, with a 4,096-entry traversal
bound; that bound is not an engine recruitment limit. Dead, transported,
foreign-owned and malformed unit records are refused. The fixed 48-tile
activity range is unchanged. Drawing and remembering a foreign building do
not authorize production, food-sale or ship-queue changes.

The new dev.4 batching candidate passed eight batch methods, 19 existing
native methods, independent source review and 480 original-native cases
comparing 20,352 exact output tuples. Seventy-two isolated compiled-DLL scene
stages passed across both selections, all six policies, 512/1024/2048 worlds
and two seeds, with AI zero. They do not run Anno. All six builds passed independent review with three identical runtimes per
Food selection. The full suite completed 358 tests in 195.016 seconds: 353
passed and five Windows link-privilege tests were skipped. Closed-game
preservation and the production installation/restoration cycle passed. The
new World-only build is installed with its updated shortcut. Fresh automatic
startup, `wc4` loading and the user's remembered-town display/`wc5` save check
passed. Independent disk checks retained world geometry and exploration history.
Camera movement remains laggy while a stationary view is smooth; performance
is unresolved. CPU benchmarks of the specific capture preparation are not game FPS.

V4's full repair suite completed 350 tests: 345 passed and five Windows
link-privilege skips. Its production installer cycle, fresh automatic `wc3`
load, independent `wc4` history inspection and eligible native scout observer
check passed. The user confirmed foreign controls blocked, own controls
working and a deployed scout exploring land. Lag improved but remained
noticeable; broader performance acceptance did not pass. See the
[visibility validation record](WORLD_VISIBILITY_VALIDATION.md) for exact scope.

The preceding 0.6.0-dev.2 V3 profile had three matching builds per Food selection,
322 automated tests (317 passed, five Windows link-privilege skips), 27
native/codec methods, and 72 isolated compiled-DLL scene stages. Its closed-game
installer cycle passed. Its stock game loaded `wv63` with land/sea fog and
produced independently checked `wc1`, `wc2` and `wc3` checkpoints. The user
confirmed last-seen building retention and updates on returning, but then
reported lag, foreign shipyard/production controls and missing land-unit
exploration. V3 is not an accepted release; those observations and failures
remain separate from the dev.3 repair tests. The original `wv63` checkpoint
remains retained in its automatic backup.

Historical r8 smoothness/visibility checks do not validate charted-world
behavior, broader interactions or long sessions. Food + World actual gameplay
is not being repeated, as requested by the user; both-profile automated checks
remain separate evidence.

## Preserved World Settings baseline

The existing experimental implementation includes:

- World sizes 256, 512, 1024 and experimental 2048 square tiles.
- Island size selection, strict/lenient big islands, count and minimum spacing.
- Whole-map distribution, a preview and map regeneration before starting.
- Separate stock difficulty, starting money, fleet and AI war-policy choices.
- Zero to three ordinary AI opponents within the inspected stock placeholder
  range; this is not a verified hard engine maximum.
- Individual switches for eight native cultures, Pirates and Venetians,
  including the stock Venetian town.
- Separate plant and mineral availability settings.
- Rejection of overlapping/infeasible layouts and missing essential resources.

The accepted corrected Huge build passed actual fresh-world generation and a
strict save/reload comparison after restarting Anno. Smaller saved worlds were
also loaded and inspected under that engine. Automatic activation and opening
the World Settings preview were tested separately in the launcher work.

Those historical observations remain bounded and are not new tests of the
modular installer integration. They do not certify all combinations,
extended trade/combat, harvesting/mining access or long-session stability.
Earlier failed Huge builds and the limited different-runtime save migration
must remain distinguishable from accepted tests.

## Preserved 0.3 independent World Settings profile

Leaving Food unchecked selects a different native profile rather than merely
hiding a checkbox. The managed copy remains the actual executable host and
world data root. Inspected stock native DLLs, resident/food definitions,
building archives and UI images stay unchanged. The installed additions are
the World runtime, World-policy private AI modules and required World island
assets. Stock AI retains only the narrowly derived World-policy flag-preserver
hook, not the Food goods/index adaptations.

The independent runtime and its stock-bound 173-edit engine plan have separate
fingerprints from the preserved combined build. Food-only and combined paths
retain their existing Food changes. Restore before changing the installed
selection and use a fresh game launch. Profiles with Food disabled remain
disabled when saved and reloaded.

Compilation and native preimage proofs have passed for the independent profile.
Its packaged automatic startup, World Settings menu, new 1024 world, stock diet
inspection and fresh-process native save reload also passed with zero ordinary
AI selected. See [decoupling validation](DECOUPLING_VALIDATION.md) for the exact
scope and remaining active-AI, Huge and extended-gameplay coverage. Older
combined-world observations remain separate evidence.

## Food baseline

Preserve the existing five-food diet, market handling, production/need changes,
consumer-goods menus, artwork and visible prices. The imported Food 0.5.0
package remains an experimental baseline rather than a finished economy
overhaul.

Food development should verify production, consumption, resident supply,
market sales, starvation, trade, AI planning and save/reload together. A native
index guard or brief AI movement observation is not proof of a functioning AI
food economy. The standalone package's original no-AI guidance and the later
combined implementation's separately bounded checks both need to stay visible.

## AI capacity target

The requested target is up to **eight ordinary AI opponents**. That would be
additional to the human player and must be distinguished from a total
participant limit. No eight-AI implementation or verified limit is provided
here.

Before exposing a higher count, investigate controller allocation, native
owner/slot indexing, reserved special-faction roles, diplomacy, flags/UI,
scene generation, save data and simulation behavior. Tests must preserve
Pirates, Venetians and the native cultures while exercising the new ordinary
players. Count validation should reflect proven capacity at each stage.

Smarter AI also needs behavior goals independently of player count: reliable
food supply, settlement, resource planning, transport, trading and diplomacy.
Changing declaration frequency alone does not establish more capable AI.

## Local-host multiplayer target

The priority is a local host and joining human players. **Eight human players**
is a desired capacity to investigate, not a current supported number. The
number of available flags does not prove that capacity.

Research the native session/transport model, player roles, world initialization,
save/resume and synchronization first. A first implementation should prove a
small host/join session with matching features and stable simulation before
larger sessions are offered.

## Knowledge overhaul direction

Possible design work includes stronger roles for schools/universities,
education or research progression, and unlocks that connect to other modules.
The exact mechanic is still a design decision. Do not introduce a new resource
or assume an existing research-state representation without inspecting how it
is stored and used.

Any progression needs deterministic updates, save persistence, clear player
feedback, AI handling and multiplayer synchronization. Education, costs and
unlocks must remain compatible with the selected Food and economy rules.

## Further World Settings candidates

Deposit quantities/depletion, broader trader and Pirate strategy,
starting diplomacy and victory goals need their own native and save
investigations. These remain proposals for subsequent settings.
