# Feature catalogue

The overhaul offers feature checkboxes before installation, with world-specific
choices remaining in the in-game World Settings menu. The modular installer
checks and installs Food alone, World Settings alone, or both on an independent
managed copy, and restores its managed files to the verified vanilla baseline.
It does not support arbitrary combinations of future native modifications.

## Current and planned modules

| Module | Priority | Current status | Selection constraints |
| --- | --- | --- | --- |
| World Settings | Priority | Experimental 0.6.0-dev.2 adds charted land and sea, last-seen buildings and exploration history in saves; stock startup, sampled fog, building-memory/revisit observations and Save As file checks passed; restart/performance acceptance remains pending | Food is optional; each selection needs its exact local payload/runtime profile and marked copy; automated and actual game evidence remain separate |
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

Experimental 0.6.0-dev.2 adds charted land and sea, remembered buildings and
checkpoint-bound exploration history to the visibility choices, retaining
island inspection, balanced starts and resource distribution. The installer selects the feature
combination; it does not configure individual worlds. Six pages keep the
choices beside the persistent preview area: World, Players, Starting,
Presets, Islands and Visibility. Terra incognita covers that preview.

| Setting | Behavior and constraints |
| --- | --- |
| Map seed | Enter or copy an unsigned 32-bit seed, including zero. The same seed, generator fingerprint and settings reproduce the validated map preview. Regenerate chooses another displayed seed. |
| Saved presets | Save/load all 29 world choices, including seed, preferred island and both visibility choices, using bounded version-3 named files inside the managed copy. A different generator fingerprint or preceding schema is refused; older files are retained. |
| Island inspection | With a revealed preview, click any island, including native and special-faction islands, to inspect dimensions, climate, fertile-land estimate, planned crop/mineral masks, occupants, template ore/whale occurrences, nearby resources and starting eligibility. The estimate does not establish building or mine accessibility. |
| Starting position | Choose a climate or, with a revealed preview, inspect an ordinary uninhabited island and explicitly prefer it. Terra incognita disables manual island selection, clears a preceding preferred island and retains climate preferences. Starting ships move to checked nearby water; native/special islands and unsafe coastal starts are refused. Inspection alone does not move the starting fleet; no settlement is built automatically. |
| Balanced starts | Optionally allocate distinct ordinary islands to the human and selected ordinary AI opponents using fertile-land estimates and resource access. Close, balanced and distant separation choices apply to balanced starts. A preferred human island/climate remains a constraint. This does not improve AI strategy or increase the supported AI count. |
| Resource distribution | Original, Spread resources or Specialised regions. Spread favours geographic separation; Specialised regions favours grouping around a compatible seeded region. Both preserve each resource's world count from the selected fertility level, with native climate and occurrence limits. Per-island quantities can change; saturated fertility and native/climate constraints can leave modes with identical assignments. Native/special-faction resource assignments remain untouched. |
| Nearby basic resources | Optionally guarantee grain, flax, potatoes, iron and salt on ordinary islands within `max(128, worldSize / 4)` tiles of each actual participant's starting island. This can increase world abundance above fertility settings and is not a complete Food-overhaul diet guarantee. |
| Starting cargo | Custom tools, wood and food apply to each trade ship. Each distinct stack uses a 50-ton hold; small trade ships have four holds and big trade ships have eight. The choice must fit every trade ship in the fleet. Warship cannon equipment is retained. |
| Climate balance | Balanced, favour temperate (north/prairie), tropical (jungle/steppe) or polar (polar/tundra). Enabled cultures, all six climates and essential resources remain required. |
| Layout style | Evenly spread, grouped archipelagos or a central ocean. Geometry, native placement grid, ship reserves, border bounds and minimum spacing remain validated. An impossible choice fails rather than changing layout style silently. |
| Disasters | Enable/disable the inspected native endless-game disaster option while retaining the separately selected faction options. |
| Map visibility | Unexplored (terra incognita) covers uncharted land and sea with an opaque layer in the main view. Ships and settlements chart nearby eight-tile cells permanently. Unknown minimap areas are uniform and show no island outlines. Geography revealed is the default and shows the terrain layout. Fully explored also unlocks island fertility information. Native island contact remains separate fertility/gameplay knowledge and does not reveal a whole island's terrain. Terra incognita covers setup geometry, details, start badges and resource summaries. |
| Enemy activity | Strict line of sight (default) or Reveal all activity. Strict uses a fixed 48-tile radius around controllable human ships and owned settlement building-anchor rectangles. Enemy ships and units hide outside current sight. Buildings keep their last-seen appearance until revisited. Reveal all activity shows live activity within charted areas; Unexplored keeps unknown areas covered in both activity modes. |
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
results must not be relabelled as testing the new generator. Both native
profiles have three matching current builds and independent artifact review.
The current suite ran 322 tests: 317 passed and five Windows link-privilege
tests were skipped; 27 native/codec methods also passed. Seventy-two isolated
compiled-DLL scene stages cover both Food selections, all six visibility
combinations, 512/1024/2048 worlds and two seeds, with zero ordinary AI.
These stages do not execute Anno or certify rendering. The current production
installation/restoration cycle passed. The final V3 stock profile then
automatically started and loaded `wv63`, with continuous fog observed over
uncharted land and sea. The actual `wc1` Save As checkpoint passed independent
WSCHART file validation, including its chart data and remembered buildings.
The user confirmed that known buildings remain visible after sailing away and
that new development appears on return. The subsequent `wc2` checkpoint passed
independent history and native-world file checks. These are bounded observations
within the running game, rather than a fresh-process persistence test.
The original `wv63` checkpoint remains byte-identical in its automatic backup;
the current named `wv63` has newer exploration history. Fresh-world generation,
restart/reload persistence and performance acceptance remain
pending for 0.6.0-dev.2.

The [visibility validation record](WORLD_VISIBILITY_VALIDATION.md) keeps that
evidence separate from historical 0.6.0-dev.1 r8 World-only startup, certified
`wv63` reload and the user's smooth camera/visibility sample. That sample does
not validate the new charted-world implementation, broader interactions or
long-session behavior. Food + World actual visibility gameplay is not being
repeated at the user's request; its automated evidence is separate, and
another Food live run is not a publication requirement.

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

Deposit quantities/depletion, trader and Pirate behavior,
starting diplomacy and victory goals need their own native and save
investigations. These remain proposals for subsequent settings.
