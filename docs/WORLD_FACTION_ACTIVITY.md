# Pirate activity and neutral trade

**0.7.0-dev.1 is installed on the managed World-only test copy.** The updated
desktop shortcut starts that build with automatic World Settings activation.
Startup, loading the older `wr2` world and creating/saving a new world passed.
The saved activity policies match the selections and survived both running-game
and fresh-process loading. Four merchant ships were recorded in `pa3`.
Pirates had not met the native town-development prerequisite; actual pirate
armament/raids and comparative merchant visit rates remain unverified. This is
an experimental development build.

The change adds three choices to the in-game **Players** page.
It leaves mine depletion and starting land units unchanged. Food remains an
independent installation choice.

| Choice | Rare / Weak | Normal | Frequent / Strong |
| --- | --- | --- | --- |
| Pirate reinforcement frequency | Twice the native waiting threshold | Native threshold | Half the native waiting threshold |
| Pirate strength, newly created ships | Half the native cannon count, minimum 4 | Native cannon count | Native count plus half, rounded up, maximum 18 |
| Neutral merchant trade frequency | Half the native trading-fleet target, rounded up | Native target | Twice the native target, maximum 10 |

**Known save/load limitation:** pirate strength applies to newly created ships.
The unchanged native loader caps existing pirate ships at **six cannons** when
loading a save, including native Normal armament above six. The selected policy
persists for future creations; above-cap equipment on an existing ship does
not. This build does not repair or override that engine rule. The same native
loader caps merchant ships at eight cannons; merchant activity settings do not
change equipment rules.

Pirates and Venetians retain their separate on/off checkboxes. Disabling a
faction disables its activity controls and preserves the selected values for
later use. Activity choices do not change the seed's islands, resources or
starting positions.

Frequency is subject to the native simulation. Pirates still use their fleet
limits, target selection and routes; changing their reinforcement threshold
does not guarantee an attack at a particular time. Neutral merchants follow
continuous routes rather than a fixed visit timer. Their available fleet grows
with qualifying settlements, so additional ships create more opportunities for
visits. Rare can equal Normal when the native target is already one ship.

Strength affects pirate ships created after the policy is bound. It does not
refill damaged ships or replace their existing armament. The verified native
pirate AI itself equips 4–18 cannons, despite the ordinary six-cannon equipment
capacity of the pirate hull. Normal preserves that existing native exception.

New presets use version 4. Only version 3 presets from the exact preceding
`ws6-e980d1f2563739790004625336b4a6f243c94fb0e00bc59bb80662f4546693ae`
generator can be migrated: their three new choices become Normal in memory.
Loading does not rewrite the old preset file. Other generator identities and
unrecognised formats remain refused.

## Implementation and persistence

The target is the inspected AMD64 History Edition, with separate verified
`CompLogic` and `CompLogicClassic` bindings. Classic-family offsets are proved
independently. New private AI payloads are derived from the exact existing
World-only and Food + World inputs; historical payloads and source remain
unchanged. The original game modules are not the deployment target.

The new choices persist in the native `COMP.SPEZFLAG` word of each matching
special controller. Native low flags are preserved. Pirate tag `0x5754` uses
bits 8–9 for frequency and 10–11 for strength; merchant tag `0x5755` uses bits
8–9 for frequency. Reserved bits and invalid choices are refused at the load
boundary. Untagged older controllers use Normal. A fresh start stages both
policies and verifies their destinations before committing them; pending menu
choices are not applied to a loaded save.

Native research established the pirate timing, creation arguments and fleet
limits in isolated instruction fixtures. Merchant research established the
settlement-derived target and the controller's 40-ship storage limit. These
are automated engine checks, not observations of long-running raids or trade.

The existing renderer, chart format, mineral-symbol repair, ownership checks,
scout exploration and camera preparation remain unchanged. The added saved-tag
certificate runs at the Scene load boundary, before checkpoint publication;
it is not a drawing-time diagnostic. The native visibility transaction remains
28 components with the existing 173 engine edits. No new runtime export is
needed. Original game modules, the 488 imported source files and 43 original
compiled inputs are retained.

## Validation at this development stage

| Check | Result and scope |
| --- | --- |
| Broad automated regression run | 337 tests run in 266.315 seconds: 336 passed, one Windows symlink-privilege skip. |
| Portable package, installer, restoration and profile suites | 89 tests run in 110.147 seconds: 86 passed, three Windows symlink-privilege skips. These overlap the broad run and are not an additional aggregate test total. |
| Focused faction fixtures | 14 methods passed with no skips; independently repeated. Includes 112 native COMP save/token/load round trips, 680 Windows unwind instruction contexts, strict identities, malformed policies, protected destinations and the staged fresh-start/cancel lifecycle. Merchant-specific fixtures passed separately. These are isolated native fixtures. |
| Reproducible builds | Six independently checked builds: three identical runtime/AI results per Food selection, including the canonical published copies. Both profiles were built and packaged; only World-only was installed and run. |
| Installation and restoration | Closed-game cycle passed. It preserved all 49 existing named saves, 50 native saves, 114 SaveGame-root files, five existing presets and all 55 preceding backup generations. Two restored generations bring the preserved total to 57. The previous desktop shortcut was retained before updating it. |
| Automatic startup and older save | World-only automatic startup and loading `wr2` passed. This does not establish the new policies' save/reload behavior. |
| New in-game settings and save | `Activity1` was saved with all 32 version-4 preset fields matching the captured preview and generator. The new world loaded and was saved as `pa1`; its native faction words match Frequent / Strong / Frequent. |
| Saved geography and resources | All 24 saved islands match the captured preview's geometry, climates, crop bits and positive physical mineral masks. There are 101 mineral entries, 11 positive. This does not prove live harvesting or later depletion. |
| Later merchant spawning | `pa2` has two new Venetian trading ships, definition 1507; `pa3` has four. The new IDs were absent from earlier checkpoints. This shows spawning under Frequent, not a measured comparison of visit rates or trading volume. |
| Running-game load and resave | Loading `pa2` through the gear menu's Load screen passed: the world/shoreline returned without a black map, and runtime/engine guards passed. `pa2r` preserves both special-faction policy words. |
| Fresh-process load and resave | A fresh automatic launch loaded `pa2r`; the resulting `pa3` checkpoint retains all three activity choices. All 24 islands/resources still match `Activity1`, with a valid WSCHART extension. |
| Pirate eligibility and gameplay | No pirate ships were recorded. A read-only native census found one qualifying town against the engine's requirement of three before the reinforcement timer runs. Stronger creation armament and interval scaling are proved in native fixtures, not live raids. |
| Native equipment loading | 60 isolated native load/save cases confirm the existing six-cannon pirate and eight-cannon merchant clamps. These are retained limitations, not activity-policy loss. |

After installation, the 14 faction and nine merchant fixture methods passed
again with no skips. The faction fixture reconstructs its exact preceding
private AI inputs from pinned stock and frozen inputs, so installing the new
private modules does not invalidate future test runs. This repeats existing
checks; it is not additional gameplay evidence.

`Activity1` uses seed **123456789**, Big **1024 × 1024**, Mixed islands,
24 islands, spacing 0, three ordinary AI opponents, all eight cultures,
Pirates and Venetians. Pirate frequency is Frequent, pirate strength Strong
and neutral merchant frequency Frequent. In `pa1`, the native pirate policy
is `0x57540A00` and the Venetian merchant policy is `0x57550200`.
`pa2r` and the fresh-process `pa3` retain both words. Merchant IDs 4221 and 1415
are joined by 4347 and 5011 in `pa3`. The pirate controller retains native
`TYP=3`, no ships and an unused reinforcement clock. The census found only the
Venetian town eligible; the exact stock prerequisite runs before the timer.
Frequent does not force immediate pirate spawning in an undeveloped world.

This world selected **Geography revealed** and **Reveal all enemy activity**.
Its `WSCHART` extension validates with policy `0x5000`, generation 1 and empty
charted/observed history. It provides no new terra-incognita, strict sight or
exploration-retention evidence. Earlier visibility acceptance remains bound
to the builds and checks in the [historical validation record](WORLD_VISIBILITY_VALIDATION.md).

Food remains optional. The combined profile passed automated build/package
checks; Food was not installed or tested in actual gameplay for this change.

## Build and evidence identities

Generator: `ws6-6113d0190fad378ad46a5a36c921b7d70b437f31359c6836ba3dd74c585f3327`.
Settings are 132 bytes; preset version 4 contains 32 fields.

| Published artifact | SHA256 |
| --- | --- |
| World-only runtime | `027e6d0dcb4134fa591c0a36f1bcaea76d976bc3191b5fae1cdf6942c8becd16` |
| Food + World runtime | `b07e7a97335885bcb444be1dd043835b10280bef1dfb31d41c9bc880e8a73f6a` |
| World-only private CompLogic | `d4dbe1844b2b3e3c3eddcc22d55a62b50d3e0d3fafcdb51ee5781395b812bc68` |
| World-only private CompLogicClassic | `6227218f09e57db2211eb1afa11cb471d2dfd5228e7213fe2d54f717d6ef49d3` |
| Food + World private CompLogic | `fca39112873f10003abf617b2804ec8dc82cb5264655d59a65535b2b370c99fc` |
| Food + World private CompLogicClassic | `d49b4c360cbc02963d403108fb2c2205ee8a818f4b0ad15747614a3598b36888` |

The following records stay in ignored local development storage; game payloads,
saves and private evidence are not distributed through the public repository.

| Local evidence record | SHA256 |
| --- | --- |
| `faction-activity-v1-postpin-build-audit.json` | `29963773d84dd20aca64c60565d3ff88e24dca086c551a2eef1cf2d6a46465ad` |
| `world-faction-v1-narrow-cycle-20261111/result.json` | `2cc2f61909cd45fbbde6d591fd6efb0cbe1910a1b4c6e8fdc2e184ae7201ddd4` |
| `faction-activity-v1-portable-suites-e0e283f0096f40b78977494393301127/report.json` | `9db127457cdb411a9238b98ebb4635860a9cfcdf4ed41000d41f26a6798da152` |
| `world-faction-v1-pa1-native-policy-20261111.json` | `8af026091a0e0b5db4e71d649d728eca1fa8572430f3170ea381f1458910afea` |
| `world-faction-v1-pa1-disk-fbdb37dac5fc464e926a8c9b0aaa291e/archive-and-validation.json` | `33e4310f541ca43b48b339163cb84ecb180f8101593274838e191f8aacf4b6c6` |
| `world-faction-v1-pa2-native-policy-20261111.json` | `3b65d6e11862b4084cf99e5609cfd07d8ee356395218f7bcbc186a0dc80130e2` |
| `world-faction-v1-pa2-ingame-reload-20261111.json` | `40a71ae7532e788e272019ee9bd2646d73667f24573051f556f6fcd07a055170` |
| `world-faction-v1-pa3-disk-4e0a1f7338014ff194af0423e211d8b3/archive-and-validation.json` | `f978944c6fbdc27c30af82a6bb1362f8edf24e01f86735aa36e8f373f2a149a3` |
| `world-faction-v1-pirate-stock-preconditions-20261111.json` | `1bd00fda3846e90fd81e8e78162f77e47246e6300df798044cf9cad6e2488db1` |
| `faction-native-ship-head-clamp-c0c461f31aac46a4b3e5aae66fc29ba8.json` | `ae3351f6d6bbf5b9886e184e1f251827396ecfcf3f7c40e57b2554fa5dd07002` |
| `faction-activity-fixture-repeatability-da460f277b3845528b9beeed1cea4d49/result.json` | `af547bc001cd93c41ccdf228dd5c8eb90fde52441fce9f9c913444745e819e78` |
