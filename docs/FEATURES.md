# Feature catalogue

The overhaul will offer optional modules before installation or launch, with
world-specific choices remaining in the in-game World Settings menu. The
current selector prepares and validates feature profiles. It does not yet
install an arbitrary combination of native modifications.

## Current and planned modules

| Module | Priority | Current status | Selection constraints |
| --- | --- | --- | --- |
| World Settings | Priority | Imported experimental 0.11.0-dev.1 source and preserved local tested package | Requires the current Food 0.5.0 baseline and exact combined marked copy |
| Food overhaul | Priority | Imported experimental 0.5.0 source and preserved local tested package | Keep its tested gameplay changes; standalone and combined AI evidence have different scope |
| Automatic launch | Supporting platform | Imported launcher 1.0.0 source; actual automatic startup/activation/menu test exists for the preserved build | Bound to the inspected World Settings package and supported native fingerprints |
| Smarter AI | Planned | Existing combined AI adaptations are a starting point, not a completed overhaul | Unavailable as a new independent module until implemented and validated |
| Local-host multiplayer | Priority research | No new transport, lobby or capacity implementation provided by this migration | Unavailable; establish engine/network feasibility and session limits first |
| Knowledge overhaul | Planned | Design and native-state investigation pending | Unavailable; establish education/research behavior, persistence and interactions first |

Unavailable modules must not be enabled merely by editing a profile file.
The UI should explain their status and the validator must enforce it too.

## World Settings baseline

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

Those observations remain bounded. They do not certify all combinations,
extended trade/combat, harvesting/mining access or long-session stability.
Earlier failed Huge builds and the limited different-runtime save migration
must remain distinguishable from accepted tests.

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

Useful follow-up candidates include reusable map seeds, saved presets,
starting-area selection, custom cargo, climate balance, layout styles and
disaster options. Deposit quantities/depletion, map visibility, trader and
Pirate behavior, starting diplomacy and victory goals need their own native
and save investigations. These are proposals rather than delivered settings.
