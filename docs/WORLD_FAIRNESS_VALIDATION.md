# Island inspection, fair starts and resource distribution validation

This record covers **0.5.0-dev.1**, reviewed on **8 November 2026**. The seven
earlier expanded-menu features
retain their own [0.4 validation record](WORLD_OPTIONS_VALIDATION.md). Earlier
compilation, installation, live gameplay and save/reload observations do not
certify the new generator.

## Feature contract

All world choices remain inside Anno. The installer independently selects
World Settings with or without the Food overhaul; it does not configure worlds.
The five menu pages are **World**, **Players**, **Starting options**, **Presets**
and **Islands**, beside the persistent seed and exact cached map preview.

| Addition | Intended behavior and limits |
| --- | --- |
| Island inspection | Clicking any island inspects it without changing the starting position. Details include climate, dimensions, catalogue fertile-land estimate, planned crop/mineral availability, inhabitants/special faction, template ore and whale occurrences, starting eligibility/assignment and nearby ordinary-island resources. |
| Area estimate | The catalogue's `fertileLand` count is an estimate of fertile terrain. It is not a guarantee of buildable area, coastal accessibility, a valid building footprint or accessible mines. |
| Explicit preferred start | A separate button prefers an eligible inspected ordinary island. Native, Pirate and Venetian islands remain inspectable but cannot be selected as starts. Existing climate preference and safe coastal-water checks remain. |
| Balanced starts | Optionally assign distinct ordinary starting islands to the human and selected AI opponents. Compare fertile-land estimates and resources, honour a preferred human island/climate, and apply close/balanced/distant separation. Refuse impossible requests rather than silently reducing requirements. |
| Resource distribution | Original distribution, Spread resources and Specialised regions relocate planned resource assignments within native climate support and actual ore-occurrence capacity. Spread separates each resource; Specialised regions groups each around a compatible seeded region. Both preserve each resource's world count from the selected fertility level; per-island availability can change. Native/special-faction assignments stay untouched. Essential world coverage remains required. |
| Optional nearby basics | Grain, flax, potatoes, iron and salt must be present on ordinary islands within `max(128, worldSize / 4)` tiles of each participant's starting island. Crop access counts fertile terrain rather than polar raw flags. This can add resources above the fertility-selected world abundance. It is not a promise that every Food-overhaul production chain is local. |
| Preview markers | A white outline identifies inspection; **S** marks the human start and **1–3** mark assigned ordinary AI starts. Pirate/Venetian badges remain distinct. |
| Presets | Version-2 bounded text includes all 27 settings and the new generator identity. Older preset files are preserved and refused when their fingerprint/schema differs. No silent migration is performed. |

Fair starts use the existing inspected ordinary-player range. They do not
increase player capacity or implement the planned smarter-AI module. Native
special-faction roles, Food changes, checked vanilla behavior in World-only,
original installed files, backups and saves remain preservation requirements.

## Source and ABI

The existing 96-byte settings structure gains four signed 32-bit fields:
`fairStarts`, `startSeparation`, `resourceDistribution`, `guaranteeBasics`.
The original prefix remains at the same offsets. The new settings size is
**112 bytes**; the exact cached preview is **5248 bytes** with the unchanged
40-byte island rows. The island-details read-only query is a separate bounded
44-byte structure, so inspection does not mutate the cached plan.

Defaults keep the original start/resource policy: fair starts disabled,
balanced separation selected but inactive, original distribution, nearby-basic
guarantee disabled. The authored source is staged onto copies of the immutable
43 imported compiled inputs. Stock and Food builds retain their separate
native preimages and runtime identities.

## Reviewed native builds

The current generator fingerprint is
`ws5-9763e325b88da3c2e60d75368626888fe5effa444071076c45bb3683dada1808`.

| Native profile | Canonical SHA-256 |
| --- | --- |
| World only | `3ae9e17383ff7aa4405fe0a39274f81e443d545f10582c395cc97c138554f371` |
| Food and World | `f2eab1d1a9dcb7aaa35f2e28b277101e94d0b538a9b77583f59d031cad1d381b` |

Both profiles compiled three times from separate staging directories to
byte-identical outputs with the reviewed Zig 0.16.0 toolchain. The third
builds published the matching local runtime profiles. Every build checked
the original 43 compiled-source fingerprints, exact profile-specific AMD64
executable/module fingerprints, all nine native hook preimages, all 173 engine
edit preimages and both chained-unwind parent records. The required exports,
new settings/snapshot schema and canonical metadata also passed.

An independent read-only staging audit exercised both native profile recipes:
112-byte settings, 5248-byte previews, all 27 preset fields, unchanged imported
source dictionaries and resource/start/details helper ordering matched the
shared contract. The separate island-details structure is 44 bytes and its
query requires the caller's size to match; a non-ready or invalid-index request
is refused without modifying the output.

These are compilation and native-input proofs. No game is executed by the
builder or staging audit, and publishing a runtime profile does not install it.

## Evidence status

Replace pending entries only with evidence from this build.

| Layer | Current scope |
| --- | --- |
| Menu/parser fixtures | Ten targeted tests passed for source staging, all-field version-2 round trips, unsigned seeds, malformed/truncated/foreign presets, safe preset names and the native island-description formatter. |
| Shared settings, planner and start policy | Public suite passed: 216 tests run, 211 passed and five Windows symlink-privilege skips. Native fixtures include fair starts and eight resource-policy tests. |
| Exact AMD64 native compilation | Both profiles compiled three times with identical canonical hashes; exact profile-specific native preimages and frozen source checks passed. |
| Full compiled-runtime API fixtures | Both real compiled profiles passed the 192-profile-plan distribution matrix, repeatability/detail comparisons, fair human starts, feasible/infeasible basic guarantees and 60 actual scene-serialization checks outside Anno. AI count was zero; no activation guard was bypassed. |
| Installer/restoration | Production closed-game restoration/install cycle passed for both 0.5 profiles, preserving all checked source inputs, existing saves/presets and historical backup generations; see the separate lifecycle scope below. |
| Actual game UI/world/save/restart | Pending for this build and each Food selection. |
| Extended gameplay | Not established by short menu, generation or save checks. |

The menu/parser fixtures execute native C outside Anno. They do not establish
actual in-game layout, control focus, loaded-world assignments, mining access,
Food economy behavior or live AI settlement.

## Automated checks and native policy fixtures

The full public suite completed in 173.910 seconds on Windows: **216 tests
run, 211 passed, five skipped** because Windows symlink creation privileges
were unavailable. The private complete log is retained locally. The suite
includes existing package/profile/copy/restoration refusal checks, new ABI
validation, native scene-owner evidence and the new settings policies.

Eight resource tests execute native C against the real reviewed template
catalogue. They check deterministic modes, world resource counts, unchanged
geometry and native/special islands, geographic clustering/spreading, guarantees
for each selected player, full-slot mineral swaps, impossible-request rollback,
polar nonplant exclusions and invalid native-capacity rejection. Fair-start
fixtures check distinct safe deterministic starts, preferred-human constraints,
inactive-owner preservation, infeasible land/separation refusal and summaries.
Those policy fixtures model their scene/resource boundaries outside the game;
their results do not establish native AI settlement or simulation behavior.

The local C fixtures used the existing reviewed Zig toolchain. No independent
GCC/Clang installation was available on PATH and no Linux fixture execution is
claimed here. Repository privacy/content checks passed for 569 public files;
the scoped whitespace check also passed. Licensed native inputs, copied island
assets, saves and complete private reports remain ignored and unuploaded.

## Actual compiled DLL APIs outside Anno

Both reviewed DLLs were loaded by an isolated fixture process and their real
planner, cached-preview, island-details, summary and scene-staging exports were
called. The private report records these results separately from game runs:

- **96 shared distribution scenarios / 192 profile plans**, each checked for
  exact repeatability and cross-profile identity. The matrix covers all three
  resource modes, four fertility levels, seeds zero and `4294967295`, worlds
  512/1024/2048 and several layout/climate combinations. Resource counts,
  geometry and the 44-byte island details matched between profiles.
- **12 fair human-start scenarios**, including explicit preferred-island
  application without changing geometry. This matrix uses zero AI opponents;
  active native AI owner allocation remains a separate game check.
- **12 feasible nearby-basic cases** and **12 infeasible nearby-basic
  refusals** across the two profiles. The feasible cases independently
  established native grain/flax/potatoes/iron/salt availability within the
  reported island-edge radius. Incompatible preferred starts were also refused.
- **60 scene stages** serialized the exact cached preview into real native
  scene chunks. Island links and expected human ship positions matched. A
  change to any new settings field was refused before creating a scene file;
  staged-state details queries were refused without output mutation.
- Bounds and structure-size guards on the details API rejected invalid calls
  without changing caller output.

The fixture used 111 verified copies of island/dummy assets in a separate
ignored directory and verified them unchanged afterwards. It did not write
the managed working copy, start Anno, install/activate hooks, bypass AI
configuration guards, load a native world or exercise the game UI. This proves
real compiled policy/serialization behavior, not an actual game session or
the complete Food economy.

## Isolated multi-player-count policy fixture

A separate private fixture copied the exact staged planner prefix into an
isolated native test library. It deliberately substituted the **AI
configuration gate only inside that fixture** so selected-player policies
could be inspected without starting Anno. The published DLLs, native
activation guards and original sources remained unchanged. Eighteen zero-AI
cases matched the actual reviewed DLL's plans exactly, bounding the effect of
that fixture substitution.

The fixture found feasible settings at seed `123456789` for a stock profile
with three selected AI opponents and Spread resources, and a combined profile
with one selected AI opponent, Specialised regions and guaranteed basics. It
recorded the expected starts, positions, resource masks and balance summary
for later comparison. These are **policy predictions**. They do not prove
native controller allocation, activation, game loading, live AI behavior or
save/reload compatibility with active opponents.

## Production installer/restoration cycle

With Anno closed, the high-level production installer completed this sequence
on the independent managed copy: restore the accepted 0.4 journal, install and
restore World-only 0.5, install and restore Food + World 0.5, then reinstall
World-only 0.5. Both fresh prepared packages matched the current native runtime,
generator and Food selection. Reapplying each installed selection passed the
production exact-no-op check.

The stock installation changed 19 managed files; the combined installation
changed 41. Every restoration returned the 23 inspected stock inputs and
removed the 19 introduced payload files. The original installed source's 23
checked native/data inputs, its 297 historical backup files, all **32 existing
native saves**, both older preset files and all **12 older restoration
generations** remained byte-exact. Three new restored generations were retained,
giving 15 previous generations at the end. The legacy source inventory and
all 43 compiled inputs also remained unchanged.

The cycle used the production closed-game guard without substituting or
bypassing it. It did not launch Anno, operate its UI, write process memory or
terminate processes. These are real installation/restoration comparisons,
separate from actual in-game acceptance of the new options. The existing
presets' older schema/generator identities remain preserved on disk; they are
not silently converted by installation or restoration.

## Acceptance checks to complete

1. Verify immutable source closure and exact AMD64 executable/module
   architecture, native hook/engine preimages and unwind metadata separately
   for the World-only and Food + World profiles. Compile reproducibly and bind
   packages to the exact reviewed runtime, generator and snapshot identities.
2. Exercise deterministic seeds across distribution modes, fertility choices,
   climates, supported world sizes and active-player counts. Independently
   check world/resource coverage, ore-slot capacity, per-resource world counts,
   spacing, non-overlap and border limits.
3. Check fair starts with each separation mode, preferred human island/climate,
   one to four actual participants and impossible combinations. Verify distinct
   ordinary islands, measured fairness constraints, coastal water and the
   exact selected-player/native-owner mapping.
4. Check the nearby-basic guarantee around every actual participant, including
   impossible iron/salt capacity cases. Confirm it may add only valid native
   resources and that disabled guarantees do not inflate fertility-selected
   world abundance.
5. Compare ready preview, staged scene, loaded world and a saved/reloaded world.
   Check human and ordinary-AI ship positions, resource masks, special factions,
   selected Food/stock diet and retained existing starting options.
6. Observe the five actual menu pages at the supported display scale. Inspect
   ordinary/native/Pirate/Venetian islands, confirm selection does not alter a
   preferred start, test the explicit start button and rejected starts, and
   exercise new settings through preset save/reload and a fresh process.
7. Restore/reinstall each supported selection on managed copies and compare
   original inputs, stock backups, all existing native saves and preset files.
   Keep every older backup generation and ensure the installed Ubisoft source
   is unchanged.

Do not infer long-session AI quality, harvesting/mining accessibility or Food
economy correctness merely from mask, scene or serializer checks.
